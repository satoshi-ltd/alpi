from __future__ import annotations

from pathlib import Path

from alpi import config as cfg_mod
from alpi import prompt_cache as pc
from alpi.prompts import guidance


def _cfg(home: Path, model: str) -> cfg_mod.Config:
    (home / "config.yaml").write_text(f"model: {model}\n")
    return cfg_mod.load(home)


def test_model_family_normalizes_provider_prefixes() -> None:
    assert guidance.model_family("openrouter/anthropic/claude-3.5-sonnet") == "anthropic"
    assert guidance.model_family("claude-3.5-sonnet") == "anthropic"
    assert guidance.model_family("openrouter/openai/gpt-4o") == "openai"
    assert guidance.model_family("gpt-4") == "openai"
    assert guidance.model_family("openrouter/openai/gpt-4o-mini") == "openai_mini"
    assert guidance.model_family("gemini/gemini-2.0-flash") == "gemini_flash"
    assert guidance.model_family("gemini/gemini-1.5-pro") == "gemini"
    assert guidance.model_family("ollama/llama-2") == "local"
    assert guidance.model_family("") == "unknown"
    assert guidance.model_family("some-weird-model") == "unknown"


def test_strong_and_unknown_families_get_no_guidance() -> None:
    for model in ("claude-3.5-sonnet", "gpt-4o", "gemini-1.5-pro", "some-weird-model", ""):
        assert guidance.guidance_blocks_for_model(model) == []
        assert guidance.render_guidance(model) == ""


def test_weak_families_get_tool_and_verify_guidance() -> None:
    for model in ("ollama/llama-2", "openrouter/openai/gpt-4o-mini", "gemini/gemini-2.0-flash"):
        assert guidance.guidance_blocks_for_model(model) == ["tool_discipline", "verify_before_done"]


def test_custom_ollama_endpoint_is_local() -> None:
    providers = {"ollama": [{"name": "home"}, {"name": "mistral-box"}]}
    assert guidance.model_family("home/llama3", providers) == "local"
    assert guidance.model_family("mistral-box/qwen2.5", providers) == "local"
    assert guidance.guidance_blocks_for_model("home/llama3", providers) == [
        "tool_discipline",
        "verify_before_done",
    ]


def test_custom_endpoint_name_without_provider_config_is_unknown() -> None:
    assert guidance.model_family("home/llama3") == "unknown"
    assert guidance.guidance_blocks_for_model("home/llama3") == []


def test_custom_ollama_endpoint_reaches_build_parts(tmp_path: Path) -> None:
    (tmp_path / "config.yaml").write_text(
        "model: home/llama3\nproviders:\n  ollama:\n    - name: home\n"
    )
    cfg = cfg_mod.load(tmp_path)
    parts = pc.build_parts(tmp_path, cfg)
    assert "tool" in parts["guidance"].lower()


def test_render_guidance_includes_block_text() -> None:
    text = guidance.render_guidance("ollama/llama-2")
    assert "tool" in text.lower()
    assert "done" in text.lower()


def test_no_duplicate_blocks() -> None:
    blocks = guidance.guidance_blocks_for_model("ollama/llama-2")
    assert len(blocks) == len(set(blocks))


def test_guidance_part_present_for_weak_model(tmp_path: Path) -> None:
    parts = pc.build_parts(tmp_path, _cfg(tmp_path, "ollama/llama-2"))
    assert parts["guidance"]
    assert "tool" in parts["guidance"].lower()


def test_guidance_part_empty_for_strong_model(tmp_path: Path) -> None:
    parts = pc.build_parts(tmp_path, _cfg(tmp_path, "openrouter/anthropic/claude-3.5-sonnet"))
    assert parts["guidance"] == ""


def test_guidance_is_ordered_right_after_surface() -> None:
    assert pc.PART_ORDER.index("guidance") == pc.PART_ORDER.index("surface") + 1


def test_guidance_never_includes_workgroup_protocol() -> None:
    text = guidance.render_guidance("ollama/llama-2")
    assert "#task" not in text
    assert "quorum" not in text.lower()
