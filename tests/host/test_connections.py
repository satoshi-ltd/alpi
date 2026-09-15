from __future__ import annotations

import hashlib
import json
import logging
import multiprocessing as mp
import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml
import pytest

from alpi import cli, config as cfg_mod, ledger, ui
from alpi.host import (
    _chat_events,
    chat,
    connections,
    device_state,
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


def _conn_op_worker(root_str: str, op: str, op_args: tuple, delay: float, barrier) -> None:
    import time as _time

    from alpi import home as home_mod
    from alpi.host import connections as conn

    home_mod._ROOT = Path(root_str)
    conn.invalidate_cache()
    original = conn._atomic_write

    def slow(data):
        _time.sleep(delay)  # widen the read→write window so a missing cross-process lock loses updates
        original(data)

    conn._atomic_write = slow
    barrier.wait()
    getattr(conn, op)(*op_args)


def test_concurrent_create_across_processes_keeps_both(monkeypatch, tmp_path: Path) -> None:
    root = _root(monkeypatch, tmp_path)
    ctx = mp.get_context()
    barrier = ctx.Barrier(2)
    procs = [
        ctx.Process(target=_conn_op_worker, args=(str(root), "create_connection", (label,), 0.4, barrier))
        for label in ("one", "two")
    ]
    for p in procs:
        p.start()
    for p in procs:
        p.join(30)
    for p in procs:
        assert p.exitcode == 0
    connections.invalidate_cache()
    labels = sorted(c["label"] for c in connections.list_connections())
    assert labels == ["one", "two"], labels


def test_concurrent_add_and_revoke_across_processes(monkeypatch, tmp_path: Path) -> None:
    root = _root(monkeypatch, tmp_path)
    conn, dev1 = connections.create_connection("base")
    connections.add_device(conn["id"])
    connections.invalidate_cache()
    ctx = mp.get_context()
    barrier = ctx.Barrier(2)
    p_add = ctx.Process(target=_conn_op_worker, args=(str(root), "add_device", (conn["id"],), 0.4, barrier))
    p_rev = ctx.Process(target=_conn_op_worker, args=(str(root), "revoke_device", (conn["id"], dev1["id"]), 0.4, barrier))
    p_add.start()
    p_rev.start()
    p_add.join(30)
    p_rev.join(30)
    assert p_add.exitcode == 0
    assert p_rev.exitcode == 0
    connections.invalidate_cache()
    row = next(c for c in connections.list_connections() if c["id"] == conn["id"])
    active = [d for d in row["devices"] if d["status"] != "deleted"]
    revoked = [d for d in row["devices"] if d["status"] == "deleted"]
    assert len(active) == 2, [(d["id"], d["status"]) for d in row["devices"]]
    assert any(d["id"] == dev1["id"] for d in revoked), "revoke was lost"


def _legacy_hold_and_write_worker(root_str: str, barrier) -> None:
    import time as _time

    from alpi import home as home_mod
    from alpi.host import devices as dev

    home_mod._ROOT = Path(root_str)
    dev._invalidate_cache()
    with dev._store_lock():
        rows = dev._read_strict()
        barrier.wait()
        _time.sleep(0.4)  # hold devices.lock across the migrator's read window
        rows.append({
            "token": "legacy-new-token",
            "label": "added-during-migration",
            "created": 100,
            "last_seen": None,
            "role": "member",
            "profile_scope": [],
        })
        dev.save(rows)


def _migrate_worker(root_str: str, barrier) -> None:
    from alpi import home as home_mod
    from alpi.host import connections as conn

    home_mod._ROOT = Path(root_str)
    conn.invalidate_cache()
    barrier.wait()
    conn.load_store()


def test_migration_coordinates_with_legacy_writer(monkeypatch, tmp_path: Path) -> None:
    root = _root(monkeypatch, tmp_path)
    legacy = root / "host" / "devices.yaml"
    legacy.parent.mkdir(parents=True)
    legacy.write_text(yaml.safe_dump([{
        "token": "dev0-token", "label": "dev0", "created": 10,
        "last_seen": 20, "role": "member", "profile_scope": [],
    }]))
    ctx = mp.get_context()
    barrier = ctx.Barrier(2)
    p_write = ctx.Process(target=_legacy_hold_and_write_worker, args=(str(root), barrier))
    p_migrate = ctx.Process(target=_migrate_worker, args=(str(root), barrier))
    p_write.start()
    p_migrate.start()
    p_write.join(30)
    p_migrate.join(30)
    assert p_write.exitcode == 0
    assert p_migrate.exitcode == 0
    connections.invalidate_cache()
    labels = {c["label"] for c in connections.list_connections(include_deleted=True)}
    assert "added-during-migration" in labels, labels


def _add_and_report_worker(root_str: str, conn_id: str, queue, barrier) -> None:
    from alpi import home as home_mod
    from alpi.host import connections as conn

    home_mod._ROOT = Path(root_str)
    conn.invalidate_cache()
    barrier.wait()
    try:
        conn.add_device(conn_id)
        queue.put("added")
    except KeyError:
        queue.put("not-found")


def _revoke_worker(root_str: str, token_id: str, barrier) -> None:
    import asyncio

    from alpi import home as home_mod
    from alpi.host import connections as conn

    home_mod._ROOT = Path(root_str)
    conn.invalidate_cache()
    barrier.wait()
    asyncio.run(conn._legacy_revoke({"token_id": token_id}, None))


def test_legacy_revoke_add_device_toctou(monkeypatch, tmp_path: Path) -> None:
    root = _root(monkeypatch, tmp_path)
    conn, dev1 = connections.create_connection("base")
    connections.invalidate_cache()
    token_id = dev1["token"][-8:]
    ctx = mp.get_context()
    barrier = ctx.Barrier(2)
    queue = ctx.Queue()
    p_rev = ctx.Process(target=_revoke_worker, args=(str(root), token_id, barrier))
    p_add = ctx.Process(target=_add_and_report_worker, args=(str(root), conn["id"], queue, barrier))
    p_rev.start()
    p_add.start()
    p_rev.join(30)
    p_add.join(30)
    assert p_rev.exitcode == 0
    assert p_add.exitcode == 0
    add_result = queue.get(timeout=5)
    connections.invalidate_cache()
    row = next((c for c in connections.list_connections(include_deleted=True) if c["id"] == conn["id"]), None)
    assert row is not None
    if add_result == "added":
        assert row["status"] != "deleted", row
        by_id = {d["id"]: d for d in row["devices"]}
        active = [d for d in row["devices"] if d["status"] != "deleted"]
        assert len(active) == 1, row["devices"]
        assert by_id[dev1["id"]]["status"] == "deleted", row["devices"]
    else:
        assert add_result == "not-found"
        assert row["status"] == "deleted", row


def test_read_path_is_lock_free(monkeypatch, tmp_path: Path) -> None:
    _root(monkeypatch, tmp_path)
    connections.create_connection("x")
    connections.invalidate_cache()
    calls = []
    original_locked = connections._locked

    def spy():
        calls.append(1)
        return original_locked()

    monkeypatch.setattr(connections, "_locked", spy)
    connections.load_store()
    connections.list_connections()
    connections.authenticate("nope")
    assert calls == [], "read path must not take the exclusive lock (perf regression guard)"


def test_revoke_by_token_id_revokes_only_target(monkeypatch, tmp_path: Path) -> None:
    _root(monkeypatch, tmp_path)
    conn, dev1 = connections.create_connection("base")
    _conn2, dev2 = connections.add_device(conn["id"])
    connections.invalidate_cache()
    assert connections.revoke_by_token_id(dev1["token"][-8:]) is True
    connections.invalidate_cache()
    row = next(c for c in connections.list_connections(include_deleted=True) if c["id"] == conn["id"])
    assert row["status"] != "deleted"
    by_id = {d["id"]: d for d in row["devices"]}
    assert by_id[dev1["id"]]["status"] == "deleted"
    assert by_id[dev2["id"]]["status"] != "deleted"


def test_revoke_by_token_id_deletes_connection_for_last_unused_device(monkeypatch, tmp_path: Path) -> None:
    _root(monkeypatch, tmp_path)
    conn, dev1 = connections.create_connection("base")
    connections.invalidate_cache()
    assert connections.revoke_by_token_id(dev1["token"][-8:]) is True
    connections.invalidate_cache()
    row = next(c for c in connections.list_connections(include_deleted=True) if c["id"] == conn["id"])
    assert row["status"] == "deleted"


def test_legacy_save_does_not_resurrect_after_migration(monkeypatch, tmp_path: Path) -> None:
    from alpi.host import devices

    root = _root(monkeypatch, tmp_path)
    (root / "host").mkdir(parents=True)
    (root / "host" / "connections.yaml").write_text(
        yaml.safe_dump({"version": 1, "connections": []}),
    )
    legacy = root / "host" / "devices.yaml"
    devices.save([{
        "token": "x", "label": "y", "created": 1,
        "last_seen": None, "role": "member", "profile_scope": [],
    }])
    assert not legacy.exists()


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
    assert rows[0]["devices"][0]["token_hash"] == hashlib.sha256(b"legacy-token").hexdigest()
    assert rows[0]["devices"][0]["token_id"] == "legacy-token"[-8:]
    assert "legacy-token" not in connections.store_path().read_text()
    assert rows[0]["devices"][0]["client"] == "unknown"
    auth = connections.authenticate("legacy-token")
    assert (auth.connection_id, auth.role, auth.profile_scope) == (rows[0]["id"], "member", ("atlas",))
    assert connections.store_path().exists()
    assert oct(connections.store_path().stat().st_mode & 0o777) == "0o600"
    assert not legacy.exists()
    assert list(legacy.parent.glob("devices.yaml*")) == []

    before = connections.store_path().stat().st_mtime_ns
    connections.load_store()
    assert connections.store_path().stat().st_mtime_ns == before


def test_migration_writes_no_backup_and_leaves_historical_copies_alone(
    monkeypatch, tmp_path: Path,
) -> None:
    root = _root(monkeypatch, tmp_path)
    legacy = root / "host" / "devices.yaml"
    legacy.parent.mkdir(parents=True)
    legacy.write_text(yaml.safe_dump([{"token": "live", "label": "Live"}]))
    historical = legacy.with_name("devices.yaml.migrated")
    historical.write_text("older backup")

    connections.load_store()

    assert not legacy.exists()
    assert historical.read_text() == "older backup"
    assert sorted(p.name for p in legacy.parent.glob("devices.yaml*")) == ["devices.yaml.migrated"]


def test_device_tokens_are_stored_hashed(monkeypatch, tmp_path: Path) -> None:
    _root(monkeypatch, tmp_path)
    row, device = connections.create_connection("Javi")

    text = connections.store_path().read_text()
    stored = yaml.safe_load(text)["connections"][0]["devices"][0]

    assert device["token"] not in text
    assert "token" not in stored
    assert stored["token_hash"] == hashlib.sha256(device["token"].encode()).hexdigest()
    assert stored["token_id"] == device["token"][-8:]
    assert connections.authenticate(device["token"]).connection_id == row["id"]
    assert connections.authenticate(stored["token_hash"]).valid is False


def test_cleartext_store_is_hashed_on_first_read_without_re_pairing(monkeypatch, tmp_path: Path) -> None:
    root = _root(monkeypatch, tmp_path)
    path = root / "host" / "connections.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(yaml.safe_dump({"version": 2, "connections": [{
        "id": "conn_javi", "label": "Javi", "created": 1, "status": "active",
        "role": "member", "profile_scope": ["atlas"], "pairings": [],
        "devices": [
            {"id": "dev_mac", "token": "plain-macbook-token", "name": "MacBook",
             "client": "desktop", "created": 1, "last_seen": 2, "status": "active"},
            {"id": "dev_old", "token": "", "token_id": "oldphone", "name": "Old",
             "client": "mobile", "created": 1, "status": "deleted"},
        ],
    }]}))

    auth = connections.authenticate("plain-macbook-token")

    assert auth.valid
    assert (auth.connection_id, auth.device_id, auth.profile_scope) == ("conn_javi", "dev_mac", ("atlas",))
    text = path.read_text()
    assert "plain-macbook-token" not in text
    devices = {d["id"]: d for d in yaml.safe_load(text)["connections"][0]["devices"]}
    assert devices["dev_mac"]["token_hash"] == hashlib.sha256(b"plain-macbook-token").hexdigest()
    assert devices["dev_mac"]["token_id"] == "plain-macbook-token"[-8:]
    assert "token" not in devices["dev_mac"]
    assert (devices["dev_old"]["token_hash"], devices["dev_old"]["token_id"]) == ("", "oldphone")
    assert oct(path.stat().st_mode & 0o777) == "0o600"

    before = path.stat().st_mtime_ns
    connections.load_store()
    assert path.stat().st_mtime_ns == before

    assert connections.revoke_by_token_id("plain-macbook-token"[-8:]) is True
    assert connections.authenticate("plain-macbook-token").valid is False


