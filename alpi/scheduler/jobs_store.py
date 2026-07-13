from __future__ import annotations

import contextlib
import json
import os
import sys
from collections.abc import Callable, Iterator
from pathlib import Path

if sys.platform == "win32":
    import msvcrt
    _fcntl = None
else:
    import fcntl as _fcntl
    msvcrt = None


class CorruptJobsFile(RuntimeError):
    pass


# jobs.json holds definitions only; runs.json holds per-id run state. Merged on read, split on write.
STATE_FIELDS = ("last_run_at", "last_run_status")


def jobs_path(home: Path) -> Path:
    return home / "schedule" / "jobs.json"


def runs_path(home: Path) -> Path:
    return home / "schedule" / "runs.json"


def _lock_path(home: Path) -> Path:
    return home / "schedule" / "jobs.lock"


@contextlib.contextmanager
def locked(home: Path) -> Iterator[None]:
    lp = _lock_path(home)
    lp.parent.mkdir(parents=True, exist_ok=True)
    f = open(lp, "w")
    try:
        if sys.platform == "win32":
            msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
        else:
            _fcntl.flock(f.fileno(), _fcntl.LOCK_EX)
        yield
    finally:
        try:
            if sys.platform == "win32":
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                _fcntl.flock(f.fileno(), _fcntl.LOCK_UN)
        finally:
            f.close()


def _load_json(p: Path, expect: type) -> list | dict:
    if not p.exists():
        return expect()
    raw = p.read_text(encoding="utf-8")
    if not raw.strip():
        return expect()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise CorruptJobsFile(f"{p}: invalid JSON ({e})") from e
    if not isinstance(data, expect):
        raise CorruptJobsFile(f"{p}: top-level value is {type(data).__name__}, expected {expect.__name__}")
    return data


def _read_defs_inside_lock(home: Path) -> list[dict]:
    return _load_json(jobs_path(home), list)


def _read_runs_inside_lock(home: Path) -> dict:
    return _load_json(runs_path(home), dict)


def _write_inside_lock(p: Path, payload: list | dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, indent=2))
            fh.flush()
            os.fsync(fh.fileno())
    except Exception:
        try: tmp.unlink()
        except OSError: pass
        raise
    os.replace(str(tmp), str(p))


def _merged_inside_lock(home: Path) -> list[dict]:
    defs = _read_defs_inside_lock(home)
    runs = _read_runs_inside_lock(home)
    merged: list[dict] = []
    for j in defs:
        m = dict(j)
        state = runs.get(str(j.get("id")))
        if isinstance(state, dict):
            for k in STATE_FIELDS:
                # legacy state still embedded in jobs.json wins until the first write migrates it out
                if k in state and k not in m:
                    m[k] = state[k]
        merged.append(m)
    return merged


def _split(jobs: list[dict]) -> tuple[list[dict], dict]:
    defs: list[dict] = []
    runs: dict = {}
    for j in jobs:
        defs.append({k: v for k, v in j.items() if k not in STATE_FIELDS})
        state = {k: j[k] for k in STATE_FIELDS if k in j}
        if state and j.get("id"):
            runs[str(j["id"])] = state
    return defs, runs


def read(home: Path) -> list[dict]:
    with locked(home):
        return _merged_inside_lock(home)


def update(
    home: Path,
    mutator: Callable[[list[dict]], list[dict] | None],
) -> list[dict]:
    with locked(home):
        old_defs = _read_defs_inside_lock(home)
        old_runs = _read_runs_inside_lock(home)
        jobs = _merged_inside_lock(home)
        result = mutator(jobs)
        if result is None:
            return jobs
        new_defs, new_runs = _split(result)
        # Crash-safe order: state lands before the definitions needing it (a def without last_run_at re-fires); orphans pruned last.
        union_runs = {**old_runs, **new_runs}
        if union_runs != old_runs:
            _write_inside_lock(runs_path(home), union_runs)
        if new_defs != old_defs:
            _write_inside_lock(jobs_path(home), new_defs)
        if new_runs != union_runs:
            _write_inside_lock(runs_path(home), new_runs)
        return result
