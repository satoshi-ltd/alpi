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


def test_knowledge_category_absent_when_store_has_no_freelist(tmp_path: Path) -> None:
    """No `knowledge.sqlite` and no freelist -> cleanup row appears with
    size 0, empty files, and the vacuum action. Empty list makes the
    cleanup loop skip it just like other empty categories."""
    cats = _cleanup_categories(tmp_path)
    knowledge = next(c for c in cats if c["key"] == "knowledge")
    assert knowledge["size"] == 0
    assert knowledge["files"] == []
    assert knowledge["action"] == "vacuum"


def test_knowledge_category_surfaces_freelist_bytes(tmp_path: Path) -> None:
    """After artificial bloat the knowledge category must surface reclaimable
    bytes and point at `knowledge.sqlite` for display."""
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
    knowledge = next(c for c in cats if c["key"] == "knowledge")
    assert knowledge["size"] > 0
    assert knowledge["files"] == [sp]
    assert knowledge["action"] == "vacuum"


def test_compact_reclaims_freelist_without_deleting_store(tmp_path: Path) -> None:
    """`compact()` runs VACUUM and shrinks the file but must NOT unlink
    `knowledge.sqlite` - embeddings would be lost."""
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
    for needle in ("sessions/", "mentions/", "secrets/"):
        assert needle in gi, f"missing {needle!r} in .gitignore"


def test_generated_category_lists_only_old_out_files(tmp_path: Path) -> None:
    import os
    import time

    from alpi import cleanup

    out = tmp_path / "out"
    (out / "nested").mkdir(parents=True)
    old = out / "old-image.jpg"
    old.write_text("jpg")
    stale = time.time() - (cleanup.GENERATED_KEEP_DAYS + 5) * 86_400
    os.utime(old, (stale, stale))
    old_nested = out / "nested" / "old-doc.pdf"
    old_nested.write_text("pdf")
    os.utime(old_nested, (stale, stale))
    fresh = out / "fresh.png"
    fresh.write_text("png")

    cat = next(c for c in cleanup.categories(tmp_path) if c["key"] == "generated")
    assert cat["destructive"] is True
    assert sorted(p.name for p in cat["files"]) == ["old-doc.pdf", "old-image.jpg"]

    result = cleanup.apply(tmp_path, "generated")
    assert result["ok"] and result["removed"] == 2
    assert fresh.exists() and not old.exists() and not old_nested.exists()


def test_bootstrap_gitignore_covers_out_and_run_state(tmp_path: Path) -> None:
    home_mod.ensure_home(tmp_path)
    gi = (tmp_path / ".gitignore").read_text()
    for needle in ("out/", "schedule/runs.json"):
        assert needle in gi, f"missing {needle!r} in .gitignore"


def test_generated_refuses_symlinked_out_root(tmp_path: Path) -> None:
    import os
    import time

    from alpi import cleanup

    outside = tmp_path / "outside"
    outside.mkdir()
    victim = outside / "victim.pdf"
    victim.write_text("precious")
    stale = time.time() - (cleanup.GENERATED_KEEP_DAYS + 5) * 86_400
    os.utime(victim, (stale, stale))
    home = tmp_path / "home"
    home.mkdir()
    (home / "out").symlink_to(outside)

    cat = next(c for c in cleanup.categories(home) if c["key"] == "generated")
    assert cat["files"] == []
    cleanup.apply(home, "generated")
    assert victim.exists()


def test_generated_skips_symlinks_inside_out(tmp_path: Path) -> None:
    import os
    import time

    from alpi import cleanup

    outside = tmp_path / "outside"
    (outside / "deep").mkdir(parents=True)
    victim = outside / "deep" / "victim.pdf"
    victim.write_text("precious")
    loose = outside / "loose.pdf"
    loose.write_text("precious")
    home = tmp_path / "home"
    (home / "out").mkdir(parents=True)
    (home / "out" / "link-dir").symlink_to(outside / "deep")
    (home / "out" / "link-file.pdf").symlink_to(loose)
    stale = time.time() - (cleanup.GENERATED_KEEP_DAYS + 5) * 86_400
    for p in (victim, loose, home / "out" / "link-file.pdf"):
        try:
            os.utime(p, (stale, stale), follow_symlinks=False)
        except (NotImplementedError, OSError):
            os.utime(p, (stale, stale))

    cat = next(c for c in cleanup.categories(home) if c["key"] == "generated")
    assert cat["files"] == []
    cleanup.apply(home, "generated")
    assert victim.exists() and loose.exists()


def test_ensure_home_provisions_private_out_dir(tmp_path: Path) -> None:
    import stat

    home_mod.ensure_home(tmp_path)
    out = tmp_path / "out"
    assert out.is_dir()
    assert stat.S_IMODE(out.stat().st_mode) == 0o700
    assert home_mod.out_root(tmp_path) == out


def test_ensure_home_never_touches_a_symlinked_out(tmp_path: Path) -> None:
    import stat

    outside = tmp_path / "outside"
    outside.mkdir(mode=0o755)
    home = tmp_path / "home"
    home.mkdir()
    (home / "out").symlink_to(outside)
    home_mod.ensure_home(home)
    assert stat.S_IMODE(outside.stat().st_mode) == 0o755
    assert home_mod.out_root(home) is None


def test_ensure_home_survives_broken_out_symlink(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    (home / "out").symlink_to(tmp_path / "gone")
    home_mod.ensure_home(home)
    assert (home / "out").is_symlink()
    assert home_mod.out_root(home) is None


def test_ensure_home_leaves_regular_file_named_out(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    (home / "out").write_text("i am a file")
    home_mod.ensure_home(home)
    assert (home / "out").read_text() == "i am a file"
    assert home_mod.out_root(home) is None
