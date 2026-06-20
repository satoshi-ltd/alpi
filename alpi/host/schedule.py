from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from alpi.host import server as host_server
from alpi.scheduler import jobs_store


# asyncio.create_task is weak-ref; this set keeps the task alive until done_callback drops it.
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


async def _schedule_list(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    profile = str((params or {}).get("profile") or "")
    home = _resolve_home(profile)
    try:
        jobs = jobs_store.read(home)
    except jobs_store.CorruptJobsFile as e:
        raise host_server.HandlerError(
            -32603, "internal-error", data={"detail": f"jobs.json corrupt: {e}"},
        )
    return {"jobs": jobs}


async def _schedule_remove(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    from alpi.host.handlers import _check_id

    profile = str((params or {}).get("profile") or "")
    job_id = str((params or {}).get("id") or "").strip()
    _check_id(job_id, "id")
    home = _resolve_home(profile)
    if not jobs_store.jobs_path(home).exists():
        raise host_server.HandlerError(
            -32004, "not-found", data={"detail": "no jobs.json"},
        )

    def _remove(jobs: list[dict]) -> list[dict]:
        keep = [j for j in jobs if j.get("id") != job_id]
        if len(keep) == len(jobs):
            raise host_server.HandlerError(
                -32004, "not-found", data={"detail": f"no job {job_id!r}"},
            )
        return keep
    try:
        jobs_store.update(home, _remove)
    except jobs_store.CorruptJobsFile as e:
        raise host_server.HandlerError(
            -32603, "internal-error", data={"detail": f"jobs.json corrupt: {e}"},
        )
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
    if not jobs_store.jobs_path(home).exists():
        raise host_server.HandlerError(
            -32004, "not-found", data={"detail": "no jobs.json"},
        )

    def _set_paused(jobs: list[dict]) -> list[dict]:
        for j in jobs:
            if j.get("id") == job_id:
                j["paused"] = paused
                return jobs
        raise host_server.HandlerError(
            -32004, "not-found", data={"detail": f"no job {job_id!r}"},
        )
    try:
        jobs_store.update(home, _set_paused)
    except jobs_store.CorruptJobsFile as e:
        raise host_server.HandlerError(
            -32603, "internal-error", data={"detail": f"jobs.json corrupt: {e}"},
        )
    _emit_schedule_changed(home, job_id, "paused" if paused else "resumed")
    return {"ok": True, "paused": paused}


async def _schedule_fire(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    import logging

    from alpi.host.handlers import _check_id
    from alpi.scheduler.run import fire_by_id

    profile = str((params or {}).get("profile") or "")
    job_id = str((params or {}).get("id") or "").strip()
    _check_id(job_id, "id")
    home = _resolve_home(profile)

    try:
        jobs = jobs_store.read(home)
    except jobs_store.CorruptJobsFile as e:
        raise host_server.HandlerError(
            -32603, "internal-error", data={"detail": f"jobs.json corrupt: {e}"},
        )
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
