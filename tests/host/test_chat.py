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

    def run_turn(self, text, emit, **kwargs) -> None:  # noqa: ANN001
        from alpi.engine import AgentEvent

        emit(AgentEvent(
            kind="tool_start", name="search", args={"q": "x"},
        ))
        emit(AgentEvent(kind="tool_end", name="search", ok=True))
        emit(AgentEvent(kind="assistant_done", text=f"echo: {text}", final=True))

    def request_interrupt(self, reason: str = "unknown") -> None:
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

        def run_turn(self, text, emit, **kwargs) -> None:  # noqa: ANN001
            from alpi.engine import AgentEvent

            seen["text"] = text
            seen["turn_count"] = len(self.session.turns)
            seen["users"] = [getattr(t, "user", "") for t in self.session.turns]
            seen["messages"] = list(self.session.messages)
            seen["input_tokens"] = self.session.input_tokens
            emit(AgentEvent(kind="assistant_done", text=f"echo: {text}", final=True))

        def request_interrupt(self, reason: str = "unknown") -> None:
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
async def test_data_chat_send_unknown_session_errors(
    monkeypatch, short_tmp: Path,
) -> None:
    home = short_tmp / "h"
    home.mkdir()
    load_or_generate(home)

    ran = {"turn": False}

    class _Engine:
        def __init__(self, *, home: Path, cfg) -> None:  # noqa: ANN001
            self.home = home
            self.session = SimpleNamespace(
                id="freshuuid0001", subdir="sessions", turns=[], messages=[],
            )

        def run_turn(self, text, emit, **kwargs) -> None:  # noqa: ANN001
            from alpi.engine import AgentEvent

            ran["turn"] = True
            emit(AgentEvent(kind="assistant_done", text=f"echo: {text}", final=True))

        def request_interrupt(self, reason: str = "unknown") -> None:
            return None

        def save_session(self) -> None:
            return None

    from alpi import config as cfg_mod
    monkeypatch.setattr(cfg_mod, "load", lambda h: SimpleNamespace(model="x"))
    import alpi.engine
    monkeypatch.setattr(alpi.engine, "Engine", _Engine)
    from alpi.host import chat as dc
    monkeypatch.setattr(dc, "_resolve_home", lambda profile: home)

    import alpi.cli as cli_mod
    monkeypatch.setattr(cli_mod, "_continue_specific_session", lambda *a, **k: False)

    srv = host_server.Server(home=home)
    data_handlers.register(srv)
    dc.register(srv)
    await srv.start()

    raw = b""
    try:
        reader, writer = await asyncio.open_unix_connection(str(srv.socket_path()))
        writer.write((json.dumps({
            "id": "req-missing",
            "method": "host.chat.send",
            "params": {
                "profile": "default",
                "text": "hello",
                "request_id": "req-missing",
                "session_id": "deadbeefdead",
            },
        }) + "\n").encode("utf-8"))
        await writer.drain()
        while True:
            line = await reader.readline()
            if not line:
                break
            raw += line
        writer.close()
        await writer.wait_closed()
    finally:
        await srv.stop()

    assert b"session not found" in raw
    assert b"echo:" not in raw
    assert ran["turn"] is False


