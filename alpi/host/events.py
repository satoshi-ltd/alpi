from __future__ import annotations

import asyncio
import threading
from typing import Any

from alpi.host import server as host_server


_lock = threading.Lock()
_subscribers: set[tuple[asyncio.Queue, frozenset[str] | None]] = set()
_loop_ref: asyncio.AbstractEventLoop | None = None


def register(server: host_server.Server) -> None:
    server.register_stream("host.events.subscribe", _subscribe_handler)


def emit(kind: str, data: dict[str, Any] | None = None) -> None:
    payload = {"event": kind, "data": data or {}}
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


__all__ = ["register", "emit"]
