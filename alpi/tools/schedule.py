"""schedule tool — manage scheduled jobs in ~/.alpi/schedule/jobs.json."""

from __future__ import annotations

import json
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
        "Actions: list, add, remove, fire.\n"
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
        "in the prompt — delivery is automatic; adding it sends twice."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["list", "add", "remove", "fire"]},
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
                "description": "Delivery platform. Default: telegram.",
                "default": "telegram",
            },
            "chat_id": {
                "type": "string",
                "description": "Target chat id. Default: first allowlisted chat.",
            },
            "id": {"type": "string", "description": "Job id (for remove / fire)."},
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

    def run(self, action: str, kind: str = "cron", expression: str = "",
            after_hours: float | None = None, prompt: str = "",
            platform: str = "telegram", chat_id: str = "",
            run_at: str = "", id: str | None = None) -> ToolResult:
        home = get_home()
        jobs_path = home / "schedule" / "jobs.json"
        jobs_path.parent.mkdir(parents=True, exist_ok=True)
        jobs: list[dict] = json.loads(jobs_path.read_text()) if jobs_path.exists() else []

        if action == "list":
            return ToolResult(ok=True, output=json.dumps(jobs, indent=2))

        if action == "add":
            if not prompt:
                return ToolResult(ok=False, output="", error="'prompt' is required")
            from alpi.tools.skill import scan_skill_body
            flags = scan_skill_body(prompt)
            if flags:
                return ToolResult(
                    ok=False, output="",
                    error=(
                        "threat scan blocked scheduled prompt "
                        f"(runs unattended with full tool access): {', '.join(flags)}"
                    ),
                )
            from datetime import datetime, timezone
            now_iso = datetime.now(timezone.utc).isoformat()
            job: dict = {
                "id": uuid.uuid4().hex[:8],
                "kind": kind or "cron",
                "prompt": prompt,
                "platform": (platform or "telegram").lower(),
                "chat_id": chat_id or "",
                "last_run_at": now_iso if (kind or "cron") == "cron" else None,
            }
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

            return ToolResult(
                ok=True,
                output=f"Added {job['kind']} job {job['id']} — {hint}",
            )

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


TOOL = Schedule
