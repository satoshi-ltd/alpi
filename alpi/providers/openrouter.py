"""OpenRouter provider — models tracked per-user in config, not fetched."""

from __future__ import annotations

from alpi import config as cfg_mod
from alpi.home import get_home
from alpi.providers.base import ModelInfo, Provider


class OpenRouter(Provider):
    name = "openrouter"
    display = "OpenRouter"
    api_key_env = "OPENROUTER_API_KEY"
    description = "Any model via openrouter.ai"

    def list_models(self) -> list[ModelInfo]:
        cfg = cfg_mod.load(get_home())
        ids = cfg.providers.get("openrouter", {}).get("models", []) or []
        return [ModelInfo(id=f"openrouter/{i}", display=i) for i in ids if i]
