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
    assert snap["profile"] == {
        "usd": pytest.approx(0.22), "tokens": 1500,
        "tokens_cached": 0, "tokens_measured": 0,
    }
    assert snap["by_peer"]["__interactive__"] == {
        "usd": pytest.approx(0.22),
        "tokens": 1500,
        "tokens_cached": 0, "tokens_measured": 0,
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
        "tokens_cached": 0,
        "tokens_measured": 0,
        "by_connection": {
            "host": {
                "usd": pytest.approx(0.35),
                "tokens": 1500,
                "tokens_in": 1200,
                "tokens_out": 300,
                "tokens_cached": 0,
                "tokens_measured": 0,
            },
        },
    }


def test_free_model_usage_recorded_at_zero_cost(home: Path) -> None:
    ledger.record(home, usd=0.0, tokens=5000, tokens_in=4800, tokens_out=200)
    snap = ledger.snapshot(home)
    today = datetime.now(timezone.utc).date().isoformat()
    assert snap["history"][today] == {
        "usd": 0.0, "tokens": 5000, "tokens_in": 4800, "tokens_out": 200,
        "tokens_cached": 0, "tokens_measured": 0,
        "by_connection": {
            "host": {
                "usd": 0.0, "tokens": 5000,
                "tokens_in": 4800, "tokens_out": 200,
                "tokens_cached": 0, "tokens_measured": 0,
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


def test_measured_completions_build_cache_buckets(home: Path) -> None:
    ledger.record(home, usd=0.01, tokens=1050, tokens_in=1000, tokens_out=50,
                  tokens_cached=800)
    ledger.record(home, usd=0.01, tokens=520, tokens_in=500, tokens_out=20,
                  tokens_cached=0)
    snap = ledger.snapshot(home)
    today = datetime.now(timezone.utc).date().isoformat()
    assert snap["profile"]["tokens_cached"] == 800
    assert snap["profile"]["tokens_measured"] == 1500, (
        "a reported zero is a measured miss and grows the denominator"
    )
    assert snap["by_peer"]["__interactive__"]["tokens_cached"] == 800
    assert snap["by_connection"]["host"]["tokens_measured"] == 1500
    assert snap["history"][today]["tokens_cached"] == 800
    assert snap["history"][today]["tokens_measured"] == 1500


def test_unmeasured_traffic_never_grows_the_denominator(home: Path) -> None:
    ledger.record(home, usd=0.01, tokens=1050, tokens_in=1000, tokens_out=50)
    snap = ledger.snapshot(home)
    today = datetime.now(timezone.utc).date().isoformat()
    for entry in (snap["profile"], snap["by_peer"]["__interactive__"],
                  snap["by_connection"]["host"], snap["history"][today]):
        assert entry["tokens_cached"] == 0
        assert entry["tokens_measured"] == 0, (
            "unreported completions must stay out of the hit-rate denominator"
        )
        assert "cache_discount_usd" not in entry


def test_malformed_cached_value_degrades_to_unmeasured(home: Path) -> None:
    ledger.record(home, usd=0.01, tokens=100, tokens_in=90, tokens_out=10,
                  tokens_cached="abc")
    snap = ledger.snapshot(home)
    assert snap["profile"]["tokens_cached"] == 0
    assert snap["profile"]["tokens_measured"] == 0


def test_cache_discount_and_cost_source_accumulate_in_history(home: Path) -> None:
    ledger.record(home, usd=0.02, tokens=100, tokens_in=90, tokens_out=10,
                  tokens_cached=50, cache_discount_usd=0.011, cost_source="provider")
    ledger.record(home, usd=0.02, tokens=100, tokens_in=90, tokens_out=10,
                  cache_discount_usd=0.004, cost_source="table")
    ledger.record(home, usd=0.02, tokens=100, tokens_in=90, tokens_out=10,
                  cost_source="provider")
    snap = ledger.snapshot(home)
    today = datetime.now(timezone.utc).date().isoformat()
    h = snap["history"][today]
    assert h["cache_discount_usd"] == pytest.approx(0.015)
    assert h["cost_sources"] == {"provider": 2, "table": 1}
    assert snap["profile"]["cache_discount_usd"] == pytest.approx(0.015)


def test_record_completion_carries_cache_fields(home: Path) -> None:
    from types import SimpleNamespace
    ledger.record_completion(home, SimpleNamespace(
        input_tokens=1000, output_tokens=50, cost_usd=0.01,
        cached_tokens=700, cache_discount=0.005, cost_source="provider",
    ))
    snap = ledger.snapshot(home)
    assert snap["profile"]["tokens_cached"] == 700
    assert snap["profile"]["tokens_measured"] == 1000
    assert snap["profile"]["cache_discount_usd"] == pytest.approx(0.005)
    today = datetime.now(timezone.utc).date().isoformat()
    assert snap["history"][today]["cost_sources"] == {"provider": 1}


def test_cache_keys_survive_day_rollover(home: Path) -> None:
    yesterday = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
    with _set_day(yesterday):
        ledger.record(home, usd=0.01, tokens=1050, tokens_in=1000, tokens_out=50,
                      tokens_cached=800, cache_discount_usd=0.002)
    snap = ledger.snapshot(home)
    rolled = snap["history"][yesterday]
    assert rolled["tokens_cached"] == 800
    assert rolled["tokens_measured"] == 1000
    assert rolled["cache_discount_usd"] == pytest.approx(0.002)


def test_rollover_of_pre_cache_day_defaults_to_zero_counts(home: Path) -> None:
    yesterday = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
    ledger.save(home, {
        "day": yesterday,
        "profile": {"usd": 1.0, "tokens": 10},
        "by_peer": {}, "by_connection": {}, "history": {},
    })
    snap = ledger.snapshot(home)
    rolled = snap["history"][yesterday]
    assert rolled["tokens_cached"] == 0
    assert rolled["tokens_measured"] == 0
    assert rolled["cache_discount_usd"] == 0.0


def test_cache_summary_windows_and_sums_raw_counts(home: Path) -> None:
    d0 = datetime.now(timezone.utc).date()
    recent = (d0 - timedelta(days=2)).isoformat()
    old = (d0 - timedelta(days=20)).isoformat()
    with _set_day(recent):
        ledger.record(home, usd=0.01, tokens=1000, tokens_in=900, tokens_out=100,
                      tokens_cached=600, cache_discount_usd=0.003, cost_source="provider")
    with _set_day(old):
        ledger.record(home, usd=0.01, tokens=1000, tokens_in=900, tokens_out=100,
                      tokens_cached=900, cost_source="provider")
    s = ledger.cache_summary(home, days=7)
    assert s["tokens_cached"] == 600
    assert s["tokens_measured"] == 900
    assert s["days"] == 1
    assert s["cache_discount_usd"] == pytest.approx(0.003)
    assert s["cost_sources"] == {"provider": 1}
    wide = ledger.cache_summary(home, days=30)
    assert wide["tokens_cached"] == 1500
    assert wide["days"] == 2


def test_cache_summary_counts_cost_sources_of_unmeasured_days(home: Path) -> None:
    """A day priced entirely by list-price arithmetic with no cache info is exactly what the histogram exists to surface — it must not be skipped."""
    d0 = datetime.now(timezone.utc).date()
    unmeasured_day = (d0 - timedelta(days=2)).isoformat()
    with _set_day(unmeasured_day):
        ledger.record(home, usd=0.05, tokens=1000, tokens_in=900, tokens_out=100,
                      cost_source="litellm")
    ledger.record(home, usd=0.01, tokens=100, tokens_in=90, tokens_out=10,
                  tokens_cached=50, cost_source="provider")
    s = ledger.cache_summary(home, days=7)
    assert s["cost_sources"] == {"litellm": 1, "provider": 1}
    assert s["days"] == 1, "cost sources aggregate; the unmeasured day still adds no cache day"


def test_cache_summary_window_is_exactly_n_days(home: Path) -> None:
    d0 = datetime.now(timezone.utc).date()
    inside = (d0 - timedelta(days=6)).isoformat()
    outside = (d0 - timedelta(days=7)).isoformat()
    for day in (inside, outside):
        with _set_day(day):
            ledger.record(home, usd=0.01, tokens=100, tokens_in=90, tokens_out=10,
                          tokens_cached=30)
    s = ledger.cache_summary(home, days=7)
    assert s["tokens_cached"] == 30, "days=7 covers exactly 7 calendar dates ending today"
    assert s["days"] == 1


def test_negative_discount_nets_down_the_day_total(home: Path) -> None:
    ledger.record(home, usd=0.02, tokens=100, tokens_in=90, tokens_out=10,
                  tokens_cached=10, cache_discount_usd=0.010)
    ledger.record(home, usd=0.02, tokens=100, tokens_in=90, tokens_out=10,
                  tokens_cached=0, cache_discount_usd=-0.004)
    snap = ledger.snapshot(home)
    assert snap["profile"]["cache_discount_usd"] == pytest.approx(0.006)
    s = ledger.cache_summary(home, days=1)
    assert s["cache_discount_usd"] == pytest.approx(0.006)


def test_corrupt_persisted_cache_values_do_not_kill_a_recording_turn(home: Path) -> None:
    today = datetime.now(timezone.utc).date().isoformat()
    ledger.save(home, {
        "day": today,
        "profile": {"usd": 0.1, "tokens": 10, "tokens_cached": "abc",
                    "tokens_measured": None, "cache_discount_usd": "x"},
        "by_peer": {}, "by_connection": {}, "history": {},
    })
    ledger.record(home, usd=0.01, tokens=100, tokens_in=90, tokens_out=10,
                  tokens_cached=50, cache_discount_usd=0.001)
    snap = ledger.snapshot(home)
    assert snap["profile"]["tokens_cached"] == 50
    assert snap["profile"]["tokens_measured"] == 90


def test_corrupt_cache_values_survive_rollover(home: Path) -> None:
    yesterday = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
    ledger.save(home, {
        "day": yesterday,
        "profile": {"usd": 1.0, "tokens": 10, "tokens_cached": "abc"},
        "by_peer": {}, "by_connection": {}, "history": {},
    })
    snap = ledger.snapshot(home)
    assert snap["history"][yesterday]["tokens_cached"] == 0


def test_cache_summary_ignores_future_dated_entries(home: Path) -> None:
    future = (datetime.now(timezone.utc).date() + timedelta(days=3)).isoformat()
    with _set_day(future):
        ledger.record(home, usd=0.01, tokens=100, tokens_in=90, tokens_out=10,
                      tokens_cached=90, cost_source="provider")
    ledger.record(home, usd=0.01, tokens=100, tokens_in=90, tokens_out=10,
                  tokens_cached=30)
    s = ledger.cache_summary(home, days=7)
    assert s["tokens_cached"] == 30, "clock-skewed future days must not enter any window"
    assert s["cost_sources"] == {}
    assert s["days"] == 1
