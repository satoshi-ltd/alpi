from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml
import pytest

from alpi import cli, ledger, ui
from alpi.host import (
    _chat_events,
    chat,
    connections,
    handlers,
    sessions as host_sessions,
    usage as host_usage,
)
from alpi.host.connection_context import ConnectionContext, use
from alpi.session import Session, Turn
from alpi.host.server import HandlerError, Server


def _root(monkeypatch, tmp_path: Path) -> Path:
    from alpi import home
    monkeypatch.setattr(home, "_ROOT", tmp_path)
    connections.invalidate_cache()
    return tmp_path


def test_migrates_devices_store_without_rotating_tokens(monkeypatch, tmp_path: Path) -> None:
    root = _root(monkeypatch, tmp_path)
    legacy = root / "host" / "devices.yaml"
    legacy.parent.mkdir(parents=True)
    legacy.write_text(yaml.safe_dump([{
        "token": "legacy-token",
        "label": "Javi MacBook",
        "created": 10,
        "last_seen": 20,
        "role": "member",
        "profile_scope": ["atlas"],
    }]))

    rows = connections.list_connections()

    assert len(rows) == 1
    assert rows[0]["label"] == "Javi MacBook"
    assert rows[0]["devices"][0]["token"] == "legacy-token"
    assert rows[0]["devices"][0]["client"] == "unknown"
    assert connections.authenticate("legacy-token").connection_id == rows[0]["id"]
    assert connections.store_path().exists()
    assert not legacy.exists()
    assert legacy.with_name("devices.yaml.migrated").exists()


def test_migration_keeps_an_existing_backup_and_moves_the_live_store(
    monkeypatch, tmp_path: Path,
) -> None:
    root = _root(monkeypatch, tmp_path)
    legacy = root / "host" / "devices.yaml"
    legacy.parent.mkdir(parents=True)
    legacy.write_text(yaml.safe_dump([{"token": "live", "label": "Live"}]))
    legacy.with_name("devices.yaml.migrated").write_text("older backup")

    connections.load_store()

    assert not legacy.exists()
    assert legacy.with_name("devices.yaml.migrated").read_text() == "older backup"
    assert len(list(legacy.parent.glob("devices.yaml.migrated.*"))) == 1


def test_connection_can_hold_multiple_independently_revocable_devices(monkeypatch, tmp_path: Path) -> None:
    _root(monkeypatch, tmp_path)
    row, first = connections.create_connection("Javi", profile_scope=["atlas"])
    _, second = connections.add_device(row["id"])

    assert connections.authenticate(first["token"]).connection_id == row["id"]
    assert connections.authenticate(second["token"]).connection_id == row["id"]

    assert connections.revoke_device(row["id"], second["id"])
    assert connections.authenticate(second["token"]).valid is False
    assert connections.authenticate(first["token"]).valid is True
    assert [device["id"] for device in connections.public_connection(
        connections.list_connections()[0],
    )["devices"]] == [first["id"]]


def test_disabling_connection_blocks_every_device(monkeypatch, tmp_path: Path) -> None:
    _root(monkeypatch, tmp_path)
    row, first = connections.create_connection("Javi")
    _, second = connections.add_device(row["id"])

    assert connections.update_connection(row["id"], status="disabled")

    first_auth = connections.authenticate(first["token"])
    second_auth = connections.authenticate(second["token"])

    assert first_auth.valid is False
    assert first_auth.reason == "connection-disabled"
    assert first_auth.connection_id == row["id"]
    assert first_auth.device_id == first["id"]
    assert second_auth.valid is False
    assert second_auth.reason == "connection-disabled"


@pytest.mark.asyncio
async def test_update_rejects_an_invalid_role(monkeypatch, tmp_path: Path) -> None:
    _root(monkeypatch, tmp_path)
    row, _device = connections.create_connection("Javi")

    with pytest.raises(HandlerError) as error:
        await connections._update({
            "connection_id": row["id"],
            "role": "owner",
        }, Server(tmp_path))

    assert error.value.code == -32602
    assert connections.list_connections()[0]["role"] == "member"


@pytest.mark.asyncio
async def test_update_rejects_an_empty_label(monkeypatch, tmp_path: Path) -> None:
    _root(monkeypatch, tmp_path)
    row, device = connections.create_connection("Javi")

    assert connections.update_connection(row["id"], label="  ") is False
    with pytest.raises(HandlerError) as update_error:
        await connections._update({
            "connection_id": row["id"],
            "label": "  ",
        }, Server(tmp_path))
    with pytest.raises(HandlerError) as legacy_error:
        await connections._legacy_rename({
            "token_id": device["token_id"],
            "label": "",
        }, Server(tmp_path))

    assert update_error.value.code == -32602
    assert legacy_error.value.code == -32602
    assert connections.list_connections()[0]["label"] == "Javi"


