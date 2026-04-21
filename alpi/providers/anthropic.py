from __future__ import annotations

import os

from alpi.providers.base import ModelInfo, Provider


_FALLBACK = [
    "claude-opus-4-7",
    "claude-opus-4-6",
    "claude-sonnet-4-6",
    "claude-sonnet-4-5",
    "claude-haiku-4-5",
]

_EXCLUDE_PREFIXES = ("claude-2", "claude-instant", "claude-1")


class Anthropic(Provider):
    name = "anthropic"
    display = "Anthropic"
    api_key_env = "ANTHROPIC_API_KEY"
    description = "Claude models"

    def list_models(self) -> list[ModelInfo]:
        ids = _fetch() or _FALLBACK
        ids = [i for i in ids if not i.startswith(_EXCLUDE_PREFIXES)]
        return [ModelInfo(id=f"anthropic/{i}", display=i) for i in ids]


def _fetch() -> list[str]:
    import httpx
    key = os.environ.get("ANTHROPIC_API_KEY") or ""
    if not key:
        return []
    try:
        with httpx.Client(timeout=3) as c:
            r = c.get(
                "https://api.anthropic.com/v1/models",
                headers={
                    "x-api-key": key,
                    "anthropic-version": "2023-06-01",
                },
            )
            r.raise_for_status()
            data = r.json()
    except Exception:
        return []
    return [m.get("id") for m in data.get("data", []) if m.get("id")]
