"""OpenRouter provider — models tracked per-user in config, not fetched."""

from __future__ import annotations

from alf import config as cfg_mod
from alf.home import get_home
from alf.providers.base import ModelInfo, Provider


class OpenRouter(Provider):
    name = "openrouter"
    display = "OpenRouter"
    api_key_env = "OPENROUTER_API_KEY"
    description = "Any model via openrouter.ai"

    def list_models(self) -> list[ModelInfo]:
        cfg = cfg_mod.load(get_home())
        ids = cfg.providers.get("openrouter", {}).get("models", []) or []
        return [ModelInfo(id=f"openrouter/{i}", display=i) for i in ids if i]
