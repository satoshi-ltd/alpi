"""Pin the structured payload of `schedule.done` / `schedule.failed`: `reply`, `delivered_to`, and `silent` across branches (agent vs no_agent, notify vs silent, success vs failure, native-notify dedup, oversized reply cap)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from alpi.scheduler import run as scheduler


def _events_stdout(events: list[dict]) -> str:
    return "\n".join(json.dumps(e) for e in events)


def _capture_emit(monkeypatch) -> list[tuple[str, dict]]:
    """Capture every host_events.emit() call made during the test."""
    captured: list[tuple[str, dict]] = []
    from alpi.host import events as host_events
    monkeypatch.setattr(
        host_events, "emit",
        lambda kind, data=None: captured.append((kind, dict(data or {}))),
    )
    return captured


def _seed_job(home: Path, job: dict) -> None:
    home_jobs = home / "schedule" / "jobs.json"
    home_jobs.parent.mkdir(parents=True, exist_ok=True)
    home_jobs.write_text(json.dumps([job]))


# --------------------------------------------------------------------
# agent jobs
# --------------------------------------------------------------------


def test_event_carries_agent_reply_when_no_platform(
    monkeypatch, tmp_home_no_env: Path,
) -> None:
    """Silent maintenance job WITH agent output → `reply` populated, `silent` False, `delivered_to` empty."""

    class _Proc:
        returncode = 0
        stdout = _events_stdout([{"kind": "reply", "text": "indexed 12 files"}])
        stderr = ""

    monkeypatch.setattr(scheduler.subprocess, "run", lambda *a, **kw: _Proc())
    emits = _capture_emit(monkeypatch)
    _seed_job(tmp_home_no_env, {
        "id": "reindex", "kind": "cron", "expression": "* * * * *",
        "prompt": "reindex", "last_run_at": None,
    })

    scheduler.tick(tmp_home_no_env)

    schedule_events = [e for e in emits if e[0] == "schedule.done"]
    assert len(schedule_events) == 1
    _, payload = schedule_events[0]
    assert payload["reply"] == "indexed 12 files"
    assert "silent run ok" in payload["message"]
    assert payload["silent"] is False
    assert payload["delivered_to"] == ""


def test_event_carries_agent_reply_when_notify_true(
    monkeypatch, tmp_home_no_env: Path,
) -> None:
    """notify:true job → reply mirrors the agent output, delivered_to='alpi', and a native push (agent.message) is emitted."""

    class _Proc:
        returncode = 0
        stdout = _events_stdout([{"kind": "reply", "text": "hi there"}])
        stderr = ""

    monkeypatch.setattr(scheduler.subprocess, "run", lambda *a, **kw: _Proc())
    emits = _capture_emit(monkeypatch)

    _seed_job(tmp_home_no_env, {
        "id": "greet", "kind": "cron", "expression": "* * * * *",
        "prompt": "say hi", "notify": True, "last_run_at": None,
    })
    scheduler.tick(tmp_home_no_env)

    payload = [e for e in emits if e[0] == "schedule.done"][0][1]
    assert payload["reply"] == "hi there"
    assert payload["delivered_to"] == "alpi"
    assert payload["silent"] is False
    assert any(k == "agent.message" for k, _ in emits)  # native push fired


def test_event_reply_empty_when_agent_notified(
    monkeypatch, tmp_home_no_env: Path,
) -> None:
    """Agent natively notified (notify) → reply empty, delivered_to='external' so clients don't re-notify."""

    class _Proc:
        returncode = 0
        stdout = _events_stdout([
            {"kind": "tool_start", "name": "notify"},
            {"kind": "tool_end", "name": "notify", "ok": True},
            {"kind": "reply", "text": "already sent"},
        ])
        stderr = ""

    monkeypatch.setattr(scheduler.subprocess, "run", lambda *a, **kw: _Proc())
    emits = _capture_emit(monkeypatch)

    _seed_job(tmp_home_no_env, {
        "id": "self", "kind": "cron", "expression": "* * * * *",
        "prompt": "post", "notify": True, "last_run_at": None,
    })
    scheduler.tick(tmp_home_no_env)

    payload = [e for e in emits if e[0] == "schedule.done"][0][1]
    assert payload["reply"] == ""
    assert payload["delivered_to"] == "external"
    assert "no duplicate" in payload["message"]
    assert payload["silent"] is False


