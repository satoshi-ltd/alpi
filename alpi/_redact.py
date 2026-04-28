"""Best-effort redaction of secret-shaped values before persisting
session logs. Value-pattern only — we do NOT redact by key name to
avoid corrupting `--continue` resume on legitimate fields whose name
happens to contain ``password`` / ``token`` / etc."""

from __future__ import annotations

import re
from typing import Any


_VALUE_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"gho_[A-Za-z0-9]{20,}"),
    re.compile(r"xox[abprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"AIza[A-Za-z0-9_-]{30,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"\d{8,12}:[A-Za-z0-9_-]{30,}"),
)

_REDACTED = "[REDACTED]"


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
    for pat in _VALUE_PATTERNS:
        out = pat.sub(_REDACTED, out)
    return out
