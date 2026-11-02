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
    cfg.tools.read_image.model = "openrouter/vision"
    assert "vision: openrouter/vision" in model_selector.tiers_status(cfg)
    assert "fallbacks: —" in model_selector.tiers_status(cfg)


def test_fallbacks_status_counts_and_lists_the_chain(tmp_path: Path) -> None:
    cfg = config.Config(home=tmp_path, model="openrouter/main")
    assert model_selector.fallbacks_status(cfg) == "(none)"
    cfg.fallback_models = ["openrouter/a", "openai/b"]
    assert model_selector.fallbacks_status(cfg) == "openrouter/a → openai/b"
    assert "fallbacks: 2" in model_selector.tiers_status(cfg)
    assert "not set" not in model_selector.tiers_status(cfg)


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


def test_configure_vision_pick_and_clear(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "h"
    home.mkdir()
    cfg = config.load(home)

    choices = iter(["pick", "clear"])
    monkeypatch.setattr("alpi.ui.menu", lambda *a, **kw: next(choices))
    monkeypatch.setattr("alpi.ui.ok_and_wait", lambda *a, **kw: None)
    monkeypatch.setattr(model_selector, "_pick_provider", lambda cfg: object())
    monkeypatch.setattr(model_selector, "_ensure_key", lambda cfg, p: None)
    monkeypatch.setattr(
        model_selector, "_pick_model", lambda p, cfg: "openrouter/deepseek/vision",
    )

    model_selector._configure_vision(cfg)
    reloaded = config.load(home)
    assert reloaded.tools.read_image.model == "openrouter/deepseek/vision"
    assert reloaded.providers["openrouter"]["models"][0] == "deepseek/vision"

    model_selector._configure_vision(reloaded)
    assert config.load(home).tools.read_image.model == ""


def _fallback_home(tmp_path: Path, chain: list[str]) -> Path:
    home = tmp_path / "h"
    home.mkdir()
    cfg = config.load(home)
    cfg.model = "openrouter/main"
    cfg.fallback_models = chain
    config.save(cfg)
    return home


def _patch_picker(monkeypatch, menus, picked) -> list[str]:
    failures: list[str] = []
    monkeypatch.setattr("alpi.ui.menu", lambda *a, **kw: next(menus))
    monkeypatch.setattr("alpi.ui.ok_and_wait", lambda *a, **kw: None)
    monkeypatch.setattr("alpi.ui.fail_and_wait", lambda msg: failures.append(msg))
    monkeypatch.setattr(model_selector, "_pick_provider", lambda cfg: object())
    monkeypatch.setattr(model_selector, "_ensure_key", lambda cfg, p: None)
    monkeypatch.setattr(model_selector, "_pick_model", lambda p, cfg: next(picked))
    return failures


def test_configure_fallbacks_adds_in_order_and_refuses_main_and_duplicates(
    tmp_path: Path, monkeypatch,
) -> None:
    home = _fallback_home(tmp_path, [])
    menus = iter(["add", "add", "add", "add", None])
    picked = iter(["openrouter/a", "openai/b", "openrouter/main", "openrouter/a"])
    failures = _patch_picker(monkeypatch, menus, picked)

    model_selector._configure_fallbacks(config.load(home))

    reloaded = config.load(home)
    assert reloaded.fallback_models == ["openrouter/a", "openai/b"]
    assert reloaded.providers["openrouter"]["models"][0] == "a"
    assert len(failures) == 2
    assert "main model" in failures[0]
    assert "already" in failures[1]


def test_configure_fallbacks_reorders_removes_and_clears(tmp_path: Path, monkeypatch) -> None:
    home = _fallback_home(tmp_path, ["openrouter/a", "openai/b", "openai/c"])
    menus = iter([
        ("entry", 2), "up",
        ("entry", 0), "remove",
        None,
    ])
    _patch_picker(monkeypatch, menus, iter([]))
    model_selector._configure_fallbacks(config.load(home))
    assert config.load(home).fallback_models == ["openai/c", "openai/b"]

    _patch_picker(monkeypatch, iter(["clear", None]), iter([]))
    model_selector._configure_fallbacks(config.load(home))
    assert config.load(home).fallback_models == []
    assert "fallback_models" not in (home / "config.yaml").read_text()


def test_edit_fallback_offers_only_valid_moves(tmp_path: Path, monkeypatch) -> None:
    home = _fallback_home(tmp_path, ["openrouter/a", "openai/b"])
    seen: list[list[str]] = []

    def menu(title, items, **kw):
        seen.append([value for _label, value, _status in items])
        return None

    monkeypatch.setattr("alpi.ui.menu", menu)
    cfg = config.load(home)
    model_selector._edit_fallback(cfg, 0)
    model_selector._edit_fallback(cfg, 1)
    assert seen == [["down", "remove"], ["up", "remove"]]
    assert config.load(home).fallback_models == ["openrouter/a", "openai/b"]


def test_run_tiers_routes_to_fallback_menu(tmp_path: Path, monkeypatch) -> None:
    home = _fallback_home(tmp_path, [])
    calls: list[str] = []
    menus = iter(["fallbacks", None])
    monkeypatch.setattr("alpi.ui.menu", lambda *a, **kw: next(menus))
    monkeypatch.setattr(model_selector, "_configure_fallbacks", lambda cfg: calls.append("fb"))
    model_selector.run_tiers(config.load(home))
    assert calls == ["fb"]
