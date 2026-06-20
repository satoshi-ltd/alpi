from __future__ import annotations

import ipaddress
import socket
import ssl
import time
from typing import Optional, Tuple, Union
from urllib.parse import urlparse

import httpcore
import httpx

from alpi.tools._guards import _is_blocked_ip, _is_loopback, _METADATA_HOSTS


VerifyArg = Union[ssl.SSLContext, str, bool]


class _PinnedBackend(httpcore.NetworkBackend):
    def __init__(
        self,
        host_to_ips: dict[str, list[str]],
        inner: httpcore.NetworkBackend | None = None,
    ) -> None:
        self._pinned = {h: list(ips) for h, ips in host_to_ips.items()}
        self._inner = inner or httpcore.SyncBackend()

    def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        ips = self._pinned.get(host)
        if not ips:
            raise httpcore.ConnectError(f"host {host!r} not in pinned DNS map (rebinding guard)")
        deadline = (time.monotonic() + timeout) if timeout is not None else None
        last_err: BaseException | None = None
        for ip in ips:
            remaining = (deadline - time.monotonic()) if deadline is not None else None
            if remaining is not None and remaining <= 0:
                break
            try:
                return self._inner.connect_tcp(
                    ip, port,
                    timeout=remaining,
                    local_address=local_address,
                    socket_options=socket_options,
                )
            except (httpcore.ConnectError, httpcore.ConnectTimeout, OSError) as e:
                last_err = e
                continue
        raise last_err if last_err is not None else httpcore.ConnectError(
            f"no pinned IP for {host!r} succeeded",
        )

    def connect_unix_socket(self, path, timeout=None, socket_options=None):
        return self._inner.connect_unix_socket(path, timeout=timeout, socket_options=socket_options)

    def sleep(self, seconds):
        return self._inner.sleep(seconds)


def resolve_and_pin(
    url: str, *, allow_loopback: bool = False,
) -> Tuple[bool, str, Optional[str], list[str]]:
    if not url:
        return False, "empty url", None, []
    try:
        parsed = urlparse(url)
    except Exception:
        return False, "unparseable url", None, []
    if parsed.scheme not in ("http", "https"):
        return False, f"unsupported scheme {parsed.scheme!r}", None, []
    host = (parsed.hostname or "").lower()
    if not host:
        return False, "missing host", None, []
    if host in _METADATA_HOSTS:
        return False, f"cloud metadata host {host!r}", None, []

    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None

    if literal is not None:
        if _is_blocked_ip(literal) and not (allow_loopback and _is_loopback(literal)):
            return False, f"private/link-local ip {literal}", None, []
        return True, "", host, [host]

    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return False, f"dns resolution failed for {host!r}", None, []

    pinned: list[str] = []
    seen: set[str] = set()
    for info in infos:
        addr = info[4][0]
        if addr in seen:
            continue
        seen.add(addr)
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if _is_blocked_ip(ip) and not (allow_loopback and _is_loopback(ip)):
            return False, f"{host!r} resolves to private ip {ip}", None, []
        pinned.append(addr)
    if not pinned:
        return False, f"{host!r} resolved to no usable address", None, []
    return True, "", host, pinned


def make_pinned_transport(
    host_to_ips: dict[str, list[str]], *, verify: VerifyArg = True,
) -> httpx.HTTPTransport:
    transport = httpx.HTTPTransport(verify=verify)
    ssl_context = transport._pool._ssl_context
    transport._pool = httpcore.ConnectionPool(
        ssl_context=ssl_context,
        network_backend=_PinnedBackend(host_to_ips),
    )
    return transport


def safe_client(
    url: str,
    *,
    allow_loopback: bool = False,
    timeout: float = 30.0,
    follow_redirects: bool = False,
    verify: VerifyArg = True,
) -> Tuple[bool, str, Optional[httpx.Client]]:
    ok, reason, host, ips = resolve_and_pin(url, allow_loopback=allow_loopback)
    if not ok or host is None or not ips:
        return False, reason, None
    transport = make_pinned_transport({host: ips}, verify=verify)
    client = httpx.Client(
        transport=transport,
        timeout=timeout,
        follow_redirects=follow_redirects,
    )
    return True, "", client
