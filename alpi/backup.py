"""Encrypted profile backup / restore.

Zero-knowledge archive of ``~/.alpi/<profile>/``: the user's passphrase is
the only key. Same primitives as `age` with a passphrase recipient
(Scrypt KDF + ChaCha20-Poly1305) but without a new runtime dependency —
``cryptography`` is already pinned for the ALP keys.

File layout::

    b"ALPIBKP1\\n"                    9-byte magic
    json header + b"\\n"              salt, nonce, KDF params, metadata
    ciphertext                        ChaCha20-Poly1305(gzip(tar(profile)))

The ciphertext is single-shot AEAD: profiles are MB-scale, not GB-scale,
so streaming chunks would add complexity for no payoff. Bumping the
magic to ``ALPIBKP2`` is the migration path if that ever changes.
"""

from __future__ import annotations

import base64
import binascii
import gzip
import io
import json
import os
import tarfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

MAGIC = b"ALPIBKP1\n"
SALT_BYTES = 16
NONCE_BYTES = 12
KEY_BYTES = 32

# Scrypt cost. n=2**17, r=8, p=1 ~ 128 MiB / ~1 s on a modern laptop —
# enough headroom that a 10-char passphrase is not online-crackable.
SCRYPT_N = 1 << 17
SCRYPT_R = 8
SCRYPT_P = 1
_KDF_PARAMS = {"n": SCRYPT_N, "r": SCRYPT_R, "p": SCRYPT_P, "length": KEY_BYTES}


# Top-level dirs that hold ephemeral / machine-specific state. Restoring
# them on a different machine would either be wrong (sockets, PIDs) or
# pollute the new profile with stale logs / caches. ``profiles/`` is the
# nested-profile root; backups are per-profile, so don't recurse into it.
_EXCLUDE_DIRS = frozenset({"cache", "logs", ".trash", "profiles"})
_EXCLUDE_SUFFIXES = (".sock", ".pid")


class BackupError(Exception):
    """Raised for any backup/restore failure surfaced to the CLI."""


@dataclass(frozen=True)
class BackupInfo:
    """Returned by :func:`create_backup` for the CLI to summarise."""

    path: Path
    profile: str
    file_count: int
    plaintext_bytes: int
    archive_bytes: int


@dataclass(frozen=True)
class RestoreInfo:
    """Returned by :func:`restore_backup` for the CLI to summarise."""

    target: Path
    profile: str
    file_count: int
    created_at: str


@dataclass(frozen=True)
class _RestoreEntry:
    member: tarfile.TarInfo
    rel: Path


def default_filename(profile: str, when: datetime | None = None) -> str:
    when = when or datetime.now(timezone.utc)
    safe = profile.replace("/", "_") or "default"
    return f"{safe}.{when:%Y-%m-%d}.alpi-backup"


def _iter_files(profile_dir: Path) -> Iterable[Path]:
    for root, dirs, files in os.walk(profile_dir):
        # Prune in-place so os.walk skips excluded subtrees entirely.
        rel_root = Path(root).relative_to(profile_dir)
        if rel_root.parts and rel_root.parts[0] in _EXCLUDE_DIRS:
            dirs[:] = []
            continue
        dirs[:] = [d for d in dirs if d not in _EXCLUDE_DIRS]
        for fn in files:
            if fn.endswith(_EXCLUDE_SUFFIXES):
                continue
            yield Path(root) / fn


def _derive_key(passphrase: str, salt: bytes, *, n: int, r: int, p: int) -> bytes:
    kdf = Scrypt(salt=salt, length=KEY_BYTES, n=n, r=r, p=p)
    return kdf.derive(passphrase.encode("utf-8"))


def _build_tar(profile_dir: Path, arcname: str) -> tuple[bytes, int]:
    buf = io.BytesIO()
    file_count = 0
    with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode="w") as tar:
            for path in sorted(_iter_files(profile_dir)):
                rel = path.relative_to(profile_dir)
                tar.add(path, arcname=f"{arcname}/{rel.as_posix()}", recursive=False)
                file_count += 1
    return buf.getvalue(), file_count