@pytest.mark.asyncio
async def test_pairing_preflight_does_not_create_orphan_credentials(
    monkeypatch, tmp_path: Path,
) -> None:
    from alpi.host import network

    _root(monkeypatch, tmp_path)
    row, _device = connections.create_connection("Existing")
    monkeypatch.setattr(network, "resolve_host_endpoint", lambda _home: None)

    with pytest.raises(HandlerError) as create_error:
        await connections._create({"label": "Duplicate"}, Server(tmp_path))
    with pytest.raises(HandlerError) as add_error:
        await connections._add_device({"connection_id": row["id"]}, Server(tmp_path))

    stored = connections.list_connections()
    assert create_error.value.message == "no-advertised-host"
    assert add_error.value.message == "no-advertised-host"
    assert [item["label"] for item in stored] == ["Existing"]
    assert len(stored[0]["devices"]) == 1


@pytest.mark.asyncio
async def test_legacy_pairing_cancel_removes_an_unused_connection(
    monkeypatch, tmp_path: Path,
) -> None:
    _root(monkeypatch, tmp_path)
    row, device = connections.create_connection("Cancelled")

    result = await connections._legacy_revoke(
        {"token_id": device["token_id"]}, Server(tmp_path),
    )

    assert result == {"ok": True, "existed": True}
    assert connections.list_connections() == []
    assert not connections.authenticate(device["token"]).valid


def test_register_device_only_writes_changed_metadata(monkeypatch, tmp_path: Path) -> None:
    _root(monkeypatch, tmp_path)
    _row, device = connections.create_connection("Javi")
    writes = 0
    real_write = connections._atomic_write

    def counted_write(data):
        nonlocal writes
        writes += 1
        real_write(data)

    monkeypatch.setattr(connections, "_atomic_write", counted_write)

    assert connections.register_device(
        device["token"], client="desktop", name="MacBook", app_version="0.4.39",
    )
    assert writes == 1
    assert connections.register_device(
        device["token"], client="desktop", name="MacBook", app_version="0.4.39",
    )
    assert writes == 1


def test_concurrent_authentication_coalesces_last_seen_write(
    monkeypatch, tmp_path: Path,
) -> None:
    _root(monkeypatch, tmp_path)
    _row, device = connections.create_connection("Javi")
    writes = 0
    real_write = connections._atomic_write

    def counted_write(data):
        nonlocal writes
        writes += 1
        real_write(data)

    monkeypatch.setattr(connections, "_atomic_write", counted_write)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(
            lambda _index: connections.authenticate(device["token"]),
            range(16),
        ))

    assert all(result.valid for result in results)
    assert writes == 1


def test_authentication_fails_closed_when_store_is_unreadable(
    monkeypatch, tmp_path: Path,
) -> None:
    root = _root(monkeypatch, tmp_path)
    path = root / "host" / "connections.yaml"
    path.parent.mkdir(parents=True)
    path.write_text("connections: [")

    assert connections.authenticate("anything").valid is False


def test_authentication_uses_last_valid_cache_during_a_read_failure(
    monkeypatch, tmp_path: Path,
) -> None:
    _root(monkeypatch, tmp_path)
    _row, device = connections.create_connection("Javi")
    assert connections.authenticate(device["token"], min_interval=999).valid
    assert connections.authenticate(device["token"], min_interval=999).valid
    connections.store_path().write_text("connections: [")
    monkeypatch.setattr(connections, "_cached_at", 0.0)

    assert connections.authenticate(device["token"], min_interval=999).valid


def test_authentication_reuses_the_normalised_cache(monkeypatch, tmp_path: Path) -> None:
    _root(monkeypatch, tmp_path)
    _row, device = connections.create_connection("Javi")
    assert connections.authenticate(device["token"], min_interval=999).valid
    connections.invalidate_cache()
    calls = 0
    real_normalise = connections._normalise_store

    def counted_normalise(raw):
        nonlocal calls
        calls += 1
        return real_normalise(raw)

    monkeypatch.setattr(connections, "_normalise_store", counted_normalise)

    assert connections.authenticate(device["token"], min_interval=999).valid
    assert connections.authenticate(device["token"], min_interval=999).valid
    assert calls == 1


