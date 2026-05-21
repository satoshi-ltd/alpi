"""``link.ask`` handler — turn semantics that don't need a real LLM."""

from __future__ import annotations

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

    def run_turn(self, prompt: str, emit, *, source: str = "user") -> None:  # noqa: ANN001
        from alpi.engine import AgentEvent

        # Snapshot the messages the engine "would have" seen — the
        # handler test reads this back to check thread hydration.
        self._messages_seen = list(self.session.messages)
        emit(AgentEvent(kind="assistant_done", text=f"echo: {prompt}", final=True))
        emit(AgentEvent(kind="usage", tokens_in=1, tokens_out=2, cost=0.0))

    def request_interrupt(self) -> None:
        return

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
    assert captured["engines"][0].session.saved is False
    assert not (home / "sessions").exists()


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
