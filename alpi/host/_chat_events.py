from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

# Per-turn replay sidecar so a desktop client whose stream socket dies mid-stream can backfill on reconnect. session.json is only written after the turn completes — until then, every delta lived only on the dropped socket.

_EVENTS_PREFIX = "_events_"
_EVENTS_SUFFIX = ".jsonl"
_HEARTBEAT_KIND = "heartbeat"
_MAX_FRAME_BYTES = 32 * 1024
_MAX_TEXT_FIELD_BYTES = 8 * 1024

_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()
_seq_state: dict[str, int] = {}


def _file_for(home: Path, session_id: str) -> Path:
    return home / "sessions" / f"{_EVENTS_PREFIX}{session_id}{_EVENTS_SUFFIX}"


def _key(home: Path, session_id: str) -> str:
    return f"{home}|{session_id}"


def _lock_for(home: Path, session_id: str) -> threading.Lock:
    k = _key(home, session_id)
    with _locks_guard:
        lk = _locks.get(k)
        if lk is None:
            lk = threading.Lock()
            _locks[k] = lk
        return lk


def reset_for_turn(
    home: Path, session_id: str, request_id: str, connection_id: str = "host",
) -> None:
    """Truncate sidecar so a new turn starts fresh.

    Each turn is its own replay window — older turns are already in session.json.
    """
    path = _file_for(home, session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _lock_for(home, session_id):
        key = _key(home, session_id)
        _seq_state[key] = 0
        try:
            path.write_text(
                json.dumps({
                    "kind": "turn_start",
                    "seq": 0,
                    "ts": time.time(),
                    "request_id": request_id,
                    "connection_id": connection_id,
                }) + "\n",
                encoding="utf-8",
            )
        except OSError:
            pass


def append(
    home: Path,
    session_id: str,
    request_id: str,
    frame: dict[str, Any],
) -> int:
    """Persist a single chat frame to the sidecar. Returns the assigned seq."""
    path = _file_for(home, session_id)
    key = _key(home, session_id)
    with _lock_for(home, session_id):
        payload = json.dumps(frame, default=str)
        if len(payload) > _MAX_FRAME_BYTES:
            # Truncate text-bearing fields to keep replay log bounded.
            clipped = dict(frame)
            for k in ("text", "output"):
                if isinstance(clipped.get(k), str):
                    clipped[k] = _clip_text(clipped[k], _MAX_TEXT_FIELD_BYTES)
            payload = json.dumps(clipped, default=str)
        seq = _seq_state.get(key, 0) + 1
        _seq_state[key] = seq
        record = json.dumps({
            "seq": seq,
            "ts": time.time(),
            "request_id": request_id,
            "frame": json.loads(payload),
        })
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(record + "\n")
        except OSError:
            pass
        return seq


def _clip_text(text: str, max_bytes: int) -> str:
    raw = text.encode("utf-8", errors="replace")
    if len(raw) <= max_bytes:
        return text
    suffix = "…".encode("utf-8")
    head = raw[: max(0, max_bytes - len(suffix))]
    return head.decode("utf-8", errors="ignore") + "…"


def heartbeat(home: Path, session_id: str, request_id: str) -> int:
    """Write a heartbeat record so a stalled client can tell the daemon is alive."""
    return append(
        home,
        session_id,
        request_id,
        {"event": _HEARTBEAT_KIND, "ts_ms": int(time.time() * 1000)},
    )


def read_since(
    home: Path,
    session_id: str,
    after_seq: int = 0,
    limit: int = 1000,
) -> dict[str, Any]:
    """Return frames with seq > after_seq from the sidecar, oldest first."""
    path = _file_for(home, session_id)
    if not path.exists():
        return {"events": [], "next_seq": after_seq, "exists": False}
    events: list[dict[str, Any]] = []
    last_seq = after_seq
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                seq = int(rec.get("seq") or 0)
                if seq <= after_seq:
                    last_seq = max(last_seq, seq)
                    continue
                events.append(rec)
                last_seq = seq
                if len(events) >= limit:
                    break
    except OSError:
        return {"events": [], "next_seq": after_seq, "exists": False}
    return {"events": events, "next_seq": last_seq, "exists": True}


def connection_id(home: Path, session_id: str) -> str | None:
    path = _file_for(home, session_id)
    try:
        with path.open("r", encoding="utf-8") as fh:
            first = json.loads(fh.readline())
    except (OSError, ValueError):
        return None
    value = first.get("connection_id") if isinstance(first, dict) else None
    return str(value) if value else None


def purge(home: Path, session_id: str) -> None:
    path = _file_for(home, session_id)
    with _lock_for(home, session_id):
        _seq_state.pop(_key(home, session_id), None)
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            pass


__all__ = ["append", "connection_id", "heartbeat", "read_since", "reset_for_turn", "purge"]
