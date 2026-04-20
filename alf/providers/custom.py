"""Custom OpenAI-compatible endpoints (Ollama, LM Studio, vLLM, ...)."""

from __future__ import annotations

from dataclasses import dataclass

from alf.providers.base import ModelInfo, Provider


@dataclass
class CustomProvider(Provider):
    name: str
    display: str
    base_url: str
    api_key_env: str = ""
    description: str = "OpenAI-compatible endpoint"

    def list_models(self) -> list[ModelInfo]:
        return _fetch_models(self.base_url, self.api_key_env, self.name)

    def has_key(self) -> bool:
        # No key required for fully open endpoints; True means "callable".
        if not self.api_key_env:
            return True
        import os
        return bool(os.environ.get(self.api_key_env))


def _fetch_models(base_url: str, api_key_env: str, prefix: str) -> list[ModelInfo]:
    import os

    import httpx

    headers = {}
    if api_key_env and os.environ.get(api_key_env):
        headers["Authorization"] = f"Bearer {os.environ[api_key_env]}"

    try:
        with httpx.Client(timeout=10, follow_redirects=True) as client:
            r = client.get(base_url.rstrip("/") + "/models", headers=headers)
            r.raise_for_status()
            data = r.json()
    except Exception:
        return []

    raw = data.get("data", data) if isinstance(data, dict) else []
    rows: list[ModelInfo] = []
    for m in raw:
        mid = m.get("id") if isinstance(m, dict) else None
        if mid:
            rows.append(ModelInfo(id=f"{prefix}/{mid}", display=mid))
    return rows
