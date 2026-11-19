from __future__ import annotations

import asyncio
import json
import os
import signal
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest
import websockets

from alpi.host import _chat_events, connections, workers
from alpi.host import chat as dc
from tests.host.test_tcp_listener import _start_security_test_server, _ws_request, short_tmp  # noqa: F401

_SMALL = 3


@pytest.fixture
def small_pools(monkeypatch):
    monkeypatch.setitem(workers._SIZES, "turn", _SMALL)
    monkeypatch.setattr(workers, "_pools", {})
    yield
    for executor in workers._pools.values():
        executor.shutdown(wait=False, cancel_futures=True)


class _BlockedEngine:
    release = threading.Event()
    started = threading.Semaphore(0)

    def __init__(self, *, home: Path, cfg) -> None:  # noqa: ANN001
        self.session = SimpleNamespace(id=f"s-{uuid.uuid4().hex[:8]}", subdir="sessions")

    def run_turn(self, text, emit, **kwargs) -> None:  # noqa: ANN001
        type(self).started.release()
        type(self).release.wait(30)

    def request_interrupt(self, reason: str = "unknown") -> None:
        type(self).release.set()

    def save_session(self) -> None:
        return None


async def _open_turn(server, profile_home: Path):
    reader, writer = await asyncio.open_unix_connection(str(server.socket_path()))
    request_id = uuid.uuid4().hex
    writer.write((json.dumps({
        "id": request_id, "method": "host.chat.send",
        "params": {"profile": "default", "text": "hi", "request_id": request_id},
    }) + "\n").encode())
    await writer.drain()
    return reader, writer


async def _all_started(count: int, timeout: float) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while count:
        if _BlockedEngine.started.acquire(blocking=False):
            count -= 1
            continue
        assert asyncio.get_running_loop().time() < deadline, "turns did not start"
        await asyncio.sleep(0.02)


async def _next_event(reader, wanted: str, timeout: float) -> dict:
    async def scan() -> dict:
        while True:
            line = await reader.readline()
            assert line, "stream closed"
            frame = json.loads(line)
            if frame.get("event") == wanted:
                return frame
    return await asyncio.wait_for(scan(), timeout)


@pytest.mark.asyncio
async def test_blocked_turns_leave_websocket_rpcs_and_heartbeats_running(short_tmp, monkeypatch, small_pools) -> None:  # noqa: F811
    import alpi.engine
    from alpi import config as cfg_mod

    connections.invalidate_cache()
    loop = asyncio.get_running_loop()
    default = ThreadPoolExecutor(max_workers=_SMALL)
    loop.set_default_executor(default)
    _BlockedEngine.release = threading.Event()
    _BlockedEngine.started = threading.Semaphore(0)
    server, url = await _start_security_test_server(short_tmp, monkeypatch)
    home = short_tmp / "h"
    monkeypatch.setattr(cfg_mod, "load", lambda h: SimpleNamespace(model="x"))
    monkeypatch.setattr(alpi.engine, "Engine", _BlockedEngine)
    monkeypatch.setattr(dc, "_resolve_home", lambda profile: home)
    monkeypatch.setattr(dc, "_HEARTBEAT_PERIOD_S", 0.1)
    dc.register(server)
    _row, device = connections.create_connection("Web")
    streams = []
    try:
        for _ in range(_SMALL):
            streams.append(await _open_turn(server, home))
        await _all_started(_SMALL, 5)
        reader, _writer = streams[0]
        await _next_event(reader, "session_start", 5)
        assert (await _next_event(reader, "heartbeat", 3))["event"] == "heartbeat"
        async with websockets.connect(url) as ws:
            await ws.send(_ws_request(device["token"]))
            reply = json.loads(await asyncio.wait_for(ws.recv(), 3))
        assert "result" in reply
    finally:
        _BlockedEngine.release.set()
        for _reader, writer in streams:
            writer.close()
        await server.stop()
        default.shutdown(wait=False, cancel_futures=True)


