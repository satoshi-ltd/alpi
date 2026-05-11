"""Shared, locked playwright Chromium installer.

Both the daemon prefetch (``alpi.service._prefetch_assets``) and the
lazy fallback in ``alpi.tools.browser._launch_chromium`` call this. The
lock guarantees that ``playwright install chromium`` runs at most once
even if both fire at the same time.
"""

from __future__ import annotations

import subprocess
import sys
import threading


_install_lock = threading.Lock()
_installed = False


def ensure_chromium(timeout_s: int = 600) -> None:
    """Install Chromium if it isn't on disk yet. Idempotent."""
    global _installed
    if _installed:
        return
    with _install_lock:
        if _installed:
            return
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            check=False,
            capture_output=True,
            timeout=timeout_s,
        )
        _installed = True


def reset_for_testing() -> None:
    global _installed
    _installed = False
