"""ALN — ``chat.turn_done`` event emission rules.

Emitted only when a user-initiated turn completes naturally and crosses the
"worth notifying" bar: at least one tool call OR ≥5s of work. Skipped for
peer-initiated turns and for trivial fast exchanges so mobile ambient
notifications stay signal-only."""

from __future__ import annotations

from pathlib import Path

import pytest

from alpi import config, home, memory
from alpi.engine import Engine


@pytest.fixture
def bootstrapped_home(tmp_path: Path) -> Path:
    home.ensure_home(tmp_path)
    config.seed_defaults(tmp_path)
    memory.MemoryStore(tmp_path).seed_defaults()
    return tmp_path


def _trivial_stream(*_a, **_kw):
    yield {"text_delta": "hola", "reasoning_delta": "", "tool_calls_delta": []}
    yield {
        "final": True, "tool_calls": [],
        "input_tokens": 1, "output_tokens": 1, "cost_usd": 0.0,
    }


def _write_file_then_done_stream(target: Path):
    steps = [
        [
            {"text_delta": "", "reasoning_delta": "", "tool_calls_delta": []},
            {
                "final": True,
                "tool_calls": [{
                    "id": "tc1",
                    "name": "write_file",
                    "arguments": '{"path": "' + str(target) + '", "content": "hi"}',
                }],
                "input_tokens": 1, "output_tokens": 1, "cost_usd": 0.0,
            },
        ],
        [
            {"text_delta": "done", "reasoning_delta": "", "tool_calls_delta": []},
            {
                "final": True, "tool_calls": [],
                "input_tokens": 1, "output_tokens": 1, "cost_usd": 0.0,
            },
        ],
    ]
    call = {"i": 0}

    def _stream(*_a, **_kw):
        idx = call["i"]
        call["i"] += 1
        for frame in steps[idx]:
            yield frame
    return _stream


def _capture(monkeypatch) -> list[tuple[str, dict]]:
    captured: list[tuple[str, dict]] = []
    from alpi.host import events as host_events
    monkeypatch.setattr(
        host_events, "emit",
        lambda kind, data=None: captured.append((kind, data or {})),
    )
    return captured


def test_trivial_fast_user_turn_does_not_emit(
    bootstrapped_home: Path, monkeypatch,
) -> None:
    """Heuristic floor: no tool calls AND <5s elapsed → not worth notifying."""
    from alpi import engine as engine_mod
    monkeypatch.setattr(engine_mod.llm, "stream", _trivial_stream)
    captured = _capture(monkeypatch)

    cfg = config.load(bootstrapped_home)
    engine = Engine(home=bootstrapped_home, cfg=cfg)
    engine.run_turn("hola", lambda _ev: None)

    assert not any(k == "chat.turn_done" for k, _ in captured)


def test_turn_with_tool_call_emits_for_user_source(
    bootstrapped_home: Path, monkeypatch,
) -> None:
    """Any tool call clears the bar — mobile gets a notif on completion."""
    target = bootstrapped_home / "n.txt"
    from alpi import engine as engine_mod
    monkeypatch.setattr(engine_mod.llm, "stream", _write_file_then_done_stream(target))
    captured = _capture(monkeypatch)

    cfg = config.load(bootstrapped_home)
    engine = Engine(home=bootstrapped_home, cfg=cfg)
    engine.run_turn("write a note", lambda _ev: None)

    dones = [d for k, d in captured if k == "chat.turn_done"]
    assert len(dones) == 1
    assert dones[0]["source"] == "user"
    assert dones[0]["tool_count"] >= 1
    assert dones[0]["session_id"] == engine.session.id
    assert dones[0]["profile"] == "default"
    assert "done" in dones[0]["summary"]


def test_peer_source_never_emits_even_with_tool_calls(
    bootstrapped_home: Path, monkeypatch,
) -> None:
    """A turn driven by an incoming ALP link must not trigger a notification
    on the local user — peer-driven flows have their own delivery channel."""
    target = bootstrapped_home / "p.txt"
    from alpi import engine as engine_mod
    monkeypatch.setattr(engine_mod.llm, "stream", _write_file_then_done_stream(target))
    captured = _capture(monkeypatch)

    cfg = config.load(bootstrapped_home)
    engine = Engine(home=bootstrapped_home, cfg=cfg)
    engine.run_turn("do stuff", lambda _ev: None, source="peer")

    assert not any(k == "chat.turn_done" for k, _ in captured)


def test_long_user_turn_emits_even_without_tools(
    bootstrapped_home: Path, monkeypatch,
) -> None:
    """The 5s elapsed bar fires even for tool-less turns. Time-machine
    ``time.time`` so the test runs instantly: each call advances the clock
    by 10s so any pair of (start, end) samples exceeds the 5s threshold."""
    from alpi import engine as engine_mod
    monkeypatch.setattr(engine_mod.llm, "stream", _trivial_stream)
    captured = _capture(monkeypatch)

    state = {"t": 1000.0}
    def _advancing_time() -> float:
        state["t"] += 10.0
        return state["t"]
    monkeypatch.setattr(engine_mod.time, "time", _advancing_time)

    cfg = config.load(bootstrapped_home)
    engine = Engine(home=bootstrapped_home, cfg=cfg)
    engine.run_turn("explain", lambda _ev: None)

    dones = [d for k, d in captured if k == "chat.turn_done"]
    assert len(dones) == 1
    assert dones[0]["duration_s"] >= 5.0
    assert dones[0]["tool_count"] == 0
