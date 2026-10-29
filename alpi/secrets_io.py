from __future__ import annotations

import os
import tempfile
from pathlib import Path


def safe_write_secret(path: Path | str, content: str | bytes, mode: int = 0o600) -> None:
    # mkstemp gives O_EXCL + 0o600 at create with a random name, immune to a stale .tmp sibling.
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = content.encode() if isinstance(content, str) else content
    fd, tmp_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp",
    )
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        if mode != 0o600:
            os.chmod(tmp, mode)
        os.replace(tmp, path)
    except Exception:
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass
        raise


def open_private(path: Path | str, *, truncate: bool = False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | (os.O_TRUNC if truncate else os.O_APPEND)
    flags |= getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    fd = os.open(str(path), flags, 0o600)
    try:
        if hasattr(os, "fchmod"):
            os.fchmod(fd, 0o600)
        return os.fdopen(fd, "w", encoding="utf-8")
    except Exception:
        os.close(fd)
        raise
