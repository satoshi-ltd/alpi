"""AC.1 phase 1 — skill curator review."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from alpi import curator, skills_usage


DAY = 86_400.0


def _make_skill(home: Path, category: str, name: str,
                description: str = "x", pinned: bool = False,
                mtime: float | None = None) -> Path:
    d = home / "skills" / category / name
    d.mkdir(parents=True, exist_ok=True)
    md = d / "SKILL.md"
    pinned_field = f"pinned: {'true' if pinned else 'false'}\n"
    md.write_text(
        "---\n"
        f"name: {name}\n"
        f"description: {description}\n"
        f"category: {category}\n"
        f"{pinned_field}"
        "---\n"
        f"# {name}\n",
        encoding="utf-8",
    )
    if mtime is not None:
        import os
        os.utime(md, (mtime, mtime))
    return d


def _seed_usage(home: Path, *, name: str, last_seen: float,
                use_count: int = 1, view_count: int = 0,
                patch_count: int = 0) -> None:
    path = skills_usage.usage_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    state = {"v": skills_usage.USAGE_VERSION, "skills": {}}
    if path.exists():
        state = json.loads(path.read_text(encoding="utf-8"))
    state["skills"][name] = {
        "view_count": view_count, "use_count": use_count,
        "patch_count": patch_count,
        "first_seen": last_seen - DAY,
        "last_seen": last_seen,
        "pinned": False,
    }
    path.write_text(json.dumps(state, separators=(",", ":")), encoding="utf-8")


def test_review_clean_library_has_no_findings(tmp_path: Path) -> None:
    findings = curator.review(tmp_path, now=time.time())
    assert findings["summary"]["stale"] == 0
    assert findings["summary"]["cold"] == 0
    assert findings["summary"]["prefix_clusters"] == 0
    assert findings["stale"] == []
    assert findings["cold"] == []
    assert findings["prefix_clusters"] == []


def test_stale_flag_picks_up_unused_skill(tmp_path: Path) -> None:
    now = time.time()
    _make_skill(tmp_path, "research", "ancient")
    _seed_usage(tmp_path, name="ancient", last_seen=now - 60 * DAY, use_count=4)

    findings = curator.review(tmp_path, now=now)
    names = [r["name"] for r in findings["stale"]]
    assert names == ["ancient"]
    assert findings["stale"][0]["use_count"] == 4
    assert findings["stale"][0]["last_seen_days_ago"] == 60.0


def test_stale_ignores_pinned_skills(tmp_path: Path) -> None:
    now = time.time()
    _make_skill(tmp_path, "research", "anchor", pinned=True)
    _seed_usage(tmp_path, name="anchor", last_seen=now - 90 * DAY)
    assert curator.review(tmp_path, now=now)["stale"] == []


def test_stale_ignores_recent_skill(tmp_path: Path) -> None:
    now = time.time()
    _make_skill(tmp_path, "research", "fresh")
    _seed_usage(tmp_path, name="fresh", last_seen=now - 2 * DAY)
    assert curator.review(tmp_path, now=now)["stale"] == []


def test_window_days_override_widens_stale_window(tmp_path: Path) -> None:
    now = time.time()
    _make_skill(tmp_path, "research", "midage")
    _seed_usage(tmp_path, name="midage", last_seen=now - 45 * DAY)

    default_window = curator.review(tmp_path, now=now)
    assert len(default_window["stale"]) == 1

    long_window = curator.review(tmp_path, now=now, window_days=60)
    assert long_window["stale"] == []


def test_cold_flags_disk_skill_without_usage(tmp_path: Path) -> None:
    now = time.time()
    _make_skill(tmp_path, "research", "ghost", mtime=now - 60 * DAY)

    findings = curator.review(tmp_path, now=now)
    assert [r["name"] for r in findings["cold"]] == ["ghost"]
    assert findings["cold"][0]["on_disk_days_ago"] == 60.0


def test_cold_does_not_flag_a_fresh_stub(tmp_path: Path) -> None:
    now = time.time()
    _make_skill(tmp_path, "research", "newborn", mtime=now - 1 * DAY)
    assert curator.review(tmp_path, now=now)["cold"] == []


def test_cold_ignores_pinned_disk_skill(tmp_path: Path) -> None:
    now = time.time()
    _make_skill(tmp_path, "research", "pinned-stub", pinned=True,
                mtime=now - 60 * DAY)
    assert curator.review(tmp_path, now=now)["cold"] == []


def test_prefix_cluster_flags_three_or_more_siblings(tmp_path: Path) -> None:
    for n in ("debug-parser-a", "debug-parser-b", "debug-parser-c"):
        _make_skill(tmp_path, "research", n)

    clusters = curator.review(tmp_path, now=time.time())["prefix_clusters"]
    assert len(clusters) == 1
    c = clusters[0]
    assert c["prefix"] == "debug"
    assert c["count"] == 3
    assert sorted(c["names"]) == ["debug-parser-a", "debug-parser-b", "debug-parser-c"]


def test_prefix_cluster_requires_at_least_three(tmp_path: Path) -> None:
    for n in ("debug-parser-a", "debug-parser-b"):
        _make_skill(tmp_path, "research", n)
    assert curator.review(tmp_path, now=time.time())["prefix_clusters"] == []


def test_write_report_emits_md_and_json(tmp_path: Path) -> None:
    now = time.time()
    _make_skill(tmp_path, "research", "ghost", mtime=now - 60 * DAY)
    _make_skill(tmp_path, "research", "stale-one")
    _seed_usage(tmp_path, name="stale-one", last_seen=now - 60 * DAY)

    findings = curator.review(tmp_path, now=now)
    out_dir = curator.write_report(tmp_path, findings, ts=now)

    assert (out_dir / "report.md").exists()
    assert (out_dir / "report.json").exists()
    raw = json.loads((out_dir / "report.json").read_text())
    assert raw["summary"]["stale"] == 1
    assert raw["summary"]["cold"] == 1
    md = (out_dir / "report.md").read_text()
    assert "ghost" in md
    assert "stale-one" in md
    assert "Skill curator report" in md
    assert "Review each row" in md


def test_write_report_dir_is_under_logs_curator(tmp_path: Path) -> None:
    findings = curator.review(tmp_path, now=time.time())
    out_dir = curator.write_report(tmp_path, findings)
    assert out_dir.parent == tmp_path / "logs" / "curator"
    assert out_dir.name.endswith("Z")  # UTC stamp like 20260526T180000Z


def test_list_reports_returns_newest_first(tmp_path: Path) -> None:
    findings = curator.review(tmp_path, now=time.time())
    a = curator.write_report(tmp_path, findings, ts=1_700_000_000.0)
    b = curator.write_report(tmp_path, findings, ts=1_800_000_000.0)
    c = curator.write_report(tmp_path, findings, ts=1_900_000_000.0)
    assert curator.list_reports(tmp_path) == [c, b, a]


def test_list_reports_empty_when_no_runs(tmp_path: Path) -> None:
    assert curator.list_reports(tmp_path) == []


def test_two_runs_in_the_same_second_do_not_collide(tmp_path: Path) -> None:
    """Timestamp dir name carries milliseconds so two runs within the same second land in separate folders instead of overwriting each other."""
    findings = curator.review(tmp_path, now=time.time())
    a = curator.write_report(tmp_path, findings, ts=1_900_000_000.001)
    b = curator.write_report(tmp_path, findings, ts=1_900_000_000.500)
    assert a != b
    assert a.exists() and b.exists()


def test_clean_library_report_text_says_nothing_to_review(tmp_path: Path) -> None:
    findings = curator.review(tmp_path, now=time.time())
    md = curator._render_markdown(findings)
    assert "Nothing to review" in md


def test_review_swallows_oserror_on_skill_md_stat(tmp_path: Path, monkeypatch) -> None:
    """A skill dir whose ``SKILL.md`` can't be stat()'d (FS race, perm) must not abort the run."""
    _make_skill(tmp_path, "research", "doomed", mtime=time.time() - 60 * DAY)
    orig_stat = Path.stat
    def _flaky(self, *a, **kw):
        if self.name == "SKILL.md":
            raise OSError("vanished")
        return orig_stat(self, *a, **kw)
    monkeypatch.setattr(Path, "stat", _flaky)
    findings = curator.review(tmp_path, now=time.time())
    assert findings["summary"]["skills_on_disk"] == 1
