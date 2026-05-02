"""Batch / parallel mode for research + delegate (R.3).

We don't spin up real LLM calls — we patch `_run_single` on each tool
and verify the dispatch logic: validation, parallel execution, result
aggregation, and per-task emit prefixes.
"""

from __future__ import annotations

import threading
import time

from alpi.tools import _state as S
from alpi.tools.base import ToolResult
from alpi.tools.delegate import Delegate
from alpi.tools.research import MAX_PARALLEL_TASKS, Research


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
    def fake_single(self, goal, context="", toolsets=None):
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

    def fake_single(self, goal, context="", toolsets=None):
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
