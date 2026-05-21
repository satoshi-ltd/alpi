"""CM.1 — read-only audit of memory quality.

Reports six categories without mutating any file:

- usage pressure (how close USER.md / MEMORY.md are to their caps);
- low-confidence entries eligible for expiry;
- near-duplicate clusters at multiple overlap-coefficient thresholds
  (calibration candidates for the dedup cutoff currently hard-coded at 0.7);
- entries that look like operational state (chat ids, ISO timestamps,
  long numeric ids) and probably belong in sessions or logs;
- promotion-queue backlog (count, age of oldest, target distribution);
- compaction-log stats (frequency + token-reduction distribution).

Operator entry point: ``alpi memory audit`` (alpi/cli.py).
"""

from __future__ import annotations

import json
import statistics
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

from alpi import promotion
from alpi.home import agent_path
from alpi.memory import (
    ENTRY_DELIMITER,
    LOW_CONFIDENCE_MAX_AGE_DAYS,
    MEMORY_CHAR_LIMIT,
    USER_CHAR_LIMIT,
    MemoryStore,
    _content_tokens,
    _normalize_for_dedup,
    _should_prune,
    parse_meta,
    strip_meta,
)


# The dedup similarity used here mirrors production: `overlap / min(|a|, |b|)`,
# i.e. the Szymkiewicz–Simpson overlap coefficient (NOT Jaccard, which would
# be `overlap / union`). The threshold sweep calibrates that exact metric so
# audit findings stay comparable to the live dedup cutoff in `_find_duplicate_index`.
DEFAULT_THRESHOLDS: tuple[float, ...] = (0.5, 0.6, 0.7, 0.8)
USAGE_PRESSURE_WARN_PCT = 0.80


# ---------- result types ----------


@dataclass
class FileUsage:
    name: str
    used: int
    limit: int | None  # None for AGENT.md (unbounded)

    @property
    def percent(self) -> float | None:
        if self.limit is None or self.limit <= 0:
            return None
        return self.used / self.limit


@dataclass
class StaleEntry:
    file: str
    index: int
    text: str
    captured: str
    reinforced: int


@dataclass
class DuplicateCluster:
    file: str
    members: list[tuple[int, str]]


@dataclass
class DuplicateReport:
    threshold: float
    clusters: list[DuplicateCluster]


@dataclass
class OperationalLeak:
    file: str
    index: int
    text: str
    warning: str


@dataclass
class PromotionStats:
    pending: int
    oldest_age_days: float | None
    by_target: dict[str, int]


@dataclass
class CompactionStats:
    events_7d: int
    events_30d: int
    avg_ratio: float | None
    median_ratio: float | None
    fired_pct: float | None


@dataclass
class AuditReport:
    usage: list[FileUsage]
    stale: list[StaleEntry]
    duplicates: list[DuplicateReport]
    operational: list[OperationalLeak]
    promotion: PromotionStats
    compaction: CompactionStats
    pressure_warnings: list[str] = field(default_factory=list)


# ---------- audit entry point ----------


def run_audit(
    home: Path,
    *,
    thresholds: tuple[float, ...] = DEFAULT_THRESHOLDS,
    today: date | None = None,
    now: float | None = None,
) -> AuditReport:
    """Compute the audit. Pure: reads files, never writes. ``today`` /
    ``now`` are injectable for deterministic tests."""
    today = today or datetime.now(timezone.utc).date()
    now_ts = now if now is not None else time.time()

    files = _collect_files(home)
    usage = _usage(files)
    stale = _stale(files, today)
    duplicates = _duplicates(files, thresholds)
    operational = _operational(files)
    promo = _promotion(home, now_ts)
    comp = _compaction(home, now_ts)
    pressure = _pressure_warnings(usage, promo)

    return AuditReport(
        usage=usage,
        stale=stale,
        duplicates=duplicates,
        operational=operational,
        promotion=promo,
        compaction=comp,
        pressure_warnings=pressure,
    )


# ---------- file collection ----------


