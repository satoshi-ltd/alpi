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
