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


def test_any_saved_keys_reads_explicit_env(tmp_path: Path) -> None:
    """The "Remove keys" affordance must light up when the *profile* has saved keys, even if the process env is empty (daemon never inherits the profile's secrets)."""
    from alpi import providers as prov_mod

    builtin = prov_mod.builtin()
    # With explicit empty env: nothing saved → no affordance.
    assert model_selector._any_saved_keys(builtin, env={}) is False
    # With an OpenAI key in the profile env: affordance shows.
    key_env_name = next(p.api_key_env for p in builtin if p.name == "openai")
    assert model_selector._any_saved_keys(builtin, env={key_env_name: "x"}) is True


def test_tier_status_and_tiers_status(tmp_path: Path) -> None:
    cfg = config.Config(home=tmp_path, model="openrouter/main")
    assert model_selector.tier_status(cfg.tiers.fast) == "(main model)"
    assert "not set" in model_selector.tiers_status(cfg)
    cfg.tiers.fast = config.TierConfig(model="openrouter/flash", effort="low")
    assert model_selector.tier_status(cfg.tiers.fast) == "openrouter/flash · effort low"
    assert "fast: openrouter/flash" in model_selector.tiers_status(cfg)
    assert "deep: —" in model_selector.tiers_status(cfg)


def test_configure_tier_clear_resets_and_saves(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "h"
    home.mkdir()
    cfg = config.load(home)
    cfg.model = "openrouter/main"
    cfg.tiers.deep = config.TierConfig(model="openrouter/big", effort="high")
    config.save(cfg)

    monkeypatch.setattr("alpi.ui.menu", lambda *a, **kw: "clear")
    monkeypatch.setattr("alpi.ui.ok_and_wait", lambda *a, **kw: None)
    model_selector._configure_tier(cfg, "deep")

    reloaded = config.load(home)
    assert reloaded.tiers.deep.model == ""
    assert reloaded.tiers.deep.effort == ""


def test_configure_tier_pick_sets_model_and_effort(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "h"
    home.mkdir()
    cfg = config.load(home)
    cfg.model = "openrouter/main"
    config.save(cfg)

    menus = iter(["pick", "low"])
    monkeypatch.setattr("alpi.ui.menu", lambda *a, **kw: next(menus))
    monkeypatch.setattr("alpi.ui.ok_and_wait", lambda *a, **kw: None)
    monkeypatch.setattr(model_selector, "_pick_provider", lambda cfg: object())
    monkeypatch.setattr(model_selector, "_ensure_key", lambda cfg, p: None)
    monkeypatch.setattr(model_selector, "_pick_model", lambda p, cfg: "openrouter/flash")
    model_selector._configure_tier(cfg, "fast")

    reloaded = config.load(home)
    assert reloaded.tiers.fast.model == "openrouter/flash"
    assert reloaded.tiers.fast.effort == "low"
