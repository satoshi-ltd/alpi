"""Tests for the email subsystem."""

from __future__ import annotations

import email as stdlib_email
from email.message import EmailMessage
from pathlib import Path
from typing import Any

import pytest

from alpi.mail import imap as email_client
from alpi.mail.imap import ImapClient, ImapError
from alpi.tools.email import Email


# --------------------------------------------------------------------
# Fakes
# --------------------------------------------------------------------


class _FakeIMAP:
    """Minimal IMAP stand-in for tests."""

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
def client() -> ImapClient:
    return ImapClient(
        address="me@example.com", password="pw",
        imap_host="imap.example.com", smtp_host="smtp.example.com",
    )


# --------------------------------------------------------------------
# from_env
# --------------------------------------------------------------------


def test_from_env_requires_all_four(monkeypatch) -> None:
    monkeypatch.delenv("IMAP_ADDRESS", raising=False)
    monkeypatch.delenv("IMAP_PASSWORD", raising=False)
    monkeypatch.delenv("IMAP_HOST", raising=False)
    monkeypatch.delenv("SMTP_HOST", raising=False)
    with pytest.raises(ImapError, match="missing"):
        ImapClient.from_env()


def test_from_env_builds_from_env_vars(monkeypatch) -> None:
    monkeypatch.setenv("IMAP_ADDRESS", "me@example.com")
    monkeypatch.setenv("IMAP_PASSWORD", "pw")
    monkeypatch.setenv("IMAP_HOST", "imap.example.com")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    c = ImapClient.from_env()
    assert c.address == "me@example.com"
    assert c.imap_port == 993
    assert c.smtp_port == 587


# --------------------------------------------------------------------
# IMAP list + search
# --------------------------------------------------------------------


def _fake_envelope_fetch(uids: list[str]) -> list:
    """Build the tuple-shaped FETCH payload for envelopes."""
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

    # Seed the fake IMAP instance before the call.
    orig_factory = email_client.imaplib.IMAP4_SSL

    def factory(host, port):
        imap = orig_factory(host, port)
        _install(imap)
        return imap

    email_client.imaplib.IMAP4_SSL = factory  # type: ignore[assignment]

    envelopes = client.list(folder="INBOX", limit=10)
    assert len(envelopes) == 3
    assert envelopes[0].uid == "3"        # most recent first
    assert envelopes[0].subject == "subject 3"
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
    search_calls = [c for c in imap.calls if c[0] == "uid:SEARCH"]
    assert search_calls
    args = search_calls[0][1]
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
    """Regression: port 465 needs ``SMTP_SSL``."""
    c = ImapClient(
        address="me@x.com", password="pw",
        imap_host="i.x.com", smtp_host="s.x.com", smtp_port=465,
    )
    c.send(to=["t@x.com"], subject="s", body="b")
    assert fake_smtp["kind"] == "SMTP_SSL"


def test_smtp_port_587_uses_starttls(fake_smtp) -> None:
    c = ImapClient(
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
            # Record MOVE attempts and fail COPY so fall-through is tested.
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


def _isolate_accounts(monkeypatch, tmp_path) -> None:
    """Strip IMAP env and Gmail token so the tool has no backend."""
    for var in ("IMAP_ADDRESS", "IMAP_PASSWORD", "IMAP_HOST", "SMTP_HOST"):
        monkeypatch.delenv(var, raising=False)
    import alpi.home as home_mod
    monkeypatch.setattr(home_mod, "_ROOT", tmp_path)


def test_tool_surfaces_config_error_cleanly(monkeypatch, tmp_path) -> None:
    _isolate_accounts(monkeypatch, tmp_path)
    result = Email().run(action="list")
    assert not result.ok
    assert "no email account" in result.error.lower()


def test_tool_requires_uid_for_read(monkeypatch, tmp_path) -> None:
    _isolate_accounts(monkeypatch, tmp_path)
    monkeypatch.setenv("IMAP_ADDRESS", "me@x.com")
    monkeypatch.setenv("IMAP_PASSWORD", "p")
    monkeypatch.setenv("IMAP_HOST", "i")
    monkeypatch.setenv("SMTP_HOST", "s")
    result = Email().run(action="read")  # missing uid
    assert not result.ok
    assert "uid" in result.error


def test_tool_unknown_action(monkeypatch, tmp_path) -> None:
    _isolate_accounts(monkeypatch, tmp_path)
    monkeypatch.setenv("IMAP_ADDRESS", "me@x.com")
    monkeypatch.setenv("IMAP_PASSWORD", "p")
    monkeypatch.setenv("IMAP_HOST", "i")
    monkeypatch.setenv("SMTP_HOST", "s")
    result = Email().run(action="nuke_everything")
    assert not result.ok
    assert "unknown action" in result.error


# --------------------------------------------------------------------
# Misc helpers
# --------------------------------------------------------------------


def test_decode_header_handles_utf8() -> None:
    encoded = "=?utf-8?b?SG9sYSDCoQ==?="
    from alpi.mail.imap import _decode_header
    assert _decode_header(encoded) == "Hola ¡"


def test_clean_addr_extracts_email() -> None:
    from alpi.mail.imap import _clean_addr
    assert _clean_addr('"Pepe" <Pepe@X.COM>') == "pepe@x.com"
    assert _clean_addr("pepe@x.com") == "pepe@x.com"
    assert _clean_addr("") == ""


def test_imap_date_converts_iso_to_rfc() -> None:
    from alpi.mail.imap import _imap_date
    assert _imap_date("2026-04-20") == "20-Apr-2026"
        # Pass through when already in IMAP format
    assert _imap_date("20-Apr-2026") == "20-Apr-2026"
