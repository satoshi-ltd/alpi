"""host.events.history backfill RPC + bounded on-disk JSONL persistence."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import pytest

from alpi.host import events as host_events
from alpi.host import server as host_server


def _reset_state(home: Path) -> host_server.Server:
    """Wire a fresh Server(home=...) through register() so _history_path is taken from it, not from alpi.home._ROOT."""
    host_events._history.clear()
    host_events._writes_since_compact = 0
    host_events._history_path = None
    srv = host_server.Server(home=home)
    host_events.register(srv)
    return srv


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return tmp_path


def test_emit_records_event_into_history_and_jsonl(root: Path) -> None:
    srv = _reset_state(root)
    host_events.emit("wg.done", {"profile": "doc", "wg_id": "architecture"})

    out = asyncio.run(host_events._history_handler({}, srv))
    assert len(out["events"]) == 1
    ev = out["events"][0]
    assert ev["event"] == "wg.done"
    assert ev["data"] == {"profile": "doc", "wg_id": "architecture"}
    assert "at" in ev and ev["at"] > 0

    jsonl = (root / "host" / "events.jsonl").read_text(encoding="utf-8")
    parsed = [json.loads(line) for line in jsonl.splitlines() if line.strip()]
    assert parsed == [ev]


def test_history_reloads_from_disk_on_register(root: Path) -> None:
    path = root / "host" / "events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"event": "schedule.done", "data": {"job_id": "abc"}, "at": 1.0}) + "\n"
        + json.dumps({"event": "session_changed", "data": {"profile": "doc"}, "at": 2.0}) + "\n",
        encoding="utf-8",
    )
    srv = _reset_state(root)
    out = asyncio.run(host_events._history_handler({}, srv))
    assert [e["event"] for e in out["events"]] == ["schedule.done", "session_changed"]


def test_history_filters_by_since_and_kinds(root: Path) -> None:
    srv = _reset_state(root)
    host_events.emit("wg.post", {"wg_id": "architecture"})
    cutoff = time.time()
    time.sleep(0.01)
    host_events.emit("schedule.done", {"job_id": "x"})
    host_events.emit("wg.done", {"wg_id": "customers"})

    out_since = asyncio.run(host_events._history_handler({"since": cutoff}, srv))
    assert [e["event"] for e in out_since["events"]] == ["schedule.done", "wg.done"]

    out_kinds = asyncio.run(
        host_events._history_handler({"kinds": ["wg.done", "wg.post"]}, srv),
    )
    assert [e["event"] for e in out_kinds["events"]] == ["wg.post", "wg.done"]


def test_history_ring_caps_at_max(
    root: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(host_events, "HISTORY_MAX", 4)
    monkeypatch.setattr(host_events, "_history", type(host_events._history)(maxlen=4))
    srv = _reset_state(root)
    for i in range(10):
        host_events.emit("session_changed", {"i": i})
    out = asyncio.run(host_events._history_handler({}, srv))
    assert len(out["events"]) == 4
    assert [e["data"]["i"] for e in out["events"]] == [6, 7, 8, 9]


def test_jsonl_compacts_after_compact_every_writes(
    root: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The append-only path is only an interim — every COMPACT_EVERY writes the file is rewritten with the in-memory deque so it can't grow unboundedly even under hot emit() (session_changed et al)."""
    monkeypatch.setattr(host_events, "HISTORY_MAX", 10)
    monkeypatch.setattr(host_events, "COMPACT_EVERY", 5)
    monkeypatch.setattr(host_events, "_history", type(host_events._history)(maxlen=10))
    srv = _reset_state(root)
    path = root / "host" / "events.jsonl"

    # Emit 100 events: that's 20× COMPACT_EVERY. Without compaction the file would hold 100 lines.
    for i in range(100):
        host_events.emit("schedule.done", {"i": i})

    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    # After the last compact (at i=99, which is the 100th write → write count 100 % 5 == 0), file holds exactly the ring contents = 10 lines.
    assert len(lines) == 10
    parsed = [json.loads(line) for line in lines]
    assert [p["data"]["i"] for p in parsed] == list(range(90, 100))

    # Memory ring agrees.
    out = asyncio.run(host_events._history_handler({}, srv))
    assert [e["data"]["i"] for e in out["events"]] == list(range(90, 100))
