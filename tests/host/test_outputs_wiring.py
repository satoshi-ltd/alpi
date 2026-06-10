"""Output creation hooks in send_message and scheduler.run."""

from __future__ import annotations

from pathlib import Path

from alpi import outputs as outputs_mod
from alpi.gateway import delivery
from alpi.host import events as host_events
from alpi.scheduler import run as sched_run
from alpi.tools.notify import Notify
from alpi.tools.send_message import SendMessage


def _capture(monkeypatch) -> list[tuple[str, dict]]:
    captured: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        host_events, "emit",
        lambda kind, data=None: captured.append((kind, dict(data or {}))),
    )
    return captured


def _profile_home(tmp_path: Path, name: str) -> Path:
    h = tmp_path / "profiles" / name
    h.mkdir(parents=True)
    return h


def test_notify_creates_output(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    events = _capture(monkeypatch)

    result = Notify().run(text="ping", title="hi")
    assert result.ok, result.error

    items = outputs_mod.list_outputs(tmp_path)
    assert len(items) == 1
    out = items[0]
    assert out["source"] == "send_message"
    assert out["body"] == "ping"
    assert "title" not in out
    assert out["delivered_to"] == ["alpi"]
    assert out["status"] == "unread"

    msg = next(d for k, d in events if k == "agent.message")
    assert msg["output_id"] == out["id"]
    assert msg["deep_link"] == f"/outputs/{out['profile']}/{out['id']}"
    created = next(d for k, d in events if k == "output.created")
    assert created["id"] == out["id"]
    assert created["source"] == "send_message"


def test_send_message_gateway_only_creates_output(
    monkeypatch, tmp_path: Path,
) -> None:
    """Gateway-only path still files a row in the inbox — the message went out, the user should be able to see it later."""
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_IDS", "42")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "x")
    events = _capture(monkeypatch)
    monkeypatch.setattr(
        delivery, "send_to",
        lambda *a, **kw: None,
    )

    SendMessage().run(text="hi", channel="telegram", chat_id="42")

    items = outputs_mod.list_outputs(tmp_path)
    assert len(items) == 1
    assert items[0]["delivered_to"] == ["telegram"]
    assert items[0]["body"] == "hi"
    assert [k for k, _ in events if k == "agent.message"] == []


def test_send_message_attachment_only_creates_no_output(
    monkeypatch, tmp_path: Path,
) -> None:
    """Voice-note path: empty text + attachment → audio reaches Telegram, no inbox row."""
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_IDS", "42")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "x")
    _capture(monkeypatch)
    monkeypatch.setattr(delivery, "send_to", lambda *a, **kw: None)

    audio = tmp_path / "clip.ogg"
    audio.write_bytes(b"OggS")

    result = SendMessage().run(
        text="", channel="telegram", chat_id="42", attachment=str(audio),
    )
    assert result.ok, result.error
    assert outputs_mod.list_outputs(tmp_path) == []


def test_send_message_failed_gateway_only_creates_no_output(
    monkeypatch, tmp_path: Path,
) -> None:
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_IDS", "42")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "x")
    _capture(monkeypatch)

    def boom(*a, **kw):
        raise delivery.DeliveryError("telegram down")
    monkeypatch.setattr(delivery, "send_to", boom)

    result = SendMessage().run(text="hi", channel="telegram", chat_id="42")
    assert not result.ok
    assert outputs_mod.list_outputs(tmp_path) == []


def test_notify_suppressed_in_schedule_child_no_output(
    monkeypatch, tmp_path: Path,
) -> None:
    """Schedule child defers output creation to the parent so output_id stays attached to the agent.message that actually reaches the user."""
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    monkeypatch.setenv("ALPI_SCHEDULE_CHILD", "1")
    monkeypatch.setenv("ALPI_PARENT_EMITS_AGENT_MESSAGE", "1")
    events = _capture(monkeypatch)

    result = Notify().run(text="ping")
    assert result.ok
    assert [k for k, _ in events if k == "agent.message"] == []
    assert outputs_mod.list_outputs(tmp_path) == []


def test_send_message_gateway_only_suppressed_in_schedule_child(
    monkeypatch, tmp_path: Path,
) -> None:
    """Same rule for gateway-only — the parent owns output creation, otherwise the child writes a row the parent never references."""
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    monkeypatch.setenv("ALPI_SCHEDULE_CHILD", "1")
    monkeypatch.setenv("ALPI_PARENT_EMITS_AGENT_MESSAGE", "1")
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_IDS", "42")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "x")
    _capture(monkeypatch)
    monkeypatch.setattr(delivery, "send_to", lambda *a, **kw: None)

    result = SendMessage().run(text="hi", channel="telegram", chat_id="42")
    assert result.ok
    assert outputs_mod.list_outputs(tmp_path) == []


def test_scheduler_failed_creates_output(
    tmp_path: Path, monkeypatch,
) -> None:
    home = _profile_home(tmp_path, "rex")
    sched_dir = home / "schedule"
    sched_dir.mkdir()
    (sched_dir / "jobs.json").write_text(
        '[{"id":"j-fail","kind":"cron","expression":"* * * * *","prompt":"x"}]'
    )
    events = _capture(monkeypatch)
    monkeypatch.setattr(
        sched_run, "run_job",
        lambda job, h: sched_run.JobOutcome(False, "boom"),
    )

    sched_run.tick(home)

    items = outputs_mod.list_outputs(home)
    assert len(items) == 1
    out = items[0]
    assert out["source"] == "schedule"
    assert out["source_id"] == "j-fail"
    assert out["type"] == "error"
    assert out["delivered_to"] == []
    assert out["body"] == "boom"

    failed = next(d for k, d in events if k == "schedule.failed")
    assert failed["output_id"] == out["id"]
    assert failed["deep_link"] == f"/outputs/{out['profile']}/{out['id']}"


def test_scheduler_done_silent_maintenance_creates_no_output(
    tmp_path: Path, monkeypatch,
) -> None:
    """Silent jobs (notify: false, no stdout) leave no inbox row — they're true noise, not state worth revisiting."""
    home = _profile_home(tmp_path, "ok")
    sched_dir = home / "schedule"
    sched_dir.mkdir()
    (sched_dir / "jobs.json").write_text(
        '[{"id":"j-ok","kind":"cron","expression":"* * * * *","prompt":"x"}]'
    )
    events = _capture(monkeypatch)
    monkeypatch.setattr(
        sched_run, "run_job",
        lambda job, h: sched_run.JobOutcome(True, "ran", silent=True),
    )

    sched_run.tick(home)

    assert outputs_mod.list_outputs(home) == []
    done = next(d for k, d in events if k == "schedule.done")
    assert "output_id" not in done


def test_scheduler_done_notify_creates_output(
    tmp_path: Path, monkeypatch,
) -> None:
    """notify: true pushes the reply to the owner's apps — the scheduler files an inbox row (delivered_to=["alpi"]) and emits agent.message."""
    home = _profile_home(tmp_path, "mirai")
    sched_dir = home / "schedule"
    sched_dir.mkdir()
    (sched_dir / "jobs.json").write_text(
        '[{"id":"daily","kind":"cron","expression":"* * * * *","prompt":"x","notify":true}]'
    )
    events = _capture(monkeypatch)
    monkeypatch.setattr(
        sched_run, "run_job",
        lambda job, h: sched_run.JobOutcome(
            True, "notified",
            reply="Daily summary · 5 open PRs",
            delivered_to="alpi",
        ),
    )

    sched_run.tick(home)

    items = outputs_mod.list_outputs(home)
    assert len(items) == 1
    out = items[0]
    assert out["source"] == "schedule"
    assert out["source_id"] == "daily"
    assert out["body"] == "Daily summary · 5 open PRs"
    assert out["delivered_to"] == ["alpi"]
    assert out["type"] == "info"

    done = next(d for k, d in events if k == "schedule.done")
    assert done["output_id"] == out["id"]
    assert done["deep_link"] == f"/outputs/mirai/{out['id']}"

    msg = next(d for k, d in events if k == "agent.message")
    assert msg["output_id"] == out["id"]
    assert msg["body"] == "Daily summary · 5 open PRs"


def test_scheduler_done_stdout_only_creates_no_output(
    tmp_path: Path, monkeypatch,
) -> None:
    """Stdout-only summary (notify: false, no send_message) is not user-facing → no inbox row."""
    home = _profile_home(tmp_path, "ops")
    sched_dir = home / "schedule"
    sched_dir.mkdir()
    (sched_dir / "jobs.json").write_text(
        '[{"id":"reindex","kind":"cron","expression":"* * * * *","prompt":"x"}]'
    )
    events = _capture(monkeypatch)
    monkeypatch.setattr(
        sched_run, "run_job",
        lambda job, h: sched_run.JobOutcome(
            True, "silent run ok: indexed 12 files",
            reply="indexed 12 files",
            delivered_to="",
        ),
    )

    sched_run.tick(home)

    assert outputs_mod.list_outputs(home) == []
    done = next(d for k, d in events if k == "schedule.done")
    assert "output_id" not in done


def test_scheduler_emits_event_even_when_outputs_append_fails(
    tmp_path: Path, monkeypatch,
) -> None:
    """Persistence is opportunistic — disk-full must not swallow the schedule.failed event."""
    home = _profile_home(tmp_path, "fragile")
    sched_dir = home / "schedule"
    sched_dir.mkdir()
    (sched_dir / "jobs.json").write_text(
        '[{"id":"j-x","kind":"cron","expression":"* * * * *","prompt":"x"}]'
    )
    events = _capture(monkeypatch)
    monkeypatch.setattr(
        sched_run, "run_job",
        lambda job, h: sched_run.JobOutcome(False, "boom"),
    )

    def _explode(*_a, **_kw):
        raise OSError("disk full")
    monkeypatch.setattr(outputs_mod, "append", _explode)

    sched_run.tick(home)

    failed = next(d for k, d in events if k == "schedule.failed")
    assert failed["job_id"] == "j-x"
    assert "output_id" not in failed


def test_scheduler_done_send_message_path_does_not_duplicate_output(
    tmp_path: Path, monkeypatch,
) -> None:
    """delivered_to="external" means send_message already filed; schedule.done must not duplicate."""
    home = _profile_home(tmp_path, "abby")
    sched_dir = home / "schedule"
    sched_dir.mkdir()
    (sched_dir / "jobs.json").write_text(
        '[{"id":"brief","kind":"cron","expression":"* * * * *","prompt":"x"}]'
    )
    events = _capture(monkeypatch)
    monkeypatch.setattr(
        sched_run, "run_job",
        lambda job, h: sched_run.JobOutcome(
            True,
            "agent delivered via send_message; no duplicate reply pushed",
            delivered_to="external",
        ),
    )

    sched_run.tick(home)

    assert outputs_mod.list_outputs(home) == []
    done = next(d for k, d in events if k == "schedule.done")
    assert "output_id" not in done


def test_scheduler_send_message_creates_one_output(
    tmp_path: Path, monkeypatch,
) -> None:
    """Job that called send_message → parent files the output; schedule.done must not duplicate."""
    home = _profile_home(tmp_path, "atlas")
    sched_dir = home / "schedule"
    sched_dir.mkdir()
    (sched_dir / "jobs.json").write_text(
        '[{"id":"j-msg","kind":"cron","expression":"* * * * *","prompt":"x"}]'
    )
    events = _capture(monkeypatch)

    def _run_job(job, h):
        sched_run._emit_agent_messages(h, [{
            "text": "hi", "title": "from cron",
            "channel": "alpi", "type": "info",
        }])
        return sched_run.JobOutcome(
            True, "agent delivered via send_message; no duplicate reply pushed",
            delivered_to="external",
        )
    monkeypatch.setattr(sched_run, "run_job", _run_job)

    sched_run.tick(home)

    items = outputs_mod.list_outputs(home)
    assert len(items) == 1
    out = items[0]
    assert out["source"] == "send_message"
    assert out["body"] == "hi"
    assert out["delivered_to"] == ["alpi"]

    msgs = [d for k, d in events if k == "agent.message"]
    assert len(msgs) == 1
    assert msgs[0]["output_id"] == out["id"]
    assert msgs[0]["deep_link"] == f"/outputs/atlas/{out['id']}"
    done = next(d for k, d in events if k == "schedule.done")
    assert "output_id" not in done


def test_normalize_gateway_only_send_message_args() -> None:
    """Gateway-only call: channel=telegram → delivered_to=["telegram"]."""
    msg = outputs_mod.normalize_send_message_args({
        "text": "hi", "channel": "telegram", "chat_id": "1",
    })
    assert msg is not None
    assert msg["channel"] == "telegram"
    assert msg["delivered_to"] == ["telegram"]


def test_normalize_both_with_platform() -> None:
    msg = outputs_mod.normalize_send_message_args({
        "text": "hi", "channel": "both", "platform": "telegram",
    })
    assert msg is not None
    assert msg["channel"] == "both"
    assert msg["delivered_to"] == ["alpi", "telegram"]


def test_normalize_drops_empty_text() -> None:
    assert outputs_mod.normalize_send_message_args({"text": "  "}) is None


def test_normalize_rejects_bogus_channel() -> None:
    assert outputs_mod.normalize_send_message_args({
        "text": "ok", "channel": "signal",
    }) is None


def test_scheduler_gateway_only_creates_output_without_agent_message(
    tmp_path: Path, monkeypatch,
) -> None:
    """Gateway-only from a child: parent files the output but no agent.message — child already pushed downstream."""
    home = _profile_home(tmp_path, "ada")
    events = _capture(monkeypatch)

    sched_run._emit_agent_messages(home, [{
        "text": "hi", "channel": "telegram", "chat_id": "1",
    }])

    items = outputs_mod.list_outputs(home)
    assert len(items) == 1
    assert items[0]["delivered_to"] == ["telegram"]
    assert items[0]["body"] == "hi"
    assert [k for k, _ in events if k == "agent.message"] == []
    assert [k for k, _ in events if k == "output.created"] == ["output.created"]


def test_scheduler_both_records_full_delivered_to(
    tmp_path: Path, monkeypatch,
) -> None:
    """channel="both" → one output with delivered_to=["alpi", gateway] AND the agent.message."""
    home = _profile_home(tmp_path, "ada")
    events = _capture(monkeypatch)

    sched_run._emit_agent_messages(home, [{
        "text": "x", "title": "t", "channel": "both", "platform": "telegram",
    }])

    items = outputs_mod.list_outputs(home)
    assert len(items) == 1
    out = items[0]
    assert out["delivered_to"] == ["alpi", "telegram"]

    msgs = [d for k, d in events if k == "agent.message"]
    assert len(msgs) == 1
    assert msgs[0]["output_id"] == out["id"]
    assert msgs[0]["deep_link"] == f"/outputs/ada/{out['id']}"


def test_every_output_id_event_carries_profile_in_deep_link(
    tmp_path: Path, monkeypatch,
) -> None:
    """Every output_id-carrying event must ship a profile-scoped deep_link."""
    home = _profile_home(tmp_path, "vera")
    sched_dir = home / "schedule"
    sched_dir.mkdir()
    (sched_dir / "jobs.json").write_text(
        '[{"id":"j-bad","kind":"cron","expression":"* * * * *","prompt":"x"}]'
    )
    events = _capture(monkeypatch)

    def _run_job(job, h):
        sched_run._emit_agent_messages(h, [{
            "text": "ok", "title": "t", "channel": "alpi",
        }])
        return sched_run.JobOutcome(False, "boom")
    monkeypatch.setattr(sched_run, "run_job", _run_job)

    sched_run.tick(home)

    carriers = [d for _, d in events if d.get("output_id")]
    assert carriers, "no events with output_id captured"
    for payload in carriers:
        assert payload.get("deep_link", "").startswith("/outputs/vera/")
        assert payload["deep_link"].endswith(payload["output_id"])
