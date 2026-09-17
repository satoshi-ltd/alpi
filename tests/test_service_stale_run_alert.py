import asyncio
import json
import logging
import subprocess
from pathlib import Path

import pytest

from alpi import runs, service


def _capture_events(monkeypatch) -> list[tuple[str, dict]]:
    seen: list[tuple[str, dict]] = []
    from alpi.host import events as host_events
    monkeypatch.setattr(host_events, "emit", lambda kind, payload=None: seen.append((kind, payload or {})))
    return seen


def _home(tmp_path: Path, jobs: list[dict] | None = None) -> Path:
    home = tmp_path / "sentinel"
    (home / "schedule").mkdir(parents=True)
    (home / "config.yaml").write_text("model: test\n")
    (home / "schedule" / "jobs.json").write_text(json.dumps(jobs or []))
    return home


@pytest.fixture(autouse=True)
def _fresh_sweep_state():
    runs._silence_seen.clear()
    service._reported_open.clear()
    yield
    runs._silence_seen.clear()
    service._reported_open.clear()


def _failed(seen):
    return [p for kind, p in seen if kind == "schedule.failed"]


def test_a_dead_scheduled_run_files_an_error_and_raises_schedule_failed(tmp_path: Path, monkeypatch) -> None:
    home = _home(tmp_path, [{"id": "35cbf2b8", "title": "Sentinel PR review"}])
    seen = _capture_events(monkeypatch)

    service._alert_stale_runs(home, "sentinel", [{
        "run_id": "dba55843", "job_id": "35cbf2b8", "source": "schedule",
        "silent_for_s": 108540.0, "reason": "dead", "journal_closed": True, "pid_recorded": True,
    }])

    payload = _failed(seen)[0]
    assert payload["profile"] == "sentinel" and payload["job_id"] == "35cbf2b8"
    assert payload["title"] == "Sentinel PR review" and payload["run_id"] == "dba55843"
    assert "108540" in payload["body"] and "process was gone" in payload["body"]
    assert payload["deep_link"] == f"/outputs/sentinel/{payload['output_id']}"
    from alpi import outputs as outputs_mod
    filed = outputs_mod.read(home, payload["output_id"])
    assert filed["type"] == "error" and filed["title"] == "Sentinel PR review did not finish"


def test_a_dead_run_that_recorded_no_pid_is_not_described_as_having_one(tmp_path: Path, monkeypatch) -> None:
    home = _home(tmp_path)
    seen = _capture_events(monkeypatch)
    service._alert_stale_runs(home, "sentinel", [{
        "run_id": "r0", "job_id": "", "source": "user", "silent_for_s": 4000.0,
        "reason": "dead", "journal_closed": True, "pid_recorded": False,
    }])
    body = _failed(seen)[0]["body"]
    assert "recorded no pid" in body and "process was gone" not in body


def test_a_dead_manual_run_still_alerts_without_a_job(tmp_path: Path, monkeypatch) -> None:
    home = _home(tmp_path)
    seen = _capture_events(monkeypatch)
    service._alert_stale_runs(home, "sentinel", [{
        "run_id": "adb7799e", "job_id": "", "source": "user", "silent_for_s": 47.0,
        "reason": "dead", "journal_closed": True, "pid_recorded": True,
    }])
    payload = _failed(seen)[0]
    assert payload["job_id"] == "" and payload["title"] == "manual run" and payload["kind"] == "run"


def test_a_silent_run_is_reported_as_wedged_with_its_timeout(tmp_path: Path, monkeypatch) -> None:
    home = _home(tmp_path, [{"id": "35cbf2b8", "title": "Sentinel PR review"}])
    seen = _capture_events(monkeypatch)
    service._alert_stale_runs(home, "sentinel", [{
        "run_id": "6c20ce52", "job_id": "35cbf2b8", "source": "schedule", "silent_for_s": 71160.0,
        "reason": "silent", "timeout_s": 1700, "pid_killed": True, "journal_closed": True,
    }])
    payload = _failed(seen)[0]
    assert "wedged" in payload["message"] and "1700s timeout" in payload["body"] and "has been killed" in payload["body"]
    from alpi import outputs as outputs_mod
    assert outputs_mod.read(home, payload["output_id"])["title"] == "Sentinel PR review went silent"


def test_a_silent_run_left_open_says_so_and_asks_for_a_human(tmp_path: Path, monkeypatch) -> None:
    home = _home(tmp_path, [{"id": "j", "title": "job"}])
    seen = _capture_events(monkeypatch)
    service._alert_stale_runs(home, "sentinel", [{
        "run_id": "x", "job_id": "j", "source": "schedule", "silent_for_s": 5000.0,
        "reason": "silent", "timeout_s": 60, "pid_killed": False, "journal_closed": False,
    }])
    body = _failed(seen)[0]["body"]
    assert "left open" in body and "will not repeat" in body and "killed" not in body.split("nothing was killed")[0]


