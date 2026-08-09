from __future__ import annotations

import json
import logging
import os
import secrets
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from alpi.host.connection_context import ConnectionContext, current


log = logging.getLogger("alpi.host.admin_audit")
MAX_BYTES = 5_000_000
BACKUP_COUNT = 3
DEFAULT_LIMIT = 100
MAX_LIMIT = 500
DENIED_REPEAT_SECONDS = 60.0
MAX_FIELD_LENGTH = 160
MAX_RECORD_BYTES = 4_096

AUDITED_METHODS = frozenset({
    "host.approval.respond",
    "host.cleanup.apply",
    "host.config.set_field",
    "host.config.unset_field",
    "host.connections.add_device",
    "host.connections.cancel_pairing",
    "host.connections.create",
    "host.connections.delete",
    "host.connections.exchange_pairing",
    "host.connections.register_device",
    "host.connections.revoke_device",
    "host.connections.set_status",
    "host.connections.update",
    "host.daemon.restart",
    "host.daemon.update",
    "host.devices.demote",
    "host.devices.generate",
    "host.devices.promote",
    "host.devices.rename",
    "host.devices.revoke",
    "host.devices.set_profiles",
    "host.email.add",
    "host.email.gmail.exchange",
    "host.email.remove",
    "host.mcp.add",
    "host.mcp.remove",
    "host.network.restart_host_server",
    "host.network.set_advertised",
    "host.outputs.delete",
    "host.peers.add",
    "host.peers.pending_accept",
    "host.peers.pending_discard",
    "host.peers.remove",
    "host.profile.create",
    "host.profile.delete",
    "host.profile.memory_write",
    "host.providers.add_ollama",
    "host.providers.add_openrouter_model",
    "host.providers.remove_ollama",
    "host.providers.remove_openrouter_model",
    "host.providers.set_key",
    "host.providers.unset_key",
    "host.sandbox.network",
    "host.sandbox.set",
    "host.schedule.fire",
    "host.schedule.remove",
    "host.schedule.set_paused",
    "host.sessions.delete",
    "host.voice.set_auto_read",
    "host.voice.set_voice",
    "host.workgroup.action",
    "host.workgroup.add_member",
    "host.workgroup.create",
    "host.workgroup.kick",
    "host.workgroup.launch_recipe",
    "host.workgroup.remove",
    "host.workgroup.trigger",
    "host.workgroup.update",
})

_COMMON_TARGET_KEYS = ("profile",)
_TARGET_KEYS_BY_PREFIX = {
    "host.connections.": (
        "connection_id", "device_id", "pairing_id", "status", "role", "profiles", "name",
    ),
    "host.devices.": ("token_id", "role", "profiles"),
    "host.providers.": ("profile", "provider", "key", "model"),
    "host.peers.": ("profile", "peer_id", "id"),
    "host.profile.": ("profile",),
    "host.config.": ("profile", "key"),
    "host.mcp.": ("profile", "name"),
    "host.email.": ("profile", "account_id"),
    "host.sandbox.": ("profile",),
    "host.voice.": ("profile",),
    "host.schedule.": ("profile", "job_id", "id", "paused"),
    "host.workgroup.": (
        "profile", "wg_id", "member", "action", "pipeline", "name",
    ),
}
_TARGET_KEYS_BY_METHOD = {
    "host.approval.respond": ("profile", "request_id", "choice"),
    "host.cleanup.apply": ("profile",),
    "host.daemon.restart": (),
    "host.daemon.update": (),
    "host.network.restart_host_server": (),
    "host.network.set_advertised": ("name",),
    "host.outputs.delete": ("profile", "id"),
    "host.sessions.delete": ("profile",),
}
_write_lock = threading.Lock()
_denied_seen: dict[tuple[str, str, str, str], float] = {}


def audit_path(home: Path) -> Path:
    return home / "logs" / "admin-audit.jsonl"


def is_audited(method: str) -> bool:
    return method in AUDITED_METHODS


