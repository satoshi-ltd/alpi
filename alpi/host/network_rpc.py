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


async def _status(_params: dict[str, Any], server: host_server.Server) -> dict[str, Any]:
    from alpi import config as cfg_mod
    from alpi.host.network import (
        _detect_lan_ip,
        diagnose_bind_ip,
        resolve_host_endpoint,
        resolve_host_pairing_name,
        resolve_host_tcp_port,
    )
    from alpi.host.tailscale import detect_tailscale_ip

    home = server.home
    cfg = cfg_mod.load(home)
    configured = str((cfg.host or {}).get("tcp_host") or "").strip() or None

    try:
        endpoint = resolve_host_endpoint(home)
    except Exception:  # noqa: BLE001
        endpoint = None
    host_in_use: str | None = None
    raw_scope: str | None = None
    if endpoint is not None:
        host_in_use, raw_scope = endpoint

    return {
        "scope_in_use": classify_scope(host_in_use, raw_scope),
        "host_in_use": host_in_use,
        "is_override": raw_scope == "configured",
        "port": resolve_host_tcp_port(home),
        "device_name": resolve_host_pairing_name(home),
        "candidates": {
            "tailscale": detect_tailscale_ip(),
            "lan": _detect_lan_ip(),
            "configured": configured,
        },
        "diagnosis": diagnose_bind_ip(),
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

    host_in = str(host_param).strip() if host_param is not _SENTINEL else _SENTINEL
    name_in = str(name_param).strip() if name_param is not _SENTINEL else _SENTINEL

    if isinstance(host_in, str) and host_in:
        err = _validate_advertised_host(host_in)
        if err:
            raise host_server.HandlerError(
                -32602, "invalid-host", data={"detail": err},
            )

    home = server.home
    cfg = cfg_mod.load(home)
    host_cfg = dict(cfg.host or {})
    changed = False

    if host_in is not _SENTINEL:
        if host_in:
            if host_cfg.get("tcp_host") != host_in:
                host_cfg["tcp_host"] = host_in
                changed = True
        elif "tcp_host" in host_cfg:
            host_cfg.pop("tcp_host", None)
            changed = True

    if name_in is not _SENTINEL:
        if name_in:
            if host_cfg.get("device_name") != name_in:
                host_cfg["device_name"] = name_in
                changed = True
        elif "device_name" in host_cfg:
            host_cfg.pop("device_name", None)
            changed = True

    if changed:
        cfg.host = host_cfg
        cfg_mod.save(cfg)

    return {"ok": True, "restart_needed": changed}


async def _restart_host_server(
    _params: dict[str, Any], server: host_server.Server,
) -> dict[str, Any]:
    # Full daemon restart via SIGTERM; supervisor respawns with fresh config. Matches `alpi setup`'s `_restart_daemon_for_apply`.
    from alpi import service as svc

    home = server.home
    if svc.daemon_running_pid(home) is None:
        return {"ok": True, "restarted": False}
    svc.stop_daemon(home, timeout=2.0)
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
