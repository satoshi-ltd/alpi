"""Tests for the Memory tool (the one exposed to the LLM)."""

from __future__ import annotations

from pathlib import Path

import pytest

from alpi.tools.memory import Memory


@pytest.fixture
def isolated_home(tmp_home_no_env: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("ALPI_HOME", str(tmp_home_no_env))
    (tmp_home_no_env / "memories").mkdir(parents=True, exist_ok=True)
    return tmp_home_no_env


def test_tool_description_carries_core_rules() -> None:
    """The description is injected into every LLM turn. The wording has
    been pruned Hermes-style, but the load-bearing invariants must
    survive so even weaker models follow them:

    - All three targets named and discoverable by filename.
    - The no-duplication rule (a fact belongs to exactly one file).
    - The "skip" list signalling what NOT to persist.
    - The explicit "acknowledgement != persistence" rule (otherwise
      small models confirm in text and never call the tool).
    - The replace-match-verbatim rule (otherwise models hallucinate
      match strings and corrupt the file).
    """
    desc = Memory.description
    assert "USER.md" in desc and "MEMORY.md" in desc and "PERSONALITY.md" in desc
    assert "never duplicate" in desc.lower()
    assert "skip:" in desc.lower() or "skip " in desc.lower()
    assert "session progress" in desc.lower()
    assert "call this tool" in desc.lower() and "lost" in desc.lower()
    assert "verbatim" in desc.lower()


def test_tool_description_instructs_neutral_user_voice() -> None:
    """MEMORY.md entries must not nominalize the user by name — the
    name lives in USER.md. Description spells this out explicitly so
    small models don't default to 'Javi wants…' style writes."""
    desc = Memory.description
    assert "neutral" in desc.lower() or 'user"' in desc.lower()
    assert "never" in desc.lower() and "name" in desc.lower()


def test_content_param_description_reinforces_neutral_voice() -> None:
    """Second reminder on the `content` parameter — the agent often
    reads parameter hints even when the top-level description
    description gets skimmed."""
    hint = Memory.parameters["properties"]["content"]["description"]
    assert '"user"' in hint.lower() or "\"user\"" in hint
    assert "name" in hint.lower()


def test_add_user_fact(isolated_home: Path) -> None:
    r = Memory().run(action="add", target="USER.md", content="Javi prefiere café negro.")
    assert r.ok, r.error
    assert "café negro" in (isolated_home / "memories" / "USER.md").read_text()


def test_add_memory_fact(isolated_home: Path) -> None:
    r = Memory().run(action="add", target="MEMORY.md", content="Ruta: /opt/homebrew/bin")
    assert r.ok, r.error
    assert "homebrew" in (isolated_home / "memories" / "MEMORY.md").read_text()


def test_read_reports_usage(isolated_home: Path) -> None:
    Memory().run(action="add", target="USER.md", content="Dato 1")
    r = Memory().run(action="read", target="USER.md")
    assert r.ok
    assert "Dato 1" in r.output
    assert "%" in r.output


def test_personality_add(isolated_home: Path) -> None:
    (isolated_home / "memories" / "PERSONALITY.md").write_text("# Identity\nYou are alpi.\n")
    r = Memory().run(
        action="add", target="personality.md",
        content="Usa bullets cortos, nunca párrafos.",
    )
    assert r.ok, r.error
    assert "bullets" in (isolated_home / "memories" / "PERSONALITY.md").read_text()


def test_personality_add_rejects_dup(isolated_home: Path) -> None:
    (isolated_home / "memories" / "PERSONALITY.md").write_text("Base.\nUsa bullets.\n")
    r = Memory().run(action="add", target="personality.md", content="Usa bullets.")
    assert not r.ok
    assert "already" in (r.error or "").lower()


def test_personality_replace(isolated_home: Path) -> None:
    (isolated_home / "memories" / "PERSONALITY.md").write_text("Frase antigua.\n")
    r = Memory().run(
        action="replace", target="personality.md",
        match="Frase antigua.", content="Frase nueva.",
    )
    assert r.ok, r.error
    assert "Frase nueva" in (isolated_home / "memories" / "PERSONALITY.md").read_text()


def test_replace_entry_unique_match(isolated_home: Path) -> None:
    Memory().run(action="add", target="USER.md", content="Edad: 35")
    r = Memory().run(
        action="replace", target="USER.md",
        match="Edad: 35", content="Edad: 36",
    )
    assert r.ok, r.error
    assert "Edad: 36" in (isolated_home / "memories" / "USER.md").read_text()


def test_remove_entry(isolated_home: Path) -> None:
    Memory().run(action="add", target="USER.md", content="Dato A")
    Memory().run(action="add", target="USER.md", content="Dato B")
    r = Memory().run(action="remove", target="USER.md", match="Dato A")
    assert r.ok, r.error
    text = (isolated_home / "memories" / "USER.md").read_text()
    assert "Dato A" not in text
    assert "Dato B" in text


def test_unknown_target_rejected(isolated_home: Path) -> None:
    r = Memory().run(action="add", target="SOMETHING.md", content="x")
    assert not r.ok


def test_replace_matches_without_accent(isolated_home: Path) -> None:
    """match='te verde' should find entry 'té verde' (accent insensitive)."""
    Memory().run(action="add", target="USER.md", content="Me gusta el té verde.")
    r = Memory().run(
        action="replace", target="USER.md",
        match="te verde", content="Me gusta el café negro.",
    )
    assert r.ok, r.error
    content = (isolated_home / "memories" / "USER.md").read_text()
    assert "café negro" in content
    assert "verde" not in content


def test_remove_matches_case_insensitive(isolated_home: Path) -> None:
    Memory().run(action="add", target="USER.md", content="Javi vive en Madrid.")
    r = Memory().run(action="remove", target="USER.md", match="MADRID")
    assert r.ok, r.error
    assert "Madrid" not in (isolated_home / "memories" / "USER.md").read_text()


def test_personality_replace_accent_insensitive(isolated_home: Path) -> None:
    (isolated_home / "memories" / "PERSONALITY.md").write_text(
        "Usa sinónimos en español cuándo puedas.\n"
    )
    r = Memory().run(
        action="replace", target="personality.md",
        match="cuando puedas", content="siempre",
    )
    assert r.ok, r.error
    assert "siempre" in (isolated_home / "memories" / "PERSONALITY.md").read_text()
