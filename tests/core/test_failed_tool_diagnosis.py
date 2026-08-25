"""A failed tool's diagnosis must reach the model on every path that relays tools — engine, delegate and research — via the shared failure_payload helper."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from alpi.config import Config, ToolsConfig
from alpi.engine import Engine
from alpi.tools.base import ToolResult


@pytest.fixture
def engine(monkeypatch, tmp_path: Path) -> Engine:
    home = tmp_path / "h"
    home.mkdir()
    (home / "sessions").mkdir()
    (home / "config.yaml").write_text(yaml.safe_dump({"model": "gpt-5.4-mini"}))
    monkeypatch.setattr("alpi.engine._maybe_load_mcps", lambda _cfg: [])
    monkeypatch.setattr(Engine, "_build_system_prompt", lambda self: "alpi")
    monkeypatch.setattr("alpi.ctx_window.resolve", lambda _h, _c, _m: 400_000)
    monkeypatch.setattr("alpi.ledger.check", lambda *a, **kw: None)
    monkeypatch.setattr("alpi.ledger.record", lambda *a, **kw: None)
    cfg = Config(
        home=home, model="gpt-5.4-mini",
        tools=ToolsConfig(max_steps_per_turn=6),
        raw={},
    )
    return Engine(home=home, cfg=cfg)


def _streams(calls):
    def fake_stream(*_a, **_kw):
        step = calls.pop(0)
        yield {
            "final": True,
            "input_tokens": 1, "output_tokens": 1, "cost_usd": 0.0,
            "tool_calls": step, "text_delta": "" if step else "done",
        }
    return fake_stream


def test_failed_tool_output_reaches_the_transcript(engine: Engine, monkeypatch) -> None:
    monkeypatch.setattr("alpi.llm.stream", _streams([
        [{"id": "c1", "name": "skill",
          "arguments": '{"action": "run", "name": "repo-task", "args": ["clone", "x"]}'}],
        [],
    ]))
    monkeypatch.setattr(
        "alpi.tools.execute",
        lambda *_a, **_kw: ToolResult(
            ok=False,
            output='{"ok": false, "error": "clone failed: fatal: could not read Username"}',
            error="script exited rc=1",
        ),
    )
    engine.run_turn("clone x", emit=lambda _e: None)

    tool_msgs = [m for m in engine.session.messages if m.get("role") == "tool"]
    assert tool_msgs, "no tool message reached the transcript"
    payload = tool_msgs[-1]["content"]
    assert "ERROR: script exited rc=1" in payload
    assert "could not read Username" in payload


def test_failed_tool_without_output_stays_terse(engine: Engine, monkeypatch) -> None:
    monkeypatch.setattr("alpi.llm.stream", _streams([
        [{"id": "c1", "name": "skill", "arguments": '{"action": "run"}'}],
        [],
    ]))
    monkeypatch.setattr(
        "alpi.tools.execute",
        lambda *_a, **_kw: ToolResult(ok=False, output="", error="bad arguments"),
    )
    engine.run_turn("x", emit=lambda _e: None)

    tool_msgs = [m for m in engine.session.messages if m.get("role") == "tool"]
    payload = tool_msgs[-1]["content"]
    # nothing but the error between the untrusted-output markers
    assert "ERROR: bad arguments\n[END OUTPUT" in payload


def test_failure_payload_folds_output_and_stays_terse_without_it() -> None:
    from alpi.tools.base import failure_payload

    with_diag = ToolResult(ok=False, output='{"ok": false, "error": "boom"}', error="rc=1")
    assert failure_payload(with_diag) == 'ERROR: rc=1\n{"ok": false, "error": "boom"}'
    bare = ToolResult(ok=False, output="  \n", error="bad arguments")
    assert failure_payload(bare) == "ERROR: bad arguments"


def _completions_then_capture(monkeypatch, captured: list):
    from types import SimpleNamespace

    calls = [
        [{"id": "c1", "name": "write_file", "arguments": '{"path": "x", "content": "y"}'}],
        [],
    ]

    def fake_complete(**kw):
        captured.append(kw.get("messages") or [])
        step = calls.pop(0)
        return SimpleNamespace(content="done" if not step else "", tool_calls=step,
                               input_tokens=1, output_tokens=1, cost_usd=0.0, raw=None)

    monkeypatch.setattr("alpi.llm.complete", fake_complete)


def _failing_execute(*_a, **_kw):
    return ToolResult(ok=False, output="FAIL src/app.test.js\nExpected 2, got 3",
                      error="command failed (exit 1)")


def test_delegate_relays_the_failed_tool_diagnosis(monkeypatch, tmp_home_no_env: Path) -> None:
    from alpi.tools.delegate import Delegate
    import alpi.tools as tools_mod

    captured: list = []
    _completions_then_capture(monkeypatch, captured)
    monkeypatch.setattr(tools_mod, "execute", _failing_execute)
    out = Delegate().run(goal="fix the failing test", toolsets=["file"])
    assert out.ok
    tool_msgs = [m for m in captured[-1] if m.get("role") == "tool"]
    assert tool_msgs, "delegate relayed no tool message"
    body = tool_msgs[-1]["content"]
    assert "ERROR: command failed (exit 1)" in body
    assert "Expected 2, got 3" in body
    # repo-controlled stdout enters a write-capable sub-agent: it must arrive fenced as data, never as instructions
    assert "[UNTRUSTED OUTPUT tool=write_file kind=error" in body
    assert "[END OUTPUT tool=write_file]" in body


def test_research_relays_the_failed_tool_diagnosis(monkeypatch, tmp_home_no_env: Path) -> None:
    from alpi.tools.research import Research
    import alpi.tools as tools_mod

    captured: list = []
    from types import SimpleNamespace

    calls = [
        [{"id": "c1", "name": "web_fetch", "arguments": '{"url": "https://x"}'}],
        [],
    ]

    def fake_complete(**kw):
        captured.append(kw.get("messages") or [])
        step = calls.pop(0)
        return SimpleNamespace(content="report" if not step else "", tool_calls=step,
                               input_tokens=1, output_tokens=1, cost_usd=0.0, raw=None)

    monkeypatch.setattr("alpi.llm.complete", fake_complete)
    monkeypatch.setattr(tools_mod, "execute", lambda *a, **kw: ToolResult(
        ok=False, output="status 503 from upstream\nretry-after: 60", error="fetch failed"))
    out = Research().run(brief="what is X")
    assert out.ok
    tool_msgs = [m for m in captured[-1] if m.get("role") == "tool"]
    assert tool_msgs, "research relayed no tool message"
    body = tool_msgs[-1]["content"]
    assert "ERROR: fetch failed" in body
    assert "retry-after: 60" in body
    assert "[UNTRUSTED OUTPUT tool=web_fetch kind=error" in body
    assert "[END OUTPUT tool=web_fetch]" in body
