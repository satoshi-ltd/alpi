from __future__ import annotations

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


def test_daily_tokens_is_ignored_usd_caps(home: Path) -> None:
    ledger.record(home, usd=10.0, tokens=100)
    with pytest.raises(ledger.BudgetExceeded) as exc:
        ledger.check(home, {"daily_usd": 2.0, "daily_tokens": 10**9})
    assert exc.value.cap_kind == "usd"


def test_token_only_budget_is_uncapped(home: Path) -> None:
    ledger.record(home, usd=0.0, tokens=10**9)
    ledger.check(home, {"daily_tokens": 1000})  # token budget removed → no cap, no raise


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


def test_record_populates_daily_history(home: Path) -> None:
    ledger.record(home, usd=0.05, tokens=1500, tokens_in=1200, tokens_out=300)
    ledger.record(home, usd=0.30, tokens=0)
    snap = ledger.snapshot(home)
    today = datetime.now(timezone.utc).date().isoformat()
    assert snap["history"][today] == {
        "usd": pytest.approx(0.35),
        "tokens": 1500,
        "tokens_in": 1200,
        "tokens_out": 300,
        "by_connection": {
            "host": {
                "usd": pytest.approx(0.35),
                "tokens": 1500,
                "tokens_in": 1200,
                "tokens_out": 300,
            },
        },
    }


def test_free_model_usage_recorded_at_zero_cost(home: Path) -> None:
    ledger.record(home, usd=0.0, tokens=5000, tokens_in=4800, tokens_out=200)
    snap = ledger.snapshot(home)
    today = datetime.now(timezone.utc).date().isoformat()
    assert snap["history"][today] == {
        "usd": 0.0, "tokens": 5000, "tokens_in": 4800, "tokens_out": 200,
        "by_connection": {
            "host": {
                "usd": 0.0, "tokens": 5000,
                "tokens_in": 4800, "tokens_out": 200,
            },
        },
    }
    assert snap["profile"]["tokens"] == 5000


def test_history_today_mirrors_profile_total_after_prior_untracked_spend(home: Path) -> None:
    today = datetime.now(timezone.utc).date().isoformat()
    ledger.save(home, {
        "day": today,
        "profile": {"usd": 0.50, "tokens": 1_000_000},
        "by_peer": {"__interactive__": {"usd": 0.50, "tokens": 1_000_000}},
        "history": {},
    })
    ledger.record(home, usd=0.0, tokens=200, tokens_in=190, tokens_out=10)
    snap = ledger.snapshot(home)
    assert snap["history"][today]["usd"] == pytest.approx(0.50)
    assert snap["history"][today]["tokens"] == 1_000_200
    assert snap["history"][today]["tokens_in"] == 190
    assert snap["history"][today]["tokens_out"] == 10


def test_history_survives_day_rollover(home: Path) -> None:
    yesterday = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
    ledger.save(home, {
        "day": yesterday,
        "profile": {"usd": 0.5, "tokens": 100},
        "by_peer": {},
        "history": {yesterday: {"usd": 0.5, "tokens": 100, "tokens_in": 80, "tokens_out": 20}},
    })
    snap = ledger.snapshot(home)
    assert snap["profile"] == {"usd": 0.0, "tokens": 0}
    assert snap["history"][yesterday]["usd"] == pytest.approx(0.5)


def test_rollover_folds_stale_profile_lacking_history(home: Path) -> None:
    yesterday = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
    ledger.save(home, {
        "day": yesterday,
        "profile": {"usd": 0.5, "tokens": 100},
        "by_peer": {},
    })
    snap = ledger.snapshot(home)
    assert snap["history"][yesterday]["usd"] == pytest.approx(0.5)
    assert snap["history"][yesterday]["tokens"] == 100


def test_history_prunes_days_beyond_window(home: Path) -> None:
    today = datetime.now(timezone.utc).date().isoformat()
    old = (datetime.now(timezone.utc).date() - timedelta(days=ledger.HISTORY_DAYS + 5)).isoformat()
    ledger.save(home, {
        "day": today,
        "profile": {"usd": 0.0, "tokens": 0},
        "by_peer": {},
        "history": {old: {"usd": 9.0, "tokens": 1, "tokens_in": 1, "tokens_out": 0}},
    })
    ledger.record(home, usd=0.01, tokens=10, tokens_in=10, tokens_out=0)
    snap = ledger.snapshot(home)
    assert old not in snap["history"]
    assert today in snap["history"]


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


def test_save_swallows_oserror_so_record_does_not_kill_the_turn(
    home: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the daemon hits RLIMIT_NOFILE (FD exhaustion), the ledger temp-file
    write raises OSError. record() must log + drop rather than propagate, or
    a tool-heavy turn dies mid-stream and the desktop never gets reply/done."""
    import alpi.ledger as ledger_mod

    original_write_text = Path.write_text

    def fail_on_tmp(self, *args, **kwargs):
        if self.name.endswith(".json.tmp"):
            raise OSError(24, "Too many open files")
        return original_write_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", fail_on_tmp)
    ledger_mod.record(home, usd=0.10, tokens=50)


def test_spend_archive_deduplicates_retries_but_keeps_recreated_entities(
    home: Path,
) -> None:
    values = {"cost_usd": 0.25, "tokens_in": 100, "tokens_out": 20}
    ledger.archive_entity(home, "workgroup", "proj-x", source_at="first", **values)
    ledger.archive_entity(home, "workgroup", "proj-x", source_at="first", **values)
    ledger.archive_entity(home, "workgroup", "proj-x", source_at="second", **values)
    rows = [row for row in ledger.read_archive(home) if row["id"] == "proj-x"]
    assert [row["source_at"] for row in rows] == ["first", "second"]


def test_budget_usd_or_uncapped(home: Path) -> None:
    assert ledger._budget({}) == (None, 0)
    assert ledger._budget({"daily_usd": 5.0}) == ("usd", 5.0)
    # daily_tokens is no longer a budget kind — uncapped unless daily_usd is set.
    assert ledger._budget({"daily_tokens": 1000}) == (None, 0)
    kind, cap = ledger._budget({"daily_usd": 5.0, "daily_tokens": 100})
    assert kind == "usd" and cap == 5.0
    assert ledger._budget({"daily_usd": 0}) == (None, 0)
