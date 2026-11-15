import hashlib
import itertools
import json
import math
import os
import subprocess
from collections import defaultdict
from functools import lru_cache


COMMON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "common")
WHITE = "rgb(255, 255, 255)"
NEUTRAL = "#8a8a8a"
MOTION_MIN = 20
MARK_SIZES = {"inline": 16, "row": 24, "header": 28, "list": 40, "tile": 48, "hero": 72}
SMALL = 32
EYE_MIN_PX = 2.4
EYE_CAP = 1.3
TILE_MIX = 0.14
TILE_SCALE = 1.4
TILE_RADIUS = 0.23
TARGET_AREA = 4500
LIGHT_GROUNDS = ("#ffffff", "#f6f6f6", "#f4f4f4", "#f0f0f0")
DARK_GROUNDS = ("#0e0e0e", "#121212", "#1a1a1a", "#282828")

BRAND_INK = "#14110c"
CREAM = "#f3efe6"
EYE_INK = "#fffffd"
PAPER = "#f6f3ec"
EAR_SPREAD = 14
EAR_SPLAY = 16

STATES = ("idle", "busy", "working", "needs", "done", "failed", "paused", "offline")
STATE_LABEL = {"idle": "idle", "busy": "busy", "working": "working", "needs": "needs you", "done": "done", "failed": "failed",
               "paused": "paused", "offline": "offline"}
STATE_TABLE = {
    "idle": ("no row state, daemon connected", "rest pills; blink, sometimes twice; a glance aside with the near eye bigger; a curious look, one eye smaller", "full accent", "breathes"),
    "busy": ("the loading indicator only, never a row: <code>BusyMark</code> on desktop and <code>Busy</code> on the phone, Twin waiting for a first byte", "smaller look pills raised to one side; glance around, squint a moment, thinking", "full accent", "bobs and leans"),
    "working": ("<code>activity.running</code> → row state <code>working</code>; a sent prompt still waiting for output (<code>pending</code>) reads working too; the chat header from send until the turn ends", "squint bars slanted inward; scan left to right like reading, look up between lines, blink", "full accent", "rhythmic squash and stretch, like typing"),
    "needs": ("<code>activity.needs_you</code> → row state <code>needs-you</code> (approval or a question pending), and a profile with no model (<code>needs-provider</code>)", "rest morphs to wide ovals on the hop; look up at you, around, blink", "full accent", "anticipation, hop, squash, settle"),
    "done": ("a reply landed while the profile was not open: <code>checkUnread</code> → <code>unread</code> in <code>Sidebar.jsx</code>", "happy upturned hooks that grow on the bounce", "full accent", "a happy little bounce"),
    "failed": ("a recent job failure → row state <code>failed</code> in <code>useActivity.js</code>; a workgroup task in <code>error</code>", "squint on the shiver, then sad slants drooped low, a sigh and a blink", "full accent", "a short shiver, then a slow sink and droop"),
    "paused": ("<code>profile.paused</code>", "sleepy closed arcs, still", "dashed neutral grey outline, no fill", "none"),
    "offline": ("the daemon is unreachable (connection lost in <code>useDaemonData.js</code>); every mark of that daemon", "none", "accent at 30 %", "none"),
}

LEGACY_SHAPE = {"diamond": "round", "shield": "bell", "house": "arch", "heart": "heart", "plane": "drop", "rocket": "pill",
                "star": "clover", "box": "squircle", "bulb": "bean", "tree": "pebble", "crown": "dome", "feather": "cloud"}


def rgb(value):
    if not value.startswith("#"):
        return value
    h = value.lstrip("#")
    return "rgb({}, {}, {})".format(*(int(h[i:i + 2], 16) for i in (0, 2, 4)))


@lru_cache(maxsize=None)
def mark_tone(colour):
    script = (f"import {{markTone}} from {json.dumps(os.path.join(COMMON, 'markTone.mjs'))};"
              f"process.stdout.write(JSON.stringify(markTone({json.dumps(colour)}, 'light')));")
    out = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def body_fill(colour, theme=None):
    light = mark_tone(colour) if isinstance(colour, str) and colour.startswith("#") else colour
    if light == colour or theme == "dark":
        return rgb(colour)
    return rgb(light) if theme == "light" else f"light-dark({rgb(light)}, {rgb(colour)})"


def tint(colour, mix=TILE_MIX):
    if not colour.startswith("#"):
        return colour
    h = colour.lstrip("#")
    return "rgba({}, {}, {}, {})".format(*(int(h[i:i + 2], 16) for i in (0, 2, 4)), mix)


def mixed(colour, ground, mix=TILE_MIX):
    a, g = (tuple(int(c[i:i + 2], 16) for i in (1, 3, 5)) for c in (colour, ground))
    return "#%02x%02x%02x" % tuple(round(g[i] + (a[i] - g[i]) * mix) for i in range(3))


def _smin(a, b, k):
    h = max(k - abs(a - b), 0) / k
    return min(a, b) - h * h * k / 4


def _union(k, *fs):
    def f(x, y):
        d = fs[0](x, y)
        for g in fs[1:]:
            d = _smin(d, g(x, y), k)
        return d
    return f


def _cut(k, f, g):
    return lambda x, y: -_smin(-f(x, y), g(x, y), k)


def _circle(cx, cy, r):
    return lambda x, y: math.hypot(x - cx, y - cy) - r


def _ellipse(cx, cy, rx, ry, rot=0):
    c, s = math.cos(math.radians(-rot)), math.sin(math.radians(-rot))

    def f(x, y):
        px, py = x - cx, y - cy
        return (math.hypot((px * c - py * s) / rx, (px * s + py * c) / ry) - 1) * min(rx, ry)
    return f


