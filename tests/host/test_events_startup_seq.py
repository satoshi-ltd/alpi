"""A stale-run alert is emitted before the host task exists; it must still land above a client's cursor."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from alpi import service
from alpi.host import events as host_events
from alpi.host import server as host_server


def _history_with_prior_events(home: Path, last_seq: int) -> None:
    path = home / "host" / "events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for seq in range(1, last_seq + 1):
            fh.write(json.dumps({
                "event": "schedule.done", "data": {"job_id": "old"},
                "at": 1.0 * seq, "seq": seq,
            }) + "\n")


def _fresh_bus(home: Path) -> None:
    host_events._history.clear()
    host_events._writes_since_compact = 0
    host_events._history_path = None
    host_events._seq_counter = 0
    host_events._history_loaded = False


def _profile(home: Path) -> Path:
    (home / "schedule").mkdir(parents=True, exist_ok=True)
    (home / "schedule" / "jobs.json").write_text(json.dumps(
        [{"id": "35cbf2b8", "title": "Sentinel PR review"}],
    ))
    return home


def test_a_startup_alert_lands_above_a_reconnecting_client_cursor(
    root: Path, monkeypatch,
) -> None:
    """The daemon alerts on dead runs before register() restores the persisted seq.

    Without the counter, the alert takes seq=1 while the client holds cursor 100,
    and host.events.history(after_seq=100) hides the very notification this exists for.
    """
    _history_with_prior_events(root, last_seq=100)
    _fresh_bus(root)
    monkeypatch.setenv("ALPI_HOME", str(root))
    _profile(root)

    service._alert_stale_runs(root, "default", [{
        "run_id": "dba55843", "job_id": "35cbf2b8",
        "source": "schedule", "silent_for_s": 108540.0,
    }])

    # The host task starts only after profiles are up; this is that moment.
    srv = host_server.Server(home=root)
    host_events.register(srv)

    out = asyncio.run(host_events._history_handler({"after_seq": 100}, srv))
    kinds = [e["event"] for e in out["events"]]
    assert "schedule.failed" in kinds, (
        f"the client saw {kinds!r} after cursor 100 — the startup alert was filed below it"
    )
    failed = next(e for e in out["events"] if e["event"] == "schedule.failed")
    assert failed["seq"] > 100
    assert failed["data"]["run_id"] == "dba55843"


def test_the_alert_survives_a_restart_and_replays_once(root: Path, monkeypatch) -> None:
    _history_with_prior_events(root, last_seq=7)
    _fresh_bus(root)
    monkeypatch.setenv("ALPI_HOME", str(root))
    _profile(root)

    service._alert_stale_runs(root, "default", [{
        "run_id": "r1", "job_id": "35cbf2b8", "source": "schedule", "silent_for_s": 60.0,
    }])
    srv = host_server.Server(home=root)
    host_events.register(srv)

    # A second daemon start re-reads the same file; the alert must not be duplicated or renumbered.
    _fresh_bus(root)
    srv2 = host_server.Server(home=root)
    host_events.register(srv2)

    out = asyncio.run(host_events._history_handler({"after_seq": 7}, srv2))
    failed = [e for e in out["events"] if e["event"] == "schedule.failed"]
    assert len(failed) == 1
    assert failed[0]["seq"] > 7


@pytest.fixture
def root(tmp_path: Path) -> Path:
    home = tmp_path / "alpi"
    home.mkdir()
    return home
