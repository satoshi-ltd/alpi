from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from alpi.alp.keys import load_or_generate
from alpi.host import handlers as data_handlers
from alpi.host import server as host_server


@pytest.fixture
def short_tmp() -> Path:
    d = Path(tempfile.mkdtemp(prefix="alp-timing-", dir="/tmp"))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


def _engine_class(script):  # noqa: ANN001
    class _Engine:
        def __init__(self, *, home: Path, cfg) -> None:  # noqa: ANN001
            self.home = home
            self.session = SimpleNamespace(id="sid", subdir="sessions")

        def run_turn(self, text, emit, **kwargs) -> None:  # noqa: ANN001
            from alpi.engine import _ReasoningSpans
            spans = _ReasoningSpans(emit, time.time(), [])
            script(spans)
            spans.close()

        def request_interrupt(self, reason: str = "unknown") -> None:
            pass

        def save_session(self) -> None:
            return None

    return _Engine


async def _stream(monkeypatch, home: Path, script) -> list[dict]:  # noqa: ANN001
    import alpi.engine
    from alpi import config as cfg_mod
    from alpi.host import chat as dc

    monkeypatch.setattr(cfg_mod, "load", lambda h: SimpleNamespace(model="x"))
    monkeypatch.setattr(alpi.engine, "Engine", _engine_class(script))
    monkeypatch.setattr(dc, "_resolve_home", lambda profile: home)
    srv = host_server.Server(home=home)
    data_handlers.register(srv)
    dc.register(srv)
    await srv.start()
    try:
        reader, writer = await asyncio.open_unix_connection(str(srv.socket_path()))
        writer.write((json.dumps({
            "id": "req", "method": "host.chat.send",
            "params": {"profile": "default", "text": "hi", "request_id": "req"},
        }) + "\n").encode())
        await writer.drain()
        frames = []
        while True:
            line = await reader.readline()
            if not line:
                break
            frames.append(json.loads(line))
        writer.close()
        await writer.wait_closed()
    finally:
        await srv.stop()
    return [f for f in frames if f.get("event") not in ("preparing", "heartbeat")]


@pytest.mark.asyncio
async def test_tool_frames_carry_start_time_and_duration(monkeypatch, short_tmp: Path) -> None:
    home = short_tmp / "h"
    home.mkdir()
    load_or_generate(home)

    def script(emit) -> None:  # noqa: ANN001
        from alpi.engine import AgentEvent
        emit(AgentEvent(kind="tool_start", name="read_file", tool_id="t1", args={"path": "a"}))
        time.sleep(0.2)
        emit(AgentEvent(kind="tool_end", name="read_file", tool_id="t1", ok=True, output="x"))
        emit(AgentEvent(kind="assistant_done", text="ok", final=True))

    before = time.time()
    frames = await _stream(monkeypatch, home, script)

    start = next(f for f in frames if f["event"] == "tool_start")
    end = next(f for f in frames if f["event"] == "tool_end")
    assert before <= start["started_at"] <= time.time()
    assert isinstance(end["duration_s"], float)
    assert 0.1 <= end["duration_s"] < 5.0
    assert end["duration_s"] == round(end["duration_s"], 1)
    assert not any(f["event"] == "reasoning_done" for f in frames)

    from alpi.host import _chat_events
    stored = _chat_events.read_since(home, "sid", after_seq=0)["events"]
    kinds = {e.get("event"): e for e in (s.get("frame", s) for s in stored)}
    assert "started_at" in kinds["tool_start"]
    assert "duration_s" in kinds["tool_end"]


@pytest.mark.asyncio
async def test_reasoning_done_fires_once_per_step_after_reasoning(monkeypatch, short_tmp: Path) -> None:
    home = short_tmp / "h"
    home.mkdir()
    load_or_generate(home)

    def script(emit) -> None:  # noqa: ANN001
        from alpi.engine import AgentEvent
        emit(AgentEvent(kind="reasoning_delta", text="thinking"))
        time.sleep(0.1)
        emit(AgentEvent(kind="reasoning_delta", text=" more"))
        emit(AgentEvent(kind="tool_start", name="grep", tool_id="t1"))
        emit(AgentEvent(kind="tool_end", name="grep", tool_id="t1", ok=True))
        emit(AgentEvent(kind="reasoning_delta", text="again"))
        emit(AgentEvent(kind="assistant_delta", text="Hel"))
        emit(AgentEvent(kind="assistant_delta", text="lo"))
        emit(AgentEvent(kind="assistant_done", text="Hello", final=True))

    frames = await _stream(monkeypatch, home, script)
    kinds = [f["event"] for f in frames]

    assert kinds.count("reasoning_done") == 2
    first = kinds.index("reasoning_done")
    assert kinds[first - 1] == "reasoning_delta"
    assert kinds[first + 1] == "tool_start"
    second = kinds.index("reasoning_done", first + 1)
    assert kinds[second + 1] == "assistant_delta"
    seconds = [f["seconds"] for f in frames if f["event"] == "reasoning_done"]
    assert seconds[0] >= 0.1
    assert all(isinstance(s, float) for s in seconds)


