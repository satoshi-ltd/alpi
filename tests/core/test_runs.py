from __future__ import annotations

from pathlib import Path

import pytest

from alpi import runs
from alpi.core.run_context import RunContext
from alpi.engine import AgentEvent


def _context(home: Path, *, run_id: str | None = None) -> RunContext:
    return RunContext.create(
        home=home,
        workspace=home / "workspace",
        profile="default",
        source="user",
        session_id="s1",
        connection_id="c1",
        device_id="d1",
        run_id=run_id,
    )


def test_run_journal_roundtrip_and_summary(tmp_path: Path) -> None:
    context = _context(tmp_path)
    runs.start(context, model="model-1")
    runs.record_agent_event(context, AgentEvent(kind="assistant_delta", text="hello"))
    runs.finish(context, "completed")

    journal = runs.read(tmp_path, context.run_id)
    assert [row["kind"] for row in journal["events"]] == [
        "run.started", "agent.assistant_delta", "run.finished",
    ]
    item = runs.summary(tmp_path, context.run_id)
    assert item["status"] == "completed"
    assert item["connection_id"] == "c1"
    assert item["event_count"] == 3
    assert runs.list_runs(tmp_path)[0]["id"] == context.run_id
    assert runs.run_path(tmp_path, context.run_id).stat().st_mode & 0o777 == 0o600


def test_summary_reads_only_the_edges_of_a_journal(tmp_path: Path, monkeypatch) -> None:
    context = _context(tmp_path)
    runs.start(context)
    for index in range(100):
        runs.append(tmp_path, context.run_id, "test", {"index": index})
    runs.finish(context, "completed")
    original_loads = runs.json.loads
    calls = 0

    def counted_loads(value):
        nonlocal calls
        calls += 1
        return original_loads(value)

    monkeypatch.setattr(runs.json, "loads", counted_loads)
    item = runs.summary(tmp_path, context.run_id)

    assert item["event_count"] == 102
    assert item["status"] == "completed"
    assert calls == 2


def test_finish_releases_per_run_process_state(tmp_path: Path) -> None:
    context = _context(tmp_path)
    path_key = str(runs.run_path(tmp_path, context.run_id))
    runs.start(context)
    assert path_key in runs._locks and path_key in runs._seq

    runs.finish(context, "completed")

    assert path_key not in runs._locks and path_key not in runs._seq


def test_supervisor_can_finish_a_child_run_once(tmp_path: Path) -> None:
    context = _context(tmp_path)
    runs.start(context)

    assert runs.finish_if_running(tmp_path, context.run_id, "interrupted") is True
    assert runs.finish_if_running(tmp_path, context.run_id, "failed") is False
    assert runs.summary(tmp_path, context.run_id)["status"] == "interrupted"


def test_usage_summary_sums_every_usage_event(tmp_path: Path) -> None:
    context = _context(tmp_path)
    runs.start(context)
    runs.append(tmp_path, context.run_id, "agent.usage", {
        "tokens_in": 100, "tokens_out": 20, "cost": 0.12,
    })
    runs.append(tmp_path, context.run_id, "agent.usage", {
        "tokens_in": 50, "tokens_out": 5, "cost": 0.03,
    })

    assert runs.usage_summary(tmp_path, context.run_id) == {
        "usd": pytest.approx(0.15),
        "tokens": 175,
        "tokens_in": 150,
        "tokens_out": 25,
    }


def test_reconcile_stale_closes_legacy_run_but_not_live_pid(
    tmp_path: Path, monkeypatch,
) -> None:
    monkeypatch.setattr(runs.time, "time", lambda: 100.0)
    legacy_id = "legacy"
    runs.append(tmp_path, legacy_id, "run.started", {
        "run_id": legacy_id, "profile": "default",
    })
    live = _context(tmp_path)
    runs.start(live)
    monkeypatch.setattr(runs.time, "time", lambda: 5000.0)

    assert runs.reconcile_stale(tmp_path, older_than_s=3600) == 1
    assert runs.summary(tmp_path, legacy_id)["status"] == "interrupted"
    assert runs.summary(tmp_path, live.run_id)["status"] == "running"


def test_reconcile_stale_scans_beyond_the_public_list_limit(
    tmp_path: Path, monkeypatch,
) -> None:
    monkeypatch.setattr(runs.time, "time", lambda: 100.0)
    runs.append(tmp_path, "buried", "run.started", {
        "run_id": "buried", "profile": "default",
    })
    for index in range(runs.MAX_LIST_LIMIT + 1):
        context = _context(tmp_path, run_id=f"newer-{index}")
        runs.start(context)
        runs.finish(context, "completed")
    monkeypatch.setattr(runs.time, "time", lambda: 5000.0)

    assert runs.reconcile_stale(tmp_path, older_than_s=3600) == 1
    assert runs.summary(tmp_path, "buried")["status"] == "interrupted"


def test_terminal_arguments_are_omitted_from_agent_events_and_workflows(tmp_path: Path) -> None:
    context = _context(tmp_path)
    secret = "not-shaped-like-a-token"
    runs.start(context)
    runs.record_agent_event(context, AgentEvent(
        kind="tool_start", name="terminal", args={"action": "run", "command": secret},
    ))
    runs.record_agent_event(context, AgentEvent(
        kind="tool_start", name="workflow",
        args={"steps": [{
            "id": "shell", "tool": "terminal",
            "arguments": {"action": "run", "command": secret},
        }]},
    ))

    rows = runs.read(tmp_path, context.run_id)["events"]
    assert secret not in str(rows)
    assert rows[1]["data"]["args"] == {"action": "run"}
    nested = rows[2]["data"]["args"]["steps"][0]["arguments"]
    assert nested == {"action": "run"}


def test_run_journal_redacts_and_bounds_text(tmp_path: Path) -> None:
    context = _context(tmp_path)
    runs.start(context)
    secret = "sk-" + "x" * 32
    runs.append(tmp_path, context.run_id, "test", {"text": secret + "z" * 50_000})

    row = runs.read(tmp_path, context.run_id)["events"][-1]
    assert secret not in str(row)
    assert "[REDACTED]" in str(row)
    assert len(str(row["data"])) < 20_000


def test_read_missing_run(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        runs.read(tmp_path, "missing")


def test_run_id_cannot_escape_journal_directory(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="invalid run id"):
        runs.read(tmp_path, "../../outside")


def test_run_journal_does_not_follow_directory_or_file_symlinks(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    (home / "runs").symlink_to(outside)
    context = _context(home)

    with pytest.raises(OSError, match="must not be a symlink"):
        runs.start(context)
    assert list(outside.iterdir()) == []
    assert runs.list_runs(home) == []
    with pytest.raises(FileNotFoundError):
        runs.read(home, "outside")

    (home / "runs").unlink()
    (home / "runs").mkdir()
    target = outside / "target.jsonl"
    target.write_text("leave me")
    runs.run_path(home, context.run_id).symlink_to(target)
    with pytest.raises(OSError):
        runs.start(context)
    with pytest.raises(FileNotFoundError):
        runs.read(home, context.run_id)
    assert target.read_text() == "leave me"


def test_list_runs_tolerates_journal_deleted_during_scan(tmp_path: Path, monkeypatch) -> None:
    context = _context(tmp_path)
    runs.start(context)
    path = runs.run_path(tmp_path, context.run_id)
    original_stat = Path.stat

    def racing_stat(self, *args, **kwargs):
        if self == path:
            raise FileNotFoundError(self)
        return original_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", racing_stat)

    assert runs.list_runs(tmp_path) == []