def _collect_files(
    home: Path,
) -> list[tuple[str, list[str], int | None, str]]:
    """Return ``(name, entries, char_limit, raw_text)`` for each memory file.

    USER.md / MEMORY.md split on ``§``; AGENT.md splits on blank lines
    (free-form paragraph stanzas). ``raw_text`` is the on-disk content used
    for usage measurement so the audit matches what MemoryStore.usage() and
    the system-prompt injector actually count."""
    store = MemoryStore(home=home)
    out: list[tuple[str, list[str], int | None, str]] = []

    for name, path, limit in (
        ("USER.md", store.user_path, USER_CHAR_LIMIT),
        ("MEMORY.md", store.memory_path, MEMORY_CHAR_LIMIT),
    ):
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        entries = [e for e in text.split(ENTRY_DELIMITER) if strip_meta(e).strip()]
        out.append((name, entries, limit, text))

    a_path = agent_path(home)
    a_text = a_path.read_text(encoding="utf-8") if a_path.exists() else ""
    stanzas = [s for s in a_text.split("\n\n") if strip_meta(s).strip()]
    out.append(("AGENT.md", stanzas, None, a_text))

    return out


# ---------- usage ----------


def _usage(
    files: list[tuple[str, list[str], int | None, str]],
) -> list[FileUsage]:
    """Match ``MemoryStore.usage()``: count the full file text after stripping metadata comments. That is what the system prompt sees (delimiters and blank lines included) and what triggers the on-disk write cap."""
    out: list[FileUsage] = []
    for name, _entries, limit, raw_text in files:
        used = len(strip_meta(raw_text))
        out.append(FileUsage(name=name, used=used, limit=limit))
    return out


# ---------- low-confidence stale ----------


def _stale(
    files: list[tuple[str, list[str], int | None, str]], today: date,
) -> list[StaleEntry]:
    out: list[StaleEntry] = []
    for name, entries, _limit, _raw in files:
        for i, entry in enumerate(entries):
            try:
                stale = _should_prune(entry, today, LOW_CONFIDENCE_MAX_AGE_DAYS)
            except (TypeError, ValueError):
                # Hand-edited meta with non-numeric reinforced / bad date → safest read is "not auto-pruneable, but surface it as stale anyway so the operator notices".
                stale = True
            if not stale:
                continue
            meta = parse_meta(entry) or {}
            out.append(StaleEntry(
                file=name,
                index=i,
                text=_preview(strip_meta(entry)),
                captured=meta.get("captured", ""),
                reinforced=_safe_int(meta.get("reinforced", "0")),
            ))
    return out


# ---------- duplicate clusters ----------


def _duplicates(
    files: list[tuple[str, list[str], int | None, str]],
    thresholds: tuple[float, ...],
) -> list[DuplicateReport]:
    out: list[DuplicateReport] = []
    for t in thresholds:
        clusters: list[DuplicateCluster] = []
        for name, entries, _limit, _raw in files:
            for group in _overlap_clusters(entries, t):
                clusters.append(DuplicateCluster(
                    file=name,
                    members=[(i, _preview(strip_meta(entries[i]))) for i in group],
                ))
        out.append(DuplicateReport(threshold=t, clusters=clusters))
    return out


def _overlap_clusters(entries: list[str], threshold: float) -> list[list[int]]:
    """Union-find clustering by overlap-coefficient token similarity at ``threshold`` (``overlap / min(|a|, |b|)``, same metric as the live dedup in ``_find_duplicate_index``). Singletons omitted."""
    n = len(entries)
    if n < 2:
        return []

    bodies = [strip_meta(e) for e in entries]
    norms = [_normalize_for_dedup(b) for b in bodies]
    tokens = [_content_tokens(b) for b in bodies]

    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for i in range(n):
        if not norms[i]:
            continue
        for j in range(i + 1, n):
            if not norms[j]:
                continue
            if (norms[i] == norms[j]
                    or norms[i] in norms[j]
                    or norms[j] in norms[i]):
                union(i, j)
                continue
            ti, tj = tokens[i], tokens[j]
            if not (ti and tj):
                continue
            overlap = len(ti & tj)
            smaller = min(len(ti), len(tj))
            if smaller >= 2 and overlap / smaller >= threshold:
                union(i, j)

    by_root: dict[int, list[int]] = {}
    for i in range(n):
        by_root.setdefault(find(i), []).append(i)
    return [members for members in by_root.values() if len(members) > 1]


# ---------- operational-state leaks ----------


