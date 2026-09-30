from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import prune_actions  # noqa: E402

NOW = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)


def _stamp(days_ago: float) -> str:
    return (NOW - timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _run(run_id: int, workflow: int, days_ago: float, status: str = "completed") -> dict:
    return {"id": run_id, "workflow_id": workflow, "status": status, "created_at": _stamp(days_ago)}


def test_runs_keep_the_newest_per_workflow_and_anything_younger_than_the_age_floor() -> None:
    runs = [_run(i, 1, days_ago=i) for i in range(1, 16)] + [_run(100 + i, 2, days_ago=i) for i in range(1, 4)]

    doomed = prune_actions.select_runs(runs, keep=10, min_age_days=7, now=NOW)

    assert sorted(doomed) == [11, 12, 13, 14, 15]


def test_selection_does_not_depend_on_the_order_of_the_listing() -> None:
    runs = [_run(i, 1, days_ago=i) for i in range(1, 16)]
    shuffled = runs[7:] + runs[:7][::-1]

    assert sorted(prune_actions.select_runs(shuffled, keep=10, min_age_days=7, now=NOW)) == [11, 12, 13, 14, 15]


def test_a_run_exactly_at_the_age_floor_is_kept() -> None:
    runs = [_run(1, 1, days_ago=1), _run(2, 1, days_ago=7)]

    assert prune_actions.select_runs(runs, keep=1, min_age_days=7, now=NOW) == []


def test_a_rerun_counts_from_when_it_started_again() -> None:
    old = _run(1, 1, days_ago=30)
    old["run_started_at"] = _stamp(1)

    assert prune_actions.select_runs([_run(2, 1, days_ago=0.5), old], keep=1, min_age_days=7, now=NOW) == []


def test_a_run_inside_the_newest_ten_survives_even_when_old() -> None:
    runs = [_run(i, 1, days_ago=30 + i) for i in range(1, 6)]

    assert prune_actions.select_runs(runs, keep=10, min_age_days=7, now=NOW) == []


def test_a_run_beyond_the_newest_ten_survives_while_younger_than_the_age_floor() -> None:
    runs = [_run(i, 1, days_ago=i / 10) for i in range(1, 16)]

    assert prune_actions.select_runs(runs, keep=10, min_age_days=7, now=NOW) == []


def test_runs_still_going_are_never_selected() -> None:
    runs = [_run(1, 1, days_ago=1)] + [_run(i, 1, days_ago=20 + i, status="in_progress") for i in range(2, 6)]

    assert prune_actions.select_runs(runs, keep=1, min_age_days=7, now=NOW) == []


def test_artifacts_older_than_the_age_floor_are_selected() -> None:
    artifacts = [
        {"id": 1, "created_at": _stamp(1)},
        {"id": 2, "created_at": _stamp(6.9)},
        {"id": 3, "created_at": _stamp(7.1)},
        {"id": 4, "created_at": _stamp(90)},
    ]

    assert prune_actions.select_artifacts(artifacts, min_age_days=7, now=NOW) == [3, 4]


class FakeGh:
    def __init__(self, runs: list[dict], artifacts: list[dict], missing: set[str] = frozenset(), broken: set[str] = frozenset()) -> None:
        self.runs, self.artifacts = runs, artifacts
        self.missing, self.broken = missing, broken
        self.deleted: list[str] = []

    def __call__(self, args: list[str]) -> str:
        if args[0] == "-X":
            path = args[2]
            if path in self.missing:
                raise prune_actions.GhError("gh: Not Found (HTTP 404)")
            if path in self.broken:
                raise prune_actions.GhError("gh: Forbidden (HTTP 403)")
            self.deleted.append(path)
            return ""
        rows = self.runs if "/runs?" in args[1] else self.artifacts
        return "\n".join(json.dumps(row) for row in rows)


def _fleet() -> FakeGh:
    runs = [_run(i, 1, days_ago=i) for i in range(1, 15)]
    artifacts = [{"id": 7, "created_at": _stamp(30)}, {"id": 8, "created_at": _stamp(2)}]
    return FakeGh(runs, artifacts)


def test_the_default_is_a_dry_run_that_deletes_nothing(capsys: pytest.CaptureFixture[str]) -> None:
    gh = _fleet()

    code = prune_actions.main(["--repo", "o/r"], gh=gh, now=NOW)

    assert code == 0
    assert gh.deleted == []
    assert capsys.readouterr().out.splitlines() == [
        "runs: would delete 4 of 14",
        "artifacts: would delete 1 of 2",
    ]


def test_apply_deletes_the_selected_runs_and_artifacts(capsys: pytest.CaptureFixture[str]) -> None:
    gh = _fleet()

    code = prune_actions.main(["--repo", "o/r", "--apply"], gh=gh, now=NOW)

    assert code == 0
    assert sorted(gh.deleted) == sorted(
        [f"repos/o/r/actions/runs/{i}" for i in (11, 12, 13, 14)] + ["repos/o/r/actions/artifacts/7"]
    )
    assert "runs: deleted 4 of 14" in capsys.readouterr().out


def test_an_already_deleted_item_counts_as_done() -> None:
    gh = _fleet()
    gh.missing = {"repos/o/r/actions/runs/11"}

    assert prune_actions.main(["--repo", "o/r", "--apply"], gh=gh, now=NOW) == 0


def test_a_refused_deletion_fails_the_run(capsys: pytest.CaptureFixture[str]) -> None:
    gh = _fleet()
    gh.broken = {"repos/o/r/actions/runs/12"}

    code = prune_actions.main(["--repo", "o/r", "--apply"], gh=gh, now=NOW)

    captured = capsys.readouterr()
    assert code == 1
    assert "runs: deleted 3 of 14" in captured.out
    assert "cannot delete repos/o/r/actions/runs/12" in captured.err


def test_negative_limits_are_refused() -> None:
    with pytest.raises(SystemExit):
        prune_actions.main(["--repo", "o/r", "--keep", "-1"], gh=_fleet(), now=NOW)
