"""Batch / parallel mode for research + delegate (R.3).

We don't spin up real LLM calls — we patch `_run_single` on each tool
and verify the dispatch logic: validation, parallel execution, result
aggregation, and per-task emit prefixes.
"""

from __future__ import annotations

import time
from pathlib import Path

from alpi.tools import _state as S
from alpi.tools.base import ToolResult
from alpi.tools.delegate import Delegate
from alpi.tools.research import MAX_PARALLEL_TASKS, Research
from alpi.host.connection_context import ConnectionContext, current, use


def test_research_rejects_missing_brief() -> None:
    r = Research().run()
    assert not r.ok
    assert "brief" in r.error.lower()


def test_research_rejects_too_many_tasks() -> None:
    tasks = [{"brief": f"task {i}"} for i in range(MAX_PARALLEL_TASKS + 1)]
    r = Research().run(tasks=tasks)
    assert not r.ok
    assert "max" in r.error.lower()


def test_research_rejects_task_without_brief() -> None:
    r = Research().run(tasks=[{"brief": "ok"}, {"depth": "quick"}])
    assert not r.ok
    assert "task 1" in r.error


def test_research_batch_runs_in_parallel(monkeypatch) -> None:
    """Three sleeping tasks should finish in parallel."""
    started: list[float] = []

    def fake_single(self, brief, depth="normal"):
        started.append(time.time())
        time.sleep(0.2)
        return ToolResult(ok=True, output=f"done: {brief}")

    monkeypatch.setattr(Research, "_run_single", fake_single)

    t0 = time.time()
    r = Research().run(tasks=[
        {"brief": "a"}, {"brief": "b"}, {"brief": "c"},
    ])
    elapsed = time.time() - t0
    assert r.ok
    assert elapsed < 0.5, f"batch took {elapsed:.2f}s — not parallel"
    assert "Task 1: a" in r.output
    assert "Task 2: b" in r.output
    assert "Task 3: c" in r.output
    assert "done: a" in r.output


def test_research_batch_aggregates_failures(monkeypatch) -> None:
    def fake_single(self, brief, depth="normal"):
        if brief == "bad":
            return ToolResult(ok=False, output="", error="boom")
        return ToolResult(ok=True, output=f"ok-{brief}")

    monkeypatch.setattr(Research, "_run_single", fake_single)

    r = Research().run(tasks=[{"brief": "good"}, {"brief": "bad"}])
    assert r.ok  # batch result is OK even if sub-tasks fail
    assert "ok-good" in r.output
    assert "[failed: boom]" in r.output


def test_research_batch_inherits_parent_interrupt(monkeypatch) -> None:
    """Workers should re-see the parent interrupt getter."""
    S.set_interrupt_getter(lambda: True)

    seen: list[bool] = []

    def fake_single(self, brief, depth="normal"):
        seen.append(S.is_interrupted())
        return ToolResult(ok=True, output="ok")

    try:
        monkeypatch.setattr(Research, "_run_single", fake_single)
        Research().run(tasks=[{"brief": "x"}, {"brief": "y"}])
    finally:
        S.set_interrupt_getter(None)

    assert seen == [True, True]


def test_delegate_rejects_missing_goal() -> None:
    r = Delegate().run()
    assert not r.ok
    assert "goal" in r.error.lower()


def test_delegate_batch_runs_and_aggregates(monkeypatch) -> None:
    def fake_single(self, goal, context="", toolsets=None, tier="main", max_steps=0):
        return ToolResult(ok=True, output=f"did: {goal}")

    monkeypatch.setattr(Delegate, "_run_single", fake_single)

    r = Delegate().run(tasks=[
        {"goal": "build"}, {"goal": "test"},
    ])
    assert r.ok
    assert "did: build" in r.output
    assert "did: test" in r.output
    assert "Task 1: build" in r.output


def test_delegate_batch_uses_per_task_emit(monkeypatch) -> None:
    """The worker's emit should prefix with [i/N]."""
    emits: list[str] = []
    S.set_emit(lambda label, err: emits.append(label))

    def fake_single(self, goal, context="", toolsets=None, tier="main", max_steps=0):
        S.emit_state("inside")
        return ToolResult(ok=True, output="ok")

    try:
        monkeypatch.setattr(Delegate, "_run_single", fake_single)
        Delegate().run(tasks=[{"goal": "a"}, {"goal": "b"}])
    finally:
        S.set_emit(None)

    # Both workers should have emitted a prefixed label that the parent emit
    # received verbatim.
    prefixes = {e.split(" ")[0] for e in emits}
    assert prefixes == {"[1/2]", "[2/2]"}


def test_parallel_subagents_keep_connection_context(monkeypatch) -> None:
    seen = []

    def fake_research(self, brief, depth="normal"):
        seen.append(("research", current().connection_id, current().device_id))
        return ToolResult(ok=True, output=brief)

    def fake_delegate(self, goal, context="", toolsets=None, tier="main", max_steps=0):
        seen.append(("delegate", current().connection_id, current().device_id))
        return ToolResult(ok=True, output=goal)

    monkeypatch.setattr(Research, "_run_single", fake_research)
    monkeypatch.setattr(Delegate, "_run_single", fake_delegate)
    with use(ConnectionContext("conn_javi", "dev_phone", "remote")):
        Research().run(tasks=[{"brief": "a"}, {"brief": "b"}])
        Delegate().run(tasks=[{"goal": "a"}, {"goal": "b"}])

    assert seen == [
        ("research", "conn_javi", "dev_phone"),
        ("research", "conn_javi", "dev_phone"),
        ("delegate", "conn_javi", "dev_phone"),
        ("delegate", "conn_javi", "dev_phone"),
    ]


def test_parallel_subagents_keep_execution_spine_context(
    tmp_path: Path, monkeypatch,
) -> None:
    from alpi.core.run_context import RunContext, current as current_run, use as use_run
    from alpi.core.tool_executor import ToolExecutor, current as current_executor, use as use_executor

    context = RunContext("run", tmp_path, tmp_path, "default", "user", "s", "host")
    executor = ToolExecutor(context)
    seen = []

    def fake_research(self, brief, depth="normal"):
        seen.append((current_run(), current_executor()))
        return ToolResult(ok=True, output=brief)

    monkeypatch.setattr(Research, "_run_single", fake_research)
    with use_run(context), use_executor(executor):
        Research().run(tasks=[{"brief": "a"}, {"brief": "b"}])

    assert seen == [(context, executor), (context, executor)]


def test_delegate_clamp_steps_defaults_and_caps() -> None:
    from alpi.tools.delegate import MAX_STEPS, MAX_STEPS_CAP, _clamp_steps

    assert _clamp_steps(0) == MAX_STEPS
    assert _clamp_steps(-5) == MAX_STEPS
    assert _clamp_steps("junk") == MAX_STEPS
    assert _clamp_steps(60) == 60
    assert _clamp_steps(10_000) == MAX_STEPS_CAP


def test_delegate_batch_threads_max_steps_to_workers(monkeypatch) -> None:
    seen: list[int] = []

    def fake_single(self, goal, context="", toolsets=None, tier="main", max_steps=0):
        seen.append(max_steps)
        return ToolResult(ok=True, output="ok")

    monkeypatch.setattr(Delegate, "_run_single", fake_single)
    Delegate().run(tasks=[{"goal": "a"}, {"goal": "b"}], max_steps=60)
    assert seen == [60, 60]