@pytest.mark.asyncio
async def test_no_reasoning_done_without_reasoning(monkeypatch, short_tmp: Path) -> None:
    home = short_tmp / "h"
    home.mkdir()
    load_or_generate(home)

    def script(emit) -> None:  # noqa: ANN001
        from alpi.engine import AgentEvent
        emit(AgentEvent(kind="assistant_delta", text="Hi"))
        emit(AgentEvent(kind="assistant_done", text="Hi", final=True))

    frames = await _stream(monkeypatch, home, script)
    assert "reasoning_done" not in [f["event"] for f in frames]


@pytest.mark.asyncio
async def test_reasoning_only_step_still_closes(monkeypatch, short_tmp: Path) -> None:
    home = short_tmp / "h"
    home.mkdir()
    load_or_generate(home)

    def script(emit) -> None:  # noqa: ANN001
        from alpi.engine import AgentEvent
        emit(AgentEvent(kind="reasoning_delta", text="hmm"))

    frames = await _stream(monkeypatch, home, script)
    kinds = [f["event"] for f in frames]
    assert kinds.count("reasoning_done") == 1
    assert kinds.index("reasoning_done") < kinds.index("reply")


@pytest.mark.asyncio
async def test_interleaved_reasoning_counts_each_span_from_its_own_start(
    monkeypatch, short_tmp: Path,
) -> None:
    home = short_tmp / "h"
    home.mkdir()
    load_or_generate(home)

    def script(emit) -> None:  # noqa: ANN001
        from alpi.engine import AgentEvent
        emit(AgentEvent(kind="reasoning_delta", text="a"))
        emit(AgentEvent(kind="assistant_delta", text="Part one. "))
        time.sleep(0.5)
        emit(AgentEvent(kind="reasoning_delta", text="b"))
        time.sleep(0.2)
        emit(AgentEvent(kind="assistant_delta", text="Part two."))
        emit(AgentEvent(kind="assistant_done", text="Part one. Part two.", final=True))

    frames = await _stream(monkeypatch, home, script)
    seconds = [f["seconds"] for f in frames if f["event"] == "reasoning_done"]

    assert len(seconds) == 2
    assert 0.1 <= seconds[1] < 0.5


@pytest.mark.asyncio
async def test_reasoning_done_frames_carry_engine_seconds_verbatim(monkeypatch, short_tmp: Path) -> None:
    home = short_tmp / "h"
    home.mkdir()
    load_or_generate(home)

    def script(emit) -> None:  # noqa: ANN001
        from alpi.engine import AgentEvent
        emit(AgentEvent(kind="reasoning_done", seconds=7.3))
        emit(AgentEvent(kind="assistant_done", text="ok", final=True))

    frames = await _stream(monkeypatch, home, script)
    assert [f["seconds"] for f in frames if f["event"] == "reasoning_done"] == [7.3]


class _CrashEngine:
    def __init__(self, *, home: Path, cfg) -> None:  # noqa: ANN001
        self.home = home
        self.session = SimpleNamespace(id="sid-crash", subdir="sessions", connection_id="host", device_id="")
        self.saved = 0

    def run_turn(self, text, emit, **kwargs) -> None:  # noqa: ANN001
        raise RuntimeError("provider exploded")

    def request_interrupt(self, reason: str = "unknown") -> None:
        pass


@pytest.mark.asyncio
@pytest.mark.parametrize("save_works", [True, False])
async def test_crashed_turn_closes_in_flight(monkeypatch, short_tmp: Path, save_works: bool) -> None:
    import alpi.engine
    from alpi import config as cfg_mod
    from alpi.host import chat as dc
    from alpi.host import events as host_events

    home = short_tmp / "h"
    home.mkdir()
    load_or_generate(home)
    engines: list = []

    class _Engine(_CrashEngine):
        def __init__(self, **kw) -> None:  # noqa: ANN003
            super().__init__(**kw)
            engines.append(self)

        def save_session(self) -> None:
            if not save_works:
                raise OSError("disk full")
            self.saved += 1

    monkeypatch.setattr(cfg_mod, "load", lambda h: SimpleNamespace(model="x"))
    monkeypatch.setattr(alpi.engine, "Engine", _Engine)
    monkeypatch.setattr(dc, "_resolve_home", lambda profile: home)
    events: list = []
    listener = lambda kind, data: events.append((kind, dict(data)))  # noqa: E731
    host_events.add_listener(listener)
    srv = host_server.Server(home=home)
    data_handlers.register(srv)
    dc.register(srv)
    await srv.start()
    try:
        reader, writer = await asyncio.open_unix_connection(str(srv.socket_path()))
        writer.write((json.dumps({
            "id": "req", "method": "host.chat.send",
            "params": {"profile": "default", "text": "hi", "request_id": "req"},
        }) + "\n").encode())
        await writer.drain()
        while await reader.readline():
            pass
        writer.close()
        await writer.wait_closed()
    finally:
        await srv.stop()
        host_events.remove_listener(listener)

    if save_works:
        assert engines[0].saved == 1
    else:
        closes = [d for k, d in events if k == "session_changed"]
        assert closes == [{
            "profile": "default", "id": "sid-crash", "subdir": "sessions",
            "connection_id": "host", "device_id": "", "in_flight": False,
        }]
