"""``host.daemon.restart`` — schedules SIGTERM after returning, so the
launchd / systemd KeepAlive supervisor respawns with the latest config.
The verb is a hot-apply primitive used by the desktop and TUI when a
service flag toggles."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from alpi.host import daemon as data_daemon
from alpi.host import server as host_server


@pytest.mark.asyncio
async def test_returns_ok_and_schedules_sigterm(tmp_path: Path) -> None:
    home = tmp_path / "h"
    home.mkdir()
    srv = host_server.Server(home=home)
    data_daemon.register(srv)

    scheduled: list[float] = []

    class FakeLoop:
        def call_later(self, delay, _fn):
            scheduled.append(delay)

    with patch("asyncio.get_running_loop", return_value=FakeLoop()):
        resp = await srv._dispatch({
            "id": "r", "method": "host.daemon.restart", "params": {},
        })

    assert resp["result"] == {"ok": True, "respawn": True}
    # SIGTERM is scheduled, not invoked synchronously — the response
    # has a chance to flush before the daemon dies.
    assert len(scheduled) == 1
    assert 0.0 < scheduled[0] < 2.0


@pytest.mark.asyncio
async def test_update_upgrades_and_restarts_on_new_version(tmp_path: Path) -> None:
    home = tmp_path / "h"
    home.mkdir()
    srv = host_server.Server(home=home)
    data_daemon.register(srv)
    scheduled: list[float] = []

    result = {"ok": True, "updated": True, "current": "0.9.4", "latest": "0.9.5", "installer": "uv"}
    with patch("alpi.updater.update_now", return_value=result), \
         patch.object(data_daemon, "schedule_self_terminate", lambda delay=0.2: scheduled.append(delay)):
        resp = await srv._dispatch({
            "id": "u", "method": "host.daemon.update", "params": {},
        })

    assert resp["result"] == result
    assert len(scheduled) == 1


@pytest.mark.asyncio
async def test_update_does_not_restart_when_already_current(tmp_path: Path) -> None:
    home = tmp_path / "h"
    home.mkdir()
    srv = host_server.Server(home=home)
    data_daemon.register(srv)
    scheduled: list[float] = []

    result = {"ok": True, "updated": False, "current": "0.9.5", "latest": "0.9.5", "reason": "up-to-date"}
    with patch("alpi.updater.update_now", return_value=result), \
         patch.object(data_daemon, "schedule_self_terminate", lambda delay=0.2: scheduled.append(delay)):
        resp = await srv._dispatch({
            "id": "u", "method": "host.daemon.update", "params": {},
        })

    assert resp["result"] == result
    assert scheduled == []


def _serve_once(monkeypatch, tmp_path: Path, main) -> None:
    from alpi import service

    class Lock:
        def close(self) -> None:
            pass

    monkeypatch.setattr(service, "_configure_logging_daemon", lambda root: None)
    monkeypatch.setattr(service, "_acquire_singleton_lock", lambda root: Lock())
    monkeypatch.setattr(service, "register_stack_dump", lambda root: None)
    monkeypatch.setattr(service, "_set_proctitle_daemon", lambda n: None)
    monkeypatch.setattr(service, "_write_daemon_pid", lambda root: None)
    monkeypatch.setattr(service, "_clear_daemon_pid", lambda root: None)
    monkeypatch.setattr(service, "_main_all", main)
    monkeypatch.setattr("alpi.provider_pause.activate", lambda: None)
    monkeypatch.setattr(data_daemon, "_respawn_requested", False)
    service.serve_all(tmp_path)


def test_a_restart_the_daemon_asked_for_exits_non_zero_so_the_supervisor_respawns_it(monkeypatch, tmp_path: Path) -> None:
    killed: list[int] = []
    monkeypatch.setattr(data_daemon.os, "kill", lambda pid, sig: killed.append(sig))

    async def main(root, profiles) -> None:
        data_daemon._self_terminate()

    with pytest.raises(SystemExit) as stopped:
        _serve_once(monkeypatch, tmp_path, main)

    assert stopped.value.code == data_daemon.RESPAWN_EXIT_CODE != 0
    assert killed == [data_daemon.signal.SIGTERM]


def test_a_daemon_that_was_only_stopped_exits_clean(monkeypatch, tmp_path: Path) -> None:
    async def main(root, profiles) -> None:
        return None

    _serve_once(monkeypatch, tmp_path, main)

    assert data_daemon.respawn_requested() is False


class _Done:
    def __init__(self, returncode: int, stdout: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout


SHOW_MAIN_PID = ["systemctl", "--user", "show", "-p", "MainPID", "--value", "alpi-daemon.service"]
RESTART_UNIT = ["systemctl", "--user", "restart", "alpi-daemon.service"]


def _daemon(monkeypatch, commands: list, *, backend: str = "systemd", installed: bool = True,
            main_pid: str = "4242", restart_code: int = 0) -> None:
    from alpi import service

    def run(cmd, check, timeout=None):
        commands.append(cmd)
        return _Done(0, main_pid) if cmd == SHOW_MAIN_PID else _Done(restart_code)

    monkeypatch.setattr(service, "daemon_running_pid", lambda root: 4242)
    monkeypatch.setattr(service, "stop_daemon", lambda root, timeout=5.0: commands.append("stop") or True)
    monkeypatch.setattr(service, "daemon_installed", lambda: installed)
    monkeypatch.setattr(service, "_detect_backend", lambda: backend)
    monkeypatch.setattr(service, "_run", run)


def test_console_restart_restarts_the_systemd_unit_that_runs_the_daemon(monkeypatch) -> None:
    from click.testing import CliRunner

    from alpi import cli

    commands: list = []
    _daemon(monkeypatch, commands)

    result = CliRunner().invoke(cli.main, ["daemon", "restart"])

    assert result.exit_code == 0, result.output
    assert commands == [SHOW_MAIN_PID, "stop", RESTART_UNIT]
    assert "respawn" in result.output


@pytest.mark.parametrize("setup", [
    {"backend": "launchd"},
    {"installed": False},
    {"main_pid": "0"},
    {"main_pid": "777"},
])
def test_restart_only_stops_a_daemon_systemd_did_not_start(monkeypatch, tmp_path: Path, setup: dict) -> None:
    from alpi import service

    commands: list = []
    _daemon(monkeypatch, commands, **setup)

    assert service.restart_daemon(tmp_path) is True
    assert RESTART_UNIT not in commands and commands[-1] == "stop"


def test_console_restart_says_so_when_systemd_does_not_start_it(monkeypatch) -> None:
    from click.testing import CliRunner

    from alpi import cli

    _daemon(monkeypatch, [], restart_code=1)

    result = CliRunner().invoke(cli.main, ["daemon", "restart"])

    assert result.exit_code == 1
    assert "respawn" not in result.output
    assert "systemctl --user start alpi-daemon.service" in result.output


@pytest.mark.parametrize("restart_code, said", [(0, "daemon restarting"), (1, "systemd did not start it again")])
def test_a_setting_that_needs_a_restart_restarts_the_systemd_unit(monkeypatch, tmp_path: Path, restart_code: int, said: str) -> None:
    from alpi import cli

    commands: list = []
    _daemon(monkeypatch, commands, restart_code=restart_code)

    assert said in cli._restart_daemon_for_apply(tmp_path)
    assert commands == [SHOW_MAIN_PID, "stop", RESTART_UNIT]


@pytest.mark.parametrize("failure", [FileNotFoundError("systemctl"), __import__("subprocess").TimeoutExpired("systemctl", 30)])
def test_restart_survives_a_machine_where_systemctl_fails(monkeypatch, tmp_path: Path, failure: Exception) -> None:
    from alpi import service

    def run(cmd, check, timeout=None):
        if cmd == SHOW_MAIN_PID:
            return _Done(0, "4242")
        raise failure

    commands: list = []
    _daemon(monkeypatch, commands)
    monkeypatch.setattr(service, "_run", run)

    assert service.restart_daemon(tmp_path) is False
    assert commands == ["stop"]


def test_restart_treats_an_unreachable_systemd_as_not_supervising(monkeypatch, tmp_path: Path) -> None:
    from alpi import service

    def run(cmd, check, timeout=None):
        raise FileNotFoundError("systemctl")

    commands: list = []
    _daemon(monkeypatch, commands)
    monkeypatch.setattr(service, "_run", run)

    assert service.restart_daemon(tmp_path) is True
    assert commands == ["stop"]


def test_stopping_the_daemon_closes_the_browser_after_the_workers_and_before_the_lock(monkeypatch, tmp_path: Path) -> None:
    from alpi import service
    from alpi.host import workers

    order: list[str] = []

    class Lock:
        def close(self) -> None:
            order.append("lock")

    async def main(root, profiles) -> None:
        order.append("served")

    import signal

    monkeypatch.setattr(workers, "shutdown", lambda: order.append("workers"))
    monkeypatch.setattr(
        service, "_close_browser",
        lambda: order.append("browser, signals held" if signal.getsignal(signal.SIGINT) is signal.SIG_IGN else "browser"),
    )
    monkeypatch.setattr(service, "_configure_logging_daemon", lambda root: None)
    monkeypatch.setattr(service, "_acquire_singleton_lock", lambda root: Lock())
    monkeypatch.setattr(service, "register_stack_dump", lambda root: None)
    monkeypatch.setattr(service, "_set_proctitle_daemon", lambda n: None)
    monkeypatch.setattr(service, "_write_daemon_pid", lambda root: None)
    monkeypatch.setattr(service, "_clear_daemon_pid", lambda root: None)
    monkeypatch.setattr(service, "_main_all", main)
    monkeypatch.setattr("alpi.provider_pause.activate", lambda: None)
    monkeypatch.setattr(data_daemon, "_respawn_requested", False)

    service.serve_all(tmp_path)

    assert order == ["served", "workers", "browser, signals held", "lock"]


def test_closing_the_browser_at_stop_never_loads_it_and_never_stops_the_shutdown(monkeypatch) -> None:
    import sys
    import types

    from alpi import service

    monkeypatch.delitem(sys.modules, "alpi.tools.browser", raising=False)
    service._close_browser()
    assert "alpi.tools.browser" not in sys.modules

    closed: list[str] = []
    monkeypatch.setitem(sys.modules, "alpi.tools.browser", types.SimpleNamespace(_shutdown=lambda wait: closed.append(wait)))
    service._close_browser()
    assert len(closed) == 1 and closed[0] < 5

    def broken(wait: float) -> None:
        raise RuntimeError("chromium is gone")

    monkeypatch.setitem(sys.modules, "alpi.tools.browser", types.SimpleNamespace(_shutdown=broken))
    service._close_browser()
