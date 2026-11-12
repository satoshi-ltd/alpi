import hashlib
import json
import math
import os
import subprocess
from functools import lru_cache

import folds

INK_EYE = "#14110c"
PAPER_EYE = "#fffaf0"
EYE_CONTRAST = 4.5
SMALL_MAX = 32
ACCESSORY_MIN = 24
LIGHT_GROUNDS = ("#ffffff", "#f6f6f6", "#f4f4f4", "#f0f0f0")
DARK_GROUNDS = ("#0b0b0b", "#0f0f0f", "#151515", "#202020")

PALETTE = [
    ("amber", "#b87d08"), ("orange", "#d86a05"), ("vermilion", "#f15233"), ("rose", "#ef4c79"),
    ("magenta", "#e052ac"), ("violet", "#ad68ef"), ("indigo", "#7a79fd"), ("blue", "#088ced"),
    ("sky", "#0f93c4"), ("teal", "#079a8c"), ("green", "#009e48"), ("lime", "#71950d"),
]
COLOUR = dict(PALETTE)

STATES = ("idle", "working", "needs", "failed", "paused", "no-provider", "offline")
STATE_LABEL = {"idle": "idle", "working": "working", "needs": "needs you", "failed": "failed", "paused": "paused", "no-provider": "no provider", "offline": "offline"}
EYE_STYLES = ("oval", "bead", "seed")
ACCESSORIES = ("antenna", "headset", "chullo", "flower")

LEGACY_SHAPE = {"diamond": "kite", "house": "bell", "heart": "bean", "plane": "drop", "shield": "gem", "rocket": "onigiri",
                "star": "cloud", "tree": "sprout", "box": "peanut", "crown": "ears", "feather": "tadpole", "bulb": "bubble"}


def rgb(value):
    h = value.lstrip("#")
    return "rgb({}, {}, {})".format(*(int(h[i:i + 2], 16) for i in (0, 2, 4)))


def _toward(p, q, r):
    d = math.dist(p, q)
    k = min(r, d / 2) / d
    return (p[0] + (q[0] - p[0]) * k, p[1] + (q[1] - p[1]) * k)


def rounded(points, r):
    n = len(points)
    corners = [(_toward(points[i], points[i - 1], r), points[i], _toward(points[i], points[(i + 1) % n], r)) for i in range(n)]
    f = lambda p: "%.1f %.1f" % p
    d = "M" + f(corners[0][2])
    for i in range(1, n + 1):
        a, p, b = corners[i % n]
        d += f" L{f(a)} Q{f(p)} {f(b)}"
    return d + " Z"


def smooth(points):
    n = len(points)
    f = lambda p: "%.1f %.1f" % p
    d = "M" + f(points[0])
    for i in range(n):
        p0, p1, p2, p3 = points[i - 1], points[i], points[(i + 1) % n], points[(i + 2) % n]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d += f" C{f(c1)} {f(c2)} {f(p2)}"
    return d + " Z"


def _path(d):
    return f'<path d="{d}"/>'


def _circle(cx, cy, r):
    return f'<circle cx="{cx}" cy="{cy}" r="{r}"/>'


def _ellipse(cx, cy, rx, ry, rot=0):
    turn = f' transform="rotate({rot} {cx} {cy})"' if rot else ""
    return f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}"{turn}/>'


def _rect(x, y, w, h, rx):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}"/>'


HEX = [(50 + 46 * math.cos(math.radians(-90 + 60 * k)), 50 + 46 * math.sin(math.radians(-90 + 60 * k))) for k in range(6)]

