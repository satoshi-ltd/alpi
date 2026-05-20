"""Schedule daemon — polls ``jobs.json`` every TICK_SECONDS, fires due jobs."""

from __future__ import annotations

import json
import logging
import os
import shlex
import signal
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from croniter import croniter

from alpi.gateway import delivery

log = logging.getLogger("alpi.schedule")


@dataclass
class JobOutcome:
    # `delivered_to`: "" | "telegram" | "email" | "external" (send_message). `silent`: True only when ok AND no user-facing output AND no delivery. Contract referenced by host event consumers — see AGENTS.md.
    ok: bool
    message: str
    reply: str = ""
    delivered_to: str = ""
    silent: bool = False

    def __iter__(self):
        # Back-compat tuple unpack `ok, msg, reply = run_job(...)`.
        yield self.ok
        yield self.message
        yield self.reply

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
    # Paused jobs never auto-fire from the tick. ``fire_by_id`` still
    # runs them — pause is a "stop the schedule" knob, not "delete".
    if job.get("paused"):
        return False
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



def validate_no_agent_command(prompt: str, home: Path) -> str | None:
    # Form-based allowlist: only `python[3] [flags] <skill_script>` or a
    # `<skill_script>` invoked directly. Blocks `-c`/`-m` (inline code/module
    # bypass the script-on-disk check) and non-python executables (rm, bash,
    # curl…) even when a skills/ path appears as an argument.
    expanded = prompt.replace("${ALPI_HOME}", str(home)).replace(
        "$ALPI_HOME", str(home),
    )
    try:
        argv = shlex.split(expanded)
    except ValueError as e:
        return f"command parse error: {e}"
    if not argv:
        return "empty command"

    skills_root = (home / "skills").resolve()

    def _under_skills(tok: str) -> bool:
        try:
            rel = Path(tok).resolve().relative_to(skills_root)
        except (OSError, ValueError, RuntimeError):
            return False
        parts = rel.parts
        return len(parts) >= 4 and parts[2] == "scripts"

    exe = argv[0]
    rest = argv[1:]

    if _under_skills(exe):
        return None

    exe_name = Path(exe).name
    if not (exe_name in {"python", "python3"} or exe_name.startswith("python3.")):
        return (
            f"no_agent executable must be python or a script under "
            f"{home}/skills/ — got: {exe!r}"
        )

    for tok in rest:
        if tok.startswith(("-c", "-m", "--command", "--module")):
            return f"forbidden python flag in no_agent: {tok!r}"
        if tok.startswith("-"):
            continue
        if _under_skills(tok):
            return None
        return (
            f"first non-flag python arg must be a script under "
            f"{home}/skills/ — got: {tok!r}"
        )
    return f"no_agent python invocation needs a script under {home}/skills/"


