"""Tests for ``scripts/refresh_models.py`` — the OpenRouter catalog generator."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "refresh_models",
    Path(__file__).resolve().parents[2] / "scripts" / "refresh_models.py",
)
refresh = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(refresh)


def test_safe_input_reserves_capped_margin() -> None:
    m = {
        "id": "x/y",
        "context_length": 400000,
        "top_provider": {"context_length": 400000, "max_completion_tokens": 128000},
    }
    assert refresh.safe_input_limit(m) == 400000 - 32_768


def test_safe_input_caps_reserve_for_huge_max_completion() -> None:
    m = {
        "id": "minimax/m3",
        "context_length": 1_000_000,
        "top_provider": {"context_length": 1_000_000, "max_completion_tokens": 988_000},
    }
    assert refresh.safe_input_limit(m) == 1_000_000 - 32_768


def test_safe_input_without_completion_reserves_default() -> None:
    assert refresh.safe_input_limit({"id": "a", "context_length": 1_000_000}) == 1_000_000 - 32_768


def test_safe_input_invalid_returns_none() -> None:
    assert refresh.safe_input_limit({"id": "a"}) is None
    assert refresh.safe_input_limit({"id": "a", "context_length": 0}) is None
    assert refresh.safe_input_limit({"id": "a", "context_length": "x"}) is None


def test_build_filters_invalid_and_sorts() -> None:
    models = [
        {"id": "z/last", "context_length": 100},
        {"id": "a/first", "context_length": 200},
        {"context_length": 300},  # no id → dropped
        {"id": "n/none"},  # no context → dropped
    ]
    out = refresh.build(models)
    assert list(out) == ["a/first", "z/last"]
    assert out["a/first"] == 200


def test_build_dedups_keeping_last() -> None:
    models = [
        {"id": "dup/x", "context_length": 100},
        {"id": "dup/x", "context_length": 200},
    ]
    assert refresh.build(models) == {"dup/x": 200}


def test_write_atomic_replaces_without_leftovers(tmp_path: Path) -> None:
    target = tmp_path / "cat.yaml"
    target.write_text("OLD", encoding="utf-8")
    refresh.write_atomic(target, "NEW")
    assert target.read_text(encoding="utf-8") == "NEW"
    assert not list(tmp_path.glob(".tmp-*"))