def _safe_text(value: Any) -> str:
    text = " ".join(str(value or "").split())
    encoded = text.encode("utf-8")
    if len(encoded) <= MAX_FIELD_LENGTH:
        return text
    return encoded[:MAX_FIELD_LENGTH].decode("utf-8", errors="ignore")


def _target_keys(method: str) -> tuple[str, ...]:
    exact = _TARGET_KEYS_BY_METHOD.get(method)
    if exact is not None:
        return exact
    for prefix, keys in _TARGET_KEYS_BY_PREFIX.items():
        if method.startswith(prefix):
            return keys
    return _COMMON_TARGET_KEYS


def _safe_target(
    method: str,
    params: dict[str, Any],
    response: dict[str, Any] | None,
    *,
    include_params: bool = True,
) -> dict[str, Any]:
    allowed = _target_keys(method)
    candidates = dict(params) if include_params else {}
    result = (response or {}).get("result")
    if isinstance(result, dict):
        for key in allowed:
            if key not in candidates and key in result:
                candidates[key] = result[key]
    target: dict[str, Any] = {}
    for key in allowed:
        value = candidates.get(key)
        if isinstance(value, str) and value:
            target[key] = _safe_text(value)
        elif key == "profiles" and isinstance(value, list):
            profiles = [_safe_text(item) for item in value[:8] if isinstance(item, str) and item]
            if profiles:
                target[key] = profiles
        elif key == "paused" and isinstance(value, bool):
            target[key] = value
    return target


def _identity_snapshot(
    context: ConnectionContext, target: dict[str, Any],
) -> tuple[str, str, str, str]:
    if context.connection_id == "host":
        actor_connection_label = "Local host"
        actor_device_name = ""
    else:
        actor_connection_label = ""
        actor_device_name = ""
    target_connection_label = ""
    target_device_name = ""
    try:
        from alpi.host.connections import load_auth_store, store_path

        if not store_path().exists():
            return (
                actor_connection_label,
                actor_device_name,
                target_connection_label,
                target_device_name,
            )
        rows = load_auth_store()["connections"]
        actor = next((row for row in rows if row["id"] == context.connection_id), None)
        if actor is not None:
            actor_connection_label = _safe_text(actor.get("label"))
            device = next(
                (row for row in actor.get("devices", []) if row["id"] == context.device_id),
                None,
            )
            if device is not None:
                actor_device_name = _safe_text(device.get("name"))
        target_connection_id = str(target.get("connection_id") or "")
        target_connection = next(
            (row for row in rows if row["id"] == target_connection_id),
            None,
        )
        if target_connection is not None:
            target_connection_label = _safe_text(target_connection.get("label"))
            target_device_id = str(target.get("device_id") or "")
            target_device = next(
                (
                    row for row in target_connection.get("devices", [])
                    if row["id"] == target_device_id
                ),
                None,
            )
            if target_device is not None:
                target_device_name = _safe_text(target_device.get("name"))
    except Exception:  # noqa: BLE001
        pass
    return (
        actor_connection_label,
        actor_device_name,
        target_connection_label,
        target_device_name,
    )


def _rotate(path: Path, incoming_bytes: int) -> None:
    try:
        size = path.stat().st_size
    except OSError:
        size = 0
    if size + incoming_bytes <= MAX_BYTES:
        return
    oldest = path.with_name(f"{path.name}.{BACKUP_COUNT}")
    try:
        oldest.unlink()
    except FileNotFoundError:
        pass
    for index in range(BACKUP_COUNT - 1, 0, -1):
        source = path.with_name(f"{path.name}.{index}")
        target = path.with_name(f"{path.name}.{index + 1}")
        try:
            os.replace(source, target)
        except FileNotFoundError:
            pass
    try:
        os.replace(path, path.with_name(f"{path.name}.1"))
    except FileNotFoundError:
        pass