def _operational(files: list[tuple[str, list[str], int | None, str]]) -> list[OperationalLeak]:
    from alpi.tools.memory import _operational_warning

    out: list[OperationalLeak] = []
    for name, entries, _limit, _raw in files:
        for i, entry in enumerate(entries):
            body = strip_meta(entry).strip()
            if not body:
                continue
            warning = _operational_warning(body)
            if warning:
                out.append(OperationalLeak(
                    file=name,
                    index=i,
                    text=_preview(body),
                    warning=warning.lstrip("⚠ ").strip(),
                ))
    return out


# ---------- promotion queue ----------


def _promotion(home: Path, now_ts: float) -> PromotionStats:
    """Read the promotion queue WITHOUT calling ``promotion.list_pending`` — that helper rewrites the file when it prunes expired rows, which we must not do from a read-only audit."""
    path = promotion.queue_path(home)
    if not path.exists():
        return PromotionStats(pending=0, oldest_age_days=None, by_target={})

    rows: list[dict] = []
    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError:
        return PromotionStats(pending=0, oldest_age_days=None, by_target={})

    # Per-line tolerance: a single malformed row must not skip the rest of the queue.
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
        if now_ts - created > promotion.MAX_AGE_DAYS * 86400:
            continue  # would be pruned on next write; ignore here
        rows.append(obj)

    by_target: dict[str, int] = {}
    for r in rows:
        by_target[str(r.get("target") or "MEMORY.md")] = (
            by_target.get(str(r.get("target") or "MEMORY.md"), 0) + 1
        )

    oldest_age = None
    if rows:
        oldest = min(_safe_float(r.get("created_at")) for r in rows)
        oldest_age = max(0.0, (now_ts - oldest) / 86400.0)

    return PromotionStats(
        pending=len(rows),
        oldest_age_days=oldest_age,
        by_target=by_target,
    )


# ---------- compaction stats ----------


def _compaction(home: Path, now_ts: float) -> CompactionStats:
    path = home / "logs" / "compaction.jsonl"
    if not path.exists():
        return CompactionStats(
            events_7d=0, events_30d=0,
            avg_ratio=None, median_ratio=None, fired_pct=None,
        )

    events_7d = 0
    events_30d = 0
    ratios: list[float] = []
    fired_count = 0
    fired_total = 0

    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError:
        raw_text = ""

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
        ts = _safe_float(obj.get("ts"))
        age_days = (now_ts - ts) / 86400.0
        if age_days > 30:
            continue  # rolling window — older events don't inform current behaviour
        events_30d += 1
        if age_days <= 7:
            events_7d += 1
        before = _safe_float(obj.get("tokens_before"))
        after = _safe_float(obj.get("tokens_after"))
        if before > 0:
            ratios.append(after / before)
        fired = obj.get("fired")
        if fired is not None:
            fired_total += 1
            if fired:
                fired_count += 1

    avg = sum(ratios) / len(ratios) if ratios else None
    med = statistics.median(ratios) if ratios else None
    fired_pct = (fired_count / fired_total) if fired_total > 0 else None

    return CompactionStats(
        events_7d=events_7d,
        events_30d=events_30d,
        avg_ratio=avg,
        median_ratio=med,
        fired_pct=fired_pct,
    )


# ---------- pressure summary ----------


def _pressure_warnings(usage: list[FileUsage], promo: PromotionStats) -> list[str]:
    out: list[str] = []
    for u in usage:
        if u.percent is not None and u.percent >= USAGE_PRESSURE_WARN_PCT:
            out.append(
                f"{u.name} at {u.percent * 100:.0f}% of cap "
                f"({u.used}/{u.limit})"
            )
    if promo.pending >= promotion.MAX_PENDING * 0.8:
        out.append(
            f"promotion queue near cap: {promo.pending} pending "
            f"(cap {promotion.MAX_PENDING})"
        )
    return out


# ---------- helpers ----------


def _preview(text: str, *, length: int = 100) -> str:
    one_line = " ".join(text.split())
    return one_line if len(one_line) <= length else one_line[: length - 1] + "…"


def _safe_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


__all__ = [
    "AuditReport", "CompactionStats", "DuplicateCluster", "DuplicateReport",
    "FileUsage", "OperationalLeak", "PromotionStats", "StaleEntry",
    "DEFAULT_THRESHOLDS", "USAGE_PRESSURE_WARN_PCT",
    "run_audit",
]