@pytest.mark.asyncio
async def test_data_chat_send_mention_unknown_session_errors(
    monkeypatch, short_tmp: Path,
) -> None:
    home = short_tmp / "h"
    home.mkdir()
    load_or_generate(home)

    from alpi.alp import mention as alp_mention
    monkeypatch.setattr(
        alp_mention, "parse",
        lambda text, home=None: SimpleNamespace(peer_id="bob", prompt="hi"),
    )

    async def _empty(*a, **k):  # noqa: ANN001, ANN202
        for _ in ():
            yield

    monkeypatch.setattr(alp_mention, "execute_stream", _empty)

    from alpi import config as cfg_mod
    monkeypatch.setattr(cfg_mod, "load", lambda h: SimpleNamespace(model="x"))
    import alpi.engine
    monkeypatch.setattr(
        alpi.engine, "Engine",
        lambda *, home, cfg: SimpleNamespace(
            home=home,
            session=SimpleNamespace(
                id="freshuuid0002", subdir="sessions", turns=[], messages=[],
            ),
        ),
    )
    from alpi.host import chat as dc
    monkeypatch.setattr(dc, "_resolve_home", lambda profile: home)
    import alpi.cli as cli_mod
    monkeypatch.setattr(cli_mod, "_continue_specific_session", lambda *a, **k: False)

    srv = host_server.Server(home=home)
    data_handlers.register(srv)
    dc.register(srv)
    await srv.start()

    raw = b""
    try:
        reader, writer = await asyncio.open_unix_connection(str(srv.socket_path()))
        writer.write((json.dumps({
            "id": "req-m",
            "method": "host.chat.send",
            "params": {
                "profile": "default",
                "text": "@bob hi",
                "request_id": "req-m",
                "session_id": "deadbeefdead",
            },
        }) + "\n").encode("utf-8"))
        await writer.drain()
        while True:
            line = await reader.readline()
            if not line:
                break
            raw += line
        writer.close()
        await writer.wait_closed()
    finally:
        await srv.stop()

    assert b"session not found" in raw
    assert b"tool_start" not in raw


def test_truncate_hydrated_session_carries_attachment_markers() -> None:
    from alpi.host.chat import _truncate_hydrated_session

    engine = SimpleNamespace(session=SimpleNamespace(
        turns=[
            SimpleNamespace(
                user="mejora esta",
                assistant="hecho",
                attachments=[{"name": "room.jpg", "mime": "image/jpeg", "size": 10}],
                output_attachments=[
                    {"name": "x.jpg", "mime": "image/jpeg",
                     "path": "/tmp/out/x.jpg", "kind": "image"},
                ],
            ),
            SimpleNamespace(user="otra", assistant="vale", attachments=[], output_attachments=[]),
        ],
        messages=[], input_tokens=5, output_tokens=3, cost_usd=0.1, last_ctx_tokens=9,
    ))
    _truncate_hydrated_session(engine, 1)
    joined = "\n".join(m.get("content") or "" for m in engine.session.messages)
    assert "[attached: room.jpg (image/jpeg)]" in joined
    assert "/tmp/out/x.jpg" in joined
    assert engine.session.input_tokens == 0


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

    kinds = [e.get("event") for e in events if e.get("event") not in ("preparing", "heartbeat")]
    assert kinds == [
        "session_start", "tool_start", "tool_end", "reply", "done",
    ]
    start = next(e for e in events if e["event"] == "session_start")
    assert start["session_id"] == "fake-session-id"
    assert start["model_used"] == "x"
    reply = next(e for e in events if e["event"] == "reply")
    assert reply["text"] == "echo: hello"
    assert reply["session_id"] == "fake-session-id"


