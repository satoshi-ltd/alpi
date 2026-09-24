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


def _seen_by(engine) -> list[str]:
    return [str(m.get("content") or "") for m in engine.session.messages]


def test_link_ask_scopes_history_by_conversation_within_a_peer(monkeypatch, tmp_path: Path) -> None:
    home = tmp_path / "bob"
    home.mkdir()
    captured: dict = {}
    _patch_engine(monkeypatch, captured)
    active = alp_handlers._ActiveTurn()

    first = alp_handlers._run_turn(home, "alice secret one", "alice", active, conversation="c1")
    alp_handlers._run_turn(home, "alice other topic", "alice", active, conversation="c2")
    alp_handlers._run_turn(home, "alice follow-up", "alice", active, conversation="c1")

    assert first["history"] == "conversation"
    assert not any("alice secret one" in m for m in _seen_by(captured["engines"][1]))
    third = _seen_by(captured["engines"][2])
    assert "alice secret one" in third and "echo: alice secret one" in third
    assert not any("alice other topic" in m for m in third)
    assert (home / "mentions" / "alice@c1.json").exists()
    assert (home / "mentions" / "alice@c2.json").exists()
    assert not (home / "mentions" / "alice.json").exists()


def test_link_ask_conversation_history_survives_a_restart(monkeypatch, tmp_path: Path) -> None:
    import json

    home = tmp_path / "bob"
    home.mkdir()
    captured: dict = {}
    _patch_engine(monkeypatch, captured)

    alp_handlers._run_turn(home, "turn one", "alice", alp_handlers._ActiveTurn(), conversation="c1")
    alp_handlers._run_turn(home, "turn two", "alice", alp_handlers._ActiveTurn(), conversation="c1")
    alp_handlers._run_turn(home, "turn three", "alice", alp_handlers._ActiveTurn(), conversation="c1")

    seen = _seen_by(captured["engines"][2])
    assert [m for m in seen if m.startswith("turn")] == ["turn one", "turn two"]
    stored = json.loads((home / "mentions" / "alice@c1.json").read_text())
    assert stored["sender"] == "alice" and stored["conversation"] == "c1"
    assert [t["user"] for t in stored["turns"]] == ["turn one", "turn two", "turn three"]


def test_link_ask_same_conversation_id_from_another_peer_selects_nothing(
    monkeypatch, tmp_path: Path,
) -> None:
    home = tmp_path / "bob"
    home.mkdir()
    captured: dict = {}
    _patch_engine(monkeypatch, captured)
    active = alp_handlers._ActiveTurn()

    alp_handlers._run_turn(home, "alice secret", "alice", active, conversation="shared-id")
    alp_handlers._run_turn(home, "carol asks", "carol", active, conversation="shared-id")

    assert not any("alice secret" in m for m in _seen_by(captured["engines"][1]))
    assert (home / "mentions" / "carol@shared-id.json").exists()


@pytest.mark.asyncio
async def test_streaming_link_ask_scopes_history_by_conversation(monkeypatch, tmp_path: Path) -> None:
    home = tmp_path / "bob"
    home.mkdir()
    captured: dict = {}
    _patch_engine(monkeypatch, captured)
    active = alp_handlers._ActiveTurn()
    lock = asyncio.Lock()

    async def run(prompt: str, conversation: str | None) -> dict:
        frames = [
            frame async for frame in alp_handlers._run_turn_stream(
                home, prompt, "alice", active, lock, conversation=conversation,
            )
        ]
        return frames[-1]

    first = await run("stream secret", "c1")
    await run("stream other", "c2")
    third = await run("stream follow-up", "c1")

    assert first["history"] == "conversation" and third["history"] == "conversation"
    assert not any("stream secret" in m for m in _seen_by(captured["engines"][1]))
    assert "stream secret" in _seen_by(captured["engines"][2])
    assert not any("stream other" in m for m in _seen_by(captured["engines"][2]))