def _legacy_rows(*tokens: str) -> str:
    return yaml.safe_dump([
        {"token": token, "label": f"Device {index}", "created": 10, "last_seen": 20,
         "role": "member", "profile_scope": ["atlas"]}
        for index, token in enumerate(tokens)
    ])


def _write_store(host: Path, text: str) -> Path:
    path = host / "connections.yaml"
    path.write_text(text)
    path.chmod(0o600)
    return path


def _hashed_store(token: str, *, status: str = "active") -> str:
    return yaml.safe_dump({"version": 2, "connections": [{
        "id": "conn_javi", "label": "Javi", "created": 1, "status": "active", "role": "member",
        "profile_scope": ["atlas"], "pairings": [],
        "devices": [{
            "id": "dev_mac",
            "token_hash": hashlib.sha256(token.encode()).hexdigest() if status == "active" else "",
            "token_id": token[-8:], "name": "MacBook", "client": "desktop",
            "created": 1, "last_seen": 2, "status": status,
        }],
    }]})


def test_legacy_migration_write_failure_keeps_the_origin_intact(monkeypatch, tmp_path: Path) -> None:
    root = _root(monkeypatch, tmp_path)
    legacy = root / "host" / "devices.yaml"
    legacy.parent.mkdir(parents=True)
    legacy.write_text(_legacy_rows("legacy-token"))
    before = legacy.read_text()

    def fail(_data):
        raise OSError("disk full")

    monkeypatch.setattr(connections, "_atomic_write", fail)
    with pytest.raises(OSError):
        connections.load_store()

    assert legacy.read_text() == before
    assert not connections.store_path().exists()
    assert list(legacy.parent.glob("devices.yaml.*")) == []


