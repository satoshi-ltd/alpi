"""Canonical ``/status`` rows shared by the TUI panel and Telegram shortcut."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def status_rows(
    *,
    session_id: str,
    model: str,
    turns: int,
    elapsed_seconds: int | None,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
    home: Path | None = None,
    cfg_budget: dict[str, Any] | None = None,
) -> list[tuple[str, str]]:
    """``home`` + ``cfg_budget`` append a ``daily budget`` row from the
    ledger; omit both for a session-only view."""
    rows: list[tuple[str, str]] = [
        ("model", model),
        ("turns", str(turns)),
    ]
    if elapsed_seconds is not None:
        mins, secs = divmod(int(elapsed_seconds), 60)
        rows.append(("elapsed", f"{mins:02d}:{secs:02d}"))
    rows.extend([
        ("tokens",       f"in={input_tokens:,}  out={output_tokens:,}"),
        ("session cost", f"${cost_usd:.4f}"),
    ])
    if home is not None:
        from alpi import ledger
        rows.append(("daily budget", ledger.status_line(home, cfg_budget or {})))
    return rows


def status_title(session_id: str) -> str:
    return f"session {session_id}"
