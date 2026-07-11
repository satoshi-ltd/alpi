"""Daily spending ledger — profile cap gate.

Single source of truth for budget enforcement: interactive TUI,
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
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any


log = logging.getLogger("alpi.ledger")
INTERACTIVE_BUCKET = "__interactive__"
HISTORY_DAYS = 30


class BudgetExceeded(Exception):
    """Raised when a check would push usage past the profile cap."""

    def __init__(self, cap_kind: str, cap: float, used: float) -> None:
        super().__init__(
            f"Daily budget reached (${used:.4f} / ${cap:.2f}). Resets at UTC midnight — "
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
        "history": {},
    }


def _prune_history(history: dict[str, Any], today: str) -> dict[str, Any]:
    try:
        cutoff = date.fromisoformat(today) - timedelta(days=HISTORY_DAYS)
    except ValueError:
        return history
    out: dict[str, Any] = {}
    for d, v in history.items():
        try:
            if date.fromisoformat(d) >= cutoff:
                out[d] = v
        except (ValueError, TypeError):
            continue
    return out


def _rollover(data: dict[str, Any], today: str) -> dict[str, Any]:
    history = dict(data.get("history") or {})
    old_day = data.get("day")
    prof = data.get("profile") or {}
    if old_day and old_day != today and old_day not in history and (
        prof.get("usd") or prof.get("tokens")
    ):
        history[old_day] = {
            "usd": float(prof.get("usd", 0.0)),
            "tokens": int(prof.get("tokens", 0)),
            "tokens_in": 0,
            "tokens_out": 0,
        }
    fresh = _blank(today)
    fresh["history"] = _prune_history(history, today)
    return fresh


def load(home: Path) -> dict[str, Any]:
    """Return today's ledger, rolling over (or creating fresh) on a stale or
    corrupt file rather than letting it brick the profile. The ``history``
    map of past-day totals survives a day rollover; only the live counters
    (``profile``/``by_peer``) reset."""
    today = _today_utc()
    p = _path(home)
    if not p.exists():
        return _blank(today)
    try:
        data = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return _blank(today)
    if not isinstance(data, dict):
        return _blank(today)
    if data.get("day") != today:
        return _rollover(data, today)
    data.setdefault("profile", {"usd": 0.0, "tokens": 0})
    data.setdefault("by_peer", {})
    data.setdefault("history", {})
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
    usd = (cfg_budget or {}).get("daily_usd")
    if isinstance(usd, (int, float)) and usd > 0:
        return "usd", float(usd)
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


def record_completion(
    home: Path, completion: Any, cfg_budget: dict[str, Any] | None = None,
) -> None:
    """Ledger entry from any llm.complete-shaped object; tolerates objects missing usage fields."""
    tokens_in = int(getattr(completion, "input_tokens", 0) or 0)
    tokens_out = int(getattr(completion, "output_tokens", 0) or 0)
    usd = float(getattr(completion, "cost_usd", 0.0) or 0.0)
    record(
        home, usd=usd, tokens=tokens_in + tokens_out,
        tokens_in=tokens_in, tokens_out=tokens_out, cfg_budget=cfg_budget,
    )


def spend_fraction(home: Path, cfg_budget: dict[str, Any] | None) -> float | None:
    """Today's spend as a fraction of the daily cap; None when uncapped."""
    kind, cap = _budget(cfg_budget)
    if kind is None or cap <= 0:
        return None
    with _lock:
        data = load(home)
    return float(data["profile"].get(kind, 0)) / cap


def record(
    home: Path,
    *,
    usd: float,
    tokens: int,
    tokens_in: int = 0,
    tokens_out: int = 0,
    cfg_budget: dict[str, Any] | None = None,
) -> None:
    """Add today's spend; emits ``budget.threshold`` once per crossing (highest threshold wins if a single record vaults past both). ``tokens_in``/``tokens_out`` feed the per-day ``history`` split (best-effort: non-token spend like image generation passes ``tokens=0`` and contributes ``usd`` only)."""
    if usd <= 0 and tokens <= 0:
        return
    peer_id = _peer_ctx.get() or INTERACTIVE_BUCKET
    with _lock:
        data = load(home)
        profile = data.setdefault("profile", {"usd": 0.0, "tokens": 0})
        before_usd = float(profile.get("usd", 0))
        profile["usd"] = before_usd + max(0.0, float(usd))
        profile["tokens"] = int(profile.get("tokens", 0)) + max(0, int(tokens))
        buckets = data.setdefault("by_peer", {})
        bucket = buckets.setdefault(peer_id, {"usd": 0.0, "tokens": 0})
        bucket["usd"] = float(bucket.get("usd", 0)) + max(0.0, float(usd))
        bucket["tokens"] = int(bucket.get("tokens", 0)) + max(0, int(tokens))
        today = str(data.get("day"))
        history = data.setdefault("history", {})
        hentry = history.setdefault(
            today, {"usd": 0.0, "tokens": 0, "tokens_in": 0, "tokens_out": 0},
        )
        hentry["usd"] = float(profile["usd"])
        hentry["tokens"] = int(profile["tokens"])
        hentry["tokens_in"] = int(hentry.get("tokens_in", 0)) + max(0, int(tokens_in))
        hentry["tokens_out"] = int(hentry.get("tokens_out", 0)) + max(0, int(tokens_out))
        data["history"] = _prune_history(history, today)
        save(home, data)
        after_usd = profile["usd"]
    if cfg_budget is None:
        return
    kind, cap = _budget(cfg_budget)
    if kind != "usd" or cap <= 0:
        return
    crossed = None
    if before_usd < cap <= after_usd:
        crossed = "100"
    elif before_usd < cap * 0.8 <= after_usd:
        crossed = "80"
    if crossed is None:
        return
    try:
        from alpi.home import profile_name
        from alpi.host import events as host_events
        host_events.emit("budget.threshold", {
            "profile": profile_name(home),
            "level": crossed,
            "used_usd": round(after_usd, 4),
            "cap_usd": cap,
        })
    except Exception:  # noqa: BLE001
        pass


def snapshot(home: Path) -> dict[str, Any]:
    return load(home)


def status_line(home: Path, cfg_budget: dict[str, Any] | None) -> str:
    """``used / cap`` value for the ``daily budget`` row (TUI)."""
    data = load(home)
    prof = data.get("profile", {"usd": 0.0, "tokens": 0})
    used_usd = float(prof.get("usd", 0))
    used_tokens = int(prof.get("tokens", 0))
    kind, cap = _budget(cfg_budget)
    if kind is None:
        return f"${used_usd:.4f} · {used_tokens:,} tokens · no cap"
    suffix = " · capped" if used_usd >= cap else ""
    return f"${used_usd:.4f} / ${cap:.2f}{suffix}"