@pytest.mark.asyncio
async def test_local_delegate_owns_sidecar_and_marks_session_active(
    monkeypatch, short_tmp: Path,
) -> None:
    import threading

    home = short_tmp / "h"
    home.mkdir()
    load_or_generate(home)
    started = threading.Event()
    release = threading.Event()

    class _BlockingEngine(_FakeEngine):
        def __init__(self, *, home: Path, cfg) -> None:  # noqa: ANN001
            super().__init__(home=home, cfg=cfg)
            from alpi.host.connection_context import current
            self.session.connection_id = current().connection_id

        def run_turn(self, text, emit, **kwargs) -> None:  # noqa: ANN001
            from alpi.engine import AgentEvent

            started.set()
            emit(AgentEvent(kind="tool_start", name="search", args={"q": "x"}))
            release.wait(timeout=2)
            emit(AgentEvent(kind="assistant_done", text="done", final=True))

    from alpi import config as cfg_mod
    from alpi.host import chat as dc
    from alpi.host import connections
    import alpi.engine

    monkeypatch.setattr(cfg_mod, "load", lambda h: SimpleNamespace(model="x"))
    monkeypatch.setattr(alpi.engine, "Engine", _BlockingEngine)
    monkeypatch.setattr(dc, "_resolve_home", lambda profile: home)
    monkeypatch.setattr(connections, "list_connections", lambda: [{
        "id": "conn_test",
        "status": "active",
        "role": "admin",
        "profile_scope": [],
    }])

    srv = host_server.Server(home=home)
    data_handlers.register(srv)
    dc.register(srv)
    await srv.start()
    reader = writer = None
    try:
        reader, writer = await asyncio.open_unix_connection(str(srv.socket_path()))
        writer.write((json.dumps({
            "id": "delegated",
            "method": "host.chat.delegate",
            "params": {
                "profile": "smith",
                "connection_id": "conn_test",
                "text": "audit",
                "request_id": "delegated",
            },
        }) + "\n").encode())
        await writer.drain()
        assert await asyncio.to_thread(started.wait, 1)
        for _ in range(100):
            if dc.session_key("smith", "fake-session-id") in dc._session_active:
                break
            await asyncio.sleep(0.01)
        assert dc.session_key("smith", "fake-session-id") in dc._session_active
        assert dc._chat_events.connection_id(home, "fake-session-id") == "conn_test"
        replay = {"events": []}
        for _ in range(100):
            replay = dc._chat_events.read_since(home, "fake-session-id")
            if any(
                row["frame"].get("event") == "tool_start"
                for row in replay["events"]
            ):
                break
            await asyncio.sleep(0.01)
        assert any(
            row["frame"].get("event") == "tool_start"
            for row in replay["events"]
        )
        release.set()
        events = []
        while line := await reader.readline():
            events.append(json.loads(line))
        assert any(event.get("event") == "done" for event in events)
    finally:
        release.set()
        if writer is not None:
            writer.close()
            await writer.wait_closed()
        await srv.stop()


@pytest.mark.asyncio
async def test_delegate_rejects_unknown_connection(monkeypatch) -> None:
    from alpi.host import chat as dc
    from alpi.host import connections

    monkeypatch.setattr(connections, "list_connections", lambda: [])
    with pytest.raises(host_server.HandlerError, match="not-found"):
        await dc._data_chat_delegate({
            "profile": "smith",
            "connection_id": "conn_missing",
            "text": "audit",
            "request_id": "missing",
        }, host_server.Server(home=Path("/tmp")), lambda frame: None)


@pytest.mark.asyncio
async def test_delegate_preserves_member_profile_scope(monkeypatch) -> None:
    from alpi.host import chat as dc
    from alpi.host import connections

    monkeypatch.setattr(connections, "list_connections", lambda: [{
        "id": "conn_member",
        "status": "active",
        "role": "member",
        "profile_scope": ["neo"],
    }])
    with pytest.raises(host_server.HandlerError, match="forbidden"):
        await dc._data_chat_delegate({
            "profile": "smith",
            "connection_id": "conn_member",
            "text": "audit",
            "request_id": "scoped",
        }, host_server.Server(home=Path("/tmp")), lambda frame: None)


def test_chat_delegate_is_local_only() -> None:
    assert "host.chat.delegate" in host_server._LOCAL_ONLY_METHODS


@pytest.mark.asyncio
async def test_data_chat_send_reports_overridden_model(
    monkeypatch, short_tmp: Path,
) -> None:
    home = short_tmp / "h"
    home.mkdir()
    load_or_generate(home)

    from alpi import config as cfg_mod
    monkeypatch.setattr(
        cfg_mod, "load",
        lambda h: SimpleNamespace(model="x", model_reasoning=SimpleNamespace(effort="high")),
    )
    import alpi.engine
    monkeypatch.setattr(alpi.engine, "Engine", _FakeEngine)
    from alpi.host import chat as dc
    monkeypatch.setattr(dc, "_resolve_home", lambda profile: home)

    srv = host_server.Server(home=home)
    data_handlers.register(srv)
    dc.register(srv)
    await srv.start()

    try:
        reader, writer = await asyncio.open_unix_connection(str(srv.socket_path()))
        writer.write((json.dumps({
            "id": "req-ov",
            "method": "host.chat.send",
            "params": {
                "profile": "default",
                "text": "hello",
                "request_id": "req-ov",
                "model": "override-model",
            },
        }) + "\n").encode("utf-8"))
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

    start = next(e for e in events if e["event"] == "session_start")
    assert start["model_used"] == "override-model"


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

        def run_turn(self, text, emit, **kwargs) -> None:  # noqa: ANN001
            from alpi.engine import AgentEvent
            import time as _t

            for _ in range(40):
                if self._stop:
                    emit(AgentEvent(kind="interrupted"))
                    return
                _t.sleep(0.025)
            emit(AgentEvent(kind="assistant_done", text="done", final=True))

        def request_interrupt(self, reason: str = "unknown") -> None:
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


