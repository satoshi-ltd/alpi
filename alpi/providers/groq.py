from __future__ import annotations

from alpi.providers.base import ModelInfo, Provider
from alpi.providers.curated import load_curated


class Groq(Provider):
    name = "groq"
    display = "Groq"
    api_key_env = "GROQ_API_KEY"
    description = "Ultra-fast inference, free tier"

    def list_models(self) -> list[ModelInfo]:
        return [
            ModelInfo(id=f"groq/{m['id']}", display=m["id"], note=m.get("note", ""))
            for m in load_curated("groq")
        ]
