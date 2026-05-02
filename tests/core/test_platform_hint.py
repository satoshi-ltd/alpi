"""``ALPI_PLATFORM`` injects a per-surface system-prompt hint."""

from __future__ import annotations

import pytest

from alpi.engine import _platform_hint


def test_tui_has_no_hint(monkeypatch) -> None:
    monkeypatch.delenv("ALPI_PLATFORM", raising=False)
    assert _platform_hint() == ""


def test_cron_hint_says_no_user_present(monkeypatch) -> None:
    monkeypatch.setenv("ALPI_PLATFORM", "cron")
    hint = _platform_hint()
    assert "scheduled job" in hint.lower()
    assert "no user" in hint.lower()
    assert "autonomous" in hint.lower()


def test_telegram_hint_mentions_markdown_conversion(monkeypatch) -> None:
    monkeypatch.setenv("ALPI_PLATFORM", "telegram")
    hint = _platform_hint()
    assert "telegram" in hint.lower()
    assert "markdownv2" in hint.lower()
    assert "table" in hint.lower()


def test_email_hint_requires_plain_text(monkeypatch) -> None:
    monkeypatch.setenv("ALPI_PLATFORM", "email")
    hint = _platform_hint()
    assert "plain text" in hint.lower()
    assert "markdown" in hint.lower()


def test_gmail_hint_matches_email(monkeypatch) -> None:
    monkeypatch.setenv("ALPI_PLATFORM", "gmail")
    hint = _platform_hint()
    assert "plain text" in hint.lower()


def test_unknown_platform_returns_empty(monkeypatch) -> None:
    monkeypatch.setenv("ALPI_PLATFORM", "carrier-pigeon")
    assert _platform_hint() == ""
