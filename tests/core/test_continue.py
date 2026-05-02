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
                  tools: list[dict] | None = None) -> None:
    sessions = home_ / "sessions"
    sessions.mkdir(parents=True, exist_ok=True)
    (sessions / f"{sid}.json").write_text(json.dumps({
        "id": sid,
        "model": "openrouter/xiaomi/mimo-v2-flash",
        "started_at": 1_700_000_000,
        "input_tokens": 500,
        "output_tokens": 300,
        "cost_usd": 0.0,
        "last_ctx_tokens": 1200,
        "turns": [
            {
                "at": 1_700_000_001,
                "user": user,
                "assistant": assistant,
                "tools": tools or [],
            }
        ],
    }))


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
