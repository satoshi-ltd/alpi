from __future__ import annotations

import asyncio
import contextlib
import json
import threading
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from click.testing import CliRunner

from alpi import cli, doctor, run_ledger
from alpi.host import activity
from alpi.host import schedule as host_schedule
from alpi.host import server as host_server
from alpi.scheduler import jobs_store
from alpi.scheduler import run as scheduler
from alpi.tools.schedule import Schedule

_PAST = "2026-01-01T09:00:00"


def _seed(home: Path, jobs: list[dict]) -> None:
    jobs_store.update(home, lambda _jobs: jobs)


def _fail_once(home: Path, monkeypatch) -> None:
    _seed(home, [{"id": "remind", "kind": "once", "run_at": _PAST, "prompt": "remind me", "title": "Remind"}])
    monkeypatch.setattr(scheduler, "run_job", lambda job, h: scheduler.JobOutcome(False, "provider said no"))
    scheduler.tick(home)


def test_a_failed_one_shot_is_shown_failed_and_not_pending_everywhere(tmp_home_no_env: Path, monkeypatch) -> None:
    home = tmp_home_no_env
    _fail_once(home, monkeypatch)
    monkeypatch.setattr(cli, "_bootstrap", lambda h: None)

    job = jobs_store.read(home)[0]
    assert scheduler.job_status(job, home=home) == "failed"
    assert scheduler.next_fire(job, home=home) is None

    text = CliRunner().invoke(cli.main, ["schedule", "list"]).output
    assert "→ failed" in text and "provider said no" in text
    rows = json.loads(CliRunner().invoke(cli.main, ["schedule", "list", "--json"]).output)
    assert rows[0]["status"] == "failed"

    listed = json.loads(Schedule().run(action="list").output)
    assert listed[0]["status"] == "failed" and listed[0]["last_run_message"] == "provider said no"

    monkeypatch.setattr(host_schedule, "_resolve_home", lambda profile: home)
    hosted = asyncio.run(host_schedule._schedule_list({"profile": "default"}, None))
    assert hosted["jobs"][0]["status"] == "failed"

    rows = activity._scheduled([("default", home)])
    lines = cli._activity_lines({"scheduled": rows}, datetime.now().timestamp())
    assert "Failed one-shot · 1" in lines and "Scheduled · 0" in lines

    jobs_line = next(c for c in doctor._check_services(home, "default") if c.name == "Jobs")
    assert jobs_line.detail == "0 scheduled, 1 failed one-shot"


def test_a_test_fire_before_run_at_leaves_the_one_shot_due(tmp_home_no_env: Path, monkeypatch) -> None:
    home = tmp_home_no_env
    run_at = datetime.now().astimezone() + timedelta(hours=1)
    _seed(home, [{"id": "later", "kind": "once", "run_at": run_at.replace(tzinfo=None).isoformat(), "prompt": "p"}])
    ran: list[str] = []
    monkeypatch.setattr(scheduler, "run_job", lambda job, h: (ran.append(job["id"]) or scheduler.JobOutcome(True, "ok")))

    assert scheduler.fire_by_id(home, "later")[0]
    assert scheduler.job_status(jobs_store.read(home)[0], home=home) == "scheduled"

    scheduler.tick(home, now=run_at + timedelta(minutes=1))

    assert ran == ["later", "later"]
    assert jobs_store.read(home) == []


def test_firing_a_failed_one_shot_again_removes_it_when_it_succeeds(tmp_home_no_env: Path, monkeypatch) -> None:
    home = tmp_home_no_env
    _fail_once(home, monkeypatch)
    monkeypatch.setattr(scheduler, "run_job", lambda job, h: scheduler.JobOutcome(True, "ok"))

    assert scheduler.fire_by_id(home, "remind")[0]

    assert jobs_store.read(home) == []


def _blocking_run(monkeypatch):
    started, release = threading.Event(), threading.Event()
    ran: list[str] = []

    def run(job, h):
        ran.append(job["id"])
        started.set()
        release.wait(10)
        return scheduler.JobOutcome(True, "ok")

    monkeypatch.setattr(scheduler, "run_job", run)
    return started, release, ran


def test_a_fire_while_the_tick_runs_the_job_is_refused(tmp_home_no_env: Path, monkeypatch) -> None:
    home = tmp_home_no_env
    _seed(home, [{"id": "slow", "kind": "cron", "expression": "* * * * *", "prompt": "p", "last_run_at": _PAST}])
    started, release, ran = _blocking_run(monkeypatch)
    ticking = threading.Thread(target=scheduler.tick, args=(home,))
    ticking.start()
    try:
        assert started.wait(10)
        ok, message = scheduler.fire_by_id(home, "slow")
    finally:
        release.set()
        ticking.join(10)

    assert not ok and "already running" in message
    assert ran == ["slow"]


