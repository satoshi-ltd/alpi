from __future__ import annotations

import contextlib
import hashlib
import hmac
import os
import re
import secrets
import sys
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from alpi.host import server as host_server
from alpi.host.connection_context import ConnectionContext

if sys.platform == "win32":
    import msvcrt
    _fcntl = None
else:
    import fcntl as _fcntl
    msvcrt = None


SCHEMA_VERSION = 2
PAIRING_TTL_SECONDS = 10 * 60
PAIRING_HISTORY_RETENTION_SECONDS = 7 * 24 * 60 * 60
PAIRING_HISTORY_LIMIT = 50
_VALID_ROLES = frozenset({"member", "admin"})
_VALID_STATUSES = frozenset({"active", "disabled", "deleted"})
_VALID_CLIENTS = frozenset({"desktop", "mobile", "unknown"})
_SAFE_PROFILE = re.compile(r"^[A-Za-z0-9_-]+$")
_CORRUPT_SCOPE = "<corrupt>"
_cache_lock = threading.Lock()
_cached: dict[str, Any] | None = None
_cached_path: str | None = None
_cached_identity: tuple[str, int, int, int] | None = None
_failed_identity: tuple[str, int, int, int] | None = None


class StoreUnavailable(Exception):
    pass


class PairingExchangeError(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class AuthResult:
    valid: bool
    role: str = ""
    profile_scope: tuple[str, ...] = ()
    connection_id: str = ""
    device_id: str = ""
    reason: str = ""

    @property
    def context(self) -> ConnectionContext:
        return ConnectionContext(
            connection_id=self.connection_id,
            device_id=self.device_id or None,
            source="remote",
            role=self.role or "member",
        )


def _root() -> Path:
    from alpi.home import _ROOT
    return _ROOT


def store_path() -> Path:
    return _root() / "host" / "connections.yaml"


def legacy_store_path() -> Path:
    return _root() / "host" / "devices.yaml"


def _lock_path() -> Path:
    return _root() / "host" / "connections.lock"


@contextlib.contextmanager
def _locked() -> Iterator[None]:
    lp = _lock_path()
    lp.parent.mkdir(parents=True, exist_ok=True)
    f = open(lp, "w")  # noqa: SIM115 — held for the critical section
    try:
        if sys.platform == "win32":
            msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
        else:
            _fcntl.flock(f.fileno(), _fcntl.LOCK_EX)
        yield
    finally:
        try:
            if sys.platform == "win32":
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                _fcntl.flock(f.fileno(), _fcntl.LOCK_UN)
        finally:
            f.close()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(8)}"


def _tokens_match(stored: str, presented: str) -> bool:
    if not stored or not presented:
        return False
    try:
        return hmac.compare_digest(stored.encode(), presented.encode())
    except (AttributeError, UnicodeError):
        return False


def _role(value: Any) -> str:
    value = str(value or "").strip().lower()
    return value if value in _VALID_ROLES else "member"


def _status(value: Any) -> str:
    value = str(value or "active").strip().lower()
    return value if value in _VALID_STATUSES else "disabled"


