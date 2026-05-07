"""AT — auto-archive on delete + ``pinned`` frontmatter flag.

Skills are agent work product; destructive deletion was a foot-gun.
``delete`` now archives to ``skills/.archive/<category>/<name>__<UTC>/``
(recoverable via ``mv``). ``pinned: True`` in frontmatter blocks the
archive transition entirely until the user unpins.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alpi.tools.skill import Skill, all_skills


@pytest.fixture
def isolated_home(tmp_home_no_env: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("ALPI_HOME", str(tmp_home_no_env))
    return tmp_home_no_env


def _create(name: str = "throwaway") -> object:
    return Skill().run(
        action="create",
        name=name,
        category="software",
        description="Disposable skill for archive tests.",
        body="## When to use\nNever.\n",
    )


def test_delete_archives_instead_of_destroying(isolated_home: Path) -> None:
    _create(name="throwaway")
    live_dir = isolated_home / "skills" / "software" / "throwaway"
    assert live_dir.exists()

    r = Skill().run(action="delete", name="throwaway")

    assert r.ok, r.error
    assert not live_dir.exists()
    archive_root = isolated_home / "skills" / ".archive" / "software"
    assert archive_root.exists()
    archived = list(archive_root.iterdir())
    assert len(archived) == 1
    assert archived[0].name.startswith("throwaway__")
    # SKILL.md travels with the directory — restoration is just `mv`.
    assert (archived[0] / "SKILL.md").exists()


def test_pinned_skill_refuses_delete(isolated_home: Path) -> None:
    _create(name="important")
    Skill().run(
        action="set_meta",
        name="important",
        fields={"pinned": True},
    )

    r = Skill().run(action="delete", name="important")

    assert not r.ok
    assert "pinned" in r.error.lower()
    # Still live, not archived.
    assert (isolated_home / "skills" / "software" / "important").exists()
    assert not (isolated_home / "skills" / ".archive").exists()


def test_unpinning_allows_archive(isolated_home: Path) -> None:
    _create(name="reversible")
    Skill().run(action="set_meta", name="reversible", fields={"pinned": True})
    Skill().run(action="set_meta", name="reversible", fields={"pinned": False})

    r = Skill().run(action="delete", name="reversible")

    assert r.ok, r.error
    assert not (isolated_home / "skills" / "software" / "reversible").exists()


def test_archive_dir_excluded_from_skill_listing(isolated_home: Path) -> None:
    _create(name="ghost")
    Skill().run(action="delete", name="ghost")

    # Archived skill must NOT appear in any live-skill enumeration:
    # the dispatcher would otherwise treat it as a candidate for view/edit/run.
    live_names = {p.name for p in all_skills(isolated_home)}
    assert "ghost" not in live_names


def test_pinned_field_rejects_non_bool(isolated_home: Path) -> None:
    _create(name="strict")

    r = Skill().run(
        action="set_meta",
        name="strict",
        fields={"pinned": "maybe"},
    )

    assert not r.ok
    assert "pinned" in r.error.lower()
