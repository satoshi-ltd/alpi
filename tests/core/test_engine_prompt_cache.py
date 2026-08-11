"""CL.1/CL.4 wiring — cache_control injection targeting the stable messages[0], and the append-only host-context suffix contract."""

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
    """The injection targets ``index: 0`` — ``messages[0]`` MUST be the stable system prefix. Since CL.4 the volatile clock rides the user turn's host-context suffix, so everything after messages[0] is append-only conversation."""
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
    assert sent[1]["role"] == "user"
    assert sent[1]["content"].startswith("hola")
    assert "# NOW" in sent[1]["content"], "the clock rides the user suffix"


def test_two_turns_share_every_prior_provider_visible_byte(
    bootstrapped_home: Path, monkeypatch,
) -> None:
    """CL.4 acceptance — turn N+1's request must extend turn N's final request, never edit it (interior deletions split the provider prefix AND perturb OpenRouter's derived sticky key)."""
    from alpi import engine as engine_mod

    captured: list = []

    def _capture_stream(*_a, messages=None, **_kw):
        captured.append([dict(m) for m in (messages or [])])
        yield {"text_delta": "ok", "reasoning_delta": "", "tool_calls_delta": []}
        yield {
            "final": True, "tool_calls": [],
            "input_tokens": 1, "output_tokens": 1, "cost_usd": 0.0,
        }
    monkeypatch.setattr(engine_mod.llm, "stream", _capture_stream)

    cfg = config.load(bootstrapped_home)
    engine = Engine(home=bootstrapped_home, cfg=cfg)
    engine.run_turn("primera", lambda _ev: None)
    engine.run_turn("segunda", lambda _ev: None)

    first, second = captured[0], captured[-1]
    assert second[: len(first)] == first
    assert len(second) > len(first)


def test_saved_session_rehydrates_the_exact_user_bytes(
    bootstrapped_home: Path, monkeypatch,
) -> None:
    from alpi import engine as engine_mod
    from alpi.cli import _hydrate_from_path

    def _stream(*_a, **_kw):
        yield {"text_delta": "hecho", "reasoning_delta": "", "tool_calls_delta": []}
        yield {
            "final": True, "tool_calls": [],
            "input_tokens": 1, "output_tokens": 1, "cost_usd": 0.0,
        }
    monkeypatch.setattr(engine_mod.llm, "stream", _stream)

    cfg = config.load(bootstrapped_home)
    engine = Engine(home=bootstrapped_home, cfg=cfg)
    engine.run_turn("hola", lambda _ev: None)
    live_user = next(
        m["content"] for m in engine.session.messages if m["role"] == "user"
    )
    path = engine.session.save()

    fresh = Engine(home=bootstrapped_home, cfg=cfg)
    assert _hydrate_from_path(fresh, path) is True
    hydrated_user = next(
        m["content"] for m in fresh.session.messages if m["role"] == "user"
    )
    assert hydrated_user == live_user, (
        "a fresh Engine must replay the provider-visible bytes, suffix included"
    )


def test_multimodal_turn_keeps_parts_and_appends_one_suffix_part(
    bootstrapped_home: Path, monkeypatch, tmp_path: Path,
) -> None:
    from alpi import engine as engine_mod

    img = tmp_path / "x.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 32)

    def _stream(*_a, **_kw):
        yield {"text_delta": "ok", "reasoning_delta": "", "tool_calls_delta": []}
        yield {
            "final": True, "tool_calls": [],
            "input_tokens": 1, "output_tokens": 1, "cost_usd": 0.0,
        }
    monkeypatch.setattr(engine_mod.llm, "stream", _stream)
    monkeypatch.setattr("alpi.attachments.vision_status", lambda _m: "yes")

    cfg = config.load(bootstrapped_home)
    engine = Engine(home=bootstrapped_home, cfg=cfg)
    engine.run_turn(
        "mira esto", lambda _ev: None,
        attachments=[{"path": str(img)}],
    )
    user_msg = next(
        m for m in engine.session.messages if m["role"] == "user"
    )
    parts = user_msg["content"]
    assert isinstance(parts, list)
    assert parts[-1]["type"] == "text"
    assert any(p.get("type") == "image_url" for p in parts[:-1])
    suffixed = [p for p in parts if p.get("type") == "text" and "# HOST CONTEXT" in p.get("text", "")]
    assert len(suffixed) == 1