SHAPES = {
    "kite": ([_path(rounded([(50, 3), (92, 37), (50, 97), (8, 37)], 15))], (41, 13), (11, 36)),
    "gem": ([_path(rounded(HEX, 13))], (47, 14), (9, 36)),
    "onigiri": ([_path(rounded([(50, 9), (96, 90), (4, 90)], 20))], (64, 12), (22, 26)),
    "drop": ([_path("M50 4 C58 22 86 42 86 62 A36 36 0 0 1 14 62 C14 42 42 22 50 4 Z")], (63, 13), (6, 34)),
    "bell": ([_path("M50 7 C71 7 77 26 79 47 C81 68 90 77 93 84 Q96 93 86 93 L14 93 Q4 93 7 84 C10 77 19 68 21 47 C23 26 29 7 50 7 Z")], (44, 12), (7, 28)),
    "bean": ([_path("M20 24 C34 10 66 10 80 22 C96 36 96 64 82 78 C72 88 60 86 50 78 C40 86 26 88 16 76 C4 62 6 36 20 24 Z")], (45, 15), (13, 40)),
    "peanut": ([_circle(50, 30, 25), _circle(50, 66, 31)], (29, 10), (5, 23)),
    "cloud": ([_circle(28, 60, 20), _circle(52, 42, 26), _circle(74, 58, 20), _rect(8, 54, 86, 32, 16)], (57, 13), (16, 38)),
    "ears": ([_rect(12, 32, 76, 60, 28), _ellipse(30, 26, 9, 17, -14), _ellipse(70, 26, 9, 17, 14)], (60, 14), (32, 36)),
    "tadpole": ([_path(smooth([(44, 5), (70, 12), (80, 34), (76, 56), (84, 74), (96, 92), (72, 88), (52, 78), (28, 74), (10, 58), (8, 32), (20, 13)]))], (38, 13), (6, 32)),
    "bubble": ([_circle(53, 44, 40), _path(rounded([(24, 60), (6, 96), (48, 80)], 6))], (42, 13), (4, 38)),
    "sprout": ([_circle(50, 60, 36), _path("M50 30 C44 16 54 4 74 4 C76 20 66 32 50 30 Z")], (58, 13), (24, 34)),
}
SHAPE_ORDER = list(SHAPES)
DEFAULT_SHAPE = "kite"
PAIRED_SHAPE = {"amber": "kite", "vermilion": "bell", "rose": "bean", "magenta": "drop", "blue": "gem", "teal": "onigiri",
                "violet": "cloud", "green": "sprout", "sky": "peanut", "indigo": "ears", "lime": "tadpole", "orange": "bubble"}

MOTION_STYLE = ("<style>.am-blink,.am-scan,.am-hop{transform-box: fill-box; transform-origin: center}"
                ".am-blink{animation: am-blink 5.6s infinite}"
                "@keyframes am-blink{0%,93%,100%{transform: scaleY(1)}96.5%{transform: scaleY(0.12)}}"
                ".am-scan{animation: am-scan 1.8s ease-in-out infinite}"
                "@keyframes am-scan{0%,100%{transform: translateX(0)}50%{transform: translateX(-8px)}}"
                ".am-hop{animation: am-hop 2.4s ease-in-out infinite}"
                "@keyframes am-hop{0%,50%,100%{transform: translateY(0)}62%{transform: translateY(-9px)}74%{transform: translateY(0)}82%{transform: translateY(-3px)}90%{transform: translateY(0)}}"
                "@media (prefers-reduced-motion: reduce){.am-blink,.am-scan,.am-hop{animation: none}}</style>")


def eye_ink(colour):
    return INK_EYE if folds.contrast(colour, INK_EYE) >= EYE_CONTRAST else PAPER_EYE


def contrasts(colour):
    return {"light": min(folds.contrast(colour, g) for g in LIGHT_GROUNDS), "dark": min(folds.contrast(colour, g) for g in DARK_GROUNDS),
            "eyes": folds.contrast(colour, eye_ink(colour))}


