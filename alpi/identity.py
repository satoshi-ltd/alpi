"""Public-bio synthesis from a profile's AGENT.md.

A one-shot LLM call that distills AGENT.md (private persona) into a
short tag-line broadcast in workgroups (``cfg.public_bio``). Always
user-initiated — from ``alpi setup → Identity`` (typing ``draft``) or
the Draft button in the desktop ProfileDetail. Never auto-fires.
"""

from __future__ import annotations

from pathlib import Path


def draft_bio_from_agent(home: Path, cfg) -> str:
    """One-shot LLM synthesis. Returns the drafted bio or raises
    ``ValueError`` with a clear message. No side effects."""
    from alpi import config as _cfg, home as _home, llm as _llm

    agent_md = _home.agent_path(home)
    text = agent_md.read_text() if agent_md.exists() else ""
    if not text.strip():
        raise ValueError("AGENT.md is empty — nothing to summarise")
    if not cfg.model:
        raise ValueError("no model configured — set one first")
    messages = [
        {
            "role": "system",
            "content": (
                "You write one-line public bios for AI agents. "
                "Read the agent's private AGENT.md and produce a single "
                "tag-line under 100 chars (no quotes, no period at end) "
                "that another agent could read in a workgroup roster to "
                "understand this agent's role and bias. Output only the "
                "tag-line, nothing else."
            ),
        },
        {"role": "user", "content": text[:8000]},
    ]
    # resolve_model injects the profile's api_key from its .env; calling complete with raw cfg.model would silently fall back to os.environ, which under the daemon belongs to no profile in particular.
    result = _llm.complete(messages=messages, **_cfg.resolve_model(cfg))
    lines = (result.content or "").strip().splitlines()
    if not lines:
        raise ValueError("LLM returned an empty draft")
    first = lines[0].strip().strip('"').strip("'").strip()
    if not first:
        raise ValueError("LLM returned an empty draft")
    return first[:200]
