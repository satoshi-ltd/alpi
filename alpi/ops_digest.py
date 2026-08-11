"""OPS.1 — local evidence digest.

A simple, read-only aggregator over data already on disk:

- broken / unavailable tools (TL.1 availability layer);
- skill usage distribution + pinned-but-cold (SK.1 telemetry);
- memory promotion backlog + usage pressure;
- compaction rate over the time window.

Deliberately not an observability product: no LLM summary, no
recommendations, no dashboard, no new on-disk state. Every section
reads existing primitives via the modules that own them.
"""

from __future__ import annotations

import json
import re
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from alpi import promotion, skills_usage


DEFAULT_WINDOW_DAYS = 7.0

_WINDOW_RE = re.compile(r"^\s*(\d+)\s*([dhm])\s*$", re.IGNORECASE)


def parse_window(value: str | float | int) -> float:
    """Return days. Accepts ``"7d"`` / ``"12h"`` / ``"30m"`` shorthand or a raw numeric (interpreted as days). Raises ``ValueError`` on unparseable input so the CLI can surface a clear error instead of silently defaulting."""
    if isinstance(value, (int, float)):
        days = float(value)
        if days <= 0:
            raise ValueError(f"window must be positive: {value!r}")
        return days
    if not isinstance(value, str):
        raise ValueError(f"invalid window: {value!r}")
    match = _WINDOW_RE.match(value)
    if match is None:
        try:
            days = float(value)
        except ValueError as exc:
            raise ValueError(f"invalid window: {value!r}") from exc
        if days <= 0:
            raise ValueError(f"window must be positive: {value!r}")
        return days
    n = int(match.group(1))
    if n <= 0:
        raise ValueError(f"window must be positive: {value!r}")
    unit = match.group(2).lower()
    if unit == "d":
        return float(n)
    if unit == "h":
        return n / 24.0
    if unit == "m":
        return n / 1440.0
    raise ValueError(f"invalid window unit: {value!r}")


# ---------- result types ----------


@dataclass
class ToolsSection:
    total: int
    unavailable: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class SkillsSection:
    total: int
    by_state: dict[str, int] = field(default_factory=dict)
    top_used: list[tuple[str, int]] = field(default_factory=list)
    pinned_cold: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class MemorySection:
    promotion_pending: int
    promotion_oldest_age_days: float | None
    promotion_by_target: dict[str, int] = field(default_factory=dict)
    pressure_warnings: list[str] = field(default_factory=list)


@dataclass
class CompactionSection:
    events_in_window: int
    fired_pct: float | None = None
    avg_ratio: float | None = None
    median_ratio: float | None = None


@dataclass
class RunsSection:
    total: int
    by_kind: dict[str, int] = field(default_factory=dict)
    by_outcome: dict[str, int] = field(default_factory=dict)
    recent_failures: list[dict[str, Any]] = field(default_factory=list)
    slowest: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class CacheSection:
    days_with_data: int
    tokens_cached: int = 0
    tokens_measured: int = 0
    cache_discount_usd: float = 0.0
    cost_sources: dict[str, int] = field(default_factory=dict)

    @property
    def hit_pct(self) -> float | None:
        if self.tokens_measured <= 0:
            return None
        return 100.0 * self.tokens_cached / self.tokens_measured


@dataclass
class DigestReport:
    window_days: float
    generated_at: float
    tools: ToolsSection
    skills: SkillsSection
    memory: MemorySection
    compaction: CompactionSection
    runs: RunsSection
    cache: CacheSection


# ---------- entry point ----------


def run_digest(
    home: Path,
    *,
    window_days: float = DEFAULT_WINDOW_DAYS,
    now: float | None = None,
) -> DigestReport:
    """Build the digest. Pure: reads files, never writes. ``now`` is injectable for deterministic tests."""
    nowt = now if now is not None else time.time()
    return DigestReport(
        window_days=window_days,
        generated_at=nowt,
        tools=_tools_section(),
        skills=_skills_section(home, nowt),
        memory=_memory_section(home, nowt),
        compaction=_compaction_section(home, nowt, window_days),
        runs=_runs_section(home),
        cache=_cache_section(home, nowt, window_days),
    )


def _cache_section(home: Path, now_ts: float, window_days: float) -> CacheSection:
    """Day-grained on purpose: the ledger history is per-UTC-day, so sub-day windows round up to one day."""
    try:
        from datetime import datetime, timezone
        from math import ceil

        from alpi import ledger
        s = ledger.cache_summary(
            home,
            days=max(1, int(ceil(window_days))),
            today=datetime.fromtimestamp(now_ts, tz=timezone.utc).date().isoformat(),
        )
    except Exception:  # noqa: BLE001
        return CacheSection(days_with_data=0)
    return CacheSection(
        days_with_data=int(s.get("days") or 0),
        tokens_cached=int(s.get("tokens_cached") or 0),
        tokens_measured=int(s.get("tokens_measured") or 0),
        cache_discount_usd=float(s.get("cache_discount_usd") or 0.0),
        cost_sources=dict(s.get("cost_sources") or {}),
    )


