from __future__ import annotations

from alpi.providers.base import ModelInfo, Provider
from alpi.providers.curated import load_curated


class Anthropic(Provider):
    name = "anthropic"
    display = "Anthropic"
    api_key_env = "ANTHROPIC_API_KEY"
    description = "Claude models"

    def list_models(self) -> list[ModelInfo]:
        return [
            ModelInfo(id=f"anthropic/{m['id']}", display=m["id"], note=m.get("note", ""))
            for m in load_curated("anthropic")
        ]
