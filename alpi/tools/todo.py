"""In-memory todo list scoped to the current session."""

from __future__ import annotations

from alpi.tools.base import Tool, ToolResult

_TODOS: list[dict] = []


class Todo(Tool):
    name = "todo"
    description = (
        "In-session task list. Use for multi-step work (3+ steps) so you "
        "can track progress without re-reading the whole transcript.\n"
        "\n"
        "Actions: list | add | complete | clear.\n"
        "\n"
        "Guidelines:\n"
        "  • only ONE item in_progress at a time — break work linearly\n"
        "  • mark `complete` immediately when a step is done\n"
        "  • if a step fails, `complete` it and `add` a revised one\n"
        "\n"
        "Not persisted across sessions. For one-shot tasks (≤2 steps), "
        "skip this — just do the work."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["list", "add", "complete", "clear"]},
            "content": {"type": "string", "description": "Task content for 'add'."},
            "index": {"type": "integer", "description": "Task index for 'complete'."},
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
            _TODOS.append({"content": content, "done": False})
            return ToolResult(ok=True, output=_format(_TODOS))
        if action == "complete":
            if index is None or not (0 <= index < len(_TODOS)):
                return ToolResult(ok=False, output="", error="valid 'index' required")
            _TODOS[index]["done"] = True
            return ToolResult(ok=True, output=_format(_TODOS))
        if action == "clear":
            _TODOS.clear()
            return ToolResult(ok=True, output="(cleared)")
        return ToolResult(ok=False, output="", error=f"unknown action: {action}")


def _format(items: list[dict]) -> str:
    return "\n".join(
        f"{i}. [{'x' if t['done'] else ' '}] {t['content']}"
        for i, t in enumerate(items)
    )


TOOL = Todo
