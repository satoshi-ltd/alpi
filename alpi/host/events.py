from __future__ import annotations

import asyncio
import json
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any

from alpi import home as home_mod
from alpi.host import server as host_server


_lock = threading.Lock()
_subscribers: set[tuple[asyncio.Queue, frozenset[str] | None]] = set()
_loop_ref: asyncio.AbstractEventLoop | None = None

# Rolling history so clients that were offline when an event fired can backfill on
# connect via host.events.history. Bounded in memory by HISTORY_MAX; the JSONL
# sidecar is compacted every COMPACT_EVERY writes so it can't grow unboundedly
# even under hot emitters (session_changed, schedule fires, etc.).
HISTORY_MAX = 500
COMPACT_EVERY = 50

_history: deque[dict[str, Any]] = deque(maxlen=HISTORY_MAX)
_history_lock = threading.Lock()
_history_path: Path | None = None
_writes_since_compact = 0


def _history_file() -> Path:
    # register(server) sets _history_path from the daemon's Server(home=...).
    # Fall back to alpi.home._ROOT for unit tests or embedded contexts that
    # never call register() — defensive, not the happy path.
    if _history_path is not None:
        return _history_path
    return home_mod._ROOT / "host" / "events.jsonl"


def _load_history() -> None:
    path = _history_file()
    if not path.exists():
        return
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    items: list[dict[str, Any]] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and "event" in obj:
            items.append(obj)
    with _history_lock:
        _history.clear()
        for it in items[-HISTORY_MAX:]:
            _history.append(it)


def _compact_jsonl(path: Path, snapshot: list[dict[str, Any]]) -> None:
    """Atomic rewrite of the JSONL with the in-memory deque.

    Bounds the on-disk size at ~HISTORY_MAX + COMPACT_EVERY lines even under
    hot emitters. Writes via tmp+rename so a crash mid-compact never leaves
    a half-written history file.
    """
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tmp.open("w", encoding="utf-8") as f:
            for it in snapshot:
                f.write(json.dumps(it) + "\n")
        tmp.replace(path)
    except OSError:
        try:
            tmp.unlink()
        except OSError:
            pass


def _append_history(payload: dict[str, Any]) -> None:
    global _writes_since_compact
    with _history_lock:
        _history.append(payload)
        _writes_since_compact += 1
        compact_now = _writes_since_compact >= COMPACT_EVERY
        snapshot = list(_history) if compact_now else None
        if compact_now:
            _writes_since_compact = 0
    path = _history_file()
    try:
        if compact_now and snapshot is not None:
            _compact_jsonl(path, snapshot)
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload) + "\n")
    except OSError:
        # Persistence is opportunistic; never propagate from the emit path.
        pass


def register(server: host_server.Server) -> None:
    global _history_path
    _history_path = server.home / "host" / "events.jsonl"
    _load_history()
    server.register_stream("host.events.subscribe", _subscribe_handler)
    server.register("host.events.history", _history_handler)


def emit(kind: str, data: dict[str, Any] | None = None) -> None:
    payload = {"event": kind, "data": data or {}, "at": time.time()}
    _append_history(payload)
    with _lock:
        if not _subscribers or _loop_ref is None:
            return
        loop = _loop_ref
        targets = [
            q for (q, kinds) in _subscribers if kinds is None or kind in kinds
        ]
    if not targets:
        return
    for q in targets:
        loop.call_soon_threadsafe(_safe_put, q, payload)


def _safe_put(queue: asyncio.Queue, payload: dict[str, Any]) -> None:
    try:
        queue.put_nowait(payload)
    except asyncio.QueueFull:
        # Drop instead of blocking emitters.
        pass


async def _subscribe_handler(
    params: dict[str, Any], _server: host_server.Server, send_frame,
) -> None:
    global _loop_ref
    loop = asyncio.get_running_loop()
    with _lock:
        _loop_ref = loop

    kinds_param = params.get("kinds")
    kinds: frozenset[str] | None
    if isinstance(kinds_param, list) and kinds_param:
        kinds = frozenset(str(k) for k in kinds_param)
    else:
        kinds = None

    queue: asyncio.Queue = asyncio.Queue(maxsize=1024)
    entry = (queue, kinds)
    with _lock:
        _subscribers.add(entry)
    try:
        await send_frame({"event": "subscribed"})
        while True:
            payload = await queue.get()
            try:
                await send_frame(payload)
            except (ConnectionResetError, BrokenPipeError):
                return
    finally:
        with _lock:
            _subscribers.discard(entry)


async def _history_handler(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    since = params.get("since")
    since_ts = float(since) if isinstance(since, (int, float)) else None
    limit_raw = params.get("limit")
    limit = int(limit_raw) if isinstance(limit_raw, (int, float)) else HISTORY_MAX
    limit = max(1, min(limit, HISTORY_MAX))

    kinds_param = params.get("kinds")
    kinds: frozenset[str] | None
    if isinstance(kinds_param, list) and kinds_param:
        kinds = frozenset(str(k) for k in kinds_param)
    else:
        kinds = None

    with _history_lock:
        items = list(_history)
    if since_ts is not None:
        items = [it for it in items if float(it.get("at") or 0) > since_ts]
    if kinds is not None:
        items = [it for it in items if it.get("event") in kinds]
    if len(items) > limit:
        items = items[-limit:]
    return {"events": items}


__all__ = ["register", "emit"]
