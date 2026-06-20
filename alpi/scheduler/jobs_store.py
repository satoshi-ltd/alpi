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


def jobs_path(home: Path) -> Path:
    return home / "schedule" / "jobs.json"


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


def _read_inside_lock(home: Path) -> list[dict]:
    p = jobs_path(home)
    if not p.exists():
        return []
    raw = p.read_text(encoding="utf-8")
    if not raw.strip():
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise CorruptJobsFile(f"{p}: invalid JSON ({e})") from e
    if not isinstance(data, list):
        raise CorruptJobsFile(f"{p}: top-level value is {type(data).__name__}, expected list")
    return data


def _write_inside_lock(home: Path, jobs: list[dict]) -> None:
    p = jobs_path(home)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(jobs, indent=2))
            fh.flush()
            os.fsync(fh.fileno())
    except Exception:
        try: tmp.unlink()
        except OSError: pass
        raise
    os.replace(str(tmp), str(p))


def read(home: Path) -> list[dict]:
    with locked(home):
        return _read_inside_lock(home)


def update(
    home: Path,
    mutator: Callable[[list[dict]], list[dict] | None],
) -> list[dict]:
    with locked(home):
        jobs = _read_inside_lock(home)
        result = mutator(jobs)
        if result is None:
            return jobs
        _write_inside_lock(home, result)
        return result
