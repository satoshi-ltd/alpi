"""Tests for alpi.service — install/uninstall for gateway + schedule.

Both backends (launchd/systemd) are exercised via ``platform.system``
monkeypatching; ``subprocess.run`` is mocked so we never touch the
real OS. Verifies:
- Correct plist/unit path and content
- Correct launchctl/systemctl arguments
- Conflict detection with a manually-running daemon (handled in the
  CLI helper; we unit-test its inputs via a minimal click harness).
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from alpi import service


# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------


@pytest.fixture
def mock_run(monkeypatch):
    """Capture all ``subprocess.run`` calls made from service._run."""
    calls: list[dict] = []

    def fake(args, check=True):
        calls.append({"args": args, "check": check})
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(service, "_run", fake)
    return calls


@pytest.fixture
def fake_home(tmp_path: Path):
    return tmp_path / "home"


# --------------------------------------------------------------------
# Backend detection + name validation
# --------------------------------------------------------------------


def test_unknown_name_rejected() -> None:
    with pytest.raises(service.ServiceError, match="unknown daemon name"):
        service.install("chaos", Path("/tmp"), "default")


def test_unsupported_platform_raises(monkeypatch, fake_home) -> None:
    monkeypatch.setattr(service.platform, "system", lambda: "Windows")
    with pytest.raises(service.ServiceError, match="unsupported platform"):
        service.install("gateway", fake_home, "default")


# --------------------------------------------------------------------
# launchd (macOS)
# --------------------------------------------------------------------


def test_launchd_install_writes_plist_and_bootstraps(
        monkeypatch, mock_run, fake_home, tmp_path) -> None:
    monkeypatch.setattr(service.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(service.shutil, "which", lambda n: "/usr/local/bin/alpi")
    monkeypatch.setattr(service.os, "getuid", lambda: 501)
    monkeypatch.setattr(service.Path, "home", classmethod(lambda cls: tmp_path))

    backend = service.install("schedule", fake_home, "work")

    assert backend == "launchd"
    plist = tmp_path / "Library/LaunchAgents/com.alpi.schedule.work.plist"
    assert plist.exists()
    content = plist.read_text()
    assert "<string>com.alpi.schedule.work</string>" in content
    assert "<string>/usr/local/bin/alpi</string>" in content
    assert "<string>schedule</string>" in content
    assert "<string>start</string>" in content
    assert f"<string>{fake_home}</string>" in content
    assert "<key>RunAtLoad</key>" in content
    assert "<key>KeepAlive</key>" in content

    # bootout first (idempotency), then bootstrap.
    cmds = [c["args"] for c in mock_run]
    assert cmds[0] == ["launchctl", "bootout", "gui/501", str(plist)]
    assert cmds[1] == ["launchctl", "bootstrap", "gui/501", str(plist)]


def test_launchd_uninstall_bootouts_and_removes_plist(
        monkeypatch, mock_run, fake_home, tmp_path) -> None:
    monkeypatch.setattr(service.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(service.os, "getuid", lambda: 501)
    monkeypatch.setattr(service.Path, "home", classmethod(lambda cls: tmp_path))

    plist = tmp_path / "Library/LaunchAgents/com.alpi.gateway.default.plist"
    plist.parent.mkdir(parents=True, exist_ok=True)
    plist.write_text("<plist/>")

    backend = service.uninstall("gateway", fake_home, "default")

    assert backend == "launchd"
    assert not plist.exists()
    assert mock_run[0]["args"] == [
        "launchctl", "bootout", "gui/501", str(plist),
    ]


def test_launchd_uninstall_errors_if_not_installed(
        monkeypatch, fake_home, tmp_path) -> None:
    monkeypatch.setattr(service.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(service.Path, "home", classmethod(lambda cls: tmp_path))
    with pytest.raises(service.ServiceError, match="not installed"):
        service.uninstall("schedule", fake_home, "default")


def test_launchd_install_reports_bootstrap_failure(
        monkeypatch, fake_home, tmp_path) -> None:
    monkeypatch.setattr(service.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(service.shutil, "which", lambda n: "/usr/local/bin/alpi")
    monkeypatch.setattr(service.os, "getuid", lambda: 501)
    monkeypatch.setattr(service.Path, "home", classmethod(lambda cls: tmp_path))

    def fake_run(args, check=True):
        if args[1] == "bootstrap":
            return subprocess.CompletedProcess(args, 5, stdout="", stderr="boom")
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(service, "_run", fake_run)

    with pytest.raises(service.ServiceError, match="bootstrap failed"):
        service.install("schedule", fake_home, "default")


# --------------------------------------------------------------------
# systemd --user (Linux)
# --------------------------------------------------------------------


def test_systemd_install_writes_unit_and_enables(
        monkeypatch, mock_run, fake_home, tmp_path) -> None:
    monkeypatch.setattr(service.platform, "system", lambda: "Linux")
    monkeypatch.setattr(service.shutil, "which", lambda n: "/home/x/.local/bin/alpi")
    monkeypatch.setattr(service.Path, "home", classmethod(lambda cls: tmp_path))

    backend = service.install("gateway", fake_home, "personal")

    assert backend == "systemd"
    unit = tmp_path / ".config/systemd/user/alpi-gateway-personal.service"
    assert unit.exists()
    content = unit.read_text()
    assert "alpi gateway daemon (personal)" in content
    assert f"ExecStart=/home/x/.local/bin/alpi gateway start" in content
    assert f"Environment=ALPI_HOME={fake_home}" in content
    assert "Restart=on-failure" in content
    assert "WantedBy=default.target" in content

    cmds = [c["args"] for c in mock_run]
    assert cmds[0] == ["systemctl", "--user", "daemon-reload"]
    assert cmds[1] == [
        "systemctl", "--user", "enable", "--now",
        "alpi-gateway-personal.service",
    ]


def test_systemd_uninstall_disables_and_removes_unit(
        monkeypatch, mock_run, fake_home, tmp_path) -> None:
    monkeypatch.setattr(service.platform, "system", lambda: "Linux")
    monkeypatch.setattr(service.Path, "home", classmethod(lambda cls: tmp_path))

    unit = tmp_path / ".config/systemd/user/alpi-schedule-default.service"
    unit.parent.mkdir(parents=True, exist_ok=True)
    unit.write_text("[Unit]\n")

    service.uninstall("schedule", fake_home, "default")

    assert not unit.exists()
    cmds = [c["args"] for c in mock_run]
    assert ["systemctl", "--user", "disable", "--now",
            "alpi-schedule-default.service"] in cmds
    assert ["systemctl", "--user", "daemon-reload"] in cmds


def test_systemd_install_surfaces_bus_error(monkeypatch, fake_home, tmp_path) -> None:
    monkeypatch.setattr(service.platform, "system", lambda: "Linux")
    monkeypatch.setattr(service.shutil, "which", lambda n: "/usr/bin/alpi")
    monkeypatch.setattr(service.Path, "home", classmethod(lambda cls: tmp_path))

    def fake_run(args, check=True):
        return subprocess.CompletedProcess(
            args, 1, stdout="", stderr="Failed to connect to bus: No such file",
        )

    monkeypatch.setattr(service, "_run", fake_run)

    with pytest.raises(service.ServiceError) as e:
        service.install("schedule", fake_home, "default")
    assert "daemon-reload failed" in str(e.value)
    assert "systemd --user" in str(e.value)  # the helpful hint


# --------------------------------------------------------------------
# installed() probe
# --------------------------------------------------------------------


def test_installed_returns_none_when_no_file(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(service.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(service.Path, "home", classmethod(lambda cls: tmp_path))
    assert service.installed("gateway", "default") is None


def test_installed_detects_existing_plist(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(service.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(service.Path, "home", classmethod(lambda cls: tmp_path))
    plist = tmp_path / "Library/LaunchAgents/com.alpi.schedule.default.plist"
    plist.parent.mkdir(parents=True, exist_ok=True)
    plist.write_text("x")
    assert service.installed("schedule", "default") == "launchd"


def test_installed_detects_existing_unit(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(service.platform, "system", lambda: "Linux")
    monkeypatch.setattr(service.Path, "home", classmethod(lambda cls: tmp_path))
    unit = tmp_path / ".config/systemd/user/alpi-gateway-work.service"
    unit.parent.mkdir(parents=True, exist_ok=True)
    unit.write_text("[Unit]\n")
    assert service.installed("gateway", "work") == "systemd"


# --------------------------------------------------------------------
# Misc
# --------------------------------------------------------------------


def test_service_label_varies_by_platform(monkeypatch) -> None:
    monkeypatch.setattr(service.platform, "system", lambda: "Darwin")
    assert service.service_label("schedule", "default") == "com.alpi.schedule.default"
    monkeypatch.setattr(service.platform, "system", lambda: "Linux")
    assert service.service_label("gateway", "work") == "alpi-gateway-work"


def test_locate_alpi_falls_back_to_python_dash_m(monkeypatch) -> None:
    monkeypatch.setattr(service.shutil, "which", lambda n: None)
    path = service._locate_alpi()
    assert "-m alpi" in path
    assert path.split()[0].endswith("python") or "python" in path.split()[0]
