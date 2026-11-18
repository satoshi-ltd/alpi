from __future__ import annotations

import json
import logging
import shutil
import tempfile
from pathlib import Path

import pytest

from alpi.host import connections, devices
from alpi.host import server as host_server
from alpi.host.connection_context import ConnectionContext


@pytest.fixture
def root(monkeypatch):
    d = Path(tempfile.mkdtemp(prefix="alp-host-actor-", dir="/tmp"))
    from alpi import home as home_mod
    monkeypatch.setattr(home_mod, "_ROOT", d)
    connections.invalidate_cache()
    devices._invalidate_cache()
    try:
        yield d
    finally:
        connections.invalidate_cache()
        devices._invalidate_cache()
        shutil.rmtree(d, ignore_errors=True)


async def _forbidden_lines(root: Path, caplog, method: str, params: dict) -> list[str]:
    srv = host_server.Server(home=root)
    sent: list[dict] = []

    async def send(payload):
        sent.append(payload)

    with caplog.at_level(logging.WARNING, logger="alpi.host.server"):
        await srv._handle_request(
            json.dumps({"id": "r", "method": method, "params": params}), send, require_token=True,
        )
    assert sent[0]["error"]["code"] == -32001
    return [r.getMessage() for r in caplog.records if r.getMessage().startswith("host forbidden:")]


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["host.peers.ping", "host.providers.ollama_models"])
async def test_a_member_refused_an_admin_verb_is_named_in_the_log(root: Path, caplog, method: str) -> None:
    connection, issued = connections.create_connection("phone", role="member")
    token = issued["token"]
    device_id = connection["devices"][0]["id"]

    lines = await _forbidden_lines(root, caplog, method, {"auth_token": token})

    assert lines == [
        f"host forbidden: {method} blocked for role=member "
        f"(connection={connection['id']} device={device_id})"
    ]
    assert token not in lines[0]
    assert token[-8:] not in lines[0]
    assert "phone" not in lines[0]


@pytest.mark.asyncio
async def test_a_local_only_verb_refused_over_remote_names_the_caller(root: Path, caplog) -> None:
    connection, issued = connections.create_connection("laptop", role="admin")

    lines = await _forbidden_lines(root, caplog, "host.network.status", {"auth_token": issued["token"]})

    assert lines == [
        "host forbidden: host.network.status blocked over remote transport "
        f"(connection={connection['id']} device={connection['devices'][0]['id']})"
    ]
    assert issued["token"] not in lines[0]


@pytest.mark.asyncio
async def test_a_local_only_config_key_refusal_names_the_caller(root: Path, caplog) -> None:
    connection, issued = connections.create_connection("laptop", role="admin")

    lines = await _forbidden_lines(
        root, caplog, "host.config.set_field",
        {"auth_token": issued["token"], "key": "alp.tcp_port", "value": 1},
    )

    assert lines == [
        "host forbidden: config key 'alp.tcp_port' is local-only "
        f"(connection={connection['id']} device={connection['devices'][0]['id']})"
    ]
    assert issued["token"] not in lines[0]


@pytest.mark.asyncio
async def test_scoped_profile_refusals_name_the_caller(root: Path, caplog) -> None:
    connection, issued = connections.create_connection("phone", role="member", profile_scope=["work"])
    actor = f"(connection={connection['id']} device={connection['devices'][0]['id']})"

    missing = await _forbidden_lines(root, caplog, "host.sessions.list", {"auth_token": issued["token"]})
    caplog.clear()
    outside = await _forbidden_lines(
        root, caplog, "host.sessions.list", {"auth_token": issued["token"], "profile": "home"},
    )

    assert missing == [f"host forbidden: host.sessions.list requires explicit profile for scoped token {actor}"]
    assert outside == [
        f"host forbidden: host.sessions.list blocked for token, profile='home' not in scope=['work'] {actor}"
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("params", [{}, {"profile": "home"}])
async def test_a_scoped_member_cannot_forge_a_line_through_the_method(root: Path, caplog, params: dict) -> None:
    connection, issued = connections.create_connection("phone", role="member", profile_scope=["work"])
    forged = (
        "host.peers.ping blocked for role=member (connection=conn_aaaaaaaaaaaaaaaa device=dev_bbbbbbbbbbbbbbbb)"
        "\nhost forbidden: x"
    )

    lines = await _forbidden_lines(root, caplog, forged, {"auth_token": issued["token"], **params})

    assert len(lines) == 1
    assert "\n" not in lines[0]
    assert "conn_aaaaaaaaaaaaaaaa" not in lines[0]
    assert lines[0].startswith("host forbidden: ? ")
    assert lines[0].endswith(f"(connection={connection['id']} device={connection['devices'][0]['id']})")


@pytest.mark.asyncio
async def test_a_legacy_device_is_named_without_its_token_suffix(root: Path, caplog) -> None:
    row = devices.add(label="seed", role="member")
    assert not connections.store_path().exists()

    lines = await _forbidden_lines(root, caplog, "host.peers.ping", {"auth_token": row["token"]})

    assert lines == ["host forbidden: host.peers.ping blocked for role=member (connection=legacy device=legacy)"]
    assert row["token"][-8:] not in lines[0]


def test_an_actor_id_cannot_forge_a_log_line() -> None:
    forged = ConnectionContext(connection_id="conn_1\nhost forbidden: fake", device_id=None, source="remote")

    assert host_server._actor(forged) == "connection=? device=-"
