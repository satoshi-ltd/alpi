"""Schedule daemon — polls ``jobs.json`` every TICK_SECONDS, fires due jobs."""

from __future__ import annotations

import json
import logging
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from croniter import croniter

from alpi.gateway import delivery

log = logging.getLogger("alpi.schedule")

# How often to wake up and check for due jobs. 30s is fine-grained enough
# for "every minute" expressions while keeping CPU ~0.
TICK_SECONDS = 30



def jobs_path(home: Path) -> Path:
    return home / "schedule" / "jobs.json"


def pid_path(home: Path) -> Path:
    return home / "schedule" / "scheduler.pid"


def _sessions_dir(home: Path) -> Path:
    return home / "sessions"



def _load_jobs(home: Path) -> list[dict]:
    p = jobs_path(home)
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text() or "[]")
    except json.JSONDecodeError:
        log.warning("jobs.json is malformed — treating as empty")
        return []
    return data if isinstance(data, list) else []


def _save_jobs(home: Path, jobs: list[dict]) -> None:
    p = jobs_path(home)
    p.parent.mkdir(parents=True, exist_ok=True)
    # Write atomically: write a sibling then rename.
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(jobs, indent=2))
    tmp.replace(p)



def _now() -> datetime:
    return datetime.now().astimezone()


def _parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def is_due(job: dict, now: datetime | None = None, home: Path | None = None) -> bool:
    """True if the job should run right now."""
    now = now or _now()
    kind = job.get("kind", "cron")
    last = _parse_iso(job.get("last_run_at"))

    if kind == "cron":
        expr = job.get("expression", "")
        if not expr:
            return False
        try:
            # Validate the expression once regardless of first-run shortcut.
            croniter(expr)
        except Exception as e:  # noqa: BLE001
            log.warning("bad cron expression for %s: %s", job.get("id"), e)
            return False
        # No prior run → fire on the first tick so the user sees activity
        # right after adding a job. Subsequent runs use croniter from the
        # last run as the anchor.
        if last is None:
            return True
        anchor = last.astimezone(now.tzinfo) if last.tzinfo else last.replace(tzinfo=now.tzinfo)
        next_run = croniter(expr, anchor).get_next(datetime)
        if next_run.tzinfo is None:
            next_run = next_run.replace(tzinfo=now.tzinfo)
        return next_run <= now

    if kind == "once":
        # Fires once when run_at is reached, then tick() deletes it.
        # last_run_at is a guard in case deletion failed on a previous tick.
        if last is not None:
            return False
        run_at = _parse_iso(job.get("run_at"))
        if run_at is None:
            return False
        if run_at.tzinfo is None:
            run_at = run_at.replace(tzinfo=now.tzinfo)
        return run_at <= now

    if kind == "inactivity":
        after_hours = float(job.get("after_hours") or 0)
        if after_hours <= 0 or home is None:
            return False
        threshold = timedelta(hours=after_hours)
        # Cooldown: don't re-fire within `after_hours` of our own last fire.
        if last and (now - last) < threshold:
            return False
        last_activity = _last_user_activity(home)
        if last_activity is None:
            # No session ever — treat as "very inactive" and fire once.
            return True
        return (now - last_activity) >= threshold

    return False


def _last_user_activity(home: Path) -> datetime | None:
    sdir = _sessions_dir(home)
    if not sdir.exists():
        return None
    files = list(sdir.glob("*.json"))
    if not files:
        return None
    newest = max(files, key=lambda p: p.stat().st_mtime)
    return datetime.fromtimestamp(newest.stat().st_mtime, tz=timezone.utc)



def run_job(job: dict, home: Path) -> tuple[bool, str]:
    """Invoke the prompt through ``alpi chat --once`` and deliver the reply."""
    prompt = job.get("prompt", "").strip()
    if not prompt:
        return False, "empty prompt"

    from alpi.tools.skill import scan_skill_body
    flags = scan_skill_body(prompt)
    if flags:
        return False, f"threat scan blocked fire: {', '.join(flags)}"

    wrapped = (
        "[SCHEDULED: running from cron; user is not watching live. "
        "Answer concisely; the reply is auto-delivered to their chat. "
        "If the job is purely to deliver text, just write the text as "
        "the reply — do NOT also call `send_message`; that would "
        "send it twice.]\n\n"
        + prompt
    )

    env = dict(os.environ)
    env["ALPI_HOME"] = str(home)
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "alpi", "chat", "--once", wrapped, "--emit-events"],
            env=env, capture_output=True, text=True, timeout=600,
        )
    except subprocess.TimeoutExpired:
        return False, "agent timed out"
    if proc.returncode != 0:
        return False, f"agent rc={proc.returncode}: {proc.stderr[:300]}"

    already_delivered, reply = _parse_events(proc.stdout or "")

    if already_delivered:
        return True, "agent delivered via send_message; no duplicate reply pushed"

    if not reply:
        return False, "agent produced no reply"

    platform = (job.get("platform") or "telegram").lower()
    chat_id = job.get("chat_id") or delivery.default_chat_id(platform)
    if not chat_id:
        return False, f"no chat_id and no default for {platform}"

    try:
        delivery.send_to(platform, chat_id, reply)
    except delivery.DeliveryError as e:
        return False, f"delivery failed: {e}"
    return True, f"delivered to {platform}:{chat_id}"


