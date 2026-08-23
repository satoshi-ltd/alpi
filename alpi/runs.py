from __future__ import annotations

import json
import math
import os
import re
import threading
import time
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from alpi._redact import redact
from alpi.core.run_context import RunContext


FORMAT_VERSION = 1
MAX_EVENT_BYTES = 32 * 1024
MAX_TEXT_BYTES = 12 * 1024
MAX_LIST_LIMIT = 200

_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()
_seq: dict[str, int] = {}
_active: dict[tuple[str, str], tuple[str, Any]] = {}
_active_lock = threading.Lock()
_SAFE_RUN_ID = re.compile(r"^[A-Za-z0-9_-]+$")


def run_path(home: Path, run_id: str) -> Path:
    if not _SAFE_RUN_ID.fullmatch(run_id or ""):
        raise ValueError("invalid run id")
    return home / "runs" / f"{run_id}.jsonl"


def _lock(path: Path) -> threading.Lock:
    key = str(path)
    with _locks_guard:
        value = _locks.get(key)
        if value is None:
            value = threading.Lock()
            _locks[key] = value
        return value


def _clip_text(value: str) -> str:
    raw = value.encode("utf-8", errors="replace")
    if len(raw) <= MAX_TEXT_BYTES:
        return value
    suffix = "…".encode()
    return raw[: MAX_TEXT_BYTES - len(suffix)].decode("utf-8", errors="ignore") + "…"


