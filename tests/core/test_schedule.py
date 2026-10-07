"""Tests for the schedule daemon: due-time logic, tick, kind=inactivity,
plus auto-spawn."""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from alpi.scheduler import jobs_store
from alpi.scheduler import run as scheduler
from alpi.host.connection_context import ConnectionContext, use
from alpi.tools.schedule import Schedule


# --------------------------------------------------------------------
# Job store (via the schedule tool)
# --------------------------------------------------------------------


def test_cron_tool_add_cron_job_writes_jobs_json(tmp_home_no_env: Path) -> None:
    out = Schedule().run(action="add", kind="cron",
                     expression="*/5 * * * *", prompt="morning summary",
                     notify=True)
    assert out.ok
    data = json.loads((tmp_home_no_env / "schedule" / "jobs.json").read_text())
    assert len(data) == 1
    job = data[0]
    assert job["kind"] == "cron"
    assert job["expression"] == "*/5 * * * *"
    assert job["notify"] is True
    assert "platform" not in job and "chat_id" not in job
    assert "last_run_at" not in job
    runs = json.loads((tmp_home_no_env / "schedule" / "runs.json").read_text())
    assert runs[job["id"]]["last_run_at"] is not None
    datetime.fromisoformat(runs[job["id"]]["last_run_at"])
    assert "last_run_status" not in runs[job["id"]]


def test_cron_tool_keeps_creator_connection(tmp_home_no_env: Path) -> None:
    with use(ConnectionContext("conn_javi", "dev_phone", "remote")):
        out = Schedule().run(
            action="add", kind="cron", expression="0 9 * * *", prompt="daily brief",
        )

    assert out.ok
    job = json.loads((tmp_home_no_env / "schedule" / "jobs.json").read_text())[0]
    assert job["connection_id"] == "conn_javi"


def test_cron_tool_add_cron_job_silent_by_default(tmp_home_no_env: Path) -> None:
    """Without `notify`, a job is silent maintenance — no native push."""
    out = Schedule().run(action="add", kind="cron",
                     expression="0 3 * * *", prompt="reindex workspace")
    assert out.ok
    data = json.loads((tmp_home_no_env / "schedule" / "jobs.json").read_text())
    assert data[0]["notify"] is False


def test_cron_tool_add_stores_title(tmp_home_no_env: Path) -> None:
    out = Schedule().run(action="add", kind="cron", expression="0 9 * * 1",
                     prompt="python3 ${ALPI_HOME}/skills/personal/sports/scripts/run.py",
                     no_agent=True, title="Sports this weekend")
    assert out.ok
    job = json.loads((tmp_home_no_env / "schedule" / "jobs.json").read_text())[0]
    assert job["title"] == "Sports this weekend"


def test_cron_tool_add_without_title_omits_field(tmp_home_no_env: Path) -> None:
    out = Schedule().run(action="add", kind="cron", expression="0 9 * * 1",
                     prompt="morning summary")
    assert out.ok
    job = json.loads((tmp_home_no_env / "schedule" / "jobs.json").read_text())[0]
    assert "title" not in job


def test_cron_tool_update_sets_title(tmp_home_no_env: Path) -> None:
    Schedule().run(action="add", kind="cron", expression="0 9 * * 1",
                   prompt="morning summary")
    jid = json.loads((tmp_home_no_env / "schedule" / "jobs.json").read_text())[0]["id"]
    out = Schedule().run(action="update", id=jid, title="Morning brief")
    assert out.ok
    job = json.loads((tmp_home_no_env / "schedule" / "jobs.json").read_text())[0]
    assert job["title"] == "Morning brief"


def test_cron_tool_update_empty_title_clears_it(tmp_home_no_env: Path) -> None:
    Schedule().run(action="add", kind="cron", expression="0 9 * * 1",
                   prompt="morning summary", title="Morning brief")
    jid = json.loads((tmp_home_no_env / "schedule" / "jobs.json").read_text())[0]["id"]
    out = Schedule().run(action="update", id=jid, title="")
    assert out.ok
    job = json.loads((tmp_home_no_env / "schedule" / "jobs.json").read_text())[0]
    assert "title" not in job


def test_cron_tool_update_omitted_title_untouched(tmp_home_no_env: Path) -> None:
    Schedule().run(action="add", kind="cron", expression="0 9 * * 1",
                   prompt="morning summary", title="Morning brief")
    jid = json.loads((tmp_home_no_env / "schedule" / "jobs.json").read_text())[0]["id"]
    Schedule().run(action="update", id=jid, paused=True)
    job = json.loads((tmp_home_no_env / "schedule" / "jobs.json").read_text())[0]
    assert job["title"] == "Morning brief"


def test_cron_tool_add_inactivity_job(tmp_home_no_env: Path) -> None:
    out = Schedule().run(action="add", kind="inactivity", after_hours=6,
                     prompt="check on me")
    assert out.ok
    data = json.loads((tmp_home_no_env / "schedule" / "jobs.json").read_text())
    assert data[0]["kind"] == "inactivity"
    assert data[0]["after_hours"] == 6


def test_cron_tool_add_requires_expression(tmp_home_no_env: Path) -> None:
    out = Schedule().run(action="add", kind="cron", prompt="x")
    assert not out.ok
    assert "expression" in out.error


def test_cron_tool_add_inactivity_requires_after_hours(tmp_home_no_env: Path) -> None:
    out = Schedule().run(action="add", kind="inactivity", prompt="x")
    assert not out.ok
    assert "after_hours" in out.error


# --------------------------------------------------------------------
# Due-time logic
# --------------------------------------------------------------------


def test_is_due_cron_fires_when_next_run_past(tmp_home_no_env: Path) -> None:
    # "every minute"; last_run_at = 2 minutes ago → is_due @ now.
    now = datetime(2026, 4, 19, 12, 0, 0, tzinfo=timezone.utc)
    job = {
        "kind": "cron",
        "expression": "* * * * *",
        "last_run_at": (now - timedelta(minutes=2)).isoformat(),
    }
    assert scheduler.is_due(job, now=now, home=tmp_home_no_env)


def test_is_due_cron_skips_when_not_due(tmp_home_no_env: Path) -> None:
    now = datetime(2026, 4, 19, 12, 0, 30, tzinfo=timezone.utc)
    job = {
        "kind": "cron",
        "expression": "0 * * * *",   # every hour on the hour
        "last_run_at": now.replace(minute=0, second=0).isoformat(),
    }
    # Last run was at 12:00:00; next is 13:00:00; we're at 12:00:30 → NOT due.
    assert not scheduler.is_due(job, now=now, home=tmp_home_no_env)


def test_is_due_cron_bad_expression(tmp_home_no_env: Path) -> None:
    job = {"kind": "cron", "expression": "not-a-cron", "last_run_at": "2000-01-01T00:00:00+00:00"}
    assert not scheduler.is_due(job, home=tmp_home_no_env)


def test_is_due_cron_respects_local_timezone(tmp_home_no_env: Path) -> None:
    """Cron expressions must be interpreted in the user's local time.

    Regression test for the Hua Hin bug: ``10 12 * * 1-5`` meant "12:10
    weekdays" in the user's local clock. The old ``_now()`` returned
    UTC, so croniter treated the expression as 12:10 UTC (= 19:10
    Thailand) — off by seven hours.
    """
    from datetime import timezone as _tz
    from datetime import timedelta as _td

    # Simulate a user in UTC+7. Anchor = yesterday 12:10:01 local, so
    # the last fire was right after yesterday's slot → next slot is
    # today 12:10 local.
    local = _tz(_td(hours=7))
    anchor = datetime(2026, 4, 19, 12, 10, 1, tzinfo=local)
    job = {
        "kind": "cron",
        "expression": "10 12 * * *",
        "last_run_at": anchor.isoformat(),
    }

    # At 12:11 local today, the 12:10 slot just passed → fire.
    now_after = datetime(2026, 4, 20, 12, 11, 0, tzinfo=local)
    assert scheduler.is_due(job, now=now_after, home=tmp_home_no_env)

    # At 12:09 local today, the 12:10 slot is still ahead → don't fire.
    # Critically: this would FIRE if the scheduler were treating the
    # expression as UTC (12:10 UTC = 19:10 local, well past 12:09
    # local → past due). The correct local-tz reading says not yet.
    now_before = datetime(2026, 4, 20, 12, 9, 0, tzinfo=local)
    assert not scheduler.is_due(job, now=now_before, home=tmp_home_no_env)


def test_is_due_inactivity_fires_when_quiet(tmp_home_no_env: Path) -> None:
    # Newest session file → 10 hours old. Threshold = 6 hours → due.
    sdir = tmp_home_no_env / "sessions"
    sdir.mkdir(parents=True, exist_ok=True)
    f = sdir / "old.json"
    f.write_text("{}")
    old_ts = time.time() - 10 * 3600
    import os
    os.utime(f, (old_ts, old_ts))

    now = datetime.now(timezone.utc)
    job = {"kind": "inactivity", "after_hours": 6, "last_run_at": None}
    assert scheduler.is_due(job, now=now, home=tmp_home_no_env)


def test_is_due_inactivity_cooldown(tmp_home_no_env: Path) -> None:
    # Session 10h old but we already fired 1h ago → cooldown still active.
    sdir = tmp_home_no_env / "sessions"
    sdir.mkdir(parents=True, exist_ok=True)
    f = sdir / "old.json"
    f.write_text("{}")
    old_ts = time.time() - 10 * 3600
    import os
    os.utime(f, (old_ts, old_ts))

    now = datetime.now(timezone.utc)
    job = {
        "kind": "inactivity", "after_hours": 6,
        "last_run_at": (now - timedelta(hours=1)).isoformat(),
    }
    assert not scheduler.is_due(job, now=now, home=tmp_home_no_env)


def test_is_due_inactivity_user_is_active(tmp_home_no_env: Path) -> None:
    sdir = tmp_home_no_env / "sessions"
    sdir.mkdir(parents=True, exist_ok=True)
    (sdir / "fresh.json").write_text("{}")  # mtime = now
    now = datetime.now(timezone.utc)
    job = {"kind": "inactivity", "after_hours": 1, "last_run_at": None}
    assert not scheduler.is_due(job, now=now, home=tmp_home_no_env)


# --------------------------------------------------------------------
# tick()
# --------------------------------------------------------------------


_PAST = "2000-01-01T00:00:00+00:00"


def test_tick_fires_due_jobs_and_updates_last_run(monkeypatch, tmp_home_no_env: Path) -> None:
    # Set up one always-due cron job.
    jobs = [{
        "id": "abc123", "kind": "cron", "expression": "* * * * *",
        "prompt": "ping",
        "last_run_at": _PAST,
    }]
    scheduler._save_jobs(tmp_home_no_env, jobs)

    calls = []
    monkeypatch.setattr(
        scheduler, "run_job",
        lambda job, home: (calls.append(job["id"]) or scheduler.JobOutcome(True, "ok")),
    )

    results = scheduler.tick(tmp_home_no_env)
    assert results == [("abc123", True, "ok")]
    assert calls == ["abc123"]

    saved = json.loads((tmp_home_no_env / "schedule" / "jobs.json").read_text())
    assert "last_run_at" not in saved[0]
    merged = jobs_store.read(tmp_home_no_env)
    assert merged[0]["last_run_at"] != _PAST
    assert merged[0]["last_run_status"] == "ok"


def test_tick_fires_nothing_while_profile_paused(monkeypatch, tmp_home_no_env: Path) -> None:
    jobs = [{
        "id": "abc123", "kind": "cron", "expression": "* * * * *",
        "prompt": "ping",
        "last_run_at": _PAST,
    }]
    scheduler._save_jobs(tmp_home_no_env, jobs)
    fired = []
    monkeypatch.setattr(
        scheduler, "run_job",
        lambda job, home: (fired.append(job["id"]) or scheduler.JobOutcome(True, "ok")),
    )

    (tmp_home_no_env / "config.yaml").write_text("paused: true\n")
    assert scheduler.tick(tmp_home_no_env) == []
    assert fired == []

    (tmp_home_no_env / "config.yaml").write_text("paused: false\n")
    results = scheduler.tick(tmp_home_no_env)
    assert results == [("abc123", True, "ok")]
    assert fired == ["abc123"]


def test_pause_mid_tick_stops_remaining_jobs(monkeypatch, tmp_home_no_env: Path) -> None:
    jobs = [
        {"id": "first", "kind": "cron", "expression": "* * * * *", "prompt": "a", "last_run_at": _PAST},
        {"id": "second", "kind": "cron", "expression": "* * * * *", "prompt": "b", "last_run_at": _PAST},
    ]
    scheduler._save_jobs(tmp_home_no_env, jobs)
    ran = []

    def run_and_pause(job, home):
        ran.append(job["id"])
        if job["id"] == "first":
            (tmp_home_no_env / "config.yaml").write_text("paused: true\n")
        return scheduler.JobOutcome(True, "ok")

    monkeypatch.setattr(scheduler, "run_job", run_and_pause)
    results = scheduler.tick(tmp_home_no_env)
    assert ran == ["first"], ran
    assert results == [("first", True, "ok")]
    merged = {j["id"]: j for j in jobs_store.read(tmp_home_no_env)}
    assert merged["first"]["last_run_at"] != _PAST
    assert merged["second"]["last_run_at"] == _PAST


