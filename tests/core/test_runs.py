from __future__ import annotations

from pathlib import Path

import json
import os
import signal
import time

import pytest

from alpi import runs
from alpi.core.run_context import RunContext
from alpi.engine import AgentEvent


def _context(home: Path, *, run_id: str | None = None) -> RunContext:
    return RunContext.create(
        home=home,
        workspace=home / "workspace",
        profile="default",
        source="user",
        session_id="s1",
        connection_id="c1",
        device_id="d1",
        run_id=run_id,
    )


def test_run_journal_roundtrip_and_summary(tmp_path: Path) -> None:
    context = _context(tmp_path)
    runs.start(context, model="model-1")
    runs.record_agent_event(context, AgentEvent(kind="assistant_done", text="hello", final=True))
    runs.finish(context, "completed")

    journal = runs.read(tmp_path, context.run_id)
    assert [row["kind"] for row in journal["events"]] == [
        "run.started", "agent.assistant_done", "run.finished",
    ]
    item = runs.summary(tmp_path, context.run_id)
    assert item["status"] == "completed"
    assert item["connection_id"] == "c1"
    assert item["event_count"] == 3
    assert runs.list_runs(tmp_path)[0]["id"] == context.run_id
    assert runs.run_path(tmp_path, context.run_id).stat().st_mode & 0o777 == 0o600


def test_summary_reads_only_the_edges_of_a_journal(tmp_path: Path, monkeypatch) -> None:
    context = _context(tmp_path)
    runs.start(context)
    for index in range(100):
        runs.append(tmp_path, context.run_id, "test", {"index": index})
    runs.finish(context, "completed")
    original_loads = runs.json.loads
    calls = 0

    def counted_loads(value):
        nonlocal calls
        calls += 1
        return original_loads(value)

    monkeypatch.setattr(runs.json, "loads", counted_loads)
    item = runs.summary(tmp_path, context.run_id)

    assert item["event_count"] == 102
    assert item["status"] == "completed"
    assert calls == 2


def test_finish_releases_per_run_process_state(tmp_path: Path) -> None:
    context = _context(tmp_path)
    path_key = str(runs.run_path(tmp_path, context.run_id))
    runs.start(context)
    assert path_key in runs._locks and path_key in runs._seq

    runs.finish(context, "completed")

    assert path_key not in runs._locks and path_key not in runs._seq


def test_supervisor_can_finish_a_child_run_once(tmp_path: Path) -> None:
    context = _context(tmp_path)
    runs.start(context)

    assert runs.finish_if_running(tmp_path, context.run_id, "interrupted") is True
    assert runs.finish_if_running(tmp_path, context.run_id, "failed") is False
    assert runs.summary(tmp_path, context.run_id)["status"] == "interrupted"


def test_usage_summary_sums_every_usage_event(tmp_path: Path) -> None:
    context = _context(tmp_path)
    runs.start(context)
    runs.append(tmp_path, context.run_id, "agent.usage", {
        "tokens_in": 100, "tokens_out": 20, "cost": 0.12,
    })
    runs.append(tmp_path, context.run_id, "agent.usage", {
        "tokens_in": 50, "tokens_out": 5, "cost": 0.03,
    })

    assert runs.usage_summary(tmp_path, context.run_id) == {
        "usd": pytest.approx(0.15),
        "tokens": 175,
        "tokens_in": 150,
        "tokens_out": 25,
    }


def test_reconcile_stale_closes_legacy_run_but_not_live_pid(
    tmp_path: Path, monkeypatch,
) -> None:
    monkeypatch.setattr(runs.time, "time", lambda: 100.0)
    legacy_id = "legacy"
    runs.append(tmp_path, legacy_id, "run.started", {
        "run_id": legacy_id, "profile": "default",
    })
    live = _context(tmp_path)
    runs.start(live)
    monkeypatch.setattr(runs.time, "time", lambda: 5000.0)

    closed = runs.reconcile_stale(tmp_path, older_than_s=3600)
    assert [row["run_id"] for row in closed] == [legacy_id]
    assert runs.summary(tmp_path, legacy_id)["status"] == "interrupted"
    assert runs.summary(tmp_path, live.run_id)["status"] == "running"


def test_reconcile_stale_scans_beyond_the_public_list_limit(
    tmp_path: Path, monkeypatch,
) -> None:
    monkeypatch.setattr(runs.time, "time", lambda: 100.0)
    runs.append(tmp_path, "buried", "run.started", {
        "run_id": "buried", "profile": "default",
    })
    for index in range(runs.MAX_LIST_LIMIT + 1):
        context = _context(tmp_path, run_id=f"newer-{index}")
        runs.start(context)
        runs.finish(context, "completed")
    monkeypatch.setattr(runs.time, "time", lambda: 5000.0)

    assert [row["run_id"] for row in runs.reconcile_stale(tmp_path, older_than_s=3600)] == ["buried"]
    assert runs.summary(tmp_path, "buried")["status"] == "interrupted"


def test_reconcile_stale_reports_the_job_behind_each_closed_run(
    tmp_path: Path, monkeypatch,
) -> None:
    monkeypatch.setattr(runs.time, "time", lambda: 100.0)
    runs.append(tmp_path, "dead", "run.started", {
        "run_id": "dead", "profile": "default", "job_id": "35cbf2b8", "source": "schedule",
    })
    monkeypatch.setattr(runs.time, "time", lambda: 5000.0)

    closed = runs.reconcile_stale(tmp_path, older_than_s=3600)

    assert len(closed) == 1
    assert closed[0]["run_id"] == "dead"
    assert closed[0]["job_id"] == "35cbf2b8"
    assert closed[0]["source"] == "schedule"
    assert closed[0]["silent_for_s"] > 3600


