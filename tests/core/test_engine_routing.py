"""Engine-side dynamic routing: ALPI_TIER, fallback chain, reactive escalation."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from alpi import config as cfg_mod
from alpi.engine import Engine


def _make_engine(monkeypatch, tmp_path: Path, data: dict) -> Engine:
    home = tmp_path / "h"
    home.mkdir()
    (home / "config.yaml").write_text(yaml.safe_dump(data))
    monkeypatch.delenv("ALPI_TIER", raising=False)
    monkeypatch.setattr("alpi.engine._maybe_load_mcps", lambda _cfg: [])
    monkeypatch.setattr(Engine, "_build_system_prompt", lambda self: "you are alpi")
    monkeypatch.setattr("alpi.ctx_window.resolve", lambda *a: 400_000)
    monkeypatch.setattr("alpi.ledger.check", lambda *a, **kw: None)
    monkeypatch.setattr("alpi.ledger.record", lambda *a, **kw: None)
    monkeypatch.setattr("alpi.ledger.spend_fraction", lambda *a, **kw: None)
    cfg = cfg_mod.load(home)
    return Engine(home=home, cfg=cfg)


def _final_chunk(text: str, tool_calls=None):
    return {
        "final": True,
        "tool_calls": tool_calls or [],
        "input_tokens": 10,
        "output_tokens": 5,
        "cost_usd": 0.0,
        "_text": text,
    }


def _scripted_stream(monkeypatch, script):
    """script(call_index, kwargs) -> final-chunk dict, or raises."""
    calls: list[dict] = []

    def fake_stream(messages, tools, **kwargs):
        idx = len(calls)
        calls.append(dict(kwargs))
        chunk = dict(script(idx, kwargs))
        text = chunk.pop("_text", "")
        if text:
            yield {"text_delta": text}
        yield chunk

    monkeypatch.setattr("alpi.llm.stream", fake_stream)
    return calls


def _failing_tools(n: int):
    return [
        {"id": f"t{i}", "name": "search", "arguments": "{}"} for i in range(n)
    ]


def _patch_failing_execute(monkeypatch):
    from alpi.tools.base import ToolResult

    monkeypatch.setattr(
        "alpi.tools.execute",
        lambda name, args, deny=frozenset(): ToolResult(ok=False, output="", error="boom"),
    )


def test_plain_turn_records_model_on_turn(monkeypatch, tmp_path: Path) -> None:
    engine = _make_engine(monkeypatch, tmp_path, {"model": "base-model"})
    _scripted_stream(monkeypatch, lambda i, kw: _final_chunk("hola"))
    events = []
    engine.run_turn("hi", emit=events.append)
    assert engine.session.turns[-1].model == "base-model"
    assert not [e for e in events if e.kind == "routing"]
    usage = next(e for e in events if e.kind == "usage")
    assert usage.model == "base-model"


def test_alpi_tier_env_routes_turn_to_fast_tier(monkeypatch, tmp_path: Path) -> None:
    engine = _make_engine(monkeypatch, tmp_path, {
        "model": "base-model",
        "tiers": {"fast": {"model": "flash-model"}},
    })
    monkeypatch.setenv("ALPI_TIER", "fast")
    calls = _scripted_stream(monkeypatch, lambda i, kw: _final_chunk("ok"))
    events = []
    engine.run_turn("digest", emit=events.append)
    assert calls[0]["model"] == "flash-model"
    assert engine.session.turns[-1].model == "flash-model"


def test_alpi_tier_env_with_unconfigured_tier_uses_main(monkeypatch, tmp_path: Path) -> None:
    engine = _make_engine(monkeypatch, tmp_path, {"model": "base-model"})
    monkeypatch.setenv("ALPI_TIER", "fast")
    calls = _scripted_stream(monkeypatch, lambda i, kw: _final_chunk("ok"))
    engine.run_turn("digest", emit=lambda e: None)
    assert calls[0]["model"] == "base-model"
    assert engine.session.turns[-1].model == "base-model"


def test_fallback_chain_swaps_model_when_provider_fails(monkeypatch, tmp_path: Path) -> None:
    engine = _make_engine(monkeypatch, tmp_path, {
        "model": "primary",
        "fallback_models": ["backup"],
    })

    def script(i, kw):
        if kw.get("model") == "primary":
            raise RuntimeError("provider down")
        return _final_chunk("saved by backup")

    calls = _scripted_stream(monkeypatch, script)
    events = []
    engine.run_turn("hi", emit=events.append)
    routing = [e for e in events if e.kind == "routing"]
    assert len(routing) == 1
    assert routing[0].model == "backup"
    assert "backup" in routing[0].text
    assert calls[-1]["model"] == "backup"
    done = next(e for e in events if e.kind == "assistant_done" and e.final)
    assert done.text == "saved by backup"
    assert engine.session.turns[-1].model == "backup"
    assert not [e for e in events if e.kind == "error"]


def test_fallback_exhausted_surfaces_error(monkeypatch, tmp_path: Path) -> None:
    engine = _make_engine(monkeypatch, tmp_path, {
        "model": "primary",
        "fallback_models": ["backup"],
    })

    def script(i, kw):
        raise RuntimeError(f"down: {kw.get('model')}")

    _scripted_stream(monkeypatch, script)
    events = []
    engine.run_turn("hi", emit=events.append)
    assert len([e for e in events if e.kind == "routing"]) == 1
    errors = [e for e in events if e.kind == "error"]
    assert errors and "backup" in errors[0].text


def test_no_fallback_after_partial_output(monkeypatch, tmp_path: Path) -> None:
    engine = _make_engine(monkeypatch, tmp_path, {
        "model": "primary",
        "fallback_models": ["backup"],
    })

    def fake_stream(messages, tools, **kwargs):
        yield {"text_delta": "half a rep"}
        raise RuntimeError("mid-stream drop")

    monkeypatch.setattr("alpi.llm.stream", fake_stream)
    events = []
    engine.run_turn("hi", emit=events.append)
    assert not [e for e in events if e.kind == "routing"]
    assert [e for e in events if e.kind == "error"]


def test_escalates_to_deep_tier_after_consecutive_tool_failures(
    monkeypatch, tmp_path: Path,
) -> None:
    engine = _make_engine(monkeypatch, tmp_path, {
        "model": "base-model",
        "tiers": {"deep": {"model": "openrouter/deep", "effort": "high"}},
    })
    _patch_failing_execute(monkeypatch)

    def script(i, kw):
        if i == 0:
            return _final_chunk("trying tools", tool_calls=_failing_tools(3))
        return _final_chunk("recovered")

    calls = _scripted_stream(monkeypatch, script)
    events = []
    engine.run_turn("do the thing", emit=events.append)
    routing = [e for e in events if e.kind == "routing"]
    assert len(routing) == 1
    assert routing[0].model == "openrouter/deep"
    assert "3 consecutive tool failures" in routing[0].text
    assert calls[0]["model"] == "base-model"
    assert calls[1]["model"] == "openrouter/deep"
    assert calls[1]["extra_body"]["reasoning"]["effort"] == "high"
    assert engine.session.turns[-1].model == "openrouter/deep"


def test_escalation_fires_at_most_once_per_turn(monkeypatch, tmp_path: Path) -> None:
    engine = _make_engine(monkeypatch, tmp_path, {
        "model": "base-model",
        "tiers": {"deep": {"model": "deep-model"}},
    })
    _patch_failing_execute(monkeypatch)

    def script(i, kw):
        if i in (0, 1):
            return _final_chunk("", tool_calls=_failing_tools(3))
        return _final_chunk("giving my best answer")

    calls = _scripted_stream(monkeypatch, script)
    events = []
    engine.run_turn("stubborn", emit=events.append)
    assert len([e for e in events if e.kind == "routing"]) == 1
    assert calls[2]["model"] == "deep-model"


def test_escalation_prefers_effort_bump_on_reasoning_models(
    monkeypatch, tmp_path: Path,
) -> None:
    engine = _make_engine(monkeypatch, tmp_path, {"model": "openrouter/base"})
    _patch_failing_execute(monkeypatch)

    def script(i, kw):
        if i == 0:
            return _final_chunk("", tool_calls=_failing_tools(3))
        return _final_chunk("done")

    calls = _scripted_stream(monkeypatch, script)
    events = []
    engine.run_turn("hi", emit=events.append)
    routing = [e for e in events if e.kind == "routing"]
    assert len(routing) == 1
    assert "effort" in routing[0].text
    assert routing[0].model == "openrouter/base"
    assert calls[1]["model"] == "openrouter/base"
    assert calls[1]["extra_body"]["reasoning"]["effort"] == "high"


def test_escalation_skipped_when_budget_nearly_spent(monkeypatch, tmp_path: Path) -> None:
    engine = _make_engine(monkeypatch, tmp_path, {
        "model": "base-model",
        "tiers": {"deep": {"model": "deep-model"}},
    })
    monkeypatch.setattr("alpi.ledger.spend_fraction", lambda *a, **kw: 0.85)
    _patch_failing_execute(monkeypatch)

    def script(i, kw):
        if i == 0:
            return _final_chunk("", tool_calls=_failing_tools(3))
        return _final_chunk("done cheap")

    calls = _scripted_stream(monkeypatch, script)
    events = []
    engine.run_turn("hi", emit=events.append)
    assert not [e for e in events if e.kind == "routing"]
    assert calls[1]["model"] == "base-model"


def test_no_escalation_without_deep_tier_or_reasoning_support(
    monkeypatch, tmp_path: Path,
) -> None:
    engine = _make_engine(monkeypatch, tmp_path, {"model": "base-model"})
    _patch_failing_execute(monkeypatch)

    def script(i, kw):
        if i == 0:
            return _final_chunk("", tool_calls=_failing_tools(3))
        return _final_chunk("done")

    calls = _scripted_stream(monkeypatch, script)
    events = []
    engine.run_turn("hi", emit=events.append)
    assert not [e for e in events if e.kind == "routing"]
    assert calls[1]["model"] == "base-model"


def test_empty_reply_escalates_before_retry(monkeypatch, tmp_path: Path) -> None:
    engine = _make_engine(monkeypatch, tmp_path, {
        "model": "base-model",
        "tiers": {"deep": {"model": "deep-model"}},
    })

    def script(i, kw):
        if i == 0:
            return _final_chunk("")
        return _final_chunk("hola")

    calls = _scripted_stream(monkeypatch, script)
    events = []
    engine.run_turn("hi", emit=events.append)
    routing = [e for e in events if e.kind == "routing"]
    assert len(routing) == 1
    assert "empty reply" in routing[0].text
    assert calls[1]["model"] == "deep-model"
    done = next(e for e in events if e.kind == "assistant_done" and e.final)
    assert done.text == "hola"


def test_compaction_summarizer_routes_to_fast_tier(monkeypatch, tmp_path: Path) -> None:
    from types import SimpleNamespace

    engine = _make_engine(monkeypatch, tmp_path, {
        "model": "base-model",
        "tiers": {"fast": {"model": "flash-model"}},
    })
    seen: dict = {}

    def fake_compact(*, messages, user_text, ctx_window, summarize, policy, force):
        summarize("transcript", 100)
        return messages, SimpleNamespace(
            fired=False, tool_truncated=0, tokens_before=0, tokens_after=0,
            summarized_messages=0,
        )

    monkeypatch.setattr("alpi.compaction.compact", fake_compact)

    def fake_complete(messages, **kw):
        seen["model"] = kw.get("model")
        return SimpleNamespace(
            content="sum", tool_calls=[], input_tokens=0, output_tokens=0,
            cost_usd=0.0, raw=None,
        )

    monkeypatch.setattr("alpi.llm.complete", fake_complete)
    engine.compact_now(emit=lambda e: None)
    assert seen["model"] == "flash-model"


def test_live_tier_edit_applies_on_next_turn(monkeypatch, tmp_path: Path) -> None:
    engine = _make_engine(monkeypatch, tmp_path, {"model": "base-model"})
    monkeypatch.setenv("ALPI_TIER", "fast")
    calls = _scripted_stream(monkeypatch, lambda i, kw: _final_chunk("ok"))
    engine.run_turn("one", emit=lambda e: None)
    assert calls[0]["model"] == "base-model"
    (engine.home / "config.yaml").write_text(yaml.safe_dump({
        "model": "base-model",
        "tiers": {"fast": {"model": "flash-model"}},
    }))
    engine.run_turn("two", emit=lambda e: None)
    assert calls[-1]["model"] == "flash-model"


def test_fallback_routing_event_never_leaks_provider_exception_text(
    monkeypatch, tmp_path: Path,
) -> None:
    engine = _make_engine(monkeypatch, tmp_path, {
        "model": "primary",
        "fallback_models": ["backup"],
    })

    def script(i, kw):
        if kw.get("model") == "primary":
            raise RuntimeError(
                "401 from provider; request headers: Authorization: Bearer sk-secret-123"
            )
        return _final_chunk("ok")

    _scripted_stream(monkeypatch, script)
    events = []
    engine.run_turn("hi", emit=events.append)
    routing = next(e for e in events if e.kind == "routing")
    assert "Bearer" not in routing.text and "sk-secret" not in routing.text
    assert "primary" in routing.text and "backup" in routing.text


def test_compaction_fits_transcript_to_the_fast_tier_window(
    monkeypatch, tmp_path: Path,
) -> None:
    from types import SimpleNamespace

    engine = _make_engine(monkeypatch, tmp_path, {
        "model": "base-model",
        "tiers": {"fast": {"model": "flash-model"}},
    })
    monkeypatch.setattr(
        "alpi.ctx_window.resolve",
        lambda _h, _c, m: 2_000 if m == "flash-model" else 400_000,
    )
    for i in range(30):
        engine.session.messages.append({"role": "user", "content": f"q{i} " + "x" * 3000})
        engine.session.messages.append({"role": "assistant", "content": f"a{i} " + "y" * 3000})

    seen: dict = {}

    def fake_complete(messages, **kw):
        seen.setdefault("prompt", messages[-1]["content"])
        seen.setdefault("max_tokens", kw.get("max_tokens"))
        seen.setdefault("model", kw.get("model"))
        return SimpleNamespace(
            content="dense briefing", tool_calls=[], input_tokens=0,
            output_tokens=0, cost_usd=0.0, raw=None,
        )

    monkeypatch.setattr("alpi.llm.complete", fake_complete)
    engine.compact_now(emit=lambda e: None)

    assert seen["model"] == "flash-model"
    assert seen["max_tokens"] <= 800
    assert "elided to fit the summarizer window" in seen["prompt"]
    # ~500-token floor × 4 chars + prompt scaffolding: nowhere near the ~180k-char middle.
    assert len(seen["prompt"]) < 10_000


def test_cost_trail_covers_main_loop_wrap_and_tool_calls(monkeypatch, tmp_path: Path) -> None:
    """usd books the main loop, the forced close and tool calls, so one real turn must trail all three."""
    from alpi import run_ledger
    from alpi.tools import _state as tool_state_mod
    from alpi.tools.base import ToolResult

    engine = _make_engine(monkeypatch, tmp_path, {
        "model": "openrouter/x/y", "tools": {"max_steps_per_turn": 1},
    })

    def script(idx, _kw):
        if idx == 0:
            return {
                "final": True, "input_tokens": 10, "output_tokens": 5,
                "cost_usd": 0.06, "cost_source": "table-base",
                "generation_id": "gen-main", "provider": None,
                "tool_calls": [{"id": "t0", "name": "search", "arguments": "{}"}],
                "_text": "",
            }
        return {
            "final": True, "input_tokens": 20, "output_tokens": 8,
            "cost_usd": 0.50, "cost_source": "provider",
            "generation_id": "gen-wrap", "provider": "OpenInference",
            "tool_calls": [], "_text": "final answer",
        }

    _scripted_stream(monkeypatch, script)

    def execute(name, args, deny=frozenset()):
        tool_state_mod.record_usage(
            5, 2, 0.01, None, None, "provider",
            provider="DeepInfra", generation_id="gen-tool",
        )
        return ToolResult(ok=True, output="tool output")

    monkeypatch.setattr("alpi.tools.execute", execute)
    engine.run_turn("hi", emit=lambda _e: None)

    trail = engine._turn_cost_trail
    assert trail["generation_id"] == ["gen-main", "gen-tool", "gen-wrap"]
    assert trail["cost_source"] == ["table-base", "provider"]
    assert trail["provider"] == ["DeepInfra", "OpenInference"]

    row = run_ledger.read(engine.home)[0]
    assert row["generation_id"] == "gen-main,gen-tool,gen-wrap"
    assert row["cost_source"] == "table-base,provider"
    assert row["provider"] == "DeepInfra,OpenInference"
    assert row["usd"] == pytest.approx(0.57)


def test_cost_trail_covers_compaction_side_calls(monkeypatch, tmp_path: Path) -> None:
    """Compaction books spend through its own side-call path, so that callback must trail it too."""
    from alpi import compaction

    engine = _make_engine(monkeypatch, tmp_path, {"model": "openrouter/x/y"})
    monkeypatch.setattr("alpi.llm.complete", lambda **kw: SimpleNamespace(
        content="summary", tool_calls=[], input_tokens=900, output_tokens=40,
        cost_usd=0.02, raw=None, cached_tokens=0, cache_discount=None,
        cost_source="provider", provider="OpenInference", generation_id="gen-compact",
    ))
    summaries: list[str] = []

    def fake_compact(messages, user_text, ctx_window, summarize, policy=None, force=False):
        summaries.append(summarize("a transcript", 500))
        return list(messages), compaction.CompactionResult(
            fired=False, tool_truncated=0, summarized_messages=0,
            tokens_before=0, tokens_after=0,
        )

    monkeypatch.setattr("alpi.compaction.compact", fake_compact)
    engine.compact_now(emit=lambda _e: None)

    assert summaries == ["summary"]
    trail = engine._turn_cost_trail
    assert trail["generation_id"] == ["gen-compact"]
    assert trail["provider"] == ["OpenInference"]
    assert trail["cost_source"] == ["provider"]


def test_interactive_turn_does_not_replay_visible_text(monkeypatch, tmp_path: Path) -> None:
    engine = _make_engine(monkeypatch, tmp_path, {"model": "openrouter/x/y"})
    monkeypatch.delenv("ALPI_SCHEDULE_CHILD", raising=False)
    monkeypatch.delenv("ALPI_WORKGROUP_DISPATCH", raising=False)
    calls = _scripted_stream(monkeypatch, lambda i, kw: _final_chunk("hola"))
    engine.run_turn("hi", emit=lambda _e: None)
    assert calls[0]["replay_visible"] is False


def test_scheduled_turn_replays_so_a_stall_stays_retryable(monkeypatch, tmp_path: Path) -> None:
    """Nobody is watching a cron run, so replaying already-streamed text costs nothing and the retry gate opens."""
    engine = _make_engine(monkeypatch, tmp_path, {"model": "openrouter/x/y"})
    monkeypatch.setenv("ALPI_SCHEDULE_CHILD", "1")
    calls = _scripted_stream(monkeypatch, lambda i, kw: _final_chunk("hola"))
    engine.run_turn("hi", emit=lambda _e: None)
    assert calls[0]["replay_visible"] is True


def test_forced_close_also_replays_when_unattended(monkeypatch, tmp_path: Path) -> None:
    from alpi.tools.base import ToolResult

    engine = _make_engine(monkeypatch, tmp_path, {
        "model": "openrouter/x/y", "tools": {"max_steps_per_turn": 1},
    })
    monkeypatch.setenv("ALPI_SCHEDULE_CHILD", "1")
    calls = _scripted_stream(monkeypatch, lambda i, kw: (
        _final_chunk("", [{"id": "t0", "name": "search", "arguments": "{}"}]) if i == 0
        else _final_chunk("done")
    ))
    monkeypatch.setattr(
        "alpi.tools.execute",
        lambda name, args, deny=frozenset(): ToolResult(ok=True, output="ok"),
    )
    engine.run_turn("hi", emit=lambda _e: None)
    assert len(calls) >= 2
    assert all(c["replay_visible"] is True for c in calls)
