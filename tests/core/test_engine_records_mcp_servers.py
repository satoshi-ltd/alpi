"""A turn must hand its run the MCP servers of the process, which the sweep can only reach through it."""

from __future__ import annotations

from pathlib import Path

import pytest

from alpi import runs
from alpi.config import Config, ToolsConfig
from alpi.engine import Engine


@pytest.fixture
def engine(monkeypatch, tmp_path: Path) -> Engine:
    home = tmp_path / "h"
    home.mkdir()
    monkeypatch.setattr("alpi.engine._maybe_load_mcps", lambda _cfg: [])
    monkeypatch.setattr(Engine, "_build_system_prompt", lambda self: "you are alpi")
    monkeypatch.setattr("alpi.ctx_window.resolve", lambda _h, _c, _m: 400_000)
    monkeypatch.setattr("alpi.ledger.check", lambda *a, **kw: None)
    monkeypatch.setattr("alpi.ledger.record", lambda *a, **kw: None)
    monkeypatch.setattr(runs, "proc_starttime", lambda pid: f"start-{pid}")
    cfg = Config(home=home, model="gpt-5.4-mini", tools=ToolsConfig(max_steps_per_turn=4), raw={})
    return Engine(home=home, cfg=cfg)


def _observe_mid_turn(monkeypatch, engine: Engine) -> dict:
    # A run that ends well forgets what it spawned, so the registry can only be read in flight.
    seen: dict[str, object] = {}

    def fake_stream(messages, tools, **kwargs):
        seen["recorded"] = runs._recorded_children(engine.home, engine.active_run_id)
        yield {"final": True, "text": "done", "input_tokens": 1,
               "output_tokens": 1, "cost_usd": 0.0, "tool_calls": []}

    monkeypatch.setattr("alpi.llm.stream", fake_stream)
    return seen


def test_a_turn_records_the_live_mcp_servers_under_its_run(engine: Engine, monkeypatch) -> None:
    monkeypatch.setattr("alpi.engine._live_mcp_pids", lambda: [4242, 4343])
    seen = _observe_mid_turn(monkeypatch, engine)

    engine.run_turn("hola", emit=lambda e: None)

    assert [pgid for pgid, _start in seen["recorded"]] == [4242, 4343]


def test_a_turn_with_no_mcp_servers_records_nothing(engine: Engine, monkeypatch) -> None:
    monkeypatch.setattr("alpi.engine._live_mcp_pids", lambda: [])
    seen = _observe_mid_turn(monkeypatch, engine)

    engine.run_turn("hola", emit=lambda e: None)

    assert seen["recorded"] == []


def test_a_turn_that_ends_well_leaves_no_registry_behind(engine: Engine, monkeypatch) -> None:
    monkeypatch.setattr("alpi.engine._live_mcp_pids", lambda: [4242])
    _observe_mid_turn(monkeypatch, engine)

    engine.run_turn("hola", emit=lambda e: None)

    assert not runs.children_path(engine.home, engine.last_run_id).exists()
