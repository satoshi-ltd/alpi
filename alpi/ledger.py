"""Daily spending ledger — profile cap gate.

Single source of truth for budget enforcement: interactive TUI, gateway,
scheduler, sub-agents, and inbound ALP all admit through ``check()`` and
record through ``record()``. ``by_peer`` buckets are observability only.
File: ``~/.alpi/<profile>/logs/ledger.json``; resets at UTC midnight via
the ``day`` field — stale day wipes the counters on next load.
"""

from __future__ import annotations

import json
import logging
import threading
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


log = logging.getLogger("alpi.ledger")
INTERACTIVE_BUCKET = "__interactive__"


class BudgetExceeded(Exception):
    """Raised when a check would push usage past the profile cap."""

    def __init__(self, cap_kind: str, cap: float, used: float) -> None:
        if cap_kind == "usd":
            shape = f"${used:.4f} / ${cap:.2f}"
        else:
            shape = f"{int(used):,} / {int(cap):,} tokens"
        super().__init__(
            f"Daily budget reached ({shape}). Resets at UTC midnight — "
            f"raise the cap in `alpi setup → Budget` if you need more."
        )
        self.cap_kind = cap_kind
        self.cap = cap
        self.used = used


_peer_ctx: ContextVar[str | None] = ContextVar("ledger_peer_id", default=None)
_lock = threading.Lock()


@contextmanager
def peer_context(peer_id: str | None):
    """Route ``record()`` into ``peer_id`` instead of ``__interactive__``."""
    token = _peer_ctx.set(peer_id)
    try:
        yield
    finally:
        _peer_ctx.reset(token)


def _today_utc() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _path(home: Path) -> Path:
    return home / "logs" / "ledger.json"


def _blank(day: str) -> dict[str, Any]:
    return {
        "day": day,
        "profile": {"usd": 0.0, "tokens": 0},
        "by_peer": {},
    }


def load(home: Path) -> dict[str, Any]:
    """Return today's ledger, rolling over (or creating fresh) on a stale or
    corrupt file rather than letting it brick the profile."""
    today = _today_utc()
    p = _path(home)
    if not p.exists():
        return _blank(today)
    try:
        data = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return _blank(today)
    if not isinstance(data, dict) or data.get("day") != today:
        return _blank(today)
    data.setdefault("profile", {"usd": 0.0, "tokens": 0})
    data.setdefault("by_peer", {})
    return data


def save(home: Path, data: dict[str, Any]) -> None:
    p = _path(home)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    try:
        tmp.write_text(json.dumps(data, separators=(",", ":"), sort_keys=True))
        tmp.replace(p)
    except OSError as e:
        # Budget accounting must not crash a live turn under FD pressure.
        log.warning("ledger save dropped: %s", e)
        try:
            tmp.unlink()
        except OSError:
            pass


def _budget(cfg_budget: dict[str, Any] | None) -> tuple[str | None, float]:
    """``daily_usd`` wins when both are set; ``(None, 0)`` means uncapped."""
    budget = cfg_budget or {}
    usd = budget.get("daily_usd")
    if isinstance(usd, (int, float)) and usd > 0:
        return "usd", float(usd)
    tokens = budget.get("daily_tokens")
    if isinstance(tokens, int) and tokens > 0:
        return "tokens", float(tokens)
    return None, 0.0


def check(home: Path, cfg_budget: dict[str, Any] | None) -> None:
    """Raise ``BudgetExceeded`` if the profile is at or past cap; no-op if uncapped."""
    kind, cap = _budget(cfg_budget)
    if kind is None:
        return
    with _lock:
        data = load(home)
    used = float(data["profile"].get(kind, 0))
    if used >= cap:
        raise BudgetExceeded(kind, cap, used)


def record(home: Path, *, usd: float, tokens: int) -> None:
    """Add today's spend to the profile total and the current peer bucket
    (clamped to zero — a mis-signed report must not rewind the ledger)."""
    if usd <= 0 and tokens <= 0:
        return
    peer_id = _peer_ctx.get() or INTERACTIVE_BUCKET
    with _lock:
        data = load(home)
        profile = data.setdefault("profile", {"usd": 0.0, "tokens": 0})
        profile["usd"] = float(profile.get("usd", 0)) + max(0.0, float(usd))
        profile["tokens"] = int(profile.get("tokens", 0)) + max(0, int(tokens))
        buckets = data.setdefault("by_peer", {})
        bucket = buckets.setdefault(peer_id, {"usd": 0.0, "tokens": 0})
        bucket["usd"] = float(bucket.get("usd", 0)) + max(0.0, float(usd))
        bucket["tokens"] = int(bucket.get("tokens", 0)) + max(0, int(tokens))
        save(home, data)


def snapshot(home: Path) -> dict[str, Any]:
    return load(home)


def status_line(home: Path, cfg_budget: dict[str, Any] | None) -> str:
    """``used / cap`` value for the ``daily budget`` row (TUI + Telegram)."""
    data = load(home)
    prof = data.get("profile", {"usd": 0.0, "tokens": 0})
    used_usd = float(prof.get("usd", 0))
    used_tokens = int(prof.get("tokens", 0))
    kind, cap = _budget(cfg_budget)
    if kind is None:
        return f"${used_usd:.4f} · {used_tokens:,} tokens · no cap"
    if kind == "usd":
        suffix = " · capped" if used_usd >= cap else ""
        return f"${used_usd:.4f} / ${cap:.2f}{suffix}"
    suffix = " · capped" if used_tokens >= cap else ""
    return f"{used_tokens:,} / {int(cap):,} tokens{suffix}"
