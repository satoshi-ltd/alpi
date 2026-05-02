"""``alpi diff`` — what changed in this profile since a cutoff.

Single primitive shared by three surfaces: the CLI subcommand,
the TUI ``/diff`` panel, and (later) a ``host.profile.diff`` verb
the desktop calls. ``compute(home, since)`` walks the profile
tree using file mtimes as the source of truth — no separate
audit log to keep in sync. ``render(report, since, profile)``
formats it for terminal output.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


_SINCE_RE = re.compile(r"^\s*(\d+)\s*([smhdw])\s*$", re.IGNORECASE)
_UNITS = {
    "s": 1,
    "m": 60,
    "h": 3600,
    "d": 86400,
    "w": 86400 * 7,
}


def parse_since(spec: str, *, now: datetime | None = None) -> datetime:
    """Resolve ``spec`` to a UTC cutoff. Accepts ``Nh``/``Nd``/``Nm``/etc.
    and ISO-8601 dates / datetimes. ``now`` is injectable for tests."""
    base = now or datetime.now(timezone.utc)
    s = spec.strip()
    m = _SINCE_RE.match(s)
    if m:
        value = int(m.group(1))
        unit = m.group(2).lower()
        return base - timedelta(seconds=value * _UNITS[unit])
    try:
        dt = datetime.fromisoformat(s)
    except ValueError as exc:
        raise ValueError(
            f"unrecognised --since value {spec!r}; use ``Nh`` / ``Nd`` "
            f"(e.g. ``24h``, ``7d``) or an ISO-8601 timestamp"
        ) from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@dataclass(frozen=True)
class _SessionFacts:
    count: int = 0
    turns: int = 0
    tool_calls: int = 0
    cost_usd: float = 0.0
    tokens: int = 0
    elapsed_s: float = 0.0
    last_at: float = 0.0  # epoch seconds; 0 = none


def _scan_sessions(directory: Path, cutoff_epoch: float) -> _SessionFacts:
    if not directory.exists():
        return _SessionFacts()
    count = turns = tool_calls = tokens = 0
    cost = elapsed = 0.0
    last_at = 0.0
    for path in directory.glob("*.json"):
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        if mtime < cutoff_epoch:
            continue
        try:
            data = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        count += 1
        turn_list = data.get("turns") or []
        turns += len(turn_list)
        for t in turn_list:
            tool_calls += len(t.get("tools") or [])
        tokens += int(data.get("input_tokens") or 0) + int(data.get("output_tokens") or 0)
        cost += float(data.get("cost_usd") or 0)
        elapsed += float(data.get("elapsed") or 0)
        if mtime > last_at:
            last_at = mtime
    return _SessionFacts(
        count=count,
        turns=turns,
        tool_calls=tool_calls,
        cost_usd=round(cost, 6),
        tokens=tokens,
        elapsed_s=round(elapsed, 3),
        last_at=last_at,
    )


def _scan_memory(home: Path, cutoff_epoch: float) -> list[dict[str, Any]]:
    """Memory files (``memories/*.md``) modified since cutoff. We don't
    diff *contents* — that would require keeping snapshots; the file's
    mtime + current size is enough to tell the user 'something happened
    here, go look'."""
    root = home / "memories"
    if not root.exists():
        return []
    out: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.md")):
        try:
            st = path.stat()
        except OSError:
            continue
        if st.st_mtime < cutoff_epoch:
            continue
        out.append({"file": path.name, "mtime": st.st_mtime, "size": st.st_size})
    return out


def _scan_skills(home: Path, cutoff_epoch: float) -> list[dict[str, Any]]:
    root = home / "skills"
    if not root.exists():
        return []
    out: list[dict[str, Any]] = []
    for path in sorted(root.iterdir()):
        if not path.is_dir() or path.name.startswith("."):
            continue
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        if mtime < cutoff_epoch:
            continue
        out.append({"name": path.name, "mtime": mtime})
    return out


def _scan_peers(home: Path, cutoff_epoch: float) -> dict[str, Any]:
    yaml_path = home / "alp" / "peers.yaml"
    info: dict[str, Any] = {"count": 0, "yaml_mtime": None, "changed": False}
    if not yaml_path.exists():
        return info
    try:
        st = yaml_path.stat()
    except OSError:
        return info
    info["yaml_mtime"] = st.st_mtime
    info["changed"] = st.st_mtime >= cutoff_epoch
    try:
        from alpi.alp import peers as peers_mod
        info["count"] = len(peers_mod.load(home))
    except Exception:  # noqa: BLE001
        pass
    return info


def _scan_mentions(home: Path, cutoff_epoch: float) -> dict[str, Any]:
    root = home / "mentions"
    if not root.exists():
        return {"peers": [], "files": 0}
    peers: list[str] = []
    files = 0
    for path in sorted(root.glob("*.json")):
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        if mtime < cutoff_epoch:
            continue
        files += 1
        peers.append(path.stem)
    return {"peers": peers, "files": files}


def _scan_schedule_runs(home: Path, cutoff_epoch: float) -> dict[str, Any]:
    root = home / "schedule" / "output"
    if not root.exists():
        return {"count": 0, "by_job": {}}
    by_job: dict[str, int] = {}
    last_at = 0.0
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        if mtime < cutoff_epoch:
            continue
        # ``schedule/output/<job_id>/<run-stamp>.…`` — the parent dir
        # name is the job id. Files written at the top level (no
        # per-job subdir) are bucketed under ``"_misc"``.
        rel = path.relative_to(root)
        job = rel.parts[0] if len(rel.parts) > 1 else "_misc"
        by_job[job] = by_job.get(job, 0) + 1
        if mtime > last_at:
            last_at = mtime
    total = sum(by_job.values())
    return {"count": total, "by_job": by_job, "last_at": last_at}


def _budget_today(home: Path) -> dict[str, Any]:
    try:
        from alpi import config, ledger
        snap = ledger.snapshot(home)
        try:
            cfg = config.load(home)
            cap_kind, cap = ledger._budget(cfg.budget)
        except Exception:  # noqa: BLE001
            cap_kind, cap = (None, 0.0)
        return {
            "usd": float(snap.get("profile", {}).get("usd", 0) or 0),
            "tokens": int(snap.get("profile", {}).get("tokens", 0) or 0),
            "cap_kind": cap_kind,
            "cap": float(cap),
        }
    except Exception:  # noqa: BLE001
        return {"usd": 0.0, "tokens": 0, "cap_kind": None, "cap": 0.0}


def compute(home: Path, since: datetime) -> dict[str, Any]:
    """Walk the profile tree at ``home`` and return a structured report
    of state changes whose mtime is at-or-after ``since``. Side-effect
    free: never writes, never raises on a malformed file (skips it)."""
    cutoff = since.timestamp()
    sessions_local = _scan_sessions(home / "sessions", cutoff)
    sessions_gw = _scan_sessions(home / "gateway" / "sessions", cutoff)
    return {
        "since": since.astimezone(timezone.utc).isoformat(timespec="seconds"),
        "now": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "memory": _scan_memory(home, cutoff),
        "sessions": _facts_dict(sessions_local),
        "gateway_sessions": _facts_dict(sessions_gw),
        "mentions": _scan_mentions(home, cutoff),
        "skills": _scan_skills(home, cutoff),
        "peers": _scan_peers(home, cutoff),
        "schedule_runs": _scan_schedule_runs(home, cutoff),
        "budget_today": _budget_today(home),
    }


def _facts_dict(f: _SessionFacts) -> dict[str, Any]:
    return {
        "count": f.count,
        "turns": f.turns,
        "tool_calls": f.tool_calls,
        "cost_usd": f.cost_usd,
        "tokens": f.tokens,
        "elapsed_s": f.elapsed_s,
        "last_at": f.last_at,
    }


# Rendering

def _fmt_relative(epoch: float, *, now: datetime | None = None) -> str:
    if not epoch:
        return "—"
    base = now or datetime.now(timezone.utc)
    delta = base - datetime.fromtimestamp(epoch, tz=timezone.utc)
    secs = int(delta.total_seconds())
    if secs < 60:
        return f"{secs}s ago"
    if secs < 3600:
        return f"{secs // 60}m ago"
    if secs < 86400:
        return f"{secs // 3600}h ago"
    return f"{secs // 86400}d ago"


def _fmt_duration(secs: float) -> str:
    secs = int(secs)
    if secs < 60:
        return f"{secs}s"
    if secs < 3600:
        return f"{secs // 60}m {secs % 60}s"
    h, rem = divmod(secs, 3600)
    return f"{h}h {rem // 60}m"


def render(report: dict[str, Any], *, profile: str) -> str:
    """Plain-text rendering, no terminal escapes — the TUI formats with
    its own widgets and the CLI is happy without colour. Stable layout:
    one section header per group, ``  key  value`` rows underneath."""
    since = report["since"]
    lines: list[str] = []
    lines.append(f"profile: {profile}")
    lines.append(f"since:   {since}")
    lines.append("")

    mem = report["memory"]
    lines.append("memory")
    if not mem:
        lines.append("  no changes")
    else:
        for entry in mem:
            rel = _fmt_relative(entry["mtime"])
            lines.append(f"  {entry['file']:<14} edited {rel}  ({entry['size']} bytes)")
    lines.append("")

    s = report["sessions"]
    lines.append("sessions (local)")
    if s["count"] == 0:
        lines.append("  no new sessions")
    else:
        lines.append(
            f"  {s['count']} sessions  {s['turns']} turns  "
            f"{s['tool_calls']} tool calls"
        )
        lines.append(
            f"  {_fmt_duration(s['elapsed_s'])} of agent time  "
            f"${s['cost_usd']:.4f} / {s['tokens']} tokens"
        )
        lines.append(f"  last activity  {_fmt_relative(s['last_at'])}")
    lines.append("")

    g = report["gateway_sessions"]
    if g["count"] > 0:
        lines.append("sessions (gateway)")
        lines.append(
            f"  {g['count']} sessions  {g['turns']} turns  "
            f"{g['tool_calls']} tool calls"
        )
        lines.append(
            f"  {_fmt_duration(g['elapsed_s'])} of agent time  "
            f"${g['cost_usd']:.4f} / {g['tokens']} tokens"
        )
        lines.append(f"  last activity  {_fmt_relative(g['last_at'])}")
        lines.append("")

    m = report["mentions"]
    if m["files"]:
        lines.append("mentions")
        lines.append(f"  {m['files']} active threads  ({', '.join(m['peers'])})")
        lines.append("")

    sk = report["skills"]
    lines.append("skills")
    if not sk:
        lines.append("  no installs / changes")
    else:
        for entry in sk:
            lines.append(f"  {entry['name']:<24} {_fmt_relative(entry['mtime'])}")
    lines.append("")

    p = report["peers"]
    lines.append("peers")
    if p["yaml_mtime"] is None:
        lines.append("  no peers configured")
    else:
        status = "list edited " + _fmt_relative(p["yaml_mtime"]) if p["changed"] else "unchanged"
        lines.append(f"  {p['count']} pinned  ({status})")
    lines.append("")

    sched = report["schedule_runs"]
    if sched["count"]:
        lines.append("schedule")
        for job, count in sorted(sched["by_job"].items()):
            lines.append(f"  {job:<24} fired {count}×")
        lines.append("")

    b = report["budget_today"]
    lines.append("budget today")
    if b["cap_kind"] == "usd":
        pct = (b["usd"] / b["cap"] * 100) if b["cap"] else 0
        lines.append(f"  ${b['usd']:.4f} / ${b['cap']:.2f} ({pct:.0f}%)")
    elif b["cap_kind"] == "tokens":
        pct = (b["tokens"] / b["cap"] * 100) if b["cap"] else 0
        lines.append(f"  {b['tokens']} / {int(b['cap'])} tokens ({pct:.0f}%)")
    else:
        lines.append(f"  ${b['usd']:.4f} / {b['tokens']} tokens (uncapped)")
    return "\n".join(lines)
