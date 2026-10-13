from __future__ import annotations

import json
import math
import re
import sys
import unicodedata
from decimal import ROUND_HALF_UP, Decimal, localcontext
from typing import Any

# Mirrored by common/chartSpec.mjs; common/chartSpec.fixtures.mjs holds the corpus both test against.
CHART_TYPES = ("line", "bar")
MAX_SERIES = 4
MAX_POINTS = {"line": 60, "bar": 24}
MAX_TEXT = 80

_SPARK = "▁▂▃▄▅▆▇█"
_EIGHTHS = " ▏▎▍▌▋▊▉"
_STACK_FILL = ("█", "▓", "▒", "░")
_FENCE_RE = re.compile(r"^([ \t]*)```chart(?:[ \t][^\n]*)?\n(.*?)\n[ \t]*```[ \t]*$", re.M | re.S)
_SPACE_RE = re.compile("[ \t\n\r\f\v\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+")
_SUFFIXES = ((1e9, "B", 1e9), (1e6, "M", 1e6), (1e4, "k", 1e3))


def _is_number(value: Any) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return math.isfinite(value) if isinstance(value, float) else abs(value) <= sys.float_info.max


def _is_text(value: Any) -> bool:
    return isinstance(value, str) or _is_number(value)


def _number_text(value: float) -> str:
    number = float(value)
    if number == 0:
        return "0"
    if 1e-6 <= abs(number) < 1e21:
        text = format(Decimal(repr(number)), "f")
        return text.rstrip("0").rstrip(".") if "." in text else text
    return re.sub(r"e([+-])0*(\d)", r"e\1\2", repr(number))


def _squash(text: str) -> str:
    return _SPACE_RE.sub(" ", text).removeprefix(" ").removesuffix(" ")


def _text(value: Any) -> str:
    return _squash(_squash(value if isinstance(value, str) else _number_text(value))[:MAX_TEXT])


def _reject_constant(name: str) -> Any:
    raise ValueError(name)


def parse_chart(source: Any) -> dict[str, Any] | None:
    try:
        raw = json.loads(source, parse_constant=_reject_constant) if isinstance(source, str) else source
    except ValueError:
        return None
    if not isinstance(raw, dict) or raw.get("type") not in CHART_TYPES:
        return None
    kind = raw["type"]
    x = raw.get("x")
    if not isinstance(x, list) or not x or len(x) > MAX_POINTS[kind] or not all(_is_text(v) for v in x):
        return None
    if kind == "line" and len(x) < 2:
        return None
    raw_series = raw.get("series")
    if not isinstance(raw_series, list) or not raw_series or len(raw_series) > MAX_SERIES:
        return None
    stacked = raw.get("stacked") is True
    series = []
    for s in raw_series:
        values = s.get("values") if isinstance(s, dict) else None
        if not isinstance(values, list) or len(values) != len(x):
            return None
        if not all(v is None or _is_number(v) for v in values) or all(v is None for v in values):
            return None
        if stacked and kind == "bar" and any(v is not None and v < 0 for v in values):
            return None
        series.append({"name": _text(s["name"]) if _is_text(s.get("name")) else "", "values": list(values)})
    if stacked and kind == "bar" and not all(math.isfinite(sum(float(s["values"][i] or 0) for s in series)) for i in range(len(x))):
        return None
    return {
        "type": kind,
        "stacked": kind == "bar" and stacked and len(series) > 1,
        "title": _text(raw["title"]) if _is_text(raw.get("title")) else "",
        "unit": _text(raw["unit"]) if _is_text(raw.get("unit")) else "",
        "x": [_text(v) for v in x],
        "series": series,
    }


def _round(value: float, digits: int) -> str:
    text = f"{Decimal(repr(float(value))).quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP):,f}"
    return text.rstrip("0").rstrip(".") if "." in text else text


def _exponent(value: float) -> str:
    with localcontext() as context:
        context.prec = 800
        exact = Decimal(value)
        power = exact.adjusted()
        mantissa = exact.scaleb(-power).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        if abs(mantissa) >= 10:
            mantissa, power = (mantissa / 10).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP), power + 1
    return f"{mantissa}e{'+' if power >= 0 else '-'}{abs(power)}"


