from __future__ import annotations

import os
import secrets
import threading
import time
from pathlib import Path
from typing import Any

import yaml

from alpi.host import server as host_server


_VALID_ROLES = frozenset({"member", "admin"})


def _normalise_role(value: Any) -> str:
    """Anything not in ``_VALID_ROLES`` collapses to ``"member"`` — least-privilege fallback for entries that predate the field on disk."""
    role = str(value or "").strip().lower()
    return role if role in _VALID_ROLES else "member"


def register(server: host_server.Server) -> None:
    server.register("host.devices.list", _list)
    server.register("host.devices.generate", _generate)
    server.register("host.devices.revoke", _revoke)
    server.register("host.devices.rename", _rename)
    server.register("host.devices.promote", _promote)
    server.register("host.devices.demote", _demote)


def _store_path() -> Path:
    from alpi.home import _ROOT
    return _ROOT / "host" / "devices.yaml"


def _guard_pytest_isolation(path: Path) -> None:
    """Refuse to write the real developer store from inside a pytest run. We had a regression where a test fixture forgot to monkeypatch ``alpi.home._ROOT`` and the parametrized case silently appended `seed` rows to ``~/.alpi/host/devices.yaml`` on every test run. This guard is cheap and catches the next slip in the same shape."""
    if "PYTEST_CURRENT_TEST" not in os.environ:
        return
    try:
        from alpi import home as home_mod
        root = home_mod._ROOT
    except Exception:  # noqa: BLE001
        return
    # Anything under /tmp / pytest's tmp_path / a non-default home is fine.
    real_default = Path.home() / ".alpi"
    try:
        if root.resolve() == real_default.resolve():
            raise RuntimeError(
                "devices.save() refused to write the real ~/.alpi store from inside "
                "a pytest run — fixture forgot to monkeypatch alpi.home._ROOT. "
                "Tests must either use the `short_tmp` fixture or call "
                "`monkeypatch.setattr(home_mod, '_ROOT', tmp_path)`."
            )
    except OSError:
        pass


# 5s in-process cache so per-RPC token validation doesn't hit disk on every call. Writes invalidate.
_cache_lock = threading.Lock()
_cached: list[dict[str, Any]] | None = None
_cached_at: float = 0.0
_CACHE_TTL_S = 5.0


def _invalidate_cache() -> None:
    global _cached, _cached_at
    with _cache_lock:
        _cached = None
        _cached_at = 0.0


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
            "role": _normalise_role(row.get("role")),
        })
    return out


def _load_cached() -> list[dict[str, Any]]:
    global _cached, _cached_at
    with _cache_lock:
        if _cached is not None and (time.time() - _cached_at) < _CACHE_TTL_S:
            return [dict(d) for d in _cached]
    fresh = load()
    with _cache_lock:
        _cached = [dict(d) for d in fresh]
        _cached_at = time.time()
    return fresh


def save(devices: list[dict[str, Any]]) -> None:
    """Atomic write via tmp+rename so a crashed daemon never leaves a half-written devices.yaml that would lock out every paired client."""
    path = _store_path()
    _guard_pytest_isolation(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    text = yaml.safe_dump(devices, sort_keys=False, allow_unicode=True)
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
    except Exception:
        try: tmp.unlink()
        except OSError: pass
        raise
    os.replace(str(tmp), str(path))
    _invalidate_cache()


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


# Validate + record last_seen in one call; writes only when last_seen is stale to keep auth I/O bounded.
def validate_and_touch(token: str, min_interval: float = 60.0) -> bool:
    return validate_and_lookup_role(token, min_interval=min_interval)[0]


def validate_and_lookup_role(
    token: str, min_interval: float = 60.0,
) -> tuple[bool, str]:
    """Returns ``(valid, role)``; empty role string when invalid. Fail-closed for every WS path: an empty/missing store still rejects every token. The local Unix socket bootstraps the first device by bypassing token auth entirely (``require_token=False``) — no remote needs the empty-store backdoor."""
    if not token:
        return False, ""
    devices = _load_cached()
    if not devices:
        return False, ""
    now = int(time.time())
    match_idx = -1
    for i, d in enumerate(devices):
        if d["token"] == token:
            match_idx = i
            break
    if match_idx < 0:
        return False, ""
    role = _normalise_role(devices[match_idx].get("role"))
    last = devices[match_idx].get("last_seen") or 0
    if now - int(last) >= min_interval:
        # Reload fresh to avoid writing a stale snapshot when the cache is older than the file.
        fresh = load()
        for d in fresh:
            if d["token"] == token:
                d["last_seen"] = now
                break
        save(fresh)
    return True, role


def add(label: str = "", role: str = "member") -> dict[str, Any]:
    devices = load()
    # 24 bytes urlsafe = 32 chars, 192 bits entropy — keeps the QR small.
    row = {
        "token": secrets.token_urlsafe(24),
        "label": (label or "").strip() or "pending",
        "created": int(time.time()),
        "last_seen": None,
        "role": _normalise_role(role),
    }
    devices.append(row)
    save(devices)
    return row


def set_role(token: str, role: str) -> bool:
    """Flip role on an existing device; unknown roles are silently rejected to avoid widening the enum on disk."""
    if role not in _VALID_ROLES:
        return False
    devices = load()
    changed = False
    for d in devices:
        if d["token"] == token:
            if d.get("role") != role:
                d["role"] = role
                changed = True
            break
    if changed:
        save(devices)
    return changed


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
        "role": _normalise_role(d.get("role")),
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
    role = _normalise_role((params or {}).get("role"))
    row = add(label, role=role)
    host, raw_scope = endpoint
    from alpi.host.network import classify_scope
    return {
        "token": row["token"],
        "label": row["label"],
        "created": row["created"],
        "role": row["role"],
        "host": host,
        "scope": classify_scope(host, raw_scope),
        "is_override": raw_scope == "configured",
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


async def _promote(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    return await _set_role_handler(params, "admin")


async def _demote(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    return await _set_role_handler(params, "member")


async def _set_role_handler(params: dict[str, Any], role: str) -> dict[str, Any]:
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
    set_role(target["token"], role)
    return {"ok": True, "role": role}


__all__ = [
    "register", "load", "save", "is_valid", "touch", "validate_and_touch",
    "validate_and_lookup_role", "add", "revoke", "rename", "set_role",
]
