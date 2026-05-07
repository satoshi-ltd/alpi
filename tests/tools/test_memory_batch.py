"""Tests for ``memory(add, entries=[...])`` batched writes.

Why this exists: a previous session captured the agent calling
``memory(add)`` 16 times in one turn to record team facts. Each call
costs a round-trip and tokens. Batching collapses the same write to
a single call while preserving per-entry duplicate checks.
"""

from __future__ import annotations

from pathlib import Path

from alpi.tools.memory import Memory


def test_add_batch_writes_all_entries(tmp_home_no_env: Path) -> None:
    r = Memory().run(
        action="add", target="USER.md",
        entries=[
            "User name is Test.",
            "User lives in Madrid.",
            "User prefers concise replies.",
        ],
    )
    assert r.ok, r.error
    assert "Added 3 entries" in r.output
    text = (tmp_home_no_env / "memories" / "USER.md").read_text()
    for e in ("Test", "Madrid", "concise"):
        assert e in text


def test_add_batch_skips_duplicates_within_one_file(tmp_home_no_env: Path) -> None:
    """When some entries dup against the other file, the unique ones still
    land — caller gets the kept entry plus a per-skip note."""
    Memory().run(action="add", target="USER.md", content="User name is Same.")
    r = Memory().run(
        action="add", target="MEMORY.md",
        entries=[
            "User name is Same.",
            "Project uses pytest.",
        ],
    )
    assert r.ok
    assert "Project uses pytest" in (tmp_home_no_env / "memories" / "MEMORY.md").read_text()
    assert "skipped" in r.output.lower()


def test_add_batch_skips_duplicate_inside_same_batch(tmp_home_no_env: Path) -> None:
    r = Memory().run(
        action="add", target="USER.md",
        entries=[
            "User prefers terse replies.",
            "User prefers terse replies.",
            "User optimizes for clarity.",
        ],
    )

    assert r.ok, r.error
    text = (tmp_home_no_env / "memories" / "USER.md").read_text()
    assert text.count("User prefers terse replies.") == 1
    assert "User optimizes for clarity." in text
    assert "duplicate of USER.md" in r.output


def test_add_batch_limit_failure_writes_nothing(tmp_home_no_env: Path) -> None:
    Memory().run(action="add", target="USER.md", content="Existing fact.")
    too_large = "x" * 4000

    r = Memory().run(
        action="add", target="USER.md",
        entries=["New fact before overflow.", too_large],
    )

    assert not r.ok
    text = (tmp_home_no_env / "memories" / "USER.md").read_text()
    assert "Existing fact." in text
    assert "New fact before overflow." not in text


def test_add_batch_rejects_when_all_entries_are_duplicates(
    tmp_home_no_env: Path,
) -> None:
    Memory().run(action="add", target="USER.md",
                  content="User name is Solo.")
    r = Memory().run(
        action="add", target="MEMORY.md",
        entries=["User name is Solo.", "User name is Solo."],
    )
    assert not r.ok
    assert "no entries added" in r.error.lower()


def test_add_rejects_both_content_and_entries(tmp_home_no_env: Path) -> None:
    r = Memory().run(
        action="add", target="USER.md",
        content="x", entries=["y"],
    )
    assert not r.ok
    assert "either" in r.error.lower()


def test_add_requires_some_payload(tmp_home_no_env: Path) -> None:
    r = Memory().run(action="add", target="USER.md")
    assert not r.ok
    assert "required" in r.error.lower()


def test_add_batch_works_for_agent_md(tmp_home_no_env: Path) -> None:
    """AGENT.md goes through ``_handle_agent`` — batch path must work
    there too, not only USER/MEMORY."""
    r = Memory().run(
        action="add", target="AGENT.md",
        entries=[
            "## Voice\nTerse, direct.",
            "## Format\nPrefer bullets over prose.",
        ],
    )
    assert r.ok
    text = (tmp_home_no_env / "memories" / "AGENT.md").read_text()
    assert "Voice" in text
    assert "Format" in text


def test_add_single_content_still_works(tmp_home_no_env: Path) -> None:
    """Backwards compat: existing callers that pass ``content=...`` keep
    working unchanged."""
    r = Memory().run(action="add", target="USER.md",
                      content="User name is Legacy.")
    assert r.ok
    assert "Legacy" in (tmp_home_no_env / "memories" / "USER.md").read_text()
