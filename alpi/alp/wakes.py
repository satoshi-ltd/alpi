from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable

_LOCK = threading.Lock()
_CALLBACKS: dict[str, Callable[[str], None]] = {}


def register(home: Path, callback: Callable[[str], None]) -> None:
    with _LOCK:
        _CALLBACKS[str(home)] = callback


def unregister(home: Path) -> None:
    with _LOCK:
        _CALLBACKS.pop(str(home), None)


def fire(home: Path, wg_id: str) -> None:
    """Nudge the poller that owns ``home`` about fresh workgroup traffic; polling remains the recovery path when nobody is registered."""
    with _LOCK:
        cb = _CALLBACKS.get(str(home))
    if cb is None:
        return
    try:
        cb(wg_id)
    except Exception:  # noqa: BLE001
        pass