def test_reconcile_stale_reports_nothing_when_no_journal_is_orphaned(tmp_path: Path) -> None:
    context = _context(tmp_path)
    runs.start(context)
    runs.finish(context, "completed")

    assert runs.reconcile_stale(tmp_path, older_than_s=3600) == []


def test_reconcile_stale_marks_its_rows_as_dead_and_says_whether_a_pid_was_recorded(
    tmp_path: Path, monkeypatch,
) -> None:
    monkeypatch.setattr(runs.time, "time", lambda: 100.0)
    runs.append(tmp_path, "nopid", "run.started", {"run_id": "nopid", "profile": "default", "job_id": "j1"})
    runs.append(tmp_path, "gone", "run.started", {"run_id": "gone", "profile": "default", "job_id": "j1", "pid": 999998})
    monkeypatch.setattr(runs, "_pid_alive", lambda pid: False)
    monkeypatch.setattr(runs.time, "time", lambda: 5000.0)

    rows = {r["run_id"]: r for r in runs.reconcile_stale(tmp_path, older_than_s=3600)}

    assert rows["nopid"]["reason"] == "dead" and rows["nopid"]["pid_recorded"] is False
    assert rows["gone"]["reason"] == "dead" and rows["gone"]["pid_recorded"] is True
    assert all(r["journal_closed"] for r in rows.values())


def _scheduled_journal(home: Path, run_id: str, *, pid: int = 0, job_id: str = "j1", pid_start: str | None = None) -> None:
    data = {"run_id": run_id, "profile": "default", "job_id": job_id, "source": "schedule", "pid": pid}
    if pid_start is not None:
        data["pid_start"] = pid_start
    runs.append(home, run_id, "run.started", data)


def _quiet(monkeypatch) -> None:
    runs._silence_seen.clear()
    monkeypatch.setattr(runs.time, "time", lambda: 1000.0)


PAST = 1000.0 + 1700 + 300 + 1   # one second past timeout + grace for a 1700 s job


def test_reconcile_silent_needs_to_watch_the_silence_itself_before_acting(tmp_path: Path, monkeypatch) -> None:
    """A wall-clock age alone is not enough: a clock step or a wake from suspend must never kill a healthy child."""
    _quiet(monkeypatch)
    _scheduled_journal(tmp_path, "wedged")
    kw = dict(timeout_for_job=lambda job_id: 1700, now=PAST)

    first = runs.reconcile_silent(tmp_path, now_mono=0.0, **kw)
    too_soon = runs.reconcile_silent(tmp_path, now_mono=299.0, **kw)
    acted = runs.reconcile_silent(tmp_path, now_mono=300.0, **kw)

    assert first == [] and too_soon == []
    assert [r["run_id"] for r in acted] == ["wedged"]
    assert acted[0]["reason"] == "silent" and acted[0]["timeout_s"] == 1700
    assert acted[0]["journal_closed"] is True and acted[0]["pid_killed"] is False
    assert runs.summary(tmp_path, "wedged")["status"] == "interrupted"
    assert "wedged" not in runs._silence_seen


def test_reconcile_silent_restarts_the_watch_when_the_run_writes_again(tmp_path: Path, monkeypatch) -> None:
    _quiet(monkeypatch)
    _scheduled_journal(tmp_path, "woke")
    kw = dict(timeout_for_job=lambda job_id: 1700)

    runs.reconcile_silent(tmp_path, now=PAST, now_mono=0.0, **kw)
    monkeypatch.setattr(runs.time, "time", lambda: PAST)
    runs.append(tmp_path, "woke", "agent.tool_end", {"name": "x"})

    assert runs.reconcile_silent(tmp_path, now=PAST + 1, now_mono=400.0, **kw) == []
    assert runs.summary(tmp_path, "woke")["status"] == "running"


def test_reconcile_silent_leaves_a_run_inside_its_window_alone(tmp_path: Path, monkeypatch) -> None:
    _quiet(monkeypatch)
    _scheduled_journal(tmp_path, "busy")

    out = runs.reconcile_silent(tmp_path, timeout_for_job=lambda job_id: 1700, now=1000.0 + 1700 + 300, now_mono=0.0)

    assert out == [] and "busy" not in runs._silence_seen


def test_reconcile_silent_ignores_runs_without_a_job(tmp_path: Path, monkeypatch) -> None:
    _quiet(monkeypatch)
    runs.append(tmp_path, "manual", "run.started", {"run_id": "manual", "profile": "default", "source": "user"})
    kw = dict(timeout_for_job=lambda job_id: 60, now=99999.0)

    runs.reconcile_silent(tmp_path, now_mono=0.0, **kw)
    assert runs.reconcile_silent(tmp_path, now_mono=1000.0, **kw) == []
    assert runs.summary(tmp_path, "manual")["status"] == "running"


def test_reconcile_silent_ignores_a_job_it_cannot_size(tmp_path: Path, monkeypatch) -> None:
    _quiet(monkeypatch)
    _scheduled_journal(tmp_path, "orphan", job_id="deleted")
    kw = dict(timeout_for_job=lambda job_id: None, now=99999.0)

    runs.reconcile_silent(tmp_path, now_mono=0.0, **kw)
    assert runs.reconcile_silent(tmp_path, now_mono=1000.0, **kw) == []


