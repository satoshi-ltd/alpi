from __future__ import annotations

import json
import shutil
import tempfile
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from alpi import ledger


@pytest.fixture
def home() -> Path:
    d = Path(tempfile.mkdtemp(prefix="alpi-ledger-"))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


def _set_day(day: str):
    return patch.object(ledger, "_today_utc", return_value=day)


def test_missing_file_returns_blank_for_today(home: Path) -> None:
    data = ledger.load(home)
    assert data["profile"] == {"usd": 0.0, "tokens": 0}
    assert data["by_peer"] == {}
    assert data["day"] == datetime.now(timezone.utc).date().isoformat()


def test_record_accumulates_into_profile_and_interactive_bucket(home: Path) -> None:
    ledger.record(home, usd=0.15, tokens=1000)
    ledger.record(home, usd=0.07, tokens=500)
    snap = ledger.snapshot(home)
    assert snap["profile"] == {"usd": pytest.approx(0.22), "tokens": 1500}
    assert snap["by_peer"]["__interactive__"] == {
        "usd": pytest.approx(0.22),
        "tokens": 1500,
    }


def test_peer_context_routes_records_to_peer_bucket(home: Path) -> None:
    with ledger.peer_context("alice"):
        ledger.record(home, usd=0.10, tokens=800)
    ledger.record(home, usd=0.05, tokens=200)
    snap = ledger.snapshot(home)
    assert snap["profile"]["tokens"] == 1000
    assert snap["by_peer"]["alice"]["tokens"] == 800
    assert snap["by_peer"]["__interactive__"]["tokens"] == 200


def test_zero_delta_is_noop(home: Path) -> None:
    ledger.record(home, usd=0, tokens=0)
    assert not ledger._path(home).exists()


def test_negative_deltas_are_clamped(home: Path) -> None:
    ledger.record(home, usd=-1.0, tokens=-999)
    snap = ledger.snapshot(home)
    assert snap["profile"]["usd"] == 0.0
    assert snap["profile"]["tokens"] == 0


def test_check_passes_with_no_budget(home: Path) -> None:
    ledger.check(home, {})
    ledger.check(home, None)
    ledger.check(home, {"daily_usd": 0})


def test_check_passes_under_cap(home: Path) -> None:
    ledger.record(home, usd=1.0, tokens=500)
    ledger.check(home, {"daily_usd": 5.0})


def test_check_raises_at_or_over_cap(home: Path) -> None:
    ledger.record(home, usd=5.0, tokens=1000)
    with pytest.raises(ledger.BudgetExceeded) as exc:
        ledger.check(home, {"daily_usd": 5.0})
    assert exc.value.cap_kind == "usd"
    assert exc.value.cap == 5.0
    assert exc.value.used == 5.0


def test_check_uses_usd_when_both_caps_set(home: Path) -> None:
    ledger.record(home, usd=10.0, tokens=100)
    with pytest.raises(ledger.BudgetExceeded) as exc:
        ledger.check(home, {"daily_usd": 2.0, "daily_tokens": 10**9})
    assert exc.value.cap_kind == "usd"


def test_check_tokens_only_profile(home: Path) -> None:
    ledger.record(home, usd=0.0, tokens=1000)
    with pytest.raises(ledger.BudgetExceeded) as exc:
        ledger.check(home, {"daily_tokens": 1000})
    assert exc.value.cap_kind == "tokens"


def test_stale_day_resets_on_load(home: Path) -> None:
    yesterday = (
        datetime.now(timezone.utc).date() - timedelta(days=1)
    ).isoformat()
    ledger.save(
        home,
        {
            "day": yesterday,
            "profile": {"usd": 42.0, "tokens": 99999},
            "by_peer": {"alice": {"usd": 42.0, "tokens": 99999}},
        },
    )
    snap = ledger.snapshot(home)
    assert snap["profile"] == {"usd": 0.0, "tokens": 0}
    assert snap["by_peer"] == {}


def test_corrupt_file_is_treated_as_blank(home: Path) -> None:
    p = ledger._path(home)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("not-json{{{")
    snap = ledger.snapshot(home)
    assert snap["profile"] == {"usd": 0.0, "tokens": 0}


def test_save_is_atomic_under_concurrent_records(home: Path) -> None:
    def worker() -> None:
        for _ in range(50):
            ledger.record(home, usd=0.01, tokens=1)
    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    snap = ledger.snapshot(home)
    assert snap["profile"]["tokens"] == 8 * 50
    assert snap["profile"]["usd"] == pytest.approx(8 * 50 * 0.01)


def test_peer_context_unwinds_on_exception(home: Path) -> None:
    try:
        with ledger.peer_context("alice"):
            ledger.record(home, usd=0.5, tokens=100)
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    ledger.record(home, usd=0.2, tokens=50)
    snap = ledger.snapshot(home)
    assert snap["by_peer"]["alice"]["tokens"] == 100
    assert snap["by_peer"]["__interactive__"]["tokens"] == 50


def test_budget_selects_pickone(home: Path) -> None:
    assert ledger._budget({}) == (None, 0)
    assert ledger._budget({"daily_usd": 5.0}) == ("usd", 5.0)
    assert ledger._budget({"daily_tokens": 1000}) == ("tokens", 1000.0)
    kind, cap = ledger._budget({"daily_usd": 5.0, "daily_tokens": 100})
    assert kind == "usd" and cap == 5.0
    assert ledger._budget({"daily_usd": 0}) == (None, 0)
    assert ledger._budget({"daily_tokens": -1}) == (None, 0)
