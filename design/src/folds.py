import json
import math
import os
import re
import subprocess
from functools import lru_cache

ALPACA_SVG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "site", "assets", "alpi-black.svg")
LIGHT, BASE, SHADE = 0, 1, 2
ALPACA_TONES = [BASE, SHADE, LIGHT, SHADE, SHADE, BASE, LIGHT, BASE, SHADE, LIGHT, LIGHT, BASE]


def _hex(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _lin(v):
    v /= 255
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def _gamma(v):
    v = max(0.0, min(1.0, v))
    return 12.92 * v if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055


def to_oklab(h):
    r, g, b = (_lin(x) for x in _hex(h))
    l = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    return (0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
            1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
            0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s)


def _linear_rgb(L, a, b):
    l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    return (4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
            -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
            -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s)


def oklch(L, C, h):
    while C > 0:
        a, b = C * math.cos(math.radians(h)), C * math.sin(math.radians(h))
        rgb = _linear_rgb(L, a, b)
        if all(-1e-4 <= v <= 1 + 1e-4 for v in rgb):
            return "#%02x%02x%02x" % tuple(round(_gamma(v) * 255) for v in rgb)
        C -= 0.004
    v = round(_gamma(L ** 3) * 255)
    return "#%02x%02x%02x" % (v, v, v)


def lch(h):
    L, a, b = to_oklab(h)
    return L, math.hypot(a, b), math.degrees(math.atan2(b, a)) % 360


def delta_e(a, b):
    return math.dist(to_oklab(a), to_oklab(b))


def tones(accent):
    ink = _COMMON["ink"].get(accent.lower())
    if ink:
        return {LIGHT: ink[0], BASE: ink[1], SHADE: ink[2]}
    L, C, h = lch(accent)
    return {LIGHT: oklch(min(L + 0.11, 0.97), C * 0.82, h), BASE: accent, SHADE: oklch(max(L - 0.15, 0.05), C * 0.95, h)}


def luminance(h):
    r, g, b = (_lin(v) for v in _hex(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


HUES = [("rose", 8), ("vermilion", 32), ("orange", 55), ("amber", 82), ("lime", 125), ("green", 153), ("teal", 196), ("sky", 222), ("blue", 245), ("indigo", 275), ("violet", 305), ("magenta", 350)]
BATH = {"rose": (0.70, 0.17), "vermilion": (0.66, 0.19), "orange": (0.73, 0.16), "amber": (0.81, 0.15), "lime": (0.78, 0.17), "green": (0.72, 0.16),
        "teal": (0.70, 0.11), "sky": (0.78, 0.13), "blue": (0.66, 0.14), "indigo": (0.60, 0.17), "violet": (0.60, 0.19), "magenta": (0.64, 0.20)}


def palette(kind):
    out = []
    for name, hue in HUES:
        L, C = BATH[name]
        if kind == "soft":
            L, C = (0.86 if name in ("amber", "lime") else 0.80), 0.10
        elif kind == "deep":
            L, C = (0.72 if name in ("amber", "lime", "orange") else 0.54), 0.16
        out.append((name, "#f0b447" if (name == "amber" and kind == "bath") else oklch(L, C, hue)))
    return out


def inset(pts, d):
    n = len(pts)
    area = sum(pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1] for i in range(n))
    sign = 1 if area > 0 else -1
    lines = []
    for i in range(n):
        (x1, y1), (x2, y2) = pts[i], pts[(i + 1) % n]
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy) or 1
        nx, ny = -dy / length * sign, dx / length * sign
        lines.append((x1 + nx * d, y1 + ny * d, dx, dy))
    out = []
    for i in range(n):
        px, py, ax, ay = lines[i - 1]
        qx, qy, bx, by = lines[i]
        det = ax * by - ay * bx
        if abs(det) < 1e-9:
            out.append(pts[i])
            continue
        t = ((qx - px) * by - (qy - py) * bx) / det
        x, y = px + ax * t, py + ay * t
        vx, vy = x - pts[i][0], y - pts[i][1]
        if math.hypot(vx, vy) > 3 * d:
            k = 3 * d / math.hypot(vx, vy)
            x, y = pts[i][0] + vx * k, pts[i][1] + vy * k
        out.append((x, y))
    return out


COMMON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "common")


