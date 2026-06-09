"""CL.1 phase 1 — stable cacheable prefix.

What we care about: the rendered prefix stays byte-identical across
calls so providers that auto-cache (OpenAI, Gemini, OpenRouter) keep
hitting; per-turn volatile content (``# NOW``, workgroup ctx, skill
keyword hint) is appended by the engine OUTSIDE the prefix builder and
never enters ``render_cacheable``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from alpi import config as cfg_mod
from alpi import prompt_cache as pc


def _make_cfg(home: Path, model: str = "openrouter/anthropic/claude-3.5-sonnet") -> cfg_mod.Config:
    (home / "config.yaml").write_text(f"model: {model}\n")
    return cfg_mod.load(home)


def test_env_block_states_host_python_version() -> None:
    block = pc._env_block(Path("/tmp/home"), Path("/tmp/ws"))
    assert "host Python" in block
    assert f"{sys.version_info.major}.{sys.version_info.minor}" in block


def test_part_order_is_stable_contract() -> None:
    assert pc.PART_ORDER == (
        "agent_profile",
        "base_prompt",
        "env",
        "system_time",
        "surface",
        "guidance",
        "knowledge_rule",
        "skills_index",
        "user_md",
        "memory_md",
    )


def test_build_parts_emits_every_named_part(tmp_path: Path) -> None:
    cfg = _make_cfg(tmp_path)
    parts = pc.build_parts(tmp_path, cfg)
    assert set(parts.keys()) == set(pc.PART_ORDER)


def test_render_matches_legacy_join_shape(tmp_path: Path) -> None:
    cfg = _make_cfg(tmp_path)
    parts = pc.build_parts(tmp_path, cfg)
    rendered = pc.render_cacheable(parts)
    expected = "\n\n".join(parts[name] for name in pc.PART_ORDER if parts[name])
    assert rendered == expected


def test_two_consecutive_builds_produce_identical_text(tmp_path: Path) -> None:
    cfg = _make_cfg(tmp_path)
    a = pc.render_cacheable(pc.build_parts(tmp_path, cfg))
    b = pc.render_cacheable(pc.build_parts(tmp_path, cfg))
    assert a == b


def test_now_block_is_not_in_the_prefix(tmp_path: Path) -> None:
    """The per-turn ``# NOW`` block (timestamp body) lives outside the cacheable prefix — the engine appends it as a separate system message every turn. The prefix may *mention* ``# NOW`` in instructions but must not embed the actual ``Local: <date>`` body."""
    from alpi import clock
    cfg = _make_cfg(tmp_path)
    rendered = pc.render_cacheable(pc.build_parts(tmp_path, cfg))
    now_body = clock.now_block()
    assert now_body not in rendered
    assert "Local:" not in rendered


def test_memory_change_only_affects_memory_part(tmp_path: Path) -> None:
    cfg = _make_cfg(tmp_path)
    before = pc.build_parts(tmp_path, cfg)

    (tmp_path / "memories").mkdir(parents=True, exist_ok=True)
    (tmp_path / "memories" / "MEMORY.md").write_text(
        "- the creator prefers tabs over spaces\n", encoding="utf-8",
    )
    after = pc.build_parts(tmp_path, cfg)

    moved = [name for name in pc.PART_ORDER if before[name] != after[name]]
    assert moved == ["memory_md"]


def test_surface_change_only_affects_surface_part(tmp_path: Path, monkeypatch) -> None:
    cfg = _make_cfg(tmp_path)
    monkeypatch.delenv("ALPI_PLATFORM", raising=False)
    before = pc.build_parts(tmp_path, cfg)

    monkeypatch.setenv("ALPI_PLATFORM", "telegram")
    after = pc.build_parts(tmp_path, cfg)

    moved = [name for name in pc.PART_ORDER if before[name] != after[name]]
    assert moved == ["surface"]


def test_skills_reordering_on_disk_does_not_move_skills_index(tmp_path: Path) -> None:
    """``skills_index_block`` sorts by category then name; touching mtime must not perturb the prefix or implicit caching breaks every turn."""
    cfg = _make_cfg(tmp_path)
    skills = tmp_path / "skills" / "research"
    skills.mkdir(parents=True)
    for name in ("alpha", "bravo", "charlie"):
        d = skills / name
        d.mkdir()
        (d / "meta.yaml").write_text(f"name: {name}\ndescription: x\n", encoding="utf-8")
        (d / f"{name}.md").write_text("body\n", encoding="utf-8")

    first = pc.build_parts(tmp_path, cfg)["skills_index"]

    os.utime(skills / "alpha", (1_900_000_000, 1_900_000_000))
    os.utime(skills / "bravo", (1_500_000_000, 1_500_000_000))

    second = pc.build_parts(tmp_path, cfg)["skills_index"]
    assert first == second


def test_cache_kwargs_empty_model_returns_no_kwargs() -> None:
    assert pc.cache_kwargs_for_model("") == {}


def test_cache_kwargs_returns_injection_when_supported(monkeypatch) -> None:
    import litellm.utils as _lu
    monkeypatch.setattr(_lu, "supports_prompt_caching", lambda model: True)
    out = pc.cache_kwargs_for_model("anthropic/claude-3.5-sonnet")
    assert out == {
        "cache_control_injection_points": [
            {"location": "message", "index": 0},
        ],
    }


def test_cache_kwargs_returns_empty_when_unsupported(monkeypatch) -> None:
    import litellm.utils as _lu
    monkeypatch.setattr(_lu, "supports_prompt_caching", lambda model: False)
    assert pc.cache_kwargs_for_model("openai/gpt-3.5-turbo") == {}


def test_cache_kwargs_swallows_litellm_exception(monkeypatch) -> None:
    """A future LiteLLM that renames or removes ``supports_prompt_caching`` must NOT bring down a turn — fall back to no marker."""
    import litellm.utils as _lu
    def _boom(model):
        raise RuntimeError("supports_prompt_caching went away")
    monkeypatch.setattr(_lu, "supports_prompt_caching", _boom)
    assert pc.cache_kwargs_for_model("anthropic/claude-3.5-sonnet") == {}


def test_cache_kwargs_targets_index_zero_not_role(monkeypatch) -> None:
    """Sanity: target the first message slot, not ``role=system``. The engine appends ``# NOW`` and other volatile system messages after the stable one; marking by role would cache them too."""
    import litellm.utils as _lu
    monkeypatch.setattr(_lu, "supports_prompt_caching", lambda model: True)
    point = pc.cache_kwargs_for_model("x")["cache_control_injection_points"][0]
    assert "role" not in point
    assert point["index"] == 0
    assert point["location"] == "message"
