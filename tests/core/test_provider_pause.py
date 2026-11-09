from __future__ import annotations

import json
from pathlib import Path

import pytest

from alpi import provider_pause as pp
from alpi.scheduler import run as scheduler


@pytest.fixture(autouse=True)
def _clean():
    pp.reset()
    pp.activate()
    yield
    pp.reset()


def test_an_inactive_process_never_records_a_pause() -> None:
    pp.reset()
    assert pp.record_failure("p", "insufficient_credit", now=0.0) is None
    assert pp.record_failure("p", "insufficient_credit", now=1.0) is None
    assert pp.paused("p", now=2.0) is None
    assert pp.record_success("p") is None


def test_only_the_first_open_is_announced_and_a_lapsed_window_lets_one_probe_through() -> None:
    pp.record_failure("p", "auth", now=0.0)
    assert pp.record_failure("p", "auth", now=1.0) is not None
    after = 1.0 + pp.ACCOUNT_BASE_S + 1
    assert pp.paused("p", now=after) is None
    assert pp.paused("p", now=after) is not None
    assert pp.record_failure("p", "auth", now=after) is None
    assert pp.paused("p", now=after + 1).window_s == pp.ACCOUNT_BASE_S * 2


def test_two_account_failures_open_the_pause_and_the_second_call_announces_it() -> None:
    assert pp.record_failure("p", "insufficient_credit", now=1000.0) is None
    state = pp.record_failure("p", "insufficient_credit", now=1001.0)
    assert state is not None and state.until == 1001.0 + pp.ACCOUNT_BASE_S
    assert pp.paused("p", now=1002.0) is state
    assert pp.describe("p", now=1002.0)["code"] == "insufficient_credit"


def test_a_lapsed_window_lets_one_attempt_through_and_a_failure_doubles_it() -> None:
    pp.record_failure("p", "auth", now=0.0)
    pp.record_failure("p", "auth", now=1.0)
    after = 1.0 + pp.ACCOUNT_BASE_S + 1
    assert pp.paused("p", now=after) is None
    assert pp.record_failure("p", "auth", now=after) is None
    state = pp.paused("p", now=after + 1)
    assert state is not None and state.window_s == pp.ACCOUNT_BASE_S * 2


def test_the_window_caps_and_a_success_closes_everything() -> None:
    now = 0.0
    for _ in range(12):
        pp.record_failure("p", "model_unavailable", now=now)
        now = (pp.paused("p", now=now) or pp.PauseState()).until + 1
    assert pp._states["p"].window_s == pp.ACCOUNT_MAX_S
    closed = pp.record_success("p")
    assert closed is not None and closed.open
    assert pp.paused("p", now=now) is None
    assert pp.record_success("p") is None


def test_transport_failures_use_the_short_window_and_other_codes_are_ignored() -> None:
    assert pp.record_failure("p", "rate_limited", now=0.0) is None
    assert pp.record_failure("p", "bad_request", now=0.0) is None
    assert pp.paused("p", now=1.0) is None
    pp.record_failure("p", "provider_unavailable", now=0.0)
    state = pp.record_failure("p", "timeout", now=1.0)
    assert state is not None and state.window_s == pp.TRANSPORT_BASE_S


def test_announce_once_keeps_one_line_per_key_per_pause() -> None:
    pp.record_failure("p", "auth", now=0.0)
    pp.record_failure("p", "auth", now=1.0)
    assert pp.announce_once("p", "job:a") is True
    assert pp.announce_once("p", "job:a") is False
    assert pp.announce_once("p", "job:b") is True
    assert pp.announce_once("other", "job:a") is False


def test_profiles_are_independent() -> None:
    pp.record_failure("a", "auth", now=0.0)
    pp.record_failure("a", "auth", now=1.0)
    assert pp.paused("a", now=2.0) is not None
    assert pp.paused("b", now=2.0) is None


_PAST = "2020-01-01T00:00:00+00:00"


def _jobs(home: Path, *ids: str) -> None:
    scheduler._save_jobs(home, [
        {"id": i, "kind": "cron", "expression": "* * * * *", "prompt": "ping", "last_run_at": _PAST}
        for i in ids
    ])


