"""Unit tests for the Gmail REST client. Real OAuth/API hits are out of
scope — we patch the token getter and the HTTP layer and verify the
request shapes + response parsing."""

from __future__ import annotations

import base64
import json
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from alpi.mail import gmail as gmail_mod
from alpi.mail.gmail import GmailClient, GmailError


@pytest.fixture
def client(tmp_path: Path, monkeypatch) -> GmailClient:
    monkeypatch.setattr(
        gmail_mod, "get_access_token",
        lambda _home, _account_id: "fake-access-token",
    )
    return GmailClient(home=tmp_path, account_id="me_gmail_com")


def _mock_response(json_body: dict | None = None, status: int = 200):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = json_body or {}
    r.text = json.dumps(json_body or {})
    return r


def _mock_httpx(get_return=None, post_return=None):
    ctx = MagicMock()
    ctx.__enter__.return_value = ctx
    ctx.__exit__.return_value = None
    ctx.get.return_value = get_return or _mock_response()
    ctx.post.return_value = post_return or _mock_response()
    return ctx


def test_list_inbox_returns_envelopes(client: GmailClient, monkeypatch) -> None:
    ids_response = _mock_response({"messages": [{"id": "msg1"}, {"id": "msg2"}]})
    meta_response_1 = _mock_response({
        "id": "msg1",
        "labelIds": ["INBOX", "UNREAD"],
        "payload": {"headers": [
            {"name": "From", "value": "Alice <a@example.com>"},
            {"name": "To", "value": "me@gmail.com"},
            {"name": "Subject", "value": "Hello"},
            {"name": "Date", "value": "Mon, 22 Apr 2026 09:00:00 +0200"},
        ]},
    })
    meta_response_2 = _mock_response({
        "id": "msg2",
        "labelIds": ["INBOX"],
        "payload": {"headers": [
            {"name": "From", "value": "b@example.com"},
            {"name": "Subject", "value": "Re: something"},
        ]},
    })
    client_ctx = _mock_httpx()
    client_ctx.get.side_effect = [ids_response, meta_response_1, meta_response_2]
    monkeypatch.setattr(gmail_mod.httpx, "Client", lambda **kw: client_ctx)

    envs = client.list(folder="INBOX", limit=10)
    assert len(envs) == 2
    assert envs[0].uid == "msg1"
    assert envs[0].from_ == "Alice <a@example.com>"
    assert envs[0].subject == "Hello"
    assert envs[0].unread is True
    assert envs[1].unread is False


def test_search_builds_gmail_query(client: GmailClient, monkeypatch) -> None:
    captured: dict = {}

    def fake_get(url, headers, params):
        captured["params"] = params
        return _mock_response({"messages": []})

    ctx = _mock_httpx(get_return=_mock_response({"messages": []}))
    ctx.get.side_effect = lambda url, headers, params: (
        captured.update(params=params) or _mock_response({"messages": []})
    )
    monkeypatch.setattr(gmail_mod.httpx, "Client", lambda **kw: ctx)

    client.search(
        folder="INBOX", from_="alice@x.com", subject="report",
        since="2026-01-15", unread_only=True, limit=5,
    )
    q = captured["params"]["q"]
    assert "label:INBOX" in q
    assert "is:unread" in q
    assert 'from:"alice@x.com"' in q
    assert 'subject:"report"' in q
    assert "after:2026/01/15" in q
    assert captured["params"]["maxResults"] == 5


def test_read_decodes_body_and_parses_headers(client: GmailClient, monkeypatch) -> None:
    body_data = base64.urlsafe_b64encode(b"Hello, world!\n\nRegards.").decode()
    msg_response = _mock_response({
        "id": "msg1",
        "labelIds": ["INBOX"],
        "payload": {
            "headers": [
                {"name": "From", "value": "alice@example.com"},
                {"name": "To", "value": "me@gmail.com"},
                {"name": "Subject", "value": "Test"},
                {"name": "Date", "value": "Mon, 22 Apr 2026 09:00:00 +0200"},
                {"name": "Message-Id", "value": "<id-1@example.com>"},
            ],
            "mimeType": "text/plain",
            "body": {"data": body_data},
        },
    })
    ctx = _mock_httpx(get_return=msg_response)
    monkeypatch.setattr(gmail_mod.httpx, "Client", lambda **kw: ctx)

    msg = client.read("msg1")
    assert msg.subject == "Test"
    assert "Hello, world!" in msg.body
    assert msg.message_id == "<id-1@example.com>"
    assert msg.body_truncated is False


