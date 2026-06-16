"""Tests for `--continue` resume logic (no LLM needed)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from rich.console import Console

from alpi import config, home, memory
from alpi.cli import _continue_last_session
from alpi.engine import Engine


@pytest.fixture
def bootstrapped_home(tmp_home_no_env: Path) -> Path:
    home.ensure_home(tmp_home_no_env)
    config.seed_defaults(tmp_home_no_env)
    memory.MemoryStore(tmp_home_no_env).seed_defaults()
    (tmp_home_no_env / "personality.md").write_text("# Identity\nYou are alpi.\n")
    return tmp_home_no_env


def _save_session(home_: Path, sid: str, user: str, assistant: str,
                  tools: list[dict] | None = None,
                  output_attachments: list[dict] | None = None) -> None:
    sessions = home_ / "sessions"
    sessions.mkdir(parents=True, exist_ok=True)
    turn = {
        "at": 1_700_000_001,
        "user": user,
        "assistant": assistant,
        "tools": tools or [],
    }
    if output_attachments:
        turn["output_attachments"] = output_attachments
    (sessions / f"{sid}.json").write_text(json.dumps({
        "id": sid,
        "model": "openrouter/xiaomi/mimo-v2-flash",
        "started_at": 1_700_000_000,
        "input_tokens": 500,
        "output_tokens": 300,
        "cost_usd": 0.0,
        "last_ctx_tokens": 1200,
        "turns": [turn],
    }))


def _touch_session(home_: Path, sid: str, mtime: int) -> None:
    path = home_ / "sessions" / f"{sid}.json"
    import os
    os.utime(path, (mtime, mtime))


def test_no_sessions_returns_false(bootstrapped_home: Path) -> None:
    cfg = config.load(bootstrapped_home)
    engine = Engine(home=bootstrapped_home, cfg=cfg)
    assert _continue_last_session(engine, bootstrapped_home, Console()) is False


def test_resume_carries_context_and_adopts_id(bootstrapped_home: Path) -> None:
    _save_session(
        bootstrapped_home, "saved-123",
        user="mi color favorito es el turquesa",
        assistant="¡buena elección!",
    )

    cfg = config.load(bootstrapped_home)
    engine = Engine(home=bootstrapped_home, cfg=cfg)
    assert _continue_last_session(engine, bootstrapped_home, Console())
    assert engine.session.id == "saved-123"
    # User + assistant rebuilt as messages.
    assert any(
        "turquesa" in (m.get("content") or "")
        for m in engine.session.messages
    )
    assert any(
        "buena elección" in (m.get("content") or "")
        for m in engine.session.messages
    )
    # Resume note present so the model knows the history is prior context.
    assert any(
        "previous session" in (m.get("content") or "").lower()
        for m in engine.session.messages
    )
    # The turns log is also loaded onto the engine for later save().
    assert len(engine.session.turns) == 1
    assert engine.session.turns[0].user == "mi color favorito es el turquesa"


def test_resume_surfaces_produced_attachment_paths(bootstrapped_home: Path) -> None:
    _save_session(
        bootstrapped_home, "made-img",
        user="mejora esta imagen",
        assistant="Listo, ya mejoré la foto.",
        output_attachments=[{
            "name": "studio-enhanced.jpg", "mime": "image/jpeg",
            "path": "/tmp/out/studio-enhanced.jpg", "kind": "image",
        }],
    )
    cfg = config.load(bootstrapped_home)
    engine = Engine(home=bootstrapped_home, cfg=cfg)
    assert _continue_last_session(engine, bootstrapped_home, Console())
    joined = "\n".join(m.get("content") or "" for m in engine.session.messages)
    assert "/tmp/out/studio-enhanced.jpg" in joined


def test_resume_drops_tool_output_but_keeps_produced_path(bootstrapped_home: Path) -> None:
    _save_session(
        bootstrapped_home, "tooled",
        user="mejora esta imagen",
        assistant="Listo.",
        tools=[{"name": "skill", "args": {"name": "generate-image"},
                "result": "SECRET_TOOL_OUTPUT_42", "ok": True, "duration_s": 1.0}],
        output_attachments=[{
            "name": "x.jpg", "mime": "image/jpeg",
            "path": "/tmp/out/x.jpg", "kind": "image",
        }],
    )
    cfg = config.load(bootstrapped_home)
    engine = Engine(home=bootstrapped_home, cfg=cfg)
    assert _continue_last_session(engine, bootstrapped_home, Console())
    joined = "\n".join(m.get("content") or "" for m in engine.session.messages)
    assert "/tmp/out/x.jpg" in joined
    assert "SECRET_TOOL_OUTPUT_42" not in joined


def test_resume_once_continue_last_resumes_latest(bootstrapped_home: Path) -> None:
    from alpi.cli import _resume_once
    _save_session(bootstrapped_home, "prev-chat", user="my color is turquoise", assistant="ok")
    engine = Engine(home=bootstrapped_home, cfg=config.load(bootstrapped_home))
    _resume_once(engine, bootstrapped_home, continue_last=True)
    assert engine.session.id == "prev-chat"
    assert any("turquoise" in (m.get("content") or "") for m in engine.session.messages)


def test_resume_once_session_id_is_specific_not_latest(bootstrapped_home: Path) -> None:
    from alpi.cli import _resume_once
    _save_session(bootstrapped_home, "target", user="fact to remember", assistant="ok")
    _save_session(bootstrapped_home, "newer", user="something else", assistant="ok")
    _touch_session(bootstrapped_home, "target", 1_700_000_000)
    _touch_session(bootstrapped_home, "newer", 1_700_001_000)
    engine = Engine(home=bootstrapped_home, cfg=config.load(bootstrapped_home))
    _resume_once(engine, bootstrapped_home, session_id="target")
    assert engine.session.id == "target"
    assert any("fact to remember" in (m.get("content") or "") for m in engine.session.messages)


def test_resume_once_missing_session_id_raises(bootstrapped_home: Path) -> None:
    import click
    from alpi.cli import _resume_once
    engine = Engine(home=bootstrapped_home, cfg=config.load(bootstrapped_home))
    with pytest.raises(click.ClickException):
        _resume_once(engine, bootstrapped_home, session_id="no-such-session")


def test_resume_once_continue_last_is_best_effort(bootstrapped_home: Path) -> None:
    from alpi.cli import _resume_once
    engine = Engine(home=bootstrapped_home, cfg=config.load(bootstrapped_home))
    _resume_once(engine, bootstrapped_home, continue_last=True)
    assert engine.session.turns == []


def test_continue_specific_session_rejects_traversal(bootstrapped_home: Path) -> None:
    from alpi.cli import _continue_specific_session
    (bootstrapped_home / "sessions").mkdir(exist_ok=True)
    (bootstrapped_home / "secret.json").write_text(json.dumps({
        "id": "secret",
        "turns": [{"at": 1, "user": "leaked secret", "assistant": "x", "tools": []}],
    }))
    engine = Engine(home=bootstrapped_home, cfg=config.load(bootstrapped_home))
    assert _continue_specific_session(engine, bootstrapped_home, "../secret") is False
    assert not any("leaked" in (m.get("content") or "") for m in engine.session.messages)


def test_continue_skips_scheduled_sessions(bootstrapped_home: Path) -> None:
    _save_session(
        bootstrapped_home, "chat-123",
        user="normal chat",
        assistant="ok",
    )
    _save_session(
        bootstrapped_home, "scheduled-123",
        user="[SCHEDULED: running from cron]\n\nsend a joke",
        assistant="sent",
    )
    _touch_session(bootstrapped_home, "chat-123", 1_700_000_000)
    _touch_session(bootstrapped_home, "scheduled-123", 1_700_000_100)

    cfg = config.load(bootstrapped_home)
    engine = Engine(home=bootstrapped_home, cfg=cfg)
    assert _continue_last_session(engine, bootstrapped_home, Console())
    assert engine.session.id == "chat-123"


def test_save_after_resume_overwrites_same_file(bootstrapped_home: Path) -> None:
    _save_session(bootstrapped_home, "persist-me",
                  user="algo", assistant="vale")

    cfg = config.load(bootstrapped_home)
    engine = Engine(home=bootstrapped_home, cfg=cfg)
    _continue_last_session(engine, bootstrapped_home, Console())

    # Simulate a new turn completing in this resumed session.
    engine.session.log_turn(
        user="nuevo turno", assistant="ok",
        tools=[], started_at=1_700_000_100,
    )
    engine.save_session()

    files = list((bootstrapped_home / "sessions").glob("*.json"))
    assert len(files) == 1
    assert files[0].stem == "persist-me"
    data = json.loads(files[0].read_text())
    users = [t["user"] for t in data["turns"]]
    assert "algo" in users
    assert "nuevo turno" in users


def test_empty_session_not_saved(bootstrapped_home: Path) -> None:
    cfg = config.load(bootstrapped_home)
    engine = Engine(home=bootstrapped_home, cfg=cfg)
    # No turns logged — save() should no-op.
    assert engine.save_session() is None
    assert not list((bootstrapped_home / "sessions").glob("*.json"))


def test_tool_log_serialization_roundtrip(bootstrapped_home: Path) -> None:
    _save_session(
        bootstrapped_home, "with-tools",
        user="busca algo",
        assistant="aquí tienes",
        tools=[
            {"at": 1_700_000_002, "name": "web_search",
             "args": {"query": "algo"},
             "result": "12 results", "ok": True, "duration_s": 1.2},
        ],
    )
    cfg = config.load(bootstrapped_home)
    engine = Engine(home=bootstrapped_home, cfg=cfg)
    assert _continue_last_session(engine, bootstrapped_home, Console())
    turn = engine.session.turns[0]
    assert len(turn.tools) == 1
    tl = turn.tools[0]
    assert tl.name == "web_search"
    assert tl.args == {"query": "algo"}
    assert tl.ok is True
    assert tl.duration_s == 1.2
