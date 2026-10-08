from __future__ import annotations

import asyncio
import base64
import json
import os
import re
import secrets
import shutil
import time
from pathlib import Path
from typing import Any

from alpi import attachments as att
from alpi.host import server as host_server

_STAGE_TTL_SECONDS = 6 * 3600


_FETCH_IMG_MIME = {
    "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
    "webp": "image/webp", "gif": "image/gif",
}
# One contract with attachments.MAX_FILE_BYTES: anything the engine can attach, a client can fetch.
_MAX_FETCH_BYTES = att.MAX_FILE_BYTES


def register(server: host_server.Server) -> None:
    server.register("host.attachments.stage", _stage)
    server.register("host.attachments.fetch", _fetch)


def _resolve_home(profile: str) -> Path:
    from alpi.host.handlers import _resolve_home as _r
    return _r(profile)


def _safe_name(name: Any) -> str:
    base = Path(str(name or "")).name
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("._") or "file"
    return cleaned[:128]


def _stage_root(home: Path) -> Path:
    return home / "host" / "attachments" / "tmp"


def _sweep(root: Path) -> None:
    now = time.time()
    try:
        entries = list(root.glob("*"))
    except OSError:
        return
    for d in entries:
        try:
            if d.is_dir() and now - d.stat().st_mtime > _STAGE_TTL_SECONDS:
                shutil.rmtree(d, ignore_errors=True)
        except OSError:
            pass


async def _stage(params: dict[str, Any], server: host_server.Server) -> dict[str, Any]:
    profile = str(params.get("profile") or "")
    name = _safe_name(params.get("name"))
    mime = str(params.get("mime") or "").strip().lower()
    data_b64 = str(params.get("data_base64") or params.get("data") or "")

    # Match validate()'s per-type cap so a file that stages can also send; unknown types stage as opaque files.
    cap = att.MAX_TEXT_FILE_BYTES if att.is_text(mime) else att.MAX_FILE_BYTES
    # Reject by encoded length before decoding (~4 base64 chars per 3 bytes).
    if len(data_b64) > cap // 3 * 4 + 8:
        raise host_server.HandlerError(-32602, f"attachment exceeds the {cap}-byte cap")
    try:
        data = base64.b64decode(data_b64, validate=True)
    except Exception as e:  # noqa: BLE001
        raise host_server.HandlerError(-32602, "invalid base64 data") from e
    if not data:
        raise host_server.HandlerError(-32602, "empty attachment")
    if len(data) > cap:
        raise host_server.HandlerError(
            -32602, f"{len(data)} bytes exceeds the {cap}-byte cap",
        )

    home = _resolve_home(profile)
    root = _stage_root(home)
    root.mkdir(parents=True, exist_ok=True)
    _sweep(root)
    target_dir = root / secrets.token_hex(8)
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / name
    try:
        _record_owner(target_dir)
        path.write_bytes(data)
    except OSError:
        shutil.rmtree(target_dir, ignore_errors=True)
        raise
    # Validate exactly as host.chat.send will, so anything that stages can send.
    try:
        validated = att.validate([{"path": str(path), "name": name, "mime": mime}])
    except att.AttachmentError as e:
        shutil.rmtree(target_dir, ignore_errors=True)
        raise host_server.HandlerError(-32602, str(e)) from e
    return {
        "ok": True,
        "attachment": {
            "path": str(path),
            "name": name,
            "mime": validated[0].mime,
            "size": len(data),
        },
    }


_OWNER_FILE = ".owner"


def _record_owner(directory: Path) -> None:
    from alpi.host.connection_context import current
    ctx = current()
    (directory / _OWNER_FILE).write_text(json.dumps({
        "connection_id": ctx.connection_id, "device_id": ctx.device_id or "",
    }))


