"""schedule tool — manage scheduled jobs in ~/.alf/schedule/jobs.json."""

from __future__ import annotations

import json
import uuid

from alf.home import get_home
from alf.tools.base import Tool, ToolResult


class Schedule(Tool):
    name = "schedule"
    description = (
        "Schedule a proactive job. Actions: list, add, remove.\n"
        "\n"
        "Pick `kind`:\n"
        "  cron       — cron expression (field: `expression`, e.g. '0 9 * * *')\n"
        "  inactivity — fires after N hours of user silence (field: `after_hours`)\n"
        "\n"
        "`prompt` is what alf should do when the job fires. Its reply "
        "is AUTO-DELIVERED to `platform` + `chat_id` (defaults: telegram "
        "+ first allowlisted chat). Do NOT include 'send to telegram' "
        "in the prompt — delivery is automatic; adding it sends twice."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["list", "add", "remove"]},
            "kind": {
                "type": "string",
                "enum": ["cron", "inactivity"],
                "description": "Job kind. Default: cron.",
                "default": "cron",
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
                "description": "What to ask alf to do when the job fires.",
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
            "id": {"type": "string", "description": "Job id (for remove)."},
        },
        "required": ["action"],
    }

    def run(self, action: str, kind: str = "cron", expression: str = "",
            after_hours: float | None = None, prompt: str = "",
            platform: str = "telegram", chat_id: str = "",
            id: str | None = None) -> ToolResult:
        home = get_home()
        jobs_path = home / "schedule" / "jobs.json"
        jobs_path.parent.mkdir(parents=True, exist_ok=True)
        jobs: list[dict] = json.loads(jobs_path.read_text()) if jobs_path.exists() else []

        if action == "list":
            return ToolResult(ok=True, output=json.dumps(jobs, indent=2))

        if action == "add":
            if not prompt:
                return ToolResult(ok=False, output="", error="'prompt' is required")
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

            # Tell the user how to activate delivery. Same pattern as
            # the gateway: nothing starts until the user asks for it.
            from alf.scheduler.run import running_pid
            if running_pid(home):
                hint = "daemon is running — job will fire on schedule"
            else:
                hint = "run 'alf schedule start' (or install it) to fire jobs"

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

        return ToolResult(ok=False, output="", error=f"unknown action: {action}")


TOOL = Schedule
