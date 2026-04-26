"""Version-check + upgrade flow for ``alpi``.

Cache at ``~/.alpi/cache/update_check.json`` (global, not per-profile)
is refreshed by a daemon thread; ``alpi doctor`` and the TUI top bar
read it. ``ALPI_SKIP_UPDATE_CHECK=1`` disables the daemon (set by
the test autouse fixture)."""

from __future__ import annotations

import datetime as _dt
import json
import os
import shutil
import subprocess
import threading
from pathlib import Path

import httpx

from alpi import __version__

_PYPI_URL_DEFAULT = "https://pypi.org/pypi/alpi-agent/json"
_CHANGELOG_URL = "https://github.com/satoshi-ltd/alpi/blob/main/CHANGELOG.md"
# 8 h: a release lands in the badge by next morning under typical use.
_CACHE_TTL_SECONDS = 8 * 3600
_PYPI_TIMEOUT_SECONDS = 3.0
_PACKAGE_NAME = "alpi-agent"


def _cache_path() -> Path:
    return Path.home() / ".alpi" / "cache" / "update_check.json"


def _pypi_url() -> str:
    # ``ALPI_UPDATE_INDEX`` overrides for TestPyPI rehearsals.
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
    # Defensive — corrupt JSON or missing fields → ``None`` (refetch).
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
    # Returns ``None`` on any failure — the daemon path stays silent.
    try:
        with httpx.Client(timeout=_PYPI_TIMEOUT_SECONDS) as client:
            r = client.get(_pypi_url())
            r.raise_for_status()
            data = r.json() or {}
    except Exception:  # noqa: BLE001
        return None
    info = data.get("info") or {}
    version = info.get("version")
    if not isinstance(version, str) or not version.strip():
        return None
    return version.strip()


def _is_newer(latest: str, current: str) -> bool:
    # Falls back to ``False`` on parse error — under-report rather than
    # badge spuriously.
    try:
        from packaging.version import Version
        return Version(latest) > Version(current)
    except Exception:  # noqa: BLE001
        return False


def refresh_cache_if_stale() -> None:
    cache = _load_cache()
    if cache is not None and _is_cache_fresh(cache):
        return
    latest = _fetch_pypi_version()
    if latest is None:
        return
    _save_cache(latest, __version__)


def trigger_background_check_if_enabled() -> None:
    if os.environ.get("ALPI_SKIP_UPDATE_CHECK"):
        return
    try:
        threading.Thread(
            target=refresh_cache_if_stale, daemon=True,
            name="alpi-update-check",
        ).start()
    except RuntimeError:
        # Frozen interpreters reject thread creation — silently skip.
        pass


def available_update() -> str | None:
    """Latest PyPI version when newer than ``__version__``, else
    ``None``. Reads cache only — safe in hot paths."""
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
    """``"uv"`` | ``"pipx"`` | ``"dev"`` (editable / source install)."""
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
    from alpi import ui

    ui._console.print(f"[dim]checking PyPI for {_PACKAGE_NAME}…[/dim]")
    latest = _fetch_pypi_version()
    if latest is None:
        ui.fail(
            "could not reach PyPI (offline, or the index is down). "
            "Try again or run `uv tool upgrade alpi-agent` manually."
        )
        return 1

    # Refresh cache while online — clears any stale badge.
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

    # Spawn fresh subprocess — current process still imports old code.
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
    # Cache the upgraded version so the badge clears immediately.
    try:
        _save_cache(latest, latest)
    except OSError:
        pass
    return 0
