from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest

from alpi.host import admin_audit
from alpi.host import connections
from alpi.host import server as host_server
from alpi.host.connection_context import ConnectionContext


@pytest.fixture(autouse=True)
def isolated_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from alpi import home

    monkeypatch.setattr(home, "_ROOT", tmp_path)
    connections.invalidate_cache()
    admin_audit._denied_seen.clear()
    yield tmp_path
    connections.invalidate_cache()
    admin_audit._denied_seen.clear()


async def _request(
    server: host_server.Server,
    body: dict,
    *,
    require_token: bool = False,
    bootstrap: bool = False,
) -> list[dict]:
    sent: list[dict] = []

    async def send(payload: dict) -> None:
        sent.append(payload)

    await server._handle_request(
        json.dumps(body), send, require_token=require_token, bootstrap=bootstrap,
    )
    return sent


def _entries(home: Path) -> list[dict]:
    return admin_audit.list_entries(home, limit=500)["entries"]


@pytest.mark.asyncio
async def test_successful_mutation_records_actor_target_and_no_values(tmp_path: Path) -> None:
    server = host_server.Server(home=tmp_path)

    async def set_field(_params, _server):
        return {"ok": True}

    server.register("host.config.set_field", set_field)
    secret = "sk-never-write-this"
    sent = await _request(server, {
        "id": "r",
        "method": "host.config.set_field",
        "params": {"profile": "atlas", "key": "api_key", "value": secret},
    })

    assert sent[0]["result"] == {"ok": True}
    entry = _entries(tmp_path)[0]
    assert entry["connection_id"] == "host"
    assert entry["connection_label"] == "Local host"
    assert entry["method"] == "host.config.set_field"
    assert entry["target"] == {"profile": "atlas", "key": "api_key"}
    assert entry["result"] == "success"
    raw = admin_audit.audit_path(tmp_path).read_text()
    assert secret not in raw
    assert "auth_token" not in raw
    assert stat.S_IMODE(admin_audit.audit_path(tmp_path).stat().st_mode) == 0o600


@pytest.mark.asyncio
async def test_remote_admin_identity_is_attributed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        host_server,
        "_check_token_meta",
        lambda _body: host_server.AuthMeta(
            True, "admin", [], "conn_owner", "dev_mac",
        ),
    )
    server = host_server.Server(home=tmp_path)

    async def revoke(_params, _server):
        return {"ok": True}

    server.register("host.connections.revoke_device", revoke)
    await _request(server, {
        "id": "r",
        "method": "host.connections.revoke_device",
        "params": {
            "auth_token": "permanent-secret",
            "connection_id": "conn_service",
            "device_id": "dev_node",
        },
    }, require_token=True)

    entry = _entries(tmp_path)[0]
    assert entry["connection_id"] == "conn_owner"
    assert entry["device_id"] == "dev_mac"
    assert entry["source"] == "remote"
    assert entry["target"] == {
        "connection_id": "conn_service", "device_id": "dev_node",
    }
    assert "permanent-secret" not in admin_audit.audit_path(tmp_path).read_text()


@pytest.mark.asyncio
async def test_authenticated_denials_are_recorded_once_per_window(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        host_server,
        "_check_token_meta",
        lambda _body: host_server.AuthMeta(
            True, "member", ["atlas"], "conn_customer", "dev_node",
        ),
    )
    server = host_server.Server(home=tmp_path)
    reached = 0

    async def admin_only(_params, _server):
        nonlocal reached
        reached += 1
        return {"ok": True}

    server.register("host.connections.delete", admin_only)
    body = {
        "id": "r",
        "method": "host.connections.delete",
        "params": {"auth_token": "secret", "connection_id": "conn_other"},
    }
    first = await _request(server, body, require_token=True)
    second = await _request(server, body, require_token=True)

    assert first[0]["error"]["code"] == -32001
    assert second[0]["error"]["code"] == -32001
    assert reached == 0
    entries = _entries(tmp_path)
    assert len(entries) == 1
    assert entries[0]["result"] == "denied"
    assert entries[0]["connection_id"] == "conn_customer"


