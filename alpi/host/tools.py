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
# prefix-based map is plenty without burdening every Tool class with
# metadata that only the UI consumes.
_CATEGORIES: list[tuple[str, tuple[str, ...]]] = [
    ("Filesystem", ("read_file", "write_file", "edit_file", "read_image")),
    ("Workspace", ("workspace_search", "workspace_index")),
    ("Web", ("web_search", "web_fetch", "web_extract", "browser")),
    ("Memory", ("memory", "session_search")),
    ("Comms", ("send_message", "email", "peer")),
    ("Agent", ("skill", "schedule", "delegate", "research", "todo")),
    ("Media", ("tts", "stt")),
    ("System", ("terminal", "db")),
    ("Collab", ("workgroup",)),
]


def _category_for(name: str) -> str:
    for label, members in _CATEGORIES:
        if name in members:
            return label
    return "Other"


def register(server: host_server.Server) -> None:
    server.register("host.tools.list", _tools_list)


async def _tools_list(
    _params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    from alpi import tools as tools_mod

    items: list[dict[str, Any]] = []
    for cls in tools_mod.all_tools():
        if ":" in cls.name:
            continue
        items.append({
            "name": cls.name,
            "category": _category_for(cls.name),
            "description": cls.description,
            "parameters": cls.parameters,
        })
    return {"tools": items}
