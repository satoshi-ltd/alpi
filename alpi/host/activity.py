from __future__ import annotations

import asyncio
import threading
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from alpi.host import server as host_server


DEBOUNCE_S = 1.0
SCHEDULED_MAX = 20
TITLE_MAX = 80
_ACTIVE_PIPELINE = frozenset({"running", "between"})
_DONE_PHASE = frozenset({"completed", "skipped"})
_TRIGGERS = frozenset({
    "approval.request", "approval.resolved",
    "clarification.request", "clarification.resolved",
    "schedule.changed", "schedule.done", "schedule.failed",
})
_WG_TRIGGERS = frozenset({"wg.post", "wg.done", "wg.blocked", "workgroup_changed"})

_enabled = False
_emit_lock = threading.Lock()
_last_emit: dict[str, float] = {}
_trailing: set[str] = set()

_runs_lock = threading.Lock()
_runs: dict[tuple[str, str], dict[str, Any]] = {}

_cache_lock = threading.Lock()
_wg_cache: dict[str, tuple[tuple, dict[str, Any] | None]] = {}
_wg_seen: dict[tuple[str, str], tuple | None] = {}
_wg_checks: set[tuple[str, str]] = set()
_jobs_cache: dict[str, tuple[tuple, list[dict[str, Any]]]] = {}


def register(server: host_server.Server) -> None:
    global _enabled
    from alpi.host import events as host_events
    _enabled = True
    host_events.add_listener(_on_event)
    server.register("host.activity.list", _list_handler)


def changed(profile: str | None) -> None:
    if not _enabled:
        return
    name = profile or "default"
    with _emit_lock:
        if name in _trailing:
            return
        wait = _last_emit.get(name, float("-inf")) + DEBOUNCE_S - time.monotonic()
        if wait > 0:
            _trailing.add(name)
            _later(wait, _flush, name)
            return
        _last_emit[name] = time.monotonic()
    _emit(name)


def _flush(name: str) -> None:
    with _emit_lock:
        _trailing.discard(name)
        _last_emit[name] = time.monotonic()
    _emit(name)


def _emit(name: str) -> None:
    from alpi.host import events as host_events
    host_events.emit("activity.changed", {"profile": name}, history=False)


def _later(delay: float, fn, *args: Any) -> None:  # noqa: ANN001
    timer = threading.Timer(delay, fn, args=args)
    timer.daemon = True
    timer.start()


def _on_event(kind: str, data: dict[str, Any]) -> None:
    if kind in _TRIGGERS:
        changed(data.get("profile"))
    elif kind in _WG_TRIGGERS and data.get("wg_id"):
        _queue_wg_check(str(data.get("profile") or "default"), str(data["wg_id"]))


def _queue_wg_check(profile: str, wg_id: str) -> None:
    if not _enabled:
        return
    key = (profile, wg_id)
    with _cache_lock:
        if key in _wg_checks:
            return
        _wg_checks.add(key)
    _later(DEBOUNCE_S, _wg_check, profile, wg_id)


def _wg_check(profile: str, wg_id: str) -> None:
    with _cache_lock:
        _wg_checks.discard((profile, wg_id))
    try:
        home = _home_for(profile)
        row = _hub_row(home, profile, wg_id) or _member_row(home, profile, wg_id)
    except Exception:  # noqa: BLE001
        return
    if _note_seen(profile, wg_id, row):
        changed(profile)


def _signature(row: dict[str, Any] | None) -> tuple | None:
    if row is None:
        return None
    return (row["pipeline"], row["phase"], row["phases_done"], row["phases_total"])


def _note_seen(profile: str, wg_id: str, row: dict[str, Any] | None) -> bool:
    sig = _signature(row)
    with _cache_lock:
        before = _wg_seen.get((profile, wg_id))
        _wg_seen[(profile, wg_id)] = sig
    return before != sig


def start_run(profile: str, key: str, **row: Any) -> None:
    with _runs_lock:
        _runs[(profile, key)] = {
            "kind": "turn",
            "profile": profile,
            "session_id": None,
            "title": None,
            "started_at": time.time(),
            "source": "chat",
            **row,
        }
    changed(profile)


def end_run(profile: str, key: str) -> None:
    with _runs_lock:
        existed = _runs.pop((profile, key), None) is not None
    if existed:
        changed(profile)


@contextmanager
def tracked_run(profile: str, key: str, **row: Any) -> Iterator[None]:
    start_run(profile, key, **row)
    try:
        yield
    finally:
        end_run(profile, key)


