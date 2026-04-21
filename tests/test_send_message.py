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


def test_send_message_tool_uses_default_chat(monkeypatch) -> None:
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_IDS", "42")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "x")
    called = {}

    def fake_send(platform, chat_id, text):
        called["args"] = (platform, chat_id, text)

    monkeypatch.setattr(delivery, "send_to", fake_send)
    result = SendMessage().run(text="ping")
    assert result.ok
    assert called["args"] == ("telegram", "42", "ping")
    assert "telegram:42" in result.output


def test_send_message_tool_explicit_platform_chat(monkeypatch) -> None:
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_IDS", "42")
    calls = []
    monkeypatch.setattr(
        delivery, "send_to", lambda p, c, t: calls.append((p, c, t)),
    )
    result = SendMessage().run(text="hi", platform="telegram", chat_id="42")
    assert result.ok
    assert calls == [("telegram", "42", "hi")]


def test_send_message_tool_no_allowlist_fails(monkeypatch) -> None:
    monkeypatch.delenv("TELEGRAM_ALLOWED_CHAT_IDS", raising=False)
    result = SendMessage().run(text="hi")
    assert not result.ok
    assert "no chat_id" in result.error
