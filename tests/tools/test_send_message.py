"""Tests for the send_message tool + delivery helpers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from alpi.gateway import delivery
from alpi.tools.send_message import SendMessage


def test_allowed_chat_ids_and_default(monkeypatch) -> None:
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_IDS", " 123 , 456, 123")
    assert delivery.allowed_chat_ids("telegram") == ["123", "456"]
    assert delivery.default_chat_id("telegram") == "123"

    monkeypatch.delenv("TELEGRAM_ALLOWED_CHAT_IDS", raising=False)
    assert delivery.allowed_chat_ids("telegram") == []
    assert delivery.default_chat_id("telegram") is None


def test_send_to_rejects_non_allowlist(monkeypatch) -> None:
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_IDS", "123")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "x")
    with pytest.raises(delivery.DeliveryError, match="not in"):
        delivery.send_to("telegram", "999", "hi")


def test_send_to_unknown_platform(monkeypatch) -> None:
    monkeypatch.setenv("SLACK_ALLOWED_CHAT_IDS", "C01")
    with pytest.raises(delivery.DeliveryError, match="unknown platform"):
        delivery.send_to("slack", "C01", "hi")


def test_send_to_empty_text(monkeypatch) -> None:
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_IDS", "123")
    with pytest.raises(delivery.DeliveryError, match="empty"):
        delivery.send_to("telegram", "123", "   ")


def test_send_to_telegram_posts(monkeypatch) -> None:
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_IDS", "123")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "TOKEN")

    captured = []

    class _FakeResp:
        status_code = 200
        text = ""

    class _FakeClient:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, url, json):  # noqa: A002
            captured.append((url, json))
            return _FakeResp()

    with patch.object(delivery, "httpx") as fake_httpx:
        fake_httpx.Client = _FakeClient
        delivery.send_to("telegram", "123", "hello")

    assert len(captured) == 1
    url, body = captured[0]
    assert url.endswith("/bot TOKEN/sendMessage".replace(" ", ""))
    assert body == {"chat_id": "123", "text": "hello"}


def test_send_to_telegram_splits_long_messages(monkeypatch) -> None:
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_IDS", "123")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "TOKEN")

    posts = []

    class _FakeResp:
        status_code = 200
        text = ""

    class _FakeClient:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, url, json):  # noqa: A002
            posts.append(json["text"])
            return _FakeResp()

    with patch.object(delivery, "httpx") as fake_httpx:
        fake_httpx.Client = _FakeClient
        delivery.send_to("telegram", "123", "x" * (delivery.TELEGRAM_MAX_CHARS + 10))

    assert len(posts) == 2
    assert len(posts[0]) == delivery.TELEGRAM_MAX_CHARS


def _capture_events(monkeypatch) -> list[tuple[str, dict]]:
    captured: list[tuple[str, dict]] = []
    from alpi.host import events as host_events
    monkeypatch.setattr(
        host_events, "emit",
        lambda kind, data=None: captured.append((kind, dict(data or {}))),
    )
    return captured


def test_send_message_default_channel_alpi_emits_event_no_gateway(
    monkeypatch, tmp_path: Path,
) -> None:
    """The strategic default: alpi-native delivery via the host event
    stream. No gateway config required — works on a fresh profile with
    zero Telegram / IMAP setup."""
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    events = _capture_events(monkeypatch)
    gateway_calls: list = []
    monkeypatch.setattr(
        delivery, "send_to",
        lambda *a, **kw: gateway_calls.append(("send_to", a, kw)),
    )

    result = SendMessage().run(text="ping")
    assert result.ok, result.error
    assert "alpi" in result.output

    agent_msgs = [d for k, d in events if k == "agent.message"]
    assert len(agent_msgs) == 1
    assert agent_msgs[0]["body"] == "ping"
    assert agent_msgs[0]["severity"] == "normal"
    assert agent_msgs[0]["kind"] == "result"
    assert gateway_calls == []


def test_send_message_alpi_uses_title_and_severity(
    monkeypatch, tmp_path: Path,
) -> None:
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    events = _capture_events(monkeypatch)

    result = SendMessage().run(
        text="Don't forget the standup at 10:30",
        title="Meeting in 10 min",
        severity="important",
        kind="reminder",
    )
    assert result.ok, result.error
    msg = next(d for k, d in events if k == "agent.message")
    assert msg["title"] == "Meeting in 10 min"
    assert msg["severity"] == "important"
    assert msg["kind"] == "reminder"


def test_send_message_attaches_active_session(
    monkeypatch, tmp_path: Path,
) -> None:
    """When the Engine has bound an active session via ``set_active_session``, the alpi-channel event carries ``session_id`` + ``deep_link`` so the mobile/desktop notification tap routes back to the right chat — not the inbox."""
    from alpi.home import reset_active_session, set_active_session

    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    events = _capture_events(monkeypatch)

    token = set_active_session("sess-abc-123")
    try:
        result = SendMessage().run(text="task done")
    finally:
        reset_active_session(token)

    assert result.ok, result.error
    msg = next(d for k, d in events if k == "agent.message")
    assert msg["session_id"] == "sess-abc-123"
    assert msg["deep_link"] == "/chat/sess-abc-123"


def test_send_message_omits_session_when_not_bound(
    monkeypatch, tmp_path: Path,
) -> None:
    """No active session (e.g. a one-shot ``alpi -c`` invocation) → no session_id / deep_link in the payload. Mobile / desktop fall back to a generic profile-level route."""
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    events = _capture_events(monkeypatch)

    result = SendMessage().run(text="ping")
    assert result.ok, result.error
    msg = next(d for k, d in events if k == "agent.message")
    assert "session_id" not in msg
    assert "deep_link" not in msg


def test_send_message_channel_telegram_only_dispatches_gateway(
    monkeypatch, tmp_path: Path,
) -> None:
    """``channel="telegram"`` is the explicit opt-in path. No alpi-native
    event fires — the user asked specifically for Telegram."""
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_IDS", "42")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "x")
    events = _capture_events(monkeypatch)
    calls: list = []
    monkeypatch.setattr(
        delivery, "send_to",
        lambda p, c, t, attachment=None, env=None: calls.append((p, c, t, attachment)),
    )

    result = SendMessage().run(text="hi", channel="telegram", chat_id="42")
    assert result.ok, result.error
    assert calls == [("telegram", "42", "hi", None)]
    assert [k for k, _ in events if k == "agent.message"] == []


def test_send_message_channel_both_emits_event_and_gateway(
    monkeypatch, tmp_path: Path,
) -> None:
    """``channel="both"`` is the redundancy mode for users who want
    overlap: alpi-native delivery for the paired app AND a gateway
    dispatch for belt-and-suspenders."""
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_IDS", "42")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "x")
    events = _capture_events(monkeypatch)
    calls: list = []
    monkeypatch.setattr(
        delivery, "send_to",
        lambda p, c, t, attachment=None, env=None: calls.append((p, c, t, attachment)),
    )

    result = SendMessage().run(
        text="hi", channel="both", platform="telegram", chat_id="42",
    )
    assert result.ok, result.error
    assert calls == [("telegram", "42", "hi", None)]
    assert [k for k, _ in events if k == "agent.message"] == ["agent.message"]
    assert "alpi" in result.output and "telegram" in result.output


def test_send_message_channel_both_tolerates_gateway_failure(
    monkeypatch, tmp_path: Path,
) -> None:
    """If the alpi channel succeeded, a gateway dispatch failure should
    NOT fail the whole call — the user already got the notification on
    their paired app. Only fail when alpi is not the channel."""
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_IDS", "42")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "x")
    _capture_events(monkeypatch)

    def boom(*a, **kw):
        raise delivery.DeliveryError("telegram down")
    monkeypatch.setattr(delivery, "send_to", boom)

    result = SendMessage().run(
        text="hi", channel="both", platform="telegram", chat_id="42",
    )
    assert result.ok, result.error
    assert "telegram(failed" in result.output


def test_send_message_gateway_only_fails_when_no_chat_id(
    monkeypatch, tmp_path: Path,
) -> None:
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    monkeypatch.delenv("TELEGRAM_ALLOWED_CHAT_IDS", raising=False)
    result = SendMessage().run(text="hi", channel="telegram")
    assert not result.ok
    assert "no chat_id" in result.error


def test_send_message_rejects_invalid_channel(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    result = SendMessage().run(text="hi", channel="signal")
    assert not result.ok
    assert "invalid channel" in result.error


def test_send_message_rejects_invalid_both_platform(
    monkeypatch, tmp_path: Path,
) -> None:
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    result = SendMessage().run(text="hi", channel="both", platform="signal")
    assert not result.ok
    assert "invalid gateway platform" in result.error


def test_send_message_rejects_invalid_severity(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    result = SendMessage().run(text="hi", severity="ULTRA")
    assert not result.ok
    assert "invalid severity" in result.error


def test_send_message_rejects_invalid_kind(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    result = SendMessage().run(text="hi", kind="wibble")
    assert not result.ok
    assert "invalid kind" in result.error


def test_send_message_rejects_empty_text_without_attachment(
    monkeypatch, tmp_path: Path,
) -> None:
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    result = SendMessage().run(text="")
    assert not result.ok
    assert "empty" in result.error


def test_send_message_alpi_requires_text_even_with_attachment(
    monkeypatch, tmp_path: Path,
) -> None:
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    audio = tmp_path / "clip.ogg"
    audio.write_bytes(b"OggS")
    result = SendMessage().run(text="", channel="alpi", attachment=str(audio))
    assert not result.ok
    assert "alpi channel requires non-empty text" in result.error


def test_send_message_attachment_only_via_gateway(
    monkeypatch, tmp_path: Path,
) -> None:
    """Voice-note flow: ``tts(format=ogg)`` → ``send_message(channel="telegram", attachment=...)``. Local notifications don't carry attachments, so attachment-only delivery goes via gateway."""
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_IDS", "42")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "x")
    audio = tmp_path / "clip.ogg"
    audio.write_bytes(b"OggS")
    calls = []
    monkeypatch.setattr(
        delivery, "send_to",
        lambda p, c, t, attachment=None, env=None: calls.append(
            (p, c, t, attachment),
        ),
    )

    result = SendMessage().run(
        text="", channel="telegram", attachment=str(audio),
    )
    assert result.ok, result.error
    assert calls[0][3] == str(audio)


