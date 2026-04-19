"""schedule tool — manage scheduled jobs in ~/.alf/schedule/jobs.json.

Jobs are plain dicts on disk. A separate ``alf schedule start`` process
(the daemon) reads the same file, fires due jobs, and delivers their
output through ``gateway.delivery.send_to`` — so the daemon works
whether or not the gateway listener is running.

Two kinds of jobs:

- **cron** (default): fires on a standard cron expression
  (``0 9 * * *`` etc., parsed by ``croniter``).
- **inactivity**: fires once ``after_hours`` of user silence have passed
  (source of truth: mtime of the most recent file in ``sessions/``).
  A per-job cooldown equal to ``after_hours`` prevents re-spam.

On fire the daemon runs the prompt through ``alf chat --once`` and
sends the reply to ``(platform, chat_id)``. If ``chat_id`` is omitted
the daemon uses the first allowlisted chat for that platform.

The daemon's lifecycle mirrors the gateway's: it only runs if the user
explicitly starts it (``alf schedule start``) or installs it as a
system service. Adding a job here writes to disk; the ``add`` response
tells the user how to activate delivery if the daemon isn't live yet.

On-disk directory is ``~/.alf/schedule/``. If you're upgrading from
pre-v0.2 (``~/.alf/cron/``) ``home.ensure_home`` renames the legacy
folder on first run.
"""

from __future__ import annotations

import json
import uuid

from alf.home import get_home
from alf.tools.base import Tool, ToolResult


class Schedule(Tool):
    name = "schedule"
    description = (
        "Schedule a proactive job. Actions: list, add, remove. Pick "
        "`kind`: 'cron' for a standard cron expression (field: "
        "`expression`, e.g. '0 9 * * *') or 'inactivity' for a check-in "
        "after N hours of user silence (field: `after_hours`). `prompt` "
        "is what alf should do or compute when the job fires — its "
        "reply is AUTO-DELIVERED to `platform` + `chat_id` (defaults: "
        "telegram + first allowlisted chat). DO NOT include 'send to "
        "telegram' or similar in the prompt: delivery is automatic and "
        "adding it causes duplicate messages (one from `send_message`, "
        "one from the daemon). Use this tool when the user asks for "
        "reminders, recurring check-ins, or proactive outreach."
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
            job: dict = {
                "id": uuid.uuid4().hex[:8],
                "kind": kind or "cron",
                "prompt": prompt,
                "platform": (platform or "telegram").lower(),
                "chat_id": chat_id or "",
                "last_run_at": None,
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
