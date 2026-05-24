"""Guards on the Skills section of the loaded system prompt.

These three rules are load-bearing for skill-library quality. If a
refactor of `_build_system_prompt` or an edit to `system_prompt.md`
drops them, the LLM's behaviour around skill creation/maintenance
silently regresses. The unit test catches that.
"""

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
    return tmp_home_no_env


def test_system_prompt_carries_skill_quality_rules(
        bootstrapped_home: Path) -> None:
    cfg = config.load(bootstrapped_home)
    engine = Engine(home=bootstrapped_home, cfg=cfg)
    prompt = engine._system_prompt

    # Rule 1: user frustration is a skill signal, not just memory.
    assert "User frustration about a class of behaviour" in prompt

    # Rule 2: umbrella-class skills over narrow siblings.
    assert "Prefer umbrella-class skills over narrow siblings" in prompt

    # Rule 3: patch outdated skills proactively, don't wait to be asked.
    assert "Patch outdated skills proactively" in prompt


def test_system_prompt_carries_alpi_knowledge_rule(
        bootstrapped_home: Path) -> None:
    """A regression that drops the alpi_knowledge rule would let the agent answer alpi questions from training data — which predates alpi entirely."""
    cfg = config.load(bootstrapped_home)
    engine = Engine(home=bootstrapped_home, cfg=cfg)
    prompt = engine._system_prompt

    assert "ALPI SELF-KNOWLEDGE" in prompt
    assert "alpi_knowledge" in prompt