def _scope(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        return [_CORRUPT_SCOPE]
    out: list[str] = []
    for entry in value:
        name = str(entry or "").strip()
        if name and _SAFE_PROFILE.match(name) and name not in out:
            out.append(name)
    if value and not out:
        return [_CORRUPT_SCOPE]
    return out


def validate_profiles(value: Any) -> list[str]:
    if not isinstance(value, list):
        raise host_server.HandlerError(
            -32602, "invalid-params", data={"detail": "profiles must be a list"},
        )
    out: list[str] = []
    for entry in value:
        if not isinstance(entry, str) or not entry.strip() or not _SAFE_PROFILE.match(entry.strip()):
            raise host_server.HandlerError(
                -32602, "invalid-params", data={"detail": f"invalid profile name: {entry!r}"},
            )
        name = entry.strip()
        if name not in out:
            out.append(name)
    return out


def _normalise_device(row: Any, fallback_label: str = "") -> dict[str, Any] | None:
    if not isinstance(row, dict):
        return None
    token = str(row.get("token") or "")
    token_id = str(row.get("token_id") or (token[-8:] if token else ""))
    if not token and not token_id:
        return None
    client = str(row.get("client") or "unknown").strip().lower()
    return {
        "id": str(row.get("id") or _new_id("dev")),
        "token": token,
        "token_id": token_id,
        "name": str(row.get("name") or fallback_label or "").strip(),
        "client": client if client in _VALID_CLIENTS else "unknown",
        "app_version": str(row.get("app_version") or "").strip(),
        "created": int(row.get("created") or time.time()),
        "last_seen": int(row["last_seen"]) if row.get("last_seen") else None,
        "status": _status(row.get("status")),
    }


def _normalise_pairing(row: Any) -> dict[str, Any] | None:
    if not isinstance(row, dict):
        return None
    secret_hash = str(row.get("secret_hash") or "")
    if not secret_hash:
        return None
    status = str(row.get("status") or "pending")
    if status not in {"pending", "consumed", "expired", "cancelled"}:
        status = "cancelled"
    return {
        "id": str(row.get("id") or _new_id("pair")),
        "secret_hash": secret_hash,
        "created": int(row.get("created") or time.time()),
        "expires_at": int(row.get("expires_at") or 0),
        "status": status,
        "consumed_at": int(row["consumed_at"]) if row.get("consumed_at") else None,
        "device_id": str(row.get("device_id") or ""),
    }


def _prune_pairings(pairings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    now = int(time.time())
    pending: list[dict[str, Any]] = []
    history: list[dict[str, Any]] = []
    for pairing in pairings:
        if pairing["status"] == "pending" and pairing["expires_at"] > now:
            pending.append(pairing)
            continue
        if pairing["status"] == "pending":
            pairing["status"] = "expired"
        terminal_at = int(pairing.get("consumed_at") or pairing.get("created") or 0)
        if terminal_at >= now - PAIRING_HISTORY_RETENTION_SECONDS:
            history.append(pairing)
    history.sort(key=lambda pairing: int(pairing.get("created") or 0), reverse=True)
    return pending + history[:PAIRING_HISTORY_LIMIT]


def _normalise_connection(row: Any) -> dict[str, Any] | None:
    if not isinstance(row, dict):
        return None
    label = str(row.get("label") or "").strip() or "unnamed"
    devices = [
        device for raw in (row.get("devices") or [])
        if (device := _normalise_device(raw, label)) is not None
    ]
    pairings = _prune_pairings([
        pairing for raw in (row.get("pairings") or [])
        if (pairing := _normalise_pairing(raw)) is not None
    ])
    return {
        "id": str(row.get("id") or _new_id("conn")),
        "label": label,
        "created": int(row.get("created") or time.time()),
        "status": _status(row.get("status")),
        "role": _role(row.get("role")),
        "profile_scope": _scope(row.get("profile_scope")),
        "devices": devices,
        "pairings": pairings,
        "deleted_at": int(row["deleted_at"]) if row.get("deleted_at") else None,
    }


def _from_legacy(rows: Any) -> dict[str, Any]:
    if rows is None:
        rows = []
    if not isinstance(rows, list):
        raise StoreUnavailable("devices store is not a list")
    connections: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict) or not row.get("token"):
            continue
        label = str(row.get("label") or "").strip() or "unnamed"
        connection = _normalise_connection({
            "label": label,
            "created": row.get("created"),
            "role": row.get("role"),
            "profile_scope": row.get("profile_scope"),
            "devices": [{
                "token": row.get("token"),
                "name": label,
                "created": row.get("created"),
                "last_seen": row.get("last_seen"),
            }],
        })
        if connection:
            connections.append(connection)
    return {"version": SCHEMA_VERSION, "connections": connections}


def _normalise_store(raw: Any) -> dict[str, Any]:
    if isinstance(raw, list):
        return _from_legacy(raw)
    if not isinstance(raw, dict):
        raise StoreUnavailable("connections store is not an object")
    rows = raw.get("connections")
    if not isinstance(rows, list):
        raise StoreUnavailable("connections must be a list")
    return {
        "version": SCHEMA_VERSION,
        "connections": [
            connection for row in rows
            if (connection := _normalise_connection(row)) is not None
        ],
    }


def _read_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise StoreUnavailable(str(exc)) from exc


def _atomic_write(data: dict[str, Any]) -> None:
    path = store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{secrets.token_hex(4)}.tmp")
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
        os.chmod(path, 0o600)
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass
    invalidate_cache()


def _migrate_if_needed_inside_lock() -> None:
    target = store_path()
    legacy = legacy_store_path()
    if target.exists() or not legacy.exists():
        return
    from alpi.host import devices
    # lock order: connections.lock then devices.lock, never the reverse
    with devices._store_lock():
        if target.exists() or not legacy.exists():
            return
        data = _from_legacy(_read_yaml(legacy))
        _atomic_write(data)
        backup = legacy.with_name("devices.yaml.migrated")
        if backup.exists():
            backup = legacy.with_name(
                f"devices.yaml.migrated.{int(time.time())}.{secrets.token_hex(3)}",
            )
        os.replace(legacy, backup)


def _migrate_if_needed() -> None:
    if store_path().exists() or not legacy_store_path().exists():
        return
    with _locked():
        _migrate_if_needed_inside_lock()


def _read_store() -> dict[str, Any]:
    path = store_path()
    if not path.exists():
        return {"version": SCHEMA_VERSION, "connections": []}
    return _normalise_store(_read_yaml(path))


def _load_inside_lock() -> dict[str, Any]:
    _migrate_if_needed_inside_lock()
    return _read_store()


def load_store() -> dict[str, Any]:
    # lock-free read: _atomic_write's rename makes every read see a whole file; only writers/migration take the lock
    _migrate_if_needed()
    return _read_store()


def save_store(data: dict[str, Any]) -> None:
    with _locked():
        _atomic_write(_normalise_store(data))


def invalidate_cache() -> None:
    global _cached, _cached_path, _cached_identity, _failed_identity
    with _cache_lock:
        _cached = None
        _cached_path = None
        _cached_identity = None
        _failed_identity = None


def _store_identity() -> tuple[str, int, int, int] | None:
    for path in (store_path(), legacy_store_path()):
        try:
            stat = path.stat()
        except FileNotFoundError:
            continue
        except OSError:
            return (str(path), -1, -1, -1)
        return (str(path), stat.st_ino, stat.st_size, stat.st_mtime_ns)
    return None


def _cached_store() -> dict[str, Any]:
    global _cached, _cached_path, _cached_identity, _failed_identity
    path = str(store_path())
    identity = _store_identity()
    with _cache_lock:
        if (
            _cached is not None
            and _cached_path == path
            and identity in {_cached_identity, _failed_identity}
        ):
            return _cached
    try:
        fresh = load_store()
    except StoreUnavailable:
        with _cache_lock:
            if _cached_path == path and _cached is not None:
                _failed_identity = identity
                return _cached
            _cached = {"version": SCHEMA_VERSION, "connections": []}
            _cached_path = path
            _cached_identity = None
            _failed_identity = identity
            return _cached
    identity = _store_identity()
    with _cache_lock:
        _cached = fresh
        _cached_path = path
        _cached_identity = identity
        _failed_identity = None
    return fresh


def load_auth_store() -> dict[str, Any]:
    return _cached_store()


def list_connections(*, include_deleted: bool = False) -> list[dict[str, Any]]:
    rows = load_store()["connections"]
    return [row for row in rows if include_deleted or row["status"] != "deleted"]


def _device_payload(device: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": device["id"],
        "token_id": device.get("token_id") or str(device.get("token") or "")[-8:],
        "name": device.get("name") or "",
        "client": device.get("client") or "unknown",
        "app_version": device.get("app_version") or "",
        "created": device.get("created") or 0,
        "last_seen": device.get("last_seen"),
        "status": device.get("status") or "active",
    }


def public_connection(row: dict[str, Any]) -> dict[str, Any]:
    devices = [
        _device_payload(device)
        for device in row.get("devices") or []
        if device.get("status") != "deleted"
    ]
    last_seen = max((int(d.get("last_seen") or 0) for d in devices), default=0) or None
    return {
        "id": row["id"],
        "label": row.get("label") or "",
        "created": row.get("created") or 0,
        "last_seen": last_seen,
        "status": row.get("status") or "active",
        "role": row.get("role") or "member",
        "profile_scope": list(row.get("profile_scope") or []),
        "devices": devices,
    }


def _public_pairing(pairing: dict[str, Any]) -> dict[str, Any]:
    status = pairing.get("status") or "cancelled"
    if status == "pending" and int(pairing.get("expires_at") or 0) <= int(time.time()):
        status = "expired"
    return {
        "id": pairing["id"],
        "created": pairing.get("created") or 0,
        "expires_at": pairing.get("expires_at") or 0,
        "status": status,
        "consumed_at": pairing.get("consumed_at"),
        "device_id": pairing.get("device_id") or "",
    }


def _new_pairing(now: int) -> tuple[dict[str, Any], dict[str, Any]]:
    secret = secrets.token_urlsafe(32)
    stored = {
        "id": _new_id("pair"),
        "secret_hash": hashlib.sha256(secret.encode()).hexdigest(),
        "created": now,
        "expires_at": now + PAIRING_TTL_SECONDS,
        "status": "pending",
        "consumed_at": None,
        "device_id": "",
    }
    return stored, {**_public_pairing(stored), "token": secret}


def create_pairing_connection(
    label: str, *, role: str = "member", profile_scope: list[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    with _locked():
        data = _load_inside_lock()
        now = int(time.time())
        stored_pairing, pairing = _new_pairing(now)
        connection = _normalise_connection({
            "id": _new_id("conn"),
            "label": (label or "").strip() or "pending",
            "created": now,
            "status": "active",
            "role": role,
            "profile_scope": [] if _role(role) == "admin" else list(profile_scope or []),
            "devices": [],
            "pairings": [stored_pairing],
        })
        data["connections"].append(connection)
        _atomic_write(data)
        return connection, pairing


def create_device_pairing(connection_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    with _locked():
        data = _load_inside_lock()
        connection = next(
            (c for c in data["connections"] if c["id"] == connection_id and c["status"] != "deleted"),
            None,
        )
        if connection is None:
            raise KeyError(connection_id)
        stored_pairing, pairing = _new_pairing(int(time.time()))
        connection["pairings"].append(stored_pairing)
        _atomic_write(data)
        return connection, pairing


def exchange_pairing(
    pairing_token: str, *, client: str, name: str, app_version: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not pairing_token:
        raise PairingExchangeError("pairing-invalid")
    presented_hash = hashlib.sha256(pairing_token.encode()).hexdigest()
    if not any(
        _tokens_match(pairing.get("secret_hash", ""), presented_hash)
        for connection in _cached_store()["connections"]
        for pairing in connection.get("pairings") or []
    ):
        raise PairingExchangeError("pairing-invalid")
    now = int(time.time())
    with _locked():
        data = _load_inside_lock()
        for connection in data["connections"]:
            for pairing in connection.get("pairings") or []:
                if not _tokens_match(pairing.get("secret_hash", ""), presented_hash):
                    continue
                status = pairing.get("status") or "cancelled"
                if status == "pending" and int(pairing.get("expires_at") or 0) <= now:
                    pairing["status"] = "expired"
                    if not connection["devices"] and not any(
                        candidate["status"] == "pending"
                        for candidate in connection.get("pairings") or []
                    ):
                        _mark_connection_deleted(connection)
                    _atomic_write(data)
                    raise PairingExchangeError("pairing-expired")
                if status == "expired":
                    if connection["status"] != "deleted" and not connection["devices"] and not any(
                        candidate["status"] == "pending"
                        for candidate in connection.get("pairings") or []
                    ):
                        _mark_connection_deleted(connection)
                        _atomic_write(data)
                    raise PairingExchangeError("pairing-expired")
                if status == "consumed":
                    raise PairingExchangeError("pairing-used")
                if status != "pending" or connection.get("status") != "active":
                    raise PairingExchangeError("pairing-invalid")
                clean_client = client if client in _VALID_CLIENTS else "unknown"
                device = _normalise_device({
                    "id": _new_id("dev"),
                    "token": secrets.token_urlsafe(32),
                    "name": name.strip()[:128],
                    "client": clean_client,
                    "app_version": app_version.strip()[:64],
                    "created": now,
                    "status": "active",
                }, connection.get("label") or "")
                connection["devices"].append(device)
                pairing["status"] = "consumed"
                pairing["consumed_at"] = now
                pairing["device_id"] = device["id"]
                _atomic_write(data)
                return connection, device
    raise PairingExchangeError("pairing-invalid")


def pairing_status(connection_id: str, pairing_id: str) -> dict[str, Any] | None:
    with _locked():
        data = _load_inside_lock()
        connection = next((c for c in data["connections"] if c["id"] == connection_id), None)
        if connection is None:
            return None
        pairing = next((p for p in connection.get("pairings") or [] if p["id"] == pairing_id), None)
        if pairing is None:
            return None
        changed = False
        if pairing["status"] == "pending" and pairing["expires_at"] <= int(time.time()):
            pairing["status"] = "expired"
            changed = True
        if pairing["status"] == "expired" and connection["status"] != "deleted" \
                and not connection["devices"] and not any(
                    candidate["status"] == "pending"
                    for candidate in connection.get("pairings") or []
                ):
            _mark_connection_deleted(connection)
            changed = True
        if changed:
            _atomic_write(data)
        return _public_pairing(pairing)


def cancel_pairing(connection_id: str, pairing_id: str) -> bool:
    with _locked():
        data = _load_inside_lock()
        connection = next((c for c in data["connections"] if c["id"] == connection_id), None)
        if connection is None:
            return False
        pairing = next((p for p in connection.get("pairings") or [] if p["id"] == pairing_id), None)
        if pairing is None or pairing["status"] != "pending":
            return False
        pairing["status"] = "cancelled"
        if not connection["devices"] and not any(
            p["status"] == "pending" for p in connection.get("pairings") or []
        ):
            _mark_connection_deleted(connection)
        _atomic_write(data)
        return True


def create_connection(
    label: str, *, role: str = "member", profile_scope: list[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    with _locked():
        data = _load_inside_lock()
        now = int(time.time())
        device = _normalise_device({
            "id": _new_id("dev"),
            "token": secrets.token_urlsafe(24),
            "created": now,
            "status": "active",
        })
        connection = _normalise_connection({
            "id": _new_id("conn"),
            "label": (label or "").strip() or "pending",
            "created": now,
            "status": "active",
            "role": role,
            "profile_scope": [] if _role(role) == "admin" else list(profile_scope or []),
            "devices": [device],
        })
        data["connections"].append(connection)
        _atomic_write(data)
        return connection, device


def add_device(connection_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    with _locked():
        data = _load_inside_lock()
        connection = next(
            (c for c in data["connections"] if c["id"] == connection_id and c["status"] != "deleted"),
            None,
        )
        if connection is None:
            raise KeyError(connection_id)
        device = _normalise_device({
            "id": _new_id("dev"),
            "token": secrets.token_urlsafe(24),
            "created": int(time.time()),
        })
        connection["devices"].append(device)
        _atomic_write(data)
        return connection, device


def update_connection(
    connection_id: str, *, label: str | None = None, role: str | None = None,
    profile_scope: list[str] | None = None, status: str | None = None,
) -> bool:
    with _locked():
        clean_label = None
        if label is not None:
            clean_label = label.strip()
            if not clean_label:
                return False
        data = _load_inside_lock()
        row = next((c for c in data["connections"] if c["id"] == connection_id), None)
        if row is None:
            return False
        if clean_label is not None:
            row["label"] = clean_label
        if role is not None:
            if role not in _VALID_ROLES:
                return False
            row["role"] = role
            if role == "admin":
                row["profile_scope"] = []
        if profile_scope is not None and row["role"] != "admin":
            row["profile_scope"] = list(profile_scope)
        if status is not None:
            if status not in {"active", "disabled"}:
                return False
            row["status"] = status
        _atomic_write(data)
        return True


def _mark_device_deleted(device: dict[str, Any]) -> None:
    device["token_id"] = device.get("token_id") or str(device.get("token") or "")[-8:]
    device["token"] = ""
    device["status"] = "deleted"


def _mark_connection_deleted(connection: dict[str, Any]) -> None:
    connection["status"] = "deleted"
    connection["deleted_at"] = int(time.time())
    for device in connection["devices"]:
        _mark_device_deleted(device)


def delete_connection(connection_id: str) -> bool:
    with _locked():
        data = _load_inside_lock()
        row = next((c for c in data["connections"] if c["id"] == connection_id), None)
        if row is None:
            return False
        _mark_connection_deleted(row)
        _atomic_write(data)
        return True


def revoke_device(connection_id: str, device_id: str) -> bool:
    with _locked():
        data = _load_inside_lock()
        row = next((c for c in data["connections"] if c["id"] == connection_id), None)
        if row is None:
            return False
        device = next((d for d in row["devices"] if d["id"] == device_id), None)
        if device is None:
            return False
        _mark_device_deleted(device)
        _atomic_write(data)
        return True


def revoke_by_token_id(token_id: str) -> bool:
    with _locked():
        data = _load_inside_lock()
        for connection in data["connections"]:
            for device in connection["devices"]:
                current = device.get("token_id") or str(device.get("token") or "")[-8:]
                if current != token_id:
                    continue
                active = [d for d in connection["devices"] if d["status"] != "deleted"]
                if not device.get("last_seen") and len(active) == 1:
                    _mark_connection_deleted(connection)
                else:
                    _mark_device_deleted(device)
                _atomic_write(data)
                return True
        return False


def register_device(token: str, *, client: str, name: str, app_version: str) -> bool:
    client = client if client in _VALID_CLIENTS else "unknown"
    clean_name = name.strip()
    clean_version = app_version.strip()
    with _locked():
        data = _load_inside_lock()
        for connection in data["connections"]:
            for device in connection["devices"]:
                if _tokens_match(str(device.get("token") or ""), token):
                    changed = device.get("client") != client
                    if changed:
                        device["client"] = client
                    if clean_name and device.get("name") != clean_name:
                        device["name"] = clean_name
                        changed = True
                    if clean_version and device.get("app_version") != clean_version:
                        device["app_version"] = clean_version
                        changed = True
                    if changed:
                        _atomic_write(data)
                    return True
    return False


def authenticate(token: str, min_interval: float = 60.0) -> AuthResult:
    if not token:
        return AuthResult(False)
    data = _cached_store()
    now = int(time.time())
    for connection in data["connections"]:
        for device in connection["devices"]:
            if device["status"] != "active" or not _tokens_match(device.get("token", ""), token):
                continue
            if connection["status"] == "disabled":
                return AuthResult(
                    False,
                    connection_id=connection["id"],
                    device_id=device["id"],
                    reason="connection-disabled",
                )
            if connection["status"] != "active":
                continue
            result = AuthResult(
                True,
                connection["role"],
                tuple(connection["profile_scope"]),
                connection["id"],
                device["id"],
            )
            if now - int(device.get("last_seen") or 0) >= min_interval:
                _touch(token, now, min_interval)
            return result
    return AuthResult(False)


def _touch(token: str, now: int, min_interval: float) -> None:
    with _locked():
        data = _load_inside_lock()
        for connection in data["connections"]:
            for device in connection["devices"]:
                if _tokens_match(device.get("token", ""), token):
                    if now - int(device.get("last_seen") or 0) < min_interval:
                        return
                    device["last_seen"] = now
                    _atomic_write(data)
                    return


def _pairing_network() -> dict[str, Any]:
    from alpi.host.network import (
        classify_scope,
        resolve_host_endpoint,
        resolve_host_endpoints,
        resolve_host_pairing_name,
        resolve_host_tcp_port,
        pairing_unavailable_detail,
    )
    try:
        endpoints = resolve_host_endpoints(_root())
    except ValueError as exc:
        raise host_server.HandlerError(
            -32010, "invalid-advertised-endpoints", data={"detail": str(exc)},
        ) from exc
    if not endpoints:
        raise host_server.HandlerError(
            -32010, "no-advertised-host",
            data={"detail": pairing_unavailable_detail(_root())},
        )
    endpoint = resolve_host_endpoint(_root())
    legacy = {}
    if endpoint is not None:
        host, raw_scope = endpoint
        legacy = {
            "host": host,
            "scope": classify_scope(host, raw_scope),
            "is_override": raw_scope == "configured",
            "port": resolve_host_tcp_port(_root()),
        }
    return {
        **legacy,
        "url": endpoints[0]["url"],
        "endpoints": endpoints,
        "pairing_name": resolve_host_pairing_name(_root()),
    }


def _pairing_payload(
    connection: dict[str, Any], pairing: dict[str, Any], network: dict[str, Any],
) -> dict[str, Any]:
    return {
        "connection_id": connection["id"],
        "pairing_id": pairing["id"],
        "pairing_token": pairing["token"],
        "pairing_status": pairing["status"],
        "expires_at": pairing["expires_at"],
        "label": connection["label"],
        "role": connection["role"],
        "profile_scope": connection["profile_scope"],
        **network,
    }


def register(server: host_server.Server) -> None:
    server.register("host.connections.list", _list)
    server.register("host.connections.create", _create)
    server.register("host.connections.add_device", _add_device)
    server.register("host.connections.exchange_pairing", _exchange_pairing)
    server.register("host.connections.pairing_status", _pairing_status)
    server.register("host.connections.cancel_pairing", _cancel_pairing)
    server.register("host.connections.update", _update)
    server.register("host.connections.set_status", _set_status)
    server.register("host.connections.delete", _delete)
    server.register("host.connections.revoke_device", _revoke_device)
    server.register("host.connections.register_device", _register_device)
    server.register("host.devices.list", _legacy_list)
    server.register("host.devices.generate", _create)
    server.register("host.devices.revoke", _legacy_revoke)
    server.register("host.devices.rename", _legacy_rename)
    server.register("host.devices.promote", _legacy_promote)
    server.register("host.devices.demote", _legacy_demote)
    server.register("host.devices.set_profiles", _legacy_set_profiles)


async def _list(_params: dict[str, Any], _server: host_server.Server) -> dict[str, Any]:
    return {"connections": [public_connection(row) for row in list_connections()]}


async def _create(params: dict[str, Any], _server: host_server.Server) -> dict[str, Any]:
    label = str((params or {}).get("label") or "").strip()
    if not label:
        raise host_server.HandlerError(-32602, "invalid-params", data={"detail": "label required"})
    role = str((params or {}).get("role") or "member")
    if role not in _VALID_ROLES:
        raise host_server.HandlerError(-32602, "invalid-params", data={"detail": "invalid role"})
    profiles = validate_profiles((params or {}).get("profiles") or [])
    network = _pairing_network()
    connection, pairing = create_pairing_connection(label, role=role, profile_scope=profiles)
    return _pairing_payload(connection, pairing, network)


async def _add_device(params: dict[str, Any], _server: host_server.Server) -> dict[str, Any]:
    connection_id = str((params or {}).get("connection_id") or "")
    if not any(row["id"] == connection_id for row in list_connections()):
        raise host_server.HandlerError(-32004, "not-found", data={"detail": "connection not found"})
    network = _pairing_network()
    try:
        connection, pairing = create_device_pairing(connection_id)
    except KeyError:
        raise host_server.HandlerError(-32004, "not-found", data={"detail": "connection not found"})
    return _pairing_payload(connection, pairing, network)


async def _exchange_pairing(params: dict[str, Any], _server: host_server.Server) -> dict[str, Any]:
    from alpi.host.connection_context import current

    if current().source != "bootstrap":
        raise host_server.HandlerError(
            -32001, "forbidden", data={"detail": "pairing exchange is pre-authentication only"},
        )
    try:
        connection, device = exchange_pairing(
            str((params or {}).get("pairing_token") or ""),
            client=str((params or {}).get("client") or "unknown"),
            name=str((params or {}).get("name") or ""),
            app_version=str((params or {}).get("app_version") or ""),
        )
    except PairingExchangeError as exc:
        messages = {
            "pairing-expired": "pairing code expired",
            "pairing-used": "pairing code already used",
            "pairing-invalid": "pairing code invalid",
        }
        raise host_server.HandlerError(
            -32011, exc.reason, data={"detail": messages[exc.reason]},
        ) from exc
    return {
        "connection_id": connection["id"],
        "device_id": device["id"],
        "token": device["token"],
        "label": connection["label"],
        "role": connection["role"],
        "profile_scope": connection["profile_scope"],
    }


async def _pairing_status(params: dict[str, Any], _server: host_server.Server) -> dict[str, Any]:
    status = pairing_status(
        str((params or {}).get("connection_id") or ""),
        str((params or {}).get("pairing_id") or ""),
    )
    if status is None:
        raise host_server.HandlerError(-32004, "not-found", data={"detail": "pairing not found"})
    return status


async def _cancel_pairing(params: dict[str, Any], _server: host_server.Server) -> dict[str, Any]:
    existed = cancel_pairing(
        str((params or {}).get("connection_id") or ""),
        str((params or {}).get("pairing_id") or ""),
    )
    return {"ok": True, "existed": existed}


async def _update(params: dict[str, Any], _server: host_server.Server) -> dict[str, Any]:
    connection_id = str((params or {}).get("connection_id") or "")
    label = None
    if "label" in params:
        label = str(params.get("label") or "").strip()
        if not label:
            raise host_server.HandlerError(
                -32602, "invalid-params", data={"detail": "label required"},
            )
    role = params.get("role") if "role" in params else None
    if role is not None and role not in _VALID_ROLES:
        raise host_server.HandlerError(-32602, "invalid-params", data={"detail": "invalid role"})
    profiles = validate_profiles(params["profiles"]) if "profiles" in params else None
    ok = update_connection(
        connection_id,
        label=label,
        role=str(role) if role is not None else None,
        profile_scope=profiles,
    )
    if not ok:
        raise host_server.HandlerError(-32004, "not-found", data={"detail": "connection not found"})
    return {"ok": True}


async def _set_status(params: dict[str, Any], _server: host_server.Server) -> dict[str, Any]:
    connection_id = str((params or {}).get("connection_id") or "")
    status = str((params or {}).get("status") or "")
    if status not in {"active", "disabled"}:
        raise host_server.HandlerError(-32602, "invalid-params", data={"detail": "invalid status"})
    if not update_connection(connection_id, status=status):
        raise host_server.HandlerError(-32004, "not-found", data={"detail": "connection not found"})
    return {"ok": True, "status": status}


async def _delete(params: dict[str, Any], _server: host_server.Server) -> dict[str, Any]:
    return {"ok": True, "existed": delete_connection(str((params or {}).get("connection_id") or ""))}


async def _revoke_device(params: dict[str, Any], _server: host_server.Server) -> dict[str, Any]:
    existed = revoke_device(
        str((params or {}).get("connection_id") or ""),
        str((params or {}).get("device_id") or ""),
    )
    return {"ok": True, "existed": existed}


async def _register_device(params: dict[str, Any], _server: host_server.Server) -> dict[str, Any]:
    token = str((params or {}).get("auth_token") or "")
    ok = register_device(
        token,
        client=str((params or {}).get("client") or "unknown"),
        name=str((params or {}).get("name") or ""),
        app_version=str((params or {}).get("app_version") or ""),
    )
    return {"ok": ok}


def _find_token_id(token_id: str) -> tuple[dict[str, Any], dict[str, Any]] | None:
    for connection in list_connections(include_deleted=True):
        for device in connection["devices"]:
            current = device.get("token_id") or str(device.get("token") or "")[-8:]
            if current == token_id:
                return connection, device
    return None


async def _legacy_list(_params: dict[str, Any], _server: host_server.Server) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for connection in list_connections():
        for device in connection["devices"]:
            if device["status"] == "deleted":
                continue
            rows.append({
                "token_id": device.get("token_id") or str(device.get("token") or "")[-8:],
                "label": connection["label"],
                "created": device["created"],
                "last_seen": device["last_seen"],
                "role": connection["role"],
                "profile_scope": connection["profile_scope"],
            })
    return {"devices": rows}


async def _legacy_revoke(params: dict[str, Any], _server: host_server.Server) -> dict[str, Any]:
    return {"ok": True, "existed": revoke_by_token_id(str((params or {}).get("token_id") or ""))}


async def _legacy_rename(params: dict[str, Any], _server: host_server.Server) -> dict[str, Any]:
    found = _find_token_id(str((params or {}).get("token_id") or ""))
    if found is None:
        raise host_server.HandlerError(-32004, "not-found", data={"detail": "device not found"})
    connection, _device = found
    label = str((params or {}).get("label") or "").strip()
    if not label:
        raise host_server.HandlerError(-32602, "invalid-params", data={"detail": "label required"})
    update_connection(connection["id"], label=label)
    return {"ok": True}


async def _legacy_promote(params: dict[str, Any], _server: host_server.Server) -> dict[str, Any]:
    return await _legacy_role(params, "admin")


async def _legacy_demote(params: dict[str, Any], _server: host_server.Server) -> dict[str, Any]:
    return await _legacy_role(params, "member")


async def _legacy_role(params: dict[str, Any], role: str) -> dict[str, Any]:
    found = _find_token_id(str((params or {}).get("token_id") or ""))
    if found is None:
        raise host_server.HandlerError(-32004, "not-found", data={"detail": "device not found"})
    connection, _device = found
    update_connection(connection["id"], role=role)
    return {"ok": True, "role": role}


async def _legacy_set_profiles(params: dict[str, Any], _server: host_server.Server) -> dict[str, Any]:
    found = _find_token_id(str((params or {}).get("token_id") or ""))
    if found is None:
        raise host_server.HandlerError(-32004, "not-found", data={"detail": "device not found"})
    connection, _device = found
    if connection["role"] == "admin":
        raise host_server.HandlerError(-32001, "forbidden", data={"detail": "admin sees all profiles"})
    profiles = validate_profiles((params or {}).get("profiles"))
    update_connection(connection["id"], profile_scope=profiles)
    return {"ok": True, "profile_scope": profiles}