def test_reconcile_silent_leaves_a_dead_pid_to_the_stale_rule(tmp_path: Path, monkeypatch) -> None:
    _quiet(monkeypatch)
    _scheduled_journal(tmp_path, "dead", pid=999998)
    monkeypatch.setattr(runs, "_pid_alive", lambda pid: False)
    kw = dict(timeout_for_job=lambda job_id: 60, now=99999.0)

    runs.reconcile_silent(tmp_path, now_mono=0.0, **kw)
    assert runs.reconcile_silent(tmp_path, now_mono=1000.0, **kw) == []
    assert runs.summary(tmp_path, "dead")["status"] == "running"


def _sleeping_child():
    import subprocess
    import sys
    return subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])


def test_reconcile_silent_kills_a_live_child_whose_start_time_matches(tmp_path: Path, monkeypatch) -> None:
    proc = _sleeping_child()
    try:
        _quiet(monkeypatch)
        _scheduled_journal(tmp_path, "ours", pid=proc.pid, pid_start="4242")
        monkeypatch.setattr(runs, "proc_starttime", lambda pid: "4242" if pid == proc.pid else None)
        kw = dict(timeout_for_job=lambda job_id: 60, now=1000.0 + 60 + 300 + 1)

        runs.reconcile_silent(tmp_path, now_mono=0.0, **kw)
        out = runs.reconcile_silent(tmp_path, now_mono=300.0, **kw)

        assert out[0]["pid_killed"] is True and out[0]["journal_closed"] is True
        assert proc.wait(timeout=5) == -9
        assert runs.summary(tmp_path, "ours")["status"] == "interrupted"
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()


def test_reconcile_silent_reports_but_never_touches_a_live_pid_it_cannot_vouch_for(tmp_path: Path, monkeypatch) -> None:
    """A recycled pid may be anything; without a matching start time the process AND the journal are left alone."""
    proc = _sleeping_child()
    try:
        _quiet(monkeypatch)
        _scheduled_journal(tmp_path, "stranger", pid=proc.pid, pid_start="4242")
        monkeypatch.setattr(runs, "proc_starttime", lambda pid: "9999")
        kw = dict(timeout_for_job=lambda job_id: 60, now=1000.0 + 60 + 300 + 1)

        runs.reconcile_silent(tmp_path, now_mono=0.0, **kw)
        out = runs.reconcile_silent(tmp_path, now_mono=300.0, **kw)

        assert out[0]["journal_closed"] is False and out[0]["pid_killed"] is False
        assert proc.poll() is None
        assert runs.summary(tmp_path, "stranger")["status"] == "running"
        # and it keeps being reported as open, so the caller can decide how often to say it
        assert runs.reconcile_silent(tmp_path, now_mono=600.0, **kw)[0]["journal_closed"] is False
    finally:
        proc.kill()
        proc.wait()


def test_reconcile_silent_leaves_the_journal_open_when_the_kill_is_refused(tmp_path: Path, monkeypatch) -> None:
    """A live process that will not die must not get a run.finished written under it."""
    proc = _sleeping_child()
    try:
        _quiet(monkeypatch)
        _scheduled_journal(tmp_path, "armoured", pid=proc.pid, pid_start="4242")
        monkeypatch.setattr(runs, "proc_starttime", lambda pid: "4242" if pid == proc.pid else None)
        def refuse(pid, sig):
            raise PermissionError(pid)
        monkeypatch.setattr(runs.os, "kill", refuse)
        kw = dict(timeout_for_job=lambda job_id: 60, now=1000.0 + 60 + 300 + 1)

        runs.reconcile_silent(tmp_path, now_mono=0.0, **kw)
        out = runs.reconcile_silent(tmp_path, now_mono=300.0, **kw)

        assert out[0]["journal_closed"] is False and out[0]["pid_killed"] is False
        assert out[0]["kill_refused"] is True
        assert runs.summary(tmp_path, "armoured")["status"] == "running"
        assert proc.poll() is None
    finally:
        monkeypatch.undo()
        proc.kill()
        proc.wait()


def test_reconcile_silent_closes_when_the_process_vanished_between_check_and_kill(tmp_path: Path, monkeypatch) -> None:
    _quiet(monkeypatch)
    _scheduled_journal(tmp_path, "vanished", pid=424242, pid_start="x")
    monkeypatch.setattr(runs, "_pid_alive", lambda pid: True)
    monkeypatch.setattr(runs, "proc_starttime", lambda pid: "x")
    def gone(pid, sig):
        raise ProcessLookupError(pid)
    monkeypatch.setattr(runs.os, "kill", gone)
    kw = dict(timeout_for_job=lambda job_id: 60, now=99999.0)

    runs.reconcile_silent(tmp_path, now_mono=0.0, **kw)
    out = runs.reconcile_silent(tmp_path, now_mono=300.0, **kw)

    assert out[0]["journal_closed"] is True and out[0]["pid_killed"] is False
    assert runs.summary(tmp_path, "vanished")["status"] == "interrupted"


