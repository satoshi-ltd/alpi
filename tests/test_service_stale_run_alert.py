import json
from pathlib import Path

from alpi import service


def _capture_events(monkeypatch) -> list[tuple[str, dict]]:
    seen: list[tuple[str, dict]] = []
    from alpi.host import events as host_events
    monkeypatch.setattr(
        host_events, "emit",
        lambda kind, payload=None: seen.append((kind, payload or {})),
    )
    return seen


def _home(tmp_path: Path, jobs: list[dict] | None = None) -> Path:
    home = tmp_path / "sentinel"
    (home / "schedule").mkdir(parents=True)
    (home / "config.yaml").write_text("model: test\n")
    (home / "schedule" / "jobs.json").write_text(json.dumps(jobs or []))
    return home


def test_a_dead_scheduled_run_files_an_error_and_raises_schedule_failed(
    tmp_path: Path, monkeypatch,
) -> None:
    home = _home(tmp_path, [{"id": "35cbf2b8", "title": "Sentinel PR review"}])
    seen = _capture_events(monkeypatch)

    service._alert_stale_runs(home, "sentinel", [{
        "run_id": "dba55843", "job_id": "35cbf2b8",
        "source": "schedule", "silent_for_s": 108540.0,
    }])

    kinds = [kind for kind, _ in seen]
    assert "schedule.failed" in kinds

    payload = next(p for kind, p in seen if kind == "schedule.failed")
    assert payload["profile"] == "sentinel"
    assert payload["job_id"] == "35cbf2b8"
    assert payload["title"] == "Sentinel PR review"
    assert payload["run_id"] == "dba55843"
    assert "108540" in payload["body"]
    assert payload["output_id"]
    assert payload["deep_link"] == f"/outputs/sentinel/{payload['output_id']}"

    from alpi import outputs as outputs_mod
    filed = outputs_mod.read(home, payload["output_id"])
    assert filed is not None
    assert filed["type"] == "error"
    assert filed["title"] == "Sentinel PR review did not finish"
    assert "dba55843" in filed["body"]


def test_a_dead_manual_run_still_alerts_without_a_job(
    tmp_path: Path, monkeypatch,
) -> None:
    home = _home(tmp_path)
    seen = _capture_events(monkeypatch)

    service._alert_stale_runs(home, "sentinel", [{
        "run_id": "adb7799e", "job_id": "", "source": "user", "silent_for_s": 47.0,
    }])

    payload = next(p for kind, p in seen if kind == "schedule.failed")
    assert payload["job_id"] == ""
    assert payload["title"] == "manual run"
    assert payload["kind"] == "run"


def test_every_closed_run_gets_its_own_alert(tmp_path: Path, monkeypatch) -> None:
    home = _home(tmp_path, [{"id": "a", "title": "first"}, {"id": "b", "title": "second"}])
    seen = _capture_events(monkeypatch)

    service._alert_stale_runs(home, "sentinel", [
        {"run_id": "r1", "job_id": "a", "source": "schedule", "silent_for_s": 10.0},
        {"run_id": "r2", "job_id": "b", "source": "schedule", "silent_for_s": 20.0},
    ])

    failed = [p for kind, p in seen if kind == "schedule.failed"]
    assert [p["run_id"] for p in failed] == ["r1", "r2"]
    assert [p["title"] for p in failed] == ["first", "second"]


def test_unreadable_jobs_file_does_not_stop_the_alert(
    tmp_path: Path, monkeypatch,
) -> None:
    home = _home(tmp_path)
    (home / "schedule" / "jobs.json").write_text("{ this is not json")
    seen = _capture_events(monkeypatch)

    service._alert_stale_runs(home, "sentinel", [{
        "run_id": "r9", "job_id": "zz", "source": "schedule", "silent_for_s": 5.0,
    }])

    payload = next(p for kind, p in seen if kind == "schedule.failed")
    assert payload["title"] == "job zz"
