from __future__ import annotations

import asyncio
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
    server.register("host.workgroup.tasks", _workgroup_tasks)
    server.register("host.sessions.list", _sessions_list)
    server.register("host.session.read", _session_read)
    server.register("host.sessions.delete", _sessions_delete)


def _check_id(name: str, kind: str) -> None:
    if not name or not _SAFE_ID.match(name):
        raise host_server.HandlerError(
            -32602, "invalid-params",
            data={"detail": f"{kind} fails [A-Za-z0-9_-]+"},
        )


def _resolve_home(profile: str) -> Path:
    _check_id(profile, "profile")
    return home_mod.home_for(profile)


_TRANSCRIPT_DEFAULT_LIMIT = 200
_TRANSCRIPT_MAX_LIMIT = 1000


async def _workgroup_transcript(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    profile = str((params or {}).get("profile") or "")
    wg_id = str((params or {}).get("wg_id") or "").strip()
    _check_id(wg_id, "wg_id")
    home = _resolve_home(profile)
    p = params or {}
    after_seq_raw = p.get("after_seq")
    after_seq = int(after_seq_raw) if isinstance(after_seq_raw, (int, float)) else None
    limit_raw = p.get("limit")
    limit = int(limit_raw) if isinstance(limit_raw, (int, float)) else _TRANSCRIPT_DEFAULT_LIMIT
    limit = max(1, min(limit, _TRANSCRIPT_MAX_LIMIT))
    # Without after_seq, default to tail so first-paint of a large transcript ships the recent window, not the oldest.
    if "tail" in p:
        tail = bool(p["tail"])
    else:
        tail = after_seq is None
    # Per-post decrypt is CPU-bound; pagination caps cost and asyncio.to_thread keeps it off the loop.
    posts = await asyncio.to_thread(
        host_workgroup.decrypt_transcript, home, wg_id,
        after_seq=after_seq, limit=limit, tail=tail,
    )
    next_seq = posts[-1]["seq"] if posts else (after_seq or 0)
    return {"posts": posts, "next_seq": next_seq, "limit": limit}


async def _workgroup_tasks(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    profile = str((params or {}).get("profile") or "")
    wg_id = str((params or {}).get("wg_id") or "").strip()
    _check_id(wg_id, "wg_id")
    home = _resolve_home(profile)
    # Decrypt + fold is CPU-bound; keep it off the event loop.
    return await asyncio.to_thread(host_workgroup.fold_task_state, home, wg_id)


async def _sessions_list(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    profile = str((params or {}).get("profile") or "")
    limit_raw = (params or {}).get("limit")
    limit = int(limit_raw) if limit_raw is not None else None
    home = _resolve_home(profile)
    from alpi.host.connection_context import current
    connection_id = current().connection_id
    sessions = await asyncio.to_thread(host_sessions.list_sessions, home, None)
    sessions = [row for row in sessions if row.get("connection_id") == connection_id]
    if limit is not None and limit > 0:
        sessions = sessions[:limit]
    return {"sessions": sessions}


def _coerce_count(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return max(0, int(value))


async def _session_read(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    profile = str((params or {}).get("profile") or "")
    session_id = str((params or {}).get("id") or "").strip()
    _check_id(session_id, "id")
    home = _resolve_home(profile)
    from alpi.host.connection_context import current
    try:
        owner = await asyncio.to_thread(host_sessions.session_connection_id, home, session_id)
    except FileNotFoundError as e:
        raise host_server.HandlerError(-32004, "not-found", data={"detail": str(e)})
    if owner != current().connection_id:
        raise host_server.HandlerError(-32004, "not-found", data={"detail": "session not found"})
    after_turn = _coerce_count((params or {}).get("after_turn"))
    tail_turns = _coerce_count((params or {}).get("tail_turns"))
    before_turn = _coerce_count((params or {}).get("before_turn"))
    max_turns = _coerce_count((params or {}).get("max_turns"))

    def _load() -> dict[str, Any]:
        data, total, offset, first_user = host_sessions.read_session_slice(
            home,
            session_id,
            after_turn=after_turn,
            tail_turns=tail_turns,
            before_turn=before_turn,
            max_turns=max_turns,
        )
        for t in data["turns"]:
            if isinstance(t, dict):
                # empty assistant text alone does not mean interrupted
                t["unfinished"] = bool(t.get("interrupted"))
        from alpi.host import chat as host_chat
        in_flight = host_chat.session_key(profile, session_id) in host_chat._session_active
        # total_turns is the capability marker for partial-read support; kind must classify the pre-slice first turn
        return {
            "session": data,
            "total_turns": total,
            "turns_offset": offset,
            "in_flight": in_flight,
            "kind": host_sessions.classify_first_user(first_user),
        }

    try:
        return await asyncio.to_thread(_load)
    except FileNotFoundError as e:
        raise host_server.HandlerError(
            -32004, "not-found", data={"detail": str(e)},
        )


_MAX_DELETE_IDS = 200


async def _sessions_delete(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    """Bulk-delete sessions. Per-id outcome: skipped (busy or missing) goes to ``errors``; removed goes to ``deleted``."""
    from alpi.host import chat as host_chat
    profile = str((params or {}).get("profile") or "")
    raw_ids = (params or {}).get("ids")
    if not isinstance(raw_ids, list) or not raw_ids:
        raise host_server.HandlerError(
            -32602, "invalid-params", data={"detail": "ids must be a non-empty list"},
        )
    if len(raw_ids) > _MAX_DELETE_IDS:
        raise host_server.HandlerError(
            -32602, "invalid-params",
            data={"detail": f"too many ids (max {_MAX_DELETE_IDS})"},
        )
    home = _resolve_home(profile)
    from alpi.host.connection_context import current
    connection_id = current().connection_id
    deleted: list[str] = []
    errors: list[dict[str, str]] = []
    for raw in raw_ids:
        sid = str(raw or "").strip()
        if not sid or not _SAFE_ID.match(sid):
            errors.append({"id": sid, "code": "invalid-id"})
            continue
        if host_chat.session_key(profile, sid) in host_chat._session_active:
            errors.append({"id": sid, "code": "session-busy"})
            continue
        try:
            owner = await asyncio.to_thread(host_sessions.session_connection_id, home, sid)
        except FileNotFoundError:
            errors.append({"id": sid, "code": "not-found"})
            continue
        if owner != connection_id:
            errors.append({"id": sid, "code": "not-found"})
            continue
        existed = await asyncio.to_thread(host_sessions.delete_session, home, sid)
        if existed:
            deleted.append(sid)
        else:
            errors.append({"id": sid, "code": "not-found"})
    return {"deleted": deleted, "errors": errors}