def test_reconcile_silent_never_kills_its_own_process_or_its_parent(tmp_path: Path, monkeypatch) -> None:
    _quiet(monkeypatch)
    for run_id, pid in (("self", os.getpid()), ("parent", os.getppid())):
        _scheduled_journal(tmp_path, run_id, pid=pid, pid_start="same")
    monkeypatch.setattr(runs, "proc_starttime", lambda pid: "same")   # every other check would pass
    kw = dict(timeout_for_job=lambda job_id: 60, now=99999.0)

    runs.reconcile_silent(tmp_path, now_mono=0.0, **kw)
    out = {r["run_id"]: r for r in runs.reconcile_silent(tmp_path, now_mono=300.0, **kw)}

    assert all(r["pid_killed"] is False and r["journal_closed"] is False for r in out.values())
    assert set(out) == {"self", "parent"}


def test_reconcile_silent_does_not_kill_when_the_journal_recorded_no_start_time(tmp_path: Path, monkeypatch) -> None:
    """Journals written before 0.14.50 carry no pid_start; they are reported, never acted on."""
    proc = _sleeping_child()
    try:
        _quiet(monkeypatch)
        _scheduled_journal(tmp_path, "legacy", pid=proc.pid)
        monkeypatch.setattr(runs, "proc_starttime", lambda pid: "anything")
        kw = dict(timeout_for_job=lambda job_id: 60, now=99999.0)

        runs.reconcile_silent(tmp_path, now_mono=0.0, **kw)
        out = runs.reconcile_silent(tmp_path, now_mono=300.0, **kw)

        assert out[0]["pid_killed"] is False and proc.poll() is None
    finally:
        proc.kill()
        proc.wait()


@pytest.mark.skipif(not Path("/proc").exists(), reason="the real start-time gate needs /proc")
def test_reconcile_silent_real_proc_gate_kills_only_the_recorded_process(tmp_path: Path, monkeypatch) -> None:
    import subprocess
    ours = _sleeping_child()
    stranger = subprocess.Popen(["sleep", "120"])
    try:
        runs._silence_seen.clear()
        monkeypatch.setattr(runs.time, "time", lambda: 1000.0)
        _scheduled_journal(tmp_path, "ours", pid=ours.pid, pid_start=runs.proc_starttime(ours.pid))
        _scheduled_journal(tmp_path, "stranger", pid=stranger.pid, pid_start="1")
        kw = dict(timeout_for_job=lambda job_id: 60, now=1000.0 + 60 + 300 + 1)

        runs.reconcile_silent(tmp_path, now_mono=0.0, **kw)
        out = {r["run_id"]: r for r in runs.reconcile_silent(tmp_path, now_mono=300.0, **kw)}

        assert out["ours"]["pid_killed"] is True and ours.wait(timeout=5) == -9
        assert out["stranger"]["pid_killed"] is False and stranger.poll() is None
    finally:
        for p in (ours, stranger):
            if p.poll() is None:
                p.kill()
                p.wait()


def test_run_started_records_the_process_start_time(tmp_path: Path) -> None:
    context = _context(tmp_path)
    runs.start(context)
    started = runs.read(tmp_path, context.run_id, after_seq=-1, limit=1)["events"][0]["data"]
    assert "pid_start" in started
    assert started["pid_start"] == runs.proc_starttime(os.getpid())


def test_reconcile_silent_skips_finished_journals(tmp_path: Path) -> None:
    context = _context(tmp_path)
    runs.start(context)
    runs.finish(context, "completed")
    assert runs.reconcile_silent(tmp_path, timeout_for_job=lambda job_id: 1, now=1e12, now_mono=1e9) == []


def test_terminal_arguments_are_omitted_from_agent_events_and_workflows(tmp_path: Path) -> None:
    context = _context(tmp_path)
    secret = "not-shaped-like-a-token"
    runs.start(context)
    runs.record_agent_event(context, AgentEvent(
        kind="tool_start", name="terminal", args={"action": "run", "command": secret},
    ))
    runs.record_agent_event(context, AgentEvent(
        kind="tool_start", name="workflow",
        args={"steps": [{
            "id": "shell", "tool": "terminal",
            "arguments": {"action": "run", "command": secret},
        }]},
    ))

    rows = runs.read(tmp_path, context.run_id)["events"]
    assert secret not in str(rows)
    assert rows[1]["data"]["args"] == {"action": "run"}
    nested = rows[2]["data"]["args"]["steps"][0]["arguments"]
    assert nested == {"action": "run"}


def test_run_journal_redacts_and_bounds_text(tmp_path: Path) -> None:
    context = _context(tmp_path)
    runs.start(context)
    secret = "sk-" + "x" * 32
    runs.append(tmp_path, context.run_id, "test", {"text": secret + "z" * 50_000})

    row = runs.read(tmp_path, context.run_id)["events"][-1]
    assert secret not in str(row)
    assert "[REDACTED]" in str(row)
    assert len(str(row["data"])) < 20_000