@pytest.mark.asyncio
async def test_a_hung_email_probe_runs_on_its_own_pool(monkeypatch, tmp_path: Path) -> None:
    from alpi.host import probes
    from alpi.mail import accounts as accounts_mod

    hold = threading.Event()
    seen: list[str] = []

    def hung(home, account_id, account):  # noqa: ANN001
        seen.append(threading.current_thread().name)
        hold.wait(5)
        return {"status": "ok"}

    monkeypatch.setattr(probes, "_resolve_home", lambda profile: tmp_path)
    monkeypatch.setattr(accounts_mod, "get_account", lambda home, account_id: {"id": account_id})
    monkeypatch.setattr(probes, "_email_probe_blocking", hung)
    monkeypatch.setattr(probes, "_EMAIL_PROBE_TIMEOUT_SECS", 0.2)
    loop = asyncio.get_running_loop()
    default = ThreadPoolExecutor(max_workers=1)
    loop.set_default_executor(default)
    try:
        reply = await probes._email_probe({"profile": "default", "id": "a"}, None)
        assert reply == {"status": "error", "reason": "probe timed out"}
        assert seen and seen[0].startswith("alpi-probe")
        assert await asyncio.wait_for(asyncio.to_thread(lambda: "free"), 1) == "free"
    finally:
        hold.set()
        default.shutdown(wait=False, cancel_futures=True)


class _ChattyEngine(_BlockedEngine):
    def __init__(self, *, home: Path, cfg) -> None:  # noqa: ANN001
        self.session = SimpleNamespace(id="s-chatty", subdir="sessions")

    def run_turn(self, text, emit, **kwargs) -> None:  # noqa: ANN001
        from alpi.engine import AgentEvent

        for n in range(150):
            emit(AgentEvent(kind="assistant_delta", text=f"<{n}>"))
            if n % 10 == 0:
                threading.Event().wait(0.01)
        emit(AgentEvent(kind="assistant_done", text="done", final=True))


@pytest.mark.asyncio
async def test_a_turns_sidecar_keeps_the_order_its_frames_were_emitted(short_tmp, monkeypatch) -> None:  # noqa: F811
    import alpi.engine
    from alpi import config as cfg_mod
    from alpi.host import server as host_server

    home = short_tmp / "h"
    home.mkdir()
    monkeypatch.setattr(workers, "_pools", {})
    monkeypatch.setattr(cfg_mod, "load", lambda h: SimpleNamespace(model="x"))
    monkeypatch.setattr(alpi.engine, "Engine", _ChattyEngine)
    monkeypatch.setattr(dc, "_resolve_home", lambda profile: home)
    monkeypatch.setattr(dc, "_HEARTBEAT_PERIOD_S", 0.02)
    server = host_server.Server(home=home)
    dc.register(server)
    await server.start()
    try:
        reader, writer = await _open_turn(server, home)
        sent = []
        while True:
            line = await asyncio.wait_for(reader.readline(), 10)
            if not line:
                break
            sent.append(json.loads(line))
        writer.close()
    finally:
        await server.stop()
    recorded = [e["frame"] for e in _chat_events.read_since(home, "s-chatty")["events"]]
    deltas = [f["text"] for f in recorded if f.get("event") == "assistant_delta"]
    assert deltas == [f"<{n}>" for n in range(150)]
    streamed = [f for f in sent if f.get("event") not in ("preparing", "heartbeat")]
    assert [f.get("event") for f in recorded if f.get("event") != "heartbeat"] == [f.get("event") for f in streamed]


def test_the_daemon_keeps_its_pidfile_and_lock_until_running_turns_end_even_on_ctrl_c(tmp_path, monkeypatch) -> None:
    from alpi import service

    turn_done = threading.Event()
    order: list[str] = []

    class Lock:
        def close(self):
            order.append("lock released" if turn_done.is_set() else "lock released early")

    def turn():
        threading.Event().wait(0.2)
        os.kill(os.getpid(), signal.SIGINT)
        threading.Event().wait(0.3)
        turn_done.set()

    async def main(root, profiles):
        workers.submit("turn", turn)

    monkeypatch.setattr(workers, "_pools", {})
    monkeypatch.setattr(service, "_configure_logging_daemon", lambda root: None)
    monkeypatch.setattr(service, "_acquire_singleton_lock", lambda root: Lock())
    monkeypatch.setattr(service, "register_stack_dump", lambda root: None)
    monkeypatch.setattr(service, "_set_proctitle_daemon", lambda n: None)
    monkeypatch.setattr(service, "_write_daemon_pid", lambda root: None)
    monkeypatch.setattr(service, "_clear_daemon_pid", lambda root: order.append("pid cleared" if turn_done.is_set() else "pid cleared early"))
    monkeypatch.setattr(service, "_main_all", main)
    monkeypatch.setattr("alpi.provider_pause.activate", lambda: None)
    service.serve_all(tmp_path)
    assert order == ["pid cleared", "lock released"]
    assert signal.getsignal(signal.SIGINT) is signal.default_int_handler
