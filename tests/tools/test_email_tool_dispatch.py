"""Account dispatch for the `email` tool — multi-account resolution by id/address."""

from __future__ import annotations

import json
from pathlib import Path

from alpi.mail import accounts as accounts_mod
from alpi.tools import email as email_tool


def _isolate(monkeypatch, tmp_path: Path) -> None:
    import alpi.home as home_mod
    monkeypatch.setattr(home_mod, "_ROOT", tmp_path)
    monkeypatch.delenv("ALPI_PROFILE", raising=False)
    monkeypatch.delenv("ALPI_HOME", raising=False)


def _add_imap(tmp_path: Path, address: str) -> str:
    return accounts_mod.add_imap(
        tmp_path,
        address=address,
        password="pw",
        imap_host="imap.x.com",
        smtp_host="smtp.x.com",
    )


def _seed_gmail_token(tmp_path: Path, account_id: str) -> None:
    p = accounts_mod.gmail_token_path(tmp_path, account_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({
        "email": "me@gmail.com",
        "access_token": "fake",
        "refresh_token": "fake-refresh",
        "expires_at": 9999999999,
    }))


def test_no_accounts_errors_cleanly(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    client, err = email_tool._resolve_client("")
    assert client is None
    assert "no email account" in err.lower()


def test_only_imap_auto_picks_imap(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    _add_imap(tmp_path, "me@x.com")
    client, err = email_tool._resolve_client("")
    assert err is None
    assert client.__class__.__name__ == "ImapClient"


def test_only_gmail_auto_picks_gmail(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    acct = accounts_mod.add_gmail(tmp_path, address="me@gmail.com")
    _seed_gmail_token(tmp_path, acct)
    client, err = email_tool._resolve_client("")
    assert err is None
    assert client.__class__.__name__ == "GmailClient"
    assert client.account_id == acct


def test_multiple_configured_requires_explicit_account(
    monkeypatch, tmp_path: Path,
) -> None:
    _isolate(monkeypatch, tmp_path)
    _add_imap(tmp_path, "me@x.com")
    acct = accounts_mod.add_gmail(tmp_path, address="me@gmail.com")
    _seed_gmail_token(tmp_path, acct)
    client, err = email_tool._resolve_client("")
    assert client is None
    assert "multiple accounts" in err.lower()


def test_resolve_by_id(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    imap_id = _add_imap(tmp_path, "me@work.com")
    acct = accounts_mod.add_gmail(tmp_path, address="me@gmail.com")
    _seed_gmail_token(tmp_path, acct)

    imap_client, err = email_tool._resolve_client(imap_id)
    assert err is None
    assert imap_client.__class__.__name__ == "ImapClient"

    gmail_client, err = email_tool._resolve_client(acct)
    assert err is None
    assert gmail_client.__class__.__name__ == "GmailClient"


def test_resolve_by_address(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    _add_imap(tmp_path, "Me@Work.com")
    acct = accounts_mod.add_gmail(tmp_path, address="me@gmail.com")
    _seed_gmail_token(tmp_path, acct)

    client, err = email_tool._resolve_client("Me@Work.com")
    assert err is None
    assert client.__class__.__name__ == "ImapClient"
    assert client.address == "Me@Work.com"


def test_unknown_account_errors(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    _add_imap(tmp_path, "me@x.com")
    client, err = email_tool._resolve_client("nobody@elsewhere.com")
    assert client is None
    assert "not configured" in err.lower()