def test_legacy_migration_verification_failure_keeps_the_origin_and_recovers_later(
    monkeypatch, tmp_path: Path,
) -> None:
    root = _root(monkeypatch, tmp_path)
    legacy = root / "host" / "devices.yaml"
    legacy.parent.mkdir(parents=True)
    legacy.write_text(_legacy_rows("legacy-token"))
    before = legacy.read_text()

    original = connections._verify_written_store

    def reject(_expected):
        raise connections.StoreUnavailable("simulated verification failure")

    connections._verify_written_store = reject
    try:
        with pytest.raises(connections.StoreUnavailable):
            connections.load_store()
    finally:
        connections._verify_written_store = original

    assert legacy.read_text() == before
    assert "legacy-token" not in connections.store_path().read_text()

    connections.load_store()

    assert not legacy.exists()
    assert connections.authenticate("legacy-token").valid
    assert connections.pending_migration() is None


def test_interrupted_legacy_migration_completes_on_the_next_read(monkeypatch, tmp_path: Path) -> None:
    root = _root(monkeypatch, tmp_path)
    host = root / "host"
    host.mkdir(parents=True)
    _write_store(host, _hashed_store("legacy-token"))
    (host / "devices.yaml").write_text(_legacy_rows("legacy-token"))
    before = (host / "connections.yaml").stat().st_mtime_ns

    connections.load_store()

    assert not (host / "devices.yaml").exists()
    assert (host / "connections.yaml").stat().st_mtime_ns == before
    assert connections.authenticate("legacy-token").device_id == "dev_mac"
    assert connections.pending_migration() is None
    assert list(host.glob("devices.yaml*")) == []


