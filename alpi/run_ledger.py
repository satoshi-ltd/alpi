from __future__ import annotations

import contextlib
import json
import os
import re
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None

MAX_RUNS = 1000
TAIL_CAP = 280

KINDS = frozenset({"agent", "schedule", "workgroup", "terminal"})
OUTCOMES = frozenset({"ok", "error", "timeout", "interrupted"})

SLOW_THRESHOLDS = {"agent": 120.0, "workgroup": 120.0, "schedule": 120.0, "terminal": 30.0}

_lock = threading.Lock()

_SECRET_RE = re.compile(
    r"(?i)\b(authorization|bearer|basic|tokens?|api[-_]?keys?|access[-_]?keys?"
    r"|secrets?|passwords?|passwd|pwd)\b(\s*[:=]\s*|\s+)(?:(bearer|basic)\s+)?(\S+)"
)
_BLOB_RE = re.compile(r"\b(?=[A-Za-z0-9_\-]*[0-9])[A-Za-z0-9_\-]{32,}\b")


def _mask_secret(m: re.Match) -> str:
    scheme = f"{m.group(3)} " if m.group(3) else ""
    return f"{m.group(1)}{m.group(2)}{scheme}***"


@dataclass
class RunRecord:
    at: float
    kind: str
    outcome: str
    elapsed_s: float
    profile: str = "default"
    session_id: str | None = None
    job_id: str | None = None
    workgroup_id: str | None = None
    peer_id: str | None = None
    pid: int | None = None
    backend: str | None = None
    exit_code: int | None = None
    timeout_reason: str | None = None
    last_tool: str | None = None
    tool_count: int | None = None
    output_tail: str | None = None
    model: str | None = None
    routing: str | None = None
    connection_id: str = "host"
    device_id: str | None = None
    source: str = "host"


def store_path(home: Path) -> Path:
    return home / "logs" / "runs.jsonl"


def _redact(text: str) -> str:
    text = _SECRET_RE.sub(_mask_secret, text)
    return _BLOB_RE.sub("***", text)


def _clamp_tail(text: str | None) -> str | None:
    if not text:
        return None
    flat = _redact(" ".join(str(text).split()))
    if len(flat) > TAIL_CAP:
        return "…" + flat[-(TAIL_CAP - 1):]
    return flat


def record(
    home: Path,
    *,
    kind: str,
    outcome: str,
    elapsed_s: float,
    at: float | None = None,
    profile: str = "default",
    session_id: str | None = None,
    job_id: str | None = None,
    workgroup_id: str | None = None,
    peer_id: str | None = None,
    pid: int | None = None,
    backend: str | None = None,
    exit_code: int | None = None,
    timeout_reason: str | None = None,
    last_tool: str | None = None,
    tool_count: int | None = None,
    output_tail: str | None = None,
    model: str | None = None,
    routing: str | None = None,
) -> None:
    # Best-effort: coercions are inside the try so a malformed caller value can't escape.
    try:
        from alpi.host.connection_context import current
        connection = current()
        rec = RunRecord(
            at=float(at if at is not None else time.time()),
            kind=kind if kind in KINDS else "agent",
            outcome=outcome if outcome in OUTCOMES else "error",
            elapsed_s=round(float(elapsed_s), 3),
            profile=profile or "default",
            session_id=session_id or None,
            job_id=job_id or None,
            workgroup_id=workgroup_id or None,
            peer_id=peer_id or None,
            pid=int(pid) if pid is not None else None,
            backend=backend or None,
            exit_code=int(exit_code) if exit_code is not None else None,
            timeout_reason=timeout_reason or None,
            last_tool=last_tool or None,
            tool_count=int(tool_count) if tool_count is not None else None,
            output_tail=_clamp_tail(output_tail),
            model=model or None,
            routing=routing or None,
            connection_id=connection.connection_id,
            device_id=connection.device_id,
            source=connection.source,
        )
        path = store_path(home)
        with _lock, _interproc_lock(path):
            rows = _read_all(path)
            rows.append(asdict(rec))
            if len(rows) > MAX_RUNS:
                rows = rows[-MAX_RUNS:]
            _atomic_rewrite(path, rows)
    except Exception:  # noqa: BLE001
        pass


def read(home: Path, *, kind: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    rows = _read_all(store_path(home))
    if kind is not None:
        rows = [r for r in rows if r.get("kind") == kind]
    rows.reverse()
    if limit and limit > 0:
        rows = rows[:limit]
    return rows


def _is_slow(row: dict[str, Any]) -> bool:
    threshold = SLOW_THRESHOLDS.get(row.get("kind"), 120.0)
    try:
        return float(row.get("elapsed_s") or 0.0) > threshold
    except (TypeError, ValueError):
        return False


def summarize(home: Path, *, limit: int = 50) -> dict[str, Any]:
    rows = read(home, limit=0)  # limit=0 = no cap (all rows), most-recent-first
    by_kind: dict[str, int] = {}
    by_outcome: dict[str, int] = {}
    for r in rows:
        k, o = r.get("kind", "?"), r.get("outcome", "?")
        by_kind[k] = by_kind.get(k, 0) + 1
        by_outcome[o] = by_outcome.get(o, 0) + 1
    problematic = [r for r in rows if r.get("outcome") != "ok"][:limit]
    slow = [r for r in rows if _is_slow(r)][:limit]
    return {
        "total": len(rows),
        "counts": {"by_kind": by_kind, "by_outcome": by_outcome},
        "recent": rows[:limit],
        "problematic": problematic,
        "slow": slow,
    }


@contextlib.contextmanager
def _interproc_lock(path: Path):
    # Serializes the read+rewrite across scheduler / chat-child / terminal processes.
    if fcntl is None:
        yield
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.parent / (path.name + ".lock")
    f = open(lock_path, "w")
    try:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        finally:
            f.close()


def _read_all(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and obj.get("kind"):
            out.append(obj)
    return out


def _atomic_rewrite(path: Path, items: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for it in items:
                f.write(json.dumps(it, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
    except Exception:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise
    os.replace(str(tmp), str(path))


__all__ = [
    "MAX_RUNS", "OUTCOMES", "KINDS", "SLOW_THRESHOLDS",
    "RunRecord", "record", "read", "summarize", "store_path",
]
