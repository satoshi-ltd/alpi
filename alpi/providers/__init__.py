"""Provider registry."""

from __future__ import annotations

from typing import Iterable

from alpi.providers.anthropic import Anthropic
from alpi.providers.base import ModelInfo, Provider
from alpi.providers.custom import CustomProvider
from alpi.providers.google import Google
from alpi.providers.groq import Groq
from alpi.providers.openai import OpenAI
from alpi.providers.openrouter import OpenRouter


def builtin() -> list[Provider]:
    return [Anthropic(), OpenAI(), OpenRouter(), Google(), Groq()]


def custom(cfg_entries: Iterable[dict]) -> list[CustomProvider]:
    out: list[CustomProvider] = []
    for entry in cfg_entries or []:
        name = entry.get("name") or ""
        base = entry.get("base_url") or ""
        if not name or not base:
            continue
        out.append(CustomProvider(
            name=name,
            display=f"{name}  ({base})",
            base_url=base,
            api_key_env=entry.get("api_key_env", "") or "",
        ))
    return out


__all__ = [
    "Anthropic", "OpenAI", "OpenRouter", "Google", "Groq",
    "CustomProvider", "ModelInfo", "Provider",
    "builtin", "custom",
]
