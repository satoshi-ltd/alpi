"""Best-effort redaction of secret-shaped values before persisting
session logs. Value-pattern only — we do NOT redact by key name to
avoid corrupting `--continue` resume on legitimate fields whose name
happens to contain ``password`` / ``token`` / etc."""

from __future__ import annotations

import re
from typing import Any


_REDACTED = "[REDACTED]"

# (pattern, replacement); most map the whole match to [REDACTED], structured ones keep surrounding shape.
_VALUE_PATTERNS: tuple[tuple[re.Pattern, str], ...] = (
    (re.compile(r"sk-[A-Za-z0-9_-]{16,}"), _REDACTED),
    (re.compile(r"ghp_[A-Za-z0-9]{20,}"), _REDACTED),
    (re.compile(r"gho_[A-Za-z0-9]{20,}"), _REDACTED),
    (re.compile(r"xox[abprs]-[A-Za-z0-9-]{10,}"), _REDACTED),
    (re.compile(r"AIza[A-Za-z0-9_-]{30,}"), _REDACTED),
    (re.compile(r"AKIA[0-9A-Z]{16}"), _REDACTED),
    (re.compile(r"\d{8,12}:[A-Za-z0-9_-]{30,}"), _REDACTED),
    # user:pass@ in a URL — keep the scheme, drop the credentials.
    (re.compile(r"(?P<scheme>[a-zA-Z][a-zA-Z0-9+.-]*://)[^/\s:@]+:[^/\s@]+@"),
     r"\g<scheme>[REDACTED]@"),
    # PEM private-key blocks.
    (re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----",
                re.S), _REDACTED),
)


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return _redact_string(value)
    return value


def _redact_string(s: str) -> str:
    out = s
    for pat, repl in _VALUE_PATTERNS:
        out = pat.sub(repl, out)
    return out
