from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from alpi.config import Config, ToolsConfig
from alpi.engine import Engine
from alpi.tools.base import ToolResult


def _engine(monkeypatch, tmp_path: Path, max_steps: int) -> Engine:
    home = tmp_path / "h"
    home.mkdir()
    monkeypatch.setattr("alpi.engine._maybe_load_mcps", lambda _cfg: [])
    monkeypatch.setattr(Engine, "_build_system_prompt", lambda self: "you are alpi")
    monkeypatch.setattr("alpi.ctx_window.resolve", lambda _h, _c, _m: 100_000)
    monkeypatch.setattr("alpi.ledger.check", lambda *a, **kw: None)
    monkeypatch.setattr("alpi.ledger.record", lambda *a, **kw: None)
    monkeypatch.setattr("alpi.ledger.spend_fraction", lambda *a, **kw: None)
    cfg = Config(home=home, model="gpt-5.4-mini", tools=ToolsConfig(max_steps_per_turn=max_steps), raw={})
    return Engine(home=home, cfg=cfg)


def _tool_loop(monkeypatch, tool_steps: int, output_chars: int, text_chars: int = 0):
    seen = {"messages": [], "summaries": 0}

    def fake_stream(messages, tools, **kwargs):
        seen["messages"].append([dict(m) for m in messages])
        step = len(seen["messages"]) - 1
        if not tools:
            yield {"text_delta": "wrapped"}
            yield {"final": True, "tool_calls": [], "input_tokens": 1, "output_tokens": 1, "cost_usd": 0.0}
            return
        if step < tool_steps:
            if text_chars:
                yield {"text_delta": "y" * text_chars}
            yield {"tool_calls_delta": True}
            yield {
                "final": True, "input_tokens": 1, "output_tokens": 1, "cost_usd": 0.0,
                "tool_calls": [{"id": f"c{step}", "name": "search", "arguments": "{}"}],
            }
            return
        yield {"text_delta": "final answer"}
        yield {"final": True, "tool_calls": [], "input_tokens": 1, "output_tokens": 1, "cost_usd": 0.0}

    def fake_complete(**kw):
        seen["summaries"] += 1
        return SimpleNamespace(content="[BRIEFING]", input_tokens=1, output_tokens=1, cost_usd=0.0)

    monkeypatch.setattr("alpi.llm.stream", fake_stream)
    monkeypatch.setattr("alpi.llm.complete", fake_complete)
    monkeypatch.setattr(
        "alpi.tools.execute",
        lambda name, args, deny=frozenset(): ToolResult(ok=True, output="x" * output_chars),
    )
    return seen


def _no_orphans(messages: list[dict]) -> None:
    pending: set[str] = set()
    for m in messages:
        if m.get("role") == "assistant":
            assert not pending, pending
            pending = {c["id"] for c in (m.get("tool_calls") or [])}
        elif m.get("role") == "tool":
            assert m["tool_call_id"] in pending, m["tool_call_id"]
            pending.discard(m["tool_call_id"])
        else:
            assert not pending, (m.get("role"), pending)
    assert not pending, pending


def test_compaction_fires_mid_turn_and_prunes_old_tool_outputs(monkeypatch, tmp_path: Path) -> None:
    engine = _engine(monkeypatch, tmp_path, max_steps=30)
    seen = _tool_loop(monkeypatch, tool_steps=14, output_chars=30_000)
    events: list = []
    engine.run_turn("read everything", emit=events.append)

    kinds = [e.kind for e in events]
    assert "auto_compact" in kinds
    assert kinds.index("auto_compact") > kinds.index("tool_end")
    last = seen["messages"][-1]
    assert any("elided by auto-compact" in str(m.get("content") or "") for m in last)
    _no_orphans(last)
    done = next(e for e in events if e.kind == "assistant_done" and e.final)
    assert done.text == "final answer"
    assert (tmp_path / "h" / "logs" / "compaction.jsonl").exists()


def test_compaction_summarizes_mid_turn_when_pruning_is_not_enough(monkeypatch, tmp_path: Path) -> None:
    engine = _engine(monkeypatch, tmp_path, max_steps=30)
    seen = _tool_loop(monkeypatch, tool_steps=14, output_chars=1_000, text_chars=25_000)
    events: list = []
    engine.run_turn("read everything", emit=events.append)

    assert seen["summaries"] >= 1
    last = seen["messages"][-1]
    assert any(str(m.get("content") or "").startswith("[auto-compacted summary]") for m in last)
    _no_orphans(last)
    assert next(e for e in events if e.kind == "assistant_done" and e.final).text == "final answer"


def test_wrap_up_still_runs_after_a_mid_turn_compaction(monkeypatch, tmp_path: Path) -> None:
    engine = _engine(monkeypatch, tmp_path, max_steps=12)
    seen = _tool_loop(monkeypatch, tool_steps=40, output_chars=30_000)
    events: list = []
    engine.run_turn("never ends", emit=events.append)

    assert "auto_compact" in [e.kind for e in events]
    assert len(seen["messages"]) == 13
    done = next(e for e in events if e.kind == "assistant_done" and e.final)
    assert done.text == "wrapped"
