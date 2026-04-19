"""OpenRouter provider — fetches the model catalog dynamically."""

from __future__ import annotations

import json
import time
from pathlib import Path

from alf.home import get_home
from alf.providers.base import ModelInfo, Provider

CACHE_TTL_SECONDS = 24 * 3600
TOP_N = 20

# Popular tool-capable models surfaced first. Anything not in this list is
# still reachable via "Enter custom model name".
_POPULAR_PREFIXES = (
    "anthropic/claude-opus",
    "anthropic/claude-sonnet",
    "anthropic/claude-haiku",
    "openai/gpt-5",
    "openai/gpt-4.1",
    "openai/gpt-4o",
    "openai/o3",
    "openai/o1",
    "google/gemini-2.5-pro",
    "google/gemini-2.5-flash",
    "google/gemini-2.0",
    "x-ai/grok",
    "meta-llama/llama-3.3",
    "mistralai/mistral-large",
    "qwen/qwen-2.5",
    "deepseek/deepseek",
    "moonshotai/kimi",
    "xiaomi/mimo",
)


class OpenRouter(Provider):
    name = "openrouter"
    display = "OpenRouter"
    api_key_env = "OPENROUTER_API_KEY"
    description = "200+ models, pay-per-use"

    def list_models(self) -> list[ModelInfo]:
        catalog = _load_catalog()
        tool_models = [m for m in catalog if _supports_tools(m)]

        popular, rest = [], []
        for m in tool_models:
            mid = m.get("id") or ""
            if not mid:
                continue
            if _is_popular(mid):
                popular.append(m)
            else:
                rest.append(m)

        popular.sort(key=lambda m: _popularity_index(m.get("id", "")))
        rest.sort(key=lambda m: (m.get("id") or "").lower())

        rows: list[ModelInfo] = []
        for m in (popular + rest)[:TOP_N]:
            mid = m["id"]
            pricing = m.get("pricing") or {}
            prompt = _fmt_price(pricing.get("prompt"))
            completion = _fmt_price(pricing.get("completion"))
            note = f"in {prompt} / out {completion}" if prompt else ""
            rows.append(ModelInfo(id=f"openrouter/{mid}", display=mid, note=note))
        return rows


def _supports_tools(m: dict) -> bool:
    params = m.get("supported_parameters") or []
    return "tools" in params


def _is_popular(mid: str) -> bool:
    return any(mid.startswith(p) for p in _POPULAR_PREFIXES)


def _popularity_index(mid: str) -> int:
    for i, p in enumerate(_POPULAR_PREFIXES):
        if mid.startswith(p):
            return i
    return len(_POPULAR_PREFIXES)


def _load_catalog() -> list[dict]:
    cache = get_home() / "cache" / "openrouter_models.json"
    cache.parent.mkdir(parents=True, exist_ok=True)
    if cache.exists() and time.time() - cache.stat().st_mtime < CACHE_TTL_SECONDS:
        try:
            return json.loads(cache.read_text()).get("data", [])
        except Exception:
            pass
    return _fetch_and_cache(cache)


def _fetch_and_cache(cache: Path) -> list[dict]:
    import httpx
    try:
        with httpx.Client(timeout=20, follow_redirects=True) as client:
            r = client.get("https://openrouter.ai/api/v1/models")
            r.raise_for_status()
            data = r.json()
        cache.write_text(json.dumps(data))
        return data.get("data", [])
    except Exception:
        return []


def _fmt_price(raw: str | None) -> str:
    if raw is None:
        return ""
    try:
        # OpenRouter prices are dollars per token as a string.
        v = float(raw)
    except (TypeError, ValueError):
        return ""
    if v == 0:
        return "free"
    per_m = v * 1_000_000
    return f"${per_m:.2f}/Mtok"