def test_the_tick_does_not_run_a_job_a_manual_fire_is_running(tmp_home_no_env: Path, monkeypatch) -> None:
    home = tmp_home_no_env
    _seed(home, [{"id": "slow", "kind": "cron", "expression": "0 9 * * *", "prompt": "p", "last_run_at": _PAST}])
    started, release, ran = _blocking_run(monkeypatch)
    firing = threading.Thread(target=scheduler.fire_by_id, args=(home, "slow"))
    firing.start()
    try:
        assert started.wait(10)
        assert scheduler.tick(home) == []
    finally:
        release.set()
        firing.join(10)

    assert ran == ["slow"]
    assert scheduler.tick(home) == []
    assert ran == ["slow"]


def test_a_manual_fire_writes_its_ledger_row(tmp_home_no_env: Path, monkeypatch) -> None:
    home = tmp_home_no_env
    _seed(home, [{"id": "abc", "kind": "cron", "expression": "0 9 * * *", "prompt": "p"}])
    monkeypatch.setattr(scheduler, "run_job", lambda job, h: scheduler.JobOutcome(False, "boom", exit_code=2))

    scheduler.fire_by_id(home, "abc")

    rows = run_ledger.read(home, kind="schedule")
    assert [(r["job_id"], r["outcome"], r["exit_code"]) for r in rows] == [("abc", "error", 2)]


def test_a_test_fire_that_ends_after_run_at_still_leaves_the_one_shot_due(tmp_home_no_env: Path, monkeypatch) -> None:
    home = tmp_home_no_env
    start = datetime.now().astimezone()
    run_at = start + timedelta(minutes=1)
    _seed(home, [{"id": "soon", "kind": "once", "run_at": run_at.replace(tzinfo=None).isoformat(), "prompt": "p"}])
    clock = [start]
    monkeypatch.setattr(scheduler, "_now", lambda: clock[0])

    def run(job, h):
        clock[0] = run_at + timedelta(minutes=1)
        return scheduler.JobOutcome(True, "ok")

    monkeypatch.setattr(scheduler, "run_job", run)

    assert scheduler.fire_by_id(home, "soon")[0]

    [job] = jobs_store.read(home)
    assert scheduler.is_due(job, now=run_at + timedelta(minutes=2), home=home)


def test_a_one_shot_test_fired_by_an_older_version_runs_once_after_the_upgrade(tmp_home_no_env: Path, monkeypatch) -> None:
    home = tmp_home_no_env
    _seed(home, [{"id": "old", "kind": "once", "run_at": "2026-03-01T09:00:00", "prompt": "p",
                  "last_run_at": "2026-02-20T10:00:00+01:00", "last_run_status": "ok"}])
    ran: list[str] = []
    monkeypatch.setattr(scheduler, "run_job", lambda job, h: (ran.append(job["id"]) or scheduler.JobOutcome(True, "ok")))

    scheduler.tick(home)
    scheduler.tick(home)

    assert ran == ["old"]
    assert jobs_store.read(home) == []


def test_the_tick_rereads_a_job_under_its_run_lock(tmp_home_no_env: Path, monkeypatch) -> None:
    home = tmp_home_no_env
    _seed(home, [{"id": "cron", "kind": "cron", "expression": "0 9 * * *", "prompt": "p", "last_run_at": _PAST}])
    real_lock = jobs_store.run_lock

    @contextlib.contextmanager
    def lock_after_a_fire_finished(h, job_id):
        def stamp(jobs):
            jobs[0]["last_run_at"] = datetime.now().astimezone().isoformat()
            return jobs
        jobs_store.update(h, stamp)
        with real_lock(h, job_id) as acquired:
            yield acquired

    monkeypatch.setattr(jobs_store, "run_lock", lock_after_a_fire_finished)
    monkeypatch.setattr(scheduler, "run_job", lambda job, h: pytest.fail("ran a job a fire had just run"))

    assert scheduler.tick(home) == []


def test_the_daemon_refuses_a_fire_while_the_job_runs(tmp_home_no_env: Path, monkeypatch) -> None:
    home = tmp_home_no_env
    _seed(home, [{"id": "slow", "kind": "cron", "expression": "0 9 * * *", "prompt": "p"}])
    monkeypatch.setattr(host_schedule, "_resolve_home", lambda profile: home)

    with jobs_store.run_lock(home, "slow") as held:
        assert held
        with pytest.raises(host_server.HandlerError) as refused:
            asyncio.run(host_schedule._schedule_fire({"profile": "default", "id": "slow"}, None))

    assert "already running" in refused.value.data["detail"]
    assert not jobs_store.is_running(home, "slow")


def test_the_console_says_a_refused_daemon_fire_is_already_running(tmp_home_no_env: Path, monkeypatch) -> None:
    from alpi.tui import host_client

    async def refuse(method, params=None, **kwargs):
        raise host_client.HostError(-32009, "conflict")

    monkeypatch.setattr(host_client, "daemon_present", lambda: True)
    monkeypatch.setattr(host_client, "acall", refuse)

    ok, message = scheduler.fire_from_console(tmp_home_no_env, "slow")

    assert not ok and message == "job 'slow' is already running; wait for that run to finish"
