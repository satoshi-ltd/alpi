"""Gateway per-chat session pointer map."""

from __future__ import annotations

from pathlib import Path

from alpi import session_map


def test_get_missing_returns_none(tmp_path: Path) -> None:
    assert session_map.get(tmp_path, "chat-1") is None


def test_set_then_get_roundtrips(tmp_path: Path) -> None:
    session_map.set(tmp_path, "chat-1", "sess-abc")
    assert session_map.get(tmp_path, "chat-1") == "sess-abc"


def test_set_overwrites_previous(tmp_path: Path) -> None:
    session_map.set(tmp_path, "chat-1", "sess-old")
    session_map.set(tmp_path, "chat-1", "sess-new")
    assert session_map.get(tmp_path, "chat-1") == "sess-new"


def test_forget_removes_pointer(tmp_path: Path) -> None:
    session_map.set(tmp_path, "chat-1", "sess-abc")
    assert session_map.forget(tmp_path, "chat-1") is True
    assert session_map.get(tmp_path, "chat-1") is None


def test_forget_missing_returns_false(tmp_path: Path) -> None:
    assert session_map.forget(tmp_path, "never-existed") is False


def test_forget_does_not_touch_session_file(tmp_path: Path) -> None:
    """/new semantics — the underlying session JSON must survive forget."""
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    (sessions / "sess-abc.json").write_text('{"id": "sess-abc"}')
    session_map.set(tmp_path, "chat-1", "sess-abc")
    session_map.forget(tmp_path, "chat-1")
    assert (sessions / "sess-abc.json").exists()


def test_empty_chat_id_is_ignored(tmp_path: Path) -> None:
    """Edge case: webhook/email without a real chat id shouldn't pollute the map."""
    session_map.set(tmp_path, "", "sess-abc")
    assert session_map.get(tmp_path, "") is None
    assert session_map.all_pointers(tmp_path) == {}


def test_pointers_isolated_per_chat(tmp_path: Path) -> None:
    session_map.set(tmp_path, "chat-a", "sess-a1")
    session_map.set(tmp_path, "chat-b", "sess-b1")
    assert session_map.get(tmp_path, "chat-a") == "sess-a1"
    assert session_map.get(tmp_path, "chat-b") == "sess-b1"
    session_map.forget(tmp_path, "chat-a")
    assert session_map.get(tmp_path, "chat-a") is None
    assert session_map.get(tmp_path, "chat-b") == "sess-b1"


def test_malformed_json_falls_back_to_empty(tmp_path: Path) -> None:
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    (sessions / "_gateway_map.json").write_text("{{{ not json")
    assert session_map.get(tmp_path, "chat-1") is None
    # Subsequent writes heal the file.
    session_map.set(tmp_path, "chat-1", "sess-abc")
    assert session_map.get(tmp_path, "chat-1") == "sess-abc"


def test_set_waits_for_stable_lock(tmp_path: Path) -> None:
    import fcntl
    import threading

    lock = tmp_path / "gateway" / "sessions" / "_map.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.touch()

    done = threading.Event()

    def worker() -> None:
        session_map.set(tmp_path, "chat-lock", "sess-lock")
        done.set()

    fh = lock.open("a")
    fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
    t = threading.Thread(target=worker)
    t.start()
    try:
        assert not done.wait(0.3)
        assert session_map.get(tmp_path, "chat-lock") is None
    finally:
        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        fh.close()
        assert done.wait(2.0)
        t.join()

    assert session_map.get(tmp_path, "chat-lock") == "sess-lock"