def test_denial_budget_does_not_allow_unique_targets_to_fill_the_log(
    tmp_path: Path,
) -> None:
    context = ConnectionContext(
        connection_id="conn_customer",
        device_id="dev_node",
        source="remote",
        role="member",
    )
    for index in range(100):
        admin_audit.record_denied(
            tmp_path,
            "host.connections.delete",
            {"connection_id": f"conn_target_{index}"},
            context,
        )

    assert len(_entries(tmp_path)) == 1


@pytest.mark.asyncio
async def test_handler_error_records_only_stable_error_envelope(tmp_path: Path) -> None:
    server = host_server.Server(home=tmp_path)
    secret = "private failure detail"

    async def fail(_params, _server):
        raise host_server.HandlerError(
            -32602, "invalid-params", data={"detail": secret},
        )

    server.register("host.profile.delete", fail)
    await _request(server, {
        "id": "r", "method": "host.profile.delete", "params": {"profile": "atlas"},
    })

    entry = _entries(tmp_path)[0]
    assert entry["result"] == "error"
    assert entry["error_code"] == -32602
    assert entry["error"] == "invalid-params"
    assert secret not in admin_audit.audit_path(tmp_path).read_text()


@pytest.mark.asyncio
async def test_unsuccessful_result_is_not_recorded_as_success(tmp_path: Path) -> None:
    server = host_server.Server(home=tmp_path)

    async def unavailable(_params, _server):
        return {"ok": False}

    server.register("host.connections.cancel_pairing", unavailable)
    await _request(server, {
        "id": "r",
        "method": "host.connections.cancel_pairing",
        "params": {"connection_id": "conn_service", "pairing_id": "pair_missing"},
    })

    assert _entries(tmp_path)[0]["result"] == "error"


@pytest.mark.asyncio
async def test_pairing_exchange_attributes_new_device_without_storing_grant_or_token(
    tmp_path: Path,
) -> None:
    server = host_server.Server(home=tmp_path)

    async def exchange(_params, _server):
        return {
            "connection_id": "conn_service",
            "device_id": "dev_node",
            "token": "permanent-secret",
            "role": "member",
        }

    server.register("host.connections.exchange_pairing", exchange)
    sent = await _request(server, {
        "id": "r",
        "method": "host.connections.exchange_pairing",
        "params": {"pairing_token": "one-time-secret", "client": "node"},
    }, bootstrap=True)

    assert sent[0]["result"]["token"] == "permanent-secret"
    entry = _entries(tmp_path)[0]
    assert entry["connection_id"] == "conn_service"
    assert entry["device_id"] == "dev_node"
    assert entry["source"] == "bootstrap"
    assert entry["target"] == {
        "connection_id": "conn_service", "device_id": "dev_node", "role": "member",
    }
    raw = admin_audit.audit_path(tmp_path).read_text()
    assert "one-time-secret" not in raw
    assert "permanent-secret" not in raw


@pytest.mark.asyncio
async def test_failed_bootstrap_is_small_param_free_and_rate_limited(tmp_path: Path) -> None:
    server = host_server.Server(home=tmp_path)

    async def reject(_params, _server):
        raise host_server.HandlerError(-32011, "pairing-invalid")

    server.register("host.connections.exchange_pairing", reject)
    hostile = {key: "🧨" * 2_000 for key in (
        "name", "connection_id", "device_id", "pairing_id", "status", "role", "profiles",
    )}
    hostile["profiles"] = ["🧨" * 2_000 for _ in range(100)]
    hostile["pairing_token"] = "one-time-secret"
    body = {
        "id": "r",
        "method": "host.connections.exchange_pairing",
        "params": hostile,
    }

    for _ in range(50):
        await _request(server, body, bootstrap=True)

    entries = _entries(tmp_path)
    assert len(entries) == 1
    assert entries[0]["target"] == {}
    raw = admin_audit.audit_path(tmp_path).read_bytes()
    assert len(raw) <= admin_audit.MAX_RECORD_BYTES
    assert b"one-time-secret" not in raw


