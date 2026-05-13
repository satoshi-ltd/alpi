"""Conditional activation: ``skill_eligibility`` + the gate in
``skills_index_block``. The agent must never see a skill it can't
run; ``skill(action='list')`` must surface the same skill with the
reason it's hidden.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alpi.tools.skill import (
    Skill,
    skill_eligibility,
    skill_requirements,
    skills_index_block,
)


@pytest.fixture
def isolated_home(tmp_home_no_env: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("ALPI_HOME", str(tmp_home_no_env))
    return tmp_home_no_env


# skill_requirements

def test_requirements_empty_when_no_keys() -> None:
    assert skill_requirements({}) == {
        "env": [], "bins": [], "config": [], "platforms": [],
    }


def test_requirements_parses_env_list() -> None:
    meta = {"requires_env": "['FOO', 'BAR']"}
    assert skill_requirements(meta)["env"] == ["FOO", "BAR"]


def test_requirements_filters_bad_env_var_names() -> None:
    meta = {"requires_env": "['FOO', 'with space', 'OK_VAR']"}
    assert skill_requirements(meta)["env"] == ["FOO", "OK_VAR"]


# skill_eligibility — pure

def test_eligible_when_no_requirements() -> None:
    ok, missing = skill_eligibility({}, env={})
    assert ok and missing == []


def test_missing_env_var_blocks() -> None:
    ok, missing = skill_eligibility({"requires_env": "['TOKEN']"}, env={})
    assert not ok
    assert missing == ["env var TOKEN"]


def test_empty_env_value_counts_as_missing() -> None:
    ok, missing = skill_eligibility(
        {"requires_env": "['TOKEN']"}, env={"TOKEN": ""},
    )
    assert not ok and "env var TOKEN" in missing


def test_multiple_misses_reported_together() -> None:
    ok, missing = skill_eligibility(
        {"requires_env": "['A', 'B', 'C']"}, env={"A": "set"},
    )
    assert not ok
    assert missing == ["env var B", "env var C"]


def test_eligible_when_all_satisfied() -> None:
    ok, missing = skill_eligibility(
        {"requires_env": "['TOKEN']"}, env={"TOKEN": "abc"},
    )
    assert ok and missing == []


# Integration: skills_index_block must hide ineligible skills

def test_index_block_hides_skill_with_unmet_env(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("REQUIRED_VAR", raising=False)
    r = Skill().run(
        action="create",
        name="needs-token",
        category="software",
        description="Needs an env var",
        body="## When to use\nWhen the var is set.\n",
        requires_env=["REQUIRED_VAR"],
    )
    assert r.ok, r.error
    block = skills_index_block(isolated_home)
    assert "needs-token" not in block


def test_index_block_shows_skill_when_env_present(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REQUIRED_VAR", "value")
    r = Skill().run(
        action="create",
        name="needs-token",
        category="software",
        description="Needs an env var",
        body="## When to use\nWhen the var is set.\n",
        requires_env=["REQUIRED_VAR"],
    )
    assert r.ok, r.error
    block = skills_index_block(isolated_home)
    assert "needs-token" in block


def test_list_shows_inactive_with_reason(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MISSING_VAR", raising=False)
    Skill().run(
        action="create",
        name="needs-x",
        category="software",
        description="Needs MISSING_VAR",
        body="## When to use\nN/A in tests.\n",
        requires_env=["MISSING_VAR"],
    )
    r = Skill().run(action="list")
    assert r.ok, r.error
    assert "needs-x" in r.output
    assert "[inactive: missing env var MISSING_VAR]" in r.output


def test_list_shows_invalid_manifest_with_field_summary(
    isolated_home: Path,
) -> None:
    """A skill whose frontmatter fails the schema must surface the
    failure in ``list`` so the user can spot it without running
    ``validate`` on every skill."""
    skill_dir = isolated_home / "skills" / "personal" / "broken-name"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: BadName\n"
        "description: Has a CamelCase name\n"
        "category: personal\n"
        "---\n"
        "## When to use\nN/A.\n"
    )
    r = Skill().run(action="list")
    assert r.ok, r.error
    assert "broken-name" in r.output
    assert "[invalid:" in r.output
    assert "name" in r.output


def test_list_active_skill_has_no_tag(isolated_home: Path) -> None:
    Skill().run(
        action="create",
        name="happy",
        category="personal",
        description="Active and well",
        body="## When to use\n.\n",
    )
    r = Skill().run(action="list")
    assert r.ok, r.error
    # The line should NOT have either tag.
    line = next(l for l in r.output.splitlines() if "happy" in l)
    assert "[invalid" not in line
    assert "[inactive" not in line


def test_eligible_skill_appears_alongside_ineligible_in_index(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HAVE", "yes")
    monkeypatch.delenv("DONT_HAVE", raising=False)
    Skill().run(
        action="create",
        name="works",
        category="software",
        description="Has its env var",
        body="## When to use\nFirst.\n",
        requires_env=["HAVE"],
    )
    Skill().run(
        action="create",
        name="broken",
        category="software",
        description="Lacks its env var",
        body="## When to use\nSecond.\n",
        requires_env=["DONT_HAVE"],
    )
    block = skills_index_block(isolated_home)
    assert "works" in block
    assert "broken" not in block