def test_send_builds_multipart_and_posts_raw(client: GmailClient, monkeypatch) -> None:
    captured: dict = {}

    def fake_post(url, headers, json):
        captured["url"] = url
        captured["json"] = json
        return _mock_response({"id": "sent-1"})

    ctx = _mock_httpx()
    ctx.post.side_effect = fake_post
    monkeypatch.setattr(gmail_mod.httpx, "Client", lambda **kw: ctx)

    client.send(
        to=["alice@example.com"],
        subject="Test subject",
        body="Test body",
        cc=["bob@example.com"],
    )
    assert captured["url"].endswith("/messages/send")
    raw = captured["json"]["raw"]
    decoded = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)).decode("utf-8")
    assert "To: alice@example.com" in decoded
    assert "Cc: bob@example.com" in decoded
    assert "Subject: Test subject" in decoded
    assert "Test body" in decoded


def test_reply_threads_to_original(client: GmailClient, monkeypatch) -> None:
    meta = _mock_response({
        "id": "orig1",
        "threadId": "thread-abc",
        "payload": {"headers": [
            {"name": "From", "value": "alice@example.com"},
            {"name": "Subject", "value": "Original"},
            {"name": "Message-Id", "value": "<orig-id@example.com>"},
        ]},
    })
    captured: dict = {}

    def fake_post(url, headers, json):
        captured["json"] = json
        return _mock_response({})

    ctx = _mock_httpx(get_return=meta)
    ctx.post.side_effect = fake_post
    monkeypatch.setattr(gmail_mod.httpx, "Client", lambda **kw: ctx)

    client.reply("orig1", body="Thanks!")
    raw = base64.urlsafe_b64decode(
        captured["json"]["raw"] + "=" * (-len(captured["json"]["raw"]) % 4),
    ).decode()
    assert captured["json"]["threadId"] == "thread-abc"
    assert "In-Reply-To: <orig-id@example.com>" in raw
    assert "To: alice@example.com" in raw
    assert "Subject: Re: Original" in raw


def test_move_to_archive_removes_inbox(client: GmailClient, monkeypatch) -> None:
    captured: dict = {}

    def fake_post(url, headers, json):
        captured["url"] = url
        captured["json"] = json
        return _mock_response({})

    ctx = _mock_httpx()
    ctx.post.side_effect = fake_post
    monkeypatch.setattr(gmail_mod.httpx, "Client", lambda **kw: ctx)

    client.move("msg1", dest_folder="ARCHIVE", folder="INBOX")
    assert "INBOX" in captured["json"]["removeLabelIds"]
    assert captured["json"]["addLabelIds"] == []


def test_delete_trashes(client: GmailClient, monkeypatch) -> None:
    captured: dict = {}

    def fake_post(url, headers, json):
        captured["url"] = url
        return _mock_response({})

    ctx = _mock_httpx()
    ctx.post.side_effect = fake_post
    monkeypatch.setattr(gmail_mod.httpx, "Client", lambda **kw: ctx)

    client.delete("msg1")
    assert captured["url"].endswith("/messages/msg1/trash")


def test_mark_seen_removes_unread_label(client: GmailClient, monkeypatch) -> None:
    captured: dict = {}

    def fake_post(url, headers, json):
        captured["json"] = json
        return _mock_response({})

    ctx = _mock_httpx()
    ctx.post.side_effect = fake_post
    monkeypatch.setattr(gmail_mod.httpx, "Client", lambda **kw: ctx)

    client.mark_seen("msg1")
    assert captured["json"]["removeLabelIds"] == ["UNREAD"]


def test_401_raises_friendly_error(client: GmailClient, monkeypatch) -> None:
    ctx = _mock_httpx(get_return=_mock_response({"error": {"message": "bad"}}, status=401))
    monkeypatch.setattr(gmail_mod.httpx, "Client", lambda **kw: ctx)

    with pytest.raises(GmailError, match="unauthorized"):
        client.test()


def test_download_attachment_saves_bytes(
    client: GmailClient, monkeypatch, tmp_path: Path,
) -> None:
    raw_bytes = b"PDF-1.5 fake"
    msg_resp = _mock_response({
        "id": "msg1",
        "payload": {
            "parts": [
                {"filename": "report.pdf", "body": {"attachmentId": "att-1"}},
            ],
        },
    })
    att_resp = _mock_response({
        "data": base64.urlsafe_b64encode(raw_bytes).decode(),
    })
    ctx = _mock_httpx()
    ctx.get.side_effect = [msg_resp, att_resp]
    monkeypatch.setattr(gmail_mod.httpx, "Client", lambda **kw: ctx)

    dest = tmp_path / "report.pdf"
    n = client.download_attachment("msg1", "report.pdf", dest)
    assert dest.read_bytes() == raw_bytes
    assert n == len(raw_bytes)
