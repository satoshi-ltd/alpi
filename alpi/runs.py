from __future__ import annotations

import json
import math
import os
import re
import signal
import threading
import time
from collections.abc import Callable
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from alpi._redact import redact
from alpi.core.run_context import RunContext, current as current_run


FORMAT_VERSION = 1
MAX_EVENT_BYTES = 32 * 1024
MAX_TEXT_BYTES = 12 * 1024
MAX_LIST_LIMIT = 200

_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()
_seq: dict[str, int] = {}
_active: dict[tuple[str, str], tuple[str, Any]] = {}
_active_lock = threading.Lock()
_SAFE_RUN_ID = re.compile(r"^[A-Za-z0-9_-]+$")
# Streaming transport only: every assistant_done is kept (final=True marks the deliverable) and the reconnect replay is the sessions sidecar.
_TRANSIENT_KINDS = frozenset({"reasoning_delta", "assistant_delta"})


def run_path(home: Path, run_id: str) -> Path:
    if not _SAFE_RUN_ID.fullmatch(run_id or ""):
        raise ValueError("invalid run id")
    return home / "runs" / f"{run_id}.jsonl"


def _lock(path: Path) -> threading.Lock:
    key = str(path)
    with _locks_guard:
        value = _locks.get(key)
        if value is None:
            value = threading.Lock()
            _locks[key] = value
        return value


def _clip_text(value: str) -> str:
    raw = value.encode("utf-8", errors="replace")
    if len(raw) <= MAX_TEXT_BYTES:
        return value
    suffix = "…".encode()
    return raw[: MAX_TEXT_BYTES - len(suffix)].decode("utf-8", errors="ignore") + "…"


