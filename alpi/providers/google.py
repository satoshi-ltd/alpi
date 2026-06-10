from __future__ import annotations

from alpi.providers.base import ModelInfo, Provider


class Google(Provider):
    name = "google"
    display = "Google"
    api_key_env = "GEMINI_API_KEY"
    model_prefix = "gemini"
    description = "Gemini models"

    def list_models(self) -> list[ModelInfo]:
        ids = [
            "gemini-2.5-pro",
            "gemini-2.5-flash",
            "gemini-2.0-flash",
        ]
        return [ModelInfo(id=f"gemini/{m}", display=m) for m in ids]
