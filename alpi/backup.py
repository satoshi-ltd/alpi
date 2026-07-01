"""Encrypted whole-machine backup / restore.

Zero-knowledge archive of ``~/.alpi/`` (every profile + global config):
the user's passphrase is the only key. Same primitives as `age` with a
passphrase recipient (Scrypt KDF + ChaCha20-Poly1305) but without a new
runtime dependency — ``cryptography`` is already pinned for the ALP keys.

File layout::

    b"ALPIBKP1\\n"                    9-byte magic
    json header + b"\\n"              salt, nonce, KDF params, metadata
    ciphertext                        ChaCha20-Poly1305(gzip(tar(alpi-home)))

The ciphertext is single-shot AEAD: the home is MB-scale, sometimes
tens of MB once `knowledge.sqlite` is built, so streaming chunks would
add complexity for no payoff at this size. Bumping the magic to
``ALPIBKP2`` is the migration path if that ever changes.
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


# Dirs that hold ephemeral / machine-specific state. Restoring them on a
# different machine is either wrong (sockets, PIDs) or pollutes with stale
# logs / caches. Applied at every depth so each profile's own cache/logs/
# trash get pruned too.
_EXCLUDE_DIRS = frozenset({"cache", "logs", ".trash"})
_EXCLUDE_FILES = frozenset({".DS_Store", "Thumbs.db"})
_EXCLUDE_SUFFIXES = (".sock", ".pid")
_ARCNAME = "alpi-home"


class BackupError(Exception):
    """Raised for any backup/restore failure surfaced to the CLI."""


@dataclass(frozen=True)
class BackupInfo:
    """Returned by :func:`create_backup` for the CLI to summarise."""

    path: Path
    file_count: int
    plaintext_bytes: int
    archive_bytes: int


@dataclass(frozen=True)
class PreviewEntry:
    """One row of :func:`preview` output — a top-level group inside the home."""

    name: str
    size: int
    file_count: int


@dataclass(frozen=True)
class PreviewFile:
    """One of the largest individual files in :func:`preview` output."""

    path: str
    size: int


@dataclass(frozen=True)
class BackupPreview:
    """Dry-run summary of what :func:`create_backup` would archive.

    ``default_entries`` covers everything directly under ``~/.alpi/`` that
    isn't a named profile (the default-profile data + global config).
    ``profile_entries`` is one row per named profile under ``profiles/``.
    Both are sorted by size desc.
    """

    home: Path
    total_size: int
    total_files: int
    default_entries: list[PreviewEntry]
    profile_entries: list[PreviewEntry]
    largest_files: list[PreviewFile]


@dataclass(frozen=True)
class RestoreInfo:
    """Returned by :func:`restore_backup` for the CLI to summarise."""

    target: Path
    file_count: int
    created_at: str


@dataclass(frozen=True)
class _RestoreEntry:
    member: tarfile.TarInfo
    rel: Path


def default_filename(when: datetime | None = None) -> str:
    when = when or datetime.now(timezone.utc)
    return f"alpi.{when:%Y-%m-%d}.alpi-backup"


def _iter_files(root: Path) -> Iterable[Path]:
    for parent, dirs, files in os.walk(root):
        # Prune in-place at every depth so each profile's own cache/logs/.trash
        # get skipped too (not just the top-level ones).
        dirs[:] = [d for d in dirs if d not in _EXCLUDE_DIRS]
        for fn in files:
            if fn in _EXCLUDE_FILES:
                continue
            if fn.endswith(_EXCLUDE_SUFFIXES):
                continue
            yield Path(parent) / fn


def _group_for(rel: Path) -> tuple[str, str]:
    # Returns ``(section, name)`` where ``section`` is "default" or
    # "profiles". "default" covers the global config + default-profile
    # tree at ``~/.alpi/<thing>``; "profiles" covers each named profile
    # one level deep under ``profiles/<name>/...``.
    parts = rel.parts
    if not parts:
        return ("default", ".")
    if parts[0] == "profiles" and len(parts) >= 2:
        return ("profiles", parts[1])
    return ("default", parts[0])


_LARGEST_FILES_TOP_N = 5
_LARGEST_FILE_MIN_BYTES = 1024 * 1024


def preview(home: Path) -> BackupPreview:
    """Walk ``home`` with the same exclusions :func:`create_backup` applies.

    Returns a per-group size + file-count breakdown plus the top
    ``_LARGEST_FILES_TOP_N`` individual files (filter: ≥1MB) so the CLI
    can show what the archive will contain — and which specific files
    dominate it — before the user types their passphrase.
    """
    if not home.exists() or not home.is_dir():
        raise BackupError(f"alpi home not found: {home}")
    sizes: dict[tuple[str, str], int] = {}
    counts: dict[tuple[str, str], int] = {}
    files: list[PreviewFile] = []
    total_size = 0
    total_files = 0
    for path in _iter_files(home):
        try:
            size = path.stat().st_size
        except OSError:
            continue
        rel = path.relative_to(home)
        key = _group_for(rel)
        sizes[key] = sizes.get(key, 0) + size
        counts[key] = counts.get(key, 0) + 1
        total_size += size
        total_files += 1
        if size >= _LARGEST_FILE_MIN_BYTES:
            files.append(PreviewFile(path=rel.as_posix(), size=size))
    default_entries = [
        PreviewEntry(name=name, size=sizes[k], file_count=counts[k])
        for k, name in ((k, k[1]) for k in sizes if k[0] == "default")
    ]
    profile_entries = [
        PreviewEntry(name=name, size=sizes[k], file_count=counts[k])
        for k, name in ((k, k[1]) for k in sizes if k[0] == "profiles")
    ]
    default_entries.sort(key=lambda e: (-e.size, e.name))
    profile_entries.sort(key=lambda e: (-e.size, e.name))
    files.sort(key=lambda f: (-f.size, f.path))
    return BackupPreview(
        home=home,
        total_size=total_size,
        total_files=total_files,
        default_entries=default_entries,
        profile_entries=profile_entries,
        largest_files=files[:_LARGEST_FILES_TOP_N],
    )


def _derive_key(passphrase: str, salt: bytes, *, n: int, r: int, p: int) -> bytes:
    kdf = Scrypt(salt=salt, length=KEY_BYTES, n=n, r=r, p=p)
    return kdf.derive(passphrase.encode("utf-8"))


def _build_tar(home: Path) -> tuple[bytes, int]:
    buf = io.BytesIO()
    file_count = 0
    with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode="w") as tar:
            for path in sorted(_iter_files(home)):
                rel = path.relative_to(home)
                tar.add(path, arcname=f"{_ARCNAME}/{rel.as_posix()}", recursive=False)
                file_count += 1
    return buf.getvalue(), file_count


def create_backup(
    home: Path,
    out_path: Path,
    passphrase: str,
) -> BackupInfo:
    """Encrypt the entire alpi ``home`` into ``out_path``.

    Walks the home recursively (every profile + global config), excluding
    caches, logs, sockets, and PIDs at every depth. Refuses to overwrite
    an existing file — the caller decides whether to ``unlink`` first.
    Empty passphrases are rejected.
    """
    if not passphrase:
        raise BackupError("passphrase must not be empty")
    if not home.exists() or not home.is_dir():
        raise BackupError(f"alpi home not found: {home}")
    if out_path.exists():
        raise BackupError(f"output already exists: {out_path}")

    plaintext, file_count = _build_tar(home)
    if file_count == 0:
        raise BackupError(f"alpi home is empty, nothing to back up: {home}")

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
        "scope": "machine",
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
    if header.get("scope") != "machine":
        raise BackupError(
            f"unsupported backup scope: {header.get('scope')!r} (expected 'machine')"
        )
    return header, header_bytes, ct


def inspect(archive_path: Path) -> dict:
    """Return the backup header (metadata) without touching the ciphertext.

    Used by ``alpi restore`` to show ``scope`` / ``created_at`` /
    ``file_count`` before prompting for the passphrase.
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
        original = Path(member.name)
        if original.is_absolute():
            raise BackupError(f"refusing unsafe path in backup: {member.name}")
        parts = original.parts
        if not parts:
            continue
        # Tar root MUST be ``_ARCNAME`` — refuse archives with any other
        # prefix even if their inner paths look benign.
        if parts[0] != _ARCNAME:
            raise BackupError(
                f"unexpected tar root {parts[0]!r} (expected {_ARCNAME!r})"
            )
        rel = Path(*parts[1:]) if len(parts) > 1 else None
        if rel is None or not rel.parts:
            continue
        if any(p == ".." for p in rel.parts) or rel.is_absolute():
            raise BackupError(f"refusing unsafe path in backup: {member.name}")
        entries.append(_RestoreEntry(member=member, rel=rel))
    return entries


