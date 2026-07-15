from __future__ import annotations

import logging
import os
import threading
import time

_log = logging.getLogger("alpi.timing")
_ENABLED = os.environ.get("ALPI_TIMING", "").strip().lower() not in ("", "0", "false", "no")

_lock = threading.Lock()
_start: dict[str, float] = {}
_last: dict[str, float] = {}
_local = threading.local()


def enabled() -> bool:
    return _ENABLED


def mark(req: str, phase: str) -> None:
    if not _ENABLED or not req:
        return
    now = time.monotonic()
    with _lock:
        start = _start.setdefault(req, now)
        prev = _last.get(req, start)
        _last[req] = now
    _log.info("timing %s  %-16s +%6.0fms  (t=%7.0fms)", req, phase, (now - prev) * 1000, (now - start) * 1000)


def done(req: str) -> None:
    if not _ENABLED or not req:
        return
    with _lock:
        _start.pop(req, None)
        _last.pop(req, None)


def set_current(req: str | None) -> None:
    if not _ENABLED:
        return
    _local.req = req


def mark_current(phase: str) -> None:
    mark(getattr(_local, "req", None) or "", phase)
