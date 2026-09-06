# Deployment runtime (ALPI_PLATFORM). Only container runtime is docker:
# PID 1 is alpi/pid1.py's init with the daemon as its only child, bind 0.0.0.0, advertise via env.
# ALPI_PLATFORM also marks scheduled/cron runs — not runtimes.

from __future__ import annotations

import os


def platform_id() -> str:
    return (os.environ.get("ALPI_PLATFORM") or "").strip().lower()


def is_docker() -> bool:
    return platform_id() == "docker"
