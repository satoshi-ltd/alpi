"""host.outputs.* verbs. Mutations emit ``output.updated``; producers emit ``output.created``."""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any

from alpi import outputs as outputs_mod
from alpi.host import events as host_events
from alpi.host import server as host_server


_OUTPUT_ID = re.compile(r"^[a-f0-9]{12}$")
_LIST_DEFAULT_LIMIT = 100
_LIST_MAX_LIMIT = outputs_mod.MAX_OUTPUTS


def register(server: host_server.Server) -> None:
    server.register("host.outputs.list", _list)
    server.register("host.outputs.read", _read)
    server.register("host.outputs.mark_read", _mark_read)
    server.register("host.outputs.mark_all_read", _mark_all_read)
    server.register("host.outputs.delete", _delete)


def _resolve_home(profile: str) -> Path:
    from alpi.host.handlers import _resolve_home as _r
    return _r(profile)


def _check_output_id(output_id: str) -> None:
    if not output_id or not _OUTPUT_ID.match(output_id):
        raise host_server.HandlerError(
            -32602, "invalid-params",
            data={"detail": "output id must be 12 lowercase hex chars"},
        )


async def _list(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    profile = str((params or {}).get("profile") or "")
    status = (params or {}).get("status")
    if status is not None:
        status = str(status).strip().lower()
        if status not in outputs_mod.VALID_STATUS:
            raise host_server.HandlerError(
                -32602, "invalid-params",
                data={"detail": f"invalid status: {status!r}"},
            )
    limit_raw = (params or {}).get("limit")
    limit = int(limit_raw) if isinstance(limit_raw, (int, float)) else _LIST_DEFAULT_LIMIT
    limit = max(1, min(limit, _LIST_MAX_LIMIT))
    home = _resolve_home(profile)
    items = await asyncio.to_thread(
        outputs_mod.list_outputs, home, status=status, limit=limit,
    )
    return {"outputs": items}


async def _read(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    profile = str((params or {}).get("profile") or "")
    output_id = str((params or {}).get("id") or "").strip()
    _check_output_id(output_id)
    home = _resolve_home(profile)
    item = await asyncio.to_thread(outputs_mod.read, home, output_id)
    if item is None:
        raise host_server.HandlerError(
            -32004, "not-found", data={"detail": f"no output {output_id!r}"},
        )
    return {"output": item}


async def _mark_read(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    profile = str((params or {}).get("profile") or "")
    output_id = str((params or {}).get("id") or "").strip()
    _check_output_id(output_id)
    home = _resolve_home(profile)
    item = await asyncio.to_thread(outputs_mod.mark_read, home, output_id)
    if item is None:
        raise host_server.HandlerError(
            -32004, "not-found", data={"detail": f"no output {output_id!r}"},
        )
    try:
        host_events.emit("output.updated", {
            "profile": profile,
            "id": output_id,
            "status": item.get("status", "read"),
        })
    except Exception:  # noqa: BLE001
        pass
    return {"ok": True, "output": item}


async def _delete(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    profile = str((params or {}).get("profile") or "")
    output_id = str((params or {}).get("id") or "").strip()
    _check_output_id(output_id)
    home = _resolve_home(profile)
    removed = await asyncio.to_thread(outputs_mod.delete, home, output_id)
    if not removed:
        raise host_server.HandlerError(
            -32004, "not-found", data={"detail": f"no output {output_id!r}"},
        )
    try:
        host_events.emit("output.updated", {
            "profile": profile,
            "id": output_id,
            "action": "deleted",
        })
    except Exception:  # noqa: BLE001
        pass
    return {"ok": True}


async def _mark_all_read(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    profile = str((params or {}).get("profile") or "")
    home = _resolve_home(profile)
    count = await asyncio.to_thread(outputs_mod.mark_all_read, home)
    if count:
        try:
            host_events.emit("output.updated", {
                "profile": profile,
                "action": "mark_all_read",
                "count": count,
            })
        except Exception:  # noqa: BLE001
            pass
    return {"ok": True, "count": count}


__all__ = ["register"]