def test_each_fired_job_is_stamped_before_the_next_one_runs(monkeypatch, tmp_home_no_env: Path) -> None:
    jobs = [
        {"id": "first", "kind": "cron", "expression": "* * * * *", "prompt": "a", "last_run_at": _PAST},
        {"id": "second", "kind": "cron", "expression": "* * * * *", "prompt": "b", "last_run_at": _PAST},
    ]
    scheduler._save_jobs(tmp_home_no_env, jobs)
    seen_while_second_runs = {}

    def run(job, home):
        if job["id"] == "second":
            seen_while_second_runs.update({j["id"]: j for j in jobs_store.read(home)})
        return scheduler.JobOutcome(True, "ok")

    monkeypatch.setattr(scheduler, "run_job", run)
    scheduler.tick(tmp_home_no_env)

    assert seen_while_second_runs["first"]["last_run_at"] != _PAST
    assert seen_while_second_runs["first"]["last_run_status"] == "ok"
    assert seen_while_second_runs["second"]["last_run_at"] == _PAST


def test_the_stamp_lands_before_the_run_is_reported(monkeypatch, tmp_home_no_env: Path) -> None:
    scheduler._save_jobs(tmp_home_no_env, [
        {"id": "only", "kind": "cron", "expression": "* * * * *", "prompt": "a", "last_run_at": _PAST},
    ])
    stamped_at_report = []
    monkeypatch.setattr(scheduler, "run_job", lambda job, home: scheduler.JobOutcome(True, "ok"))
    monkeypatch.setattr(
        scheduler, "_emit_schedule_event",
        lambda home, job, outcome: stamped_at_report.append(jobs_store.read(home)[0]["last_run_at"]),
    )

    scheduler.tick(tmp_home_no_env)

    assert stamped_at_report and stamped_at_report[0] != _PAST


def test_a_restart_after_the_first_job_does_not_fire_it_again(monkeypatch, tmp_home_no_env: Path) -> None:
    now = datetime(2026, 3, 2, 12, 0, tzinfo=timezone.utc)
    jobs = [
        {"id": "first", "kind": "cron", "expression": "* * * * *", "prompt": "a", "last_run_at": _PAST},
        {"id": "second", "kind": "cron", "expression": "* * * * *", "prompt": "b", "last_run_at": _PAST},
    ]
    scheduler._save_jobs(tmp_home_no_env, jobs)
    ran = []
    crashed = []

    class Crash(BaseException):
        pass

    def run(job, home):
        ran.append(job["id"])
        if job["id"] == "second" and not crashed:
            crashed.append(True)
            raise Crash
        return scheduler.JobOutcome(True, "ok")

    monkeypatch.setattr(scheduler, "run_job", run)
    with pytest.raises(Crash):
        scheduler.tick(tmp_home_no_env, now=now)
    ran.clear()
    scheduler.tick(tmp_home_no_env, now=now + timedelta(seconds=10))

    assert ran == ["second"]


def test_stamping_per_job_keeps_one_shot_and_failure_semantics(monkeypatch, tmp_home_no_env: Path) -> None:
    jobs = [
        {"id": "done", "kind": "once", "run_at": _PAST, "prompt": "a"},
        {"id": "broken", "kind": "cron", "expression": "* * * * *", "prompt": "b", "last_run_at": _PAST},
        {"id": "retry", "kind": "once", "run_at": _PAST, "prompt": "c"},
    ]
    scheduler._save_jobs(tmp_home_no_env, jobs)
    outcomes = {"done": True, "broken": False, "retry": False}
    monkeypatch.setattr(
        scheduler, "run_job",
        lambda job, home: scheduler.JobOutcome(outcomes[job["id"]], "x"),
    )

    scheduler.tick(tmp_home_no_env)

    merged = {j["id"]: j for j in jobs_store.read(tmp_home_no_env)}
    assert "done" not in merged
    assert merged["broken"]["last_run_status"] == "error"
    assert merged["broken"]["last_run_at"] != _PAST
    assert merged["retry"]["last_run_status"] == "error"


def test_fire_by_id_bypasses_profile_pause(monkeypatch, tmp_home_no_env: Path) -> None:
    jobs = [{"id": "abc123", "kind": "cron", "expression": "* * * * *", "prompt": "ping", "last_run_at": None}]
    scheduler._save_jobs(tmp_home_no_env, jobs)
    (tmp_home_no_env / "config.yaml").write_text("paused: true\n")
    ran = []
    monkeypatch.setattr(
        scheduler, "run_job",
        lambda job, home: (ran.append(job["id"]) or scheduler.JobOutcome(True, "ok")),
    )
    ok, _msg = scheduler.fire_by_id(tmp_home_no_env, "abc123")
    assert ok is True
    assert ran == ["abc123"]


def test_tick_skips_not_due(monkeypatch, tmp_home_no_env: Path) -> None:
    # Job's next fire is an hour away.
    now = datetime.now(timezone.utc)
    jobs = [{
        "id": "a", "kind": "cron", "expression": "0 0 1 1 *",  # yearly
        "prompt": "x",
        "last_run_at": now.isoformat(),
    }]
    scheduler._save_jobs(tmp_home_no_env, jobs)

    fired = []
    monkeypatch.setattr(
        scheduler, "run_job",
        lambda job, home: (fired.append(1) or scheduler.JobOutcome(True, "ok")),
    )
    results = scheduler.tick(tmp_home_no_env)
    assert results == []
    assert fired == []


def test_tick_failure_still_updates_last_run(monkeypatch, tmp_home_no_env: Path) -> None:
    jobs = [{
        "id": "x", "kind": "cron", "expression": "* * * * *",
        "prompt": "boom",
        "last_run_at": _PAST,
    }]
    scheduler._save_jobs(tmp_home_no_env, jobs)
    monkeypatch.setattr(scheduler, "run_job",
                        lambda job, home: scheduler.JobOutcome(False, "boom"))
    results = scheduler.tick(tmp_home_no_env)
    assert results == [("x", False, "boom")]
    merged = jobs_store.read(tmp_home_no_env)
    assert merged[0]["last_run_at"] != _PAST
    assert merged[0]["last_run_status"] == "error"
    assert "last_run_at" not in json.loads(
        (tmp_home_no_env / "schedule" / "jobs.json").read_text())[0]


def test_a_job_that_raises_is_stamped_failed_and_the_pass_goes_on(monkeypatch, tmp_home_no_env: Path) -> None:
    jobs = [
        {"id": jid, "kind": "cron", "expression": "* * * * *", "prompt": jid, "last_run_at": _PAST}
        for jid in ("a", "b", "c")
    ]
    scheduler._save_jobs(tmp_home_no_env, jobs)
    fired: list[str] = []

    def run(job, home):
        fired.append(job["id"])
        if job["id"] == "b":
            raise PermissionError("agent subprocess denied")
        return scheduler.JobOutcome(True, "ok")

    monkeypatch.setattr(scheduler, "run_job", run)
    now = datetime(2026, 10, 3, 12, 0, 5, tzinfo=timezone.utc)
    results = scheduler.tick(tmp_home_no_env, now=now)

    assert [(jid, ok) for jid, ok, _ in results] == [("a", True), ("b", False), ("c", True)]
    assert "PermissionError" in results[1][2]
    status = {j["id"]: j["last_run_status"] for j in jobs_store.read(tmp_home_no_env)}
    assert status == {"a": "ok", "b": "error", "c": "ok"}

    fired.clear()
    scheduler.tick(tmp_home_no_env, now=now + timedelta(seconds=10))
    assert fired == []
    from alpi import outputs as outputs_mod
    errors = [o for o in outputs_mod.list_outputs(tmp_home_no_env) if o.get("type") == "error"]
    assert [o.get("job_id") for o in errors] == ["b"]


def test_a_job_fired_by_hand_that_raises_is_stamped_and_reported(monkeypatch, tmp_home_no_env: Path, caplog) -> None:
    scheduler._save_jobs(tmp_home_no_env, [{"id": "m", "kind": "cron", "expression": "0 3 * * *", "prompt": "m"}])

    def run(job, home):
        raise OSError("token=sk-live-1234567890abcdefghij could not open /data/x")

    monkeypatch.setattr(scheduler, "run_job", run)
    ok, message = scheduler.fire_by_id(tmp_home_no_env, "m")

    assert ok is False
    assert message.startswith("the run raised OSError")
    assert "sk-live-1234567890abcdefghij" not in message
    assert "sk-live-1234567890abcdefghij" not in caplog.text and "OSError" in caplog.text
    assert jobs_store.read(tmp_home_no_env)[0]["last_run_status"] == "error"


def test_a_run_that_succeeded_stays_ok_when_closing_its_activity_row_raises(monkeypatch, tmp_home_no_env: Path) -> None:
    from contextlib import contextmanager
    from alpi.host import activity

    @contextmanager
    def closing_fails(home, job):
        yield
        raise RuntimeError("Event loop is closed")

    monkeypatch.setattr(activity, "scheduled_run", closing_fails)
    monkeypatch.setattr(scheduler, "run_job", lambda job, home: scheduler.JobOutcome(True, "done"))
    assert scheduler._run_guarded({"id": "j"}, tmp_home_no_env).ok is True

    monkeypatch.setattr(scheduler, "run_job", lambda job, home: (_ for _ in ()).throw(ValueError()))
    assert scheduler._run_guarded({"id": "j"}, tmp_home_no_env).message == "the run raised ValueError"


def _deploy_by_file(home: Path, jobs: list[dict], runs: dict | None = None) -> None:
    jobs_store.jobs_path(home).parent.mkdir(parents=True, exist_ok=True)
    jobs_store.jobs_path(home).write_text(json.dumps(jobs))
    if runs is not None:
        jobs_store.runs_path(home).write_text(json.dumps(runs))


def _record_fires(monkeypatch) -> list[str]:
    fired: list[str] = []
    monkeypatch.setattr(
        scheduler, "run_job",
        lambda job, home: (fired.append(job["id"]) or scheduler.JobOutcome(True, "ok")),
    )
    return fired


def test_a_cron_job_deployed_without_state_waits_for_its_next_occurrence(monkeypatch, tmp_home_no_env: Path) -> None:
    _deploy_by_file(tmp_home_no_env, [
        {"id": "weekly", "kind": "cron", "expression": "25 17 * * 0", "prompt": "report"},
    ])
    fired = _record_fires(monkeypatch)
    thursday = datetime(2026, 9, 24, 15, 0, tzinfo=timezone.utc)

    assert scheduler.tick(tmp_home_no_env, now=thursday) == []
    assert scheduler.tick(tmp_home_no_env, now=thursday + timedelta(minutes=1)) == []
    assert fired == []
    assert json.loads(jobs_store.runs_path(tmp_home_no_env).read_text()) == {
        "weekly": {"first_seen_at": thursday.isoformat()},
    }
    assert "first_seen_at" not in json.loads(jobs_store.jobs_path(tmp_home_no_env).read_text())[0]
    assert scheduler.next_fire(jobs_store.read(tmp_home_no_env)[0], thursday) == datetime(
        2026, 9, 27, 17, 25, tzinfo=timezone.utc)

    sunday = datetime(2026, 9, 27, 17, 25, 30, tzinfo=timezone.utc)
    assert scheduler.tick(tmp_home_no_env, now=sunday) == [("weekly", True, "ok")]
    assert fired == ["weekly"]


def test_a_paused_job_is_anchored_when_resumed_not_when_deployed(monkeypatch, tmp_home_no_env: Path) -> None:
    _deploy_by_file(tmp_home_no_env, [
        {"id": "daily", "kind": "cron", "expression": "0 9 * * *", "prompt": "x", "paused": True},
    ])
    fired = _record_fires(monkeypatch)
    monday = datetime(2026, 9, 21, 8, 0, tzinfo=timezone.utc)
    assert scheduler.tick(tmp_home_no_env, now=monday) == []
    assert "daily" not in jobs_store._load_json(jobs_store.runs_path(tmp_home_no_env), dict)

    jobs_store.update(tmp_home_no_env, lambda jobs: [{**j, "paused": False} for j in jobs])
    friday = datetime(2026, 9, 25, 10, 0, tzinfo=timezone.utc)
    assert scheduler.tick(tmp_home_no_env, now=friday) == []
    assert fired == []
    assert jobs_store.read(tmp_home_no_env)[0]["first_seen_at"] == friday.isoformat()


