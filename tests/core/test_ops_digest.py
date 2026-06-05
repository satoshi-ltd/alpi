"""OPS.1 — evidence digest aggregator.

Verifies each section reads existing primitives without mutating disk,
window parsing, and end-to-end shape stability for downstream consumers
(JSON output, CLI render, future cli automation)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from alpi import memory, ops_digest, promotion, skills_usage
from alpi.gateway import breaker as br
from alpi.memory import MemoryStore


# ---------- parse_window ----------


@pytest.mark.parametrize("value, expected", [
    ("7d", 7.0),
    ("30d", 30.0),
    ("12h", 0.5),
    ("24h", 1.0),
    ("60m", 60 / 1440.0),
    ("3", 3.0),
    ("0.5", 0.5),
    (7, 7.0),
    (1.5, 1.5),
])
def test_parse_window_accepts_shorthand_and_numeric(value, expected) -> None:
    assert ops_digest.parse_window(value) == pytest.approx(expected)


@pytest.mark.parametrize("value", [
    "", "abc", "7x", "-3d", "0d", "0", -5, 0,
])
def test_parse_window_rejects_invalid(value) -> None:
    with pytest.raises(ValueError):
        ops_digest.parse_window(value)


# ---------- bootstrap fixture ----------


@pytest.fixture
def home(tmp_path: Path) -> Path:
    (tmp_path / "memories").mkdir(parents=True, exist_ok=True)
    MemoryStore(home=tmp_path).seed_defaults()
    return tmp_path


# ---------- tools section ----------


def test_tools_section_counts_unavailable_via_availability_report(
    home: Path, monkeypatch,
) -> None:
    """OPS.1 doesn't enumerate tools itself — it consumes the TL.1
    availability_report so adding a new optional-dep tool elsewhere lands
    in the digest for free."""
    from alpi import tools as tools_mod
    monkeypatch.setattr(
        tools_mod, "availability_report",
        lambda: [
            ("read_file", True, ""),
            ("browser", False, "playwright not installed"),
            ("memory", True, ""),
            ("stt", False, "faster-whisper not installed"),
        ],
    )
    report = ops_digest.run_digest(home, now=1_700_000_000.0)
    assert report.tools.total == 4
    assert ("browser", "playwright not installed") in report.tools.unavailable
    assert ("stt", "faster-whisper not installed") in report.tools.unavailable
    assert len(report.tools.unavailable) == 2


# ---------- gateways section ----------


def test_gateways_section_aggregates_breaker_states(home: Path) -> None:
    """Pulls live state from BreakerStore without writing anything new —
    the digest is downstream of the breaker, not a duplicate state."""
    store = br.BreakerStore(home)
    for _ in range(br.FAILURE_THRESHOLD):
        store.record_failure("telegram", "401", now=1_700_000_000.0)
    store.record_failure("imap", "timeout", now=1_700_000_000.0)
    br._singletons.clear()

    report = ops_digest.run_digest(home, now=1_700_000_000.0 + 60)
    gw = report.gateways
    assert gw.total_tracked == 2
    assert gw.by_state["disabled"] == 1
    assert gw.by_state["degraded"] == 1
    assert any(d["platform"] == "telegram" for d in gw.disabled)
    assert any(d["platform"] == "imap" for d in gw.degraded)
    disabled_tg = next(d for d in gw.disabled if d["platform"] == "telegram")
    assert "cooldown_remaining_s" in disabled_tg
    assert disabled_tg["cooldown_remaining_s"] > 0


def test_gateways_section_empty_when_no_state(home: Path) -> None:
    report = ops_digest.run_digest(home, now=1_700_000_000.0)
    assert report.gateways.total_tracked == 0
    assert report.gateways.degraded == []
    assert report.gateways.disabled == []


# ---------- skills section ----------


def test_skills_section_reuses_telemetry_summary(home: Path) -> None:
    now = 1_700_000_000.0
    day = 86400.0
    skills_usage.record_usage(home, "fresh-skill", "run", now=now - 1 * day)
    skills_usage.record_usage(home, "ageing", "view", now=now - 45 * day)
    skills_usage.record_usage(home, "cold-pin", "view",
                              pinned=True, now=now - 100 * day)

    report = ops_digest.run_digest(home, now=now)
    sk = report.skills
    assert sk.total == 3
    assert sk.by_state["active"] == 1
    assert sk.by_state["stale"] == 1
    assert sk.by_state["archived"] == 1
    assert ("cold-pin", "archived") in sk.pinned_cold
    assert sk.top_used[0][0] == "fresh-skill"


# ---------- memory section ----------


def test_memory_section_pending_queue_oldest_and_targets(home: Path) -> None:
    now = 1_700_000_000.0
    path = promotion.queue_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {"id": "a", "created_at": now - 3 * 86400.0,
         "source": "compaction", "session_id": "s1",
         "model": "m", "target": "USER.md",
         "text": "fact 1", "confidence": "normal", "warnings": []},
        {"id": "b", "created_at": now - 1 * 86400.0,
         "source": "manual", "session_id": "s2",
         "model": "m", "target": "MEMORY.md",
         "text": "fact 2", "confidence": "normal", "warnings": []},
    ]
    path.write_text("\n".join(json.dumps(r) for r in rows))

    report = ops_digest.run_digest(home, now=now)
    mem = report.memory
    assert mem.promotion_pending == 2
    assert mem.promotion_oldest_age_days == pytest.approx(3.0, abs=0.01)
    assert mem.promotion_by_target == {"USER.md": 1, "MEMORY.md": 1}


def test_memory_section_drops_expired_pending(home: Path) -> None:
    """Promotion rows older than ``promotion.MAX_AGE_DAYS`` would be pruned
    on the next write; OPS.1 reads them as already-gone so the count
    matches what the operator would see post-cleanup."""
    now = 1_700_000_000.0
    path = promotion.queue_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "id": "old", "created_at": now - 60 * 86400.0,
        "source": "compaction", "session_id": "s",
        "model": "m", "target": "USER.md",
        "text": "expired", "confidence": "normal", "warnings": [],
    }
    path.write_text(json.dumps(row) + "\n")

    report = ops_digest.run_digest(home, now=now)
    assert report.memory.promotion_pending == 0


def test_memory_section_does_not_rewrite_queue(home: Path) -> None:
    """Trip-wire: the digest must not touch ``promotion_queue.jsonl`` even
    when it observes expired rows. Read-only is a hard guarantee of OPS.1
    so it can be run from cron without surprising mutations."""
    now = 1_700_000_000.0
    path = promotion.queue_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    original = json.dumps({
        "id": "old", "created_at": now - 60 * 86400.0,
        "source": "compaction", "session_id": "s",
        "model": "m", "target": "USER.md",
        "text": "expired", "confidence": "normal", "warnings": [],
    }) + "\n"
    path.write_text(original)

    ops_digest.run_digest(home, now=now)
    assert path.read_text() == original


def test_memory_section_flags_usage_pressure(home: Path) -> None:
    """A USER.md or MEMORY.md at ≥80% of cap is one of the few signals
    worth surfacing in the digest. CM.1 lite (no audit run, just file
    size against cap)."""
    big = "x" * int(memory.USER_CHAR_LIMIT * 0.85)
    (home / "memories" / "USER.md").write_text(big)
    report = ops_digest.run_digest(home, now=1_700_000_000.0)
    assert any("USER.md" in w and "%" in w for w in report.memory.pressure_warnings)


# ---------- compaction section ----------


def test_compaction_section_filters_by_window(home: Path) -> None:
    """Window respects ``--since`` so a 7d invocation drops a 30d-old
    event but keeps a 1d-old one. Same JSONL format as CM.1's audit."""
    now = 1_700_000_000.0
    day = 86400.0
    log = home / "logs" / "compaction.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {"ts": now - 1 * day, "tokens_before": 4000, "tokens_after": 1000, "fired": True},
        {"ts": now - 3 * day, "tokens_before": 2000, "tokens_after": 800, "fired": True},
        {"ts": now - 30 * day, "tokens_before": 1000, "tokens_after": 500, "fired": False},
    ]
    log.write_text("\n".join(json.dumps(r) for r in rows))

    report = ops_digest.run_digest(home, window_days=7.0, now=now)
    c = report.compaction
    assert c.events_in_window == 2
    assert c.fired_pct == pytest.approx(1.0, abs=0.01)
    assert c.avg_ratio == pytest.approx((0.25 + 0.4) / 2, abs=0.01)


