from __future__ import annotations

import asyncio
import contextlib
import json
import shutil
import tempfile
from pathlib import Path

import pytest

from alpi.host import devices
from alpi.host import events as host_events
from alpi.host import server as host_server

BLOCKED = ("output.created", "agent.message", "schedule.changed", "budget.threshold")
ALLOWED = ("session_changed", "wg.post")


@pytest.fixture
def short_tmp(monkeypatch):
    d = Path(tempfile.mkdtemp(prefix="alp-events-role-", dir="/tmp"))
    from alpi import home as home_mod
    monkeypatch.setattr(home_mod, "_ROOT", d)
    devices._invalidate_cache()
    try:
        yield d
    finally:
        devices._invalidate_cache()
        shutil.rmtree(d, ignore_errors=True)


async def _history_kinds(srv, token: str) -> list[str]:
    sent: list[dict] = []

    async def send(p):
        sent.append(p)

    body = {"id": "h", "method": "host.events.history", "params": {"auth_token": token}}
    await srv._handle_request(json.dumps(body), send, require_token=True)
    return [e["event"] for e in sent[0]["result"]["events"]]


async def _stream_frames(srv, token: str) -> list[dict]:
    sent: list[dict] = []
    subscribed = asyncio.Event()

    async def send(p):
        sent.append(p)
        if p.get("event") == "subscribed":
            subscribed.set()

    body = {"id": "s", "method": "host.events.subscribe", "params": {"auth_token": token}}
    task = asyncio.create_task(
        srv._handle_request(json.dumps(body), send, require_token=True)
    )
    try:
        await asyncio.wait_for(subscribed.wait(), timeout=2.0)
        for kind in BLOCKED:
            host_events.emit(kind, {"profile": "default", "body": "secret"})
        host_events.emit("session_changed", {"id": "abc"})
        # session_changed is emitted last and is allowed: its arrival means the FIFO queue drained past every blocked frame.
        for _ in range(200):
            if any(p.get("event") == "session_changed" for p in sent):
                break
            await asyncio.sleep(0.01)
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
    return sent


@pytest.mark.asyncio
async def test_history_strips_admin_only_events_for_member(short_tmp: Path) -> None:
    member = devices.add(label="phone", role="member")
    srv = host_server.Server(home=short_tmp)
    host_events.register(srv)
    for kind in (*ALLOWED, *BLOCKED):
        host_events.emit(kind, {"profile": "default"})

    kinds = await _history_kinds(srv, member["token"])
    for allowed in ALLOWED:
        assert allowed in kinds, allowed
    for blocked in BLOCKED:
        assert blocked not in kinds, blocked


@pytest.mark.asyncio
async def test_history_unchanged_for_admin(short_tmp: Path) -> None:
    admin = devices.add(label="mac", role="admin")
    srv = host_server.Server(home=short_tmp)
    host_events.register(srv)
    for kind in (*ALLOWED, *BLOCKED):
        host_events.emit(kind, {"profile": "default"})

    kinds = await _history_kinds(srv, admin["token"])
    for kind in (*ALLOWED, *BLOCKED):
        assert kind in kinds, kind


@pytest.mark.asyncio
async def test_stream_drops_admin_only_events_for_member(short_tmp: Path) -> None:
    member = devices.add(label="phone", role="member")
    srv = host_server.Server(home=short_tmp)
    host_events.register(srv)

    frames = await _stream_frames(srv, member["token"])
    kinds = [p.get("event") for p in frames]
    assert "session_changed" in kinds
    for blocked in BLOCKED:
        assert blocked not in kinds, blocked
    assert not any(p.get("data", {}).get("body") == "secret" for p in frames)


@pytest.mark.asyncio
async def test_stream_unchanged_for_admin(short_tmp: Path) -> None:
    admin = devices.add(label="mac", role="admin")
    srv = host_server.Server(home=short_tmp)
    host_events.register(srv)

    frames = await _stream_frames(srv, admin["token"])
    kinds = [p.get("event") for p in frames]
    for kind in (*BLOCKED, "session_changed"):
        assert kind in kinds, kind


def _sibling_devices(scope: str, role: str = "member"):
    from alpi.host import connections
    connections.invalidate_cache()
    row, first = connections.create_connection("Web", role=role, session_scope=scope)
    _row, second = connections.add_device(row["id"])
    return row["id"], first, second


def _session_payloads(prefix: str, connection_id: str, first_id: str, second_id: str) -> list[dict]:
    return [
        {"id": f"{prefix}-mine", "profile": "default", "connection_id": connection_id, "device_id": first_id},
        {"id": f"{prefix}-sibling", "profile": "default", "connection_id": connection_id, "device_id": second_id},
        {"id": f"{prefix}-foreign", "profile": "default", "connection_id": "conn_other", "device_id": "dev_x"},
        {"id": f"{prefix}-legacy", "profile": "default"},
    ]


async def _stream_session_ids(srv, token: str, payloads: list[dict]) -> list[str]:
    sent: list[dict] = []
    subscribed = asyncio.Event()

    async def send(p):
        sent.append(p)
        if p.get("event") == "subscribed":
            subscribed.set()

    body = {"id": "s", "method": "host.events.subscribe", "params": {"auth_token": token}}
    task = asyncio.create_task(srv._handle_request(json.dumps(body), send, require_token=True))
    try:
        await asyncio.wait_for(subscribed.wait(), timeout=2.0)
        for data in payloads:
            host_events.emit("session_changed", data)
        host_events.emit("session_changed", {"id": "sentinel"})
        for _ in range(200):
            if any(p.get("data", {}).get("id") == "sentinel" for p in sent):
                break
            await asyncio.sleep(0.01)
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
    return [p["data"]["id"] for p in sent if p.get("event") == "session_changed"]


