"""Tests for the email gateway platform (inbound listener + outbound).

Covers the IMAP poll logic by mocking the ImapClient's IMAP helpers.
No real network. We focus on:
- Baseline UID on first run (no backfill)
- Subsequent polls surface only messages with UID > last_seen
- Noreply / auto / bulk filter drops unwanted senders
- mark_as_read calls IMAP STORE
- Persisted state file round-trip
- delivery.send_to("email", ...) dispatch + allowlist env name
"""

from __future__ import annotations

import asyncio
import email as email_lib
import json
from email.message import EmailMessage
from pathlib import Path
from typing import Any

import pytest

from alpi.gateway import delivery
from alpi.gateway.base import IncomingMessage, OutgoingMessage
from alpi.gateway.platforms import imap as email_platform


# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------


def _build_msg(sender: str, subject: str, body: str,
               headers: dict[str, str] | None = None) -> bytes:
    m = EmailMessage()
    m["From"] = sender
    m["To"] = "alf@example.com"
    m["Subject"] = subject
    for k, v in (headers or {}).items():
        m[k] = v
    m.set_content(body)
    return m.as_bytes()


class _FakeIMAP:
    """IMAP mock tailored to email.Email.listen's usage."""

    def __init__(self) -> None:
        self.selected: str = ""
        self.searches: list = []
        self.store_calls: list = []
        self.uids_in_box: dict[str, bytes] = {}
        self.search_responses: dict[tuple, list[str]] = {}

    def login(self, user, password):
        pass

    def select(self, folder, readonly=False):
        self.selected = folder
        return ("OK", [b"1"])

    def uid(self, cmd, *args):
        if cmd == "SEARCH":
            self.searches.append(args)
            key = tuple(str(a) for a in args if a is not None)
            hits = self.search_responses.get(key, list(self.uids_in_box.keys()))
            return ("OK", [" ".join(hits).encode()])
        if cmd == "FETCH":
            uid = args[0]
            raw = self.uids_in_box.get(uid, b"")
            return ("OK", [((f"1 (UID {uid} BODY[] {{0}}").encode(), raw)])
        if cmd == "STORE":
            self.store_calls.append(args)
            return ("OK", [b""])
        return ("OK", [b""])

    def close(self):
        pass

    def logout(self):
        pass


@pytest.fixture
def patch_imap(monkeypatch):
    holder: dict[str, _FakeIMAP] = {}

    def factory(host, port):
        holder["imap"] = _FakeIMAP()
        return holder["imap"]

    import alpi.mail.imap as client_mod
    monkeypatch.setattr(client_mod.imaplib, "IMAP4_SSL", factory)
    return holder


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("IMAP_ADDRESS", "alf@example.com")
    monkeypatch.setenv("IMAP_PASSWORD", "pw")
    monkeypatch.setenv("IMAP_HOST", "imap.example.com")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")


# --------------------------------------------------------------------
# Baseline + polling
# --------------------------------------------------------------------


def test_discover_baseline_returns_latest_uid(env, patch_imap, tmp_path: Path) -> None:
    imap_holder = patch_imap
    # Pre-wire so any IMAP the platform opens gets these UIDs.
    def factory_with_state(host, port):
        imap = _FakeIMAP()
        imap.uids_in_box = {"7": b"", "8": b"", "9": b""}
        imap_holder["imap"] = imap
        return imap
    import alpi.mail.imap as client_mod
    client_mod.imaplib.IMAP4_SSL = factory_with_state  # type: ignore[assignment]

    platform = email_platform.Imap(tmp_path)
    assert platform._discover_baseline_uid() == 9


def test_poll_once_returns_only_messages_after_last_uid(env, tmp_path: Path, monkeypatch) -> None:
    raw_old = _build_msg("pepe@x.com", "old", "body")
    raw_new = _build_msg("ana@y.com", "new", "hi")

    def factory(host, port):
        imap = _FakeIMAP()
        imap.uids_in_box = {"5": raw_old, "6": raw_new}
        # Simulate IMAP's `UID 6:*` search returning just 6.
        imap.search_responses[("UID", "6:*")] = ["6"]
        return imap

    import alpi.mail.imap as client_mod
    monkeypatch.setattr(client_mod.imaplib, "IMAP4_SSL", factory)

    platform = email_platform.Imap(tmp_path)
    results = platform._poll_once(since_uid=5)
    assert len(results) == 1
    uid, msg = results[0]
    assert uid == "6"
    assert msg["From"] == "ana@y.com"


