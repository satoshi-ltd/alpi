from __future__ import annotations

import json
import re
from typing import Any

from alpi.tools.base import Tool, ToolResult


_REF = re.compile(r"\$\{([A-Za-z0-9_-]+)\.(ok|output|error)\}")


def _expand(value: Any, results: dict[str, dict[str, Any]]) -> Any:
    if isinstance(value, dict):
        return {key: _expand(item, results) for key, item in value.items()}
    if isinstance(value, list):
        return [_expand(item, results) for item in value]
    if not isinstance(value, str):
        return value
    match = _REF.fullmatch(value)
    if match:
        return results.get(match.group(1), {}).get(match.group(2))

    def replacement(item: re.Match) -> str:
        resolved = results.get(item.group(1), {}).get(item.group(2))
        return "" if resolved is None else str(resolved)

    return _REF.sub(
        replacement,
        value,
    )


class Workflow(Tool):
    name = "workflow"
    description = (
        "Run a small dependency graph of existing tools under the current run's "
        "policy, permissions, execution world, and audit journal. Independent "
        "read-only steps may run in parallel. Reference prior values with "
        "${step_id.output}, ${step_id.ok}, or ${step_id.error}."
    )
    parameters = {
        "type": "object",
        "properties": {
            "steps": {
                "type": "array", "minItems": 1, "maxItems": 50,
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "tool": {"type": "string"},
                        "arguments": {"type": "object"},
                        "depends_on": {"type": "array", "items": {"type": "string"}},
                        "continue_on_error": {"type": "boolean", "default": False},
                    },
                    "required": ["id", "tool", "arguments"],
                },
            },
        },
        "required": ["steps"],
    }

    def run(self, steps: list[dict]) -> ToolResult:
        from alpi import tools
        from alpi.core.tool_executor import ToolCall, current

        if not isinstance(steps, list) or not 1 <= len(steps) <= 50:
            return ToolResult(False, "", "steps must contain 1 to 50 entries")
        pending: dict[str, dict] = {}
        for raw in steps:
            if not isinstance(raw, dict):
                return ToolResult(False, "", "invalid workflow step: expected an object")
            sid = str(raw.get("id") or "").strip()
            name = str(raw.get("tool") or "").strip()
            args = raw.get("arguments")
            deps = raw.get("depends_on") or []
            if not sid or sid in pending or name == "workflow" or not isinstance(args, dict):
                return ToolResult(False, "", f"invalid or duplicate workflow step: {sid or '(missing id)'}")
            if not isinstance(deps, list) or any(not isinstance(dep, str) for dep in deps):
                return ToolResult(False, "", f"invalid dependencies for step: {sid}")
            pending[sid] = {**raw, "tool": name, "depends_on": deps}
        unknown = sorted({dep for row in pending.values() for dep in row["depends_on"] if dep not in pending})
        if unknown:
            return ToolResult(False, "", f"unknown workflow dependencies: {', '.join(unknown)}")

        results: dict[str, dict[str, Any]] = {}
        executor = current()
        while pending:
            ready = [sid for sid, row in pending.items() if all(dep in results for dep in row["depends_on"])]
            if not ready:
                return ToolResult(False, json.dumps(results), "workflow dependency cycle")
            calls = [
                ToolCall(sid, pending[sid]["tool"], _expand(pending[sid]["arguments"], results))
                for sid in ready
            ]
            if executor is not None:
                outcomes = executor.execute_parallel(calls)
                completed = [(outcome.call.call_id, outcome.result) for outcome in outcomes]
            else:
                completed = [(call.call_id, tools.execute(call.name, call.arguments)) for call in calls]
            stop = None
            for sid, result in completed:
                results[sid] = result.to_dict()
                row = pending.pop(sid)
                if not result.ok and not bool(row.get("continue_on_error")) and stop is None:
                    stop = sid
            if stop is not None:
                return ToolResult(False, json.dumps(results, ensure_ascii=False), f"workflow stopped at step: {stop}")
        return ToolResult(True, json.dumps(results, ensure_ascii=False))


TOOL = Workflow
