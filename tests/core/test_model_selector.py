"""Tests for model-selector helpers."""

from __future__ import annotations

from pathlib import Path

from alpi import config, model_selector


def test_remember_openrouter_model_moves_suffix_to_front(tmp_path: Path) -> None:
    cfg = config.Config(
        home=tmp_path,
        model="",
        providers={"openrouter": {"models": ["old", "kept", "new"]}},
    )
    model_selector._remember_openrouter_model(cfg, "openrouter/new")
    assert cfg.providers["openrouter"]["models"] == ["new", "old", "kept"]


def test_remember_openrouter_model_ignores_other_providers(tmp_path: Path) -> None:
    cfg = config.Config(home=tmp_path, model="", providers={"openrouter": {"models": ["a"]}})
    model_selector._remember_openrouter_model(cfg, "anthropic/claude")
    assert cfg.providers["openrouter"]["models"] == ["a"]


def test_append_env_replaces_existing_key(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("ALPHA=1\nBETA=2\n")

    model_selector._append_env(env_path, "BETA", "3")

    assert env_path.read_text() == "ALPHA=1\nBETA=3\n"


def test_append_env_adds_missing_key(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("ALPHA=1\n")

    model_selector._append_env(env_path, "BETA", "2")

    assert env_path.read_text() == "ALPHA=1\nBETA=2\n"


def test_remove_env_key_deletes_only_one_line(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("ALPHA=1\nBETA=2\nGAMMA=3\n")

    model_selector._remove_env_key(env_path, "BETA")

    assert env_path.read_text() == "ALPHA=1\nGAMMA=3\n"
