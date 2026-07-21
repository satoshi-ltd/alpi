"""Inbound link.ask runs the target turn under a peer:<id> connection so spend attributes to the caller, not the generic host bucket."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

from alpi.alp import handlers
from alpi.engine import AgentEvent


def _capture_engine(captured: dict):
    class _FakeEngine:
        def __init__(self, home, cfg):
            self.session = SimpleNamespace(id="s1", messages=[])

        def run_turn(self, prompt, emit, source, persist_inflight):
            captured["connection_id"] = self.connection_context.connection_id
            captured["source"] = self.connection_context.source
            emit(AgentEvent(kind="assistant_done", text="hi", final=True))
            emit(AgentEvent(kind="usage", tokens_in=1, tokens_out=1, cost=0.0))

    return _FakeEngine


def _patch_threads(monkeypatch) -> None:
    monkeypatch.setattr("alpi.alp.mention_thread.load", lambda home, pid: [])
    monkeypatch.setattr("alpi.alp.mention_thread.hydrate", lambda msgs, thread: None)
    monkeypatch.setattr("alpi.alp.mention_thread.append", lambda *a, **kw: None)


def _patch_engine(monkeypatch, fake) -> None:
    monkeypatch.setattr("alpi.alp.handlers.Engine", fake)
    monkeypatch.setattr("alpi.engine.Engine", fake)


def test_inbound_turn_runs_under_peer_connection(tmp_path: Path, monkeypatch) -> None:
    captured: dict = {}
    _patch_engine(monkeypatch, _capture_engine(captured))
    monkeypatch.setattr("alpi.alp.handlers.cfg_mod.load", lambda home: None)
    _patch_threads(monkeypatch)

    result = handlers._run_turn(tmp_path, "hola", "alexandra", handlers._ActiveTurn())

    assert captured["connection_id"] == "peer:alexandra"
    assert captured["source"] == "peer"
    assert result["text"] == "hi"


def test_inbound_stream_runs_under_peer_connection(tmp_path: Path, monkeypatch) -> None:
    captured: dict = {}
    _patch_engine(monkeypatch, _capture_engine(captured))
    monkeypatch.setattr("alpi.alp.handlers.cfg_mod.load", lambda home: None)
    _patch_threads(monkeypatch)

    async def run():
        gen = handlers._run_turn_stream(
            tmp_path, "hola", "alexandra", handlers._ActiveTurn(), asyncio.Lock(),
        )
        return [item async for item in gen]

    out = asyncio.run(run())

    assert captured["connection_id"] == "peer:alexandra"
    assert captured["source"] == "peer"
    assert any(i.get("kind") == "final" for i in out)


def test_inbound_turn_attributes_spend_to_peer_bucket(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "h"
    home.mkdir()
    (home / "config.yaml").write_text("model: m\n")

    from alpi.engine import Engine
    monkeypatch.setattr("alpi.engine._maybe_load_mcps", lambda _cfg: [])
    monkeypatch.setattr(Engine, "_build_system_prompt", lambda self: "sys")
    monkeypatch.setattr("alpi.ctx_window.resolve", lambda _h, _c, _m: 400_000)
    _patch_threads(monkeypatch)

    def fake_stream(messages, tools, **kwargs):
        yield {
            "final": True, "text": "hi",
            "input_tokens": 100, "output_tokens": 10, "cost_usd": 0.01,
            "tool_calls": [],
        }

    monkeypatch.setattr("alpi.llm.stream", fake_stream)

    handlers._run_turn(home, "hola", "alexandra", handlers._ActiveTurn())

    from alpi import ledger
    snap = ledger.snapshot(home)
    assert "peer:alexandra" in snap.get("by_connection", {})
    assert snap["by_connection"]["peer:alexandra"]["usd"] > 0
