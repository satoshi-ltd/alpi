from __future__ import annotations

import threading
from pathlib import Path

import pytest

from alpi import config as cfg_mod
from alpi import ledger, llm
from alpi.home import get_home
from alpi.llm import Completion
from alpi.tools import research as research_mod
from alpi.tools.base import ToolResult
from alpi.tools.research import Research


def _config(home: Path, *, max_usd: object = None, daily: float | None = None) -> None:
    lines = []
    if max_usd is not None:
        lines += ["tools:", "  research:", f"    max_usd: {max_usd}"]
    if daily is not None:
        lines += ["budget:", f"  daily_usd: {daily}"]
    (home / "config.yaml").write_text("\n".join(lines) + "\n")


def _search_call(cost: float, content: str = "") -> Completion:
    return Completion(
        content=content, input_tokens=1, output_tokens=1, cost_usd=cost, raw=None,
        tool_calls=[{"id": "c", "name": "web_search", "arguments": '{"query": "topic"}'}],
    )


def _report(cost: float, text: str = "final report") -> Completion:
    return Completion(content=text, input_tokens=1, output_tokens=1, cost_usd=cost, raw=None, tool_calls=[])


@pytest.fixture
def provider(tmp_home_no_env: Path, monkeypatch: pytest.MonkeyPatch):
    state = {"calls": 0, "tools_on": [], "lock": threading.Lock(), "step_cost": 0.04, "synthesis_cost": 0.01, "ledger": False}

    def complete(*, messages, tools=None, **_kw):
        with state["lock"]:
            state["calls"] += 1
            state["tools_on"].append(bool(tools))
        if not tools:
            cost = state["synthesis_cost"]
            if state["ledger"]:
                ledger.record(get_home(), usd=cost, tokens=2)
            return _report(cost)
        cost = state["step_cost"]
        if state["ledger"]:
            ledger.record(get_home(), usd=cost, tokens=2)
        return _search_call(cost, content="partial note")

    monkeypatch.setattr(llm, "complete", complete)
    import alpi.tools as tools_pkg
    monkeypatch.setattr(tools_pkg, "execute", lambda *_a, **_k: ToolResult(ok=True, output="hit"), raising=False)
    return state


def test_the_cap_defaults_to_one_dollar_and_zero_removes_it(tmp_home_no_env: Path) -> None:
    assert research_mod.max_usd(cfg_mod.load(get_home())) == 1.0
    for value in ("0.25", "3"):
        _config(tmp_home_no_env, max_usd=value)
        assert research_mod.max_usd(cfg_mod.load(get_home())) == float(value)
    _config(tmp_home_no_env, max_usd=0)
    assert research_mod.max_usd(cfg_mod.load(get_home())) is None
    for bad in ("fast", "-1", "true", ".nan", ".inf"):
        _config(tmp_home_no_env, max_usd=bad)
        assert research_mod.max_usd(cfg_mod.load(get_home())) == 1.0


def test_a_single_call_stops_investigating_at_its_reserve_and_still_writes_the_report(
    tmp_home_no_env: Path, provider,
) -> None:
    _config(tmp_home_no_env, max_usd=0.10)
    result = Research().run(brief="topic", depth="deep")
    assert result.ok
    assert provider["calls"] == 3 and provider["tools_on"] == [True, True, False]
    assert result.output.startswith("final report")
    assert "stopped early by the per-call cost cap ($0.10)" in result.output


def test_a_single_call_with_no_room_for_the_report_returns_partial_findings(
    tmp_home_no_env: Path, provider,
) -> None:
    _config(tmp_home_no_env, max_usd=0.10)
    provider["step_cost"] = 0.06
    result = Research().run(brief="topic", depth="deep")
    assert result.ok
    assert provider["calls"] == 2 and provider["tools_on"] == [True, True]
    assert "stopped by the per-call cost cap ($0.10) before a final report" in result.output
    assert "partial note" in result.output and "web_search: topic" in result.output


def test_parallel_tasks_share_one_cap_and_overshoot_by_at_most_one_call_each(
    tmp_home_no_env: Path, provider,
) -> None:
    _config(tmp_home_no_env, max_usd=0.20)
    provider["step_cost"] = 0.05
    provider["synthesis_cost"] = 0.05
    result = Research().run(tasks=[{"brief": f"t{i}", "depth": "deep"} for i in range(3)])
    assert result.ok
    spent = provider["calls"] * 0.05
    assert spent <= 0.20 + 3 * 0.05 + 1e-9
    assert provider["calls"] < 3 * 30
    assert result.output.count("## Task") == 3
    assert "stopped" in result.output


def test_a_call_with_no_cap_runs_to_its_step_ceiling(tmp_home_no_env: Path, provider) -> None:
    _config(tmp_home_no_env, max_usd=0)
    provider["step_cost"] = 5.0
    result = Research().run(brief="topic", depth="fast")
    assert result.ok
    assert provider["calls"] == research_mod.DEPTH_STEPS_DEFAULTS["fast"] + 1
    assert "stopped" not in result.output


def test_research_leaves_daily_headroom_for_the_parent_answer(tmp_home_no_env: Path, provider) -> None:
    _config(tmp_home_no_env, max_usd=50, daily=1.0)
    provider["ledger"] = True
    provider["step_cost"] = 0.12
    ledger.record(get_home(), usd=0.80, tokens=1)
    result = Research().run(brief="topic", depth="deep")
    assert result.ok
    assert "daily budget headroom reserved for the main answer" in result.output
    assert provider["calls"] == 1
    ledger.check(get_home(), cfg_mod.load(get_home()).budget)