async def _history_session_ids(srv, token: str) -> list[str]:
    sent: list[dict] = []

    async def send(p):
        sent.append(p)

    body = {"id": "h", "method": "host.events.history", "params": {"auth_token": token}}
    await srv._handle_request(json.dumps(body), send, require_token=True)
    return [e["data"].get("id") for e in sent[0]["result"]["events"] if e["event"] == "session_changed"]


@pytest.mark.parametrize(
    "scope,role,sibling_visible",
    [("device", "member", False), ("connection", "member", True), ("device", "admin", True)],
)
@pytest.mark.asyncio
async def test_stream_scopes_session_changed_to_the_subscriber(
    short_tmp: Path, scope: str, role: str, sibling_visible: bool,
) -> None:
    connection_id, first, second = _sibling_devices(scope, role)
    srv = host_server.Server(home=short_tmp)
    host_events.register(srv)
    prefix = f"s-{scope}-{role}"

    ids = await _stream_session_ids(
        srv, first["token"], _session_payloads(prefix, connection_id, first["id"], second["id"]),
    )

    assert f"{prefix}-mine" in ids and f"{prefix}-legacy" in ids
    assert (f"{prefix}-foreign" in ids) is (role == "admin")
    assert (f"{prefix}-sibling" in ids) is sibling_visible


@pytest.mark.parametrize(
    "scope,role,sibling_visible",
    [("device", "member", False), ("connection", "member", True), ("device", "admin", True)],
)
@pytest.mark.asyncio
async def test_history_scopes_session_changed_to_the_subscriber(
    short_tmp: Path, scope: str, role: str, sibling_visible: bool,
) -> None:
    connection_id, first, second = _sibling_devices(scope, role)
    srv = host_server.Server(home=short_tmp)
    host_events.register(srv)
    prefix = f"h-{scope}-{role}"
    for data in _session_payloads(prefix, connection_id, first["id"], second["id"]):
        host_events.emit("session_changed", data)

    ids = await _history_session_ids(srv, first["token"])

    assert f"{prefix}-mine" in ids and f"{prefix}-legacy" in ids
    assert (f"{prefix}-foreign" in ids) is (role == "admin")
    assert (f"{prefix}-sibling" in ids) is sibling_visible


def _prompt_payloads(prefix: str, connection_id: str, first_id: str, second_id: str) -> list[dict]:
    return [
        {"request_id": f"{prefix}-mine", "profile": "default", "connection_id": connection_id, "device_id": first_id},
        {"request_id": f"{prefix}-sibling", "profile": "default", "connection_id": connection_id, "device_id": second_id},
        {"request_id": f"{prefix}-foreign", "profile": "default", "connection_id": "conn_other", "device_id": "dev_x"},
    ]


@pytest.mark.parametrize("kind", ["clarification.request", "clarification.resolved", "approval.request", "approval.resolved"])
@pytest.mark.parametrize(
    "scope,role,sibling_visible",
    [("device", "member", False), ("connection", "member", True), ("device", "admin", True)],
)
@pytest.mark.asyncio
async def test_prompt_events_reach_only_the_turn_owner(
    short_tmp: Path, kind: str, scope: str, role: str, sibling_visible: bool,
) -> None:
    connection_id, first, second = _sibling_devices(scope, role)
    srv = host_server.Server(home=short_tmp)
    host_events.register(srv)
    prefix = f"p-{kind}-{scope}-{role}"
    sent: list[dict] = []
    subscribed = asyncio.Event()

    async def send(p):
        sent.append(p)
        if p.get("event") == "subscribed":
            subscribed.set()

    body = {"id": "s", "method": "host.events.subscribe", "params": {"auth_token": first["token"]}}
    task = asyncio.create_task(srv._handle_request(json.dumps(body), send, require_token=True))
    try:
        await asyncio.wait_for(subscribed.wait(), timeout=2.0)
        for data in _prompt_payloads(prefix, connection_id, first["id"], second["id"]):
            host_events.emit(kind, data)
        host_events.emit(kind, {"request_id": f"{prefix}-end", "profile": "default", "connection_id": connection_id, "device_id": first["id"]})
        for _ in range(200):
            if any(p.get("data", {}).get("request_id") == f"{prefix}-end" for p in sent):
                break
            await asyncio.sleep(0.01)
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
    live = [p["data"]["request_id"] for p in sent if p.get("event") == kind]
    history_sent: list[dict] = []

    async def hsend(p):
        history_sent.append(p)

    hbody = {"id": "h", "method": "host.events.history", "params": {"auth_token": first["token"]}}
    await srv._handle_request(json.dumps(hbody), hsend, require_token=True)
    history = [e["data"].get("request_id") for e in history_sent[0]["result"]["events"] if e["event"] == kind]
    for ids in (live, history):
        assert f"{prefix}-mine" in ids
        assert (f"{prefix}-foreign" in ids) is (role == "admin")
        assert (f"{prefix}-sibling" in ids) is sibling_visible

