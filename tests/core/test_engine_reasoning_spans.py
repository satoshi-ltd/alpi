from __future__ import annotations

import json
from pathlib import Path

import pytest

from alpi import config, home, memory, session as session_mod
from alpi.engine import Engine
from alpi.host import handlers as data_handlers
from alpi.host import server as host_server
from alpi.host import sessions as data_sessions
from alpi.tools.base import ToolResult


@pytest.fixture
def bootstrapped_home(tmp_home_no_env: Path) -> Path:
    home.ensure_home(tmp_home_no_env)
    config.seed_defaults(tmp_home_no_env)
    memory.MemoryStore(tmp_home_no_env).seed_defaults()
    data_sessions._clear_payload_cache()
    return tmp_home_no_env


def _final(tool_id: str | None = None) -> dict:
    calls = [{"id": tool_id, "name": "noop", "arguments": "{}"}] if tool_id else []
    return {"final": True, "tool_calls": calls, "input_tokens": 1, "output_tokens": 1, "cost_usd": 0.0}


def _three_span_turn(monkeypatch):  # noqa: ANN001
    from alpi import engine as engine_mod
    clock = {"t": 1000.0}
    monkeypatch.setattr(engine_mod.time, "time", lambda: clock["t"])

    steps = [
        [(1000.0, {"reasoning_delta": "plan"}), (1003.0, _final("t0"))],
        [(1055.0, {"reasoning_delta": "check"}), (1056.5, _final("t1"))],
        [(1107.0, {"reasoning_delta": "wrap"}), (1109.0, {"text_delta": "the answer"}), (1112.0, _final())],
    ]
    calls = {"i": 0}

    def _stream(*_a, **_kw):
        idx = calls["i"]
        calls["i"] += 1
        for t, chunk in steps[idx]:
            clock["t"] = t
            yield chunk

    def _execute(_name, _args, **_kw):
        clock["t"] += 50.0
        return ToolResult(ok=True, output="ok")

    monkeypatch.setattr(engine_mod.llm, "stream", _stream)
    monkeypatch.setattr(engine_mod.tools, "execute", _execute)


def test_three_spans_store_before_tool_and_match_live_frames(bootstrapped_home, monkeypatch):
    _three_span_turn(monkeypatch)
    events: list = []
    engine = Engine(home=bootstrapped_home, cfg=config.load(bootstrapped_home))
    engine.run_turn("go", events.append)

    turn = engine.session.turns[-1]
    assert [t.name for t in turn.tools] == ["noop", "noop"]
    assert turn.reasoning_spans == [
        {"seconds": 3.0, "before_tool": 0, "text": "plan"},
        {"seconds": 3.5, "before_tool": 1, "text": "check"},
        {"seconds": 2.5, "before_tool": 2, "text": "wrap"},
    ]
    live = [ev.seconds for ev in events if ev.kind == "reasoning_done"]
    assert live == [sp["seconds"] for sp in turn.reasoning_spans]
    assert turn.reasoned_s == turn.reasoning_spans[0]["seconds"]

    kinds = [ev.kind for ev in events]
    first_done = kinds.index("reasoning_done")
    assert kinds.index("tool_start") > first_done
    assert kinds[kinds.index("assistant_delta") - 1] == "reasoning_done"

    engine.session.save()
    path = bootstrapped_home / "sessions" / f"{engine.session.id}.json"
    raw = json.loads(path.read_text())["turns"][-1]
    assert raw["reasoning_spans"] == turn.reasoning_spans
    assert session_mod.load_turns(json.loads(path.read_text()))[-1].reasoning_spans == turn.reasoning_spans


@pytest.mark.asyncio
async def test_session_read_exposes_reasoning_spans(bootstrapped_home, monkeypatch):
    _three_span_turn(monkeypatch)
    engine = Engine(home=bootstrapped_home, cfg=config.load(bootstrapped_home))
    engine.run_turn("go", lambda _e: None)
    engine.session.save()

    srv = host_server.Server(home=bootstrapped_home)
    data_handlers.register(srv)
    monkeypatch.setattr(data_handlers, "_resolve_home", lambda p: bootstrapped_home)
    response = await srv._dispatch({
        "id": "r", "method": "host.session.read",
        "params": {"profile": "default", "id": engine.session.id},
    })
    turn = response["result"]["session"]["turns"][-1]
    assert [sp["before_tool"] for sp in turn["reasoning_spans"]] == [0, 1, 2]


def test_turn_without_reasoning_omits_the_field(bootstrapped_home, monkeypatch):
    from alpi import engine as engine_mod

    def _stream(*_a, **_kw):
        yield {"text_delta": "hi"}
        yield _final()
    monkeypatch.setattr(engine_mod.llm, "stream", _stream)
    events: list = []
    engine = Engine(home=bootstrapped_home, cfg=config.load(bootstrapped_home))
    engine.run_turn("hello", events.append)

    assert engine.session.turns[-1].reasoning_spans == []
    assert not any(ev.kind == "reasoning_done" for ev in events)
    engine.session.save()
    raw = json.loads((bootstrapped_home / "sessions" / f"{engine.session.id}.json").read_text())
    assert "reasoning_spans" not in raw["turns"][-1]


