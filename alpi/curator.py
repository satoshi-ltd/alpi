"""AC.1 phase 1 — post-hoc skill curator (report-only).

Reads ``skills/.usage.json`` telemetry plus the on-disk skills tree,
flags candidates for review, writes a markdown + json report to
``<home>/logs/curator/<UTC-timestamp>/``. Never mutates skills, never
deletes — that's AC.2.

Heuristics shipped in this phase:

- **stale** — skills with a ``last_seen`` older than ``window_days``
  (default ``skills_usage.STALE_DAYS``). Skips pinned skills.
- **cold** — skills on disk that have no usage row at all and whose
  ``SKILL.md`` mtime is itself older than the same window. A recently
  added skill that hasn't been invoked yet is silently ignored.
- **prefix clusters** — three or more skills sharing a ``<word>-`` /
  ``<word>_`` prefix. Surfaces umbrella-consolidation candidates.

What this phase does NOT do:

- No upstream-update checks on imported skills (no import system yet).
- No session-scoped narrowness detection (telemetry lacks session ids).
- No mutation, archive move, or ``absorbed_into:`` metadata write.
"""

from __future__ import annotations

import json
import re
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from alpi import skills_usage


_PREFIX_RE = re.compile(r"^([a-z][a-z0-9]+)[-_]")
_MIN_CLUSTER_SIZE = 3
_REPORT_VERSION = 1


def _frontmatter(skill_dir: Path) -> dict[str, str]:
    from alpi.tools.skill import _frontmatter as _fm
    return _fm(skill_dir / "SKILL.md")


def _all_skills(home: Path) -> list[Path]:
    from alpi.tools.skill import all_skills
    return all_skills(home)


def _days_since(ts: float, now: float) -> float:
    if ts <= 0:
        return float("inf")
    return max(0.0, (now - ts) / 86400.0)


