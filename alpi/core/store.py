from __future__ import annotations

import sqlite3
from pathlib import Path

import sqlite_vec


def store_path(home: Path) -> Path:
    return home / "knowledge.sqlite"


def open_store(home: Path) -> sqlite3.Connection:
    path = store_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    return conn


def reclaimable_bytes(home: Path) -> int:
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
