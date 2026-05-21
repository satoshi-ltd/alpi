"""SK.1 — skill telemetry: record/load/classify/summary."""

from __future__ import annotations

import json
from pathlib import Path

from alpi import skills_usage as su


def _load_raw(home: Path) -> dict:
    return json.loads(su.usage_path(home).read_text(encoding="utf-8"))


def test_record_creates_file_and_initial_entry(tmp_path: Path) -> None:
    su.record_usage(tmp_path, "@alpi/knowledge", "view", now=1000.0)

    raw = _load_raw(tmp_path)
    assert raw["v"] == su.USAGE_VERSION
    entry = raw["skills"]["@alpi/knowledge"]
    assert entry["view_count"] == 1
    assert entry["use_count"] == 0
    assert entry["patch_count"] == 0
    assert entry["first_seen"] == 1000.0
    assert entry["last_seen"] == 1000.0


def test_action_buckets_route_correctly(tmp_path: Path) -> None:
    """Each action increments the right counter so view/use/patch stay
    separable. ``list`` is intentionally NOT in the bucket map — it's a
    profile-wide meta-action with no per-skill ``name`` to attribute."""
    for action in ("view", "validate"):
        su.record_usage(tmp_path, "okr-review", action)
    for action in ("run", "invoke", "test"):
        su.record_usage(tmp_path, "okr-review", action)
    for action in ("create", "edit", "patch", "add_file", "remove_file", "set_meta"):
        su.record_usage(tmp_path, "okr-review", action)

    entry = su.load_all(tmp_path)["okr-review"]
    assert entry["view_count"] == 2
    assert entry["use_count"] == 3
    assert entry["patch_count"] == 6


def test_list_action_has_no_bucket(tmp_path: Path) -> None:
    """``list`` is the meta-action over the whole catalog; it has no
    target ``name`` to attribute usage to. Calling ``record_usage`` with
    action='list' is a defined no-op so a future hook regression at the
    skill.py call site can't accidentally pollute per-skill counters."""
    su.record_usage(tmp_path, "okr-review", "list")
    assert su.load_all(tmp_path) == {}


def test_unknown_action_is_silent_noop(tmp_path: Path) -> None:
    """Skill.py calls record_usage for every action without pre-filtering. Unmapped names must not error and must not create stub entries."""
    su.record_usage(tmp_path, "okr-review", "wibble")
    assert su.load_all(tmp_path) == {}


def test_pinned_snapshot_refreshes_on_each_touch(tmp_path: Path) -> None:
    su.record_usage(tmp_path, "okr-review", "view", pinned=False, now=1.0)
    assert su.load_all(tmp_path)["okr-review"]["pinned"] is False
    su.record_usage(tmp_path, "okr-review", "run", pinned=True, now=2.0)
    assert su.load_all(tmp_path)["okr-review"]["pinned"] is True


def test_last_seen_advances_first_seen_holds(tmp_path: Path) -> None:
    su.record_usage(tmp_path, "n", "view", now=100.0)
    su.record_usage(tmp_path, "n", "view", now=500.0)
    entry = su.load_all(tmp_path)["n"]
    assert entry["first_seen"] == 100.0
    assert entry["last_seen"] == 500.0


def test_forget_removes_entry(tmp_path: Path) -> None:
    su.record_usage(tmp_path, "deleted-skill", "view")
    assert "deleted-skill" in su.load_all(tmp_path)
    su.forget(tmp_path, "deleted-skill")
    assert "deleted-skill" not in su.load_all(tmp_path)


def test_forget_unknown_is_safe(tmp_path: Path) -> None:
    su.forget(tmp_path, "never-existed")


def test_corrupt_file_is_treated_as_empty(tmp_path: Path) -> None:
    path = su.usage_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not valid json")
    assert su.load_all(tmp_path) == {}
    su.record_usage(tmp_path, "fresh", "view")
    assert "fresh" in su.load_all(tmp_path)


def test_classify_active_stale_archived(tmp_path: Path) -> None:
    now = 1_700_000_000.0
    day = 86400.0
    assert su.classify({"last_seen": now - 5 * day}, now=now) == "active"
    assert su.classify({"last_seen": now - 45 * day}, now=now) == "stale"
    assert su.classify({"last_seen": now - 120 * day}, now=now) == "archived"
    assert su.classify({}, now=now) == "archived"


def test_summary_counts_by_state_and_top_used(tmp_path: Path) -> None:
    now = 1_700_000_000.0
    day = 86400.0
    su.record_usage(tmp_path, "a", "run", now=now - 1 * day)
    su.record_usage(tmp_path, "a", "run", now=now - 1 * day)
    su.record_usage(tmp_path, "a", "run", now=now - 1 * day)
    su.record_usage(tmp_path, "b", "run", now=now - 50 * day)
    su.record_usage(tmp_path, "c", "run", now=now - 200 * day)

    out = su.summary(tmp_path, now=now)
    assert out["total"] == 3
    assert out["by_state"] == {"active": 1, "stale": 1, "archived": 1}
    assert out["top_used"][0] == ("a", 3)


def test_summary_flags_pinned_but_cold(tmp_path: Path) -> None:
    """A skill that's pinned (user said 'keep this') but hasn't been touched
    in months is the most interesting curation candidate — operator should
    see it surface in doctor / digest output."""
    now = 1_700_000_000.0
    su.record_usage(tmp_path, "cold-pinned", "view",
                    pinned=True, now=now - 100 * 86400.0)
    su.record_usage(tmp_path, "warm-pinned", "view",
                    pinned=True, now=now - 1 * 86400.0)

    out = su.summary(tmp_path, now=now)
    names = {n for n, _ in out["pinned_cold"]}
    assert "cold-pinned" in names
    assert "warm-pinned" not in names
