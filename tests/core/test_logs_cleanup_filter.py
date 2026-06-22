from pathlib import Path

import pytest

from alpi.cli import _cleanup_categories


@pytest.fixture
def fake_profile_home(tmp_path: Path) -> Path:
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "agent.log").write_text("agent line\n")
    (logs / "agent.log.1").write_text("rotated agent gen\n")
    (logs / "approval.log").write_text("approval line\n")
    (logs / "ledger.json").write_text('{"daily_usd": 0.0}')
    (logs / "runs.jsonl").write_text('{"id": "x"}\n')
    (logs / "compaction.jsonl").write_text('{"trigger": "auto"}\n')
    (logs / "curator").mkdir()
    return tmp_path


def _logs_category(home: Path) -> dict:
    cats = _cleanup_categories(home)
    matches = [c for c in cats if c["key"] == "logs"]
    assert matches, "expected a 'logs' cleanup category"
    return matches[0]


def test_cleanup_logs_category_includes_rotated_logs(fake_profile_home: Path):
    category = _logs_category(fake_profile_home)
    names = {p.name for p in category["files"]}
    assert {"agent.log", "agent.log.1", "approval.log"} <= names, (
        f"Subsystem logs cleanup must include rotated *.log files; got {sorted(names)}"
    )


def test_cleanup_logs_category_excludes_state_files(fake_profile_home: Path):
    category = _logs_category(fake_profile_home)
    names = {p.name for p in category["files"]}
    forbidden = {"ledger.json", "runs.jsonl", "compaction.jsonl"}
    leaked = names & forbidden
    assert not leaked, (
        f"Subsystem logs cleanup must NOT include budget / telemetry state files; "
        f"the UI label promises only *.log. Leaked: {sorted(leaked)}"
    )


def test_cleanup_logs_category_excludes_curator_subdir(fake_profile_home: Path):
    category = _logs_category(fake_profile_home)
    names = {p.name for p in category["files"]}
    assert "curator" not in names, (
        "curator/ is a directory (and has its own cleanup category); "
        "must not appear as a file in the logs bucket"
    )
