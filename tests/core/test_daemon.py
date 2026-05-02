"""Daemon orchestration and install tests."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from alpi import home as home_mod
from alpi import service


def _make_root(tmp_path: Path, profile_names: list[str]) -> Path:
    root = tmp_path / "root"
    root.mkdir()
    (root / "config.yaml").write_text("model: x\n")
    for name in profile_names:
        d = root / "profiles" / name
        d.mkdir(parents=True)
        (d / "config.yaml").write_text("model: x\n")
    return root


def test_list_profiles_returns_default_first(tmp_path: Path) -> None:
    root = _make_root(tmp_path, ["bravo", "alfa"])
    profiles = home_mod.list_profiles(root)
    # default first; others sorted alphabetically.
    assert profiles == ["default", "alfa", "bravo"]


def test_list_profiles_skips_dotdirs(tmp_path: Path) -> None:
    root = _make_root(tmp_path, ["alice"])
    (root / "profiles" / ".trash").mkdir()
    profiles = home_mod.list_profiles(root)
    assert profiles == ["default", "alice"]


def test_list_profiles_when_no_profiles_subdir(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    assert home_mod.list_profiles(root) == ["default"]


def test_profile_tasks_respects_subsystem_flags(tmp_path: Path) -> None:
    """Only enabled subsystems get tasks; host stays default-only."""
    home = tmp_path / "h"
    home.mkdir()
    subs = {
        "gateway": True, "schedule": False, "alp": True,
        "host": True, "workgroups": False,
    }

    async def run() -> list[str]:
        tasks = service._profile_tasks(home, "alice", subs)
        names = [t.get_name() for t in tasks]
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        return names

    names = asyncio.run(run())
    assert "alice/gateway" in names
    assert "alice/alp" in names
    assert "alice/schedule" not in names
    # Host is blocked twice: task assembly and supervisor.
    assert not any(n.endswith("/host") for n in names)
    # Workgroups off means no poller or preempt watcher.
    assert not any("workgroup" in n for n in names)


def test_profile_tasks_workgroups_includes_preempt_watcher(
    tmp_path: Path,
) -> None:
    """Workgroups enable both the poller and the preempt watcher."""
    home = tmp_path / "h"
    home.mkdir()
    subs = {
        "gateway": False, "schedule": False, "alp": False,
        "host": False, "workgroups": True,
    }

    async def run() -> list[str]:
        tasks = service._profile_tasks(home, "alice", subs)
        names = [t.get_name() for t in tasks]
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        return names

    names = asyncio.run(run())
    assert "alice/workgroups" in names
    assert "alice/workgroup-preempt" in names


def test_profile_tasks_host_only_for_default(tmp_path: Path) -> None:
    home = tmp_path / "h"
    home.mkdir()
    subs = {
        "gateway": False, "schedule": False, "alp": False,
        "host": True, "workgroups": False,
    }

    async def run() -> list[str]:
        tasks = service._profile_tasks(home, "default", subs)
        names = [t.get_name() for t in tasks]
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        return names

    assert "default/host" in asyncio.run(run())


def test_daemon_pid_helpers_roundtrip(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    assert service.daemon_running_pid(root) is None

    # Live pid should round-trip.
    import os
    service._write_daemon_pid(root)
    assert service.daemon_pid_path(root).exists()
    assert service.daemon_running_pid(root) == os.getpid()

    service._clear_daemon_pid(root)
    assert not service.daemon_pid_path(root).exists()


def test_daemon_running_pid_clears_stale(tmp_path: Path) -> None:
    """Stale PID files are cleaned up on read."""
    root = tmp_path / "root"
    root.mkdir()
    p = service.daemon_pid_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("999999")  # well past PID_MAX on any sane host
    assert service.daemon_running_pid(root) is None
    assert not p.exists()


def test_install_daemon_writes_plist_and_bootstraps(
    monkeypatch, tmp_path: Path,
) -> None:
    """``install_daemon`` writes and bootstraps the launchd plist."""
    import subprocess
    from unittest.mock import MagicMock

    monkeypatch.setattr("platform.system", lambda: "Darwin")
    monkeypatch.setattr(service, "_locate_alpi", lambda: "/usr/local/bin/alpi")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    fake_run = MagicMock(return_value=subprocess.CompletedProcess(
        args=[], returncode=0, stdout="", stderr="",
    ))
    monkeypatch.setattr(service, "_run", fake_run)

    root = tmp_path / "root"
    root.mkdir()

    backend = service.install_daemon(root)
    assert backend == "launchd"

    plist = tmp_path / "Library" / "LaunchAgents" / "com.alpi.daemon.plist"
    assert plist.exists()
    content = plist.read_text()
    assert "<string>com.alpi.daemon</string>" in content
    # No ``-p`` flag; the daemon is machine-wide.
    assert "<string>-p</string>" not in content
    assert "<string>daemon</string>" in content
    assert "<string>start</string>" in content


def test_daemon_installed_reflects_plist_presence(
    monkeypatch, tmp_path: Path,
) -> None:
    monkeypatch.setattr("platform.system", lambda: "Darwin")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    assert service.daemon_installed() is False
    p = tmp_path / "Library" / "LaunchAgents" / "com.alpi.daemon.plist"
    p.parent.mkdir(parents=True)
    p.write_text("<plist/>")
    assert service.daemon_installed() is True


def test_uninstall_daemon_removes_plist(monkeypatch, tmp_path: Path) -> None:
    import subprocess
    from unittest.mock import MagicMock

    monkeypatch.setattr("platform.system", lambda: "Darwin")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(service, "_run", MagicMock(return_value=(
        subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
    )))
    p = tmp_path / "Library" / "LaunchAgents" / "com.alpi.daemon.plist"
    p.parent.mkdir(parents=True)
    p.write_text("<plist/>")
    backend = service.uninstall_daemon()
    assert backend == "launchd"
    assert not p.exists()


def test_systemd_install_runs_enable_linger(
    monkeypatch, tmp_path: Path,
) -> None:
    """Systemd install should try ``loginctl enable-linger``."""
    import subprocess
    from unittest.mock import MagicMock

    monkeypatch.setattr("platform.system", lambda: "Linux")
    monkeypatch.setattr(service, "_locate_alpi", lambda: "/usr/local/bin/alpi")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    fake_run = MagicMock(return_value=subprocess.CompletedProcess(
        args=[], returncode=0, stdout="", stderr="",
    ))
    monkeypatch.setattr(service, "_run", fake_run)

    root = tmp_path / "root"
    root.mkdir()
    service.install_daemon(root)

    cmds = [call.args[0] for call in fake_run.call_args_list]
    assert any(
        c[:2] == ["loginctl", "enable-linger"] for c in cmds
    ), f"expected loginctl enable-linger in {cmds}"


@pytest.mark.asyncio
async def test_supervise_isolates_subsystem_crash() -> None:
    """Crashes stay isolated inside the supervisor."""

    async def boom(home: Path, profile: str) -> None:
        raise RuntimeError("synthetic crash")

    # ``alp`` exercises the (home, profile) call shape.
    await service._supervise(boom, Path("/tmp"), "alice", "alp")
    # If we got here, the crash was swallowed.
