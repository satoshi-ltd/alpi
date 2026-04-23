"""Scheduler auto-install on first `alpi` run."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from alpi import cli


def test_autoinstall_skipped_when_env_flag_set(tmp_path: Path, monkeypatch) -> None:
    """Conftest sets ALPI_SKIP_AUTO_INSTALL=1; the helper must honour it."""
    calls: list[tuple] = []
    from alpi import service
    monkeypatch.setattr(service, "installed", lambda *a, **kw: (calls.append(("inst",)) or None))
    monkeypatch.setattr(service, "install", lambda *a, **kw: (calls.append(("install",)) or "launchd"))

    cli._auto_install_scheduler(tmp_path, "default")
    assert calls == []


def test_autoinstall_called_on_main(tmp_path: Path, monkeypatch) -> None:
    """With the skip flag off, the callback installs schedule once."""
    monkeypatch.delenv("ALPI_SKIP_AUTO_INSTALL", raising=False)
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    calls: list[str] = []

    from alpi import service
    monkeypatch.setattr(service, "installed", lambda name, profile="default": None)
    monkeypatch.setattr(
        service, "install",
        lambda name, h, profile="default": (calls.append(name) or "launchd"),
    )

    # Invoke a harmless subcommand that goes through main() callback.
    CliRunner().invoke(cli.main, ["logs", "--help"])
    assert calls == ["schedule"]


def test_autoinstall_skipped_for_daemon_entrypoints(tmp_path: Path, monkeypatch) -> None:
    """``alpi schedule start`` is launchd's invocation — don't re-install from inside."""
    monkeypatch.delenv("ALPI_SKIP_AUTO_INSTALL", raising=False)
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    calls: list[str] = []

    from alpi import service
    monkeypatch.setattr(service, "installed", lambda name, profile="default": None)
    monkeypatch.setattr(
        service, "install",
        lambda name, h, profile="default": (calls.append(name) or "launchd"),
    )

    # schedule/gateway groups short-circuit — use --help so we don't start the daemon.
    CliRunner().invoke(cli.main, ["schedule", "start", "--help"])
    CliRunner().invoke(cli.main, ["gateway", "start", "--help"])
    assert calls == []


def test_autoinstall_respects_uninstall_marker(tmp_path: Path, monkeypatch) -> None:
    """After the first attempt, a later run must NOT reinstall — otherwise
    uninstalling via the wizard silently reverses on next `alpi` call."""
    monkeypatch.delenv("ALPI_SKIP_AUTO_INSTALL", raising=False)
    calls: list[str] = []
    from alpi import service
    monkeypatch.setattr(service, "installed", lambda *a, **kw: None)
    monkeypatch.setattr(
        service, "install",
        lambda name, h, profile="default": (calls.append(name) or "launchd"),
    )

    # First run: installs and drops the marker.
    cli._auto_install_scheduler(tmp_path, "default")
    assert calls == ["schedule"]
    assert (tmp_path / "schedule" / ".bootstrapped").exists()

    # Second run (simulating the user having uninstalled via the wizard
    # in between): marker present → must NOT re-install.
    cli._auto_install_scheduler(tmp_path, "default")
    assert calls == ["schedule"], "should not re-install after first-run marker"


def test_autoinstall_swallows_service_errors(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("ALPI_SKIP_AUTO_INSTALL", raising=False)
    from alpi import service

    def boom(*a, **kw):
        raise service.ServiceError("no launchctl here")

    monkeypatch.setattr(service, "installed", lambda *a, **kw: None)
    monkeypatch.setattr(service, "install", boom)

    # Must not raise.
    cli._auto_install_scheduler(tmp_path, "default")
