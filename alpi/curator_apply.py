from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


def load_report(home: Path, report_id: str | None = None) -> tuple[Path, dict[str, Any]]:
    from alpi import curator
    if report_id:
        report_dir = home / "logs" / "curator" / report_id
    else:
        reports = curator.list_reports(home)
        if not reports:
            raise FileNotFoundError(
                "no curator reports found — run `alpi curator review` first"
            )
        report_dir = reports[0]
    path = report_dir / "report.json"
    if not path.exists():
        raise FileNotFoundError(f"no report.json under {report_dir}")
    return report_dir, json.loads(path.read_text(encoding="utf-8"))


def archive_actions(report: dict[str, Any]) -> list[dict[str, Any]]:
    return [a for a in (report.get("actions") or []) if a.get("type") == "archive"]


def apply_report(
    home: Path,
    report: dict[str, Any],
    *,
    dry_run: bool = False,
    now: float | None = None,
) -> dict[str, Any]:
    from alpi import skills_usage
    from alpi.tools.skill import _find_skill, _is_pinned, archive_skill_dir

    results: list[dict[str, Any]] = []
    for action in report.get("actions") or []:
        name = str(action.get("skill") or "")
        atype = action.get("type")
        entry: dict[str, Any] = {"skill": name, "type": atype}
        if atype != "archive":
            results.append({**entry, "status": "skipped", "reason": "unsupported action type"})
            continue
        # Names are looked up under home/skills only; reject anything path-like.
        if not name or "/" in name or "\\" in name or name.startswith("."):
            results.append({**entry, "status": "skipped", "reason": "invalid skill name"})
            continue
        # Resolve by category when the action carries one — avoids archiving the
        # wrong skill if a name is duplicated across categories.
        category = str(action.get("category") or "")
        skill_dir = None
        if category and "/" not in category and not category.startswith("."):
            cand = home / "skills" / category / name
            if cand.is_dir():
                skill_dir = cand
        if skill_dir is None:
            skill_dir = _find_skill(home, name)
        if skill_dir is None:
            results.append(
                {**entry, "status": "skipped", "reason": "not found (already archived or removed)"}
            )
            continue
        if _is_pinned(skill_dir):
            results.append({**entry, "status": "skipped", "reason": "pinned"})
            continue
        if dry_run:
            results.append({**entry, "status": "would-archive"})
            continue
        dest = archive_skill_dir(home, skill_dir)
        skills_usage.forget(home, name)
        results.append({**entry, "status": "archived", "dest": str(dest)})

    counts: dict[str, int] = {}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    return {
        "applied_at": float(now) if now is not None else time.time(),
        "dry_run": dry_run,
        "report_version": report.get("version"),
        "counts": counts,
        "results": results,
    }


def write_apply_report(report_dir: Path, result: dict[str, Any]) -> Path:
    path = report_dir / "apply.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
