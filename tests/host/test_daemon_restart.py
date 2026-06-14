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

    class FakeLoop:
        def call_later(self, delay, _fn):
            scheduled.append(delay)

    result = {"ok": True, "updated": True, "current": "0.9.4", "latest": "0.9.5", "installer": "uv"}
    with patch("alpi.updater.update_now", return_value=result), \
         patch("asyncio.get_running_loop", return_value=FakeLoop()):
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

    class FakeLoop:
        def call_later(self, delay, _fn):
            scheduled.append(delay)

    result = {"ok": True, "updated": False, "current": "0.9.5", "latest": "0.9.5", "reason": "up-to-date"}
    with patch("alpi.updater.update_now", return_value=result), \
         patch("asyncio.get_running_loop", return_value=FakeLoop()):
        resp = await srv._dispatch({
            "id": "u", "method": "host.daemon.update", "params": {},
        })

    assert resp["result"] == result
    assert scheduled == []
