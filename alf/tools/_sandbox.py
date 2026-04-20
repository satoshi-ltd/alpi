"""OS-level isolation wrapper for subprocess commands."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Iterable


class SandboxUnavailable(RuntimeError):
    pass


_MACOS_PROFILE = """
(version 1)
(deny default)
(allow process-fork)
(allow process-exec*)
(allow signal)
(allow sysctl-read)
(allow mach-lookup)
(allow iokit-open)
(allow ipc-posix-shm)
(allow file-read*)
(deny file-read-data
    (subpath (param "HOME_SSH"))
    (subpath (param "HOME_AWS"))
    (subpath (param "HOME_GNUPG")))
(allow file-write*
    (subpath (param "WORKSPACE"))
    (subpath (param "ALF_HOME"))
    (subpath "/tmp")
    (subpath "/private/tmp")
    (subpath "/private/var/folders"))
%NETWORK%
""".strip()


def wrap_command(
    cmd: str,
    *,
    workspace: Path,
    alf_home: Path,
    allow_network: bool,
) -> list[str]:
    platform = sys.platform
    if platform == "darwin":
        return _wrap_macos(cmd, workspace, alf_home, allow_network)
    if platform.startswith("linux"):
        return _wrap_linux(cmd, workspace, alf_home, allow_network)
    raise SandboxUnavailable(
        f"No sandbox implementation for platform {platform!r}. "
        "Set tools.terminal.sandbox=false to run without OS isolation."
    )


def _wrap_macos(
    cmd: str,
    workspace: Path,
    alf_home: Path,
    allow_network: bool,
) -> list[str]:
    if shutil.which("sandbox-exec") is None:
        raise SandboxUnavailable(
            "sandbox-exec not found. macOS ships it at /usr/bin/sandbox-exec; "
            "either reinstall your system toolchain or set "
            "tools.terminal.sandbox=false."
        )
    home = os.path.expanduser("~")
    profile = _MACOS_PROFILE.replace(
        "%NETWORK%",
        "(allow network*)" if allow_network else "(deny network*)",
    )
    params = [
        f"-D WORKSPACE={workspace}",
        f"-D ALF_HOME={alf_home}",
        f"-D HOME_SSH={home}/.ssh",
        f"-D HOME_AWS={home}/.aws",
        f"-D HOME_GNUPG={home}/.gnupg",
    ]
    return [
        "sandbox-exec",
        *[part for p in params for part in p.split(" ", 1)],
        "-p", profile,
        "--",
        "/bin/sh", "-c", cmd,
    ]


def _wrap_linux(
    cmd: str,
    workspace: Path,
    alf_home: Path,
    allow_network: bool,
) -> list[str]:
    if shutil.which("bwrap") is None:
        raise SandboxUnavailable(
            "bubblewrap (bwrap) not found. Install it (apt install bubblewrap, "
            "dnf install bubblewrap, pacman -S bubblewrap) or set "
            "tools.terminal.sandbox=false."
        )
    args: list[str] = ["bwrap", "--die-with-parent"]
    args += ["--unshare-user", "--unshare-pid", "--unshare-uts", "--unshare-ipc"]
    if not allow_network:
        args += ["--unshare-net"]
    args += _ro_binds([
        "/usr", "/bin", "/sbin", "/lib", "/lib64", "/etc/alternatives",
        "/etc/ssl", "/etc/ca-certificates", "/etc/resolv.conf",
    ])
    args += ["--bind", str(workspace), str(workspace)]
    args += ["--bind", str(alf_home), str(alf_home)]
    args += ["--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp"]
    args += ["--chdir", str(workspace)]
    args += ["--", "/bin/sh", "-c", cmd]
    return args


def _ro_binds(paths: Iterable[str]) -> list[str]:
    out: list[str] = []
    for p in paths:
        if os.path.exists(p):
            out += ["--ro-bind", p, p]
    return out