def _cone(ax, ay, ra, bx, by, rb):
    h = math.dist((ax, ay), (bx, by))
    ux, uy = (bx - ax) / h, (by - ay) / h
    b = (ra - rb) / h
    a = math.sqrt(1 - b * b)

    def f(x, y):
        px, py = x - ax, y - ay
        qy, qx = px * ux + py * uy, abs(px * uy - py * ux)
        k = -b * qx + a * qy
        if k < 0:
            return math.hypot(qx, qy) - ra
        if k > a * h:
            return math.hypot(qx, qy - h) - rb
        return qx * a + qy * b - ra
    return f


def _poly(points, r):
    def f(x, y):
        d, s = (x - points[0][0]) ** 2 + (y - points[0][1]) ** 2, 1
        for i, (vx, vy) in enumerate(points):
            jx, jy = points[i - 1]
            ex, ey, wx, wy = jx - vx, jy - vy, x - vx, y - vy
            t = max(0.0, min(1.0, (wx * ex + wy * ey) / (ex * ex + ey * ey)))
            d = min(d, (wx - ex * t) ** 2 + (wy - ey * t) ** 2)
            c = (y >= vy, y < jy, ex * wy > ey * wx)
            if all(c) or not any(c):
                s = -s
        return s * math.sqrt(d) - r
    return f


def _march(f, lo=-4, hi=104):
    n = hi - lo + 1
    v = [[f(lo + i, lo + j) for i in range(n)] for j in range(n)]
    links, points = defaultdict(list), {}

    def edge(a, b):
        key = (a, b) if a < b else (b, a)
        if key not in points:
            (ai, aj), (bi, bj) = key
            va, vb = v[aj][ai], v[bj][bi]
            t = va / (va - vb)
            points[key] = (lo + ai + (bi - ai) * t, lo + aj + (bj - aj) * t)
        return key

    for j in range(n - 1):
        for i in range(n - 1):
            c = ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1))
            inside = [v[y][x] < 0 for x, y in c]
            if all(inside) or not any(inside):
                continue
            centre = math.fsum(v[y][x] for x, y in c) < 0
            crossings = [k for k in range(4) if inside[k] != inside[(k + 1) % 4]]
            if len(crossings) == 2:
                pairs = [crossings]
            else:
                pairs = [((k - 1) % 4, k) for k in range(4) if inside[k] != centre]
            for e1, e2 in pairs:
                a, b = edge(c[e1], c[(e1 + 1) % 4]), edge(c[e2], c[(e2 + 1) % 4])
                links[a].append(b)
                links[b].append(a)
    loops, seen = [], set()
    for start in links:
        if start in seen:
            continue
        loop, prev, cur = [], None, start
        while cur not in seen:
            seen.add(cur)
            loop.append(points[cur])
            nxt = [k for k in links[cur] if k != prev and k not in seen]
            prev, cur = cur, (nxt[0] if nxt else start)
        loops.append(loop)
    return max(loops, key=len)


def _rdp(points, eps):
    if len(points) < 3:
        return points
    (ax, ay), (bx, by) = points[0], points[-1]
    length = math.hypot(bx - ax, by - ay) or 1e-9
    far, index = 0, 0
    for i in range(1, len(points) - 1):
        px, py = points[i]
        d = abs((bx - ax) * (ay - py) - (ax - px) * (by - ay)) / length
        if d > far:
            far, index = d, i
    if far <= eps:
        return [points[0], points[-1]]
    return _rdp(points[:index + 1], eps)[:-1] + _rdp(points[index:], eps)


def _closed_rdp(points, eps):
    far = max(range(len(points)), key=lambda i: math.dist(points[0], points[i]))
    return _rdp(points[:far + 1], eps)[:-1] + _rdp(points[far:] + [points[0]], eps)[:-1]


def _bezier(points):
    n = len(points)
    f = lambda p: "%.1f %.1f" % p
    d = "M" + f(points[0])
    for i in range(n):
        p0, p1, p2, p3 = points[i - 1], points[i], points[(i + 1) % n], points[(i + 2) % n]
        d1, d2, d3 = (max(math.dist(a, b), 1e-6) ** 0.5 for a, b in ((p0, p1), (p1, p2), (p2, p3)))
        c1 = tuple((d1 * d1 * p2[k] - d2 * d2 * p0[k] + (2 * d1 * d1 + 3 * d1 * d2 + d2 * d2) * p1[k]) / (3 * d1 * (d1 + d2)) for k in (0, 1))
        c2 = tuple((d3 * d3 * p1[k] - d2 * d2 * p3[k] + (2 * d3 * d3 + 3 * d3 * d2 + d2 * d2) * p2[k]) / (3 * d3 * (d3 + d2)) for k in (0, 1))
        d += f" C{f(c1)} {f(c2)} {f(p2)}"
    return d + " Z"


def _squircle(cx, cy, a, b, n=3.4, taper=0.0):
    def f(x, y):
        v = (y - cy) / b
        w = a * (1 + taper * v)
        u = (x - cx) / w
        return ((abs(u) ** n + abs(v) ** n) ** (1 / n) - 1) * min(w, b)
    return f


def _clover():
    radii = (17, 15.5, 16.5, 15, 16.2)
    lobes = [_circle(50 + 23 * math.cos(math.radians(-90 + 72 * k + 4)), 52 + 23 * math.sin(math.radians(-90 + 72 * k + 4)), r) for k, r in enumerate(radii)]
    return _union(8, _circle(50, 52, 24), *lobes)


def _ears(ball, top):
    turn, length = math.radians(EAR_SPLAY), 33 - top
    return tuple((50 + side * (EAR_SPREAD + (length + 2) * math.sin(turn)), 33 - (length + 2) * math.cos(turn), ball) for side in (-1, 1))


