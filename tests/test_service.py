"""Unified service install + lifecycle helpers.

Covers the new (post-unification) ``alpi.service`` API. The legacy
per-daemon (``gateway`` / ``schedule`` / ``alp``) install model is
gone — there's one plist / unit per profile, supervising the single
``alpi -p <profile> service start`` process that orchestrates every
enabled subsystem on one asyncio loop.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from alpi import service


@pytest.fixture
def tmp_home() -> Path:
    d = Path(tempfile.mkdtemp(prefix="alpi-svc-test-"))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


# Backend selection


def test_unsupported_platform_raises(monkeypatch, tmp_home: Path) -> None:
    monkeypatch.setattr("platform.system", lambda: "FreeBSD")
    with pytest.raises(service.ServiceError, match="unsupported platform"):
        service.install(tmp_home, "alice")


# launchd (macOS)


def test_launchd_install_writes_plist_and_bootstraps(
    monkeypatch, tmp_home: Path, tmp_path: Path,
) -> None:
    monkeypatch.setattr("platform.system", lambda: "Darwin")
    monkeypatch.setattr(service, "_locate_alpi", lambda: "/usr/local/bin/alpi")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    fake_run = MagicMock(return_value=subprocess.CompletedProcess(
        args=[], returncode=0, stdout="", stderr="",
    ))
    monkeypatch.setattr(service, "_run", fake_run)

    backend = service.install(tmp_home, "alice")
    assert backend == "launchd"

    plist = tmp_path / "Library" / "LaunchAgents" / "com.alpi.service.alice.plist"
    assert plist.exists()
    body = plist.read_text()
    assert "com.alpi.service.alice" in body
    assert "/usr/local/bin/alpi" in body
    assert "<string>service</string>" in body
    assert "<string>alice</string>" in body
    assert "RunAtLoad" in body and "KeepAlive" in body

    assert any(
        call.args[0][0] == "launchctl" and call.args[0][1] == "bootstrap"
        for call in fake_run.call_args_list
    )


def test_launchd_uninstall_bootouts_and_removes_plist(
    monkeypatch, tmp_home: Path, tmp_path: Path,
) -> None:
    monkeypatch.setattr("platform.system", lambda: "Darwin")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(service, "_run", MagicMock(
        return_value=subprocess.CompletedProcess(args=[], returncode=0,
                                                  stdout="", stderr=""),
    ))
    plist_dir = tmp_path / "Library" / "LaunchAgents"
    plist_dir.mkdir(parents=True)
    plist = plist_dir / "com.alpi.service.alice.plist"
    plist.write_text("<plist/>")

    backend = service.uninstall(tmp_home, "alice")
    assert backend == "launchd"
    assert not plist.exists()


def test_launchd_uninstall_errors_if_not_installed(
    monkeypatch, tmp_home: Path, tmp_path: Path,
) -> None:
    monkeypatch.setattr("platform.system", lambda: "Darwin")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    with pytest.raises(service.ServiceError, match="not installed"):
        service.uninstall(tmp_home, "alice")


def test_launchd_install_reports_bootstrap_failure(
    monkeypatch, tmp_home: Path, tmp_path: Path,
) -> None:
    monkeypatch.setattr("platform.system", lambda: "Darwin")
    monkeypatch.setattr(service, "_locate_alpi", lambda: "/usr/local/bin/alpi")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(service, "_run", MagicMock(
        return_value=subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="permission denied",
        ),
    ))
    with pytest.raises(service.ServiceError, match="bootstrap failed"):
        service.install(tmp_home, "alice")


# systemd --user (Linux)


def test_systemd_install_writes_unit_and_enables(
    monkeypatch, tmp_home: Path, tmp_path: Path,
) -> None:
    monkeypatch.setattr("platform.system", lambda: "Linux")
    monkeypatch.setattr(service, "_locate_alpi", lambda: "/usr/local/bin/alpi")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(service, "_run", MagicMock(
        return_value=subprocess.CompletedProcess(args=[], returncode=0,
                                                  stdout="", stderr=""),
    ))
    backend = service.install(tmp_home, "alice")
    assert backend == "systemd"
    unit = tmp_path / ".config" / "systemd" / "user" / "alpi-service-alice.service"
    assert unit.exists()
    body = unit.read_text()
    assert "ExecStart=/usr/local/bin/alpi -p alice service start" in body
    assert "Restart=on-failure" in body


def test_systemd_uninstall_disables_and_removes_unit(
    monkeypatch, tmp_home: Path, tmp_path: Path,
) -> None:
    monkeypatch.setattr("platform.system", lambda: "Linux")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(service, "_run", MagicMock(
        return_value=subprocess.CompletedProcess(args=[], returncode=0,
                                                  stdout="", stderr=""),
    ))
    unit_dir = tmp_path / ".config" / "systemd" / "user"
    unit_dir.mkdir(parents=True)
    unit = unit_dir / "alpi-service-alice.service"
    unit.write_text("[Unit]\n")

    service.uninstall(tmp_home, "alice")
    assert not unit.exists()


def test_systemd_install_surfaces_bus_error(
    monkeypatch, tmp_home: Path, tmp_path: Path,
) -> None:
    monkeypatch.setattr("platform.system", lambda: "Linux")
    monkeypatch.setattr(service, "_locate_alpi", lambda: "/usr/local/bin/alpi")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(service, "_run", MagicMock(
        return_value=subprocess.CompletedProcess(
            args=[], returncode=1, stdout="",
            stderr="Failed to connect to bus: No such file or directory",
        ),
    ))
    with pytest.raises(service.ServiceError) as exc:
        service.install(tmp_home, "alice")
    assert "tmux/screen" in str(exc.value)


# Detection helpers


def test_installed_returns_none_when_no_file(
    monkeypatch, tmp_path: Path,
) -> None:
    monkeypatch.setattr("platform.system", lambda: "Darwin")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    assert service.installed("alice") is None


def test_installed_detects_existing_plist(
    monkeypatch, tmp_path: Path,
) -> None:
    monkeypatch.setattr("platform.system", lambda: "Darwin")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    plist_dir = tmp_path / "Library" / "LaunchAgents"
    plist_dir.mkdir(parents=True)
    (plist_dir / "com.alpi.service.alice.plist").write_text("<plist/>")
    assert service.installed("alice") == "launchd"


def test_installed_detects_existing_unit(
    monkeypatch, tmp_path: Path,
) -> None:
    monkeypatch.setattr("platform.system", lambda: "Linux")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    unit_dir = tmp_path / ".config" / "systemd" / "user"
    unit_dir.mkdir(parents=True)
    (unit_dir / "alpi-service-alice.service").write_text("[Unit]\n")
    assert service.installed("alice") == "systemd"


def test_label_varies_by_platform(monkeypatch) -> None:
    monkeypatch.setattr("platform.system", lambda: "Darwin")
    assert service.label("alice") == "com.alpi.service.alice"
    monkeypatch.setattr("platform.system", lambda: "Linux")
    assert service.label("alice") == "alpi-service-alice"


# Subsystem toggle + PID lifecycle helpers


def test_enabled_subsystems_defaults_all_on_when_section_missing(
    tmp_home: Path,
) -> None:
    (tmp_home / "config.yaml").write_text("model: x\n")
    on = service.enabled_subsystems(tmp_home)
    assert on == {
        "gateway": True, "schedule": True, "alp": True, "workgroups": True,
    }


def test_enabled_subsystems_honours_explicit_toggles(tmp_home: Path) -> None:
    (tmp_home / "config.yaml").write_text(
        "model: x\nservice:\n  gateway: false\n  schedule: true\n"
        "  alp: false\n  workgroups: false\n",
    )
    on = service.enabled_subsystems(tmp_home)
    assert on == {
        "gateway": False, "schedule": True, "alp": False, "workgroups": False,
    }


def test_running_pid_clears_stale_pid_file(tmp_home: Path) -> None:
    """A PID file pointing at a dead process should be cleaned up so
    callers see a clean ``not running`` state."""
    pid_file = service.pid_path(tmp_home)
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text("999999")  # almost-certainly-dead pid
    assert service.running_pid(tmp_home) is None
    assert not pid_file.exists()


def test_running_pid_returns_live_pid(tmp_home: Path) -> None:
    pid_file = service.pid_path(tmp_home)
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(str(os.getpid()))
    assert service.running_pid(tmp_home) == os.getpid()


def test_status_reports_subsystems_and_running_state(tmp_home: Path) -> None:
    (tmp_home / "config.yaml").write_text("model: x\n")
    info = service.status(tmp_home, "alice")
    assert info["profile"] == "alice"
    assert info["running"] is False
    assert info["subsystems"] == {
        "gateway": True, "schedule": True, "alp": True, "workgroups": True,
    }


def test_parse_etime_handles_all_three_formats() -> None:
    assert service._parse_etime("00:42") == 42
    assert service._parse_etime("01:30:00") == 5400
    assert service._parse_etime("2-03:00:00") == 2 * 86400 + 3 * 3600
