from __future__ import annotations

import json
from pathlib import Path

import pytest

from alpi import compaction
from alpi.config import CompactionConfig, Config, ToolsConfig
from alpi.engine import Engine
from tests.core.test_engine_compact_midturn import _no_orphans, _tool_loop


def _engine(monkeypatch, tmp_path: Path, max_steps: int, prune_after: int = 120_000) -> Engine:
    home = tmp_path / "h"
    home.mkdir()
    monkeypatch.setattr("alpi.engine._maybe_load_mcps", lambda _cfg: [])
    monkeypatch.setattr(Engine, "_build_system_prompt", lambda self: "you are alpi")
    monkeypatch.setattr("alpi.ctx_window.resolve", lambda _h, _c, _m: 1_000_000)
    monkeypatch.setattr("alpi.ledger.check", lambda *a, **kw: None)
    monkeypatch.setattr("alpi.ledger.record", lambda *a, **kw: None)
    monkeypatch.setattr("alpi.ledger.spend_fraction", lambda *a, **kw: None)
    cfg = Config(
        home=home, model="gpt-5.4-mini", tools=ToolsConfig(max_steps_per_turn=max_steps),
        compaction=CompactionConfig(prune_after_tokens=prune_after), raw={},
    )
    return Engine(home=home, cfg=cfg)


def _log(tmp_path: Path) -> list[dict]:
    path = tmp_path / "h" / "logs" / "compaction.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_a_long_turn_prunes_old_tool_output_in_batches_without_a_summary(monkeypatch, tmp_path: Path) -> None:
    engine = _engine(monkeypatch, tmp_path, max_steps=70)
    seen = _tool_loop(monkeypatch, tool_steps=60, output_chars=20_000)
    events: list = []
    engine.run_turn("read everything", emit=events.append)

    assert seen["summaries"] == 0
    passes = [row for row in _log(tmp_path) if row["trigger"] == "prune"]
    assert passes and all(not row["fired"] for row in passes)
    trims = [e for e in events if e.kind == "auto_compact"]
    assert len(trims) == len(passes) and all(e.text.startswith("old tool output trimmed") for e in trims)
    freed_per_pass = 20_000 // compaction.CHARS_PER_TOKEN - (
        compaction.TOOL_PRUNE_KEEP_HEAD_CHARS + compaction.TOOL_PRUNE_KEEP_TAIL_CHARS
    ) // compaction.CHARS_PER_TOKEN
    min_batch = -(-compaction.PRUNE_MIN_SAVED_TOKENS // freed_per_pass)
    assert all(row["tool_truncated"] >= min_batch for row in passes)
    assert len(passes) <= 60 // min_batch
    first_prune_step = next(
        n for n, msgs in enumerate(seen["messages"])
        if any("elided by auto-compact" in str(m.get("content") or "") for m in msgs)
    )
    assert 0 < first_prune_step < 60
    last = seen["messages"][-1]
    _no_orphans(last)
    tail_tools = [m for m in last[-compaction.DEFAULT_KEEP_TAIL:] if m.get("role") == "tool"]
    assert tail_tools and all("x" * 20_000 in m["content"] for m in tail_tools)
    assert max(compaction.estimate_messages_tokens(msgs) for msgs in seen["messages"]) < 200_000
    assert next(e for e in events if e.kind == "assistant_done" and e.final).text == "final answer"


def test_a_twelve_step_turn_never_prunes(monkeypatch, tmp_path: Path) -> None:
    engine = _engine(monkeypatch, tmp_path, max_steps=20)
    seen = _tool_loop(monkeypatch, tool_steps=12, output_chars=20_000)
    engine.run_turn("read a little", emit=lambda e: None)

    assert _log(tmp_path) == []
    assert not any("elided by auto-compact" in str(m.get("content") or "") for m in seen["messages"][-1])


def test_zero_turns_the_watermark_off(monkeypatch, tmp_path: Path) -> None:
    engine = _engine(monkeypatch, tmp_path, max_steps=70, prune_after=0)
    seen = _tool_loop(monkeypatch, tool_steps=60, output_chars=20_000)
    engine.run_turn("read everything", emit=lambda e: None)

    assert _log(tmp_path) == []
    assert not any("elided by auto-compact" in str(m.get("content") or "") for m in seen["messages"][-1])


def _history(results: int, chars: int) -> list[dict]:
    messages: list[dict] = [{"role": "system", "content": "s"}, {"role": "user", "content": "go"}]
    for n in range(results):
        messages.append({"role": "assistant", "content": "", "tool_calls": [{"id": f"c{n}", "function": {"name": "t", "arguments": "{}"}}]})
        messages.append({"role": "tool", "tool_call_id": f"c{n}", "content": "x" * chars})
    return messages


@pytest.mark.parametrize("results, chars, prunes", [
    (20, 20_000, False),
    (30, 20_000, True),
    (6, 200_000, True),
])
def test_the_watermark_prunes_only_past_the_threshold_and_a_worthwhile_batch(results, chars, prunes) -> None:
    messages = _history(results, chars)
    out = compaction.prune_past_watermark(messages, 120_000)
    assert (out is not None) is prunes
    if out is not None:
        new_messages, result = out
        assert result.tokens_after < result.tokens_before
        assert new_messages[-compaction.DEFAULT_KEEP_TAIL:] == messages[-compaction.DEFAULT_KEEP_TAIL:]
        assert messages[3]["content"] == "x" * chars


def test_a_pass_that_frees_too_little_waits() -> None:
    messages = _history(30, 20_000)
    first, _ = compaction.prune_past_watermark(messages, 120_000)
    first.extend(_history(1, 20_000)[2:])
    assert compaction.prune_past_watermark(first, 120_000) is None
