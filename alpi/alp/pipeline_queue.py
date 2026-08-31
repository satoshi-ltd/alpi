from __future__ import annotations

import contextlib
import json
import os
import sys
import tempfile
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from alpi import config as cfg_mod


if sys.platform == "win32":
    import msvcrt
    _fcntl = None
else:
    import fcntl as _fcntl
    msvcrt = None


def path(home: Path) -> Path:
    return home / "alp" / "pipeline_queue.json"


def limit(home: Path) -> int:
    raw = (cfg_mod.load(home).alp or {}).get("max_active_pipelines", 0)
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return 0


@contextlib.contextmanager
def _locked(home: Path) -> Iterator[None]:
    lock_path = home / "alp" / "pipeline_queue.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    f = open(lock_path, "w")
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


def _read(home: Path) -> list[dict[str, Any]]:
    try:
        raw = json.loads(path(home).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(raw, list):
        return []
    out = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        wg_id = str(item.get("wg_id") or "").strip()
        pipeline = str(item.get("pipeline") or "").strip()
        if wg_id and pipeline:
            entry = {
                "wg_id": wg_id,
                "pipeline": pipeline,
                "enqueued_at": str(item.get("enqueued_at") or ""),
            }
            opener = str(item.get("opener") or "").strip()
            if opener:
                entry["opener"] = opener
            out.append(entry)
    return out


def _write(home: Path, entries: list[dict[str, Any]]) -> None:
    target = path(home)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".pipeline_queue.", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False, separators=(",", ":"))
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp_name, 0o600)
        os.replace(tmp_name, target)
    finally:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass


def entries(home: Path) -> list[dict[str, Any]]:
    with _locked(home):
        return _read(home)


def enqueue(
    home: Path, wg_id: str, pipeline: str, *, opener: str = "",
) -> dict[str, Any]:
    with _locked(home):
        current = [item for item in _read(home) if item["wg_id"] != wg_id]
        item = {
            "wg_id": wg_id,
            "pipeline": pipeline,
            "enqueued_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        if opener.strip():
            item["opener"] = opener.strip()
        current.append(item)
        _write(home, current)
        return {**item, "position": len(current)}


def remove(
    home: Path, wg_id: str, pipeline: str | None = None,
    *, enqueued_at: str | None = None,
) -> bool:
    with _locked(home):
        current = _read(home)
        kept = [
            item for item in current
            if not (
                item["wg_id"] == wg_id
                and (pipeline is None or item["pipeline"] == pipeline)
                and (enqueued_at is None or item["enqueued_at"] == enqueued_at)
            )
        ]
        if len(kept) == len(current):
            return False
        _write(home, kept)
        return True


def positions(home: Path) -> dict[str, dict[str, Any]]:
    return {
        item["wg_id"]: {**item, "position": index}
        for index, item in enumerate(entries(home), start=1)
    }
