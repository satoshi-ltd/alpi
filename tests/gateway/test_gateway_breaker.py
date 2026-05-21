"""GW.1 — per profile + platform circuit breaker.

Verifies state transitions (healthy → degraded → disabled → healthy),
exponential backoff math, persistence across BreakerStore instances, and
the singleton-per-home contract that lets async tasks share state."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from alpi.gateway import breaker as br


def test_fresh_platform_is_healthy(tmp_path: Path) -> None:
    store = br.BreakerStore(tmp_path)
    st = store.state_of("telegram")
    assert st.status == "healthy"
    assert st.consecutive_failures == 0
    assert st.last_error == ""
    assert store.should_skip("telegram") is False


def test_first_failure_moves_to_degraded(tmp_path: Path) -> None:
    store = br.BreakerStore(tmp_path)
    prev, curr = store.record_failure("telegram", "timeout", now=1000.0)
    assert prev == "healthy"
    assert curr == "degraded"
    st = store.state_of("telegram")
    assert st.consecutive_failures == 1
    assert st.last_error == "timeout"
    assert st.last_error_at == 1000.0
    assert st.status == "degraded"
    assert store.should_skip("telegram", now=1000.0) is False


def test_threshold_failures_flip_to_disabled_with_backoff(tmp_path: Path) -> None:
    """At ``FAILURE_THRESHOLD`` consecutive failures the platform is locked out for the base backoff window. The fifth failure triggers, not the sixth."""
    store = br.BreakerStore(tmp_path)
    for i in range(br.FAILURE_THRESHOLD - 1):
        _, curr = store.record_failure("imap", f"err {i}", now=1000.0 + i)
        assert curr == "degraded"
    _, curr = store.record_failure("imap", "boom", now=2000.0)
    assert curr == "disabled"
    st = store.state_of("imap")
    assert st.disabled_until == 2000.0 + br.BACKOFF_BASE_S
    assert store.should_skip("imap", now=2000.0 + 60) is True
    assert store.should_skip("imap", now=st.disabled_until + 1) is False


def test_backoff_doubles_up_to_cap(tmp_path: Path) -> None:
    """Each additional failure past the threshold doubles the cooldown so
    a broken platform doesn't pummel the upstream — capped at BACKOFF_CAP_S."""
    store = br.BreakerStore(tmp_path)
    for i in range(br.FAILURE_THRESHOLD + 5):
        store.record_failure("gmail", f"err", now=1000.0)
    st = store.state_of("gmail")
    assert st.disabled_until - 1000.0 == br.BACKOFF_CAP_S


def test_success_resets_counter_and_restores_healthy(tmp_path: Path) -> None:
    store = br.BreakerStore(tmp_path)
    for _ in range(7):
        store.record_failure("matrix", "down", now=1000.0)
    assert store.state_of("matrix").status == "disabled"
    prev, curr = store.record_success("matrix", now=2000.0)
    assert prev == "disabled"
    assert curr == "healthy"
    st = store.state_of("matrix")
    assert st.consecutive_failures == 0
    assert st.disabled_until == 0.0
    assert st.last_error == ""
    assert st.last_success_at == 2000.0
    assert store.should_skip("matrix") is False


def test_state_persists_across_instances(tmp_path: Path) -> None:
    """A daemon restart must not forget that telegram was disabled — the
    breaker exists to AVOID hammering the upstream, restoring it to
    healthy on every restart would defeat the purpose."""
    a = br.BreakerStore(tmp_path)
    for _ in range(br.FAILURE_THRESHOLD):
        a.record_failure("telegram", "401", now=1000.0)
    assert a.state_of("telegram").status == "disabled"

    b = br.BreakerStore(tmp_path)
    st = b.state_of("telegram")
    assert st.status == "disabled"
    assert st.consecutive_failures == br.FAILURE_THRESHOLD
    assert st.last_error == "401"


def test_for_home_returns_singleton(tmp_path: Path) -> None:
    """Two callers asking ``for_home(same_path)`` get the SAME store. Otherwise the in-memory cache + atomic-write pattern would race when an async loop and a sync ``alpi doctor`` invocation hit the file simultaneously."""
    a = br.for_home(tmp_path)
    b = br.for_home(tmp_path)
    assert a is b


