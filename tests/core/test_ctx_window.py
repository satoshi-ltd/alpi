"""Tests for ``alpi.ctx_window`` — generated openrouter limits + litellm fallback."""

from __future__ import annotations

import importlib
import sys
import types
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


def test_resolve_from_openrouter_catalog(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        ctx_window, "_openrouter_limits",
        lambda: {"deepseek/deepseek-v4-flash": 934464},
    )
    got = ctx_window.resolve(tmp_path, _Cfg(), "openrouter/deepseek/deepseek-v4-flash")
    assert got == 934464


def test_resolve_openrouter_native_id(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        ctx_window, "_openrouter_limits", lambda: {"openrouter/owl-alpha": 786612},
    )
    assert ctx_window.resolve(tmp_path, _Cfg(), "openrouter/owl-alpha") == 786612


def test_resolve_falls_back_to_litellm(monkeypatch, tmp_path: Path) -> None:
    fake = types.ModuleType("litellm")
    fake.model_cost = {"openai/gpt-4o-mini": {"max_input_tokens": 128000}}
    monkeypatch.setitem(sys.modules, "litellm", fake)
    assert ctx_window.resolve(tmp_path, _Cfg(), "openai/gpt-4o-mini") == 128000


def test_resolve_fallback_when_unknown(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(ctx_window, "_openrouter_limits", lambda: {})
    fake = types.ModuleType("litellm")
    fake.model_cost = {}
    monkeypatch.setitem(sys.modules, "litellm", fake)
    assert ctx_window.resolve(tmp_path, _Cfg(), "openrouter/nope/nope") == 200_000


def test_committed_catalog_is_positive_int_map() -> None:
    limits = ctx_window._openrouter_limits()
    assert limits
    assert all(isinstance(v, int) and v > 0 for v in limits.values())


def test_committed_catalog_includes_glm_5_3_flash_safe_input_limit() -> None:
    assert ctx_window._openrouter_limits()["z-ai/glm-5.3-flash"] == 1_015_808
