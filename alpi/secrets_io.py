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