def test_research_does_not_start_when_the_headroom_is_already_reserved(tmp_home_no_env: Path, provider) -> None:
    _config(tmp_home_no_env, max_usd=50, daily=1.0)
    ledger.record(get_home(), usd=0.95, tokens=1)
    result = Research().run(brief="topic", depth="fast")
    assert not result.ok and "no room under the daily budget headroom" in result.error
    assert provider["calls"] == 0


def test_a_cap_crossed_by_the_last_step_returns_partial_findings_without_a_report_call(
    tmp_home_no_env: Path, provider, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _config(tmp_home_no_env, max_usd=0.10)
    steps = research_mod.DEPTH_STEPS_DEFAULTS["fast"]
    costs = iter([0.001] * (steps - 1) + [5.0])
    provider["calls"] = 0

    def complete(*, messages, tools=None, **_kw):
        provider["calls"] += 1
        provider["tools_on"].append(bool(tools))
        return _search_call(next(costs), content="partial note")

    monkeypatch.setattr(llm, "complete", complete)
    result = Research().run(brief="topic", depth="fast")
    assert result.ok and provider["calls"] == steps
    assert all(provider["tools_on"][-steps:])
    assert "before a final report" in result.output and "partial note" in result.output


def test_the_cap_counts_what_a_sub_tool_spends_on_its_own_model_calls(
    tmp_home_no_env: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from alpi.tools import _state as tool_state_mod
    import alpi.tools as tools_pkg

    _config(tmp_home_no_env, max_usd=0.10)
    calls = {"research": 0}

    def complete(*, messages, tools=None, **_kw):
        calls["research"] += 1
        return _search_call(0.001, content="note") if tools else _report(0.001)

    def execute(name, args, **_kw):
        tool_state_mod.record_usage(1, 1, 0.04)
        return ToolResult(ok=True, output="extracted")

    monkeypatch.setattr(llm, "complete", complete)
    monkeypatch.setattr(tools_pkg, "execute", execute, raising=False)
    forwarded: list[float] = []
    tool_state_mod.set_usage_sink(lambda i, o, c, *a, **k: forwarded.append(c))
    try:
        result = Research().run(brief="topic", depth="deep")
    finally:
        tool_state_mod.set_usage_sink(None)
    assert result.ok
    assert calls["research"] < research_mod.DEPTH_STEPS_DEFAULTS["deep"]
    assert sum(forwarded) >= 0.075
    assert "stopped" in result.output


def test_tools_of_a_batch_do_not_start_once_the_completion_that_asked_for_them_spent_the_cap(
    tmp_home_no_env: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import alpi.tools as tools_pkg

    _config(tmp_home_no_env, max_usd=0.10)
    executed: list[str] = []
    asked = Completion(
        content="", input_tokens=1, output_tokens=1, cost_usd=0.11, raw=None,
        tool_calls=[{"id": f"c{i}", "name": "web_extract", "arguments": '{"url": "https://x.test/%d"}' % i} for i in range(3)],
    )
    monkeypatch.setattr(llm, "complete", lambda **_kw: asked)
    monkeypatch.setattr(
        tools_pkg, "execute", lambda name, *_a, **_k: executed.append(name) or ToolResult(ok=True, output="x"), raising=False,
    )
    result = Research().run(brief="topic", depth="deep")
    assert executed == []
    assert result.ok and "stopped by the per-call cost cap ($0.10)" in result.output


def test_a_tool_that_spends_past_the_reserve_stops_the_rest_of_its_batch(
    tmp_home_no_env: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import alpi.tools as tools_pkg
    from alpi.tools import _state as tool_state_mod

    _config(tmp_home_no_env, max_usd=0.10)
    executed: list[str] = []
    asked = Completion(
        content="", input_tokens=1, output_tokens=1, cost_usd=0.001, raw=None,
        tool_calls=[{"id": f"c{i}", "name": "web_extract", "arguments": '{"url": "https://x.test/%d"}' % i} for i in range(3)],
    )

    def complete(*, messages, tools=None, **_kw):
        return asked if tools else _report(0.001)

    def execute(name, args, **_kw):
        executed.append(args["url"])
        tool_state_mod.record_usage(1, 1, 0.08)
        return ToolResult(ok=True, output="extracted")

    monkeypatch.setattr(llm, "complete", complete)
    monkeypatch.setattr(tools_pkg, "execute", execute, raising=False)
    result = Research().run(brief="topic", depth="deep")
    assert executed == ["https://x.test/0"]
    assert result.ok and "stopped early by the per-call cost cap" in result.output


def test_partial_findings_keep_bounded_excerpts_of_what_the_tools_returned(
    tmp_home_no_env: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import alpi.tools as tools_pkg
    from alpi.tools import _state as tool_state_mod

    _config(tmp_home_no_env, max_usd=0.10)
    asked = Completion(
        content="", input_tokens=1, output_tokens=1, cost_usd=0.05, raw=None,
        tool_calls=[{"id": "c", "name": "web_fetch", "arguments": '{"url": "https://docs.test/page"}'}],
    )

    def execute(*_a, **_k):
        tool_state_mod.record_usage(1, 1, 0.06)
        return ToolResult(ok=True, output="FINDING " + "word " * 400)

    monkeypatch.setattr(llm, "complete", lambda **_kw: asked)
    monkeypatch.setattr(tools_pkg, "execute", execute, raising=False)
    result = Research().run(brief="topic", depth="deep")
    assert result.ok and "before a final report" in result.output
    assert "web_fetch: https://docs.test/page" in result.output and "FINDING word" in result.output
    assert len(result.output) < 2000
