"""Pin the contract: only the terminal `assistant_done` of a turn carries `final=True`; preamble emissions before tool calls do not."""

from __future__ import annotations

from pathlib import Path

import pytest

from alpi.config import Config, ToolsConfig
from alpi.engine import Engine


@pytest.fixture
def patched_engine(monkeypatch, tmp_path: Path):
    home = tmp_path / "h"
    home.mkdir()
    monkeypatch.setattr("alpi.engine._maybe_load_mcps", lambda _cfg: [])
    monkeypatch.setattr(Engine, "_build_system_prompt", lambda self: "you are alpi")
    monkeypatch.setattr("alpi.ctx_window.resolve", lambda _h, _c, _m: 400_000)
    monkeypatch.setattr("alpi.ledger.check", lambda *a, **kw: None)
    monkeypatch.setattr("alpi.ledger.record", lambda *a, **kw: None)
    cfg = Config(
        home=home,
        model="gpt-5.4-mini",
        tools=ToolsConfig(max_steps_per_turn=6),
        raw={},
    )
    return Engine(home=home, cfg=cfg)


def _final_chunk(text: str, tool_calls=None):
    return {
        "final": True,
        "text": text,
        "input_tokens": 10,
        "output_tokens": 5,
        "cost_usd": 0.0,
        "tool_calls": tool_calls or [],
    }


def _stub_stream(monkeypatch, scripted_chunks: list[dict]):
    calls = {"i": 0}

    def fake_stream(messages, tools, **kwargs):
        idx = calls["i"]
        if idx >= len(scripted_chunks):
            yield _final_chunk("")
            return
        calls["i"] += 1
        chunk = dict(scripted_chunks[idx])
        text = chunk.pop("text", "")
        if text:
            yield {"text_delta": text}
        yield chunk

    monkeypatch.setattr("alpi.llm.stream", fake_stream)
    return calls


def test_only_terminal_assistant_done_is_marked_final(
    patched_engine: Engine, monkeypatch,
) -> None:
    """Preamble (text + tool_calls in the same step) → final=False; only the closing text-only step is final."""
    chunks = [
        _final_chunk("Let me check things first.", tool_calls=[{
            "id": "tc1",
            "name": "todo",
            "arguments": '{"action": "list"}',
        }]),
        _final_chunk("¡Buenos días!"),
    ]
    _stub_stream(monkeypatch, chunks)

    events = []
    patched_engine.run_turn("morning", emit=lambda e: events.append(e))

    dones = [e for e in events if e.kind == "assistant_done"]
    assert [e.text for e in dones] == ["Let me check things first.", "¡Buenos días!"]
    assert [e.final for e in dones] == [False, True]


def test_single_step_reply_is_final(patched_engine: Engine, monkeypatch) -> None:
    """A turn with no tool calls emits a single final assistant_done."""
    _stub_stream(monkeypatch, [_final_chunk("hola")])

    events = []
    patched_engine.run_turn("hi", emit=lambda e: events.append(e))

    dones = [e for e in events if e.kind == "assistant_done"]
    assert len(dones) == 1
    assert dones[0].final is True
    assert dones[0].text == "hola"
