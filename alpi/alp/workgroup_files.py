"""Encrypted file sidecars for ALP workgroups."""

from __future__ import annotations

import base64
import asyncio
import contextlib
import hashlib
import json
import os
import re
import sys
import tempfile
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from alpi import attachments
from alpi.alp import server as alp_server
from alpi.alp.keys import Keypair
from alpi.home import format_bytes

if sys.platform == "win32":
    import msvcrt
    _fcntl = None
else:
    import fcntl as _fcntl
    msvcrt = None


CHUNK_BYTES = 256 * 1024
MAX_FILE_BYTES = attachments.MAX_FILE_BYTES
MAX_WORKGROUP_BYTES = 200 * 1024 * 1024
_PART_TTL_SECONDS = 24 * 3600
_AEAD_TAG_BYTES = 16
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_MARKER_LINE_RE = re.compile(
    r"^(?:@\S+\s+)*#(?:task|done|skip|working|file)\b",
    re.MULTILINE,
)
_MAX_NAME_CHARS = 255
_MAX_NOTE_CHARS = 2000
_DEFAULT_LIST_LIMIT = 50
_MAX_LIST_LIMIT = 200


class WorkgroupFileError(ValueError):
    pass


def _validate_hash(value: Any) -> str:
    digest = str(value or "").strip().lower()
    if not _HASH_RE.fullmatch(digest):
        raise WorkgroupFileError("sha256 must be a lowercase SHA-256 hex digest")
    return digest


def _validate_size(value: Any) -> int:
    if isinstance(value, bool):
        raise WorkgroupFileError("size must be an integer")
    try:
        size = int(value)
    except (TypeError, ValueError) as e:
        raise WorkgroupFileError("size must be an integer") from e
    if size <= 0 or size > MAX_FILE_BYTES:
        raise WorkgroupFileError(f"size must be between 1 and {MAX_FILE_BYTES}")
    return size


def _validate_name(value: Any) -> str:
    raw = str(value or "").strip()
    name = Path(raw).name
    if (
        not name
        or name in {".", ".."}
        or name != raw
        or any(ord(char) < 32 or ord(char) == 127 for char in name)
        or len(name) > _MAX_NAME_CHARS
    ):
        raise WorkgroupFileError("name must be a plain file name")
    return name


def _validate_note(value: Any) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise WorkgroupFileError("note must be a string")
    note = value.strip()
    if len(note) > _MAX_NOTE_CHARS:
        raise WorkgroupFileError(f"note exceeds {_MAX_NOTE_CHARS} characters")
    if _MARKER_LINE_RE.search(note):
        raise WorkgroupFileError("note must not contain workgroup protocol markers")
    return note


def _validate_nonce(value: Any) -> str:
    nonce = str(value or "")
    try:
        raw = base64.b64decode(nonce, validate=True)
    except Exception as e:  # noqa: BLE001
        raise WorkgroupFileError("nonce must be valid base64") from e
    if len(raw) != 12:
        raise WorkgroupFileError("nonce must encode 12 bytes")
    return nonce


def _files_root(home: Path, wg_id: str) -> Path:
    from alpi.alp.workgroup import _wg_dir

    wg_dir = _wg_dir(home, wg_id)
    if wg_dir.is_symlink():
        raise WorkgroupFileError("unsafe workgroup directory")
    root = wg_dir / "files"
    if root.is_symlink():
        raise WorkgroupFileError("unsafe workgroup files directory")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if root.is_symlink() or not root.is_dir():
        raise WorkgroupFileError("unsafe workgroup files directory")
    os.chmod(root, 0o700)
    return root


@contextlib.contextmanager
def _locked(home: Path, wg_id: str) -> Iterator[None]:
    root = _files_root(home, wg_id)
    f = open(root / ".lock", "a+b")
    try:
        if sys.platform == "win32":
            f.seek(0)
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


