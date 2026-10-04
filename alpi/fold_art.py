from __future__ import annotations

import math
import os
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any, TextIO

from rich.text import Text

from alpi import appearance, palette
from alpi.fold_shapes import SHAPES

FALLBACK_GLYPH = "◆"
FALLBACK_INACTIVE = "◇"
DEFAULT_ROWS = 8
BANNER_ROWS = 6

GLYPHS = {
    "diamond": "⬥",
    "house": "⌂",
    "heart": "❥",
    "plane": "➤",
    "shield": "⬟",
    "rocket": "⌃",
    "star": "✦",
    "tree": "▴",
    "box": "⬝",
    "crown": "♛",
    "feather": "✎",
    "bulb": "☼",
    "honeycomb": "⬢",
    palette.ALPACA_FOLD: "❖",
}

_FALLBACK_ACCENT = "#f0b447"


def _linear(value: int) -> float:
    v = value / 255
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def _gamma(value: float) -> float:
    c = max(0.0, min(1.0, value))
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def _byte(value: float) -> str:
    return f"{math.floor(_gamma(value) * 255 + 0.5):02x}"


def _six_digits(value: Any) -> str:
    text = value.strip().lower() if isinstance(value, str) else ""
    if len(text) == 7 and text[0] == "#" and all(c in "0123456789abcdef" for c in text[1:]):
        return text
    if len(text) == 4 and text[0] == "#" and all(c in "0123456789abcdef" for c in text[1:]):
        return "#" + "".join(c * 2 for c in text[1:])
    return _FALLBACK_ACCENT


def _to_oklab(hex_value: str) -> tuple[float, float, float]:
    r, g, b = (_linear(int(hex_value[i:i + 2], 16)) for i in (1, 3, 5))
    l_ = math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b)
    m_ = math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b)
    s_ = math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b)
    return (
        0.2104542553 * l_ + 0.793617785 * m_ - 0.0040720468 * s_,
        1.9779984951 * l_ - 2.428592205 * m_ + 0.4505937099 * s_,
        0.0259040371 * l_ + 0.7827717662 * m_ - 0.808675766 * s_,
    )


def _from_oklch(lightness: float, chroma: float, hue: float) -> str:
    c = chroma
    while c > 0:
        a = c * math.cos(math.radians(hue))
        b = c * math.sin(math.radians(hue))
        l_ = (lightness + 0.3963377774 * a + 0.2158037573 * b) ** 3
        m_ = (lightness - 0.1055613458 * a - 0.0638541728 * b) ** 3
        s_ = (lightness - 0.0894841775 * a - 1.291485548 * b) ** 3
        rgb = (
            4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_,
            -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_,
            -0.0041960863 * l_ - 0.7034186147 * m_ + 1.707614701 * s_,
        )
        if all(-1e-4 <= v <= 1 + 1e-4 for v in rgb):
            return "#" + "".join(_byte(v) for v in rgb)
        c -= 0.004
    grey = _byte(lightness ** 3)
    return f"#{grey}{grey}{grey}"


INK_TONES = {
    "#14110c": ("#14110c", "#14110c", "#14110c"),
    "#f3efe6": ("#f3efe6", "#f3efe6", "#f3efe6"),
    "#7a7468": ("#7a7468", "#7a7468", "#7a7468"),
}


def fold_tones(accent: Any) -> tuple[str, str, str]:
    base = _six_digits(accent)
    if base in INK_TONES:
        return INK_TONES[base]
    lightness, a, b = _to_oklab(base)
    chroma = math.hypot(a, b)
    hue = (math.degrees(math.atan2(b, a)) + 360) % 360
    return (
        _from_oklch(min(lightness + 0.11, 0.97), chroma * 0.82, hue),
        base,
        _from_oklch(max(lightness - 0.15, 0.05), chroma * 0.95, hue),
    )


def _inside(x: float, y: float, polygon: tuple[tuple[float, float], ...]) -> bool:
    hit = False
    j = len(polygon) - 1
    for i, (xi, yi) in enumerate(polygon):
        xj, yj = polygon[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            hit = not hit
        j = i
    return hit


def _sample(facets, tones: tuple[str, str, str], x: float, y: float) -> str | None:
    colour = None
    for tone, points in facets:
        if _inside(x, y, points):
            colour = tones[tone]
    return colour


def grid(fold: str, accent: Any, rows: int = DEFAULT_ROWS) -> list[list[tuple[str | None, str | None]]]:
    facets = SHAPES[fold]
    tones = fold_tones(accent)
    size = rows * 2
    step = 100 / size
    out = []
    for row in range(rows):
        line = []
        for col in range(size):
            x = (col + 0.5) * step
            top = _sample(facets, tones, x, (row * 2 + 0.5) * step)
            bottom = _sample(facets, tones, x, (row * 2 + 1.5) * step)
            line.append((top, bottom))
        out.append(line)
    return out


def art(fold: str, accent: Any, rows: int = DEFAULT_ROWS) -> Text:
    text = Text(no_wrap=True, overflow="ignore")
    for index, line in enumerate(grid(fold, accent, rows)):
        if index:
            text.append("\n")
        for top, bottom in line:
            if top and bottom:
                text.append("▀", style=f"{top} on {bottom}")
            elif top:
                text.append("▀", style=top)
            elif bottom:
                text.append("▄", style=bottom)
            else:
                text.append(" ")
    return text


def glyph(fold: str) -> str:
    return GLYPHS.get(fold, FALLBACK_GLYPH)


def beside(picture: Text, lines: list[Text], gap: int = 2) -> Text:
    rows = picture.split("\n")
    width = max((row.cell_len for row in rows), default=0)
    offset = max(0, (len(rows) - len(lines)) // 2)
    out = Text(no_wrap=True, overflow="ignore")
    for index, row in enumerate(rows):
        if index:
            out.append("\n")
        out.append_text(row)
        out.append(" " * (width - row.cell_len))
        extra = index - offset
        if 0 <= extra < len(lines):
            out.append(" " * gap)
            out.append_text(lines[extra])
    return out


def supports_fold_art(stream: TextIO | None = None, env: Mapping[str, str] | None = None) -> bool:
    env = os.environ if env is None else env
    stream = sys.stdout if stream is None else stream
    if env.get("NO_COLOR") or env.get("TERM", "").lower() == "dumb":
        return False
    if env.get("COLORTERM", "").lower() not in {"truecolor", "24bit"}:
        return False
    locale = env.get("LC_ALL") or env.get("LC_CTYPE") or env.get("LANG") or ""
    if locale and "utf" not in locale.lower():
        return False
    encoding = (getattr(stream, "encoding", "") or "").lower().replace("-", "").replace("_", "")
    if encoding != "utf8":
        return False
    try:
        return bool(stream.isatty())
    except (AttributeError, ValueError):
        return False


def identity(home: Path | str | None, tui: dict[str, Any] | None) -> tuple[str, str]:
    accent = palette.profile_accent(tui)
    if home is not None and appearance.is_default(home):
        return palette.ALPACA_FOLD, palette.BRAND_INK["dark" if palette.is_dark(tui) else "light"]
    return appearance.current(tui)[0], accent


def marker(home: Path | str | None, tui: dict[str, Any] | None, **support: Any) -> tuple[str, str]:
    fold, accent = identity(home, tui)
    shown = glyph(fold) if supports_fold_art(**support) else FALLBACK_GLYPH
    return shown, accent
