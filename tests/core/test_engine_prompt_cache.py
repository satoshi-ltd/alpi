"""CL.1 wiring — Engine forwards LiteLLM ``cache_control_injection_points``
when ``litellm.utils.supports_prompt_caching`` says yes, and stays quiet
otherwise. Also pins the messages layout the injection assumes:
``messages[0]`` is the stable prefix, ``messages[1]`` is the ``# NOW`` block.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alpi import config, home, memory
from alpi.engine import Engine


@pytest.fixture
def bootstrapped_home(tmp_home_no_env: Path) -> Path:
    home.ensure_home(tmp_home_no_env)
    config.seed_defaults(tmp_home_no_env)
    (tmp_home_no_env / "config.yaml").write_text(
        "model: anthropic/claude-3.5-sonnet\n",
    )
    memory.MemoryStore(tmp_home_no_env).seed_defaults()
    return tmp_home_no_env


def _stub_stream(text: str = "ok"):
    def _stream(*_a, **_kw):
        yield {"text_delta": text, "reasoning_delta": "", "tool_calls_delta": []}
        yield {
            "final": True,
            "tool_calls": [],
            "input_tokens": 1,
            "output_tokens": 1,
            "cost_usd": 0.0,
        }
    return _stream


def _spy_stream(captured: list, text: str = "ok"):
    base = _stub_stream(text)
    def _stream(*args, **kwargs):
        captured.append(kwargs)
        yield from base(*args, **kwargs)
    return _stream


def test_supported_model_passes_injection_to_llm(
    bootstrapped_home: Path, monkeypatch,
) -> None:
    from alpi import engine as engine_mod
    import litellm.utils as _lu

    monkeypatch.setattr(_lu, "supports_prompt_caching", lambda model, **_kw: True)
    captured: list = []
    monkeypatch.setattr(engine_mod.llm, "stream", _spy_stream(captured))

    cfg = config.load(bootstrapped_home)
    engine = Engine(home=bootstrapped_home, cfg=cfg)
    engine.run_turn("hola", lambda _ev: None)

    assert captured, "llm.stream was never called"
    kwargs = captured[0]
    assert kwargs.get("cache_control_injection_points") == [
        {"location": "message", "index": 0},
    ]


def test_unsupported_model_omits_injection(
    bootstrapped_home: Path, monkeypatch,
) -> None:
    from alpi import engine as engine_mod
    import litellm.utils as _lu

    monkeypatch.setattr(_lu, "supports_prompt_caching", lambda model, **_kw: False)
    captured: list = []
    monkeypatch.setattr(engine_mod.llm, "stream", _spy_stream(captured))

    cfg = config.load(bootstrapped_home)
    engine = Engine(home=bootstrapped_home, cfg=cfg)
    engine.run_turn("hola", lambda _ev: None)

    assert captured, "llm.stream was never called"
    assert "cache_control_injection_points" not in captured[0]


def test_litellm_helper_failure_falls_back_to_no_injection(
    bootstrapped_home: Path, monkeypatch,
) -> None:
    """If LiteLLM's helper goes away or raises (version drift, name change), the engine still runs the turn — caching is opt-in optimisation, never a hard dependency."""
    from alpi import engine as engine_mod
    import litellm.utils as _lu

    def _boom(model, **_kw):
        raise RuntimeError("supports_prompt_caching went away")
    monkeypatch.setattr(_lu, "supports_prompt_caching", _boom)
    captured: list = []
    monkeypatch.setattr(engine_mod.llm, "stream", _spy_stream(captured))

    cfg = config.load(bootstrapped_home)
    engine = Engine(home=bootstrapped_home, cfg=cfg)
    engine.run_turn("hola", lambda _ev: None)

    assert captured
    assert "cache_control_injection_points" not in captured[0]


def test_messages_layout_matches_injection_index_zero(
    bootstrapped_home: Path, monkeypatch,
) -> None:
    """The injection targets ``index: 0`` — ``messages[0]`` MUST be the stable system prefix and ``messages[1]`` MUST be the volatile ``# NOW`` block. If this ever flips, the marker would land on volatile content and cache would break every turn."""
    from alpi import engine as engine_mod
    import litellm.utils as _lu

    monkeypatch.setattr(_lu, "supports_prompt_caching", lambda model, **_kw: True)
    captured_messages: list = []

    def _capture_stream(*_a, messages=None, **_kw):
        captured_messages.append(list(messages or []))
        yield {"text_delta": "ok", "reasoning_delta": "", "tool_calls_delta": []}
        yield {
            "final": True, "tool_calls": [],
            "input_tokens": 1, "output_tokens": 1, "cost_usd": 0.0,
        }
    monkeypatch.setattr(engine_mod.llm, "stream", _capture_stream)

    cfg = config.load(bootstrapped_home)
    engine = Engine(home=bootstrapped_home, cfg=cfg)
    engine.run_turn("hola", lambda _ev: None)

    sent = captured_messages[0]
    assert sent[0]["role"] == "system"
    assert "Local:" not in sent[0]["content"]
    assert sent[1]["role"] == "system"
    assert sent[1]["content"].startswith("# NOW\n")
