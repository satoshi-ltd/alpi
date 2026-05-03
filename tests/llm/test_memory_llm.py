"""LLM-in-loop tests for the memory tool.

Asserts the LLM routes facts to the right file (USER / MEMORY /
AGENT) and that persisted content stays in English even when the
chat is in another language.
"""

from __future__ import annotations

import pytest


pytestmark = pytest.mark.llm


def _read(path):
    return path.read_text() if path.exists() else ""


def test_user_fact_lands_in_user_md(llm_engine) -> None:
    engine, home, trace, run = llm_engine()
    run("Soy Javi, vivo en Bilbao y soy ingeniero de software.")

    memory_calls = [
        e for e in trace.tool_calls("memory")
        if e.args.get("action") == "add" and e.args.get("target") == "USER.md"
    ]
    assert memory_calls, (
        "agent did not store the user fact in USER.md "
        "(routing failed - would land elsewhere)"
    )

    user_md = _read(home / "memories" / "USER.md")
    # Stored in English even though chat is Spanish.
    assert "Javi" in user_md
    assert "Bilbao" in user_md
    # No Spanish stopwords in the persisted entry.
    lower = user_md.lower()
    assert "soy " not in lower and "vivo " not in lower, (
        f"USER.md was persisted in Spanish - got:\n{user_md}"
    )


def test_persona_change_lands_in_agent_md(llm_engine) -> None:
    engine, home, trace, run = llm_engine()
    run(
        "A partir de ahora, cuando me sugieras una receta, añade siempre "
        "un wine pairing al final. Esto es parte de tu personalidad - "
        "guárdalo en AGENT.md."
    )

    agent_calls = [
        e for e in trace.tool_calls("memory")
        if e.args.get("target") == "AGENT.md"
    ]
    assert agent_calls, "agent did not write the persona rule to AGENT.md"

    agent_md = _read(home / "memories" / "AGENT.md")
    lower = agent_md.lower()
    assert "wine pairing" in lower or "wine" in lower, (
        f"wine-pairing rule not persisted; got:\n{agent_md}"
    )
    # English persistence.
    assert "maridaje" not in lower, (
        "rule stored in Spanish - English persistence rule failed"
    )


def test_persisted_content_stays_english_under_spanish_chat(llm_engine) -> None:
    """Whichever target the agent picks, the body is English."""
    engine, home, trace, run = llm_engine()
    run("Recuerda que tengo intolerancia al gluten - apúntalo.")

    memory_calls = [
        e for e in trace.tool_calls("memory")
        if e.args.get("action") == "add"
    ]
    assert memory_calls, "agent did not call memory(action='add')"

    target = memory_calls[0].args.get("target", "USER.md")
    md = _read(home / "memories" / target)
    lower = md.lower()
    # Concept must be there (translated forms).
    assert "gluten" in lower
    # No Spanish persistence.
    assert "intolerancia" not in lower, (
        f"persisted in Spanish - got:\n{md}"
    )
