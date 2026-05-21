"""TL.1 — cached probe layer for tool availability.

Each ``Tool`` subclass can override ``check() -> (available, reason)``.
This module caches the result briefly so the probe is cheap even when
``schemas()`` runs on every turn. ``alpi doctor`` bypasses the cache so
the operator always sees fresh state.
"""

from __future__ import annotations

import time
from threading import Lock
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from alpi.tools.base import Tool


_TTL_SECONDS = 60.0

_cache: dict[str, tuple[float, bool, str]] = {}
_lock = Lock()


def is_available(cls: type["Tool"]) -> tuple[bool, str]:
    name = cls.name
    now = time.time()
    with _lock:
        entry = _cache.get(name)
        if entry is not None and now - entry[0] < _TTL_SECONDS:
            return entry[1], entry[2]
    try:
        ok, reason = cls.check()
    except Exception as exc:  # noqa: BLE001
        ok, reason = False, f"check raised: {exc}"
    with _lock:
        _cache[name] = (now, ok, reason)
    return ok, reason


def invalidate() -> None:
    """Drop all cached probe results. Used by tests and by `alpi doctor` to force a fresh snapshot."""
    with _lock:
        _cache.clear()


__all__ = ["is_available", "invalidate"]
