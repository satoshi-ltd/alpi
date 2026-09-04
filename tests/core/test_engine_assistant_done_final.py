"""Turn-shape contracts: terminal-only `final=True`, wrap/side accounting, and OpenRouter cache affinity on every call path."""

from __future__ import annotations

from pathlib import Path

import pytest

from alpi.config import Config, ToolsConfig
from alpi.engine import Engine
from alpi.session import HOST_CONTEXT_CAP
from alpi.tools.base import ToolResult


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

    from alpi import runs
    journal = runs.read(patched_engine.home, patched_engine.last_run_id)["events"]
    assert journal[0]["kind"] == "run.started"
    assert journal[0]["data"]["input"] == "hi"
    assert journal[-1]["data"]["outcome"] == "completed"


def test_engine_uses_supervisor_run_id_from_environment(
    patched_engine: Engine, monkeypatch,
) -> None:
    monkeypatch.setenv("ALPI_RUN_ID", "supervised-run")
    _stub_stream(monkeypatch, [_final_chunk("done")])

    patched_engine.run_turn("hi", emit=lambda _event: None)

    assert patched_engine.last_run_id == "supervised-run"
    from alpi import runs
    assert runs.summary(patched_engine.home, "supervised-run")["status"] == "completed"


def test_targeted_interrupt_before_engine_entry_is_preserved(
    patched_engine: Engine, monkeypatch,
) -> None:
    calls = _stub_stream(monkeypatch, [_final_chunk("must not run")])
    run_id = "cancel-before-entry"
    patched_engine.active_run_id = run_id
    patched_engine.request_interrupt("test-pre-start")
    events = []

    patched_engine.run_turn("stop before the model", events.append, run_id=run_id)

    assert calls["i"] == 0
    assert any(event.kind == "interrupted" for event in events)
    from alpi import runs
    assert runs.summary(patched_engine.home, run_id)["status"] == "interrupted"


def test_engine_parallelizes_safe_batch_and_preserves_result_order(
    patched_engine: Engine, monkeypatch,
) -> None:
    import threading
    from alpi import tools
    from alpi.tools.base import Tool

    barrier = threading.Barrier(2)

    class SafeBatchTool(Tool):
        name = "test_safe_batch"
        description = "test"
        parallel_safe = True

        def run(self, value: str) -> ToolResult:
            barrier.wait(timeout=2)
            return ToolResult(True, value)

    monkeypatch.setitem(tools._TOOLS, SafeBatchTool.name, SafeBatchTool)
    _stub_stream(monkeypatch, [
        _final_chunk("", tool_calls=[
            {"id": "a", "name": SafeBatchTool.name, "arguments": '{"value":"first"}'},
            {"id": "b", "name": SafeBatchTool.name, "arguments": '{"value":"second"}'},
        ]),
        _final_chunk("done"),
    ])

    patched_engine.run_turn("parallel", emit=lambda _event: None)
    logged = patched_engine.session.turns[-1].tools
    assert [tool.result for tool in logged] == ["first", "second"]


@pytest.mark.parametrize("interrupt_event", ["assistant_done", "tool_start"])
def test_interrupt_before_parallel_dispatch_skips_batch(
    patched_engine: Engine, monkeypatch, interrupt_event: str,
) -> None:
    from alpi import tools
    from alpi.tools.base import Tool

    executed = []

    class SafeBatchTool(Tool):
        name = "test_interrupt_safe_batch"
        description = "test"
        parallel_safe = True

        def run(self, value: str) -> ToolResult:
            executed.append(value)
            return ToolResult(True, value)

    monkeypatch.setitem(tools._TOOLS, SafeBatchTool.name, SafeBatchTool)
    _stub_stream(monkeypatch, [_final_chunk("checking", tool_calls=[
        {"id": "a", "name": SafeBatchTool.name, "arguments": '{"value":"first"}'},
        {"id": "b", "name": SafeBatchTool.name, "arguments": '{"value":"second"}'},
    ])])
    events = []

    def emit(event):
        events.append(event)
        if event.kind == interrupt_event and not event.final:
            patched_engine.request_interrupt("test-after-batch")

    patched_engine.run_turn("parallel", emit=emit)

    assert executed == []
    assert sum(event.kind == "tool_end" for event in events) == 2
    assert patched_engine.session.turns[-1].interrupted is True


def test_tool_end_preserves_structured_transient_result(
    patched_engine: Engine, monkeypatch,
) -> None:
    _stub_stream(monkeypatch, [
        _final_chunk("", tool_calls=[{
            "id": "busy", "name": "todo", "arguments": '{"action":"list"}',
        }]),
        _final_chunk("done"),
    ])
    monkeypatch.setattr(
        "alpi.tools.execute",
        lambda *_args, **_kwargs: ToolResult(
            ok=False, output="", error="target busy", transient=True,
        ),
    )
    events = []

    patched_engine.run_turn("try once", emit=events.append)

    tool_end = next(event for event in events if event.kind == "tool_end")
    assert tool_end.ok is False
    assert tool_end.transient is True


