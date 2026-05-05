from __future__ import annotations

import ipaddress
import os
import shutil
import subprocess

# Tailscale CGNAT range.
TAILSCALE_RANGE = ipaddress.ip_network("100.64.0.0/10")

# macOS App Store / DMG installs don't put `tailscale` on $PATH; binary lives in the .app bundle.
_FALLBACK_BINARIES = (
    "/Applications/Tailscale.app/Contents/MacOS/Tailscale",
    "/opt/homebrew/bin/tailscale",
    "/usr/local/bin/tailscale",
    "/usr/bin/tailscale",
)


def _resolve_binary() -> str | None:
    found = shutil.which("tailscale")
    if found:
        return found
    for path in _FALLBACK_BINARIES:
        if os.access(path, os.X_OK):
            return path
    return None


def detect_tailscale_ip() -> str | None:
    return _from_cli() or _from_ifconfig()


def _from_cli() -> str | None:
    binary = _resolve_binary()
    if binary is None:
        return None
    try:
        out = subprocess.run(
            [binary, "ip", "-4"],
            check=False,
            capture_output=True,
            text=True,
            timeout=2.0,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    for line in out.stdout.splitlines():
        candidate = line.strip()
        if is_tailscale_ip(candidate):
            return candidate
    return None


def _from_ifconfig() -> str | None:
    # Fallback for the launchd context where Tailscale CLI refuses without HOME/keychain.
    binary = shutil.which("ifconfig") or "/sbin/ifconfig"
    try:
        out = subprocess.run(
            [binary],
            check=False,
            capture_output=True,
            text=True,
            timeout=2.0,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    for line in out.stdout.splitlines():
        line = line.strip()
        if not line.startswith("inet "):
            continue
        # Lines look like:  ``inet 100.114.140.25 --> 100.114.140.25 netmask 0xffffffff``
        parts = line.split()
        if len(parts) < 2:
            continue
        candidate = parts[1]
        if is_tailscale_ip(candidate):
            return candidate
    return None


def is_tailscale_ip(addr: str) -> bool:
    if not addr:
        return False
    try:
        return ipaddress.ip_address(addr) in TAILSCALE_RANGE
    except ValueError:
        return False


__all__ = ["detect_tailscale_ip", "is_tailscale_ip", "TAILSCALE_RANGE"]