def _paths(root: Path, digest: str) -> tuple[Path, Path, Path, Path]:
    return (
        root / f"{digest}.bin",
        root / f"{digest}.json",
        root / f".{digest}.part",
        root / f".{digest}.part.json",
    )


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(value, f, separators=(",", ":"), ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        os.chmod(path, 0o600)
    finally:
        tmp.unlink(missing_ok=True)


def _sweep_parts(root: Path) -> None:
    cutoff = time.time() - _PART_TTL_SECONDS
    for part in root.glob(".*.part"):
        try:
            if part.is_symlink() or part.stat().st_mtime >= cutoff:
                continue
            part.unlink(missing_ok=True)
            part.with_name(part.name + ".json").unlink(missing_ok=True)
        except OSError:
            continue
    for meta_path in root.glob(".*.part.json"):
        part = meta_path.with_suffix("")
        try:
            if meta_path.is_symlink() or part.exists() or meta_path.stat().st_mtime >= cutoff:
                continue
            meta_path.unlink(missing_ok=True)
        except OSError:
            continue


def _stored_bytes(root: Path, *, exclude_digest: str = "") -> int:
    total = 0
    for meta_path in root.glob("*.json"):
        if meta_path.name.startswith(".") or meta_path.is_symlink():
            continue
        meta = _read_json(meta_path)
        if meta is None or meta.get("sha256") == exclude_digest:
            continue
        bin_path = root / f"{meta.get('sha256')}.bin"
        if not bin_path.is_file() or bin_path.is_symlink():
            continue
        try:
            total += max(0, int(meta.get("size", 0)))
        except (TypeError, ValueError):
            continue
    for meta_path in root.glob(".*.part.json"):
        if meta_path.is_symlink():
            continue
        meta = _read_json(meta_path)
        if meta is None or meta.get("sha256") == exclude_digest:
            continue
        try:
            total += max(0, int(meta.get("size", 0)))
        except (TypeError, ValueError):
            continue
    return total


def _marker_text(name: str, size: int, digest: str, note: str) -> str:
    first = f"#file {name} · {format_bytes(size)} · sha256:{digest}"
    return f"{first}\n{note}" if note else first


def _append_marker(
    home: Path,
    wg,
    kp: Keypair,
    *,
    uploader: str,
    key_version: int,
    name: str,
    size: int,
    digest: str,
    note: str,
) -> dict[str, Any]:
    from alpi.alp import wakes
    from alpi.alp.workgroup import (
        _MAX_TRANSCRIPT_POSTS,
        _append_transcript,
        _read_transcript,
        _save_members,
        _wg_dir,
        encrypt_post,
        hub_group_keys,
    )

    group_key = hub_group_keys(home, wg, kp).get(key_version)
    if group_key is None:
        raise WorkgroupFileError(f"key_version {key_version} is not available")
    d = _wg_dir(home, wg.meta.id)
    existing = _read_transcript(d)
    if len(existing) >= _MAX_TRANSCRIPT_POSTS:
        raise WorkgroupFileError("workgroup transcript is full")
    nonce, ciphertext = encrypt_post(
        group_key,
        _marker_text(name, size, digest, note).encode("utf-8"),
    )
    seq = int(existing[-1].get("seq", 0)) + 1 if existing else 1
    entry = {
        "seq": seq,
        "ts": _utcnow(),
        "from": uploader,
        "key_version": key_version,
        "nonce": nonce,
        "ciphertext": ciphertext,
    }
    member = wg.member(uploader)
    if member is not None:
        member.last_seen_at = entry["ts"]
        _save_members(d, wg.members)
    _append_transcript(d, entry)
    try:
        from alpi.host import events as host_events
        from alpi.home import profile_name
        host_events.emit("wg.post", {
            "profile": profile_name(home),
            "wg_id": wg.meta.id,
            "seq": seq,
        })
    except Exception:  # noqa: BLE001
        pass
    wakes.fire(home, wg.meta.id)
    return {"seq": seq, "ts": entry["ts"]}


def _utcnow() -> str:
    import datetime as dt

    return dt.datetime.now(tz=dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _verified_existing(
    bin_path: Path,
    meta_path: Path,
    digest: str,
    size: int,
) -> dict[str, Any] | None:
    if bin_path.is_symlink() or meta_path.is_symlink():
        raise WorkgroupFileError("stored workgroup file is unsafe")
    if not bin_path.exists() and not meta_path.exists():
        return None
    meta = _read_json(meta_path)
    if meta is None or not bin_path.is_file():
        raise WorkgroupFileError("stored workgroup file is incomplete")
    if meta.get("sha256") != digest or int(meta.get("size", -1)) != size:
        raise WorkgroupFileError("stored workgroup file conflicts with upload")
    return meta


def _put_chunk_locked(
    home: Path,
    wg,
    kp: Keypair,
    uploader: str,
    params: dict[str, Any],
) -> dict[str, Any]:
    from alpi.alp.workgroup import decrypt_post, hub_group_keys

    digest = _validate_hash(params.get("sha256"))
    size = _validate_size(params.get("size"))
    name = _validate_name(params.get("name"))
    note = _validate_note(params.get("note"))
    nonce = _validate_nonce(params.get("nonce"))
    try:
        key_version = int(params.get("key_version"))
        offset = int(params.get("offset", 0))
    except (TypeError, ValueError) as e:
        raise WorkgroupFileError("key_version and offset must be integers") from e
    if key_version <= 0 or offset < 0:
        raise WorkgroupFileError("key_version must be positive and offset non-negative")
    try:
        data = base64.b64decode(str(params.get("data_base64") or ""), validate=True)
    except Exception as e:  # noqa: BLE001
        raise WorkgroupFileError("data_base64 must be valid base64") from e
    if len(data) > CHUNK_BYTES:
        raise WorkgroupFileError(f"chunk exceeds {CHUNK_BYTES} bytes")
    done = bool(params.get("done"))
    ciphertext_size = size + _AEAD_TAG_BYTES
    if offset + len(data) > ciphertext_size:
        raise WorkgroupFileError("chunk exceeds declared ciphertext size")

    root = _files_root(home, wg.meta.id)
    _sweep_parts(root)
    bin_path, meta_path, part_path, part_meta_path = _paths(root, digest)
    existing = _verified_existing(bin_path, meta_path, digest, size)
    if existing is not None:
        marker = _append_marker(
            home, wg, kp, uploader=uploader,
            key_version=key_version, name=name, size=size, digest=digest, note=note,
        )
        return {
            "ok": True, "existed": True, "complete": True,
            "next_offset": ciphertext_size, "marker": marker,
        }

    upload_meta = {
        "name": name,
        "size": size,
        "sha256": digest,
        "key_version": key_version,
        "nonce": nonce,
        "uploaded_by": uploader,
        "note": note,
    }
    current_meta = _read_json(part_meta_path) if part_meta_path.exists() else None
    if offset == 0:
        if current_meta is not None and current_meta.get("uploaded_by") != uploader:
            return {
                "ok": True, "busy": True, "complete": False,
                "next_offset": 0,
            }
        if _stored_bytes(root, exclude_digest=digest) + size > MAX_WORKGROUP_BYTES:
            raise alp_server.HandlerError(-32012, "file-quota-exceeded")
        part_path.unlink(missing_ok=True)
        part_meta_path.unlink(missing_ok=True)
        _atomic_json(part_meta_path, upload_meta)
    elif current_meta != upload_meta:
        raise WorkgroupFileError("upload metadata changed between chunks")

    if part_path.is_symlink():
        raise WorkgroupFileError("workgroup upload staging file is unsafe")
    current = part_path.stat().st_size if part_path.exists() else 0
    if current != offset:
        raise WorkgroupFileError(f"offset mismatch: expected {current}, got {offset}")
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(part_path, flags, 0o600)
        with os.fdopen(fd, "ab") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
    except OSError as e:
        if offset == 0:
            part_path.unlink(missing_ok=True)
            part_meta_path.unlink(missing_ok=True)
        raise WorkgroupFileError(f"cannot stage file chunk: {e}") from e
    next_offset = offset + len(data)
    if not done:
        return {"ok": True, "complete": False, "next_offset": next_offset}
    if next_offset != ciphertext_size:
        raise WorkgroupFileError(
            f"final chunk ended at {next_offset}, expected {ciphertext_size}",
        )

    keys = hub_group_keys(home, wg, kp)
    group_key = keys.get(key_version)
    if group_key is None:
        part_path.unlink(missing_ok=True)
        part_meta_path.unlink(missing_ok=True)
        raise WorkgroupFileError(f"key_version {key_version} is not available")
    try:
        ciphertext = part_path.read_bytes()
        plaintext = decrypt_post(
            group_key,
            nonce,
            base64.b64encode(ciphertext).decode("ascii"),
        )
    except Exception as e:  # noqa: BLE001
        part_path.unlink(missing_ok=True)
        part_meta_path.unlink(missing_ok=True)
        raise WorkgroupFileError("encrypted file failed authentication") from e
    if len(plaintext) != size or hashlib.sha256(plaintext).hexdigest() != digest:
        part_path.unlink(missing_ok=True)
        part_meta_path.unlink(missing_ok=True)
        raise WorkgroupFileError("file size or sha256 verification failed")

    final_meta = {
        **upload_meta,
        "uploaded_at": _utcnow(),
    }
    try:
        os.replace(part_path, bin_path)
        os.chmod(bin_path, 0o600)
        _atomic_json(meta_path, final_meta)
    except Exception:
        bin_path.unlink(missing_ok=True)
        raise
    finally:
        part_meta_path.unlink(missing_ok=True)
    try:
        marker = _append_marker(
            home, wg, kp, uploader=uploader,
            key_version=key_version, name=name, size=size, digest=digest, note=note,
        )
    except Exception:
        bin_path.unlink(missing_ok=True)
        meta_path.unlink(missing_ok=True)
        raise
    return {
        "ok": True, "existed": False, "complete": True,
        "next_offset": next_offset, "marker": marker,
    }


def put_chunk(
    home: Path,
    wg,
    kp: Keypair,
    uploader: str,
    params: dict[str, Any],
) -> dict[str, Any]:
    with _locked(home, wg.meta.id):
        return _put_chunk_locked(home, wg, kp, uploader, params)


def get_chunk(
    home: Path,
    wg_id: str,
    digest_value: Any,
    offset_value: Any,
) -> dict[str, Any]:
    digest = _validate_hash(digest_value)
    try:
        offset = int(offset_value or 0)
    except (TypeError, ValueError) as e:
        raise WorkgroupFileError("offset must be an integer") from e
    if offset < 0:
        raise WorkgroupFileError("offset must be non-negative")
    with _locked(home, wg_id):
        root = _files_root(home, wg_id)
        bin_path, meta_path, _, _ = _paths(root, digest)
        if (
            not bin_path.is_file()
            or bin_path.is_symlink()
            or meta_path.is_symlink()
        ):
            raise alp_server.HandlerError(-32011, "file-not-found")
        meta = _read_json(meta_path)
        if meta is None:
            raise alp_server.HandlerError(-32011, "file-not-found")
        ciphertext_size = bin_path.stat().st_size
        if offset > ciphertext_size:
            raise WorkgroupFileError(
                f"offset mismatch: ciphertext ends at {ciphertext_size}",
            )
        with bin_path.open("rb") as f:
            f.seek(offset)
            data = f.read(CHUNK_BYTES)
        return {
            "data_base64": base64.b64encode(data).decode("ascii"),
            "size": int(meta["size"]),
            "ciphertext_size": ciphertext_size,
            "eof": offset + len(data) >= ciphertext_size,
            "name": str(meta["name"]),
            "sha256": digest,
            "key_version": int(meta["key_version"]),
            "nonce": str(meta["nonce"]),
        }


def list_metadata(
    home: Path,
    wg_id: str,
    offset_value: Any = 0,
    limit_value: Any = _DEFAULT_LIST_LIMIT,
) -> dict[str, Any]:
    try:
        offset = int(offset_value or 0)
        limit = int(limit_value or _DEFAULT_LIST_LIMIT)
    except (TypeError, ValueError) as e:
        raise WorkgroupFileError("offset and limit must be integers") from e
    if offset < 0 or limit < 1 or limit > _MAX_LIST_LIMIT:
        raise WorkgroupFileError(
            f"offset must be non-negative and limit between 1 and {_MAX_LIST_LIMIT}",
        )
    with _locked(home, wg_id):
        root = _files_root(home, wg_id)
        files = []
        for meta_path in root.glob("*.json"):
            if meta_path.name.startswith(".") or meta_path.is_symlink():
                continue
            digest = meta_path.stem
            if not _HASH_RE.fullmatch(digest):
                continue
            bin_path = root / f"{digest}.bin"
            if not bin_path.is_file() or bin_path.is_symlink():
                continue
            meta = _read_json(meta_path)
            if meta is None or meta.get("sha256") != digest:
                continue
            try:
                files.append({
                    "name": _validate_name(meta.get("name")),
                    "size": _validate_size(meta.get("size")),
                    "sha256": digest,
                    "uploaded_by": str(meta.get("uploaded_by") or ""),
                    "uploaded_at": str(meta.get("uploaded_at") or ""),
                    "note": _validate_note(meta.get("note")),
                })
            except WorkgroupFileError:
                continue
        files.sort(
            key=lambda item: (item["uploaded_at"], item["sha256"]),
            reverse=True,
        )
        page = files[offset: offset + limit]
        consumed = offset + len(page)
        return {
            "files": page,
            "total": len(files),
            "next_offset": consumed if consumed < len(files) else None,
        }


def register(server: alp_server.Server, home: Path) -> None:
    from alpi.alp import workgroup as wg_mod

    async def file_put(params, peer, srv):
        wg_id = str((params or {}).get("workgroup_id") or "").strip()
        wg = wg_mod.load(home, wg_id)
        if wg is None:
            raise alp_server.HandlerError(-32009, "workgroup-not-found")
        member = wg.member(peer.pubkey)
        if member is None:
            raise alp_server.HandlerError(-32008, "workgroup-not-member")
        if not member.joined:
            raise alp_server.HandlerError(
                -32008, "workgroup-not-joined",
                {"detail": "run workgroup.join before uploading files"},
            )
        if wg.meta.paused:
            raise alp_server.HandlerError(-32010, "workgroup-paused")
        try:
            return await asyncio.to_thread(
                put_chunk, home, wg, srv.kp, peer.pubkey, params or {},
            )
        except alp_server.HandlerError:
            raise
        except (OSError, WorkgroupFileError, TypeError, ValueError) as e:
            raise alp_server.HandlerError(
                -32602, "invalid-workgroup-file", {"detail": str(e)},
            ) from e

    async def file_get(params, peer, srv):
        wg_id = str((params or {}).get("workgroup_id") or "").strip()
        wg = wg_mod.load(home, wg_id)
        if wg is None:
            raise alp_server.HandlerError(-32009, "workgroup-not-found")
        member = wg.member(peer.pubkey)
        if member is None:
            raise alp_server.HandlerError(-32008, "workgroup-not-member")
        if not member.joined:
            raise alp_server.HandlerError(
                -32008, "workgroup-not-joined",
                {"detail": "run workgroup.join before fetching files"},
            )
        try:
            return await asyncio.to_thread(
                get_chunk,
                home,
                wg_id,
                (params or {}).get("sha256"),
                (params or {}).get("offset", 0),
            )
        except alp_server.HandlerError:
            raise
        except (OSError, WorkgroupFileError, TypeError, ValueError) as e:
            raise alp_server.HandlerError(
                -32602, "invalid-workgroup-file", {"detail": str(e)},
            ) from e

    async def file_list(params, peer, srv):
        wg_id = str((params or {}).get("workgroup_id") or "").strip()
        wg = wg_mod.load(home, wg_id)
        if wg is None:
            raise alp_server.HandlerError(-32009, "workgroup-not-found")
        member = wg.member(peer.pubkey)
        if member is None:
            raise alp_server.HandlerError(-32008, "workgroup-not-member")
        if not member.joined:
            raise alp_server.HandlerError(
                -32008, "workgroup-not-joined",
                {"detail": "run workgroup.join before listing files"},
            )
        try:
            return await asyncio.to_thread(
                list_metadata,
                home,
                wg_id,
                (params or {}).get("offset", 0),
                (params or {}).get("limit", _DEFAULT_LIST_LIMIT),
            )
        except (OSError, WorkgroupFileError, TypeError, ValueError) as e:
            raise alp_server.HandlerError(
                -32602, "invalid-workgroup-file", {"detail": str(e)},
            ) from e

    server.register("workgroup.file_put", file_put)
    server.register("workgroup.file_get", file_get)
    server.register("workgroup.file_list", file_list)
