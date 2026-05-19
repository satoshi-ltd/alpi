"""schedule tool — manage scheduled jobs in ~/.alpi/schedule/jobs.json."""

from __future__ import annotations

import json
import re
import shlex
import uuid
from typing import Any

from alpi.home import get_home
from alpi.tools.base import Tool, ToolResult


class Schedule(Tool):
    name = "schedule"
    description = (
        "Schedule a proactive job. CALL this tool — do NOT just say "
        "\"done, you'll get X at Y\" in the reply; nothing is "
        "scheduled unless this tool is invoked.\n"
        "\n"
        "Actions: list, add, update, remove, fire.\n"
        "\n"
        "`fire` runs a specific job ad-hoc — same threat-scan + "
        "dispatch path as the scheduler daemon. Useful right after "
        "`add` to verify the prompt works end-to-end without waiting "
        "for the cron window. Once-jobs are NOT consumed by fire.\n"
        "\n"
        "Pick `kind`:\n"
        "  once       — fires on a single date/time, then deletes itself "
        "(field: `run_at`, ISO 8601, e.g. '2026-04-21T09:00:00')\n"
        "  cron       — recurring cron expression (field: `expression`, e.g. '0 9 * * *')\n"
        "  inactivity — fires after N hours of user silence (field: `after_hours`)\n"
        "\n"
        "Rule of thumb: user named a specific date or said \"in 10 min / "
        "tomorrow at 9 / the 25th\" → `once`. User said \"every day / "
        "every Monday / at 5pm\" without a date → `cron`.\n"
        "\n"
        "Times are evaluated in the machine's local timezone. When the "
        "user says \"at 2pm\" write `0 14 * * *` for cron or "
        "`...T14:00:00` for once — do NOT convert to UTC.\n"
        "\n"
        "`prompt` is what alpi should do when the job fires. Its reply "
        "is AUTO-DELIVERED to `platform` + `chat_id` (defaults: telegram "
        "+ first allowlisted chat). Do NOT include 'send to telegram' "
        "in the prompt — delivery is automatic; adding it sends twice.\n"
        "\n"
        "Language: write the `prompt` in ENGLISH, regardless of the "
        "chat language. Schedule prompts are persisted in jobs.json and "
        "re-injected into the LLM context every time the job fires — "
        "non-English prompts bias replies forever, exactly like memory "
        "and skill bodies. If the OUTPUT must be in another language "
        "(e.g. a Spanish daily message), say so inside the prompt: "
        "``\"Send a Telegram greeting in Spanish: 'Buenos dias' …\"`` "
        "— English instruction, target-language content."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "add", "update", "remove", "fire"],
            },
            "force": {
                "type": "boolean",
                "description": (
                    "Bypass the duplicate-detection guard on `add`. Default "
                    "false: a job whose (kind + cron + first 80 chars of "
                    "prompt) matches an existing job is rejected so you "
                    "don't end up with two copies of the same daily summary. "
                    "Set true only when you genuinely want a near-duplicate."
                ),
                "default": False,
            },
            "kind": {
                "type": "string",
                "enum": ["once", "cron", "inactivity"],
                "description": "Job kind. Default: cron.",
                "default": "cron",
            },
            "run_at": {
                "type": "string",
                "description": "ISO 8601 datetime for kind=once, e.g. '2026-04-21T09:00:00'. Interpreted in the machine's local tz if naive.",
            },
            "expression": {
                "type": "string",
                "description": "Cron expression for kind=cron, e.g. '0 9 * * *'.",
            },
            "after_hours": {
                "type": "number",
                "description": "Inactivity threshold for kind=inactivity.",
            },
            "prompt": {
                "type": "string",
                "description": "What to ask alpi to do when the job fires.",
            },
            "platform": {
                "type": "string",
                "description": (
                    "Delivery platform for the agent's reply. Leave empty "
                    "for silent maintenance jobs (no gateway dispatch). "
                    "Set to 'telegram' / 'matrix' / 'imap' / 'gmail' for "
                    "user-facing scheduled messages."
                ),
                "default": "",
            },
            "chat_id": {
                "type": "string",
                "description": "Target chat id. Default: first allowlisted chat.",
            },
            "id": {"type": "string", "description": "Job id (for update / remove / fire)."},
            "paused": {
                "type": "boolean",
                "description": "Pause/resume an existing job (update only).",
            },
            "no_agent": {
                "type": "boolean",
                "description": (
                    "When true, `prompt` is executed as a shell command via "
                    "shlex (no LLM, no token cost). `${ALPI_HOME}` expands "
                    "to the profile home; the profile's .env is loaded. "
                    "Use for deterministic skills (data sync, file "
                    "processors) where an agent invocation adds nothing. "
                    "Empty stdout = silent ok. Non-empty stdout is "
                    "delivered if `platform` is set, otherwise logged."
                ),
                "default": False,
            },
        },
        "required": ["action"],
    }

    @classmethod
    def schema(cls) -> dict[str, Any]:
        """Inject current local time so the LLM can resolve relative phrases
        ("in 10 min", "tomorrow at 9", "next Monday") to correct absolute
        times. Without this, the LLM has no grounding for today's date."""
        from datetime import datetime
        now = datetime.now().astimezone()
        preamble = (
            f"Current time: {now.strftime('%Y-%m-%d %H:%M:%S %z')}. "
            f"Use this as the reference for any relative phrase like "
            f"\"in N minutes\", \"tonight\", \"tomorrow\", \"next Monday\".\n\n"
        )
        base = super().schema()
        base["function"]["description"] = preamble + base["function"]["description"]
        return base

    def run(self, action: str, kind: str = "", expression: str = "",
            after_hours: float | None = None, prompt: str = "",
            platform: str = "", chat_id: str = "",
            run_at: str = "", id: str | None = None,
            force: bool = False,
            paused: bool | None = None,
            no_agent: bool | None = None) -> ToolResult:
        home = get_home()
        jobs_path = home / "schedule" / "jobs.json"
        jobs_path.parent.mkdir(parents=True, exist_ok=True)
        jobs: list[dict] = json.loads(jobs_path.read_text()) if jobs_path.exists() else []

        if action == "list":
            return ToolResult(ok=True, output=json.dumps(jobs, indent=2))

        if action == "add":
            if not prompt:
                return ToolResult(ok=False, output="", error="'prompt' is required")
            auto_no_agent = False
            if no_agent is None and _looks_like_shell_command(prompt):
                no_agent = True
                auto_no_agent = True
            if no_agent:
                from alpi.scheduler.run import validate_no_agent_command
                err = validate_no_agent_command(prompt, home)
                if err:
                    return ToolResult(ok=False, output="", error=err)
            else:
                err = _validate_prompt(prompt, platform)
                if err:
                    return ToolResult(ok=False, output="", error=err)
            if not force:
                dup = _find_duplicate(jobs, kind or "cron", expression,
                                       run_at, after_hours, prompt)
                if dup is not None:
                    return ToolResult(
                        ok=False, output="",
                        error=(
                            f"a similar job already exists (id={dup['id']}, "
                            f"kind={dup.get('kind')}). Run "
                            f"schedule(action='list') to inspect, then "
                            f"either remove the old one or pass force=true "
                            f"to add this one anyway."
                        ),
                    )
            from datetime import datetime, timezone
            now_iso = datetime.now(timezone.utc).isoformat()
            job: dict = {
                "id": uuid.uuid4().hex[:8],
                "kind": kind or "cron",
                "prompt": prompt,
                "platform": (platform or "").lower(),
                "chat_id": chat_id or "",
                "last_run_at": now_iso if (kind or "cron") == "cron" else None,
            }
            if no_agent:
                job["no_agent"] = True
            if job["kind"] == "cron":
                if not expression:
                    return ToolResult(
                        ok=False, output="",
                        error="'expression' is required for kind=cron",
                    )
                job["expression"] = expression
            elif job["kind"] == "once":
                if not run_at:
                    return ToolResult(
                        ok=False, output="",
                        error="'run_at' (ISO 8601) is required for kind=once",
                    )
                try:
                    datetime.fromisoformat(run_at)
                except ValueError:
                    return ToolResult(
                        ok=False, output="",
                        error=f"'run_at' is not a valid ISO 8601 datetime: {run_at!r}",
                    )
                job["run_at"] = run_at
            elif job["kind"] == "inactivity":
                if after_hours is None or after_hours <= 0:
                    return ToolResult(
                        ok=False, output="",
                        error="'after_hours' must be > 0 for kind=inactivity",
                    )
                job["after_hours"] = float(after_hours)
            else:
                return ToolResult(ok=False, output="", error=f"unknown kind: {kind}")

            jobs.append(job)
            jobs_path.write_text(json.dumps(jobs, indent=2))

            # Tell the user how to activate delivery. Nothing fires
            # without the alpi daemon running with the schedule
            # subsystem enabled for this profile.
            from alpi import home as home_mod
            from alpi import service as svc
            running = svc.daemon_running_pid(home_mod._ROOT) is not None
            if running and svc.enabled_subsystems(home).get("schedule"):
                hint = "daemon is running — job will fire on schedule"
            else:
                hint = "start the daemon ('alpi daemon start' or install it) to fire jobs"

            suffix = " · auto-inferred no_agent=true (prompt is a shell command)" if auto_no_agent else ""
            return ToolResult(
                ok=True,
                output=f"Added {job['kind']} job {job['id']} — {hint}{suffix}",
            )

        if action == "update":
            if not id:
                return ToolResult(ok=False, output="", error="'id' required")
            job = next((j for j in jobs if j.get("id") == id), None)
            if job is None:
                return ToolResult(ok=False, output="", error=f"job {id} not found")

            changes: list[str] = []
            next_platform = (platform or job.get("platform") or "").lower()
            # Snapshot before mutation: needed to detect on↔off transitions
            # and re-validate the inherited prompt with the right rule set.
            was_no_agent = bool(job.get("no_agent"))
            effective_no_agent = no_agent if no_agent is not None else was_no_agent
            if prompt:
                if effective_no_agent:
                    from alpi.scheduler.run import validate_no_agent_command
                    err = validate_no_agent_command(prompt, home)
                    if err:
                        return ToolResult(ok=False, output="", error=err)
                else:
                    err = _validate_prompt(prompt, next_platform)
                    if err:
                        return ToolResult(ok=False, output="", error=err)
                job["prompt"] = prompt
                changes.append("prompt")
            elif platform and not effective_no_agent:
                err = _validate_prompt(job.get("prompt", ""), next_platform)
                if err:
                    return ToolResult(ok=False, output="", error=err)
            if platform:
                job["platform"] = next_platform
                changes.append("platform")
            if chat_id:
                job["chat_id"] = chat_id
                changes.append("chat_id")
            if paused is not None:
                job["paused"] = bool(paused)
                changes.append("paused")
            if no_agent is not None:
                if no_agent:
                    if not was_no_agent:
                        from alpi.scheduler.run import validate_no_agent_command
                        err = validate_no_agent_command(job.get("prompt", ""), home)
                        if err:
                            return ToolResult(ok=False, output="", error=err)
                    job["no_agent"] = True
                else:
                    # Off-transition: existing prompt was a shell command,
                    # re-run LLM-prompt validators before the agent path consumes it.
                    if was_no_agent:
                        err = _validate_prompt(job.get("prompt", ""), next_platform)
                        if err:
                            return ToolResult(ok=False, output="", error=err)
                    job.pop("no_agent", None)
                changes.append("no_agent")

            if kind:
                job["kind"] = kind
                changes.append("kind")
            job_kind = job.get("kind") or "cron"
            if expression:
                job["expression"] = expression
                changes.append("expression")
            if run_at:
                from datetime import datetime
                try:
                    datetime.fromisoformat(run_at)
                except ValueError:
                    return ToolResult(
                        ok=False, output="",
                        error=f"'run_at' is not a valid ISO 8601 datetime: {run_at!r}",
                    )
                job["run_at"] = run_at
                changes.append("run_at")
            if after_hours is not None:
                if after_hours <= 0:
                    return ToolResult(
                        ok=False, output="",
                        error="'after_hours' must be > 0 for kind=inactivity",
                    )
                job["after_hours"] = float(after_hours)
                changes.append("after_hours")

            err = _validate_job_shape(job)
            if err:
                return ToolResult(ok=False, output="", error=err)
            if job_kind == "cron" and "last_run_at" not in job:
                from datetime import datetime, timezone
                job["last_run_at"] = datetime.now(timezone.utc).isoformat()
            jobs_path.write_text(json.dumps(jobs, indent=2))
            changed = ", ".join(dict.fromkeys(changes)) or "nothing"
            return ToolResult(ok=True, output=f"Updated job {id}: {changed}")

        if action == "remove":
            if not id:
                return ToolResult(ok=False, output="", error="'id' required")
            new_jobs = [j for j in jobs if j.get("id") != id]
            if len(new_jobs) == len(jobs):
                return ToolResult(ok=False, output="", error=f"job {id} not found")
            jobs_path.write_text(json.dumps(new_jobs, indent=2))
            return ToolResult(ok=True, output=f"Removed job {id}")

        if action == "fire":
            if not id:
                return ToolResult(ok=False, output="", error="'id' required")
            from alpi.scheduler.run import fire_by_id
            ok, msg = fire_by_id(home, id)
            return ToolResult(ok=ok, output=msg, error=None if ok else msg)

        return ToolResult(ok=False, output="", error=f"unknown action: {action}")


