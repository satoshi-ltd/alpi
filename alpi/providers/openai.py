from __future__ import annotations

from alpi.providers.base import ModelInfo, Provider


_CURATED: list[tuple[str, str]] = [
    ("gpt-5.4",         "flagship"),
    ("gpt-5.4-mini",    "balanced"),
    ("gpt-5.4-nano",    "cheap · fast"),
    ("gpt-5.3-codex",   "coding"),
    ("o3",              "heavy reasoning"),
]


class OpenAI(Provider):
    name = "openai"
    display = "OpenAI"
    api_key_env = "OPENAI_API_KEY"
    description = "GPT, o-series"

    def list_models(self) -> list[ModelInfo]:
        return [
            ModelInfo(id=f"openai/{m}", display=m, note=tag)
            for m, tag in _CURATED
        ]