def _twin(stalk, ball, top):
    turn, length = math.radians(EAR_SPLAY), 33 - top
    ears = [_union(3, _cone(50 + side * EAR_SPREAD, 33, stalk, 50 + side * (EAR_SPREAD + length * math.sin(turn)), 33 - length * math.cos(turn), stalk), _circle(x, y, r))
            for side, (x, y, r) in zip((-1, 1), _ears(ball, top))]
    return _union(7, _squircle(50, 60, 36, 30, 3.8, 0.0), *ears)


FIELDS = {
    "round": lambda: _union(30, _circle(49, 50, 38), _circle(53, 56, 33)),
    "squircle": lambda: _squircle(50, 51, 36, 34, 3.4, 0.07),
    "drop": lambda: _cone(54, 11, 3.6, 49, 61, 33),
    "dome": lambda: _cut(12, _union(18, _circle(42, 50, 32), _circle(63, 58, 26)), lambda x, y: 84 - y),
    "pill": lambda: _cone(50, 29, 23.5, 50, 70, 27),
    "clover": _clover,
    "cloud": lambda: _union(7, _circle(29, 58, 16), _circle(47, 43, 22), _circle(67, 50, 17), _circle(80, 61, 11), _cone(24, 67, 13, 79, 67, 13)),
    "bean": lambda: _cut(14, _cone(30, 53, 26, 70, 47, 26), _circle(53, 93, 16)),
    "pebble": lambda: _union(22, _poly([(51, 25), (80, 76), (20, 76)], 12), _circle(50, 59, 26)),
    "arch": lambda: _union(10, _circle(50, 41, 28), _poly([(28, 41), (72, 41), (75, 79), (25, 79)], 8)),
    "heart": lambda: _union(14, _circle(35, 40, 19.5), _circle(64, 41, 20.5), _poly([(22, 50), (78, 50), (50, 83)], 8)),
    "bell": lambda: _union(14, _cone(50, 30, 19, 50, 56, 25), _ellipse(50, 74, 35, 10)),
    "alpi-twin": lambda: _twin(3.6, 7.5, 16),
    "alpi-twin-small": lambda: _twin(4.8, 8.8, 18),
}
BRAND = {
    "alpi-twin": dict(balls=_ears(7.5, 16), signature="beacon"),
    "alpi-twin-small": dict(balls=_ears(8.8, 18), signature="beacon"),
}
PINNED_FRAME = {"alpi-twin": (50.0, 52.8315, 1.030694), "alpi-twin-small": (50.0, 52.7698, 1.023725)}
BRAND_SHAPES = ("alpi-twin",)
BRAND_TRIAL = "alpi-twin"
EYE_AT = {"round": (44, 12, 2), "squircle": (46, 12, -1), "drop": (59, 11, 1), "dome": (52, 12, -4), "pill": (44, 9.5, 0), "clover": (48, 11, 0),
          "cloud": (50, 10.5, -3), "bean": (48, 13, 0), "pebble": (59, 10, 1), "arch": (44, 11, 1), "heart": (46, 13, 0), "bell": (50, 10, 0),
          "alpi-twin": (58, 12, 0), "alpi-twin-small": (58, 12, 0)}
CHARACTER = {"round": (1.0, 0.0, "bottom"), "squircle": (0.8, 0.6, "bottom"), "drop": (0.7, 4.0, "top"), "dome": (1.3, 1.0, "bottom"),
             "pill": (1.7, 0.0, "bottom"), "clover": (0.9, 3.5, "centre"), "cloud": (1.1, 1.5, "bottom"), "bean": (1.2, 1.2, "bottom"),
             "pebble": (0.9, 1.0, "bottom"), "arch": (1.0, 0.5, "bottom"), "heart": (1.0, 2.5, "centre"), "bell": (0.8, 3.0, "top"),
             "alpi-twin": (0.8, 1.0, "bottom"), "alpi-twin-small": (0.8, 1.0, "bottom")}
SHAPE_ORDER = ["round", "squircle", "drop", "dome", "pill", "clover", "cloud", "bean", "pebble", "arch", "heart", "bell"]
DEFAULT_SHAPE = "round"
FAMILY = [("round", "orange"), ("squircle", "blue"), ("drop", "magenta"), ("dome", "amber"), ("pill", "teal"), ("clover", "violet"),
          ("cloud", "sky"), ("bean", "green"), ("pebble", "lime"), ("arch", "indigo"), ("heart", "rose"), ("bell", "vermilion")]


@lru_cache(maxsize=None)
def frame(shape):
    loop = _march(FIELDS[shape](), -8, 112)
    xs, ys = [x for x, y in loop], [y for x, y in loop]
    area = math.fsum(loop[i - 1][0] * y - x * loop[i - 1][1] for i, (x, y) in enumerate(loop)) / 2
    cy = math.fsum((loop[i - 1][1] + y) * (loop[i - 1][0] * y - x * loop[i - 1][1]) for i, (x, y) in enumerate(loop)) / (6 * area)
    if shape in PINNED_FRAME:
        return loop, PINNED_FRAME[shape]
    return loop, ((min(xs) + max(xs)) / 2, ((min(ys) + max(ys)) / 2 + cy) / 2, math.sqrt(TARGET_AREA / abs(area)))


def place(shape, x, y):
    cx, cy, k = frame(shape)[1]
    return 50 + k * (x - cx), 50 + k * (y - cy)


@lru_cache(maxsize=None)
def outline(shape):
    moved = [place(shape, x, y) for x, y in frame(shape)[0]]
    xs, ys = [x for x, y in moved], [y for x, y in moved]
    return dict(d=_bezier(_closed_rdp(moved, 0.14)), top=min(ys), bottom=max(ys), left=min(xs), right=max(xs))


