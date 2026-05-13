"""In-session task list. State lives on ``Session.todos`` via a ContextVar so parallel sessions don't share."""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any

from alpi.tools.base import Tool, ToolResult

_PENDING = "pending"
_IN_PROGRESS = "in_progress"
_COMPLETED = "completed"

# Engine binds this around tool calls so each tool sees its own session's list.
_active_store: ContextVar[list[dict[str, Any]] | None] = ContextVar(
    "alpi_todo_store", default=None,
)


def bind_store(items: list[dict[str, Any]]):
    """Engine handle to swap the active todo list around tool execution."""
    return _active_store.set(items)


def reset_store(token) -> None:
    _active_store.reset(token)


def open_todos(store: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return todos in ``pending`` or ``in_progress`` — both are unfinished."""
    return [t for t in store if t.get("status") in (_PENDING, _IN_PROGRESS)]


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
        "HARD RULE — open todos are a binding contract: while any task is "
        "`pending` or `in_progress`, the engine treats your turn as "
        "incomplete. A final assistant message with no tool_calls in that "
        "state is auto-rejected; you'll be re-prompted to continue and it "
        "consumes one of your remaining steps. Either keep emitting "
        "tool_calls until every todo is `complete`, or `clear` the list "
        "before you stop.\n"
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
        store = _active_store.get()
        if store is None:
            # No binding → ephemeral list (non-engine callers, isolated tests).
            store = []
        if action == "list":
            if not store:
                return ToolResult(ok=True, output="(no todos)")
            return ToolResult(ok=True, output=_format(store))
        if action == "add":
            if not content:
                return ToolResult(ok=False, output="", error="'content' required for add")
            store.append({"content": content, "status": _PENDING})
            return ToolResult(ok=True, output=_format(store))
        if action == "start":
            if index is None or not (0 <= index < len(store)):
                return ToolResult(ok=False, output="", error="valid 'index' required")
            active = next(
                (i for i, t in enumerate(store) if t["status"] == _IN_PROGRESS),
                None,
            )
            if active is not None and active != index:
                return ToolResult(
                    ok=False,
                    output="",
                    error=f"task {active} is already in_progress — complete it first",
                )
            store[index]["status"] = _IN_PROGRESS
            return ToolResult(ok=True, output=_format(store))
        if action == "complete":
            if index is None or not (0 <= index < len(store)):
                return ToolResult(ok=False, output="", error="valid 'index' required")
            store[index]["status"] = _COMPLETED
            return ToolResult(ok=True, output=_format(store))
        if action == "clear":
            store.clear()
            return ToolResult(ok=True, output="(cleared)")
        return ToolResult(ok=False, output="", error=f"unknown action: {action}")


_MARK = {_PENDING: "[ ]", _IN_PROGRESS: "[·]", _COMPLETED: "[x]"}


def _format(items: list[dict[str, Any]]) -> str:
    return "\n".join(
        f"{i}. {_MARK[t['status']]} {t['content']}"
        for i, t in enumerate(items)
    )


TOOL = Todo
