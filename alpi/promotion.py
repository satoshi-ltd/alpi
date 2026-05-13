"""Memory promotion queue — staging area for facts compaction wants to durably remember.

Compaction must never write to ``MEMORY.md`` directly: a single bad summary
would otherwise pollute long-term memory. Instead it emits **candidates**
into this queue, where the operator (or the agent, with explicit confirm)
reviews each one before it lands on disk via the normal memory write path.

Storage: append-only JSONL at ``<home>/memories/promotion_queue.jsonl``.
Cap: 200 pending candidates per profile (oldest pending evicted on overflow).
Expiry: pending candidates older than ``MAX_AGE_DAYS`` are pruned on read.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


MAX_PENDING = 200
MAX_AGE_DAYS = 30
_MAX_AGE_SECONDS = MAX_AGE_DAYS * 86400


# A promotion candidate. ``id`` is a stable short hex so the agent / CLI can
# reference it without leaking session content. ``text`` is the fact itself
# in declarative English, the same shape ``memory(action="add")`` expects.
@dataclass
class Candidate:
    id: str
    created_at: float
    source: str             # "compaction" | "reviewer" | "manual"
    session_id: str
    model: str
    target: str             # "USER.md" | "MEMORY.md" | "AGENT.md"
    text: str
    confidence: str = "normal"
    warnings: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Candidate":
        return cls(
            id=str(d.get("id") or ""),
            created_at=float(d.get("created_at") or 0.0),
            source=str(d.get("source") or "manual"),
            session_id=str(d.get("session_id") or ""),
            model=str(d.get("model") or ""),
            target=str(d.get("target") or "MEMORY.md"),
            text=str(d.get("text") or ""),
            confidence=str(d.get("confidence") or "normal"),
            warnings=list(d.get("warnings") or []),
        )


def queue_path(home: Path) -> Path:
    return home / "memories" / "promotion_queue.jsonl"


def _new_id() -> str:
    return uuid.uuid4().hex[:8]


def _read_lines(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out


def _write_lines(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    text = "\n".join(json.dumps(r, separators=(",", ":")) for r in rows)
    tmp.write_text(text + ("\n" if rows else ""), encoding="utf-8")
    tmp.replace(path)


def _prune_expired(rows: list[dict], *, now: float | None = None) -> list[dict]:
    now = now if now is not None else time.time()
    return [r for r in rows if now - float(r.get("created_at") or 0.0) <= _MAX_AGE_SECONDS]


def _enforce_cap(rows: list[dict]) -> list[dict]:
    """Keep the most recent ``MAX_PENDING`` rows when over cap."""
    if len(rows) <= MAX_PENDING:
        return rows
    rows.sort(key=lambda r: float(r.get("created_at") or 0.0))
    return rows[-MAX_PENDING:]


def list_pending(home: Path, *, now: float | None = None) -> list[Candidate]:
    """Return pending candidates, oldest first. Prunes expired and rewrites if changed."""
    path = queue_path(home)
    rows = _read_lines(path)
    pruned = _prune_expired(rows, now=now)
    if len(pruned) != len(rows):
        _write_lines(path, pruned)
    pruned.sort(key=lambda r: float(r.get("created_at") or 0.0))
    return [Candidate.from_dict(r) for r in pruned]


def add(
    home: Path,
    *,
    source: str,
    session_id: str,
    model: str,
    target: str,
    text: str,
    confidence: str = "normal",
    warnings: list[str] | None = None,
) -> Candidate:
    """Append a candidate, prune expired, enforce cap. Returns the stored Candidate."""
    if target not in ("USER.md", "MEMORY.md", "AGENT.md"):
        raise ValueError(f"target must be USER.md|MEMORY.md|AGENT.md, got {target!r}")
    cand = Candidate(
        id=_new_id(),
        created_at=time.time(),
        source=source,
        session_id=session_id,
        model=model,
        target=target,
        text=text.strip(),
        confidence=confidence,
        warnings=list(warnings or []),
    )
    path = queue_path(home)
    rows = _prune_expired(_read_lines(path))
    rows.append(asdict(cand))
    rows = _enforce_cap(rows)
    _write_lines(path, rows)
    return cand


def discard(home: Path, candidate_id: str) -> bool:
    """Remove one candidate by id. Returns True if removed, False if not found."""
    path = queue_path(home)
    rows = _read_lines(path)
    kept = [r for r in rows if r.get("id") != candidate_id]
    if len(kept) == len(rows):
        return False
    _write_lines(path, kept)
    return True


def get(home: Path, candidate_id: str) -> Candidate | None:
    for cand in list_pending(home):
        if cand.id == candidate_id:
            return cand
    return None


def remove_and_return(home: Path, candidate_id: str) -> Candidate | None:
    """Pop a candidate by id; returns the Candidate or None."""
    path = queue_path(home)
    rows = _read_lines(path)
    target_row = None
    kept: list[dict] = []
    for r in rows:
        if r.get("id") == candidate_id and target_row is None:
            target_row = r
            continue
        kept.append(r)
    if target_row is None:
        return None
    _write_lines(path, kept)
    return Candidate.from_dict(target_row)


__all__ = [
    "MAX_AGE_DAYS",
    "MAX_PENDING",
    "Candidate",
    "add",
    "discard",
    "get",
    "list_pending",
    "queue_path",
    "remove_and_return",
]