def test_compaction_section_handles_missing_log(home: Path) -> None:
    report = ops_digest.run_digest(home)
    assert report.compaction.events_in_window == 0
    assert report.compaction.avg_ratio is None


def test_compaction_section_tolerates_malformed_rows(home: Path) -> None:
    """A corrupt row must not abort the rest of the window — observability
    that crashes on bad data is worse than no observability."""
    now = 1_700_000_000.0
    log = home / "logs" / "compaction.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps({"ts": now - 86400.0, "tokens_before": 2000,
                    "tokens_after": 800, "fired": True}),
        "{not valid json",
        "true",  # not a dict
        json.dumps({"ts": "not-a-number"}),
    ]
    log.write_text("\n".join(lines))

    report = ops_digest.run_digest(home, window_days=7.0, now=now)
    assert report.compaction.events_in_window == 1
    assert report.compaction.fired_pct == 1.0


# ---------- end-to-end ----------


def test_run_digest_returns_complete_report_shape(home: Path) -> None:
    """Smoke test: every section populates without raising on a fresh
    profile. Shape stability matters because the CLI's JSON output is the
    contract for any future automation that consumes the digest."""
    report = ops_digest.run_digest(home, window_days=7.0, now=1_700_000_000.0)
    assert isinstance(report.window_days, float)
    assert report.window_days == 7.0
    assert isinstance(report.tools, ops_digest.ToolsSection)
    assert isinstance(report.gateways, ops_digest.GatewaysSection)
    assert isinstance(report.skills, ops_digest.SkillsSection)
    assert isinstance(report.memory, ops_digest.MemorySection)
    assert isinstance(report.compaction, ops_digest.CompactionSection)
    assert isinstance(report.runs, ops_digest.RunsSection)


