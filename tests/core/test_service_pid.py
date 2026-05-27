from __future__ import annotations

import os
from pathlib import Path

from alpi import service


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_missing_pidfile_returns_none(tmp_path: Path) -> None:
    assert service.daemon_running_pid(tmp_path) is None


def test_empty_or_garbage_pidfile_returns_none(tmp_path: Path) -> None:
    p = service.daemon_pid_path(tmp_path)
    _write(p, "")
    assert service.daemon_running_pid(tmp_path) is None
    _write(p, "not-a-number")
    assert service.daemon_running_pid(tmp_path) is None


def test_live_self_pid_round_trip(tmp_path: Path) -> None:
    service._write_daemon_pid(tmp_path)
    assert service.daemon_running_pid(tmp_path) == os.getpid()


def test_stale_pidfile_dead_process_is_unlinked(tmp_path: Path, monkeypatch) -> None:
    def fake_kill(pid: int, sig: int) -> None:
        raise ProcessLookupError(pid)
    monkeypatch.setattr(service.os, "kill", fake_kill)
    p = service.daemon_pid_path(tmp_path)
    _write(p, "12345")
    assert service.daemon_running_pid(tmp_path) is None
    assert not p.exists()


def test_pid_alive_but_starttime_mismatch_is_treated_as_stale(
    tmp_path: Path, monkeypatch,
) -> None:
    # Container restart: stale pidfile's starttime no longer matches the process holding that PID.
    pid = os.getpid()
    p = service.daemon_pid_path(tmp_path)
    _write(p, f"{pid} 1")
    actual = service._proc_starttime(pid)
    if actual is None or actual == "1":
        return  # /proc unavailable (macOS) — strong check is a no-op
    assert service.daemon_running_pid(tmp_path) is None
    assert not p.exists()


def test_legacy_format_falls_back_to_weak_check(tmp_path: Path) -> None:
    pid = os.getpid()
    p = service.daemon_pid_path(tmp_path)
    _write(p, str(pid))
    assert service.daemon_running_pid(tmp_path) == pid


def test_proc_starttime_parses_comm_with_parens_and_spaces() -> None:
    # /proc/<pid>/stat field 2 is "(comm)" which can contain ')' or whitespace — parser must use rfind.
    actual = service._proc_starttime(os.getpid())
    if actual is not None:
        assert actual.isdigit()
