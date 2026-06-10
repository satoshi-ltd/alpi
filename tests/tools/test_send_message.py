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


def test_send_message_gateway_failure_is_reported(
    monkeypatch, tmp_path: Path,
) -> None:
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_IDS", "42")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "x")

    def boom(*a, **kw):
        raise delivery.DeliveryError("telegram down")
    monkeypatch.setattr(delivery, "send_to", boom)

    result = SendMessage().run(text="hi", channel="telegram", chat_id="42")
    assert not result.ok
    assert "telegram down" in result.error


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


def test_send_message_rejects_empty_text_without_attachment(
    monkeypatch, tmp_path: Path,
) -> None:
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    result = SendMessage().run(text="", channel="telegram")
    assert not result.ok
    assert "empty" in result.error


def test_send_message_attachment_only_via_gateway(
    monkeypatch, tmp_path: Path,
) -> None:
    """Voice-note flow: ``tts(format=ogg)`` → ``send_message(channel="telegram", attachment=...)``. Local notifications don't carry attachments, so attachment-only delivery goes via gateway. ``ALPI_HOME`` isolation is mandatory: ``SendMessage.run`` resolves the home via ``get_home()`` and would otherwise leak into the developer's real ``~/.alpi``."""
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
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
