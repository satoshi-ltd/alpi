"""Tests for the email subsystem — EmailClient + tool.

IMAP/SMTP are mocked (fake classes injected via monkeypatch on
``imaplib.IMAP4_SSL`` / ``smtplib.SMTP``). No real network, no real
mailbox. We exercise:

- ``from_env`` argument validation
- list + search translate to expected IMAP SEARCH criteria
- read parses headers + body + attachments
- send writes the right ``EmailMessage`` + recipients
- reply / forward compose subject + threading headers correctly
- move / delete fall through folder candidates
- tool dispatcher surfaces EmailError as ToolResult.error
"""

from __future__ import annotations

import email as stdlib_email
from email.message import EmailMessage
from pathlib import Path
from typing import Any

import pytest

from alf.email import client as email_client
from alf.email.client import EmailClient, EmailError
from alf.tools.email import Email


# --------------------------------------------------------------------
# Fakes
# --------------------------------------------------------------------


class _FakeIMAP:
    """Minimal IMAP stand-in. Tests configure ``search_result`` and
    ``fetch_result`` to shape the response. Records every call."""

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.calls: list[tuple[str, tuple]] = []
        self.search_result: list[str] = []
        self.fetch_result: Any = []
        self.move_ok = True

    def login(self, user: str, password: str) -> None:
        self.calls.append(("login", (user, password)))

    def select(self, folder: str, readonly: bool = False):
        self.calls.append(("select", (folder, readonly)))
        return ("OK", [b"1"])

    def uid(self, cmd: str, *args: Any):
        self.calls.append((f"uid:{cmd}", args))
        if cmd == "SEARCH":
            return ("OK", [" ".join(self.search_result).encode()])
        if cmd == "FETCH":
            return ("OK", self.fetch_result)
        if cmd == "MOVE":
            return ("OK", [b""]) if self.move_ok else ("NO", [b"no"])
        if cmd == "COPY":
            return ("OK", [b""])
        if cmd == "STORE":
            return ("OK", [b""])
        return ("OK", [b""])

    def expunge(self):
        self.calls.append(("expunge", ()))
        return ("OK", [b""])

    def close(self):
        self.calls.append(("close", ()))

    def logout(self):
        self.calls.append(("logout", ()))


class _FakeSMTP:
    def __init__(self, host: str, port: int, timeout: int = 30) -> None:
        self.host = host
        self.port = port
        self.sent: list[tuple[EmailMessage, str, list[str]]] = []

    def ehlo(self):
        pass

    def starttls(self, context=None):
        pass

    def login(self, user: str, password: str):
        pass

    def send_message(self, msg: EmailMessage, from_addr: str, to_addrs: list[str]):
        self.sent.append((msg, from_addr, list(to_addrs)))

    def quit(self):
        pass


@pytest.fixture
def fake_imap(monkeypatch):
    holder: dict[str, _FakeIMAP] = {}

    def factory(host: str, port: int):
        holder["imap"] = _FakeIMAP(host, port)
        return holder["imap"]

    monkeypatch.setattr(email_client.imaplib, "IMAP4_SSL", factory)
    return holder


@pytest.fixture
def fake_smtp(monkeypatch):
    holder: dict[str, _FakeSMTP] = {}

    def factory(host: str, port: int, timeout: int = 30):
        holder["smtp"] = _FakeSMTP(host, port, timeout)
        holder.setdefault("kind", "SMTP")
        return holder["smtp"]

    def ssl_factory(host: str, port: int, timeout: int = 30, context=None):
        holder["smtp"] = _FakeSMTP(host, port, timeout)
        holder["kind"] = "SMTP_SSL"
        return holder["smtp"]

    monkeypatch.setattr(email_client.smtplib, "SMTP", factory)
    monkeypatch.setattr(email_client.smtplib, "SMTP_SSL", ssl_factory)
    return holder


@pytest.fixture
def client() -> EmailClient:
    return EmailClient(
        address="me@example.com", password="pw",
        imap_host="imap.example.com", smtp_host="smtp.example.com",
    )