def _eye(x, y, style, small, fill, grow=1.0):
    if style == "bead":
        r = (5.8 if small else 4.6) * grow
        return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{fill}"/>'
    if style == "seed":
        r = (6.6 if small else 5.4) * grow
        side = 1 if x > 50 else -1
        cy, tx, ty = y + r * 0.35, x - side * r * 0.3, y - r * 1.5
        k = r * 1.08
        return (f'<path d="M{tx:.1f} {ty:.1f} C{x + k:.1f} {y - r * 0.5:.1f} {x + k:.1f} {cy + r:.1f} {x:.1f} {cy + r:.1f} '
                f'C{x - k:.1f} {cy + r:.1f} {x - k:.1f} {y - r * 0.5:.1f} {tx:.1f} {ty:.1f} Z" fill="{fill}"/>')
    rx, ry = (6.2 if small else 4.8) * grow, (8.8 if small else 7.2) * grow
    return f'<ellipse cx="{x:.1f}" cy="{y:.1f}" rx="{rx:.1f}" ry="{ry:.1f}" fill="{fill}"/>'


def _line(x1, y1, x2, y2, width, fill):
    return f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{fill}" stroke-width="{width}" stroke-linecap="round"/>'


def _delay(seed):
    return -(int(hashlib.md5(seed.encode()).hexdigest(), 16) % 56) / 10


def eyes(shape, colour, size, state, style="oval", seed="", still=False):
    if state == "offline":
        return ""
    ey, dx = SHAPES[shape][1]
    small = size <= SMALL_MAX
    fill = rgb(colour) if state == "no-provider" else rgb(eye_ink(colour))
    xs = (50 - dx, 50 + dx)
    width = 6.2 if small else 4.4
    if state == "failed":
        a = 6.4 if small else 5.0
        return "".join(_line(x - a, ey - a, x + a, ey + a, width, fill) + _line(x - a, ey + a, x + a, ey - a, width, fill) for x in xs)
    if state == "paused":
        a = 7.6 if small else 6.0
        return "".join(_line(x - a, ey + 2, x + a, ey + 2, width, fill) for x in xs)
    if state == "working":
        pair = "".join(_eye(x + 4, ey, style, small, fill) for x in xs)
        return f'<g class="am-scan">{pair}</g>'
    if state == "needs":
        return "".join(_eye(x, ey - 6, style, small, fill, 1.16) for x in xs)
    pair = "".join(_eye(x, ey, style, small, fill) for x in xs)
    if state == "idle" and not still:
        return f'<g class="am-blink" style="animation-delay: {_delay(seed or shape):.1f}s">{pair}</g>'
    return pair


def accessory(shape, kind, ink):
    ey, _ = SHAPES[shape][1]
    ty, hw = SHAPES[shape][2]
    if kind == "antenna":
        return (f'<line x1="50" y1="{ty + 4}" x2="58" y2="{ty - 13}" stroke="{ink}" stroke-width="4.5" stroke-linecap="round"/>'
                f'<circle cx="59" cy="{ty - 16}" r="6.5" fill="{ink}"/>')
    if kind == "headset":
        x1, x2 = 50 - hw - 3, 50 + hw + 3
        top = ty - 9
        return (f'<path d="M{x1} {ey} C{x1} {top - 6} {x2} {top - 6} {x2} {ey}" fill="none" stroke="{ink}" stroke-width="5"/>'
                f'<rect x="{x1 - 6}" y="{ey - 10}" width="12" height="20" rx="5" fill="{ink}"/><rect x="{x2 - 6}" y="{ey - 10}" width="12" height="20" rx="5" fill="{ink}"/>'
                f'<path d="M{x1} {ey + 9} Q{x1 + 2} {ey + 22} {x1 + 18} {ey + 22}" fill="none" stroke="{ink}" stroke-width="4" stroke-linecap="round"/>'
                f'<circle cx="{x1 + 19}" cy="{ey + 22}" r="4.5" fill="{ink}"/>')
    if kind == "chullo":
        w = min(hw, 26)
        base = ty + 8
        return (f'<path d="M{50 - w} {base} C{50 - w} {base - 16} {50 - 8} {base - 30} {50} {base - 32} C{50 + 8} {base - 30} {50 + w} {base - 16} {50 + w} {base} Z" fill="{ink}"/>'
                f'<path d="M{50 - w} {base - 3} L{50 - w + 8} {base - 3} L{50 - w + 2} {base + 16} Z" fill="{ink}" stroke="{ink}" stroke-width="3" stroke-linejoin="round"/>'
                f'<path d="M{50 + w} {base - 3} L{50 + w - 8} {base - 3} L{50 + w - 2} {base + 16} Z" fill="{ink}" stroke="{ink}" stroke-width="3" stroke-linejoin="round"/>'
                f'<circle cx="50" cy="{base - 35}" r="6.5" fill="{ink}"/>')
    if kind == "flower":
        cx, cy = 50 + hw * 0.62, ty + 1
        petals = "".join(f'<circle cx="{cx + 6.2 * math.cos(math.radians(-90 + 72 * k)):.1f}" cy="{cy + 6.2 * math.sin(math.radians(-90 + 72 * k)):.1f}" r="4.6"/>' for k in range(5))
        return f'<g fill="{ink}">{petals}</g><circle cx="{cx:.1f}" cy="{cy:.1f}" r="3.2" fill="{PAPER_EYE}"/>'
    return ""


