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
        task_map = service._profile_tasks(home, "alice", subs)
        tasks = [t for ts in task_map.values() for t in ts]
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
        task_map = service._profile_tasks(home, "alice", subs)
        tasks = [t for ts in task_map.values() for t in ts]
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
        task_map = service._profile_tasks(home, "default", subs)
        tasks = [t for ts in task_map.values() for t in ts]
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


def test_profile_home_resolves_against_root(tmp_path: Path) -> None:
    """``_profile_home`` honors the daemon's ``root``, not the import-time ``_ROOT``."""
    root = tmp_path / "alt-root"
    assert service._profile_home(root, "default") == root
    assert service._profile_home(root, "alfa") == root / "profiles" / "alfa"


def test_start_new_profiles_skips_already_active(
    monkeypatch, tmp_path: Path,
) -> None:
    """Re-scanning the same profile must not duplicate its tasks."""
    root = _make_root(tmp_path, ["alfa"])

    calls: list[tuple[Path, str]] = []

    def fake_profile_tasks(home, profile, subsystems):
        calls.append((home, profile))
        return {}

    monkeypatch.setattr(service, "_profile_tasks", fake_profile_tasks)
    registry: dict = {}

    service._start_new_profiles(root, ["default", "alfa"], registry)
    service._start_new_profiles(root, ["default", "alfa"], registry)

    assert calls == [
        (root, "default"),
        (root / "profiles" / "alfa", "alfa"),
    ]
    assert set(registry) == {"default", "alfa"}


def test_start_new_profiles_retries_on_config_error(
    monkeypatch, tmp_path: Path,
) -> None:
    """A broken config keeps the profile inactive so the next tick retries."""
    root = _make_root(tmp_path, ["alfa"])
    expected_home = root / "profiles" / "alfa"

    seen_homes: list[Path] = []

    def flaky(home: Path) -> dict[str, bool]:
        seen_homes.append(home)
        if len(seen_homes) == 1:
            raise RuntimeError("synthetic yaml error")
        return {
            "gateway": False, "schedule": False, "alp": False,
            "host": False, "workgroups": False,
        }

    monkeypatch.setattr(service, "enabled_subsystems", flaky)
    monkeypatch.setattr(service, "_profile_tasks", lambda *_: {})

    registry: dict = {}
    service._start_new_profiles(root, ["alfa"], registry)
    assert "alfa" not in registry

    service._start_new_profiles(root, ["alfa"], registry)
    assert "alfa" in registry
    assert seen_homes == [expected_home, expected_home]


def test_start_new_profiles_marks_zero_subsystem_profile_active(
    monkeypatch, tmp_path: Path,
) -> None:
    """Profile with everything disabled is still marked active to stop log spam."""
    root = _make_root(tmp_path, ["alfa"])

    monkeypatch.setattr(service, "enabled_subsystems", lambda _: {
        "gateway": False, "schedule": False, "alp": False,
        "host": False, "workgroups": False,
    })
    monkeypatch.setattr(service, "_profile_tasks", lambda *_: {})

    registry: dict = {}
    service._start_new_profiles(root, ["alfa"], registry)
    service._start_new_profiles(root, ["alfa"], registry)

    assert set(registry) == {"alfa"}
    assert registry["alfa"]["tasks"] == {}


@pytest.mark.asyncio
async def test_main_all_picks_up_runtime_profile(
    monkeypatch, tmp_path: Path,
) -> None:
    """A profile created after boot must be discovered by the rescan loop."""
    root = _make_root(tmp_path, ["alfa"])
    monkeypatch.setattr(service, "_PROFILE_RESCAN_SECONDS", 0.05)
    monkeypatch.setattr(service, "_prefetch_assets", lambda: None)
    monkeypatch.setattr(service, "_load_env", lambda *_: None)

    started: list[tuple[Path, str]] = []

    def fake_profile_tasks(home, profile, subsystems):
        started.append((home, profile))
        t = asyncio.create_task(asyncio.sleep(60), name=f"{profile}/fake")
        return {"fake": [t]}

    monkeypatch.setattr(service, "_profile_tasks", fake_profile_tasks)

    runner = asyncio.create_task(service._main_all(
        root, home_mod.list_profiles(root),
    ))
    try:
        for _ in range(40):
            await asyncio.sleep(0.02)
            names = {p for _, p in started}
            if {"default", "alfa"}.issubset(names):
                break
        names = {p for _, p in started}
        assert {"default", "alfa"}.issubset(names), started

        (root / "profiles" / "bravo").mkdir()
        (root / "profiles" / "bravo" / "config.yaml").write_text("model: x\n")

        for _ in range(40):
            await asyncio.sleep(0.05)
            if any(p == "bravo" for _, p in started):
                break
        bravo = [home for home, p in started if p == "bravo"]
        assert bravo == [root / "profiles" / "bravo"], started
    finally:
        runner.cancel()
        try:
            await runner
        except (asyncio.CancelledError, Exception):
            pass


def _fake_subsystem_tasks_factory(created: list):
    def fake(home, profile, name):
        t = asyncio.create_task(
            asyncio.sleep(60), name=f"{profile}/{name}#{len(created)}",
        )
        created.append((name, t))
        return [t]
    return fake


