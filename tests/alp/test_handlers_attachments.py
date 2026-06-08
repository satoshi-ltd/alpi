from __future__ import annotations

from pathlib import Path

import pytest

from alpi import config, home, memory
from alpi.alp import handlers
from alpi.engine import AgentEvent


@pytest.fixture
def bootstrapped_home(tmp_home_no_env: Path) -> Path:
    home.ensure_home(tmp_home_no_env)
    config.seed_defaults(tmp_home_no_env)
    memory.MemoryStore(tmp_home_no_env).seed_defaults()
    return tmp_home_no_env


def test_alp_reply_carries_attachment_listing_even_without_text(bootstrapped_home, monkeypatch):
    def fake_run_turn(self, prompt, emit, **_kw):
        emit(AgentEvent(
            kind="assistant_done", text="", final=True,
            attachments=[{"mime": "image/jpeg", "name": "hero.jpg", "path": "/p/out/hero.jpg"}],
        ))
    monkeypatch.setattr(handlers.Engine, "run_turn", fake_run_turn)

    result = handlers._run_turn(bootstrapped_home, "make a hero", "peer-x", handlers._ActiveTurn())
    assert "Attachments:" in result["text"]
    assert "hero.jpg" in result["text"] and "/p/out/hero.jpg" in result["text"]
