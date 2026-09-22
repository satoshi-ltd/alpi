# Deployment runtime (ALPI_PLATFORM). Only container runtime is docker:
# PID 1 is alpi/pid1.py's init with the daemon as its only child, bind 0.0.0.0, advertise via env.
# ALPI_PLATFORM also marks scheduled/cron runs — not runtimes.

from __future__ import annotations

import os


_DEPLOY_ENV = "ALPI_DEPLOY_RUNTIME"
_RUNTIMES = frozenset({"docker"})


def platform_id() -> str:
    # ALPI_PLATFORM is overloaded: a scheduled turn overwrites it with "cron", so a job inside
    # a container would otherwise read as a host install. The carried value is the runtime.
    carried = (os.environ.get(_DEPLOY_ENV) or "").strip().lower()
    return carried or (os.environ.get("ALPI_PLATFORM") or "").strip().lower()


def deploy_env() -> dict[str, str]:
    """Env a spawner must merge in when it overwrites ALPI_PLATFORM, so the runtime survives."""
    current = platform_id()
    return {_DEPLOY_ENV: current} if current in _RUNTIMES else {}


def is_docker() -> bool:
    return platform_id() == "docker"
