"""MC.1 — reasoning_effort plumbing: config roundtrip, helper, resolve_model."""

from __future__ import annotations

from pathlib import Path

import pytest

from alpi import config as cfg_mod
from alpi.providers.reasoning import (
    merge_into_kwargs,
    normalise_effort,
    reasoning_kwargs,
    supports_reasoning,
)


@pytest.mark.parametrize("raw, expected", [
    ("low",    "low"),
    ("MEDIUM", "medium"),
    ("High",   "high"),
    ("off",    ""),
    ("none",   ""),
    ("",       ""),
    (None,     ""),
    ("wibble", ""),
    (123,      ""),
])
def test_normalise_effort_canonicalises_or_drops(raw, expected) -> None:
    assert normalise_effort(raw) == expected


@pytest.mark.parametrize("model", [
    "openai/o3-mini",
    "openai/o4-mini",
    "openai/gpt-5.4-mini",      # curated catalog
    "openai/gpt-5.4-nano",      # curated catalog
    "openai/gpt-5.5",           # curated catalog
    "openai/gpt-5.5-pro",       # curated catalog
    "openai/gpt-5",             # custom-typed (catalog miss → regex fallback)
    "openai/gpt-5-mini",        # custom-typed (regex fallback)
    "anthropic/claude-sonnet-4-6",
    "anthropic/claude-opus-4",
    "google/gemini-2.5-pro",
    "deepseek/deepseek-r1",
    "openrouter/openai/o3-mini",
    "openrouter/anthropic/claude-sonnet-4-6",
])
def test_supports_reasoning_true_for_known_models(model) -> None:
    assert supports_reasoning(model) is True


@pytest.mark.parametrize("model", [
    "",
    "openai/gpt-4o",
    "openai/gpt-4o-mini",
    "anthropic/claude-3.5-sonnet",
    "anthropic/claude-3-haiku",
    "google/gemini-1.5-pro",
    "google/gemini-2.0-flash",
    "ollama/llama-3.3-70b",
    "groq/llama-3.1-70b",
])
def test_supports_reasoning_false_for_known_unsupported_direct(model) -> None:
    assert supports_reasoning(model) is False


def test_supports_reasoning_consults_curated_catalog() -> None:
    """The catalog (`curated_models.yaml`) is the source of truth for openai /
    anthropic. Every curated entry flagged `reasoning: true` must resolve to
    True so the wizard / settings always offer the dropdown for picked models."""
    from alpi.providers.curated import load_curated
    for provider in ("openai", "anthropic"):
        for entry in load_curated(provider):
            if entry.get("reasoning"):
                qualified = f"{provider}/{entry['id']}"
                assert supports_reasoning(qualified) is True, qualified


@pytest.mark.parametrize("model", [
    "openrouter/openai/gpt-4o",
    "openrouter/openai/gpt-4o-mini",
    "openrouter/anthropic/claude-3-haiku",
    "openrouter/some/weird-custom-route",
    "openrouter/x/y",
])
def test_openrouter_models_always_report_supported(model) -> None:
    """OpenRouter silently ignores ``reasoning`` when the upstream doesn't
    support it, so we always show the dropdown for ``openrouter/...`` models
    and let the user decide. The microcopy in the wizard explains the no-op."""
    assert supports_reasoning(model) is True


def test_reasoning_kwargs_returns_empty_when_effort_is_off() -> None:
    assert reasoning_kwargs("openai/o3-mini", "") == {}
    assert reasoning_kwargs("openai/o3-mini", "off") == {}


def test_reasoning_kwargs_returns_empty_when_model_unsupported() -> None:
    assert reasoning_kwargs("openai/gpt-4o", "high") == {}


def test_reasoning_kwargs_direct_provider_uses_top_level_param() -> None:
    assert reasoning_kwargs("openai/o3-mini", "high") == {"reasoning_effort": "high"}
    assert reasoning_kwargs("anthropic/claude-sonnet-4-6", "medium") == {
        "reasoning_effort": "medium",
    }


def test_reasoning_kwargs_openrouter_uses_extra_body_shape() -> None:
    assert reasoning_kwargs("openrouter/openai/o3-mini", "low") == {
        "extra_body": {"reasoning": {"effort": "low"}},
    }


