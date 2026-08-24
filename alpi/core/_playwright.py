"""Shared, locked playwright Chromium installer.

Both the daemon prefetch (``alpi.service._prefetch_assets``) and the
lazy fallback in ``alpi.tools.browser._launch_chromium`` call this. The
lock guarantees that ``playwright install chromium`` runs at most once
even if both fire at the same time.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

log = logging.getLogger(__name__)

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
        started = time.monotonic()
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "--only-shell", "chromium"],
            check=False,
            capture_output=True,
            timeout=timeout_s,
        )
        elapsed = time.monotonic() - started
        if result.returncode != 0:
            tail = (result.stderr or b"")[-400:].decode("utf-8", "replace").strip()
            log.warning(
                "playwright install chromium failed (rc=%d, %.1fs): %s",
                result.returncode, elapsed, tail,
            )
            return
        log.info("chromium ensured in %.1fs", elapsed)
        _prune_stale_chromium()
        _installed = True


def _browsers_cache_dir() -> Path:
    env = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if env:
        return Path(env)
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "ms-playwright"
    return Path(os.environ.get("XDG_CACHE_HOME") or (Path.home() / ".cache")) / "ms-playwright"


def _wanted_chromium_dirs() -> set[str]:
    import playwright

    spec = Path(playwright.__file__).parent / "driver" / "package" / "browsers.json"
    data = json.loads(spec.read_text(encoding="utf-8"))
    out: set[str] = set()
    for browser in data.get("browsers", []):
        # Only the shell: `chromium.launch(headless=True)` runs chrome-headless-shell, so a full chromium build on disk is dead weight and must stay prunable.
        if str(browser.get("name") or "") != "chromium-headless-shell":
            continue
        revision = str(browser.get("revision") or "")
        if revision:
            out.add(f"chromium_headless_shell-{revision}")
    return out


# Each playwright bump downloads a fresh ~520MB chromium build and orphans the previous one — unbounded cache growth (observed: >1GB of stacked revisions). Only chromium* entries are touched: firefox/webkit may belong to other tools on the machine.
def _prune_stale_chromium(cache_dir: Path | None = None) -> int:
    try:
        wanted = _wanted_chromium_dirs()
    except Exception:  # noqa: BLE001
        return 0
    if not wanted:
        return 0
    root = cache_dir or _browsers_cache_dir()
    if not root.is_dir():
        return 0
    # Refuse to prune unless the wanted build is actually on disk — a failed install must never delete the last working browser.
    if not any((root / w).is_dir() for w in wanted):
        return 0
    removed = 0
    for entry in root.glob("chromium*"):
        if not entry.is_dir() or entry.name in wanted:
            continue
        try:
            shutil.rmtree(entry)
            removed += 1
            log.info("pruned stale browser build %s", entry.name)
        except OSError:
            continue
    return removed


def reset_for_testing() -> None:
    global _installed
    _installed = False
