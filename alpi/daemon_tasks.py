from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Awaitable, Callable

log = logging.getLogger("alpi.service")

RESTART_BASE_S = 5.0
RESTART_MAX_S = 300.0
HEALTHY_AFTER_S = 300.0
ALERT_AFTER = 3
ERROR_CHARS = 300

_snapshot_path: Path | None = None
_states: dict[str, dict[str, Any]] = {}


def snapshot_path(root: Path) -> Path:
    return root / "service.tasks.json"


def configure(root: Path) -> None:
    global _snapshot_path
    _snapshot_path = snapshot_path(root)
    _states.clear()
    _write()


def clear(root: Path) -> None:
    global _snapshot_path
    _snapshot_path = None
    _states.clear()
    try:
        snapshot_path(root).unlink()
    except OSError:
        pass


def read(root: Path, pid: int | None) -> list[dict[str, Any]] | None:
    try:
        data = json.loads(snapshot_path(root).read_text())
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or pid is None or data.get("pid") != pid:
        return None
    tasks = data.get("tasks")
    return [t for t in tasks if isinstance(t, dict)] if isinstance(tasks, list) else None


def _write() -> None:
    if _snapshot_path is None:
        return
    from alpi.secrets_io import safe_write_secret
    rows = [dict(v, task=k) for k, v in sorted(_states.items())]
    try:
        safe_write_secret(_snapshot_path, json.dumps({"pid": os.getpid(), "tasks": rows}))
    except OSError:
        log.exception("cannot write the daemon task snapshot")


def _set(key: str, *, fresh: bool = False, **fields: Any) -> None:
    row = {"failures": 0} if fresh else _states.get(key, {"failures": 0})
    row.update(fields)
    _states[key] = row
    _write()


def _drop(key: str) -> None:
    if _states.pop(key, None) is not None:
        _write()


def _error_text(exc: BaseException) -> str:
    from alpi._redact import redact
    text = f"{type(exc).__name__}: {exc}"
    return str(redact(text))[:ERROR_CHARS]


def _alert(home: Path, profile: str, name: str, *, failures: int, error: str, recovered: bool) -> None:
    from alpi.provider_pause import _file_alert
    if recovered:
        _file_alert(
            home, profile, title=f"{profile}: daemon task {name} recovered",
            body=f"The daemon task {name} has been running again for {int(HEALTHY_AFTER_S // 60)} minutes.",
            code="task_recovered", type="info", kind="daemon",
        )
        return
    _file_alert(
        home, profile, title=f"{profile}: daemon task {name} keeps failing",
        body=(
            f"The daemon task {name} failed {failures} times in a row and is restarted with a growing delay "
            f"(up to {int(RESTART_MAX_S // 60)} minutes). Last error: {error}. "
            "`alpi daemon status` shows its state; the service log has the traceback."
        ),
        code="task_failing", kind="daemon",
    )


async def supervise(
    run: Callable[[], Awaitable[None]], home: Path, profile: str, name: str,
) -> None:
    key = f"{profile}/{name}"
    failures = 0
    alerted = False
    _set(key, fresh=True, state="running", since=time.time(), retry_at=None)
    try:
        while True:
            _set(key, state="running", since=time.time(), retry_at=None)
            exc, healthy = await _run_once(run, key, failures, home, profile, name, alerted)
            if healthy:
                failures, alerted = 0, False
            if exc is None:
                _set(key, state="stopped", since=time.time())
                return
            failures += 1
            error = _error_text(exc)
            delay = min(RESTART_BASE_S * 2 ** (failures - 1), RESTART_MAX_S)
            log.error(
                "daemon task %s crashed (failure %d in a row) — restarting in %.0fs; unrelated tasks remain available",
                key, failures, delay, exc_info=exc,
            )
            _set(key, state="restarting", failures=failures, last_error=error, retry_at=time.time() + delay)
            if failures == ALERT_AFTER:
                alerted = True
                _alert(home, profile, name, failures=failures, error=error, recovered=False)
            await asyncio.sleep(delay)
    finally:
        if _states.get(key, {}).get("state") != "stopped":
            _drop(key)


async def _run_once(
    run: Callable[[], Awaitable[None]], key: str, failures: int,
    home: Path, profile: str, name: str, alerted: bool,
) -> tuple[BaseException | None, bool]:
    task = asyncio.ensure_future(run())
    healthy = False
    try:
        done, _ = await asyncio.wait({task}, timeout=HEALTHY_AFTER_S)
        if not done:
            healthy = True
            if failures:
                _set(key, failures=0, last_error=None)
            if alerted:
                _alert(home, profile, name, failures=0, error="", recovered=True)
            await asyncio.wait({task})
        task.result()
        error: BaseException | None = None
    except asyncio.CancelledError as cancelled:
        current = asyncio.current_task()
        if current is not None and current.cancelling():
            task.cancel()
            for outcome in await asyncio.gather(task, return_exceptions=True):
                if isinstance(outcome, Exception):
                    log.error("daemon task %s raised while stopping", key, exc_info=outcome)
            raise
        error = RuntimeError(f"cancelled from inside the task: {cancelled!r}")
    except Exception as caught:  # noqa: BLE001
        error = caught
    return error, healthy