def test_merge_into_kwargs_preserves_ollama_extra_body() -> None:
    base = {"model": "openai/llama-3.3-70b", "extra_body": {"options": {"num_ctx": 32000}}}
    extra = {"extra_body": {"reasoning": {"effort": "medium"}}}
    merged = merge_into_kwargs(base, extra)
    assert merged["extra_body"]["options"] == {"num_ctx": 32000}
    assert merged["extra_body"]["reasoning"] == {"effort": "medium"}


def test_merge_into_kwargs_top_level_keys() -> None:
    base = {"model": "openai/o3-mini", "api_key": "sk-xxx"}
    extra = {"reasoning_effort": "high"}
    merged = merge_into_kwargs(base, extra)
    assert merged == {
        "model": "openai/o3-mini",
        "api_key": "sk-xxx",
        "reasoning_effort": "high",
    }


def test_config_roundtrips_reasoning_effort(tmp_home_no_env: Path) -> None:
    cfg_mod.seed_defaults(tmp_home_no_env)
    cfg = cfg_mod.load(tmp_home_no_env)
    cfg.model = "openai/o3-mini"
    cfg.model_reasoning.effort = "high"
    cfg_mod.save(cfg)

    reloaded = cfg_mod.load(tmp_home_no_env)
    assert reloaded.model_reasoning.effort == "high"


def test_config_does_not_persist_empty_effort(tmp_home_no_env: Path) -> None:
    """An empty `effort` is the canonical 'off' state — config.save should not
    write a stale `model_reasoning:` key to disk."""
    import yaml
    cfg_mod.seed_defaults(tmp_home_no_env)
    cfg = cfg_mod.load(tmp_home_no_env)
    cfg.model = "openai/o3-mini"
    cfg.model_reasoning.effort = ""
    cfg_mod.save(cfg)

    raw = yaml.safe_load((tmp_home_no_env / "config.yaml").read_text())
    assert "model_reasoning" not in raw


def test_config_load_coerces_invalid_effort_to_empty(tmp_home_no_env: Path) -> None:
    import yaml
    cfg_mod.seed_defaults(tmp_home_no_env)
    (tmp_home_no_env / "config.yaml").write_text(yaml.safe_dump({
        "model": "openai/o3-mini",
        "model_reasoning": {"effort": "wibble"},
    }))
    cfg = cfg_mod.load(tmp_home_no_env)
    assert cfg.model_reasoning.effort == ""


def test_config_load_normalises_off_to_empty(tmp_home_no_env: Path) -> None:
    import yaml
    cfg_mod.seed_defaults(tmp_home_no_env)
    (tmp_home_no_env / "config.yaml").write_text(yaml.safe_dump({
        "model": "openai/o3-mini",
        "model_reasoning": {"effort": "off"},
    }))
    cfg = cfg_mod.load(tmp_home_no_env)
    assert cfg.model_reasoning.effort == ""


def test_resolve_model_attaches_reasoning_for_default_model(tmp_home_no_env: Path) -> None:
    cfg_mod.seed_defaults(tmp_home_no_env)
    cfg = cfg_mod.load(tmp_home_no_env)
    cfg.model = "openai/o3-mini"
    cfg.model_reasoning.effort = "high"
    kwargs = cfg_mod.resolve_model(cfg)
    assert kwargs.get("reasoning_effort") == "high"


def test_resolve_model_does_not_attach_when_effort_off(tmp_home_no_env: Path) -> None:
    cfg_mod.seed_defaults(tmp_home_no_env)
    cfg = cfg_mod.load(tmp_home_no_env)
    cfg.model = "openai/o3-mini"
    cfg.model_reasoning.effort = ""
    kwargs = cfg_mod.resolve_model(cfg)
    assert "reasoning_effort" not in kwargs
    assert "extra_body" not in kwargs


def test_resolve_model_does_not_attach_for_unsupported_model(
    tmp_home_no_env: Path,
) -> None:
    cfg_mod.seed_defaults(tmp_home_no_env)
    cfg = cfg_mod.load(tmp_home_no_env)
    cfg.model = "openai/gpt-4o"
    cfg.model_reasoning.effort = "high"
    kwargs = cfg_mod.resolve_model(cfg)
    assert "reasoning_effort" not in kwargs


