from __future__ import annotations

from alpi.providers.base import ModelInfo, Provider
from alpi.providers.curated import load_curated


class Google(Provider):
    name = "google"
    display = "Google"
    api_key_env = "GEMINI_API_KEY"
    model_prefix = "gemini"
    description = "Gemini models"

    def list_models(self) -> list[ModelInfo]:
        return [
            ModelInfo(id=f"gemini/{m['id']}", display=m["id"], note=m.get("note", ""))
            for m in load_curated("google")
        ]