# --------------------------------------------------------------------
# from_env
# --------------------------------------------------------------------


def test_from_env_requires_all_four(monkeypatch) -> None:
    monkeypatch.delenv("EMAIL_ADDRESS", raising=False)
    monkeypatch.delenv("EMAIL_PASSWORD", raising=False)
    monkeypatch.delenv("EMAIL_IMAP_HOST", raising=False)
    monkeypatch.delenv("EMAIL_SMTP_HOST", raising=False)
    with pytest.raises(EmailError, match="missing"):
        EmailClient.from_env()


def test_from_env_builds_from_env_vars(monkeypatch) -> None:
    monkeypatch.setenv("EMAIL_ADDRESS", "me@example.com")
    monkeypatch.setenv("EMAIL_PASSWORD", "pw")
    monkeypatch.setenv("EMAIL_IMAP_HOST", "imap.example.com")
    monkeypatch.setenv("EMAIL_SMTP_HOST", "smtp.example.com")
    c = EmailClient.from_env()
    assert c.address == "me@example.com"
    assert c.imap_port == 993
    assert c.smtp_port == 587


# --------------------------------------------------------------------
# IMAP list + search
# --------------------------------------------------------------------


def _fake_envelope_fetch(uids: list[str]) -> list:
    """Construct the tuple-shaped data imaplib FETCH returns for envelopes."""
    out: list = []
    for i, uid in enumerate(uids):
        meta = (
            f"{i + 1} (UID {uid} FLAGS (\\Seen) "
            f"BODYSTRUCTURE (\"text\" \"plain\" () () () \"7bit\" 10))"
        ).encode()
        headers = (
            f"From: sender{uid}@x.com\r\n"
            f"To: me@example.com\r\n"
            f"Subject: subject {uid}\r\n"
            f"Date: Mon, 20 Apr 2026 10:00:00 +0000\r\n\r\n"
        ).encode()
        out.append((meta, headers))
    return out


def test_list_returns_envelopes(client, fake_imap) -> None:
    def _install(imap):
        imap.search_result = ["1", "2", "3"]
        imap.fetch_result = _fake_envelope_fetch(["1", "2", "3"])

    # Pre-seed by calling once to materialize the IMAP instance.
    # list() internally opens a new IMAP connection, so we configure the
    # factory to configure the connection on instantiation.
    orig_factory = email_client.imaplib.IMAP4_SSL

    def factory(host, port):
        imap = orig_factory(host, port)
        _install(imap)
        return imap

    # monkeypatch already installed the fake — wrap it to seed state.
    email_client.imaplib.IMAP4_SSL = factory  # type: ignore[assignment]

    envelopes = client.list(folder="INBOX", limit=10)
    assert len(envelopes) == 3
    assert envelopes[0].uid == "3"        # most recent first
    assert envelopes[0].subject == "subject 3"
    # Restore
    email_client.imaplib.IMAP4_SSL = orig_factory  # type: ignore[assignment]


def test_search_translates_criteria(client, fake_imap) -> None:
    orig_factory = email_client.imaplib.IMAP4_SSL

    def factory(host, port):
        imap = orig_factory(host, port)
        imap.search_result = []
        imap.fetch_result = []
        return imap

    email_client.imaplib.IMAP4_SSL = factory  # type: ignore[assignment]

    client.search(from_="pepe@x.com", subject="hola", unread_only=True)
    imap = fake_imap["imap"]
    # Find the SEARCH call and verify criteria.
    search_calls = [c for c in imap.calls if c[0] == "uid:SEARCH"]
    assert search_calls
    args = search_calls[0][1]
    # First arg is None, then criteria.
    assert args[0] is None
    crit = list(args[1:])
    assert "UNSEEN" in crit
    assert "FROM" in crit and "pepe@x.com" in crit
    assert "SUBJECT" in crit and "hola" in crit
    email_client.imaplib.IMAP4_SSL = orig_factory  # type: ignore[assignment]


# --------------------------------------------------------------------
# read
# --------------------------------------------------------------------