def _wipe_children(target_dir: Path, keep: Path) -> None:
    """Remove every child of ``target_dir`` except the subtree containing ``keep``.

    Called only AFTER the archive's AEAD tag verifies and ``_restore_entries``
    accepts the tar layout — so a wrong passphrase or tampered backup can
    never destroy the user's data. If ``keep`` lives inside a child
    directory (e.g. ``target/backups/self.alpi-backup``), that whole
    child subtree is preserved.
    """
    import shutil

    keep_resolved = keep.resolve() if keep.exists() else keep
    for child in target_dir.iterdir():
        try:
            child_resolved = child.resolve()
        except OSError:
            child_resolved = child
        if child_resolved == keep_resolved or _is_inside(keep_resolved, child_resolved):
            continue
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            try:
                child.unlink()
            except OSError:
                pass


def _is_inside(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def restore_backup(
    archive_path: Path,
    target_dir: Path,
    passphrase: str,
    *,
    force: bool = False,
) -> RestoreInfo:
    """Decrypt ``archive_path`` into ``target_dir`` as a clean replace.

    Refuses if ``target_dir`` exists and is non-empty unless ``force``
    is set. With ``force``, every existing child of ``target_dir`` is
    removed AFTER the AEAD tag verifies — a wrong passphrase or tampered
    archive raises ``BackupError`` without touching the user's data.
    The archive file itself is preserved if it happens to live inside
    ``target_dir``.
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
            if force and not _is_dir_empty(target_dir):
                _wipe_children(target_dir, keep=archive_path)
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
        file_count=file_count,
        created_at=str(header.get("created_at", "")),
    )