def test_run_digest_is_read_only(home: Path) -> None:
    """Trip-wire mirroring ``memory audit``'s read-only test — the digest
    must never write to any directory under the profile root."""
    (home / "memories" / "USER.md").write_text("hello\n")
    (home / "memories" / "MEMORY.md").write_text("world\n")
    skills_usage.record_usage(home, "x", "view")
    snapshot = {
        p: p.read_bytes()
        for p in home.rglob("*")
        if p.is_file()
    }
    ops_digest.run_digest(home, window_days=7.0)
    after = {
        p: p.read_bytes()
        for p in home.rglob("*")
        if p.is_file()
    }
    assert snapshot == after


# ---------- runs section ----------


def test_runs_section_empty_without_ledger(home: Path) -> None:
    report = ops_digest.run_digest(home, now=1_700_000_000.0)
    assert report.runs.total == 0
    assert report.runs.recent_failures == []
    assert report.runs.slowest == []


def test_runs_section_aggregates_ledger(home: Path) -> None:
    from alpi import run_ledger
    run_ledger.record(home, kind="agent", outcome="ok", elapsed_s=1.0, at=1.0)
    run_ledger.record(home, kind="schedule", outcome="timeout", elapsed_s=600.0,
                      at=2.0, timeout_reason="timeout_600s")
    run_ledger.record(home, kind="terminal", outcome="error", elapsed_s=40.0, at=3.0)
    report = ops_digest.run_digest(home, now=1_700_000_000.0)
    runs = report.runs
    assert runs.total == 3
    assert runs.by_kind == {"agent": 1, "schedule": 1, "terminal": 1}
    assert {f["outcome"] for f in runs.recent_failures} == {"timeout", "error"}
    # Slowest first.
    assert runs.slowest[0]["kind"] == "schedule"


