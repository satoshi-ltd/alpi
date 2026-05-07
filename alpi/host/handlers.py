from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from alpi import home as home_mod
from alpi.host import sessions as host_sessions
from alpi.host import server as host_server
from alpi.host import workgroup as host_workgroup


_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]+$")


def register(server: host_server.Server) -> None:
    server.register("host.workgroup.transcript", _workgroup_transcript)
    server.register("host.sessions.list", _sessions_list)
    server.register("host.session.read", _session_read)


def _check_id(name: str, kind: str) -> None:
    if not name or not _SAFE_ID.match(name):
        raise host_server.HandlerError(
            -32602, "invalid-params",
            data={"detail": f"{kind} fails [A-Za-z0-9_-]+"},
        )


def _resolve_home(profile: str) -> Path:
    _check_id(profile, "profile")
    return home_mod.home_for(profile)


async def _workgroup_transcript(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    profile = str((params or {}).get("profile") or "")
    wg_id = str((params or {}).get("wg_id") or "").strip()
    _check_id(wg_id, "wg_id")
    home = _resolve_home(profile)
    return {"posts": host_workgroup.decrypt_transcript(home, wg_id)}


async def _sessions_list(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    profile = str((params or {}).get("profile") or "")
    limit_raw = (params or {}).get("limit")
    limit = int(limit_raw) if limit_raw is not None else None
    home = _resolve_home(profile)
    return {"sessions": host_sessions.list_sessions(home, limit=limit)}


async def _session_read(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    profile = str((params or {}).get("profile") or "")
    session_id = str((params or {}).get("id") or "").strip()
    _check_id(session_id, "id")
    home = _resolve_home(profile)
    try:
        data = host_sessions.read_session(home, session_id)
    except FileNotFoundError as e:
        raise host_server.HandlerError(
            -32004, "not-found", data={"detail": str(e)},
        )
    return {"session": data}