def test_terminal_command_is_not_persisted_in_turn_or_run_journal(
    patched_engine: Engine, monkeypatch,
) -> None:
    from alpi import runs, tools
    from alpi.tools.base import Tool

    secret = "not-shaped-like-a-token"

    class FakeTerminal(Tool):
        name = "terminal"
        description = "test"

        def run(self, **kwargs) -> ToolResult:
            return ToolResult(True, "done")

    monkeypatch.setitem(tools._TOOLS, FakeTerminal.name, FakeTerminal)
    _stub_stream(monkeypatch, [
        _final_chunk("", tool_calls=[{
            "id": "shell", "name": "terminal",
            "arguments": '{"action":"run","command":"not-shaped-like-a-token"}',
        }]),
        _final_chunk("done"),
    ])

    patched_engine.run_turn("execute it", emit=lambda _event: None)

    assert patched_engine.session.turns[-1].tools[0].args == {"action": "run"}
    journal = runs.read(patched_engine.home, patched_engine.last_run_id)["events"]
    assert secret not in str(journal)
    saved = patched_engine.session.save()
    assert saved is not None and secret not in saved.read_text()


def test_max_steps_cap_triggers_wrap_up_final_reply(
    patched_engine: Engine, monkeypatch,
) -> None:
    usage_calls: list = []
    monkeypatch.setattr(
        "alpi.tools._state.bump_turn_usage",
        lambda i, o, c, cached=0: usage_calls.append((i, o, c)),
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
    assert patched_engine.session.turns[-1].interrupted is True


def test_silent_tool_only_completion_is_not_persisted_as_interrupted(
    patched_engine: Engine, monkeypatch,
) -> None:
    _stub_stream(monkeypatch, [_final_chunk("")])

    events = []
    patched_engine.run_turn("do something silent", emit=lambda e: events.append(e))

    assert not any(e.kind == "interrupted" for e in events)
    assert patched_engine.session.turns[-1].assistant == ""
    assert patched_engine.session.turns[-1].interrupted is False


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


def test_turn_deadline_from_env(monkeypatch) -> None:
    from alpi.engine import _turn_deadline_from_env

    monkeypatch.delenv("ALPI_TURN_BUDGET_S", raising=False)
    assert _turn_deadline_from_env(100.0) is None
    monkeypatch.setenv("ALPI_TURN_BUDGET_S", "30")
    assert _turn_deadline_from_env(100.0) == 130.0
    monkeypatch.setenv("ALPI_TURN_BUDGET_S", "0")
    assert _turn_deadline_from_env(100.0) is None
    monkeypatch.setenv("ALPI_TURN_BUDGET_S", "garbage")
    assert _turn_deadline_from_env(100.0) is None


def test_wall_clock_jump_does_not_expire_turn(
    patched_engine: Engine, monkeypatch,
) -> None:
    monkeypatch.setattr(
        "alpi.engine._turn_deadline_from_env", lambda started: 80.0,
    )
    monkeypatch.setattr("alpi.engine.time.monotonic", lambda: 50.0)

    _stub_stream(monkeypatch, [_final_chunk("finished")])
    events = []
    patched_engine.run_turn("go", emit=lambda event: events.append(event))

    assert any(
        event.kind == "assistant_done" and event.final and event.text == "finished"
        for event in events
    )
    assert not any(event.kind == "error" for event in events)


def test_monotonic_deadline_triggers_wrap_up(
    patched_engine: Engine, monkeypatch,
) -> None:
    monkeypatch.setenv("ALPI_TURN_BUDGET_S", "0.0001")
    calls = {"loop": 0, "wrap": 0}

    def fake_stream(messages, tools, **kwargs):
        if not tools:  # tools-OFF wrap-up call after the soft deadline trips
            calls["wrap"] += 1
            yield {"text_delta": "Time-boxed best-effort answer."}
            yield {"final": True, "text": "", "input_tokens": 11,
                   "output_tokens": 7, "cost_usd": 0.1, "tool_calls": []}
            return
        calls["loop"] += 1
        yield _final_chunk("", tool_calls=[{
            "id": "tc", "name": "todo", "arguments": '{"action": "list"}',
        }])

    monkeypatch.setattr("alpi.llm.stream", fake_stream)

    events = []
    patched_engine.run_turn("do work", emit=lambda e: events.append(e))

    dones = [e for e in events if e.kind == "assistant_done" and e.final]
    assert dones and "Time-boxed best-effort" in dones[-1].text
    assert calls["wrap"] == 1
    assert calls["loop"] < 6, "deadline must break the loop before exhausting max_steps"
    assert not any(e.kind == "error" for e in events)


def test_deadline_reached_during_stream_skips_returned_tool_calls(
    patched_engine: Engine, monkeypatch,
) -> None:
    import time

    ledger_calls: list[dict] = []
    monkeypatch.setattr(
        "alpi.ledger.record", lambda *args, **kwargs: ledger_calls.append(kwargs),
    )
    monkeypatch.setattr(
        "alpi.engine._turn_deadline_from_env", lambda started: time.monotonic() + 0.01,
    )
    calls = {"loop": 0, "wrap": 0}

    def fake_stream(messages, tools, **kwargs):
        if not tools:
            calls["wrap"] += 1
            yield {"text_delta": "Time-boxed answer."}
            yield _final_chunk("")
            return
        calls["loop"] += 1
        time.sleep(0.03)
        final = _final_chunk("", tool_calls=[{
            "id": "tc", "name": "todo", "arguments": '{"action": "list"}',
        }])
        final["input_tokens"] = 123
        final["output_tokens"] = 7
        yield final

    monkeypatch.setattr("alpi.llm.stream", fake_stream)

    events = []
    patched_engine.run_turn("do work", emit=events.append)

    assert calls == {"loop": 1, "wrap": 1}
    assert not any(event.kind == "tool_start" for event in events)
    assert any(call.get("tokens_in") == 123 for call in ledger_calls)
    assert any(event.kind == "usage" and event.tokens_in == 123 for event in events)
    assert any(
        event.kind == "assistant_done" and event.final and "Time-boxed" in event.text
        for event in events
    )


def test_deadline_stops_a_stream_that_keeps_emitting_reasoning(
    patched_engine: Engine, monkeypatch,
) -> None:
    now = [100.0]
    calls = {"loop": 0, "wrap": 0, "deltas": 0}
    monkeypatch.setattr("alpi.engine.time.monotonic", lambda: now[0])
    monkeypatch.setattr(
        "alpi.engine._turn_deadline_from_env", lambda started: 105.0,
    )

    def fake_stream(messages, tools, **kwargs):
        if not tools:
            calls["wrap"] += 1
            yield {"text_delta": "Time-boxed answer."}
            yield _final_chunk("")
            return
        calls["loop"] += 1
        calls["deltas"] += 1
        yield {"reasoning_delta": "first"}
        now[0] = 106.0
        calls["deltas"] += 1
        yield {"reasoning_delta": "late"}
        calls["deltas"] += 1
        yield _final_chunk("should not be consumed")

    monkeypatch.setattr("alpi.llm.stream", fake_stream)

    events = []
    patched_engine.run_turn("do work", emit=events.append)

    assert calls == {"loop": 1, "wrap": 1, "deltas": 2}
    assert not any(
        event.kind == "assistant_done" and "should not be consumed" in event.text
        for event in events
    )
    assert any(
        event.kind == "assistant_done" and event.final and "Time-boxed" in event.text
        for event in events
    )


def test_generous_budget_does_not_trip(
    patched_engine: Engine, monkeypatch,
) -> None:
    monkeypatch.setenv("ALPI_TURN_BUDGET_S", "9999")
    _stub_stream(monkeypatch, [_final_chunk("hola")])

    events = []
    patched_engine.run_turn("hi", emit=lambda e: events.append(e))

    dones = [e for e in events if e.kind == "assistant_done"]
    assert len(dones) == 1
    assert dones[0].final is True
    assert dones[0].text == "hola"


def test_request_interrupt_logs_reason(patched_engine: Engine, caplog) -> None:
    import logging

    with caplog.at_level(logging.WARNING, logger="alpi.engine"):
        patched_engine.request_interrupt("preempt-same-session")
    assert patched_engine.interrupt_requested is True
    assert "preempt-same-session" in caplog.text


def test_request_interrupt_default_reason(patched_engine: Engine) -> None:
    patched_engine.request_interrupt()
    assert patched_engine.interrupt_requested is True


def test_empty_reply_is_retried_then_answered(
    patched_engine: Engine, monkeypatch,
) -> None:
    _stub_stream(monkeypatch, [_final_chunk(""), _final_chunk("Las funciones del AM son X, Y, Z.")])

    events = []
    patched_engine.run_turn("funciones del account manager", emit=lambda e: events.append(e))

    dones = [e for e in events if e.kind == "assistant_done" and e.final]
    assert len(dones) == 1
    assert dones[0].text == "Las funciones del AM son X, Y, Z."
    assert any(
        m.get("role") == "user" and "empty reply" in str(m.get("content", ""))
        for m in patched_engine.session.messages
    ), "engine should inject a nudge after an empty close"
    assert not any(e.kind == "error" for e in events)


def test_empty_reply_retry_is_bounded(patched_engine: Engine, monkeypatch) -> None:
    n = {"c": 0}

    def fake_stream(messages, tools, **kwargs):
        n["c"] += 1
        yield _final_chunk("")

    monkeypatch.setattr("alpi.llm.stream", fake_stream)

    events = []
    patched_engine.run_turn("x", emit=lambda e: events.append(e))

    assert any(e.kind == "done" for e in events)
    assert n["c"] == 2, "one initial call + exactly one nudge retry"
    assert not any(e.kind == "error" for e in events)


def test_wrap_up_forwards_cache_fields_to_ledger_and_event(
    patched_engine: Engine, monkeypatch,
) -> None:
    ledger_calls: list[dict] = []
    monkeypatch.setattr(
        "alpi.ledger.record", lambda *a, **kw: ledger_calls.append(kw),
    )
    bump_calls: list = []
    monkeypatch.setattr(
        "alpi.tools._state.bump_turn_usage",
        lambda i, o, c, cached=None: bump_calls.append((i, o, c, cached)),
    )

    def fake_stream(messages, tools, **kwargs):
        if not tools:
            yield {"text_delta": "Best-effort answer."}
            yield {"final": True, "text": "", "input_tokens": 777,
                   "output_tokens": 333, "cost_usd": 0.5, "tool_calls": [],
                   "cached_tokens": 555, "cache_discount": 0.01,
                   "cost_source": "provider"}
            return
        yield _final_chunk("", tool_calls=[{
            "id": "tc", "name": "todo", "arguments": '{"action": "list"}',
        }])

    monkeypatch.setattr("alpi.llm.stream", fake_stream)

    events = []
    patched_engine.run_turn("keep using tools", emit=lambda e: events.append(e))

    wrap_row = ledger_calls[-1]
    assert wrap_row["tokens_cached"] == 555
    assert wrap_row["cache_discount_usd"] == 0.01
    assert wrap_row["cost_source"] == "provider"
    assert (777, 333, 0.5, 555) in bump_calls
    assert patched_engine.session.cached_input_tokens == 555
    assert patched_engine.session.cache_measured_input_tokens == 777
    usage_events = [e for e in events if e.kind == "usage"]
    assert usage_events[-1].cached_in == 555


def test_empty_wrap_reply_still_records_its_usage(
    patched_engine: Engine, monkeypatch,
) -> None:
    """An empty wrap completion consumed a full context of input — the accounting must not hide behind the content check."""
    usage_calls: list = []
    monkeypatch.setattr(
        "alpi.tools._state.bump_turn_usage",
        lambda i, o, c, cached=None: usage_calls.append((i, o, c)),
    )

    def fake_stream(messages, tools, **kwargs):
        if not tools:
            yield {"final": True, "text": "", "input_tokens": 777,
                   "output_tokens": 0, "cost_usd": 0.5, "tool_calls": []}
            return
        yield _final_chunk("", tool_calls=[{
            "id": "tc", "name": "todo", "arguments": '{"action": "list"}',
        }])

    monkeypatch.setattr("alpi.llm.stream", fake_stream)

    events = []
    patched_engine.run_turn("keep using tools", emit=lambda e: events.append(e))

    assert (777, 0, 0.5) in usage_calls
    assert patched_engine.session.last_ctx_tokens == 777
    usage_events = [e for e in events if e.kind == "usage"]
    assert any(e.tokens_in == 777 for e in usage_events)


def test_tool_side_usage_reaches_session_ledger_and_event_via_sink(
    patched_engine: Engine, monkeypatch,
) -> None:
    ledger_calls: list[dict] = []
    monkeypatch.setattr(
        "alpi.ledger.record", lambda *a, **kw: ledger_calls.append(kw),
    )

    from alpi.tools import _state as state_mod
    from alpi.tools.base import ToolResult

    def fake_execute(name, args, deny=None):
        state_mod.record_usage(100, 10, 0.02, 60, 0.004, "provider")
        return ToolResult(ok=True, output="done")

    monkeypatch.setattr("alpi.tools.execute", fake_execute)

    chunks = [
        _final_chunk("checking", tool_calls=[{
            "id": "tc1", "name": "todo", "arguments": '{"action": "list"}',
        }]),
        _final_chunk("done"),
    ]
    _stub_stream(monkeypatch, chunks)

    events = []
    patched_engine.run_turn("go", emit=lambda e: events.append(e))

    assert patched_engine.session.cached_input_tokens == 60
    assert patched_engine.session.cache_measured_input_tokens == 100
    sink_rows = [k for k in ledger_calls if k.get("tokens_cached") == 60]
    assert sink_rows and sink_rows[0]["cache_discount_usd"] == 0.004
    assert sink_rows[0]["cost_source"] == "provider"
    usage_events = [e for e in events if e.kind == "usage"]
    assert any(e.cached_in == 60 for e in usage_events)


def test_openrouter_calls_carry_a_stable_affinity_session_id(
    monkeypatch, tmp_path: Path,
) -> None:
    home = tmp_path / "h"
    home.mkdir()
    monkeypatch.setattr("alpi.engine._maybe_load_mcps", lambda _cfg: [])
    monkeypatch.setattr(Engine, "_build_system_prompt", lambda self: "sys")
    monkeypatch.setattr("alpi.ctx_window.resolve", lambda *a: 400_000)
    monkeypatch.setattr("alpi.ledger.check", lambda *a, **kw: None)
    monkeypatch.setattr("alpi.ledger.record", lambda *a, **kw: None)
    cfg = Config(
        home=home, model="openrouter/deepseek/deepseek-v4-flash-0731",
        tools=ToolsConfig(max_steps_per_turn=6), raw={},
    )
    engine = Engine(home=home, cfg=cfg)

    seen: list = []

    def fake_stream(messages, tools, **kwargs):
        seen.append((kwargs.get("extra_body") or {}).get("session_id"))
        if len(seen) == 1:
            yield _final_chunk("", tool_calls=[
                {"id": "t1", "name": "todo", "arguments": '{"action": "list"}'},
            ])
        else:
            yield {"text_delta": "ok"}
            yield _final_chunk("")

    monkeypatch.setattr("alpi.llm.stream", fake_stream)
    engine.run_turn("hola", emit=lambda e: None)
    engine.run_turn("otra", emit=lambda e: None)

    assert len(seen) >= 3
    assert all(s == seen[0] for s in seen), "one logical conversation, one sticky key"
    assert seen[0] and seen[0].startswith("alpi-")


def test_non_openrouter_models_get_no_session_id(
    patched_engine: Engine, monkeypatch,
) -> None:
    seen: list = []

    def fake_stream(messages, tools, **kwargs):
        seen.append(kwargs.get("extra_body"))
        yield _final_chunk("ok")

    monkeypatch.setattr("alpi.llm.stream", fake_stream)
    patched_engine.run_turn("hola", emit=lambda e: None)
    assert seen and all(
        not (b or {}).get("session_id") for b in seen
    ), "session_id is an OpenRouter body field, never sent elsewhere"


def test_post_turn_memory_maintenance_fires_once(
    patched_engine: Engine, monkeypatch,
) -> None:
    calls: list = []
    monkeypatch.setattr("alpi.memory.run_maintenance", lambda home: calls.append(home))
    _stub_stream(monkeypatch, [_final_chunk("hola")])
    patched_engine.run_turn("hi", emit=lambda e: None)
    assert calls == [patched_engine.home], (
        "pruning left the prompt builder (CL.1) — this post-turn call is its only trigger"
    )


def test_affinity_scopes_workgroup_peer_and_session(
    patched_engine: Engine, monkeypatch,
) -> None:
    from alpi import prefix_diag
    from alpi.home import profile_name
    from alpi.host.connection_context import ConnectionContext

    profile = profile_name(patched_engine.home)
    monkeypatch.delenv("ALPI_WORKGROUP_DISPATCH", raising=False)
    monkeypatch.delenv("ALPI_SCHEDULE_ID", raising=False)

    assert patched_engine._cache_affinity() == prefix_diag.affinity_id(
        profile, session_id=patched_engine.session.id,
    )

    patched_engine.connection_context = ConnectionContext(
        connection_id="peer:quill", source="peer",
    )
    assert patched_engine._cache_affinity() == prefix_diag.affinity_id(
        profile, peer_id="quill", session_id=patched_engine.session.id,
    )

    monkeypatch.setenv("ALPI_WORKGROUP_DISPATCH", "wg_1")
    assert patched_engine._cache_affinity() == prefix_diag.affinity_id(
        profile, workgroup_id="wg_1", peer_id="quill",
        session_id=patched_engine.session.id,
    ), "workgroup scope outranks peer"

    monkeypatch.delenv("ALPI_WORKGROUP_DISPATCH", raising=False)
    monkeypatch.setenv("ALPI_SCHEDULE_ID", "job-9")
    assert patched_engine._cache_affinity() == prefix_diag.affinity_id(
        profile, schedule_id="job-9", session_id=patched_engine.session.id,
    ) or patched_engine._cache_affinity() == prefix_diag.affinity_id(
        profile, peer_id="quill", schedule_id="job-9",
        session_id=patched_engine.session.id,
    )


def test_workgroup_dispatch_requests_only_its_context(
    patched_engine: Engine, monkeypatch,
) -> None:
    requested: list[str | None] = []

    def fake_build(_home, wg_id=None, max_chars=None):
        requested.append(wg_id)
        assert max_chars and max_chars < HOST_CONTEXT_CAP
        return "target context"

    monkeypatch.setenv("ALPI_WORKGROUP_DISPATCH", "wg_target")
    monkeypatch.setattr("alpi.alp.agent_context.build", fake_build)
    _stub_stream(monkeypatch, [_final_chunk("done")])

    patched_engine.run_turn("work", emit=lambda _event: None)

    assert requested == ["wg_target"]
    assert "target context" in patched_engine.last_host_context


def test_workgroup_dispatch_skips_keyword_skill_hints(
    patched_engine: Engine, monkeypatch,
) -> None:
    calls = []
    monkeypatch.setenv("ALPI_WORKGROUP_DISPATCH", "wg_target")
    monkeypatch.setattr(
        "alpi.alp.agent_context.build",
        lambda _home, wg_id=None, max_chars=None: "target context",
    )
    monkeypatch.setattr(
        "alpi.tools.skill.keyword_match_hint",
        lambda *_args, **_kwargs: calls.append(True) or "wrong hint",
    )
    _stub_stream(monkeypatch, [_final_chunk(""), _final_chunk("")])

    patched_engine.run_turn("research hotel", emit=lambda _event: None)

    assert calls == []
    assert "wrong hint" not in patched_engine.last_host_context


def test_workgroup_dispatch_fails_before_llm_without_target_context(
    patched_engine: Engine, monkeypatch,
) -> None:
    provider_called = [False]

    def fake_stream(*args, **kwargs):
        provider_called[0] = True
        yield _final_chunk("wrong")

    monkeypatch.setenv("ALPI_WORKGROUP_DISPATCH", "wg_missing")
    monkeypatch.setattr(
        "alpi.alp.agent_context.build",
        lambda _home, wg_id=None, max_chars=None: None,
    )
    monkeypatch.setattr("alpi.llm.stream", fake_stream)

    with pytest.raises(RuntimeError, match="workgroup dispatch context unavailable: wg_missing"):
        patched_engine.run_turn("work", emit=lambda _event: None)

    assert provider_called == [False]


def test_workgroup_dispatch_stops_after_substantive_post(
    patched_engine: Engine, monkeypatch,
) -> None:
    calls = _stub_stream(monkeypatch, [_final_chunk("", tool_calls=[{
        "id": "post", "name": "workgroup_post",
        "arguments": '{"wg_id":"wg_target","text":"build green"}',
    }])])
    monkeypatch.setenv("ALPI_WORKGROUP_DISPATCH", "wg_target")
    monkeypatch.setattr(
        "alpi.alp.agent_context.build",
        lambda _home, wg_id=None, max_chars=None: "target context",
    )
    monkeypatch.setattr(
        "alpi.tools.execute",
        lambda _name, _args, deny=None: ToolResult(ok=True, output="posted seq 2"),
    )
    events = []

    patched_engine.run_turn("work", emit=events.append)

    assert calls["i"] == 1
    assert any(event.kind == "done" for event in events)
    assert not any(event.kind == "assistant_done" and event.final for event in events)


def test_workgroup_dispatch_continues_after_working_post(
    patched_engine: Engine, monkeypatch,
) -> None:
    calls = _stub_stream(monkeypatch, [
        _final_chunk("", tool_calls=[{
            "id": "post", "name": "workgroup_post",
            "arguments": (
                '{"wg_id":"wg_target","text":"#working running the build (terminal)"}'
            ),
        }]),
        _final_chunk("finished locally"),
    ])
    monkeypatch.setenv("ALPI_WORKGROUP_DISPATCH", "wg_target")
    monkeypatch.setattr(
        "alpi.alp.agent_context.build",
        lambda _home, wg_id=None, max_chars=None: "target context",
    )
    deliveries = []

    def fake_execute(name, args, deny=None):
        if name == "workgroup_post":
            deliveries.append(dict(args))
        return ToolResult(ok=True, output="posted seq 2")

    monkeypatch.setattr("alpi.tools.execute", fake_execute)
    events = []

    patched_engine.run_turn("work", emit=events.append)

    assert calls["i"] == 2
    assert [row["text"] for row in deliveries] == [
        "#working running the build (terminal)",
        "finished locally",
    ]
    finals = [event.text for event in events if event.kind == "assistant_done" and event.final]
    assert finals == []


def test_workgroup_step_limit_posts_a_working_continuation(
    patched_engine: Engine, monkeypatch,
) -> None:
    patched_engine.cfg.tools.max_steps_per_turn = 2
    monkeypatch.setenv("ALPI_WORKGROUP_DISPATCH", "wg_target")
    monkeypatch.setattr(
        "alpi.alp.agent_context.build",
        lambda _home, wg_id=None, max_chars=None: "target context",
    )
    calls = []

    def fake_stream(messages, tools, **kwargs):
        names = [_schema["function"]["name"] for _schema in tools]
        calls.append({
            "names": names,
            "tool_choice": kwargs.get("tool_choice"),
            "parallel_tool_calls": kwargs.get("parallel_tool_calls"),
        })
        if len(calls) <= 2:
            yield _final_chunk("", tool_calls=[{
                "id": f"todo-{len(calls)}", "name": "todo",
                "arguments": '{"action":"list"}',
            }])
            return
        yield _final_chunk("", tool_calls=[{
            "id": "handoff", "name": "workgroup_post",
            "arguments": (
                '{"wg_id":"wg_target","text":"#working first pass written; validating remaining fields"}'
            ),
        }])

    deliveries = []

    def fake_execute(name, args, **_kwargs):
        if name == "workgroup_post":
            deliveries.append(dict(args))
        return ToolResult(ok=True, output="posted seq 9")

    monkeypatch.setattr("alpi.llm.stream", fake_stream)
    monkeypatch.setattr("alpi.tools.execute", fake_execute)
    events = []

    patched_engine.run_turn("work", emit=events.append)

    assert len(calls) == 3
    assert calls[-1] == {
        "names": ["workgroup_post"],
        "tool_choice": "required",
        "parallel_tool_calls": False,
    }
    assert deliveries == [{
        "wg_id": "wg_target",
        "text": "#working first pass written; validating remaining fields (continuation)",
    }]
    assert [tool.name for tool in patched_engine.session.turns[-1].tools] == [
        "todo", "todo", "workgroup_post",
    ]
    assert any(
        event.kind == "tool_end"
        and event.name == "workgroup_post"
        and event.ok
        for event in events
    )
    assert not any(
        event.kind == "assistant_done" and event.final for event in events
    )


def test_workgroup_deadline_posts_a_working_continuation(
    patched_engine: Engine, monkeypatch,
) -> None:
    now = [100.0]
    monkeypatch.setenv("ALPI_WORKGROUP_DISPATCH", "wg_target")
    monkeypatch.setattr("alpi.engine.time.monotonic", lambda: now[0])
    monkeypatch.setattr(
        "alpi.engine._turn_deadline_from_env", lambda _started: 105.0,
    )
    monkeypatch.setattr(
        "alpi.alp.agent_context.build",
        lambda _home, wg_id=None, max_chars=None: "target context",
    )
    schemas = []
    deadlines = []

    def fake_stream(messages, tools, **kwargs):
        schemas.append([schema["function"]["name"] for schema in tools])
        deadlines.append(kwargs.get("absolute_deadline"))
        if len(schemas) == 1:
            yield {"reasoning_delta": "started"}
            now[0] = 106.0
            raise RuntimeError("provider still blocked at the soft deadline")
        yield _final_chunk("", tool_calls=[{
            "id": "handoff", "name": "workgroup_post",
            "arguments": '{"wg_id":"wg_target","text":"#working draft saved; completing intake"}',
        }])

    executed = []

    def fake_execute(name, args, **_kwargs):
        executed.append((name, dict(args)))
        return ToolResult(ok=True, output="posted seq 10")

    monkeypatch.setattr("alpi.llm.stream", fake_stream)
    monkeypatch.setattr("alpi.tools.execute", fake_execute)
    events = []

    patched_engine.run_turn("work", emit=events.append)

    assert deadlines == [105.0, 151.0]
    assert schemas[-1] == ["workgroup_post"]
    assert executed == [(
        "workgroup_post",
        {"wg_id": "wg_target", "text": "#working draft saved; completing intake (continuation)"},
    )]
    assert not any(
        event.kind == "assistant_done" and event.final for event in events
    )


def test_workgroup_empty_reply_posts_a_working_continuation(
    patched_engine: Engine, monkeypatch,
) -> None:
    monkeypatch.setenv("ALPI_WORKGROUP_DISPATCH", "wg_target")
    monkeypatch.setenv("ALPI_WORKGROUP_PIPELINE", "1")
    monkeypatch.setenv("ALPI_WORKGROUP_MEMBER_TURN", "1")
    monkeypatch.setattr(
        "alpi.alp.agent_context.build",
        lambda _home, wg_id=None, max_chars=None: "target context",
    )
    calls = _stub_stream(monkeypatch, [
        _final_chunk(""),
        _final_chunk(""),
        _final_chunk("", tool_calls=[{
            "id": "handoff", "name": "workgroup_post",
            "arguments": (
                '{"wg_id":"wg_target","text":"#working locale files written; validating bounds"}'
            ),
        }]),
    ])
    deliveries = []

    def fake_execute(name, args, **_kwargs):
        if name == "workgroup_post":
            deliveries.append(dict(args))
        return ToolResult(ok=True, output="posted seq 10")

    monkeypatch.setattr("alpi.tools.execute", fake_execute)
    events = []

    patched_engine.run_turn("work", emit=events.append)

    assert calls["i"] == 3
    nudges = [
        m["content"] for m in patched_engine.session.messages
        if m.get("role") == "user" and str(m.get("content", "")).startswith("[engine] You ended this workgroup turn")
    ]
    assert len(nudges) == 1 and "workgroup_post" in nudges[0] and "plain text" not in nudges[0]
    assert deliveries == [{
        "wg_id": "wg_target",
        "text": "#working locale files written; validating bounds (continuation)",
    }]
    assert any(event.kind == "done" for event in events)
    assert not any(event.kind == "error" for event in events)


def test_workgroup_closure_only_text_finishes_silently(
    patched_engine: Engine, monkeypatch,
) -> None:
    monkeypatch.setenv("ALPI_WORKGROUP_DISPATCH", "wg_target")
    monkeypatch.setenv("ALPI_WORKGROUP_CLOSURE_ONLY", "1")
    monkeypatch.setattr(
        "alpi.alp.agent_context.build",
        lambda _home, wg_id=None, max_chars=None: "target context",
    )
    _stub_stream(monkeypatch, [_final_chunk("The task is still active.")])
    deliveries = []
    monkeypatch.setattr(
        "alpi.tools.execute",
        lambda name, args, **_kwargs: deliveries.append((name, args)),
    )
    events = []

    patched_engine.run_turn("close or stay silent", emit=events.append)

    assert deliveries == []
    assert any(event.kind == "done" for event in events)
    assert not any(event.kind == "error" for event in events)


def test_workgroup_member_text_without_tools_finishes_silently(
    patched_engine: Engine, monkeypatch,
) -> None:
    monkeypatch.setenv("ALPI_WORKGROUP_DISPATCH", "wg_target")
    monkeypatch.setenv("ALPI_WORKGROUP_PIPELINE", "1")
    monkeypatch.setenv("ALPI_WORKGROUP_MEMBER_TURN", "1")
    monkeypatch.setattr(
        "alpi.alp.agent_context.build",
        lambda _home, wg_id=None, max_chars=None: "target context",
    )
    _stub_stream(monkeypatch, [_final_chunk("I will inspect the files now.")])
    deliveries = []
    monkeypatch.setattr(
        "alpi.tools.execute",
        lambda name, args, **_kwargs: deliveries.append((name, args)),
    )
    events = []

    patched_engine.run_turn("work", emit=events.append)

    assert deliveries == []
    assert any(event.kind == "done" for event in events)
    assert not any(event.kind == "error" for event in events)


@pytest.mark.parametrize("bad_final", [
    _final_chunk("plain text instead of a post"),
    _final_chunk("", tool_calls=[{
        "id": "delivery", "name": "workgroup_post",
        "arguments": '{"wg_id":"wg_target","text":"partial work handed off"}',
    }]),
    _final_chunk("", tool_calls=[{
        "id": "wrong", "name": "workgroup_post",
        "arguments": '{"wg_id":"wg_other","text":"wrong target"}',
    }]),
])
def test_workgroup_finalizer_never_surfaces_or_misroutes_assistant_text(
    patched_engine: Engine, monkeypatch, bad_final: dict,
) -> None:
    patched_engine.cfg.tools.max_steps_per_turn = 1
    monkeypatch.setenv("ALPI_WORKGROUP_DISPATCH", "wg_target")
    monkeypatch.setattr(
        "alpi.alp.agent_context.build",
        lambda _home, wg_id=None, max_chars=None: "target context",
    )
    _stub_stream(monkeypatch, [
        _final_chunk("", tool_calls=[{
            "id": "todo", "name": "todo",
            "arguments": '{"action":"list"}',
        }]),
        bad_final,
    ])
    executed = []

    def fake_execute(name, args, **_kwargs):
        if name == "workgroup_post":
            executed.append((name, args))
        return ToolResult(ok=True, output="ok")

    monkeypatch.setattr(
        "alpi.tools.execute", fake_execute,
    )
    events = []

    patched_engine.run_turn("work", emit=events.append)

    assert [(name, args["wg_id"]) for name, args in executed] == [("workgroup_post", "wg_target")]
    assert executed[0][1]["text"] == (
        "#working turn ended before its handoff (1-step tool limit); "
        "saved work stays in the project, resuming from it on the next dispatch (continuation)"
    )
    assert not any(event.kind == "error" for event in events)
    assert not any(
        event.kind == "assistant_done" and event.final for event in events
    )


def test_side_purpose_gets_its_own_affinity(patched_engine: Engine) -> None:
    main = patched_engine._with_affinity({"model": "openrouter/x/y"})
    side = patched_engine._with_affinity({"model": "openrouter/x/y"}, purpose="side")
    assert main["extra_body"]["session_id"] != side["extra_body"]["session_id"]


def test_escalation_keeps_the_affinity(
    patched_engine: Engine, monkeypatch,
) -> None:
    from alpi import config as cfg_mod_real

    monkeypatch.setattr("alpi.ledger.spend_fraction", lambda *a, **kw: None)
    patched_engine.cfg.tiers.deep.model = "openrouter/deep/x"
    patched_engine.cfg.tiers.deep.effort = "high"
    monkeypatch.setattr(
        cfg_mod_real, "resolve_model",
        lambda cfg, **kw: {"model": "openrouter/deep/x"},
    )
    routed = patched_engine._escalated_route("openrouter/a/b", "high", "test")
    assert routed is not None
    kwargs, model, effort, note = routed
    assert model == "openrouter/deep/x"
    assert kwargs["extra_body"]["session_id"].startswith("alpi-")


def test_reset_session_clears_prefix_diag_state(patched_engine: Engine) -> None:
    patched_engine._prefix_shape = object()
    patched_engine._prefix_shape_loaded = True
    patched_engine._turn_prefix_reasons = {"tools"}
    patched_engine.last_host_context = "x"
    patched_engine.reset_session()
    assert patched_engine._prefix_shape is None
    assert patched_engine._prefix_shape_loaded is False
    assert patched_engine._turn_prefix_reasons == set()
    assert patched_engine._expected_rewrite == "reset"
    assert patched_engine.last_host_context == ""


def test_workgroup_finalizer_failure_still_posts_a_code_authored_continuation(
    patched_engine: Engine, monkeypatch,
) -> None:
    from alpi import llm as _llm

    now = [100.0]
    monkeypatch.setenv("ALPI_WORKGROUP_DISPATCH", "wg_target")
    monkeypatch.setattr("alpi.engine.time.monotonic", lambda: now[0])
    monkeypatch.setattr(
        "alpi.engine._turn_deadline_from_env", lambda _started: 105.0,
    )
    monkeypatch.setattr(
        "alpi.alp.agent_context.build",
        lambda _home, wg_id=None, max_chars=None: "target context",
    )
    calls = {"i": 0}

    def fake_stream(messages, tools, **kwargs):
        calls["i"] += 1
        if calls["i"] == 1:
            yield {"reasoning_delta": "started"}
            now[0] = 106.0
            raise RuntimeError("provider still blocked at the soft deadline")
        yield {"reasoning_delta": "still thinking"}
        raise _llm.TurnBudgetExceeded("turn budget deadline exceeded")

    executed = []

    def fake_execute(name, args, **_kwargs):
        executed.append((name, dict(args)))
        return ToolResult(ok=True, output="posted seq 11")

    monkeypatch.setattr("alpi.llm.stream", fake_stream)
    monkeypatch.setattr("alpi.tools.execute", fake_execute)
    events = []

    patched_engine.run_turn("work", emit=events.append)

    assert calls["i"] == 2
    assert len(executed) == 1 and executed[0][0] == "workgroup_post"
    text = executed[0][1]["text"]
    assert executed[0][1]["wg_id"] == "wg_target"
    assert text.startswith("#working turn ended before its handoff (out of time, handoff call failed: TurnBudgetExceeded)")
    assert text.endswith("(continuation)")
    assert any(event.kind == "done" for event in events)
    assert not any(event.kind == "error" for event in events)



def test_engine_exposes_the_turn_tool_count_to_each_tool_call(
    patched_engine: Engine, monkeypatch,
) -> None:
    from alpi.tools import _state

    calls = _stub_stream(monkeypatch, [
        _final_chunk("", tool_calls=[
            {"id": "t1", "name": "todo", "arguments": '{"action":"list"}'},
            {"id": "t2", "name": "todo", "arguments": '{"action":"list"}'},
        ]),
        _final_chunk("done"),
    ])
    seen = []

    def fake_execute(name, args, **_kwargs):
        seen.append(_state.get_turn_tools_run())
        return ToolResult(ok=True, output="ok")

    monkeypatch.setattr("alpi.tools.execute", fake_execute)

    patched_engine.run_turn("work", emit=lambda _e: None)

    assert calls["i"] == 2
    assert seen == [0, 1]
