"""LLM-in-loop tests for persona behaviour."""

from __future__ import annotations

import pytest


pytestmark = pytest.mark.llm


def _seed_persona(home, name: str, expertise: str) -> None:
    (home / "memories" / "AGENT.md").write_text(
        f"You are {name}, a personal AI agent.\n\n"
        "## Voice\n"
        "- Direct, helpful.\n"
        "- Short sentences, no filler.\n\n"
        "## Expertise\n"
        f"- {expertise}\n"
    )


def test_persona_name_emerges_when_asked(llm_engine) -> None:
    _engine, _home, trace, run = llm_engine(
        before_engine=lambda home: _seed_persona(
            home,
            name="Mira",
            expertise="Basque cuisine",
        )
    )
    run("¿Quién eres? Una sola frase.")

    reply = trace.assistant_text().lower()
    assert "mira" in reply, f"persona name not adopted; reply:\n{reply}"


def test_expertise_emerges_in_domain_question(llm_engine) -> None:
    _engine, _home, trace, run = llm_engine(
        before_engine=lambda home: _seed_persona(
            home,
            name="Mira",
            expertise="Basque cuisine, pintxos and Bilbao recipes",
        )
    )
    run("Sugiéreme un pintxo clásico para empezar la noche.")

    reply = trace.assistant_text().lower()
    basque_signals = (
        "gilda", "txangurro", "bacalao", "tortilla", "txakoli",
        "pil-pil", "anchoa", "piparra", "rioja",
    )
    assert any(t in reply for t in basque_signals), (
        f"reply lacks any Basque-domain vocabulary; got:\n{reply}"
    )