@pytest.mark.asyncio
async def test_engine_exception_emits_error_frame_before_done(
    monkeypatch, short_tmp: Path,
) -> None:
    """If engine.run_turn raises mid-turn (e.g. OSError(EMFILE) from a
    leaking tool), the desktop must receive an `error` frame BEFORE `done`
    or it clears pendingTurn and silently drops the error."""
    home = short_tmp / "h"
    home.mkdir()
    load_or_generate(home)

    class _CrashEngine:
        def __init__(self, *, home: Path, cfg) -> None:  # noqa: ANN001
            self.home = home
            self.session = SimpleNamespace(id="crash-sid", subdir="sessions")

        def run_turn(self, text, emit, **kwargs) -> None:  # noqa: ANN001
            from alpi.engine import AgentEvent

            emit(AgentEvent(kind="assistant_delta", text="partial"))
            raise OSError(24, "Too many open files")

        def request_interrupt(self, reason: str = "unknown") -> None:
            return None

        def save_session(self) -> None:
            return None

    from alpi import config as cfg_mod
    monkeypatch.setattr(cfg_mod, "load", lambda h: SimpleNamespace(model="x"))
    import alpi.engine
    monkeypatch.setattr(alpi.engine, "Engine", _CrashEngine)
    from alpi.host import chat as dc
    monkeypatch.setattr(dc, "_resolve_home", lambda profile: home)

    srv = host_server.Server(home=home)
    data_handlers.register(srv)
    dc.register(srv)
    await srv.start()

    try:
        reader, writer = await asyncio.open_unix_connection(str(srv.socket_path()))
        writer.write((json.dumps({
            "id": "req-crash",
            "method": "host.chat.send",
            "params": {
                "profile": "default",
                "text": "boom",
                "request_id": "req-crash",
            },
        }) + "\n").encode())
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
    assert "error" in kinds, kinds
    error_idx = kinds.index("error")
    done_idx = kinds.index("done") if "done" in kinds else len(kinds)
    assert error_idx < done_idx, (
        f"error must arrive before done so the desktop's pendingTurn captures it; got {kinds}"
    )