def _parse_events(stdout: str) -> tuple[bool, str]:
    """Return (send_message_used, final_reply_text) from --emit-events output."""
    sent_via_tool = False
    reply = ""
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        kind = ev.get("kind")
        if kind == "tool_start" and ev.get("name") == "send_message":
            sent_via_tool = True
        elif kind == "reply":
            reply = (ev.get("text") or "").strip()
    return sent_via_tool, reply


# Tick + main loop


def tick(home: Path, now: datetime | None = None) -> list[tuple[str, bool, str]]:
    """Run one pass: fire every due job, persist ``last_run_at`` on success."""
    now = now or _now()
    jobs = _load_jobs(home)
    kept: list[dict] = []
    results: list[tuple[str, bool, str]] = []
    changed = False

    for job in jobs:
        if not is_due(job, now=now, home=home):
            kept.append(job)
            continue
        job_id = job.get("id", "?")
        log.info("firing job %s (%s)", job_id, job.get("kind", "cron"))
        ok, msg = run_job(job, home)
        log.info("job %s %s — %s", job_id, "OK" if ok else "FAIL", msg)
        # Update last_run_at even on failure to avoid a tight re-fire loop.
        job["last_run_at"] = now.isoformat()
        changed = True
        results.append((job_id, ok, msg))
        # One-shot jobs die after a successful fire; on failure, keep so
        # the next tick retries.
        if job.get("kind") == "once" and ok:
            continue
        kept.append(job)

    if changed:
        _save_jobs(home, kept)
    return results


def run(home: Path) -> None:
    _configure_logging(home)
    _load_env(home)
    _write_pid(home)
    log.info("Scheduler started (tick=%ss).", TICK_SECONDS)

    def _term(signum: int, _frame: Any) -> None:
        log.info("Scheduler stopping (signal %s).", signum)
        _clear_pid(home)
        sys.exit(0)

    signal.signal(signal.SIGTERM, _term)
    signal.signal(signal.SIGINT, _term)

    try:
        while True:
            try:
                tick(home)
            except Exception as e:  # noqa: BLE001
                log.exception("tick crashed: %s", e)
            time.sleep(TICK_SECONDS)
    finally:
        _clear_pid(home)


# PID + logging + env helpers (same shape as gateway)


def _write_pid(home: Path) -> None:
    p = pid_path(home)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(str(os.getpid()))


def _clear_pid(home: Path) -> None:
    p = pid_path(home)
    if p.exists():
        try:
            p.unlink()
        except OSError:
            pass


def _load_env(home: Path) -> None:
    env_path = home / ".env"
    if env_path.exists():
        from dotenv import load_dotenv
        load_dotenv(env_path, override=False)
        log.info("Loaded env from %s", env_path)


def _configure_logging(home: Path) -> None:
    from alpi._log import FORMAT, MAX_BYTES, log_path

    path = log_path(home, "schedule")
    path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(path, maxBytes=MAX_BYTES, backupCount=0)
    logging.basicConfig(
        level=logging.INFO,
        format=FORMAT,
        handlers=[file_handler, logging.StreamHandler()],
    )


# Process control (used by CLI start/stop/status)


def running_pid(home: Path) -> int | None:
    """Return the scheduler PID if it's alive, else None (clearing stale PID)."""
    p = pid_path(home)
    if not p.exists():
        return None
    try:
        pid = int(p.read_text().strip())
    except ValueError:
        p.unlink(missing_ok=True)
        return None
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        p.unlink(missing_ok=True)
        return None
    except PermissionError:
        # Process exists but owned by someone else — be conservative and
        # report it as running so we don't step on it.
        return pid
    return pid


def stop(home: Path) -> bool:
    pid = running_pid(home)
    if pid is None:
        return False
    os.kill(pid, signal.SIGTERM)
    return True


def ensure_running(home: Path) -> int | None:
    """Spawn a detached schedule daemon if one is not already running."""
    pid = running_pid(home)
    if pid:
        return pid

    from alpi._log import log_path
    log_file_path = log_path(home, "schedule")
    log_file_path.parent.mkdir(parents=True, exist_ok=True)
    # Open in append mode and hand the fd to the child. The parent
    # closes its handle immediately after spawn so we don't hold extra
    # fds open in the TUI.
    log_fd = open(log_file_path, "a")
    env = dict(os.environ)
    env["ALPI_HOME"] = str(home)
    try:
        proc = subprocess.Popen(
            [sys.executable, "-m", "alpi", "schedule", "start"],
            stdin=subprocess.DEVNULL,
            stdout=log_fd,
            stderr=log_fd,
            start_new_session=True,
            env=env,
        )
    finally:
        log_fd.close()
    return proc.pid
