"""MC.1 — central reasoning_effort plumbing for the profile's default model."""

from __future__ import annotations

import re
from typing import Any


VALID_EFFORTS = ("low", "medium", "high")

# `off` is the wizard-facing label for "no reasoning param"; the dataclass stores it as "".
_OFF_ALIASES = frozenset({"", "off", "none", "disabled", "no"})


def normalise_effort(value: Any) -> str:
    if value is None:
        return ""
    s = str(value).strip().lower()
    if s in _OFF_ALIASES:
        return ""
    if s in VALID_EFFORTS:
        return s
    return ""


# Direct providers without a curated YAML catalog (google/deepseek/xai) — we fall back to regex. OpenAI + Anthropic are catalog-driven: the YAML is the source of truth, the regex below is the safety net for custom-typed model strings the user enters via the wizard's "custom model" prompt.
_DIRECT_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"^openai/o[1-9](?:[._-]|$)"),
    re.compile(r"^openai/gpt-5(?:[.-]|$)"),
    # Two Claude naming conventions in the wild:
    #   old: anthropic/claude-3-7-sonnet / anthropic/claude-3-5-sonnet (only 3.7+ supports thinking)
    #   new: anthropic/claude-sonnet-4-6 / claude-opus-4 / claude-haiku-4-5 (Claude 4+ supports thinking)
    re.compile(r"^anthropic/claude-(?:[4-9]|3-[7-9]|(?:sonnet|opus|haiku)-[4-9])"),
    re.compile(r"^google/gemini-2\.[5-9]"),
    re.compile(r"^deepseek/.*r1"),
    re.compile(r"^xai/grok-(?:3|4)-reasoning"),
)

_CATALOG_PROVIDERS = frozenset({"openai", "anthropic"})


def supports_reasoning(model: str) -> bool:
    """True when the wizard / settings UI should expose the effort dropdown.

    Order of evidence:
    1. ``openrouter/*`` — always True; OpenRouter's unified ``reasoning`` param
       is silently ignored upstream when not supported, so we let the user pick.
    2. ``openai/<id>`` / ``anthropic/<id>`` — consult `curated_models.yaml`. The
       catalog is the source of truth: a model marked ``reasoning: true`` is
       supported, anything else (including unknown ids) falls through to (3).
    3. Regex fallback — catches o-series, gpt-5.x, Claude 3.7+/4+, Gemini 2.5+,
       DeepSeek R1, Grok 3/4 reasoning, even when the user types the model
       name manually outside the curated catalog.
    """
    if not model:
        return False
    m = model.strip()
    if m.startswith("openrouter/"):
        return True
    if "/" in m:
        provider, model_id = m.split("/", 1)
        if provider in _CATALOG_PROVIDERS:
            from alpi.providers.curated import load_curated
            for entry in load_curated(provider):
                if entry.get("id") == model_id and entry.get("reasoning"):
                    return True
    for pat in _DIRECT_PATTERNS:
        if pat.match(m):
            return True
    return False


def reasoning_kwargs(model: str, effort: str) -> dict[str, Any]:
    """Return the kwargs to merge into the litellm call for `model` + `effort`.

    Empty effort or unsupported model → empty dict (no param sent). The caller must merge this into its own kwargs without overwriting nested keys like `extra_body.options.num_ctx`.
    """
    eff = normalise_effort(effort)
    if not eff or not supports_reasoning(model):
        return {}
    if model.startswith("openrouter/"):
        return {"extra_body": {"reasoning": {"effort": eff}}}
    return {"reasoning_effort": eff}


def merge_into_kwargs(base: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    """Deep-merge `extra` into `base`, with `extra_body` recursed one level deep so an Ollama num_ctx and a reasoning entry can coexist."""
    out = dict(base)
    for key, val in extra.items():
        if key == "extra_body" and isinstance(val, dict) and isinstance(out.get("extra_body"), dict):
            merged = dict(out["extra_body"])
            for k2, v2 in val.items():
                if isinstance(v2, dict) and isinstance(merged.get(k2), dict):
                    inner = dict(merged[k2])
                    inner.update(v2)
                    merged[k2] = inner
                else:
                    merged[k2] = v2
            out["extra_body"] = merged
        else:
            out[key] = val
    return out


def apply_session_model_override(cfg: Any, model_id: str) -> None:
    """Mutate cfg for an in-process session override: swap the model AND clear the
    profile's reasoning effort. Mid-chat overrides are 'a different model, no
    extra knobs' — effort lives with the profile's default model only. host.chat
    and TUI /model both go through this so the invariant is impossible to skip.
    """
    cfg.model = model_id
    cfg.model_reasoning.effort = ""


__all__ = [
    "VALID_EFFORTS",
    "normalise_effort",
    "supports_reasoning",
    "reasoning_kwargs",
    "merge_into_kwargs",
    "apply_session_model_override",
]