def test_tick_skips_agent_jobs_while_the_provider_is_paused_and_leaves_them_due(monkeypatch, tmp_home_no_env: Path) -> None:
    from alpi.home import profile_name
    profile = profile_name(tmp_home_no_env)
    _jobs(tmp_home_no_env, "job1")
    fired: list[str] = []
    monkeypatch.setattr(scheduler, "run_job", lambda job, home: (fired.append(job["id"]) or scheduler.JobOutcome(True, "ok")))
    pp.record_failure(profile, "insufficient_credit")
    pp.record_failure(profile, "insufficient_credit")

    assert scheduler.tick(tmp_home_no_env) == []
    assert fired == []
    assert "last_run_status" not in json.loads((tmp_home_no_env / "schedule" / "runs.json").read_text()).get("job1", {})

    pp.reset(profile)
    assert scheduler.tick(tmp_home_no_env) == [("job1", True, "ok")]
    assert fired == ["job1"]


def test_tick_still_runs_script_jobs_while_paused(monkeypatch, tmp_home_no_env: Path) -> None:
    from alpi.home import profile_name
    profile = profile_name(tmp_home_no_env)
    scheduler._save_jobs(tmp_home_no_env, [
        {"id": "s1", "kind": "cron", "expression": "* * * * *", "prompt": "x", "no_agent": True, "last_run_at": _PAST},
    ])
    fired: list[str] = []
    monkeypatch.setattr(scheduler, "run_job", lambda job, home: (fired.append(job["id"]) or scheduler.JobOutcome(True, "ok")))
    pp.record_failure(profile, "auth")
    pp.record_failure(profile, "auth")
    scheduler.tick(tmp_home_no_env)
    assert fired == ["s1"]


def test_two_failed_fires_with_a_credit_code_open_the_pause_and_file_one_alert(monkeypatch, tmp_home_no_env: Path) -> None:
    from alpi.home import profile_name
    from alpi import outputs as outputs_mod
    profile = profile_name(tmp_home_no_env)
    _jobs(tmp_home_no_env, "job1", "job2", "job3")
    seen: list[tuple[str, dict]] = []
    from alpi.host import events as host_events
    monkeypatch.setattr(host_events, "emit", lambda kind, payload=None: seen.append((kind, payload or {})))
    monkeypatch.setattr(host_events, "ensure_history_loaded", lambda: None)
    fired: list[str] = []

    def _fail(job, home):
        fired.append(job["id"])
        return scheduler.JobOutcome(False, "agent error: out of credit", provider_code="insufficient_credit")

    monkeypatch.setattr(scheduler, "run_job", _fail)
    results = scheduler.tick(tmp_home_no_env)
    assert fired == ["job1", "job2"]
    assert [r[1] for r in results] == [False, False]
    assert pp.paused(profile) is not None
    alerts = [p for kind, p in seen if kind == "schedule.failed" and p.get("kind") == "provider"]
    assert len(alerts) == 1 and alerts[0]["code"] == "insufficient_credit"
    filed = outputs_mod.read(tmp_home_no_env, alerts[0]["output_id"])
    assert filed["type"] == "error" and "paused for 15 minutes" in filed["body"]


def test_a_successful_fire_closes_the_pause_and_announces_the_recovery(monkeypatch, tmp_home_no_env: Path) -> None:
    from alpi.home import profile_name
    profile = profile_name(tmp_home_no_env)
    _jobs(tmp_home_no_env, "job1")
    seen: list[tuple[str, dict]] = []
    from alpi.host import events as host_events
    monkeypatch.setattr(host_events, "emit", lambda kind, payload=None: seen.append((kind, payload or {})))
    monkeypatch.setattr(host_events, "ensure_history_loaded", lambda: None)
    monkeypatch.setattr(scheduler, "run_job", lambda job, home: scheduler.JobOutcome(True, "ok"))
    pp.record_failure(profile, "auth", now=0.0)
    pp.record_failure(profile, "auth", now=1.0)
    scheduler.tick(tmp_home_no_env)
    assert pp.paused(profile) is None
    assert [p for kind, p in seen if kind == "schedule.done" and p.get("kind") == "provider"]


def test_parse_events_keeps_the_error_code() -> None:
    parsed = scheduler._parse_events(json.dumps({"kind": "error", "text": "x", "code": "insufficient_credit", "detail": "d"}))
    assert parsed.errored and parsed.error_code == "insufficient_credit"
    assert scheduler._parse_events(json.dumps({"kind": "error", "text": "x"})).error_code == ""


