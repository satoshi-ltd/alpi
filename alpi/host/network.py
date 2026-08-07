from __future__ import annotations

import functools
import ipaddress
import os
import shutil
import subprocess
import socket
from typing import Any
from urllib.parse import urlsplit
from pathlib import Path

from alpi import runtime
from alpi.host.tailscale import detect_tailscale_ip, is_tailscale_ip
from alpi.host.server import DEFAULT_TCP_PORT


_PRIVATE_RANGES = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
)


# Tailscale first, LAN fallback. Never 0.0.0.0/public — pairing token would leak in plaintext.
# Cached per process: re-running per profile blocks the loop (Tailscale CLI hits its 2s timeout under launchd).
@functools.lru_cache(maxsize=1)
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
    if runtime.is_docker():
        # Container can't see host interfaces — endpoint comes from env.
        hinted = _advertise_host_hint()
        if hinted:
            return (hinted, runtime.platform_id())
        return None
    return detect_bind_ip()


def resolve_bind_host(
    configured: str | None, *, is_docker: bool, allow_public: bool,
) -> str | None:
    # Advertised network.host -> a local-safe bind (not used verbatim: a
    # hostname / public IP isn't a local interface). docker -> 0.0.0.0;
    # empty -> detected IP else None; private/overlay IP -> itself; hostname
    # -> 0.0.0.0; public IP -> 0.0.0.0 iff allow_public else None.
    if is_docker:
        return "0.0.0.0"
    if not configured:
        detected = detect_bind_ip()
        return detected[0] if detected else None
    try:
        ip = ipaddress.ip_address(configured)
    except ValueError:
        return "0.0.0.0"
    if ip.is_loopback or ip.is_unspecified:
        return None
    if is_tailscale_ip(configured) or any(ip in net for net in _PRIVATE_RANGES):
        return configured
    return "0.0.0.0" if allow_public else None


def resolve_host_tcp_bind(home: Path) -> tuple[str, int] | None:
    port = resolve_host_tcp_port(home)
    bind = resolve_bind_host(
        _configured_host(home),
        is_docker=runtime.is_docker(),
        allow_public=host_allow_public_bind(home),
    )
    return (bind, port) if bind is not None else None


def host_allow_public_bind(home: Path) -> bool:
    from alpi import config as cfg_mod
    cfg = cfg_mod.load(home)
    return bool((cfg.host or {}).get("allow_public_bind") or False)


def resolve_host_tcp_port(home: Path) -> int:
    from alpi import config as cfg_mod

    env_port = _env_port("ALPI_HOST_TCP_PORT")
    if env_port is not None:
        return env_port
    cfg = cfg_mod.load(home)
    return int((cfg.host or {}).get("tcp_port") or DEFAULT_TCP_PORT)


def _env_port(name: str) -> int | None:
    raw = str(os.environ.get(name) or "").strip()
    if not raw:
        return None
    try:
        port = int(raw)
    except ValueError:
        return None
    return port if 1 <= port <= 65535 else None


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


