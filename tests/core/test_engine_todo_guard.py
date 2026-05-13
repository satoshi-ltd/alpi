"""Engine guard: model can't finalize a turn while todos are open.

A model that opens a todo list via the `todo` tool and then tries to close
the turn with a final text-only message (no tool_calls) breaks the contract
that the user implicitly accepted when they asked for multi-step work.
Pre-fix: the engine returned immediately on `not tool_calls`. Post-fix:
it inspects `session.todos` for `pending`/`in_progress` entries and, when
found, injects a synthetic `role: user` continuation that costs one of the
remaining steps from ``max_steps_per_turn``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alpi.config import Config, ToolsConfig
from alpi.engine import Engine
from alpi.session import Session
from alpi.tools import todo as todo_mod


@pytest.fixture
def patched_engine(monkeypatch, tmp_path: Path):
    """Engine stubbed enough to drive `run_turn` without hitting the network."""
    home = tmp_path / "h"
    home.mkdir()
    monkeypatch.setattr("alpi.engine._maybe_load_mcps", lambda _cfg: [])
    monkeypatch.setattr(Engine, "_build_system_prompt", lambda self: "you are alpi")
    monkeypatch.setattr("alpi.ctx_window.resolve", lambda _h, _c, _m: 400_000)
    monkeypatch.setattr("alpi.ledger.check", lambda *a, **kw: None)
    monkeypatch.setattr("alpi.ledger.record", lambda *a, **kw: None)

    cfg = Config(
        home=home,
        model="gpt-5.4-mini",
        tools=ToolsConfig(max_steps_per_turn=6),
        raw={},
    )
    return Engine(home=home, cfg=cfg)


def _final_chunk(text: str, tool_calls=None):
    return {
        "final": True,
        "text": text,
        "input_tokens": 10,
        "output_tokens": 5,
        "cost_usd": 0.0,
        "tool_calls": tool_calls or [],
    }


def _stub_stream(monkeypatch, scripted_chunks: list[dict]):
    """Replay a fixed sequence of LLM steps, one per engine iteration."""
    calls = {"i": 0, "captured_messages": []}

    def fake_stream(messages, tools, **kwargs):
        idx = calls["i"]
        calls["captured_messages"].append([dict(m) for m in messages])
        if idx >= len(scripted_chunks):
            yield {"text_delta": "(no more scripted chunks)"}
            yield _final_chunk("")
            return
        calls["i"] += 1
        chunk = dict(scripted_chunks[idx])
        text = chunk.pop("text", "")
        if text:
            yield {"text_delta": text}
        yield chunk

    monkeypatch.setattr("alpi.llm.stream", fake_stream)
    return calls


def test_session_todos_are_per_instance_not_shared(tmp_path: Path) -> None:
    """Module-level `_TODOS` is gone — two Session instances must own
    independent lists even when constructed in the same process."""
    s1 = Session(home=tmp_path / "a", model="x")
    s2 = Session(home=tmp_path / "b", model="x")
    s1.todos.append({"content": "only in s1", "status": "pending"})
    assert s2.todos == []
    assert s1.todos != s2.todos


def test_guard_fires_when_model_returns_with_open_todos(
    patched_engine: Engine, monkeypatch,
) -> None:
    """Step 1: model returns text-only. Step 2: forced to continue and uses
    `todo(complete)`. Step 3: clean exit.

    Note on streaming: rejected `assistant_delta` frames from step 1 may
    have been emitted before the guard fires (deltas stream as bytes
    arrive, the guard runs after the final marker). The contract this
    test pins is on `assistant_done` — that frame must NOT be emitted
    for the premature text, only for legitimate finals.
    """
    engine = patched_engine
    engine.session.todos.append({"content": "ship the thing", "status": "in_progress"})

    chunks = [
        _final_chunk("I'm done early"),  # tries to close while todo in_progress
        _final_chunk("calling complete", tool_calls=[{
            "id": "tc1",
            "name": "todo",
            "arguments": '{"action": "complete", "index": 0}',
        }]),
        _final_chunk("ok now actually done"),  # tool_calls empty, no open todos
    ]
    calls = _stub_stream(monkeypatch, chunks)

    events = []
    engine.run_turn("do multi-step work", emit=lambda e: events.append(e))

    # Engine cycled three LLM calls instead of bailing on the first text-only response.
    assert calls["i"] == 3, (
        f"engine should have re-prompted instead of finalizing; saw {calls['i']} LLM calls"
    )
    # The synthetic continuation lives in the captured messages of the SECOND llm call.
    second_msgs = calls["captured_messages"][1]
    nag = [m for m in second_msgs if m["role"] == "user" and m["content"].startswith("[engine]")]
    assert nag, "no synthetic continuation found in second-call messages"
    assert "in_progress" in nag[-1]["content"]
    assert "#0" in nag[-1]["content"]
    assistant_done_texts = [e.text for e in events if e.kind == "assistant_done"]
    assert "I'm done early" not in assistant_done_texts
    assert assistant_done_texts == ["calling complete", "ok now actually done"]
    # Final exit emitted `done`.
    kinds = [e.kind for e in events]
    assert "done" in kinds


def test_guard_does_not_fire_when_all_todos_are_completed(
    patched_engine: Engine, monkeypatch,
) -> None:
    """Closed contract: every todo `completed` → text-only reply is fine."""
    engine = patched_engine
    engine.session.todos.append({"content": "done already", "status": "completed"})

    calls = _stub_stream(monkeypatch, [_final_chunk("all set")])

    events = []
    engine.run_turn("wrap up", emit=lambda e: events.append(e))

    assert calls["i"] == 1, "no extra LLM iteration should fire when todos are completed"
    assert any(e.kind == "done" for e in events)


def test_guard_does_not_fire_when_no_todos_were_ever_opened(
    patched_engine: Engine, monkeypatch,
) -> None:
    """No `todo` use → no contract → no guard. Same behavior as pre-fix."""
    engine = patched_engine
    calls = _stub_stream(monkeypatch, [_final_chunk("nothing to track")])

    events = []
    engine.run_turn("quick question", emit=lambda e: events.append(e))

    assert calls["i"] == 1
    assert any(e.kind == "done" for e in events)


def test_persistent_refusal_to_continue_burns_max_steps(
    patched_engine: Engine, monkeypatch,
) -> None:
    """If the model keeps emitting empty replies, the guard re-prompts until
    `max_steps_per_turn` is exhausted — no infinite loop."""
    engine = patched_engine
    engine.session.todos.append({"content": "won't do it", "status": "pending"})

    # Model stubbornly returns empty tool_calls every time.
    refusal = _final_chunk("nope")
    calls = _stub_stream(monkeypatch, [refusal] * 20)  # more than max_steps_per_turn

    events = []
    engine.run_turn("force it", emit=lambda e: events.append(e))

    # max_steps_per_turn=6 → exactly 6 iterations, then "Reached max tool steps; stopping."
    assert calls["i"] == 6
    error_events = [e for e in events if e.kind == "error"]
    assert any("max tool steps" in e.text for e in error_events)


def test_todo_tool_writes_into_active_session_store(
    patched_engine: Engine, monkeypatch,
) -> None:
    """Sanity check the wiring: a `todo(add)` call inside a turn lands on
    `self.session.todos`, not a process-global list."""
    engine = patched_engine

    chunks = [
        _final_chunk("setting up", tool_calls=[{
            "id": "tc-add",
            "name": "todo",
            "arguments": '{"action": "add", "content": "task A"}',
        }]),
        _final_chunk("cleaning up", tool_calls=[{
            "id": "tc-clear",
            "name": "todo",
            "arguments": '{"action": "clear"}',
        }]),
        _final_chunk("done"),
    ]
    _stub_stream(monkeypatch, chunks)

    engine.run_turn("track work", emit=lambda _e: None)

    # After clear the list ends empty, but during the run it held the added row.
    # We verify the engine's session is the same instance touched by the tool by inspecting the message thread for the todo tool result.
    tool_outputs = [
        m["content"] for m in engine.session.messages if m.get("role") == "tool"
    ]
    assert any("task A" in out for out in tool_outputs), tool_outputs
    assert engine.session.todos == []


def test_concurrent_sessions_do_not_share_todo_store(
    patched_engine: Engine, monkeypatch, tmp_path: Path,
) -> None:
    """Crucial regression: pre-fix the `_TODOS` global meant a `todo(add)`
    in session A would surface inside session B's `todo(list)`."""
    engine_a = patched_engine

    # Run engine_a to insert one todo, but don't reset the context yet.
    chunks_a = [
        _final_chunk("adding A", tool_calls=[{
            "id": "a1",
            "name": "todo",
            "arguments": '{"action": "add", "content": "from session A"}',
        }]),
        _final_chunk("done"),
    ]
    _stub_stream(monkeypatch, chunks_a)
    engine_a.run_turn("track A", emit=lambda _e: None)

    # Build a second engine sharing the same home but a fresh Session.
    home_b = tmp_path / "b"
    home_b.mkdir()
    monkeypatch.setattr("alpi.engine._maybe_load_mcps", lambda _cfg: [])
    monkeypatch.setattr(Engine, "_build_system_prompt", lambda self: "you are alpi")
    cfg_b = Config(
        home=home_b,
        model="gpt-5.4-mini",
        tools=ToolsConfig(max_steps_per_turn=4),
        raw={},
    )
    engine_b = Engine(home=home_b, cfg=cfg_b)

    chunks_b = [
        _final_chunk("listing", tool_calls=[{
            "id": "b1",
            "name": "todo",
            "arguments": '{"action": "list"}',
        }]),
        _final_chunk("done"),
    ]
    _stub_stream(monkeypatch, chunks_b)
    engine_b.run_turn("look at B", emit=lambda _e: None)

    # Session B must NOT see "from session A".
    b_tool_outputs = [
        m["content"] for m in engine_b.session.messages if m.get("role") == "tool"
    ]
    for out in b_tool_outputs:
        assert "from session A" not in out, (
            f"session B saw session A's todo — cross-session leak. output: {out!r}"
        )


def test_todo_module_exposes_bind_reset_and_open(tmp_path: Path) -> None:
    """Engine relies on `bind_store` / `reset_store` / `open_todos` — make
    sure they stay public and behave."""
    assert callable(getattr(todo_mod, "bind_store", None))
    assert callable(getattr(todo_mod, "reset_store", None))
    assert callable(getattr(todo_mod, "open_todos", None))

    items = [
        {"content": "a", "status": "completed"},
        {"content": "b", "status": "pending"},
        {"content": "c", "status": "in_progress"},
    ]
    o = todo_mod.open_todos(items)
    assert {t["content"] for t in o} == {"b", "c"}
