"""Tests for ``host.chat.send`` and ``host.chat.cancel``."""

from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from alpi.host import server as host_server
from alpi.alp.keys import load_or_generate
from alpi.host import chat as data_chat
from alpi.host import handlers as data_handlers


@pytest.fixture
def short_tmp() -> Path:
    d = Path(tempfile.mkdtemp(prefix="alp-chat-", dir="/tmp"))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


class _FakeEngine:
    """Minimal ``Engine`` stub for host-chat tests."""

    def __init__(self, *, home: Path, cfg) -> None:  # noqa: ANN001
        self.home = home
        self.session = SimpleNamespace(id="fake-session-id", subdir="sessions")
        self._interrupted = False

    def run_turn(self, text: str, emit) -> None:  # noqa: ANN001
        from alpi.engine import AgentEvent

        emit(AgentEvent(
            kind="tool_start", name="search", args={"q": "x"},
        ))
        emit(AgentEvent(kind="tool_end", name="search", ok=True))
        emit(AgentEvent(kind="assistant_done", text=f"echo: {text}"))

    def request_interrupt(self) -> None:
        self._interrupted = True

    def save_session(self) -> None:
        return None


def _patch_engine(monkeypatch) -> None:
    from alpi import config as cfg_mod
    from alpi.host import chat as dc

    monkeypatch.setattr(
        cfg_mod, "load", lambda h: SimpleNamespace(model="x"),
    )

    import alpi.engine
    monkeypatch.setattr(alpi.engine, "Engine", _FakeEngine)
    monkeypatch.setattr(
        dc, "_resolve_home", lambda profile: Path("/tmp"),
    )


@pytest.mark.asyncio
async def test_data_chat_send_rewrite_truncates_hydrated_session(
    monkeypatch, short_tmp: Path,
) -> None:
    home = short_tmp / "h"
    home.mkdir()
    load_or_generate(home)

    seen = {}

    class _RewriteEngine:
        def __init__(self, *, home: Path, cfg) -> None:  # noqa: ANN001
            self.home = home
            self.session = SimpleNamespace(
                id="rewrite-session",
                subdir="sessions",
                turns=[],
                messages=[],
                input_tokens=12,
                output_tokens=8,
                cost_usd=0.5,
                last_ctx_tokens=77,
            )

        def run_turn(self, text: str, emit) -> None:  # noqa: ANN001
            from alpi.engine import AgentEvent

            seen["text"] = text
            seen["turn_count"] = len(self.session.turns)
            seen["users"] = [getattr(t, "user", "") for t in self.session.turns]
            seen["messages"] = list(self.session.messages)
            seen["input_tokens"] = self.session.input_tokens
            emit(AgentEvent(kind="assistant_done", text=f"echo: {text}"))

        def request_interrupt(self) -> None:
            return None

        def save_session(self) -> None:
            return None

    from alpi import config as cfg_mod
    monkeypatch.setattr(cfg_mod, "load", lambda h: SimpleNamespace(model="x"))
    import alpi.engine
    monkeypatch.setattr(alpi.engine, "Engine", _RewriteEngine)
    from alpi.host import chat as dc
    monkeypatch.setattr(dc, "_resolve_home", lambda profile: home)

    def _fake_continue(engine, _home, _session_id):  # noqa: ANN001
        engine.session.turns = [
            SimpleNamespace(user="first", assistant="one"),
            SimpleNamespace(user="second", assistant="two"),
            SimpleNamespace(user="third", assistant="three"),
        ]
        engine.session.messages = [
            {"role": "system", "content": "note"},
            {"role": "user", "content": "first"},
            {"role": "assistant", "content": "one"},
            {"role": "user", "content": "second"},
            {"role": "assistant", "content": "two"},
            {"role": "user", "content": "third"},
            {"role": "assistant", "content": "three"},
        ]
        return True

    import alpi.cli as cli_mod
    monkeypatch.setattr(cli_mod, "_continue_specific_session", _fake_continue)

    srv = host_server.Server(home=home)
    data_handlers.register(srv)
    dc.register(srv)
    await srv.start()

    try:
        reader, writer = await asyncio.open_unix_connection(str(srv.socket_path()))
        writer.write((json.dumps({
            "id": "req-rw",
            "method": "host.chat.send",
            "params": {
                "profile": "default",
                "text": "rewrite me",
                "request_id": "req-rw",
                "session_id": "rewrite-session",
                "rewrite_from_turn": 1,
            },
        }) + "\n").encode("utf-8"))
        await writer.drain()

        while await reader.readline():
            pass
        writer.close()
        await writer.wait_closed()
    finally:
        await srv.stop()

    assert seen["text"] == "rewrite me"
    assert seen["turn_count"] == 1
    assert seen["users"] == ["first"]
    assert [m["role"] for m in seen["messages"]] == ["system", "user", "assistant"]
    assert seen["input_tokens"] == 0


