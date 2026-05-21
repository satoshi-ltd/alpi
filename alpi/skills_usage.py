"""SK.1 — local skill telemetry.

Per-skill view / use / patch counts + timestamps + pinned snapshot persisted
to ``<profile>/skills/.usage.json``. Pure measurement: state classification
(active / stale / archived) is derived on read from ``last_seen`` so the
file never drifts out of sync with the real cutoffs.

Consumers: ``alpi doctor``, future ``alpi ops digest`` (OPS.1), and the
v0.7 curator (AC.1) which will recommend prunes from this data.
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from threading import Lock


USAGE_VERSION = 1

ACTION_TO_BUCKET: dict[str, str] = {
    "view":         "view_count",
    "validate":     "view_count",
    "run":          "use_count",
    "invoke":       "use_count",
    "test":         "use_count",
    "create":       "patch_count",
    "edit":         "patch_count",
    "patch":        "patch_count",
    "add_file":     "patch_count",
    "remove_file":  "patch_count",
    "set_meta":     "patch_count",
}

STALE_DAYS = 30
ARCHIVED_DAYS = 90


_lock = Lock()


def usage_path(home: Path) -> Path:
    return home / "skills" / ".usage.json"


def _empty() -> dict:
    return {"v": USAGE_VERSION, "skills": {}}


def _load(path: Path) -> dict:
    if not path.exists():
        return _empty()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _empty()
    if not isinstance(raw, dict) or raw.get("v") != USAGE_VERSION:
        return _empty()
    skills = raw.get("skills")
    if not isinstance(skills, dict):
        raw["skills"] = {}
    return raw


def _atomic_write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Per-pid + per-thread tmp suffix so two daemon instances on the same
    # profile dir can't race on a shared ``.usage.json.tmp`` and clobber
    # each other's write mid-rename.
    suffix = f".tmp.{os.getpid()}.{threading.get_ident()}"
    tmp = path.with_suffix(path.suffix + suffix)
    tmp.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    tmp.replace(path)


def record_usage(
    home: Path, skill_name: str, action: str,
    *, pinned: bool | None = None, now: float | None = None,
) -> None:
    """Bump the counter for ``action`` on ``skill_name`` and refresh timestamps + pinned snapshot. Silent no-op for unmapped actions so ``skill.py`` can call without filtering."""
    bucket = ACTION_TO_BUCKET.get(action)
    if not bucket or not skill_name:
        return
    ts = now if now is not None else time.time()
    path = usage_path(home)
    with _lock:
        state = _load(path)
        entry = state["skills"].get(skill_name) or {
            "view_count": 0, "use_count": 0, "patch_count": 0,
            "first_seen": ts, "last_seen": ts, "pinned": False,
        }
        entry[bucket] = int(entry.get(bucket, 0)) + 1
        entry["last_seen"] = ts
        if not entry.get("first_seen"):
            entry["first_seen"] = ts
        if pinned is not None:
            entry["pinned"] = bool(pinned)
        state["skills"][skill_name] = entry
        _atomic_write(path, state)


def forget(home: Path, skill_name: str) -> None:
    """Drop an entry — called on ``skill(action=delete)`` so usage doesn't outlive the skill itself."""
    if not skill_name:
        return
    path = usage_path(home)
    with _lock:
        state = _load(path)
        if skill_name in state["skills"]:
            del state["skills"][skill_name]
            _atomic_write(path, state)


def load_all(home: Path) -> dict[str, dict]:
    """Return the raw ``{name: entry}`` map. Read-only snapshot."""
    return dict(_load(usage_path(home)).get("skills", {}))


def classify(entry: dict, *, now: float | None = None) -> str:
    """Derive ``active`` / ``stale`` / ``archived`` from ``last_seen`` so the on-disk file never lies about cutoffs."""
    last = float(entry.get("last_seen") or 0.0)
    if last <= 0:
        return "archived"
    age_days = ((now if now is not None else time.time()) - last) / 86400.0
    if age_days < STALE_DAYS:
        return "active"
    if age_days < ARCHIVED_DAYS:
        return "stale"
    return "archived"


def summary(home: Path, *, now: float | None = None) -> dict:
    """Aggregate stats for ``alpi doctor`` / OPS.1: how many active vs stale vs archived, top-used, and pinned-but-cold entries that probably want operator attention."""
    skills = load_all(home)
    nowt = now if now is not None else time.time()
    by_state = {"active": 0, "stale": 0, "archived": 0}
    pinned_cold: list[tuple[str, str]] = []
    used: list[tuple[str, int]] = []
    for name, entry in skills.items():
        state = classify(entry, now=nowt)
        by_state[state] += 1
        use_count = int(entry.get("use_count") or 0)
        used.append((name, use_count))
        if entry.get("pinned") and state != "active":
            pinned_cold.append((name, state))
    used.sort(key=lambda t: t[1], reverse=True)
    return {
        "total":        len(skills),
        "by_state":     by_state,
        "top_used":     used[:10],
        "pinned_cold":  pinned_cold,
    }


__all__ = [
    "ACTION_TO_BUCKET",
    "ARCHIVED_DAYS",
    "STALE_DAYS",
    "USAGE_VERSION",
    "classify",
    "forget",
    "load_all",
    "record_usage",
    "summary",
    "usage_path",
]