def _load_common():
    script = (
        f"import {{FOLDS, FOLD_IDS, FOLD_MODELS, INK_TONES}} from {json.dumps(os.path.join(COMMON, 'folds.mjs'))};"
        "const shapes = {}; for (const id of Object.keys(FOLDS)) shapes[id] = FOLDS[id]();"
        "process.stdout.write(JSON.stringify({shapes, ids: FOLD_IDS, models: FOLD_MODELS, ink: INK_TONES}));"
    )
    try:
        out = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True, check=True)
    except FileNotFoundError:
        raise SystemExit("design/build.py needs node on PATH to read the shared folds in common/")
    return json.loads(out.stdout)


_COMMON = _load_common()
SHAPE_ORDER = list(_COMMON["ids"])
MODELS = dict(_COMMON["models"])
MAX_FACETS = 6
MIN_ASPECT = 0.8
_SHAPES = _COMMON["shapes"]
SHAPES = {name: (lambda name=name: [([tuple(p) for p in f["points"]], f["tone"]) for f in _SHAPES[name]]) for name in _SHAPES}


def alpaca_facets():
    with open(ALPACA_SVG) as f:
        svg = f.read()
    polys = []
    for d in re.findall(r'<path d="([^"]+)"', svg):
        polys.append([tuple(float(v) for v in pair.split(",")) for pair in re.findall(r"[\d.]+,[\d.]+", d)])
    xs = [p[0] for pts in polys for p in pts]
    ys = [p[1] for pts in polys for p in pts]
    x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    scale = 100 / (y1 - y0)
    ox = (100 - (x1 - x0) * scale) / 2
    return [([((x - x0) * scale + ox, (y - y0) * scale) for x, y in pts], ALPACA_TONES[i % len(ALPACA_TONES)]) for i, pts in enumerate(polys)]


def normalise(shapes, fill=94):
    pts = [p for poly, _ in shapes for p in poly]
    x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
    y0, y1 = min(p[1] for p in pts), max(p[1] for p in pts)
    k = fill / max(x1 - x0, y1 - y0)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    return [([(50 + (x - cx) * k, 50 + (y - cy) * k) for x, y in poly], tone) for poly, tone in shapes]


@lru_cache(maxsize=None)
def low_facets():
    script = (
        f"import {{foldFacets}} from {json.dumps(os.path.join(COMMON, 'folds.mjs'))};"
        "process.stdout.write(JSON.stringify(foldFacets('alpaca-low')));"
    )
    out = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True, check=True)
    return [([tuple(p) for p in f["points"]], f["tone"]) for f in json.loads(out.stdout)]


def facets(form, fit=True):
    if form == "alpaca":
        return alpaca_facets()
    if form == "alpaca-low":
        return low_facets()
    shapes = SHAPES[form]()
    return normalise(shapes) if fit else shapes


def gap_for(form, size):
    return 0.0 if form in ("alpaca", "alpaca-low") else max(1.1, 30 / size)


def _poly(pts, fill, extra=""):
    return '<polygon points="%s" fill="%s"%s/>' % (" ".join("%.1f,%.1f" % p for p in pts), fill, extra)


def fold_body(form, accent, size=64, facet_attrs=None, fit=True):
    palette = tones(accent)
    shapes = facets(form, fit)
    gap = gap_for(form, size)
    parts = []
    for i, (pts, tone) in enumerate(shapes):
        poly = inset(pts, gap) if gap else pts
        parts.append(_poly(poly, palette[tone], facet_attrs(i, len(shapes), tone) if facet_attrs else ""))
    return "".join(parts)


def fold(form, accent, size=64, facet_attrs=None, extra="", fit=True):
    return (f'<svg viewBox="0 0 100 100" width="{size}" height="{size}" role="img" aria-label="{form}" '
            f'style="flex-shrink: 0; display: block"{extra}>{fold_body(form, accent, size, facet_attrs, fit)}</svg>')


def flat(accent, size=64, creases=True):
    t = tones(accent)
    parts = [f'<rect x="8" y="8" width="84" height="84" rx="2" fill="{t[LIGHT]}"/>']
    if creases:
        for x1, y1, x2, y2 in ((8, 8, 92, 92), (92, 8, 8, 92), (50, 8, 50, 92), (8, 50, 92, 50)):
            parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{accent}" stroke-width="1.2" stroke-dasharray="3 2.4" opacity="0.9"/>')
    return f'<svg viewBox="0 0 100 100" width="{size}" height="{size}" role="img" aria-label="flat sheet" style="flex-shrink: 0; display: block">{"".join(parts)}</svg>'


