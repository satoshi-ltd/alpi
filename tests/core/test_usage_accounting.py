"""Every LLM call site must land its tokens/cost in the ledger (and session where one exists)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import yaml

from alpi import config as cfg_mod
from alpi import ledger
from alpi.tools import _state as tool_state_mod


def _completion(content: str = "done", tokens_in: int = 100, tokens_out: int = 50):
    return SimpleNamespace(
        content=content, tool_calls=[], input_tokens=tokens_in,
        output_tokens=tokens_out, cost_usd=0.01, raw=None,
    )


def _sink_capture():
    calls: list[tuple[int, int, float]] = []
    tool_state_mod.set_usage_sink(lambda i, o, c: calls.append((i, o, c)))
    return calls


def test_web_extract_records_usage_main_and_override(monkeypatch, tmp_path: Path) -> None:
    home = tmp_path / "h"
    home.mkdir()
    (home / "config.yaml").write_text(yaml.safe_dump({
        "model": "openrouter/main",
        "tools": {"web_extract": {"model": "openrouter/cheap"}},
    }))
    cfg = cfg_mod.load(home)
    monkeypatch.setattr("alpi.config.load", lambda _h: cfg)
    monkeypatch.setattr("alpi.home.get_home", lambda: home)
    monkeypatch.setattr("alpi.llm.complete", lambda **kw: _completion("summary"))
    from alpi.tools.base import ToolResult
    monkeypatch.setattr(
        "alpi.tools.web_fetch.WebFetch.run",
        lambda self, **kw: ToolResult(ok=True, output="page body"),
    )
    monkeypatch.setattr("alpi.tools._sandbox.require_network", lambda name: None)
    from alpi.tools.web_extract import WebExtract

    calls = _sink_capture()
    try:
        assert WebExtract().run(url="https://example.com").ok
        assert calls == [(100, 50, 0.01)]

        cfg.tools.web_extract.model = ""
        assert WebExtract().run(url="https://example.com").ok
        assert calls == [(100, 50, 0.01)] * 2
    finally:
        tool_state_mod.set_usage_sink(None)


def test_knowledge_maintain_records_usage(monkeypatch, tmp_path: Path) -> None:
    home = tmp_path / "h"
    home.mkdir()
    (home / "config.yaml").write_text(yaml.safe_dump({"model": "openrouter/main"}))
    root = tmp_path / "kb"
    root.mkdir()
    monkeypatch.setattr("alpi.llm.complete", lambda **kw: _completion("{}"))
    from alpi.tools.knowledge_base import maintain_knowledge

    calls = _sink_capture()
    try:
        maintain_knowledge(home, root, topic="pricing", apply=False)
        assert calls == [(100, 50, 0.01)]
    finally:
        tool_state_mod.set_usage_sink(None)


def _make_engine(monkeypatch, tmp_path: Path, data: dict):
    from alpi.engine import Engine

    home = tmp_path / "h"
    home.mkdir()
    (home / "config.yaml").write_text(yaml.safe_dump(data))
    monkeypatch.delenv("ALPI_TIER", raising=False)
    monkeypatch.setattr("alpi.engine._maybe_load_mcps", lambda _cfg: [])
    monkeypatch.setattr(Engine, "_build_system_prompt", lambda self: "sys")
    monkeypatch.setattr("alpi.ctx_window.resolve", lambda *a: 400_000)
    monkeypatch.setattr("alpi.ledger.check", lambda *a, **kw: None)
    return Engine(home=home, cfg=cfg_mod.load(home))


def test_compaction_summarizer_and_candidates_record_usage(
    monkeypatch, tmp_path: Path,
) -> None:
    engine = _make_engine(monkeypatch, tmp_path, {"model": "openrouter/main"})
    monkeypatch.setattr(
        "alpi.llm.complete", lambda **kw: _completion('{"candidates": []}'),
    )

    def fake_compact(*, messages, user_text, ctx_window, summarize, policy, force):
        summarize("transcript", 100)
        rebuilt = messages + [
            {"role": "system", "content": "[auto-compacted summary]\nthe gist"},
        ]
        return rebuilt, SimpleNamespace(
            fired=True, tool_truncated=0, tokens_before=100, tokens_after=10,
            summarized_messages=3,
        )

    monkeypatch.setattr("alpi.compaction.compact", fake_compact)
    tool_state_mod.reset_turn_usage()
    events = []
    engine.compact_now(emit=events.append)

    tally = tool_state_mod.get_turn_usage()
    assert tally["tokens_in"] == 200 and tally["tokens_out"] == 100
    assert engine.session.input_tokens == 200
    assert engine.session.output_tokens == 100
    assert round(engine.session.cost_usd, 4) == 0.02
    data = ledger.load(engine.home)
    assert data["profile"]["tokens"] == 300
    assert round(data["profile"]["usd"], 4) == 0.02
    usage_events = [e for e in events if e.kind == "usage"]
    assert len(usage_events) == 2


def test_memory_reviewer_records_to_ledger(monkeypatch, tmp_path: Path) -> None:
    from alpi import review

    home = tmp_path / "h"
    home.mkdir()
    (home / "config.yaml").write_text(yaml.safe_dump({"model": "openrouter/main"}))
    cfg = cfg_mod.load(home)
    monkeypatch.setattr("alpi.llm.complete", lambda **kw: _completion("Nothing to save."))
    review._run_review(home, cfg, [{"role": "user", "content": "hi"}])
    data = ledger.load(home)
    assert data["profile"]["tokens"] == 150
    assert round(data["profile"]["usd"], 4) == 0.01


def test_memory_reviewer_skips_when_budget_exhausted(monkeypatch, tmp_path: Path) -> None:
    from alpi import review

    home = tmp_path / "h"
    home.mkdir()
    (home / "config.yaml").write_text(yaml.safe_dump({"model": "openrouter/main"}))
    cfg = cfg_mod.load(home)
    llm_calls = []
    monkeypatch.setattr(
        "alpi.llm.complete", lambda **kw: llm_calls.append(1) or _completion(),
    )

    def raise_exceeded(*a, **kw):
        raise ledger.BudgetExceeded("usd", 1.0, 2.0)

    monkeypatch.setattr("alpi.ledger.check", raise_exceeded)
    assert review._run_review(home, cfg, [{"role": "user", "content": "hi"}]) == 0
    assert llm_calls == []


def test_identity_draft_records_to_ledger(monkeypatch, tmp_path: Path) -> None:
    from alpi import identity
    from alpi.home import agent_path

    home = tmp_path / "h"
    home.mkdir()
    (home / "config.yaml").write_text(yaml.safe_dump({"model": "openrouter/main"}))
    cfg = cfg_mod.load(home)
    ap = agent_path(home)
    ap.parent.mkdir(parents=True, exist_ok=True)
    ap.write_text("A test persona.")
    monkeypatch.setattr("alpi.llm.complete", lambda **kw: _completion("a bio"))
    assert identity.draft_bio_from_agent(home, cfg) == "a bio"
    data = ledger.load(home)
    assert data["profile"]["tokens"] == 150
    assert round(data["profile"]["usd"], 4) == 0.01


def test_delegate_stops_before_llm_when_budget_exhausted(
    monkeypatch, tmp_home_no_env: Path,
) -> None:
    from alpi.tools.delegate import Delegate

    llm_calls = []
    monkeypatch.setattr(
        "alpi.llm.complete", lambda **kw: llm_calls.append(1) or _completion(),
    )

    def raise_exceeded(*a, **kw):
        raise ledger.BudgetExceeded("usd", 1.0, 2.0)

    monkeypatch.setattr("alpi.ledger.check", raise_exceeded)
    out = Delegate().run(goal="rename files")
    assert not out.ok
    assert "budget" in out.error.lower()
    assert llm_calls == []


def test_research_stops_before_llm_when_budget_exhausted(
    monkeypatch, tmp_home_no_env: Path,
) -> None:
    from alpi.tools.research import Research

    llm_calls = []
    monkeypatch.setattr(
        "alpi.llm.complete", lambda **kw: llm_calls.append(1) or _completion(),
    )

    def raise_exceeded(*a, **kw):
        raise ledger.BudgetExceeded("usd", 1.0, 2.0)

    monkeypatch.setattr("alpi.ledger.check", raise_exceeded)
    out = Research().run(brief="what is X")
    assert not out.ok
    assert "budget" in out.error.lower()
    assert llm_calls == []


def test_compaction_summarize_skipped_when_budget_exhausted(
    monkeypatch, tmp_path: Path,
) -> None:
    engine = _make_engine(monkeypatch, tmp_path, {"model": "openrouter/main"})

    def raise_exceeded(*a, **kw):
        raise ledger.BudgetExceeded("usd", 1.0, 2.0)

    monkeypatch.setattr("alpi.ledger.check", raise_exceeded)
    llm_calls = []
    monkeypatch.setattr(
        "alpi.llm.complete", lambda **kw: llm_calls.append(1) or _completion(),
    )

    def fake_compact(*, messages, user_text, ctx_window, summarize, policy, force):
        assert summarize("transcript", 100) == ""
        return messages, SimpleNamespace(
            fired=False, tool_truncated=0, tokens_before=0, tokens_after=0,
            summarized_messages=0,
        )

    monkeypatch.setattr("alpi.compaction.compact", fake_compact)
    engine.compact_now(emit=lambda e: None)
    assert llm_calls == []
    assert engine.session.input_tokens == 0


def test_engine_blocks_first_stream_when_compaction_crossed_the_cap(
    monkeypatch, tmp_path: Path,
) -> None:
    engine = _make_engine(monkeypatch, tmp_path, {"model": "openrouter/main"})
    checks = {"n": 0}

    def check(home, budget):
        checks["n"] += 1
        if checks["n"] > 1:
            raise ledger.BudgetExceeded("usd", 1.0, 2.0)

    monkeypatch.setattr("alpi.ledger.check", check)
    stream_calls = []

    def fake_stream(**kw):
        stream_calls.append(1)
        return iter(())

    monkeypatch.setattr("alpi.llm.stream", fake_stream)
    events = []
    engine.run_turn("hi", emit=events.append)
    assert stream_calls == []
    assert any(e.kind == "error" and "budget" in e.text.lower() for e in events)


def test_delegate_synthesis_blocked_when_cap_crossed_after_last_step(
    monkeypatch, tmp_home_no_env: Path,
) -> None:
    from alpi.tools.delegate import MAX_STEPS, Delegate

    completions = []

    def fake_complete(**kw):
        completions.append(1)
        return SimpleNamespace(
            content="", input_tokens=1, output_tokens=1, cost_usd=0.5, raw=None,
            tool_calls=[{"id": "t1", "name": "nope", "arguments": "{}"}],
        )

    monkeypatch.setattr("alpi.llm.complete", fake_complete)
    checks = {"n": 0}

    def check(home, budget):
        checks["n"] += 1
        if checks["n"] > MAX_STEPS:
            raise ledger.BudgetExceeded("usd", 1.0, 2.0)

    monkeypatch.setattr("alpi.ledger.check", check)
    out = Delegate().run(goal="loop forever")
    assert not out.ok
    assert "budget" in out.error.lower()
    assert len(completions) == MAX_STEPS


def test_research_synthesis_blocked_when_cap_crossed_after_last_step(
    monkeypatch, tmp_home_no_env: Path,
) -> None:
    from alpi.tools.research import DEPTH_STEPS_DEFAULTS, Research

    steps = DEPTH_STEPS_DEFAULTS["fast"]
    completions = []

    def fake_complete(**kw):
        completions.append(1)
        return SimpleNamespace(
            content="", input_tokens=1, output_tokens=1, cost_usd=0.5, raw=None,
            tool_calls=[{"id": "t1", "name": "nope", "arguments": "{}"}],
        )

    monkeypatch.setattr("alpi.llm.complete", fake_complete)
    checks = {"n": 0}

    def check(home, budget):
        checks["n"] += 1
        if checks["n"] > steps:
            raise ledger.BudgetExceeded("usd", 1.0, 2.0)

    monkeypatch.setattr("alpi.ledger.check", check)
    out = Research().run(brief="loop forever", depth="fast")
    assert not out.ok
    assert "budget" in out.error.lower()
    assert len(completions) == steps


def test_identity_draft_blocked_when_budget_exhausted(
    monkeypatch, tmp_path: Path,
) -> None:
    import pytest

    from alpi import identity
    from alpi.home import agent_path

    home = tmp_path / "h"
    home.mkdir()
    (home / "config.yaml").write_text(yaml.safe_dump({"model": "openrouter/main"}))
    cfg = cfg_mod.load(home)
    ap = agent_path(home)
    ap.parent.mkdir(parents=True, exist_ok=True)
    ap.write_text("A test persona.")
    llm_calls = []
    monkeypatch.setattr(
        "alpi.llm.complete", lambda **kw: llm_calls.append(1) or _completion(),
    )

    def raise_exceeded(*a, **kw):
        raise ledger.BudgetExceeded("usd", 1.0, 2.0)

    monkeypatch.setattr("alpi.ledger.check", raise_exceeded)
    with pytest.raises(ledger.BudgetExceeded):
        identity.draft_bio_from_agent(home, cfg)
    assert llm_calls == []