def test_reasoning_only_step_closes_at_step_end(bootstrapped_home, monkeypatch):
    from alpi import engine as engine_mod

    def _stream(*_a, **_kw):
        yield {"reasoning_delta": "hmm"}
        yield _final()
    monkeypatch.setattr(engine_mod.llm, "stream", _stream)
    events: list = []
    engine = Engine(home=bootstrapped_home, cfg=config.load(bootstrapped_home))
    engine.run_turn("hello", events.append)

    assert [ev.kind for ev in events].count("reasoning_done") >= 1
    assert all(sp["before_tool"] == 0 for sp in engine.session.turns[-1].reasoning_spans)


def test_old_session_without_spans_loads():
    turns = session_mod.load_turns({"turns": [
        {"at": 1.0, "user": "u", "assistant": "a", "tools": [], "reasoning": "r", "reasoned_s": 2.0},
        {"at": 2.0, "user": "u", "assistant": "a", "tools": [], "reasoning_spans": [
            {"seconds": 1.2, "before_tool": 0}, {"bad": True}, "junk",
        ]},
    ]})
    assert turns[0].reasoning_spans == []
    assert turns[0].reasoned_s == 2.0
    assert turns[1].reasoning_spans == [{"seconds": 1.2, "before_tool": 0}]


def test_a_step_without_tools_does_not_inflate_the_next_span(monkeypatch):
    from alpi import engine as engine_mod
    from alpi.engine import AgentEvent, _ReasoningSpans
    clock = {"t": 100.0}
    monkeypatch.setattr(engine_mod.time, "time", lambda: clock["t"])
    out: list = []
    spans = _ReasoningSpans(out.append, 100.0, [])
    spans.new_step(True)
    clock["t"] = 101.0
    spans(AgentEvent(kind="reasoning_delta", text="first"))
    clock["t"] = 102.0
    spans(AgentEvent(kind="assistant_done", text=""))
    clock["t"] = 160.0
    spans.new_step(False)
    spans(AgentEvent(kind="reasoning_delta", text="second"))
    clock["t"] = 161.5
    spans.close()
    assert spans.spans == [{"seconds": 2.0, "before_tool": 0, "text": "first"}, {"seconds": 1.5, "before_tool": 0, "text": "second"}]
    assert [ev.seconds for ev in out if ev.kind == "reasoning_done"] == [2.0, 1.5]


def test_span_text_survives_save_and_load_and_old_rows_load_without_it():
    rows = session_mod._spans_from_serialized([
        {"seconds": 1.0, "before_tool": 0, "text": "plan"},
        {"seconds": 2.0, "before_tool": 1},
        {"seconds": "bad"},
    ])
    assert rows == [{"seconds": 1.0, "before_tool": 0, "text": "plan"}, {"seconds": 2.0, "before_tool": 1}]
    assert session_mod._span_row({"seconds": 1.04, "before_tool": 0, "text": "x" * 20000}, lambda v: v, [10**9])["text"].startswith("x")
    assert len(session_mod._span_row({"seconds": 1.0, "before_tool": 0, "text": "x" * 20000}, lambda v: v, [10**9])["text"]) <= session_mod.TOOL_REASONING_CAP + 64


def test_all_span_texts_share_the_turn_reasoning_budget():
    budget = [session_mod.TURN_REASONING_CAP]
    rows = [session_mod._span_row({"seconds": 1.0, "before_tool": i, "text": "y" * 6000}, lambda v: v, budget) for i in range(10)]
    stored = sum(len(r.get("text", "").encode()) for r in rows)
    assert stored <= session_mod.TURN_REASONING_CAP + 64
    assert "text" not in rows[-1] and rows[-1]["seconds"] == 1.0


def test_reasoning_discarded_by_a_retry_never_reaches_the_span(bootstrapped_home, monkeypatch):
    from alpi import engine as engine_mod

    def _stream(*_a, **_kw):
        yield {"reasoning_delta": "DISCARDED"}
        yield {"retry_reset": True}
        yield {"reasoning_delta": "kept"}
        yield {"text_delta": "answer"}
        yield _final()

    monkeypatch.setattr(engine_mod.llm, "stream", _stream)
    engine = Engine(home=bootstrapped_home, cfg=config.load(bootstrapped_home))
    engine.run_turn("go", lambda _ev: None)
    turn = engine.session.turns[-1]
    assert [sp.get("text") for sp in turn.reasoning_spans] == ["kept"]
    assert turn.reasoning == "kept"
