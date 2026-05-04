from __future__ import annotations

import ipaddress
import shutil
import subprocess

from alpi.host.tailscale import detect_tailscale_ip


_PRIVATE_RANGES = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
)


# Tailscale first, LAN fallback. Never 0.0.0.0/public — pairing token would leak in plaintext.
def detect_bind_ip() -> tuple[str, str] | None:
    ts = detect_tailscale_ip()
    if ts:
        return (ts, "tailscale")
    lan = _detect_lan_ip()
    if lan:
        return (lan, "lan")
    return None


def _detect_lan_ip() -> str | None:
    binary = shutil.which("ifconfig") or "/sbin/ifconfig"
    try:
        out = subprocess.run(
            [binary], check=False, capture_output=True, text=True, timeout=2.0,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    for line in out.stdout.splitlines():
        line = line.strip()
        if not line.startswith("inet "):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        candidate = parts[1]
        if _is_private_lan(candidate):
            return candidate
    return None


def _is_private_lan(addr: str) -> bool:
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return False
    if ip.is_loopback:
        return False
    return any(ip in net for net in _PRIVATE_RANGES)


__all__ = ["detect_bind_ip"]
