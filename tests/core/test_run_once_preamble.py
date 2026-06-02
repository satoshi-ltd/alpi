"""`_run_once` writes only the terminal assistant reply to stdout — preamble emitted before tool calls is discarded."""

from __future__ import annotations

import io
import sys
from pathlib import Path

from alpi import cli as _cli_mod
from alpi.config import Config, ToolsConfig
from alpi.engine import AgentEvent


def _make_run_turn(event_sequence: list[AgentEvent]):
    """Return a fake run_turn that fires the given events and returns."""
    def fake_run_turn(self, user_text: str, emit=None, **_kwargs):
        if emit:
            for ev in event_sequence:
                emit(ev)
    return fake_run_turn


def test_preamble_stripped_before_tool_call(tmp_home: Path, monkeypatch) -> None:
    """Text emitted before a tool_start must not appear in the final reply."""
    monkeypatch.setattr(_cli_mod, "_bootstrap", lambda _h: None)
    monkeypatch.setattr(
        "alpi.config.load",
        lambda _h: Config(home=tmp_home, model="stub", raw={}),
    )
    monkeypatch.setattr("alpi.engine.Engine.save_session", lambda self: None)
    monkeypatch.setattr("alpi.engine._maybe_load_mcps", lambda _cfg: [])
    monkeypatch.setattr("alpi.engine.Engine._build_system_prompt", lambda self: "stub")
    monkeypatch.setattr("alpi.ctx_window.resolve", lambda _h, _c, _m: 200_000)
    monkeypatch.setattr("alpi.ledger.check", lambda *a, **kw: None)
    monkeypatch.setattr("alpi.ledger.record", lambda *a, **kw: None)

    events = [
        AgentEvent(kind="assistant_done", text="Let me load the skill first."),
        AgentEvent(kind="tool_start", name="skill", args={}),
        AgentEvent(kind="tool_end", name="skill", ok=True),
        AgentEvent(kind="assistant_done", text="Now let me check the recent joke history."),
        AgentEvent(kind="tool_start", name="read_file", args={}),
        AgentEvent(kind="tool_end", name="read_file", ok=True),
        AgentEvent(
            kind="assistant_done",
            text="¡Buenos días! El café también llora los lunes.",
            final=True,
        ),
    ]
    monkeypatch.setattr(
        "alpi.engine.Engine.run_turn",
        _make_run_turn(events),
    )

    buf = io.StringIO()
    monkeypatch.setattr(sys, "stdout", buf)
    _cli_mod._run_once(tmp_home, "buenos días", emit_events=False, persist=False)

    output = buf.getvalue().strip()
    assert output == "¡Buenos días! El café también llora los lunes."
    assert "Let me load the skill first" not in output
    assert "recent joke history" not in output


def test_no_tool_calls_keeps_full_reply(tmp_home: Path, monkeypatch) -> None:
    """When there are no tool calls the single assistant_done is the reply."""
    monkeypatch.setattr(_cli_mod, "_bootstrap", lambda _h: None)
    monkeypatch.setattr(
        "alpi.config.load",
        lambda _h: Config(home=tmp_home, model="stub", raw={}),
    )
    monkeypatch.setattr("alpi.engine.Engine.save_session", lambda self: None)
    monkeypatch.setattr("alpi.engine._maybe_load_mcps", lambda _cfg: [])
    monkeypatch.setattr("alpi.engine.Engine._build_system_prompt", lambda self: "stub")
    monkeypatch.setattr("alpi.ctx_window.resolve", lambda _h, _c, _m: 200_000)
    monkeypatch.setattr("alpi.ledger.check", lambda *a, **kw: None)
    monkeypatch.setattr("alpi.ledger.record", lambda *a, **kw: None)

    events = [
        AgentEvent(
            kind="assistant_done",
            text="Aquí tienes la respuesta directa.",
            final=True,
        ),
    ]
    monkeypatch.setattr(
        "alpi.engine.Engine.run_turn",
        _make_run_turn(events),
    )

    buf = io.StringIO()
    monkeypatch.setattr(sys, "stdout", buf)
    _cli_mod._run_once(tmp_home, "pregunta simple", emit_events=False, persist=False)

    output = buf.getvalue().strip()
    assert output == "Aquí tienes la respuesta directa."


def test_emit_events_serializes_tool_state(tmp_home: Path, monkeypatch) -> None:
    """`--emit-events` must serialize mid-tool `tool_state` to stdout — it is the
    daemon idle-timeout's sign-of-life for a long-running tool (e.g. a build)."""
    import json

    monkeypatch.setattr(_cli_mod, "_bootstrap", lambda _h: None)
    monkeypatch.setattr(
        "alpi.config.load",
        lambda _h: Config(home=tmp_home, model="stub", raw={}),
    )
    monkeypatch.setattr("alpi.engine.Engine.save_session", lambda self: None)
    monkeypatch.setattr("alpi.engine._maybe_load_mcps", lambda _cfg: [])
    monkeypatch.setattr("alpi.engine.Engine._build_system_prompt", lambda self: "stub")
    monkeypatch.setattr("alpi.ctx_window.resolve", lambda _h, _c, _m: 200_000)
    monkeypatch.setattr("alpi.ledger.check", lambda *a, **kw: None)
    monkeypatch.setattr("alpi.ledger.record", lambda *a, **kw: None)

    events = [
        AgentEvent(kind="tool_start", name="terminal", args={"command": "npm run build"}),
        AgentEvent(kind="tool_state", name="terminal", text="running… 15s"),
        AgentEvent(kind="tool_end", name="terminal", ok=True),
        AgentEvent(kind="assistant_done", text="build green", final=True),
    ]
    monkeypatch.setattr("alpi.engine.Engine.run_turn", _make_run_turn(events))

    buf = io.StringIO()
    monkeypatch.setattr(sys, "stdout", buf)
    _cli_mod._run_once(tmp_home, "build it", emit_events=True, persist=False)

    kinds = [
        json.loads(line)["kind"]
        for line in buf.getvalue().splitlines() if line.strip().startswith("{")
    ]
    assert "tool_state" in kinds
    assert kinds.index("tool_state") > kinds.index("tool_start")
