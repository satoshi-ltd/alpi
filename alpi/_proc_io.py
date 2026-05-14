"""Async subprocess I/O helpers shared by gateway + service daemon paths."""

from __future__ import annotations

import asyncio
from collections import deque


async def drain_tail(
    stream: asyncio.StreamReader | None,
    *,
    max_lines: int = 40,
) -> str:
    """Drain a pipe stream fully (no buffer-fill deadlock) keeping only the last ``max_lines`` decoded lines."""
    if stream is None:
        return ""
    tail: deque[str] = deque(maxlen=max_lines)
    while True:
        line = await stream.readline()
        if not line:
            break
        tail.append(line.decode(errors="replace").rstrip("\n"))
    return "\n".join(tail)
