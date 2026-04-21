"""Tests for `Engine.reset_session` — backs the `/new` slash command."""

from __future__ import annotations

from pathlib import Path

import pytest

from alpi import config, home, memory
from alpi.engine import Engine


@pytest.fixture
def bootstrapped_home(tmp_home_no_env: Path) -> Path:
    home.ensure_home(tmp_home_no_env)
    config.seed_defaults(tmp_home_no_env)
    memory.MemoryStore(tmp_home_no_env).seed_defaults()
    (tmp_home_no_env / "PERSONALITY.md").write_text("# Identity\nYou are alf.\n")
    return tmp_home_no_env


def test_reset_session_assigns_fresh_id(bootstrapped_home: Path) -> None:
    cfg = config.load(bootstrapped_home)
    engine = Engine(home=bootstrapped_home, cfg=cfg)
    old_id = engine.session.id
    engine.session.messages.append({"role": "user", "content": "hi"})
    engine.session.messages.append({"role": "assistant", "content": "hello"})

    engine.reset_session()

    assert engine.session.id != old_id


def test_reset_session_preserves_system_prompt_and_drops_rest(
        bootstrapped_home: Path) -> None:
    cfg = config.load(bootstrapped_home)
    engine = Engine(home=bootstrapped_home, cfg=cfg)
    engine.session.messages.append({"role": "user", "content": "first"})
    engine.session.messages.append({"role": "assistant", "content": "hi back"})

    engine.reset_session()

    roles = [m.get("role") for m in engine.session.messages]
    assert roles == ["system"]
    assert engine.session.messages[0]["content"] == engine._system_prompt


def test_reset_session_clears_interrupt_flag(bootstrapped_home: Path) -> None:
    cfg = config.load(bootstrapped_home)
    engine = Engine(home=bootstrapped_home, cfg=cfg)
    engine.request_interrupt()
    assert engine.interrupt_requested

    engine.reset_session()

    assert engine.interrupt_requested is False
