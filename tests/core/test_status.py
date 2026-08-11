"""Direct tests for ``alpi.status``."""

from __future__ import annotations

from pathlib import Path

from alpi import status


def test_status_title_formats_session_id() -> None:
    assert status.status_title("abc123") == "session abc123"


def test_status_rows_basic_shape() -> None:
    rows = status.status_rows(
        session_id="abc123",
        model="openai/gpt-4o-mini",
        turns=2,
        elapsed_seconds=125,
        input_tokens=1_234,
        output_tokens=567,
        cost_usd=0.0042,
    )
    assert rows == [
        ("model", "openai/gpt-4o-mini"),
        ("turns", "2"),
        ("elapsed", "02:05"),
        ("tokens", "in=1,234  out=567"),
        ("cache", "no provider cache data"),
        ("session cost", "$0.0042"),
    ]


def test_status_rows_adds_budget_when_home_present(tmp_path: Path) -> None:
    rows = dict(
        status.status_rows(
            session_id="abc123",
            model="m",
            turns=0,
            elapsed_seconds=None,
            input_tokens=0,
            output_tokens=0,
            cost_usd=0.0,
            home=tmp_path,
            cfg_budget={"daily_usd": 5.0},
        )
    )
    assert rows["daily budget"] == "$0.0000 / $5.00"


def test_status_rows_show_hit_rate_when_measured() -> None:
    rows = dict(status.status_rows(
        session_id="abc123", model="m", turns=1, elapsed_seconds=None,
        input_tokens=14_000, output_tokens=100, cost_usd=0.01,
        cached_input_tokens=11_760, cache_measured_input_tokens=14_000,
    ))
    assert rows["cache"] == "hit 84.0%  (11,760 of 14,000 measured in)"