def test_divergent_legacy_store_is_kept_and_reported(monkeypatch, tmp_path: Path, caplog) -> None:
    root = _root(monkeypatch, tmp_path)
    host = root / "host"
    host.mkdir(parents=True)
    _write_store(host, _hashed_store("legacy-token"))
    (host / "devices.yaml").write_text(_legacy_rows("legacy-token", "extra-token"))
    legacy_before = (host / "devices.yaml").read_text()
    store_before = (host / "connections.yaml").stat().st_mtime_ns
    caplog.set_level(logging.WARNING, logger="alpi.host.connections")

    rows = connections.load_store()["connections"]

    assert (host / "devices.yaml").read_text() == legacy_before
    assert (host / "connections.yaml").stat().st_mtime_ns == store_before
    assert [d["id"] for c in rows for d in c["devices"]] == ["dev_mac"]
    assert connections.authenticate("legacy-token", min_interval=10**9).valid
    assert connections.authenticate("extra-token").valid is False
    assert "1 device token(s) absent" in (connections.pending_migration() or "")
    assert any("migration pending" in record.message for record in caplog.records)
    assert "extra-token" not in caplog.text


def test_leftover_legacy_of_unexpected_shape_is_kept_with_a_warning(monkeypatch, tmp_path: Path) -> None:
    root = _root(monkeypatch, tmp_path)
    host = root / "host"
    host.mkdir(parents=True)
    _write_store(host, _hashed_store("legacy-token"))
    odd = "devices:\n  - token: synthetic-legacy-secret\n"
    (host / "devices.yaml").write_text(odd)
    store_before = (host / "connections.yaml").stat().st_mtime_ns

    connections.load_store()

    assert (host / "devices.yaml").read_text() == odd
    assert (host / "connections.yaml").stat().st_mtime_ns == store_before
    assert "not a device list" in (connections.pending_migration() or "")
    assert connections.authenticate("synthetic-legacy-secret").valid is False
    assert connections.authenticate("legacy-token", min_interval=10**9).valid


def test_legacy_rows_without_tokens_keep_the_file_for_review(monkeypatch, tmp_path: Path) -> None:
    root = _root(monkeypatch, tmp_path)
    legacy = root / "host" / "devices.yaml"
    legacy.parent.mkdir(parents=True)
    legacy.write_text(yaml.safe_dump([
        {"token": "legacy-token", "label": "Javi", "created": 10},
        {"label": "no credential here", "created": 11},
    ]))
    before = legacy.read_text()

    connections.load_store()

    assert connections.authenticate("legacy-token").valid
    assert "legacy-token" not in connections.store_path().read_text()
    assert legacy.read_text() == before
    assert "1 row(s) without a token" in (connections.pending_migration() or "")


def test_leftover_legacy_is_removed_only_after_the_destination_is_hashed(monkeypatch, tmp_path: Path) -> None:
    root = _root(monkeypatch, tmp_path)
    host = root / "host"
    host.mkdir(parents=True)
    _write_store(host, yaml.safe_dump({"version": 2, "connections": [{
        "id": "conn_javi", "label": "Javi", "created": 1, "status": "active", "role": "member",
        "profile_scope": [], "pairings": [],
        "devices": [{"id": "dev_mac", "token": "legacy-token", "created": 1, "status": "active"}],
    }]}))
    (host / "devices.yaml").write_text(_legacy_rows("legacy-token"))

    connections.load_store()

    assert "legacy-token" not in (host / "connections.yaml").read_text()
    assert not (host / "devices.yaml").exists()
    assert connections.authenticate("legacy-token").valid
    assert connections.pending_migration() is None