def _rounded(x, y, w, h, r):
    return (f"M{x + r:.1f} {y:.1f}H{x + w - r:.1f}A{r:.1f} {r:.1f} 0 0 1 {x + w:.1f} {y + r:.1f}V{y + h - r:.1f}A{r:.1f} {r:.1f} 0 0 1 {x + w - r:.1f} {y + h:.1f}"
            f"H{x + r:.1f}A{r:.1f} {r:.1f} 0 0 1 {x:.1f} {y + h - r:.1f}V{y + r:.1f}A{r:.1f} {r:.1f} 0 0 1 {x + r:.1f} {y:.1f}Z")


@lru_cache(maxsize=None)
def balls(shape):
    sig = BRAND[shape]
    return tuple((*place(shape, x, y), r * frame(shape)[1][2]) for x, y, r in sig["balls"])


def _anchor(shape):
    ey, dx, look = EYE_AT[shape]
    x, y = place(shape, 50 + look, ey)
    return y, dx * frame(shape)[1][2], x


EYE = {"pill": (4.8, 11.6), "oval": (7.2, 9.4), "arc": (8.4, 8.4)}
EYE_POINTS = 48
EYE_GRID = 8
EYE_GAP_PX = 1.0
EYE_SPLINE = "0.45 0 0.25 1"


def _arc(r, half, t, up=True):
    a = math.radians(half)
    c = (r + r * math.cos(a)) / 2
    k = 1 if up else -1
    ends = [(s * r * math.sin(a), -r * math.cos(a)) for s in (-1, 1)]

    def f(x, y):
        px, py = x, k * y - c
        if abs(math.atan2(px, -py)) <= a:
            return abs(math.hypot(px, py) - r) - t
        return min(math.hypot(px - ex, py - ey) for ex, ey in ends) - t
    return f


def _bar(w, h):
    r = min(w, h) / 2
    if w > h:
        return _cone(-(w / 2 - r), 0, r, w / 2 - r, 0, r)
    return _cone(0, -(h / 2 - r), r, 0, h / 2 - r, r)


EXPRESSIONS = {
    "rest": (lambda: _bar(9.6, 23.2), 0),
    "wide": (lambda: _ellipse(0, 0, 8.2, 11.2), 0),
    "squint": (lambda: _bar(15, 6.4), -8),
    "happy": (lambda: _arc(7.6, 76, 3.1), 0),
    "sleepy": (lambda: _arc(7.2, 60, 2.4, up=False), 0),
    "sad": (lambda: _cone(0, -4.2, 3.9, 0, 4, 5.0), -22),
    "look": (lambda: _bar(8.6, 17), 0),
    "blink": (lambda: _bar(13, 1.8), 0),
}
EXPRESSION_LABEL = {"rest": "rest · a tall pill", "wide": "wide · a round oval", "squint": "squint · a short flat pill", "happy": "happy · an upturned hook",
                    "sleepy": "sleepy · a thin closed arc", "sad": "sad · a drooped slant", "look": "look · a smaller pill", "blink": "blink · a flat line"}


def _crossings(loop):
    hits = []
    for i, (x, y) in enumerate(loop):
        px, py = loop[i - 1]
        if (px <= 0 < x) or (x <= 0 < px):
            t = px / (px - x)
            hits.append((py + (y - py) * t, i))
    return min(hits), max(hits)


def _resample(path, n):
    lengths = [0.0]
    for a, b in zip(path, path[1:]):
        lengths.append(lengths[-1] + math.dist(a, b))
    out, j = [], 0
    for k in range(n + 1):
        s = lengths[-1] * k / n
        while j < len(lengths) - 2 and lengths[j + 1] < s:
            j += 1
        span = lengths[j + 1] - lengths[j] or 1e-9
        u = (s - lengths[j]) / span
        out.append(tuple(path[j][m] + (path[j + 1][m] - path[j][m]) * u for m in (0, 1)))
    return out


