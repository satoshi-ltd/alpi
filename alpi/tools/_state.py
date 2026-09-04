"""Tool-state emitter — ContextVar-backed so parallel sub-agents don't race."""

from __future__ import annotations

import os
import threading
import uuid
from contextvars import ContextVar
from typing import Callable, Optional

EmitFn = Callable[[str, bool], None]
InterruptFn = Callable[[], bool]
# (input, output, cost_usd, cached, cache_discount, cost_source)
UsageFn = Callable[[int, int, float, "int | None", "float | None", "str | None"], None]

_emit: ContextVar[Optional[EmitFn]] = ContextVar("alpi_emit", default=None)
_interrupt_getter: ContextVar[Optional[InterruptFn]] = ContextVar(
    "alpi_interrupt", default=None,
)
_usage_sink: ContextVar[Optional[UsageFn]] = ContextVar("alpi_usage", default=None)
# Per-turn running tally for tools that need live spend.
_turn_usage: ContextVar[Optional[dict]] = ContextVar("alpi_turn_usage", default=None)
_declared_turn_usage: ContextVar[Optional[dict]] = ContextVar(
    "alpi_declared_turn_usage", default=None,
)
_turn_tools_run: ContextVar[int] = ContextVar("alpi_turn_tools_run", default=0)
_turn_counters: ContextVar[Optional[dict[str, int]]] = ContextVar(
    "alpi_turn_counters", default=None,
)
_turn_id: ContextVar[str] = ContextVar("alpi_turn_id", default="")
_active_skills_env: ContextVar[Optional[set]] = ContextVar(
    "alpi_active_skills_env", default=None,
)
# Current-turn attachments ({name, path, mime}); runtime-only, never persisted.
_turn_attachments: ContextVar[Optional[list]] = ContextVar(
    "alpi_turn_attachments", default=None,
)


def get_emit() -> Optional[EmitFn]:
    return _emit.get()


def set_emit(callback: Optional[EmitFn]) -> None:
    _emit.set(callback)


def get_interrupt_getter() -> Optional[InterruptFn]:
    return _interrupt_getter.get()


def set_interrupt_getter(getter: Optional[InterruptFn]) -> None:
    _interrupt_getter.set(getter)


def is_interrupted() -> bool:
    g = _interrupt_getter.get()
    if g is None:
        return False
    try:
        return bool(g())
    except Exception:
        return False


def get_usage_sink() -> Optional[UsageFn]:
    return _usage_sink.get()


def set_usage_sink(sink: Optional[UsageFn]) -> None:
    _usage_sink.set(sink)


def record_usage(
    input_tokens: int, output_tokens: int, cost_usd: float,
    cached_input_tokens: int | None = None,
    cache_discount: float | None = None,
    cost_source: str | None = None,
) -> None:
    sink = _usage_sink.get()
    if sink is not None:
        try:
            sink(
                int(input_tokens), int(output_tokens), float(cost_usd),
                cached_input_tokens, cache_discount, cost_source,
            )
        except Exception:
            pass
    try:
        bump_turn_usage(input_tokens, output_tokens, cost_usd, cached_input_tokens)
    except Exception:  # noqa: BLE001
        pass


_tally_lock = threading.Lock()


def reset_turn_usage() -> None:
    """Start a fresh per-turn usage tally."""
    _turn_usage.set({
        "tokens_in": 0, "tokens_out": 0, "usd": 0.0,
        "cached_in": 0, "measured_in": 0,
    })
    _declared_turn_usage.set({
        "tokens_in": 0, "tokens_out": 0, "usd": 0.0,
        "cached_in": 0, "measured_in": 0,
    })
    _turn_counters.set({})
    _turn_tools_run.set(0)
    _turn_id.set(os.environ.get("ALPI_WORKGROUP_TURN_ID") or uuid.uuid4().hex)


def set_turn_tools_run(count: int) -> None:
    _turn_tools_run.set(int(count))


def get_turn_tools_run() -> int:
    return _turn_tools_run.get()


def get_turn_usage() -> Optional[dict]:
    """Snapshot of the current turn's tokens + USD cost."""
    tally = _turn_usage.get()
    if tally is None:
        return None
    with _tally_lock:
        return dict(tally)


