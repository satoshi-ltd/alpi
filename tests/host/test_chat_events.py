"""Tests for the per-turn replay sidecar that backs ``host.chat.events_since``."""

from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from alpi.alp.keys import load_or_generate
from alpi.host import _chat_events as chat_events
from alpi.host import chat as data_chat
from alpi.host import handlers as data_handlers
from alpi.host import server as host_server


@pytest.fixture
def short_tmp() -> Path:
    d = Path(tempfile.mkdtemp(prefix="alp-chatev-", dir="/tmp"))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_append_assigns_monotonic_seq_and_read_since_filters(short_tmp: Path) -> None:
    home = short_tmp / "h"
    home.mkdir()
    sid = "sess1"
    chat_events.reset_for_turn(home, sid, "rid")
    seq_a = chat_events.append(home, sid, "rid", {"event": "tool_start", "name": "x"})
    seq_b = chat_events.append(home, sid, "rid", {"event": "assistant_delta", "text": "a"})
    seq_c = chat_events.append(home, sid, "rid", {"event": "assistant_delta", "text": "b"})

    assert (seq_a, seq_b, seq_c) == (1, 2, 3)

    full = chat_events.read_since(home, sid, after_seq=0)
    assert full["exists"] is True
    assert full["next_seq"] == 3
    kinds = [e["frame"]["event"] for e in full["events"]]
    assert kinds == ["tool_start", "assistant_delta", "assistant_delta"]

    partial = chat_events.read_since(home, sid, after_seq=2)
    assert [e["frame"]["text"] for e in partial["events"]] == ["b"]
    assert partial["next_seq"] == 3


def test_reset_for_turn_truncates_previous_turn(short_tmp: Path) -> None:
    home = short_tmp / "h"
    home.mkdir()
    sid = "sess2"
    chat_events.reset_for_turn(home, sid, "rid-1")
    chat_events.append(home, sid, "rid-1", {"event": "assistant_delta", "text": "old"})
    chat_events.reset_for_turn(home, sid, "rid-2")
    new_seq = chat_events.append(home, sid, "rid-2", {"event": "assistant_delta", "text": "fresh"})

    assert new_seq == 1
    state = chat_events.read_since(home, sid, after_seq=0)
    texts = [e["frame"].get("text") for e in state["events"]]
    assert "old" not in texts
    assert "fresh" in texts


def test_read_since_missing_file_returns_exists_false(short_tmp: Path) -> None:
    home = short_tmp / "h"
    home.mkdir()
    state = chat_events.read_since(home, "missing-sess", after_seq=0)
    assert state == {"events": [], "next_seq": 0, "exists": False}


def test_read_since_respects_limit(short_tmp: Path) -> None:
    home = short_tmp / "h"
    home.mkdir()
    sid = "sess3"
    chat_events.reset_for_turn(home, sid, "rid")
    for i in range(10):
        chat_events.append(home, sid, "rid", {"event": "assistant_delta", "text": f"d{i}"})
    state = chat_events.read_since(home, sid, after_seq=0, limit=3)
    assert len(state["events"]) == 3
    assert state["next_seq"] == 3


def test_oversized_frame_text_is_truncated(short_tmp: Path) -> None:
    home = short_tmp / "h"
    home.mkdir()
    sid = "sess4"
    chat_events.reset_for_turn(home, sid, "rid")
    big = "x" * (64 * 1024)
    chat_events.append(home, sid, "rid", {"event": "assistant_delta", "text": big})
    state = chat_events.read_since(home, sid, after_seq=0)
    persisted = state["events"][0]["frame"]["text"]
    assert len(persisted) < len(big)
    assert persisted.endswith("…")


class _FakeEngine:
    def __init__(self, *, home: Path, cfg) -> None:  # noqa: ANN001
        self.home = home
        self.session = SimpleNamespace(id="sess-stream", subdir="sessions")

    def run_turn(self, text, emit, **kwargs) -> None:  # noqa: ANN001
        from alpi.engine import AgentEvent

        emit(AgentEvent(kind="assistant_delta", text="hi "))
        emit(AgentEvent(kind="assistant_delta", text=text))
        emit(AgentEvent(kind="assistant_done", text=f"hi {text}", final=True))

    def request_interrupt(self) -> None:
        return None

    def save_session(self) -> None:
        return None


def _patch_engine(monkeypatch, home: Path) -> None:
    from alpi import config as cfg_mod
    monkeypatch.setattr(cfg_mod, "load", lambda h: SimpleNamespace(model="x"))
    import alpi.engine
    monkeypatch.setattr(alpi.engine, "Engine", _FakeEngine)
    monkeypatch.setattr(data_chat, "_resolve_home", lambda profile: home)
    import alpi.cli as cli_mod
    monkeypatch.setattr(cli_mod, "_continue_specific_session", lambda *a, **kw: True)


@pytest.mark.asyncio
async def test_chat_send_persists_frames_to_sidecar_for_existing_session(
    monkeypatch, short_tmp: Path,
) -> None:
    home = short_tmp / "h"
    home.mkdir()
    load_or_generate(home)
    _patch_engine(monkeypatch, home)

    srv = host_server.Server(home=home)
    data_handlers.register(srv)
    data_chat.register(srv)
    await srv.start()

    try:
        reader, writer = await asyncio.open_unix_connection(str(srv.socket_path()))
        writer.write((json.dumps({
            "id": "rep-1",
            "method": "host.chat.send",
            "params": {
                "profile": "default",
                "text": "ping",
                "request_id": "rep-1",
                "session_id": "sess-stream",
            },
        }) + "\n").encode())
        await writer.drain()
        while await reader.readline():
            pass
        writer.close()
        await writer.wait_closed()
    finally:
        await srv.stop()

    state = chat_events.read_since(home, "sess-stream", after_seq=0)
    assert state["exists"] is True
    kinds = [e["frame"]["event"] for e in state["events"]]
    # Frames emitted by the engine plus the daemon-side reply/done bookends.
    assert "assistant_delta" in kinds
    assert "reply" in kinds
    assert "done" in kinds
    assert state["next_seq"] >= 4


