"""Pin the structured payload of `schedule.done` / `schedule.failed`: `reply`, `delivered_to`, and `silent` are populated correctly across every branch (agent vs no_agent, platform vs silent, success vs failure, send_message dedup, oversized reply cap)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from alpi.gateway import delivery
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
        "prompt": "reindex", "platform": "", "chat_id": "", "last_run_at": None,
    })

    scheduler.tick(tmp_home_no_env)

    schedule_events = [e for e in emits if e[0] == "schedule.done"]
    assert len(schedule_events) == 1
    _, payload = schedule_events[0]
    assert payload["reply"] == "indexed 12 files"
    assert "silent run ok" in payload["message"]
    assert payload["silent"] is False
    assert payload["delivered_to"] == ""


def test_event_carries_agent_reply_when_platform_delivered(
    monkeypatch, tmp_home_no_env: Path,
) -> None:
    """Platform-delivered job → `reply` mirrors the gateway text, `delivered_to` names the channel for client-side dedup."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "x")
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_IDS", "1")

    class _Proc:
        returncode = 0
        stdout = _events_stdout([{"kind": "reply", "text": "hola"}])
        stderr = ""

    monkeypatch.setattr(scheduler.subprocess, "run", lambda *a, **kw: _Proc())
    monkeypatch.setattr(delivery, "send_to", lambda *a, **kw: None)
    emits = _capture_emit(monkeypatch)

    _seed_job(tmp_home_no_env, {
        "id": "greet", "kind": "cron", "expression": "* * * * *",
        "prompt": "say hi", "platform": "telegram", "chat_id": "1",
        "last_run_at": None,
    })
    scheduler.tick(tmp_home_no_env)

    payload = [e for e in emits if e[0] == "schedule.done"][0][1]
    assert payload["reply"] == "hola"
    assert "telegram:1" in payload["message"]
    assert payload["delivered_to"] == "telegram"
    assert payload["silent"] is False


def test_event_reply_empty_when_send_message_handled_delivery(
    monkeypatch, tmp_home_no_env: Path,
) -> None:
    """Agent self-delivered via send_message → `reply` empty, `delivered_to`="external" so clients don't re-notify."""

    class _Proc:
        returncode = 0
        stdout = _events_stdout([
            {"kind": "tool_start", "name": "send_message"},
            {"kind": "tool_end", "name": "send_message", "ok": True},
            {"kind": "reply", "text": "ya enviado"},
        ])
        stderr = ""

    monkeypatch.setattr(scheduler.subprocess, "run", lambda *a, **kw: _Proc())
    emits = _capture_emit(monkeypatch)

    _seed_job(tmp_home_no_env, {
        "id": "self", "kind": "cron", "expression": "* * * * *",
        "prompt": "post", "platform": "telegram", "chat_id": "1",
        "last_run_at": None,
    })
    scheduler.tick(tmp_home_no_env)

    payload = [e for e in emits if e[0] == "schedule.done"][0][1]
    assert payload["reply"] == ""
    assert "send_message" in payload["message"]
    assert payload["delivered_to"] == "external"
    assert payload["silent"] is False


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
        "prompt": "fail", "platform": "", "chat_id": "", "last_run_at": None,
    })
    scheduler.tick(tmp_home_no_env)

    failed = [e for e in emits if e[0] == "schedule.failed"]
    assert len(failed) == 1
    payload = failed[0][1]
    assert payload["reply"] == ""
    assert "rc=" in payload["message"]


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
        "prompt": "verbose", "platform": "", "chat_id": "", "last_run_at": None,
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
    """no_agent + no platform → `reply` is the script's clean stdout (the abby reminder path)."""

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
        "platform": "", "chat_id": "", "last_run_at": None,
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
        "platform": "", "chat_id": "", "last_run_at": None,
    })
    scheduler.tick(tmp_home_no_env)

    payload = [e for e in emits if e[0] == "schedule.done"][0][1]
    assert payload["reply"] == ""
    assert payload["message"] == "silent run ok"
    assert payload["silent"] is True
    assert payload["delivered_to"] == ""