@pytest.mark.asyncio
async def test_data_chat_send_concurrent_same_session_returns_busy(
    monkeypatch, short_tmp: Path,
) -> None:
    home = short_tmp / "h"
    home.mkdir()
    load_or_generate(home)

    from types import SimpleNamespace as NS

    started = {"count": 0}

    class _SlowEngine:
        def __init__(self, *, home: Path, cfg) -> None:  # noqa: ANN001
            self.session = NS(id="shared-sid", subdir="sessions")
            self._stop = False
            self._idx = 0

        def run_turn(self, text, emit, **kwargs) -> None:  # noqa: ANN001
            from alpi.engine import AgentEvent
            import time as _t

            started["count"] += 1
            self._idx = started["count"]
            for _ in range(80):
                if self._stop:
                    emit(AgentEvent(kind="interrupted"))
                    return
                _t.sleep(0.025)
            emit(AgentEvent(kind="assistant_done", text=f"turn-{self._idx}:{text}", final=True))

        def request_interrupt(self, reason: str = "unknown") -> None:
            self._stop = True

        def save_session(self) -> None:
            return None

    from alpi import config as cfg_mod
    monkeypatch.setattr(cfg_mod, "load", lambda h: NS(model="x"))
    import alpi.engine
    monkeypatch.setattr(alpi.engine, "Engine", _SlowEngine)
    from alpi.host import chat as dc
    monkeypatch.setattr(dc, "_resolve_home", lambda profile: home)
    import alpi.cli as cli_mod
    monkeypatch.setattr(
        cli_mod, "_continue_specific_session",
        lambda *a, **kw: True,
    )

    srv = host_server.Server(home=home)
    data_handlers.register(srv)
    dc.register(srv)
    await srv.start()

    async def _send_and_collect(request_id: str, text: str) -> list[dict]:
        reader, writer = await asyncio.open_unix_connection(str(srv.socket_path()))
        writer.write((json.dumps({
            "id": request_id,
            "method": "host.chat.send",
            "params": {
                "profile": "default",
                "text": text,
                "request_id": request_id,
                "session_id": "shared-sid",
            },
        }) + "\n").encode())
        await writer.drain()
        events: list[dict] = []
        while True:
            line = await reader.readline()
            if not line:
                break
            events.append(json.loads(line))
        writer.close()
        await writer.wait_closed()
        return events

    try:
        task_a = asyncio.create_task(_send_and_collect("rA", "first"))
        # let A start running before B arrives
        await asyncio.sleep(0.15)
        task_b = asyncio.create_task(_send_and_collect("rB", "second"))
        events_a, events_b = await asyncio.gather(task_a, task_b)
    finally:
        await srv.stop()

    kinds_a = [e.get("event") for e in events_a]
    kinds_b = [e.get("event") for e in events_b]
    assert "interrupted" not in kinds_a, kinds_a
    assert "reply" in kinds_a and "done" in kinds_a, kinds_a
    assert any(e.get("event") == "error" and e.get("code") == "busy" for e in events_b), events_b
    assert "reply" not in kinds_b, kinds_b
    reply_a = next(e for e in events_a if e["event"] == "reply")
    assert reply_a["text"].endswith("first")


@pytest.mark.asyncio
async def test_data_chat_send_releases_claim_when_setup_raises(
    monkeypatch, short_tmp: Path,
) -> None:
    home = short_tmp / "h"
    home.mkdir()
    load_or_generate(home)

    from types import SimpleNamespace as NS

    class _Eng:
        def __init__(self, *, home: Path, cfg) -> None:  # noqa: ANN001
            self.session = NS(id="sid-leak", subdir="sessions")

        def run_turn(self, text, emit, **kwargs) -> None:  # noqa: ANN001
            return None

        def request_interrupt(self, reason: str = "unknown") -> None:
            return None

        def save_session(self) -> None:
            return None

    from alpi import config as cfg_mod
    monkeypatch.setattr(cfg_mod, "load", lambda h: NS(model="x"))
    import alpi.engine
    monkeypatch.setattr(alpi.engine, "Engine", _Eng)
    from alpi.host import chat as dc
    monkeypatch.setattr(dc, "_resolve_home", lambda profile: home)

    def _boom(*a, **kw):
        raise RuntimeError("setup boom")

    monkeypatch.setattr(dc._chat_events, "reset_for_turn", _boom)

    srv = host_server.Server(home=home)
    frames: list[dict] = []

    async def _send_frame(f) -> None:
        frames.append(f)

    dc._active.clear()
    dc._session_active.clear()
    with pytest.raises(RuntimeError, match="setup boom"):
        await dc._data_chat_send(
            {"profile": "default", "text": "hi", "request_id": "rZ", "session_id": None},
            srv,
            _send_frame,
        )

    assert dc._active == {}, dc._active
    assert dc._session_active == {}, dc._session_active