def _bounded(value: Any) -> Any:
    if isinstance(value, str):
        return _clip_text(value)
    if isinstance(value, dict):
        return {str(k): _bounded(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_bounded(item) for item in value]
    return value


def persisted_tool_arguments(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    safe = dict(arguments)
    if name == "terminal":
        safe.pop("command", None)
    elif name == "workflow":
        raw_steps = safe.get("steps")
        if not isinstance(raw_steps, list):
            return safe
        steps = []
        for raw in raw_steps:
            if not isinstance(raw, dict):
                steps.append(raw)
                continue
            step = dict(raw)
            nested_name = str(step.get("tool") or "")
            nested_args = step.get("arguments")
            if isinstance(nested_args, dict):
                step["arguments"] = persisted_tool_arguments(nested_name, nested_args)
            steps.append(step)
        safe["steps"] = steps
    return safe


def _last_seq(path: Path) -> int:
    cached = _seq.get(str(path))
    if cached is not None:
        return cached
    last = -1
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    row = json.loads(line)
                    if isinstance(row, dict):
                        last = max(last, int(row.get("seq", -1)))
                except (ValueError, TypeError):
                    continue
    except OSError:
        pass
    return last


def append(home: Path, run_id: str, kind: str, data: dict[str, Any] | None = None) -> dict:
    path = run_path(home, run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.parent.is_symlink():
        raise OSError("run journal directory must not be a symlink")
    try:
        os.chmod(path.parent, 0o700)
    except OSError:
        pass
    with _lock(path):
        seq = _last_seq(path) + 1
        payload = _bounded(redact(data or {}))
        record = {
            "version": FORMAT_VERSION,
            "seq": seq,
            "at": time.time(),
            "kind": str(kind),
            "data": payload,
        }
        encoded = json.dumps(record, ensure_ascii=False, default=str)
        if len(encoded.encode()) > MAX_EVENT_BYTES:
            record["data"] = {"truncated": True, "preview": _clip_text(encoded)}
            encoded = json.dumps(record, ensure_ascii=False)
        flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(str(path), flags, 0o600)
        try:
            os.fchmod(fd, 0o600)
        except OSError:
            os.close(fd)
            raise
        with os.fdopen(fd, "a", encoding="utf-8") as handle:
            handle.write(encoded + "\n")
            handle.flush()
        _seq[str(path)] = seq
        return record


def start(context: RunContext, *, model: str = "", input_text: str = "") -> None:
    append(context.home, context.run_id, "run.started", {
        "run_id": context.run_id,
        "profile": context.profile,
        "source": context.source,
        "session_id": context.session_id,
        "connection_id": context.connection_id,
        "device_id": context.device_id,
        "role": context.role,
        "job_id": context.job_id,
        "workgroup_id": context.workgroup_id,
        "workspace": str(context.workspace),
        "model": model,
        "input": input_text,
    })


def register_active(context: RunContext, engine: Any) -> None:
    with _active_lock:
        _active[(context.profile, context.run_id)] = (context.connection_id, engine)


def unregister_active(context: RunContext) -> None:
    with _active_lock:
        _active.pop((context.profile, context.run_id), None)


def active(profile: str, run_id: str) -> tuple[str, Any] | None:
    with _active_lock:
        return _active.get((profile, run_id))


def active_ids(profile: str) -> set[str]:
    with _active_lock:
        return {run_id for (owner_profile, run_id) in _active if owner_profile == profile}


def finish(context: RunContext, outcome: str) -> None:
    path = run_path(context.home, context.run_id)
    try:
        append(context.home, context.run_id, "run.finished", {"outcome": outcome})
    finally:
        key = str(path)
        with _locks_guard:
            _seq.pop(key, None)
            _locks.pop(key, None)


def record_agent_event(context: RunContext, event: Any) -> None:
    if is_dataclass(event):
        data = asdict(event)
    elif isinstance(event, dict):
        data = dict(event)
    else:
        data = {"value": str(event)}
    kind = str(data.pop("kind", "event"))
    if kind in {"tool_start", "tool_end"} and isinstance(data.get("args"), dict):
        data["args"] = persisted_tool_arguments(str(data.get("name") or ""), data["args"])
    append(context.home, context.run_id, f"agent.{kind}", data)


def read(home: Path, run_id: str, *, after_seq: int = -1, limit: int = 1000) -> dict:
    path = run_path(home, run_id)
    if path.parent.is_symlink() or not path.exists() or path.is_symlink():
        raise FileNotFoundError(run_id)
    rows = []
    next_seq = after_seq
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if not isinstance(row, dict):
                continue
            try:
                seq = int(row.get("seq", -1))
            except (TypeError, ValueError):
                continue
            if seq <= after_seq:
                continue
            rows.append(row)
            next_seq = seq
            if len(rows) >= max(1, min(int(limit), 5000)):
                break
    return {"events": rows, "next_seq": next_seq}


def _first_record(path: Path) -> dict[str, Any] | None:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            try:
                return json.loads(line)
            except ValueError:
                continue
    return None


def _last_record(path: Path) -> dict[str, Any] | None:
    with path.open("rb") as handle:
        handle.seek(0, os.SEEK_END)
        end = handle.tell()
        start = max(0, end - MAX_EVENT_BYTES - 2)
        handle.seek(start)
        lines = handle.read().splitlines()
    if start > 0 and lines:
        lines = lines[1:]
    for line in reversed(lines):
        try:
            return json.loads(line)
        except ValueError:
            continue
    return None


def summary(home: Path, run_id: str) -> dict:
    path = run_path(home, run_id)
    if path.parent.is_symlink() or not path.exists() or path.is_symlink():
        raise FileNotFoundError(run_id)
    first = _first_record(path)
    last = _last_record(path)
    if (
        not isinstance(first, dict) or not isinstance(last, dict)
        or first.get("kind") != "run.started"
    ):
        raise ValueError(f"invalid run journal: {run_id}")
    try:
        count = int(last.get("seq")) + 1
        started_at = float(first.get("at"))
        updated_at = float(last.get("at"))
    except (TypeError, ValueError):
        raise ValueError(f"invalid run journal: {run_id}") from None
    if count < 1 or not math.isfinite(started_at) or not math.isfinite(updated_at):
        raise ValueError(f"invalid run journal: {run_id}")
    final = last if last.get("kind") == "run.finished" else None
    start_data = first.get("data") or {}
    if not isinstance(start_data, dict):
        raise ValueError(f"invalid run journal: {run_id}")
    final_data = (final or {}).get("data") or {}
    if not isinstance(final_data, dict):
        raise ValueError(f"invalid run journal: {run_id}")
    return {
        "id": run_id,
        "started_at": started_at,
        "updated_at": updated_at,
        "status": final_data.get("outcome") or "running",
        "profile": start_data.get("profile") or "default",
        "source": start_data.get("source") or "user",
        "session_id": start_data.get("session_id"),
        "connection_id": start_data.get("connection_id") or "host",
        "device_id": start_data.get("device_id"),
        "job_id": start_data.get("job_id"),
        "workgroup_id": start_data.get("workgroup_id"),
        "model": start_data.get("model") or "",
        "event_count": count,
    }


def list_runs(home: Path, *, limit: int = 50) -> list[dict]:
    directory = home / "runs"
    if not directory.exists() or directory.is_symlink():
        return []
    dated_paths = []
    try:
        candidates = directory.glob("*.jsonl")
        for path in candidates:
            try:
                if not path.is_symlink():
                    dated_paths.append((path.stat().st_mtime, path))
            except OSError:
                continue
    except OSError:
        return []
    paths = [
        path for _mtime, path in sorted(
            dated_paths, key=lambda item: (item[0], item[1].name), reverse=True,
        )
    ]
    rows = []
    for path in paths[: max(1, min(int(limit), MAX_LIST_LIMIT))]:
        try:
            rows.append(summary(home, path.stem))
        except (OSError, ValueError):
            continue
    return rows


__all__ = [
    "FORMAT_VERSION", "MAX_EVENT_BYTES", "MAX_LIST_LIMIT", "active", "active_ids", "append", "finish",
    "persisted_tool_arguments",
    "list_runs", "read", "record_agent_event", "run_path", "start", "summary",
    "register_active", "unregister_active",
]