def _runs_section(home: Path) -> RunsSection:
    try:
        from alpi import run_ledger
        s = run_ledger.summarize(home, limit=50)
    except Exception:  # noqa: BLE001
        return RunsSection(total=0)
    slowest = sorted(
        s.get("slow") or [],
        key=lambda r: float(r.get("elapsed_s") or 0.0),
        reverse=True,
    )[:5]
    counts = s.get("counts") or {}
    return RunsSection(
        total=int(s.get("total") or 0),
        by_kind=dict(counts.get("by_kind") or {}),
        by_outcome=dict(counts.get("by_outcome") or {}),
        recent_failures=list(s.get("problematic") or [])[:5],
        slowest=slowest,
    )


# ---------- section: tools ----------


def _tools_section() -> ToolsSection:
    """Tools whose availability probe fails today. Built-in tools live; MCP server health requires `alpi doctor` (live spawn) and stays out of the digest."""
    try:
        from alpi import tools as tools_mod
        report = tools_mod.availability_report()
    except Exception:  # noqa: BLE001
        return ToolsSection(total=0)
    unavailable = [(name, reason) for name, ok, reason in report if not ok]
    return ToolsSection(total=len(report), unavailable=unavailable)


# ---------- section: skills ----------


def _skills_section(home: Path, now_ts: float) -> SkillsSection:
    try:
        summary = skills_usage.summary(home, now=now_ts)
    except Exception:  # noqa: BLE001
        return SkillsSection(total=0)
    return SkillsSection(
        total=int(summary.get("total") or 0),
        by_state=dict(summary.get("by_state") or {}),
        top_used=list(summary.get("top_used") or [])[:5],
        pinned_cold=list(summary.get("pinned_cold") or []),
    )


# ---------- section: memory ----------


def _memory_section(home: Path, now_ts: float) -> MemorySection:
    """Lightweight read: promotion queue + memory usage pressure. The heavy audit (duplicate clusters, operational-state scans) stays in ``alpi memory audit``."""
    rows = _read_promotion_queue(home, now_ts)
    by_target: dict[str, int] = {}
    for row in rows:
        target = str(row.get("target") or "MEMORY.md")
        by_target[target] = by_target.get(target, 0) + 1

    oldest_age: float | None = None
    if rows:
        oldest_ts = min(_safe_float(r.get("created_at")) for r in rows)
        if oldest_ts > 0:
            oldest_age = max(0.0, (now_ts - oldest_ts) / 86400.0)

    pressure: list[str] = []
    try:
        from alpi.memory import MemoryStore
        usage = MemoryStore(home=home).usage()
        for name, (used, cap) in usage.items():
            if cap > 0 and used / cap >= 0.80:
                pct = int(used * 100 // cap)
                pressure.append(f"{name} at {pct}% of cap ({used}/{cap})")
    except Exception:  # noqa: BLE001
        pass

    if len(rows) >= promotion.MAX_PENDING * 0.8:
        pressure.append(
            f"promotion queue near cap: {len(rows)} pending "
            f"(cap {promotion.MAX_PENDING})"
        )

    return MemorySection(
        promotion_pending=len(rows),
        promotion_oldest_age_days=oldest_age,
        promotion_by_target=by_target,
        pressure_warnings=pressure,
    )


def _read_promotion_queue(home: Path, now_ts: float) -> list[dict]:
    """Same shape as ``memory_audit._promotion`` — read-only, never rewrites the queue file when expired rows would normally be pruned."""
    path = promotion.queue_path(home)
    if not path.exists():
        return []
    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    rows: list[dict] = []
    cutoff_age = promotion.MAX_AGE_DAYS * 86400.0
    for line in raw_text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        created = _safe_float(obj.get("created_at"))
        if now_ts - created > cutoff_age:
            continue
        rows.append(obj)
    return rows


# ---------- section: compaction ----------


def _compaction_section(
    home: Path, now_ts: float, window_days: float,
) -> CompactionSection:
    """Streams ``compaction.jsonl`` line by line so a long-running profile with a fat log doesn't pull the whole file into memory on every digest invocation."""
    path = home / "logs" / "compaction.jsonl"
    if not path.exists():
        return CompactionSection(events_in_window=0)

    cutoff = now_ts - window_days * 86400.0
    events = 0
    fired_total = 0
    fired_count = 0
    ratios: list[float] = []

    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(obj, dict):
                    continue
                ts = _safe_float(obj.get("ts"))
                if ts < cutoff:
                    continue
                events += 1
                before = _safe_float(obj.get("tokens_before"))
                after = _safe_float(obj.get("tokens_after"))
                if before > 0:
                    ratios.append(after / before)
                fired = obj.get("fired")
                if fired is not None:
                    fired_total += 1
                    if fired:
                        fired_count += 1
    except OSError:
        return CompactionSection(events_in_window=0)

    return CompactionSection(
        events_in_window=events,
        fired_pct=(fired_count / fired_total) if fired_total > 0 else None,
        avg_ratio=(sum(ratios) / len(ratios)) if ratios else None,
        median_ratio=statistics.median(ratios) if ratios else None,
    )


# ---------- helpers ----------


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


__all__ = [
    "CacheSection",
    "CompactionSection",
    "DEFAULT_WINDOW_DAYS",
    "DigestReport",
    "MemorySection",
    "RunsSection",
    "SkillsSection",
    "ToolsSection",
    "parse_window",
    "run_digest",
]