def test_leftover_legacy_survives_a_corrupt_destination(monkeypatch, tmp_path: Path) -> None:
    root = _root(monkeypatch, tmp_path)
    host = root / "host"
    host.mkdir(parents=True)
    _write_store(host, "{{{ not yaml\n")
    (host / "devices.yaml").write_text(_legacy_rows("legacy-token"))

    with pytest.raises(connections.StoreUnavailable):
        connections.load_store()

    assert (host / "devices.yaml").exists()
    assert (host / "connections.yaml").read_text() == "{{{ not yaml\n"


def test_revoked_device_is_not_revived_from_a_leftover_legacy_store(monkeypatch, tmp_path: Path) -> None:
    root = _root(monkeypatch, tmp_path)
    host = root / "host"
    host.mkdir(parents=True)
    _write_store(host, _hashed_store("legacy-token", status="deleted"))
    (host / "devices.yaml").write_text(_legacy_rows("legacy-token"))

    connections.load_store()

    assert (host / "devices.yaml").exists()
    assert connections.authenticate("legacy-token").valid is False
    assert connections.pending_migration() is not None


def test_empty_store_file_keeps_the_last_valid_cache(monkeypatch, tmp_path: Path) -> None:
    _root(monkeypatch, tmp_path)
    row, device = connections.create_connection("Javi")
    connections.authenticate(device["token"])
    assert connections.authenticate(device["token"], min_interval=10**9).valid
    path = connections.store_path()

    for content in ("", "null\n", "{{{ not yaml\n"):
        path.write_text(content)

        assert connections.authenticate(device["token"], min_interval=10**9).valid
        with pytest.raises(connections.StoreUnavailable):
            connections.load_store()
        with pytest.raises(connections.StoreUnavailable):
            connections.add_device(row["id"])
        assert path.read_text() == content


@pytest.mark.asyncio
async def test_server_start_migrates_legacy_devices_into_hashed_connections(monkeypatch) -> None:
    from alpi.host import server as host_server

    short = Path(tempfile.mkdtemp(prefix="alpi-tok-", dir="/tmp"))
    try:
        root = _root(monkeypatch, short)
        legacy = root / "host" / "devices.yaml"
        legacy.parent.mkdir(parents=True)
        legacy.write_text(yaml.safe_dump([{
            "token": "legacy-token", "label": "Javi", "created": 10,
            "last_seen": 20, "role": "member", "profile_scope": [],
        }]))
        srv = Server(home=root)
        await srv.start()
        try:
            assert not legacy.exists()
            text = connections.store_path().read_text()
            assert "legacy-token" not in text
            stored = yaml.safe_load(text)["connections"][0]["devices"][0]
            assert stored["token_hash"] == hashlib.sha256(b"legacy-token").hexdigest()
            meta = host_server._check_token_meta(
                {"method": "host.config.get", "params": {"auth_token": "legacy-token"}},
            )
            assert meta.valid
            assert meta.connection_id.startswith("conn_")
            assert list((root / "host").glob("devices.yaml*")) == []
        finally:
            await srv.stop()
    finally:
        shutil.rmtree(short, ignore_errors=True)


async def _start_with_fake_ws(monkeypatch, root: Path) -> tuple[Server, list]:
    srv = Server(home=root)
    srv._tcp_bind = ("10.1.2.3", 49200)
    started: list = []

    async def fake_start_ws(host, port):
        started.append((host, port))

    monkeypatch.setattr(srv, "_start_ws", fake_start_ws)
    await srv.start()
    return srv, started


@pytest.mark.asyncio
async def test_server_start_keeps_remote_access_closed_when_migration_fails(monkeypatch) -> None:
    short = Path(tempfile.mkdtemp(prefix="alpi-tok-", dir="/tmp"))
    try:
        root = _root(monkeypatch, short)
        legacy = root / "host" / "devices.yaml"
        legacy.parent.mkdir(parents=True)
        legacy.write_text("not: [valid yaml\n")
        srv, started = await _start_with_fake_ws(monkeypatch, root)
        try:
            assert started == []
            assert legacy.exists()
            assert not connections.store_path().exists()
        finally:
            await srv.stop()
    finally:
        shutil.rmtree(short, ignore_errors=True)


