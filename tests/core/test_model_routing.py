"""Model tiers (fast/deep) — config parsing, resolve_model routing, side-task consumers."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import yaml

from alpi import config as cfg_mod


def _load(tmp_path: Path, data: dict) -> cfg_mod.Config:
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    (home / "config.yaml").write_text(yaml.safe_dump(data))
    return cfg_mod.load(home)


def test_tiers_default_empty_and_tier_resolves_to_main(tmp_path: Path) -> None:
    cfg = _load(tmp_path, {"model": "openrouter/main"})
    assert cfg.tiers.fast.model == ""
    assert cfg.tiers.deep.model == ""
    assert cfg_mod.resolve_model(cfg, tier="fast") == cfg_mod.resolve_model(cfg)
    assert cfg_mod.resolve_model(cfg, tier="deep") == cfg_mod.resolve_model(cfg)


def test_unknown_tier_name_resolves_to_main(tmp_path: Path) -> None:
    cfg = _load(tmp_path, {
        "model": "openrouter/main",
        "tiers": {"fast": {"model": "openrouter/flash"}},
    })
    assert cfg_mod.resolve_model(cfg, tier="turbo") == cfg_mod.resolve_model(cfg)
    assert cfg_mod.resolve_model(cfg, tier="main") == cfg_mod.resolve_model(cfg)
    assert cfg_mod.resolve_model(cfg, tier=None) == cfg_mod.resolve_model(cfg)


def test_configured_tier_resolves_its_model_with_its_own_effort(tmp_path: Path) -> None:
    cfg = _load(tmp_path, {
        "model": "openrouter/main",
        "model_reasoning": {"effort": "high"},
        "tiers": {"fast": {"model": "openrouter/flash", "effort": "low"}},
    })
    fast = cfg_mod.resolve_model(cfg, tier="fast")
    assert fast["model"] == "openrouter/flash"
    assert fast["extra_body"]["reasoning"]["effort"] == "low"
    main = cfg_mod.resolve_model(cfg)
    assert main["model"] == "openrouter/main"
    assert main["extra_body"]["reasoning"]["effort"] == "high"


def test_tier_without_effort_never_inherits_profile_effort(tmp_path: Path) -> None:
    cfg = _load(tmp_path, {
        "model": "openrouter/main",
        "model_reasoning": {"effort": "high"},
        "tiers": {"deep": {"model": "openrouter/big"}},
    })
    deep = cfg_mod.resolve_model(cfg, tier="deep")
    assert deep["model"] == "openrouter/big"
    assert "extra_body" not in deep and "reasoning_effort" not in deep


def test_explicit_model_override_wins_over_tier(tmp_path: Path) -> None:
    cfg = _load(tmp_path, {
        "model": "openrouter/main",
        "tiers": {"fast": {"model": "openrouter/flash"}},
    })
    out = cfg_mod.resolve_model(cfg, model="openrouter/other", tier="fast")
    assert out["model"] == "openrouter/other"


def test_invalid_tier_effort_normalises_to_empty(tmp_path: Path) -> None:
    cfg = _load(tmp_path, {
        "tiers": {"fast": {"model": "openrouter/flash", "effort": "ultra"}},
    })
    assert cfg.tiers.fast.effort == ""


def test_tier_model_helper(tmp_path: Path) -> None:
    cfg = _load(tmp_path, {"tiers": {"deep": {"model": "openrouter/big"}}})
    assert cfg_mod.tier_model(cfg, "deep") == "openrouter/big"
    assert cfg_mod.tier_model(cfg, "fast") == ""
    assert cfg_mod.tier_model(cfg, "main") == ""
    assert cfg_mod.tier_model(cfg, None) == ""


def test_save_round_trips_tiers_and_omits_empty(tmp_path: Path) -> None:
    cfg = _load(tmp_path, {"model": "openrouter/main"})
    cfg.tiers.fast = cfg_mod.TierConfig(model="openrouter/flash", effort="low")
    cfg_mod.save(cfg)
    reloaded = cfg_mod.load(cfg.home)
    assert reloaded.tiers.fast.model == "openrouter/flash"
    assert reloaded.tiers.fast.effort == "low"
    raw = yaml.safe_load(cfg.config_path.read_text())
    assert "deep" not in raw["tiers"]

    cfg.tiers.fast = cfg_mod.TierConfig()
    cfg_mod.save(cfg)
    raw = yaml.safe_load(cfg.config_path.read_text())
    assert "tiers" not in raw


def test_fallback_models_normalised_on_load(tmp_path: Path) -> None:
    cfg = _load(tmp_path, {
        "fallback_models": ["openrouter/a", " openrouter/a ", "", "openrouter/b"],
    })
    assert cfg.fallback_models == ["openrouter/a", "openrouter/b"]
    cfg2 = _load(tmp_path, {"fallback_models": "openrouter/a"})
    assert cfg2.fallback_models == []


def _capture_resolver(monkeypatch) -> dict:
    captured: dict = {}
    real = cfg_mod.resolve_model

    def wrapper(cfg, **kw):
        captured.update(kw)
        return real(cfg, **kw)

    monkeypatch.setattr(cfg_mod, "resolve_model", wrapper)
    return captured


def _fake_completion(text: str = "done") -> SimpleNamespace:
    return SimpleNamespace(
        content=text, tool_calls=[], input_tokens=1, output_tokens=1,
        cost_usd=0.0, raw=None,
    )


def test_memory_reviewer_routes_to_fast_tier(monkeypatch, tmp_path: Path) -> None:
    from alpi import review

    captured = _capture_resolver(monkeypatch)
    monkeypatch.setattr("alpi.llm.complete", lambda **kw: _fake_completion())
    cfg = _load(tmp_path, {"model": "openrouter/main"})
    saved = review._run_review(cfg.home, cfg, [{"role": "user", "content": "hi"}])
    assert saved == 0
    assert captured.get("tier") == "fast"


def test_identity_draft_routes_to_fast_tier(monkeypatch, tmp_path: Path) -> None:
    from alpi import identity
    from alpi.home import agent_path

    captured = _capture_resolver(monkeypatch)
    monkeypatch.setattr("alpi.llm.complete", lambda **kw: _fake_completion("a bio"))
    cfg = _load(tmp_path, {"model": "openrouter/main"})
    ap = agent_path(cfg.home)
    ap.parent.mkdir(parents=True, exist_ok=True)
    ap.write_text("I am a test persona.")
    assert identity.draft_bio_from_agent(cfg.home, cfg) == "a bio"
    assert captured.get("tier") == "fast"


def test_delegate_routes_requested_tier(monkeypatch, tmp_home_no_env: Path) -> None:
    from alpi.tools.delegate import Delegate

    captured = _capture_resolver(monkeypatch)
    monkeypatch.setattr("alpi.llm.complete", lambda **kw: _fake_completion())
    out = Delegate().run(goal="rename files", tier="fast")
    assert out.ok
    assert captured.get("tier") == "fast"


def test_delegate_rejects_unknown_tier(tmp_home_no_env: Path) -> None:
    from alpi.tools.delegate import Delegate

    out = Delegate().run(goal="x", tier="turbo")
    assert not out.ok
    assert "tier" in out.error


def test_research_depth_maps_to_tier(monkeypatch, tmp_home_no_env: Path) -> None:
    from alpi.tools.research import Research

    captured = _capture_resolver(monkeypatch)
    monkeypatch.setattr("alpi.llm.complete", lambda **kw: _fake_completion("report"))
    out = Research().run(brief="what is X", depth="fast")
    assert out.ok
    assert captured.get("tier") == "fast"
    out = Research().run(brief="what is X", depth="deep")
    assert out.ok
    assert captured.get("tier") == "deep"
    out = Research().run(brief="what is X", depth="quick")
    assert not out.ok and "depth" in out.error
    out = Research().run(brief="what is X", depth="normal")
    assert out.ok
    assert captured.get("tier") == "normal"
    out = Research().run(brief="what is X", depth="shallow")
    assert not out.ok and "depth" in out.error


def test_web_extract_override_accepts_tier_reference(monkeypatch, tmp_path: Path) -> None:
    cfg = _load(tmp_path, {
        "model": "openrouter/main",
        "tools": {"web_extract": {"model": "fast"}},
        "tiers": {"fast": {"model": "openrouter/flash"}},
    })
    seen: dict = {}

    def fake_complete(**kw):
        seen["model"] = kw.get("model")
        return _fake_completion("summary")

    monkeypatch.setattr("alpi.llm.complete", fake_complete)
    monkeypatch.setattr("alpi.config.load", lambda home: cfg)
    monkeypatch.setattr("alpi.home.get_home", lambda: cfg.home)
    from alpi.tools.web_extract import WebExtract
    from alpi.tools.base import ToolResult
    monkeypatch.setattr(
        "alpi.tools.web_fetch.WebFetch.run",
        lambda self, **kw: ToolResult(ok=True, output="page body"),
    )
    monkeypatch.setattr("alpi.tools._sandbox.require_network", lambda name: None)
    out = WebExtract().run(url="https://example.com")
    assert out.ok
    assert seen["model"] == "openrouter/flash"


def test_web_extract_tier_reference_unconfigured_uses_main(monkeypatch, tmp_path: Path) -> None:
    cfg = _load(tmp_path, {
        "model": "openrouter/main",
        "tools": {"web_extract": {"model": "fast"}},
    })
    seen: list = []

    def fake_complete(**kw):
        seen.append(kw.get("model"))
        return _fake_completion("summary")

    monkeypatch.setattr("alpi.llm.complete", fake_complete)
    monkeypatch.setattr("alpi.config.load", lambda home: cfg)
    monkeypatch.setattr("alpi.home.get_home", lambda: cfg.home)
    from alpi.tools.web_extract import WebExtract
    from alpi.tools.base import ToolResult
    monkeypatch.setattr(
        "alpi.tools.web_fetch.WebFetch.run",
        lambda self, **kw: ToolResult(ok=True, output="page body"),
    )
    monkeypatch.setattr("alpi.tools._sandbox.require_network", lambda name: None)
    out = WebExtract().run(url="https://example.com")
    assert out.ok
    assert seen == ["openrouter/main"]
    assert "[fallback:" not in out.output