def mark(shape, colour, size=16, state="idle", style="oval", wear=None, seed="", ink="#14110c", still=False):
    parts, faded = "".join(SHAPES[shape][0]), state in ("no-provider", "offline")
    fade = ' opacity="0.3"' if faded else ""
    worn = wear and size >= ACCESSORY_MIN and state != "offline"
    inner = f'<g fill="{rgb(colour)}"{fade}>{parts}</g>{eyes(shape, colour, size, state, style, seed, still)}'
    if worn:
        inner += accessory(shape, wear, ink)
    if state == "needs":
        inner = f'<g class="am-hop">{inner}</g>'
    box = "-12 -22 124 124" if worn else "0 0 100 100"
    label = " ".join(filter(None, (shape, STATE_LABEL[state], wear if worn else "")))
    return (f'<svg viewBox="{box}" width="{size}" height="{size}" role="img" aria-label="{label}" data-mark="{shape}" '
            f'style="flex-shrink: 0; display: block; overflow: visible">{inner}</svg>')


@lru_cache(maxsize=None)
def shipped_accents():
    script = f"import {{ACCENTS}} from {json.dumps(os.path.join(folds.COMMON, 'accents.mjs'))};process.stdout.write(JSON.stringify(ACCENTS));"
    out = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True, check=True)
    return [tuple(pair) for pair in json.loads(out.stdout)]


APP_MARKS = {
    "peek": dict(ground="#f6f3ec", body="#0b89e8", shape="gem", transform="translate(-30 17) scale(1.6)",
                 eyes=((39, 60, 6.4, 10, 0), (61, 60, 6.4, 10, 0))),
    "ears": dict(ground="#0c0b09", body="#f3efe6", shape="ears", transform="rotate(-10 50 50) translate(-28 6) scale(1.56)",
                 eyes=((40, 69, 6.2, 9.6, -10), (62, 65, 6.2, 9.6, -10))),
}


def app_mark(kind, size=120, radius=22):
    spec = APP_MARKS[kind]
    clip = f"am-app-{kind}-{size}"
    ink = rgb(INK_EYE)
    eyes_ = "".join(f'<ellipse cx="{x}" cy="{y}" rx="{rx}" ry="{ry}" transform="rotate({rot} {x} {y})" fill="{ink}"/>' for x, y, rx, ry, rot in spec["eyes"])
    body = "".join(SHAPES[spec["shape"]][0])
    return (f'<svg viewBox="0 0 100 100" width="{size}" height="{size}" role="img" aria-label="app mark sketch, {kind}" style="flex-shrink: 0; display: block">'
            f'<clipPath id="{clip}"><rect width="100" height="100" rx="{radius}"/></clipPath><g clip-path="url(#{clip})">'
            f'<rect width="100" height="100" fill="{rgb(spec["ground"])}"/><g transform="{spec["transform"]}" fill="{rgb(spec["body"])}">{body}</g>{eyes_}</g></svg>')