def test_read_missing_run(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        runs.read(tmp_path, "missing")


def test_run_id_cannot_escape_journal_directory(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="invalid run id"):
        runs.read(tmp_path, "../../outside")


def test_run_journal_does_not_follow_directory_or_file_symlinks(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    (home / "runs").symlink_to(outside)
    context = _context(home)

    with pytest.raises(OSError, match="must not be a symlink"):
        runs.start(context)
    assert list(outside.iterdir()) == []
    assert runs.list_runs(home) == []
    with pytest.raises(FileNotFoundError):
        runs.read(home, "outside")

    (home / "runs").unlink()
    (home / "runs").mkdir()
    target = outside / "target.jsonl"
    target.write_text("leave me")
    runs.run_path(home, context.run_id).symlink_to(target)
    with pytest.raises(OSError):
        runs.start(context)
    with pytest.raises(FileNotFoundError):
        runs.read(home, context.run_id)
    assert target.read_text() == "leave me"


def test_list_runs_tolerates_journal_deleted_during_scan(tmp_path: Path, monkeypatch) -> None:
    context = _context(tmp_path)
    runs.start(context)
    path = runs.run_path(tmp_path, context.run_id)
    original_stat = Path.stat

    def racing_stat(self, *args, **kwargs):
        if self == path:
            raise FileNotFoundError(self)
        return original_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", racing_stat)

    assert runs.list_runs(tmp_path) == []


def test_model_state_is_journaled_only_on_transitions(tmp_path: Path) -> None:
    context = _context(tmp_path)
    runs.start(context)
    for _ in range(500):
        runs.record_agent_event(context, AgentEvent(kind="model_state"))
    runs.record_agent_event(context, AgentEvent(kind="model_state", text="reasoning"))
    runs.record_agent_event(context, AgentEvent(kind="model_state", text="reasoning"))
    runs.record_agent_event(context, AgentEvent(kind="assistant_done", text="ok", final=True))
    runs.finish(context, "completed")

    kinds = [row["kind"] for row in runs.read(tmp_path, context.run_id)["events"]]
    assert kinds == ["run.started", "agent.model_state", "agent.model_state", "agent.assistant_done", "run.finished"]
    assert context.run_id not in runs._last_model_state


def test_only_model_state_is_deduplicated(tmp_path: Path) -> None:
    context = _context(tmp_path)
    runs.start(context)
    for _ in range(3):
        runs.record_agent_event(context, AgentEvent(kind="tool_start", name="read_file"))
        runs.record_agent_event(context, AgentEvent(kind="tool_end", name="read_file", output="ok"))
        runs.record_agent_event(context, AgentEvent(kind="usage", tokens_in=10, tokens_out=5))
        runs.record_agent_event(context, AgentEvent(kind="model_state"))
    runs.finish(context, "completed")

    kinds = [row["kind"] for row in runs.read(tmp_path, context.run_id)["events"]]
    assert kinds.count("agent.tool_start") == 3
    assert kinds.count("agent.tool_end") == 3
    assert kinds.count("agent.usage") == 3
    assert kinds.count("agent.model_state") == 1


def test_model_state_memory_is_kept_per_run(tmp_path: Path) -> None:
    first = _context(tmp_path)
    second = _context(tmp_path, run_id="run-second")
    runs.start(first)
    runs.start(second)

    runs.record_agent_event(first, AgentEvent(kind="model_state"))
    runs.record_agent_event(second, AgentEvent(kind="model_state"))
    runs.record_agent_event(first, AgentEvent(kind="model_state"))
    runs.finish(first, "completed")
    runs.finish(second, "completed")

    for context in (first, second):
        kinds = [row["kind"] for row in runs.read(tmp_path, context.run_id)["events"]]
        assert kinds.count("agent.model_state") == 1, context.run_id
    assert runs._last_model_state == {}


def test_model_state_retries_after_failed_append(tmp_path: Path, monkeypatch) -> None:
    context = _context(tmp_path)
    runs.start(context)
    real_append = runs.append
    attempts = 0

    def flaky_append(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise OSError("temporary write failure")
        return real_append(*args, **kwargs)

    event = AgentEvent(kind="model_state", text="reasoning")
    with monkeypatch.context() as patch:
        patch.setattr(runs, "append", flaky_append)
        with pytest.raises(OSError, match="temporary write failure"):
            runs.record_agent_event(context, event)
        runs.record_agent_event(context, event)
        runs.record_agent_event(context, event)

    runs.finish(context, "completed")
    assert attempts == 2
    events = runs.read(tmp_path, context.run_id)["events"]
    states = [row for row in events if row["kind"] == "agent.model_state"]
    assert len(states) == 1
    assert states[0]["data"]["text"] == "reasoning"
    assert context.run_id not in runs._last_model_state


def test_streaming_deltas_never_reach_the_journal(tmp_path: Path) -> None:
    assert runs._TRANSIENT_KINDS == {"reasoning_delta", "assistant_delta"}
    context = _context(tmp_path)
    runs.start(context)
    runs.record_agent_event(context, AgentEvent(kind="reasoning_delta", text="thinking"))
    runs.record_agent_event(context, AgentEvent(kind="assistant_delta", text="hel"))
    runs.record_agent_event(context, {"kind": "assistant_delta", "text": "lo"})
    runs.record_agent_event(context, AgentEvent(kind="model_state", text="reasoning"))
    runs.record_agent_event(context, AgentEvent(kind="assistant_done", text="hello", final=True))
    runs.finish(context, "completed")

    kinds = [row["kind"] for row in runs.read(tmp_path, context.run_id)["events"]]
    assert kinds == ["run.started", "agent.model_state", "agent.assistant_done", "run.finished"]
    text = runs.run_path(tmp_path, context.run_id).read_text()
    assert "thinking" not in text and "hel" not in text.replace("hello", "")


# --------------------------------------------------------------------
# PROC.2 — what a run detached must die with it
# --------------------------------------------------------------------


def _detached_child():
    import subprocess
    import sys
    return subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(120)"], start_new_session=True,
    )


def _detached_context(home: Path, run_id: str) -> RunContext:
    return RunContext.create(
        home=home, workspace=home, profile="default", source="schedule",
        session_id="s1", connection_id="host", run_id=run_id,
    )


def _stable_starttimes(monkeypatch) -> None:
    monkeypatch.setattr(runs, "proc_starttime", lambda pid: f"start-{pid}")


def test_a_swept_run_takes_the_group_it_detached_with_it(tmp_path: Path, monkeypatch) -> None:
    run = _sleeping_child()
    child = _detached_child()
    try:
        _stable_starttimes(monkeypatch)
        runs.record_child(_detached_context(tmp_path, "ours"), child.pid)
        _quiet(monkeypatch)
        _scheduled_journal(tmp_path, "ours", pid=run.pid, pid_start=f"start-{run.pid}")
        kw = dict(timeout_for_job=lambda job_id: 60, now=1000.0 + 60 + 300 + 1)

        runs.reconcile_silent(tmp_path, now_mono=0.0, **kw)
        out = runs.reconcile_silent(tmp_path, now_mono=300.0, **kw)

        assert out[0]["pid_killed"] is True
        assert out[0]["child_groups_killed"] == 1
        assert run.wait(timeout=5) == -9
        assert child.wait(timeout=5) == -9, "the detached child survived the sweep"
    finally:
        for proc in (run, child):
            if proc.poll() is None:
                proc.kill()
                proc.wait()


def test_a_dead_runs_orphans_are_swept_too(tmp_path: Path, monkeypatch) -> None:
    child = _detached_child()
    try:
        _stable_starttimes(monkeypatch)
        runs.record_child(_detached_context(tmp_path, "gone"), child.pid)
        monkeypatch.setattr(runs.time, "time", lambda: 100.0)
        _scheduled_journal(tmp_path, "gone", pid=999998)
        monkeypatch.setattr(runs, "_pid_alive", lambda pid: False)
        monkeypatch.setattr(runs.time, "time", lambda: 5000.0)

        rows = runs.reconcile_stale(tmp_path, older_than_s=3600)

        assert rows[0]["child_groups_killed"] == 1
        assert child.wait(timeout=5) == -9
    finally:
        if child.poll() is None:
            child.kill()
            child.wait()


def test_a_group_whose_leader_was_replaced_is_left_alone(tmp_path: Path, monkeypatch) -> None:
    child = _detached_child()
    try:
        monkeypatch.setattr(runs, "proc_starttime", lambda pid: "recorded")
        runs.record_child(_detached_context(tmp_path, "stranger"), child.pid)
        # The pid now belongs to somebody else: no proof, no signal.
        monkeypatch.setattr(runs, "proc_starttime", lambda pid: "someone-else")

        assert runs.kill_child_groups(tmp_path, "stranger") == 0
        assert child.poll() is None
    finally:
        child.kill()
        child.wait()


def test_a_child_that_does_not_lead_its_own_group_is_never_signalled(tmp_path: Path, monkeypatch) -> None:
    _stable_starttimes(monkeypatch)
    runs.record_child(_detached_context(tmp_path, "attached"), 4242)
    # Its pid is somebody else's group id: signalling it would reach a group this run never owned.
    monkeypatch.setattr(runs.os, "getpgid", lambda pid: 1)
    signalled: list[int] = []
    monkeypatch.setattr(runs.os, "killpg", lambda pgid, sig: signalled.append(pgid))

    assert runs.kill_child_groups(tmp_path, "attached") == 0
    assert signalled == []


def test_a_terminal_command_lands_in_the_registry_of_the_run_that_asked_for_it(
    tmp_path: Path, monkeypatch,
) -> None:
    from alpi.core.run_context import use as use_run_context
    from alpi.tools.terminal import Terminal

    _stable_starttimes(monkeypatch)
    with use_run_context(_detached_context(tmp_path, "shellrun")):
        assert Terminal().run(command="true").ok

    assert len(runs._recorded_children(tmp_path, "shellrun")) == 1


def test_a_background_job_lands_in_the_registry_of_the_run_that_started_it(
    tmp_path: Path, monkeypatch,
) -> None:
    from alpi.core.run_context import use as use_run_context
    from alpi.tools.terminal import Terminal

    _stable_starttimes(monkeypatch)
    with use_run_context(_detached_context(tmp_path, "bgrun")):
        result = Terminal().run(action="background", command="sleep 30")
    assert result.ok
    recorded = runs._recorded_children(tmp_path, "bgrun")
    try:
        assert len(recorded) == 1
    finally:
        os.killpg(recorded[0][0], signal.SIGKILL)


def test_a_pipeline_gate_lands_in_the_registry_of_the_run_that_ran_it(
    tmp_path: Path, monkeypatch,
) -> None:
    import sys

    from alpi.alp import pipeline_gates as gates
    from alpi.core.run_context import use as use_run_context

    _stable_starttimes(monkeypatch)
    workspace = tmp_path / "ws"
    (workspace / "proj").mkdir(parents=True)
    step = gates.GateStep(
        "content", "quill", "", "", "", (sys.executable, "-c", "print('ok')"), "proj",
    )
    with use_run_context(_detached_context(tmp_path, "gaterun")):
        passed, _out = gates.run_gate(step, workspace)

    assert passed
    assert len(runs._recorded_children(tmp_path, "gaterun")) == 1


def test_a_command_outside_any_run_is_recorded_nowhere(tmp_path: Path, monkeypatch) -> None:
    from alpi.tools.terminal import Terminal

    _stable_starttimes(monkeypatch)
    recorded: list[int] = []
    monkeypatch.setattr(runs, "record_child", lambda ctx, pid: recorded.append(pid))

    assert Terminal().run(command="true").ok
    assert recorded == []


def test_a_child_with_no_provable_identity_is_never_recorded(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(runs, "proc_starttime", lambda pid: None)
    runs.record_child(_detached_context(tmp_path, "unprovable"), 424242)
    assert not runs.children_path(tmp_path, "unprovable").exists()


def test_a_run_that_ends_well_forgets_what_it_spawned(tmp_path: Path, monkeypatch) -> None:
    _stable_starttimes(monkeypatch)
    context = _detached_context(tmp_path, "tidy")
    runs.start(context)
    runs.record_child(context, 4242)
    assert runs.children_path(tmp_path, "tidy").exists()

    runs.finish(context, "completed")

    assert not runs.children_path(tmp_path, "tidy").exists()


def test_closing_a_child_owned_journal_forgets_what_it_spawned(tmp_path: Path, monkeypatch) -> None:
    _stable_starttimes(monkeypatch)
    context = _detached_context(tmp_path, "abandoned")
    runs.start(context)
    runs.record_child(context, 4242)

    assert runs.finish_if_running(tmp_path, "abandoned", "interrupted") is True
    assert not runs.children_path(tmp_path, "abandoned").exists()


def test_the_registry_survives_a_corrupt_line(tmp_path: Path, monkeypatch) -> None:
    _stable_starttimes(monkeypatch)
    context = _detached_context(tmp_path, "messy")
    runs.record_child(context, 4242)
    with runs.children_path(tmp_path, "messy").open("a", encoding="utf-8") as fh:
        fh.write("not json\n{}\n" + json.dumps({"pgid": 0, "start": "x"}) + "\n")
    runs.record_child(context, 4343)

    assert runs._recorded_children(tmp_path, "messy") == [
        (4242, "start-4242"), (4343, "start-4343"),
    ]


def test_the_registry_is_invisible_to_everything_that_scans_the_runs_directory(
    tmp_path: Path, monkeypatch,
) -> None:
    _stable_starttimes(monkeypatch)
    context = _detached_context(tmp_path, "listed")
    runs.start(context)
    runs.record_child(context, 4242)

    assert [row["id"] for row in runs.list_runs(tmp_path)] == ["listed"]
    assert [row[0]["id"] for row in runs.running_journals(tmp_path, time.time())] == ["listed"]


# --------------------------------------------------------------------
# PROC.2 — survivors of a group that lost its leader
# --------------------------------------------------------------------


def _fake_proc(monkeypatch, table: dict[int, bytes], *, on_kill=None) -> list[int]:
    """Stand in for /proc and pidfd, which this machine has neither of. Returns what got signalled."""
    signalled: list[int] = []
    monkeypatch.setattr(runs, "_all_pids", lambda: sorted(table))
    monkeypatch.setattr(runs, "_environ_of", lambda pid: table.get(pid, b""))
    monkeypatch.setattr(runs, "_open_pidfd", lambda pid: pid)
    monkeypatch.setattr(runs, "_close_pidfd", lambda fd: None)

    def kill(fd: int) -> bool:
        signalled.append(fd)
        if on_kill is not None:
            on_kill(fd)
        return True

    monkeypatch.setattr(runs, "_kill_pidfd", kill)
    return signalled


def test_a_survivor_of_a_leaderless_group_is_killed_by_its_stamp(tmp_path: Path, monkeypatch) -> None:
    import subprocess
    # The exact shape: a shell that backgrounds work and exits, leaving its group leaderless.
    # The background job must not inherit the pipe, or reading it waits for the survivor.
    leader = subprocess.Popen(["/bin/sh", "-c", "sleep 300 >/dev/null 2>&1 & echo $!"],
                              stdout=subprocess.PIPE, text=True, start_new_session=True)
    survivor = int(leader.stdout.readline().strip())
    leader.wait(timeout=10)
    try:
        _stable_starttimes(monkeypatch)
        runs.record_child(_detached_context(tmp_path, "orphaned"), leader.pid)
        _fake_proc(
            monkeypatch,
            {survivor: b"PATH=/bin\0ALPI_SPAWNED_BY=77-start-77\0"},
            on_kill=lambda fd: os.kill(fd, signal.SIGKILL),
        )

        assert runs.kill_child_groups(tmp_path, "orphaned", pid=77, pid_start="start-77") == 1
        for _ in range(50):
            try:
                os.kill(survivor, 0)
            except ProcessLookupError:
                break
            time.sleep(0.05)
        else:
            pytest.fail(f"survivor {survivor} outlived the sweep")
    finally:
        try:
            os.kill(survivor, signal.SIGKILL)
        except ProcessLookupError:
            pass


def test_a_process_that_carries_no_stamp_of_ours_is_never_touched(monkeypatch) -> None:
    signalled = _fake_proc(monkeypatch, {
        4242: b"ALPI_SPAWNED_BY=99-other\0",
        4243: b"PATH=/bin\0",
        4244: b"ALPI_SPAWNED_BY=77-start-77-extra\0",
    })

    assert runs.kill_stamped_survivors(77, "start-77") == 0
    assert signalled == []


def test_a_run_with_no_provable_identity_sweeps_no_survivors(monkeypatch) -> None:
    # An empty half would make the stamp a prefix that matches whatever carries the pid alone.
    signalled = _fake_proc(
        monkeypatch, {4242: b"ALPI_SPAWNED_BY=77-\0", 4243: b"ALPI_SPAWNED_BY=-start\0"},
    )

    assert runs.kill_stamped_survivors(77, "") == 0
    assert runs.kill_stamped_survivors(0, "start") == 0
    assert signalled == []


def test_the_stamp_is_absent_when_the_start_time_cannot_be_read(monkeypatch) -> None:
    monkeypatch.setattr(runs, "proc_starttime", lambda pid: None)
    assert runs.owner_stamp() == ""
    assert runs.stamp_env({"PATH": "/bin"}) == {"PATH": "/bin"}


def test_a_terminal_command_actually_inherits_the_stamp(tmp_path: Path, monkeypatch) -> None:
    from alpi.tools.terminal import Terminal

    _stable_starttimes(monkeypatch)
    result = Terminal().run(command="printf '%s' \"$ALPI_SPAWNED_BY\"")

    assert result.ok
    assert runs.owner_stamp() in result.output


def test_a_pipeline_gate_actually_inherits_the_stamp(tmp_path: Path, monkeypatch) -> None:
    import sys

    from alpi.alp import pipeline_gates as gates

    _stable_starttimes(monkeypatch)
    workspace = tmp_path / "ws"
    (workspace / "proj").mkdir(parents=True)
    step = gates.GateStep(
        "content", "quill", "", "", "",
        (sys.executable, "-c", "import os; print(os.environ.get('ALPI_SPAWNED_BY', 'MISSING'))"),
        "proj",
    )

    passed, out = gates.run_gate(step, workspace)

    assert passed
    assert runs.owner_stamp() in out


def test_a_supervisor_closing_a_journal_kills_what_the_run_left_running(
    tmp_path: Path, monkeypatch,
) -> None:
    from alpi.scheduler.run import _close_supervised_journal

    child = _detached_child()
    try:
        _stable_starttimes(monkeypatch)
        context = _detached_context(tmp_path, "supervised")
        runs.start(context)
        runs.record_child(context, child.pid)

        _close_supervised_journal(tmp_path, "supervised")

        assert child.wait(timeout=5) == -9, "the registry was dropped before anything killed it"
        assert runs.summary(tmp_path, "supervised")["status"] == "interrupted"
    finally:
        if child.poll() is None:
            child.kill()
            child.wait()


def test_a_pid_replaced_between_the_scan_and_the_signal_is_never_hit(monkeypatch) -> None:
    table = {4242: b"ALPI_SPAWNED_BY=77-start-77\0"}
    signalled: list[int] = []
    monkeypatch.setattr(runs, "_all_pids", lambda: sorted(table))
    monkeypatch.setattr(runs, "_environ_of", lambda pid: table.get(pid, b""))
    monkeypatch.setattr(runs, "_close_pidfd", lambda fd: None)
    monkeypatch.setattr(runs, "_kill_pidfd", lambda fd: signalled.append(fd) or True)

    def bind(pid: int) -> int:
        # The scan is a stale read: by the time the handle binds, somebody else holds the pid.
        table[pid] = b"PATH=/bin\0"
        return pid

    monkeypatch.setattr(runs, "_open_pidfd", bind)

    assert runs.kill_stamped_survivors(77, "start-77") == 0
    assert signalled == []


def test_a_handle_that_cannot_be_bound_is_never_signalled_by_pid(monkeypatch) -> None:
    signalled: list[int] = []
    monkeypatch.setattr(runs, "_all_pids", lambda: [4242])
    monkeypatch.setattr(runs, "_environ_of", lambda pid: b"ALPI_SPAWNED_BY=77-start-77\0")
    monkeypatch.setattr(runs, "_open_pidfd", lambda pid: None)
    monkeypatch.setattr(runs.os, "kill", lambda pid, sig: signalled.append(pid))

    assert runs.kill_stamped_survivors(77, "start-77") == 0
    assert signalled == []


def test_a_verifiable_group_is_cleared_before_its_marked_leader_is_reaped(
    tmp_path: Path, monkeypatch,
) -> None:
    import subprocess

    # A live leader holding an unmarked child in its group: only the group pass can reach it.
    leader = subprocess.Popen(
        ["/bin/sh", "-c", "env -i sleep 300 >/dev/null 2>&1 & echo $!; exec sleep 300"],
        stdout=subprocess.PIPE, text=True, start_new_session=True,
    )
    unmarked = int(leader.stdout.readline().strip())
    try:
        _stable_starttimes(monkeypatch)
        runs.record_child(_detached_context(tmp_path, "ordered"), leader.pid)
        _fake_proc(
            monkeypatch,
            {leader.pid: b"ALPI_SPAWNED_BY=77-start-77\0"},
            # Reaping is what destroys the proof the group pass needs.
            on_kill=lambda fd: (os.kill(fd, signal.SIGKILL), leader.wait(timeout=5)),
        )

        runs.kill_child_groups(tmp_path, "ordered", pid=77, pid_start="start-77")

        for _ in range(60):
            try:
                os.kill(unmarked, 0)
            except ProcessLookupError:
                break
            time.sleep(0.05)
        else:
            pytest.fail(f"unmarked child {unmarked} in the group outlived the sweep")
    finally:
        for target in (unmarked, leader.pid):
            try:
                os.kill(target, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if leader.poll() is None:
            leader.wait(timeout=5)