def test_runs_section_tolerates_corrupt_ledger(home: Path) -> None:
    (home / "logs").mkdir(parents=True, exist_ok=True)
    (home / "logs" / "runs.jsonl").write_text("not json\n{\"kind\":\"agent\",\"outcome\":\"ok\",\"elapsed_s\":1}\n")
    report = ops_digest.run_digest(home, now=1_700_000_000.0)
    assert report.runs.total == 1  # bad line skipped, valid one kept


# ---------- CLI contract ----------


def test_cli_digest_json_emits_stable_schema(tmp_path: Path, monkeypatch) -> None:
    """``alpi digest --json`` is the contract any future automation
    consumes. This pins the top-level schema so a downstream OPS dashboard
    or external script can't be silently broken by a rename."""
    from click.testing import CliRunner
    from alpi import cli

    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    (tmp_path / "memories").mkdir(parents=True, exist_ok=True)
    MemoryStore(home=tmp_path).seed_defaults()

    result = CliRunner().invoke(cli.main, ["digest", "--json"])
    assert result.exit_code == 0, result.output

    payload = json.loads(result.output)
    assert payload["window_days"] == 7.0
    assert "generated_at" in payload
    for section in ("tools", "gateways", "skills", "memory", "compaction", "runs"):
        assert section in payload, f"missing section: {section}"
    assert "unavailable" in payload["tools"]
    assert "by_state" in payload["gateways"]
    assert "promotion_pending" in payload["memory"]
    assert "events_in_window" in payload["compaction"]
    assert "by_kind" in payload["runs"] and "recent_failures" in payload["runs"]


def test_cli_digest_human_render_includes_each_section(
    tmp_path: Path, monkeypatch,
) -> None:
    """Smoke for the Rich render. Section headers must all appear so the
    operator's quick scan keeps working as new sections get added/renamed."""
    from click.testing import CliRunner
    from alpi import cli

    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    (tmp_path / "memories").mkdir(parents=True, exist_ok=True)
    MemoryStore(home=tmp_path).seed_defaults()

    result = CliRunner().invoke(cli.main, ["digest"])
    assert result.exit_code == 0, result.output
    out = result.output
    assert "digest" in out
    assert "window:" in out
    for heading in ("Tools", "Gateways", "Skills", "Memory", "Compaction", "Runs"):
        assert heading in out, f"missing section heading: {heading}"


def test_cli_digest_respects_since_flag(tmp_path: Path, monkeypatch) -> None:
    """``alpi digest --since 24h`` lands as window_days=1.0 in the JSON output so
    downstream automation can plumb the window through reliably."""
    from click.testing import CliRunner
    from alpi import cli

    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    (tmp_path / "memories").mkdir(parents=True, exist_ok=True)
    MemoryStore(home=tmp_path).seed_defaults()

    result = CliRunner().invoke(
        cli.main, ["digest", "--since", "24h", "--json"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["window_days"] == pytest.approx(1.0)


def test_cli_digest_rejects_invalid_since(tmp_path: Path, monkeypatch) -> None:
    """A garbage ``--since`` surfaces a clear ClickException with non-zero
    exit, not a silent fallback to the default. Operator scripts can rely
    on the failure being explicit."""
    from click.testing import CliRunner
    from alpi import cli

    monkeypatch.setenv("ALPI_HOME", str(tmp_path))

    result = CliRunner().invoke(cli.main, ["digest", "--since", "wibble"])
    assert result.exit_code != 0
    assert "invalid window" in result.output.lower()
