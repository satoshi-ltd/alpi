from __future__ import annotations

from alf.providers.base import ModelInfo, Provider


class Anthropic(Provider):
    name = "anthropic"
    display = "Anthropic"
    api_key_env = "ANTHROPIC_API_KEY"
    description = "Claude models"

    def list_models(self) -> list[ModelInfo]:
        ids = [
            "claude-opus-4-7",
            "claude-opus-4-6",
            "claude-sonnet-4-6",
            "claude-sonnet-4-5",
            "claude-haiku-4-5",
        ]
        return [ModelInfo(id=f"anthropic/{m}", display=m) for m in ids]
