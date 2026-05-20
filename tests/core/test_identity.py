"""Public-bio synthesis primitive — alpi.identity."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from alpi import config as cfg_mod
from alpi import identity


@dataclass
class _StubResult:
    content: str


def _stub_cfg(home: Path, model: str):
    # identity.draft_bio_from_agent now runs through resolve_model(cfg) so it can pull a per-profile api_key — the stub must be a real Config or resolve_model would AttributeError on `.providers`.
    return cfg_mod.Config(home=home, model=model)


def _seed_agent(home: Path, text: str) -> None:
    (home / "memories").mkdir(parents=True, exist_ok=True)
    (home / "memories" / "AGENT.md").write_text(text)


def test_draft_returns_clean_first_line(tmp_home, monkeypatch):
    _seed_agent(tmp_home, "# Agent\nyou are a careful librarian")
    monkeypatch.setattr(
        "alpi.llm.complete",
        lambda **kw: _StubResult(content='"librarian — keeps the record"\nextra'),
    )
    out = identity.draft_bio_from_agent(tmp_home, _stub_cfg(tmp_home, "x"))
    assert out == "librarian — keeps the record"


def test_draft_truncates_to_200_chars(tmp_home, monkeypatch):
    _seed_agent(tmp_home, "x")
    long_bio = "y" * 500
    monkeypatch.setattr(
        "alpi.llm.complete",
        lambda **kw: _StubResult(content=long_bio),
    )
    out = identity.draft_bio_from_agent(tmp_home, _stub_cfg(tmp_home, "x"))
    assert len(out) == 200


def test_draft_raises_when_agent_empty(tmp_home):
    (tmp_home / "memories").mkdir(parents=True, exist_ok=True)
    (tmp_home / "memories" / "AGENT.md").write_text("   \n")
    with pytest.raises(ValueError, match="AGENT.md is empty"):
        identity.draft_bio_from_agent(tmp_home, _stub_cfg(tmp_home, "x"))


def test_draft_raises_when_agent_missing(tmp_home):
    with pytest.raises(ValueError, match="AGENT.md is empty"):
        identity.draft_bio_from_agent(tmp_home, _stub_cfg(tmp_home, "x"))


def test_draft_raises_when_no_model(tmp_home):
    _seed_agent(tmp_home, "agent text")
    with pytest.raises(ValueError, match="no model configured"):
        identity.draft_bio_from_agent(tmp_home, _stub_cfg(tmp_home, ""))


def test_draft_raises_when_llm_returns_empty(tmp_home, monkeypatch):
    _seed_agent(tmp_home, "agent text")
    monkeypatch.setattr(
        "alpi.llm.complete",
        lambda **kw: _StubResult(content="   "),
    )
    with pytest.raises(ValueError, match="empty draft"):
        identity.draft_bio_from_agent(tmp_home, _stub_cfg(tmp_home, "x"))


def test_draft_strips_quotes_and_whitespace(tmp_home, monkeypatch):
    _seed_agent(tmp_home, "agent")
    monkeypatch.setattr(
        "alpi.llm.complete",
        lambda **kw: _StubResult(content='  "  spaced bio  "  '),
    )
    out = identity.draft_bio_from_agent(tmp_home, _stub_cfg(tmp_home, "x"))
    assert out == "spaced bio"
