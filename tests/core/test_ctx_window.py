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


def test_a_same_model_suffix_does_not_cost_it_its_window(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        ctx_window, "_openrouter_limits", lambda: {"z-ai/glm-5.3-flash": 1_015_808},
    )
    for suffix in ("nitro", "floor", "online", "exacto"):
        got = ctx_window.resolve(tmp_path, _Cfg(), f"openrouter/z-ai/glm-5.3-flash:{suffix}")
        assert got == 1_015_808, suffix


def test_a_variant_the_catalog_carries_answers_for_itself(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        ctx_window, "_openrouter_limits",
        lambda: {"z-ai/glm-5.3-flash": 1_015_808, "z-ai/glm-5.3-flash:batch": 64_000},
    )
    got = ctx_window.resolve(tmp_path, _Cfg(), "openrouter/z-ai/glm-5.3-flash:batch")
    assert got == 64_000


def test_an_unknown_suffix_is_not_stripped(monkeypatch, tmp_path: Path) -> None:
    # `:free` is a real variant that can serve a smaller window; guessing the paid one
    # would overestimate, which is the direction that overflows a turn.
    monkeypatch.setattr(
        ctx_window, "_openrouter_limits", lambda: {"z-ai/glm-5.3-flash": 1_015_808},
    )
    fake = types.ModuleType("litellm")
    fake.model_cost = {}
    monkeypatch.setitem(sys.modules, "litellm", fake)
    assert ctx_window.resolve(tmp_path, _Cfg(), "openrouter/z-ai/glm-5.3-flash:free") == 200_000


def test_an_ollama_tag_is_never_mistaken_for_a_stripped_suffix(monkeypatch, tmp_path: Path) -> None:
    seen: list[tuple[str, str]] = []

    def fake_resolve_num_ctx(base_url: str, model: str) -> int:
        seen.append((base_url, model))
        return 8192

    ollama_mod = importlib.import_module("alpi.providers.ollama")
    monkeypatch.setattr(ollama_mod, "resolve_num_ctx", fake_resolve_num_ctx)
    cfg = _Cfg({"ollama": [{"name": "local", "url": "http://localhost:11434"}]})
    assert ctx_window.resolve(tmp_path, cfg, "local/llama3:8b") == 8192
    assert seen == [("http://localhost:11434", "llama3:8b")]


def test_the_committed_catalog_has_no_row_for_a_stripped_suffix() -> None:
    # If one ever appears, the exact match wins and the strip becomes dead code.
    bad = sorted(
        k for k in ctx_window._openrouter_limits()
        if k.rpartition(":")[2] in ctx_window._SAME_WINDOW_SUFFIXES
    )
    assert bad == []
