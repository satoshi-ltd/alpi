"""GW.1 — per profile + platform circuit breaker.

Each gateway platform (telegram, imap, gmail, matrix) reports success/failure
to the shared ``BreakerStore`` after every tick. After ``FAILURE_THRESHOLD``
consecutive errors the platform is marked ``disabled`` and the next tick is
held until ``disabled_until`` passes. The backoff doubles each cycle from
``BACKOFF_BASE`` up to ``BACKOFF_CAP``. A successful tick resets the counter
and restores ``healthy``.

State is per-profile: ``<home>/gateway/.breaker-state.json``. State
transitions emit ``gateway.state`` host events so desktop / mobile can
render platform status live.
"""

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import Any


FAILURE_THRESHOLD = 5
BACKOFF_BASE_S = 5 * 60.0
BACKOFF_CAP_S = 60 * 60.0

VALID_STATUS = ("healthy", "degraded", "disabled")
SCHEMA_VERSION = 1


@dataclass
class PlatformState:
    status: str = "healthy"
    consecutive_failures: int = 0
    last_error: str = ""
    last_error_at: float = 0.0
    last_success_at: float = 0.0
    disabled_until: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "consecutive_failures": int(self.consecutive_failures),
            "last_error": self.last_error,
            "last_error_at": float(self.last_error_at),
            "last_success_at": float(self.last_success_at),
            "disabled_until": float(self.disabled_until),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "PlatformState":
        out = cls()
        if not isinstance(d, dict):
            return out
        status = str(d.get("status") or "healthy")
        if status not in VALID_STATUS:
            status = "healthy"
        out.status = status
        try:
            out.consecutive_failures = int(d.get("consecutive_failures") or 0)
        except (TypeError, ValueError):
            out.consecutive_failures = 0
        out.last_error = str(d.get("last_error") or "")
        for key in ("last_error_at", "last_success_at", "disabled_until"):
            try:
                setattr(out, key, float(d.get(key) or 0.0))
            except (TypeError, ValueError):
                setattr(out, key, 0.0)
        return out


def _backoff_seconds(consecutive_failures: int) -> float:
    """Exponential backoff after the threshold: 5min, 10, 20, 40, 60 (capped)."""
    excess = max(0, consecutive_failures - FAILURE_THRESHOLD)
    secs = BACKOFF_BASE_S * (2 ** excess)
    return min(secs, BACKOFF_CAP_S)


