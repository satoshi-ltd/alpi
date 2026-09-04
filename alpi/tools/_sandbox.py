"""OS-level isolation wrapper for subprocess commands."""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Iterable


class SandboxUnavailable(RuntimeError):
    pass


def network_allowed() -> bool:
    import yaml
    from alpi.home import get_home
    try:
        cfg_path = get_home() / "config.yaml"
        if not cfg_path.exists():
            return True
        data = yaml.safe_load(cfg_path.read_text()) or {}
        term = ((data.get("tools") or {}).get("terminal") or {})
    except Exception:  # noqa: BLE001
        return True
    if not term.get("sandbox"):
        return True
    return bool(term.get("allow_network"))


def require_network(tool_name: str):
    if network_allowed():
        return None
    from alpi.tools.base import ToolResult
    return ToolResult(
        ok=False, output="",
        error=(
            f"{tool_name} needs network but sandbox is locked "
            f"(tools.terminal.allow_network=false). Unlock via "
            f"`alpi setup → Sandbox` or disable sandbox."
        ),
    )


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
    (subpath (param "HOME_GNUPG"))
    (regex #"/\\.alpi/(profiles/[^/]+/)?\\.env$")
    (regex #"/\\.alpi/.*/secrets/"))
(allow file-write*
%PERSISTENT_WRITES%
%TEMP_WRITES%
    ; Character devices that well-behaved CLI tools reopen for r+w
    ; (git writes progress lines to /dev/null when no tty is attached,
    ; node/python seed from /dev/urandom, anything interactive probes
    ; /dev/tty). Exposing these is strictly less dangerous than
    ; denying them — they're not persistent storage.
    (literal "/dev/null")
    (literal "/dev/zero")
    (literal "/dev/random")
    (literal "/dev/urandom")
    (literal "/dev/tty")
    (literal "/dev/stdin")
    (literal "/dev/stdout")
    (literal "/dev/stderr"))
(deny file-write*
    (regex #"/\\.alpi/(profiles/[^/]+/)?\\.env$")
    (regex #"/\\.alpi/(profiles/[^/]+/)?config\\.yaml$")
    (regex #"/\\.alpi/.*/secrets/"))
%NETWORK%
""".strip()


def wrap_command(
    cmd: str,
    *,
    workspace: Path,
    alpi_home: Path,
    allow_network: bool,
    write_rules: tuple[tuple[str, Path], ...] | None = None,
) -> list[str]:
    platform = sys.platform
    if platform == "darwin":
        return _wrap_macos(
            cmd, workspace, alpi_home, allow_network, write_rules,
        )
    if platform.startswith("linux"):
        return _wrap_linux(
            cmd, workspace, alpi_home, allow_network, write_rules,
        )
    raise SandboxUnavailable(
        f"No sandbox implementation for platform {platform!r}. "
        "Set tools.terminal.sandbox=false to run without OS isolation."
    )


def _wrap_macos(
    cmd: str,
    workspace: Path,
    alpi_home: Path,
    allow_network: bool,
    write_rules: tuple[tuple[str, Path], ...] | None,
) -> list[str]:
    if shutil.which("sandbox-exec") is None:
        raise SandboxUnavailable(
            "sandbox-exec not found. macOS ships it at /usr/bin/sandbox-exec; "
            "either reinstall your system toolchain or set "
            "tools.terminal.sandbox=false."
        )
    home = os.path.expanduser("~")
    effective_rules = write_rules
    if effective_rules is None:
        effective_rules = (("subpath", workspace), ("subpath", alpi_home))
        temp_writes = """    (subpath "/tmp")
    (subpath "/private/tmp")
    (subpath "/private/var/folders")"""
        terminal_tmp = None
    else:
        terminal_tmp = scoped_temp_dir()
        temp_writes = '    (subpath (param "TERMINAL_TMP"))'
    persistent = "\n".join(
        f'    ({kind} (param "WRITE_{index}"))'
        for index, (kind, _) in enumerate(effective_rules)
    )
    profile = _MACOS_PROFILE.replace(
        "%PERSISTENT_WRITES%", persistent,
    ).replace(
        "%TEMP_WRITES%", temp_writes,
    ).replace(
        "%NETWORK%",
        "(allow network*)" if allow_network else "(deny network*)",
    )
    params = [
        f"-D HOME_SSH={home}/.ssh",
        f"-D HOME_AWS={home}/.aws",
        f"-D HOME_GNUPG={home}/.gnupg",
        *(
            f"-D WRITE_{index}={path}"
            for index, (_, path) in enumerate(effective_rules)
        ),
        *([f"-D TERMINAL_TMP={terminal_tmp}"] if terminal_tmp is not None else []),
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
    alpi_home: Path,
    allow_network: bool,
    write_rules: tuple[tuple[str, Path], ...] | None,
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
    args += ["--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp"]
    if write_rules is None:
        args += _linux_dir_mounts([workspace, alpi_home])
        args += ["--bind", str(workspace), str(workspace)]
        args += ["--bind", str(alpi_home), str(alpi_home)]
    else:
        writable = [path for _, path in write_rules]
        args += _linux_dir_mounts([workspace, alpi_home, *writable])
        args += ["--ro-bind", str(workspace), str(workspace)]
        args += ["--ro-bind", str(alpi_home), str(alpi_home)]
        for _, path in write_rules:
            args += ["--bind", str(path), str(path)]
    args += ["--remount-ro", "/"]
    args += ["--chdir", str(workspace)]
    args += ["--", "/bin/sh", "-c", cmd]
    return args


def phase_write_rules(
    workspace: Path,
    raw_scope: str | None = None,
) -> tuple[tuple[str, Path], ...] | None:
    """Translate an active phase scope to exact OS-sandbox write rules."""
    raw = os.environ.get("ALPI_WORKGROUP_WRITE_SCOPE") if raw_scope is None else raw_scope
    if raw is None:
        return None
    try:
        scope = json.loads(raw)
        root_value = str(scope.get("root") or "")
        patterns = scope.get("paths")
    except (AttributeError, TypeError, json.JSONDecodeError) as exc:
        raise SandboxUnavailable("active phase write scope is invalid; terminal refused") from exc
    if not isinstance(patterns, list):
        raise SandboxUnavailable("active phase write scope has no path list; terminal refused")
    workspace = workspace.resolve()
    root = (workspace / root_value).resolve()
    try:
        root.relative_to(workspace)
    except ValueError as exc:
        raise SandboxUnavailable("active phase root escapes the workspace; terminal refused") from exc
    if not root.is_dir():
        raise SandboxUnavailable("active phase root is unavailable; terminal refused")

    rules: list[tuple[str, Path]] = []
    for value in patterns:
        if not isinstance(value, str) or not value:
            raise SandboxUnavailable("active phase contains an invalid writable path; terminal refused")
        pattern = value
        kind = "literal"
        relative = pattern
        if pattern == "**":
            kind, relative = "subpath", ""
        elif pattern.endswith("/**") and not any(c in pattern[:-3] for c in "*?["):
            kind, relative = "subpath", pattern[:-3]
        elif any(c in pattern for c in "*?["):
            raise SandboxUnavailable(
                f"active phase path pattern cannot be sandboxed exactly: {pattern!r}; terminal refused"
            )
        path = (root / relative).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise SandboxUnavailable(
                f"active phase path escapes its root: {pattern!r}; terminal refused"
            ) from exc
        if kind == "subpath" and not path.is_dir():
            try:
                path.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                raise SandboxUnavailable(
                    f"active phase writable directory is unavailable: {pattern!r}; terminal refused"
                ) from exc
        if kind == "literal" and not path.is_file():
            raise SandboxUnavailable(
                f"active phase writable file is unavailable: {pattern!r}; terminal refused"
            )
        rule = (kind, path)
        if rule not in rules:
            rules.append(rule)
    return tuple(rules)


def scoped_temp_dir() -> Path:
    path = Path(tempfile.gettempdir()).resolve() / f"alpi-terminal-{os.getuid()}"
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    return path


def _linux_dir_mounts(paths: Iterable[Path]) -> list[str]:
    mountpoints = {
        "/tmp", "/proc", "/dev",
        "/usr", "/bin", "/sbin", "/lib", "/lib64", "/etc",
    }
    out: list[str] = []
    seen: set[str] = set()
    for path in paths:
        cur = Path("/")
        for part in path.parts[1:]:
            cur /= part
            s = str(cur)
            if s in mountpoints or s in seen:
                continue
            out += ["--dir", s]
            seen.add(s)
    return out


def _ro_binds(paths: Iterable[str]) -> list[str]:
    out: list[str] = []
    for p in paths:
        if os.path.exists(p):
            out += ["--ro-bind", p, p]
    return out
