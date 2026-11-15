from __future__ import annotations

import math
import os
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any, TextIO

from rich.text import Text

from alpi import appearance, mark_shapes, palette

FALLBACK_GLYPH = "◆"
FALLBACK_INACTIVE = "◇"
DEFAULT_ROWS = 8
BANNER_ROWS = 6
TWIN = "alpi-twin"
TWIN_SMALL = "alpi-twin-small"
TWIN_SMALL_BELOW = 24
SUBSAMPLES = 4
FILL_COVER = 0.5

SHAPE_GLYPHS = {
    "round": "⬤",
    "squircle": "⯀",
    "drop": "⧫",
    "dome": "⯊",
    "pill": "⬮",
    "clover": "✤",
    "cloud": "ɷ",
    "bean": "◗",
    "pebble": "⬬",
    "arch": "⋂",
    "heart": "❥",
    "bell": "⍾",
}
GLYPHS = {
    **SHAPE_GLYPHS,
    palette.WORKGROUP_SHAPE: "⬢",
    palette.TWIN_SHAPE: "⍥",
}

_FALLBACK_ACCENT = "#f0b447"
NAME_MIN_CONTRAST = 4.5
NAME_STEP = 0.12
_NAME_NUDGE = 0.02
MARK_EYE_FLOOR = 3
MARK_STEP = 0.01


def _linear(value: int) -> float:
    v = value / 255
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def _gamma(value: float) -> float:
    c = max(0.0, min(1.0, value))
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def _byte(value: float) -> str:
    return f"{math.floor(_gamma(value) * 255 + 0.5):02x}"


def _hex_or_none(value: Any) -> str | None:
    text = value.strip().lower() if isinstance(value, str) else ""
    if len(text) == 7 and text[0] == "#" and all(c in "0123456789abcdef" for c in text[1:]):
        return text
    if len(text) == 4 and text[0] == "#" and all(c in "0123456789abcdef" for c in text[1:]):
        return "#" + "".join(c * 2 for c in text[1:])
    return None


def _six_digits(value: Any) -> str:
    return _hex_or_none(value) or _FALLBACK_ACCENT


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


def shift_lightness(value: Any, delta: float) -> str:
    lightness, a, b = _to_oklab(_six_digits(value))
    chroma = math.hypot(a, b)
    hue = (math.degrees(math.atan2(b, a)) + 360) % 360
    return _from_oklch(min(0.98, max(0.04, lightness + delta)), chroma * (0.85 if delta > 0 else 0.95), hue)


def luminance(hex_value: str) -> float:
    r, g, b = (_linear(int(hex_value[i:i + 2], 16)) for i in (1, 3, 5))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a: str, b: str) -> float:
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def name_tone(accent: Any, ground: Any) -> str | None:
    accent_hex, ground_hex = _hex_or_none(accent), _hex_or_none(ground)
    if not accent_hex or not ground_hex or accent.strip() != accent or ground.strip() != ground:
        return None
    direction = -1 if luminance(ground_hex) > 0.2 else 1
    delta = NAME_STEP
    while delta < 1:
        tone = shift_lightness(accent_hex, direction * delta)
        if contrast_ratio(tone, ground_hex) >= NAME_MIN_CONTRAST:
            return tone
        delta += _NAME_NUDGE
    return "#141414" if direction < 0 else "#ffffff"


def tone_against(accent: str, ground: str, floor: float) -> str:
    direction = -1 if luminance(ground) > 0.2 else 1
    delta, tone = 0.0, accent
    while contrast_ratio(tone, ground) < floor and delta < 1:
        delta = round(delta + MARK_STEP, 2)
        tone = shift_lightness(accent, direction * delta)
    return tone


def mark_tone(accent: Any, theme: str) -> Any:
    hex_value = accent.lower() if isinstance(accent, str) and len(accent) == 7 and _hex_or_none(accent) else None
    if theme != "light" or not hex_value:
        return accent
    tone = tone_against(hex_value, palette.EYE_INK["light"], MARK_EYE_FLOOR)
    return accent if tone == hex_value else tone


def body_colour(accent: Any, tui: dict[str, Any] | None) -> Any:
    return mark_tone(accent, "dark" if palette.is_dark(tui) else "light")


def name_colour(accent: Any, tui: dict[str, Any] | None) -> str:
    ground = (palette.DARK if palette.is_dark(tui) else palette.LIGHT)["bg"]
    return name_tone(accent, ground) or _six_digits(accent)


def outline_of(shape: str, size: float = 2 * DEFAULT_ROWS) -> str:
    if shape == palette.TWIN_SHAPE:
        return TWIN_SMALL if size < TWIN_SMALL_BELOW else TWIN
    return palette.resolve_shape(shape)


def eye_pair(name: str, size: float, key: tuple | None = None) -> tuple[tuple[tuple[float, float], ...], ...]:
    gx, gy, left, right = key or mark_shapes.STILL["idle"]
    eye_x, eye_y, eye_dx = mark_shapes.EYES[name]
    reach = 0.7 if size < mark_shapes.SMALL else 1
    grow = min(mark_shapes.EYE_CAP, max(1, mark_shapes.EYE_MIN_PX * 50 / (mark_shapes.EYE_PILL_HALF * size)))
    gap = max(3, mark_shapes.EYE_GAP_PX * 100 / size) / 2
    eyes = []
    for side, (expression, stretch, dy) in ((-1, left), (1, right)):
        points = mark_shapes.EXPRESSIONS[expression]
        inner = -min(x for x, _ in points)
        scale = min(grow * stretch, (eye_dx - gap) / inner) if inner > 0 else grow * stretch
        x0 = eye_x + reach * gx + side * eye_dx
        y0 = eye_y + reach * (gy + dy)
        eyes.append(tuple((x0 + side * x * scale, y0 + y * scale) for x, y in points))
    return tuple(eyes)


