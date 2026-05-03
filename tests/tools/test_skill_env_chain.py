"""End-to-end env-passthrough chain.

This is the test that would have caught the bug where ``_create``
wrote ``requires_env: [VAR]`` to frontmatter but ``_view`` only
looked at the legacy ``env:`` field, breaking the subprocess
passthrough for every skill created with the new code path.

The chain:

  1. ``skill(action='create', requires_env=['TEST_TOKEN'])`` writes the
     frontmatter.
  2. The user / wizard populates ``TEST_TOKEN`` in profile env.
  3. ``skill(action='view', name='…')`` runs — should add ``TEST_TOKEN``
     to ``_state.get_active_skills_env()`` so terminal subprocesses see it.
  4. ``terminal._build_subprocess_env()`` returns a dict containing
     ``TEST_TOKEN``.

Each step asserted separately — when this regresses we want a precise
finger-pointing failure, not a vague "skill is broken".
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alpi.tools import _state
from alpi.tools.skill import Skill
from alpi.tools.terminal import _build_subprocess_env


@pytest.fixture
def isolated_home(tmp_home_no_env: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("ALPI_HOME", str(tmp_home_no_env))
    _state.reset_skill_env()
    return tmp_home_no_env


def test_view_registers_requires_env_for_subprocess(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TEST_TOKEN", "secret-value")
    Skill().run(
        action="create",
        name="env-passthrough",
        category="software",
        description="Passthrough chain probe",
        body="## When to use\nFor the env chain test.\n",
        requires_env=["TEST_TOKEN"],
    )

    # Step 3 — view registers the env passthrough.
    r = Skill().run(action="view", name="env-passthrough")
    assert r.ok, r.error
    assert "TEST_TOKEN" in _state.get_active_skills_env(), (
        "view did not register requires_env for subprocess passthrough — "
        "the bug we shipped in 0.3.11 (now fixed)."
    )

    # Step 4 — terminal's subprocess env reflects it.
    env = _build_subprocess_env()
    assert env.get("TEST_TOKEN") == "secret-value"


def test_view_falls_back_to_legacy_env_field(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Skills authored before ``requires_env`` shipped used ``env:`` in
    frontmatter. They must still work — _view reads both."""
    monkeypatch.setenv("LEGACY_VAR", "legacy-value")
    skill_dir = isolated_home / "skills" / "personal" / "legacy"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: legacy\n"
        "description: Pre-requires_env skill\n"
        "category: personal\n"
        "env: ['LEGACY_VAR']\n"
        "---\n"
        "## When to use\nFor compat.\n"
    )

    Skill().run(action="view", name="legacy")
    env = _build_subprocess_env()
    assert env.get("LEGACY_VAR") == "legacy-value"


def test_view_unions_requires_env_and_env(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A skill that has BOTH fields (e.g. mid-migration) gets both
    sets of vars passed through."""
    monkeypatch.setenv("NEW_VAR", "n")
    monkeypatch.setenv("OLD_VAR", "o")
    skill_dir = isolated_home / "skills" / "personal" / "mixed"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: mixed\n"
        "description: Has both fields during migration\n"
        "category: personal\n"
        "requires_env: ['NEW_VAR']\n"
        "env: ['OLD_VAR']\n"
        "---\n"
        "## When to use\nFor migration.\n"
    )

    Skill().run(action="view", name="mixed")
    env = _build_subprocess_env()
    assert env.get("NEW_VAR") == "n"
    assert env.get("OLD_VAR") == "o"


def test_view_does_not_leak_undeclared_vars(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A skill that declares only TOKEN_A must NOT cause TOKEN_B (set
    in the parent env but undeclared) to flow into the subprocess."""
    monkeypatch.setenv("TOKEN_A", "a")
    monkeypatch.setenv("TOKEN_B", "b")
    Skill().run(
        action="create",
        name="narrow-decl",
        category="software",
        description="Declares one var only",
        body="## When to use\n.\n",
        requires_env=["TOKEN_A"],
    )

    Skill().run(action="view", name="narrow-decl")
    env = _build_subprocess_env()
    assert env.get("TOKEN_A") == "a"
    assert "TOKEN_B" not in env


def test_skill_with_no_env_declarations_passes_no_vars(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RANDOM_VAR", "x")
    Skill().run(
        action="create",
        name="no-env",
        category="software",
        description="No env needed",
        body="## When to use\n.\n",
    )

    Skill().run(action="view", name="no-env")
    env = _build_subprocess_env()
    assert "RANDOM_VAR" not in env


def test_view_sub_file_does_not_register_env(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``view`` with ``file=`` arg returns a file from a subdir — not
    SKILL.md itself. Should NOT trigger env registration (the LLM is
    just reading a script, not committing to running the skill)."""
    monkeypatch.setenv("TOKEN_X", "x")
    Skill().run(
        action="create",
        name="subdir-view",
        category="software",
        description="Has subdir files",
        body="## When to use\n.\n",
        requires_env=["TOKEN_X"],
    )
    Skill().run(
        action="add_file",
        name="subdir-view",
        subdir="references",
        filename="notes.md",
        content="just a reference",
    )

    _state.reset_skill_env()
    Skill().run(action="view", name="subdir-view", file="references/notes.md")
    assert "TOKEN_X" not in _state.get_active_skills_env()
