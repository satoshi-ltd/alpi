"""Provider registry."""

from __future__ import annotations

from typing import Iterable

from alf.providers.anthropic import Anthropic
from alf.providers.base import ModelInfo, Provider
from alf.providers.custom import CustomProvider
from alf.providers.google import Google
from alf.providers.groq import Groq
from alf.providers.openai import OpenAI
from alf.providers.openrouter import OpenRouter


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
