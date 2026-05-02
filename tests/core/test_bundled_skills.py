"""Bundled skills infrastructure (BE).

`@alpi/*` namespace resolves against the ``alpi.skills`` package
resources. User skills stay under ``{home}/skills/``. Bundled skills
are read-only — any mutating action on a ``@alpi/*`` name is rejected.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alpi.tools import skill as skill_mod
from alpi.tools.skill import Skill


@pytest.fixture
def isolated_home(tmp_home_no_env: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("ALPI_HOME", str(tmp_home_no_env))
    (tmp_home_no_env / "skills").mkdir(parents=True, exist_ok=True)
    return tmp_home_no_env


@pytest.fixture
def fake_bundled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "bundled_skills"
    root.mkdir()
    skill = root / "demo"
    skill.mkdir()
    (skill / "SKILL.md").write_text(
        "---\n"
        "name: demo\n"
        "description: a demo bundled skill for tests\n"
        "category: miscellaneous\n"
        "---\n"
        "# Demo\n"
        "This is a bundled skill used in tests.\n"
    )
    monkeypatch.setattr(skill_mod, "_bundled_root", lambda: root)
    return root


# List / index


def test_list_includes_bundled(isolated_home: Path, fake_bundled: Path) -> None:
    r = Skill().run(action="list")
    assert r.ok, r.error
    assert "@alpi/ [bundled]" in r.output
    assert "@alpi/demo" in r.output


def test_list_without_bundled_shows_only_user(
        isolated_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(skill_mod, "_bundled_root", lambda: None)
    r = Skill().run(action="list")
    assert r.ok
    assert "@alpi" not in r.output


def test_index_block_marks_bundled(isolated_home: Path, fake_bundled: Path) -> None:
    block = skill_mod.skills_index_block(isolated_home)
    assert "[bundled]" in block
    assert "@alpi/demo" in block
    assert "a demo bundled skill" in block


def test_index_block_user_first_bundled_after(
        isolated_home: Path, fake_bundled: Path) -> None:
    """User skills should appear before bundled skills."""
    Skill().run(
        action="create", name="my-user-skill", category="personal",
        description="my own", body="# my\nsomething",
    )
    block = skill_mod.skills_index_block(isolated_home)
    user_pos = block.find("my-user-skill")
    bundled_pos = block.find("@alpi/demo")
    assert user_pos != -1 and bundled_pos != -1
    assert user_pos < bundled_pos


# View


def test_view_bundled_skill(isolated_home: Path, fake_bundled: Path) -> None:
    r = Skill().run(action="view", name="@alpi/demo")
    assert r.ok, r.error
    assert "# Demo" in r.output
    assert "This is a bundled skill" in r.output


def test_view_unknown_bundled(isolated_home: Path, fake_bundled: Path) -> None:
    r = Skill().run(action="view", name="@alpi/nonexistent")
    assert not r.ok
    assert "not found" in (r.error or "").lower()


# Mutation guards — bundled skills are read-only


def test_create_with_bundled_prefix_rejected(
        isolated_home: Path, fake_bundled: Path) -> None:
    r = Skill().run(
        action="create", name="@alpi/new-one", category="personal",
        description="try to poison the namespace", body="# nope",
    )
    assert not r.ok
    assert "bundled" in (r.error or "").lower()
    assert "read-only" in (r.error or "").lower()


def test_edit_bundled_rejected(isolated_home: Path, fake_bundled: Path) -> None:
    r = Skill().run(action="edit", name="@alpi/demo", body="# overridden")
    assert not r.ok
    assert "bundled" in (r.error or "").lower()


def test_delete_bundled_rejected(isolated_home: Path, fake_bundled: Path) -> None:
    r = Skill().run(action="delete", name="@alpi/demo")
    assert not r.ok
    assert "bundled" in (r.error or "").lower()


def test_patch_bundled_rejected(isolated_home: Path, fake_bundled: Path) -> None:
    r = Skill().run(
        action="patch", name="@alpi/demo",
        subdir="scripts", filename="run.py",
        old_string="a", new_string="b",
    )
    assert not r.ok
    assert "bundled" in (r.error or "").lower()


def test_add_file_bundled_rejected(isolated_home: Path, fake_bundled: Path) -> None:
    r = Skill().run(
        action="add_file", name="@alpi/demo",
        subdir="references", filename="new.md", content="# new",
    )
    assert not r.ok
    assert "bundled" in (r.error or "").lower()


def test_remove_file_bundled_rejected(isolated_home: Path, fake_bundled: Path) -> None:
    r = Skill().run(
        action="remove_file", name="@alpi/demo",
        subdir="scripts", filename="run.py",
    )
    assert not r.ok
    assert "bundled" in (r.error or "").lower()


# Disk-level @ prefix is ignored


def test_user_skill_under_at_prefix_dir_is_invisible(
        isolated_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Defense in depth: if someone manually writes a skill to
    `{home}/skills/@alpi/foo/SKILL.md`, it is ignored by the listing
    so it cannot shadow bundled skills."""
    monkeypatch.setattr(skill_mod, "_bundled_root", lambda: None)
    rogue = isolated_home / "skills" / "@alpi" / "rogue"
    rogue.mkdir(parents=True)
    (rogue / "SKILL.md").write_text(
        "---\nname: rogue\ndescription: sneaky\ncategory: miscellaneous\n---\n# rogue\n",
    )
    r = Skill().run(action="list")
    assert "rogue" not in r.output


# User skill creation under normal categories still works


def test_create_user_skill_normal_category(isolated_home: Path) -> None:
    r = Skill().run(
        action="create", name="write-daily", category="personal",
        description="write a daily note", body="# daily\nroutine steps",
    )
    assert r.ok, r.error
    assert (isolated_home / "skills" / "personal" / "write-daily" / "SKILL.md").is_file()