def create_backup(
    profile_dir: Path,
    out_path: Path,
    passphrase: str,
    *,
    profile_name: str | None = None,
) -> BackupInfo:
    """Encrypt ``profile_dir`` into ``out_path``.

    Refuses to overwrite an existing file — the caller decides whether
    to ``unlink`` first. Empty passphrases are rejected.
    """
    if not passphrase:
        raise BackupError("passphrase must not be empty")
    if not profile_dir.exists() or not profile_dir.is_dir():
        raise BackupError(f"profile directory not found: {profile_dir}")
    if out_path.exists():
        raise BackupError(f"output already exists: {out_path}")

    profile = profile_name or profile_dir.name or "default"
    plaintext, file_count = _build_tar(profile_dir, arcname=profile)
    if file_count == 0:
        raise BackupError(f"profile is empty, nothing to back up: {profile_dir}")

    salt = os.urandom(SALT_BYTES)
    nonce = os.urandom(NONCE_BYTES)
    key = _derive_key(passphrase, salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P)
    header = {
        "v": 1,
        "kdf": "scrypt",
        "kdf_params": _KDF_PARAMS,
        "cipher": "chacha20poly1305",
        "compression": "gzip",
        "salt": base64.b64encode(salt).decode("ascii"),
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "profile": profile,
        "file_count": file_count,
        "plaintext_bytes": len(plaintext),
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    header_bytes = json.dumps(header, separators=(",", ":")).encode("utf-8") + b"\n"

    aead = ChaCha20Poly1305(key)
    # AAD binds the header to the ciphertext: tampering the metadata
    # (e.g. lowering the KDF cost) flips the tag and triggers the same
    # InvalidTag the wrong passphrase does.
    ct = aead.encrypt(nonce, plaintext, header_bytes)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("wb") as f:
        f.write(MAGIC)
        f.write(header_bytes)
        f.write(ct)
    try:
        os.chmod(out_path, 0o600)
    except OSError:
        pass

    return BackupInfo(
        path=out_path,
        profile=profile,
        file_count=file_count,
        plaintext_bytes=len(plaintext),
        archive_bytes=out_path.stat().st_size,
    )


def _read_envelope(archive_path: Path) -> tuple[dict, bytes, bytes]:
    with archive_path.open("rb") as f:
        magic = f.read(len(MAGIC))
        if magic != MAGIC:
            raise BackupError(f"not an alpi backup (bad magic): {archive_path}")
        header_line = bytearray()
        while True:
            ch = f.read(1)
            if not ch:
                raise BackupError(f"truncated backup (no header): {archive_path}")
            if ch == b"\n":
                break
            header_line += ch
            if len(header_line) > 64 * 1024:
                raise BackupError("backup header is implausibly large")
        ct = f.read()
    header_bytes = bytes(header_line) + b"\n"
    try:
        header = json.loads(header_line.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise BackupError(f"corrupt backup header: {e}") from None
    if header.get("v") != 1:
        raise BackupError(f"unsupported backup version: {header.get('v')!r}")
    return header, header_bytes, ct


def inspect(archive_path: Path) -> dict:
    """Return the backup header without touching the ciphertext.

    Used by ``alpi restore`` to show ``profile`` + ``created_at`` before
    prompting for the passphrase.
    """
    header, _, _ = _read_envelope(archive_path)
    return header


def _read_crypto_header(header: dict) -> tuple[bytes, bytes]:
    if header.get("kdf") != "scrypt":
        raise BackupError(f"unsupported backup KDF: {header.get('kdf')!r}")
    if header.get("cipher") != "chacha20poly1305":
        raise BackupError(f"unsupported backup cipher: {header.get('cipher')!r}")
    if header.get("compression") != "gzip":
        raise BackupError(f"unsupported backup compression: {header.get('compression')!r}")
    try:
        salt = base64.b64decode(header["salt"], validate=True)
        nonce = base64.b64decode(header["nonce"], validate=True)
        params = header["kdf_params"]
        actual_params = {
            "n": int(params["n"]),
            "r": int(params["r"]),
            "p": int(params["p"]),
            "length": int(params["length"]),
        }
    except (KeyError, TypeError, ValueError, binascii.Error) as e:
        raise BackupError(f"corrupt backup header: {e}") from None
    if len(salt) != SALT_BYTES or len(nonce) != NONCE_BYTES:
        raise BackupError("corrupt backup header: invalid salt or nonce length")
    if actual_params != _KDF_PARAMS:
        raise BackupError("unsupported backup crypto parameters")
    return salt, nonce


def _is_dir_empty(path: Path) -> bool:
    if not path.exists():
        return True
    if not path.is_dir():
        return False
    for _ in path.iterdir():
        return False
    return True


def _restore_entries(tar: tarfile.TarFile) -> list[_RestoreEntry]:
    entries: list[_RestoreEntry] = []
    for member in tar.getmembers():
        # Strip the top-level arcname so any source profile name restores
        # cleanly into ``target_dir`` (the user may rename).
        original = Path(member.name)
        if original.is_absolute():
            raise BackupError(f"refusing unsafe path in backup: {member.name}")
        parts = original.parts
        if not parts:
            continue
        rel = Path(*parts[1:]) if len(parts) > 1 else None
        if rel is None or not rel.parts:
            continue
        if any(p == ".." for p in rel.parts) or rel.is_absolute():
            raise BackupError(f"refusing unsafe path in backup: {member.name}")
        entries.append(_RestoreEntry(member=member, rel=rel))
    return entries


def restore_backup(
    archive_path: Path,
    target_dir: Path,
    passphrase: str,
    *,
    force: bool = False,
) -> RestoreInfo:
    """Decrypt ``archive_path`` into ``target_dir``.

    Refuses if ``target_dir`` exists and is non-empty unless ``force``
    is set. The decrypted tarball is verified before any file lands on
    disk: a wrong passphrase or tampered archive raises ``BackupError``
    without partial extraction.
    """
    if not passphrase:
        raise BackupError("passphrase must not be empty")
    if not archive_path.exists():
        raise BackupError(f"backup file not found: {archive_path}")
    if not _is_dir_empty(target_dir) and not force:
        raise BackupError(
            f"target is not empty: {target_dir} (pass --force to overwrite)"
        )

    header, header_bytes, ct = _read_envelope(archive_path)
    salt, nonce = _read_crypto_header(header)
    key = _derive_key(passphrase, salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P)
    aead = ChaCha20Poly1305(key)
    try:
        plaintext = aead.decrypt(nonce, ct, header_bytes)
    except Exception:
        raise BackupError("decryption failed — wrong passphrase or corrupt backup") from None

    file_count = 0
    with gzip.GzipFile(fileobj=io.BytesIO(plaintext), mode="rb") as gz:
        with tarfile.open(fileobj=gz, mode="r") as tar:
            entries = _restore_entries(tar)
            target_dir.mkdir(parents=True, exist_ok=True)
            for entry in entries:
                member = entry.member
                dest = target_dir / entry.rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                if member.isdir():
                    dest.mkdir(exist_ok=True)
                    continue
                if not member.isfile():
                    continue
                src = tar.extractfile(member)
                if src is None:
                    continue
                with dest.open("wb") as out:
                    out.write(src.read())
                try:
                    os.chmod(dest, member.mode & 0o777)
                except OSError:
                    pass
                file_count += 1

    return RestoreInfo(
        target=target_dir,
        profile=str(header.get("profile", "")),
        file_count=file_count,
        created_at=str(header.get("created_at", "")),
    )
