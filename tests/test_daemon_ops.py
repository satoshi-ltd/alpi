"""Gateway/Schedule ops UX — smart stop warn, restart verb, doctor stale check."""

from __future__ import annotations

import os
import signal
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from alpi import cli, doctor


# Shared fixture: isolate ALPI_PROFILE across tests (cli.main sets it on
# os.environ directly; leaks hurt other tests).
@pytest.fixture(autouse=True)
def _isolate_profile_env(monkeypatch):
    before = os.environ.get("ALPI_PROFILE")
    monkeypatch.delenv("ALPI_PROFILE", raising=False)
    yield
    if before is None:
        os.environ.pop("ALPI_PROFILE", None)
    else:
        os.environ["ALPI_PROFILE"] = before


def _write_pid(tmp_path: Path, pid: int) -> Path:
    pid_file = tmp_path / "gateway" / "gateway.pid"
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(str(pid))
    return pid_file


def test_stop_warns_when_service_installed(tmp_path: Path, monkeypatch) -> None:
    """Serviced daemons bounce back — warn the user so they don't think
    the stop was a no-op."""
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    monkeypatch.delenv("ALPI_SKIP_AUTO_INSTALL", raising=False)

    from alpi import service
    monkeypatch.setattr(service, "installed",
                        lambda name, profile="default": "launchd")
    monkeypatch.setattr(service, "install",
                        lambda *a, **kw: "launchd")

    pid_file = _write_pid(tmp_path, os.getpid())  # current process is alive

    # Capture only actual SIGTERMs — ``_read_live_pid`` also calls
    # ``os.kill(pid, 0)`` as a liveness probe; ignore that.
    sent: list[int] = []

    def _fake_kill(p, s):
        if s == signal.SIGTERM:
            sent.append(p)

    monkeypatch.setattr(os, "kill", _fake_kill)

    result = CliRunner().invoke(cli.main, ["gateway", "stop"])
    assert result.exit_code == 0
    assert "managed by launchd" in result.output
    assert "uninstall" in result.output.lower()
    assert f"SIGTERM to pid {os.getpid()}" in result.output
    assert sent == [os.getpid()]


def test_stop_without_service_just_stops(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    monkeypatch.delenv("ALPI_SKIP_AUTO_INSTALL", raising=False)

    from alpi import service
    monkeypatch.setattr(service, "installed",
                        lambda name, profile="default": None)
    monkeypatch.setattr(service, "install",
                        lambda *a, **kw: "launchd")

    _write_pid(tmp_path, os.getpid())
    monkeypatch.setattr(os, "kill", lambda p, s: None)

    result = CliRunner().invoke(cli.main, ["gateway", "stop"])
    assert result.exit_code == 0
    assert "managed by" not in result.output
    assert "SIGTERM" in result.output


def test_stop_no_process_running(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    monkeypatch.delenv("ALPI_SKIP_AUTO_INSTALL", raising=False)
    from alpi import service
    monkeypatch.setattr(service, "installed", lambda *a, **kw: None)
    monkeypatch.setattr(service, "install", lambda *a, **kw: "launchd")

    result = CliRunner().invoke(cli.main, ["gateway", "stop"])
    assert result.exit_code == 0
    assert "not running" in result.output


def test_restart_without_service_degrades_gracefully(
    tmp_path: Path, monkeypatch,
) -> None:
    """No service registered → nothing will bring the daemon back;
    restart becomes a plain stop with a clear note."""
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    monkeypatch.delenv("ALPI_SKIP_AUTO_INSTALL", raising=False)

    from alpi import service
    monkeypatch.setattr(service, "installed", lambda *a, **kw: None)
    monkeypatch.setattr(service, "install", lambda *a, **kw: "launchd")

    _write_pid(tmp_path, os.getpid())
    sent: list[int] = []
    monkeypatch.setattr(os, "kill", lambda p, s: sent.append((p, s)))

    result = CliRunner().invoke(cli.main, ["gateway", "restart"])
    assert result.exit_code == 0
    assert "No service registered" in result.output
    assert sent  # SIGTERM was still sent


def test_restart_with_service_waits_for_bounce(
    tmp_path: Path, monkeypatch,
) -> None:
    """Service installed → poll pid file until a new pid appears."""
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    monkeypatch.delenv("ALPI_SKIP_AUTO_INSTALL", raising=False)

    from alpi import service
    monkeypatch.setattr(service, "installed",
                        lambda name, profile="default": "launchd")
    monkeypatch.setattr(service, "install",
                        lambda *a, **kw: "launchd")

    pid_file = _write_pid(tmp_path, os.getpid())
    monkeypatch.setattr(os, "kill", lambda p, s: None)

    # Simulate launchd rotating the pid file after a brief delay.
    def _relaunch_pid_file() -> None:
        time.sleep(0.2)
        pid_file.write_text(str(os.getpid() + 1))

    import threading
    threading.Thread(target=_relaunch_pid_file, daemon=True).start()

    result = CliRunner().invoke(cli.main, ["gateway", "restart"])
    assert result.exit_code == 0
    assert "restarted via launchd" in result.output


# Doctor stale-binary check


def test_stale_binary_detection_ignores_unknown_pid(monkeypatch) -> None:
    # ps on a bogus pid returns non-zero → no warn.
    assert doctor._is_binary_newer_than_process(time.time() + 100, 999999) is False


def test_stale_binary_detection_no_binary_found(monkeypatch) -> None:
    # If we can't locate the binary, don't warn.
    import shutil as _sh
    monkeypatch.setattr(_sh, "which", lambda x: None)
    assert doctor._alpi_binary_mtime() is None


def test_stale_binary_true_when_binary_newer(monkeypatch) -> None:
    """Use the current process as the probe — we can query ourselves
    with ps and control the pretend binary mtime."""
    future = time.time() + 10_000  # binary "modified" way after process start
    assert doctor._is_binary_newer_than_process(future, os.getpid()) is True


def test_stale_binary_false_when_binary_older(monkeypatch) -> None:
    past = time.time() - 365 * 24 * 3600   # binary modified a year ago
    assert doctor._is_binary_newer_than_process(past, os.getpid()) is False


# Surface: doctor service check flags the warn


def test_doctor_flags_stale_binary(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(doctor, "_alpi_binary_mtime", lambda: time.time() + 10_000)
    monkeypatch.setattr(doctor, "_live_pid", lambda home, name: os.getpid())
    from alpi import service
    monkeypatch.setattr(service, "installed",
                        lambda name, profile="default": "launchd")

    checks = doctor._check_services(tmp_path, "default")
    gateway_row = next(c for c in checks if c.name == "Gateway")
    assert gateway_row.status == "warn"
    assert "binary is newer" in gateway_row.detail
    assert "alpi gateway restart" in gateway_row.detail