@pytest.mark.asyncio
async def test_enable_tcp_refuses_until_the_credential_store_migrates(monkeypatch) -> None:
    short = Path(tempfile.mkdtemp(prefix="alpi-tok-", dir="/tmp"))
    try:
        root = _root(monkeypatch, short)
        legacy = root / "host" / "devices.yaml"
        legacy.parent.mkdir(parents=True)
        legacy.write_text("not: [valid yaml\n")
        srv = Server(home=root)
        started: list = []

        async def fake_start_ws(host, port):
            started.append((host, port))

        monkeypatch.setattr(srv, "_start_ws", fake_start_ws)
        await srv.start()
        try:
            await srv.enable_tcp(("10.1.2.3", 49200))
            assert started == []
            assert legacy.exists()

            legacy.write_text(yaml.safe_dump([{"token": "legacy-token", "label": "Javi", "created": 10}]))
            await srv.enable_tcp(("10.1.2.3", 49200))
            assert started == [("10.1.2.3", 49200)]
            assert not legacy.exists()
            assert connections.authenticate("legacy-token").valid
        finally:
            await srv.stop()
    finally:
        shutil.rmtree(short, ignore_errors=True)


@pytest.mark.asyncio
async def test_server_start_opens_remote_access_after_a_clean_migration(monkeypatch) -> None:
    short = Path(tempfile.mkdtemp(prefix="alpi-tok-", dir="/tmp"))
    try:
        root = _root(monkeypatch, short)
        legacy = root / "host" / "devices.yaml"
        legacy.parent.mkdir(parents=True)
        legacy.write_text(yaml.safe_dump([{"token": "legacy-token", "label": "Javi", "created": 10}]))
        srv, started = await _start_with_fake_ws(monkeypatch, root)
        try:
            assert started == [("10.1.2.3", 49200)]
            assert not legacy.exists()
        finally:
            await srv.stop()
    finally:
        shutil.rmtree(short, ignore_errors=True)


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
async def test_pairing_hostname_error_points_to_wss_configuration(
    monkeypatch, tmp_path: Path,
) -> None:
    _root(monkeypatch, tmp_path)
    cfg = cfg_mod.load(tmp_path)
    cfg.network = {"host": "box.tail1234.ts.net"}
    cfg_mod.save(cfg)

    with pytest.raises(HandlerError) as error:
        await connections._create({"label": "Phone"}, Server(tmp_path))

    assert error.value.code == -32010
    assert "box.tail1234.ts.net" in error.value.data["detail"]
    assert "wss://" in error.value.data["detail"]
    assert "host.endpoints" in error.value.data["detail"]
    assert connections.list_connections() == []


@pytest.mark.asyncio
async def test_pairing_payload_advertises_ordered_routes(monkeypatch, tmp_path: Path) -> None:
    from alpi.host import network

    _root(monkeypatch, tmp_path)
    endpoints = [
        {"url": "wss://client.example.com", "label": "Secure Internet"},
        {"url": "ws://100.64.10.2:49200", "label": "Direct"},
    ]
    monkeypatch.setattr(network, "resolve_host_endpoints", lambda _home: endpoints)
    monkeypatch.setattr(network, "resolve_host_endpoint", lambda _home: ("100.64.10.2", "tailscale"))
    monkeypatch.setattr(network, "resolve_host_tcp_port", lambda _home: 49200)
    monkeypatch.setattr(network, "resolve_host_pairing_name", lambda _home: "Alpi Host")

    result = await connections._create({"label": "Javi"}, Server(tmp_path))

    assert result["url"] == "wss://client.example.com"
    assert result["endpoints"] == endpoints
    assert result["host"] == "100.64.10.2"
    assert result["port"] == 49200


def test_console_pairing_data_keeps_connection_identity() -> None:
    payload, link = cli._pairing_code_data(
        "wss://client.example.com", "Client", "secret-token", "conn_123",
    )

    assert payload == {
        "u": "wss://client.example.com",
        "n": "Client",
        "g": "secret-token",
        "c": "conn_123",
    }
    assert "connection_id=conn_123" in link
    assert "pairing_token=secret-token" in link


def test_pairing_grant_is_hashed_and_exchanged_once(monkeypatch, tmp_path: Path) -> None:
    _root(monkeypatch, tmp_path)
    row, pairing = connections.create_pairing_connection("Javi", profile_scope=["atlas"])

    stored = yaml.safe_load(connections.store_path().read_text())
    raw_pairing = stored["connections"][0]["pairings"][0]
    assert pairing["token"] not in connections.store_path().read_text()
    assert len(raw_pairing["secret_hash"]) == 64
    assert stored["connections"][0]["devices"] == []

    exchanged, device = connections.exchange_pairing(
        pairing["token"], client="mobile", name="iPhone", app_version="1.2.3",
    )

    assert exchanged["id"] == row["id"]
    assert connections.authenticate(device["token"]).connection_id == row["id"]
    assert device["token"] not in connections.store_path().read_text()
    assert connections.pairing_status(row["id"], pairing["id"])["status"] == "consumed"
    with pytest.raises(connections.PairingExchangeError) as replay:
        connections.exchange_pairing(
            pairing["token"], client="desktop", name="Copy", app_version="1.0",
        )
    assert replay.value.reason == "pairing-used"


