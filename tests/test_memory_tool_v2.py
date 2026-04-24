"""Regression coverage for the v2 memory rules.

- A: AGENT.md uses paragraph-level fold + Jaccard dedup, not a raw
  substring check.
- C: add to USER.md / MEMORY.md rejects when the content is already in
  the other file (cross-file duplicate catch).
- E: add returns an operational-state warning when the entry looks
  like a session / chat id log.
- F: when the target reaches ≥80% usage, the tool output carries a
  consolidation hint.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alpi.memory import MEMORY_CHAR_LIMIT, USER_CHAR_LIMIT
from alpi.tools.memory import Memory


@pytest.fixture
def isolated_home(tmp_home_no_env: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("ALPI_HOME", str(tmp_home_no_env))
    (tmp_home_no_env / "memories").mkdir(parents=True, exist_ok=True)
    return tmp_home_no_env


# A — AGENT.md paragraph dedup


def test_agent_add_rejects_paraphrased_stanza(isolated_home: Path) -> None:
    (isolated_home / "memories" / "AGENT.md").write_text(
        "# Voice\n"
        "- Direct, pragmatic, lightly opinionated.\n"
        "- Short sentences, no hedging.\n"
    )
    r = Memory().run(
        action="add", target="AGENT.md",
        content=(
            "# Voice\n"
            "- Pragmatic senior collaborator, lightly opinionated.\n"
            "- Short sentences, no hedging, no filler.\n"
        ),
    )
    assert not r.ok
    assert "duplicate" in (r.error or "").lower()
    assert "replace" in (r.error or "").lower()


def test_agent_add_accepts_genuinely_new_section(isolated_home: Path) -> None:
    (isolated_home / "memories" / "AGENT.md").write_text(
        "# Voice\n- Direct, pragmatic.\n"
    )
    r = Memory().run(
        action="add", target="AGENT.md",
        content="# Defaults\n- Local-first. No cloud.\n",
    )
    assert r.ok, r.error
    text = (isolated_home / "memories" / "AGENT.md").read_text()
    assert "# Voice" in text and "# Defaults" in text


# C — cross-file duplicate detection


def test_add_to_user_rejects_if_already_in_memory(isolated_home: Path) -> None:
    Memory().run(action="add", target="MEMORY.md",
                 content="Vehículos: Volvo XC60 T8 y BMW Z4 E85 (2003).")
    r = Memory().run(action="add", target="USER.md",
                     content="Vehículos: Volvo XC60 T8 y BMW Z4 E85 (2003).")
    assert not r.ok
    assert "memory.md" in (r.error or "").lower()


def test_add_to_memory_rejects_if_already_in_user(isolated_home: Path) -> None:
    Memory().run(action="add", target="USER.md",
                 content="Prefiere respuestas concisas, sin relleno.")
    r = Memory().run(action="add", target="MEMORY.md",
                     content="Prefiere respuestas concisas, sin relleno.")
    assert not r.ok
    assert "user.md" in (r.error or "").lower()


def test_distinct_facts_across_files_do_not_trigger(isolated_home: Path) -> None:
    Memory().run(action="add", target="USER.md",
                 content="Vive en Hua Hin.")
    r = Memory().run(action="add", target="MEMORY.md",
                     content="Workspace por defecto: /Users/javi/git/alpi.")
    assert r.ok, r.error


# E — operational-state warning


def test_operational_state_pattern_triggers_warning(isolated_home: Path) -> None:
    r = Memory().run(
        action="add", target="USER.md",
        content="Telegram chat 8560283937: María Luisa, first interaction 2026-04-22.",
    )
    assert r.ok, r.error
    assert "⚠" in r.output or "operational" in r.output.lower()


def test_session_id_triggers_warning(isolated_home: Path) -> None:
    r = Memory().run(
        action="add", target="MEMORY.md",
        content="Last known session_id for the work chat: abc123.",
    )
    assert r.ok, r.error
    assert "⚠" in r.output or "session" in r.output.lower()


def test_plain_user_fact_has_no_warning(isolated_home: Path) -> None:
    r = Memory().run(
        action="add", target="USER.md",
        content="Le gusta el café negro por la mañana.",
    )
    assert r.ok, r.error
    assert "⚠" not in r.output


# F — consolidation hint at ≥80% usage


def test_over_80_percent_adds_consolidation_hint(isolated_home: Path) -> None:
    # Fill MEMORY.md to ~85% of its limit with a single long entry.
    long_entry = "x " * (int(MEMORY_CHAR_LIMIT * 0.85) // 2)
    Memory().run(action="add", target="MEMORY.md", content=long_entry)
    # Now add a small legitimate entry; the response must flag the state.
    r = Memory().run(action="add", target="MEMORY.md", content="Ollama en localhost:11434.")
    assert r.ok, r.error
    assert "consolidate-memory" in r.output


def test_well_below_limit_has_no_hint(isolated_home: Path) -> None:
    r = Memory().run(action="add", target="USER.md", content="Nombre: Javi.")
    assert r.ok, r.error
    assert "consolidate-memory" not in r.output


# F — the limits themselves got bumped (regression, locks in the new values)


def test_char_limits_are_v2_values() -> None:
    assert USER_CHAR_LIMIT == 3000
    assert MEMORY_CHAR_LIMIT == 5000
