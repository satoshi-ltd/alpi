"""Async subprocess I/O helpers shared by the scheduler + service daemon paths."""

from __future__ import annotations

import asyncio
from collections import deque
from typing import Callable


async def drain_tail(
    stream: asyncio.StreamReader | None,
    *,
    max_lines: int = 40,
    on_activity: "Callable[[], None] | None" = None,
) -> str:
    """Drain a stream fully (no buffer-fill deadlock), keeping the last ``max_lines`` lines; ``on_activity`` fires per line as a child sign-of-life for the daemon idle-turn timeout."""
    if stream is None:
        return ""
    tail: deque[str] = deque(maxlen=max_lines)
    while True:
        line = await stream.readline()
        if not line:
            break
        if on_activity is not None:
            on_activity()
        tail.append(line.decode(errors="replace").rstrip("\n"))
    return "\n".join(tail)