def test_an_unparsable_last_run_at_is_anchored_instead_of_stranding_the_job(monkeypatch, tmp_home_no_env: Path) -> None:
    _deploy_by_file(
        tmp_home_no_env,
        [{"id": "j", "kind": "cron", "expression": "* * * * *", "prompt": "x"}],
        {"j": {"last_run_at": "not-a-date"}},
    )
    fired = _record_fires(monkeypatch)
    now = datetime(2026, 9, 25, 10, 0, 10, tzinfo=timezone.utc)
    assert scheduler.tick(tmp_home_no_env, now=now) == []
    assert scheduler.tick(tmp_home_no_env, now=now + timedelta(minutes=1)) == [("j", True, "ok")]
    assert fired == ["j"]


def test_a_job_paused_while_the_tick_runs_is_not_anchored(monkeypatch, tmp_home_no_env: Path) -> None:
    _deploy_by_file(
        tmp_home_no_env,
        [{"id": "due", "kind": "cron", "expression": "* * * * *", "prompt": "a"},
         {"id": "new", "kind": "cron", "expression": "0 9 * * *", "prompt": "b"}],
        {"due": {"last_run_at": _PAST}},
    )

    def run_and_pause_new(job, home):
        jobs_store.update(home, lambda jobs: [{**j, "paused": True} if j["id"] == "new" else j for j in jobs])
        return scheduler.JobOutcome(True, "ok")

    monkeypatch.setattr(scheduler, "run_job", run_and_pause_new)
    assert scheduler.tick(tmp_home_no_env) == [("due", True, "ok")]
    assert "first_seen_at" not in {j["id"]: j for j in jobs_store.read(tmp_home_no_env)}["new"]


def test_a_numeric_id_or_timestamp_from_a_deploy_neither_crashes_nor_refires(monkeypatch, tmp_home_no_env: Path) -> None:
    _deploy_by_file(
        tmp_home_no_env,
        [{"id": 5, "kind": "cron", "expression": "* * * * *", "prompt": "x"},
         {"id": "epoch", "kind": "cron", "expression": "* * * * *", "prompt": "y"}],
        {"5": {"last_run_at": _PAST}, "epoch": {"last_run_at": 1790000000}},
    )
    fired = _record_fires(monkeypatch)
    now = datetime(2026, 9, 25, 10, 0, 10, tzinfo=timezone.utc)
    assert scheduler.tick(tmp_home_no_env, now=now) == [("5", True, "ok")]
    assert scheduler.tick(tmp_home_no_env, now=now + timedelta(seconds=30)) == []
    assert scheduler.tick(tmp_home_no_env, now=now + timedelta(minutes=1)) == [("5", True, "ok"), ("epoch", True, "ok")]
    assert fired == [5, 5, "epoch"]


# --------------------------------------------------------------------
# run_job() — delivery integration
# --------------------------------------------------------------------


def _events_stdout(events: list[dict]) -> str:
    return "\n".join(json.dumps(e) for e in events)


def test_run_job_notifies_when_notify_true(monkeypatch, tmp_home_no_env: Path) -> None:
    captured = {}

    class _FakeCompletedProcess:
        returncode = 0
        stdout = _events_stdout([{"kind": "reply", "text": "hello world"}])
        stderr = ""

    def fake_run(*a, **kw):
        captured["args"] = a[0]
        captured["env"] = kw.get("env") or {}
        return _FakeCompletedProcess()

    monkeypatch.setattr(scheduler.subprocess, "run", fake_run)

    job = {"id": "j", "kind": "cron", "prompt": "p", "notify": True}
    outcome = scheduler.run_job(job, tmp_home_no_env)
    assert outcome.ok
    assert "--no-save" in captured["args"]
    assert captured["env"].get("ALPI_SCHEDULE_CHILD") == "1"
    assert outcome.delivered_to == "alpi"
    assert outcome.reply == "hello world"


def test_run_job_silent_when_notify_false(monkeypatch, tmp_home_no_env: Path) -> None:
    """Jobs without ``notify`` run silently — work happens, no native
    push, empty reply is success."""
    class _FakeCompletedProcess:
        returncode = 0
        stdout = _events_stdout([])
        stderr = ""

    captured_args = {}

    def fake_run(*a, **kw):
        captured_args["cmd"] = a[0]
        return _FakeCompletedProcess()

    monkeypatch.setattr(scheduler.subprocess, "run", fake_run)

    job = {"id": "j", "kind": "cron", "prompt": "reindex"}
    ok, msg, _reply = scheduler.run_job(job, tmp_home_no_env)
    assert ok
    assert "silent" in msg
    joined = " ".join(captured_args["cmd"])
    # Silent-job wrapper teaches the agent: notify(...) for a native push, email for a third party; schedule.done alone doesn't wake the user.
    assert "notify" in joined
    assert "email" in joined
    assert "schedule.done" in joined


def test_run_job_silent_does_not_notify(monkeypatch, tmp_home_no_env: Path) -> None:
    class _FakeCompletedProcess:
        returncode = 0
        stdout = _events_stdout([{"kind": "reply", "text": "did some work"}])
        stderr = ""

    monkeypatch.setattr(
        scheduler.subprocess, "run",
        lambda *a, **kw: _FakeCompletedProcess(),
    )
    job = {"id": "j", "kind": "cron", "prompt": "p", "notify": False}
    outcome = scheduler.run_job(job, tmp_home_no_env)
    assert outcome.ok
    assert outcome.delivered_to == ""
    assert "silent" in outcome.message


def test_run_job_skips_auto_notify_when_agent_already_notified(
        monkeypatch, tmp_home_no_env: Path) -> None:
    """If the sub-agent natively notified the user (notify), the daemon
    must NOT also auto-notify the reply."""
    class _FakeCompletedProcess:
        returncode = 0
        stdout = _events_stdout([
            {"kind": "tool_start", "name": "notify", "preview": "standup"},
            {"kind": "tool_end", "name": "notify", "ok": True},
            {"kind": "reply", "text": "done"},
        ])
        stderr = ""

    monkeypatch.setattr(
        scheduler.subprocess, "run",
        lambda *a, **kw: _FakeCompletedProcess(),
    )
    job = {"id": "j", "kind": "cron", "prompt": "p", "notify": True}
    outcome = scheduler.run_job(job, tmp_home_no_env)
    assert outcome.ok
    assert outcome.delivered_to == "external"
    assert "no duplicate" in outcome.message


# --------------------------------------------------------------------
# run_job() — no_agent (script-only watchdog) path
# --------------------------------------------------------------------


def _fake_completed(rc: int, stdout: str = "", stderr: str = ""):
    """Build a stub CompletedProcess matching scheduler's subprocess.run usage."""
    class _Stub:
        returncode = rc
        def __init__(self) -> None:
            self.stdout = stdout
            self.stderr = stderr
    return _Stub()


def _stub_skill_path(home: Path, leaf: str = "scripts/run.py") -> str:
    # Path.resolve() canonicalizes via the filesystem, so the parent tree
    # must exist for the allowlist check to land under skills/ correctly.
    skill = home / "skills" / "personal" / "stub"
    (skill / "scripts").mkdir(parents=True, exist_ok=True)
    script = skill / leaf
    script.write_text("#!/usr/bin/env python3\n")
    return str(script)


def test_no_agent_silent_when_no_stdout(monkeypatch, tmp_home_no_env: Path) -> None:
    """A no_agent job with empty stdout is a silent success — the daemon
    must NOT spawn the LLM agent and must NOT call delivery.send_to."""
    script = _stub_skill_path(tmp_home_no_env)
    spawn_calls = []
    def fake_run(argv, **kw):
        spawn_calls.append(argv)
        # ensure the command was tokenized by shlex (not the wrapped agent path)
        assert "alpi" not in argv[:3], "no_agent must not invoke alpi chat"
        return _fake_completed(rc=0, stdout="")

    monkeypatch.setattr(scheduler.subprocess, "run", fake_run)

    job = {"id": "j", "kind": "cron", "no_agent": True,
           "prompt": f"python3 {script}"}
    ok, msg, _reply = scheduler.run_job(job, tmp_home_no_env)

    assert ok
    assert "silent" in msg
    assert spawn_calls == [["python3", script]]


def test_no_agent_notifies_stdout_when_notify_true(
        monkeypatch, tmp_home_no_env: Path) -> None:
    """Non-empty stdout becomes the reply and is pushed natively when notify=True."""
    script = _stub_skill_path(tmp_home_no_env)

    monkeypatch.setattr(
        scheduler.subprocess, "run",
        lambda *a, **kw: _fake_completed(rc=0, stdout="hello from script\n"),
    )
    job = {"id": "j", "kind": "cron", "no_agent": True,
           "prompt": f"python3 {script}", "notify": True}
    outcome = scheduler.run_job(job, tmp_home_no_env)

    assert outcome.ok
    assert outcome.delivered_to == "alpi"
    assert outcome.reply == "hello from script"


def test_no_agent_nonzero_exit_fails_with_stderr(
        monkeypatch, tmp_home_no_env: Path) -> None:
    """Script failure surfaces a snippet of stderr in the result message
    so the operator can diagnose without digging into the daemon log."""
    script = _stub_skill_path(tmp_home_no_env)
    monkeypatch.setattr(
        scheduler.subprocess, "run",
        lambda *a, **kw: _fake_completed(rc=2, stderr="ModuleNotFoundError: foo"),
    )

    job = {"id": "j", "kind": "cron", "no_agent": True,
           "prompt": f"python3 {script}"}
    ok, msg, _reply = scheduler.run_job(job, tmp_home_no_env)

    assert not ok
    assert "rc=2" in msg
    assert "ModuleNotFoundError" in msg


def test_no_agent_expands_alpi_home_and_loads_dotenv(
        monkeypatch, tmp_home_no_env: Path) -> None:
    """${ALPI_HOME} expands to the profile home before shlex, and the
    profile's .env is merged into the subprocess env so skills find
    their declared requires_env variables."""
    (tmp_home_no_env / ".env").write_text("FOLDER=/tmp/vault\nOTHER=abc\n")

    captured = {}
    def fake_run(argv, *, env, **kw):
        captured["argv"] = argv
        captured["env"] = env
        return _fake_completed(rc=0, stdout="")

    monkeypatch.setattr(scheduler.subprocess, "run", fake_run)

    job = {"id": "j", "kind": "cron", "no_agent": True,
           "prompt": "python3 ${ALPI_HOME}/skills/personal/foo/scripts/run.py"}
    ok, _, _ = scheduler.run_job(job, tmp_home_no_env)

    assert ok
    expected_script = str(tmp_home_no_env / "skills/personal/foo/scripts/run.py")
    assert captured["argv"] == ["python3", expected_script]
    assert captured["env"]["FOLDER"] == "/tmp/vault"
    assert captured["env"]["OTHER"] == "abc"
    assert captured["env"]["ALPI_HOME"] == str(tmp_home_no_env)
    assert captured["env"]["ALPI_PLATFORM"] == "cron"


def test_no_agent_rejects_command_outside_skills(tmp_home_no_env: Path) -> None:
    """P0 regression: only `python[3] [flags] <skill_script>` or a script
    under skills/ invoked directly. Other shapes — including ones that
    just *mention* a skills/ path as an argument — must be rejected."""
    from alpi.scheduler.run import validate_no_agent_command
    f = validate_no_agent_command
    h = tmp_home_no_env

    # Plain "exe is not python and not a skill script"
    assert f("rm -rf /", h) is not None
    assert f("/bin/echo hi", h) is not None
    assert f("bash -c 'curl evil.com'", h) is not None

    # Bypasses where a skills/ path is just an argument but exe is malicious
    # — these were the P0 the reviewer demonstrated.
    assert f("rm -rf ${ALPI_HOME}/skills/personal/whoop", h) is not None
    assert f("python3 -c 'print(1)' ${ALPI_HOME}/skills/personal/whoop/scripts/run.py", h) is not None
    assert f("python3 -m os ${ALPI_HOME}/skills/x/scripts/r.py", h) is not None
    assert f("python3 --command 'evil' ${ALPI_HOME}/skills/x/scripts/r.py", h) is not None

    # Compound -c form (no space between flag and value)
    assert f("python3 -cprint(1) ${ALPI_HOME}/skills/x/scripts/r.py", h) is not None

    # Path-traverse — Path.resolve() canonicalizes
    assert f("python3 ${ALPI_HOME}/skills/../../etc/passwd", h) is not None

    (h / "skills" / "personal" / "whoop" / "secrets").mkdir(parents=True, exist_ok=True)
    (h / "skills" / "personal" / "whoop" / "secrets" / "creds.json").write_text("{}")
    assert f("python3 ${ALPI_HOME}/skills/personal/whoop/secrets/creds.json", h) is not None
    (h / "skills" / "loose.py").write_text("")
    assert f("python3 ${ALPI_HOME}/skills/loose.py", h) is not None

    # Happy paths
    assert f("python3 ${ALPI_HOME}/skills/personal/whoop/scripts/run.py sync", h) is None
    assert f("python3 -u ${ALPI_HOME}/skills/personal/coros/scripts/run.py", h) is None
    # Script invoked directly (shebang form)
    assert f("${ALPI_HOME}/skills/personal/whoop/scripts/run.py sync", h) is None