def test_pairing_history_is_bounded_and_not_returned_in_connection_list(
    monkeypatch, tmp_path: Path,
) -> None:
    _root(monkeypatch, tmp_path)
    row, _device = connections.create_connection("Javi")
    for _index in range(connections.PAIRING_HISTORY_LIMIT + 10):
        _connection, pairing = connections.create_device_pairing(row["id"])
        assert connections.cancel_pairing(row["id"], pairing["id"])

    stored = connections.list_connections()[0]
    assert len(stored["pairings"]) == connections.PAIRING_HISTORY_LIMIT
    assert "pairings" not in connections.public_connection(stored)


@pytest.mark.asyncio
async def test_pairing_exchange_handler_requires_bootstrap_context(
    monkeypatch, tmp_path: Path,
) -> None:
    _root(monkeypatch, tmp_path)
    _row, pairing = connections.create_pairing_connection("Phone")

    with pytest.raises(HandlerError) as blocked:
        await connections._exchange_pairing(
            {"pairing_token": pairing["token"]}, Server(tmp_path),
        )

    assert blocked.value.code == -32001
    assert connections.authenticate(pairing["token"]).valid is False


def test_concurrent_pairing_exchange_has_exactly_one_winner(monkeypatch, tmp_path: Path) -> None:
    _root(monkeypatch, tmp_path)
    row, pairing = connections.create_pairing_connection("Javi")

    def exchange(index):
        try:
            return connections.exchange_pairing(
                pairing["token"], client="desktop", name=f"Desktop {index}", app_version="1",
            )[1]["token"]
        except connections.PairingExchangeError as exc:
            return exc.reason

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(exchange, range(8)))

    assert results.count("pairing-used") == 7
    assert len([value for value in results if value != "pairing-used"]) == 1
    stored = next(item for item in connections.list_connections() if item["id"] == row["id"])
    assert len(stored["devices"]) == 1


def test_invalid_pairing_attempts_reuse_the_store_cache(monkeypatch, tmp_path: Path) -> None:
    _root(monkeypatch, tmp_path)
    connections.create_pairing_connection("Javi")
    connections.load_auth_store()
    parses = 0
    normalise = connections._normalise_store

    def counted(raw):
        nonlocal parses
        parses += 1
        return normalise(raw)

    monkeypatch.setattr(connections, "_normalise_store", counted)
    for index in range(100):
        with pytest.raises(connections.PairingExchangeError):
            connections.exchange_pairing(
                f"invalid-{index}", client="unknown", name="", app_version="",
            )

    assert parses == 0


def test_pairing_expiry_and_cancellation(monkeypatch, tmp_path: Path) -> None:
    _root(monkeypatch, tmp_path)
    now = 1_700_000_000
    monkeypatch.setattr(connections.time, "time", lambda: now)
    row, pairing = connections.create_pairing_connection("Expired")
    monkeypatch.setattr(connections.time, "time", lambda: now + connections.PAIRING_TTL_SECONDS)

    with pytest.raises(connections.PairingExchangeError) as expired:
        connections.exchange_pairing(
            pairing["token"], client="mobile", name="Phone", app_version="1",
        )
    assert expired.value.reason == "pairing-expired"
    assert connections.pairing_status(row["id"], pairing["id"])["status"] == "expired"
    assert not any(item["id"] == row["id"] for item in connections.list_connections())

    active, pending = connections.create_pairing_connection("Cancelled")
    assert connections.cancel_pairing(active["id"], pending["id"])
    assert connections.pairing_status(active["id"], pending["id"])["status"] == "cancelled"
    assert not any(item["id"] == active["id"] for item in connections.list_connections())


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


def test_invalid_tokens_do_not_reparse_unchanged_store(monkeypatch, tmp_path: Path) -> None:
    _root(monkeypatch, tmp_path)
    connections.create_connection("Javi")
    connections.invalidate_cache()
    calls = 0
    real_normalise = connections._normalise_store

    def counted_normalise(raw):
        nonlocal calls
        calls += 1
        return real_normalise(raw)

    monkeypatch.setattr(connections, "_normalise_store", counted_normalise)

    for index in range(100):
        assert not connections.authenticate(f"invalid-{index}").valid
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


def test_console_network_setup_edits_native_listen_port_and_restarts(
    monkeypatch, tmp_path: Path,
) -> None:
    from alpi import config as cfg_mod

    root = _root(monkeypatch, tmp_path)
    cfg = cfg_mod.Config(home=root, model="openai/x")
    cfg.network = {"host": "192.168.1.20"}
    cfg_mod.save(cfg)
    monkeypatch.delenv("ALPI_HOST_TCP_PORT", raising=False)
    values = iter(["49201", "Studio", "wss://client.example.com"])
    prompts = []
    restarts = []

    def text(prompt, **_kwargs):
        prompts.append(prompt)
        return next(values)

    monkeypatch.setattr(ui, "text", text)
    monkeypatch.setattr(ui, "ok_and_wait", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        cli,
        "_restart_daemon_for_apply",
        lambda root_path: restarts.append(root_path) or " · daemon restarting",
    )

    cli._devices_network_setup(root)

    stored = cfg_mod.load(root)
    assert stored.host["tcp_port"] == 49201
    assert stored.host["device_name"] == "Studio"
    assert stored.host["endpoints"] == [
        {"label": "Public", "url": "wss://client.example.com"},
    ]
    assert "Port:" in prompts
    assert restarts == [root]