def get_undeclared_turn_usage() -> tuple[Optional[dict], Optional[dict]]:
    """Return the pending usage delta and the absolute snapshot it came from."""
    tally = _turn_usage.get()
    declared = _declared_turn_usage.get()
    if tally is None or declared is None:
        return None, None
    with _tally_lock:
        snapshot = dict(tally)
        delta = {
            "tokens_in": max(
                0,
                int(snapshot.get("tokens_in", 0))
                - int(declared.get("tokens_in", 0)),
            ),
            "tokens_out": max(
                0,
                int(snapshot.get("tokens_out", 0))
                - int(declared.get("tokens_out", 0)),
            ),
            "usd": max(
                0.0,
                float(snapshot.get("usd", 0.0))
                - float(declared.get("usd", 0.0)),
            ),
            "cached_in": max(
                0,
                int(snapshot.get("cached_in", 0))
                - int(declared.get("cached_in", 0)),
            ),
            "measured_in": max(
                0,
                int(snapshot.get("measured_in", 0))
                - int(declared.get("measured_in", 0)),
            ),
        }
    return delta, snapshot


def mark_turn_usage_declared(snapshot: Optional[dict]) -> None:
    """Advance the declaration baseline to an accepted post's snapshot."""
    declared = _declared_turn_usage.get()
    if declared is None or snapshot is None:
        return
    with _tally_lock:
        for key in ("tokens_in", "tokens_out", "cached_in", "measured_in"):
            declared[key] = max(int(declared.get(key, 0)), int(snapshot.get(key, 0)))
        declared["usd"] = max(
            float(declared.get("usd", 0.0)), float(snapshot.get("usd", 0.0)),
        )


def get_turn_id() -> str:
    return _turn_id.get()


def spend_turn_counter(name: str, limit: int) -> int | None:
    counters = _turn_counters.get()
    if counters is None:
        counters = {}
        _turn_counters.set(counters)
    with _tally_lock:
        spent = int(counters.get(name, 0))
        if spent >= limit:
            return None
        spent += 1
        counters[name] = spent
        return spent


def get_turn_usage_ref() -> Optional[dict]:
    """Live tally dict for cross-thread adoption — worker threads get a fresh ContextVar copy, so research/delegate must re-bind the parent's dict or their spend never reaches the turn tally."""
    return _turn_usage.get()


def adopt_turn_usage(tally: Optional[dict]) -> None:
    _turn_usage.set(tally)


def bump_turn_usage(
    input_tokens: int, output_tokens: int, cost_usd: float,
    cached_input_tokens: int | None = None,
) -> None:
    """``cached_input_tokens=None`` = unreported; never coerce to 0, which is a measured miss."""
    tally = _turn_usage.get()
    if tally is None:
        return
    with _tally_lock:
        tally["tokens_in"] = int(tally.get("tokens_in", 0)) + int(input_tokens)
        tally["tokens_out"] = int(tally.get("tokens_out", 0)) + int(output_tokens)
        tally["usd"] = float(tally.get("usd", 0.0)) + float(cost_usd)
        if cached_input_tokens is not None:
            tally["cached_in"] = int(tally.get("cached_in", 0)) + int(cached_input_tokens)
            tally["measured_in"] = int(tally.get("measured_in", 0)) + int(input_tokens)


def reset_skill_env() -> None:
    _active_skills_env.set(set())


def add_skill_env(names: list[str]) -> None:
    if not names:
        return
    current = _active_skills_env.get()
    if current is None:
        current = set()
        _active_skills_env.set(current)
    for n in names:
        if isinstance(n, str) and n.strip():
            current.add(n.strip())


def get_active_skills_env() -> set[str]:
    current = _active_skills_env.get()
    return set(current) if current else set()


def reset_turn_attachments() -> None:
    _turn_attachments.set([])


def set_turn_attachments(items: Optional[list]) -> None:
    _turn_attachments.set(list(items) if items else [])


def get_turn_attachments() -> list:
    return list(_turn_attachments.get() or [])


def emit_state(label: str, *, error: bool = False) -> None:
    cb = _emit.get()
    if cb is not None:
        try:
            cb(label, error)
        except Exception:
            pass
