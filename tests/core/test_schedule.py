"""Tests for the schedule daemon: due-time logic, tick, kind=inactivity,
plus auto-spawn."""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from alpi.scheduler import run as scheduler
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
    assert job["last_run_at"] is not None
    datetime.fromisoformat(job["last_run_at"])
    assert "last_run_status" not in job


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
    job = {"kind": "cron", "expression": "not-a-cron"}
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


def test_tick_fires_due_jobs_and_updates_last_run(monkeypatch, tmp_home_no_env: Path) -> None:
    # Set up one always-due cron job.
    jobs = [{
        "id": "abc123", "kind": "cron", "expression": "* * * * *",
        "prompt": "ping",
        "last_run_at": None,
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
    assert saved[0]["last_run_at"] is not None
    assert saved[0]["last_run_status"] == "ok"


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
        "last_run_at": None,
    }]
    scheduler._save_jobs(tmp_home_no_env, jobs)
    monkeypatch.setattr(scheduler, "run_job",
                        lambda job, home: scheduler.JobOutcome(False, "boom"))
    results = scheduler.tick(tmp_home_no_env)
    assert results == [("x", False, "boom")]
    saved = json.loads((tmp_home_no_env / "schedule" / "jobs.json").read_text())
    assert saved[0]["last_run_at"] is not None
    assert saved[0]["last_run_status"] == "error"


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
    saved = json.loads(jobs_path.read_text())
    alpha = next(j for j in saved if j["id"] == "alpha")
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
    assert "last_run_at" in jobs_after[0]


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


def test_job_run_timeout_clamps_to_bounds() -> None:
    assert scheduler.job_run_timeout({"timeout": 10}) == 30
    assert scheduler.job_run_timeout({"timeout": 99999}) == scheduler.MAX_RUN_TIMEOUT_SECONDS


def test_job_run_timeout_ignores_garbage() -> None:
    assert scheduler.job_run_timeout({"timeout": "nope"}) == 900
    assert scheduler.job_run_timeout({"timeout": None}) == 900


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
