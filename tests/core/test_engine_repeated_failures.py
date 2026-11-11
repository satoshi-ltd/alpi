from __future__ import annotations

from pathlib import Path

import yaml

from alpi import config as cfg_mod
from alpi.engine import Engine
from alpi.tools.base import ToolResult


def _make_engine(monkeypatch, tmp_path: Path, data: dict | None = None) -> Engine:
    home = tmp_path / "h"
    home.mkdir()
    (home / "config.yaml").write_text(yaml.safe_dump(data or {
        "model": "base-model", "tiers": {"deep": {"model": "deep-model"}},
    }))
    monkeypatch.delenv("ALPI_TIER", raising=False)
    monkeypatch.delenv("ALPI_PLATFORM", raising=False)
    monkeypatch.delenv("ALPI_SILENT_JOB", raising=False)
    monkeypatch.setattr("alpi.engine._maybe_load_mcps", lambda _cfg: [])
    monkeypatch.setattr(Engine, "_build_system_prompt", lambda self: "you are alpi")
    monkeypatch.setattr("alpi.ctx_window.resolve", lambda *a: 400_000)
    monkeypatch.setattr("alpi.ledger.check", lambda *a, **kw: None)
    monkeypatch.setattr("alpi.ledger.record", lambda *a, **kw: None)
    monkeypatch.setattr("alpi.ledger.spend_fraction", lambda *a, **kw: None)
    return Engine(home=home, cfg=cfg_mod.load(home))


def _final(text: str, tool_calls=None) -> dict:
    return {"final": True, "tool_calls": tool_calls or [], "input_tokens": 1, "output_tokens": 1, "cost_usd": 0.0, "_text": text}


def _stream(monkeypatch, script):
    calls: list[list[dict]] = []

    def fake_stream(messages, tools, **kwargs):
        idx = len(calls)
        calls.append([dict(m) for m in messages])
        chunk = dict(script(idx))
        text = chunk.pop("_text", "")
        if text:
            yield {"text_delta": text}
        yield chunk

    monkeypatch.setattr("alpi.llm.stream", fake_stream)
    return calls


def _tools(monkeypatch, results):
    executed: list[str] = []

    def _run(name, args, deny=frozenset(), deny_reasons=None):
        executed.append(name)
        return results(name, len(executed))

    monkeypatch.setattr("alpi.tools.execute", _run)
    monkeypatch.setattr("alpi.tools._execute_registered", _run)
    return executed


def _call(i: int, name: str = "terminal") -> dict:
    return {"id": f"t{i}", "name": name, "arguments": "{}"}


def _hints(messages: list[dict]) -> list[str]:
    return [str(m["content"]) for m in messages if m.get("role") == "user" and "[engine] The last" in str(m.get("content"))]


def test_three_identical_failures_hint_instead_of_escalating(monkeypatch, tmp_path: Path) -> None:
    engine = _make_engine(monkeypatch, tmp_path)
    _tools(monkeypatch, lambda name, n: ToolResult(ok=False, output="", error="pass_token_required: include the passToken"))

    def script(i):
        if i < 3:
            return _final("", tool_calls=[_call(i)])
        return _final("giving up")

    calls = _stream(monkeypatch, script)
    events: list = []
    engine.run_turn("go", emit=events.append)
    assert not [e for e in events if e.kind == "routing"]
    hints = _hints(calls[3])
    assert len(hints) == 1
    assert "pass_token_required" in hints[0] and "terminal" in hints[0]
    assert not _hints(calls[2])


def test_the_same_error_from_different_calls_is_not_a_repeat(monkeypatch, tmp_path: Path) -> None:
    engine = _make_engine(monkeypatch, tmp_path)
    _tools(monkeypatch, lambda name, n: ToolResult(ok=False, output="", error="command failed (exit 1)"))
    args = ['{"command": "grep a"}', '{"command": "grep b"}', '{"command": "grep c"}']

    def script(i):
        if i < 3:
            return _final("", tool_calls=[{"id": f"t{i}", "name": "terminal", "arguments": args[i]}])
        return _final("done")

    calls = _stream(monkeypatch, script)
    events: list = []
    engine.run_turn("go", emit=events.append)
    assert not any(_hints(c) for c in calls)
    routing = [e for e in events if e.kind == "routing"]
    assert len(routing) == 1 and "3 consecutive tool failures" in routing[0].text


