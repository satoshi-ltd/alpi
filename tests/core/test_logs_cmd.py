"""Tests for `alpi logs` (unified tail)."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from alpi import cli, logs


def _seed(home: Path, sub: str, lines: list[str]) -> Path:
    d = home / "logs"
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"{sub}.log"
    f.write_text("\n".join(lines) + "\n")
    return f


def test_discover_globs_all_subsystems(tmp_path: Path) -> None:
    _seed(tmp_path, "gateway", ["x"])
    _seed(tmp_path, "schedule", ["y"])
    (tmp_path / "irrelevant").mkdir()  # not a .log file → not discovered
    files = logs.discover(tmp_path, source=None)
    names = sorted(f.stem for f in files)
    assert names == ["gateway", "schedule"]


def test_discover_source_filter(tmp_path: Path) -> None:
    _seed(tmp_path, "gateway", ["x"])
    _seed(tmp_path, "schedule", ["y"])
    files = logs.discover(tmp_path, source="schedule")
    assert len(files) == 1
    assert files[0].stem == "schedule"


def test_tail_merges_by_timestamp(tmp_path: Path) -> None:
    _seed(tmp_path, "gateway", [
        "2026-04-23 10:00:00 INFO alpi.gateway first",
        "2026-04-23 10:00:03 INFO alpi.gateway third",
    ])
    _seed(tmp_path, "schedule", [
        "2026-04-23 10:00:01 INFO alpi.schedule second",
    ])
    out = logs.tail(tmp_path, source=None, n=10)
    order = [l.text.split()[-1] for l in out]
    assert order == ["first", "second", "third"]


def test_tail_respects_n(tmp_path: Path) -> None:
    _seed(tmp_path, "gateway", [f"2026-04-23 10:00:0{i} INFO x {i}" for i in range(5)])
    out = logs.tail(tmp_path, source=None, n=2)
    assert len(out) == 2
    assert out[-1].text.endswith("4")


def test_tail_carries_timestamp_across_continuation_lines(tmp_path: Path) -> None:
    """Tracebacks should sort next to their parent line."""
    _seed(tmp_path, "gateway", [
        "2026-04-23 10:00:00 ERROR alpi.gateway boom",
        "    Traceback (most recent call last):",
        "      File …",
    ])
    out = logs.tail(tmp_path, source=None, n=10)
    assert all(l.ts == "2026-04-23 10:00:00" for l in out)


def test_logs_command_prints_tail(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    _seed(tmp_path, "gateway", ["2026-04-23 10:00:00 INFO alpi.gateway hello"])
    result = CliRunner().invoke(cli.main, ["logs", "-n", "5"])
    assert result.exit_code == 0
    assert "hello" in result.output
    assert "gateway" in result.output


def test_logs_command_empty_home(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    result = CliRunner().invoke(cli.main, ["logs"])
    assert result.exit_code == 0
    assert "no logs yet" in result.output
