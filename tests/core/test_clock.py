"""Tests for `alpi.clock` — date/time context shipped to the LLM."""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from alpi import clock


def test_user_timezone_honors_env(monkeypatch) -> None:
    monkeypatch.setenv("TZ", "Europe/Madrid")
    assert clock.user_timezone() == "Europe/Madrid"


def test_user_timezone_invalid_env_falls_through(monkeypatch) -> None:
    # Invalid env → falls through to /etc/localtime / tzname / UTC; the guarantee is "some valid IANA name", not a specific value.
    monkeypatch.setenv("TZ", "Not/A/Zone")
    name = clock.user_timezone()
    assert ZoneInfo(name) is not None


def test_user_timezone_no_env_returns_resolvable(monkeypatch) -> None:
    monkeypatch.delenv("TZ", raising=False)
    name = clock.user_timezone()
    assert ZoneInfo(name) is not None


def test_now_block_format_with_explicit_now() -> None:
    now = datetime(2026, 5, 18, 9, 30, tzinfo=timezone.utc)
    block = clock.now_block("Europe/Madrid", now=now)
    # 09:30 UTC == 11:30 Madrid in DST.
    assert block.startswith("# NOW\n")
    assert "Monday, 2026-05-18 11:30 (Europe/Madrid)" in block
    assert "UTC:   2026-05-18T09:30Z" in block


def test_now_block_handles_invalid_tz_with_fallback() -> None:
    now = datetime(2026, 5, 18, 9, 30, tzinfo=timezone.utc)
    block = clock.now_block("Not/A/Zone", now=now)
    # Falls back to UTC; the local line must reflect UTC, not silently drop.
    assert "(UTC)" in block
    assert "Monday, 2026-05-18 09:30 (UTC)" in block


def test_now_block_handles_naive_datetime_as_utc() -> None:
    # An accidentally naive datetime is interpreted as UTC, never raises.
    now = datetime(2026, 5, 18, 9, 30)
    block = clock.now_block("UTC", now=now)
    assert "Monday, 2026-05-18 09:30 (UTC)" in block
    assert "UTC:   2026-05-18T09:30Z" in block


def test_now_block_default_now_is_fresh() -> None:
    for block in (clock.now_block("UTC"), clock.now_block("UTC")):
        assert block.startswith("# NOW\n")
        assert "Local:" in block
        assert "UTC:" in block


def test_system_time_section_carries_timezone(monkeypatch) -> None:
    monkeypatch.setenv("TZ", "America/New_York")
    section = clock.system_time_section()
    assert section.startswith("# DATE & TIME")
    assert "Timezone: America/New_York" in section
    assert "# NOW" in section
    assert "Do NOT guess" in section


def test_system_time_section_invalid_tz_falls_back_to_utc(monkeypatch) -> None:
    monkeypatch.setenv("TZ", "Not/A/Zone")
    section = clock.system_time_section("Also/Not/A/Zone")
    assert "Timezone: UTC" in section


def test_dst_transition_reflected_in_local_time() -> None:
    # Madrid: +1 CET in winter, +2 CEST in summer — same UTC instant must render differently.
    winter_utc = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
    summer_utc = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)
    assert "13:00 (Europe/Madrid)" in clock.now_block("Europe/Madrid", now=winter_utc)
    assert "14:00 (Europe/Madrid)" in clock.now_block("Europe/Madrid", now=summer_utc)