def _bounded(value: Any) -> Any:
    if isinstance(value, str):
        return _clip_text(value)
    if isinstance(value, dict):
        return {str(k): _bounded(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_bounded(item) for item in value]
    return value


def persisted_tool_arguments(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    safe = dict(arguments)
    if name == "terminal":
        safe.pop("command", None)
    elif name == "workflow":
        raw_steps = safe.get("steps")
        if not isinstance(raw_steps, list):
            return safe
        steps = []
        for raw in raw_steps:
            if not isinstance(raw, dict):
                steps.append(raw)
                continue
            step = dict(raw)
            nested_name = str(step.get("tool") or "")
            nested_args = step.get("arguments")
            if isinstance(nested_args, dict):
                step["arguments"] = persisted_tool_arguments(nested_name, nested_args)
            steps.append(step)
        safe["steps"] = steps
    return safe


def _last_seq(path: Path) -> int:
    cached = _seq.get(str(path))
    if cached is not None:
        return cached
    last = -1
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    row = json.loads(line)
                    if isinstance(row, dict):
                        last = max(last, int(row.get("seq", -1)))
                except (ValueError, TypeError):
                    continue
    except OSError:
        pass
    return last


def append(home: Path, run_id: str, kind: str, data: dict[str, Any] | None = None) -> dict:
    path = run_path(home, run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.parent.is_symlink():
        raise OSError("run journal directory must not be a symlink")
    try:
        os.chmod(path.parent, 0o700)
    except OSError:
        pass
    with _lock(path):
        seq = _last_seq(path) + 1
        payload = _bounded(redact(data or {}))
        record = {
            "version": FORMAT_VERSION,
            "seq": seq,
            "at": time.time(),
            "kind": str(kind),
            "data": payload,
        }
        encoded = json.dumps(record, ensure_ascii=False, default=str)
        if len(encoded.encode()) > MAX_EVENT_BYTES:
            record["data"] = {"truncated": True, "preview": _clip_text(encoded)}
            encoded = json.dumps(record, ensure_ascii=False)
        flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(str(path), flags, 0o600)
        try:
            os.fchmod(fd, 0o600)
        except OSError:
            os.close(fd)
            raise
        with os.fdopen(fd, "a", encoding="utf-8") as handle:
            handle.write(encoded + "\n")
            handle.flush()
        _seq[str(path)] = seq
        return record


def start(context: RunContext, *, model: str = "", input_text: str = "") -> None:
    from alpi.session import sessions_lock

    # Shared with Session.save and the retention sweep: a run that names its session here cannot
    # slip in between the sweep's check and its delete.
    with sessions_lock(context.home / "sessions", exclusive=False):
        _start(context, model=model, input_text=input_text)


def _start(context: RunContext, *, model: str, input_text: str) -> None:
    append(context.home, context.run_id, "run.started", {
        "run_id": context.run_id,
        "profile": context.profile,
        "source": context.source,
        "session_id": context.session_id,
        "connection_id": context.connection_id,
        "device_id": context.device_id,
        "role": context.role,
        "job_id": context.job_id,
        "workgroup_id": context.workgroup_id,
        "workspace": str(context.workspace),
        "pid": os.getpid(),
        "pid_start": proc_starttime(os.getpid()),
        "model": model,
        "input": input_text,
    })


def register_active(context: RunContext, engine: Any) -> None:
    with _active_lock:
        _active[(context.profile, context.run_id)] = (context.connection_id, engine)


def unregister_active(context: RunContext) -> None:
    with _active_lock:
        _active.pop((context.profile, context.run_id), None)


def active(profile: str, run_id: str) -> tuple[str, Any] | None:
    with _active_lock:
        return _active.get((profile, run_id))


def active_ids(profile: str) -> set[str]:
    with _active_lock:
        return {run_id for (owner_profile, run_id) in _active if owner_profile == profile}


def finish(context: RunContext, outcome: str) -> None:
    _last_model_state.pop(context.run_id, None)
    path = run_path(context.home, context.run_id)
    forget_children(context.home, context.run_id)
    try:
        append(context.home, context.run_id, "run.finished", {"outcome": outcome})
    finally:
        key = str(path)
        with _locks_guard:
            _seq.pop(key, None)
            _locks.pop(key, None)


_OWNER_ENV = "ALPI_SPAWNED_BY"


def owner_stamp() -> str:
    start = proc_starttime(os.getpid())
    return f"{os.getpid()}-{start}" if start else ""


def stamp_env(env: dict[str, str]) -> dict[str, str]:
    # Inherited through every exec, so a survivor stays identifiable after its group loses its leader.
    stamp = owner_stamp()
    return {**env, _OWNER_ENV: stamp} if stamp else dict(env)


def _all_pids() -> list[int]:
    try:
        return [int(name) for name in os.listdir("/proc") if name.isdigit()]
    except OSError:
        return []


def _environ_of(pid: int) -> bytes:
    try:
        with open(f"/proc/{pid}/environ", "rb") as handle:
            return handle.read()
    except OSError:
        return b""


def _stamped_pids(needle: bytes) -> list[int]:
    ours = {os.getpid(), os.getppid()}
    return [
        pid for pid in _all_pids()
        if pid not in ours and needle in _environ_of(pid).split(b"\0")
    ]


def _open_pidfd(pid: int) -> int | None:
    try:
        return os.pidfd_open(pid)
    except (AttributeError, OSError):
        return None


def _kill_pidfd(fd: int) -> bool:
    try:
        signal.pidfd_send_signal(fd, signal.SIGKILL)
        return True
    except (AttributeError, OSError):
        return False


def _close_pidfd(fd: int) -> None:
    try:
        os.close(fd)
    except OSError:
        pass


def kill_stamped_survivors(pid: int, pid_start: str) -> int:
    """Kill what outlived a run's process groups; the inherited stamp is the proof of ownership."""
    if pid <= 0 or not pid_start:
        return 0
    needle = f"{_OWNER_ENV}={pid}-{pid_start}".encode()
    killed = 0
    for target in _stamped_pids(needle):
        fd = _open_pidfd(target)
        # A bare pid is a stale read by the time it is signalled; the handle is what makes the
        # identity hold, so re-read the stamp only once it is bound and never signal without it.
        if fd is None:
            continue
        try:
            if needle in _environ_of(target).split(b"\0") and _kill_pidfd(fd):
                killed += 1
        finally:
            _close_pidfd(fd)
    return killed


def children_path(home: Path, run_id: str) -> Path:
    return run_path(home, run_id).with_suffix(".children")


def record_child(context: RunContext, pid: int) -> None:
    # A detached child outlives the signal that ends its run; this list is the only way back.
    if pid <= 0:
        return
    start = proc_starttime(pid)
    # No proof of identity later would mean signalling whoever inherits the pid instead.
    if not start:
        return
    path = children_path(context.home, context.run_id)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(str(path), flags, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as handle:
            handle.write(json.dumps({"pgid": int(pid), "start": start}) + "\n")
    except (OSError, ValueError):
        pass


def record_current_child(pid: int) -> None:
    context = current_run()
    if context is not None:
        record_child(context, pid)


def _recorded_children(home: Path, run_id: str) -> list[tuple[int, str]]:
    try:
        raw = children_path(home, run_id).read_text(encoding="utf-8")
    except (OSError, ValueError):
        return []
    out: list[tuple[int, str]] = []
    for line in raw.splitlines():
        try:
            row = json.loads(line)
            pgid, start = int(row["pgid"]), str(row["start"])
        except (ValueError, TypeError, KeyError):
            continue
        if pgid > 0 and start:
            out.append((pgid, start))
    return out


def kill_child_groups(home: Path, run_id: str, *, pid: int = 0, pid_start: str = "") -> int:
    """Signal every process group this run detached, then whatever outlived a leaderless one."""
    killed = 0
    for pgid, start in _recorded_children(home, run_id):
        if pgid in (os.getpid(), os.getppid()):
            continue
        if proc_starttime(pgid) != start:
            continue
        try:
            # Only when it still leads its own group: anything else is a group we do not own.
            if os.getpgid(pgid) != pgid:
                continue
            os.killpg(pgid, signal.SIGKILL)
        except (OSError, AttributeError):
            continue
        killed += 1
    # Groups first, always: signalling a marked leader reaps it, and an unmarked child left in
    # its group then belongs to a group nothing can vouch for any more.
    return killed + kill_stamped_survivors(pid, pid_start)


def kill_run_leftovers(home: Path, run_id: str) -> int:
    """Everything a run left running, for a supervisor closing its journal by hand."""
    try:
        started = (_first_record(run_path(home, run_id)) or {}).get("data") or {}
    except (OSError, ValueError):
        return 0
    return kill_child_groups(
        home, run_id,
        pid=_safe_int(started.get("pid")), pid_start=str(started.get("pid_start") or ""),
    )


def forget_children(home: Path, run_id: str) -> None:
    try:
        children_path(home, run_id).unlink()
    except (OSError, ValueError):
        pass


def finish_if_running(home: Path, run_id: str, outcome: str) -> bool:
    """Close a child-owned run journal when its supervising process exits first."""
    try:
        row = summary(home, run_id)
    except (FileNotFoundError, OSError, ValueError):
        return False
    if row.get("status") != "running":
        return False
    path = run_path(home, run_id)
    try:
        append(home, run_id, "run.finished", {"outcome": outcome})
    finally:
        key = str(path)
        with _locks_guard:
            _seq.pop(key, None)
            _locks.pop(key, None)
    forget_children(home, run_id)
    return True


def usage_summary(home: Path, run_id: str) -> dict[str, Any]:
    """Sum recorded completion usage for one durable run."""
    totals: dict[str, Any] = {
        "usd": 0.0, "tokens": 0, "tokens_in": 0, "tokens_out": 0,
    }
    after_seq = -1
    while True:
        try:
            page = read(home, run_id, after_seq=after_seq, limit=5000)
        except (FileNotFoundError, OSError, ValueError):
            return totals
        events = page["events"]
        for event in events:
            if event.get("kind") != "agent.usage":
                continue
            data = event.get("data") or {}
            tokens_in = max(0, _safe_int(data.get("tokens_in")))
            tokens_out = max(0, _safe_int(data.get("tokens_out")))
            totals["usd"] += max(0.0, _safe_float(data.get("cost")))
            totals["tokens_in"] += tokens_in
            totals["tokens_out"] += tokens_out
        if not events or int(page["next_seq"]) <= after_seq:
            break
        after_seq = int(page["next_seq"])
        if len(events) < 5000:
            break
    totals["tokens"] = totals["tokens_in"] + totals["tokens_out"]
    return totals


SILENCE_GRACE_S = 300.0

# run_id -> (updated_at it went quiet at, monotonic time the sweep first saw it past threshold).
# Silence is judged on the wall clock; a live pid is only killed once this process has also watched it stay quiet for a grace on the monotonic clock, so a clock step or a wake from suspend can never kill a healthy child on its own.
_silence_seen: dict[str, tuple[float, float]] = {}


def proc_starttime(pid: int) -> str | None:
    # /proc/<pid>/stat field 22 — survives container PID reuse. None on non-Linux.
    try:
        with open(f"/proc/{pid}/stat", "rb") as f:
            data = f.read()
    except OSError:
        return None
    rparen = data.rfind(b")")
    if rparen < 0:
        return None
    tail = data[rparen + 1:].split()
    if len(tail) < 20:
        return None
    try:
        return tail[19].decode("ascii")
    except UnicodeDecodeError:
        return None


def running_journals(home: Path, now: float) -> list[tuple[dict, dict, int, float]]:
    """Every journal still marked running, with its start data, pid and seconds since its last event."""
    out: list[tuple[dict, dict, int, float]] = []
    directory = home / "runs"
    if not directory.exists() or directory.is_symlink():
        return out
    try:
        paths = list(directory.glob("*.jsonl"))
    except OSError:
        return out
    for path in paths:
        if path.is_symlink():
            continue
        try:
            row = summary(home, path.stem)
        except (OSError, ValueError):
            continue
        if row.get("status") != "running":
            continue
        try:
            first = _first_record(path) or {}
            started = first.get("data") or {}
            pid = _safe_int(started.get("pid"))
            age = now - float(row.get("updated_at") or 0.0)
        except (OSError, TypeError, ValueError):
            continue
        out.append((row, started, pid, age))
    return out


def _closed_row(row: dict, started: dict, age: float, reason: str, **extra: Any) -> dict[str, Any]:
    return {
        "run_id": str(row["id"]),
        "job_id": str(started.get("job_id") or ""),
        "source": str(started.get("source") or ""),
        "silent_for_s": round(age, 1),
        "reason": reason,
        "journal_closed": True,
        "pid_killed": False,
        **extra,
    }


def reconcile_stale(
    home: Path,
    *,
    older_than_s: float = 3600.0,
    journals: list[tuple[dict, dict, int, float]] | None = None,
) -> list[dict[str, Any]]:
    """Close journals whose process is gone.

    Returns one row per closed journal so the caller can alert: a run whose
    daemon died never reaches the scheduler's own failure path, so this is the
    only place its death can be reported.
    """
    now = time.time()
    closed: list[dict[str, Any]] = []
    rows = journals if journals is not None else running_journals(home, now)
    for row, started, pid, age in rows:
        if pid > 0 and _pid_alive(pid):
            continue
        if pid <= 0 and age < older_than_s:
            continue
        run_id = str(row["id"])
        # Before the close, which forgets them; a journal with no pid never recorded one.
        killed = kill_child_groups(
            home, run_id, pid=pid, pid_start=str(started.get("pid_start") or ""),
        ) if pid > 0 else 0
        if finish_if_running(home, run_id, "interrupted"):
            _silence_seen.pop(run_id, None)
            extra = {"child_groups_killed": killed} if killed else {}
            closed.append(_closed_row(row, started, age, "dead", pid_recorded=pid > 0, **extra))
    return closed


def reconcile_silent(
    home: Path,
    *,
    timeout_for_job: Callable[[str], int | None],
    grace_s: float = SILENCE_GRACE_S,
    now: float | None = None,
    now_mono: float | None = None,
    journals: list[tuple[dict, dict, int, float]] | None = None,
) -> list[dict[str, Any]]:
    """Report scheduled runs that have written nothing for longer than their job allows.

    The pid check cannot see a child that is alive but wedged, and the
    scheduler's own timeout did not end two such runs in production: they sat
    in ``running`` for 20 and 30 hours. A healthy run emits an event on every
    tool call and model step, so silence past the job timeout plus a grace has
    no legitimate cause. Only runs with a job are judged — a job is the only
    thing that says how long a run may take.

    A live pid is killed only when it is provably this run's process: same
    start time as the one the child recorded at run start. Anything else that
    is alive is reported but left untouched, journal included — writing a
    ``run.finished`` under a writer that may still append would corrupt it.
    """
    now = time.time() if now is None else now
    now_mono = time.monotonic() if now_mono is None else now_mono
    rows = journals if journals is not None else running_journals(home, now)
    out: list[dict[str, Any]] = []
    for row, started, pid, age in rows:
        run_id = str(row["id"])
        job_id = str(started.get("job_id") or "")
        if not job_id:
            continue
        timeout = timeout_for_job(job_id)
        if not timeout:
            continue
        updated_at = float(row.get("updated_at") or 0.0)
        if age <= float(timeout) + grace_s:
            _silence_seen.pop(run_id, None)
            continue
        seen = _silence_seen.get(run_id)
        if seen is None or seen[0] != updated_at:
            _silence_seen[run_id] = (updated_at, now_mono)
            continue
        if now_mono - seen[1] < grace_s:
            continue
        extra: dict[str, Any] = {"timeout_s": int(timeout)}
        if pid > 0 and _pid_alive(pid):
            if not _is_this_runs_process(pid, started):
                out.append(_closed_row(row, started, age, "silent", journal_closed=False, **extra))
                continue
            try:
                os.kill(pid, signal.SIGKILL)
                extra["pid_killed"] = True
            except ProcessLookupError:
                extra["pid_killed"] = False   # gone between the liveness check and the kill: nothing left to conflict with the close
            except PermissionError:
                # Alive and untouchable: closing now would put a run.finished under a writer that may still append.
                out.append(_closed_row(row, started, age, "silent", journal_closed=False, kill_refused=True, **extra))
                continue
            killed = kill_child_groups(
                home, run_id, pid=pid, pid_start=str(started.get("pid_start") or ""),
            )
            if killed:
                extra["child_groups_killed"] = killed
            extra["journal_closed"] = finish_if_running(home, run_id, "interrupted")
            _silence_seen.pop(run_id, None)
            out.append(_closed_row(row, started, age, "silent", **extra))
            continue
        if pid > 0:
            continue  # a dead pid belongs to reconcile_stale, which ran first
        if finish_if_running(home, run_id, "interrupted"):
            _silence_seen.pop(run_id, None)
            out.append(_closed_row(row, started, age, "silent", **extra))
    return out


def _is_this_runs_process(pid: int, started: dict) -> bool:
    # A recycled pid can be the daemon, another profile's child, or anything at all; only a matching start time proves it is the process that wrote run.started.
    if pid in (os.getpid(), os.getppid()):
        return False
    expected = started.get("pid_start")
    if not expected:
        return False
    return proc_starttime(pid) == str(expected)



def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _safe_float(value: Any) -> float:
    try:
        result = float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
    return result if math.isfinite(result) else 0.0


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True

_last_model_state: dict[str, str] = {}


def record_agent_event(context: RunContext, event: Any) -> None:
    kind_hint = event.get("kind") if isinstance(event, dict) else getattr(event, "kind", None)
    if str(kind_hint) in _TRANSIENT_KINDS:
        return
    if is_dataclass(event):
        data = asdict(event)
    elif isinstance(event, dict):
        data = dict(event)
    else:
        data = {"value": str(event)}
    kind = str(data.pop("kind", "event"))
    if kind == "model_state":
        # The engine emits one per streamed tool-call fragment, every one with the same payload.
        snapshot = json.dumps(data, sort_keys=True, default=str)
        if _last_model_state.get(context.run_id) == snapshot:
            return
    if kind in {"tool_start", "tool_end"} and isinstance(data.get("args"), dict):
        data["args"] = persisted_tool_arguments(str(data.get("name") or ""), data["args"])
    append(context.home, context.run_id, f"agent.{kind}", data)
    if kind == "model_state":
        _last_model_state[context.run_id] = snapshot


def read(home: Path, run_id: str, *, after_seq: int = -1, limit: int = 1000) -> dict:
    path = run_path(home, run_id)
    if path.parent.is_symlink() or not path.exists() or path.is_symlink():
        raise FileNotFoundError(run_id)
    rows = []
    next_seq = after_seq
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if not isinstance(row, dict):
                continue
            try:
                seq = int(row.get("seq", -1))
            except (TypeError, ValueError):
                continue
            if seq <= after_seq:
                continue
            rows.append(row)
            next_seq = seq
            if len(rows) >= max(1, min(int(limit), 5000)):
                break
    return {"events": rows, "next_seq": next_seq}


def _first_record(path: Path) -> dict[str, Any] | None:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            try:
                return json.loads(line)
            except ValueError:
                continue
    return None


def _last_record(path: Path) -> dict[str, Any] | None:
    with path.open("rb") as handle:
        handle.seek(0, os.SEEK_END)
        end = handle.tell()
        start = max(0, end - MAX_EVENT_BYTES - 2)
        handle.seek(start)
        lines = handle.read().splitlines()
    if start > 0 and lines:
        lines = lines[1:]
    for line in reversed(lines):
        try:
            return json.loads(line)
        except ValueError:
            continue
    return None


def summary(home: Path, run_id: str) -> dict:
    path = run_path(home, run_id)
    if path.parent.is_symlink() or not path.exists() or path.is_symlink():
        raise FileNotFoundError(run_id)
    first = _first_record(path)
    last = _last_record(path)
    if (
        not isinstance(first, dict) or not isinstance(last, dict)
        or first.get("kind") != "run.started"
    ):
        raise ValueError(f"invalid run journal: {run_id}")
    try:
        count = int(last.get("seq")) + 1
        started_at = float(first.get("at"))
        updated_at = float(last.get("at"))
    except (TypeError, ValueError):
        raise ValueError(f"invalid run journal: {run_id}") from None
    if count < 1 or not math.isfinite(started_at) or not math.isfinite(updated_at):
        raise ValueError(f"invalid run journal: {run_id}")
    final = last if last.get("kind") == "run.finished" else None
    start_data = first.get("data") or {}
    if not isinstance(start_data, dict):
        raise ValueError(f"invalid run journal: {run_id}")
    final_data = (final or {}).get("data") or {}
    if not isinstance(final_data, dict):
        raise ValueError(f"invalid run journal: {run_id}")
    return {
        "id": run_id,
        "started_at": started_at,
        "updated_at": updated_at,
        "status": final_data.get("outcome") or "running",
        "profile": start_data.get("profile") or "default",
        "source": start_data.get("source") or "user",
        "session_id": start_data.get("session_id"),
        "connection_id": start_data.get("connection_id") or "host",
        "device_id": start_data.get("device_id"),
        "job_id": start_data.get("job_id"),
        "workgroup_id": start_data.get("workgroup_id"),
        "model": start_data.get("model") or "",
        "event_count": count,
    }


def list_runs(home: Path, *, limit: int = 50) -> list[dict]:
    directory = home / "runs"
    if not directory.exists() or directory.is_symlink():
        return []
    dated_paths = []
    try:
        candidates = directory.glob("*.jsonl")
        for path in candidates:
            try:
                if not path.is_symlink():
                    dated_paths.append((path.stat().st_mtime, path))
            except OSError:
                continue
    except OSError:
        return []
    paths = [
        path for _mtime, path in sorted(
            dated_paths, key=lambda item: (item[0], item[1].name), reverse=True,
        )
    ]
    rows = []
    for path in paths[: max(1, min(int(limit), MAX_LIST_LIMIT))]:
        try:
            rows.append(summary(home, path.stem))
        except (OSError, ValueError):
            continue
    return rows


__all__ = [
    "FORMAT_VERSION", "MAX_EVENT_BYTES", "MAX_LIST_LIMIT", "active", "active_ids", "append", "finish",
    "finish_if_running", "proc_starttime", "reconcile_stale", "reconcile_silent", "running_journals", "usage_summary",
    "children_path", "forget_children", "kill_child_groups", "kill_run_leftovers", "kill_stamped_survivors",
    "owner_stamp", "record_child", "record_current_child", "stamp_env",
    "persisted_tool_arguments",
    "list_runs", "read", "record_agent_event", "run_path", "start", "summary",
    "register_active", "unregister_active",
]
