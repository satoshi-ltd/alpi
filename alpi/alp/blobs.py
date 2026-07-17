"""Content-addressed ALP blob transfer."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import os
import re
import stat
import tempfile
from pathlib import Path
from typing import Any

from alpi import attachments
from alpi.alp import client as alp_client
from alpi.alp import peers as peers_mod
from alpi.alp import server as alp_server
from alpi.alp.keys import Keypair, load_or_generate


CHUNK_BYTES = 512 * 1024
MAX_BLOB_BYTES = attachments.MAX_FILE_BYTES
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")


class BlobError(ValueError):
    pass


def _validate_hash(value: Any) -> str:
    digest = str(value or "").strip().lower()
    if not _HASH_RE.fullmatch(digest):
        raise BlobError("hash must be a lowercase SHA-256 hex digest")
    return digest


def _validate_size(value: Any) -> int:
    if isinstance(value, bool):
        raise BlobError("size must be an integer")
    try:
        size = int(value)
    except (TypeError, ValueError) as e:
        raise BlobError("size must be an integer") from e
    if size < 0 or size > MAX_BLOB_BYTES:
        raise BlobError(f"size must be between 0 and {MAX_BLOB_BYTES}")
    return size


def _private_dir(path: Path) -> Path:
    if path.is_symlink():
        raise BlobError(f"unsafe symlink: {path}")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink() or not path.is_dir():
        raise BlobError(f"unsafe blob directory: {path}")
    os.chmod(path, 0o700)
    return path


def blob_root(home: Path) -> Path:
    alp_root = home / "alp"
    if alp_root.is_symlink():
        raise BlobError("unsafe ALP directory")
    _private_dir(alp_root)
    return _private_dir(alp_root / "blobs")


def _incoming_path(home: Path, sender_pubkey: str, digest: str) -> Path:
    incoming = _private_dir(blob_root(home) / ".incoming")
    sender = hashlib.sha256(sender_pubkey.encode("utf-8")).hexdigest()[:16]
    return incoming / f"{sender}-{digest}.part"


def _blob_path(home: Path, digest: str) -> Path:
    return blob_root(home) / digest


def _sha256_file(path: Path) -> tuple[str, int]:
    h = hashlib.sha256()
    size = 0
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(path, flags)
    except OSError as e:
        raise BlobError(f"cannot open blob: {e}") from e
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise BlobError("blob is not a regular file")
        with os.fdopen(fd, "rb") as f:
            fd = -1
            while True:
                chunk = f.read(CHUNK_BYTES)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_BLOB_BYTES:
                    raise BlobError(f"blob exceeds {MAX_BLOB_BYTES} bytes")
                h.update(chunk)
    finally:
        if fd >= 0:
            os.close(fd)
    return h.hexdigest(), size


def _open_verified_blob(path: Path, digest: str):
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(path, flags)
    except OSError as e:
        raise BlobError(f"cannot open blob: {e}") from e
    f = os.fdopen(fd, "rb")
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_BLOB_BYTES:
            raise BlobError("blob is not a valid regular file")
        h = hashlib.sha256()
        size = 0
        while True:
            chunk = f.read(CHUNK_BYTES)
            if not chunk:
                break
            size += len(chunk)
            h.update(chunk)
        if h.hexdigest() != digest:
            raise BlobError("stored blob failed hash verification")
        f.seek(0)
        return f, size
    except Exception:
        f.close()
        raise


def _write_chunk(
    home: Path,
    sender_pubkey: str,
    digest: str,
    size: int,
    offset: int,
    data: bytes,
    final: bool,
) -> dict[str, Any]:
    target = _blob_path(home, digest)
    if target.is_symlink():
        raise BlobError("blob target must not be a symlink")
    if target.exists():
        actual_hash, actual_size = _sha256_file(target)
        if actual_hash != digest or actual_size != size:
            raise BlobError("stored blob conflicts with requested hash or size")
        return {"hash": digest, "size": size, "next_offset": size, "complete": True}

    part = _incoming_path(home, sender_pubkey, digest)
    if part.is_symlink():
        raise BlobError("blob staging file must not be a symlink")
    current = part.stat().st_size if part.exists() else 0
    if offset == 0:
        current = 0
    elif current != offset:
        raise BlobError(f"offset mismatch: expected {current}, got {offset}")
    if offset + len(data) > size:
        raise BlobError("chunk exceeds declared blob size")
    if len(data) > CHUNK_BYTES:
        raise BlobError(f"chunk exceeds {CHUNK_BYTES} bytes")

    flags = os.O_WRONLY | os.O_CREAT
    flags |= os.O_TRUNC if offset == 0 else os.O_APPEND
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(part, flags, 0o600)
        with os.fdopen(fd, "wb" if offset == 0 else "ab") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
    except OSError as e:
        raise BlobError(f"cannot stage blob chunk: {e}") from e

    next_offset = offset + len(data)
    if final:
        if next_offset != size:
            raise BlobError(f"final chunk ended at {next_offset}, expected {size}")
        actual_hash, actual_size = _sha256_file(part)
        if actual_hash != digest or actual_size != size:
            part.unlink(missing_ok=True)
            raise BlobError("blob hash verification failed")
        os.replace(part, target)
        os.chmod(target, 0o600)
    return {
        "hash": digest,
        "size": size,
        "next_offset": next_offset,
        "complete": final,
    }


def register(server: alp_server.Server, home: Path) -> None:
    async def put_blob(params, peer, srv):
        try:
            digest = _validate_hash((params or {}).get("hash"))
            size = _validate_size((params or {}).get("size"))
            offset = int((params or {}).get("offset", 0))
            if offset < 0:
                raise BlobError("offset must be non-negative")
            encoded = str((params or {}).get("data") or "")
            try:
                data = base64.b64decode(encoded, validate=True)
            except Exception as e:  # noqa: BLE001
                raise BlobError("data must be valid base64") from e
            final = bool((params or {}).get("final"))
            return await asyncio.to_thread(
                _write_chunk,
                home,
                peer.pubkey,
                digest,
                size,
                offset,
                data,
                final,
            )
        except (BlobError, TypeError, ValueError) as e:
            raise alp_server.HandlerError(-32602, "invalid-blob", {"detail": str(e)}) from e

    async def get_blob(params, peer, srv):
        try:
            digest = _validate_hash((params or {}).get("hash"))
            path = _blob_path(home, digest)
        except BlobError as e:
            raise alp_server.HandlerError(-32602, "invalid-blob", {"detail": str(e)}) from e
        if not path.exists() or path.is_symlink():
            raise alp_server.HandlerError(-32012, "blob-not-found")
        try:
            f, size = await asyncio.to_thread(_open_verified_blob, path, digest)
        except BlobError as e:
            raise alp_server.HandlerError(-32012, "blob-not-found") from e

        async def stream():
            offset = 0
            try:
                while True:
                    data = await asyncio.to_thread(f.read, CHUNK_BYTES)
                    if not data:
                        break
                    yield {
                        "kind": "chunk",
                        "hash": digest,
                        "offset": offset,
                        "data": base64.b64encode(data).decode("ascii"),
                    }
                    offset += len(data)
                yield {"kind": "final", "hash": digest, "size": size}
            finally:
                f.close()

        return stream()

    server.register("link.put_blob", put_blob)
    server.register("link.get_blob", get_blob)


def _peer(home: Path, peer_id: str):
    peer = peers_mod.get_by_id(home, peer_id)
    if peer is None:
        raise alp_client.ClientError(f"peer {peer_id!r} not in peers.yaml")
    return peer


async def _call_peer(home: Path, peer_id: str, sender: Keypair, method: str, params: dict):
    peer = _peer(home, peer_id)
    if peer.address:
        return await alp_client.call_peer(
            home=home,
            peer_id=peer_id,
            sender=sender,
            method=method,
            params=params,
        )
    return await alp_client.call(
        socket_path=peers_mod.local_socket_path(peer),
        sender=sender,
        recipient_pubkey_b64=peer.pubkey,
        method=method,
        params=params,
    )


async def put(home: Path, peer_id: str, source: Path) -> dict[str, Any]:
    source = source.expanduser()
    digest, size = await asyncio.to_thread(_sha256_file, source)
    sender = load_or_generate(home)
    offset = 0
    with source.open("rb") as f:
        if size == 0:
            return await _call_peer(home, peer_id, sender, "link.put_blob", {
                "hash": digest, "size": 0, "offset": 0, "data": "", "final": True,
            })
        while offset < size:
            data = await asyncio.to_thread(f.read, CHUNK_BYTES)
            final = offset + len(data) == size
            result = await _call_peer(home, peer_id, sender, "link.put_blob", {
                "hash": digest,
                "size": size,
                "offset": offset,
                "data": base64.b64encode(data).decode("ascii"),
                "final": final,
            })
            offset = int(result.get("next_offset", -1))
            if offset < 0 or offset > size:
                raise alp_client.ClientError("peer returned an invalid blob offset")
    return {"hash": digest, "size": size, "complete": True}


async def get(home: Path, peer_id: str, digest: str, destination: Path) -> dict[str, Any]:
    digest = _validate_hash(digest)
    destination = destination.expanduser()
    if destination.exists():
        raise BlobError(f"destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    peer = _peer(home, peer_id)
    sender = load_or_generate(home)
    fd, tmp_name = tempfile.mkstemp(dir=destination.parent, prefix=f".{destination.name}.")
    tmp = Path(tmp_name)
    received = 0
    h = hashlib.sha256()
    final_size: int | None = None
    try:
        with os.fdopen(fd, "wb") as out:
            if peer.address:
                frames = alp_client.call_peer_stream(
                    home=home,
                    peer_id=peer_id,
                    sender=sender,
                    method="link.get_blob",
                    params={"hash": digest},
                )
            else:
                frames = alp_client.call_stream(
                    socket_path=peers_mod.local_socket_path(peer),
                    sender=sender,
                    recipient_pubkey_b64=peer.pubkey,
                    method="link.get_blob",
                    params={"hash": digest},
                )
            async for result, stream in frames:
                if stream == "chunk":
                    if int(result.get("offset", -1)) != received:
                        raise alp_client.ClientError("blob chunks arrived out of order")
                    try:
                        data = base64.b64decode(str(result.get("data") or ""), validate=True)
                    except Exception as e:  # noqa: BLE001
                        raise alp_client.ClientError("peer returned invalid blob data") from e
                    received += len(data)
                    if received > MAX_BLOB_BYTES:
                        raise alp_client.ClientError("blob exceeds local size limit")
                    h.update(data)
                    out.write(data)
                else:
                    final_size = int(result.get("size", -1))
            out.flush()
            os.fsync(out.fileno())
        if final_size != received or h.hexdigest() != digest:
            raise alp_client.ClientError("downloaded blob failed size or hash verification")
        os.replace(tmp, destination)
        return {"hash": digest, "size": received, "path": str(destination)}
    finally:
        tmp.unlink(missing_ok=True)