def test_unreadable_jobs_file_does_not_stop_the_alert(tmp_path: Path, monkeypatch) -> None:
    home = _home(tmp_path)
    (home / "schedule" / "jobs.json").write_text("{ this is not json")
    seen = _capture_events(monkeypatch)
    service._alert_stale_runs(home, "sentinel", [{
        "run_id": "r9", "job_id": "zz", "source": "schedule", "silent_for_s": 5.0,
        "reason": "dead", "journal_closed": True, "pid_recorded": True,
    }])
    assert _failed(seen)[0]["title"] == "job zz"


def _mono(monkeypatch, values: list[float]) -> None:
    it = iter(values)
    monkeypatch.setattr(runs.time, "monotonic", lambda: next(it))


def test_sweep_closes_a_dead_run_and_reports_an_open_one_exactly_once(tmp_path: Path, monkeypatch) -> None:
    home = _home(tmp_path, [{"id": "j1", "title": "first", "timeout": 60}])
    seen = _capture_events(monkeypatch)
    monkeypatch.setattr(runs.time, "time", lambda: 1000.0)
    runs.append(home, "dead", "run.started", {"run_id": "dead", "profile": "sentinel", "job_id": "j1", "pid": 999998})
    runs.append(home, "quiet", "run.started", {"run_id": "quiet", "profile": "sentinel", "job_id": "j1", "pid": 999999, "pid_start": "k"})
    monkeypatch.setattr(runs, "_pid_alive", lambda pid: pid == 999999)
    monkeypatch.setattr(runs, "proc_starttime", lambda pid: "not-k")
    monkeypatch.setattr(runs.time, "time", lambda: 1000.0 + 60 + 300 + 5)
    _mono(monkeypatch, [0.0, 300.0, 600.0, 900.0])

    service._sweep_runs(home, "sentinel")   # dead closes now; quiet is only observed
    service._sweep_runs(home, "sentinel")   # quiet reported, left open
    service._sweep_runs(home, "sentinel")   # nothing new to say

    failed = _failed(seen)
    assert [p["run_id"] for p in failed] == ["dead", "quiet"]
    assert "interrupted" in failed[0]["message"] and "wedged" in failed[1]["message"]
    assert runs.summary(home, "dead")["status"] == "interrupted"
    assert runs.summary(home, "quiet")["status"] == "running"


def test_left_open_alerts_are_deduplicated_per_profile_not_globally(tmp_path: Path, monkeypatch) -> None:
    """Sweeping an empty profile must not make another profile's open run alert again."""
    a = _home(tmp_path / "a", [{"id": "j", "title": "job", "timeout": 60}])
    b = _home(tmp_path / "b", [])
    seen = _capture_events(monkeypatch)
    monkeypatch.setattr(runs.time, "time", lambda: 1000.0)
    runs.append(a, "open", "run.started", {"run_id": "open", "profile": "a", "job_id": "j", "pid": 999999, "pid_start": "k"})
    monkeypatch.setattr(runs, "_pid_alive", lambda pid: pid == 999999)
    monkeypatch.setattr(runs, "proc_starttime", lambda pid: "not-k")
    monkeypatch.setattr(runs.time, "time", lambda: 1000.0 + 60 + 300 + 5)
    _mono(monkeypatch, [0.0, 300.0, 600.0, 900.0, 1200.0, 1500.0])

    service._sweep_runs(a, "a")   # observe
    service._sweep_runs(a, "a")   # report once
    service._sweep_runs(b, "b")   # another profile, nothing to say
    service._sweep_runs(a, "a")
    service._sweep_runs(b, "b")
    service._sweep_runs(a, "a")

    assert [p["run_id"] for p in _failed(seen)] == ["open"]


def test_a_refused_kill_is_reported_as_such(tmp_path: Path, monkeypatch) -> None:
    home = _home(tmp_path, [{"id": "j", "title": "job"}])
    seen = _capture_events(monkeypatch)
    service._alert_stale_runs(home, "sentinel", [{
        "run_id": "x", "job_id": "j", "source": "schedule", "silent_for_s": 5000.0,
        "reason": "silent", "timeout_s": 60, "pid_killed": False, "journal_closed": False, "kill_refused": True,
    }])
    body = _failed(seen)[0]["body"]
    assert "refused the kill" in body and "left open" in body


def test_sweep_is_quiet_when_nothing_is_wrong(tmp_path: Path, monkeypatch) -> None:
    home = _home(tmp_path)
    seen = _capture_events(monkeypatch)
    service._sweep_runs(home, "sentinel")
    assert seen == []


def test_sweep_judges_a_run_whose_job_was_deleted_by_the_scheduler_ceiling(tmp_path: Path, monkeypatch) -> None:
    from alpi.scheduler.run import MAX_RUN_TIMEOUT_SECONDS
    home = _home(tmp_path, [])
    seen = _capture_events(monkeypatch)
    monkeypatch.setattr(runs.time, "time", lambda: 1000.0)
    runs.append(home, "orphan", "run.started", {"run_id": "orphan", "profile": "sentinel", "job_id": "gone", "pid": 0})
    monkeypatch.setattr(runs.time, "time", lambda: 1000.0 + MAX_RUN_TIMEOUT_SECONDS + 300 + 5)
    _mono(monkeypatch, [0.0, 300.0])

    service._sweep_runs(home, "sentinel")
    service._sweep_runs(home, "sentinel")

    assert _failed(seen)[0]["run_id"] == "orphan"
    assert runs.summary(home, "orphan")["status"] == "interrupted"


