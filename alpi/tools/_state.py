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


def record_usage(input_tokens: int, output_tokens: int, cost_usd: float) -> None:
    sink = _usage_sink.get()
    if sink is not None:
        try:
            sink(int(input_tokens), int(output_tokens), float(cost_usd))
        except Exception:
            pass


def emit_state(label: str, *, error: bool = False) -> None:
    cb = _emit.get()
    if cb is not None:
        try:
            cb(label, error)
        except Exception:
            pass
