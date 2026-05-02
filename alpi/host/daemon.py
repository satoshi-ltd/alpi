from __future__ import annotations

import asyncio
import os
import signal
from typing import Any

from alpi.host import server as host_server


def register(server: host_server.Server) -> None:
    server.register("host.daemon.restart", _daemon_restart)


async def _daemon_restart(
    _params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    # Schedule the SIGTERM AFTER returning so the client gets a clean
    # response — launchd / systemd ``KeepAlive`` respawns the unit.
    loop = asyncio.get_running_loop()
    loop.call_later(0.2, _self_terminate)
    return {"ok": True, "respawn": True}


def _self_terminate() -> None:
    try:
        os.kill(os.getpid(), signal.SIGTERM)
    except OSError:
        pass


__all__ = ["register"]
