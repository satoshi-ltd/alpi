"""Tool-state emitter — ContextVar-backed so parallel sub-agents don't race."""

from __future__ import annotations

from contextvars import ContextVar
from typing import Callable, Optional

EmitFn = Callable[[str, bool], None]
InterruptFn = Callable[[], bool]
UsageFn = Callable[[int, int, float], None]

_emit: ContextVar[Optional[EmitFn]] = ContextVar("alpi_emit", default=None)
_interrupt_getter: ContextVar[Optional[InterruptFn]] = ContextVar(
    "alpi_interrupt", default=None,
)
_usage_sink: ContextVar[Optional[UsageFn]] = ContextVar("alpi_usage", default=None)
# Per-turn running tally for tools that need live spend.
_turn_usage: ContextVar[Optional[dict]] = ContextVar("alpi_turn_usage", default=None)
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
) -> None:
    sink = _usage_sink.get()
    if sink is not None:
        try:
            sink(int(input_tokens), int(output_tokens), float(cost_usd))
        except Exception:
            pass
    try:
        bump_turn_usage(input_tokens, output_tokens, cost_usd, cached_input_tokens)
    except Exception:  # noqa: BLE001
        pass


def reset_turn_usage() -> None:
    """Start a fresh per-turn usage tally."""
    _turn_usage.set({
        "tokens_in": 0, "tokens_out": 0, "usd": 0.0,
        "cached_in": 0, "measured_in": 0,
    })


def get_turn_usage() -> Optional[dict]:
    """Snapshot of the current turn's tokens + USD cost."""
    tally = _turn_usage.get()
    return dict(tally) if tally is not None else None


def bump_turn_usage(
    input_tokens: int, output_tokens: int, cost_usd: float,
    cached_input_tokens: int | None = None,
) -> None:
    """``cached_input_tokens=None`` = unreported; never coerce to 0, which is a measured miss."""
    tally = _turn_usage.get()
    if tally is None:
        return
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
