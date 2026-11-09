from __future__ import annotations

from pathlib import Path

import pytest

from alpi import runs
from alpi.core.run_context import RunContext


@pytest.fixture(autouse=True)
def _fresh_cache():
    runs.invalidate_journal_cache()
    yield
    runs.invalidate_journal_cache()


def _closed(home: Path, n: int) -> None:
    for i in range(n):
        ctx = RunContext.create(home=home, workspace=home, profile="p", source="user", session_id=f"s{i}", connection_id="host")
        runs.start(ctx, model="m", input_text="x")
        runs.finish(ctx, "completed")


def test_second_sweep_over_closed_journals_opens_none(tmp_path: Path, monkeypatch) -> None:
    _closed(tmp_path, 200)
    opened = {"n": 0}
    real = runs._first_record

    def counting(path):
        opened["n"] += 1
        return real(path)

    monkeypatch.setattr(runs, "_first_record", counting)
    assert runs.running_journals(tmp_path, now=0.0) == []
    first_pass = opened["n"]
    assert first_pass >= 200
    assert runs.running_journals(tmp_path, now=0.0) == []
    assert opened["n"] == first_pass


def test_a_running_journal_is_reread_and_a_changed_file_is_too(tmp_path: Path, monkeypatch) -> None:
    _closed(tmp_path, 3)
    live = RunContext.create(home=tmp_path, workspace=tmp_path, profile="p", source="user", session_id="live", connection_id="host")
    runs.start(live, model="m", input_text="x")
    rows = runs.running_journals(tmp_path, now=0.0)
    assert [r[0]["id"] for r in rows] == [live.run_id]
    opened = {"n": 0}
    real = runs._first_record

    def counting(path):
        opened["n"] += 1
        return real(path)

    monkeypatch.setattr(runs, "_first_record", counting)
    runs.running_journals(tmp_path, now=0.0)
    assert opened["n"] <= 2
    runs.finish(live, "completed")
    assert runs.running_journals(tmp_path, now=0.0) == []
    opened["n"] = 0
    runs.running_journals(tmp_path, now=0.0)
    assert opened["n"] == 0


def test_cache_entries_of_deleted_journals_are_dropped(tmp_path: Path) -> None:
    _closed(tmp_path, 2)
    runs.running_journals(tmp_path, now=0.0)
    assert len([k for k in runs._journal_status_cache if k.startswith(str(tmp_path))]) == 2
    for p in (tmp_path / "runs").glob("*.jsonl"):
        p.unlink()
    runs.running_journals(tmp_path, now=0.0)
    assert not [k for k in runs._journal_status_cache if k.startswith(str(tmp_path))]
