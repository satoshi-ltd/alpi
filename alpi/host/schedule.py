from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

from alpi.host import server as host_server


# Strong references to in-flight fire-and-forget tasks. asyncio.create_task only holds a weak ref, so without this a long-running fire (up to 10 min) could be GC'd mid-flight; the discard callback drops the entry when the task finishes.
_BACKGROUND_FIRES: set[asyncio.Task] = set()


def register(server: host_server.Server) -> None:
    server.register("host.schedule.list", _schedule_list)
    server.register("host.schedule.remove", _schedule_remove)
    server.register("host.schedule.set_paused", _schedule_set_paused)
    server.register("host.schedule.fire", _schedule_fire)


def _resolve_home(profile: str):
    from alpi.host.handlers import _resolve_home as _r
    return _r(profile)


def _emit_schedule_changed(home: Path, job_id: str, action: str) -> None:
    from alpi import home as home_mod
    from alpi.host import events as host_events
    host_events.emit("schedule.changed", {
        "profile": home_mod.profile_name(home),
        "id": job_id,
        "action": action,
    })


def _atomic_write_json(path: Path, payload: Any) -> None:
    """tmp + rename so a crash mid-write never leaves a half-written jobs.json that would silently empty the schedule on next read."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json.dumps(payload, indent=2))
            f.flush()
            os.fsync(f.fileno())
    except Exception:
        try: tmp.unlink()
        except OSError: pass
        raise
    os.replace(str(tmp), str(path))


async def _schedule_list(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    profile = str((params or {}).get("profile") or "")
    home = _resolve_home(profile)
    p = home / "schedule" / "jobs.json"
    if not p.exists():
        return {"jobs": []}
    try:
        jobs = json.loads(p.read_text()) or []
    except json.JSONDecodeError:
        return {"jobs": []}
    return {"jobs": jobs}


async def _schedule_remove(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    from alpi.host.handlers import _check_id

    profile = str((params or {}).get("profile") or "")
    job_id = str((params or {}).get("id") or "").strip()
    _check_id(job_id, "id")
    home = _resolve_home(profile)
    p = home / "schedule" / "jobs.json"
    if not p.exists():
        raise host_server.HandlerError(
            -32004, "not-found", data={"detail": "no jobs.json"},
        )
    try:
        jobs = json.loads(p.read_text()) or []
    except json.JSONDecodeError:
        raise host_server.HandlerError(
            -32603, "internal-error", data={"detail": "jobs.json corrupt"},
        )
    keep = [j for j in jobs if j.get("id") != job_id]
    if len(keep) == len(jobs):
        raise host_server.HandlerError(
            -32004, "not-found", data={"detail": f"no job {job_id!r}"},
        )
    _atomic_write_json(p, keep)
    _emit_schedule_changed(home, job_id, "removed")
    return {"ok": True}


async def _schedule_set_paused(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    from alpi.host.handlers import _check_id

    profile = str((params or {}).get("profile") or "")
    job_id = str((params or {}).get("id") or "").strip()
    paused = bool((params or {}).get("paused", False))
    _check_id(job_id, "id")
    home = _resolve_home(profile)
    p = home / "schedule" / "jobs.json"
    if not p.exists():
        raise host_server.HandlerError(
            -32004, "not-found", data={"detail": "no jobs.json"},
        )
    try:
        jobs = json.loads(p.read_text()) or []
    except json.JSONDecodeError:
        raise host_server.HandlerError(
            -32603, "internal-error", data={"detail": "jobs.json corrupt"},
        )
    found = False
    for j in jobs:
        if j.get("id") == job_id:
            j["paused"] = paused
            found = True
            break
    if not found:
        raise host_server.HandlerError(
            -32004, "not-found", data={"detail": f"no job {job_id!r}"},
        )
    _atomic_write_json(p, jobs)
    _emit_schedule_changed(home, job_id, "paused" if paused else "resumed")
    return {"ok": True, "paused": paused}


async def _schedule_fire(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    """Fire-and-forget: validate the job id synchronously (so a stale id from the UI still returns -32004 instead of silently dropping into a background failure), then schedule the run and return. A blocking wait would freeze the UI for the agent's whole runtime (often 20-60s, up to 10 min). `fire_by_id` itself emits `schedule.done` / `schedule.failed` when the job finishes."""
    import logging

    from alpi.host.handlers import _check_id
    from alpi.scheduler.run import fire_by_id

    profile = str((params or {}).get("profile") or "")
    job_id = str((params or {}).get("id") or "").strip()
    _check_id(job_id, "id")
    home = _resolve_home(profile)

    jobs_path = home / "schedule" / "jobs.json"
    try:
        jobs = json.loads(jobs_path.read_text()) if jobs_path.exists() else []
    except (OSError, json.JSONDecodeError):
        jobs = []
    if not any(isinstance(j, dict) and j.get("id") == job_id for j in jobs):
        raise host_server.HandlerError(
            -32004, "fire-failed", data={"detail": f"no job with id {job_id!r}"},
        )

    async def _run() -> None:
        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(None, fire_by_id, home, job_id)
        except Exception as exc:  # noqa: BLE001
            logging.getLogger("alpi.host.schedule").exception(
                "background fire crashed for %s/%s: %s", home, job_id, exc,
            )

    task = asyncio.create_task(_run())
    _BACKGROUND_FIRES.add(task)
    task.add_done_callback(_BACKGROUND_FIRES.discard)
    return {"ok": True, "id": job_id}


__all__ = ["register"]
