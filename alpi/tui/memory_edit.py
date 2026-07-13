from __future__ import annotations

import contextlib
import os
import tempfile
from pathlib import Path
from typing import Callable

from alpi.memory import MemoryConflict, MemoryStore


def edit_memory_file(home: Path, name: str, launch: Callable[[Path], int]) -> str:
    store = MemoryStore(home)
    try:
        text, rev = store.read_with_rev(name)
    except (OSError, ValueError) as e:
        return f"could not open {name}: {e}"
    try:
        fd, tmp = tempfile.mkstemp(prefix=f"{name}.", suffix=".md")
    except OSError as e:
        return f"could not create a temp file: {e}"
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        try:
            code = launch(Path(tmp))
        except (OSError, ValueError) as e:
            return f"could not launch $EDITOR: {e}"
        if code != 0:
            return f"edit cancelled — {name} unchanged"
        edited = Path(tmp).read_text(encoding="utf-8")
        if edited == text:
            return f"{name} unchanged"
        try:
            store.replace(name, edited, expected_rev=rev)
        except MemoryConflict:
            return f"{name} changed elsewhere — NOT saved; reopen to edit the latest"
        except ValueError as e:
            return f"not saved: {e}"
        return f"saved {name} — live next message"
    except OSError as e:
        return f"could not edit {name}: {e}"
    finally:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