@pytest.mark.asyncio
async def test_data_chat_send_cleans_session_after_repeated_cancellation(
    monkeypatch, short_tmp: Path,
) -> None:
    import threading
    from alpi import config as cfg_mod
    from alpi.host import chat as dc

    home = short_tmp / "h"
    home.mkdir()
    load_or_generate(home)
    started = threading.Event()
    release = threading.Event()
    interrupted = threading.Event()

    class _BlockingEngine:
        def __init__(self, *, home: Path, cfg) -> None:  # noqa: ANN001
            self.session = SimpleNamespace(id="cancelled-session", subdir="sessions")

        def run_turn(self, text, emit, **kwargs) -> None:  # noqa: ANN001
            started.set()
            release.wait(timeout=2)

        def request_interrupt(self, reason: str = "unknown") -> None:
            interrupted.set()

        def save_session(self) -> None:
            return None

    monkeypatch.setattr(cfg_mod, "load", lambda h: SimpleNamespace(model="x"))
    import alpi.engine
    monkeypatch.setattr(alpi.engine, "Engine", _BlockingEngine)
    monkeypatch.setattr(dc, "_resolve_home", lambda profile: home)
    dc._active.clear()
    dc._session_active.clear()
    frames: list[dict] = []

    async def send_frame(frame: dict) -> None:
        frames.append(frame)

    task = asyncio.create_task(dc._data_chat_send({
        "profile": "default",
        "text": "wait",
        "request_id": "cancel-twice",
    }, host_server.Server(home=home), send_frame))
    assert await asyncio.to_thread(started.wait, 1)

    task.cancel()
    await asyncio.sleep(0)
    task.cancel()
    assert interrupted.wait(timeout=1)
    release.set()

    with pytest.raises(asyncio.CancelledError):
        await task
    assert dc._active == {}
    assert dc._session_active == {}
    assert not dc._get_session_lock(("default", "cancelled-session")).locked()


@pytest.mark.asyncio
async def test_chat_send_builds_engine_off_the_event_loop(
    monkeypatch, short_tmp: Path,
) -> None:
    import threading

    home = short_tmp / "h"
    home.mkdir()
    load_or_generate(home)
    seen: dict = {}

    class _ThreadProbeEngine(_FakeEngine):
        def __init__(self, *, home: Path, cfg) -> None:  # noqa: ANN001
            seen["thread"] = threading.current_thread()
            super().__init__(home=home, cfg=cfg)

    from alpi import config as cfg_mod
    monkeypatch.setattr(cfg_mod, "load", lambda h: SimpleNamespace(model="x"))
    import alpi.engine
    monkeypatch.setattr(alpi.engine, "Engine", _ThreadProbeEngine)
    from alpi.host import chat as dc
    monkeypatch.setattr(dc, "_resolve_home", lambda profile: home)

    srv = host_server.Server(home=home)
    data_handlers.register(srv)
    dc.register(srv)
    await srv.start()
    try:
        reader, writer = await asyncio.open_unix_connection(str(srv.socket_path()))
        writer.write((json.dumps({
            "id": "req-thread",
            "method": "host.chat.send",
            "params": {"profile": "default", "text": "hi", "request_id": "req-thread"},
        }) + "\n").encode("utf-8"))
        await writer.drain()
        while await reader.readline():
            pass
        writer.close()
        await writer.wait_closed()
    finally:
        await srv.stop()

    assert seen["thread"] is not threading.main_thread()


@pytest.mark.asyncio
async def test_data_chat_send_same_session_id_on_another_profile_is_not_busy(
    monkeypatch, short_tmp: Path,
) -> None:
    home = short_tmp / "h"
    home.mkdir()
    load_or_generate(home)
    _patch_engine(monkeypatch)
    from alpi.host import chat as dc
    import alpi.cli as cli_mod
    monkeypatch.setattr(cli_mod, "_continue_specific_session", lambda *a, **kw: True)

    # profile-a is mid-turn here — profile-b coincidentally shares the session id
    dc._session_active[dc.session_key("profile-a", "shared-sid")] = object()

    srv = host_server.Server(home=home)
    data_handlers.register(srv)
    dc.register(srv)
    await srv.start()

    events: list[dict] = []
    try:
        reader, writer = await asyncio.open_unix_connection(str(srv.socket_path()))
        writer.write((json.dumps({
            "id": "req-b",
            "method": "host.chat.send",
            "params": {
                "profile": "profile-b",
                "text": "hi",
                "request_id": "req-b",
                "session_id": "shared-sid",
            },
        }) + "\n").encode("utf-8"))
        await writer.drain()
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
    assert not any(e.get("event") == "error" and e.get("code") == "busy" for e in events), events
    assert "reply" in kinds and "done" in kinds, kinds
    assert dc.session_key("profile-a", "shared-sid") in dc._session_active