@lru_cache(maxsize=None)
def expression(name):
    build, tilt = EXPRESSIONS[name]
    g = build()
    loop = [(x / EYE_GRID, y / EYE_GRID) for x, y in _march(lambda x, y: g(x / EYE_GRID, y / EYE_GRID), -16 * EYE_GRID, 16 * EYE_GRID)]
    (top, i), (bottom, j) = _crossings(loop)
    n = len(loop)
    forward = [loop[(i + m) % n] for m in range(((j - i) % n) + 1)]
    if sum(x for x, y in forward) < 0:
        forward = [loop[(i - 1 - m) % n] for m in range(((i - 1 - j) % n) + 1)]
    half = _resample([(0.0, top)] + forward[1:-1] + [(0.0, bottom)], EYE_POINTS // 2)
    ring = half + [(-x, y) for x, y in reversed(half[1:-1])]
    c, s = math.cos(math.radians(tilt)), math.sin(math.radians(tilt))
    return tuple((round(x * c - y * s, 3), round(x * s + y * c, 3)) for x, y in ring)


def _k(t, expr, gx=0.0, gy=0.0, s=1.0, right=None, left=None):
    return (t, gx, gy, left or (expr, s, 0.0), right or (expr, s, 0.0))


SEQUENCE = {
    "idle": (9.6, (_k(0, "rest"), _k(0.11, "rest"), _k(0.125, "blink"), _k(0.14, "rest"), _k(0.2, "rest"),
                   _k(0.225, "rest", -3, 0, left=("rest", 1.1, 0), right=("rest", 0.9, 0.4)), _k(0.33, "rest", -3, 0, left=("rest", 1.1, 0), right=("rest", 0.9, 0.4)),
                   _k(0.355, "rest"), _k(0.5, "rest"),
                   _k(0.53, "rest", 2.2, -1.5, left=("rest", 1.06, 0), right=("look", 0.9, -1.2)), _k(0.62, "rest", 2.2, -1.5, left=("rest", 1.06, 0), right=("look", 0.9, -1.2)),
                   _k(0.645, "rest"), _k(0.66, "blink"), _k(0.675, "rest"), _k(0.69, "blink"), _k(0.705, "rest"), _k(1, "rest"))),
    "busy": (4.2, (_k(0, "look", 3, -4), _k(0.18, "look", 3, -4), _k(0.28, "look", -2.5, -4.5), _k(0.4, "look", -2.5, -4.5), _k(0.48, "squint", 0, -2.5),
                   _k(0.58, "squint", 0, -2.5), _k(0.66, "look", -0.5, -5.5), _k(0.7, "blink", -0.5, -5), _k(0.73, "look", -0.5, -5.5), _k(0.86, "look", 3, -4), _k(1, "look", 3, -4))),
    "working": (4.8, (_k(0, "squint", -2.6, 1), _k(0.08, "squint", -2.6, 1), _k(0.2, "squint", -0.9, 1.6), _k(0.26, "squint", -0.9, 1.6), _k(0.36, "squint", 0.9, 1.6),
                      _k(0.42, "squint", 0.9, 1.6), _k(0.5, "squint", 2.6, 1), _k(0.53, "blink", 2.6, 1), _k(0.56, "squint", 2.6, 1), _k(0.6, "look", 0, -1, 0.9),
                      _k(0.66, "squint", -2.6, 1), _k(0.7, "squint", -2.6, 1), _k(0.8, "squint", -0.9, 1.6), _k(0.84, "squint", -0.9, 1.6), _k(0.92, "squint", 0.9, 1.6),
                      _k(0.96, "squint", 0.9, 1.6), _k(1, "squint", -2.6, 1))),
    "needs": (2.8, (_k(0, "wide", 0, -3), _k(0.06, "wide", 0, -3), _k(0.14, "rest", 0, 0, 0.92), _k(0.24, "wide", 0, -4, 1.12), _k(0.33, "wide", 0, -2.5, 0.95),
                    _k(0.42, "wide", 0, -3), _k(0.56, "wide", 0, -3), _k(0.64, "wide", -2, -3.5), _k(0.72, "wide", -2, -3.5), _k(0.8, "wide", 2, -3.5), _k(0.86, "wide", 2, -3.5),
                    _k(0.92, "wide", 0, -3), _k(0.945, "blink", 0, -3), _k(0.97, "wide", 0, -3), _k(1, "wide", 0, -3))),
    "done": (2.4, (_k(0, "happy", 0, -1), _k(0.3, "happy", 0, -1), _k(0.38, "happy", 0, 0, 0.9), _k(0.5, "happy", 0, -2.5, 1.12), _k(0.6, "happy", 0, -0.5, 0.94),
                   _k(0.68, "happy", 0, -1.5, 1.04), _k(0.78, "happy", 0, -1), _k(1, "happy", 0, -1))),
    "failed": (5.6, (_k(0, "sad", 0, 4), _k(0.01, "squint", 0, 2, 0.9), _k(0.13, "squint", 0, 2, 0.9), _k(0.2, "sad", 0, 3.5), _k(0.36, "sad", -1.6, 5, 0.94),
                     _k(0.56, "sad", -1.6, 5, 0.94), _k(0.64, "sad", 1, 5, 0.94), _k(0.8, "sad", 1, 5, 0.94), _k(0.84, "sad", 0, 4.5), _k(0.87, "blink", 0, 5),
                     _k(0.9, "sad", 0, 4), _k(1, "sad", 0, 4))),
}
STILL = {"idle": _k(0, "rest"), "busy": _k(0, "look", 3, -4), "working": _k(0, "squint", 0, 1), "needs": _k(0, "wide", 0, -3), "done": _k(0, "happy", 0, -1),
         "failed": _k(0, "sad", 0, 4), "paused": _k(0, "sleepy", 0, 3)}
POSE = {state: dict(form=key[3][0], sx=1.0, sy=1.0, tilt=EXPRESSIONS[key[3][0]][1], lift=key[2], shift=key[1]) for state, key in STILL.items()}
LOOK = {"idle": "idle", "busy": "think", "working": "work", "needs": "needs", "done": "happy", "failed": "sad"}
BODY = {"idle": "breathe", "busy": "bob", "working": "type", "needs": "hop", "done": "bounce", "failed": "sink"}


def _keyframes(name, seconds, frames):
    return f".am-{name}{{animation-name: am-{name}; animation-duration: {seconds}s}}@keyframes am-{name}{{{frames}}}"


SQ = "scale(calc(1 + var(--s) * {0}), calc(1 - var(--s) * {1}))"
WOB = "rotate(calc(var(--w) * {0}deg))"
MOTION_STYLE = "<style>.am-a{animation-delay: var(--d, 0s); animation-iteration-count: infinite; animation-timing-function: cubic-bezier(0.45, 0, 0.25, 1)}" + "".join((
    _keyframes("look-idle", 9.6, "0%,20%,35%,56%,72%,100%{transform: none}21.5%,33%{transform: translate(calc(var(--g) * -1), 0)}57.5%,70%{transform: translate(var(--g), calc(var(--g) * -0.6)) rotate(4deg)}"),
    _keyframes("lid-idle", 9.6, "0%,11%,13.4%,62%,63.6%,65.2%,66.8%,100%{transform: none}12.2%,62.8%,66%{transform: scale(1.04, 0.08)}"),
    _keyframes("body-breathe", 4.8, f"0%,100%{{transform: none}}42%{{transform: {SQ.format(-0.012, -0.028)} {WOB.format(0.3)}}}80%{{transform: {SQ.format(0.016, 0.022)}}}"),
    _keyframes("look-think", 4.2, "0%,100%{transform: none}22%,34%{transform: translate(calc(var(--g) * -1.6), calc(var(--g) * -0.3))}52%,62%{transform: translate(calc(var(--g) * -0.5), calc(var(--g) * -0.9))}80%,88%{transform: translate(calc(var(--g) * 0.4), calc(var(--g) * -0.2))}"),
    _keyframes("lid-think", 4.2, "0%,70%,74%,100%{transform: none}72%{transform: scale(1, 0.1)}"),
    _keyframes("body-bob", 2.8, "0%,50%,100%{transform: none}25%{transform: translate(0, -1.6px) rotate(calc(var(--w) * -0.6deg - 2deg))}75%{transform: translate(0, -1.6px) rotate(calc(var(--w) * 0.6deg + 2deg))}"),
    _keyframes("look-work", 2.4, "0%,100%{transform: none}6%,18%{transform: translate(calc(var(--g) * -1), 0)}34%,44%{transform: translate(calc(var(--g) * -0.35), 0.5px)}60%,70%{transform: translate(calc(var(--g) * 0.35), 0.5px)}86%,92%{transform: translate(var(--g), 0)}"),
    _keyframes("lid-work", 4.8, "0%,47%,51%,100%{transform: none}49%{transform: scale(1.05, 0.1)}"),
    _keyframes("body-type", 0.72, f"0%,100%{{transform: none}}30%{{transform: {SQ.format(0.025, 0.035)}}}65%{{transform: {SQ.format(-0.012, -0.025)} {WOB.format(0.4)}}}"),
    _keyframes("look-needs", 2.8, "0%,20%,56%,100%{transform: none}24%,36%{transform: translate(0, calc(var(--g) * -0.6))}64%,74%{transform: translate(calc(var(--g) * -0.8), calc(var(--g) * -0.5))}80%,88%{transform: translate(calc(var(--g) * 0.8), calc(var(--g) * -0.5))}"),
    _keyframes("lid-needs", 2.8, "0%,14%,44%,92%,96%,100%{transform: none}24%{transform: scale(1.18, 1.22)}33%{transform: scale(1.05, 0.9)}94%{transform: scale(1, 0.1)}"),
    _keyframes("body-hop", 2.8, f"0%,6%,60%,100%{{transform: none}}14%{{transform: {SQ.format(0.06, 0.09)}}}24%{{transform: translate(0, -11px) {SQ.format(-0.04, -0.07)} {WOB.format(-1)}}}"
               f"33%{{transform: translate(0, 0) {SQ.format(0.08, 0.1)}}}40%{{transform: translate(0, -2.5px) {SQ.format(-0.015, -0.025)}}}47%{{transform: translate(0, 0) scale(1.01, 0.99)}}"),
    _keyframes("look-happy", 2.4, "0%,100%{transform: none}50%{transform: translate(0, -1px)}"),
    _keyframes("lid-happy", 2.4, "0%,40%,72%,100%{transform: none}50%{transform: scale(1.12, 0.86)}60%{transform: scale(0.95, 1.08)}"),
    _keyframes("body-bounce", 2.4, f"0%,30%,78%,100%{{transform: none}}38%{{transform: {SQ.format(0.04, 0.05)}}}50%{{transform: translate(0, -6px) {SQ.format(-0.02, -0.04)} rotate(calc(var(--w) * 1deg + 2deg))}}"
               f"60%{{transform: translate(0, 0) {SQ.format(0.05, 0.06)}}}68%{{transform: translate(0, -1.5px) rotate(calc(var(--w) * -0.5deg - 1deg))}}"),
    _keyframes("look-sad", 5.6, "0%,14%,92%,100%{transform: none}36%,56%{transform: translate(calc(var(--g) * -0.7), calc(var(--g) * 0.6))}64%,82%{transform: translate(calc(var(--g) * 0.4), calc(var(--g) * 0.6))}"),
    _keyframes("lid-sad", 5.6, "0%,1%,13%,84%,90%,100%{transform: none}2%,12%{transform: scale(1.06, 0.45)}87%{transform: scale(1, 0.15)}"),
    _keyframes("body-sink", 5.6, f"0%,14%,100%{{transform: none}}2%,6%,10%{{transform: translate(-1.4px, 0)}}4%,8%,12%{{transform: translate(1.4px, 0)}}"
               f"36%,82%{{transform: translate(0, 3px) {SQ.format(0.025, 0.05)} {WOB.format(-1)}}}"),
    _keyframes("body-float", 6.0, f"0%,100%{{transform: none}}50%{{transform: translate(0, -2.5px) {SQ.format(0.008, -0.02)}}}"),
    _keyframes("sig-pulse", 2.8, "0%,100%{opacity: 0; transform: scale(0.6)}45%,55%{opacity: 1; transform: none}"),
    _keyframes("sig-blink", 1.2, "0%,38%,62%,100%{opacity: 0}44%,56%{opacity: 1}"),
)) + "@media (prefers-reduced-motion: reduce){.am-a{animation: none}.am-smil{display: none}.am-still{display: inline !important}}</style>"


def _delay(seed):
    return -(int(hashlib.md5(seed.encode()).hexdigest(), 16) % 96) / 10


def _style(css):
    return f' style="{css}"'


def _animate(cls, still, extra=""):
    return "" if still else f' class="am-a {cls}"{extra}'


def eye_grow(size):
    return min(EYE_CAP, max(1.0, EYE_MIN_PX * 50 / (EYE["pill"][0] * size)))


def eye_pair(shape, size, key):
    _, gx, gy, left, right = key
    ey, dx, cx = _anchor(shape)
    reach = 0.7 if size < SMALL else 1.0
    grow = eye_grow(size)
    fx, fy = 1.0, 1.0
    gap = max(3.0, EYE_GAP_PX * 100 / size) / 2
    pair = []
    for side, (name, s, dy) in ((-1, left), (1, right)):
        pts = expression(name)
        inner = -min(x for x, y in pts) * fx
        scale = min(grow * s, (dx - gap) / inner) if inner > 0 else grow * s
        x0, y0 = cx + reach * gx + side * dx, ey + reach * (gy + dy) * fy
        pair.append([(x0 + side * x * fx * scale, y0 + y * fy * scale) for x, y in pts])
    return pair


def eye_frames(shape, size, state, still=False):
    if state == "offline":
        return 0, []
    if still or state not in SEQUENCE:
        return 0, [(0, eye_pair(shape, size, STILL[state]))]
    dur, keys = SEQUENCE[state]
    return dur, [(k[0], eye_pair(shape, size, k)) for k in keys]


def _d(points):
    return "M" + " ".join(f"{x:.1f} {y:.1f}" for x, y in points) + "Z"


def eyes(shape, colour, size, state, still=False, fill=None, seed=""):
    if state == "offline":
        return ""
    fill = fill or WHITE
    rest = "".join(f'<path d="{_d(p)}" fill="{fill}"/>' for p in eye_pair(shape, size, STILL[state]))
    if still or state not in SEQUENCE:
        return rest
    dur, frames = eye_frames(shape, size, state)
    times = ";".join(f"{t:g}" for t, _ in frames)
    splines = ";".join([EYE_SPLINE] * (len(frames) - 1))
    begin = _delay(seed or shape)
    live = "".join(f'<path d="{_d(frames[0][1][side])}" fill="{fill}"><animate attributeName="d" values="{";".join(_d(pair[side]) for _, pair in frames)}" '
                   f'keyTimes="{times}" dur="{dur}s" begin="{begin:.1f}s" repeatCount="indefinite" calcMode="spline" keySplines="{splines}"/></path>' for side in (0, 1))
    return f'<g class="am-smil">{live}</g><g class="am-still" style="display: none">{rest}</g>'


def _variant(shape, size):
    return shape + "-small" if shape in BRAND_SHAPES and size < 24 else shape


_CUTS = itertools.count()


def _signature(shape, state, still):
    sig = BRAND.get(shape, {})
    if still or not sig:
        return ""
    if "balls" in sig and state in ("busy", "working"):
        kind, half = ("blink", 0.6) if state == "working" else ("pulse", 1.4)
        return "".join(f'<circle class="am-a am-sig-{kind}" cx="{x:.1f}" cy="{y:.1f}" r="{r * 0.46:.1f}" fill="{EYE_INK}" opacity="0" '
                       f'style="transform-origin: {x:.1f}px {y:.1f}px; animation-delay: calc(var(--d, 0s) + {k * half:.1f}s)"/>' for k, (x, y, r) in enumerate(balls(shape)))
    return ""


def _masked(d, colour, holes, extra=""):
    cut = f"am-cut-{next(_CUTS)}"
    return (f'<mask id="{cut}" maskUnits="userSpaceOnUse" x="-40" y="-40" width="180" height="180">'
            f'<rect x="-40" y="-40" width="180" height="180" fill="#fff"/>{holes}</mask>'
            f'<path d="{d}" fill="{colour}" mask="url(#{cut})"{extra}/>')


def _filled(d, colour, eyes, extra=""):
    return f'<path d="{d}" fill="{colour}"{extra}/>{eyes}'


def figure(shape, colour, size, state="idle", still=False, seed="", cut=False, theme=None):
    o = outline(shape)
    sig = BRAND.get(shape, {})
    if sig and state == "paused":
        thin = size < SMALL
        width = 5.5 if thin else 3.6
        body = (f'<path d="{o["d"]}" fill="none" stroke="{rgb(NEUTRAL)}" stroke-width="{width}" '
                f'stroke-dasharray="{"8 6" if thin else "6.5 5"}" stroke-linecap="round"/>')
        return body + eyes(shape, colour, size, state, still, fill=rgb(NEUTRAL), seed=seed)
    if state == "offline":
        return f'<path d="{o["d"]}" fill="{body_fill(colour, theme)}" opacity="0.3"/>'
    if cut:
        return _masked(o["d"], body_fill(colour, theme), eyes(shape, colour, size, state, still, fill="#000", seed=seed) + _signature(shape, state, still).replace(EYE_INK, "#000"))
    return _filled(o["d"], body_fill(colour, theme), eyes(shape, colour, size, state, still, fill=EYE_INK, seed=seed) + _signature(shape, state, still))


def mark(shape, colour, size=16, state="idle", seed="", still=False):
    still = still or size < MOTION_MIN
    name, shape = shape, _variant(shape, size)
    inner = figure(shape, colour, size, state, still, seed or name)
    if state in BODY and not still:
        o = outline(shape)
        stretch, wobble, pivot = CHARACTER[shape]
        oy = {"bottom": o["bottom"], "top": o["top"], "centre": 50}[pivot]
        inner = f'<g class="am-a am-body-{BODY[state]}" style="--s: {stretch}; --w: {wobble}; transform-origin: 50px {oy:.1f}px">{inner}</g>'
    delay = "" if still else f"; --d: {_delay(seed or name):.1f}s"
    return (f'<svg viewBox="0 0 100 100" width="{size}" height="{size}" role="img" aria-label="{name} {STATE_LABEL[state]}" data-mark="{name}" '
            f'style="flex-shrink: 0; display: block; overflow: visible{delay}">{inner}</svg>')


def tile(inner, colour, size, tinted=None):
    return (f'<span style="width: {size}px; height: {size}px; border-radius: {size * TILE_RADIUS:.1f}px; background: {tinted or tint(colour)}; '
            f'display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0">{inner}</span>')


def tiled(shape, colour, size, state="idle", seed="", still=False, tinted=None):
    side = round(size * TILE_SCALE / 2) * 2
    return tile(mark(shape, colour, size, state, seed, still), colour, side, tinted)


@lru_cache(maxsize=None)
def shipped_accents():
    script = f"import {{ACCENTS}} from {json.dumps(os.path.join(COMMON, 'accents.mjs'))};process.stdout.write(JSON.stringify(ACCENTS));"
    out = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True, check=True)
    return [tuple(pair) for pair in json.loads(out.stdout)]


