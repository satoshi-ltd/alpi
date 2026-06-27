"""Tests for ``alpi.diff`` — profile-state scanner.

Strategy: build a synthetic profile under ``tmp_home``, set explicit
mtimes via ``os.utime`` so the cutoff comparisons are deterministic,
and assert on the structured report. Renderer gets a smoke pass so
formatting bugs don't pass review unnoticed.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from alpi import diff


_FIXED_NOW = datetime(2026, 5, 2, 12, 0, 0, tzinfo=timezone.utc)


def _set_mtime(path: Path, dt: datetime) -> None:
    ts = dt.timestamp()
    os.utime(path, (ts, ts))


# parse_since

class TestParseSince:
    def test_hours(self) -> None:
        cutoff = diff.parse_since("24h", now=_FIXED_NOW)
        assert cutoff == _FIXED_NOW - timedelta(hours=24)

    def test_days(self) -> None:
        cutoff = diff.parse_since("7d", now=_FIXED_NOW)
        assert cutoff == _FIXED_NOW - timedelta(days=7)

    def test_minutes(self) -> None:
        cutoff = diff.parse_since("30m", now=_FIXED_NOW)
        assert cutoff == _FIXED_NOW - timedelta(minutes=30)

    def test_weeks(self) -> None:
        cutoff = diff.parse_since("2w", now=_FIXED_NOW)
        assert cutoff == _FIXED_NOW - timedelta(weeks=2)

    def test_seconds(self) -> None:
        cutoff = diff.parse_since("90s", now=_FIXED_NOW)
        assert cutoff == _FIXED_NOW - timedelta(seconds=90)

    def test_case_insensitive_unit(self) -> None:
        a = diff.parse_since("24H", now=_FIXED_NOW)
        b = diff.parse_since("24h", now=_FIXED_NOW)
        assert a == b

    def test_iso_date_assumed_utc(self) -> None:
        cutoff = diff.parse_since("2026-04-25", now=_FIXED_NOW)
        assert cutoff == datetime(2026, 4, 25, tzinfo=timezone.utc)

    def test_iso_datetime_with_tz(self) -> None:
        cutoff = diff.parse_since("2026-04-25T10:00:00+02:00", now=_FIXED_NOW)
        assert cutoff == datetime(2026, 4, 25, 8, 0, 0, tzinfo=timezone.utc)

    def test_invalid_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="unrecognised --since"):
            diff.parse_since("yesterday", now=_FIXED_NOW)

    def test_negative_not_allowed(self) -> None:
        # The regex requires \d+, so "-7d" doesn't parse as a delta and
        # falls through to fromisoformat which also rejects it.
        with pytest.raises(ValueError):
            diff.parse_since("-7d", now=_FIXED_NOW)


# compute() — sessions

def test_compute_picks_only_sessions_after_cutoff(tmp_home: Path) -> None:
    sessions = tmp_home / "sessions"
    sessions.mkdir(parents=True)
    fresh = sessions / "fresh.json"
    fresh.write_text(json.dumps({
        "id": "fresh",
        "input_tokens": 100, "output_tokens": 50,
        "cost_usd": 0.01, "elapsed": 30.0,
        "turns": [{"tools": [{}, {}]}, {"tools": []}],
    }))
    stale = sessions / "stale.json"
    stale.write_text(json.dumps({
        "id": "stale",
        "input_tokens": 9999, "output_tokens": 9999,
        "cost_usd": 99.0, "elapsed": 9999,
        "turns": [{"tools": [{}, {}, {}]}],
    }))
    cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
    _set_mtime(fresh, datetime.now(timezone.utc) - timedelta(minutes=5))
    _set_mtime(stale, datetime.now(timezone.utc) - timedelta(days=2))

    report = diff.compute(tmp_home, cutoff)

    s = report["sessions"]
    assert s["count"] == 1
    assert s["turns"] == 2
    assert s["tool_calls"] == 2
    assert s["tokens"] == 150
    assert s["cost_usd"] == pytest.approx(0.01)
    assert s["elapsed_s"] == pytest.approx(30.0)


def test_compute_handles_malformed_session_json(tmp_home: Path) -> None:
    sessions = tmp_home / "sessions"
    sessions.mkdir(parents=True)
    bad = sessions / "broken.json"
    bad.write_text("{not valid json")
    _set_mtime(bad, datetime.now(timezone.utc) - timedelta(minutes=5))

    cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
    report = diff.compute(tmp_home, cutoff)
    assert report["sessions"]["count"] == 0


def test_compute_counts_local_sessions(tmp_home: Path) -> None:
    d = tmp_home / "sessions"
    d.mkdir(parents=True)
    f = d / "x.json"
    f.write_text(json.dumps({"id": "a", "turns": [{"tools": []}]}))
    _set_mtime(f, datetime.now(timezone.utc) - timedelta(minutes=5))

    cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
    report = diff.compute(tmp_home, cutoff)
    assert report["sessions"]["count"] == 1
    assert report["sessions"]["turns"] == 1


# compute() — memory / skills / peers / mentions / schedule

def test_compute_memory_files_filtered_by_mtime(tmp_home: Path) -> None:
    mem = tmp_home / "memories"
    mem.mkdir()
    fresh = mem / "MEMORY.md"
    fresh.write_text("recent")
    stale = mem / "USER.md"
    stale.write_text("old")
    _set_mtime(fresh, datetime.now(timezone.utc) - timedelta(minutes=5))
    _set_mtime(stale, datetime.now(timezone.utc) - timedelta(days=10))

    cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
    report = diff.compute(tmp_home, cutoff)
    files = [m["file"] for m in report["memory"]]
    assert files == ["MEMORY.md"]


def test_compute_skills_only_recent_dirs(tmp_home: Path) -> None:
    skills = tmp_home / "skills"
    skills.mkdir()
    new_skill = skills / "@alpi-fresh"
    new_skill.mkdir()
    (new_skill / "SKILL.md").write_text("x")
    old_skill = skills / "@alpi-old"
    old_skill.mkdir()
    (old_skill / "SKILL.md").write_text("x")
    hidden = skills / ".hidden"
    hidden.mkdir()
    _set_mtime(new_skill, datetime.now(timezone.utc) - timedelta(minutes=5))
    _set_mtime(old_skill, datetime.now(timezone.utc) - timedelta(days=30))
    _set_mtime(hidden, datetime.now(timezone.utc))

    cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
    report = diff.compute(tmp_home, cutoff)
    names = [s["name"] for s in report["skills"]]
    assert names == ["@alpi-fresh"]  # ``.hidden`` skipped


def test_compute_peers_yaml_change_detection(tmp_home: Path) -> None:
    alp_dir = tmp_home / "alp"
    alp_dir.mkdir()
    yaml = alp_dir / "peers.yaml"
    yaml.write_text(
        "- id: alice\n  pubkey: AAAA\n  allow: [link.ask]\n"
        "- id: bob\n  pubkey: BBBB\n  allow: []\n"
    )
    _set_mtime(yaml, datetime.now(timezone.utc) - timedelta(minutes=10))

    cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
    report = diff.compute(tmp_home, cutoff)
    assert report["peers"]["count"] == 2
    assert report["peers"]["changed"] is True


def test_compute_peers_unchanged_when_yaml_old(tmp_home: Path) -> None:
    alp_dir = tmp_home / "alp"
    alp_dir.mkdir()
    yaml = alp_dir / "peers.yaml"
    yaml.write_text("- id: alice\n  pubkey: AAAA\n  allow: []\n")
    _set_mtime(yaml, datetime.now(timezone.utc) - timedelta(days=30))

    cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
    report = diff.compute(tmp_home, cutoff)
    assert report["peers"]["count"] == 1
    assert report["peers"]["changed"] is False


def test_compute_mentions_collects_recent_threads(tmp_home: Path) -> None:
    mentions = tmp_home / "mentions"
    mentions.mkdir()
    a = mentions / "alice.json"
    a.write_text("[]")
    b = mentions / "bob.json"
    b.write_text("[]")
    _set_mtime(a, datetime.now(timezone.utc) - timedelta(minutes=5))
    _set_mtime(b, datetime.now(timezone.utc) - timedelta(days=2))

    cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
    report = diff.compute(tmp_home, cutoff)
    assert report["mentions"]["files"] == 1
    assert report["mentions"]["peers"] == ["alice"]


def test_compute_schedule_runs_grouped_by_job(tmp_home: Path) -> None:
    out = tmp_home / "schedule" / "output"
    job1 = out / "daily-summary"
    job1.mkdir(parents=True)
    for n in range(3):
        f = job1 / f"run-{n}.txt"
        f.write_text("ok")
        _set_mtime(f, datetime.now(timezone.utc) - timedelta(minutes=10 + n))
    job2 = out / "weekly-roll"
    job2.mkdir()
    f = job2 / "run.txt"
    f.write_text("ok")
    _set_mtime(f, datetime.now(timezone.utc) - timedelta(days=30))  # excluded

    cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
    report = diff.compute(tmp_home, cutoff)
    assert report["schedule_runs"]["count"] == 3
    assert report["schedule_runs"]["by_job"] == {"daily-summary": 3}


def test_compute_empty_profile_is_safe(tmp_home: Path) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
    report = diff.compute(tmp_home, cutoff)
    assert report["sessions"]["count"] == 0
    assert report["memory"] == []
    assert report["skills"] == []
    assert report["peers"]["yaml_mtime"] is None
    assert report["mentions"]["files"] == 0
    assert report["schedule_runs"]["count"] == 0


def test_compute_includes_iso_since_and_now(tmp_home: Path) -> None:
    cutoff = datetime(2026, 4, 1, tzinfo=timezone.utc)
    report = diff.compute(tmp_home, cutoff)
    assert report["since"] == "2026-04-01T00:00:00+00:00"
    assert "T" in report["now"]


# render() — smoke

def test_render_includes_section_headers(tmp_home: Path) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
    report = diff.compute(tmp_home, cutoff)
    text = diff.render(report, profile="default")
    for header in ("memory", "sessions (local)", "skills", "peers", "budget today"):
        assert header in text


def test_render_shows_session_counts_when_present(tmp_home: Path) -> None:
    sessions = tmp_home / "sessions"
    sessions.mkdir()
    f = sessions / "x.json"
    f.write_text(json.dumps({
        "id": "x",
        "input_tokens": 10, "output_tokens": 20,
        "cost_usd": 0.5, "elapsed": 65.0,
        "turns": [{"tools": [{}]}],
    }))
    _set_mtime(f, datetime.now(timezone.utc) - timedelta(minutes=5))

    cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
    report = diff.compute(tmp_home, cutoff)
    text = diff.render(report, profile="default")
    assert "1 sessions" in text
    assert "1 tool calls" in text
    assert "$0.5000" in text
