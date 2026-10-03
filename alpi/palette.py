from __future__ import annotations

from typing import Any

STATUS = {
    "success": "#3fb37a",
    "warning": "#e08a3c",
    "danger": "#c14545",
}

DARK = {
    "bg": "#0b0b0b",
    "bgPane": "#151515",
    "bgElev": "#1b1b1b",
    "ink": "#ededed",
    "ink2": "#b4b4b4",
    "ink3": "#8a8a8a",
    "accent": "#f3efe6",
    "warningText": "#f59e5b",
}

LIGHT = {
    "bg": "#f0f0f0",
    "bgPane": "#ffffff",
    "bgElev": "#ffffff",
    "ink": "#141414",
    "ink2": "#454545",
    "ink3": "#6b6b6b",
    "accent": "#14110c",
    "warningText": "#b3470e",
}

DEFAULT_ACCENT = DARK["accent"]
# #c8a24e was the pre-token default; saved configs carrying it must follow the mode's token.
_BRAND_ACCENTS = frozenset({DARK["accent"], LIGHT["accent"], "#8a5a0a", "#c8a24e"})
DEFAULT_PROFILE_COLOUR = "#f0b447"
LEGACY_ACCENTS = {"#7e8792": "#3ac9f3"}


def canonical_accent(value: str | None) -> str | None:
    if value is None:
        return None
    return LEGACY_ACCENTS.get(str(value).strip().lower(), value)


def resolve_accent(configured: str | None, dark: bool) -> str:
    value = (configured or "").strip()
    if not value or value.lower() in _BRAND_ACCENTS:
        return (DARK if dark else LIGHT)["accent"]
    return canonical_accent(value)


def is_dark(tui: dict[str, Any] | None) -> bool:
    return str((tui or {}).get("theme") or "dark").lower() != "light"


def profile_accent(tui: dict[str, Any] | None) -> str:
    return resolve_accent((tui or {}).get("accent"), is_dark(tui))


FOLDS = ("diamond", "house", "heart", "plane", "shield", "rocket", "star", "tree", "box", "crown", "feather", "bulb")
DEFAULT_FOLD = FOLDS[0]
ALPACA_FOLD = "alpaca"
BRAND_INK = {"light": "#14110c", "dark": "#f3efe6"}


def resolve_fold(configured: Any) -> str:
    value = str(configured or "").strip().lower()
    return value if value in FOLDS else DEFAULT_FOLD