PALETTE = shipped_accents()
COLOUR = dict(PALETTE)

def _superellipse(cx, cy, half, n=5.0, steps=96):
    pts = []
    for i in range(steps):
        t = 2 * math.pi * i / steps
        c, si = math.cos(t), math.sin(t)
        pts.append((cx + half * math.copysign(abs(c) ** (2 / n), c), cy + half * math.copysign(abs(si) ** (2 / n), si)))
    return "M" + "L".join(f"{x:.2f} {y:.2f}" for x, y in pts) + "Z"


ICON_SIDE = 80.47
ICON_TILE = _superellipse(50, 50, ICON_SIDE / 2)
ICON_FILL = 0.6
ICONS = {
    "paper": dict(title="Paper", sub="ink on warm paper", top="#fcfaf5", bottom="#ece6da", body=BRAND_INK, light=0.9, rim="#14110c", rim_alpha=0.1, zoom=1.0),
    "night": dict(title="Night", sub="cream on night", top="#2a2620", bottom="#0c0b09", body=CREAM, light=0.16, rim="#000000", rim_alpha=0.4, zoom=1.0),
    "white": dict(title="White", sub="ink on white", top="#ffffff", bottom="#f3f3f3", body=BRAND_INK, light=0.9, rim="#14110c", rim_alpha=0.1, zoom=1.0),
    "close-white": dict(title="Close-up · white", sub="ink on white, overscaled and cropped", top="#ffffff", bottom="#f3f3f3", body=BRAND_INK, light=0.9, rim="#14110c", rim_alpha=0.1, zoom=None),
    "close": dict(title="Close-up", sub="cream on night, overscaled and cropped", top="#2a2620", bottom="#0c0b09", body=CREAM, light=0.16, rim="#000000", rim_alpha=0.4, zoom=None),
}
CLOSE = {"alpi-twin": (1.0, 16)}
_ICON_IDS = itertools.count()


