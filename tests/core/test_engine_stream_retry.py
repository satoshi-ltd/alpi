"""Mid-stream transient errors: llm.stream owns same-model retries (until visible text), the engine owns fallback without consuming a step."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from alpi import llm
from alpi.config import Config, RuntimeConfig, ToolsConfig
from alpi.engine import Engine


class Timeout(Exception):
    pass


class MidStreamFallbackError(Exception):
    pass


def _wrapped_timeout() -> MidStreamFallbackError:
    err = MidStreamFallbackError("Upstream idle timeout exceeded")
    err.__cause__ = Timeout("Timeout Error")
    return err


def _mk_engine(tmp_path: Path, monkeypatch, *, max_steps: int = 6, fallbacks: list[str] | None = None) -> Engine:
    home = tmp_path / "h"
    home.mkdir()
    yaml = "model: gpt-5.4-mini\n"
    if fallbacks:
        yaml += "fallback_models:\n" + "".join(f"- {m}\n" for m in fallbacks)
    (home / "config.yaml").write_text(yaml)
    monkeypatch.setattr("alpi.engine._maybe_load_mcps", lambda _cfg: [])
    monkeypatch.setattr(Engine, "_build_system_prompt", lambda self: "you are alpi")
    monkeypatch.setattr("alpi.ctx_window.resolve", lambda _h, _c, _m: 400_000)
    monkeypatch.setattr("alpi.ledger.check", lambda *a, **kw: None)
    monkeypatch.setattr("alpi.ledger.record", lambda *a, **kw: None)
    monkeypatch.setattr(
        "alpi.config.resolve_model",
        lambda _cfg, model=None, **_kw: {"model": model or "gpt-5.4-mini"},
    )
    cfg = Config(
        home=home,
        model="gpt-5.4-mini",
        fallback_models=list(fallbacks or []),
        tools=ToolsConfig(max_steps_per_turn=max_steps),
        runtime=RuntimeConfig(max_retries=2, retry_backoff_s=0.0),
        raw={},
    )
    return Engine(home=home, cfg=cfg)


def _ok_stream():
    yield {"text_delta": "all good"}
    yield {
        "final": True, "text": "all good",
        "input_tokens": 10, "output_tokens": 5, "cost_usd": 0.0,
        "tool_calls": [],
    }


def test_fallback_retries_the_same_step_with_tools_and_messages(tmp_path, monkeypatch) -> None:
    eng = _mk_engine(tmp_path, monkeypatch, max_steps=1, fallbacks=["gpt-5.4-pro"])
    calls: list[dict] = []

    def fake_stream(messages, tools, **kwargs):
        calls.append({
            "model": kwargs.get("model"),
            "n_tools": len(tools or []),
            "messages": [m.get("content") for m in messages],
        })
        if len(calls) == 1:
            yield {"reasoning_delta": "hmm"}
            raise _wrapped_timeout()
        yield from _ok_stream()

    monkeypatch.setattr("alpi.llm.stream", fake_stream)

    events = []
    eng.run_turn("q", emit=events.append)

    assert [c["model"] for c in calls] == ["gpt-5.4-mini", "gpt-5.4-pro"]
    assert calls[1]["n_tools"] == calls[0]["n_tools"] > 0, "fallback call must keep the tool schemas"
    assert calls[1]["messages"] == calls[0]["messages"], "fallback call must replay the same messages"
    assert not any("step tool limit" in str(m) for m in calls[1]["messages"]), "no wrap-up prompt: the step was not consumed"
    assert not any(e.kind == "error" for e in events)
    finals = [e for e in events if e.kind == "assistant_done" and e.final]
    assert finals and finals[-1].text == "all good"


def test_visible_text_partial_still_surfaces_the_error(tmp_path, monkeypatch) -> None:
    eng = _mk_engine(tmp_path, monkeypatch, fallbacks=["gpt-5.4-pro"])
    calls = {"n": 0}

    def fake_stream(messages, tools, **kwargs):
        calls["n"] += 1
        yield {"text_delta": "partial visible answer"}
        raise _wrapped_timeout()

    monkeypatch.setattr("alpi.llm.stream", fake_stream)

    events = []
    eng.run_turn("q", emit=events.append)

    assert calls["n"] == 1, "no fallback once visible text streamed"
    assert any(e.kind == "error" for e in events)


def test_error_without_fallbacks_surfaces_after_one_call(tmp_path, monkeypatch) -> None:
    eng = _mk_engine(tmp_path, monkeypatch)
    calls = {"n": 0}

    def fake_stream(messages, tools, **kwargs):
        calls["n"] += 1
        yield {"reasoning_delta": "hmm"}
        raise _wrapped_timeout()

    monkeypatch.setattr("alpi.llm.stream", fake_stream)

    events = []
    eng.run_turn("q", emit=events.append)

    assert calls["n"] == 1
    assert any(e.kind == "error" for e in events)


def test_exhausted_fallbacks_surface_the_error(tmp_path, monkeypatch) -> None:
    eng = _mk_engine(tmp_path, monkeypatch, fallbacks=["gpt-5.4-pro"])
    calls = {"n": 0}

    def fake_stream(messages, tools, **kwargs):
        calls["n"] += 1
        yield {"reasoning_delta": "hmm"}
        raise _wrapped_timeout()

    monkeypatch.setattr("alpi.llm.stream", fake_stream)

    events = []
    eng.run_turn("q", emit=events.append)

    assert calls["n"] == 2
    assert any(e.kind == "error" for e in events)


def _chunk(text: str = "", reasoning: str = "") -> SimpleNamespace:
    return SimpleNamespace(choices=[SimpleNamespace(
        delta=SimpleNamespace(content=text, reasoning_content=reasoning, tool_calls=None),
        finish_reason=None,
    )], usage=None)


def _rt(max_retries: int = 2) -> RuntimeConfig:
    return RuntimeConfig(max_retries=max_retries, retry_backoff_s=0.0)


def test_llm_stream_retries_same_model_after_reasoning_only(monkeypatch) -> None:
    monkeypatch.setattr("alpi.llm._backoff_sleep", lambda *_a: None)
    provider_calls = {"n": 0}

    def fake_completion(kwargs):
        provider_calls["n"] += 1

        def gen():
            yield _chunk(reasoning="thinking")
            if provider_calls["n"] == 1:
                raise Timeout("upstream idle")
            yield _chunk(text="answer")
        return gen()

    monkeypatch.setattr("alpi.llm._completion_silenced", fake_completion)

    chunks = list(llm.stream("m", [{"role": "user", "content": "q"}], rt=_rt()))

    assert provider_calls["n"] == 2
    assert any(c.get("text_delta") == "answer" for c in chunks)
    assert chunks[-1]["final"] is True


def test_llm_stream_provider_calls_capped_at_one_plus_max_retries(monkeypatch) -> None:
    monkeypatch.setattr("alpi.llm._backoff_sleep", lambda *_a: None)
    provider_calls = {"n": 0}

    def fake_completion(kwargs):
        provider_calls["n"] += 1

        def gen():
            yield _chunk(reasoning="thinking")
            raise Timeout("upstream idle")
        return gen()

    monkeypatch.setattr("alpi.llm._completion_silenced", fake_completion)

    with pytest.raises(Exception):
        list(llm.stream("m", [{"role": "user", "content": "q"}], rt=_rt(max_retries=2)))

    assert provider_calls["n"] == 3


def test_llm_stream_never_retries_after_visible_text(monkeypatch) -> None:
    monkeypatch.setattr("alpi.llm._backoff_sleep", lambda *_a: None)
    provider_calls = {"n": 0}

    def fake_completion(kwargs):
        provider_calls["n"] += 1

        def gen():
            yield _chunk(text="partial")
            raise Timeout("upstream idle")
        return gen()

    monkeypatch.setattr("alpi.llm._completion_silenced", fake_completion)

    with pytest.raises(Exception):
        list(llm.stream("m", [{"role": "user", "content": "q"}], rt=_rt()))

    assert provider_calls["n"] == 1


def test_is_transient_unwraps_the_cause_chain() -> None:
    assert llm.is_transient(_wrapped_timeout())
    assert not llm.is_transient(MidStreamFallbackError("permanent-looking"))
    inner = Timeout("t")
    outer = MidStreamFallbackError("wrap")
    outer.original_exception = inner
    assert llm.is_transient(outer)


def test_interrupt_during_primary_failure_never_dials_the_fallback(tmp_path, monkeypatch) -> None:
    eng = _mk_engine(tmp_path, monkeypatch, fallbacks=["gpt-5.4-pro"])
    calls = {"n": 0}

    def fake_stream(messages, tools, **kwargs):
        calls["n"] += 1
        yield {"reasoning_delta": "hmm"}
        eng.request_interrupt("user")
        raise _wrapped_timeout()

    monkeypatch.setattr("alpi.llm.stream", fake_stream)

    events = []
    eng.run_turn("q", emit=events.append)

    assert calls["n"] == 1, "fallback must not start after an interrupt"
    assert not any(e.kind == "error" for e in events)


def test_deadline_during_primary_failure_goes_to_time_limit_wrapup(tmp_path, monkeypatch) -> None:
    import time as _time
    eng = _mk_engine(tmp_path, monkeypatch, fallbacks=["gpt-5.4-pro"])
    monkeypatch.setattr(
        "alpi.engine._turn_deadline_from_env", lambda started: _time.time() + 0.1,
    )
    calls: list[dict] = []

    def fake_stream(messages, tools, **kwargs):
        calls.append({"n_tools": len(tools or []), "messages": list(messages)})
        if len(calls) == 1:
            yield {"reasoning_delta": "hmm"}
            _time.sleep(0.25)
            raise _wrapped_timeout()
        yield {"text_delta": "best effort"}
        yield {
            "final": True, "input_tokens": 1, "output_tokens": 1,
            "cost_usd": 0.0, "tool_calls": [],
        }

    monkeypatch.setattr("alpi.llm.stream", fake_stream)

    events = []
    eng.run_turn("q", emit=events.append)

    assert len(calls) == 2
    assert calls[0]["n_tools"] > 0
    assert calls[1]["n_tools"] == 0, "second call must be the tools-off time-limit wrap-up, not the fallback"
    assert any(
        "out of time" in str(m.get("content", "")) for m in calls[1]["messages"]
    ), "wrap-up prompt must be the time-limit one"
    assert not any(e.kind == "error" for e in events)


def test_persisted_reasoning_contains_only_the_successful_attempt(tmp_path, monkeypatch) -> None:
    eng = _mk_engine(tmp_path, monkeypatch)
    monkeypatch.setattr("alpi.llm._backoff_sleep", lambda *_a: None)
    provider_calls = {"n": 0}

    def fake_completion(kwargs):
        provider_calls["n"] += 1

        def gen():
            if provider_calls["n"] == 1:
                yield _chunk(reasoning="first-try thinking")
                raise Timeout("upstream idle")
            yield _chunk(reasoning="second-try thinking")
            yield _chunk(text="answer")
        return gen()

    monkeypatch.setattr("alpi.llm._completion_silenced", fake_completion)

    events = []
    eng.run_turn("q", emit=events.append)

    assert provider_calls["n"] == 2
    turn = eng.session.turns[-1]
    assert turn.reasoning == "second-try thinking"
    assert "first-try" not in turn.reasoning


def test_interrupt_during_backoff_prevents_the_second_provider_call(tmp_path, monkeypatch) -> None:
    eng = _mk_engine(tmp_path, monkeypatch)
    provider_calls = {"n": 0}

    def fake_completion(kwargs):
        provider_calls["n"] += 1

        def gen():
            yield _chunk(reasoning="thinking")
            raise Timeout("upstream idle")
        return gen()

    monkeypatch.setattr("alpi.llm._completion_silenced", fake_completion)
    monkeypatch.setattr(
        "alpi.llm._backoff_sleep",
        lambda *_a: eng.request_interrupt("user hit stop"),
    )

    events = []
    eng.run_turn("q", emit=events.append)

    assert provider_calls["n"] == 1, "interrupt during backoff must prevent the retry call"
    assert not any(e.kind == "error" for e in events)


def test_deadline_during_backoff_goes_to_wrapup_not_retry(tmp_path, monkeypatch) -> None:
    import time as _time
    eng = _mk_engine(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "alpi.engine._turn_deadline_from_env", lambda started: _time.time() + 0.1,
    )
    monkeypatch.setattr("alpi.llm._backoff_sleep", lambda *_a: _time.sleep(0.2))
    tooled_calls = {"n": 0}
    untooled_calls = {"n": 0}

    def fake_completion(kwargs):
        if kwargs.get("tools"):
            tooled_calls["n"] += 1

            def gen():
                yield _chunk(reasoning="thinking")
                raise Timeout("upstream idle")
            return gen()
        untooled_calls["n"] += 1

        def gen_ok():
            yield _chunk(text="best effort")
        return gen_ok()

    monkeypatch.setattr("alpi.llm._completion_silenced", fake_completion)

    events = []
    eng.run_turn("q", emit=events.append)

    assert tooled_calls["n"] == 1, "deadline during backoff must prevent the retry call"
    assert untooled_calls["n"] == 1, "the turn must end via the tools-off time-limit wrap-up"
    assert not any(e.kind == "error" for e in events)
