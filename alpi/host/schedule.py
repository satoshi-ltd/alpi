from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from alpi.host import server as host_server
from alpi.scheduler import jobs_store


# asyncio.create_task is weak-ref; this set keeps the task alive until done_callback drops it.
_BACKGROUND_FIRES: set[asyncio.Task] = set()
# A fire is reserved from the moment it is accepted: the run lock is taken only once a worker picks it up.
_ACCEPTED_FIRES: set[tuple[str, str]] = set()


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
        # jobs_store.read takes a blocking flock — a scheduler mid-write would stall the whole loop.
        jobs = await asyncio.to_thread(jobs_store.read, home)
    except jobs_store.CorruptJobsFile as e:
        raise host_server.HandlerError(
            -32603, "internal-error", data={"detail": f"jobs.json corrupt: {e}"},
        )
    from alpi.scheduler.run import describe_run_timeout, job_state
    for j in jobs:
        if isinstance(j, dict):
            j["status"], nf = job_state(j, home=home)
            j["next_fire"] = nf.isoformat() if nf else None
            j.update(describe_run_timeout(j))
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
        await asyncio.to_thread(jobs_store.update, home, _remove)
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
        await asyncio.to_thread(jobs_store.update, home, _set_paused)
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
        jobs = await asyncio.to_thread(jobs_store.read, home)
    except jobs_store.CorruptJobsFile as e:
        raise host_server.HandlerError(
            -32603, "internal-error", data={"detail": f"jobs.json corrupt: {e}"},
        )
    if not any(isinstance(j, dict) and j.get("id") == job_id for j in jobs):
        raise host_server.HandlerError(
            -32004, "fire-failed", data={"detail": f"no job with id {job_id!r}"},
        )
    if await asyncio.to_thread(jobs_store.is_running, home, job_id):
        raise host_server.HandlerError(
            -32009, "conflict", data={"detail": f"job {job_id!r} is already running; wait for that run to finish"},
        )
    reservation = (str(home), job_id)
    if reservation in _ACCEPTED_FIRES:
        raise host_server.HandlerError(
            -32009, "conflict",
            data={"detail": f"job {job_id!r} was already fired and is waiting to start; wait for that run to finish"},
        )
    _ACCEPTED_FIRES.add(reservation)

    async def _run() -> None:
        from alpi.host import workers
        try:
            result = await workers.submit("turn", fire_by_id, home, job_id)
            if isinstance(result, tuple) and not result[0]:
                logging.getLogger("alpi.host.schedule").info("fire of %s/%s did not run: %s", home, job_id, result[1])
        except Exception as exc:  # noqa: BLE001
            logging.getLogger("alpi.host.schedule").exception(
                "background fire crashed for %s/%s: %s", home, job_id, exc,
            )

    def _finished(done: asyncio.Task) -> None:
        # The only release, and not a `finally` in `_run`: a task cancelled before its first step never enters the coroutine, and a second release would free the next fire's reservation.
        _BACKGROUND_FIRES.discard(done)
        _ACCEPTED_FIRES.discard(reservation)

    task = asyncio.create_task(_run())
    _BACKGROUND_FIRES.add(task)
    task.add_done_callback(_finished)
    return {"ok": True, "id": job_id}


__all__ = ["register"]
