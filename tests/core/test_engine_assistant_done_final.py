"""Pin the contract: only the terminal `assistant_done` of a turn carries `final=True`; preamble emissions before tool calls do not."""

from __future__ import annotations

from pathlib import Path

import pytest

from alpi.config import Config, ToolsConfig
from alpi.engine import Engine


@pytest.fixture
def patched_engine(monkeypatch, tmp_path: Path):
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
    calls = {"i": 0}

    def fake_stream(messages, tools, **kwargs):
        idx = calls["i"]
        if idx >= len(scripted_chunks):
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


def test_only_terminal_assistant_done_is_marked_final(
    patched_engine: Engine, monkeypatch,
) -> None:
    """Preamble (text + tool_calls in the same step) → final=False; only the closing text-only step is final."""
    chunks = [
        _final_chunk("Let me check things first.", tool_calls=[{
            "id": "tc1",
            "name": "todo",
            "arguments": '{"action": "list"}',
        }]),
        _final_chunk("¡Buenos días!"),
    ]
    _stub_stream(monkeypatch, chunks)

    events = []
    patched_engine.run_turn("morning", emit=lambda e: events.append(e))

    dones = [e for e in events if e.kind == "assistant_done"]
    assert [e.text for e in dones] == ["Let me check things first.", "¡Buenos días!"]
    assert [e.final for e in dones] == [False, True]


def test_single_step_reply_is_final(patched_engine: Engine, monkeypatch) -> None:
    """A turn with no tool calls emits a single final assistant_done."""
    _stub_stream(monkeypatch, [_final_chunk("hola")])

    events = []
    patched_engine.run_turn("hi", emit=lambda e: events.append(e))

    dones = [e for e in events if e.kind == "assistant_done"]
    assert len(dones) == 1
    assert dones[0].final is True
    assert dones[0].text == "hola"


def test_max_steps_cap_triggers_wrap_up_final_reply(
    patched_engine: Engine, monkeypatch,
) -> None:
    usage_calls: list = []
    monkeypatch.setattr(
        "alpi.tools._state.bump_turn_usage",
        lambda i, o, c: usage_calls.append((i, o, c)),
    )

    def fake_stream(messages, tools, **kwargs):
        if not tools:  # the tools-OFF wrap-up call, distinct token counts from the loop
            yield {"text_delta": "Best-effort answer with what I gathered."}
            yield {"final": True, "text": "", "input_tokens": 777,
                   "output_tokens": 333, "cost_usd": 0.5, "tool_calls": []}
            return
        # every in-loop step returns a tool call → the turn never completes naturally
        yield _final_chunk("", tool_calls=[{
            "id": "tc", "name": "todo", "arguments": '{"action": "list"}',
        }])

    monkeypatch.setattr("alpi.llm.stream", fake_stream)

    events = []
    patched_engine.run_turn("keep using tools", emit=lambda e: events.append(e))

    dones = [e for e in events if e.kind == "assistant_done"]
    assert dones, "wrap-up should emit a final assistant_done"
    assert dones[-1].final is True
    assert "Best-effort answer" in dones[-1].text
    assert not any(e.kind == "error" for e in events)
    assert (777, 333, 0.5) in usage_calls
    assert patched_engine.session.last_ctx_tokens == 777
    usage_events = [e for e in events if e.kind == "usage"]
    assert usage_events and usage_events[-1].tokens_in == 777


def test_interrupt_during_wrap_up_finalizes_as_interrupt(
    patched_engine: Engine, monkeypatch,
) -> None:
    def fake_stream(messages, tools, **kwargs):
        if not tools:  # wrap-up call: partial text streams, then the user interrupts
            yield {"text_delta": "partial answer that must not be finalized"}
            patched_engine.interrupt_requested = True
            yield _final_chunk("")
            return
        yield _final_chunk("", tool_calls=[{
            "id": "tc", "name": "todo", "arguments": '{"action": "list"}',
        }])

    monkeypatch.setattr("alpi.llm.stream", fake_stream)

    events = []
    patched_engine.run_turn("keep using tools", emit=lambda e: events.append(e))

    assert any(e.kind == "interrupted" for e in events)
    assert not [e for e in events if e.kind == "assistant_done" and e.final]


def test_max_steps_wrap_up_overrides_open_todo_guard(
    patched_engine: Engine, monkeypatch,
) -> None:
    patched_engine.session.todos.append({"content": "left open", "status": "pending"})

    def fake_stream(messages, tools, **kwargs):
        if not tools:
            yield {"text_delta": "Best-effort answer despite the open todo."}
            yield _final_chunk("")
            return
        yield _final_chunk("", tool_calls=[{
            "id": "tc", "name": "todo", "arguments": '{"action": "list"}',
        }])

    monkeypatch.setattr("alpi.llm.stream", fake_stream)

    events = []
    patched_engine.run_turn("go", emit=lambda e: events.append(e))

    dones = [e for e in events if e.kind == "assistant_done" and e.final]
    assert dones, "cap wrap-up must finalize even with an open todo"
    assert "Best-effort" in dones[-1].text
