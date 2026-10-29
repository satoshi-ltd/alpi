"""Best-effort redaction of secret-shaped values before persisting
session logs. Value-pattern only, except HTTP credential header names — we do
NOT redact by generic key names to avoid corrupting `--continue` resume on
legitimate fields whose name happens to contain ``password`` / ``token`` / etc."""

from __future__ import annotations

import re
from typing import Any


_REDACTED = "[REDACTED]"
_LONE_SURROGATE = re.compile("[\ud800-\udfff]")

# (pattern, replacement); most map the whole match to [REDACTED], structured ones keep surrounding shape.
_VALUE_PATTERNS: tuple[tuple[re.Pattern, str], ...] = (
    (re.compile(r"sk-[A-Za-z0-9_-]{16,}"), _REDACTED),
    (re.compile(r"ghp_[A-Za-z0-9]{20,}"), _REDACTED),
    (re.compile(r"gho_[A-Za-z0-9]{20,}"), _REDACTED),
    (re.compile(r"xox[abprs]-[A-Za-z0-9-]{10,}"), _REDACTED),
    (re.compile(r"AIza[A-Za-z0-9_-]{30,}"), _REDACTED),
    (re.compile(r"AKIA[0-9A-Z]{16}"), _REDACTED),
    (re.compile(r"\d{8,12}:[A-Za-z0-9_-]{30,}"), _REDACTED),
    (re.compile(r"github_pat_[A-Za-z0-9_]{20,}"), _REDACTED),
    (re.compile(r"glpat-[A-Za-z0-9_-]{20,}"), _REDACTED),
    (re.compile(r"gsk_[A-Za-z0-9]{20,}"), _REDACTED),
    (re.compile(r"ya29\.[A-Za-z0-9_-]{20,}"), _REDACTED),
    (re.compile(r"\b1//0[A-Za-z0-9_-]{20,}"), _REDACTED),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"), _REDACTED),
    (re.compile(r"(?i)\b(bearer)\s+(?=[A-Za-z._~/-]*[0-9+=])[A-Za-z0-9._~+/=-]{16,}"), r"\1 [REDACTED]"),
    (re.compile(r"(?i)(authorization:[ \t]*basic[ \t]+)[A-Za-z0-9+/]{8,}={0,2}"), r"\1[REDACTED]"),
    (re.compile(r"(?i)\b((?:set-)?cookie[ \t]*:[ \t]*)[^\s=;:'\"]+=[^\r\n'\"]*"), r"\1[REDACTED]"),
    (re.compile(r"(?i)\b(x-api-key[ \t]*:[ \t]*)[A-Za-z0-9._~+/=-]{16,}"), r"\1[REDACTED]"),
    (re.compile(r"(?i)([\"'](?:set-)?cookie[\"']\s*:\s*[\"'])[^\"'\s=;]+=[^\"']*"), r"\1[REDACTED]"),
    (re.compile(r"(?i)([\"']x-api-key[\"']\s*:\s*[\"'])[A-Za-z0-9._~+/=-]{16,}"), r"\1[REDACTED]"),
    (re.compile(r"(?i)\b(access_token|refresh_token|id_token|client_secret|api_?key|token)=[^&\s\"']{16,}"), r"\1=[REDACTED]"),
    # user:pass@ in a URL — keep the scheme, drop the credentials; the scheme stays bounded to keep the scan linear.
    (re.compile(r"(?P<scheme>[a-zA-Z0-9+.-]{1,32}://)[^/\s:@]+:[^/\s@]+@"),
     r"\g<scheme>[REDACTED]@"),
)
_PEM_BEGIN = re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY(?: BLOCK)?-----")
_PEM_END = re.compile(r"-----END [A-Z0-9 ]*PRIVATE KEY(?: BLOCK)?-----")
_HEADER_KEYS = frozenset({"cookie", "set-cookie", "x-api-key", "authorization", "proxy-authorization"})


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            scrub_surrogates(k): _REDACTED if _is_header_secret(k, v) else redact(v)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact(item) for item in value)
    if isinstance(value, str):
        return _redact_string(value)
    return value


def _is_header_secret(key: Any, value: Any) -> bool:
    return isinstance(key, str) and key.casefold() in _HEADER_KEYS and isinstance(value, str) and bool(value)


def scrub_surrogates(key: Any) -> Any:
    return _LONE_SURROGATE.sub("\ufffd", key) if isinstance(key, str) else key


def _redact_string(s: str) -> str:
    out = _LONE_SURROGATE.sub("\ufffd", s)
    for pat, repl in _VALUE_PATTERNS:
        out = pat.sub(repl, out)
    return _redact_pem(out)


def _redact_pem(s: str) -> str:
    # Stops at the first BEGIN without an END, so unmatched markers cannot rescan the tail.
    parts: list[str] = []
    pos = 0
    while (begin := _PEM_BEGIN.search(s, pos)) is not None:
        end = _PEM_END.search(s, begin.end())
        if end is None:
            break
        parts.append(s[pos:begin.start()])
        parts.append(_REDACTED)
        pos = end.end()
    if not parts:
        return s
    parts.append(s[pos:])
    return "".join(parts)