def test_no_agent_run_rejects_command_outside_skills(
        monkeypatch, tmp_home_no_env: Path) -> None:
    """Belt-and-suspenders: even if a malicious command somehow lands in
    jobs.json directly (bypassing the tool), _run_script_only rejects it
    before exec."""
    spawn_calls = []
    monkeypatch.setattr(scheduler.subprocess, "run",
                        lambda *a, **kw: spawn_calls.append(a) or None)

    job = {"id": "j", "kind": "cron", "no_agent": True,
           "prompt": "/bin/echo gotcha"}
    ok, msg, _reply = scheduler.run_job(job, tmp_home_no_env)

    assert not ok
    assert "no_agent rejected" in msg
    assert spawn_calls == [], "subprocess.run must NOT be called for rejected commands"


def test_no_agent_env_profile_wins_over_daemon_env(
        monkeypatch, tmp_home_no_env: Path) -> None:
    """P1 regression: when the daemon's own env has a stale FOLDER (e.g.
    from a sibling profile), the firing profile's .env must override it."""
    (tmp_home_no_env / ".env").write_text("FOLDER=/right/path\n")
    monkeypatch.setenv("FOLDER", "/wrong/sibling/path")
    script = _stub_skill_path(tmp_home_no_env)

    captured = {}
    def fake_run(argv, *, env, **kw):
        captured["env"] = env
        return _fake_completed(rc=0, stdout="")

    monkeypatch.setattr(scheduler.subprocess, "run", fake_run)
    job = {"id": "j", "kind": "cron", "no_agent": True,
           "prompt": f"python3 {script}"}
    ok, _, _ = scheduler.run_job(job, tmp_home_no_env)

    assert ok
    assert captured["env"]["FOLDER"] == "/right/path", (
        "profile .env must override daemon's inherited FOLDER"
    )


def test_no_agent_skips_threat_scan(monkeypatch, tmp_home_no_env: Path) -> None:
    """The threat scanner targets LLM prompt injection; for no_agent it
    must NOT run — the allowlist is the security boundary instead."""
    script = _stub_skill_path(tmp_home_no_env)
    from alpi.tools import skill as skill_mod
    scan_calls = []
    monkeypatch.setattr(skill_mod, "scan_skill_body",
                        lambda body: scan_calls.append(body) or ["fake-flag"])
    monkeypatch.setattr(
        scheduler.subprocess, "run",
        lambda *a, **kw: _fake_completed(rc=0, stdout=""),
    )

    job = {"id": "j", "kind": "cron", "no_agent": True,
           "prompt": f"python3 {script}"}
    ok, _, _ = scheduler.run_job(job, tmp_home_no_env)

    assert ok
    assert scan_calls == [], "threat scan must NOT run for no_agent jobs"


# --------------------------------------------------------------------
# ensure_running — auto-spawn
# --------------------------------------------------------------------


def test_ensure_running_noop_when_already_alive(
        monkeypatch, tmp_home_no_env: Path) -> None:
    monkeypatch.setattr(scheduler, "running_pid", lambda home: 4242)
    spawn_calls = []
    monkeypatch.setattr(
        scheduler.subprocess, "Popen",
        lambda *a, **kw: spawn_calls.append((a, kw)),
    )
    pid = scheduler.ensure_running(tmp_home_no_env)
    assert pid == 4242
    assert spawn_calls == []


