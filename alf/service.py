"""OS-level service install/uninstall for ``gateway`` and ``schedule``."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


class ServiceError(Exception):
    """Raised for any install/uninstall failure that the CLI should surface."""



def install(name: str, home: Path, profile: str = "default") -> str:
    """Install and auto-start the named daemon. Returns the backend used."""
    _validate_name(name)
    backend = _detect_backend()
    alf_bin = _locate_alf()

    if backend == "launchd":
        _launchd_install(name, home, profile, alf_bin)
        return "launchd"
    if backend == "systemd":
        _systemd_install(name, home, profile, alf_bin)
        return "systemd"
    raise ServiceError(f"unsupported platform: {platform.system()}")


def uninstall(name: str, home: Path, profile: str = "default") -> str:
    """Stop + unregister the named daemon. Returns the backend used."""
    _validate_name(name)
    backend = _detect_backend()
    if backend == "launchd":
        _launchd_uninstall(name, profile)
        return "launchd"
    if backend == "systemd":
        _systemd_uninstall(name, profile)
        return "systemd"
    raise ServiceError(f"unsupported platform: {platform.system()}")


def installed(name: str, profile: str = "default") -> str | None:
    """Return the backend name if a service unit exists on disk, else None."""
    _validate_name(name)
    backend = _detect_backend()
    if backend == "launchd" and _launchd_plist_path(name, profile).exists():
        return "launchd"
    if backend == "systemd" and _systemd_unit_path(name, profile).exists():
        return "systemd"
    return None


# Backend detection + common helpers


def _detect_backend() -> str | None:
    system = platform.system()
    if system == "Darwin":
        return "launchd"
    if system == "Linux":
        return "systemd"
    return None


def _validate_name(name: str) -> None:
    if name not in {"gateway", "schedule"}:
        raise ServiceError(f"unknown daemon name: {name!r}")


def _locate_alf() -> str:
    path = shutil.which("alf")
    if not path:
        # Fallback to ``<python> -m alf`` — works from a venv/isolated
        # install even if ``alf`` isn't on the global PATH.
        return f"{sys.executable} -m alf"
    return path


def service_label(name: str, profile: str) -> str:
    """Public label used for messages in the CLI and in status output."""
    if _detect_backend() == "launchd":
        return f"com.alf.{name}.{profile}"
    return f"alf-{name}-{profile}"


# launchd (macOS)


_PLIST_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>{label}</string>
  <key>ProgramArguments</key>
  <array>
{program_args}
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>ALF_HOME</key>
    <string>{home}</string>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
  </dict>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>{log_path}</string>
  <key>StandardErrorPath</key>
  <string>{log_path}</string>
</dict>
</plist>
"""


def _launchd_plist_path(name: str, profile: str) -> Path:
    return (
        Path.home() / "Library" / "LaunchAgents"
        / f"com.alf.{name}.{profile}.plist"
    )


def _launchd_install(name: str, home: Path, profile: str, alf_bin: str) -> None:
    label = f"com.alf.{name}.{profile}"
    plist = _launchd_plist_path(name, profile)
    plist.parent.mkdir(parents=True, exist_ok=True)

    log_path = _log_path(name, home)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    program_args = _program_args_xml(alf_bin, name)
    plist.write_text(_PLIST_TEMPLATE.format(
        label=label,
        program_args=program_args,
        home=str(home),
        log_path=str(log_path),
    ))

    uid = os.getuid()
    # Bootout first in case a previous (stale) version of the service is
    # still loaded from an earlier install — otherwise bootstrap errors.
    _run(["launchctl", "bootout", f"gui/{uid}", str(plist)], check=False)
    result = _run(
        ["launchctl", "bootstrap", f"gui/{uid}", str(plist)],
        check=False,
    )
    if result.returncode != 0:
        raise ServiceError(
            f"launchctl bootstrap failed (rc={result.returncode}): "
            f"{result.stderr or result.stdout}".strip()
        )


def _launchd_uninstall(name: str, profile: str) -> None:
    plist = _launchd_plist_path(name, profile)
    if not plist.exists():
        raise ServiceError(f"{name} is not installed (no plist at {plist})")
    uid = os.getuid()
    _run(["launchctl", "bootout", f"gui/{uid}", str(plist)], check=False)
    plist.unlink(missing_ok=True)


# systemd --user (Linux)


_UNIT_TEMPLATE = """[Unit]
Description=alf {name} daemon ({profile})
After=network-online.target

[Service]
Type=simple
Environment=ALF_HOME={home}
ExecStart={exec_start}
Restart=on-failure
RestartSec=5
StandardOutput=append:{log_path}
StandardError=append:{log_path}

[Install]
WantedBy=default.target
"""


def _systemd_unit_path(name: str, profile: str) -> Path:
    return (
        Path.home() / ".config" / "systemd" / "user"
        / f"alf-{name}-{profile}.service"
    )


def _systemd_install(name: str, home: Path, profile: str, alf_bin: str) -> None:
    unit = _systemd_unit_path(name, profile)
    unit.parent.mkdir(parents=True, exist_ok=True)
    log_path = _log_path(name, home)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    unit.write_text(_UNIT_TEMPLATE.format(
        name=name,
        profile=profile,
        home=str(home),
        exec_start=f"{alf_bin} {name} start",
        log_path=str(log_path),
    ))

    unit_id = f"alf-{name}-{profile}.service"
    # Tell systemd to re-read units, then enable+start.
    res = _run(["systemctl", "--user", "daemon-reload"], check=False)
    if res.returncode != 0:
        raise ServiceError(
            f"systemctl daemon-reload failed (rc={res.returncode}): "
            f"{res.stderr or res.stdout}".strip()
            + _systemd_hint(res)
        )
    res = _run(["systemctl", "--user", "enable", "--now", unit_id], check=False)
    if res.returncode != 0:
        raise ServiceError(
            f"systemctl enable --now failed (rc={res.returncode}): "
            f"{res.stderr or res.stdout}".strip()
            + _systemd_hint(res)
        )


def _systemd_uninstall(name: str, profile: str) -> None:
    unit = _systemd_unit_path(name, profile)
    if not unit.exists():
        raise ServiceError(f"{name} is not installed (no unit at {unit})")
    unit_id = f"alf-{name}-{profile}.service"
    _run(["systemctl", "--user", "disable", "--now", unit_id], check=False)
    unit.unlink(missing_ok=True)
    _run(["systemctl", "--user", "daemon-reload"], check=False)


def _systemd_hint(result: subprocess.CompletedProcess) -> str:
    combined = (result.stderr or "") + (result.stdout or "")
    if "Failed to connect to bus" in combined or "No such file" in combined:
        return (
            "\nNote: `systemd --user` must be available. On WSL without "
            "`systemd=true` in /etc/wsl.conf, or in minimal containers, "
            "run `alf schedule start` in a tmux/screen session instead."
        )
    return ""



def _log_path(name: str, home: Path) -> Path:
    if name == "gateway":
        return home / "gateway" / "logs" / "gateway.log"
    return home / "schedule" / "logs" / "scheduler.log"


def _program_args_xml(alf_bin: str, name: str) -> str:
    # alf_bin may be ``/path/to/alf`` or ``<python> -m alf`` — split it.
    parts = alf_bin.split() + [name, "start"]
    return "\n".join(f"    <string>{p}</string>" for p in parts)


def _run(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, check=check)