def _append(home: Path, record: dict[str, Any]) -> bool:
    encoded = (json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
    if len(encoded) > MAX_RECORD_BYTES:
        record = {**record, "target": {}, "target_truncated": True}
        encoded = (json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
    if len(encoded) > MAX_RECORD_BYTES:
        log.error("administrative audit event exceeds the hard record limit")
        return False
    path = audit_path(home)
    try:
        with _write_lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            _rotate(path, len(encoded))
            fd = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
            try:
                pending = memoryview(encoded)
                while pending:
                    written = os.write(fd, pending)
                    if written <= 0:
                        raise OSError("administrative audit write made no progress")
                    pending = pending[written:]
                if hasattr(os, "fchmod"):
                    os.fchmod(fd, 0o600)
            finally:
                os.close(fd)
    except OSError as exc:
        log.error("cannot append administrative audit event: %s", exc)
        return False
    return True


def _record(
    home: Path,
    method: str,
    params: dict[str, Any],
    response: dict[str, Any] | None,
    *,
    context: ConnectionContext,
    forced_result: str | None = None,
    allow_unlisted: bool = False,
) -> bool:
    if method not in AUDITED_METHODS and not allow_unlisted:
        return False
    target = _safe_target(
        method,
        params,
        response,
        include_params=context.source != "bootstrap",
    )
    if method == "host.connections.exchange_pairing" and response:
        result_payload = response.get("result")
        if isinstance(result_payload, dict):
            context = ConnectionContext(
                connection_id=_safe_text(result_payload.get("connection_id")) or "bootstrap",
                device_id=_safe_text(result_payload.get("device_id")) or None,
                source="bootstrap",
                role=_safe_text(result_payload.get("role")) or "member",
            )
    error = (response or {}).get("error")
    if forced_result:
        result = forced_result
    elif isinstance(error, dict):
        result = "denied" if error.get("code") == -32001 else "error"
    elif isinstance((response or {}).get("result"), dict) and response["result"].get("ok") is False:
        result = "error"
    else:
        result = "success"
    actor_label, device_name, target_label, target_device_name = _identity_snapshot(
        context, target,
    )
    record: dict[str, Any] = {
        "id": f"audit_{secrets.token_hex(8)}",
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace(
            "+00:00", "Z",
        ),
        "connection_id": _safe_text(context.connection_id) or "host",
        "connection_label": actor_label,
        "device_id": _safe_text(context.device_id),
        "device_name": device_name,
        "source": _safe_text(context.source),
        "role": _safe_text(context.role),
        "method": _safe_text(method) or "unknown",
        "target": target,
        "target_connection_label": target_label,
        "target_device_name": target_device_name,
        "result": result,
    }
    if isinstance(error, dict):
        record["error_code"] = error.get("code")
        record["error"] = _safe_text(error.get("message"))
    return _append(home, record)


def record_request(
    home: Path, method: str, params: dict[str, Any], response: dict[str, Any] | None,
) -> bool:
    try:
        context = current()
        if context.source == "bootstrap" and isinstance((response or {}).get("error"), dict):
            if not _allow_rate_limited(home, "bootstrap", "", method):
                return False
        if method == "host.connections.register_device":
            if not _allow_rate_limited(
                home, context.connection_id, context.device_id or "", method,
            ):
                return False
        return _record(home, method, params, response, context=context)
    except Exception:  # noqa: BLE001
        log.exception("cannot append administrative audit event for %s", method)
        return False


def record_denied(
    home: Path, method: str, params: dict[str, Any], context: ConnectionContext,
) -> bool:
    try:
        return _record_denied(home, method, params, context)
    except Exception:  # noqa: BLE001
        log.exception("cannot append denied administrative audit event for %s", method)
        return False


def record_auth_failed(
    home: Path, method: str, context: ConnectionContext,
) -> bool:
    try:
        known_actor = context.connection_id not in {"", "unauthenticated"}
        scope = context.connection_id if known_actor else "unauthenticated"
        device = context.device_id if known_actor else ""
        rate_method = method if known_actor else "*"
        if not _allow_rate_limited(home, scope, device or "", rate_method):
            return False
        response = {"error": {"code": -32000, "message": "auth-failed"}}
        return _record(
            home,
            method,
            {},
            response,
            context=context,
            forced_result="denied",
            allow_unlisted=True,
        )
    except Exception:  # noqa: BLE001
        log.exception("cannot append authentication failure audit event for %s", method)
        return False


def _allow_rate_limited(home: Path, connection_id: str, device_id: str, method: str) -> bool:
    now = time.monotonic()
    key = (str(home), connection_id, device_id, method)
    with _write_lock:
        previous = _denied_seen.get(key, 0.0)
        if now - previous < DENIED_REPEAT_SECONDS:
            return False
        _denied_seen[key] = now
        if len(_denied_seen) > 2_000:
            cutoff = now - DENIED_REPEAT_SECONDS
            for stale in [k for k, seen in _denied_seen.items() if seen < cutoff]:
                _denied_seen.pop(stale, None)
    return True


def _record_denied(
    home: Path, method: str, params: dict[str, Any], context: ConnectionContext,
) -> bool:
    if method not in AUDITED_METHODS:
        return False
    if not _allow_rate_limited(
        home, context.connection_id, context.device_id or "", method,
    ):
        return False
    response = {"error": {"code": -32001, "message": "forbidden"}}
    return _record(
        home, method, params, response, context=context, forced_result="denied",
    )


def _paths_newest_first(home: Path) -> list[Path]:
    path = audit_path(home)
    return [path, *(path.with_name(f"{path.name}.{index}") for index in range(1, BACKUP_COUNT + 1))]


def _matches(
    record: dict[str, Any], *, connection_id: str, device_id: str, result: str,
) -> bool:
    target = record.get("target") if isinstance(record.get("target"), dict) else {}
    if connection_id and connection_id not in {
        str(record.get("connection_id") or ""), str(target.get("connection_id") or ""),
    }:
        return False
    if device_id and device_id not in {
        str(record.get("device_id") or ""), str(target.get("device_id") or ""),
    }:
        return False
    return not result or record.get("result") == result


def list_entries(
    home: Path,
    *,
    limit: int = DEFAULT_LIMIT,
    cursor: str = "",
    connection_id: str = "",
    device_id: str = "",
    result: str = "",
) -> dict[str, Any]:
    limit = max(1, min(int(limit), MAX_LIMIT))
    if result not in {"", "success", "error", "denied"}:
        result = ""
    entries: list[dict[str, Any]] = []
    cursor_found = not cursor
    has_more = False
    for path in _paths_newest_first(home):
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line in reversed(lines):
            try:
                record = json.loads(line)
            except (json.JSONDecodeError, TypeError):
                continue
            if not isinstance(record, dict):
                continue
            if not cursor_found:
                if record.get("id") == cursor:
                    cursor_found = True
                continue
            if not _matches(
                record,
                connection_id=connection_id,
                device_id=device_id,
                result=result,
            ):
                continue
            if len(entries) >= limit:
                has_more = True
                break
            entries.append(record)
        if has_more:
            break
    return {
        "entries": entries,
        "next_cursor": entries[-1]["id"] if has_more and entries else "",
    }


def register(server: Any) -> None:
    server.register("host.audit.list", _list)


async def _list(params: dict[str, Any], server: Any) -> dict[str, Any]:
    import asyncio

    try:
        limit = int((params or {}).get("limit") or DEFAULT_LIMIT)
    except (TypeError, ValueError):
        limit = DEFAULT_LIMIT
    return await asyncio.to_thread(
        list_entries,
        server.home,
        limit=limit,
        cursor=_safe_text((params or {}).get("cursor")),
        connection_id=_safe_text((params or {}).get("connection_id")),
        device_id=_safe_text((params or {}).get("device_id")),
        result=_safe_text((params or {}).get("result")),
    )


__all__ = [
    "AUDITED_METHODS",
    "audit_path",
    "is_audited",
    "list_entries",
    "record_denied",
    "record_auth_failed",
    "record_request",
    "register",
]