def test_two_identical_then_one_different_neither_hints_nor_escalates(monkeypatch, tmp_path: Path) -> None:
    engine = _make_engine(monkeypatch, tmp_path)
    _tools(monkeypatch, lambda name, n: ToolResult(ok=False, output="", error="A" if n < 3 else "B"))

    def script(i):
        if i < 3:
            return _final("", tool_calls=[_call(i)])
        return _final("done")

    calls = _stream(monkeypatch, script)
    events: list = []
    engine.run_turn("go", emit=events.append)
    assert not [e for e in events if e.kind == "routing"]
    assert not any(_hints(c) for c in calls)


def test_an_exhausted_tool_does_not_exhaust_a_sibling_with_the_same_error(monkeypatch, tmp_path: Path) -> None:
    engine = _make_engine(monkeypatch, tmp_path)
    executed = _tools(monkeypatch, lambda name, n: ToolResult(ok=False, output="", error="same"))

    def script(i):
        if i < 5:
            return _final("", tool_calls=[_call(i, "search")])
        if i == 5:
            return _final("", tool_calls=[_call(9, "grep")])
        return _final("end")

    _stream(monkeypatch, script)
    engine.run_turn("go", emit=lambda e: None)
    assert executed == ["search"] * 5 + ["grep"]


def test_hint_is_sent_once_per_error_and_the_fifth_failure_exhausts_the_tool(monkeypatch, tmp_path: Path) -> None:
    engine = _make_engine(monkeypatch, tmp_path)
    executed = _tools(monkeypatch, lambda name, n: ToolResult(ok=False, output="", error="same thing"))

    def script(i):
        if i < 6:
            return _final("", tool_calls=[_call(i)])
        return _final("stopping")

    calls = _stream(monkeypatch, script)
    events: list = []
    engine.run_turn("go", emit=events.append)
    assert len(executed) == 5
    assert sum(len(_hints(c)) for c in calls) <= len(calls)
    assert len(_hints(calls[-1])) == 1
    refused = [e for e in events if e.kind == "tool_end" and "exhausted for this turn" in e.output]
    assert len(refused) == 1
    assert not [e for e in events if e.kind == "routing"]


def test_a_success_resets_the_streak(monkeypatch, tmp_path: Path) -> None:
    engine = _make_engine(monkeypatch, tmp_path)
    _tools(monkeypatch, lambda name, n: ToolResult(ok=True, output="fine") if n == 3 else ToolResult(ok=False, output="", error="same"))

    def script(i):
        if i < 4:
            return _final("", tool_calls=[_call(i)])
        return _final("end")

    calls = _stream(monkeypatch, script)
    engine.run_turn("go", emit=lambda e: None)
    assert not any(_hints(c) for c in calls)


def test_a_batch_with_an_exhausted_tool_runs_serially_and_refuses_it(monkeypatch, tmp_path: Path) -> None:
    engine = _make_engine(monkeypatch, tmp_path)
    executed = _tools(monkeypatch, lambda name, n: ToolResult(ok=False, output="", error="nope"))

    def script(i):
        if i < 5:
            return _final("", tool_calls=[_call(i, "search")])
        if i == 5:
            return _final("", tool_calls=[_call(10, "search"), _call(11, "search")])
        return _final("end")

    _stream(monkeypatch, script)
    events: list = []
    engine.run_turn("go", emit=events.append)
    assert len(executed) == 5
    refused = [e for e in events if e.kind == "tool_end" and "exhausted" in e.output]
    assert len(refused) == 2


