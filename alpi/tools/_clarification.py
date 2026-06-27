"""UX.1 — clarification handler registry shared by ``ask_user``.

The ``ask_user`` tool routes by surface:

- **TUI / daemon**: a handler is installed at startup by whoever owns the
  user-facing surface — ``alpi.cli`` for interactive TUI turns,
  ``alpi.host.clarification`` for the daemon WebSocket path. The tool
  calls the registered handler synchronously and returns whatever string
  it produces.
- **headless / no handler**: the tool returns a graceful fallback string
  so the model can resume in prose instead of crashing.

Mirrors the shape of ``alpi.tools._approval.set_prompt_callback`` so the
same TUI-overrides-daemon pattern keeps working without surprises.
"""

from __future__ import annotations

from typing import Any, Callable, Optional


ClarificationHandler = Callable[[str, list[dict[str, Any]], bool, bool], str]
"""``(question, choices, allow_other, multi) -> chosen text``.

The handler MUST return a string. Callers never see ``None``. A handler
that wants to express cancellation returns a sentinel string the tool
forwards to the model (e.g. ``"User cancelled clarification."``).
When ``multi`` is True the handler must return the chosen labels joined
by ``", "``.
"""


_handler: Optional[ClarificationHandler] = None


def set_handler(fn: Optional[ClarificationHandler]) -> None:
    """Install (or clear) the active handler. Last writer wins, matching the TUI-overrides-daemon convention used by approvals."""
    global _handler
    _handler = fn


def get_handler() -> Optional[ClarificationHandler]:
    return _handler


__all__ = ["ClarificationHandler", "get_handler", "set_handler"]