def test_send_message_gateway_uses_profile_env(
    monkeypatch, tmp_path: Path,
) -> None:
    """Multi-profile env scoping still holds: when an explicit gateway
    channel is used, credentials come from the active profile's .env, not
    process env. Reproduces the multi-profile leak fix."""
    monkeypatch.delenv("TELEGRAM_ALLOWED_CHAT_IDS", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)

    home = tmp_path / "profile"
    home.mkdir()
    (home / ".env").write_text(
        "TELEGRAM_ALLOWED_CHAT_IDS=77\nTELEGRAM_BOT_TOKEN=tok\n"
    )

    from alpi.home import reset_active_home, set_active_home
    captured: dict = {}

    def fake_send(platform, chat_id, text, attachment=None, env=None):
        captured["chat"] = chat_id
        captured["env"] = env

    monkeypatch.setattr(delivery, "send_to", fake_send)
    token = set_active_home(home)
    try:
        result = SendMessage().run(text="ping", channel="telegram")
    finally:
        reset_active_home(token)

    assert result.ok, result.error
    assert captured["chat"] == "77"
    assert captured["env"].get("TELEGRAM_BOT_TOKEN") == "tok"


def test_send_to_attachment_missing_file(monkeypatch) -> None:
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_IDS", "42")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "x")
    with pytest.raises(delivery.DeliveryError, match="attachment not found"):
        delivery.send_to("telegram", "42", "", attachment="/nope/missing.ogg")