@pytest.mark.asyncio
async def test_data_chat_send_streams_events_in_order(
    monkeypatch, short_tmp: Path,
) -> None:
    home = short_tmp / "h"
    home.mkdir()
    load_or_generate(home)
    _patch_engine(monkeypatch)
    from alpi.host import chat as dc
    monkeypatch.setattr(dc, "_resolve_home", lambda profile: home)

    srv = host_server.Server(home=home)
    data_handlers.register(srv)
    dc.register(srv)
    await srv.start()

    try:
        reader, writer = await asyncio.open_unix_connection(str(srv.socket_path()))
        request = {
            "id": "req-1",
            "method": "host.chat.send",
            "params": {
                "profile": "default",
                "text": "hello",
                "request_id": "req-1",
            },
        }
        writer.write((json.dumps(request) + "\n").encode("utf-8"))
        await writer.drain()

        events: list[dict] = []
        while True:
            line = await reader.readline()
            if not line:
                break
            events.append(json.loads(line))

        writer.close()
        await writer.wait_closed()
    finally:
        await srv.stop()

    kinds = [e.get("event") for e in events]
    assert kinds == [
        "tool_start", "tool_end", "reply", "done",
    ]
    reply = next(e for e in events if e["event"] == "reply")
    assert reply["text"] == "echo: hello"
    assert reply["session_id"] == "fake-session-id"


@pytest.mark.asyncio
async def test_data_chat_cancel_interrupts_active_turn(
    monkeypatch, short_tmp: Path,
) -> None:
    home = short_tmp / "h"
    home.mkdir()
    load_or_generate(home)

    from types import SimpleNamespace as NS

    class _SlowEngine:
        def __init__(self, *, home: Path, cfg) -> None:  # noqa: ANN001
            self.session = NS(id="slow-id", subdir="sessions")
            self._stop = False

        def run_turn(self, text, emit) -> None:  # noqa: ANN001
            from alpi.engine import AgentEvent
            import time as _t

            for _ in range(40):
                if self._stop:
                    emit(AgentEvent(kind="interrupted"))
                    return
                _t.sleep(0.025)
            emit(AgentEvent(kind="assistant_done", text="done"))

        def request_interrupt(self) -> None:
            self._stop = True

        def save_session(self) -> None:
            return None

    from alpi import config as cfg_mod

    monkeypatch.setattr(cfg_mod, "load", lambda h: NS(model="x"))
    import alpi.engine
    monkeypatch.setattr(alpi.engine, "Engine", _SlowEngine)
    from alpi.host import chat as dc
    monkeypatch.setattr(dc, "_resolve_home", lambda profile: home)

    srv = host_server.Server(home=home)
    data_handlers.register(srv)
    dc.register(srv)
    await srv.start()

    try:
        send_reader, send_writer = await asyncio.open_unix_connection(
            str(srv.socket_path()),
        )
        send_writer.write((json.dumps({
            "id": "r1",
            "method": "host.chat.send",
            "params": {
                "profile": "default",
                "text": "wait",
                "request_id": "r1",
            },
        }) + "\n").encode())
        await send_writer.drain()

        await asyncio.sleep(0.1)

        cancel_reader, cancel_writer = await asyncio.open_unix_connection(
            str(srv.socket_path()),
        )
        cancel_writer.write((json.dumps({
            "id": "c1",
            "method": "host.chat.cancel",
            "params": {"request_id": "r1"},
        }) + "\n").encode())
        await cancel_writer.drain()
        cancel_response = json.loads(await cancel_reader.readline())
        cancel_writer.close()
        await cancel_writer.wait_closed()

        events: list[dict] = []
        while True:
            line = await send_reader.readline()
            if not line:
                break
            events.append(json.loads(line))
        send_writer.close()
        await send_writer.wait_closed()
    finally:
        await srv.stop()

    assert cancel_response["result"]["cancelled"] is True
    kinds = [e.get("event") for e in events]
    assert "interrupted" in kinds