@pytest.mark.asyncio
async def test_data_chat_send_forwards_routing_and_reply_model(
    monkeypatch, short_tmp: Path,
) -> None:
    home = short_tmp / "h"
    home.mkdir()
    load_or_generate(home)

    class _RoutingEngine(_FakeEngine):
        def run_turn(self, text, emit, **kwargs) -> None:  # noqa: ANN001
            from alpi.engine import AgentEvent

            emit(AgentEvent(
                kind="routing", model="openrouter/deep",
                text="escalated to openrouter/deep (3 consecutive tool failures)",
            ))
            emit(AgentEvent(kind="assistant_done", text="rescued", final=True))

    from alpi import config as cfg_mod
    monkeypatch.setattr(cfg_mod, "load", lambda h: SimpleNamespace(model="x"))
    import alpi.engine
    monkeypatch.setattr(alpi.engine, "Engine", _RoutingEngine)
    from alpi.host import chat as dc
    monkeypatch.setattr(dc, "_resolve_home", lambda profile: home)

    srv = host_server.Server(home=home)
    data_handlers.register(srv)
    dc.register(srv)
    await srv.start()

    try:
        reader, writer = await asyncio.open_unix_connection(str(srv.socket_path()))
        writer.write((json.dumps({
            "id": "req-rt",
            "method": "host.chat.send",
            "params": {"profile": "default", "text": "hi", "request_id": "req-rt"},
        }) + "\n").encode("utf-8"))
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

    routing = next(e for e in events if e.get("event") == "routing")
    assert routing["model"] == "openrouter/deep"
    assert "escalated" in routing["text"]
    reply = next(e for e in events if e.get("event") == "reply")
    assert reply["model_used"] == "openrouter/deep"
    assert reply["text"] == "rescued"


@pytest.mark.asyncio
async def test_data_chat_send_forwards_usage_frames(
    monkeypatch, short_tmp: Path,
) -> None:
    home = short_tmp / "h"
    home.mkdir()
    load_or_generate(home)

    class _UsageEngine(_FakeEngine):
        def run_turn(self, text, emit, **kwargs) -> None:  # noqa: ANN001
            from alpi.engine import AgentEvent

            emit(AgentEvent(kind="tool_start", name="search", args={"q": "x"}))
            emit(AgentEvent(kind="tool_end", name="search", ok=True))
            emit(AgentEvent(
                kind="usage", tokens_in=42_000, tokens_out=120,
                cached_in=10_000, cost=0.0031, model="openrouter/z-ai/glm-5.3-flash",
                context_tokens=42_000,
            ))
            emit(AgentEvent(kind="assistant_done", text="done", final=True))

    from alpi import config as cfg_mod
    monkeypatch.setattr(cfg_mod, "load", lambda h: SimpleNamespace(model="x"))
    import alpi.engine
    monkeypatch.setattr(alpi.engine, "Engine", _UsageEngine)
    from alpi.host import chat as dc
    monkeypatch.setattr(dc, "_resolve_home", lambda profile: home)

    srv = host_server.Server(home=home)
    data_handlers.register(srv)
    dc.register(srv)
    await srv.start()

    try:
        reader, writer = await asyncio.open_unix_connection(str(srv.socket_path()))
        writer.write((json.dumps({
            "id": "req-us",
            "method": "host.chat.send",
            "params": {"profile": "default", "text": "hi", "request_id": "req-us"},
        }) + "\n").encode("utf-8"))
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

    usage = next(e for e in events if e.get("event") == "usage")
    assert usage["tokens_in"] == 42_000
    assert usage["tokens_out"] == 120
    assert usage["cached_in"] == 10_000
    assert usage["context_tokens"] == 42_000
    assert usage["cost"] == 0.0031
    assert usage["model"] == "openrouter/z-ai/glm-5.3-flash"
    kinds = [e.get("event") for e in events if e.get("event") not in ("preparing", "heartbeat")]
    assert kinds.index("usage") > kinds.index("tool_end")
    assert kinds.index("usage") < kinds.index("reply")


