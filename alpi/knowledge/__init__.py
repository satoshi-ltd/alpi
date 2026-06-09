"""Packaged answer packs about alpi itself; read by the alpi_knowledge tool."""

from __future__ import annotations

from importlib.resources import files


# Closed enum of topics. The alpi_knowledge tool validates against this; sync_knowledge.py asserts it matches the on-disk reference set.
TOPICS: dict[str, str] = {
    "readme": "readme.md",
    "quickstart": "quickstart.md",
    "install": "install.md",
    "profiles": "profiles.md",
    "skills": "skills.md",
    "tools": "tools.md",
    "models": "models.md",
    "alp": "alp.md",
    "architecture": "architecture.md",
    "config": "config.md",
    "security": "security.md",
    "deployments": "deployments.md",
    "operations": "operations.md",
}


def topics() -> list[str]:
    return list(TOPICS.keys())


def read(topic: str) -> str:
    filename = TOPICS.get(topic)
    if filename is None:
        valid = ", ".join(topics())
        raise KeyError(f"unknown alpi knowledge topic: {topic!r}. Valid topics: {valid}")
    return (files("alpi.knowledge") / "references" / filename).read_text(encoding="utf-8")