def _staged_owner(home: Path, real: Path) -> dict[str, str] | None:
    try:
        relative = real.relative_to(_stage_root(home).resolve())
    except (ValueError, OSError):
        return None
    if not relative.parts:
        return None
    try:
        owner = json.loads((_stage_root(home).resolve() / relative.parts[0] / _OWNER_FILE).read_text())
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):
        raise host_server.HandlerError(-32001, "forbidden", {"detail": "upload owner cannot be verified"}) from None
    if (
        not isinstance(owner, dict)
        or not isinstance(owner.get("connection_id"), str)
        or not owner["connection_id"]
        or not isinstance(owner.get("device_id"), str)
    ):
        raise host_server.HandlerError(-32001, "forbidden", {"detail": "upload owner cannot be verified"})
    return owner


def _caller_bound(ctx: Any) -> bool:
    return ctx.source == "remote" and ctx.role != "admin"


def _caller_may_fetch(home: Path, requested: str, real: Path) -> bool:
    from alpi.host import offered_paths
    from alpi.host import sessions as host_sessions
    from alpi.host.connection_context import owns_session, owns_session_row

    staged = _staged_owner(home, real)
    if staged is not None:
        return bool(staged) and owns_session(staged["connection_id"], staged["device_id"])
    lexical = os.path.normpath(requested)
    wanted = {str(real)}
    if os.path.realpath(lexical) == str(real):
        wanted.add(lexical)
    return any(
        wanted & offered_paths.for_session(home, row)
        for row in host_sessions.list_sessions(home, None)
        if owns_session_row(row)
    )


def _workspace(home: Path) -> Path | None:
    try:
        from alpi import config as cfg_mod
        return cfg_mod.load(home).workspace_path
    except Exception:  # noqa: BLE001
        return None


def _fetch_allowed(home: Path, real: Path) -> bool:
    return _under_any(real, att.servable_roots(home, _workspace(home), image=True))


def _fetch_nonimage_allowed(home: Path, real: Path) -> bool:
    return _under_any(real, att.servable_roots(home, _workspace(home), image=False))


def _under_any(real: Path, roots: list[Path]) -> bool:
    for r in roots:
        try:
            rc = r.resolve()
        except OSError:
            continue
        if rc == real or rc in real.parents:
            return True
    return False


# Files whose bytes must never be served to a client, no matter the root.
_DENIED_FETCH_EXT = (".pem", ".key", ".p12", ".pfx", ".keystore")


def _fetch_denied(real: Path) -> bool:
    if "secrets" in (p.lower() for p in real.parts):
        return True
    name = real.name.lower()
    return name.startswith(".env") or real.suffix.lower() in _DENIED_FETCH_EXT


async def _fetch(params: dict[str, Any], server: host_server.Server) -> dict[str, Any]:
    profile = str(params.get("profile") or "")
    path = str(params.get("path") or "")
    ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    mime = _FETCH_IMG_MIME.get(ext) or att._PRODUCED_EXT_MIME.get("." + ext)
    opaque = mime is None
    if opaque:
        mime = "application/octet-stream"
    home = _resolve_home(profile)
    try:
        real = Path(path).resolve(strict=True)
    except OSError:
        raise host_server.HandlerError(-32004, "not-found") from None
    is_image = mime.startswith("image/")
    if opaque:
        # Opaque bytes are served only from the attachment staging area — never out/ or the workspace.
        allowed = _under_any(real, [_stage_root(home)])
    elif is_image:
        allowed = _fetch_allowed(home, real)
    else:
        allowed = _fetch_nonimage_allowed(home, real)
    if not real.is_file() or not allowed or _fetch_denied(real):
        raise host_server.HandlerError(-32001, "forbidden", {"detail": "path not readable"})
    from alpi.host.connection_context import current
    if _caller_bound(current()) and not await asyncio.to_thread(_caller_may_fetch, home, path, real):
        raise host_server.HandlerError(-32001, "forbidden", {"detail": "path not readable"})
    data = real.read_bytes()
    if len(data) > _MAX_FETCH_BYTES:
        raise host_server.HandlerError(-32602, f"file exceeds {_MAX_FETCH_BYTES}-byte cap")
    return {
        "name": real.name,
        "mime": mime,
        "size": len(data),
        "data_base64": base64.b64encode(data).decode(),
    }


__all__ = ["register"]