def test_send_to_attachment_picks_voice_endpoint(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_IDS", "42")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "TOKEN")
    audio = tmp_path / "speak.ogg"
    audio.write_bytes(b"OggS\x00" * 8)

    captured: list = []

    class _FakeResp:
        status_code = 200
        text = ""

    class _FakeClient:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, url, data=None, files=None, json=None):  # noqa: A002
            captured.append({"url": url, "data": data, "files": files, "json": json})
            return _FakeResp()

    with patch.object(delivery, "httpx") as fake_httpx:
        fake_httpx.Client = _FakeClient
        delivery.send_to("telegram", "42", "caption", attachment=str(audio))

    assert len(captured) == 1
    assert captured[0]["url"].endswith("/sendVoice")
    assert captured[0]["data"] == {"chat_id": "42", "caption": "caption"}
    assert "voice" in captured[0]["files"]


def test_send_to_attachment_picks_photo_endpoint(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_IDS", "42")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "TOKEN")
    img = tmp_path / "pic.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 20)

    captured: list = []

    class _FakeResp:
        status_code = 200
        text = ""

    class _FakeClient:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self): return self

        def __exit__(self, *a): return False

        def post(self, url, data=None, files=None, json=None):  # noqa: A002
            captured.append(url)
            return _FakeResp()

    with patch.object(delivery, "httpx") as fake_httpx:
        fake_httpx.Client = _FakeClient
        delivery.send_to("telegram", "42", "", attachment=str(img))

    assert captured[0].endswith("/sendPhoto")


def test_send_to_email_rejects_attachment(monkeypatch) -> None:
    monkeypatch.setenv("IMAP_ALLOWED_SENDERS", "a@b.com")
    with pytest.raises(delivery.DeliveryError, match="attachment on email"):
        delivery.send_to("email", "a@b.com", "hi", attachment="/tmp/x.ogg")