def test_profile_summary_carries_the_pause(monkeypatch, tmp_path: Path) -> None:
    from alpi.host import device_state
    home = tmp_path / "h"
    home.mkdir()
    (home / "config.yaml").write_text("model: test\n")
    monkeypatch.setattr(device_state, "_today_ledger", lambda _h: (0.0, 0))
    monkeypatch.setattr(device_state, "_latest_chat_for", lambda _h: None)
    monkeypatch.setattr(device_state, "_counts", lambda _h: {})
    monkeypatch.setattr(device_state, "_profile_pubkey", lambda _h: None)
    monkeypatch.setattr(device_state, "_has_any_provider", lambda _h, _c: True)
    monkeypatch.setattr(device_state, "_daemon_running", lambda: True)
    monkeypatch.setattr(device_state, "_daemon_pid", lambda: 1)
    monkeypatch.setattr(device_state, "_installed_via", lambda: None)
    row = {"name": "p", "home": str(home), "is_default": False}
    assert device_state._profile_summary(row)["provider_pause"] is None
    pp.record_failure("p", "auth")
    pp.record_failure("p", "auth")
    pause = device_state._profile_summary(row)["provider_pause"]
    assert pause["code"] == "auth" and pause["until"] > 0


def test_doctor_accepts_a_tool_action_deny_entry(tmp_path: Path) -> None:
    from alpi import config as cfg_mod
    from alpi import doctor
    (tmp_path / "config.yaml").write_text("model: m\ntools:\n  deny: [\"knowledge:ingest\", \"nope\"]\n")
    checks = doctor._tool_checks(cfg_mod.load(tmp_path)) if hasattr(doctor, "_tool_checks") else None
    if checks is None:
        import inspect
        fn = next(f for n, f in inspect.getmembers(doctor, inspect.isfunction) if "availability_report" in inspect.getsource(f) and n != "run")
        checks = fn(cfg_mod.load(tmp_path))
    deny = [c for c in checks if c.name == "denylist"]
    assert deny and "nope" in deny[0].detail and "knowledge" not in deny[0].detail


def test_host_chat_engine_records_the_failure_and_the_recovery(monkeypatch, tmp_path: Path) -> None:
    from alpi.engine import AgentEvent, Engine
    home = tmp_path / "h"
    home.mkdir()
    monkeypatch.setattr("alpi.engine._maybe_load_mcps", lambda _cfg: [])
    monkeypatch.setattr(Engine, "_build_system_prompt", lambda self: "you are alpi")
    from alpi.config import Config
    engine = Engine(home=home, cfg=Config(home=home, model="m", raw={}))
    monkeypatch.setattr(pp, "notify_opened", lambda *a, **k: None)
    monkeypatch.setattr(pp, "notify_closed", lambda *a, **k: None)
    engine._note_provider_outcome("p", AgentEvent(kind="error", text="x", code="insufficient_credit"))
    engine._note_provider_outcome("p", AgentEvent(kind="error", text="x", code="insufficient_credit"))
    assert pp.paused("p") is not None
    engine._note_provider_outcome("p", AgentEvent(kind="assistant_done", text="ok", final=True))
    assert pp.paused("p") is None


def test_describe_never_takes_the_probe_slot() -> None:
    pp.record_failure("p", "auth", now=0.0)
    pp.record_failure("p", "auth", now=1.0)
    after = 1.0 + pp.ACCOUNT_BASE_S + 1
    view = pp.describe("p", now=after)
    assert view is not None and view["probing"] is False
    assert pp.paused("p", now=after) is None
    assert pp.describe("p", now=after)["probing"] is True


def test_a_probe_that_never_reports_frees_its_slot_after_the_ttl() -> None:
    pp.record_failure("p", "auth", now=0.0)
    pp.record_failure("p", "auth", now=1.0)
    after = 1.0 + pp.ACCOUNT_BASE_S + 1
    assert pp.paused("p", now=after) is None
    assert pp.paused("p", now=after + 1) is not None
    assert pp.paused("p", now=after + pp.PROBE_TTL_S + 1) is None


def test_a_neutral_outcome_releases_the_probe() -> None:
    pp.record_failure("p", "auth", now=0.0)
    pp.record_failure("p", "auth", now=1.0)
    after = 1.0 + pp.ACCOUNT_BASE_S + 1
    assert pp.paused("p", now=after) is None
    pp.release_probe("p")
    assert pp.paused("p", now=after + 1) is None


def test_a_timed_out_job_during_the_probe_frees_the_slot(monkeypatch, tmp_home_no_env: Path) -> None:
    from alpi.home import profile_name
    profile = profile_name(tmp_home_no_env)
    _jobs(tmp_home_no_env, "job1")
    monkeypatch.setattr(scheduler, "run_job", lambda job, home: scheduler.JobOutcome(False, "agent timed out", timeout_reason="timeout_900s"))
    pp.record_failure(profile, "auth", now=0.0)
    pp.record_failure(profile, "auth", now=1.0)
    monkeypatch.setattr(pp, "paused", lambda p, now=None: None)
    scheduler.tick(tmp_home_no_env)
    monkeypatch.undo()
    assert pp._states[profile].probing is False