def test_empty_reply_after_a_delivery_tool_closes_the_turn(monkeypatch, tmp_path: Path) -> None:
    engine = _make_engine(monkeypatch, tmp_path)
    _tools(monkeypatch, lambda name, n: ToolResult(ok=True, output="notified"))

    def script(i):
        if i == 0:
            return _final("", tool_calls=[_call(0, "notify")])
        return _final("")

    calls = _stream(monkeypatch, script)
    events: list = []
    engine.run_turn("daily brief", emit=events.append)
    assert len(calls) == 2
    assert not [e for e in events if e.kind == "routing"]
    assert not any("empty reply" in str(m.get("content")) for m in engine.session.messages)
    assert any(e.kind == "done" for e in events)


def test_email_send_counts_as_delivery_but_email_read_does_not(monkeypatch, tmp_path: Path) -> None:
    from alpi.session import ToolLog
    from alpi.engine import _delivered_by_tool
    assert _delivered_by_tool([ToolLog(at=0, name="email", args={"action": "send"}, result="", ok=True, duration_s=0)])
    assert not _delivered_by_tool([ToolLog(at=0, name="email", args={"action": "read"}, result="", ok=True, duration_s=0)])
    assert not _delivered_by_tool([ToolLog(at=0, name="notify", args={}, result="", ok=False, duration_s=0)])


def test_silent_scheduled_job_may_end_without_text(monkeypatch, tmp_path: Path) -> None:
    engine = _make_engine(monkeypatch, tmp_path)
    monkeypatch.setenv("ALPI_PLATFORM", "cron")
    monkeypatch.setenv("ALPI_SILENT_JOB", "1")
    calls = _stream(monkeypatch, lambda i: _final(""))
    events: list = []
    engine.run_turn("check for new workouts", emit=events.append)
    assert len(calls) == 1
    assert not [e for e in events if e.kind == "routing"]
    assert any(e.kind == "done" for e in events)


def test_notifying_scheduled_job_is_nudged_but_not_escalated(monkeypatch, tmp_path: Path) -> None:
    engine = _make_engine(monkeypatch, tmp_path)
    monkeypatch.setenv("ALPI_PLATFORM", "cron")

    def script(i):
        return _final("" if i == 0 else "the report")

    calls = _stream(monkeypatch, script)
    events: list = []
    engine.run_turn("report", emit=events.append)
    assert len(calls) == 2
    assert not [e for e in events if e.kind == "routing"]
    assert next(e for e in events if e.kind == "assistant_done" and e.final).text == "the report"


def test_attended_chat_keeps_the_escalation_on_an_empty_reply(monkeypatch, tmp_path: Path) -> None:
    engine = _make_engine(monkeypatch, tmp_path)
    calls = _stream(monkeypatch, lambda i: _final("" if i == 0 else "hola"))
    events: list = []
    engine.run_turn("hi", emit=events.append)
    routing = [e for e in events if e.kind == "routing"]
    assert len(routing) == 1 and "empty reply" in routing[0].text
    assert len(calls) == 2


def test_a_workgroup_turn_is_still_nudged_after_a_working_post(monkeypatch, tmp_path: Path) -> None:
    engine = _make_engine(monkeypatch, tmp_path)
    monkeypatch.setenv("ALPI_WORKGROUP_DISPATCH", "wg_x")
    monkeypatch.setattr("alpi.alp.agent_context.build", lambda *a, **k: "WG CONTEXT")
    _tools(monkeypatch, lambda name, n: ToolResult(ok=True, output="posted"))

    def script(i):
        if i == 0:
            return _final("", tool_calls=[_call(0, "notify")])
        if i == 1:
            return _final("")
        return _final("", tool_calls=[{"id": "p", "name": "workgroup_post", "arguments": '{"wg_id": "wg_x", "text": "#phase done"}'}])

    calls = _stream(monkeypatch, script)
    events: list = []
    engine.run_turn("[workgroup-pipeline] task", emit=events.append)
    monkeypatch.delenv("ALPI_WORKGROUP_DISPATCH")
    assert len(calls) >= 3
    assert any("empty reply" in str(m.get("content")) for m in calls[2])
    assert not [e for e in events if e.kind == "routing"]


