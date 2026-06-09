from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from alpi import ledger
from alpi.host import usage


def test_bucket_history_windows_last_14_days() -> None:
    today = date(2026, 6, 9)
    history = {
        "2026-06-09": {"usd": 0.31, "tokens": 28539, "tokens_in": 27700, "tokens_out": 839},
        "2026-06-08": {"usd": 0.10, "tokens": 5000, "tokens_in": 4000, "tokens_out": 1000},
        "2026-05-01": {"usd": 9.0, "tokens": 1, "tokens_in": 1, "tokens_out": 0},
    }
    out = usage.bucket_history(history, today)
    assert len(out) == 14
    assert out[-1] == {"iso": "2026-06-09", "tokIn": 27700, "tokOut": 839, "cost": 0.31}
    assert out[-2] == {"iso": "2026-06-08", "tokIn": 4000, "tokOut": 1000, "cost": 0.1}
    assert out[-3] == {"iso": "2026-06-07", "tokIn": 0, "tokOut": 0, "cost": 0.0}
    assert sum(d["cost"] for d in out) == pytest.approx(0.41)


def test_compute_daily_reads_ledger_history(tmp_path: Path) -> None:
    ledger.record(tmp_path, usd=0.05, tokens=1500, tokens_in=1200, tokens_out=300)
    ledger.record(tmp_path, usd=0.30, tokens=0)
    out = usage.compute_daily(tmp_path)
    today_iso = datetime.now(timezone.utc).date().isoformat()
    assert out[-1]["iso"] == today_iso
    assert out[-1]["cost"] == pytest.approx(0.35)
    assert out[-1]["tokIn"] == 1200
    assert out[-1]["tokOut"] == 300


def test_iso_day_is_utc_not_host_local() -> None:
    assert usage._iso_day("2026-06-08T23:30:00Z") == date(2026, 6, 8)
    assert usage._iso_day("2026-06-09T00:30:00Z") == date(2026, 6, 9)


def test_bucket_workgroup_buckets_by_utc_day() -> None:
    out = usage.bucket_workgroup(
        [{"ts": "2026-06-08T23:30:00Z",
          "cost": {"usd": 0.02, "tokens": 150, "tokens_in": 100, "tokens_out": 50}}],
        date(2026, 6, 9),
    )
    rec = next(d for d in out if d["iso"] == "2026-06-08")
    assert rec["tokIn"] == 100
    assert rec["tokOut"] == 50
    assert rec["cost"] == 0.02
    assert out[-1]["iso"] == "2026-06-09"
    assert out[-1]["cost"] == 0.0


def test_bucket_workgroup_uses_real_split_when_present() -> None:
    ts = "2026-06-09T12:00:00Z"
    today = usage._iso_day(ts)
    out = usage.bucket_workgroup(
        [{"ts": ts, "cost": {"usd": 0.05, "tokens": 1000, "tokens_in": 700, "tokens_out": 300}}],
        today,
    )
    assert out[-1]["tokIn"] == 700
    assert out[-1]["tokOut"] == 300
    assert out[-1]["cost"] == 0.05


def test_bucket_workgroup_attributes_historical_combined_to_input() -> None:
    ts = "2026-06-09T12:00:00Z"
    today = usage._iso_day(ts)
    out = usage.bucket_workgroup([{"ts": ts, "cost": {"usd": 0.05, "tokens": 1000}}], today)
    assert out[-1]["tokIn"] == 1000
    assert out[-1]["tokOut"] == 0


def test_bucket_workgroup_skips_costless_and_bad_ts() -> None:
    out = usage.bucket_workgroup(
        [
            {"ts": "2026-06-09T12:00:00Z"},
            {"cost": {"usd": 1.0, "tokens": 5}},
            {"ts": "garbage", "cost": {"usd": 1.0, "tokens": 5}},
        ],
        date(2026, 6, 9),
    )
    assert sum(d["tokIn"] + d["tokOut"] for d in out) == 0
    assert sum(d["cost"] for d in out) == 0


def test_compute_workgroup_daily_reads_transcript(tmp_path: Path) -> None:
    ts = "2026-06-09T12:00:00Z"
    today = usage._iso_day(ts)
    d = tmp_path / "alp" / "workgroups" / "wg1"
    d.mkdir(parents=True)
    (d / "transcript.jsonl").write_text(
        json.dumps({"seq": 1, "ts": ts, "from": "x",
                    "cost": {"usd": 0.05, "tokens": 1000, "tokens_in": 700, "tokens_out": 300}})
        + "\n"
        + json.dumps({"seq": 2, "ts": ts, "from": "x", "nonce": "n", "ciphertext": "c"})
        + "\n",
    )
    out = usage.compute_workgroup_daily(tmp_path, "wg1", today=today)
    assert out[-1]["tokIn"] == 700
    assert out[-1]["tokOut"] == 300
    assert out[-1]["cost"] == 0.05
