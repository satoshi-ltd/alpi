"""Provider registry."""

from __future__ import annotations

from typing import Iterable

from alpi.providers.anthropic import Anthropic
from alpi.providers.base import ModelInfo, Provider
from alpi.providers.google import Google
from alpi.providers.groq import Groq
from alpi.providers import ollama as ollama_mod
from alpi.providers.ollama import OllamaProvider
from alpi.providers.openai import OpenAI
from alpi.providers.openrouter import OpenRouter


def builtin() -> list[Provider]:
    return [Anthropic(), OpenAI(), OpenRouter(), Google(), Groq()]


def ollama(cfg_entries: Iterable[dict]) -> list[OllamaProvider]:
    return ollama_mod.connections(cfg_entries)


__all__ = [
    "Anthropic", "OpenAI", "OpenRouter", "Google", "Groq",
    "OllamaProvider", "ModelInfo", "Provider",
    "builtin", "ollama",
]
