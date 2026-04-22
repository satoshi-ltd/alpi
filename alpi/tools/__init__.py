"""Tool registry."""

from __future__ import annotations

from alpi.tools.base import Tool, ToolResult
from alpi.tools import (
    browser,
    delegate,
    research,
    edit_file,
    email as email_tool,
    memory as memory_tool,
    read_file,
    read_image,
    schedule as schedule_tool,
    search,
    send_message,
    session_search,
    skill as skill_tool,
    stt as stt_tool,
    terminal,
    todo,
    tts as tts_tool,
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
        available = ", ".join(sorted(_TOOLS.keys()))
        return ToolResult(
            ok=False,
            output="",
            error=f"unknown tool: {name}. Available tools: {available}",
        )
    try:
        return cls().run(**arguments)
    except TypeError as e:
        return ToolResult(ok=False, output="", error=f"bad arguments for {name}: {e}")
    except Exception as e:  # noqa: BLE001
        return ToolResult(ok=False, output="", error=f"{name} crashed: {e}")


# Register every tool exposed by the sibling modules.
for _mod in (
    read_file,
    read_image,
    write_file,
    edit_file,
    terminal,
    search,
    todo,
    web_search,
    web_fetch,
    web_extract,
    browser,
    schedule_tool,
    memory_tool,
    session_search,
    skill_tool,
    research,
    delegate,
    send_message,
    email_tool,
    tts_tool,
    stt_tool,
):
    _cls = getattr(_mod, "TOOL", None)
    if _cls is not None:
        register(_cls)

__all__ = ["Tool", "ToolResult", "all_tools", "get", "register", "schemas"]