def test_ensure_running_spawns_detached_when_dead(
        monkeypatch, tmp_home_no_env: Path) -> None:
    monkeypatch.setattr(scheduler, "running_pid", lambda home: None)

    class _FakeProc:
        pid = 9999

    captured = {}

    def fake_popen(args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return _FakeProc()

    monkeypatch.setattr(scheduler.subprocess, "Popen", fake_popen)
    pid = scheduler.ensure_running(tmp_home_no_env)

    assert pid == 9999
    # Must be detached from the parent terminal/session.
    assert captured["kwargs"].get("start_new_session") is True
    # stdin closed so the child can't block on input.
    assert captured["kwargs"].get("stdin") is scheduler.subprocess.DEVNULL
    # Child inherits ALPI_HOME so it writes to the right profile.
    env = captured["kwargs"].get("env") or {}
    assert env.get("ALPI_HOME") == str(tmp_home_no_env)
    # Command invoked is `alpi schedule start`.
    assert "schedule" in captured["args"]
    assert "start" in captured["args"]


# --------------------------------------------------------------------
# fire_by_id — ad-hoc job fire (BA)
# --------------------------------------------------------------------


def test_fire_by_id_runs_matching_job(monkeypatch, tmp_home_no_env: Path) -> None:
    jobs_path = scheduler.jobs_path(tmp_home_no_env)
    jobs_path.parent.mkdir(parents=True, exist_ok=True)
    jobs_path.write_text(json.dumps([
        {"id": "alpha", "kind": "cron", "prompt": "hi", "expression": "0 9 * * *"},
        {"id": "beta", "kind": "once", "prompt": "other", "run_at": "2099-01-01T00:00:00"},
    ], indent=2))

    called_with = {}

    def fake_run_job(job, home):
        called_with["id"] = job["id"]
        called_with["prompt"] = job["prompt"]
        return scheduler.JobOutcome(
            True, "ran alpha",
            reply="hi world", delivered_to="alpi",
        )

    monkeypatch.setattr(scheduler, "run_job", fake_run_job)

    ok, msg = scheduler.fire_by_id(tmp_home_no_env, "alpha")
    assert ok, msg
    assert called_with == {"id": "alpha", "prompt": "hi"}
    assert "ran alpha" in msg
    merged = jobs_store.read(tmp_home_no_env)
    alpha = next(j for j in merged if j["id"] == "alpha")
    assert alpha["last_run_status"] == "ok"


def test_fire_by_id_unknown_returns_error(tmp_home_no_env: Path) -> None:
    scheduler.jobs_path(tmp_home_no_env).parent.mkdir(parents=True, exist_ok=True)
    scheduler.jobs_path(tmp_home_no_env).write_text(json.dumps([]))
    ok, msg = scheduler.fire_by_id(tmp_home_no_env, "nope")
    assert not ok
    assert "nope" in msg


def test_fire_by_id_does_not_consume_once_job(
        monkeypatch, tmp_home_no_env: Path) -> None:
    """Ad-hoc fire is deliberate testing, not the natural trigger. A
    successful fire on a kind=once job must NOT delete it from jobs.json
    — the user still wants that job on the books for its real time."""
    jobs_path = scheduler.jobs_path(tmp_home_no_env)
    jobs_path.parent.mkdir(parents=True, exist_ok=True)
    jobs_path.write_text(json.dumps([
        {"id": "tomorrow", "kind": "once", "prompt": "remind me",         "run_at": "2099-01-01T09:00:00"},
    ], indent=2))

    monkeypatch.setattr(scheduler, "run_job", lambda job, home: scheduler.JobOutcome(True, "ok"))
    ok, _ = scheduler.fire_by_id(tmp_home_no_env, "tomorrow")
    assert ok

    jobs_after = json.loads(jobs_path.read_text())
    assert len(jobs_after) == 1
    assert jobs_after[0]["id"] == "tomorrow"
    # last_run_at must land so the operator sees it was tested.
    assert "last_run_at" in jobs_store.read(tmp_home_no_env)[0]


def test_schedule_tool_fire_action(monkeypatch, tmp_home_no_env: Path) -> None:
    monkeypatch.setenv("ALPI_HOME", str(tmp_home_no_env))
    (tmp_home_no_env / "schedule").mkdir(parents=True, exist_ok=True)

    # Seed one job.
    Schedule().run(action="add", kind="cron", expression="0 9 * * *",
                   prompt="ping", notify=True)

    # Look up its id from jobs.json.
    jobs = json.loads((tmp_home_no_env / "schedule" / "jobs.json").read_text())
    jid = jobs[0]["id"]

    # Stub the actual subprocess-spawning turn.
    monkeypatch.setattr(
        scheduler, "run_job",
        lambda job, home: scheduler.JobOutcome(
            True, "notified", reply="x", delivered_to="alpi",
        ),
    )

    r = Schedule().run(action="fire", id=jid)
    assert r.ok, r.error
    assert "notified" in r.output


def test_schedule_tool_fire_requires_id(tmp_home_no_env: Path,
                                         monkeypatch) -> None:
    monkeypatch.setenv("ALPI_HOME", str(tmp_home_no_env))
    r = Schedule().run(action="fire")
    assert not r.ok
    assert "id" in (r.error or "").lower()


# --------------------------------------------------------------------
# Profile isolation: scheduler.serve() must not block the event loop
# --------------------------------------------------------------------


def test_serve_runs_tick_off_loop_so_chat_can_progress(
    tmp_home_no_env: Path, monkeypatch,
) -> None:
    """The freeze reported with the doc profile happened because tick()
    was running inline on the loop and a 30s subprocess.run blocked every
    coroutine. serve() must offload tick to an executor."""
    import asyncio
    import time as _time

    tick_block_s = 0.5
    tick_started = asyncio.Event()
    tick_done = asyncio.Event()

    def slow_tick(home, now=None):  # noqa: ANN001
        # Set the event from inside a thread — schedule it on the loop.
        loop.call_soon_threadsafe(tick_started.set)
        _time.sleep(tick_block_s)
        loop.call_soon_threadsafe(tick_done.set)

    monkeypatch.setattr(scheduler, "tick", slow_tick)
    monkeypatch.setattr(scheduler, "TICK_SECONDS", 0.05)

    async def _run() -> dict:
        nonlocal loop
        loop = asyncio.get_running_loop()
        # Concurrent coroutine that wakes every 50ms — counts whether the loop is responsive.
        counter = {"wakes": 0}

        async def heartbeat() -> None:
            while not tick_done.is_set():
                await asyncio.sleep(0.05)
                counter["wakes"] += 1

        serve_task = asyncio.create_task(scheduler.serve(tmp_home_no_env))
        hb_task = asyncio.create_task(heartbeat())

        try:
            await asyncio.wait_for(tick_started.wait(), timeout=2.0)
            t0 = _time.monotonic()
            await asyncio.wait_for(tick_done.wait(), timeout=tick_block_s + 1.0)
            elapsed = _time.monotonic() - t0
        finally:
            serve_task.cancel()
            hb_task.cancel()
            for t in (serve_task, hb_task):
                try:
                    await t
                except (asyncio.CancelledError, Exception):  # noqa: BLE001
                    pass

        return {"elapsed_during_tick": elapsed, "heartbeats": counter["wakes"]}

    loop: asyncio.AbstractEventLoop | None = None  # set inside _run
    result = asyncio.run(_run())

    # During the 0.5s blocking tick the heartbeat must keep firing — without isolation it'd be stuck and elapsed would jump.
    assert result["heartbeats"] >= 3, (
        f"loop starved during tick — only {result['heartbeats']} heartbeats fired "
        "while tick blocked for 500ms; serve() must run tick in an executor"
    )


def test_job_run_timeout_defaults_to_900_when_unset() -> None:
    assert scheduler.job_run_timeout({}) == scheduler.DEFAULT_RUN_TIMEOUT_SECONDS == 900


def test_job_run_timeout_honors_explicit_value() -> None:
    assert scheduler.job_run_timeout({"timeout": 1800}) == 1800


def test_job_run_timeout_honours_a_declared_value_above_one_hour() -> None:
    assert scheduler.job_run_timeout({"timeout": 5400}) == 5400


@pytest.mark.parametrize("raw, secs", [
    (None, 900), (30, 30), (5400, 5400), (86400, 86400), (5400.0, 5400), ("5400", 5400), (" 5400 ", 5400),
])
def test_parse_run_timeout_accepts_whole_seconds_in_range(raw, secs) -> None:
    assert scheduler.parse_run_timeout(raw) == secs


@pytest.mark.parametrize("raw", [
    True, False, 29, 0, -5, 86401, 10 ** 40, 5400.5, float("nan"), float("inf"), float("-inf"),
    "5400.5", "nope", "", "\uff15\uff14\uff10\uff10", "9" * 400, [5400], {"s": 5400},
])
def test_parse_run_timeout_refuses_anything_else(raw) -> None:
    with pytest.raises(scheduler.InvalidTimeout):
        scheduler.parse_run_timeout(raw)


def test_a_bad_stored_timeout_is_never_turned_into_a_valid_one() -> None:
    for raw in (10, 99999, "nope", True, float("inf")):
        with pytest.raises(scheduler.InvalidTimeout):
            scheduler.job_run_timeout({"timeout": raw})
    assert scheduler.describe_run_timeout({"timeout": 99999})["run_timeout"] is None
    assert "99999" in scheduler.describe_run_timeout({"timeout": 99999})["timeout_error"]
    assert scheduler.describe_run_timeout({}) == {"run_timeout": 900}


def test_schedule_timeout_schema_matches_runtime_default() -> None:
    desc = Schedule.parameters["properties"]["timeout"]["description"]
    assert f"default {scheduler.DEFAULT_RUN_TIMEOUT_SECONDS}" in desc
    assert str(scheduler.MAX_RUN_TIMEOUT_SECONDS) in desc
    assert "default 600" not in desc


def test_soft_turn_budget_reserves_for_wrap_up() -> None:
    assert scheduler.soft_turn_budget(900) == 810
    assert scheduler.soft_turn_budget(600) == 540
    assert scheduler.soft_turn_budget(1800) == 1620


def test_soft_turn_budget_none_when_no_room() -> None:
    assert scheduler.soft_turn_budget(90) is None
    assert scheduler.soft_turn_budget(30) is None


def test_run_job_passes_soft_budget_to_child(tmp_home_no_env: Path, monkeypatch) -> None:
    import subprocess as _sp

    captured: dict = {}

    def fake_run(cmd, **kwargs):
        captured["env"] = kwargs.get("env", {})
        captured["timeout"] = kwargs.get("timeout")
        return _sp.CompletedProcess(cmd, 0, stdout='{"kind":"reply","text":""}\n', stderr="")

    monkeypatch.setattr(scheduler.subprocess, "run", fake_run)
    scheduler.run_job({"id": "x", "kind": "cron", "prompt": "do a thing"}, tmp_home_no_env)
    assert captured["timeout"] == 900
    assert captured["env"]["ALPI_TURN_BUDGET_S"] == "810"


def test_run_job_enforces_a_timeout_above_one_hour_in_the_agent_path(tmp_home_no_env: Path, monkeypatch) -> None:
    import subprocess as _sp

    captured: dict = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["env"] = kwargs.get("env", {})
        captured["timeout"] = kwargs.get("timeout")
        return _sp.CompletedProcess(cmd, 0, stdout='{"kind":"reply","text":""}\n', stderr="")

    monkeypatch.setattr(scheduler.subprocess, "run", fake_run)
    scheduler.run_job({"id": "x", "kind": "cron", "prompt": "audit the portfolio", "timeout": 5400}, tmp_home_no_env)
    assert captured["timeout"] == 5400
    assert captured["env"]["ALPI_TURN_BUDGET_S"] == "4860"
    assert captured["env"]["ALPI_RUN_TIMEOUT_S"] == "5400"
    assert "about 81 minutes" in " ".join(map(str, captured["cmd"]))


def test_run_job_enforces_a_timeout_above_one_hour_in_the_script_path(tmp_home_no_env: Path, monkeypatch) -> None:
    script = _stub_skill_path(tmp_home_no_env)
    captured: dict = {}

    def fake_run(argv, **kw):
        captured["timeout"] = kw.get("timeout")
        return _fake_completed(rc=0, stdout="")

    monkeypatch.setattr(scheduler.subprocess, "run", fake_run)
    ok, _msg, _reply = scheduler.run_job(
        {"id": "j", "kind": "cron", "no_agent": True, "prompt": f"python3 {script}", "timeout": 5400},
        tmp_home_no_env,
    )
    assert ok and captured["timeout"] == 5400


def test_a_run_past_a_declared_timeout_above_one_hour_is_killed_and_reported(tmp_home_no_env: Path, monkeypatch) -> None:
    import subprocess as _sp

    def fake_run(cmd, **kwargs):
        raise _sp.TimeoutExpired(cmd, kwargs["timeout"])

    monkeypatch.setattr(scheduler.subprocess, "run", fake_run)
    outcome = scheduler.run_job({"id": "j", "kind": "cron", "prompt": "audit", "timeout": 5400}, tmp_home_no_env)
    assert not outcome.ok
    assert outcome.timeout_reason == "timeout_5400s"
    assert outcome.message.startswith("agent timed out after 5400s")


def test_a_script_past_a_declared_timeout_above_one_hour_is_killed_and_reported(tmp_home_no_env: Path, monkeypatch) -> None:
    import subprocess as _sp
    script = _stub_skill_path(tmp_home_no_env)

    def fake_run(argv, **kw):
        raise _sp.TimeoutExpired(argv, kw["timeout"])

    monkeypatch.setattr(scheduler.subprocess, "run", fake_run)
    outcome = scheduler.run_job(
        {"id": "j", "kind": "cron", "no_agent": True, "prompt": f"python3 {script}", "timeout": 5400},
        tmp_home_no_env,
    )
    assert not outcome.ok and outcome.timeout_reason == "timeout_5400s"


def test_an_invalid_timeout_error_does_not_carry_a_huge_stored_value() -> None:
    err = scheduler.describe_run_timeout({"timeout": "x" * 5000})["timeout_error"]
    assert len(err) < 200


@pytest.mark.parametrize("no_agent", [False, True])
def test_run_job_fails_a_bad_stored_timeout_without_spawning(tmp_home_no_env: Path, monkeypatch, no_agent) -> None:
    script = _stub_skill_path(tmp_home_no_env)
    spawned: list = []
    monkeypatch.setattr(scheduler.subprocess, "run", lambda *a, **k: spawned.append(a))
    job = {"id": "j", "kind": "cron", "prompt": f"python3 {script}" if no_agent else "do a thing", "timeout": 99999}
    if no_agent:
        job["no_agent"] = True
    outcome = scheduler.run_job(job, tmp_home_no_env)
    assert not outcome.ok and "invalid stored timeout" in outcome.message
    assert spawned == []


def test_a_bad_stored_timeout_fails_the_fire_through_the_tick(tmp_home_no_env: Path, monkeypatch) -> None:
    jobs_store.update(tmp_home_no_env, lambda _old: [{
        "id": "bad", "kind": "cron", "expression": "* * * * *", "prompt": "do a thing",
        "timeout": True, "last_run_at": "2020-01-01T00:00:00+00:00",
    }])
    monkeypatch.setattr(scheduler.subprocess, "run", lambda *a, **k: pytest.fail("must not spawn"))
    results = scheduler.tick(tmp_home_no_env)
    assert results and results[0][0] == "bad" and not results[0][1]
    assert "invalid stored timeout" in results[0][2]
    stored = jobs_store.read(tmp_home_no_env)[0]
    assert stored["last_run_status"] == "error" and stored["timeout"] is True


def test_run_job_omits_soft_budget_when_timeout_tiny(tmp_home_no_env: Path, monkeypatch) -> None:
    import subprocess as _sp

    captured: dict = {}

    def fake_run(cmd, **kwargs):
        captured["env"] = kwargs.get("env", {})
        return _sp.CompletedProcess(cmd, 0, stdout='{"kind":"reply","text":""}\n', stderr="")

    monkeypatch.setattr(scheduler.subprocess, "run", fake_run)
    scheduler.run_job({"id": "x", "kind": "cron", "prompt": "do a thing", "timeout": 30}, tmp_home_no_env)
    assert "ALPI_TURN_BUDGET_S" not in captured["env"]


def test_cron_tool_add_persists_timeout(tmp_home_no_env: Path) -> None:
    out = Schedule().run(action="add", kind="cron", expression="0 9 * * 4",
                     prompt="weekly research post", timeout=1800)
    assert out.ok
    job = json.loads((tmp_home_no_env / "schedule" / "jobs.json").read_text())[0]
    assert job["timeout"] == 1800


def test_cron_tool_add_rejects_out_of_range_timeout(tmp_home_no_env: Path) -> None:
    out = Schedule().run(action="add", kind="cron", expression="0 9 * * 4",
                     prompt="weekly research post", timeout=99999)
    assert not out.ok
    assert "timeout" in (out.error or "")


def test_cron_tool_add_accepts_and_lists_a_timeout_above_one_hour(tmp_home_no_env: Path) -> None:
    out = Schedule().run(action="add", kind="cron", expression="0 4-15 * * 6,0",
                     prompt="weekend security audit", timeout="5400")
    assert out.ok
    job = json.loads((tmp_home_no_env / "schedule" / "jobs.json").read_text())[0]
    assert job["timeout"] == 5400
    listed = json.loads(Schedule().run(action="list").output)
    assert listed[0]["run_timeout"] == 5400


@pytest.mark.parametrize("bad", [True, 5400.5, 86401, 29])
def test_cron_tool_add_refuses_a_timeout_outside_the_contract(tmp_home_no_env: Path, bad) -> None:
    out = Schedule().run(action="add", kind="cron", expression="0 9 * * 4",
                     prompt="weekly research post", timeout=bad)
    assert not out.ok and "between 30 and 86400" in (out.error or "")
    assert not (tmp_home_no_env / "schedule" / "jobs.json").exists() or \
        json.loads((tmp_home_no_env / "schedule" / "jobs.json").read_text()) == []


def test_cron_tool_list_flags_a_bad_stored_timeout(tmp_home_no_env: Path) -> None:
    jobs_store.update(tmp_home_no_env, lambda _old: [
        {"id": "bad", "kind": "cron", "expression": "0 9 * * *", "prompt": "x", "timeout": 99999},
    ])
    listed = json.loads(Schedule().run(action="list").output)
    assert listed[0]["timeout"] == 99999 and listed[0]["run_timeout"] is None
    assert "between 30 and 86400" in listed[0]["timeout_error"]


def test_cron_tool_update_sets_timeout(tmp_home_no_env: Path) -> None:
    add = Schedule().run(action="add", kind="cron", expression="0 9 * * 4",
                     prompt="weekly research post")
    assert add.ok
    job_id = json.loads((tmp_home_no_env / "schedule" / "jobs.json").read_text())[0]["id"]
    upd = Schedule().run(action="update", id=job_id, timeout=1800)
    assert upd.ok and "timeout" in upd.output
    job = json.loads((tmp_home_no_env / "schedule" / "jobs.json").read_text())[0]
    assert job["timeout"] == 1800


def test_emit_schedule_event_titles_auto_notify_with_job_title(tmp_home_no_env: Path) -> None:
    from alpi import outputs as outputs_mod
    job = {"id": "j1", "kind": "cron", "title": "Salud · recuperación", "notify": True}
    outcome = scheduler.JobOutcome(True, "ok", reply="🟡 Recuperación al 43%", delivered_to="alpi")
    scheduler._emit_schedule_event(tmp_home_no_env, job, outcome)
    outs = outputs_mod.list_outputs(tmp_home_no_env)
    assert any(o.get("title") == "Salud · recuperación" for o in outs)


def test_emit_schedule_event_untitled_job_files_no_title(tmp_home_no_env: Path) -> None:
    from alpi import outputs as outputs_mod
    job = {"id": "j2", "kind": "cron", "notify": True}
    outcome = scheduler.JobOutcome(True, "ok", reply="algo pasó", delivered_to="alpi")
    scheduler._emit_schedule_event(tmp_home_no_env, job, outcome)
    outs = outputs_mod.list_outputs(tmp_home_no_env)
    assert outs and "title" not in outs[0]


def test_workspace_env_present_when_workspace_set(tmp_home_no_env: Path) -> None:
    from alpi.home import workspace_env
    ws = tmp_home_no_env / "ws"
    (tmp_home_no_env / "config.yaml").write_text(f"workspace: {ws}\n")
    assert workspace_env(tmp_home_no_env) == {"ALPI_WORKSPACE": str(ws.resolve())}


def test_workspace_env_omitted_when_workspace_unset(tmp_home_no_env: Path) -> None:
    from alpi.home import workspace_env
    assert workspace_env(tmp_home_no_env) == {}


def test_no_agent_env_carries_alpi_workspace(monkeypatch, tmp_home_no_env: Path) -> None:
    ws = tmp_home_no_env / "ws"
    (tmp_home_no_env / "config.yaml").write_text(f"workspace: {ws}\n")
    script = _stub_skill_path(tmp_home_no_env)
    captured = {}

    def fake_run(*a, **kw):
        captured["env"] = kw.get("env") or {}
        return _fake_completed(rc=0, stdout="ok\n")

    monkeypatch.setattr(scheduler.subprocess, "run", fake_run)
    job = {"id": "j", "kind": "cron", "no_agent": True,
           "prompt": f"python3 {script}", "notify": True}
    scheduler.run_job(job, tmp_home_no_env)
    assert captured["env"].get("ALPI_WORKSPACE") == str(ws.resolve())


def test_emit_schedule_event_push_uses_job_title_and_clean_body(tmp_home_no_env: Path, monkeypatch) -> None:
    from alpi.host import events as host_events
    calls = []
    monkeypatch.setattr(host_events, "emit", lambda kind, payload: calls.append((kind, payload)))
    job = {"id": "j3", "kind": "cron", "title": "Salud · recuperación", "notify": True}
    outcome = scheduler.JobOutcome(True, "ok", reply="✅ Recuperación al 43%", delivered_to="alpi")
    scheduler._emit_schedule_event(tmp_home_no_env, job, outcome)
    msg = next(p for (k, p) in calls if k == "agent.message")
    assert msg["title"] == "Salud · recuperación"
    assert "✅" not in msg["body"] and "Recuperación al 43%" in msg["body"]


def test_cron_tool_add_with_tier_persists_it(tmp_home_no_env: Path) -> None:
    out = Schedule().run(action="add", kind="cron", expression="0 4 * * *",
                         prompt="nightly digest", tier="fast")
    assert out.ok
    data = json.loads((tmp_home_no_env / "schedule" / "jobs.json").read_text())
    assert data[0]["tier"] == "fast"


def test_cron_tool_add_default_has_no_tier(tmp_home_no_env: Path) -> None:
    out = Schedule().run(action="add", kind="cron", expression="0 4 * * *",
                         prompt="nightly digest")
    assert out.ok
    data = json.loads((tmp_home_no_env / "schedule" / "jobs.json").read_text())
    assert "tier" not in data[0]


def test_cron_tool_add_rejects_unknown_tier(tmp_home_no_env: Path) -> None:
    out = Schedule().run(action="add", kind="cron", expression="0 4 * * *",
                         prompt="nightly digest", tier="turbo")
    assert not out.ok
    assert "tier" in out.error


def test_cron_tool_update_tier_main_removes_it(tmp_home_no_env: Path) -> None:
    Schedule().run(action="add", kind="cron", expression="0 4 * * *",
                   prompt="nightly digest", tier="deep")
    data = json.loads((tmp_home_no_env / "schedule" / "jobs.json").read_text())
    job_id = data[0]["id"]
    out = Schedule().run(action="update", id=job_id, tier="main")
    assert out.ok and "tier" in out.output
    data = json.loads((tmp_home_no_env / "schedule" / "jobs.json").read_text())
    assert "tier" not in data[0]


def test_run_job_passes_tier_to_child_env(tmp_home_no_env: Path, monkeypatch) -> None:
    captured: dict = {}

    def fake_run(argv, env=None, **kw):
        captured["env"] = env or {}
        return _fake_completed(rc=0, stdout="")

    monkeypatch.setattr(scheduler.subprocess, "run", fake_run)
    scheduler.run_job({"id": "jt", "kind": "cron", "prompt": "go", "tier": "fast"},
                      tmp_home_no_env)
    assert captured["env"]["ALPI_TIER"] == "fast"

    scheduler.run_job({"id": "jt2", "kind": "cron", "prompt": "go"}, tmp_home_no_env)
    assert "ALPI_TIER" not in captured["env"]


def test_run_job_accounts_to_host_even_for_connection_created_jobs(
        monkeypatch, tmp_home_no_env: Path) -> None:
    captured = {}

    class _FakeCompletedProcess:
        returncode = 0
        stdout = _events_stdout([{"kind": "reply", "text": "done"}])
        stderr = ""

    def fake_run(*a, **kw):
        captured["env"] = kw.get("env") or {}
        return _FakeCompletedProcess()

    monkeypatch.setattr(scheduler.subprocess, "run", fake_run)
    job = {"id": "j", "kind": "cron", "prompt": "p", "connection_id": "conn_javi"}
    assert scheduler.run_job(job, tmp_home_no_env).ok
    assert captured["env"].get("ALPI_CONNECTION_ID") == "host"
    assert captured["env"].get("ALPI_CONNECTION_SOURCE") == "schedule"


def _capture_child_env(monkeypatch, tmp_home_no_env, job: dict) -> dict:
    captured: dict = {}

    class _Done:
        returncode = 0
        stdout = _events_stdout([{"kind": "reply", "text": "ok"}])
        stderr = ""

    def fake_run(*a, **kw):
        captured["env"] = kw.get("env") or {}
        return _Done()

    monkeypatch.setattr(scheduler.subprocess, "run", fake_run)
    scheduler.run_job(job, tmp_home_no_env)
    return captured["env"]


def test_a_job_in_docker_carries_the_runtime_past_the_cron_marker(
    monkeypatch, tmp_home_no_env,
) -> None:
    monkeypatch.setenv("ALPI_PLATFORM", "docker")
    monkeypatch.delenv("ALPI_DEPLOY_RUNTIME", raising=False)

    env = _capture_child_env(
        monkeypatch, tmp_home_no_env, {"id": "j", "kind": "cron", "prompt": "p"},
    )

    # The child must still read as Docker even though its ALPI_PLATFORM says cron.
    assert env.get("ALPI_PLATFORM") == "cron"
    assert env.get("ALPI_DEPLOY_RUNTIME") == "docker"


def test_a_job_on_a_host_install_carries_no_runtime(monkeypatch, tmp_home_no_env) -> None:
    monkeypatch.delenv("ALPI_PLATFORM", raising=False)
    monkeypatch.delenv("ALPI_DEPLOY_RUNTIME", raising=False)

    env = _capture_child_env(
        monkeypatch, tmp_home_no_env, {"id": "j", "kind": "cron", "prompt": "p"},
    )

    assert "ALPI_DEPLOY_RUNTIME" not in env


def test_a_script_only_job_in_docker_carries_the_runtime_too(
    monkeypatch, tmp_home_no_env: Path,
) -> None:
    script = _stub_skill_path(tmp_home_no_env)
    monkeypatch.setenv("ALPI_PLATFORM", "docker")
    monkeypatch.delenv("ALPI_DEPLOY_RUNTIME", raising=False)
    captured: dict = {}

    def fake_run(argv, **kw):
        captured["env"] = kw.get("env") or {}
        return _fake_completed(rc=0, stdout="")

    monkeypatch.setattr(scheduler.subprocess, "run", fake_run)
    scheduler.run_job(
        {"id": "j", "kind": "cron", "no_agent": True, "prompt": f"python3 {script}"},
        tmp_home_no_env,
    )

    assert captured["env"].get("ALPI_PLATFORM") == "cron"
    assert captured["env"].get("ALPI_DEPLOY_RUNTIME") == "docker"


def _journal_of_a_busy_run(home: Path, run_id: str, now: float) -> None:
    from alpi import runs

    def ev(seq, at, kind, data):
        return json.dumps({"version": 1, "seq": seq, "at": at, "kind": kind, "data": data})

    path = runs.run_path(home, run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join([
        ev(0, now - 1700, "run.started", {"run_id": run_id, "profile": "p", "pid": 999_999, "pid_start": "0"}),
        ev(1, now - 1690, "agent.tool_start", {"name": "skill", "tool_id": "a", "args": {"action": "run", "name": "repo-intelligence", "args": ["discover"]}}),
        ev(2, now - 1600, "agent.tool_end", {"name": "skill", "tool_id": "a"}),
        ev(3, now - 900, "agent.tool_start", {"name": "bitbucket__getPullRequest", "tool_id": "b", "args": {"id": 7}}),
        ev(4, now - 880, "agent.tool_end", {"name": "bitbucket__getPullRequest", "tool_id": "b"}),
        ev(5, now - 200, "agent.assistant_done", {"text": "Coverage is clean. Running the final reconcile.\nNext step."}),
        ev(6, now - 190, "agent.tool_start", {"name": "skill", "tool_id": "c", "args": {"action": "run", "name": "repo-intelligence", "args": ["reconcile-verdicts"]}}),
    ]) + "\n")


def test_a_timed_out_run_reports_what_it_was_doing(tmp_home_no_env: Path, monkeypatch) -> None:
    import subprocess as _sp
    import time as _time

    from alpi import runs

    captured: dict = {}

    def fake_run(cmd, **kwargs):
        captured["run_id"] = kwargs["env"]["ALPI_RUN_ID"]
        _journal_of_a_busy_run(tmp_home_no_env, captured["run_id"], _time.time())
        raise _sp.TimeoutExpired(cmd, 1700)

    monkeypatch.setattr(scheduler.subprocess, "run", fake_run)
    outcome = scheduler.run_job({"id": "j1", "kind": "cron", "prompt": "scan", "timeout": 1700}, tmp_home_no_env)

    assert not outcome.ok
    assert outcome.timeout_reason == "timeout_1700s"
    assert outcome.run_id == captured["run_id"]
    assert outcome.last_tool == "skill"
    assert outcome.tool_count == 3
    assert outcome.message.startswith("agent timed out after 1700s — 3 tool calls made; last message: 'Coverage is clean.")
    assert "Next step.'; killed 3m1" in outcome.message
    assert outcome.message.endswith("reconcile-verdicts\"]}") and "`skill` " in outcome.message
    assert runs.summary(tmp_home_no_env, captured["run_id"])["status"] == "interrupted"


def test_the_ledger_row_of_a_timed_out_run_names_its_run_and_tool(tmp_home_no_env: Path) -> None:
    from alpi import run_ledger

    outcome = scheduler.JobOutcome(
        False, "agent timed out after 1700s — 3 tool calls made", timeout_reason="timeout_1700s",
        run_id="run-1", last_tool="skill", tool_count=3,
    )
    scheduler._record_schedule_run(tmp_home_no_env, {"id": "j1"}, outcome, started=1.0, elapsed=1700.0)

    rows = [json.loads(line) for line in (tmp_home_no_env / "logs" / "runs.jsonl").read_text().splitlines()]
    row = rows[-1]
    assert row["outcome"] == "timeout"
    assert row["run_id"] == "run-1"
    assert row["last_tool"] == "skill"
    assert row["tool_count"] == 3
    assert run_ledger  # the module wrote the row above


def test_a_run_killed_between_steps_names_no_tool_in_flight(tmp_home_no_env: Path) -> None:
    import time as _time

    from alpi import runs

    now = _time.time()
    path = runs.run_path(tmp_home_no_env, "between-steps")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(e) for e in [
        {"version": 1, "seq": 0, "at": now - 900, "kind": "run.started", "data": {"run_id": "between-steps", "pid": 999_999}},
        {"version": 1, "seq": 1, "at": now - 800, "kind": "agent.tool_start", "data": {"name": "skill", "tool_id": "a", "args": {}}},
        {"version": 1, "seq": 2, "at": now - 700, "kind": "agent.tool_end", "data": {"name": "skill", "tool_id": "a"}},
        {"version": 1, "seq": 3, "at": now - 10, "kind": "run.finished", "data": {"outcome": "interrupted"}},
    ]) + "\n")

    message, last_tool, tool_count = scheduler._timeout_detail(tmp_home_no_env, "between-steps", 900)

    assert message == "agent timed out after 900s — 1 tool calls made"
    assert last_tool is None
    assert tool_count == 1