def _prompt_fingerprint(text: str) -> str:
    """Normalise to detect near-duplicate prompts: lowercase, collapse
    whitespace, take the first 80 chars. Two daily-summary prompts that
    differ only in trailing wording (e.g. one says 'send to Telegram')
    fingerprint to the same prefix and trip the duplicate guard."""
    norm = " ".join((text or "").lower().split())
    return norm[:80]


_AUTO_DELIVERY_RE = re.compile(
    r"\b(?:send|post|deliver|forward)\b.{0,80}\b(?:to|via)\s+"
    r"(?:telegram|matrix|email|mail|webhook)\b",
    re.I | re.S,
)


def _looks_like_shell_command(prompt: str) -> bool:
    # Discriminator: shlex-parsed first non-flag arg after `python*` is path-like; `"python is a language"` must stay on the agent path.
    try:
        argv = shlex.split((prompt or "").strip())
    except ValueError:
        return False
    if not argv:
        return False
    head = argv[0].rsplit("/", 1)[-1]
    if not (head in {"python", "python3"} or head.startswith("python3.")):
        return False
    for tok in argv[1:]:
        if tok.startswith("-"):
            continue
        return tok.startswith(("/", "~", "${ALPI_HOME}", "$ALPI_HOME"))
    return False


def _validate_prompt(prompt: str, platform: str) -> str | None:
    from alpi.tools.skill import scan_skill_body
    flags = scan_skill_body(prompt)
    if flags:
        return (
            "threat scan blocked scheduled prompt "
            f"(runs unattended with full tool access): {', '.join(flags)}"
        )
    if _AUTO_DELIVERY_RE.search(prompt or ""):
        return (
            "scheduled job replies are auto-delivered to "
            f"{(platform or 'telegram').lower()}; remove explicit delivery "
            "instructions like 'send/post to Telegram' from the prompt"
        )
    return None