def normalize_host_endpoints(value: Any) -> list[dict[str, str]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("endpoints must be a list")
    if len(value) > 8:
        raise ValueError("at most 8 endpoints are allowed")
    endpoints: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValueError(f"endpoint {index + 1} must be an object")
        raw_url = str(item.get("url") or "").strip()
        label = str(item.get("label") or "").strip()
        if not raw_url:
            raise ValueError(f"endpoint {index + 1} needs a URL")
        if not label:
            raise ValueError(f"endpoint {index + 1} needs a label")
        if len(label) > 48:
            raise ValueError(f"endpoint {index + 1} label is too long")
        if "," in label or "=" in label:
            raise ValueError(f"endpoint {index + 1} label cannot contain ',' or '='")
        try:
            parsed = urlsplit(raw_url)
            port = parsed.port
        except ValueError as exc:
            raise ValueError(f"endpoint {index + 1} has an invalid URL: {exc}") from exc
        if parsed.scheme not in {"ws", "wss"}:
            raise ValueError(f"endpoint {index + 1} must use ws:// or wss://")
        if not parsed.hostname:
            raise ValueError(f"endpoint {index + 1} needs a hostname")
        if port == 0:
            raise ValueError(f"endpoint {index + 1} port must be between 1 and 65535")
        if parsed.username or parsed.password:
            raise ValueError(f"endpoint {index + 1} cannot contain credentials")
        if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
            raise ValueError(f"endpoint {index + 1} cannot contain a path, query, or fragment")
        host = parsed.hostname.rstrip(".")
        if ":" not in host and not all(
            part and len(part) <= 63 and part[0] != "-" and part[-1] != "-"
            and all((char.isascii() and char.isalnum()) or char == "-" for char in part)
            for part in host.split(".")
        ):
            raise ValueError(f"endpoint {index + 1} has an invalid hostname")
        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            ip = None
        if parsed.scheme == "ws" and ip is None:
            raise ValueError(
                f"endpoint {index + 1} must use wss:// for hostnames; "
                "ws:// requires a private IP literal"
            )
        if ip is not None:
            if (
                ip.is_loopback or ip.is_unspecified or ip.is_multicast
                or ip.is_link_local or ip.is_reserved
            ):
                raise ValueError(f"endpoint {index + 1} has an unsafe advertised address")
            if parsed.scheme == "ws" and not (
                is_tailscale_ip(host)
                or any(ip in net for net in _PRIVATE_RANGES)
                or ip.is_private
            ):
                raise ValueError(
                    f"endpoint {index + 1} exposes a pairing token over a public ws:// address"
                )
        host_text = f"[{host}]" if ":" in host else host
        default_port = 443 if parsed.scheme == "wss" else 80
        suffix = f":{port}" if port is not None and port != default_port else ""
        url = f"{parsed.scheme}://{host_text}{suffix}"
        if url in seen:
            raise ValueError(f"endpoint {index + 1} duplicates {url}")
        seen.add(url)
        endpoints.append({"url": url, "label": label})
    return endpoints


def resolve_host_endpoints(home: Path) -> list[dict[str, str]]:
    from alpi import config as cfg_mod

    cfg = cfg_mod.load(home)
    configured = normalize_host_endpoints((cfg.host or {}).get("endpoints"))
    if configured and any(row["url"].startswith("ws://") for row in configured):
        return configured
    endpoint = resolve_host_endpoint(home)
    if endpoint is None:
        return configured
    host, _scope = endpoint
    host_text = f"[{host}]" if ":" in host else host
    fallback = [{
        "url": f"ws://{host_text}:{resolve_host_tcp_port(home)}",
        "label": "Direct",
    }]
    try:
        direct = normalize_host_endpoints(fallback)
    except ValueError:
        direct = []
    return configured + direct


def pairing_unavailable_detail(home: Path) -> str:
    endpoint = resolve_host_endpoint(home)
    if endpoint is not None:
        host, _scope = endpoint
        try:
            ipaddress.ip_address(host.rstrip("."))
        except ValueError:
            return (
                f"Cannot pair: {host!r} is a hostname. Configure a "
                "certificate-validated wss:// URL in host.endpoints."
            )
    return "Cannot pair: no private network address detected."


def _configured_host(home: Path) -> str | None:
    from alpi import config as cfg_mod

    # Shared accessible address from config, used by BOTH the host plane and the
    # ALP listener. Empty = auto-detect (Tailscale then LAN). Containers set the
    # address via the ALPI_NETWORK_HOST env instead (see `_advertise_host_hint`
    # and `service._resolve_alp_tcp`).
    cfg = cfg_mod.load(home)
    host = str((cfg.network or {}).get("host") or "").strip()
    return host or None


def _advertise_host_hint() -> str | None:
    # Reachable endpoint clients dial — the shared accessible address, set by
    # env in containers (ALPI_NETWORK_HOST).
    return str(os.environ.get("ALPI_NETWORK_HOST") or "").strip() or None


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


def classify_scope(host: str | None, raw_scope: str | None) -> str | None:
    # User-facing scope = network character of the host, not where it came from. A configured Tailscale IP reads as "tailscale", a configured hostname reads as "custom".
    if raw_scope is None or host is None:
        return raw_scope
    if raw_scope == "docker":
        return "docker"
    if is_tailscale_ip(host):
        return "tailscale"
    try:
        ip = ipaddress.ip_address(host)
        if any(ip in net for net in _PRIVATE_RANGES):
            return "lan"
    except ValueError:
        pass
    return "custom"


__all__ = [
    "classify_scope",
    "detect_bind_ip",
    "normalize_host_endpoints",
    "pairing_unavailable_detail",
    "resolve_bind_host",
    "resolve_host_endpoint",
    "resolve_host_endpoints",
    "resolve_host_pairing_name",
    "resolve_host_tcp_bind",
    "resolve_host_tcp_port",
]