def outline(form, color, size=64):
    parts = []
    gap = gap_for(form, size)
    for pts, _ in facets(form):
        poly = inset(pts, gap) if gap else pts
        parts.append('<polygon points="%s" fill="none" stroke="%s" stroke-width="1.6" stroke-linejoin="round" stroke-dasharray="3 2.4"/>' % (" ".join("%.1f,%.1f" % p for p in poly), color))
    return f'<svg viewBox="0 0 100 100" width="{size}" height="{size}" role="img" aria-label="{form} unfolded" style="flex-shrink: 0; display: block">{"".join(parts)}</svg>'


def sweep_style(prefix, accent, seconds):
    t = tones(accent)
    frames = f"0%{{fill: {t[LIGHT]}}}33%{{fill: {t[BASE]}}}66%{{fill: {t[SHADE]}}}100%{{fill: {t[LIGHT]}}}"
    return (f"<style>@keyframes {prefix}{{{frames}}}.{prefix}-f{{animation: {prefix} {seconds}s linear infinite}}"
            f"@media (prefers-reduced-motion: reduce){{.{prefix}-f{{animation: none}}}}</style>")


def sweep_attrs(prefix, seconds):
    return lambda i, n, tone: f' class="{prefix}-f" style="animation-delay: {-(i / n) * seconds:.2f}s"'




def pulsing(inner):
    return f'<span class="fold-pulse" style="display: inline-flex">{inner}</span>'




def copies(form, accent, size=16, n=3):
    offset = round(size * 0.24)
    layers = []
    for i in range(n - 1, -1, -1):
        opacity = (1.0, 0.5, 0.28)[i]
        layers.append(f'<span style="position: absolute; left: {i * offset}px; top: {-i * round(size * 0.06)}px; opacity: {opacity}; display: block">{fold(form, accent, size)}</span>')
    pad = round(size * 0.06) * (n - 1)
    return (f'<span style="position: relative; display: inline-block; width: {size + (n - 1) * offset}px; height: {size}px; margin-top: {pad}px; flex-shrink: 0">{"".join(layers)}</span>')





BREATHE_STYLE = ("<style>@keyframes unit-ripple{0%,100%{opacity: 1}35%{opacity: 0.4}}"
                 ".unit-breathe{animation: unit-ripple 1.8s ease-in-out infinite}"
                 "@media (prefers-reduced-motion: reduce){.unit-breathe{animation: none}}</style>")


def breathe_attrs(i, n, tone):
    return f' class="unit-breathe" style="animation-delay: {-(i / n) * 1.8:.2f}s"'


@lru_cache(maxsize=None)
def crease_tones(accent, ground):
    script = (
        f"import {{creaseTones}} from {json.dumps(os.path.join(COMMON, 'crease.mjs'))};"
        f"process.stdout.write(JSON.stringify(creaseTones({json.dumps(accent)}, {json.dumps(ground)})));"
    )
    out = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True, check=True)
    return tuple(json.loads(out.stdout))


def _rotate(pts, deg, centre=(50, 50)):
    c, sn = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return [(centre[0] + (x - centre[0]) * c - (y - centre[1]) * sn, centre[1] + (x - centre[0]) * sn + (y - centre[1]) * c) for x, y in pts]


def _near(point, poly, tol):
    px, py = point
    n = len(poly)
    for i in range(n):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % n]
        dx, dy = x2 - x1, y2 - y1
        t = 0 if dx == dy == 0 else max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
        if math.hypot(px - (x1 + t * dx), py - (y1 + t * dy)) <= tol:
            return True
    return False


def _inside(pt, poly):
    x, y = pt
    hit = False
    n = len(poly)
    for i in range(n):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            hit = not hit
    return hit


def four_fold_chiral(form):
    pts = lambda shapes: {(round(x), round(y)) for poly, _ in shapes for x, y in poly}
    base = SHAPES[form]()
    original = pts(base)
    rotated = pts([(_rotate(poly, 90), tone) for poly, tone in base])
    mirrored = pts([([(100 - x, y) for x, y in poly], tone) for poly, tone in base])
    return original == rotated and original != mirrored


def one_piece(form, tol=1.5):
    polys = [poly for poly, _ in SHAPES[form]()]
    seen, todo = {0}, [0]
    while todo:
        i = todo.pop()
        for j in range(len(polys)):
            if j not in seen and (any(_near(p, polys[j], tol) for p in polys[i]) or any(_near(p, polys[i], tol) for p in polys[j])):
                seen.add(j)
                todo.append(j)
    return len(seen) == len(polys)
