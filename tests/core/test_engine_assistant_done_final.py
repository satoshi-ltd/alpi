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


def test_wall_clock_deadline_triggers_wrap_up(
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
    monkeypatch.setattr(
        "alpi.tools.execute",
        lambda _name, _args, deny=None: ToolResult(ok=True, output="posted seq 2"),
    )
    events = []

    patched_engine.run_turn("work", emit=events.append)

    assert calls["i"] == 2
    finals = [event.text for event in events if event.kind == "assistant_done" and event.final]
    assert finals == ["finished locally"]


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