def test_console_network_setup_does_not_override_environment_port(
    monkeypatch, tmp_path: Path,
) -> None:
    from alpi import config as cfg_mod

    root = _root(monkeypatch, tmp_path)
    cfg = cfg_mod.Config(home=root, model="openai/x")
    cfg.network = {"host": "192.168.1.20"}
    cfg.host = {"tcp_port": 49999}
    cfg_mod.save(cfg)
    monkeypatch.setenv("ALPI_PLATFORM", "docker")
    monkeypatch.setenv("ALPI_NETWORK_HOST", "192.168.1.20")
    monkeypatch.setenv("ALPI_HOST_TCP_PORT", "49202")
    values = iter(["Satoshi", "wss://satoshi.example.com"])
    prompts = []
    restarts = []

    def text(prompt, **_kwargs):
        prompts.append(prompt)
        return next(values)

    monkeypatch.setattr(ui, "text", text)
    monkeypatch.setattr(ui, "ok_and_wait", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        cli,
        "_restart_daemon_for_apply",
        lambda root_path: restarts.append(root_path) or " · daemon restarting",
    )

    cli._devices_network_setup(root)

    stored = cfg_mod.load(root)
    assert stored.host["tcp_port"] == 49999
    assert stored.host["device_name"] == "Satoshi"
    assert not any(prompt.startswith("Port:") for prompt in prompts)
    assert restarts == []


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
    assert bucket == {
        "usd": 0.25, "tokens": 30, "tokens_in": 20, "tokens_out": 10,
        "tokens_cached": 0, "tokens_measured": 0,
    }


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


def _seed_chat(home: Path, connection_id: str, text: str) -> str:
    session = Session(home, "model", connection_id=connection_id)
    session.turns.append(Turn(1, text, [], "reply"))
    session.save()
    return session.id


async def _latest_session(server: Server) -> dict | None:
    response = await server._dispatch({
        "id": "s", "method": "host.profile.summaries", "params": {},
    })
    assert "error" not in response
    return response["result"]["profiles"][0]["latest_session"]


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["member", "admin"])
async def test_latest_session_preview_never_crosses_connections(
    monkeypatch, tmp_path: Path, role: str,
) -> None:
    root = _root(monkeypatch, tmp_path)
    _seed_chat(root, "conn_fold", "typed on the fold")
    server = Server(root)
    device_state.register(server)

    with use(ConnectionContext("conn_fold", "dev_fold", "remote", role)):
        assert (await _latest_session(server))["first_user"] == "typed on the fold"
    # Second poll lands inside the summary TTL: a profile-only cache key would replay the fold preview here.
    with use(ConnectionContext("conn_phone", "dev_phone", "remote", role)):
        assert await _latest_session(server) is None


@pytest.mark.asyncio
async def test_latest_session_preview_stays_visible_to_the_local_socket(
    monkeypatch, tmp_path: Path,
) -> None:
    root = _root(monkeypatch, tmp_path)
    _seed_chat(root, "host", "typed in the cli")
    _seed_chat(root, "conn_phone", "typed on the phone")
    server = Server(root)
    device_state.register(server)

    assert (await _latest_session(server))["first_user"] == "typed in the cli"


@pytest.mark.asyncio
async def test_summarised_latest_session_is_readable_by_its_owner(
    monkeypatch, tmp_path: Path,
) -> None:
    root = _root(monkeypatch, tmp_path)
    _seed_chat(root, "conn_a", "mine")
    _seed_chat(root, "conn_b", "theirs")
    server = Server(root)
    device_state.register(server)
    handlers.register(server)
    monkeypatch.setattr(handlers, "_resolve_home", lambda _profile: root)

    with use(ConnectionContext("conn_a", "dev_a", "remote", "member")):
        latest = await _latest_session(server)
        read = await handlers._session_read({"profile": "default", "id": latest["id"]}, server)

    assert read["session"]["turns"][0]["user"] == "mine"


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


def test_rewrite_from_turn_resets_the_cache_counters(monkeypatch, tmp_path: Path) -> None:
    from types import SimpleNamespace

    from alpi.host.chat import _truncate_hydrated_session

    session = Session(tmp_path, "model")
    session.input_tokens = 1000
    session.output_tokens = 50
    session.cost_usd = 0.5
    session.cached_input_tokens = 800
    session.cache_measured_input_tokens = 1000
    session.turns = [Turn(1, "hola", [], "hi")]
    engine = SimpleNamespace(session=session, _system_prompt="sys", _last_relay_peer="")
    _truncate_hydrated_session(engine, 1)
    assert engine.session.cached_input_tokens == 0
    assert engine.session.cache_measured_input_tokens == 0, (
        "the discarded branch's share must not pollute the surviving hit rate"
    )
    assert engine.session.messages[0]["content"] == "sys"
