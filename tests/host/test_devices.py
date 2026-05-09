"""Per-device pairing tokens — store, verbs, middleware."""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

import pytest

from alpi.host import devices
from alpi.host import server as host_server


@pytest.fixture
def short_tmp(monkeypatch):
    d = Path(tempfile.mkdtemp(prefix="alp-host-devs-", dir="/tmp"))
    from alpi import home as home_mod
    monkeypatch.setattr(home_mod, "_ROOT", d)
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_empty_store_loads_empty(short_tmp: Path) -> None:
    assert devices.load() == []


def test_add_persists(short_tmp: Path) -> None:
    row = devices.add(label="iPhone")
    loaded = devices.load()
    assert len(loaded) == 1
    assert loaded[0]["token"] == row["token"]
    assert loaded[0]["label"] == "iPhone"


def test_is_valid_round_trip(short_tmp: Path) -> None:
    row = devices.add(label="x")
    assert devices.is_valid(row["token"])
    assert not devices.is_valid("nope")
    assert not devices.is_valid("")


def test_revoke(short_tmp: Path) -> None:
    row = devices.add(label="x")
    assert devices.revoke(row["token"]) is True
    assert devices.is_valid(row["token"]) is False
    assert devices.revoke(row["token"]) is False  # idempotent


def test_touch_updates_last_seen(short_tmp: Path) -> None:
    row = devices.add(label="x")
    assert row["last_seen"] is None
    devices.touch(row["token"])
    assert devices.load()[0]["last_seen"] is not None


def test_rename(short_tmp: Path) -> None:
    row = devices.add(label="pending")
    devices.rename(row["token"], "iPhone")
    assert devices.load()[0]["label"] == "iPhone"


@pytest.mark.asyncio
async def test_list_verb_redacts_token(short_tmp: Path) -> None:
    row = devices.add(label="iPhone")
    srv = host_server.Server(home=short_tmp)
    devices.register(srv)
    resp = await srv._dispatch({
        "id": "r", "method": "host.devices.list", "params": {},
    })
    assert "result" in resp
    listed = resp["result"]["devices"]
    assert len(listed) == 1
    assert listed[0]["label"] == "iPhone"
    assert listed[0]["token_id"] == row["token"][-8:]
    assert "token" not in listed[0]


@pytest.mark.asyncio
async def test_generate_verb_returns_full_token(short_tmp: Path) -> None:
    srv = host_server.Server(home=short_tmp)
    devices.register(srv)
    resp = await srv._dispatch({
        "id": "r",
        "method": "host.devices.generate",
        "params": {"label": "iPad"},
    })
    assert resp["result"]["token"]
    assert resp["result"]["label"] == "iPad"
    assert len(devices.load()) == 1


@pytest.mark.asyncio
async def test_generate_verb_includes_network_info_when_available(
    short_tmp: Path, monkeypatch,
) -> None:
    from alpi.host import network as net

    monkeypatch.setattr(net, "resolve_host_endpoint", lambda h: ("100.64.0.1", "tailscale"))
    monkeypatch.setattr(net, "resolve_host_tcp_port", lambda h: 49200)
    monkeypatch.setattr(net, "resolve_host_pairing_name", lambda h: "alpi-mac")

    srv = host_server.Server(home=short_tmp)
    devices.register(srv)
    resp = await srv._dispatch({
        "id": "r",
        "method": "host.devices.generate",
        "params": {"label": "Phone"},
    })
    result = resp["result"]
    assert result["host"] == "100.64.0.1"
    assert result["scope"] == "tailscale"
    assert result["port"] == 49200
    assert result["pairing_name"] == "alpi-mac"


