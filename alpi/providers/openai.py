from __future__ import annotations

from alpi.providers.base import ModelInfo, Provider
from alpi.providers.curated import load_curated


class OpenAI(Provider):
    name = "openai"
    display = "OpenAI"
    api_key_env = "OPENAI_API_KEY"
    description = "GPT, o-series"

    def list_models(self) -> list[ModelInfo]:
        return [
            ModelInfo(id=f"openai/{m['id']}", display=m["id"], note=m.get("note", ""))
            for m in load_curated("openai")
        ]
