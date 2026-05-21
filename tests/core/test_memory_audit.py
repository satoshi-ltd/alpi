"""CM.1 — memory audit (read-only).

Each category (usage, stale, duplicate clusters, operational state,
promotion queue, compaction stats) is unit-tested in isolation. An
integration test drives the full ``run_audit`` against a populated home."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from alpi import memory_audit, promotion
from alpi.memory import (
    ENTRY_DELIMITER,
    LOW_CONFIDENCE_MAX_AGE_DAYS,
    MEMORY_CHAR_LIMIT,
    USER_CHAR_LIMIT,
    MemoryStore,
)


@pytest.fixture
def home(tmp_path: Path) -> Path:
    (tmp_path / "memories").mkdir(parents=True, exist_ok=True)
    MemoryStore(home=tmp_path).seed_defaults()
    return tmp_path


def _write_user(home: Path, entries: list[str]) -> None:
    (home / "memories" / "USER.md").write_text(ENTRY_DELIMITER.join(entries))


def _write_memory(home: Path, entries: list[str]) -> None:
    (home / "memories" / "MEMORY.md").write_text(ENTRY_DELIMITER.join(entries))


def _write_agent(home: Path, paragraphs: list[str]) -> None:
    (home / "memories" / "AGENT.md").write_text("\n\n".join(paragraphs))


def _entry(text: str, *, conf: str = "normal", captured: str = "2026-05-21",
           reinforced: int = 0) -> str:
    return (
        f"{text}\n<!-- alpi-meta conf={conf} "
        f"captured={captured} reinforced={reinforced} -->"
    )


# ---------- usage ----------


def test_usage_reports_used_chars_and_limits(home: Path) -> None:
    _write_user(home, [_entry("a" * 100)])
    _write_memory(home, [_entry("b" * 200)])
    _write_agent(home, ["short paragraph"])

    report = memory_audit.run_audit(home)
    by_name = {u.name: u for u in report.usage}

    assert by_name["USER.md"].limit == USER_CHAR_LIMIT
    assert by_name["MEMORY.md"].limit == MEMORY_CHAR_LIMIT
    assert by_name["AGENT.md"].limit is None
    assert by_name["USER.md"].used == 100
    assert by_name["MEMORY.md"].used == 200
    assert by_name["AGENT.md"].used == len("short paragraph")
    assert by_name["AGENT.md"].percent is None


def test_pressure_warning_fires_at_80_percent(home: Path) -> None:
    big = _entry("x" * int(USER_CHAR_LIMIT * 0.85))
    _write_user(home, [big])

    report = memory_audit.run_audit(home)
    assert any("USER.md" in w and "%" in w for w in report.pressure_warnings)


def test_no_pressure_warning_when_under_threshold(home: Path) -> None:
    _write_user(home, [_entry("x" * 100)])

    report = memory_audit.run_audit(home)
    assert report.pressure_warnings == []


def test_usage_matches_memorystore_for_capped_files(home: Path) -> None:
    """The audit must report the same `used` chars MemoryStore.usage() does
    — otherwise an entry-only sum would silently under-count delimiters and
    blank lines and miss pressure warnings near the cap."""
    _write_user(home, [_entry("alpha"), _entry("beta"), _entry("gamma")])
    _write_memory(home, [_entry("one"), _entry("two")])

    store_usage = MemoryStore(home=home).usage()
    report = memory_audit.run_audit(home)
    by_name = {u.name: u for u in report.usage}

    assert by_name["USER.md"].used == store_usage["USER.md"][0]
    assert by_name["MEMORY.md"].used == store_usage["MEMORY.md"][0]


# ---------- stale ----------


def test_stale_flags_low_confidence_older_than_30d(home: Path) -> None:
    today = date(2026, 5, 21)
    old = (today - timedelta(days=LOW_CONFIDENCE_MAX_AGE_DAYS + 5)).isoformat()
    recent = (today - timedelta(days=5)).isoformat()

    _write_user(home, [
        _entry("old guess", conf="low", captured=old),
        _entry("recent guess", conf="low", captured=recent),
        _entry("durable fact", conf="normal", captured=old),
    ])

    report = memory_audit.run_audit(home, today=today)
    files_indexes = {(s.file, s.index) for s in report.stale}
    assert ("USER.md", 0) in files_indexes
    assert ("USER.md", 1) not in files_indexes  # not yet expired
    assert ("USER.md", 2) not in files_indexes  # normal-confidence, never expires here


def test_stale_skips_reinforced_low_confidence(home: Path) -> None:
    today = date(2026, 5, 21)
    old = (today - timedelta(days=60)).isoformat()
    _write_user(home, [_entry("reinforced", conf="low", captured=old, reinforced=2)])

    report = memory_audit.run_audit(home, today=today)
    assert report.stale == []


# ---------- duplicate clusters ----------


def test_duplicates_runs_threshold_sweep_with_default_set(home: Path) -> None:
    _write_user(home, [_entry("user lives in Phuket Thailand")])
    report = memory_audit.run_audit(home)
    thresholds = [d.threshold for d in report.duplicates]
    assert thresholds == list(memory_audit.DEFAULT_THRESHOLDS)


def test_duplicates_finds_cluster_at_lower_threshold_but_not_higher(home: Path) -> None:
    """Two entries share three content tokens out of five → overlap coefficient 0.6.
    At threshold 0.5 they cluster; at 0.7+ they don't. Confirms the
    parameterised dedup actually flexes with the threshold."""
    _write_user(home, [
        _entry("alpha beta gamma delta epsilon"),
        _entry("alpha beta gamma zeta eta theta"),
    ])

    report = memory_audit.run_audit(home, thresholds=(0.5, 0.7))
    low = next(d for d in report.duplicates if d.threshold == 0.5)
    high = next(d for d in report.duplicates if d.threshold == 0.7)

    assert any(c.file == "USER.md" and len(c.members) == 2 for c in low.clusters)
    assert all(c.file != "USER.md" or len(c.members) < 2 for c in high.clusters)


def test_duplicates_clusters_three_way_via_union_find(home: Path) -> None:
    """A~B and B~C but A and C don't share tokens directly. Union-find
    should still cluster {A, B, C} as one group."""
    _write_user(home, [
        _entry("apple banana cherry"),       # A ~ B (apple banana)
        _entry("apple banana grape mango"),  # B
        _entry("grape mango plum"),          # C ~ B (grape mango)
    ])

    report = memory_audit.run_audit(home, thresholds=(0.5,))
    clusters = report.duplicates[0].clusters
    assert any(
        c.file == "USER.md" and set(i for i, _ in c.members) == {0, 1, 2}
        for c in clusters
    )


def test_duplicates_singletons_are_omitted(home: Path) -> None:
    _write_user(home, [
        _entry("apple banana"),
        _entry("zebra warthog"),
    ])

    report = memory_audit.run_audit(home, thresholds=(0.5,))
    assert report.duplicates[0].clusters == []


# ---------- operational state ----------


def test_operational_flags_chat_id_style_entries(home: Path) -> None:
    _write_user(home, [
        _entry("user lives in Phuket"),
        _entry("chat_id 1234567890 sent a follow-up at 2026-05-21T10:00"),
    ])

    report = memory_audit.run_audit(home)
    flagged = {(op.file, op.index) for op in report.operational}
    assert ("USER.md", 1) in flagged
    assert ("USER.md", 0) not in flagged


# ---------- promotion queue ----------


def test_promotion_reports_pending_count_and_oldest(home: Path) -> None:
    now = 1_716_000_000.0  # arbitrary, deterministic
    path = promotion.queue_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {"id": "a", "created_at": now - 86400 * 3,
         "source": "compaction", "session_id": "s1",
         "model": "m", "target": "USER.md",
         "text": "fact 1", "confidence": "normal", "warnings": []},
        {"id": "b", "created_at": now - 86400 * 1,
         "source": "manual", "session_id": "s2",
         "model": "m", "target": "MEMORY.md",
         "text": "fact 2", "confidence": "normal", "warnings": []},
    ]
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n")

    report = memory_audit.run_audit(home, now=now)
    assert report.promotion.pending == 2
    assert report.promotion.oldest_age_days == pytest.approx(3.0, abs=0.01)
    assert report.promotion.by_target == {"USER.md": 1, "MEMORY.md": 1}


def test_promotion_audit_does_not_rewrite_queue(home: Path) -> None:
    """Read-only invariant: even when expired rows would normally be
    pruned, the audit must not touch the file on disk."""
    now = 1_716_000_000.0
    path = promotion.queue_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    expired_row = {
        "id": "old", "created_at": now - 86400 * 60,  # 60 days, past cap
        "source": "compaction", "session_id": "s",
        "model": "m", "target": "USER.md",
        "text": "expired", "confidence": "normal", "warnings": [],
    }
    original = json.dumps(expired_row) + "\n"
    path.write_text(original)

    memory_audit.run_audit(home, now=now)
    assert path.read_text() == original


# ---------- compaction stats ----------


def test_compaction_aggregates_recent_events(home: Path) -> None:
    now = 1_716_000_000.0
    log_dir = home / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    rows = [
        # Within 7d
        {"ts": now - 86400 * 1, "tokens_before": 4000, "tokens_after": 1000, "fired": True},
        {"ts": now - 86400 * 3, "tokens_before": 2000, "tokens_after": 800,  "fired": True},
        # Within 30d but not 7d
        {"ts": now - 86400 * 15, "tokens_before": 1000, "tokens_after": 600, "fired": False},
        # Older than 30d (ignored)
        {"ts": now - 86400 * 60, "tokens_before": 1000, "tokens_after": 100, "fired": True},
    ]
    (log_dir / "compaction.jsonl").write_text("\n".join(json.dumps(r) for r in rows))

    report = memory_audit.run_audit(home, now=now)
    assert report.compaction.events_7d == 2
    assert report.compaction.events_30d == 3
    assert report.compaction.fired_pct == pytest.approx(2 / 3, abs=0.01)
    # Avg ratio over the 30d window: (0.25 + 0.4 + 0.6) / 3
    assert report.compaction.avg_ratio == pytest.approx((0.25 + 0.4 + 0.6) / 3, abs=0.01)


def test_compaction_handles_missing_log_gracefully(home: Path) -> None:
    report = memory_audit.run_audit(home)
    assert report.compaction.events_7d == 0
    assert report.compaction.events_30d == 0
    assert report.compaction.avg_ratio is None
    assert report.compaction.fired_pct is None


# ---------- end-to-end ----------


def test_run_audit_returns_complete_report_shape(home: Path) -> None:
    """Smoke test that every category populates without raising on a fresh
    profile. AuditReport fields are stable enough to consume from OPS.1."""
    report = memory_audit.run_audit(home)
    assert isinstance(report.usage, list) and len(report.usage) == 3
    assert isinstance(report.stale, list)
    assert isinstance(report.duplicates, list)
    assert len(report.duplicates) == len(memory_audit.DEFAULT_THRESHOLDS)
    assert isinstance(report.operational, list)
    assert report.promotion.pending == 0
    assert report.compaction.events_30d == 0


def test_promotion_queue_tolerates_malformed_lines(home: Path) -> None:
    """A corrupt JSONL row (bad json, non-dict, non-numeric created_at) must
    not abort the audit — the surrounding good rows still count. An audit
    that crashes on bad data is worse than no audit."""
    now = 1_716_000_000.0
    path = promotion.queue_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    good = {
        "id": "ok", "created_at": now - 86400,
        "source": "compaction", "session_id": "s",
        "model": "m", "target": "USER.md",
        "text": "fact", "confidence": "normal", "warnings": [],
    }
    weird_created_at = {**good, "id": "weird", "created_at": "not-a-number"}
    lines = [
        json.dumps(good),
        "{not valid json",          # malformed line
        "[\"array not dict\"]",      # parses but not a dict
        json.dumps(weird_created_at),
    ]
    path.write_text("\n".join(lines) + "\n")

    report = memory_audit.run_audit(home, now=now)
    # Good row counted; weird_created_at falls back to 0 → still under MAX_AGE_DAYS at small `now`, but ages > 30d at our chosen `now` so it's filtered out by the rolling window.
    assert report.promotion.pending == 1


def test_compaction_tolerates_malformed_rows(home: Path) -> None:
    """Same robustness requirement for the compaction log: bad lines are
    skipped, good ones still contribute. Non-numeric tokens_before falls
    back to 0 and the ratio entry is dropped (no divide-by-zero)."""
    now = 1_716_000_000.0
    log_dir = home / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    rows = [
        {"ts": now - 86400, "tokens_before": 2000, "tokens_after": 800, "fired": True},
        "this is not json",  # noqa: E501
        {"ts": "not-a-number", "tokens_before": 1000, "tokens_after": 500, "fired": True},
        {"ts": now - 86400 * 2, "tokens_before": "bad", "tokens_after": "bad", "fired": False},
    ]
    (log_dir / "compaction.jsonl").write_text(
        "\n".join(r if isinstance(r, str) else json.dumps(r) for r in rows)
    )

    report = memory_audit.run_audit(home, now=now)
    # Good row (#1) contributes; #2 is malformed; #3 has ts=0 → falls outside the 30d window and is skipped; #4 has bad token counts → counted but no ratio entry.
    assert report.compaction.events_30d == 2
    assert report.compaction.avg_ratio == pytest.approx(0.4, abs=0.01)


def test_stale_tolerates_malformed_reinforced_meta(home: Path) -> None:
    """A hand-edited entry where ``reinforced`` is not numeric should still
    parse cleanly and treat the entry as reinforced=0 (the safest read)."""
    today = date(2026, 5, 21)
    old = (today - timedelta(days=60)).isoformat()
    weird = (
        "hand-edited fact\n"
        f"<!-- alpi-meta conf=low captured={old} reinforced=lots -->"
    )
    _write_user(home, [weird])

    report = memory_audit.run_audit(home, today=today)
    assert any(s.file == "USER.md" and s.reinforced == 0 for s in report.stale)


def test_run_audit_is_read_only(home: Path) -> None:
    """Trip-wire: snapshot every memory-related file before/after audit and
    fail if any of them changed."""
    _write_user(home, [_entry("fact one"), _entry("fact two")])
    _write_memory(home, [_entry("fact three")])
    _write_agent(home, ["paragraph one", "paragraph two"])

    snapshot = {p: p.read_bytes() for p in (home / "memories").rglob("*") if p.is_file()}
    memory_audit.run_audit(home)
    after = {p: p.read_bytes() for p in (home / "memories").rglob("*") if p.is_file()}
    assert snapshot == after