def _run_script_only(job: dict, home: Path) -> JobOutcome:
    # Threat scan intentionally skipped: validator restricts the prompt to skill scripts on disk, so prompt-injection heuristics don't apply.
    cmd_str = (job.get("prompt") or "").strip()
    if not cmd_str:
        return JobOutcome(False, "empty command (no_agent)")

    err = validate_no_agent_command(cmd_str, home)
    if err:
        return JobOutcome(False, f"no_agent rejected: {err}")

    expanded = cmd_str.replace("${ALPI_HOME}", str(home)).replace(
        "$ALPI_HOME", str(home),
    )
    try:
        argv = shlex.split(expanded)
    except ValueError as e:
        return JobOutcome(False, f"command parse error: {e}")
    if not argv:
        return JobOutcome(False, "empty command after parsing")

    from alpi.home import effective_profile_env as _effective_profile_env
    env = _effective_profile_env(home, extra={
        "ALPI_HOME": str(home),
        "ALPI_PLATFORM": "cron",
    })

    try:
        proc = subprocess.run(
            argv, env=env, capture_output=True, text=True, timeout=600,
        )
    except subprocess.TimeoutExpired:
        return JobOutcome(False, "script timed out")
    except FileNotFoundError:
        return JobOutcome(False, f"executable not found: {argv[0]!r}")

    if proc.returncode != 0:
        err = (proc.stderr or "").strip()
        return JobOutcome(False, f"script rc={proc.returncode}: {err[:300]}")

    reply = (proc.stdout or "").strip()
    has_platform = bool(job.get("platform"))

    if not reply:
        return JobOutcome(True, "silent run ok", silent=True)

    if not has_platform:
        summary = (reply[:120] + "…") if len(reply) > 120 else reply
        return JobOutcome(True, f"silent run ok: {summary}", reply=reply)

    platform = job["platform"].lower()
    chat_id = job.get("chat_id") or delivery.default_chat_id(platform, env=env)
    if not chat_id:
        return JobOutcome(False, f"no chat_id and no default for {platform}")
    try:
        delivery.send_to(platform, chat_id, reply, env=env)
    except delivery.DeliveryError as e:
        return JobOutcome(False, f"delivery failed: {e}")
    return JobOutcome(
        True, f"delivered to {platform}:{chat_id}",
        reply=reply, delivered_to=platform,
    )


def run_job(job: dict, home: Path) -> JobOutcome:
    # Jobs with no `platform` run silent (no gateway dispatch). With `platform` the agent reply auto-delivers — unless the agent already called `send_message`, in which case delivery is suppressed to avoid duplicates.
    if job.get("no_agent"):
        return _run_script_only(job, home)

    prompt = job.get("prompt", "").strip()
    if not prompt:
        return JobOutcome(False, "empty prompt")

    from alpi.tools.skill import scan_skill_body
    flags = scan_skill_body(prompt)
    if flags:
        return JobOutcome(False, f"threat scan blocked fire: {', '.join(flags)}")

    has_platform = bool(job.get("platform"))
    if has_platform:
        wrap_header = (
            "[SCHEDULED: running from cron; user is not watching live. "
            "Answer concisely; the reply is auto-delivered to their chat. "
            "If the job is purely to deliver text, just write the text as "
            "the reply — do NOT also call `send_message`; that would "
            "send it twice.]"
        )
    else:
        wrap_header = (
            "[SCHEDULED: running from cron as a silent maintenance task. "
            "No reply is delivered anywhere. Do the work, then end with "
            "an empty reply (a short summary is fine but discarded — it "
            "only ends up in the daemon log).]"
        )
    wrapped = wrap_header + "\n\n" + prompt

    from alpi.home import effective_profile_env as _effective_profile_env
    env = _effective_profile_env(home, extra={
        "ALPI_HOME": str(home),
        "ALPI_PLATFORM": "cron",
    })
    try:
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "alpi",
                "chat",
                "--once",
                wrapped,
                "--emit-events",
                "--no-save",
            ],
            env=env, capture_output=True, text=True, timeout=600,
        )
    except subprocess.TimeoutExpired:
        return JobOutcome(False, "agent timed out")
    if proc.returncode != 0:
        return JobOutcome(False, f"agent rc={proc.returncode}: {proc.stderr[:300]}")

    already_delivered, reply = _parse_events(proc.stdout or "")

    if already_delivered:
        return JobOutcome(
            True,
            "agent delivered via send_message; no duplicate reply pushed",
            delivered_to="external",
        )

    if not has_platform:
        # Silent maintenance job — log a short summary if the agent provided one.
        summary = (reply[:120] + "…") if len(reply) > 120 else reply
        return JobOutcome(
            True,
            f"silent run ok{(': ' + summary) if summary else ''}",
            reply=reply,
            silent=(not reply),
        )

    if not reply:
        return JobOutcome(False, "agent produced no reply")

    platform = job["platform"].lower()
    chat_id = job.get("chat_id") or delivery.default_chat_id(platform, env=env)
    if not chat_id:
        return JobOutcome(False, f"no chat_id and no default for {platform}")

    try:
        delivery.send_to(platform, chat_id, reply, env=env)
    except delivery.DeliveryError as e:
        return JobOutcome(False, f"delivery failed: {e}")
    return JobOutcome(
        True, f"delivered to {platform}:{chat_id}",
        reply=reply, delivered_to=platform,
    )


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