@pytest.mark.parametrize("journal", [
    "[]\n",
    '{"version": 1, "seq": 0, "at": "bad", "kind": "run.started", "data": {}}\n',
    '{"version": 1, "seq": 0, "at": 1.0, "kind": "agent.tool_start", "data": [1]}\n',
    '{"version": 1, "seq": 0, "at": 1.0, "kind": "agent.assistant_done", "data": {"text": 7}}\n',
    "null\n42\n",
])
def test_a_damaged_journal_never_turns_the_timeout_into_another_error(tmp_home_no_env: Path, journal: str) -> None:
    from alpi import runs

    path = runs.run_path(tmp_home_no_env, "damaged")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(journal)

    message, last_tool, tool_count = scheduler._timeout_detail(tmp_home_no_env, "damaged", 60)

    assert message.startswith("agent timed out after 60s")
    assert last_tool is None


def test_damaged_lines_are_skipped_without_losing_the_rest_of_the_diagnosis(tmp_home_no_env: Path) -> None:
    import time as _time

    from alpi import runs

    now = _time.time()
    path = runs.run_path(tmp_home_no_env, "partly-damaged")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join([
        json.dumps({"version": 1, "seq": 0, "at": now - 300, "kind": "run.started", "data": {"run_id": "partly-damaged"}}),
        json.dumps({"version": 1, "seq": 1, "at": now - 120, "kind": "agent.tool_start", "data": {"name": "skill", "tool_id": "a", "args": {"action": "run"}}}),
        "[]",
        "null",
        json.dumps({"version": 1, "seq": 2, "at": now, "kind": "run.finished", "data": {"outcome": "interrupted"}}),
    ]) + "\n")

    message, last_tool, tool_count = scheduler._timeout_detail(tmp_home_no_env, "partly-damaged", 300)

    assert "1 tool calls made; killed 2m00s into `skill`" in message
    assert (last_tool, tool_count) == ("skill", 1)


