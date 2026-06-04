"""Tool registry."""

from __future__ import annotations

from alpi.tools.base import Tool, ToolResult
from alpi.tools._availability import is_available, invalidate as _invalidate_availability
from alpi.tools import (
    peer,
    ask_user as ask_user_tool,
    browser,
    db as db_tool,
    delegate,
    research,
    edit_file,
    email as email_tool,
    knowledge as knowledge_tool,
    learn_file as learn_file_tool,
    memory as memory_tool,
    recall as recall_tool,
    workgroup_search as workgroup_search_tool,
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
    workgroup as workgroup_tool,
    workspace as workspace_tool,
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


def schemas(deny: frozenset[str] | set[str] | None = None) -> list[dict]:
    """Schemas the LLM sees. Unavailable tools (TL.1 probe failed) are filtered so the model can't reach for a broken capability. ``deny`` (per-profile ``tools.deny`` from config) is applied on top — denied tools are simply absent from the schema."""
    deny = deny or frozenset()
    return [
        cls.schema() for cls in _TOOLS.values()
        if is_available(cls)[0] and cls.name not in deny
    ]


def availability_report() -> list[tuple[str, bool, str]]:
    """Fresh ``(name, available, reason)`` snapshot for every registered tool. Bypasses the cache so `alpi doctor` always shows current state."""
    _invalidate_availability()
    return [(cls.name, *is_available(cls)) for cls in _TOOLS.values()]


def execute(
    name: str,
    arguments: dict,
    deny: frozenset[str] | set[str] | None = None,
) -> ToolResult:
    """Execute a tool by name. Unknown or currently-unavailable names return an error result instead of calling .run(). When ``deny`` includes ``name``, the call is refused — defence in depth against a stale LLM context or prompt injection that names a tool the schema no longer advertises."""
    cls = _TOOLS.get(name)
    if cls is None:
        available = ", ".join(sorted(_TOOLS.keys()))
        return ToolResult(
            ok=False,
            output="",
            error=f"unknown tool: {name}. Available tools: {available}",
        )
    if deny and name in deny:
        return ToolResult(
            ok=False, output="",
            error=f"tool denied for this profile: {name} (see tools.deny in config.yaml)",
        )
    ok, reason = is_available(cls)
    if not ok:
        return ToolResult(
            ok=False, output="",
            error=f"tool unavailable: {name} ({reason or 'check failed'})",
        )
    try:
        return cls().run(**arguments)
    except TypeError as e:
        return ToolResult(ok=False, output="", error=f"bad arguments for {name}: {e}")
    except Exception as e:  # noqa: BLE001
        return ToolResult(ok=False, output="", error=f"{name} crashed: {e}")


# Register every tool exposed by the sibling modules.
# Order matters: tools that should be preferred for common intents
# (semantic recall over user files) come first so they appear earlier
# in the schema list the LLM sees.
register(workspace_tool.TOOL_SEARCH)
register(workspace_tool.TOOL_INDEX)
register(recall_tool.TOOL_RECALL)
register(recall_tool.TOOL_INDEX)
register(workgroup_search_tool.TOOL_SEARCH)
register(workgroup_search_tool.TOOL_INDEX)
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
    db_tool,
    memory_tool,
    session_search,
    skill_tool,
    knowledge_tool,
    learn_file_tool,
    research,
    delegate,
    send_message,
    email_tool,
    tts_tool,
    stt_tool,
    peer,
    workgroup_tool,
    ask_user_tool,
):
    _cls = getattr(_mod, "TOOL", None)
    if _cls is not None:
        register(_cls)

__all__ = [
    "Tool", "ToolResult",
    "all_tools", "get", "register", "schemas", "availability_report",
]