@pytest.mark.asyncio
async def test_preparing_and_heartbeat_precede_session_start(
    monkeypatch, short_tmp: Path,
) -> None:
    import time as _time

    home = short_tmp / "h"
    home.mkdir()
    load_or_generate(home)
    from alpi import config as cfg_mod
    from alpi.host import chat as dc

    monkeypatch.setattr(cfg_mod, "load", lambda h: SimpleNamespace(model="x"))

    class _SlowEngine(_FakeEngine):
        def __init__(self, *, home: Path, cfg) -> None:  # noqa: ANN001
            _time.sleep(0.15)
            super().__init__(home=home, cfg=cfg)

    import alpi.engine
    monkeypatch.setattr(alpi.engine, "Engine", _SlowEngine)
    monkeypatch.setattr(dc, "_resolve_home", lambda profile: home)

    srv = host_server.Server(home=home)
    data_handlers.register(srv)
    dc.register(srv)
    await srv.start()
    try:
        reader, writer = await asyncio.open_unix_connection(str(srv.socket_path()))
        writer.write((json.dumps({
            "id": "req-p", "method": "host.chat.send",
            "params": {"profile": "default", "text": "hi", "request_id": "req-p"},
        }) + "\n").encode("utf-8"))
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
    ss = kinds.index("session_start")
    assert "preparing" in kinds and kinds.index("preparing") < ss
    assert "heartbeat" in kinds and kinds.index("heartbeat") < ss


@pytest.mark.asyncio
async def test_concurrent_sends_same_session_second_gets_busy(
    monkeypatch, short_tmp: Path,
) -> None:
    import threading

    home = short_tmp / "h"
    home.mkdir()
    load_or_generate(home)
    from alpi import config as cfg_mod
    from alpi.host import chat as dc

    monkeypatch.setattr(cfg_mod, "load", lambda h: SimpleNamespace(model="x"))
    builds = {"n": 0}
    release = threading.Event()

    class _BlockingEngine(_FakeEngine):
        def __init__(self, *, home: Path, cfg) -> None:  # noqa: ANN001
            builds["n"] += 1
            release.wait(timeout=5)
            super().__init__(home=home, cfg=cfg)

    import alpi.engine
    monkeypatch.setattr(alpi.engine, "Engine", _BlockingEngine)
    monkeypatch.setattr(dc, "_resolve_home", lambda profile: home)

    sid = "abcdef012345"
    srv = host_server.Server(home=home)
    data_handlers.register(srv)
    dc.register(srv)
    await srv.start()

    async def _send(rid: str):
        reader, writer = await asyncio.open_unix_connection(str(srv.socket_path()))
        writer.write((json.dumps({
            "id": rid, "method": "host.chat.send",
            "params": {"profile": "default", "text": "hi", "request_id": rid, "session_id": sid},
        }) + "\n").encode("utf-8"))
        await writer.drain()
        return reader, writer

    try:
        ra, wa = await _send("A")
        for _ in range(200):
            if builds["n"] >= 1:
                break
            await asyncio.sleep(0.01)
        assert builds["n"] == 1

        rb, wb = await _send("B")
        b_events: list[dict] = []
        while True:
            line = await rb.readline()
            if not line:
                break
            b_events.append(json.loads(line))
        wb.close()
        await wb.wait_closed()

        release.set()
        while await ra.readline():
            pass
        wa.close()
        await wa.wait_closed()
    finally:
        release.set()
        await srv.stop()

    assert any(e.get("event") == "error" and e.get("code") == "busy" for e in b_events), b_events
    assert builds["n"] == 1
