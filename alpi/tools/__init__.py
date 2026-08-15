"""Tool registry."""

from __future__ import annotations

import contextvars
import copy
from contextlib import contextmanager
from typing import Iterator

from alpi.host.connection_context import current
from alpi.tools.base import Tool, ToolResult
from alpi.tools._availability import is_available, invalidate as _invalidate_availability
from alpi.tools import (
    peer,
    ask_user as ask_user_tool,
    attach_file as attach_file_tool,
    browser,
    db as db_tool,
    delegate,
    delete_file,
    research,
    edit_file,
    email as email_tool,
    knowledge as knowledge_tool,
    knowledge_base as knowledge_base_tool,
    memory as memory_tool,
    notify as notify_tool,
    recall as recall_tool,
    workgroup_search as workgroup_search_tool,
    read_file,
    read_image,
    schedule as schedule_tool,
    search,
    session_search,
    session_read,
    skill as skill_tool,
    stt as stt_tool,
    terminal,
    todo,
    tts as tts_tool,
    web_extract,
    web_fetch,
    web_search,
    workgroup as workgroup_tool,
    workgroup_file as workgroup_file_tool,
    write_file,
)

_TOOLS: dict[str, type[Tool]] = {}

_turn_mcp_tools: contextvars.ContextVar[dict[str, type[Tool]]] = contextvars.ContextVar(
    "turn_mcp_tools", default={}
)

_MEMBER_ALLOWED_ACTIONS: dict[str, frozenset[str]] = {
    "skill": frozenset({"list", "view", "validate", "run", "test", "invoke"}),
    "memory": frozenset({"read", "promotion_list"}),
    "schedule": frozenset({"list"}),
}


@contextmanager
def use_mcp_tools(mapping: dict[str, type[Tool]] | None) -> Iterator[None]:
    token = _turn_mcp_tools.set(dict(mapping) if mapping else {})
    try:
        yield
    finally:
        _turn_mcp_tools.reset(token)


def _current_tools() -> dict[str, type[Tool]]:
    extra = _turn_mcp_tools.get()
    return {**_TOOLS, **extra} if extra else _TOOLS


def register(cls: type[Tool]) -> type[Tool]:
    _TOOLS[cls.name] = cls
    return cls


def all_tools() -> list[type[Tool]]:
    return list(_current_tools().values())


def get(name: str) -> type[Tool] | None:
    return _current_tools().get(name)


def schemas(deny: frozenset[str] | set[str] | None = None) -> list[dict]:
    deny = deny or frozenset()
    # Wire order is part of the provider's cache prefix — sort so registry/MCP insertion order can never invalidate it.
    schemas = sorted(
        (
            cls.schema() for cls in _current_tools().values()
            if is_available(cls)[0] and cls.name not in deny
        ),
        key=_schema_sort_key,
    )
    if current().role != "member":
        return schemas
    return [_member_schema(schema) for schema in schemas]


def _schema_sort_key(schema: dict) -> str:
    try:
        return str(schema.get("function", {}).get("name") or "")
    except AttributeError:
        return ""


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
    current_tools = _current_tools()
    cls = current_tools.get(name)
    if cls is None:
        available = ", ".join(sorted(current_tools.keys()))
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
    member_refusal = _member_mutation_refusal(name, arguments)
    if member_refusal is not None:
        return member_refusal
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


def _member_schema(schema: dict) -> dict:
    name = schema.get("function", {}).get("name", "")
    allowed = _MEMBER_ALLOWED_ACTIONS.get(name)
    action = schema.get("function", {}).get("parameters", {}).get("properties", {}).get("action")
    if allowed is None or not isinstance(action, dict) or not isinstance(action.get("enum"), list):
        return schema
    trimmed = copy.deepcopy(schema)
    enum = trimmed["function"]["parameters"]["properties"]["action"]["enum"]
    trimmed["function"]["parameters"]["properties"]["action"]["enum"] = [
        value for value in enum if value in allowed
    ]
    return trimmed


def _member_mutation_refusal(name: str, arguments: dict) -> ToolResult | None:
    allowed = _MEMBER_ALLOWED_ACTIONS.get(name)
    if current().role != "member" or allowed is None:
        return None
    action = str(arguments.get("action", "") or "")
    if action in allowed:
        return None
    return ToolResult(
        ok=False,
        output="",
        error=f"members cannot modify {name}; action '{action or '(none)'}' requires an admin device",
    )


# Register every tool exposed by the sibling modules.
# Order matters: durable knowledge retrieval should be the preferred recall
# surface for user/workspace knowledge.
register(knowledge_base_tool.TOOL)
register(recall_tool.TOOL_RECALL)
register(recall_tool.TOOL_INDEX)
register(workgroup_search_tool.TOOL_SEARCH)
register(workgroup_search_tool.TOOL_INDEX)
for _mod in (
    read_file,
    read_image,
    write_file,
    edit_file,
    delete_file,
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
    session_read,
    skill_tool,
    knowledge_tool,
    research,
    delegate,
    notify_tool,
    email_tool,
    tts_tool,
    stt_tool,
    peer,
    workgroup_tool,
    workgroup_file_tool,
    ask_user_tool,
    attach_file_tool,
):
    _cls = getattr(_mod, "TOOL", None)
    if _cls is not None:
        register(_cls)

__all__ = [
    "Tool", "ToolResult",
    "all_tools", "get", "register", "schemas", "availability_report",
]
