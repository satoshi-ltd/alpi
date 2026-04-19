from __future__ import annotations

from alf.providers.base import ModelInfo, Provider


class OpenAI(Provider):
    name = "openai"
    display = "OpenAI"
    api_key_env = "OPENAI_API_KEY"
    description = "GPT, o-series"

    def list_models(self) -> list[ModelInfo]:
        ids = [
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4.1",
            "gpt-4.1-mini",
            "o3",
            "o3-mini",
            "o1",
        ]
        return [ModelInfo(id=f"openai/{m}", display=m) for m in ids]
