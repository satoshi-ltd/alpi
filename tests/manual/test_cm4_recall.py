# Manual smoke, real fastembed + sqlite-vec, no LLM: uv run pytest tests/manual/test_cm4_recall.py -q -s
from __future__ import annotations

import json

from alpi.core.store import store_path
from alpi.tools import recall as rc


def _session(home, sid, turns, started_at=1700000000.0):
    sdir = home / "sessions"
    sdir.mkdir(parents=True, exist_ok=True)
    (sdir / f"{sid}.json").write_text(json.dumps({"id": sid, "started_at": started_at, "turns": turns}))


def test_recall_real_embedder_end_to_end(tmp_home):
    _session(tmp_home, "pricing", [
        {"user": "what did we land on for the renewal pricing",
         "assistant": "we set the renewal threshold at 42 seats with annual billing"},
    ])
    _session(tmp_home, "infra", [
        {"user": "where do backups go",
         "assistant": "Postgres on RDS, daily snapshots to S3"},
    ])

    summary = rc.index_sessions(tmp_home)
    assert summary["indexed_sessions"] == 2, summary
    assert store_path(tmp_home).is_file(), "store not created"

    results = rc.recall(tmp_home, "when did we decide the seat threshold for renewals", k=3)
    assert results, "recall returned nothing"
    assert results[0]["session_id"] == "pricing", results
    assert "42 seats" in results[0]["snippet"]
    print(f"OK — recalled session '{results[0]['session_id']}' by meaning: “{results[0]['snippet']}”")