@pytest.mark.asyncio
async def test_legacy_profiles_are_validated_once(monkeypatch, tmp_path: Path) -> None:
    _root(monkeypatch, tmp_path)
    _row, device = connections.create_connection("Javi")
    calls = 0
    real_validate = connections.validate_profiles

    def counted_validate(value):
        nonlocal calls
        calls += 1
        return real_validate(value)

    monkeypatch.setattr(connections, "validate_profiles", counted_validate)

    result = await connections._legacy_set_profiles({
        "token_id": device["token_id"],
        "profiles": ["atlas"],
    }, Server(tmp_path))

    assert calls == 1
    assert result == {"ok": True, "profile_scope": ["atlas"]}
    assert connections.list_connections()[0]["profile_scope"] == ["atlas"]


def test_console_connection_detail_reports_usage_and_revokes_one_device(
    monkeypatch, tmp_path: Path,
) -> None:
    root = _root(monkeypatch, tmp_path)
    row, first = connections.create_connection("Javi")
    _, second = connections.add_device(row["id"])
    connections.register_device(
        second["token"], client="desktop", name="MacBook", app_version="0.4.39",
    )
    menus = []
    confirmations = []
    choices = iter([("revoke_device", second["id"]), None])

    def menu(_title, entries, **_kwargs):
        menus.append(entries)
        return next(choices)

    def confirm(label, **_kwargs):
        confirmations.append(label)
        return True

    monkeypatch.setattr(ui, "menu", menu)
    monkeypatch.setattr(ui, "confirm", confirm)

    cli._device_detail(root, row["id"])

    assert any(entry and entry[0] == "Usage (14 days)" for entry in menus[0])
    assert any(
        isinstance(entry, tuple)
        and len(entry) > 1
        and entry[1] == ("revoke_device", second["id"])
        and "desktop · 0.4.39" in entry[2]
        for entry in menus[0]
    )
    assert "other devices keep working" in confirmations[0]
    assert connections.authenticate(first["token"]).valid
    assert not connections.authenticate(second["token"]).valid


def test_console_connections_limits_recent_rows_and_searches_all_devices(
    monkeypatch, tmp_path: Path,
) -> None:
    root = _root(monkeypatch, tmp_path)
    rows = []
    summaries = []
    for index in range(200):
        rows.append({
            "id": f"conn_{index:03d}",
            "label": f"Person {index:03d}",
            "created": index,
            "status": "disabled" if index == 199 else "active",
            "role": "member",
            "profile_scope": [],
            "devices": [{
                "id": f"dev_{index:03d}",
                "token": f"token-{index:03d}",
                "token_id": f"tok-{index:03d}",
                "name": f"Laptop {index:03d}",
                "client": "desktop",
                "app_version": "0.4.39",
                "created": index,
                "last_seen": index,
                "status": "active",
            }],
            "deleted_at": None,
        })
        summaries.append({
            "id": f"conn_{index:03d}",
            "last_seen": index,
            "sessions": index,
            "cost_14d": index / 100,
        })

    menu_calls = []
    detail_calls = []

    def menu(_title, entries, **_kwargs):
        menu_calls.append(entries)
        if len(menu_calls) == 1:
            return "search"
        if len(menu_calls) == 2:
            return ("device", "conn_010")
        return None

    monkeypatch.setattr(connections, "list_connections", lambda: rows)
    monkeypatch.setattr(host_usage, "connections_summary", lambda: {"connections": summaries})
    monkeypatch.setattr(cli, "_device_detail", lambda _home, connection_id: detail_calls.append(connection_id))
    monkeypatch.setattr(ui, "menu", menu)
    monkeypatch.setattr(ui, "text", lambda *_args, **_kwargs: "Laptop 010")
    monkeypatch.setattr("alpi.host.network.resolve_host_endpoint", lambda _home: ("host", "lan"))

    cli._devices_setup(root)

    first_rows = [
        entry for entry in menu_calls[0]
        if isinstance(entry, tuple) and len(entry) > 1 and isinstance(entry[1], tuple)
    ]
    assert len(first_rows) == 20
    assert first_rows[0][0] == "Person 199"
    assert "disabled" in first_rows[0][2]
    assert all(entry[0] != "Person 010" for entry in first_rows)
    assert any(entry[0] == "Person 010" for entry in menu_calls[1] if isinstance(entry, tuple))
    assert detail_calls == ["conn_010"]


