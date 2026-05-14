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


def reclaimable_bytes(home: Path) -> int:
    """Bytes a ``VACUUM`` would release from the per-profile RAG store.

    Computed as ``freelist_count * page_size``; returns 0 if the store
    doesn't exist yet (nothing to reclaim).
    """
    if not store_path(home).exists():
        return 0
    conn = sqlite3.connect(store_path(home))
    try:
        page_size = conn.execute("PRAGMA page_size").fetchone()[0]
        freelist = conn.execute("PRAGMA freelist_count").fetchone()[0]
        return int(page_size) * int(freelist)
    finally:
        conn.close()


def compact(home: Path) -> tuple[int, int]:
    """Run ``VACUUM`` on the per-profile RAG store, returning ``(before, after)``.

    Sizes are file bytes on disk. The store file is preserved — only the
    SQLite freelist is reclaimed. Returns ``(0, 0)`` if the store doesn't
    exist yet.
    """
    path = store_path(home)
    if not path.exists():
        return (0, 0)
    before = path.stat().st_size
    conn = sqlite3.connect(path)
    try:
        prior_isolation = conn.isolation_level
        conn.isolation_level = None
        try:
            conn.execute("VACUUM")
        finally:
            conn.isolation_level = prior_isolation
    finally:
        conn.close()
    after = path.stat().st_size
    return (before, after)
