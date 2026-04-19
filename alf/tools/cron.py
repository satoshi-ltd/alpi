"""Cron tool — manage scheduled jobs in ~/.alf/cron/jobs.json.

v0: CRUD over jobs.json. The scheduler itself (that actually runs jobs at
their expressions) is a separate process — added in v0.1.
"""

from __future__ import annotations

import json
import uuid

from alf.home import get_home
from alf.tools.base import Tool, ToolResult


class Cron(Tool):
    name = "cron"
    description = "Manage scheduled jobs. Actions: list, add, remove."
    parameters = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["list", "add", "remove"]},
            "expression": {"type": "string", "description": "Cron expression, e.g. '0 9 * * *'."},
            "prompt": {"type": "string", "description": "What to ask alf to do when it fires."},
            "id": {"type": "string", "description": "Job id for remove."},
        },
        "required": ["action"],
    }

    def run(self, action: str, expression: str = "", prompt: str = "",
            id: str | None = None) -> ToolResult:
        jobs_path = get_home() / "cron" / "jobs.json"
        jobs_path.parent.mkdir(parents=True, exist_ok=True)
        jobs: list[dict] = json.loads(jobs_path.read_text()) if jobs_path.exists() else []

        if action == "list":
            return ToolResult(ok=True, output=json.dumps(jobs, indent=2))
        if action == "add":
            if not expression or not prompt:
                return ToolResult(ok=False, output="", error="'expression' and 'prompt' required")
            job = {"id": uuid.uuid4().hex[:8], "expression": expression, "prompt": prompt}
            jobs.append(job)
            jobs_path.write_text(json.dumps(jobs, indent=2))
            return ToolResult(ok=True, output=f"Added job {job['id']}")
        if action == "remove":
            if not id:
                return ToolResult(ok=False, output="", error="'id' required")
            new_jobs = [j for j in jobs if j.get("id") != id]
            if len(new_jobs) == len(jobs):
                return ToolResult(ok=False, output="", error=f"job {id} not found")
            jobs_path.write_text(json.dumps(new_jobs, indent=2))
            return ToolResult(ok=True, output=f"Removed job {id}")
        return ToolResult(ok=False, output="", error=f"unknown action: {action}")


TOOL = Cron
