from __future__ import annotations

import os

from alpi.providers.base import ModelInfo, Provider


_FALLBACK = [
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4.1",
    "gpt-4.1-mini",
    "o3",
    "o3-mini",
    "o1",
]

_EXCLUDE_PREFIXES = (
    "dall-e", "whisper", "text-embedding", "tts-", "omni-moderation",
    "gpt-3.5", "babbage", "davinci", "text-davinci", "code-davinci",
)


class OpenAI(Provider):
    name = "openai"
    display = "OpenAI"
    api_key_env = "OPENAI_API_KEY"
    description = "GPT, o-series"

    def list_models(self) -> list[ModelInfo]:
        ids = _fetch() or _FALLBACK
        ids = [i for i in ids if not i.startswith(_EXCLUDE_PREFIXES)]
        return [
            ModelInfo(id=f"openai/{i}", display=i)
            for i in sorted(ids, reverse=True)
        ]


def _fetch() -> list[str]:
    import httpx
    key = os.environ.get("OPENAI_API_KEY") or ""
    if not key:
        return []
    try:
        with httpx.Client(timeout=3) as c:
            r = c.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {key}"},
            )
            r.raise_for_status()
            data = r.json()
    except Exception:
        return []
    return [m.get("id") for m in data.get("data", []) if m.get("id")]