def _validate_job_shape(job: dict) -> str | None:
    kind = job.get("kind") or "cron"
    if not job.get("prompt"):
        return "'prompt' is required"
    if kind == "cron" and not job.get("expression"):
        return "'expression' is required for kind=cron"
    if kind == "once" and not job.get("run_at"):
        return "'run_at' (ISO 8601) is required for kind=once"
    if kind == "inactivity" and float(job.get("after_hours") or 0) <= 0:
        return "'after_hours' must be > 0 for kind=inactivity"
    if kind not in {"cron", "once", "inactivity"}:
        return f"unknown kind: {kind}"
    return None


def _find_duplicate(
    jobs: list[dict], kind: str, expression: str, run_at: str,
    after_hours: float | None, prompt: str,
) -> dict | None:
    fp = _prompt_fingerprint(prompt)
    for j in jobs:
        if (j.get("kind") or "cron") != (kind or "cron"):
            continue
        if _prompt_fingerprint(j.get("prompt", "")) != fp:
            continue
        if kind == "cron" and j.get("expression") != expression:
            continue
        if kind == "once" and j.get("run_at") != run_at:
            continue
        if (kind == "inactivity"
                and float(j.get("after_hours") or 0) != float(after_hours or 0)):
            continue
        return j
    return None


TOOL = Schedule