def test_link_ask_without_an_establishable_conversation_uses_and_writes_no_history(
    monkeypatch, tmp_path: Path,
) -> None:
    home = tmp_path / "bob"
    home.mkdir()
    captured: dict = {}
    _patch_engine(monkeypatch, captured)
    active = alp_handlers._ActiveTurn()
    alp_handlers._run_turn(home, "legacy secret", "alice", active)
    alp_handlers._run_turn(home, "scoped secret", "alice", active, conversation="c1")
    before = sorted(p.name for p in (home / "mentions").iterdir())

    result = alp_handlers._run_turn(home, "anonymous ask", "alice", active, conversation="")
    again = alp_handlers._run_turn(home, "anonymous again", "alice", active, conversation="")

    assert result["history"] == "none" and again["history"] == "none"
    assert not any("secret" in m for m in _seen_by(captured["engines"][2]))
    assert not any("anonymous ask" in m for m in _seen_by(captured["engines"][3]))
    assert sorted(p.name for p in (home / "mentions").iterdir()) == before


def test_link_ask_keeps_the_legacy_thread_apart_from_conversation_threads(
    monkeypatch, tmp_path: Path,
) -> None:
    home = tmp_path / "bob"
    home.mkdir()
    captured: dict = {}
    _patch_engine(monkeypatch, captured)
    active = alp_handlers._ActiveTurn()

    legacy = alp_handlers._run_turn(home, "old secret", "alice", active)
    legacy_bytes = (home / "mentions" / "alice.json").read_bytes()
    scoped = alp_handlers._run_turn(home, "new conversation", "alice", active, conversation="c1")
    assert (home / "mentions" / "alice.json").read_bytes() == legacy_bytes
    legacy_again = alp_handlers._run_turn(home, "old follow-up", "alice", active)

    assert legacy["history"] == "peer" and scoped["history"] == "conversation"
    assert not any("old secret" in m for m in _seen_by(captured["engines"][1]))
    seen = _seen_by(captured["engines"][2])
    assert "old secret" in seen
    assert not any("new conversation" in m for m in seen)
    assert legacy_again["history"] == "peer"


@pytest.mark.asyncio
async def test_link_ask_handler_resolves_the_conversation_from_params(monkeypatch, tmp_path: Path) -> None:
    from alpi.alp import peers as peers_mod
    from alpi.alp import server as alp_server

    home = tmp_path / "bob"
    home.mkdir()
    captured: dict = {}
    _patch_engine(monkeypatch, captured)
    monkeypatch.setattr(
        alp_handlers.cfg_mod, "load", lambda _h: type("C", (), {"model": "x"})(),
    )
    server = alp_server.Server(home)
    alp_handlers.register_link_ask(server, home)
    alice = peers_mod.Peer(id="alice", pubkey="alice", allow=["link.ask"])
    ask = server.handlers["link.ask"]

    scoped = await ask({"prompt": "scoped", "conversation": "c1"}, alice, server)
    legacy = await ask({"prompt": "legacy"}, alice, server)
    malformed = await ask({"prompt": "malformed", "conversation": "../c1"}, alice, server)
    null = await ask({"prompt": "null", "conversation": None}, alice, server)
    frames = [
        f async for f in ask({"prompt": "streamed", "conversation": "c1", "stream": True}, alice, server)
    ]

    assert scoped["history"] == "conversation"
    assert legacy["history"] == "peer"
    assert malformed["history"] == "none" and null["history"] == "none"
    assert frames[-1]["history"] == "conversation"
    assert "scoped" in _seen_by(captured["engines"][4])
    assert not any("legacy" in m or "malformed" in m or "null" in m for m in _seen_by(captured["engines"][4]))
    assert not any("scoped" in m or "legacy" in m for m in _seen_by(captured["engines"][2]))
    assert sorted(p.name for p in (home / "mentions").iterdir()) == ["alice.json", "alice@c1.json"]