@pytest.mark.asyncio
async def test_generate_verb_omits_network_info_without_endpoint(
    short_tmp: Path, monkeypatch,
) -> None:
    from alpi.host import network as net

    monkeypatch.setattr(net, "resolve_host_endpoint", lambda h: None)

    srv = host_server.Server(home=short_tmp)
    devices.register(srv)
    resp = await srv._dispatch({
        "id": "r",
        "method": "host.devices.generate",
        "params": {"label": "Phone"},
    })
    result = resp["result"]
    assert result["token"]
    assert "host" not in result
    assert "port" not in result


@pytest.mark.asyncio
async def test_revoke_verb(short_tmp: Path) -> None:
    row = devices.add(label="x")
    srv = host_server.Server(home=short_tmp)
    devices.register(srv)
    resp = await srv._dispatch({
        "id": "r",
        "method": "host.devices.revoke",
        "params": {"token_id": row["token"][-8:]},
    })
    assert resp["result"]["ok"]
    assert devices.load() == []


@pytest.mark.asyncio
async def test_revoke_unknown_returns_not_found(short_tmp: Path) -> None:
    srv = host_server.Server(home=short_tmp)
    devices.register(srv)
    resp = await srv._dispatch({
        "id": "r",
        "method": "host.devices.revoke",
        "params": {"token_id": "deadbeef"},
    })
    assert resp["error"]["code"] == -32004


def test_check_token_open_when_store_empty(short_tmp: Path) -> None:
    """Migration: empty store = open. Tailscale-only setups keep
    working until first Add device."""
    from alpi.host.server import _check_token

    assert _check_token({"params": {}}) is True
    assert _check_token({"params": {"auth_token": "anything"}}) is True


def test_check_token_enforces_once_store_has_entries(short_tmp: Path) -> None:
    from alpi.host.server import _check_token

    row = devices.add(label="x")
    assert _check_token({"params": {}}) is False
    assert _check_token({"params": {"auth_token": "wrong"}}) is False
    assert _check_token({"params": {"auth_token": row["token"]}}) is True


def test_check_token_touches_last_seen_on_match(short_tmp: Path) -> None:
    from alpi.host.server import _check_token

    row = devices.add(label="x")
    assert devices.load()[0]["last_seen"] is None
    _check_token({"params": {"auth_token": row["token"]}})
    assert devices.load()[0]["last_seen"] is not None


@pytest.mark.asyncio
@pytest.mark.parametrize("method", [
    "host.devices.list",
    "host.devices.generate",
    "host.devices.revoke",
    "host.devices.rename",
])
async def test_devices_verbs_blocked_over_remote_transport(
    short_tmp: Path, method: str,
) -> None:
    """Pairing admin must never traverse a paired remote — a peer with
    a token must not be able to enumerate, mint, or kick devices on
    the host machine. The Unix socket is the only legitimate caller."""
    row = devices.add(label="seed")  # so token check is enforced
    srv = host_server.Server(home=short_tmp)
    devices.register(srv)

    sent: list[dict] = []

    async def send(payload):
        sent.append(payload)

    body = {
        "id": "r",
        "method": method,
        "params": {"auth_token": row["token"], "token_id": row["token"][-8:], "label": "x"},
    }
    await srv._handle_request(json.dumps(body), send, require_token=True)

    assert len(sent) == 1
    assert sent[0]["error"]["code"] == -32001
    assert sent[0]["error"]["message"] == "forbidden"


@pytest.mark.asyncio
async def test_devices_verbs_allowed_over_local_unix_transport(
    short_tmp: Path,
) -> None:
    """Same verb, but called locally (no token gate) succeeds — the
    block is transport-scoped, not method-scoped."""
    devices.add(label="seed")
    srv = host_server.Server(home=short_tmp)
    devices.register(srv)

    sent: list[dict] = []

    async def send(payload):
        sent.append(payload)

    body = {"id": "r", "method": "host.devices.list", "params": {}}
    await srv._handle_request(json.dumps(body), send, require_token=False)

    assert len(sent) == 1
    assert "result" in sent[0]
    assert "devices" in sent[0]["result"]