@pytest.mark.asyncio
async def test_auth_failure_for_sensitive_method_is_recorded_without_params(
    tmp_path: Path,
) -> None:
    server = host_server.Server(home=tmp_path)
    body = {
        "id": "r",
        "method": "host.providers.set_key",
        "params": {"auth_token": "revoked-secret", "key": "OPENAI_API_KEY", "value": "secret"},
    }

    for _ in range(20):
        response = await _request(server, body, require_token=True)
        assert response[0]["error"]["code"] == -32000

    entries = _entries(tmp_path)
    assert len(entries) == 1
    assert entries[0]["connection_id"] == "unauthenticated"
    assert entries[0]["source"] == "remote"
    assert entries[0]["result"] == "denied"
    assert entries[0]["error_code"] == -32000
    assert entries[0]["target"] == {}
    raw = admin_audit.audit_path(tmp_path).read_text()
    assert "revoked-secret" not in raw
    assert "OPENAI_API_KEY" not in raw


@pytest.mark.asyncio
async def test_unknown_auth_failures_share_one_global_budget(tmp_path: Path) -> None:
    server = host_server.Server(home=tmp_path)
    for method in (
        "host.version", "host.chat.send", "attacker.chosen.method",
    ):
        await _request(server, {
            "id": method,
            "method": method,
            "params": {"auth_token": f"invalid-{method}"},
        }, require_token=True)

    assert len(_entries(tmp_path)) == 1


@pytest.mark.asyncio
async def test_member_device_registration_is_audited_without_allowing_log_flood(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        host_server,
        "_check_token_meta",
        lambda _body: host_server.AuthMeta(
            True, "member", ["atlas"], "conn_customer", "dev_node",
        ),
    )
    server = host_server.Server(home=tmp_path)

    async def register(_params, _server):
        return {"ok": True}

    server.register("host.connections.register_device", register)
    body = {
        "id": "r",
        "method": "host.connections.register_device",
        "params": {
            "auth_token": "permanent-secret",
            "name": "Local host",
            "client": "node",
        },
    }

    for _ in range(20):
        await _request(server, body, require_token=True)

    entries = _entries(tmp_path)
    assert len(entries) == 1
    assert entries[0]["method"] == "host.connections.register_device"
    assert entries[0]["connection_id"] == "conn_customer"
    assert entries[0]["device_id"] == "dev_node"
    assert entries[0]["target"] == {"name": "Local host"}
    assert "permanent-secret" not in admin_audit.audit_path(tmp_path).read_text()


def test_query_filters_actor_or_target_and_paginates(tmp_path: Path) -> None:
    for index in range(4):
        context = ConnectionContext(
            connection_id=f"conn_{index % 2}",
            device_id=f"dev_{index}",
            source="remote",
            role="admin",
        )
        admin_audit._record(
            tmp_path,
            "host.connections.set_status",
            {"connection_id": f"target_{index % 2}", "status": "disabled"},
            {"result": {"ok": True}},
            context=context,
        )

    first = admin_audit.list_entries(tmp_path, limit=2)
    assert len(first["entries"]) == 2
    assert first["next_cursor"]
    second = admin_audit.list_entries(
        tmp_path, limit=2, cursor=first["next_cursor"],
    )
    assert len(second["entries"]) == 2
    assert not second["next_cursor"]
    filtered = admin_audit.list_entries(tmp_path, connection_id="target_1")
    assert len(filtered["entries"]) == 2


