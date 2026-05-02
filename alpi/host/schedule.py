from __future__ import annotations

import json
from typing import Any

from alpi.host import server as host_server


def register(server: host_server.Server) -> None:
    server.register("host.schedule.list", _schedule_list)
    server.register("host.schedule.remove", _schedule_remove)
    server.register("host.schedule.set_paused", _schedule_set_paused)
    server.register("host.schedule.fire", _schedule_fire)


def _resolve_home(profile: str):
    from alpi.host.handlers import _resolve_home as _r
    return _r(profile)


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
    p.write_text(json.dumps(keep, indent=2))
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
    p.write_text(json.dumps(jobs, indent=2))
    return {"ok": True, "paused": paused}


async def _schedule_fire(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    from alpi.host.handlers import _check_id
    from alpi.scheduler.run import fire_by_id

    profile = str((params or {}).get("profile") or "")
    job_id = str((params or {}).get("id") or "").strip()
    _check_id(job_id, "id")
    home = _resolve_home(profile)
    ok, msg = fire_by_id(home, job_id)
    if not ok:
        raise host_server.HandlerError(
            -32004, "fire-failed", data={"detail": msg},
        )
    return {"ok": True, "detail": msg}


__all__ = ["register"]