@pytest.mark.asyncio
async def test_reconcile_restarts_gateway_on_gateway_env_change(
    monkeypatch, tmp_path: Path,
) -> None:
    root = _make_root(tmp_path, [])
    created: list = []
    monkeypatch.setattr(service, "_subsystem_tasks", _fake_subsystem_tasks_factory(created))

    registry: dict = {}
    service._start_new_profiles(root, ["default"], registry)
    gateway_before = registry["default"]["tasks"]["gateway"][0]
    schedule_before = registry["default"]["tasks"]["schedule"][0]

    (root / ".env").write_text("TELEGRAM_BOT_TOKEN=tg-new\n")
    await service._reconcile_profiles(root, registry)

    assert gateway_before.cancelled()
    assert registry["default"]["tasks"]["gateway"][0] is not gateway_before
    assert registry["default"]["tasks"]["schedule"][0] is schedule_before

    for ts in registry["default"]["tasks"].values():
        for t in ts:
            t.cancel()
    await asyncio.gather(
        *[t for ts in registry["default"]["tasks"].values() for t in ts],
        return_exceptions=True,
    )


@pytest.mark.asyncio
async def test_reconcile_ignores_provider_key_changes(
    monkeypatch, tmp_path: Path,
) -> None:
    root = _make_root(tmp_path, [])
    created: list = []
    monkeypatch.setattr(service, "_subsystem_tasks", _fake_subsystem_tasks_factory(created))

    registry: dict = {}
    service._start_new_profiles(root, ["default"], registry)
    before = {k: v[0] for k, v in registry["default"]["tasks"].items()}

    (root / ".env").write_text("OPENROUTER_API_KEY=sk-rotated\n")
    await service._reconcile_profiles(root, registry)

    after = {k: v[0] for k, v in registry["default"]["tasks"].items()}
    assert after == before

    for t in after.values():
        t.cancel()
    await asyncio.gather(*after.values(), return_exceptions=True)


@pytest.mark.asyncio
async def test_reconcile_applies_subsystem_toggle_without_restart(
    monkeypatch, tmp_path: Path,
) -> None:
    root = _make_root(tmp_path, [])
    created: list = []
    monkeypatch.setattr(service, "_subsystem_tasks", _fake_subsystem_tasks_factory(created))

    registry: dict = {}
    service._start_new_profiles(root, ["default"], registry)
    schedule_task = registry["default"]["tasks"]["schedule"][0]
    gateway_task = registry["default"]["tasks"]["gateway"][0]

    (root / "config.yaml").write_text("model: x\nservice:\n  schedule: false\n")
    await service._reconcile_profiles(root, registry)

    assert schedule_task.cancelled()
    assert "schedule" not in registry["default"]["tasks"]
    assert registry["default"]["tasks"]["gateway"][0] is gateway_task

    (root / "config.yaml").write_text("model: x\nservice:\n  schedule: true\n")
    await service._reconcile_profiles(root, registry)
    assert "schedule" in registry["default"]["tasks"]

    for ts in registry["default"]["tasks"].values():
        for t in ts:
            t.cancel()
    await asyncio.gather(
        *[t for ts in registry["default"]["tasks"].values() for t in ts],
        return_exceptions=True,
    )


@pytest.mark.asyncio
async def test_reconcile_stops_tasks_when_profile_home_disappears(
    monkeypatch, tmp_path: Path,
) -> None:
    import shutil

    root = _make_root(tmp_path, ["alfa"])
    created: list = []
    monkeypatch.setattr(service, "_subsystem_tasks", _fake_subsystem_tasks_factory(created))

    registry: dict = {}
    service._start_new_profiles(root, ["alfa"], registry)
    tasks = [t for ts in registry["alfa"]["tasks"].values() for t in ts]
    assert tasks

    shutil.rmtree(root / "profiles" / "alfa")
    await service._reconcile_profiles(root, registry)

    assert "alfa" not in registry
    assert all(t.cancelled() for t in tasks)


def test_daemon_plist_raises_file_descriptor_limit() -> None:
    import plistlib

    # The macOS launchd default (256) is exhausted by many profiles × services;
    # the daemon must set its own ceiling, and the rendered plist must be valid.
    xml = service._DAEMON_PLIST_TEMPLATE.format(
        label="com.alpi.daemon",
        program_args="    <string>alpi</string>",
        log="/tmp/service.log",
    )
    parsed = plistlib.loads(xml.encode())
    assert parsed["SoftResourceLimits"]["NumberOfFiles"] == 8192
    assert parsed["HardResourceLimits"]["NumberOfFiles"] == 8192


def test_daemon_systemd_unit_raises_file_descriptor_limit() -> None:
    unit = service._DAEMON_UNIT_TEMPLATE.format(
        exec_start="alpi daemon start",
        log="/tmp/service.log",
    )
    service_section = unit.split("[Service]", 1)[1].split("[Install]", 1)[0]
    assert "LimitNOFILE=8192" in service_section


def test_docker_compose_raises_file_descriptor_limit() -> None:
    import yaml

    repo_root = Path(__file__).resolve().parents[2]
    compose = yaml.safe_load((repo_root / "docker-compose.yml").read_text())
    nofile = compose["services"]["alpi"]["ulimits"]["nofile"]
    assert nofile["soft"] == 8192
    assert nofile["hard"] == 8192
