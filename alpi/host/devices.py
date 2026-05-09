from __future__ import annotations

import secrets
import time
from pathlib import Path
from typing import Any

import yaml

from alpi.host import server as host_server


def register(server: host_server.Server) -> None:
    server.register("host.devices.list", _list)
    server.register("host.devices.generate", _generate)
    server.register("host.devices.revoke", _revoke)
    server.register("host.devices.rename", _rename)


def _store_path() -> Path:
    from alpi.home import _ROOT
    return _ROOT / "host" / "devices.yaml"


def load() -> list[dict[str, Any]]:
    path = _store_path()
    if not path.exists():
        return []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    except Exception:  # noqa: BLE001
        return []
    if not isinstance(data, list):
        return []
    out: list[dict[str, Any]] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        token = str(row.get("token") or "")
        if not token:
            continue
        out.append({
            "token": token,
            "label": str(row.get("label") or ""),
            "created": int(row.get("created") or 0),
            "last_seen": int(row.get("last_seen")) if row.get("last_seen") else None,
        })
    return out


def save(devices: list[dict[str, Any]]) -> None:
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(devices, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    try:
        path.chmod(0o600)
    except OSError:
        pass


def is_valid(token: str) -> bool:
    if not token:
        return False
    return any(d["token"] == token for d in load())


def touch(token: str) -> None:
    devices = load()
    now = int(time.time())
    changed = False
    for d in devices:
        if d["token"] == token:
            d["last_seen"] = now
            changed = True
            break
    if changed:
        save(devices)


def add(label: str = "") -> dict[str, Any]:
    devices = load()
    # 24 bytes urlsafe = 32 chars, 192 bits entropy — keeps the QR small.
    row = {
        "token": secrets.token_urlsafe(24),
        "label": (label or "").strip() or "pending",
        "created": int(time.time()),
        "last_seen": None,
    }
    devices.append(row)
    save(devices)
    return row


def revoke(token: str) -> bool:
    devices = load()
    before = len(devices)
    devices = [d for d in devices if d["token"] != token]
    if len(devices) == before:
        return False
    save(devices)
    return True


def rename(token: str, label: str) -> bool:
    devices = load()
    changed = False
    for d in devices:
        if d["token"] == token:
            d["label"] = (label or "").strip() or d["label"]
            changed = True
            break
    if changed:
        save(devices)
    return changed


def _redacted(d: dict[str, Any]) -> dict[str, Any]:
    # token_id = last 8 chars; the full token never leaves the daemon
    # except on `generate` (single-use, embedded in the QR).
    tok = d.get("token") or ""
    return {
        "token_id": tok[-8:] if len(tok) >= 8 else tok,
        "label": d.get("label") or "",
        "created": d.get("created") or 0,
        "last_seen": d.get("last_seen"),
    }


async def _list(_params: dict[str, Any], _server: host_server.Server) -> dict[str, Any]:
    return {"devices": [_redacted(d) for d in load()]}


async def _generate(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    from alpi.host.network import (
        resolve_host_endpoint,
        resolve_host_pairing_name,
        resolve_host_tcp_port,
    )
    from alpi.home import _ROOT

    try:
        endpoint = resolve_host_endpoint(_ROOT)
    except Exception:  # noqa: BLE001
        endpoint = None
    if endpoint is None:
        from alpi.host.network import diagnose_bind_ip

        diag = diagnose_bind_ip()
        bits = [f"{k}={v}" for k, v in diag.items() if v is not None]
        raise host_server.HandlerError(
            -32010,
            "no-advertised-host",
            data={
                "detail": "Cannot pair — no Tailscale or LAN address detected.",
                "diagnosis": diag,
                "summary": " · ".join(bits) or "nothing detected",
            },
        )

    label = str((params or {}).get("label") or "")
    row = add(label)
    host, scope = endpoint
    return {
        "token": row["token"],
        "label": row["label"],
        "created": row["created"],
        "host": host,
        "scope": scope,
        "port": resolve_host_tcp_port(_ROOT),
        "pairing_name": resolve_host_pairing_name(_ROOT),
    }


async def _revoke(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    token_id = str((params or {}).get("token_id") or "")
    if not token_id:
        raise host_server.HandlerError(
            -32602, "invalid-params", data={"detail": "token_id required"},
        )
    target = next((d for d in load() if (d["token"] or "")[-8:] == token_id), None)
    if target is None:
        raise host_server.HandlerError(
            -32004, "not-found",
            data={"detail": f"no device matching token_id {token_id!r}"},
        )
    revoke(target["token"])
    return {"ok": True}


async def _rename(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    token_id = str((params or {}).get("token_id") or "")
    label = str((params or {}).get("label") or "")
    if not token_id:
        raise host_server.HandlerError(
            -32602, "invalid-params", data={"detail": "token_id required"},
        )
    target = next((d for d in load() if (d["token"] or "")[-8:] == token_id), None)
    if target is None:
        raise host_server.HandlerError(
            -32004, "not-found",
            data={"detail": f"no device matching token_id {token_id!r}"},
        )
    rename(target["token"], label)
    return {"ok": True}


__all__ = [
    "register", "load", "save", "is_valid", "touch", "add", "revoke", "rename",
]
