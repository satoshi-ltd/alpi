"""``@alpi/knowledge`` — the first bundled skill.

The skill ships with alpi (no on-disk install) so the agent can
answer questions about alpi itself without a ``web_search`` round-
trip and without guessing from training data.

Tests cover the surface that the LLM actually uses:

- The skill is discoverable via ``bundled_skills()`` and the
  skills index.
- Read-only enforcement (mutating actions on a bundled skill are
  rejected with the variant-pattern hint).
- ``skill(action="view")`` resolves both the SKILL.md body and
  the ``references/*.md`` files.
- The references actually contain alpi documentation (sanity
  check that the sync ran and a representative doc is present).
- The frontmatter is well-formed (the `description` is what the
  agent matches against the user's task).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from alpi.tools.skill import (
    BUNDLED_PREFIX,
    Skill,
    bundled_skills,
    skills_index_block,
)


@pytest.fixture
def alpi_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    return tmp_path


def test_knowledge_appears_in_bundled_skills() -> None:
    names = [s["name"] for s in bundled_skills()]
    assert f"{BUNDLED_PREFIX}knowledge" in names


def test_knowledge_has_well_formed_frontmatter() -> None:
    entry = next(
        s for s in bundled_skills() if s["name"] == f"{BUNDLED_PREFIX}knowledge"
    )
    assert entry["category"] == "meta"
    desc = entry["description"]
    # Description is what the LLM matches against the user's task —
    # it must be a single line, non-empty, mention alpi by name.
    assert desc
    assert "\n" not in desc
    assert "alpi" in desc.lower()


def test_view_returns_skill_md_body(alpi_home: Path) -> None:
    skill = Skill()
    r = skill.run(action="view", name=f"{BUNDLED_PREFIX}knowledge")
    assert r.ok
    assert "alpi:knowledge" in r.output
    assert "Routing table" in r.output


def test_view_resolves_references(alpi_home: Path) -> None:
    skill = Skill()
    r = skill.run(
        action="view", name=f"{BUNDLED_PREFIX}knowledge",
        file="references/install.md",
    )
    assert r.ok
    # Sanity-check that this is the actual install doc, not an empty file.
    assert "alpi" in r.output.lower()
    assert "uv tool install" in r.output


def test_references_cover_the_canonical_topics(alpi_home: Path) -> None:
    """Every topic the SKILL.md routing table promises must exist
    as a file. If sync_knowledge.py drops a doc or renames it, this
    catches the drift before the LLM hits a 'not found' at runtime."""
    skill = Skill()
    expected = [
        "readme.md", "quickstart.md", "install.md", "profiles.md",
        "skills.md", "models.md", "alp.md", "architecture.md",
        "config.md", "security.md", "deployments.md", "operations.md",
    ]
    for fname in expected:
        r = skill.run(
            action="view", name=f"{BUNDLED_PREFIX}knowledge",
            file=f"references/{fname}",
        )
        assert r.ok, f"missing reference: {fname} — {r.error}"
        assert r.output.strip(), f"empty reference: {fname}"


def test_create_on_bundled_skill_is_rejected(alpi_home: Path) -> None:
    """Bundled skills are read-only. The variant pattern (create your
    own with a different name in a non-@ category) is the explicit
    escape hatch."""
    skill = Skill()
    r = skill.run(
        action="create", name=f"{BUNDLED_PREFIX}knowledge",
        category="meta", description="x", body="x",
    )
    assert not r.ok
    assert "bundled" in r.error.lower()


def test_edit_on_bundled_skill_is_rejected(alpi_home: Path) -> None:
    skill = Skill()
    r = skill.run(
        action="edit", name=f"{BUNDLED_PREFIX}knowledge", body="x",
    )
    assert not r.ok
    assert "bundled" in r.error.lower()


def test_skills_index_block_includes_knowledge(alpi_home: Path) -> None:
    """The system prompt's skills-index block is what the LLM scans
    when deciding which skill to engage. The bundled knowledge skill
    must appear (with the [bundled] marker per docs/SKILLS.md)."""
    block = skills_index_block(alpi_home)
    assert block, "expected a non-empty skills-index block"
    assert f"{BUNDLED_PREFIX}knowledge" in block
    assert "[bundled]" in block


def test_skills_index_block_carries_imperative_alpi_rule(alpi_home: Path) -> None:
    """Small LLMs ignore implicit 'prefer skills' nudges. When
    ``@alpi/knowledge`` is bundled, the index block adds an explicit
    RULE that names the skill, names the trigger word (``alpi``),
    and tells the model to call view BEFORE answering."""
    block = skills_index_block(alpi_home)
    assert "RULE" in block
    assert "@alpi/knowledge" in block
    # The rule must be imperative and reference the SKILL.md routing.
    assert "FIRST" in block
    assert "training is not" in block.lower() or "training data" in block.lower() \
        or "after your cutoff" in block.lower()


def test_skill_md_routing_table_only_lists_existing_files(alpi_home: Path) -> None:
    """The routing table maps topics to ``references/<file>.md``.
    Every filename mentioned in the table must actually be present
    in the bundled references — otherwise the LLM follows an
    instruction that points at nothing and the answer collapses."""
    import re
    skill = Skill()
    body = skill.run(action="view", name=f"{BUNDLED_PREFIX}knowledge").output
    referenced = set(re.findall(r"`([a-z]+\.md)`", body))
    # Drop the "filename" placeholder used in the API example.
    referenced.discard("<filename>.md")
    for fname in referenced:
        r = skill.run(
            action="view", name=f"{BUNDLED_PREFIX}knowledge",
            file=f"references/{fname}",
        )
        assert r.ok, f"SKILL.md mentions {fname} but the file is missing"
