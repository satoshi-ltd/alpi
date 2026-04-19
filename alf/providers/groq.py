from __future__ import annotations

from alf.providers.base import ModelInfo, Provider


class Groq(Provider):
    name = "groq"
    display = "Groq"
    api_key_env = "GROQ_API_KEY"
    description = "Ultra-fast inference, free tier"

    def list_models(self) -> list[ModelInfo]:
        ids = [
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "qwen-2.5-32b",
            "deepseek-r1-distill-llama-70b",
            "moonshotai/kimi-k2-instruct",
        ]
        return [ModelInfo(id=f"groq/{m}", display=m) for m in ids]
