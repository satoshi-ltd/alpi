from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from typing import Callable

_LOCK = threading.Lock()
_CALLBACKS: dict[str, Callable[[str], None]] = {}
_WATCHERS: dict[str, set[tuple[asyncio.AbstractEventLoop, asyncio.Event]]] = {}


def register(home: Path, callback: Callable[[str], None]) -> None:
    with _LOCK:
        _CALLBACKS[str(home)] = callback


def unregister(home: Path) -> None:
    with _LOCK:
        _CALLBACKS.pop(str(home), None)


def watch(wg_id: str, loop: asyncio.AbstractEventLoop, event: asyncio.Event) -> None:
    with _LOCK:
        _WATCHERS.setdefault(wg_id, set()).add((loop, event))


def unwatch(wg_id: str, loop: asyncio.AbstractEventLoop, event: asyncio.Event) -> None:
    with _LOCK:
        watchers = _WATCHERS.get(wg_id)
        if watchers is None:
            return
        watchers.discard((loop, event))
        if not watchers:
            _WATCHERS.pop(wg_id, None)


def fire_watchers(wg_id: str) -> None:
    with _LOCK:
        watchers = list(_WATCHERS.get(wg_id, ()))
    for loop, event in watchers:
        try:
            loop.call_soon_threadsafe(event.set)
        except RuntimeError:
            pass


def fire(home: Path, wg_id: str) -> None:
    """Nudge the poller that owns ``home`` and every local subscription worker waiting on ``wg_id``; polling stays the recovery path."""
    fire_watchers(wg_id)
    with _LOCK:
        cb = _CALLBACKS.get(str(home))
    if cb is None:
        return
    try:
        cb(wg_id)
    except Exception:  # noqa: BLE001
        pass