def test_console_profile_edit_rejects_unknown_names_and_hides_action_for_admin(
    monkeypatch, tmp_path: Path,
) -> None:
    root = _root(monkeypatch, tmp_path)
    (root / "profiles" / "atlas").mkdir(parents=True)
    member, _device = connections.create_connection("Member")
    choices = iter(["scope", None])
    values = iter(["missing", "atlas"])
    failures = []

    monkeypatch.setattr(ui, "menu", lambda *_args, **_kwargs: next(choices))
    monkeypatch.setattr(ui, "text", lambda *_args, **_kwargs: next(values))
    monkeypatch.setattr(ui, "fail", failures.append)
    cli._device_detail(root, member["id"])

    stored = next(row for row in connections.list_connections() if row["id"] == member["id"])
    assert failures == ["unknown profile(s): missing"]
    assert stored["profile_scope"] == ["atlas"]

    admin, _device = connections.create_connection("Admin", role="admin")
    menus = []
    monkeypatch.setattr(ui, "menu", lambda _title, entries, **_kwargs: menus.append(entries))
    cli._device_detail(root, admin["id"])

    assert not any(
        isinstance(entry, tuple) and len(entry) > 1 and entry[1] == "scope"
        for entry in menus[0]
    )


def test_console_disable_and_delete_require_confirmation(
    monkeypatch, tmp_path: Path,
) -> None:
    root = _root(monkeypatch, tmp_path)
    row, _device = connections.create_connection("Javi")
    choices = iter(["status", "delete", None])
    confirmations = iter([False, True])

    monkeypatch.setattr(ui, "menu", lambda *_args, **_kwargs: next(choices))
    monkeypatch.setattr(ui, "confirm", lambda *_args, **_kwargs: next(confirmations))
    monkeypatch.setattr(ui, "text", lambda *_args, **_kwargs: "wrong")
    cli._device_detail(root, row["id"])

    stored = connections.list_connections()[0]
    assert stored["status"] == "active"
    assert stored["label"] == "Javi"

    choices = iter(["status", "delete"])
    confirmations = iter([True, True])
    monkeypatch.setattr(ui, "text", lambda *_args, **_kwargs: "Javi")
    monkeypatch.setattr(ui, "ok_and_wait", lambda *_args, **_kwargs: None)
    cli._device_detail(root, row["id"])

    assert connections.list_connections() == []


def test_session_and_usage_keep_connection_identity(monkeypatch, tmp_path: Path) -> None:
    root = _root(monkeypatch, tmp_path)
    profile = root / "profiles" / "atlas"
    with use(ConnectionContext("conn_javi", "dev_phone", "remote")):
        session = Session(profile, "model", connection_id="conn_javi")
        session.turns.append(Turn(1, "hello", [], "hi"))
        path = session.save()
        ledger.record(profile, usd=0.25, tokens=30, tokens_in=20, tokens_out=10)

    assert json.loads(path.read_text())["connection_id"] == "conn_javi"
    bucket = ledger.snapshot(profile)["by_connection"]["conn_javi"]
    assert bucket == {"usd": 0.25, "tokens": 30, "tokens_in": 20, "tokens_out": 10}


def test_connection_summary_aggregates_profiles_in_one_ledger_pass(
    monkeypatch, tmp_path: Path,
) -> None:
    root = _root(monkeypatch, tmp_path)
    row, _device = connections.create_connection("Javi")
    homes = [root, root / "profiles" / "atlas"]
    for index, profile in enumerate(homes, start=1):
        with use(ConnectionContext(row["id"], f"dev_{index}", "remote")):
            session = Session(profile, "model", connection_id=row["id"])
            session.turns.append(Turn(1, f"hello {index}", [], "hi"))
            session.save()
            ledger.record(
                profile, usd=0.1 * index, tokens=10 * index,
                tokens_in=6 * index, tokens_out=4 * index,
            )

    calls = []
    real_snapshot = ledger.snapshot

    def counted_snapshot(home):
        calls.append(home)
        return real_snapshot(home)

    monkeypatch.setattr(ledger, "snapshot", counted_snapshot)
    payload = host_usage.connections_summary()
    summary = next(item for item in payload["connections"] if item["id"] == row["id"])

    assert calls == homes
    assert summary["sessions"] == 2
    assert summary["tokens_14d"] == 30
    assert summary["cost_14d"] == pytest.approx(0.3)