def icon_pose(shape, concept):
    o = outline(shape)
    if ICONS[concept]["zoom"] is None:
        scale, top = CLOSE[shape]
        return scale, 50.0, top - scale * (o["top"] - 50)
    w, h = o["right"] - o["left"], o["bottom"] - o["top"]
    scale = ICON_SIDE * ICON_FILL / max(w, h)
    return scale, 50 - scale * ((o["left"] + o["right"]) / 2 - 50), 50 - scale * ((o["top"] + o["bottom"]) / 2 - 50)


def app_icon(shape, concept, size=120, shadow=True, bleed=False):
    scale, tx, ty = icon_pose(shape, concept)
    px = size * scale / (ICON_SIDE / 100 if bleed else 1)
    return icon_svg(shape, concept, size, figure(_variant(shape, px), ICONS[concept]["body"], px, still=True, cut=True), (scale, tx, ty), shadow, bleed)


def icon_svg(shape, concept, size, art, pose, shadow=True, bleed=False):
    spec = ICONS[concept]
    scale, tx, ty = pose
    n = next(_ICON_IDS)
    fill, edge, clip, drop = (f"am-icon-{part}-{n}" for part in ("fill", "edge", "clip", "drop"))
    shade = f' filter="url(#{drop})"' if shadow and not bleed else ""
    box = f"{50 - ICON_SIDE / 2:.2f} {50 - ICON_SIDE / 2:.2f} {ICON_SIDE:.2f} {ICON_SIDE:.2f}" if bleed else "0 0 100 100"
    defs = (f'<linearGradient id="{fill}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{rgb(spec["top"])}"/><stop offset="1" stop-color="{rgb(spec["bottom"])}"/></linearGradient>'
            f'<linearGradient id="{edge}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="rgb(255, 255, 255)" stop-opacity="{spec["light"]}"/>'
            f'<stop offset="0.3" stop-color="rgb(255, 255, 255)" stop-opacity="0"/><stop offset="0.8" stop-color="{rgb(spec["rim"])}" stop-opacity="0"/>'
            f'<stop offset="1" stop-color="{rgb(spec["rim"])}" stop-opacity="{spec["rim_alpha"]}"/></linearGradient>'
            f'<clipPath id="{clip}"><path d="{ICON_TILE}"/></clipPath>'
            f'<filter id="{drop}" x="-20%" y="-20%" width="140%" height="150%"><feDropShadow dx="0" dy="1.6" stdDeviation="1.8" flood-color="rgb(0, 0, 0)" flood-opacity="0.22"/>'
            f'<feDropShadow dx="0" dy="0.3" stdDeviation="0.3" flood-color="rgb(0, 0, 0)" flood-opacity="0.18"/></filter>')
    return (f'<svg viewBox="{box}" width="{size}" height="{size}" role="img" aria-label="app icon, {shape}, {spec["title"]}" data-icon="{shape}-{concept}" '
            f'style="flex-shrink: 0; display: block; overflow: visible"><defs>{defs}</defs><path d="{ICON_TILE}" fill="url(#{fill})"{shade}/>'
            f'<g clip-path="url(#{clip})"><g transform="translate({tx:.2f} {ty:.2f}) scale({scale:.3f}) translate(-50 -50)">{art}</g></g>'
            f'<path d="{ICON_TILE}" fill="none" stroke="url(#{edge})" stroke-width="1.1" clip-path="url(#{clip})"/></svg>')