def test_read_parses_full_message(client, fake_imap) -> None:
    msg = EmailMessage()
    msg["From"] = "pepe@x.com"
    msg["To"] = "me@example.com"
    msg["Subject"] = "Hola"
    msg["Date"] = "Mon, 20 Apr 2026 10:00:00 +0000"
    msg["Message-Id"] = "<abc@x.com>"
    msg.set_content("Hello world")
    raw = msg.as_bytes()

    orig_factory = email_client.imaplib.IMAP4_SSL

    def factory(host, port):
        imap = orig_factory(host, port)
        imap.fetch_result = [(b"1 (UID 42 BODY[] {100}", raw)]
        return imap

    email_client.imaplib.IMAP4_SSL = factory  # type: ignore[assignment]

    full = client.read("42")
    assert full.uid == "42"
    assert full.from_ == "pepe@x.com"
    assert full.subject == "Hola"
    assert "Hello world" in full.body
    assert full.message_id == "<abc@x.com>"
    email_client.imaplib.IMAP4_SSL = orig_factory  # type: ignore[assignment]


# --------------------------------------------------------------------
# send + reply + forward
# --------------------------------------------------------------------


def test_smtp_port_465_uses_ssl_context(fake_smtp) -> None:
    """Regression: PrivateEmail and similar providers hang up on port
    465 if we speak plain SMTP + STARTTLS; the port demands implicit
    TLS via ``SMTP_SSL`` from the TCP handshake."""
    c = EmailClient(
        address="me@x.com", password="pw",
        imap_host="i.x.com", smtp_host="s.x.com", smtp_port=465,
    )
    c.send(to=["t@x.com"], subject="s", body="b")
    assert fake_smtp["kind"] == "SMTP_SSL"


def test_smtp_port_587_uses_starttls(fake_smtp) -> None:
    c = EmailClient(
        address="me@x.com", password="pw",
        imap_host="i.x.com", smtp_host="s.x.com", smtp_port=587,
    )
    c.send(to=["t@x.com"], subject="s", body="b")
    assert fake_smtp["kind"] == "SMTP"


def test_send_composes_message(client, fake_smtp) -> None:
    client.send(
        to=["pepe@x.com"], subject="Hola", body="body",
        cc=["ana@x.com"],
    )
    smtp = fake_smtp["smtp"]
    assert len(smtp.sent) == 1
    msg, frm, rcpts = smtp.sent[0]
    assert frm == "me@example.com"
    assert rcpts == ["pepe@x.com", "ana@x.com"]
    assert msg["Subject"] == "Hola"
    assert msg["From"] == "me@example.com"
    assert msg["To"] == "pepe@x.com"
    assert msg["Cc"] == "ana@x.com"
    assert "body" in msg.get_content()


def test_send_adds_attachments(client, fake_smtp, tmp_path: Path) -> None:
    att = tmp_path / "foo.txt"
    att.write_text("content")
    client.send(to=["pepe@x.com"], subject="x", body="y", attachments=[att])
    msg, _, _ = fake_smtp["smtp"].sent[0]
    names = [p.get_filename() for p in msg.iter_attachments()]
    assert "foo.txt" in names


def test_reply_sets_threading_headers(client, fake_imap, fake_smtp, monkeypatch) -> None:
    orig = EmailMessage()
    orig["From"] = "pepe@x.com"
    orig["To"] = "me@example.com"
    orig["Subject"] = "Hola"
    orig["Message-Id"] = "<abc@x.com>"
    orig.set_content("original body")

    orig_factory = email_client.imaplib.IMAP4_SSL

    def factory(host, port):
        imap = orig_factory(host, port)
        imap.fetch_result = [(b"1 (UID 42 BODY[] {100}", orig.as_bytes())]
        return imap

    email_client.imaplib.IMAP4_SSL = factory  # type: ignore[assignment]

    client.reply("42", "my reply")
    msg, _, rcpts = fake_smtp["smtp"].sent[0]
    assert msg["Subject"] == "Re: Hola"
    assert msg["In-Reply-To"] == "<abc@x.com>"
    assert "<abc@x.com>" in (msg["References"] or "")
    assert rcpts == ["pepe@x.com"]

    email_client.imaplib.IMAP4_SSL = orig_factory  # type: ignore[assignment]