class BreakerStore:
    """Thread-safe per-profile breaker state. One instance per daemon process; both async loops and the doctor read the same on-disk file but go through the in-memory cache when available."""

    def __init__(self, home: Path) -> None:
        self.home = home
        self._lock = Lock()
        self._states: dict[str, PlatformState] = {}
        self._loaded = False

    @property
    def path(self) -> Path:
        return self.home / "gateway" / ".breaker-state.json"

    def _load_locked(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(raw, dict) or raw.get("v") != SCHEMA_VERSION:
            return
        platforms = raw.get("platforms")
        if not isinstance(platforms, dict):
            return
        for name, payload in platforms.items():
            self._states[str(name)] = PlatformState.from_dict(payload or {})

    def _persist_locked(self) -> None:
        payload = {
            "v": SCHEMA_VERSION,
            "platforms": {n: s.to_dict() for n, s in self._states.items()},
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        suffix = f".tmp.{os.getpid()}.{threading.get_ident()}"
        tmp = self.path.with_suffix(self.path.suffix + suffix)
        tmp.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
        tmp.replace(self.path)

    def state_of(self, platform: str) -> PlatformState:
        with self._lock:
            self._load_locked()
            return PlatformState.from_dict(
                self._states.get(platform, PlatformState()).to_dict()
            )

    def all_states(self) -> dict[str, PlatformState]:
        with self._lock:
            self._load_locked()
            return {
                n: PlatformState.from_dict(s.to_dict())
                for n, s in self._states.items()
            }

    def should_skip(self, platform: str, *, now: float | None = None) -> bool:
        """True when the platform is in cooldown — caller should sleep and re-tick later instead of hitting the upstream service."""
        nowt = now if now is not None else time.time()
        st = self.state_of(platform)
        if st.status != "disabled":
            return False
        return nowt < st.disabled_until

    def record_success(self, platform: str, *, now: float | None = None) -> tuple[str, str]:
        """Returns the (previous_status, new_status) tuple. Use to decide whether to emit a ``gateway.state`` transition event.

        Already-healthy platforms early-return without persisting — Telegram polls every ~30s and IMAP/Gmail every minute; persisting on each tick would churn disk for no behavioral change. ``last_success_at`` is updated in memory only; if you need it accurate across daemon restarts, treat the file as best-effort observability data.
        """
        nowt = now if now is not None else time.time()
        with self._lock:
            self._load_locked()
            prev = self._states.get(platform)
            if (prev is not None
                    and prev.status == "healthy"
                    and prev.consecutive_failures == 0
                    and not prev.last_error
                    and prev.disabled_until == 0.0):
                prev.last_success_at = nowt
                return ("healthy", "healthy")
            new = PlatformState(
                status="healthy",
                consecutive_failures=0,
                last_error="",
                last_error_at=0.0,
                last_success_at=nowt,
                disabled_until=0.0,
            )
            previous_status = prev.status if prev else "healthy"
            self._states[platform] = new
            self._persist_locked()
            return previous_status, new.status

    def record_failure(
        self, platform: str, error: str, *, now: float | None = None,
    ) -> tuple[str, str]:
        nowt = now if now is not None else time.time()
        with self._lock:
            self._load_locked()
            prev = self._states.get(platform, PlatformState())
            new = PlatformState(
                status=prev.status,
                consecutive_failures=prev.consecutive_failures + 1,
                last_error=str(error or "")[:300],
                last_error_at=nowt,
                last_success_at=prev.last_success_at,
                disabled_until=prev.disabled_until,
            )
            if new.consecutive_failures >= FAILURE_THRESHOLD:
                new.status = "disabled"
                new.disabled_until = nowt + _backoff_seconds(new.consecutive_failures)
            elif new.consecutive_failures > 0:
                new.status = "degraded"
            self._states[platform] = new
            self._persist_locked()
            return prev.status, new.status

    def reset(self, platform: str) -> None:
        """Force-clear state (manual recovery from CLI/host)."""
        with self._lock:
            self._load_locked()
            if platform in self._states:
                del self._states[platform]
                self._persist_locked()


_singleton_lock = Lock()
_singletons: dict[str, BreakerStore] = {}


def for_home(home: Path) -> BreakerStore:
    """One BreakerStore per home so async tasks share state without races. Resolved by stringified absolute path so the same home gives the same store across modules."""
    key = str(home.resolve())
    with _singleton_lock:
        store = _singletons.get(key)
        if store is None:
            store = BreakerStore(home)
            _singletons[key] = store
        return store


def emit_state_event(
    home: Path, platform: str, previous: str, current: str,
    *, reason: str = "", disabled_until: float = 0.0,
) -> None:
    """Best-effort emit of ``gateway.state`` on transitions. Silent on import failure so a missing host module never breaks the gateway loop."""
    if previous == current:
        return
    try:
        from alpi.home import profile_name
        from alpi.host import events as host_events
        host_events.emit("gateway.state", {
            "profile": profile_name(home),
            "platform": platform,
            "previous": previous,
            "status": current,
            "reason": reason[:300] if reason else "",
            "disabled_until": float(disabled_until or 0.0),
        })
    except Exception:  # noqa: BLE001
        pass


__all__ = [
    "BACKOFF_BASE_S",
    "BACKOFF_CAP_S",
    "BreakerStore",
    "FAILURE_THRESHOLD",
    "PlatformState",
    "VALID_STATUS",
    "emit_state_event",
    "for_home",
]
