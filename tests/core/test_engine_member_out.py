from __future__ import annotations

import json
from pathlib import Path

from alpi import tools
from alpi.config import Config, ToolsConfig
from alpi.engine import Engine
from alpi.host.connection_context import ConnectionContext, use


def _final(text: str, tool_calls=None):
    return {
        "final": True, "text": text,
        "input_tokens": 10, "output_tokens": 5, "cost_usd": 0.0,
        "tool_calls": tool_calls or [],
    }


def _call(call_id: str, tool: str, **arguments):
    return {"id": call_id, "name": tool, "arguments": json.dumps(arguments)}


def _stub_stream(monkeypatch, scripted):
    state = {"i": 0, "seen": []}

    def fake_stream(messages, tools, **_kwargs):
        state["seen"].append([dict(m) for m in messages])
        chunk = dict(scripted[state["i"]]) if state["i"] < len(scripted) else _final("")
        state["i"] += 1
        text = chunk.pop("text", "")
        if text:
            yield {"text_delta": text}
        yield chunk

    monkeypatch.setattr("alpi.llm.stream", fake_stream)
    return state


def _tool_results(state) -> list[str]:
    return [str(m.get("content", "")) for m in state["seen"][-1] if m.get("role") == "tool"]


def test_a_member_turn_may_attach_what_its_skill_produced_and_the_next_turn_may_not_reread_it(tmp_home: Path, monkeypatch) -> None:
    out = tmp_home / "out"
    out.mkdir()
    report = out / "report.md"
    script = f"import json, pathlib\npathlib.Path({str(report)!r}).write_text('quarterly')\nprint(json.dumps({{'out': {str(report)!r}}}))\n"
    assert tools.execute("skill", {"action": "create", "name": "reporter", "category": "personal", "description": "Reports.", "body": "## When to use\nAlways.\n"}).ok
    assert tools.execute("skill", {"action": "add_file", "name": "reporter", "subdir": "scripts", "filename": "run.py", "content": script}).ok

    monkeypatch.setattr("alpi.engine._maybe_load_mcps", lambda _cfg: [])
    monkeypatch.setattr(Engine, "_build_system_prompt", lambda self: "you are alpi")
    monkeypatch.setattr("alpi.ctx_window.resolve", lambda _h, _c, _m: 400_000)
    monkeypatch.setattr("alpi.ledger.check", lambda *a, **kw: None)
    monkeypatch.setattr("alpi.ledger.record", lambda *a, **kw: None)
    cfg = Config(home=tmp_home, model="gpt-5.4-mini", tools=ToolsConfig(max_steps_per_turn=6), raw={})
    member = ConnectionContext(connection_id="c1", device_id="d1", source="remote", role="member")
    with use(member):
        engine = Engine(home=tmp_home, cfg=cfg)

    first = _stub_stream(monkeypatch, [
        _final("running", tool_calls=[_call("t1", "skill", action="run", name="reporter")]),
        _final("attaching", tool_calls=[_call("t2", "attach_file", path=str(report))]),
        _final("done"),
    ])
    engine.run_turn("make the report", emit=lambda _e: None)
    assert "refused" not in " ".join(_tool_results(first)).lower()
    assert "cannot read" not in " ".join(_tool_results(first))
    assert json.dumps({"out": str(report)}) in " ".join(_tool_results(first))

    second = _stub_stream(monkeypatch, [
        _final("reading", tool_calls=[_call("t3", "read_file", path=str(report))]),
        _final("done"),
    ])
    engine.run_turn("show me the report again", emit=lambda _e: None)
    joined = " ".join(_tool_results(second))
    assert "quarterly" not in joined and "created in out/" in joined
