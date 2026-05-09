from __future__ import annotations

import ipaddress
import os
import shutil
import subprocess
import socket
from pathlib import Path

from alpi.host.tailscale import detect_tailscale_ip
from alpi.host.server import DEFAULT_TCP_PORT


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


# What did detection actually see? Used to surface a diagnostic error
# instead of a bare "no advertised host". Never raises.
def diagnose_bind_ip() -> dict[str, str | None]:
    udp_ip = None
    udp_err = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 53))
            udp_ip = s.getsockname()[0]
        finally:
            s.close()
    except OSError as exc:
        udp_err = str(exc)
    return {
        "tailscale": detect_tailscale_ip(),
        "udp_probe_ip": udp_ip,
        "udp_probe_error": udp_err,
        "udp_probe_is_private": str(_is_private_lan(udp_ip)) if udp_ip else None,
        "ifconfig_lan": _detect_lan_ip_via_ifconfig(),
    }


def resolve_host_endpoint(home: Path) -> tuple[str, str] | None:
    configured = _configured_host(home)
    if configured:
        return (configured, "configured")
    if os.environ.get("ALPI_PLATFORM") == "umbrel":
        hinted = _umbrel_host_hint()
        if hinted:
            return (hinted, "umbrel")
        return None
    return detect_bind_ip()


def resolve_host_tcp_bind(home: Path) -> tuple[str, int] | None:
    port = resolve_host_tcp_port(home)
    if os.environ.get("ALPI_PLATFORM") == "umbrel":
        return ("0.0.0.0", port)
    detected = detect_bind_ip()
    if detected is None:
        return None
    ip, _scope = detected
    return (ip, port)


def resolve_host_tcp_port(home: Path) -> int:
    from alpi import config as cfg_mod

    cfg = cfg_mod.load(home)
    return int((cfg.host or {}).get("tcp_port") or DEFAULT_TCP_PORT)


def resolve_host_pairing_name(home: Path) -> str:
    from alpi import config as cfg_mod

    cfg = cfg_mod.load(home)
    name = str((cfg.host or {}).get("device_name") or "").strip()
    if name:
        return name
    env_name = str(os.environ.get("DEVICE_HOSTNAME") or "").strip()
    if env_name:
        return env_name
    return socket.gethostname() or "Alpi"


def _configured_host(home: Path) -> str | None:
    from alpi import config as cfg_mod

    cfg = cfg_mod.load(home)
    host = str((cfg.host or {}).get("tcp_host") or "").strip()
    return host or None


def _umbrel_host_hint() -> str | None:
    for key in ("ALPI_HOST_ADVERTISE_HOST", "DEVICE_DOMAIN_NAME", "DEVICE_HOSTNAME"):
        value = str(os.environ.get(key) or "").strip()
        if value:
            return value
    return None


def _detect_lan_ip() -> str | None:
    udp = _detect_lan_ip_via_udp()
    if udp:
        return udp
    return _detect_lan_ip_via_ifconfig()


# Connect a UDP socket to a public IP — no packets sent, but the kernel
# picks the outbound interface so getsockname returns its IP. Works on
# any platform, no shelling out, captures the *active* default route.
def _detect_lan_ip_via_udp() -> str | None:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 53))
        addr = s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()
    return addr if _is_private_lan(addr) else None


def _detect_lan_ip_via_ifconfig() -> str | None:
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


__all__ = [
    "detect_bind_ip",
    "resolve_host_endpoint",
    "resolve_host_pairing_name",
    "resolve_host_tcp_bind",
    "resolve_host_tcp_port",
]
