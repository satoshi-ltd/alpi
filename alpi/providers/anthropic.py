from __future__ import annotations

from alpi.providers.base import ModelInfo, Provider


_CURATED: list[tuple[str, str]] = [
    ("claude-opus-4-7",   "flagship"),
    ("claude-opus-4-6",   "flagship · 1M ctx"),
    ("claude-sonnet-4-6", "balanced"),
    ("claude-haiku-4-5",  "cheap · fast"),
]


class Anthropic(Provider):
    name = "anthropic"
    display = "Anthropic"
    api_key_env = "ANTHROPIC_API_KEY"
    description = "Claude models"

    def list_models(self) -> list[ModelInfo]:
        return [
            ModelInfo(id=f"anthropic/{m}", display=m, note=tag)
            for m, tag in _CURATED
        ]