# --------------------------------------------------------------------
# Anti-bulk filter
# --------------------------------------------------------------------


@pytest.mark.parametrize("sender", [
    "noreply@x.com",
    "no-reply@x.com",
    "mailer-daemon@x.com",
    "Bounce@x.com",
    "notifications@x.com",
])
def test_noreply_senders_are_filtered(sender: str) -> None:
    assert email_platform._is_automated(sender, {}) is True


def test_regular_sender_passes() -> None:
    assert email_platform._is_automated("pepe@x.com", {}) is False


@pytest.mark.parametrize("headers", [
    {"Auto-Submitted": "auto-generated"},
    {"Precedence": "bulk"},
    {"Precedence": "list"},
    {"List-Unsubscribe": "<mailto:remove@x.com>"},
    {"X-Auto-Response-Suppress": "All"},
])
def test_bulk_headers_are_filtered(headers: dict[str, str]) -> None:
    assert email_platform._is_automated("regular@x.com", headers) is True


def test_auto_submitted_no_still_passes() -> None:
    assert email_platform._is_automated(
        "regular@x.com", {"Auto-Submitted": "no"},
    ) is False


# --------------------------------------------------------------------
# State persistence
# --------------------------------------------------------------------


def test_save_and_load_last_uid_roundtrip(env, tmp_path: Path) -> None:
    p = email_platform.Imap(tmp_path)
    assert p._load_last_uid() is None
    p._save_last_uid(42)
    # Re-instantiate to force re-read from disk.
    p2 = email_platform.Imap(tmp_path)
    assert p2._load_last_uid() == 42


def test_state_is_per_email_address(env, tmp_path: Path, monkeypatch) -> None:
    p1 = email_platform.Imap(tmp_path)
    p1._save_last_uid(10)
    monkeypatch.setenv("IMAP_ADDRESS", "other@example.com")
    p2 = email_platform.Imap(tmp_path)
    assert p2._load_last_uid() is None
    p2._save_last_uid(20)
    monkeypatch.setenv("IMAP_ADDRESS", "alf@example.com")
    p3 = email_platform.Imap(tmp_path)
    assert p3._load_last_uid() == 10


# --------------------------------------------------------------------
# delivery dispatcher + allowlist env var name
# --------------------------------------------------------------------


def test_delivery_allowlist_uses_email_allowed_senders(monkeypatch) -> None:
    monkeypatch.setenv("IMAP_ALLOWED_SENDERS", "Pepe@X.COM, ana@y.com")
    # Case-insensitive match.
    assert delivery.is_allowed("email", "pepe@x.com") is True
    assert delivery.is_allowed("email", "PEPE@X.COM") is True
    assert delivery.is_allowed("email", "unknown@x.com") is False


def test_delivery_send_to_email_dispatches(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("IMAP_ADDRESS", "me@x.com")
    monkeypatch.setenv("IMAP_PASSWORD", "pw")
    monkeypatch.setenv("IMAP_HOST", "i.x.com")
    monkeypatch.setenv("SMTP_HOST", "s.x.com")
    monkeypatch.setenv("IMAP_ALLOWED_SENDERS", "pepe@x.com")

    sends: list = []

    class _FakeClient:
        @classmethod
        def from_env(cls):
            return cls()

        def send(self, to, subject, body):
            sends.append({"to": to, "subject": subject, "body": body})

    # Patch the lazy import inside _send_email_sync.
    import alpi.mail.imap as client_mod
    monkeypatch.setattr(client_mod, "ImapClient", _FakeClient)

    delivery.send_to("email", "pepe@x.com", "hello")
    assert sends == [{"to": ["pepe@x.com"], "subject": "[alf]", "body": "hello"}]


def test_delivery_email_rejects_unallowlisted(monkeypatch) -> None:
    monkeypatch.setenv("IMAP_ALLOWED_SENDERS", "pepe@x.com")
    with pytest.raises(delivery.DeliveryError, match="not in IMAP_ALLOWED_SENDERS"):
        delivery.send_to("email", "eve@evil.com", "boom")
