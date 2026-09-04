"""``link.ask`` handler — turn semantics that don't need a real LLM."""

from __future__ import annotations

import asyncio
import threading
import time
from pathlib import Path

import pytest

from alpi.alp import handlers as alp_handlers


class _FakeSession:
    def __init__(self) -> None:
        self.id = "fake-session-id"
        self.saved = False
        self.messages: list[dict] = []

    def save(self) -> None:
        self.saved = True


class _FakeEngine:
    def __init__(self, *, home: Path, cfg) -> None:  # noqa: ANN001
        self.session = _FakeSession()

    def run_turn(
        self, prompt: str, emit, *, source: str = "user",
        persist_inflight: bool = True,
    ) -> None:  # noqa: ANN001
        self.source = source
        self.persist_inflight = persist_inflight
        from alpi.engine import AgentEvent

        # Snapshot the messages the engine "would have" seen — the
        # handler test reads this back to check thread hydration.
        self._messages_seen = list(self.session.messages)
        emit(AgentEvent(kind="assistant_done", text=f"echo: {prompt}", final=True))
        emit(AgentEvent(kind="usage", tokens_in=1, tokens_out=2, cost=0.0))

    def request_interrupt(self, reason: str = "") -> None:
        self.interrupt_reason = reason

    def save_session(self) -> Path | None:
        # Mirrors the real engine's save path — record the call so the
        # test can assert it never happens for ``link.ask``.
        self.session.save()
        return Path("/tmp/should-not-exist")


def _patch_engine(monkeypatch, captured: dict) -> None:
    """Wire ``handlers.Engine`` to a fake that just echoes the prompt."""
    def _factory(*, home: Path, cfg) -> _FakeEngine:  # noqa: ANN001
        eng = _FakeEngine(home=home, cfg=cfg)
        captured.setdefault("engines", []).append(eng)
        return eng

    monkeypatch.setattr(alp_handlers, "Engine", _factory)
    monkeypatch.setattr("alpi.engine.Engine", _factory)
    monkeypatch.setattr(
        alp_handlers.cfg_mod, "load", lambda h: type("C", (), {"model": "x"})()
    )


def test_link_ask_does_not_persist_session(monkeypatch, tmp_path: Path) -> None:
    """Mentions are one-shot — they must not leave a file under
    ``sessions/`` so ``alpi -p <peer> --continue`` doesn't pick them up."""
    home = tmp_path / "bob"
    home.mkdir()

    captured: dict = {}
    _patch_engine(monkeypatch, captured)

    active = alp_handlers._ActiveTurn()
    out = alp_handlers._run_turn(home, "hello", "alice", active)

    assert out["text"] == "echo: hello"
    assert out["tokens_in"] == 1
    assert captured["engines"][0].source == "peer"
    assert captured["engines"][0].persist_inflight is False
    assert captured["engines"][0].session.saved is False
    assert not (home / "sessions").exists()


@pytest.mark.asyncio
async def test_streaming_link_ask_does_not_persist_inflight_stub(
    monkeypatch, tmp_path: Path,
) -> None:
    """The streaming path is what host chat @mentions use. It must also
    disable the engine's early in-flight session stub; mention history
    lives under ``mentions/<sender>.json`` instead."""
    home = tmp_path / "bob"
    home.mkdir()

    captured: dict = {}
    _patch_engine(monkeypatch, captured)

    active = alp_handlers._ActiveTurn()
    lock = __import__("asyncio").Lock()
    frames = [
        frame async for frame in alp_handlers._run_turn_stream(
            home, "hello", "alice", active, lock,
        )
    ]

    assert frames[-1]["kind"] == "final"
    assert frames[-1]["text"] == "echo: hello"
    assert frames[0] == {
        "kind": "chunk",
        "event": "started",
        "session_id": "fake-session-id",
    }
    assert captured["engines"][0].source == "peer"
    assert captured["engines"][0].persist_inflight is False
    assert captured["engines"][0].session.saved is False
    assert not (home / "sessions").exists()


@pytest.mark.asyncio
async def test_streaming_link_ask_preserves_remote_transient_error(
    monkeypatch, tmp_path: Path,
) -> None:
    from alpi.engine import AgentEvent

    home = tmp_path / "bob"
    home.mkdir()

    class TransientEngine(_FakeEngine):
        def run_turn(
            self, prompt, emit, *, source="user", persist_inflight=True,
        ):
            emit(AgentEvent(
                kind="error", text="provider unavailable", transient=True,
            ))

    def factory(*, home: Path, cfg):
        return TransientEngine(home=home, cfg=cfg)

    monkeypatch.setattr(alp_handlers, "Engine", factory)
    monkeypatch.setattr("alpi.engine.Engine", factory)
    monkeypatch.setattr(
        alp_handlers.cfg_mod, "load", lambda _h: type("C", (), {"model": "x"})(),
    )

    frames = [
        frame async for frame in alp_handlers._run_turn_stream(
            home, "hello", "alice", alp_handlers._ActiveTurn(), asyncio.Lock(),
        )
    ]

    assert frames[-1]["text"] == "[error] provider unavailable"
    assert frames[-1]["transient"] is True
    direct = alp_handlers._run_turn(
        home, "hello", "alice", alp_handlers._ActiveTurn(),
    )
    assert direct["transient"] is True