def test_for_home_separates_by_profile(tmp_path: Path) -> None:
    p1 = tmp_path / "profiles" / "alice"; p1.mkdir(parents=True)
    p2 = tmp_path / "profiles" / "bob"; p2.mkdir(parents=True)
    a = br.for_home(p1)
    b = br.for_home(p2)
    assert a is not b


def test_corrupt_state_file_falls_back_to_healthy(tmp_path: Path) -> None:
    """A garbled .breaker-state.json must not crash the daemon — the
    breaker is non-critical infrastructure; better to lose its memory
    than block the gateway loop on a JSON parse error."""
    path = tmp_path / "gateway" / ".breaker-state.json"
    path.parent.mkdir(parents=True)
    path.write_text("{not json")
    store = br.BreakerStore(tmp_path)
    assert store.state_of("telegram").status == "healthy"


def test_record_failure_truncates_long_error_text(tmp_path: Path) -> None:
    """Some upstream errors include the full HTTP body. Cap at 300 chars so the state file stays bounded across many failures."""
    store = br.BreakerStore(tmp_path)
    store.record_failure("telegram", "x" * 5000, now=1000.0)
    assert len(store.state_of("telegram").last_error) == 300


def test_reset_clears_state(tmp_path: Path) -> None:
    store = br.BreakerStore(tmp_path)
    for _ in range(br.FAILURE_THRESHOLD):
        store.record_failure("telegram", "err", now=1000.0)
    assert store.state_of("telegram").status == "disabled"
    store.reset("telegram")
    assert store.state_of("telegram").status == "healthy"


def test_emit_state_event_skips_no_op_transitions(tmp_path: Path, monkeypatch) -> None:
    """Only real transitions emit. Re-asserting the same status (e.g., another
    failure while already degraded) must not flood the event log."""
    emits: list[tuple[str, dict]] = []
    from alpi.host import events as host_events
    monkeypatch.setattr(
        host_events, "emit",
        lambda kind, data=None: emits.append((kind, data or {})),
    )

    br.emit_state_event(tmp_path, "telegram", "degraded", "degraded")
    assert emits == []

    br.emit_state_event(tmp_path, "telegram", "healthy", "degraded",
                        reason="timeout")
    state_events = [d for k, d in emits if k == "gateway.state"]
    assert len(state_events) == 1
    assert state_events[0]["platform"] == "telegram"
    assert state_events[0]["previous"] == "healthy"
    assert state_events[0]["status"] == "degraded"
    assert state_events[0]["reason"] == "timeout"


def test_record_success_does_not_churn_disk_when_already_healthy(
    tmp_path: Path,
) -> None:
    """Telegram polls every 30s, IMAP/Gmail every minute. Persisting on each
    successful tick would write the file 1000+ times per day per platform
    for no behavioral change — early-return when the state is already
    clean. The first success after creation writes once; subsequent
    successes skip the file."""
    store = br.BreakerStore(tmp_path)
    store.record_success("telegram", now=1000.0)
    first_mtime = store.path.stat().st_mtime_ns

    for i in range(1, 6):
        store.record_success("telegram", now=1000.0 + i)

    assert store.path.stat().st_mtime_ns == first_mtime
    in_mem = store.state_of("telegram")
    assert in_mem.last_success_at == 1005.0


def test_record_success_persists_when_recovering_from_failure(
    tmp_path: Path,
) -> None:
    """The early-return must NOT skip the recovery write — going from
    degraded/disabled back to healthy is exactly the transition we care
    about, and the post-recovery state has to survive a restart."""
    store = br.BreakerStore(tmp_path)
    store.record_failure("telegram", "timeout", now=1000.0)
    store.record_success("telegram", now=1001.0)

    persisted = br.BreakerStore(tmp_path).state_of("telegram")
    assert persisted.status == "healthy"
    assert persisted.consecutive_failures == 0
    assert persisted.last_error == ""


def test_persistence_uses_unique_tmp_per_pid(tmp_path: Path) -> None:
    """Atomic write must not collide on a fixed ``.tmp`` suffix — two daemons or two threads can both be persisting. Same per-pid + per-thread pattern as skills_usage."""
    store = br.BreakerStore(tmp_path)
    store.record_failure("imap", "err", now=1000.0)
    raw = json.loads(store.path.read_text())
    assert raw["v"] == br.SCHEMA_VERSION
    assert "imap" in raw["platforms"]
    leftover = list(store.path.parent.glob(".breaker-state.json.tmp*"))
    assert leftover == [], f"tmp file not cleaned up: {leftover}"
