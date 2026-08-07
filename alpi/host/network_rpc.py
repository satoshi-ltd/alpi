"""host.network.* — desktop/mobile clients query and configure the advertised pairing endpoint without dropping to the CLI."""

from __future__ import annotations

import ipaddress
import re
from typing import Any

from alpi.host import server as host_server
from alpi.host.network import classify_scope
from alpi.host.tailscale import is_tailscale_ip


_PRIVATE_RANGES = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
)

_HOSTNAME_LABEL = re.compile(r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)$")


def register(server: host_server.Server) -> None:
    server.register("host.network.status", _status)
    server.register("host.network.set_advertised", _set_advertised)
    server.register("host.network.restart_host_server", _restart_host_server)


def _probe_endpoints() -> dict[str, Any]:
    import socket

    from alpi.host.network import _detect_lan_ip_via_ifconfig, _is_private_lan
    from alpi.host.tailscale import detect_tailscale_ip

    ts = detect_tailscale_ip()
    udp_ip: str | None = None
    udp_err: str | None = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 53))
            udp_ip = s.getsockname()[0]
        finally:
            s.close()
    except OSError as exc:
        udp_err = str(exc)
    ifc = _detect_lan_ip_via_ifconfig()
    lan = (udp_ip if (udp_ip and _is_private_lan(udp_ip)) else None) or ifc
    return {
        "tailscale": ts,
        "lan": lan,
        "udp_ip": udp_ip,
        "udp_err": udp_err,
        "ifconfig": ifc,
    }


async def _status(_params: dict[str, Any], server: host_server.Server) -> dict[str, Any]:
    # Resolution order: configured → managed-runtime hint → tailscale → lan. Probes run once off-loop.
    import asyncio
    import os

    from alpi import config as cfg_mod
    from alpi import runtime
    from alpi.host.network import (
        _advertise_host_hint,
        _is_private_lan,
        normalize_host_endpoints,
        resolve_host_endpoints,
        resolve_host_pairing_name,
        resolve_host_tcp_port,
    )

    home = server.home
    cfg = cfg_mod.load(home)
    configured = str((cfg.network or {}).get("host") or "").strip() or None
    is_docker = runtime.is_docker()
    advertise_hint = _advertise_host_hint() if is_docker else None
    raw_environment_port = str(os.environ.get("ALPI_HOST_TCP_PORT") or "").strip()
    try:
        environment_port = int(raw_environment_port)
    except ValueError:
        environment_port = 0
    if 1 <= environment_port <= 65535:
        port_source = "environment"
    elif (cfg.host or {}).get("tcp_port"):
        port_source = "config"
    else:
        port_source = "default"

    probes = await asyncio.to_thread(_probe_endpoints)

    host_in_use: str | None
    raw_scope: str | None
    if configured:
        host_in_use, raw_scope = configured, "configured"
    elif is_docker:
        host_in_use, raw_scope = (
            (advertise_hint, "docker") if advertise_hint else (None, None)
        )
    elif probes["tailscale"]:
        host_in_use, raw_scope = probes["tailscale"], "tailscale"
    elif probes["lan"]:
        host_in_use, raw_scope = probes["lan"], "lan"
    else:
        host_in_use, raw_scope = None, None

    try:
        endpoints = resolve_host_endpoints(home)
        configured_endpoints = normalize_host_endpoints(
            (cfg.host or {}).get("endpoints")
        )
    except ValueError as exc:
        raise host_server.HandlerError(
            -32010, "invalid-advertised-endpoints", data={"detail": str(exc)},
        ) from exc

    return {
        "scope_in_use": classify_scope(host_in_use, raw_scope),
        "host_in_use": host_in_use,
        "is_override": raw_scope == "configured",
        "port": resolve_host_tcp_port(home),
        "port_source": port_source,
        "device_name": resolve_host_pairing_name(home),
        "endpoints": endpoints,
        "configured_endpoints": configured_endpoints,
        "is_endpoints_override": bool((cfg.host or {}).get("endpoints")),
        "websocket": server.websocket_status(),
        "candidates": {
            "tailscale": probes["tailscale"],
            "lan": probes["lan"],
            "configured": configured,
            "docker": advertise_hint,
        },
        "diagnosis": {
            "tailscale": probes["tailscale"],
            "udp_probe_ip": probes["udp_ip"],
            "udp_probe_error": probes["udp_err"],
            "udp_probe_is_private": (
                str(_is_private_lan(probes["udp_ip"])) if probes["udp_ip"] else None
            ),
            "ifconfig_lan": probes["ifconfig"],
        },
    }