# --------------------------------------------------------------------
# delete fall-through
# --------------------------------------------------------------------


def test_delete_falls_through_trash_candidates(client, fake_imap) -> None:
    orig_factory = email_client.imaplib.IMAP4_SSL
    attempts: list[str] = []

    def factory(host, port):
        imap = orig_factory(host, port)
        original_uid = imap.uid

        def tracking_uid(cmd, *args):
            # Both MOVE and COPY get tried when MOVE fails. Record the
            # MOVE attempts so we can assert on fall-through, and fail
            # COPY for the same folders so move() truly errors out.
            if cmd == "MOVE":
                attempts.append(args[1])
                if args[1] in ("Trash", "[Gmail]/Trash"):
                    return ("NO", [b"no such folder"])
            if cmd == "COPY" and args[1] in ("Trash", "[Gmail]/Trash"):
                return ("NO", [b"no such folder"])
            return original_uid(cmd, *args)

        imap.uid = tracking_uid  # type: ignore[assignment]
        return imap

    email_client.imaplib.IMAP4_SSL = factory  # type: ignore[assignment]

    client.delete("42")
    assert "Trash" in attempts
    assert "[Gmail]/Trash" in attempts
    assert "Deleted" in attempts

    email_client.imaplib.IMAP4_SSL = orig_factory  # type: ignore[assignment]


# --------------------------------------------------------------------
# Tool dispatcher
# --------------------------------------------------------------------


def test_tool_surfaces_config_error_cleanly(monkeypatch) -> None:
    for var in ("EMAIL_ADDRESS", "EMAIL_PASSWORD", "EMAIL_IMAP_HOST", "EMAIL_SMTP_HOST"):
        monkeypatch.delenv(var, raising=False)
    result = Email().run(action="list")
    assert not result.ok
    assert "email not configured" in result.error
    assert "alf setup" in result.error.lower()


def test_tool_requires_uid_for_read(monkeypatch) -> None:
    monkeypatch.setenv("EMAIL_ADDRESS", "me@x.com")
    monkeypatch.setenv("EMAIL_PASSWORD", "p")
    monkeypatch.setenv("EMAIL_IMAP_HOST", "i")
    monkeypatch.setenv("EMAIL_SMTP_HOST", "s")
    result = Email().run(action="read")  # missing uid
    assert not result.ok
    assert "uid" in result.error


def test_tool_unknown_action(monkeypatch) -> None:
    monkeypatch.setenv("EMAIL_ADDRESS", "me@x.com")
    monkeypatch.setenv("EMAIL_PASSWORD", "p")
    monkeypatch.setenv("EMAIL_IMAP_HOST", "i")
    monkeypatch.setenv("EMAIL_SMTP_HOST", "s")
    result = Email().run(action="nuke_everything")
    assert not result.ok
    assert "unknown action" in result.error


# --------------------------------------------------------------------
# Misc helpers
# --------------------------------------------------------------------


def test_decode_header_handles_utf8() -> None:
    encoded = "=?utf-8?b?SG9sYSDCoQ==?="
    from alf.email.client import _decode_header
    assert _decode_header(encoded) == "Hola ¡"


def test_clean_addr_extracts_email() -> None:
    from alf.email.client import _clean_addr
    assert _clean_addr('"Pepe" <Pepe@X.COM>') == "pepe@x.com"
    assert _clean_addr("pepe@x.com") == "pepe@x.com"
    assert _clean_addr("") == ""


def test_imap_date_converts_iso_to_rfc() -> None:
    from alf.email.client import _imap_date
    assert _imap_date("2026-04-20") == "20-Apr-2026"
    # Pass-through when already in IMAP format
    assert _imap_date("20-Apr-2026") == "20-Apr-2026"
