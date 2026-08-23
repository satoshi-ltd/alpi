"""Host plane: introspect the agent's tool registry.

The desktop/mobile UI needs to surface "what tools does this agent
have?" without spawning an agent turn. The TUI does it through the
``/tools`` floating panel reading ``alpi.tools.all_tools()`` directly;
the desktop hits this host verb instead so the same answer flows over
the wire when the client is remote.
"""

from __future__ import annotations

from typing import Any

from alpi.host import server as host_server


# UI-side categorisation. Tool names are stable identifiers, so a
# name-based map is plenty without burdening every Tool class with
# metadata that only the UI consumes.
_CATEGORIES: list[tuple[str, tuple[str, ...]]] = [
    ("Filesystem", ("read_file", "write_file", "edit_file", "delete_file", "read_image", "search", "attach_file")),
    ("Knowledge", ("knowledge",)),
    ("Web", ("web_search", "web_fetch", "web_extract", "browser")),
    ("Memory", ("memory", "session_search", "session_read", "recall_sessions", "index_sessions")),
    ("Comms", ("email", "peer", "notify", "ask_user")),
    ("Agent", ("skill", "schedule", "delegate", "research", "todo", "alpi_knowledge", "workflow")),
    ("Media", ("tts", "stt")),
    ("System", ("terminal", "db")),
    ("Collab", ("workgroup_post", "workgroup_file", "workgroup_search", "index_workgroups")),
]


def _category_for(name: str) -> str:
    # MCP tools are registered as `<server>__<tool>` (see
    # alpi/mcp/registry.py); group them by server so each MCP gets its
    # own section instead of falling into "Other".
    if "__" in name:
        server = name.split("__", 1)[0]
        return f"MCP · {server}"
    for label, members in _CATEGORIES:
        if name in members:
            return label
    return "Other"


def register(server: host_server.Server) -> None:
    server.register("host.tools.list", _tools_list)


async def _tools_list(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    from alpi import config as cfg_mod, home as home_mod, tools as tools_mod

    profile = str((params or {}).get("profile") or "").strip() or "default"
    deny: frozenset[str] = frozenset()
    try:
        cfg = cfg_mod.load(home_mod.home_for(profile))
        deny = frozenset(cfg.tools.deny or ())
    except Exception:  # noqa: BLE001 — config absent / malformed → no deny filter, list everything
        deny = frozenset()

    items: list[dict[str, Any]] = []
    for cls in tools_mod.all_tools():
        if ":" in cls.name:
            continue
        items.append({
            "name": cls.name,
            "category": _category_for(cls.name),
            "description": cls.description,
            "parameters": cls.parameters,
            "denied": cls.name in deny,
        })
    return {"tools": items}