def fire_by_id(home: Path, job_id: str) -> tuple[bool, str]:
    """Run one specific job ad-hoc, bypassing the schedule check. Same
    threat-scan + dispatch path as the daemon tick, so what you test is
    exactly what the daemon would fire. Does NOT delete ``once`` jobs —
    ad-hoc fire is deliberate testing, not the natural trigger.
    """
    # Returns 2-tuple by design; the `reply` field lives only on the host event stream.
    jobs = _load_jobs(home)
    for job in jobs:
        if job.get("id") == job_id:
            log.info("firing job %s ad-hoc (%s)", job_id, job.get("kind", "?"))
            outcome = run_job(job, home)
            log.info("job %s ad-hoc %s — %s", job_id,
                     "OK" if outcome.ok else "FAIL", outcome.message)
            job["last_run_at"] = _now().isoformat()
            _save_jobs(home, jobs)
            return outcome.ok, outcome.message
    import difflib
    available = [str(j.get("id", "")) for j in jobs if j.get("id")]
    hit = difflib.get_close_matches(job_id, available, n=1, cutoff=0.6)
    hint = f". Did you mean {hit[0]!r}?" if hit else ""
    return False, f"no job with id {job_id!r}{hint}"


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
        outcome = run_job(job, home)
        log.info("job %s %s — %s", job_id,
                 "OK" if outcome.ok else "FAIL", outcome.message)
        try:
            from alpi.home import profile_name
            from alpi.host import events as host_events
            host_events.emit(
                "schedule.done" if outcome.ok else "schedule.failed",
                {
                    "profile": profile_name(home),
                    "job_id": str(job_id),
                    "kind": str(job.get("kind", "cron")),
                    "message": outcome.message,
                    "reply": (outcome.reply or "")[:2000],
                    "delivered_to": outcome.delivered_to,
                    "silent": outcome.silent,
                },
            )
        except Exception:  # noqa: BLE001
            pass
        # Update last_run_at even on failure to avoid a tight re-fire loop.
        job["last_run_at"] = now.isoformat()
        changed = True
        results.append((job_id, outcome.ok, outcome.message))
        # One-shot jobs die after a successful fire; on failure, keep so
        # the next tick retries.
        if job.get("kind") == "once" and outcome.ok:
            continue
        kept.append(job)

    if changed:
        _save_jobs(home, kept)
    return results


async def serve(home: Path) -> None:
    """Async entry point for the orchestrator. Sleeps between ticks
    using ``asyncio.sleep`` so other subsystems share the same loop.

    ``tick`` runs in a dedicated thread executor so a long-running
    ``subprocess.run`` (up to 10 min via run_job's timeout) can't
    starve host.chat streaming or other coroutines.
    """
    import asyncio
    import concurrent.futures

    log.info("Scheduler started (tick=%ss).", TICK_SECONDS)
    loop = asyncio.get_running_loop()
    executor = concurrent.futures.ThreadPoolExecutor(
        max_workers=2, thread_name_prefix="alpi-sched",
    )
    try:
        while True:
            try:
                await loop.run_in_executor(executor, tick, home)
            except Exception as e:  # noqa: BLE001
                log.exception("tick crashed: %s", e)
            await asyncio.sleep(TICK_SECONDS)
    finally:
        executor.shutdown(wait=False)


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
    from alpi.home import effective_profile_env as _effective_profile_env
    env = _effective_profile_env(home, extra={"ALPI_HOME": str(home)})
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
