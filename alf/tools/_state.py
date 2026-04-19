"""Tool-state emitter.

Lets a running tool push short progress labels up to the UI without changing
its ``run()`` signature. The engine wires ``set_emit`` around each tool call;
tools import ``emit_state`` and call it whenever they enter a new phase.

Example in a tool::

    from alf.tools._state import emit_state

    def run(self, url):
        emit_state("fetching…")
        body = download(url)
        emit_state("parsing…")
        return ToolResult(...)

In the engine::

    from alf.tools import _state as tool_state

    tool_state.set_emit(lambda label: emit(AgentEvent(kind="tool_state", ...)))
    try:
        result = tools.execute(name, args)
    finally:
        tool_state.set_emit(None)
"""

from __future__ import annotations

from typing import Callable, Optional

# Callback signature: (label: str, is_error: bool) -> None
_emit: Optional[Callable[[str, bool], None]] = None
# Predicate returning True if the surrounding turn has been interrupted.
# Long-running tools (e.g. delegate) poll this to exit early.
_interrupt_getter: Optional[Callable[[], bool]] = None
# Usage reporter: (input_tokens, output_tokens, cost_usd) -> None.
# Tools that spin up their own LLM calls (delegate) use this so the
# enclosing session's total cost reflects the sub-agent's burn.
_usage_sink: Optional[Callable[[int, int, float], None]] = None


def set_emit(callback: Optional[Callable[[str, bool], None]]) -> None:
    """Register (or clear) the state emitter for the current tool call."""
    global _emit
    _emit = callback


def set_interrupt_getter(getter: Optional[Callable[[], bool]]) -> None:
    """Register a predicate the tool can poll to detect user interrupts."""
    global _interrupt_getter
    _interrupt_getter = getter


def is_interrupted() -> bool:
    """True if the user asked to cancel the current turn."""
    g = _interrupt_getter
    if g is None:
        return False
    try:
        return bool(g())
    except Exception:
        return False


def set_usage_sink(sink: Optional[Callable[[int, int, float], None]]) -> None:
    """Register (or clear) a sink that receives sub-LLM usage from tools."""
    global _usage_sink
    _usage_sink = sink


def record_usage(input_tokens: int, output_tokens: int, cost_usd: float) -> None:
    """Report LLM usage from inside a tool so the session cost reflects it."""
    sink = _usage_sink
    if sink is not None:
        try:
            sink(int(input_tokens), int(output_tokens), float(cost_usd))
        except Exception:
            pass


def emit_state(label: str, *, error: bool = False) -> None:
    """Push a short progress label from a running tool to the UI.

    Pass ``error=True`` for transient failure states so the UI can render
    them in red while the tool continues (e.g. fallback attempt in progress).
    """
    cb = _emit
    if cb is not None:
        try:
            cb(label, error)
        except Exception:
            pass
