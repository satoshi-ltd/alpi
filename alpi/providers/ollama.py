"""Ollama providers — each connection is a named endpoint."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import httpx

from alpi.providers.base import ModelInfo, Provider

DEFAULT_URL = "http://localhost:11434"

_IS_OLLAMA_CACHE: dict[str, bool] = {}
_NUM_CTX_CACHE: dict[tuple[str, str], int] = {}
_DEFAULT_NUM_CTX = 32768


@dataclass
class OllamaProvider(Provider):
    name: str
    url: str
    display: str = ""
    api_key_env: str = ""
    description: str = "local models via ollama.com"

    def __post_init__(self) -> None:
        if not self.display:
            self.display = self.name

    def has_key(self, env: dict[str, str] | None = None) -> bool:
        return True

    def list_models(self) -> list[ModelInfo]:
        try:
            with httpx.Client(timeout=2.0) as client:
                r = client.get(_root(self.url) + "/api/tags")
                r.raise_for_status()
                data = r.json() or {}
        except Exception:
            return []
        rows: list[ModelInfo] = []
        for m in data.get("models") or []:
            mid = m.get("name") or m.get("model") or ""
            if mid:
                size = m.get("size") or 0
                note = _fmt_size(size) if size else ""
                rows.append(ModelInfo(
                    id=f"{self.name}/{mid}", display=mid, note=note,
                ))
        return rows


def connections(entries: Iterable[dict]) -> list[OllamaProvider]:
    out: list[OllamaProvider] = []
    for entry in entries or []:
        name = (entry.get("name") or "").strip()
        url = (entry.get("url") or "").strip().rstrip("/")
        if not name or not url:
            continue
        out.append(OllamaProvider(name=name, url=url))
    return out


def _fmt_size(n: int) -> str:
    gb = n / (1024 ** 3)
    return f"{gb:.1f} GB" if gb >= 0.1 else f"{n / (1024 ** 2):.0f} MB"


def _root(base_url: str) -> str:
    url = base_url.rstrip("/")
    if url.endswith("/v1"):
        url = url[:-3]
    return url


def is_ollama(base_url: str) -> bool:
    if not base_url:
        return False
    if base_url in _IS_OLLAMA_CACHE:
        return _IS_OLLAMA_CACHE[base_url]
    ok = False
    try:
        with httpx.Client(timeout=1.0) as client:
            r = client.get(_root(base_url) + "/api/tags")
            ok = r.status_code == 200 and "models" in (r.json() or {})
    except Exception:
        ok = False
    _IS_OLLAMA_CACHE[base_url] = ok
    return ok


def resolve_num_ctx(base_url: str, model: str) -> int:
    key = (base_url, model)
    if key in _NUM_CTX_CACHE:
        return _NUM_CTX_CACHE[key]
    value = _DEFAULT_NUM_CTX
    try:
        with httpx.Client(timeout=2.0) as client:
            r = client.post(_root(base_url) + "/api/show", json={"name": model})
            r.raise_for_status()
            data = r.json() or {}
        params = data.get("parameters", "") or ""
        for line in str(params).splitlines():
            parts = line.strip().split()
            if len(parts) == 2 and parts[0] == "num_ctx":
                value = int(parts[1])
                break
        else:
            info = data.get("model_info", {}) or {}
            for k, v in info.items():
                if k.endswith(".context_length") and isinstance(v, int):
                    value = v
                    break
    except Exception:
        pass
    _NUM_CTX_CACHE[key] = value
    return value
