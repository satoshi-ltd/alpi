"""OPS.2 turn / process run ledger — JSONL store under <home>/logs/runs.jsonl."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from alpi import run_ledger


@pytest.fixture
def home(tmp_path: Path) -> Path:
    h = tmp_path / "h"
    h.mkdir()
    return h


def _ledger_writer(home_str: str, start: int, count: int) -> None:
    for i in range(count):
        run_ledger.record(
            Path(home_str), kind="agent", outcome="ok", elapsed_s=0.01,
            at=float(start * 1000 + i), session_id=f"{start}:{i}",
        )


def test_record_persists_and_reads_back(home: Path) -> None:
    run_ledger.record(
        home, kind="agent", outcome="ok", elapsed_s=1.234,
        profile="default", session_id="s1", last_tool="terminal", tool_count=3,
        output_tail="all good",
    )
    rows = run_ledger.read(home)
    assert len(rows) == 1
    r = rows[0]
    assert r["kind"] == "agent"
    assert r["outcome"] == "ok"
    assert r["elapsed_s"] == 1.234
    assert r["session_id"] == "s1"
    assert r["last_tool"] == "terminal"
    assert r["tool_count"] == 3
    assert r["output_tail"] == "all good"
    assert run_ledger.store_path(home).exists()


def test_read_is_most_recent_first(home: Path) -> None:
    run_ledger.record(home, kind="agent", outcome="ok", elapsed_s=1.0, at=100.0)
    run_ledger.record(home, kind="schedule", outcome="error", elapsed_s=2.0, at=200.0)
    rows = run_ledger.read(home)
    assert [r["at"] for r in rows] == [200.0, 100.0]


def test_read_filters_by_kind(home: Path) -> None:
    run_ledger.record(home, kind="agent", outcome="ok", elapsed_s=1.0)
    run_ledger.record(home, kind="terminal", outcome="timeout", elapsed_s=2.0)
    run_ledger.record(home, kind="terminal", outcome="ok", elapsed_s=3.0)
    assert len(run_ledger.read(home, kind="terminal")) == 2
    assert len(run_ledger.read(home, kind="agent")) == 1


def test_invalid_kind_and_outcome_are_clamped(home: Path) -> None:
    run_ledger.record(home, kind="bogus", outcome="weird", elapsed_s=1.0)
    r = run_ledger.read(home)[0]
    assert r["kind"] == "agent"
    assert r["outcome"] == "error"


def test_output_tail_is_capped_and_flattened(home: Path) -> None:
    long = "x\n" * 500
    run_ledger.record(home, kind="agent", outcome="ok", elapsed_s=1.0, output_tail=long)
    tail = run_ledger.read(home)[0]["output_tail"]
    assert tail is not None
    assert len(tail) <= run_ledger.TAIL_CAP
    assert "\n" not in tail


def test_cap_holds_at_max_runs(home: Path) -> None:
    for i in range(run_ledger.MAX_RUNS + 25):
        run_ledger.record(home, kind="agent", outcome="ok", elapsed_s=0.1, at=float(i))
    lines = run_ledger.store_path(home).read_text().splitlines()
    assert len(lines) == run_ledger.MAX_RUNS
    # Oldest dropped, newest kept.
    ats = [json.loads(line)["at"] for line in lines]
    assert ats[0] == 25.0
    assert ats[-1] == float(run_ledger.MAX_RUNS + 24)


def test_limit_caps_read_count(home: Path) -> None:
    for i in range(10):
        run_ledger.record(home, kind="agent", outcome="ok", elapsed_s=0.1, at=float(i))
    assert len(run_ledger.read(home, limit=3)) == 3


def test_summarize_empty(home: Path) -> None:
    s = run_ledger.summarize(home)
    assert s["total"] == 0
    assert s["recent"] == [] and s["problematic"] == [] and s["slow"] == []
    assert s["counts"] == {"by_kind": {}, "by_outcome": {}}


def test_summarize_counts_failures_and_slow(home: Path) -> None:
    run_ledger.record(home, kind="agent", outcome="ok", elapsed_s=1.0, at=1.0)
    run_ledger.record(home, kind="agent", outcome="error", elapsed_s=2.0, at=2.0)
    run_ledger.record(home, kind="terminal", outcome="ok", elapsed_s=40.0, at=3.0)
    run_ledger.record(home, kind="schedule", outcome="timeout", elapsed_s=600.0, at=4.0)
    s = run_ledger.summarize(home)
    assert s["total"] == 4
    assert s["counts"]["by_kind"] == {"agent": 2, "terminal": 1, "schedule": 1}
    assert s["counts"]["by_outcome"] == {"ok": 2, "error": 1, "timeout": 1}
    assert [r["outcome"] for r in s["problematic"]] == ["timeout", "error"]
    assert sorted(r["kind"] for r in s["slow"]) == ["schedule", "terminal"]


def test_summarize_respects_limit(home: Path) -> None:
    for i in range(10):
        run_ledger.record(home, kind="agent", outcome="error", elapsed_s=1.0, at=float(i))
    s = run_ledger.summarize(home, limit=3)
    assert len(s["recent"]) == 3
    assert len(s["problematic"]) == 3
    assert s["total"] == 10


def test_record_never_raises_on_bad_home(tmp_path: Path) -> None:
    # A file where a dir is expected makes the write fail; record must swallow it.
    bad = tmp_path / "afile"
    bad.write_text("x")
    run_ledger.record(bad, kind="agent", outcome="ok", elapsed_s=1.0)


def test_terminal_fg_command_records_run(home: Path, monkeypatch) -> None:
    monkeypatch.setenv("ALPI_HOME", str(home))
    from alpi.tools.terminal import Terminal

    res = Terminal().run(action="run", command="printf hello")
    assert res.ok
    rows = run_ledger.read(home, kind="terminal")
    assert len(rows) == 1
    assert rows[0]["outcome"] == "ok"
    assert rows[0]["exit_code"] == 0
    # Never the command (can carry secrets); the redacted output tail instead.
    tail = rows[0]["output_tail"] or ""
    assert "hello" in tail
    assert "printf" not in tail


def test_terminal_fg_nonzero_records_error(home: Path, monkeypatch) -> None:
    monkeypatch.setenv("ALPI_HOME", str(home))
    from alpi.tools.terminal import Terminal

    res = Terminal().run(action="run", command="exit 3")
    assert not res.ok
    row = run_ledger.read(home, kind="terminal")[0]
    assert row["outcome"] == "error"
    assert row["exit_code"] == 3


def _fake_engine(home: Path, interrupted: bool = False):
    class _Session:
        id = "sess-9"

    class _Engine:
        pass

    e = _Engine()
    e.home = home
    e.session = _Session()
    e.interrupt_requested = False
    e._interrupted_this_turn = interrupted
    return e


class _T:
    def __init__(self, n: str) -> None:
        self.name = n


def test_engine_record_run_agent_vs_workgroup(home: Path, monkeypatch) -> None:
    from alpi.engine import Engine

    fake = _fake_engine(home)
    monkeypatch.delenv("ALPI_WORKGROUP_DISPATCH", raising=False)
    Engine._record_run(
        fake, elapsed=1.0, turn_completed=True,
        turn_tools=[_T("memory"), _T("terminal")], assistant="done",
    )
    monkeypatch.setenv("ALPI_WORKGROUP_DISPATCH", "wg-42")
    Engine._record_run(
        fake, elapsed=2.0, turn_completed=False, turn_tools=[], assistant="",
    )

    assert {r["kind"] for r in run_ledger.read(home)} == {"agent", "workgroup"}
    wg = run_ledger.read(home, kind="workgroup")[0]
    assert wg["workgroup_id"] == "wg-42"
    assert wg["outcome"] == "error"
    ag = run_ledger.read(home, kind="agent")[0]
    assert ag["outcome"] == "ok"
    assert ag["last_tool"] == "terminal"
    assert ag["tool_count"] == 2


def test_engine_record_run_scheduled_child_tags_backend(home: Path, monkeypatch) -> None:
    from alpi.engine import Engine

    monkeypatch.delenv("ALPI_WORKGROUP_DISPATCH", raising=False)
    monkeypatch.setenv("ALPI_SCHEDULE_CHILD", "1")
    Engine._record_run(
        _fake_engine(home), elapsed=1.0, turn_completed=True,
        turn_tools=[_T("search")], assistant="done",
    )
    row = run_ledger.read(home, kind="agent")[0]
    assert row["backend"] == "scheduled-child"


def test_record_swallows_malformed_field(home: Path) -> None:
    # A non-numeric elapsed_s must not escape record() (coercion is inside the try).
    run_ledger.record(home, kind="agent", outcome="ok", elapsed_s="oops")
    assert run_ledger.read(home) == []


def test_engine_record_run_interrupted_outcome(home: Path, monkeypatch) -> None:
    from alpi.engine import Engine

    monkeypatch.delenv("ALPI_WORKGROUP_DISPATCH", raising=False)
    Engine._record_run(
        _fake_engine(home, interrupted=True), elapsed=0.1,
        turn_completed=False, turn_tools=[], assistant="",
    )
    assert run_ledger.read(home)[0]["outcome"] == "interrupted"


def test_output_tail_redacts_secrets(home: Path) -> None:
    run_ledger.record(
        home, kind="terminal", outcome="ok", elapsed_s=1.0,
        output_tail="Authorization: Bearer abc123secrettoken and TOKEN=supersecretvalue done",
    )
    tail = run_ledger.read(home)[0]["output_tail"]
    assert "abc123secrettoken" not in tail
    assert "supersecretvalue" not in tail
    assert "***" in tail


def test_workgroup_id_persists(home: Path) -> None:
    run_ledger.record(
        home, kind="workgroup", outcome="ok", elapsed_s=2.0, workgroup_id="wg-research",
    )
    row = run_ledger.read(home, kind="workgroup")[0]
    assert row["workgroup_id"] == "wg-research"


def test_concurrent_writers_dont_lose_records(home: Path) -> None:
    import multiprocessing as mp

    n_procs, per_proc = 4, 60  # 240 < MAX_RUNS, so nothing is trimmed
    ctx = mp.get_context("fork")
    procs = [
        ctx.Process(target=_ledger_writer, args=(str(home), s, per_proc))
        for s in range(n_procs)
    ]
    for p in procs:
        p.start()
    for p in procs:
        p.join()
    rows = run_ledger.read(home, limit=10_000)
    assert len(rows) == n_procs * per_proc
    assert len({r["session_id"] for r in rows}) == n_procs * per_proc


def test_schedule_record_helper_maps_outcome(home: Path) -> None:
    from alpi.scheduler.run import JobOutcome, _record_schedule_run

    _record_schedule_run(
        home, {"id": "job-1"},
        JobOutcome(False, "agent timed out", timeout_reason="timeout_600s"),
        started=10.0, elapsed=600.0,
    )
    _record_schedule_run(
        home, {"id": "job-2"},
        JobOutcome(False, "agent rc=1: boom", exit_code=1),
        started=20.0, elapsed=2.0,
    )
    _record_schedule_run(
        home, {"id": "job-3", "no_agent": True}, JobOutcome(True, "silent run ok"),
        started=30.0, elapsed=1.0,
    )
    rows = run_ledger.read(home, kind="schedule")
    by_job = {r["job_id"]: r for r in rows}
    assert by_job["job-1"]["outcome"] == "timeout"
    assert by_job["job-1"]["timeout_reason"] == "timeout_600s"
    assert by_job["job-2"]["outcome"] == "error"
    assert by_job["job-2"]["exit_code"] == 1
    assert by_job["job-3"]["outcome"] == "ok"
    assert by_job["job-3"]["backend"] == "script"
