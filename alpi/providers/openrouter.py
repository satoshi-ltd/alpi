"""OpenRouter provider — saved and curated models, without a network fetch."""

from __future__ import annotations

from alpi import config as cfg_mod
from alpi.home import get_home
from alpi.providers.base import ModelInfo, Provider
from alpi.providers.curated import load_curated


class OpenRouter(Provider):
    name = "openrouter"
    display = "OpenRouter"
    api_key_env = "OPENROUTER_API_KEY"
    description = "Any model via openrouter.ai"

    def list_models(self) -> list[ModelInfo]:
        cfg = cfg_mod.load(get_home())
        saved = cfg.providers.get("openrouter", {}).get("models", []) or []
        rows = [{"id": model} for model in saved if model]
        rows.extend(load_curated("openrouter"))
        seen = set()
        return [
            ModelInfo(
                id=f"openrouter/{row['id']}",
                display=row["id"],
                note=row.get("note", ""),
            )
            for row in rows
            if row.get("id") and not (row["id"] in seen or seen.add(row["id"]))
        ]
