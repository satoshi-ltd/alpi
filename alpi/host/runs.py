from __future__ import annotations

import asyncio
from typing import Any

from alpi import runs
from alpi.host import server as host_server


def register(server: host_server.Server) -> None:
    server.register("host.runs.list", _list)
    server.register("host.run.read", _read)
    server.register("host.run.cancel", _cancel)


def _home(params: dict[str, Any]):  # noqa: ANN202
    from alpi.host.handlers import _resolve_home

    return _resolve_home(str((params or {}).get("profile") or ""))


def _visible(row: dict[str, Any]) -> bool:
    from alpi.host.connection_context import owns_connection

    return owns_connection(row.get("connection_id"))


async def _list(params: dict[str, Any], _server: host_server.Server) -> dict[str, Any]:
    raw_limit = (params or {}).get("limit", 50)
    try:
        limit = max(1, min(int(raw_limit), runs.MAX_LIST_LIMIT))
    except (TypeError, ValueError):
        limit = 50
    home = _home(params)
    rows = await asyncio.to_thread(runs.list_runs, home, limit=runs.MAX_LIST_LIMIT)
    return {"runs": [row for row in rows if _visible(row)][:limit]}


async def _owned_summary(params: dict[str, Any]) -> tuple[Any, str, dict[str, Any]]:
    from alpi.host.handlers import _check_id

    run_id = str((params or {}).get("id") or "").strip()
    _check_id(run_id, "id")
    home = _home(params)
    try:
        row = await asyncio.to_thread(runs.summary, home, run_id)
    except (FileNotFoundError, ValueError) as exc:
        raise host_server.HandlerError(
            -32004, "not-found", data={"detail": "run not found"},
        ) from exc
    if not _visible(row):
        raise host_server.HandlerError(-32004, "not-found", data={"detail": "run not found"})
    return home, run_id, row


async def _read(params: dict[str, Any], _server: host_server.Server) -> dict[str, Any]:
    home, run_id, row = await _owned_summary(params)
    try:
        after_seq = int((params or {}).get("after_seq", -1))
        limit = int((params or {}).get("limit", 1000))
    except (TypeError, ValueError):
        raise host_server.HandlerError(-32602, "invalid-params") from None
    journal = await asyncio.to_thread(
        runs.read, home, run_id, after_seq=after_seq, limit=limit,
    )
    return {"run": row, **journal}


async def _cancel(params: dict[str, Any], _server: host_server.Server) -> dict[str, Any]:
    from alpi.host.handlers import _check_id
    from alpi.host.connection_context import HOST_CONNECTION_ID, current, owns_connection

    profile = str((params or {}).get("profile") or "")
    run_id = str((params or {}).get("id") or "").strip()
    _check_id(run_id, "id")
    _home(params)
    from alpi.host.chat import active_run

    local_operator = current().connection_id == HOST_CONNECTION_ID
    engine = active_run(profile, run_id)
    session = getattr(engine, "session", None)
    if engine is not None and (
        local_operator or owns_connection(getattr(session, "connection_id", None))
    ):
        engine.request_interrupt("run-cancel-rpc")
        return {"cancelled": True}
    entry = runs.active(profile, run_id)
    if entry is not None and (local_operator or owns_connection(entry[0])):
        entry[1].request_interrupt("run-cancel-rpc")
        return {"cancelled": True}
    await _owned_summary(params)
    return {"cancelled": False}


__all__ = ["register"]
