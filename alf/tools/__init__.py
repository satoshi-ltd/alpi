"""Tool registry."""

from __future__ import annotations

from alf.tools.base import Tool, ToolResult
from alf.tools import (
    config as config_tool,
    create_skill,
    delegate,
    delete_skill,
    edit_file,
    edit_skill,
    email as email_tool,
    glob as glob_tool,
    grep,
    memory as memory_tool,
    read_file,
    schedule as schedule_tool,
    send_message,
    session_search,
    terminal,
    todo,
    web_extract,
    web_fetch,
    web_search,
    write_file,
)

_TOOLS: dict[str, type[Tool]] = {}


def register(cls: type[Tool]) -> type[Tool]:
    _TOOLS[cls.name] = cls
    return cls


def all_tools() -> list[type[Tool]]:
    return list(_TOOLS.values())


def get(name: str) -> type[Tool] | None:
    return _TOOLS.get(name)


def schemas() -> list[dict]:
    return [cls.schema() for cls in _TOOLS.values()]


def execute(name: str, arguments: dict) -> ToolResult:
    """Execute a tool by name. Unknown names return an error result."""
    cls = _TOOLS.get(name)
    if cls is None:
        return ToolResult(ok=False, output="", error=f"unknown tool: {name}")
    try:
        return cls().run(**arguments)
    except TypeError as e:
        return ToolResult(ok=False, output="", error=f"bad arguments for {name}: {e}")
    except Exception as e:  # noqa: BLE001
        return ToolResult(ok=False, output="", error=f"{name} crashed: {e}")


# Register every tool exposed by the sibling modules.
for _mod in (
    read_file,
    write_file,
    edit_file,
    terminal,
    grep,
    glob_tool,
    todo,
    web_search,
    web_fetch,
    web_extract,
    schedule_tool,
    memory_tool,
    session_search,
    create_skill,
    edit_skill,
    delete_skill,
    delegate,
    send_message,
    email_tool,
    config_tool,
):
    _cls = getattr(_mod, "TOOL", None)
    if _cls is not None:
        register(_cls)

__all__ = ["Tool", "ToolResult", "all_tools", "get", "register", "schemas"]
