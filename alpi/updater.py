"""Version-check + upgrade flow for alpi.

Two surfaces care about "is there a newer version on PyPI?":

- ``alpi setup`` shows a banner heading when an update exists.
- The TUI top bar shows a small badge.

Both read from a shared cache at ``~/.alpi/state/update_check.json``
that a fire-and-forget daemon thread refreshes once every TTL. The
cache is global (not per-profile) — there's one binary on disk
regardless of which profile invokes it.

Design choices the rest of the project leans on:

- **No blocking on launch.** The check runs in a daemon thread off
  the critical path; if PyPI is offline or slow, the user never
  feels it.
- **No automatic upgrade.** alpi never reaches PyPI without the
  user asking. The badge is informational; ``alpi update`` does
  the actual work.
- **Skippable in tests.** ``ALPI_SKIP_UPDATE_CHECK=1`` short-
  circuits the daemon — the autouse fixture in ``conftest.py``
  sets it so unit tests never reach the network.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import httpx

from alpi import __version__

_PYPI_URL_DEFAULT = "https://pypi.org/pypi/alpi-agent/json"
_CHANGELOG_URL = "https://github.com/satoshi-ltd/alpi/blob/main/CHANGELOG.md"
# 8 hours: three checks complete a full day (00/08/16 wall-clock
# slots if the user opens alpi at consistent hours). Long enough to
# stay quiet under shell-script automation; short enough that a
# release lands in the user's badge by the next morning.
_CACHE_TTL_SECONDS = 8 * 3600
_PYPI_TIMEOUT_SECONDS = 3.0
_PACKAGE_NAME = "alpi-agent"


def _cache_path() -> Path:
    """Where the JSON cache lives. Global to all profiles — the
    binary version is one and the same regardless of which profile
    invokes alpi. Lives under ``cache/`` (the conventional location
    for derived/refreshable data; ``tts`` and the telegram inbound
    queue use the same root)."""
    return Path.home() / ".alpi" / "cache" / "update_check.json"


def _pypi_url() -> str:
    """Endpoint used to read the latest version. ``ALPI_UPDATE_INDEX``
    overrides for TestPyPI rehearsals (see docs/RELEASE.md)."""
    return os.environ.get("ALPI_UPDATE_INDEX") or _PYPI_URL_DEFAULT


def _utcnow_iso() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_iso(stamp: str) -> _dt.datetime | None:
    try:
        d = _dt.datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ")
    except (ValueError, TypeError):
        return None
    return d.replace(tzinfo=_dt.timezone.utc)


def _load_cache() -> dict | None:
    """Read the cache. Defensive — corrupt JSON or missing fields
    return ``None`` so the caller treats it as stale and refetches."""
    p = _cache_path()
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict):
        return None
    if not data.get("latest_version") or not data.get("checked_at"):
        return None
    return data


def _save_cache(latest_version: str, current_version: str) -> None:
    p = _cache_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "latest_version": latest_version,
        "current_version": current_version,
        "checked_at": _utcnow_iso(),
    }
    p.write_text(json.dumps(payload, separators=(",", ":")))


def _is_cache_fresh(cache: dict) -> bool:
    seen = _parse_iso(str(cache.get("checked_at") or ""))
    if seen is None:
        return False
    elapsed = (_dt.datetime.now(tz=_dt.timezone.utc) - seen).total_seconds()
    return elapsed < _CACHE_TTL_SECONDS


def _fetch_pypi_version() -> str | None:
    """Hit PyPI's JSON API. ~100–500 ms; 3 s hard timeout. Returns
    ``None`` on any failure (offline, 5xx, malformed payload, etc.)
    so the daemon path stays silent."""
    try:
        with httpx.Client(timeout=_PYPI_TIMEOUT_SECONDS) as client:
            r = client.get(_pypi_url())
            r.raise_for_status()
            data = r.json() or {}
    except Exception:  # noqa: BLE001 — silence any network/parse error
        return None
    info = data.get("info") or {}
    version = info.get("version")
    if not isinstance(version, str) or not version.strip():
        return None
    return version.strip()


def _is_newer(latest: str, current: str) -> bool:
    """Robust version comparison. Falls back to string equality if
    parsing fails (then ``False`` — better to under-report updates
    than to badge spuriously)."""
    try:
        from packaging.version import Version
        return Version(latest) > Version(current)
    except Exception:  # noqa: BLE001
        return False


def refresh_cache_if_stale() -> None:
    """Daemon entry point. Reads the cache, returns immediately if
    fresh, otherwise fetches PyPI and rewrites the cache. Silent on
    every kind of failure — this runs off the critical path."""
    cache = _load_cache()
    if cache is not None and _is_cache_fresh(cache):
        return
    latest = _fetch_pypi_version()
    if latest is None:
        return
    _save_cache(latest, __version__)


def trigger_background_check_if_enabled() -> None:
    """Hook called from ``alpi/cli.py::main`` on every invocation.
    Spawns a daemon thread that updates the cache if stale; returns
    in <10 ms regardless of network state."""
    if os.environ.get("ALPI_SKIP_UPDATE_CHECK"):
        return
    try:
        threading.Thread(
            target=refresh_cache_if_stale, daemon=True,
            name="alpi-update-check",
        ).start()
    except RuntimeError:
        # Some embedded environments (e.g. frozen interpreters) reject
        # thread creation — silently skip; not worth crashing for.
        pass


def available_update() -> str | None:
    """Return the latest PyPI version when it is newer than the
    currently-running ``__version__``, else ``None``. Reads the cache
    only — never touches the network. Safe to call in hot paths
    (every menu render, every TUI mount)."""
    cache = _load_cache()
    if cache is None:
        return None
    latest = str(cache.get("latest_version") or "")
    if not latest:
        return None
    if _is_newer(latest, __version__):
        return latest
    return None


# ── upgrade flow ────────────────────────────────────────────────────


def _detect_installer() -> str:
    """Identify how alpi was installed. Returns:

    - ``"uv"``    — via ``uv tool install alpi-agent``
    - ``"pipx"``  — via ``pipx install alpi-agent``
    - ``"dev"``   — neither; user is on an editable / source install
    """
    uv = shutil.which("uv")
    if uv:
        try:
            out = subprocess.run(
                [uv, "tool", "list"], capture_output=True, text=True,
                timeout=10, check=False,
            )
            if out.returncode == 0 and _PACKAGE_NAME in (out.stdout or ""):
                return "uv"
        except (subprocess.TimeoutExpired, OSError):
            pass
    pipx = shutil.which("pipx")
    if pipx:
        try:
            out = subprocess.run(
                [pipx, "list", "--short"], capture_output=True, text=True,
                timeout=10, check=False,
            )
            if out.returncode == 0 and _PACKAGE_NAME in (out.stdout or ""):
                return "pipx"
        except (subprocess.TimeoutExpired, OSError):
            pass
    return "dev"


def _upgrade_command(installer: str) -> list[str] | None:
    if installer == "uv":
        return ["uv", "tool", "upgrade", _PACKAGE_NAME]
    if installer == "pipx":
        return ["pipx", "upgrade", _PACKAGE_NAME]
    return None


def do_update(*, check_only: bool, yes: bool) -> int:
    """Drive the ``alpi update`` command. Returns a process exit
    code (0 success, non-zero on failure)."""
    from alpi import ui

    ui._console.print(f"[dim]checking PyPI for {_PACKAGE_NAME}…[/dim]")
    latest = _fetch_pypi_version()
    if latest is None:
        ui.fail(
            "could not reach PyPI (offline, or the index is down). "
            "Try again or run `uv tool upgrade alpi-agent` manually."
        )
        return 1

    # Refresh the cache while we're online — clears any stale badge
    # from earlier runs even if the version turns out unchanged.
    _save_cache(latest, __version__)

    if not _is_newer(latest, __version__):
        ui._console.print(
            f"[green]✓[/green] you're on the latest version "
            f"(v{__version__})."
        )
        return 0

    ui._console.print(
        f"[bold]update available:[/bold] v{__version__} → "
        f"[bold]v{latest}[/bold]"
    )
    ui._console.print(f"[dim]changelog: {_CHANGELOG_URL}[/dim]")

    if check_only:
        ui._console.print(
            "\n[dim]run `alpi update` (without --check) to install.[/dim]"
        )
        return 0

    installer = _detect_installer()
    if installer == "dev":
        ui._console.print(
            "\n[dim]you appear to be on a dev install (`uv sync` from "
            "a clone). To upgrade, `git pull` in your alpi checkout."
            "[/dim]"
        )
        return 0

    cmd = _upgrade_command(installer)
    if cmd is None:
        ui.fail(f"don't know how to upgrade installer {installer!r}")
        return 1

    if not yes:
        if not ui.confirm(
            f"\nrun `{' '.join(cmd)}` now?", default=True,
        ):
            ui._console.print("[dim]cancelled.[/dim]")
            return 0

    ui._console.print("")
    try:
        rc = subprocess.run(cmd, check=False).returncode
    except OSError as e:
        ui.fail(f"upgrade failed to start: {e}")
        return 1
    if rc != 0:
        ui.fail(f"`{' '.join(cmd)}` exited with status {rc}")
        return rc

    # Sanity-check that the new binary is wired up. Spawn a fresh
    # subprocess (the current process still imports the old code).
    alpi_bin = shutil.which("alpi")
    if alpi_bin is None:
        ui._console.print(
            "[yellow]upgrade ran, but `alpi` is no longer on PATH. "
            "Re-run uv's PATH hint or restart your shell.[/yellow]"
        )
        return 0
    try:
        out = subprocess.run(
            [alpi_bin, "--version"], capture_output=True, text=True,
            timeout=10, check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        ui.fail(f"could not run `alpi --version` after upgrade: {e}")
        return 1
    reported = (out.stdout or "").strip()
    if latest in reported:
        ui._console.print(f"[green]✓[/green] upgraded — {reported}")
    else:
        ui._console.print(
            f"[yellow]upgrade ran, but `alpi --version` reports "
            f"{reported!r} (expected v{latest}). You may need to "
            f"restart your shell.[/yellow]"
        )
    # Refresh the cache one more time — the new binary's __version__
    # matches PyPI now, so available_update() will return None and
    # the badge clears immediately.
    try:
        _save_cache(latest, latest)
    except OSError:
        pass
    return 0