def review(
    home: Path,
    *,
    window_days: float | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    """Run every heuristic against the current home. Pure: returns the structured findings, no I/O."""
    nowt = float(now) if now is not None else time.time()
    window = float(window_days) if window_days is not None else float(skills_usage.STALE_DAYS)
    usage = skills_usage.load_all(home)

    stale: list[dict[str, Any]] = []
    cold: list[dict[str, Any]] = []
    by_prefix: dict[str, list[str]] = defaultdict(list)

    on_disk = _all_skills(home)
    on_disk_names: list[str] = []

    for skill_dir in on_disk:
        try:
            meta = _frontmatter(skill_dir)
        except OSError:
            on_disk_names.append(skill_dir.name)
            continue
        name = meta.get("name") or skill_dir.name
        category = meta.get("category") or skill_dir.parent.name
        pinned = (meta.get("pinned") or "").strip().lower() == "true"
        on_disk_names.append(name)

        match = _PREFIX_RE.match(name)
        if match:
            by_prefix[match.group(1)].append(name)

        entry = usage.get(name)
        if entry:
            last_seen = float(entry.get("last_seen") or 0.0)
            days = _days_since(last_seen, nowt)
            if days >= window and not pinned:
                stale.append({
                    "name": name,
                    "category": category,
                    "pinned": pinned,
                    "last_seen_days_ago": round(days, 1),
                    "use_count": int(entry.get("use_count") or 0),
                    "view_count": int(entry.get("view_count") or 0),
                    "patch_count": int(entry.get("patch_count") or 0),
                })
        else:
            md = skill_dir / "SKILL.md"
            try:
                mtime = md.stat().st_mtime
            except OSError:
                continue
            on_disk_age = _days_since(mtime, nowt)
            if on_disk_age >= window and not pinned:
                cold.append({
                    "name": name,
                    "category": category,
                    "pinned": pinned,
                    "on_disk_days_ago": round(on_disk_age, 1),
                })

    clusters: list[dict[str, Any]] = []
    for prefix, names in sorted(by_prefix.items()):
        if len(names) >= _MIN_CLUSTER_SIZE:
            clusters.append({
                "prefix": prefix,
                "names": sorted(names),
                "count": len(names),
            })

    stale.sort(key=lambda r: r["last_seen_days_ago"], reverse=True)
    cold.sort(key=lambda r: r["on_disk_days_ago"], reverse=True)

    return {
        "version": _REPORT_VERSION,
        "generated_at": nowt,
        "window_days": window,
        "summary": {
            "skills_on_disk": len(on_disk_names),
            "skills_with_usage": len(usage),
            "stale": len(stale),
            "cold": len(cold),
            "prefix_clusters": len(clusters),
        },
        "stale": stale,
        "cold": cold,
        "prefix_clusters": clusters,
    }


def _ts_dir(home: Path, ts: float) -> Path:
    dt = datetime.fromtimestamp(ts, timezone.utc)
    stamp = dt.strftime("%Y%m%dT%H%M%S") + f"{dt.microsecond // 1000:03d}Z"
    return home / "logs" / "curator" / stamp


def write_report(
    home: Path,
    findings: dict[str, Any],
    *,
    ts: float | None = None,
) -> Path:
    """Persist ``report.md`` + ``report.json`` under ``<home>/logs/curator/<ts>/``. Returns that directory."""
    timestamp = float(ts) if ts is not None else float(findings.get("generated_at") or time.time())
    out_dir = _ts_dir(home, timestamp)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.json").write_text(
        json.dumps(findings, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out_dir / "report.md").write_text(_render_markdown(findings), encoding="utf-8")
    return out_dir


def list_reports(home: Path) -> list[Path]:
    """Past report directories, newest first."""
    root = home / "logs" / "curator"
    if not root.exists():
        return []
    return sorted(
        (p for p in root.iterdir() if p.is_dir()),
        key=lambda p: p.name,
        reverse=True,
    )


def _render_markdown(findings: dict[str, Any]) -> str:
    nowt = float(findings.get("generated_at") or time.time())
    when = datetime.fromtimestamp(nowt, timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    s = findings["summary"]
    out: list[str] = [
        "# Skill curator report",
        "",
        f"- Generated: {when}",
        f"- Window: ≥{findings['window_days']:.0f} days since last use",
        f"- Skills on disk: {s['skills_on_disk']}",
        f"- Skills with usage telemetry: {s['skills_with_usage']}",
        f"- Stale candidates: {s['stale']}",
        f"- Cold candidates: {s['cold']}",
        f"- Prefix clusters: {s['prefix_clusters']}",
        "",
        "_Report-only. No skills are modified by this run; apply suggestions manually._",
        "",
    ]

    if findings["stale"]:
        out.append("## Stale — used historically, not lately")
        out.append("")
        for r in findings["stale"]:
            out.append(
                f"- **{r['name']}** ({r['category']}) — "
                f"last used {r['last_seen_days_ago']:.0f} d ago · "
                f"{r['use_count']} use / {r['view_count']} view / {r['patch_count']} patch"
            )
        out.append("")
        out.append("Review each row; remove with the `skill` tool from a chat session if no longer needed.")
        out.append("")

    if findings["cold"]:
        out.append("## Cold — on disk but never invoked")
        out.append("")
        for r in findings["cold"]:
            out.append(
                f"- **{r['name']}** ({r['category']}) — "
                f"present {r['on_disk_days_ago']:.0f} d, never used"
            )
        out.append("")
        out.append("These may be agent-created stubs or imports the user never reached for.")
        out.append("Review before deletion — they might still be referenced by a workflow.")
        out.append("")

    if findings["prefix_clusters"]:
        out.append("## Prefix clusters — umbrella candidates")
        out.append("")
        for c in findings["prefix_clusters"]:
            members = ", ".join(c["names"])
            out.append(f"- **`{c['prefix']}-*`** ({c['count']}): {members}")
        out.append("")
        out.append(
            "If these are variants of the same workflow, consider folding them "
            "into a single umbrella skill with the variants under "
            "`references/`."
        )
        out.append("")

    if not (findings["stale"] or findings["cold"] or findings["prefix_clusters"]):
        out.append("Nothing to review. The skill library is clean.")
        out.append("")

    return "\n".join(out)


__all__ = [
    "list_reports",
    "review",
    "write_report",
]
