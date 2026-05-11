"""Public-bio synthesis primitive — alpi.identity."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from alpi import identity


@dataclass
class _StubResult:
    content: str


@dataclass
class _StubCfg:
    model: str


def _seed_agent(home: Path, text: str) -> None:
    (home / "memories").mkdir(parents=True, exist_ok=True)
    (home / "memories" / "AGENT.md").write_text(text)


def test_draft_returns_clean_first_line(tmp_home, monkeypatch):
    _seed_agent(tmp_home, "# Agent\nyou are a careful librarian")
    monkeypatch.setattr(
        "alpi.llm.complete",
        lambda model, messages: _StubResult(content='"librarian — keeps the record"\nextra'),
    )
    out = identity.draft_bio_from_agent(tmp_home, _StubCfg(model="x"))
    assert out == "librarian — keeps the record"


def test_draft_truncates_to_200_chars(tmp_home, monkeypatch):
    _seed_agent(tmp_home, "x")
    long_bio = "y" * 500
    monkeypatch.setattr(
        "alpi.llm.complete",
        lambda model, messages: _StubResult(content=long_bio),
    )
    out = identity.draft_bio_from_agent(tmp_home, _StubCfg(model="x"))
    assert len(out) == 200


def test_draft_raises_when_agent_empty(tmp_home):
    (tmp_home / "memories").mkdir(parents=True, exist_ok=True)
    (tmp_home / "memories" / "AGENT.md").write_text("   \n")
    with pytest.raises(ValueError, match="AGENT.md is empty"):
        identity.draft_bio_from_agent(tmp_home, _StubCfg(model="x"))


def test_draft_raises_when_agent_missing(tmp_home):
    with pytest.raises(ValueError, match="AGENT.md is empty"):
        identity.draft_bio_from_agent(tmp_home, _StubCfg(model="x"))


def test_draft_raises_when_no_model(tmp_home):
    _seed_agent(tmp_home, "agent text")
    with pytest.raises(ValueError, match="no model configured"):
        identity.draft_bio_from_agent(tmp_home, _StubCfg(model=""))


def test_draft_raises_when_llm_returns_empty(tmp_home, monkeypatch):
    _seed_agent(tmp_home, "agent text")
    monkeypatch.setattr(
        "alpi.llm.complete",
        lambda model, messages: _StubResult(content="   "),
    )
    with pytest.raises(ValueError, match="empty draft"):
        identity.draft_bio_from_agent(tmp_home, _StubCfg(model="x"))


def test_draft_strips_quotes_and_whitespace(tmp_home, monkeypatch):
    _seed_agent(tmp_home, "agent")
    monkeypatch.setattr(
        "alpi.llm.complete",
        lambda model, messages: _StubResult(content='  "  spaced bio  "  '),
    )
    out = identity.draft_bio_from_agent(tmp_home, _StubCfg(model="x"))
    assert out == "spaced bio"