def _number(value: float) -> str:
    value = float(value)
    magnitude = abs(value)
    if magnitude == 0:
        return "0"
    if magnitude >= 1e15 or magnitude < 1e-6:
        return _exponent(value)
    for at, suffix, divisor in _SUFFIXES:
        if magnitude >= at:
            return _round(value / divisor, 1) + suffix
    if magnitude < 1:
        exponent = Decimal(repr(float(value))).adjusted()
        return _round(value, 1 - exponent)
    return _round(value, 0 if magnitude >= 100 else 1 if magnitude >= 10 else 2)


def format_value(value: float | None, unit: str = "") -> str:
    if value is None or not math.isfinite(float(value)):
        return "—"
    text = _number(0 if value == 0 else value)
    if not unit:
        return text
    if unit == "%":
        return f"{text}%"
    return f"{unit}{text}" if unit in ("$", "€", "£", "¥") else f"{text} {unit}"


def _spark(values: list[float | None], lo: float, hi: float) -> str:
    span = (hi - lo) or 1
    return "".join(" " if v is None else _SPARK[min(len(_SPARK) - 1, int((v - lo) / span * (len(_SPARK) - 1) + 0.5))] for v in values)


def _bar(value: float, top: float, width: int) -> str:
    if top <= 0 or value <= 0:
        return ""
    eighths = round(value / top * width * 8)
    full, rest = divmod(eighths, 8)
    return "█" * full + (_EIGHTHS[rest] if rest else "")


def _width(text: str) -> int:
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 0 if unicodedata.combining(ch) else 1 for ch in text)


def _pad(text: str, width: int) -> str:
    return text + " " * max(width - _width(text), 0)


def inline_unit(unit: str) -> str:
    return unit if unit == "%" or unit in ("$", "€", "£", "¥") else ""


def render_text(spec: dict[str, Any], width: int = 24) -> str:
    unit = inline_unit(spec["unit"])
    said = bool(spec["unit"]) and re.search(rf"(?<![^\W_]){re.escape(spec['unit'])}(?![^\W_])", spec["title"], re.I) is not None
    caption = " · ".join(part for part in (spec["title"], "" if unit or said else spec["unit"]) if part)
    lines = [caption] if caption else []
    if spec["type"] == "line":
        numbers = [v for s in spec["series"] for v in s["values"] if v is not None]
        lo, hi = min(numbers), max(numbers)
        span = f'{spec["x"][0]} – {spec["x"][-1]}'
        names = [s["name"] or f"Series {i + 1}" for i, s in enumerate(spec["series"])]
        pad = max(_width(n) for n in names) if len(names) > 1 else 0
        for name, s in zip(names, spec["series"]):
            vals = [v for v in s["values"] if v is not None]
            head = f"{_pad(name, pad)}  " if pad else ""
            lines.append(f'{head}{_spark(s["values"], lo, hi)}  {format_value(vals[0], unit)} → {format_value(vals[-1], unit)}')
        lines.append(f"{span} · {format_value(lo, unit)} – {format_value(hi, unit)}")
        return "\n".join(lines)
    labels = [label if len(label) <= 24 else label[:23] + "…" for label in spec["x"]]
    pad = max(_width(label) for label in labels)
    if spec["stacked"]:
        totals = [sum(float(max(s["values"][i] or 0, 0)) for s in spec["series"]) for i in range(len(labels))]
        top = max(totals)
        for i, label in enumerate(labels):
            cells = "".join(_STACK_FILL[n] * round((max(s["values"][i] or 0, 0) / top) * width if top else 0) for n, s in enumerate(spec["series"]))
            lines.append(f"{_pad(label, pad)}  {cells.ljust(width)}  {format_value(totals[i], unit)}")
        lines.append("  ".join(f"{_STACK_FILL[n]} {s['name'] or f'Series {n + 1}'}" for n, s in enumerate(spec["series"])))
        return "\n".join(lines)
    top = max((v for s in spec["series"] for v in s["values"] if v is not None), default=0)
    for n, s in enumerate(spec["series"]):
        if len(spec["series"]) > 1:
            lines.append(s["name"] or f"Series {n + 1}")
        for label, v in zip(labels, s["values"]):
            lines.append(f"{_pad(label, pad)}  {_bar(v or 0, top, width).ljust(width)}  {format_value(v, unit)}")
    return "\n".join(lines)


def textify(markdown: str) -> str:
    def swap(m: re.Match) -> str:
        spec = parse_chart(m.group(2))
        if not spec:
            return m.group(0)
        indent = m.group(1)
        return "\n".join(indent + line for line in ["````text", *render_text(spec).split("\n"), "````"])

    return _FENCE_RE.sub(swap, (markdown or "").replace("\r\n", "\n"))
