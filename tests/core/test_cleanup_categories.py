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


def test_bootstrap_gitignore_covers_private_dirs(tmp_path: Path) -> None:
    """A profile's ``.gitignore`` must hide every dir that holds private
    history so users syncing ``~/.alpi`` via git don't leak chats."""
    home_mod.ensure_home(tmp_path)
    gi = (tmp_path / ".gitignore").read_text()
    for needle in ("sessions/", "mentions/", "gateway/sessions/", "secrets/"):
        assert needle in gi, f"missing {needle!r} in .gitignore"
