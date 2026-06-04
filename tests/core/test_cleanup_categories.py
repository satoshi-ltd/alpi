"""``setup → Cleanup`` lists per-sender @-mention threads alongside
sessions/logs/etc. so the user can wipe a remitente's memory from
the menu instead of `rm`-ing files."""

from __future__ import annotations

from pathlib import Path

from alpi import home as home_mod
from alpi.alp import mention_thread
from alpi.cli import _cleanup_categories


def test_mentions_category_lists_thread_files(tmp_path: Path) -> None:
    mention_thread.append(tmp_path, "alice", "u", "a")
    mention_thread.append(tmp_path, "carol", "u", "a")

    cats = _cleanup_categories(tmp_path)
    mentions = next(c for c in cats if c["key"] == "mentions")

    names = sorted(p.name for p in mentions["files"])
    assert names == ["alice.json", "carol.json"]
    assert mentions["size"] > 0


def test_attachments_category_lists_staged_dirs(tmp_path: Path) -> None:
    d = tmp_path / "host" / "attachments" / "tmp" / "abc123"
    d.mkdir(parents=True)
    (d / "scan.pdf").write_bytes(b"%PDF-1.4 staged")

    cats = _cleanup_categories(tmp_path)
    att = next(c for c in cats if c["key"] == "attachments")

    assert [p.name for p in att["files"]] == ["abc123"]
    assert att["size"] > 0
    assert att["action"] == "rmtree"


def test_gateway_category_only_lists_session_files_not_state(
    tmp_path: Path,
) -> None:
    """``gateway/`` mixes transport state (telegram-state.json) with
    chat sessions (``gateway/sessions/<id>.json``). The Cleanup category
    must point at the sessions subdir only — wiping transport state
    would lose Telegram offsets / IMAP last-uid and trigger reprocessing."""
    (tmp_path / "gateway").mkdir()
    (tmp_path / "gateway" / "telegram-state.json").write_text("{}")
    (tmp_path / "gateway" / "sessions").mkdir()
    (tmp_path / "gateway" / "sessions" / "abc.json").write_text("{}")

    cats = _cleanup_categories(tmp_path)
    gateway = next(c for c in cats if c["key"] == "gateway")

    names = sorted(p.name for p in gateway["files"])
    assert names == ["abc.json"]


def test_rag_category_absent_when_store_has_no_freelist(tmp_path: Path) -> None:
    """No `rag/store.sqlite` and no freelist → cleanup row appears with
    size 0, empty files, and the vacuum action. Empty list makes the
    cleanup loop skip it just like other empty categories."""
    cats = _cleanup_categories(tmp_path)
    rag = next(c for c in cats if c["key"] == "rag")
    assert rag["size"] == 0
    assert rag["files"] == []
    assert rag["action"] == "vacuum"


def test_rag_category_surfaces_freelist_bytes(tmp_path: Path) -> None:
    """After artificial bloat the rag category must surface reclaimable
    bytes and point at `rag/store.sqlite` for display."""
    import sqlite3

    from alpi.core import store as store_mod

    sp = store_mod.store_path(tmp_path)
    sp.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(sp)
    try:
        conn.execute("CREATE TABLE bloat(id INTEGER PRIMARY KEY, blob BLOB)")
        conn.executemany(
            "INSERT INTO bloat(blob) VALUES (?)",
            [(b"\x00" * 4096,) for _ in range(200)],
        )
        conn.commit()
        conn.execute("DROP TABLE bloat")
        conn.commit()
    finally:
        conn.close()

    cats = _cleanup_categories(tmp_path)
    rag = next(c for c in cats if c["key"] == "rag")
    assert rag["size"] > 0
    assert rag["files"] == [sp]
    assert rag["action"] == "vacuum"


def test_compact_reclaims_freelist_without_deleting_store(tmp_path: Path) -> None:
    """`compact()` runs VACUUM and shrinks the file but must NOT unlink
    `rag/store.sqlite` — embeddings would be lost."""
    import sqlite3

    from alpi.core import store as store_mod

    sp = store_mod.store_path(tmp_path)
    sp.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(sp)
    try:
        conn.execute("CREATE TABLE keep(id INTEGER PRIMARY KEY, blob BLOB)")
        conn.execute("INSERT INTO keep(blob) VALUES (?)", (b"survivor",))
        conn.execute("CREATE TABLE bloat(id INTEGER PRIMARY KEY, blob BLOB)")
        conn.executemany(
            "INSERT INTO bloat(blob) VALUES (?)",
            [(b"\x00" * 4096,) for _ in range(200)],
        )
        conn.commit()
        conn.execute("DROP TABLE bloat")
        conn.commit()
    finally:
        conn.close()

    before, after = store_mod.compact(tmp_path)
    assert before > after
    assert sp.exists()
    assert store_mod.reclaimable_bytes(tmp_path) == 0
    conn = sqlite3.connect(sp)
    try:
        row = conn.execute("SELECT blob FROM keep").fetchone()
    finally:
        conn.close()
    assert row[0] == b"survivor"


def test_compact_returns_zero_when_no_store(tmp_path: Path) -> None:
    from alpi.core import store as store_mod
    assert store_mod.compact(tmp_path) == (0, 0)
    assert store_mod.reclaimable_bytes(tmp_path) == 0


def test_curator_category_lists_report_dirs_recursively(tmp_path: Path) -> None:
    """Curator writes ``logs/curator/<ts>/report.md`` + ``.json``. The Cleanup category must surface the per-run dirs (not flat files) and report total bytes from rglob."""
    from alpi import curator
    for ts in (1_700_000_000.0, 1_800_000_000.0):
        curator.write_report(tmp_path, curator.review(tmp_path, now=ts), ts=ts)

    cats = _cleanup_categories(tmp_path)
    cur = next(c for c in cats if c["key"] == "curator")

    assert cur["action"] == "rmtree"
    assert len(cur["files"]) == 2
    assert all(p.is_dir() for p in cur["files"])
    assert cur["size"] > 0
    for d in cur["files"]:
        assert (d / "report.md").exists()
        assert (d / "report.json").exists()


def test_curator_category_empty_when_no_reports(tmp_path: Path) -> None:
    cats = _cleanup_categories(tmp_path)
    cur = next(c for c in cats if c["key"] == "curator")
    assert cur["files"] == []
    assert cur["size"] == 0
    assert cur["action"] == "rmtree"


def test_bootstrap_gitignore_covers_private_dirs(tmp_path: Path) -> None:
    """A profile's ``.gitignore`` must hide every dir that holds private
    history so users syncing ``~/.alpi`` via git don't leak chats."""
    home_mod.ensure_home(tmp_path)
    gi = (tmp_path / ".gitignore").read_text()
    for needle in ("sessions/", "mentions/", "gateway/sessions/", "secrets/"):
        assert needle in gi, f"missing {needle!r} in .gitignore"
