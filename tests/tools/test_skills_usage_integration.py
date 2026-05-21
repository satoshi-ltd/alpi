"""SK.1 — integration: skill tool actions actually drive .usage.json."""

from __future__ import annotations

from pathlib import Path

import pytest

from alpi import skills_usage as su
from alpi.tools.skill import Skill


@pytest.fixture
def isolated_home(tmp_home_no_env: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("ALPI_HOME", str(tmp_home_no_env))
    return tmp_home_no_env


def _create(home: Path, name: str) -> None:
    r = Skill().run(
        action="create",
        name=name,
        category="personal",
        description="A skill for telemetry tests",
        body="## When to use\nFor testing.\n",
        requires_env=[],
    )
    assert r.ok, r.error


def test_create_records_initial_patch(isolated_home: Path) -> None:
    """A successful create lands a counter entry — first sign of life for
    the skill is recorded so later 'never used' classifications stay honest."""
    _create(isolated_home, "tel-create")
    usage = su.load_all(isolated_home)
    assert "tel-create" in usage
    assert usage["tel-create"]["patch_count"] >= 1


def test_view_increments_view_count(isolated_home: Path) -> None:
    _create(isolated_home, "tel-view")
    before = su.load_all(isolated_home)["tel-view"]["view_count"]
    r = Skill().run(action="view", name="tel-view")
    assert r.ok, r.error
    after = su.load_all(isolated_home)["tel-view"]["view_count"]
    assert after == before + 1


def test_set_meta_increments_patch_count(isolated_home: Path) -> None:
    _create(isolated_home, "tel-meta")
    before = su.load_all(isolated_home)["tel-meta"]["patch_count"]
    r = Skill().run(
        action="set_meta", name="tel-meta",
        fields={"description": "edited"},
        confirm_user_skill=True,
    )
    assert r.ok, r.error
    after = su.load_all(isolated_home)["tel-meta"]["patch_count"]
    assert after == before + 1


def test_delete_forgets_entry(isolated_home: Path) -> None:
    _create(isolated_home, "tel-del")
    assert "tel-del" in su.load_all(isolated_home)
    r = Skill().run(action="delete", name="tel-del", confirm_user_skill=True)
    assert r.ok, r.error
    assert "tel-del" not in su.load_all(isolated_home)


def test_failed_action_does_not_record(isolated_home: Path) -> None:
    """A view of a non-existent skill returns an error — no stub entry
    should appear in usage.json."""
    r = Skill().run(action="view", name="does-not-exist")
    assert not r.ok
    assert "does-not-exist" not in su.load_all(isolated_home)


def test_list_action_does_not_create_entries(isolated_home: Path) -> None:
    """``list`` is a meta-action over all skills, not a touch on any one of
    them — must not pollute the per-skill counters."""
    _create(isolated_home, "tel-list")
    before = su.load_all(isolated_home)["tel-list"].copy()
    r = Skill().run(action="list")
    assert r.ok
    after = su.load_all(isolated_home)["tel-list"]
    assert after == before


def test_pinned_snapshot_reflects_frontmatter(isolated_home: Path) -> None:
    """``set_meta`` toggles ``pinned`` in the frontmatter; the next touch
    must snapshot the new value into usage.json so the curator can act on
    pinned-but-cold candidates without re-reading every SKILL.md."""
    _create(isolated_home, "tel-pin")
    assert su.load_all(isolated_home)["tel-pin"]["pinned"] is False

    r = Skill().run(
        action="set_meta", name="tel-pin",
        fields={"pinned": "true"},
        confirm_user_skill=True,
    )
    assert r.ok, r.error
    # set_meta itself bumped patch_count + refreshed snapshot.
    assert su.load_all(isolated_home)["tel-pin"]["pinned"] is True