def test_link_ask_binds_each_peers_tool_policy_to_its_own_turn(monkeypatch, tmp_path: Path) -> None:
    from alpi import tools
    from alpi.tools import _policy

    home = tmp_path / "bob"
    home.mkdir()
    seen: list[tuple[frozenset[str] | None, bool, str]] = []

    class PolicyEngine(_FakeEngine):
        def run_turn(self, prompt, emit, *, source="user", persist_inflight=True):
            terminal = tools.get("terminal").schema()
            seen.append((_policy.allowed(), _policy.permits(terminal), _policy.refusal("terminal")))
            super().run_turn(prompt, emit, source=source, persist_inflight=persist_inflight)

    monkeypatch.setattr(alp_handlers, "Engine", lambda *, home, cfg: PolicyEngine(home=home, cfg=cfg))
    active = alp_handlers._ActiveTurn()

    alp_handlers._run_turn(
        home, "a", "alexandra", active, tool_allow=frozenset({"knowledge:search"}),
    )
    alp_handlers._run_turn(home, "b", "carol", active, tool_allow=frozenset({"terminal"}))
    alp_handlers._run_turn(home, "c", "dave", active)

    assert seen[0][:2] == (frozenset({"knowledge:search"}), False)
    assert "peer 'alexandra'" in seen[0][2]
    assert seen[1][:2] == (frozenset({"terminal"}), True)
    assert seen[2][:2] == (None, True)
    assert _policy.allowed() is None


@pytest.mark.asyncio
async def test_link_ask_handler_applies_the_pinned_peers_tool_policy_on_both_paths(
    monkeypatch, tmp_path: Path,
) -> None:
    from alpi.alp import peers as peers_mod
    from alpi.alp import server as alp_server
    from alpi.tools import _policy

    home = tmp_path / "bob"
    home.mkdir()
    seen: list[frozenset[str] | None] = []

    class PolicyEngine(_FakeEngine):
        def run_turn(self, prompt, emit, *, source="user", persist_inflight=True):
            seen.append(_policy.allowed())
            super().run_turn(prompt, emit, source=source, persist_inflight=persist_inflight)

    factory = lambda *, home, cfg: PolicyEngine(home=home, cfg=cfg)  # noqa: E731
    monkeypatch.setattr(alp_handlers, "Engine", factory)
    monkeypatch.setattr("alpi.engine.Engine", factory)
    monkeypatch.setattr(
        alp_handlers.cfg_mod, "load", lambda _h: type("C", (), {"model": "x"})(),
    )
    server = alp_server.Server(home)
    alp_handlers.register_link_ask(server, home)
    ask = server.handlers["link.ask"]
    alexandra = peers_mod.Peer(
        id="alexandra", pubkey="a", allow=["link.ask"],
        tools={"allow": ["knowledge:search", "alpi_knowledge"]},
    )
    carol = peers_mod.Peer(id="carol", pubkey="c", allow=["link.ask"])

    await ask({"prompt": "x"}, alexandra, server)
    [f async for f in ask({"prompt": "y", "stream": True}, alexandra, server)]
    await ask({"prompt": "z"}, carol, server)

    assert seen == [
        frozenset({"knowledge:search", "alpi_knowledge"}),
        frozenset({"knowledge:search", "alpi_knowledge"}),
        None,
    ]
    assert _policy.allowed() is None


@pytest.mark.asyncio
async def test_link_ask_refuses_a_peer_whose_tool_policy_is_malformed(monkeypatch, tmp_path: Path) -> None:
    from alpi.alp import peers as peers_mod
    from alpi.alp import server as alp_server

    home = tmp_path / "bob"
    home.mkdir()
    created: list = []

    def factory(*, home, cfg):  # noqa: ANN001
        created.append(1)
        return _FakeEngine(home=home, cfg=cfg)

    monkeypatch.setattr(alp_handlers, "Engine", factory)
    monkeypatch.setattr("alpi.engine.Engine", factory)
    monkeypatch.setattr(
        alp_handlers.cfg_mod, "load", lambda _h: type("C", (), {"model": "x"})(),
    )
    server = alp_server.Server(home)
    alp_handlers.register_link_ask(server, home)
    ask = server.handlers["link.ask"]
    broken = peers_mod.Peer(id="alexandra", pubkey="a", allow=["link.ask"], tools="terminal")
    legacy = peers_mod.Peer(id="bea", pubkey="b", allow=["link.ask"], tools={"deny": ["write_file"]})

    for peer, detail in ((broken, "peer 'alexandra'"), (legacy, "tools.allow")):
        for params in ({"prompt": "x"}, {"prompt": "y", "stream": True}):
            with pytest.raises(alp_server.HandlerError) as err:
                ask(params, peer, server)
            assert err.value.code == -32013 and err.value.message == "peer-policy-invalid"
            assert detail in err.value.data["detail"]
    assert created == []
