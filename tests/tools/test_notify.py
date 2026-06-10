"""notify tool — native push to the owner's apps via the alpi-emit helpers."""

from __future__ import annotations

from pathlib import Path

from alpi.tools import get
from alpi.tools.notify import Notify


def _capture_events(monkeypatch) -> list[tuple[str, dict]]:
    captured: list[tuple[str, dict]] = []
    from alpi.host import events as host_events
    monkeypatch.setattr(
        host_events, "emit",
        lambda kind, data=None: captured.append((kind, dict(data or {}))),
    )
    return captured


def test_notify_is_registered() -> None:
    assert get("notify") is Notify


def test_notify_files_native_output_with_type(monkeypatch) -> None:
    captured: dict = {}

    def fake_emit(**kw):
        captured.update(kw)
        return "out-id"

    monkeypatch.setattr("alpi.tools.notify._suppress_native_emit", lambda: False)
    monkeypatch.setattr("alpi.tools.notify.create_output_and_emit_message", fake_emit)
    r = Notify().run(text="standup at 10", title="Reminder", type="error")
    assert r.ok
    assert r.output == "delivered: alpi"
    assert captured["text"] == "standup at 10"
    assert captured["title"] == "Reminder"
    assert captured["type"] == "error"
    assert captured["delivered_to"] == ["alpi"]


def test_notify_invalid_type_falls_back_to_info(monkeypatch) -> None:
    captured: dict = {}
    monkeypatch.setattr("alpi.tools.notify._suppress_native_emit", lambda: False)
    monkeypatch.setattr(
        "alpi.tools.notify.create_output_and_emit_message",
        lambda **kw: captured.update(kw) or "out-id",
    )
    Notify().run(text="hi", type="ULTRA")
    assert captured["type"] == "info"


def test_notify_emits_agent_message_with_type(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    events = _capture_events(monkeypatch)
    result = Notify().run(text="ping", title="Heads up", type="warning")
    assert result.ok, result.error
    msg = next(d for k, d in events if k == "agent.message")
    assert msg["body"] == "ping"
    assert msg["title"] == "Heads up"
    assert msg["type"] == "warning"
    assert msg["deep_link"] == f"/outputs/{msg['profile']}/{msg['output_id']}"


def test_notify_attaches_active_session(monkeypatch, tmp_path: Path) -> None:
    from alpi.home import reset_active_session, set_active_session

    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    events = _capture_events(monkeypatch)
    token = set_active_session("sess-abc-123")
    try:
        result = Notify().run(text="task done")
    finally:
        reset_active_session(token)
    assert result.ok, result.error
    msg = next(d for k, d in events if k == "agent.message")
    assert msg["session_id"] == "sess-abc-123"
    assert "sess-abc-123" not in msg["deep_link"]


def test_notify_omits_session_when_not_bound(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    events = _capture_events(monkeypatch)
    result = Notify().run(text="ping")
    assert result.ok, result.error
    msg = next(d for k, d in events if k == "agent.message")
    assert "session_id" not in msg
    assert msg["output_id"]