def test_send_message_from_schedule_reemits_agent_message_in_daemon(
    monkeypatch, tmp_home_no_env: Path,
) -> None:
    """The scheduled agent runs in a subprocess. The parent scheduler must re-emit the alpi-native notification in the daemon process so desktop/mobile subscribers see it."""

    class _Proc:
        returncode = 0
        stdout = _events_stdout([
            {
                "kind": "tool_start",
                "name": "send_message",
                "args": {
                    "text": "Research finished.",
                    "title": "Research done",
                    "type": "warning",
                    "channel": "alpi",
                },
            },
            {"kind": "tool_end", "name": "send_message", "ok": True},
            {"kind": "reply", "text": "already sent"},
        ])
        stderr = ""

    monkeypatch.setattr(scheduler.subprocess, "run", lambda *a, **kw: _Proc())
    emits = _capture_emit(monkeypatch)

    _seed_job(tmp_home_no_env, {
        "id": "research", "kind": "cron", "expression": "* * * * *",
        "prompt": "notify when done",
        "last_run_at": None,
    })
    scheduler.tick(tmp_home_no_env)

    agent_messages = [d for k, d in emits if k == "agent.message"]
    assert len(agent_messages) == 1
    msg = agent_messages[0]
    assert msg["profile"] == "default"
    assert msg["title"] == "Research done"
    assert msg["body"] == "Research finished."
    assert msg["type"] == "warning"
    assert msg["output_id"]
    assert msg["deep_link"] == f"/outputs/{msg['profile']}/{msg['output_id']}"
    done = [d for k, d in emits if k == "schedule.done"][0]
    assert done["delivered_to"] == "external"
    assert done["reply"] == ""


def test_failed_send_message_does_not_count_as_delivered(
    monkeypatch, tmp_home_no_env: Path,
) -> None:
    """A failed send_message call should not suppress the final schedule reply."""

    class _Proc:
        returncode = 0
        stdout = _events_stdout([
            {
                "kind": "tool_start",
                "name": "send_message",
                "args": {"text": "Ping", "channel": "alpi"},
            },
            {"kind": "tool_end", "name": "send_message", "ok": False},
            {"kind": "reply", "text": "fallback summary"},
        ])
        stderr = ""

    monkeypatch.setattr(scheduler.subprocess, "run", lambda *a, **kw: _Proc())
    emits = _capture_emit(monkeypatch)

    _seed_job(tmp_home_no_env, {
        "id": "fallback", "kind": "cron", "expression": "* * * * *",
        "prompt": "notify when done",
        "last_run_at": None,
    })
    scheduler.tick(tmp_home_no_env)

    assert [d for k, d in emits if k == "agent.message"] == []
    done = [d for k, d in emits if k == "schedule.done"][0]
    assert done["reply"] == "fallback summary"
    assert done["delivered_to"] == ""


def test_event_reply_empty_on_failure(
    monkeypatch, tmp_home_no_env: Path,
) -> None:
    """Failed jobs → `reply` empty; only `message` carries the error text."""

    class _Proc:
        returncode = 1
        stdout = ""
        stderr = "kaboom"

    monkeypatch.setattr(scheduler.subprocess, "run", lambda *a, **kw: _Proc())
    emits = _capture_emit(monkeypatch)

    _seed_job(tmp_home_no_env, {
        "id": "bad", "kind": "cron", "expression": "* * * * *",
        "prompt": "fail", "last_run_at": None,
    })
    scheduler.tick(tmp_home_no_env)

    failed = [e for e in emits if e[0] == "schedule.failed"]
    assert len(failed) == 1
    payload = failed[0][1]
    assert payload["reply"] == ""
    assert "rc=" in payload["message"]


def test_failed_job_enriches_schedule_failed_no_duplicate(
    monkeypatch, tmp_home_no_env: Path,
) -> None:
    """A failed job enriches schedule.failed with the job title + reason and fires NO second agent.message — clients already notify on schedule.failed."""

    class _Proc:
        returncode = 1
        stdout = ""
        stderr = "boom: connection refused"

    monkeypatch.setattr(scheduler.subprocess, "run", lambda *a, **kw: _Proc())
    emits = _capture_emit(monkeypatch)

    _seed_job(tmp_home_no_env, {
        "id": "bad", "kind": "cron", "expression": "* * * * *",
        "title": "Nightly sync", "prompt": "fail", "last_run_at": None,
    })
    scheduler.tick(tmp_home_no_env)

    failed = [d for k, d in emits if k == "schedule.failed"]
    assert len(failed) == 1
    p = failed[0]
    assert p["title"] == "Nightly sync"
    assert "rc=1" in p["body"]
    assert "connection refused" in p["body"]
    assert "exit code: 1" in p["body"]
    assert [d for k, d in emits if k == "agent.message"] == []


def test_timed_out_job_enriches_schedule_failed_no_duplicate(
    monkeypatch, tmp_home_no_env: Path,
) -> None:
    """A timed-out job: schedule.failed carries the job title + timeout reason; no duplicate agent.message."""

    def _raise_timeout(*a, **kw):
        raise scheduler.subprocess.TimeoutExpired(cmd="alpi", timeout=600)

    monkeypatch.setattr(scheduler.subprocess, "run", _raise_timeout)
    emits = _capture_emit(monkeypatch)

    _seed_job(tmp_home_no_env, {
        "id": "slow", "kind": "cron", "expression": "* * * * *",
        "title": "Heavy report", "prompt": "work", "last_run_at": None,
    })
    scheduler.tick(tmp_home_no_env)

    failed = [d for k, d in emits if k == "schedule.failed"]
    assert len(failed) == 1
    p = failed[0]
    assert p["title"] == "Heavy report"
    assert "timed out" in p["body"]
    assert "timeout:" in p["body"]
    assert [d for k, d in emits if k == "agent.message"] == []