def test_an_exception_in_the_alert_path_never_escapes_the_sweep(tmp_path: Path, monkeypatch) -> None:
    home = _home(tmp_path)
    monkeypatch.setattr(runs.time, "time", lambda: 1000.0)
    runs.append(home, "dead", "run.started", {"run_id": "dead", "profile": "sentinel", "job_id": "j", "pid": 999998})
    monkeypatch.setattr(runs, "_pid_alive", lambda pid: False)
    monkeypatch.setattr(runs.time, "time", lambda: 9000.0)
    from alpi.host import events as host_events
    def boom(*a, **k):
        raise RuntimeError("loop is closed")
    monkeypatch.setattr(host_events, "emit", boom)

    service._sweep_runs(home, "sentinel")   # must not raise

    assert runs.summary(home, "dead")["status"] == "interrupted"


def test_the_daemon_loop_sweeps_each_profile_on_a_throttle(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "profiles" / "sentinel").mkdir(parents=True)
    calls: list[str] = []
    clock = {"t": 1000.0}
    monkeypatch.setattr(service.time, "time", lambda: clock["t"])
    monkeypatch.setattr(service, "_sweep_runs", lambda home, profile: calls.append(profile))
    monkeypatch.setattr(service, "_reload_fingerprints", lambda home: {})
    registry = {"sentinel": {"tasks": {}, "fps": {}}}

    asyncio.run(service._reconcile_profiles(tmp_path, registry))
    clock["t"] += 5.0
    asyncio.run(service._reconcile_profiles(tmp_path, registry))
    assert calls == ["sentinel"]

    clock["t"] += service._RUN_SWEEP_SECONDS
    asyncio.run(service._reconcile_profiles(tmp_path, registry))
    assert calls == ["sentinel", "sentinel"]


def test_the_daemon_loop_survives_a_sweep_that_raises(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "profiles" / "sentinel").mkdir(parents=True)
    def boom(home, profile):
        raise RuntimeError("disk on fire")
    monkeypatch.setattr(service, "_sweep_runs", boom)
    monkeypatch.setattr(service, "_reload_fingerprints", lambda home: {})
    registry = {"sentinel": {"tasks": {}, "fps": {}}}

    asyncio.run(service._reconcile_profiles(tmp_path, registry))   # must not raise

    assert registry["sentinel"]["next_sweep_at"] > 0


def test_profile_start_sweeps_once_and_arms_the_throttle(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "profiles" / "sentinel").mkdir(parents=True)
    calls: list[str] = []
    monkeypatch.setattr(service, "_sweep_runs", lambda home, profile: calls.append(profile))
    monkeypatch.setattr(service, "_reload_fingerprints", lambda home: {})
    monkeypatch.setattr(service, "_warn_legacy_service_switches", lambda home, profile: None)
    monkeypatch.setattr(service, "_profile_tasks", lambda home, profile: {})
    registry: dict = {}

    service._start_new_profiles(tmp_path, ["sentinel"], registry)

    assert calls == ["sentinel"]
    assert registry["sentinel"]["next_sweep_at"] > 0


def test_run_job_owns_the_journal_of_a_child_it_kills(tmp_path: Path, monkeypatch) -> None:
    """The scheduler already alerts on its own timeout; closing the journal itself keeps the sweep from alerting a second time."""
    from alpi.scheduler import run as sched
    home = _home(tmp_path)
    captured: dict = {}
    def fake_run(argv, **kw):
        captured["env"] = kw["env"]
        raise subprocess.TimeoutExpired(argv, kw["timeout"])
    monkeypatch.setattr(sched.subprocess, "run", fake_run)
    closed: list[tuple] = []
    monkeypatch.setattr(runs, "finish_if_running", lambda h, rid, outcome: closed.append((h, rid, outcome)) or True)

    outcome = sched.run_job({"id": "j", "prompt": "do the thing", "timeout": 60}, home)

    assert outcome.ok is False and outcome.timeout_reason == "timeout_60s"
    assert len(closed) == 1 and closed[0][2] == "interrupted"
    assert closed[0][1] == captured["env"]["ALPI_RUN_ID"]
    assert len(closed[0][1]) == 32


def test_the_daemon_quiets_the_websockets_logger(tmp_path: Path, monkeypatch) -> None:
    """One third-party logger was 99.9% of service.log and rotated real evidence out in about two hours."""
    root = logging.getLogger()
    ws = logging.getLogger("websockets")
    saved = (list(root.handlers), root.level, ws.level)
    try:
        root.handlers = []
        ws.setLevel(logging.NOTSET)
        service._configure_logging_daemon(tmp_path)
        assert ws.level == logging.WARNING and not ws.isEnabledFor(logging.INFO)
    finally:
        for h in root.handlers:
            h.close()
        root.handlers, root.level = saved[0], saved[1]
        ws.setLevel(saved[2])
