"""Tests for ``alpi.ctx_window``."""

from __future__ import annotations

import importlib
import types
import sys
from pathlib import Path

from alpi import ctx_window


class _Cfg:
    def __init__(self, providers: dict | None = None) -> None:
        self.providers = providers or {}


def test_resolve_empty_model_uses_fallback(tmp_path: Path) -> None:
    assert ctx_window.resolve(tmp_path, _Cfg(), "") == 200_000


def test_resolve_prefers_ollama_provider(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, str]] = []

    def fake_resolve_num_ctx(base_url: str, model: str) -> int:
        calls.append((base_url, model))
        return 12345

    ollama_mod = importlib.import_module("alpi.providers.ollama")
    monkeypatch.setattr(ollama_mod, "resolve_num_ctx", fake_resolve_num_ctx)
    cfg = _Cfg({"ollama": [{"name": "local", "url": "http://localhost:11434"}]})
    assert ctx_window.resolve(tmp_path, cfg, "local/llama3.1") == 12345
    assert calls == [("http://localhost:11434", "llama3.1")]


def test_resolve_uses_litellm_model_cost(monkeypatch, tmp_path: Path) -> None:
    fake = types.ModuleType("litellm")
    fake.model_cost = {
        "openai/gpt-4o-mini": {"max_input_tokens": 128000},
    }
    monkeypatch.setitem(sys.modules, "litellm", fake)
    assert ctx_window.resolve(tmp_path, _Cfg(), "openai/gpt-4o-mini") == 128000


def test_resolve_falls_back_when_cost_lookup_missing(monkeypatch, tmp_path: Path) -> None:
    fake = types.ModuleType("litellm")
    fake.model_cost = {}
    monkeypatch.setitem(sys.modules, "litellm", fake)
    assert ctx_window.resolve(tmp_path, _Cfg(), "missing/model") == 200_000