_SENTINEL = object()


async def _set_advertised(
    params: dict[str, Any], server: host_server.Server,
) -> dict[str, Any]:
    # Absent key = preserve existing value; explicit "" = unset. A partial call must NOT clobber the other field.
    from alpi import config as cfg_mod

    p = params or {}
    host_param = p.get("host", _SENTINEL)
    name_param = p.get("device_name", _SENTINEL)
    endpoints_param = p.get("endpoints", _SENTINEL)

    host_in = str(host_param).strip() if host_param is not _SENTINEL else _SENTINEL
    name_in = str(name_param).strip() if name_param is not _SENTINEL else _SENTINEL
    if endpoints_param is _SENTINEL:
        endpoints_in = _SENTINEL
    else:
        from alpi.host.network import normalize_host_endpoints

        try:
            endpoints_in = normalize_host_endpoints(endpoints_param)
        except ValueError as exc:
            raise host_server.HandlerError(
                -32602, "invalid-endpoints", data={"detail": str(exc)},
            ) from exc

    if isinstance(host_in, str) and host_in:
        err = _validate_advertised_host(host_in)
        if err:
            raise host_server.HandlerError(
                -32602, "invalid-host", data={"detail": err},
            )

    home = server.home
    cfg = cfg_mod.load(home)
    host_cfg = dict(cfg.host or {})
    net_cfg = dict(cfg.network or {})
    changed = False
    restart_needed = False

    # The accessible address is shared (network.host); the pairing name is
    # host-plane only.
    if host_in is not _SENTINEL:
        if host_in:
            if net_cfg.get("host") != host_in:
                net_cfg["host"] = host_in
                changed = True
                restart_needed = True
        elif "host" in net_cfg:
            net_cfg.pop("host", None)
            changed = True
            restart_needed = True

    if name_in is not _SENTINEL:
        if name_in:
            if host_cfg.get("device_name") != name_in:
                host_cfg["device_name"] = name_in
                changed = True
        elif "device_name" in host_cfg:
            host_cfg.pop("device_name", None)
            changed = True

    if endpoints_in is not _SENTINEL:
        if endpoints_in:
            if host_cfg.get("endpoints") != endpoints_in:
                host_cfg["endpoints"] = endpoints_in
                changed = True
        elif "endpoints" in host_cfg:
            host_cfg.pop("endpoints", None)
            changed = True

    if changed:
        cfg.host = host_cfg
        cfg.network = net_cfg
        cfg_mod.save(cfg)

    return {"ok": True, "restart_needed": restart_needed}


async def _restart_host_server(
    _params: dict[str, Any], server: host_server.Server,
) -> dict[str, Any]:
    from alpi import service as svc
    from alpi.host.daemon import schedule_self_terminate

    home = server.home
    if svc.daemon_running_pid(home) is None:
        return {"ok": True, "restarted": False}
    schedule_self_terminate()
    return {"ok": True, "restarted": True}


def _validate_advertised_host(host: str) -> str | None:
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return None if _is_valid_hostname(host) else f"not a valid hostname: {host!r}"
    if ip.is_loopback:
        return "loopback addresses are not pairing targets"
    if ip.is_unspecified:
        return "0.0.0.0 / :: is not a valid advertised host"
    if ip.is_multicast or ip.is_link_local or ip.is_reserved:
        return "multicast / link-local / reserved addresses are not valid"
    if is_tailscale_ip(host):
        return None
    if any(ip in net for net in _PRIVATE_RANGES):
        return None
    # is_private also covers RFC4193 / ULA / CGNAT — keep as last gate.
    if not ip.is_private:
        return "public IPs are rejected — pairing token would leak in plaintext"
    return None


def _is_valid_hostname(host: str) -> bool:
    if not host or len(host) > 253:
        return False
    if host.endswith("."):
        host = host[:-1]
    parts = host.split(".")
    if not parts or any(not p for p in parts):
        return False
    return all(_HOSTNAME_LABEL.match(p) for p in parts)


__all__ = ["register"]
