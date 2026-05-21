"""OPS.1 — local evidence digest.

A simple, read-only aggregator over data already on disk:

- broken / unavailable tools (TL.1 availability layer);
- gateway state per platform (GW.1 breaker layer);
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
from alpi.gateway import breaker as _breaker


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
class GatewaysSection:
    total_tracked: int
    by_state: dict[str, int] = field(default_factory=dict)
    degraded: list[dict[str, Any]] = field(default_factory=list)
    disabled: list[dict[str, Any]] = field(default_factory=list)


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
class DigestReport:
    window_days: float
    generated_at: float
    tools: ToolsSection
    gateways: GatewaysSection
    skills: SkillsSection
    memory: MemorySection
    compaction: CompactionSection


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
        gateways=_gateways_section(home, nowt),
        skills=_skills_section(home, nowt),
        memory=_memory_section(home, nowt),
        compaction=_compaction_section(home, nowt, window_days),
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


# ---------- section: gateways ----------


def _gateways_section(home: Path, now_ts: float) -> GatewaysSection:
    try:
        store = _breaker.for_home(home)
        states = store.all_states()
    except Exception:  # noqa: BLE001
        return GatewaysSection(total_tracked=0)

    by_state = {"healthy": 0, "degraded": 0, "disabled": 0}
    degraded: list[dict[str, Any]] = []
    disabled: list[dict[str, Any]] = []

    for name, st in sorted(states.items()):
        by_state[st.status] = by_state.get(st.status, 0) + 1
        if st.status == "degraded":
            degraded.append({
                "platform": name,
                "last_error": st.last_error,
                "consecutive_failures": st.consecutive_failures,
            })
        elif st.status == "disabled":
            cooldown = max(0.0, st.disabled_until - now_ts)
            disabled.append({
                "platform": name,
                "last_error": st.last_error,
                "consecutive_failures": st.consecutive_failures,
                "cooldown_remaining_s": cooldown,
            })

    return GatewaysSection(
        total_tracked=len(states),
        by_state=by_state,
        degraded=degraded,
        disabled=disabled,
    )


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
    "CompactionSection",
    "DEFAULT_WINDOW_DAYS",
    "DigestReport",
    "GatewaysSection",
    "MemorySection",
    "SkillsSection",
    "ToolsSection",
    "parse_window",
    "run_digest",
]
