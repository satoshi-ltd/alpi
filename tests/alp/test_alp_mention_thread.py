"""Per-sender mention thread storage — load/append/cap."""

from __future__ import annotations

from pathlib import Path

from alpi.alp import mention_thread


def test_load_missing_returns_empty(tmp_path: Path) -> None:
    t = mention_thread.load(tmp_path, "alice")
    assert t.sender == "alice"
    assert t.turns == []


def test_append_caps_at_most_recent(tmp_path: Path) -> None:
    for i in range(mention_thread.CAP + 5):
        mention_thread.append(tmp_path, "alice", f"u{i}", f"a{i}")

    loaded = mention_thread.load(tmp_path, "alice")
    assert len(loaded.turns) == mention_thread.CAP
    # The five oldest fell off; we keep the most recent ``CAP``.
    assert loaded.turns[0].user == "u5"
    assert loaded.turns[-1].user == f"u{mention_thread.CAP + 4}"


def test_unsafe_sender_id_is_dropped(tmp_path: Path) -> None:
    """Defence in depth — the regex in ``mention.parse`` already blocks
    weird ids, but never trust a remote peer to feed sane data into a
    path. ``..`` would otherwise traverse out of ``mentions/``."""
    mention_thread.append(tmp_path, "../evil", "u", "a")
    assert not (tmp_path / "mentions").exists()
    loaded = mention_thread.load(tmp_path, "../evil")
    assert loaded.turns == []


def test_hydrate_skips_when_empty(tmp_path: Path) -> None:
    msgs: list[dict] = []
    mention_thread.hydrate(msgs, mention_thread.Thread(sender="alice"))
    assert msgs == []


def test_hydrate_injects_prior_turns(tmp_path: Path) -> None:
    mention_thread.append(tmp_path, "alice", "hello", "hi back")
    mention_thread.append(tmp_path, "alice", "what now", "answer")

    msgs: list[dict] = [{"role": "system", "content": "base"}]
    mention_thread.hydrate(msgs, mention_thread.load(tmp_path, "alice"))

    roles = [m["role"] for m in msgs]
    assert roles == ["system", "system", "user", "assistant", "user", "assistant"]
    assert msgs[2]["content"] == "hello"
    assert msgs[3]["content"] == "hi back"


def test_host_context_round_trips_byte_stable(tmp_path) -> None:
    from alpi.alp import mention_thread
    from alpi.session import with_host_context

    mention_thread.append(
        tmp_path, "quill", "hola", "respuesta", host_context="# NOW\nLocal: x",
    )
    thread = mention_thread.load(tmp_path, "quill")
    assert thread.turns[-1].host_context == "# NOW\nLocal: x"

    msgs: list[dict] = []
    mention_thread.hydrate(msgs, thread)
    user = next(m for m in msgs if m["role"] == "user")
    assert user["content"] == with_host_context("hola", "# NOW\nLocal: x")


def test_host_context_absent_for_legacy_entries(tmp_path) -> None:
    from alpi.alp import mention_thread

    mention_thread.append(tmp_path, "quill", "hola", "respuesta")
    p = tmp_path / "mentions" / "quill.json"
    assert "host_context" not in p.read_text(), "legacy shape preserved when empty"
    msgs: list[dict] = []
    mention_thread.hydrate(msgs, mention_thread.load(tmp_path, "quill"))
    user = next(m for m in msgs if m["role"] == "user")
    assert user["content"] == "hola"
