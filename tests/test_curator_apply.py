from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from alpi import curator, curator_apply


def _make_skill(home: Path, category: str, name: str, *, pinned: bool = False,
                mtime: float | None = None) -> Path:
    d = home / "skills" / category / name
    d.mkdir(parents=True, exist_ok=True)
    md = d / "SKILL.md"
    md.write_text(
        "---\n"
        f"name: {name}\n"
        "description: x\n"
        f"category: {category}\n"
        f"pinned: {'true' if pinned else 'false'}\n"
        "---\n"
        f"# {name}\n",
        encoding="utf-8",
    )
    if mtime is not None:
        os.utime(md, (mtime, mtime))
    return d


def _report(skill: str = "old", category: str = "research", reason: str = "cold") -> dict:
    return {"version": 2, "actions": [
        {"type": "archive", "skill": skill, "category": category, "reason": reason},
    ]}


def test_dry_run_plans_archive_without_moving(tmp_path: Path) -> None:
    _make_skill(tmp_path, "research", "old")
    result = curator_apply.apply_report(tmp_path, _report(), dry_run=True)
    assert result["counts"].get("would-archive") == 1
    assert (tmp_path / "skills" / "research" / "old").exists()


def test_apply_moves_skill_to_archive(tmp_path: Path) -> None:
    _make_skill(tmp_path, "research", "old")
    result = curator_apply.apply_report(tmp_path, _report())
    assert result["counts"].get("archived") == 1
    assert not (tmp_path / "skills" / "research" / "old").exists()
    archived = list((tmp_path / "skills" / ".archive" / "research").iterdir())
    assert len(archived) == 1
    assert archived[0].name.startswith("old__")


def test_pinned_skill_is_skipped(tmp_path: Path) -> None:
    _make_skill(tmp_path, "research", "keep", pinned=True)
    result = curator_apply.apply_report(tmp_path, _report(skill="keep"))
    assert result["counts"].get("skipped") == 1
    assert result["results"][0]["reason"] == "pinned"
    assert (tmp_path / "skills" / "research" / "keep").exists()


def test_apply_is_idempotent(tmp_path: Path) -> None:
    _make_skill(tmp_path, "research", "old")
    curator_apply.apply_report(tmp_path, _report())
    again = curator_apply.apply_report(tmp_path, _report())
    assert again["counts"].get("skipped") == 1
    assert again["counts"].get("archived") is None


def test_apply_resolves_by_category_on_name_collision(tmp_path: Path) -> None:
    _make_skill(tmp_path, "research", "dup")
    _make_skill(tmp_path, "software", "dup")
    report = {"version": 2, "actions": [
        {"type": "archive", "skill": "dup", "category": "software", "reason": "cold"},
    ]}
    result = curator_apply.apply_report(tmp_path, report)
    assert result["counts"].get("archived") == 1
    # the software/dup is gone, research/dup survives — category disambiguated.
    assert not (tmp_path / "skills" / "software" / "dup").exists()
    assert (tmp_path / "skills" / "research" / "dup").exists()


def test_missing_skill_is_skipped_not_error(tmp_path: Path) -> None:
    (tmp_path / "skills").mkdir()
    result = curator_apply.apply_report(tmp_path, _report(skill="ghost"))
    assert result["results"][0]["status"] == "skipped"


def test_path_like_name_is_rejected(tmp_path: Path) -> None:
    _make_skill(tmp_path, "research", "old")
    report = {"version": 2, "actions": [
        {"type": "archive", "skill": "../etc/passwd", "category": "x", "reason": "cold"},
    ]}
    result = curator_apply.apply_report(tmp_path, report)
    assert result["results"][0]["status"] == "skipped"
    assert result["results"][0]["reason"] == "invalid skill name"


def test_unsupported_action_type_is_skipped(tmp_path: Path) -> None:
    report = {"version": 2, "actions": [{"type": "mark_absorbed", "skill": "old"}]}
    result = curator_apply.apply_report(tmp_path, report)
    assert result["results"][0]["status"] == "skipped"
    assert result["results"][0]["reason"] == "unsupported action type"


def test_report_without_actions_applies_nothing(tmp_path: Path) -> None:
    result = curator_apply.apply_report(tmp_path, {"version": 1})
    assert result["results"] == []


def test_review_emits_archive_actions_excluding_pinned(tmp_path: Path) -> None:
    old = time.time() - 60 * 86400
    _make_skill(tmp_path, "research", "cold-one", mtime=old)
    _make_skill(tmp_path, "research", "pinned-one", pinned=True, mtime=old)
    findings = curator.review(tmp_path, window_days=30)
    skills = {a["skill"] for a in findings["actions"]}
    assert "cold-one" in skills
    assert "pinned-one" not in skills
    assert all(a["type"] == "archive" for a in findings["actions"])


def test_write_apply_report_creates_apply_json(tmp_path: Path) -> None:
    report_dir = tmp_path / "logs" / "curator" / "r1"
    report_dir.mkdir(parents=True)
    result = curator_apply.apply_report(tmp_path, {"version": 2, "actions": []})
    path = curator_apply.write_apply_report(report_dir, result)
    assert path.name == "apply.json"
    assert json.loads(path.read_text())["counts"] == {}


def test_load_report_latest_and_by_id(tmp_path: Path) -> None:
    findings = curator.review(tmp_path, window_days=30)
    out_dir = curator.write_report(tmp_path, findings)
    report_dir, report = curator_apply.load_report(tmp_path)
    assert report_dir == out_dir
    assert report["version"] == 2
    by_id_dir, _ = curator_apply.load_report(tmp_path, out_dir.name)
    assert by_id_dir == out_dir


def test_load_report_errors_without_reports(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        curator_apply.load_report(tmp_path)