@pytest.mark.asyncio
async def test_events_since_rpc_returns_events_after_seq(
    monkeypatch, short_tmp: Path,
) -> None:
    home = short_tmp / "h"
    home.mkdir()
    load_or_generate(home)
    _patch_engine(monkeypatch, home)

    srv = host_server.Server(home=home)
    data_handlers.register(srv)
    data_chat.register(srv)
    await srv.start()

    try:
        reader, writer = await asyncio.open_unix_connection(str(srv.socket_path()))
        writer.write((json.dumps({
            "id": "rep-2",
            "method": "host.chat.send",
            "params": {
                "profile": "default",
                "text": "two",
                "request_id": "rep-2",
                "session_id": "sess-stream",
            },
        }) + "\n").encode())
        await writer.drain()
        while await reader.readline():
            pass
        writer.close()
        await writer.wait_closed()

        # Replay from seq 0 — same shape, same length.
        r, w = await asyncio.open_unix_connection(str(srv.socket_path()))
        w.write((json.dumps({
            "id": "es-1",
            "method": "host.chat.events_since",
            "params": {
                "profile": "default",
                "session_id": "sess-stream",
                "after_seq": 0,
            },
        }) + "\n").encode())
        await w.drain()
        response = json.loads(await r.readline())
        w.close()
        await w.wait_closed()
    finally:
        await srv.stop()

    payload = response["result"]
    assert payload["exists"] is True
    assert payload["in_flight"] is False
    kinds = [e["frame"]["event"] for e in payload["events"]]
    assert "reply" in kinds and "done" in kinds


@pytest.mark.asyncio
async def test_sidecar_finishes_turn_even_when_client_disconnects_mid_stream(
    monkeypatch, short_tmp: Path,
) -> None:
    """Replay only works if the sidecar has reply+done. If the consumer loop
    stops the moment send_frame raises (client gone), late events never get
    persisted and the desktop replay is incomplete."""
    home = short_tmp / "h"
    home.mkdir()
    load_or_generate(home)

    # Engine emits a delta, sleeps long enough for the client to close, then more deltas + done.
    class _SlowEngine:
        def __init__(self, *, home: Path, cfg) -> None:  # noqa: ANN001
            self.home = home
            self.session = SimpleNamespace(id="sess-disconnect", subdir="sessions")
            self._stop = False

        def run_turn(self, text, emit, **kwargs) -> None:  # noqa: ANN001
            from alpi.engine import AgentEvent
            import time as _t

            emit(AgentEvent(kind="assistant_delta", text="early "))
            _t.sleep(0.25)
            emit(AgentEvent(kind="assistant_delta", text="late"))
            emit(AgentEvent(kind="assistant_done", text="early late", final=True))

        def request_interrupt(self) -> None:
            self._stop = True

        def save_session(self) -> None:
            return None

    from alpi import config as cfg_mod
    monkeypatch.setattr(cfg_mod, "load", lambda h: SimpleNamespace(model="x"))
    import alpi.engine
    monkeypatch.setattr(alpi.engine, "Engine", _SlowEngine)
    monkeypatch.setattr(data_chat, "_resolve_home", lambda profile: home)
    import alpi.cli as cli_mod
    monkeypatch.setattr(cli_mod, "_continue_specific_session", lambda *a, **kw: True)

    srv = host_server.Server(home=home)
    data_handlers.register(srv)
    data_chat.register(srv)
    await srv.start()

    try:
        reader, writer = await asyncio.open_unix_connection(str(srv.socket_path()))
        writer.write((json.dumps({
            "id": "rep-disc",
            "method": "host.chat.send",
            "params": {
                "profile": "default",
                "text": "die mid-stream",
                "request_id": "rep-disc",
                "session_id": "sess-disconnect",
            },
        }) + "\n").encode())
        await writer.drain()
        # Read just the first frame, then drop the connection — mimics the freeze.
        await reader.readline()
        writer.close()
        await writer.wait_closed()

        # Give the daemon a moment to drain its queue + write the rest of the turn.
        await asyncio.sleep(0.6)
    finally:
        await srv.stop()

    state = chat_events.read_since(home, "sess-disconnect", after_seq=0)
    assert state["exists"] is True
    kinds = [e["frame"]["event"] for e in state["events"]]
    assert "reply" in kinds, (
        f"sidecar must capture reply even after client disconnect; got {kinds}"
    )
    assert "done" in kinds, (
        f"sidecar must capture done even after client disconnect; got {kinds}"
    )


@pytest.mark.asyncio
async def test_events_since_requires_session_id(short_tmp: Path) -> None:
    home = short_tmp / "h"
    home.mkdir()
    load_or_generate(home)

    srv = host_server.Server(home=home)
    data_handlers.register(srv)
    data_chat.register(srv)
    await srv.start()

    try:
        r, w = await asyncio.open_unix_connection(str(srv.socket_path()))
        w.write((json.dumps({
            "id": "es-bad",
            "method": "host.chat.events_since",
            "params": {"profile": "default"},
        }) + "\n").encode())
        await w.drain()
        response = json.loads(await r.readline())
        w.close()
        await w.wait_closed()
    finally:
        await srv.stop()

    assert response["error"]["code"] == -32602
