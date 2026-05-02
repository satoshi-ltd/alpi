"""Account dispatch for the `email` tool — imap vs gmail resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from alpi.tools import email as email_tool


def _isolate(monkeypatch, tmp_path: Path) -> None:
    for var in ("IMAP_ADDRESS", "IMAP_PASSWORD", "IMAP_HOST", "SMTP_HOST"):
        monkeypatch.delenv(var, raising=False)
    import alpi.home as home_mod
    monkeypatch.setattr(home_mod, "_ROOT", tmp_path)


def _seed_gmail_token(tmp_path: Path) -> None:
    import json
    secrets = tmp_path / "secrets"
    secrets.mkdir(parents=True, exist_ok=True)
    (secrets / "gmail_token.json").write_text(json.dumps({
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
    monkeypatch.setenv("IMAP_ADDRESS", "me@x.com")
    monkeypatch.setenv("IMAP_PASSWORD", "p")
    monkeypatch.setenv("IMAP_HOST", "i")
    monkeypatch.setenv("SMTP_HOST", "s")
    client, err = email_tool._resolve_client("")
    assert err is None
    assert client.__class__.__name__ == "ImapClient"


def test_only_gmail_auto_picks_gmail(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    _seed_gmail_token(tmp_path)
    client, err = email_tool._resolve_client("")
    assert err is None
    assert client.__class__.__name__ == "GmailClient"


def test_both_configured_requires_explicit_account(
    monkeypatch, tmp_path: Path,
) -> None:
    _isolate(monkeypatch, tmp_path)
    monkeypatch.setenv("IMAP_ADDRESS", "me@x.com")
    monkeypatch.setenv("IMAP_PASSWORD", "p")
    monkeypatch.setenv("IMAP_HOST", "i")
    monkeypatch.setenv("SMTP_HOST", "s")
    _seed_gmail_token(tmp_path)
    client, err = email_tool._resolve_client("")
    assert client is None
    assert "multiple accounts" in err.lower()


def test_both_configured_explicit_pick(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    monkeypatch.setenv("IMAP_ADDRESS", "me@x.com")
    monkeypatch.setenv("IMAP_PASSWORD", "p")
    monkeypatch.setenv("IMAP_HOST", "i")
    monkeypatch.setenv("SMTP_HOST", "s")
    _seed_gmail_token(tmp_path)

    imap_client, err = email_tool._resolve_client("imap")
    assert err is None
    assert imap_client.__class__.__name__ == "ImapClient"

    gmail_client, err = email_tool._resolve_client("gmail")
    assert err is None
    assert gmail_client.__class__.__name__ == "GmailClient"


def test_unknown_account_errors(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    monkeypatch.setenv("IMAP_ADDRESS", "me@x.com")
    monkeypatch.setenv("IMAP_PASSWORD", "p")
    monkeypatch.setenv("IMAP_HOST", "i")
    monkeypatch.setenv("SMTP_HOST", "s")
    client, err = email_tool._resolve_client("outlook")
    assert client is None
    assert "not configured" in err.lower()