def test_a_damaged_journal_still_yields_the_timeout_outcome_end_to_end(tmp_home_no_env: Path, monkeypatch) -> None:
    import subprocess as _sp

    from alpi import runs

    def fake_run(cmd, **kwargs):
        path = runs.run_path(tmp_home_no_env, kwargs["env"]["ALPI_RUN_ID"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"version": 1, "seq": 0, "at": "bad", "kind": "run.started", "data": [1]}\n[]\n')
        raise _sp.TimeoutExpired(cmd, 60)

    monkeypatch.setattr(scheduler.subprocess, "run", fake_run)
    outcome = scheduler.run_job({"id": "j2", "kind": "cron", "prompt": "scan", "timeout": 60}, tmp_home_no_env)

    assert not outcome.ok
    assert outcome.timeout_reason == "timeout_60s"
    assert outcome.message.startswith("agent timed out after 60s")
    assert outcome.run_id


def test_the_ledger_tail_of_a_long_timeout_message_keeps_the_in_flight_step(tmp_home_no_env: Path) -> None:
    import time as _time

    from alpi import runs

    now = _time.time()
    path = runs.run_path(tmp_home_no_env, "long-tail")
    path.parent.mkdir(parents=True, exist_ok=True)
    args = {"action": "run", "name": "repo-intelligence", "args": ["reconcile-verdicts", "engine-payments", "very-long-argument-value"]}
    path.write_text("\n".join(json.dumps(e) for e in [
        {"version": 1, "seq": 0, "at": now - 1700, "kind": "run.started", "data": {"run_id": "long-tail", "pid": 999_999}},
        {"version": 1, "seq": 1, "at": now - 400, "kind": "agent.assistant_done", "data": {"text": "x" * 200}},
        {"version": 1, "seq": 2, "at": now - 190, "kind": "agent.tool_start", "data": {"name": "skill", "tool_id": "c", "args": args}},
        {"version": 1, "seq": 3, "at": now, "kind": "run.finished", "data": {"outcome": "interrupted"}},
    ]) + "\n")
    message, last_tool, tool_count = scheduler._timeout_detail(tmp_home_no_env, "long-tail", 1700)
    assert len(message) > 356
    outcome = scheduler.JobOutcome(False, message, timeout_reason="timeout_1700s", run_id="long-tail", last_tool=last_tool, tool_count=tool_count)

    scheduler._record_schedule_run(tmp_home_no_env, {"id": "j1"}, outcome, started=now - 1700, elapsed=1700.0)

    row = json.loads((tmp_home_no_env / "logs" / "runs.jsonl").read_text().splitlines()[-1])
    assert "killed 3m10s into `skill`" in row["output_tail"]
    assert row["last_tool"] == "skill"


def test_a_truncated_tool_end_still_closes_its_tool_start(tmp_home_no_env: Path) -> None:
    from alpi import runs

    run_id = "big-tool"
    runs.append(tmp_home_no_env, run_id, "run.started", {"run_id": run_id, "pid": 999_999})
    runs.append(tmp_home_no_env, run_id, "agent.tool_start", {"name": "edit_file", "tool_id": "e1", "args": {"path": "a.py", "old": "x" * 11_000, "new": "y" * 11_000}})
    ended = runs.append(tmp_home_no_env, run_id, "agent.tool_end", {"name": "edit_file", "tool_id": "e1", "args": {"path": "a.py", "old": "x" * 11_000, "new": "y" * 11_000}, "output": "z" * 12_000})
    runs.append(tmp_home_no_env, run_id, "run.finished", {"outcome": "interrupted"})

    assert ended["data"]["truncated"] is True
    assert ended["data"]["tool_id"] == "e1" and ended["data"]["name"] == "edit_file"
    message, last_tool, tool_count = scheduler._timeout_detail(tmp_home_no_env, run_id, 900)
    assert "into `" not in message
    assert (last_tool, tool_count) == (None, 1)


def test_a_timed_out_run_without_a_journal_still_reports_the_timeout(tmp_home_no_env: Path) -> None:
    assert scheduler._timeout_detail(tmp_home_no_env, "no-such-run", 60) == ("agent timed out after 60s", None, None)


def test_a_finished_run_carries_its_run_id(tmp_home_no_env: Path, monkeypatch) -> None:
    import subprocess as _sp

    captured: dict = {}

    def fake_run(cmd, **kwargs):
        captured["run_id"] = kwargs["env"]["ALPI_RUN_ID"]
        return _sp.CompletedProcess(cmd, 0, stdout='{"kind":"reply","text":"all good"}\n', stderr="")

    monkeypatch.setattr(scheduler.subprocess, "run", fake_run)
    outcome = scheduler.run_job({"id": "x", "kind": "cron", "prompt": "do a thing"}, tmp_home_no_env)

    assert outcome.ok
    assert outcome.run_id == captured["run_id"]


def test_the_scheduled_prompt_states_its_time_budget(tmp_home_no_env: Path, monkeypatch) -> None:
    import subprocess as _sp

    prompts: list[str] = []

    def fake_run(cmd, **kwargs):
        prompts.append(cmd[cmd.index("--once") + 1])
        return _sp.CompletedProcess(cmd, 0, stdout='{"kind":"reply","text":""}\n', stderr="")

    monkeypatch.setattr(scheduler.subprocess, "run", fake_run)
    scheduler.run_job({"id": "x", "kind": "cron", "prompt": "do a thing", "timeout": 1700}, tmp_home_no_env)
    scheduler.run_job({"id": "y", "kind": "cron", "prompt": "do a thing", "timeout": 30}, tmp_home_no_env)

    assert "This run has about 25 minutes before it is stopped" in prompts[0]
    assert "before it is stopped" not in prompts[1]


def test_emit_schedule_event_files_the_job_and_run_behind_every_row(tmp_home_no_env: Path) -> None:
    from alpi import outputs as outputs_mod
    ok = scheduler.JobOutcome(True, "ok", reply="digest", delivered_to="alpi", run_id="r" * 32)
    scheduler._emit_schedule_event(tmp_home_no_env, {"id": "daily", "kind": "cron", "title": "Daily", "notify": True}, ok)
    failed = scheduler.JobOutcome(False, "boom", run_id="f" * 32)
    scheduler._emit_schedule_event(tmp_home_no_env, {"id": "weekly", "kind": "cron", "title": "Weekly"}, failed)
    rows = {o["job_id"]: o for o in outputs_mod.list_outputs(tmp_home_no_env)}
    assert rows["daily"]["run_id"] == "r" * 32 and rows["daily"]["type"] == "info"
    assert rows["weekly"]["run_id"] == "f" * 32 and rows["weekly"]["type"] == "error"


def test_a_child_notification_carries_the_job_and_run_that_sent_it(tmp_home_no_env: Path) -> None:
    from alpi import outputs as outputs_mod
    scheduler._emit_agent_messages(tmp_home_no_env, [{"text": "done", "title": "Labs"}], job_id="labs", run_id="a" * 32)
    rows = outputs_mod.list_outputs(tmp_home_no_env)
    assert rows and rows[0]["job_id"] == "labs" and rows[0]["run_id"] == "a" * 32


def test_run_job_files_a_child_notification_with_its_job_and_run(monkeypatch, tmp_home_no_env: Path) -> None:
    from alpi import outputs as outputs_mod

    class _Done:
        returncode = 0
        stdout = _events_stdout([
            {"kind": "tool_start", "name": "notify", "preview": "labs", "args": {"text": "labs are in", "title": "Labs"}},
            {"kind": "tool_end", "name": "notify", "ok": True},
            {"kind": "reply", "text": "done"},
        ])
        stderr = ""

    monkeypatch.setattr(scheduler.subprocess, "run", lambda *a, **kw: _Done())
    outcome = scheduler.run_job({"id": "labs", "kind": "cron", "prompt": "p", "notify": True}, tmp_home_no_env)
    rows = outputs_mod.list_outputs(tmp_home_no_env)
    assert rows and rows[0]["job_id"] == "labs" and rows[0]["run_id"] == outcome.run_id


def test_a_failure_reads_as_a_failure_with_its_trace_folded(tmp_home_no_env: Path) -> None:
    from alpi import outputs as outputs_mod
    outcome = scheduler.JobOutcome(False, "agent rc=1: crashed\nTraceback (most recent call last):\n  boom", exit_code=1, timeout_reason=None)
    scheduler._emit_schedule_event(tmp_home_no_env, {"id": "nightly", "kind": "cron", "title": "Nightly sync"}, outcome)
    row = outputs_mod.list_outputs(tmp_home_no_env)[0]
    assert row["title"] == "Nightly sync failed"
    assert row["body"].startswith("**Reason:** boom\n**Exit:** 1")
    assert "```text\nTraceback (most recent call last):\n  boom\n```" in row["body"]


def test_a_failure_body_stays_under_its_cap_and_closes_its_fence() -> None:
    body = scheduler.failure_body(scheduler.JobOutcome(False, "x\n" + "line\n" * 2000, timeout_reason="wall clock 600s"))
    assert len(body) <= scheduler.FAILURE_BODY_CAP and body.endswith("```") and "**Timeout:** wall clock 600s" in body
    long_reason = scheduler.failure_body(scheduler.JobOutcome(False, "r" * 1990 + "\ntrace"))
    assert len(long_reason) <= scheduler.FAILURE_BODY_CAP and long_reason.count("```") in (0, 2)


def test_a_stored_trace_keeps_its_indentation_and_symbols() -> None:
    from alpi import outputs as outputs_mod
    body = outputs_mod.normalize_notification_body("**Reason:** boom\n\n```text\n  File \"x.py\", line 3, in <module>\n    # x\n---\n[a](u)\n```\n## Next")
    assert '  File "x.py", line 3, in <module>\n    # x\n---\n[a](u)' in body
    assert body.endswith("## Next")


def test_a_notified_reply_is_archived_whole_or_says_where_it_was_cut(tmp_home_no_env: Path) -> None:
    from alpi import outputs as outputs_mod
    long_digest = "\n".join(f"- **Sender {i}** a{i}@example.com — subject number {i}" for i in range(120))
    assert 2000 < len(long_digest) < scheduler.REPLY_BODY_CAP
    scheduler._emit_schedule_event(tmp_home_no_env, {"id": "mail", "kind": "cron", "title": "Mail", "notify": True},
                                   scheduler.JobOutcome(True, "ok", reply=long_digest, delivered_to="alpi"))
    assert outputs_mod.list_outputs(tmp_home_no_env)[0]["body"].endswith("subject number 119")
    huge = "x" * (scheduler.REPLY_BODY_CAP + 500)
    body = outputs_mod.normalize_notification_body(scheduler.reply_body(huge))
    assert body.startswith("x" * 100) and body.endswith(f"*Cut at 8,000 of {len(huge):,} characters.*")


def test_a_reply_cut_inside_a_code_block_closes_it_before_saying_where_it_was_cut() -> None:
    from alpi import outputs as outputs_mod
    reply = "Report\n\n```text\n" + "line\n" * 3000 + "```\nAfter"
    body = outputs_mod.normalize_notification_body(scheduler.reply_body(reply))
    assert body.count("```") == 2
    note = f"*Cut at 8,000 of {len(reply):,} characters.*"
    assert body.endswith(note) and body.rindex("```") < body.index(note)


def _cron(job_id: str, **extra) -> dict:
    return {"id": job_id, "kind": "cron", "expression": "* * * * *", "prompt": job_id, "last_run_at": _PAST, **extra}


def _fired_by_tick(monkeypatch) -> list[tuple[str, str]]:
    fired: list[tuple[str, str]] = []
    monkeypatch.setattr(
        scheduler, "run_job",
        lambda job, home: (fired.append((job["id"], job["prompt"])) or scheduler.JobOutcome(True, "ok")),
    )
    return fired


def test_a_job_removed_during_an_earlier_run_does_not_fire(monkeypatch, tmp_home_no_env: Path) -> None:
    scheduler._save_jobs(tmp_home_no_env, [_cron("first"), _cron("second")])
    fired: list[str] = []

    def run(job, home):
        fired.append(job["id"])
        if job["id"] == "first":
            jobs_store.update(home, lambda jobs: [j for j in jobs if j["id"] != "second"])
        return scheduler.JobOutcome(True, "ok")

    monkeypatch.setattr(scheduler, "run_job", run)

    assert scheduler.tick(tmp_home_no_env) == [("first", True, "ok")]
    assert fired == ["first"]
    assert [j["id"] for j in jobs_store.read(tmp_home_no_env)] == ["first"]


def test_a_job_paused_during_an_earlier_run_does_not_fire(monkeypatch, tmp_home_no_env: Path) -> None:
    scheduler._save_jobs(tmp_home_no_env, [_cron("first"), _cron("second")])
    fired: list[str] = []

    def run(job, home):
        fired.append(job["id"])
        if job["id"] == "first":
            def pause(jobs):
                for j in jobs:
                    if j["id"] == "second":
                        j["paused"] = True
                return jobs
            jobs_store.update(home, pause)
        return scheduler.JobOutcome(True, "ok")

    monkeypatch.setattr(scheduler, "run_job", run)

    scheduler.tick(tmp_home_no_env)

    assert fired == ["first"]


def test_a_job_edited_during_an_earlier_run_fires_with_its_new_prompt(monkeypatch, tmp_home_no_env: Path) -> None:
    scheduler._save_jobs(tmp_home_no_env, [_cron("first"), _cron("second")])
    fired: list[tuple[str, str]] = []

    def run(job, home):
        fired.append((job["id"], job["prompt"]))
        if job["id"] == "first":
            def edit(jobs):
                for j in jobs:
                    if j["id"] == "second":
                        j["prompt"] = "edited"
                return jobs
            jobs_store.update(home, edit)
        return scheduler.JobOutcome(True, "ok")

    monkeypatch.setattr(scheduler, "run_job", run)

    scheduler.tick(tmp_home_no_env)

    assert fired == [("first", "first"), ("second", "edited")]


def test_a_job_fired_by_hand_during_an_earlier_run_is_not_fired_again(monkeypatch, tmp_home_no_env: Path) -> None:
    scheduler._save_jobs(tmp_home_no_env, [_cron("first"), _cron("second")])
    fired: list[str] = []

    def run(job, home):
        fired.append(job["id"])
        if job["id"] == "first":
            def stamp(jobs):
                for j in jobs:
                    if j["id"] == "second":
                        j["last_run_at"] = datetime.now(timezone.utc).isoformat()
                return jobs
            jobs_store.update(home, stamp)
        return scheduler.JobOutcome(True, "ok")

    monkeypatch.setattr(scheduler, "run_job", run)

    scheduler.tick(tmp_home_no_env)

    assert fired == ["first"]


def test_a_successful_rerun_by_hand_is_stamped_ok_before_the_event_goes_out(monkeypatch, tmp_home_no_env: Path) -> None:
    scheduler._save_jobs(tmp_home_no_env, [_cron("abc123", last_run_status="error")])
    monkeypatch.setattr(scheduler, "run_job", lambda job, home: scheduler.JobOutcome(True, "ok"))
    seen_at_emit: list[str] = []
    monkeypatch.setattr(
        scheduler, "_emit_schedule_event",
        lambda home, job, outcome: seen_at_emit.append(jobs_store.read(home)[0]["last_run_status"]),
    )

    ok, _message = scheduler.fire_by_id(tmp_home_no_env, "abc123")

    assert ok
    assert seen_at_emit == ["ok"]


def test_a_failing_due_check_skips_that_job_and_the_pass_goes_on(monkeypatch, tmp_home_no_env: Path) -> None:
    broken = {"id": "broken", "kind": "inactivity", "after_hours": "soon", "prompt": "broken"}
    scheduler._save_jobs(tmp_home_no_env, [broken, _cron("healthy")])
    fired = _fired_by_tick(monkeypatch)

    results = scheduler.tick(tmp_home_no_env)

    assert results == [("healthy", True, "ok")]
    assert fired == [("healthy", "healthy")]


def test_a_stamp_that_fails_is_retried_next_tick_without_firing_the_job_again(monkeypatch, tmp_home_no_env: Path) -> None:
    scheduler._save_jobs(tmp_home_no_env, [_cron("abc123")])
    fired = _fired_by_tick(monkeypatch)
    real_update = jobs_store.update
    state = {"fail": True}

    def flaky(home, mutator):
        if state["fail"]:
            raise OSError("disk full")
        return real_update(home, mutator)

    monkeypatch.setattr(jobs_store, "update", flaky)
    assert scheduler.tick(tmp_home_no_env) == [("abc123", True, "ok")]
    assert jobs_store.read(tmp_home_no_env)[0]["last_run_at"] == _PAST

    state["fail"] = False
    assert scheduler.tick(tmp_home_no_env) == []

    assert fired == [("abc123", "abc123")]
    merged = jobs_store.read(tmp_home_no_env)[0]
    assert merged["last_run_at"] != _PAST
    assert merged["last_run_status"] == "ok"


def test_a_stamp_that_keeps_failing_never_fires_the_job_twice(monkeypatch, tmp_home_no_env: Path) -> None:
    scheduler._save_jobs(tmp_home_no_env, [_cron("abc123")])
    fired = _fired_by_tick(monkeypatch)

    def broken(home, mutator):
        raise OSError("disk full")

    monkeypatch.setattr(jobs_store, "update", broken)

    for _ in range(3):
        scheduler.tick(tmp_home_no_env)

    assert fired == [("abc123", "abc123")]


def test_a_one_shot_whose_stamp_fails_is_not_run_again_and_is_removed_on_recovery(monkeypatch, tmp_home_no_env: Path) -> None:
    once = {"id": "once1", "kind": "once", "run_at": _PAST, "prompt": "once1"}
    scheduler._save_jobs(tmp_home_no_env, [once])
    fired = _fired_by_tick(monkeypatch)
    real_update = jobs_store.update
    state = {"fail": True}

    def flaky(home, mutator):
        if state["fail"]:
            raise OSError("disk full")
        return real_update(home, mutator)

    monkeypatch.setattr(jobs_store, "update", flaky)
    scheduler.tick(tmp_home_no_env)
    scheduler.tick(tmp_home_no_env)
    state["fail"] = False
    scheduler.tick(tmp_home_no_env)

    assert fired == [("once1", "once1")]
    assert jobs_store.read(tmp_home_no_env) == []


def test_a_pending_stamp_never_overwrites_a_newer_one_on_disk(monkeypatch, tmp_home_no_env: Path) -> None:
    scheduler._save_jobs(tmp_home_no_env, [_cron("abc123")])
    _fired_by_tick(monkeypatch)
    real_update = jobs_store.update
    state = {"fail": True}

    def flaky(home, mutator):
        if state["fail"]:
            raise OSError("disk full")
        return real_update(home, mutator)

    monkeypatch.setattr(jobs_store, "update", flaky)
    scheduler.tick(tmp_home_no_env)
    state["fail"] = False
    newer = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()

    def by_hand(jobs):
        jobs[0]["last_run_at"] = newer
        return jobs

    real_update(tmp_home_no_env, by_hand)
    scheduler.tick(tmp_home_no_env)

    assert jobs_store.read(tmp_home_no_env)[0]["last_run_at"] == newer


def test_an_unreadable_jobs_file_mid_pass_ends_the_pass_instead_of_raising(monkeypatch, tmp_home_no_env: Path) -> None:
    scheduler._save_jobs(tmp_home_no_env, [_cron("first"), _cron("second")])
    fired = _fired_by_tick(monkeypatch)
    real_read = jobs_store.read
    calls = {"n": 0}

    def flaky(home):
        calls["n"] += 1
        if calls["n"] > 1:
            raise PermissionError("denied")
        return real_read(home)

    monkeypatch.setattr(jobs_store, "read", flaky)

    assert scheduler.tick(tmp_home_no_env) == []
    assert fired == []


def test_a_hand_fire_whose_stamp_fails_still_reports_and_emits(monkeypatch, tmp_home_no_env: Path) -> None:
    scheduler._save_jobs(tmp_home_no_env, [_cron("abc123")])
    monkeypatch.setattr(scheduler, "run_job", lambda job, home: scheduler.JobOutcome(True, "ok"))
    emitted: list[bool] = []
    monkeypatch.setattr(scheduler, "_emit_schedule_event", lambda home, job, outcome: emitted.append(outcome.ok))

    def broken(home, mutator):
        raise OSError("disk full")

    monkeypatch.setattr(jobs_store, "update", broken)

    assert scheduler.fire_by_id(tmp_home_no_env, "abc123") == (True, "ok")
    assert emitted == [True]


def test_older_compares_naive_and_aware_stamps_as_local_time() -> None:
    aware = datetime(2026, 10, 7, 12, 0, tzinfo=timezone.utc).isoformat()
    later_naive = (datetime(2026, 10, 7, 12, 0, tzinfo=timezone.utc).astimezone() + timedelta(hours=1)).replace(tzinfo=None).isoformat()
    earlier_naive = (datetime(2026, 10, 7, 12, 0, tzinfo=timezone.utc).astimezone() - timedelta(hours=1)).replace(tzinfo=None).isoformat()

    assert scheduler._older(earlier_naive, aware) is True
    assert scheduler._older(later_naive, aware) is False
    assert scheduler._older(None, aware) is True
    assert scheduler._older("garbage", aware) is True


def test_a_pending_one_shot_stamp_never_deletes_the_job_that_replaced_it(monkeypatch, tmp_home_no_env: Path) -> None:
    once = {"id": "swap1", "kind": "once", "run_at": _PAST, "prompt": "once"}
    scheduler._save_jobs(tmp_home_no_env, [once])
    fired = _fired_by_tick(monkeypatch)
    real_update = jobs_store.update
    state = {"fail": True}

    def flaky(home, mutator):
        if state["fail"]:
            raise OSError("disk full")
        return real_update(home, mutator)

    monkeypatch.setattr(jobs_store, "update", flaky)
    scheduler.tick(tmp_home_no_env)

    def to_cron(jobs):
        return [{**j, "kind": "cron", "expression": "0 0 1 1 *", "last_run_at": datetime.now(timezone.utc).isoformat()} for j in jobs if j["id"] == "swap1"]

    real_update(tmp_home_no_env, to_cron)
    state["fail"] = False
    scheduler.tick(tmp_home_no_env)
    scheduler.tick(tmp_home_no_env)

    kept = jobs_store.read(tmp_home_no_env)
    assert [(j["id"], j["kind"]) for j in kept] == [("swap1", "cron")]
    assert kept[0].get("last_run_status") is None
    assert fired == [("swap1", "once")]


def test_a_pending_one_shot_stamp_does_not_hide_the_replacement_from_the_pass(monkeypatch, tmp_home_no_env: Path) -> None:
    once = {"id": "swap2", "kind": "once", "run_at": _PAST, "prompt": "once"}
    scheduler._save_jobs(tmp_home_no_env, [once])
    fired = _fired_by_tick(monkeypatch)
    real_update = jobs_store.update
    state = {"fail": True}

    def flaky(home, mutator):
        if state["fail"]:
            raise OSError("disk full")
        return real_update(home, mutator)

    monkeypatch.setattr(jobs_store, "update", flaky)
    scheduler.tick(tmp_home_no_env)

    real_update(tmp_home_no_env, lambda jobs: [{**j, "kind": "cron", "expression": "* * * * *", "last_run_at": _PAST, "prompt": "cron"} for j in jobs])
    scheduler.tick(tmp_home_no_env)

    assert fired == [("swap2", "once"), ("swap2", "cron")]


def test_a_pending_one_shot_stamp_is_ignored_when_the_job_was_given_a_new_run_at(monkeypatch, tmp_home_no_env: Path) -> None:
    once = {"id": "swap3", "kind": "once", "run_at": _PAST, "prompt": "once"}
    scheduler._save_jobs(tmp_home_no_env, [once])
    _fired_by_tick(monkeypatch)
    real_update = jobs_store.update
    state = {"fail": True}

    def flaky(home, mutator):
        if state["fail"]:
            raise OSError("disk full")
        return real_update(home, mutator)

    monkeypatch.setattr(jobs_store, "update", flaky)
    scheduler.tick(tmp_home_no_env)

    later = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
    real_update(tmp_home_no_env, lambda jobs: [{**j, "run_at": later} for j in jobs])
    state["fail"] = False
    scheduler.tick(tmp_home_no_env)

    kept = jobs_store.read(tmp_home_no_env)
    assert [(j["id"], j["run_at"]) for j in kept] == [("swap3", later)]


def test_a_pending_cron_stamp_still_applies_after_the_expression_changed(monkeypatch, tmp_home_no_env: Path) -> None:
    scheduler._save_jobs(tmp_home_no_env, [_cron("keep1")])
    _fired_by_tick(monkeypatch)
    real_update = jobs_store.update
    state = {"fail": True}

    def flaky(home, mutator):
        if state["fail"]:
            raise OSError("disk full")
        return real_update(home, mutator)

    monkeypatch.setattr(jobs_store, "update", flaky)
    scheduler.tick(tmp_home_no_env)
    real_update(tmp_home_no_env, lambda jobs: [{**j, "expression": "*/5 * * * *"} for j in jobs])
    state["fail"] = False
    scheduler.tick(tmp_home_no_env)

    job = jobs_store.read(tmp_home_no_env)[0]
    assert job["last_run_status"] == "ok" and job["last_run_at"] != _PAST


def test_a_pending_one_shot_deletion_yields_to_a_newer_manual_stamp(monkeypatch, tmp_home_no_env: Path) -> None:
    once = {"id": "swap4", "kind": "once", "run_at": _PAST, "prompt": "once"}
    scheduler._save_jobs(tmp_home_no_env, [once])
    _fired_by_tick(monkeypatch)
    real_update = jobs_store.update
    state = {"fail": True}

    def flaky(home, mutator):
        if state["fail"]:
            raise OSError("disk full")
        return real_update(home, mutator)

    monkeypatch.setattr(jobs_store, "update", flaky)
    scheduler.tick(tmp_home_no_env)

    newer = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
    real_update(tmp_home_no_env, lambda jobs: [{**j, "last_run_at": newer, "last_run_status": "error", "last_run_message": "manual failure"} for j in jobs])
    state["fail"] = False
    scheduler.tick(tmp_home_no_env)
    scheduler.tick(tmp_home_no_env)

    kept = jobs_store.read(tmp_home_no_env)
    assert [(j["id"], j["last_run_status"], j["last_run_at"]) for j in kept] == [("swap4", "error", newer)]