def _varying(i: int, name: str = "search") -> dict:
    return {"id": f"t{i}", "name": name, "arguments": f'{{"pattern": "q{i}"}}'}


def test_one_error_under_changing_arguments_hints_first_and_escalates_only_if_it_goes_on(monkeypatch, tmp_path: Path) -> None:
    engine = _make_engine(monkeypatch, tmp_path)
    executed = _tools(monkeypatch, lambda name, n: ToolResult(ok=False, output="", error="pass_token_required: include the passToken"))

    def script(i):
        if i < 6:
            return _final("", tool_calls=[_varying(i)])
        return _final("blocked")

    calls = _stream(monkeypatch, script)
    events: list = []
    engine.run_turn("go", emit=events.append)
    assert executed == ["search"] * 6
    assert not _hints(calls[2])
    hints = _hints(calls[6])
    assert len(hints) == 1
    assert "although the arguments changed" in hints[0] and "pass_token_required" in hints[0]
    order = [e.kind for e in events if e.kind in ("engine_note", "routing")]
    assert order == ["engine_note", "routing"]
    assert "5 consecutive tool failures" in [e for e in events if e.kind == "routing"][0].text


def test_four_same_error_failures_hint_without_escalating(monkeypatch, tmp_path: Path) -> None:
    engine = _make_engine(monkeypatch, tmp_path)
    _tools(monkeypatch, lambda name, n: ToolResult(ok=n > 4, output="fine" if n > 4 else "", error="" if n > 4 else "old_string not found"))

    def script(i):
        if i < 5:
            return _final("", tool_calls=[_varying(i, "edit_file")])
        return _final("done")

    _stream(monkeypatch, script)
    events: list = []
    engine.run_turn("go", emit=events.append)
    assert [e.kind for e in events if e.kind in ("engine_note", "routing")] == ["engine_note"]


def test_an_empty_error_gets_no_same_error_hint(monkeypatch, tmp_path: Path) -> None:
    engine = _make_engine(monkeypatch, tmp_path)
    _tools(monkeypatch, lambda name, n: ToolResult(ok=False, output="", error=""))

    def script(i):
        if i < 3:
            return _final("", tool_calls=[_varying(i)])
        return _final("done")

    calls = _stream(monkeypatch, script)
    events: list = []
    engine.run_turn("go", emit=events.append)
    assert not any(_hints(c) for c in calls)
    assert len([e for e in events if e.kind == "routing"]) == 1


def test_a_parallel_batch_past_the_escalation_mark_still_gets_the_note_first(monkeypatch, tmp_path: Path) -> None:
    engine = _make_engine(monkeypatch, tmp_path)
    _tools(monkeypatch, lambda name, n: ToolResult(ok=False, output="", error="pass_token_required"))

    def script(i):
        if i == 0:
            return _final("", tool_calls=[_varying(n) for n in range(5)])
        if i == 1:
            return _final("", tool_calls=[_varying(9)])
        return _final("blocked")

    _stream(monkeypatch, script)
    events: list = []
    engine.run_turn("go", emit=events.append)
    assert [e.kind for e in events if e.kind in ("engine_note", "routing")] == ["engine_note", "routing"]


def test_every_engine_note_is_emitted_as_an_event(monkeypatch, tmp_path: Path) -> None:
    engine = _make_engine(monkeypatch, tmp_path)
    _tools(monkeypatch, lambda name, n: ToolResult(ok=False, output="", error="boom"))

    def script(i):
        if i < 3:
            return _final("", tool_calls=[_call(i, "search")])
        if i == 3:
            return _final("")
        return _final("answer")

    calls = _stream(monkeypatch, script)
    events: list = []
    engine.run_turn("go", emit=events.append)
    notes = [e.text for e in events if e.kind == "engine_note"]
    assert len(notes) == 2
    assert "[engine] The last 3 calls to search" in notes[0]
    assert "empty reply" in notes[1]
    injected = [str(m["content"]) for m in calls[-1] if m.get("role") == "user" and str(m.get("content")).startswith("[engine]")]
    assert injected == notes
