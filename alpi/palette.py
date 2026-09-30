from __future__ import annotations

from typing import Any

STATUS = {
    "success": "#3fb37a",
    "warning": "#e08a3c",
    "danger": "#c14545",
}

DARK = {
    "bg": "#0a0d11",
    "bgPane": "#11151a",
    "bgElev": "#161b22",
    "ink": "#e6edf3",
    "ink2": "#b1bac4",
    "ink3": "#828b97",
    "accent": "#f0b447",
}

LIGHT = {
    "bg": "#eef0f2",
    "bgPane": "#ffffff",
    "bgElev": "#ffffff",
    "ink": "#0b1117",
    "ink2": "#3d4955",
    "ink3": "#626e7d",
    "accent": "#8a5a0a",
}

DEFAULT_ACCENT = DARK["accent"]
# #c8a24e was the pre-token default; saved configs carrying it must follow the mode's token.
_BRAND_ACCENTS = frozenset({DEFAULT_ACCENT, LIGHT["accent"], "#c8a24e"})


def resolve_accent(configured: str | None, dark: bool) -> str:
    value = (configured or "").strip()
    if not value or value.lower() in _BRAND_ACCENTS:
        return (DARK if dark else LIGHT)["accent"]
    return value


def is_dark(tui: dict[str, Any] | None) -> bool:
    return str((tui or {}).get("theme") or "dark").lower() != "light"


def profile_accent(tui: dict[str, Any] | None) -> str:
    return resolve_accent((tui or {}).get("accent"), is_dark(tui))
