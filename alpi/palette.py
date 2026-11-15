from __future__ import annotations

from typing import Any

from alpi import mark_shapes

STATUS = {
    "success": "#3fb37a",
    "warning": "#e08a3c",
    "danger": "#c14545",
}

DARK = {
    "bg": "#1a1a1a",
    "bgPane": "#1a1a1a",
    "bgElev": "#2c2c2c",
    "fill": "#262626",
    "ink": "#ededed",
    "ink2": "#b4b4b4",
    "ink3": "#969696",
    "accent": "#f3efe6",
    "warningText": "#f59e5b",
}

LIGHT = {
    "bg": "#ffffff",
    "bgPane": "#ffffff",
    "bgElev": "#ffffff",
    "fill": "#f2f2f2",
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


def eye_ink(tui: dict[str, Any] | None) -> str:
    return EYE_INK["dark" if is_dark(tui) else "light"]


def profile_accent(tui: dict[str, Any] | None) -> str:
    return resolve_accent((tui or {}).get("accent"), is_dark(tui))


SHAPES = mark_shapes.SHAPE_ORDER
DEFAULT_SHAPE = SHAPES[0]
TWIN_SHAPE = "twin"
WORKGROUP_SHAPE = "honeycomb"
BRAND_INK = {"light": "#14110c", "dark": "#f3efe6"}
EYE_INK = {"light": "#ffffff", "dark": "#000000"}


def shape_of(value: Any) -> str | None:
    word = value.strip().lower() if isinstance(value, str) else ""
    return word if word in SHAPES else None


def legacy_shape(value: Any) -> str | None:
    word = value.strip().lower() if isinstance(value, str) else ""
    return shape_of(word) or mark_shapes.LEGACY_SHAPE.get(word)


def resolve_shape(configured: Any) -> str:
    return shape_of(configured) or DEFAULT_SHAPE