def test_event_reply_truncated_at_2000_chars(
    monkeypatch, tmp_home_no_env: Path,
) -> None:
    """Notification transports don't want unbounded payloads — cap reply."""
    big = "a" * 4000

    class _Proc:
        returncode = 0
        stdout = _events_stdout([{"kind": "reply", "text": big}])
        stderr = ""

    monkeypatch.setattr(scheduler.subprocess, "run", lambda *a, **kw: _Proc())
    emits = _capture_emit(monkeypatch)

    _seed_job(tmp_home_no_env, {
        "id": "big", "kind": "cron", "expression": "* * * * *",
        "prompt": "verbose", "last_run_at": None,
    })
    scheduler.tick(tmp_home_no_env)

    payload = [e for e in emits if e[0] == "schedule.done"][0][1]
    assert len(payload["reply"]) == 2000


# --------------------------------------------------------------------
# no_agent (script) jobs
# --------------------------------------------------------------------


@pytest.fixture
def _trivial_skill_script(tmp_home_no_env: Path) -> Path:
    """A no-op skill script under the layout validate_no_agent_command requires."""
    script = (
        tmp_home_no_env / "skills" / "communication"
        / "hello" / "scripts" / "run.py"
    )
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text("#!/usr/bin/env python3\nprint('Recordatorio · 09:00 — comprar pan')\n")
    script.chmod(0o755)
    return script


def test_event_carries_script_stdout_as_reply(
    monkeypatch, tmp_home_no_env: Path, _trivial_skill_script: Path,
) -> None:
    """no_agent + notify false → `reply` is the script's clean stdout (the abby reminder path)."""

    class _Proc:
        returncode = 0
        stdout = "⏰ Recordatorio · 09:00 — comprar pan\n"
        stderr = ""

    monkeypatch.setattr(scheduler.subprocess, "run", lambda *a, **kw: _Proc())
    emits = _capture_emit(monkeypatch)

    _seed_job(tmp_home_no_env, {
        "id": "rem", "kind": "cron", "expression": "* * * * *",
        "no_agent": True,
        "prompt": f"python3 {_trivial_skill_script}",
        "last_run_at": None,
    })
    scheduler.tick(tmp_home_no_env)

    payload = [e for e in emits if e[0] == "schedule.done"][0][1]
    assert payload["reply"] == "⏰ Recordatorio · 09:00 — comprar pan"
    assert payload["message"].startswith("silent run ok")


def test_event_reply_empty_for_silent_script_with_no_stdout(
    monkeypatch, tmp_home_no_env: Path, _trivial_skill_script: Path,
) -> None:
    """no_agent script with empty stdout → `reply` empty AND `silent=True` so clients fully suppress."""

    class _Proc:
        returncode = 0
        stdout = ""
        stderr = ""

    monkeypatch.setattr(scheduler.subprocess, "run", lambda *a, **kw: _Proc())
    emits = _capture_emit(monkeypatch)

    _seed_job(tmp_home_no_env, {
        "id": "rem", "kind": "cron", "expression": "* * * * *",
        "no_agent": True,
        "prompt": f"python3 {_trivial_skill_script}",
        "last_run_at": None,
    })
    scheduler.tick(tmp_home_no_env)

    payload = [e for e in emits if e[0] == "schedule.done"][0][1]
    assert payload["reply"] == ""
    assert payload["message"] == "silent run ok"
    assert payload["silent"] is True
    assert payload["delivered_to"] == ""


def test_notify_true_delivers_native_inbox_without_gateway(
    monkeypatch, tmp_home_no_env: Path,
) -> None:
    """`notify: true` delivers a native inbox notification — no gateway,
    no chat_id, no "no chat_id and no default" failure."""

    class _Proc:
        returncode = 0
        stdout = _events_stdout([{"kind": "reply", "text": "standup at 10"}])
        stderr = ""

    monkeypatch.setattr(scheduler.subprocess, "run", lambda *a, **kw: _Proc())
    emits = _capture_emit(monkeypatch)
    _seed_job(tmp_home_no_env, {
        "id": "remind", "kind": "cron", "expression": "* * * * *",
        "prompt": "remind me", "notify": True, "last_run_at": None,
    })

    scheduler.tick(tmp_home_no_env)

    done = [p for k, p in emits if k == "schedule.done"]
    assert len(done) == 1
    payload = done[0]
    assert payload["delivered_to"] == "alpi"
    assert payload["reply"] == "standup at 10"
    assert "no chat_id" not in payload["message"]
    assert payload.get("output_id")  # a native inbox output was filed
    assert any(k == "output.created" for k, _ in emits)