def test_resolve_model_skips_reasoning_on_explicit_override(
    tmp_home_no_env: Path,
) -> None:
    """Passing `model=...` means the caller wants a different model — the
    profile's effort must NOT leak into a tool sub-model."""
    cfg_mod.seed_defaults(tmp_home_no_env)
    cfg = cfg_mod.load(tmp_home_no_env)
    cfg.model = "openai/o3-mini"
    cfg.model_reasoning.effort = "high"
    kwargs = cfg_mod.resolve_model(
        cfg, model="anthropic/claude-sonnet-4-6", include_reasoning=False,
    )
    assert "reasoning_effort" not in kwargs
    assert kwargs["model"] == "anthropic/claude-sonnet-4-6"


def test_resolve_model_openrouter_uses_extra_body(tmp_home_no_env: Path) -> None:
    cfg_mod.seed_defaults(tmp_home_no_env)
    cfg = cfg_mod.load(tmp_home_no_env)
    cfg.model = "openrouter/openai/o3-mini"
    cfg.model_reasoning.effort = "medium"
    kwargs = cfg_mod.resolve_model(cfg)
    assert kwargs.get("extra_body") == {"reasoning": {"effort": "medium"}}
    assert "reasoning_effort" not in kwargs


def test_apply_session_model_override_clears_effort(tmp_home_no_env: Path) -> None:
    """Mid-chat override = different model, no extra knobs. Both host.chat.send
    and TUI /model funnel through apply_session_model_override; the test pins
    that the helper actually clears effort so the surfaces can't drift."""
    from alpi.providers.reasoning import apply_session_model_override
    cfg_mod.seed_defaults(tmp_home_no_env)
    cfg = cfg_mod.load(tmp_home_no_env)
    cfg.model = "openai/o3-mini"
    cfg.model_reasoning.effort = "high"

    apply_session_model_override(cfg, "openai/o4-mini")

    assert cfg.model == "openai/o4-mini"
    assert cfg.model_reasoning.effort == ""
    kwargs = cfg_mod.resolve_model(cfg)
    assert "reasoning_effort" not in kwargs
    assert "extra_body" not in kwargs


def test_host_chat_model_override_does_not_leak_reasoning(
    tmp_home_no_env: Path,
) -> None:
    """The host.chat.send call site mutates cfg.model = override and calls
    Engine(cfg). Test that the same code path also clears effort by simulating
    the override + checking resolve_model output."""
    cfg_mod.seed_defaults(tmp_home_no_env)
    cfg = cfg_mod.load(tmp_home_no_env)
    cfg.model = "openai/o3-mini"
    cfg.model_reasoning.effort = "high"
    cfg_mod.save(cfg)

    # Simulate the host.chat.send override path verbatim:
    cfg = cfg_mod.load(tmp_home_no_env)
    from alpi.providers.reasoning import apply_session_model_override
    apply_session_model_override(cfg, "openai/o4-mini")

    kwargs = cfg_mod.resolve_model(cfg)
    assert kwargs["model"] == "openai/o4-mini"
    assert "reasoning_effort" not in kwargs


def test_tui_model_panel_session_switch_does_not_leak_reasoning(
    tmp_home_no_env: Path,
) -> None:
    """TUI /model is session-only: it mutates cfg.model in memory without
    persisting. The override helper must scrub effort the same way it does
    for host.chat.send. The on-disk config is untouched."""
    cfg_mod.seed_defaults(tmp_home_no_env)
    cfg = cfg_mod.load(tmp_home_no_env)
    cfg.model = "openai/o3-mini"
    cfg.model_reasoning.effort = "medium"
    cfg_mod.save(cfg)

    # In-memory swap (what TUI /model does)
    from alpi.providers.reasoning import apply_session_model_override
    apply_session_model_override(cfg, "anthropic/claude-sonnet-4-6")
    assert cfg.model_reasoning.effort == ""

    # Original on-disk config preserved
    persisted = cfg_mod.load(tmp_home_no_env)
    assert persisted.model == "openai/o3-mini"
    assert persisted.model_reasoning.effort == "medium"
