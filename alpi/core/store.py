"""Per-profile SQLite store with sqlite-vec loaded.

Consumers (BA workspace RAG today; ALP.6 workgroup search and any future
entity-memory landing later) bring their own table schemas. This module
only owns the file location and the extension load.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import sqlite_vec


def store_path(home: Path) -> Path:
    return home / "rag" / "store.sqlite"


def open_store(home: Path) -> sqlite3.Connection:
    """Open (or create) the per-profile store with sqlite-vec loaded."""
    path = store_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    return conn
