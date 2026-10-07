from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
from pathlib import Path
from typing import Any

log = logging.getLogger("alpi.attention")
NEAR_PCT = 90
SECTIONS = ("memory", "skills", "schedules")
MESSAGE_CAP = 200
TITLE_CAP = 80
FLOOD_LIMIT = 3
_reconcile_lock = threading.Lock()


def _cap(value: Any, cap: int) -> str:
    from alpi._redact import redact

    return str(redact(str(value or "")))[:cap]


def _memory(home: Path) -> list[dict[str, Any]]:
    from alpi.memory import MemoryStore

    items = []
    for name, (used, limit) in MemoryStore(home).usage().items():
        if limit and used * 100 >= limit * NEAR_PCT:
            items.append({
                "file": name, "used": used, "limit": limit,
                "pct": round(used / limit * 100), "over": used > limit,
            })
    return items


def _skills(home: Path) -> list[dict[str, Any]]:
    from alpi.home import effective_profile_env
    from alpi.host.device_state import _skills as list_skills
    from alpi.tools import skill as skill_mod

    env = effective_profile_env(home)
    cfg = skill_mod._load_cfg_raw(home)
    items = []
    for row in list_skills(home):
        try:
            meta = skill_mod._frontmatter(Path(row["path"]))
            status, reason = skill_mod.skill_status(meta, env=env, cfg_raw=cfg)
        except OSError as e:
            status, reason = "invalid", f"SKILL.md could not be read ({e.__class__.__name__})"
        if status == "invalid":
            problem = "lint"
        elif status == "inactive" and reason.startswith("missing"):
            problem = "missing"
        else:
            continue
        items.append({
            "name": row["name"], "category": row.get("category"),
            "problem": problem, "message": _cap(reason, MESSAGE_CAP),
        })
    return items


def _schedules(home: Path) -> list[dict[str, Any]]:
    from alpi.scheduler import jobs_store

    try:
        jobs = jobs_store.read(home)
    except jobs_store.CorruptJobsFile:
        return []
    items = []
    for job in jobs:
        if not isinstance(job, dict) or job.get("paused") or job.get("last_run_status") != "error":
            continue
        items.append({
            "id": str(job.get("id") or ""),
            "title": _cap(job.get("title") or str(job.get("prompt") or "")[:60].replace("\n", " "), TITLE_CAP),
            "message": _cap(job.get("last_run_message"), MESSAGE_CAP),
            "at": job.get("last_run_at"),
            "last_ok_at": job.get("last_ok_at"),
        })
    return items


def collect(home: Path) -> dict[str, Any]:
    sections = {"memory": _memory(home), "skills": _skills(home), "schedules": _schedules(home)}
    counts = {name: len(items) for name, items in sections.items()}
    return {**sections, "counts": counts, "total": sum(counts.values())}


def _keys(data: dict[str, Any]) -> dict[str, bool]:
    keys: dict[str, bool] = {}
    for item in data["memory"]:
        keys[f"memory:{item['file']}:{'over' if item['over'] else 'near'}"] = True
    for item in data["skills"]:
        keys[f"skill:{item['category'] or ''}/{item['name']}:{item['problem']}"] = True
    for item in data["schedules"]:
        keys[f"schedule:{item['id']}:{item['at']}"] = False
    return keys


def _state_path(home: Path) -> Path:
    return home / "attention.json"


def _load_state(home: Path) -> set[str] | None:
    try:
        raw = json.loads(_state_path(home).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    keys = raw.get("keys") if isinstance(raw, dict) else None
    return {str(k) for k in keys} if isinstance(keys, list) else None


def _save_state(home: Path, keys: set[str]) -> bool:
    tmp = ""
    try:
        fd, tmp = tempfile.mkstemp(dir=str(home), prefix=".attention.", suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump({"keys": sorted(keys)}, handle)
        os.replace(tmp, _state_path(home))
        return True
    except OSError:
        if tmp:
            try:
                os.unlink(tmp)
            except OSError:
                pass
        return False


def _warning(item_key: str, data: dict[str, Any]) -> tuple[str, str] | None:
    kind, _, rest = item_key.partition(":")
    if kind == "memory":
        name = rest.split(":")[0]
        item = next(i for i in data["memory"] if i["file"] == name)
        if item["over"]:
            return (f"Memory over its limit: {name}",
                    f"{name} holds {item['used']:,} of {item['limit']:,} characters; every turn pays for the part that does not fit.")
        return (f"Memory nearly full: {name}",
                f"{name} holds {item['used']:,} of {item['limit']:,} characters ({item['pct']}%).")
    if kind == "skill":
        ident = rest.rsplit(":", 1)[0]
        category, _, name = ident.rpartition("/")
        item = next(i for i in data["skills"] if i["name"] == name and (i["category"] or "") == category)
        where = f"{category}/{name}" if category else name
        if item["problem"] == "lint":
            return (f"Skill does not pass lint: {where}", f"{item['message']}. The skill is not offered to the model until it passes.")
        return (f"Skill is missing what it requires: {where}", f"{item['message']}. The skill stays inactive until it is provided.")
    return None


def reconcile(home: Path) -> dict[str, Any]:
    from alpi import outputs as outputs_mod
    from alpi.home import profile_name
    from alpi.host import events as host_events

    with _reconcile_lock:
        data = collect(home)
        keys = _keys(data)
        stored = _load_state(home)
        previous = stored or set()
        current = set(keys)
        if stored is not None and current == previous:
            return data
        profile = profile_name(home)
        if not _save_state(home, current):
            log.warning("attention state at %s is not writable; no notification is filed", _state_path(home))
            host_events.emit("attention.changed", {"profile": profile, "counts": data["counts"], "total": data["total"]})
            return data
        fresh = []
        for key in sorted(current - previous):
            warning = _warning(key, data) if keys[key] else None
            if warning is not None:
                fresh.append((key, *warning))
        if len(fresh) > FLOOD_LIMIT:
            body = "Details are in the profile's Memories, Skills and Schedules panels, or `alpi profile show`.\n" + "\n".join(f"- {title}" for _, title, _ in fresh)
            fresh = [(",".join(key for key, _, _ in fresh), f"{len(fresh)} items need you", body)]
        failed: set[str] = set()
        for key, title, body in fresh:
            try:
                output = outputs_mod.append(home, profile=profile, body=body, type="warning", title=title, delivered_to=[])
                host_events.emit("output.created", {"profile": profile, "id": output["id"], "type": "warning"})
            except Exception as e:  # noqa: BLE001
                failed.update(key.split(","))
                log.warning("could not file the attention warning %r, retrying next tick: %s", title, e)
        if failed:
            _save_state(home, current - failed)
        if current != previous:
            host_events.emit("attention.changed", {"profile": profile, "counts": data["counts"], "total": data["total"]})
        return data


def lines(data: dict[str, Any]) -> list[str]:
    out = []
    for item in data["memory"]:
        state = "over its limit" if item["over"] else "nearly full"
        out.append(f"memory: {item['file']} {state} ({item['used']:,}/{item['limit']:,})")
    for item in data["skills"]:
        problem = "fails lint" if item["problem"] == "lint" else "inactive"
        out.append(f"skill: {item['name']} {problem} — {item['message']}")
    for item in data["schedules"]:
        detail = f" — {item['message']}" if item["message"] else ""
        out.append(f"schedule: {item['title']} failed{detail}")
    return out