def honeycomb_cells(size: float) -> dict[str, tuple[tuple[float, float], ...]]:
    want = round(max(mark_shapes.WG_GAP, mark_shapes.WG_GAP_PX * 100 / size), 1)
    gap = min(mark_shapes.HONEYCOMB, key=lambda g: abs(g - want))
    return mark_shapes.HONEYCOMB[gap]


def coverage(polygons, size: int) -> list[list[float]]:
    cover = [[0.0] * size for _ in range(size)]
    unit = 100 / size
    edges = [
        (polygon[i - 1], polygon[i]) for polygon in polygons for i in range(len(polygon))
    ]
    share = 1 / SUBSAMPLES
    for row in range(size):
        line = cover[row]
        for sub in range(SUBSAMPLES):
            y = (row + (sub + 0.5) * share) * unit
            xs = sorted(
                x0 + (y - y0) * (x1 - x0) / (y1 - y0)
                for (x0, y0), (x1, y1) in edges
                if (y0 > y) != (y1 > y)
            )
            for start, end in zip(xs[::2], xs[1::2]):
                a, b = max(0.0, start / unit), min(float(size), end / unit)
                col = int(a)
                while col < size and col < b:
                    line[col] += (min(b, col + 1) - max(a, col)) * share
                    col += 1
    return cover


def _snap(value: float) -> int:
    return math.floor(value + 0.5)


def eye_cells(name: str, size: int) -> list[tuple[int, int]]:
    unit = size / 100
    boxes = []
    for eye in eye_pair(name, size):
        xs, ys = [x * unit for x, _ in eye], [y * unit for _, y in eye]
        boxes.append((min(xs), max(xs), min(ys), max(ys)))
    centres = [(x0 + x1) / 2 for x0, x1, _, _ in boxes]
    apart = centres[1] - centres[0]
    width = max(1, min(_snap(max(x1 - x0 for x0, x1, _, _ in boxes)), math.floor(apart - 1)))
    gap = max(1, _snap(apart - width))
    left = _snap(sum(centres) / 2 - (2 * width + gap) / 2)
    cells = []
    for start, (_, _, y0, y1) in zip((left, left + width + gap), boxes):
        height = max(2, _snap(y1 - y0))
        top = _snap((y0 + y1) / 2 - height / 2)
        cells += [(r, c) for r in range(top, top + height) for c in range(start, start + width)]
    return [(r, c) for r, c in cells if 0 <= r < size and 0 <= c < size]


def _solid(polygons, size: int) -> list[list[bool]]:
    filled = [[value >= FILL_COVER for value in line] for line in coverage(polygons, size)]

    def neighbour(r: int, c: int) -> bool:
        return any(
            0 <= r + dr < size and 0 <= c + dc < size and filled[r + dr][c + dc]
            for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1))
        )

    return [[filled[r][c] and neighbour(r, c) for c in range(size)] for r in range(size)]


def _eyes(shape: str, size: int) -> set[tuple[int, int]]:
    if shape == palette.WORKGROUP_SHAPE:
        return set()
    return set(eye_cells(outline_of(shape, size), size))


def mask(shape: str, rows: int = DEFAULT_ROWS) -> list[list[bool]]:
    size = rows * 2
    if shape == palette.WORKGROUP_SHAPE:
        return _solid(list(honeycomb_cells(size).values()), size)
    filled = _solid([mark_shapes.OUTLINES[outline_of(shape, size)]], size)
    for r, c in _eyes(shape, size):
        filled[r][c] = False
    return filled


def grid(shape: str, accent: Any, rows: int = DEFAULT_ROWS, eye: Any = None) -> list[list[tuple[str | None, str | None]]]:
    colour = _six_digits(accent)
    eye_hex = _hex_or_none(eye)
    pixels = mask(shape, rows)
    eyes = _eyes(shape, rows * 2) if eye_hex else set()

    def paint(r: int, c: int) -> str | None:
        if pixels[r][c]:
            return colour
        return eye_hex if (r, c) in eyes else None

    return [
        [(paint(row * 2, c), paint(row * 2 + 1, c)) for c in range(len(pixels[row * 2]))]
        for row in range(rows)
    ]


def art(shape: str, accent: Any, rows: int = DEFAULT_ROWS, eye: Any = None) -> Text:
    text = Text(no_wrap=True, overflow="ignore")
    for index, line in enumerate(grid(shape, accent, rows, eye)):
        if index:
            text.append("\n")
        for top, bottom in line:
            if top and bottom:
                text.append("█" if top == bottom else "▀", style=top if top == bottom else f"{top} on {bottom}")
            elif top:
                text.append("▀", style=top)
            elif bottom:
                text.append("▄", style=bottom)
            else:
                text.append(" ")
    return text


def glyph(shape: str) -> str:
    return GLYPHS.get(shape, FALLBACK_GLYPH)


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
        return palette.TWIN_SHAPE, palette.BRAND_INK["dark" if palette.is_dark(tui) else "light"]
    return appearance.current(tui)[0], accent


def marker(home: Path | str | None, tui: dict[str, Any] | None, **support: Any) -> tuple[str, str]:
    shape, accent = identity(home, tui)
    shown = glyph(shape) if supports_fold_art(**support) else FALLBACK_GLYPH
    return shown, accent
