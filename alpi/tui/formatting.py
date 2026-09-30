from __future__ import annotations

from alpi.tool_hints import shorten_path, shorten_url, truncate

__all__ = ["bar", "bar_10", "fmt_count", "fmt_duration", "shorten_path", "shorten_url", "truncate"]


def fmt_duration(seconds: float) -> str:
    if seconds < 1:
        return f"{int(seconds * 1000)}ms"
    if seconds < 60:
        return f"{seconds:.1f}s"
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins}m{secs}s"


def fmt_count(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 10_000:
        return f"{n // 1000}K"
    if n >= 1000:
        return f"{n / 1000:.1f}K"
    return str(n)


def bar_10(n: int, total: int) -> str:
    return bar(n, total, 10)


def bar(n: int, total: int, cells: int) -> str:
    cells = max(1, cells)
    if total <= 0:
        return "▓" + "░" * (cells - 1)
    filled = max(0, min(cells, n * cells // total))
    return "▓" * filled + "░" * (cells - filled)
