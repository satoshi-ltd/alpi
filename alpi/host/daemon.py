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
    schedule_self_terminate()
    return {"ok": True, "respawn": True}


def schedule_self_terminate(delay: float = 0.2) -> None:
    # Deferred so the RPC returns before we SIGTERM ourselves; synchronous self-kill blocks the loop. Respawn: launchd/systemd on a host, restart policy in docker (daemon is PID 1).
    loop = asyncio.get_running_loop()
    loop.call_later(delay, _self_terminate)


def _self_terminate() -> None:
    try:
        os.kill(os.getpid(), signal.SIGTERM)
    except OSError:
        pass


__all__ = ["register", "schedule_self_terminate"]
