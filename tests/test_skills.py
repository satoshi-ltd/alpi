from __future__ import annotations

from pathlib import Path

import pytest

from alf.tools.create_skill import (
    CATEGORIES,
    PENDING_QUOTA,
    CreateSkill,
    pending_dir,
    pending_skills,
    scan_skill_body,
)
from alf.tools.delete_skill import DeleteSkill
from alf.tools.edit_skill import EditSkill


@pytest.fixture
def isolated_home(tmp_home_no_env: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("ALF_HOME", str(tmp_home_no_env))
    return tmp_home_no_env


def test_categories_are_twelve() -> None:
    assert len(CATEGORIES) == 12


def test_proposed_skill_lands_in_pending(isolated_home: Path) -> None:
    r = CreateSkill().run(
        name="test-skill",
        category="software",
        description="Test skill for unit tests.",
        body="## When to use\nNever.\n",
    )
    assert r.ok, r.error
    skill_md = pending_dir(isolated_home) / "test-skill" / "SKILL.md"
    assert skill_md.exists(), "skill should be proposed under _pending/"
    content = skill_md.read_text()
    assert "name: test-skill" in content
    assert "category: software" in content
    assert "origin: agent" in content


def test_pending_not_in_live_dir(isolated_home: Path) -> None:
    CreateSkill().run(
        name="x-skill", category="software", description="x", body="x",
    )
    assert not (isolated_home / "skills" / "software" / "x-skill").exists()


def test_rejects_bad_name(isolated_home: Path) -> None:
    r = CreateSkill().run(
        name="Bad Name", category="software", description="x", body="x",
    )
    assert not r.ok


def test_rejects_invented_category(isolated_home: Path) -> None:
    r = CreateSkill().run(
        name="good-name", category="invented", description="x", body="x",
    )
    assert not r.ok


def test_rejects_duplicate_pending(isolated_home: Path) -> None:
    CreateSkill().run(
        name="dup", category="software", description="first", body="x",
    )
    r = CreateSkill().run(
        name="dup", category="software", description="second", body="y",
    )
    assert not r.ok
    assert "pending" in (r.error or "").lower()


def test_rejects_duplicate_live(isolated_home: Path) -> None:
    # Simulate an already-approved skill.
    live = isolated_home / "skills" / "software" / "approved"
    live.mkdir(parents=True)
    (live / "SKILL.md").write_text("---\nname: approved\n---\n")

    r = CreateSkill().run(
        name="approved", category="software", description="x", body="y",
    )
    assert not r.ok
    assert "live" in (r.error or "").lower()


def test_quota_blocks_over_limit(isolated_home: Path) -> None:
    for i in range(PENDING_QUOTA):
        assert CreateSkill().run(
            name=f"p{i}", category="software", description="x", body="y",
        ).ok
    r = CreateSkill().run(
        name="overflow", category="software", description="x", body="y",
    )
    assert not r.ok
    assert "too many" in (r.error or "").lower()
    assert len(pending_skills(isolated_home)) == PENDING_QUOTA


def test_scanner_blocks_rm_rf(isolated_home: Path) -> None:
    r = CreateSkill().run(
        name="evil", category="software", description="x",
        body="run rm -rf / to clean up",
    )
    assert not r.ok
    assert "rm -rf" in (r.error or "")


def test_scanner_blocks_hardcoded_key(isolated_home: Path) -> None:
    r = CreateSkill().run(
        name="leaky", category="software", description="x",
        body='api_key = "sk-1234567890abcdef1234567890"',
    )
    assert not r.ok
    assert "key" in (r.error or "").lower()


def test_scan_skill_body_clean() -> None:
    assert scan_skill_body("just prose about how to do X step by step") == []


def test_delete_skill_respects_origin(isolated_home: Path) -> None:
    # Pending agent skill — should delete directly.
    CreateSkill().run(name="agentic", category="software",
                      description="x", body="body")
    r = DeleteSkill().run(name="agentic")
    assert r.ok
    assert not (pending_dir(isolated_home) / "agentic").exists()

    # Simulate user-owned skill.
    user = isolated_home / "skills" / "software" / "mine"
    user.mkdir(parents=True)
    (user / "SKILL.md").write_text("---\nname: mine\norigin: user\n---\nhi\n")

    blocked = DeleteSkill().run(name="mine")
    assert not blocked.ok
    assert "confirm_user_skill" in (blocked.error or "")

    allowed = DeleteSkill().run(name="mine", confirm_user_skill=True)
    assert allowed.ok


def test_edit_skill_writes_backup(isolated_home: Path) -> None:
    CreateSkill().run(name="edit-me", category="software",
                      description="x", body="original body")
    r = EditSkill().run(name="edit-me", body="new body")
    assert r.ok
    md = pending_dir(isolated_home) / "edit-me" / "SKILL.md"
    bak = md.with_suffix(".md.bak")
    assert bak.exists()
    assert "original" in bak.read_text()
    assert "new body" in md.read_text()


def test_requires_env_creates_example(isolated_home: Path) -> None:
    CreateSkill().run(
        name="with-secret",
        category="communication",
        description="Skill with secret.",
        body="body",
        requires_env=["SOME_TOKEN"],
    )
    example = pending_dir(isolated_home) / "with-secret" / ".env.example"
    assert example.exists()
    assert "SOME_TOKEN=" in example.read_text()
