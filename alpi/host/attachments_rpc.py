from __future__ import annotations

import base64
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

    if mime not in att.ALLOWED_MIMES:
        raise host_server.HandlerError(
            -32602, f"unsupported type {mime or 'unknown'!r}",
            {"allowed": sorted(att.ALLOWED_MIMES)},
        )
    # Match validate()'s per-type cap so a file that stages can also send.
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
    path.write_bytes(data)
    # Validate exactly as host.chat.send will, so anything that stages can send.
    try:
        att.validate([{"path": str(path), "name": name, "mime": mime}])
    except att.AttachmentError as e:
        shutil.rmtree(target_dir, ignore_errors=True)
        raise host_server.HandlerError(-32602, str(e)) from e
    return {
        "ok": True,
        "attachment": {
            "path": str(path),
            "name": name,
            "mime": mime,
            "size": len(data),
        },
    }


# Allowed read roots for serving image bytes to remote clients: workspace + home + temp.
def _fetch_allowed(home: Path, real: Path) -> bool:
    import tempfile

    roots = [Path("/tmp"), Path("/private/tmp"), Path(tempfile.gettempdir()), home]
    try:
        from alpi import config as cfg_mod
        ws = cfg_mod.load(home).workspace_path
        if ws:
            roots.append(ws)
    except Exception:  # noqa: BLE001
        pass
    return _under_any(real, roots)


def _fetch_nonimage_allowed(home: Path, real: Path) -> bool:
    from alpi.home import out_root
    roots = [home / "host" / "attachments" / "tmp"]
    orp = out_root(home)
    if orp is not None:
        roots.append(orp)
    try:
        from alpi import config as cfg_mod
        ws = cfg_mod.load(home).workspace_path
        if ws:
            roots.append(ws)
    except Exception:  # noqa: BLE001
        pass
    return _under_any(real, roots)


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
    if not mime:
        raise host_server.HandlerError(-32602, "unsupported file type")
    home = _resolve_home(profile)
    try:
        real = Path(path).resolve(strict=True)
    except OSError:
        raise host_server.HandlerError(-32004, "not-found") from None
    is_image = mime.startswith("image/")
    allowed = _fetch_allowed(home, real) if is_image else _fetch_nonimage_allowed(home, real)
    if not real.is_file() or not allowed or _fetch_denied(real):
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
