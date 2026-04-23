"""Unified log reader for `alpi logs`.

Convention: every subsystem writes to ``{home}/logs/{subsystem}.log``
with lines prefixed by ``YYYY-MM-DD HH:MM:SS``. The source tag comes
from the filename (``gateway.log`` → ``gateway``) — no per-subsystem
subdirectory, no config to keep in sync. New loggers plug in just by
calling ``alpi._log.get_subsystem_logger(home, name)``.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class LogLine:
    ts: str       # "YYYY-MM-DD HH:MM:SS" — empty for unparseable continuation lines
    source: str   # "gateway" / "schedule" / ...
    text: str     # raw line (no trailing newline)


def discover(home: Path, source: str | None = None) -> list[Path]:
    """Return ``{home}/logs/*.log`` files, optionally filtered by source."""
    logs_dir = home / "logs"
    if not logs_dir.is_dir():
        return []
    if source:
        p = logs_dir / f"{source}.log"
        return [p] if p.exists() else []
    return sorted(logs_dir.glob("*.log"))


def _parse_ts(line: str) -> str:
    if len(line) >= 19 and line[4] == "-" and line[7] == "-" and line[10] == " ":
        return line[:19]
    return ""


def _read_lines(path: Path) -> list[LogLine]:
    source = path.stem  # "gateway.log" → "gateway"
    try:
        raw = path.read_text().splitlines()
    except OSError:
        return []
    out: list[LogLine] = []
    last_ts = ""
    for line in raw:
        ts = _parse_ts(line) or last_ts
        if ts:
            last_ts = ts
        out.append(LogLine(ts=ts, source=source, text=line))
    return out


def tail(home: Path, source: str | None, n: int) -> list[LogLine]:
    """Merge all matching logs by timestamp and return the last ``n`` lines."""
    files = discover(home, source)
    if not files:
        return []
    merged: list[LogLine] = []
    for f in files:
        merged.extend(_read_lines(f))
    merged.sort(key=lambda l: (l.ts, l.source))
    if n > 0:
        merged = merged[-n:]
    return merged


def follow(home: Path, source: str | None, console) -> None:
    """Poll every matching log for new lines until Ctrl-C."""
    files = discover(home, source)
    offsets: dict[Path, int] = {}
    for f in files:
        try:
            offsets[f] = f.stat().st_size
        except OSError:
            offsets[f] = 0

    try:
        while True:
            for f in discover(home, source):
                try:
                    size = f.stat().st_size
                except OSError:
                    continue
                start = offsets.get(f, 0)
                if size < start:
                    start = 0  # rotated
                if size == start:
                    offsets[f] = size
                    continue
                try:
                    with f.open() as fh:
                        fh.seek(start)
                        chunk = fh.read()
                    offsets[f] = size
                except OSError:
                    continue
                sub = f.stem
                for line in chunk.splitlines():
                    _print_line(console, LogLine(ts=_parse_ts(line), source=sub, text=line))
            time.sleep(1.0)
    except KeyboardInterrupt:
        return


# Rendering

_SOURCE_WIDTH = 8


def _print_line(console, line: LogLine) -> None:
    from rich.text import Text
    tag = line.source.ljust(_SOURCE_WIDTH)
    t = Text()
    t.append(f"[{tag}] ", style="dim")
    t.append(line.text)
    console.print(t)


def print_tail(console, lines: list[LogLine]) -> None:
    for l in lines:
        _print_line(console, l)
