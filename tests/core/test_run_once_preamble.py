"""`_run_once` writes only the terminal assistant reply to stdout — preamble emitted before tool calls is discarded."""

from __future__ import annotations

import io
import sys
from pathlib import Path

from alpi import cli as _cli_mod
from alpi.config import Config
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
        AgentEvent(kind="tool_end", name="peer", ok=False, transient=True),
        AgentEvent(kind="assistant_done", text="build green", final=True),
    ]
    monkeypatch.setattr("alpi.engine.Engine.run_turn", _make_run_turn(events))

    buf = io.StringIO()
    monkeypatch.setattr(sys, "stdout", buf)
    _cli_mod._run_once(tmp_home, "build it", emit_events=True, persist=False)

    payloads = [
        json.loads(line)
        for line in buf.getvalue().splitlines() if line.strip().startswith("{")
    ]
    kinds = [payload["kind"] for payload in payloads]
    assert "tool_state" in kinds
    assert kinds.index("tool_state") > kinds.index("tool_start")
    peer_end = next(payload for payload in payloads if payload.get("name") == "peer")
    assert peer_end["transient"] is True


def test_workgroup_dispatch_does_not_parse_internal_peer_mentions(
    tmp_home: Path, monkeypatch,
) -> None:
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
    monkeypatch.setenv("ALPI_WORKGROUP_DISPATCH", "wg_1")

    def unexpected_parse(*args, **kwargs):
        raise AssertionError("internal dispatch prompts are not direct mentions")

    monkeypatch.setattr("alpi.alp.mention.parse", unexpected_parse)
    monkeypatch.setattr(
        "alpi.engine.Engine.run_turn",
        _make_run_turn([
            AgentEvent(kind="assistant_done", text="workgroup handled", final=True),
        ]),
    )

    buf = io.StringIO()
    monkeypatch.setattr(sys, "stdout", buf)
    _cli_mod._run_once(
        tmp_home, "internal example @bob", emit_events=False, persist=False,
    )

    assert buf.getvalue().strip() == "workgroup handled"


def test_direct_mention_emits_transient_peer_failure(
    tmp_home: Path, monkeypatch,
) -> None:
    import json

    from alpi.alp.mention import Mention, Result

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
    monkeypatch.delenv("ALPI_WORKGROUP_DISPATCH", raising=False)
    monkeypatch.setattr(
        "alpi.alp.mention.parse", lambda *a, **k: Mention("bob", "ping"),
    )

    async def fake_execute(*args, **kwargs):
        return Result(
            ok=False, error="-32007 target-busy", transient=True,
        )

    monkeypatch.setattr("alpi.alp.mention.execute", fake_execute)

    buf = io.StringIO()
    monkeypatch.setattr(sys, "stdout", buf)
    _cli_mod._run_once(
        tmp_home, "@bob ping", emit_events=True, persist=False,
    )

    events = [json.loads(line) for line in buf.getvalue().splitlines()]
    peer_end = next(
        event for event in events
        if event.get("kind") == "tool_end" and event.get("name") == "peer"
    )
    assert peer_end["transient"] is True


def test_emit_events_identifies_accepted_workgroup_post(
    tmp_home: Path, monkeypatch,
) -> None:
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
    monkeypatch.setattr(
        "alpi.engine.Engine.run_turn",
        _make_run_turn([
            AgentEvent(
                kind="tool_end", name="workgroup_post", ok=True,
                args={"wg_id": "wg_target", "text": "delivery"},
            ),
            AgentEvent(kind="assistant_done", text="done", final=True),
        ]),
    )

    buf = io.StringIO()
    monkeypatch.setattr(sys, "stdout", buf)
    _cli_mod._run_once(tmp_home, "deliver", emit_events=True, persist=False)

    events = [
        json.loads(line) for line in buf.getvalue().splitlines()
        if line.strip().startswith("{")
    ]
    post = next(event for event in events if event.get("name") == "workgroup_post")
    assert post == {
        "kind": "tool_end", "name": "workgroup_post", "ok": True,
        "wg_id": "wg_target",
    }


def test_emit_events_coalesces_model_progress_without_content(tmp_home: Path, monkeypatch) -> None:
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
        AgentEvent(kind="reasoning_delta", text="private reasoning"),
        AgentEvent(kind="assistant_delta", text="partial answer"),
        AgentEvent(kind="model_state"),
        AgentEvent(kind="assistant_done", text="done", final=True),
    ]
    monkeypatch.setattr("alpi.engine.Engine.run_turn", _make_run_turn(events))

    buf = io.StringIO()
    monkeypatch.setattr(sys, "stdout", buf)
    _cli_mod._run_once(tmp_home, "work", emit_events=True, persist=False)

    payloads = [json.loads(line) for line in buf.getvalue().splitlines()]
    assert [p for p in payloads if p["kind"] == "model_state"] == [
        {"kind": "model_state"},
    ]
    assert "private reasoning" not in buf.getvalue()
    assert "partial answer" not in buf.getvalue()


def test_run_once_prints_attachment_listing_without_text(tmp_home: Path, monkeypatch) -> None:
    """An attachment-only final event still prints the textual listing (MM.2)."""
    monkeypatch.setattr(_cli_mod, "_bootstrap", lambda _h: None)
    monkeypatch.setattr("alpi.config.load", lambda _h: Config(home=tmp_home, model="stub", raw={}))
    monkeypatch.setattr("alpi.engine.Engine.save_session", lambda self: None)
    monkeypatch.setattr("alpi.engine._maybe_load_mcps", lambda _cfg: [])
    monkeypatch.setattr("alpi.engine.Engine._build_system_prompt", lambda self: "stub")
    monkeypatch.setattr("alpi.ctx_window.resolve", lambda _h, _c, _m: 200_000)
    monkeypatch.setattr("alpi.ledger.check", lambda *a, **kw: None)
    monkeypatch.setattr("alpi.ledger.record", lambda *a, **kw: None)

    events = [AgentEvent(
        kind="assistant_done", text="", final=True,
        attachments=[{"mime": "image/jpeg", "name": "hero.jpg", "path": "/p/out/hero.jpg"}],
    )]
    monkeypatch.setattr("alpi.engine.Engine.run_turn", _make_run_turn(events))

    buf = io.StringIO()
    monkeypatch.setattr(sys, "stdout", buf)
    _cli_mod._run_once(tmp_home, "make a hero", emit_events=False, persist=False)

    output = buf.getvalue().strip()
    assert output.startswith("Attachments:")
    assert "image/jpeg hero.jpg /p/out/hero.jpg" in output
