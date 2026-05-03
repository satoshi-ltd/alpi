"""``skill(action='reset_state')`` and per-turn keyword boost.

Two unrelated additions tested together because both touch the
``Skill`` tool surface and a single fixture set covers them.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alpi.tools.skill import (
    Skill,
    bundled_skills,
    keyword_match_hint,
    skill_keywords,
)


@pytest.fixture
def isolated_home(tmp_home_no_env: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("ALPI_HOME", str(tmp_home_no_env))
    return tmp_home_no_env


# reset_state

def test_reset_state_removes_files_under_state(isolated_home: Path) -> None:
    Skill().run(
        action="create",
        name="reset-target",
        category="software",
        description="State target",
        body="## When to use\nN/A.\n",
    )
    state = isolated_home / "skills" / "software" / "reset-target" / "state"
    state.mkdir(parents=True, exist_ok=True)
    (state / "db.sqlite").write_text("fake")
    (state / "history.jsonl").write_text("{}\n")
    (state / "subdir").mkdir()
    (state / "subdir" / "x").write_text("y")

    r = Skill().run(action="reset_state", name="reset-target", confirm_user_skill=True)
    assert r.ok, r.error
    assert "removed 3" in r.output
    # State dir itself is preserved.
    assert state.exists()
    assert list(state.iterdir()) == []


def test_reset_state_handles_missing_dir(isolated_home: Path) -> None:
    Skill().run(
        action="create",
        name="never-stateful",
        category="software",
        description="No state dir",
        body="## When to use\nN/A.\n",
    )
    r = Skill().run(action="reset_state", name="never-stateful", confirm_user_skill=True)
    assert r.ok, r.error
    assert "no state to reset" in r.output


def test_reset_state_unknown_skill(isolated_home: Path) -> None:
    r = Skill().run(action="reset_state", name="nope", confirm_user_skill=True)
    assert not r.ok
    assert "skill not found" in r.error


def test_reset_state_rejects_bundled(isolated_home: Path) -> None:
    if not bundled_skills():
        pytest.skip("no bundled skills available")
    name = bundled_skills()[0]["name"]
    r = Skill().run(action="reset_state", name=name)
    assert not r.ok
    assert "bundled" in r.error


def test_reset_state_user_origin_requires_confirmation(
    isolated_home: Path,
) -> None:
    skill_dir = isolated_home / "skills" / "personal" / "manual"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: manual\n"
        "description: Hand-written\n"
        "category: personal\n"
        "origin: user\n"
        "---\n"
    )
    (skill_dir / "state").mkdir()
    (skill_dir / "state" / "x").write_text("data")
    r = Skill().run(action="reset_state", name="manual")
    assert not r.ok
    assert "confirm_user_skill" in r.error


# keyword_match_hint + skill_keywords parsing

def test_keywords_lowercased_and_parsed(isolated_home: Path) -> None:
    r = Skill().run(
        action="create",
        name="keyword-skill",
        category="personal",
        description="Has keywords",
        body="## When to use\nFor workout tracking.\n",
        keywords=["Whoop", "Workout", "fitness"],
    )
    assert r.ok, r.error
    md = (isolated_home / "skills" / "personal" / "keyword-skill" / "SKILL.md").read_text()
    assert "keywords: ['whoop', 'workout', 'fitness']" in md


def test_skill_keywords_parses_frontmatter() -> None:
    meta = {"keywords": "['whoop', 'fitness']"}
    assert skill_keywords(meta) == ["whoop", "fitness"]


def test_skill_keywords_empty_when_unset() -> None:
    assert skill_keywords({}) == []


# keyword_match_hint integration

def test_hint_returns_empty_when_user_text_blank(isolated_home: Path) -> None:
    Skill().run(
        action="create",
        name="x",
        category="personal",
        description="x",
        body="## When to use\nN/A.\n",
        keywords=["whoop"],
    )
    assert keyword_match_hint(isolated_home, "") == ""
    assert keyword_match_hint(isolated_home, "   ") == ""


def test_hint_fires_when_user_text_contains_keyword(isolated_home: Path) -> None:
    Skill().run(
        action="create",
        name="whoop-tracker",
        category="personal",
        description="Tracks Whoop workouts",
        body="## When to use\nFor workouts.\n",
        keywords=["whoop", "workout"],
    )
    hint = keyword_match_hint(isolated_home, "log my workout from yesterday")
    assert "whoop-tracker" in hint
    assert "SKILL HINT" in hint


def test_hint_silent_when_no_keyword_matches(isolated_home: Path) -> None:
    Skill().run(
        action="create",
        name="whoop-tracker",
        category="personal",
        description="Tracks Whoop workouts",
        body="## When to use\nFor workouts.\n",
        keywords=["whoop", "fitness"],
    )
    assert keyword_match_hint(isolated_home, "what's the weather today") == ""


def test_hint_skips_inactive_skill(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("WHOOP_TOKEN", raising=False)
    Skill().run(
        action="create",
        name="whoop-tracker",
        category="personal",
        description="Tracks Whoop workouts",
        body="## When to use\nFor workouts.\n",
        keywords=["whoop"],
        requires_env=["WHOOP_TOKEN"],
    )
    hint = keyword_match_hint(isolated_home, "log my whoop workout")
    # Skill is inactive (env var missing) — should not be boosted.
    assert "whoop-tracker" not in hint


def test_hint_lists_multiple_matches(isolated_home: Path) -> None:
    Skill().run(
        action="create",
        name="skill-a",
        category="personal",
        description="A",
        body="## When to use\n.\n",
        keywords=["foo"],
    )
    Skill().run(
        action="create",
        name="skill-b",
        category="personal",
        description="B",
        body="## When to use\n.\n",
        keywords=["bar"],
    )
    hint = keyword_match_hint(isolated_home, "I want foo and bar today")
    assert "skill-a" in hint
    assert "skill-b" in hint


def test_hint_case_insensitive_in_user_text(isolated_home: Path) -> None:
    Skill().run(
        action="create",
        name="case-skill",
        category="personal",
        description="C",
        body="## When to use\n.\n",
        keywords=["whoop"],
    )
    assert "case-skill" in keyword_match_hint(isolated_home, "WHOOP today")
    assert "case-skill" in keyword_match_hint(isolated_home, "Whoop today")


def test_hint_matches_hyphenated_keyword(isolated_home: Path) -> None:
    Skill().run(
        action="create",
        name="deep-researcher",
        category="research",
        description="Research assistant",
        body="## When to use\nFor research.\n",
        keywords=["deep-research"],
    )
    assert "deep-researcher" in keyword_match_hint(
        isolated_home, "start a deep-research pass"
    )


def test_create_with_no_keywords_writes_empty_list(isolated_home: Path) -> None:
    r = Skill().run(
        action="create",
        name="no-keywords",
        category="personal",
        description="No keywords declared",
        body="## When to use\n.\n",
    )
    assert r.ok, r.error
    md = (isolated_home / "skills" / "personal" / "no-keywords" / "SKILL.md").read_text()
    assert "keywords: []" in md