@pytest.mark.asyncio
async def test_streaming_link_ask_keeps_active_turn_alive_with_progress_frames(
    monkeypatch, tmp_path: Path,
) -> None:
    home = tmp_path / "bob"
    home.mkdir()
    captured: dict = {}

    class SlowEngine(_FakeEngine):
        def run_turn(self, prompt, emit, *, source="user", persist_inflight=True):
            time.sleep(0.04)
            super().run_turn(
                prompt, emit, source=source, persist_inflight=persist_inflight,
            )

    def factory(*, home: Path, cfg):
        engine = SlowEngine(home=home, cfg=cfg)
        captured["engine"] = engine
        return engine

    monkeypatch.setattr(alp_handlers, "Engine", factory)
    monkeypatch.setattr("alpi.engine.Engine", factory)
    monkeypatch.setattr(
        alp_handlers.cfg_mod, "load", lambda _h: type("C", (), {"model": "x"})(),
    )
    monkeypatch.setattr(alp_handlers, "_LINK_PROGRESS_INTERVAL_SECONDS", 0.01)

    frames = [
        frame async for frame in alp_handlers._run_turn_stream(
            home, "hello", "alice", alp_handlers._ActiveTurn(), asyncio.Lock(),
        )
    ]

    assert any(frame.get("event") == "progress" for frame in frames)
    assert frames[-1]["kind"] == "final"


@pytest.mark.asyncio
async def test_stream_disconnect_interrupts_the_remote_turn(
    monkeypatch, tmp_path: Path,
) -> None:
    home = tmp_path / "bob"
    home.mkdir()
    interrupted = threading.Event()

    class BlockingEngine(_FakeEngine):
        def run_turn(self, prompt, emit, *, source="user", persist_inflight=True):
            interrupted.wait(timeout=1)

        def request_interrupt(self, reason: str = "") -> None:
            self.interrupt_reason = reason
            interrupted.set()

    engine_box: dict = {}

    def factory(*, home: Path, cfg):
        engine = BlockingEngine(home=home, cfg=cfg)
        engine_box["engine"] = engine
        return engine

    monkeypatch.setattr(alp_handlers, "Engine", factory)
    monkeypatch.setattr("alpi.engine.Engine", factory)
    monkeypatch.setattr(
        alp_handlers.cfg_mod, "load", lambda _h: type("C", (), {"model": "x"})(),
    )

    active = alp_handlers._ActiveTurn()
    stream = alp_handlers._run_turn_stream(
        home, "wait", "alice", active, asyncio.Lock(),
    )
    started = await anext(stream)
    await stream.aclose()

    assert started["event"] == "started"
    assert engine_box["engine"].interrupt_reason == "alp-disconnect"
    assert active.engine is None


@pytest.mark.asyncio
async def test_link_cancel_only_interrupts_the_calling_peers_turn(
    monkeypatch, tmp_path: Path,
) -> None:
    from alpi.alp import peers as peers_mod
    from alpi.alp import server as alp_server

    home = tmp_path / "bob"
    home.mkdir()
    interrupted = threading.Event()

    class BlockingEngine(_FakeEngine):
        def run_turn(self, prompt, emit, *, source="user", persist_inflight=True):
            interrupted.wait(timeout=1)

        def request_interrupt(self, reason: str = "") -> None:
            self.interrupt_reason = reason
            interrupted.set()

    monkeypatch.setattr(alp_handlers, "Engine", BlockingEngine)
    monkeypatch.setattr("alpi.engine.Engine", BlockingEngine)
    monkeypatch.setattr(
        alp_handlers.cfg_mod, "load", lambda _h: type("C", (), {"model": "x"})(),
    )

    server = alp_server.Server(home)
    alp_handlers.register_link_ask(server, home)
    alice = peers_mod.Peer(id="alice", pubkey="alice", allow=["link.ask"])
    carol = peers_mod.Peer(id="carol", pubkey="carol", allow=["link.ask"])
    stream = server.handlers["link.ask"](
        {"prompt": "wait", "stream": True}, alice, server,
    )
    await anext(stream)

    wrong = await server.handlers["link.cancel"]({}, carol, server)
    right = await server.handlers["link.cancel"]({}, alice, server)
    await stream.aclose()

    assert wrong == {"cancelled": False}
    assert right["cancelled"] is True


def test_link_ask_persists_per_sender_mention_thread(monkeypatch, tmp_path: Path) -> None:
    """Successive mentions from the same sender must share memory: the
    second turn's engine must see the first turn's user/assistant pair
    in its message thread."""
    from alpi.alp import mention_thread

    home = tmp_path / "bob"
    home.mkdir()

    captured: dict = {}
    _patch_engine(monkeypatch, captured)

    active = alp_handlers._ActiveTurn()
    alp_handlers._run_turn(home, "first turn", "alice", active)

    thread_path = home / "mentions" / "alice.json"
    assert thread_path.exists()
    saved = mention_thread.load(home, "alice")
    assert [(t.user, t.assistant) for t in saved.turns] == [
        ("first turn", "echo: first turn"),
    ]

    alp_handlers._run_turn(home, "second turn", "alice", active)
    second_engine = captured["engines"][1]
    msgs = second_engine.session.messages
    assert any(
        m.get("role") == "user" and m.get("content") == "first turn" for m in msgs
    )
    assert any(
        m.get("role") == "assistant" and m.get("content") == "echo: first turn"
        for m in msgs
    )


def test_link_ask_isolates_threads_per_sender(monkeypatch, tmp_path: Path) -> None:
    """Alice's thread must not leak into Carol's turn — each remitente
    keeps its own context."""
    home = tmp_path / "bob"
    home.mkdir()

    captured: dict = {}
    _patch_engine(monkeypatch, captured)

    active = alp_handlers._ActiveTurn()
    alp_handlers._run_turn(home, "alice secret", "alice", active)
    alp_handlers._run_turn(home, "hi from carol", "carol", active)

    carol_engine = captured["engines"][1]
    assert not any(
        "alice secret" in str(m.get("content") or "")
        for m in carol_engine.session.messages
    )