@contextmanager
def scheduled_run(home: Path, job: dict[str, Any]) -> Iterator[None]:
    from alpi.home import profile_name
    job_id = str(job.get("id") or "?")
    with tracked_run(
        profile_name(home), f"schedule:{job_id}:{uuid.uuid4().hex}",
        source="schedule", title=_job_title(job), job_id=job_id,
    ):
        yield


def title_of(text: Any) -> str | None:
    clean = " ".join(str(text or "").split())
    if not clean:
        return None
    return clean if len(clean) <= TITLE_MAX else clean[: TITLE_MAX - 1] + "…"


def _job_title(job: dict[str, Any]) -> str:
    return str(job.get("title") or f"job {job.get('id', '?')}")


async def _list_handler(
    _params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    return await asyncio.to_thread(snapshot)


def snapshot() -> dict[str, Any]:
    from alpi.host.connection_context import current
    admin = current().role == "admin"
    profiles = _profile_homes()
    allowed = current().profile_scope
    if allowed and not admin:
        profiles = [(name, home) for name, home in profiles if name in allowed]
    return {
        "needs_you": _needs_you(),
        "running": _running_turns(admin) + _running_workgroups(profiles),
        "scheduled": _scheduled(profiles) if admin else [],
    }


def _profile_homes() -> list[tuple[str, Path]]:
    from alpi.host import device_state
    return [(str(p["name"]), Path(p["home"])) for p in device_state._profiles()]


def _home_for(profile: str) -> Path:
    for name, home in _profile_homes():
        if name == profile:
            return home
    raise FileNotFoundError(profile)


def _needs_you() -> list[dict[str, Any]]:
    from alpi.host import approval, clarification
    rows = [{
        "kind": "approval",
        "request_id": m.get("request_id"),
        "profile": m.get("profile"),
        "title": m.get("command"),
        "severity": m.get("severity"),
        "ts": m.get("ts"),
        "timeout_s": m.get("timeout_s"),
        "session_id": m.get("session_id"),
    } for m in approval.pending_requests()]
    rows += [{
        "kind": "clarification",
        "request_id": m.get("request_id"),
        "profile": m.get("profile"),
        "title": m.get("question"),
        "ts": m.get("ts"),
        "timeout_s": m.get("timeout_s"),
        "session_id": m.get("session_id"),
    } for m in clarification.pending_requests()]
    rows.sort(key=lambda r: float(r.get("ts") or 0.0))
    return rows


def _turn_visible(row: dict[str, Any], admin: bool) -> bool:
    from alpi.host.connection_context import can_handle_prompt
    source = row.get("source")
    if source == "schedule":
        return admin
    if source == "workgroup":
        return True
    return can_handle_prompt(row.get("connection_id"), row.get("device_id"))


def _running_turns(admin: bool) -> list[dict[str, Any]]:
    with _runs_lock:
        rows = [dict(r) for r in _runs.values()]
    out = []
    for row in rows:
        if not _turn_visible(row, admin):
            continue
        row.pop("connection_id", None)
        row.pop("device_id", None)
        out.append(row)
    out.sort(key=lambda r: float(r.get("started_at") or 0.0))
    return out


def _running_workgroups(profiles: list[tuple[str, Path]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for profile, home in profiles:
        for wg_id, row in _hub_rows(home, profile) + _member_rows(home, profile):
            if row is None:
                continue
            old = by_id.get(wg_id)
            if old is not None and old.get("_hub"):
                continue
            by_id[wg_id] = row
    out = [{k: v for k, v in r.items() if k != "_hub"} for r in by_id.values()]
    out.sort(key=lambda r: (str(r["profile"]), str(r["name"] or "")))
    return out


def _hub_rows(home: Path, profile: str) -> list[tuple[str, dict[str, Any] | None]]:
    root = home / "alp" / "workgroups"
    try:
        ids = sorted(p.name for p in root.iterdir() if (p / "meta.yaml").is_file())
    except OSError:
        return []
    return [(wg_id, _hub_row(home, profile, wg_id)) for wg_id in ids]


def _hub_row(home: Path, profile: str, wg_id: str) -> dict[str, Any] | None:
    d = home / "alp" / "workgroups" / wg_id
    stamp = []
    for name in ("meta.yaml", "members.yaml", "transcript.jsonl", "ledger.json"):
        try:
            st = (d / name).stat()
            stamp.append((st.st_mtime_ns, st.st_size))
        except OSError:
            stamp.append((0, 0))
    key = f"{profile}\0{d}"
    with _cache_lock:
        hit = _wg_cache.get(key)
    if hit is not None and hit[0] == tuple(stamp):
        return hit[1]
    if stamp[0] == (0, 0):
        return None
    from alpi.alp import workgroup as wg_mod
    wg = wg_mod.load(home, wg_id)
    row = None
    if wg is not None and wg.meta.pipelines:
        row = _pipeline_row(home, profile, wg_id, wg.meta.name, hub=True)
    with _cache_lock:
        _wg_cache[key] = (tuple(stamp), row)
    return row


def _member_rows(home: Path, profile: str) -> list[tuple[str, dict[str, Any] | None]]:
    from alpi.alp import subscription as sub_mod
    try:
        subs = sub_mod.load(home)
    except Exception:  # noqa: BLE001
        return []
    return [
        (sub.wg_id, _pipeline_row(home, profile, sub.wg_id, sub.name, hub=False))
        for sub in subs if sub.pipeline_mode
    ]


def _member_row(home: Path, profile: str, wg_id: str) -> dict[str, Any] | None:
    from alpi.alp import subscription as sub_mod
    sub = sub_mod.get(home, wg_id)
    if sub is None or not sub.pipeline_mode:
        return None
    return _pipeline_row(home, profile, wg_id, sub.name, hub=False)


def _pipeline_row(
    home: Path, profile: str, wg_id: str, name: Any, *, hub: bool,
) -> dict[str, Any] | None:
    from alpi.host import workgroup as host_workgroup
    try:
        run = host_workgroup.fold_task_state(home, wg_id).get("pipeline_run")
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(run, dict) or run.get("status") not in _ACTIVE_PIPELINE:
        return None
    phases = [p for p in run.get("phases") or [] if isinstance(p, dict)]
    return {
        "kind": "workgroup",
        "profile": profile,
        "workgroup_id": wg_id,
        "name": name,
        "pipeline": run.get("pipeline"),
        "phase": run.get("current_phase"),
        "phases_done": sum(1 for p in phases if p.get("state") in _DONE_PHASE),
        "phases_total": len(phases),
        "_hub": hub,
    }


def _jobs(home: Path) -> list[dict[str, Any]]:
    from alpi.scheduler import jobs_store
    stamp = []
    for path in (jobs_store.jobs_path(home), jobs_store.runs_path(home)):
        try:
            st = path.stat()
            stamp.append((st.st_mtime_ns, st.st_size))
        except OSError:
            stamp.append((0, 0))
    key = str(home)
    with _cache_lock:
        hit = _jobs_cache.get(key)
    if hit is not None and hit[0] == tuple(stamp):
        return hit[1]
    if stamp[0] == (0, 0):
        jobs: list[dict[str, Any]] = []
    else:
        try:
            jobs = [j for j in jobs_store.read(home) if isinstance(j, dict)]
        except Exception:  # noqa: BLE001
            return []
    with _cache_lock:
        _jobs_cache[key] = (tuple(stamp), jobs)
    return jobs


def _scheduled(profiles: list[tuple[str, Path]]) -> list[dict[str, Any]]:
    from alpi.scheduler.run import next_fire
    rows: list[dict[str, Any]] = []
    for profile, home in profiles:
        for job in _jobs(home):
            if job.get("paused"):
                continue
            try:
                nf = next_fire(job, home=home)
            except Exception:  # noqa: BLE001
                nf = None
            rows.append({
                "profile": profile,
                "job_id": str(job.get("id") or ""),
                "title": _job_title(job),
                "next_fire": nf.isoformat() if nf else None,
                "last_run_at": job.get("last_run_at"),
                "last_run_status": job.get("last_run_status"),
                "_at": nf.timestamp() if nf else float("inf"),
            })
    rows.sort(key=lambda r: r["_at"])
    failed = [r for r in rows if r["last_run_status"] == "error"]
    keep = failed[:SCHEDULED_MAX]
    for row in rows:
        if len(keep) >= SCHEDULED_MAX:
            break
        if row["last_run_status"] != "error":
            keep.append(row)
    keep.sort(key=lambda r: r["_at"])
    return [{k: v for k, v in r.items() if k != "_at"} for r in keep]


def _reset_for_tests() -> None:
    global _enabled
    _enabled = False
    with _emit_lock:
        _last_emit.clear()
        _trailing.clear()
    with _runs_lock:
        _runs.clear()
    with _cache_lock:
        _wg_cache.clear()
        _wg_seen.clear()
        _wg_checks.clear()
        _jobs_cache.clear()


__all__ = [
    "changed", "end_run", "register", "scheduled_run", "snapshot",
    "start_run", "title_of", "tracked_run",
]
