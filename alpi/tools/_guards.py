"""Application-level security guards — command denylist, SSRF, injection scan."""

from __future__ import annotations

import ipaddress
import re
import socket
from typing import Tuple
from urllib.parse import urlparse

from alpi.scan import scan_injection as scan_injection

_DANGEROUS: list[tuple[str, re.Pattern]] = [
    ("recursive rm on sensitive path",
     re.compile(r"\brm\s+-[a-zA-Z]*[rR][a-zA-Z]*\s+(?:/\s*$|/[^ /]|~|\$HOME)", re.IGNORECASE)),
    ("chmod 777",
     re.compile(r"\bchmod\b.*\b(?:777|a\+w)", re.IGNORECASE)),
    ("recursive chown outside workspace",
     re.compile(r"\bchown\s+-R\s+[^ ]+\s+(?:/|~|\$HOME)", re.IGNORECASE)),
    ("mkfs",
     re.compile(r"\bmkfs(?:\.\w+)?\b", re.IGNORECASE)),
    ("dd to block device",
     re.compile(r"\bdd\b[^|;&]*\bof=/dev/", re.IGNORECASE)),
    ("pipe-to-interpreter",
     re.compile(r"\b(?:curl|wget|fetch)\b[^|]*\|\s*(?:sh|bash|zsh|python|python3|perl|ruby|node)\b", re.IGNORECASE)),
    ("fork bomb",
     re.compile(r":\s*\(\s*\)\s*\{\s*:\s*\|\s*:&\s*}\s*;\s*:", re.IGNORECASE)),
    ("write to system directory",
     re.compile(r"(?:>+|tee)\s+/(?:etc|var|usr|boot|sys|proc)/", re.IGNORECASE)),
    ("read ssh private key",
     re.compile(r"(?:cat|head|tail|less|more|cp|mv|scp|rsync)\s+[^ ]*(?:\.ssh/id_|\.pem\b|id_rsa\b|id_ed25519\b)", re.IGNORECASE)),
    ("read profile secret",
     re.compile(r"(?:cat|head|tail|less|more|cp|mv|scp|rsync|grep|awk|sed|xxd|hexdump|strings|od)\b[^|;&]*?\.alpi(?:/profiles/[^/ ]+)?/(?:\.env|config\.yaml)\b", re.IGNORECASE)),
    ("write profile config",
     re.compile(r"(?:>+|tee\b)[^|;&]*?\.alpi(?:/profiles/[^/ ]+)?/(?:\.env|config\.yaml)\b", re.IGNORECASE)),
    ("dump environment",
     re.compile(r"(?:^|[|;&]\s*)\s*(?:env|printenv)\s*(?:\||;|&|>|$)", re.IGNORECASE)),
    ("sql destructive",
     re.compile(r"\b(?:DROP|TRUNCATE)\s+(?:TABLE|DATABASE|SCHEMA)\b", re.IGNORECASE)),
]


def check_command(command: str) -> Tuple[bool, str]:
    if not command:
        return True, ""
    for label, pattern in _DANGEROUS:
        if pattern.search(command):
            return False, label
    return True, ""


_BLOCKED_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),   # CGNAT — Alibaba metadata 100.100.100.200
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.0.0.0/24"),    # IETF protocol — Oracle metadata 192.0.0.192
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("::/128"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("fc00::/7"),
]


def _is_blocked_ip(ip: "ipaddress.IPv4Address | ipaddress.IPv6Address") -> bool:
    if any(ip in net for net in _BLOCKED_NETWORKS):
        return True
    mapped = getattr(ip, "ipv4_mapped", None)
    return mapped is not None and any(mapped in net for net in _BLOCKED_NETWORKS)

_METADATA_HOSTS = {
    "metadata.google.internal",
    "metadata",
    "metadata.azure.com",
    "instance-data",
}


def check_url(url: str) -> Tuple[bool, str]:
    if not url:
        return False, "empty url"
    try:
        parsed = urlparse(url)
    except Exception:
        return False, "unparseable url"
    if parsed.scheme not in ("http", "https"):
        return False, f"unsupported scheme {parsed.scheme!r}"
    host = (parsed.hostname or "").lower()
    if not host:
        return False, "missing host"
    if host in _METADATA_HOSTS:
        return False, f"cloud metadata host {host!r}"
    try:
        ip = ipaddress.ip_address(host)
        if _is_blocked_ip(ip):
            return False, f"private/link-local ip {ip}"
        return True, ""
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return False, f"dns resolution failed for {host!r}"
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
        if _is_blocked_ip(ip):
            return False, f"{host!r} resolves to private ip {ip}"
    return True, ""