def test_usage_before_connection_attribution_falls_back_to_host(
    monkeypatch, tmp_path: Path,
) -> None:
    root = _root(monkeypatch, tmp_path)
    ledger.record(root, usd=0.25, tokens=30, tokens_in=20, tokens_out=10)
    stored = ledger.snapshot(root)
    stored["by_connection"] = {}
    stored["history"][stored["day"]].pop("by_connection")
    ledger.save(root, stored)

    payload = host_usage.connections_summary()
    host = next(item for item in payload["connections"] if item["id"] == "host")

    assert host["tokens_14d"] == 30
    assert host["cost_14d"] == pytest.approx(0.25)


def test_deleted_connection_remains_in_global_usage_totals(
    monkeypatch, tmp_path: Path,
) -> None:
    root = _root(monkeypatch, tmp_path)
    row, _device = connections.create_connection("Javi")
    with use(ConnectionContext(row["id"], "dev_phone", "remote")):
        session = Session(root, "model", connection_id=row["id"])
        session.turns.append(Turn(1, "hello", [], "hi"))
        session.save()
        ledger.record(root, usd=0.4, tokens=10, tokens_in=6, tokens_out=4)
    connections.delete_connection(row["id"])

    payload = host_usage.connections_summary()

    assert all(item["id"] != row["id"] for item in payload["connections"])
    assert payload["totals"]["sessions"] == 1
    assert payload["totals"]["cost_14d"] == pytest.approx(0.4)


@pytest.mark.asyncio
async def test_session_explorer_is_partitioned_by_connection(monkeypatch, tmp_path: Path) -> None:
    root = _root(monkeypatch, tmp_path)
    for connection_id, text in (("conn_a", "from a"), ("conn_b", "from b")):
        session = Session(root, "model", connection_id=connection_id)
        session.turns.append(Turn(1, text, [], "reply"))
        session.save()

    server = Server(root)
    with use(ConnectionContext("conn_a", "dev_a", "remote")):
        result = await handlers._sessions_list({"profile": "default"}, server)
        assert [row["first_user"] for row in result["sessions"]] == ["from a"]
        foreign_id = next(
            row["id"] for row in host_sessions.list_sessions(root)
            if row["connection_id"] == "conn_b"
        )
        with pytest.raises(HandlerError) as error:
            await handlers._session_read({"profile": "default", "id": foreign_id}, server)
        assert error.value.message == "not-found"


@pytest.mark.asyncio
async def test_authenticated_request_binds_connection_and_device_context(
    monkeypatch, tmp_path: Path,
) -> None:
    root = _root(monkeypatch, tmp_path)
    row, device = connections.create_connection("Javi")
    server = Server(root)

    async def identity(_params, _server):
        from alpi.host.connection_context import current
        context = current()
        return {
            "connection_id": context.connection_id,
            "device_id": context.device_id,
        }

    server.register("host.test.identity", identity)
    sent = []
    async def send(payload):
        sent.append(payload)

    body = json.dumps({
        "id": "req",
        "method": "host.test.identity",
        "params": {"auth_token": device["token"]},
    })

    await server._handle_request(body, send, require_token=True)

    assert sent[0]["result"] == {
        "connection_id": row["id"],
        "device_id": device["id"],
    }


@pytest.mark.asyncio
async def test_disabled_connection_returns_a_structured_auth_reason(
    monkeypatch, tmp_path: Path,
) -> None:
    root = _root(monkeypatch, tmp_path)
    row, device = connections.create_connection("Javi")
    assert connections.update_connection(row["id"], status="disabled")
    server = Server(root)
    sent = []

    async def send(payload):
        sent.append(payload)

    await server._handle_request(json.dumps({
        "id": "req",
        "method": "host.profiles.list",
        "params": {"auth_token": device["token"]},
    }), send, require_token=True)

    assert sent == [{
        "id": "req",
        "error": {
            "code": -32000,
            "message": "auth-failed",
            "data": {"reason": "connection-disabled"},
        },
    }]


@pytest.mark.asyncio
async def test_inflight_replay_sidecar_is_partitioned_by_connection(
    monkeypatch, tmp_path: Path,
) -> None:
    root = _root(monkeypatch, tmp_path)
    _chat_events.reset_for_turn(root, "pending", "request", "conn_b")

    with use(ConnectionContext("conn_a", "dev_a", "remote")):
        with pytest.raises(HandlerError) as error:
            await chat._data_chat_events_since({
                "profile": "default",
                "session_id": "pending",
            }, Server(root))

    assert error.value.message == "not-found"
