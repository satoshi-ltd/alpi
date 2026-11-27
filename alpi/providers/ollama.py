"""Ollama providers — each connection is a named endpoint."""

from __future__ import annotations

import contextlib
import contextvars
import json
import time
from dataclasses import dataclass
from typing import Iterable

import httpx

from alpi.providers.base import ModelInfo, Provider

DEFAULT_URL = "http://localhost:11434"

_NUM_CTX_CACHE: dict[tuple[str, str], int] = {}
_NUM_CTX_MISS: dict[tuple[str, str], float] = {}
_TURN_SIZES: contextvars.ContextVar[dict[tuple[str, str], int] | None] = contextvars.ContextVar("alpi_ollama_turn_sizes", default=None)
_THINKING_CACHE: dict[tuple[str, str], tuple[bool, float]] = {}
_THINKING_MISS_TTL = 30.0
_NUM_CTX_MISS_TTL = 30.0
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


@contextlib.contextmanager
def one_size_per_turn():
    token = _TURN_SIZES.set({})
    try:
        yield
    finally:
        _TURN_SIZES.reset(token)


def resolve_num_ctx(base_url: str, model: str) -> int:
    key = (_root(base_url), model)
    turn = _TURN_SIZES.get()
    if turn is None:
        return _num_ctx(key)
    # The compaction check and the request of one turn must agree, even when a failed lookup recovers between them.
    if key not in turn:
        turn[key] = _num_ctx(key)
    return turn[key]


def _num_ctx(key: tuple[str, str]) -> int:
    model = key[1]
    if key in _NUM_CTX_CACHE:
        return _NUM_CTX_CACHE[key]
    if time.monotonic() - _NUM_CTX_MISS.get(key, float("-inf")) < _NUM_CTX_MISS_TTL:
        return _DEFAULT_NUM_CTX
    value = _DEFAULT_NUM_CTX
    try:
        with httpx.Client(timeout=2.0) as client:
            r = client.post(key[0] + "/api/show", json={"name": model})
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
                    # The model's maximum is a memory budget the host may not have; only a Modelfile num_ctx goes past the default.
                    value = min(v, _DEFAULT_NUM_CTX)
                    break
    except Exception:
        # Never pinned: the size is sent to the server, so a guess kept for the process would outlive the outage.
        _NUM_CTX_MISS[key] = time.monotonic()
        return _DEFAULT_NUM_CTX
    _NUM_CTX_CACHE[key] = value
    return value


def supports_thinking(base_url: str, model: str) -> bool:
    key = (base_url, model)
    cached = _THINKING_CACHE.get(key)
    if cached and (cached[0] or time.monotonic() - cached[1] < _THINKING_MISS_TTL):
        return cached[0]
    value = False
    try:
        with httpx.Client(timeout=2.0) as client:
            r = client.post(_root(base_url) + "/api/show", json={"name": model})
            r.raise_for_status()
            value = "thinking" in ((r.json() or {}).get("capabilities") or [])
    except Exception:
        pass
    _THINKING_CACHE[key] = (value, time.monotonic())
    return value


def litellm_id(model: str) -> str:
    from alpi.llm import litellm_ready
    litellm = litellm_ready()
    full = f"ollama_chat/{model}"
    # LiteLLM asks localhost:11434 about an unlisted Ollama model on every capability check and call, and register_model asks too.
    litellm.model_cost.setdefault(full, {
        "litellm_provider": "ollama_chat", "mode": "chat",
        "input_cost_per_token": 0.0, "output_cost_per_token": 0.0,
    })
    return full


def _wire_call(call: dict) -> dict:
    function = dict(call["function"]) if isinstance(call.get("function"), dict) else {}
    arguments = function.get("arguments")
    try:
        parsed = arguments if isinstance(arguments, dict) else json.loads(arguments or "")
    except (TypeError, ValueError):
        parsed = None
    function["arguments"] = json.dumps(parsed) if isinstance(parsed, dict) else "{}"
    return {**call, "type": "function", "function": function}


def call_kwargs(kwargs: dict) -> dict:
    model = str(kwargs.get("model") or "")
    base = kwargs.get("api_base")
    if not base or not model.startswith("ollama_chat/"):
        return kwargs
    # LiteLLM's Ollama route parses every stored tool call and fails the request on one that is not a typed JSON object.
    messages = [
        {**m, "tool_calls": [_wire_call(c) for c in m["tool_calls"] if isinstance(c, dict)]}
        if isinstance(m, dict) and isinstance(m.get("tool_calls"), list) and m["tool_calls"] else m
        for m in kwargs.get("messages") or []
    ]
    return {**kwargs, "messages": messages, "num_ctx": resolve_num_ctx(base, model.split("/", 1)[1])}
