"""In-memory todo list scoped to the current session."""

from __future__ import annotations

from alpi.tools.base import Tool, ToolResult

_TODOS: list[dict] = []

_PENDING = "pending"
_IN_PROGRESS = "in_progress"
_COMPLETED = "completed"


class Todo(Tool):
    name = "todo"
    description = (
        "In-session task list. Use for multi-step work (3+ steps) so you "
        "can track progress without re-reading the whole transcript.\n"
        "\n"
        "Actions: list | add | start | complete | clear.\n"
        "\n"
        "Workflow:\n"
        "  • `add` new tasks upfront — they enter as `pending`\n"
        "  • `start` a task before working on it — moves it to `in_progress`\n"
        "  • only ONE task may be `in_progress` at a time\n"
        "  • `complete` immediately when a step is done\n"
        "  • if a step fails, `complete` it and `add` a revised one\n"
        "\n"
        "Not persisted across sessions. For one-shot tasks (≤2 steps), "
        "skip this — just do the work."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "add", "start", "complete", "clear"],
            },
            "content": {"type": "string", "description": "Task content for 'add'."},
            "index": {
                "type": "integer",
                "description": "Task index for 'start' or 'complete'.",
            },
        },
        "required": ["action"],
    }

    def run(self, action: str, content: str = "", index: int | None = None) -> ToolResult:
        if action == "list":
            if not _TODOS:
                return ToolResult(ok=True, output="(no todos)")
            return ToolResult(ok=True, output=_format(_TODOS))
        if action == "add":
            if not content:
                return ToolResult(ok=False, output="", error="'content' required for add")
            _TODOS.append({"content": content, "status": _PENDING})
            return ToolResult(ok=True, output=_format(_TODOS))
        if action == "start":
            if index is None or not (0 <= index < len(_TODOS)):
                return ToolResult(ok=False, output="", error="valid 'index' required")
            active = next(
                (i for i, t in enumerate(_TODOS) if t["status"] == _IN_PROGRESS),
                None,
            )
            if active is not None and active != index:
                return ToolResult(
                    ok=False,
                    output="",
                    error=f"task {active} is already in_progress — complete it first",
                )
            _TODOS[index]["status"] = _IN_PROGRESS
            return ToolResult(ok=True, output=_format(_TODOS))
        if action == "complete":
            if index is None or not (0 <= index < len(_TODOS)):
                return ToolResult(ok=False, output="", error="valid 'index' required")
            _TODOS[index]["status"] = _COMPLETED
            return ToolResult(ok=True, output=_format(_TODOS))
        if action == "clear":
            _TODOS.clear()
            return ToolResult(ok=True, output="(cleared)")
        return ToolResult(ok=False, output="", error=f"unknown action: {action}")


_MARK = {_PENDING: "[ ]", _IN_PROGRESS: "[·]", _COMPLETED: "[x]"}


def _format(items: list[dict]) -> str:
    return "\n".join(
        f"{i}. {_MARK[t['status']]} {t['content']}"
        for i, t in enumerate(items)
    )


TOOL = Todo