def test_reader_skips_a_non_utf8_line_without_losing_valid_history(tmp_path: Path) -> None:
    for profile in ("before", "after"):
        admin_audit._record(
            tmp_path,
            "host.profile.delete",
            {"profile": profile},
            {"result": {"ok": True}},
            context=ConnectionContext(),
        )
        if profile == "before":
            with admin_audit.audit_path(tmp_path).open("ab") as handle:
                handle.write(b"\xff\xfe corrupted\n")

    entries = admin_audit.list_entries(tmp_path, limit=10)["entries"]
    assert [entry["target"]["profile"] for entry in entries] == ["after", "before"]


def test_identity_snapshot_reuses_the_file_identity_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection, device = connections.create_connection("owner", role="admin")
    real_load = connections.load_store
    reads = 0

    def counted_load():
        nonlocal reads
        reads += 1
        return real_load()

    monkeypatch.setattr(connections, "load_store", counted_load)
    context = ConnectionContext(
        connection_id=connection["id"],
        device_id=device["id"],
        source="remote",
        role="admin",
    )
    for profile in ("atlas", "mira"):
        admin_audit._record(
            tmp_path,
            "host.profile.delete",
            {"profile": profile},
            {"result": {"ok": True}},
            context=context,
        )

    assert reads == 1


def test_rotation_caps_the_number_of_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(admin_audit, "MAX_BYTES", 700)
    for index in range(20):
        admin_audit._record(
            tmp_path,
            "host.profile.delete",
            {"profile": f"profile_{index}"},
            {"result": {"ok": True}},
            context=ConnectionContext(),
        )

    path = admin_audit.audit_path(tmp_path)
    assert path.exists()
    assert path.with_name(f"{path.name}.3").exists()
    assert not path.with_name(f"{path.name}.4").exists()
    assert all(candidate.stat().st_size <= admin_audit.MAX_BYTES for candidate in tmp_path.joinpath("logs").iterdir())


def test_chat_and_reads_are_not_audited() -> None:
    assert "host.chat.send" not in admin_audit.AUDITED_METHODS
    assert "host.connections.list" not in admin_audit.AUDITED_METHODS
    assert "host.audit.list" not in admin_audit.AUDITED_METHODS
    assert "host.connections.register_device" in admin_audit.AUDITED_METHODS


def test_audit_does_not_migrate_the_legacy_device_store(tmp_path: Path) -> None:
    from alpi.host import devices

    actor = devices.add(label="owner", role="admin")
    legacy_path = devices._store_path()

    assert admin_audit._record(
        tmp_path,
        "host.devices.promote",
        {"token_id": actor["token"][-8:]},
        {"result": {"ok": True, "role": "admin"}},
        context=ConnectionContext(
            connection_id=f"legacy_{actor['token'][-8:]}",
            device_id=f"legacy_{actor['token'][-8:]}",
            source="remote",
            role="admin",
        ),
    )
    assert legacy_path.exists()
    assert not connections.store_path().exists()


@pytest.mark.asyncio
async def test_audit_list_verb_is_paginated(tmp_path: Path) -> None:
    admin_audit._record(
        tmp_path,
        "host.profile.delete",
        {"profile": "atlas"},
        {"result": {"ok": True}},
        context=ConnectionContext(),
    )
    server = host_server.Server(home=tmp_path)
    admin_audit.register(server)

    response = await server._dispatch({
        "id": "r", "method": "host.audit.list", "params": {"limit": 1},
    })

    assert response["result"]["entries"][0]["target"]["profile"] == "atlas"
    assert response["result"]["next_cursor"] == ""


def test_audit_failure_never_breaks_the_admin_operation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(admin_audit, "_append", lambda *_args: (_ for _ in ()).throw(OSError("disk")))
    assert admin_audit.record_request(
        tmp_path,
        "host.profile.delete",
        {"profile": "atlas"},
        {"result": {"ok": True}},
    ) is False


def test_audited_methods_are_admin_local_or_pairing_only() -> None:
    allowed = host_server._ADMIN_METHODS | host_server._LOCAL_ONLY_METHODS | {
        "host.connections.exchange_pairing",
        "host.connections.register_device",
    }
    assert admin_audit.AUDITED_METHODS <= allowed
