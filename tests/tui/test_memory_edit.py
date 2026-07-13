from __future__ import annotations

from pathlib import Path

from alpi.memory import MemoryStore
from alpi.tui.memory_edit import edit_memory_file


def _store(tmp_path: Path) -> MemoryStore:
    (tmp_path / "memories").mkdir(parents=True)
    return MemoryStore(home=tmp_path)


def test_edit_saves_on_clean_exit(tmp_path: Path) -> None:
    store = _store(tmp_path)

    def launch(p: Path) -> int:
        p.write_text("brand new identity")
        return 0

    msg = edit_memory_file(tmp_path, "AGENT.md", launch)
    assert msg.startswith("saved AGENT.md")
    assert store.read_with_rev("AGENT.md")[0] == "brand new identity"


def test_edit_missing_editor_reports_and_keeps_file(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.replace("AGENT.md", "original")

    def launch(_p: Path) -> int:
        raise FileNotFoundError("nano: not found")

    msg = edit_memory_file(tmp_path, "AGENT.md", launch)
    assert "could not launch" in msg
    assert store.read_with_rev("AGENT.md")[0] == "original"


def test_edit_nonzero_exit_discards(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.replace("AGENT.md", "original")

    def launch(p: Path) -> int:
        p.write_text("half-typed, then quit :q!")
        return 1

    msg = edit_memory_file(tmp_path, "AGENT.md", launch)
    assert "cancelled" in msg
    assert store.read_with_rev("AGENT.md")[0] == "original"


def test_edit_rejects_over_limit(tmp_path: Path) -> None:
    from alpi.memory import USER_CHAR_LIMIT
    store = _store(tmp_path)

    def launch(p: Path) -> int:
        p.write_text("x" * (USER_CHAR_LIMIT + 1))
        return 0

    msg = edit_memory_file(tmp_path, "USER.md", launch)
    assert "not saved" in msg
    assert store.read_with_rev("USER.md")[0] == ""


def test_edit_reports_symlink_read_without_escaping(tmp_path: Path) -> None:
    import os
    store = _store(tmp_path)
    outside = tmp_path / "outside.txt"
    outside.write_text("secret")
    os.symlink(outside, store.agent_path)

    called = False

    def launch(_p: Path) -> int:
        nonlocal called
        called = True
        return 0

    msg = edit_memory_file(tmp_path, "AGENT.md", launch)
    assert "could not open" in msg
    assert called is False


def test_edit_handles_filesystem_error_after_launch(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.replace("AGENT.md", "v0")

    def launch(p: Path) -> int:
        p.unlink()  # temp vanished — the later read_text raises OSError
        return 0

    msg = edit_memory_file(tmp_path, "AGENT.md", launch)
    assert "could not edit" in msg
    assert store.read_with_rev("AGENT.md")[0] == "v0"


def test_edit_detects_concurrent_change(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.replace("AGENT.md", "v0")

    def launch(p: Path) -> int:
        p.write_text("my slow edit")
        MemoryStore(home=tmp_path).replace("AGENT.md", "agent wrote this")
        return 0

    msg = edit_memory_file(tmp_path, "AGENT.md", launch)
    assert "changed elsewhere" in msg
    assert store.read_with_rev("AGENT.md")[0] == "agent wrote this"
