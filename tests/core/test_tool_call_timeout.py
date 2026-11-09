from __future__ import annotations

import time
from pathlib import Path

import pytest

from alpi import tools as tools_mod
from alpi.core.run_context import RunContext
from alpi.core.tool_executor import ToolExecutor
from alpi.tools.base import Tool, ToolResult


class _Slow(Tool):
    name = "zz_slow"
    description = "sleeps"
    parameters = {"type": "object", "properties": {"seconds": {"type": "number"}}}

    def run(self, seconds: float = 0.0) -> ToolResult:
        time.sleep(seconds)
        return ToolResult(ok=True, output=f"slept {seconds}")


class _SlowExempt(_Slow):
    name = "zz_slow_exempt"
    call_timeout_exempt = True


@pytest.fixture
def registry(monkeypatch):
    saved = dict(tools_mod._TOOLS)
    tools_mod.register(_Slow)
    tools_mod.register(_SlowExempt)
    yield
    tools_mod._TOOLS.clear()
    tools_mod._TOOLS.update(saved)


def _executor(tmp_path: Path, **kw) -> ToolExecutor:
    ctx = RunContext.create(home=tmp_path, workspace=tmp_path, profile="p", source="user", session_id="s", connection_id="host")
    return ToolExecutor(ctx, **kw)


def test_a_tool_past_the_cap_returns_a_transient_failure_and_the_turn_moves_on(registry, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("alpi.core.tool_executor._MIN_CALL_TIMEOUT_S", 0.05)
    ex = _executor(tmp_path, call_timeout_s=0.2)
    started = time.monotonic()
    result = ex.execute("zz_slow", {"seconds": 2.0})
    assert time.monotonic() - started < 1.0
    assert result.ok is False and result.transient is True
    assert "did not finish within 0s" in result.error or "did not finish within" in result.error


def test_a_fast_tool_is_unaffected(registry, tmp_path: Path) -> None:
    ex = _executor(tmp_path, call_timeout_s=5.0)
    result = ex.execute("zz_slow", {"seconds": 0.0})
    assert result.ok and result.output == "slept 0.0"


def test_an_exempt_tool_gets_no_deadline(registry, tmp_path: Path) -> None:
    ex = _executor(tmp_path, call_timeout_s=0.1)
    ex.turn_deadline = time.monotonic() + 0.1
    assert ex.call_deadline("zz_slow_exempt") is None
    result = ex.execute("zz_slow_exempt", {"seconds": 0.3})
    assert result.ok


def test_the_turn_deadline_shortens_the_cap_and_zero_disables_it(registry, tmp_path: Path) -> None:
    ex = _executor(tmp_path, call_timeout_s=600.0)
    ex.turn_deadline = time.monotonic() + 90.0
    assert 88.0 < ex.call_deadline("zz_slow") <= 90.0
    ex.turn_deadline = time.monotonic() + 20.0
    assert ex.call_deadline("zz_slow") == 600.0
    off = _executor(tmp_path, call_timeout_s=0.0)
    assert off.call_deadline("zz_slow") is None


def test_a_timed_out_call_is_journaled_as_a_failure(registry, tmp_path: Path, monkeypatch) -> None:
    from alpi import runs
    monkeypatch.setattr("alpi.core.tool_executor._MIN_CALL_TIMEOUT_S", 0.05)
    ex = _executor(tmp_path, call_timeout_s=0.1)
    ex.execute("zz_slow", {"seconds": 1.0})
    events = runs.read(tmp_path, ex.context.run_id)["events"]
    finished = [e for e in events if e["kind"] == "tool.finished"]
    assert finished and finished[-1]["data"]["ok"] is False
    assert "did not finish" in finished[-1]["data"]["error"]


def test_config_reads_and_round_trips_the_cap(tmp_path: Path) -> None:
    from alpi import config as cfg_mod
    (tmp_path / "config.yaml").write_text("model: m\ntools:\n  call_timeout_s: 45\n")
    cfg = cfg_mod.load(tmp_path)
    assert cfg.tools.call_timeout_s == 45.0
    assert cfg_mod._tools_delta(cfg)["call_timeout_s"] == 45.0
    (tmp_path / "config.yaml").write_text("model: m\ntools:\n  call_timeout_s: true\n")
    assert cfg_mod.load(tmp_path).tools.call_timeout_s == 600.0
    (tmp_path / "config.yaml").write_text("model: m\ntools:\n  call_timeout_s: -3\n")
    assert cfg_mod.load(tmp_path).tools.call_timeout_s == 0.0


def test_the_engine_hands_its_soft_deadline_to_the_executor(monkeypatch, tmp_path: Path) -> None:
    from alpi.config import Config, ToolsConfig
    from alpi.engine import Engine
    home = tmp_path / "h"
    home.mkdir()
    monkeypatch.setattr("alpi.engine._maybe_load_mcps", lambda _cfg: [])
    monkeypatch.setattr(Engine, "_build_system_prompt", lambda self: "you are alpi")
    monkeypatch.setattr("alpi.ctx_window.resolve", lambda *a: 400_000)
    monkeypatch.setattr("alpi.ledger.check", lambda *a, **kw: None)
    monkeypatch.setattr("alpi.ledger.record", lambda *a, **kw: None)
    monkeypatch.setenv("ALPI_TURN_BUDGET_S", "120")
    seen: dict = {}

    def fake_stream(messages, tools, **kwargs):
        from alpi.core.tool_executor import current
        ex = current()
        seen["cap"] = ex.call_timeout_s
        seen["deadline"] = ex.call_deadline("read_file")
        yield {"text_delta": "ok"}
        yield {"final": True, "tool_calls": [], "input_tokens": 1, "output_tokens": 1, "cost_usd": 0.0}

    monkeypatch.setattr("alpi.llm.stream", fake_stream)
    engine = Engine(home=home, cfg=Config(home=home, model="m", tools=ToolsConfig(call_timeout_s=600.0), raw={}))
    engine.run_turn("hi", emit=lambda e: None)
    assert seen["cap"] == 600.0
    assert 100.0 < seen["deadline"] <= 120.0


def test_past_the_turn_deadline_the_plain_cap_applies_and_workgroup_post_is_exempt(registry, tmp_path: Path) -> None:
    ex = _executor(tmp_path, call_timeout_s=600.0)
    ex.turn_deadline = time.monotonic() - 5.0
    assert ex.call_deadline("zz_slow") == 600.0
    assert ex.call_deadline("workgroup_post") is None
