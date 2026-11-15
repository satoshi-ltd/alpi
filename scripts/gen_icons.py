#!/usr/bin/env python3
import argparse
import json
import math
import re
import struct
import subprocess
import sys
import zlib
from functools import lru_cache
from itertools import accumulate
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MARKS = REPO / "common" / "agentMarks.mjs"

TWIN = "alpi-twin"
TWIN_SMALL = "alpi-twin-small"
SMALL_BELOW = 24
LIGHT_ACCENT = "#14110c"
DARK_ACCENT = "#f3efe6"
FAVICON_ACCENT = "#14110c"
WHITE = (0xFF, 0xFF, 0xFF)
PAPER = WHITE
INK = (0x0C, 0x0B, 0x09)
TINT_GROUND = (0, 0, 0)
TINT_INK = (255, 255, 255)
TILE_TOP = (0xFF, 0xFF, 0xFF)
TILE_BOTTOM = (0xF3, 0xF3, 0xF3)
RIM = (0x14, 0x11, 0x0C)
SUPERSAMPLE = 8
TURN_ORIGIN = (50.0, 55.0)
HALF_TURN = 0.5
ICON_SIDE = 80.47
ICON_EXPONENT = 5.0
ICON_STEPS = 96
ICON_FILL = 0.6
CLOSE_SCALE = 1.0
CLOSE_TOP = 16.0
CLOSE_MIN = 128
SHADOWS = ((1.6, 1.8, 0.22), (0.3, 0.3, 0.18))
EDGE_WIDTH = 1.1
EDGE_LIGHT = 0.9
EDGE_RIM = 0.1
SAFE_RADIUS = 0.306
SAFE_FILL = 0.97
SPLASH_MARK = 0.88
FAVICON_MARK = 0.92
TRAY_FIT = (1.0349, 44.45, 49.15)
TRAY_STATES = ("quiet", "dot", "needs", "offline")
TRAY_SIZES = (16, 20, 22, 24, 32, 36)
TRAY_DIR = "desktop/src-tauri/icons/tray"
BADGE = (80.0, 80.0)
BADGE_KNOCK = 23.0
DOT_RADIUS = 15.0
RING_RADIUS = 12.0
RING_WIDTH = 7.0
SLASH_KNOCK = ((10.0, 10.0), (92.0, 92.0), 22.0)
SLASH = ((12.0, 12.0), (90.0, 90.0), 9.0)
ICNS_ENTRIES = ((b"ic07", 128), (b"ic08", 256), (b"ic09", 512), (b"ic10", 1024), (b"ic11", 32), (b"ic12", 64), (b"ic13", 256), (b"ic14", 512))
ICO_SIZES = (16, 32, 48, 64, 128, 256)
SINGLE_INK = ("mobile/assets/ios-tinted.png", "mobile/assets/favicon.png")
SITE_MARKS = {"site/assets/alpi-black.svg": "#14110c", "site/assets/alpi-white.svg": "#ffffff"}


def node(script):
    try:
        out = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True, check=True)
    except FileNotFoundError:
        raise SystemExit("gen_icons.py needs node on PATH to read the shared marks in common/")
    return json.loads(out.stdout)


@lru_cache(maxsize=None)
def marks():
    script = (
        f"import * as m from {json.dumps(str(MARKS))};"
        f"process.stdout.write(JSON.stringify({{shapes: {{{json.dumps(TWIN)}: m.SHAPES[{json.dumps(TWIN)}], {json.dumps(TWIN_SMALL)}: m.SHAPES[{json.dumps(TWIN_SMALL)}]}},"
        "rest: m.EXPRESSIONS.rest, still: m.STILL.idle, pose: m.POSE.idle, turn: m.TURN,"
        "eye: {min: m.EYE_MIN_PX, cap: m.EYE_CAP, half: m.EYE_PILL_HALF, gap: m.EYE_GAP_PX}, small: m.SMALL}));"
    )
    return node(script)


def rgb_of(hex_colour):
    return tuple(int(hex_colour[i:i + 2], 16) for i in (1, 3, 5))


def hex_of(rgb):
    return "#" + "".join(f"{v:02x}" for v in rgb)


def variant(size):
    return TWIN_SMALL if size < SMALL_BELOW else TWIN


def held_pose():
    return tuple(marks()["turn"]["still"]["idle"])


def half_pose():
    return tuple(a * HALF_TURN for a in held_pose())


def knots(shape):
    numbers = [float(v) for v in re.findall(r"-?\d+(?:\.\d+)?", marks()["shapes"][shape]["d"])]
    points = [tuple(numbers[i:i + 2]) for i in range(0, len(numbers), 2)]
    out = [points[0]] + points[3::3]
    return out[:-1] if out[-1] == out[0] else out


def project(points, pose):
    ry, rx, rz = (math.radians(a) for a in pose)
    ox, oy = TURN_ORIGIN
    depth = marks()["turn"]["depth"]
    out = []
    for x, y in points:
        px, py, pz = x - ox, y - oy, 0.0
        px, py = px * math.cos(rz) - py * math.sin(rz), px * math.sin(rz) + py * math.cos(rz)
        py, pz = py * math.cos(rx) - pz * math.sin(rx), py * math.sin(rx) + pz * math.cos(rx)
        px, pz = px * math.cos(ry) + pz * math.sin(ry), -px * math.sin(ry) + pz * math.cos(ry)
        w = 1 - pz / (100 * depth)
        out.append((50 + (px + ox - 50) / w, 50 + (py + oy - 50) / w))
    return out


def eye_pair(shape, size):
    data, spec = marks(), marks()["shapes"][shape]
    eye = data["eye"]
    ey, dx, cx = spec["eyeY"], spec["eyeDx"], spec["eyeX"]
    _, gx, gy, left, right = data["still"]
    reach = 0.7 if size < data["small"] else 1.0
    grow = min(eye["cap"], max(1.0, eye["min"] * 50 / (eye["half"] * size)))
    gap = max(3.0, eye["gap"] * 100 / size) / 2
    pts = [tuple(p) for p in data["rest"]]
    inner = -min(x for x, _ in pts)
    pair = []
    for side, (_, s, dy) in ((-1, left), (1, right)):
        scale = min(grow * s, (dx - gap) / inner) if inner > 0 else grow * s
        x0, y0 = cx + reach * gx + side * dx, ey + reach * (gy + dy)
        pair.append([(x0 + side * x * scale, y0 + y * scale) for x, y in pts])
    return pair


def turned_parts(size, pose):
    shape = variant(size)
    body = project(knots(shape), pose)
    spec, still = marks()["shapes"][shape], marks()["pose"]
    ox, oy = spec["eyeX"] + still["shift"], spec["eyeY"] + still["lift"]
    turn = marks()["turn"]
    sy, sx = math.sin(math.radians(pose[0])), math.sin(math.radians(pose[1]))
    slide = (turn["slide"][0] * sy, -turn["slide"][1] * sx)
    squeeze = (1 - turn["squeeze"] * abs(sy), 1 - turn["squeeze"] * abs(sx))
    eyes = [project([(ox + slide[0] + (x - ox) * squeeze[0], oy + slide[1] + (y - oy) * squeeze[1]) for x, y in eye], pose)
            for eye in eye_pair(shape, size)]
    return body, eyes


def bezier(points):
    n = len(points)
    segments = []
    for i in range(n):
        p0, p1, p2, p3 = points[i - 1], points[i], points[(i + 1) % n], points[(i + 2) % n]
        d1, d2, d3 = (max(math.dist(a, b), 1e-6) ** 0.5 for a, b in ((p0, p1), (p1, p2), (p2, p3)))
        c1 = tuple((d1 * d1 * p2[k] - d2 * d2 * p0[k] + (2 * d1 * d1 + 3 * d1 * d2 + d2 * d2) * p1[k]) / (3 * d1 * (d1 + d2)) for k in (0, 1))
        c2 = tuple((d3 * d3 * p1[k] - d2 * d2 * p3[k] + (2 * d3 * d3 + 3 * d3 * d2 + d2 * d2) * p2[k]) / (3 * d3 * (d3 + d2)) for k in (0, 1))
        segments.append((p1, c1, c2, p2))
    return segments


def flatten(segments, unit):
    out = []
    for p0, c1, c2, p3 in segments:
        steps = max(4, math.ceil(math.dist(p0, p3) * unit / 2))
        for k in range(steps):
            t = k / steps
            u = 1 - t
            out.append(tuple(u * u * u * p0[i] + 3 * u * u * t * c1[i] + 3 * u * t * t * c2[i] + t * t * t * p3[i] for i in (0, 1)))
    return out


def twin_polygons(size, pose, scale, tx, ty):
    body, eyes = turned_parts(size, pose)
    unit = size / 100 * scale

    def place(points):
        return [((tx + scale * (x - 50)) * size / 100, (ty + scale * (y - 50)) * size / 100) for x, y in points]

    return [place(flatten(bezier(body), unit))] + [place(eye) for eye in eyes]


def bounds(points):
    xs, ys = [x for x, _ in points], [y for _, y in points]
    return min(xs), max(xs), min(ys), max(ys)


def fit_pose(pose, fill):
    left, right, top, bottom = bounds(turned_parts(100, pose)[0])
    scale = fill * 100 / max(right - left, bottom - top)
    return scale, 50 - scale * ((left + right) / 2 - 50), 50 - scale * ((top + bottom) / 2 - 50)


def close_pose():
    left, right, top, bottom = bounds(turned_parts(100, held_pose())[0])
    return CLOSE_SCALE, 50 - CLOSE_SCALE * ((left + right) / 2 - 50), CLOSE_TOP - CLOSE_SCALE * (top - 50)


def full_pose():
    return fit_pose(held_pose(), ICON_SIDE * ICON_FILL / 100)


def bleed(pose):
    scale, tx, ty = pose
    k = 100 / ICON_SIDE
    return scale * k, 50 + (tx - 50) * k, 50 + (ty - 50) * k


def safe_pose(pose_angles):
    body, _ = turned_parts(100, pose_angles)
    left, right, top, bottom = bounds(body)
    cx, cy = (left + right) / 2, (top + bottom) / 2
    reach = max(math.hypot(x - cx, y - cy) for x, y in body)
    scale = SAFE_RADIUS * 100 * SAFE_FILL / reach
    return scale, 50 - scale * (cx - 50), 50 - scale * (cy - 50)


def superellipse(size, half):
    n, out = ICON_EXPONENT, []
    for i in range(ICON_STEPS):
        t = 2 * math.pi * i / ICON_STEPS
        c, s = math.cos(t), math.sin(t)
        out.append(((50 + half * math.copysign(abs(c) ** (2 / n), c)) * size / 100, (50 + half * math.copysign(abs(s) ** (2 / n), s)) * size / 100))
    return out


def tile_distance(x, y, size, dy=0.0):
    u, v = (x * 100 / size - 50) / (ICON_SIDE / 2), (y * 100 / size - 50 - dy) / (ICON_SIDE / 2)
    au, av, n = abs(u), abs(v), ICON_EXPONENT
    f = (au ** n + av ** n) ** (1 / n)
    if f < 1e-6:
        return -ICON_SIDE / 2
    gu, gv = au ** (n - 1) / f ** (n - 1), av ** (n - 1) / f ** (n - 1)
    return (f - 1) * (ICON_SIDE / 2) / max(math.hypot(gu, gv), 1e-6)


def circle(cx, cy, r, steps=96):
    return [(cx + r * math.cos(2 * math.pi * i / steps), cy + r * math.sin(2 * math.pi * i / steps)) for i in range(steps)]


def capsule(a, b, width, steps=48):
    (ax, ay), (bx, by), r = a, b, width / 2
    angle = math.atan2(by - ay, bx - ax)

    def arc(cx, cy, start):
        return [(cx + r * math.cos(start + math.pi * i / steps), cy + r * math.sin(start + math.pi * i / steps)) for i in range(steps + 1)]

    return arc(bx, by, angle - math.pi / 2) + arc(ax, ay, angle + math.pi / 2)


class Region:
    def __init__(self, polygons):
        edges = []
        for poly in polygons:
            for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
                if y1 == y2:
                    continue
                if y1 > y2:
                    x1, y1, x2, y2 = x2, y2, x1, y1
                edges.append((y1, y2, x1, (x2 - x1) / (y2 - y1)))
        edges.sort()
        self.edges = edges

    def scan(self, height):
        edges, nxt, active = self.edges, 0, []
        for row in range(height):
            for sub in range(SUPERSAMPLE):
                ys = row + (sub + 0.5) / SUPERSAMPLE
                while nxt < len(edges) and edges[nxt][0] <= ys:
                    active.append(edges[nxt])
                    nxt += 1
                active = [e for e in active if e[1] > ys]
                xs = sorted(x + (ys - y1) * slope for y1, _, x, slope in active)
                yield list(zip(xs[::2], xs[1::2]))


def union(a, b):
    out = []
    for lo, hi in sorted(a + b):
        if out and lo <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], hi))
        else:
            out.append((lo, hi))
    return out


def intersect(a, b):
    out, i, j = [], 0, 0
    while i < len(a) and j < len(b):
        lo, hi = max(a[i][0], b[j][0]), min(a[i][1], b[j][1])
        if lo < hi:
            out.append((lo, hi))
        if a[i][1] < b[j][1]:
            i += 1
        else:
            j += 1
    return out


def subtract(a, b):
    out = []
    for lo, hi in a:
        for blo, bhi in b:
            if bhi <= lo or blo >= hi:
                continue
            if blo > lo:
                out.append((lo, blo))
            lo = max(lo, bhi)
            if lo >= hi:
                break
        if lo < hi:
            out.append((lo, hi))
    return out


def coverage(lines, width, height):
    w = 1 / SUPERSAMPLE
    grid = []
    for _ in range(height):
        part, diff = [0.0] * (width + 1), [0.0] * (width + 1)
        for _ in range(SUPERSAMPLE):
            for a, b in next(lines):
                a, b = max(a, 0.0), min(b, float(width))
                if b <= a:
                    continue
                i0, i1 = int(a), int(b)
                if i0 == i1:
                    part[i0] += (b - a) * w
                    continue
                part[i0] += (i0 + 1 - a) * w
                part[i1] += (b - i1) * w
                diff[i0 + 1] += w
                diff[i1] -= w
        grid.append([min(1.0, round(r + p, 9)) for r, p in zip(accumulate(diff[:width]), part)])
    return grid


def combine(op, *regions):
    return (op(*parts) for parts in zip(*regions))


def over(dst, colour, alpha):
    if alpha <= 0:
        return dst
    r, g, b, a = dst
    keep = 1 - alpha
    return (colour[0] * alpha + r * keep, colour[1] * alpha + g * keep, colour[2] * alpha + b * keep, alpha + a * keep)


def encode(px, rgb):
    r, g, b, a = px
    if a <= 0:
        return b"\x00\x00\x00" if rgb else b"\x00\x00\x00\x00"
    out = bytes(max(0, min(255, round(v / a))) for v in (r, g, b))
    return out if rgb else out + bytes([max(0, min(255, round(a * 255)))])


def png(size, raw, rgb):
    def chunk(tag, data):
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    header = struct.pack(">IIBBBBB", size, size, 8, 2 if rgb else 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")


def mark_coverage(size, pose_angles, placement, clip=None):
    polys = twin_polygons(size, pose_angles, *placement)
    lines = Region(polys).scan(size)
    if clip is not None:
        lines = combine(intersect, lines, Region([clip]).scan(size))
    return coverage(lines, size, size)


def tile_icon(size):
    close = size >= CLOSE_MIN
    placement = close_pose() if close else full_pose()
    half = ICON_SIDE / 2
    tile = superellipse(size, half)
    tile_cov = coverage(Region([tile]).scan(size), size, size)
    inner = coverage(Region([superellipse(size, half - EDGE_WIDTH / 2 - 1)]).scan(size), size, size)
    reach = max(dy + 4 * sigma for dy, sigma, _ in SHADOWS) + 1
    outer = coverage(Region([superellipse(size, half + reach)]).scan(size), size, size)
    mark = mark_coverage(size, held_pose(), placement, tile if close else None)
    ink = rgb_of(LIGHT_ACCENT)
    ppu = size / 100
    top = 50 - half
    raw = bytearray()
    for y in range(size):
        cy = y + 0.5
        t = min(1.0, max(0.0, (cy / ppu - top) / ICON_SIDE))
        ground = tuple(TILE_TOP[k] + (TILE_BOTTOM[k] - TILE_TOP[k]) * t for k in range(3))
        light = EDGE_LIGHT * max(0.0, 1 - t / 0.3)
        rim = EDGE_RIM * max(0.0, (t - 0.8) / 0.2)
        cache = {}
        raw.append(0)
        for x in range(size):
            tc, mc = tile_cov[y][x], mark[y][x]
            if outer[y][x] == 0:
                raw += b"\x00\x00\x00\x00"
                continue
            if inner[y][x] == 1:
                hit = cache.get(mc)
                if hit is None:
                    hit = cache[mc] = encode(over((*ground, 1.0), ink, mc), False)
                raw += hit
                continue
            cx = x + 0.5
            px = (0.0, 0.0, 0.0, 0.0)
            if tc < 1:
                for dy, sigma, opacity in SHADOWS:
                    d = tile_distance(cx, cy, size, dy)
                    if d < 4 * sigma:
                        px = over(px, (0, 0, 0), opacity * 0.5 * math.erfc(d / (sigma * math.sqrt(2))))
            px = over(px, ground, tc)
            px = over(px, ink, mc)
            if (light or rim) and tc > 0:
                d = tile_distance(cx, cy, size) * ppu
                band = min(1.0, 0.5 - d) - min(1.0, max(0.0, 0.5 - d - EDGE_WIDTH / 2 * ppu))
                if band > 0:
                    px = over(px, WHITE, light * band) if light else over(px, RIM, rim * band)
            raw += encode(px, False)
    return png(size, bytes(raw), False)


def flat_icon(size, ground, accent, placement, pose_angles=None, rgb=False):
    mark = mark_coverage(size, pose_angles or held_pose(), placement)
    ink = rgb_of(accent)
    base = (*ground, 1.0) if ground else (0.0, 0.0, 0.0, 0.0)
    cache = {}

    def pixel(c):
        hit = cache.get(c)
        if hit is None:
            hit = cache[c] = encode(over(base, ink, c), rgb)
        return hit

    return png(size, b"".join(b"\x00" + b"".join(map(pixel, row)) for row in mark), rgb)


def tray_regions(size, state):
    k = size / 100
    scale, cx, cy = TRAY_FIT

    def place(points):
        return [((50 + scale * (x - cx)) * k, (50 + scale * (y - cy)) * k) for x, y in points]

    body, eyes = turned_parts(size * scale, half_pose())
    mark = Region([place(flatten(bezier(body), size / 100 * scale))] + [place(e) for e in eyes]).scan(size)

    def scaled(points):
        return [(x * k, y * k) for x, y in points]

    if state == "quiet":
        return mark
    if state == "offline":
        knock = Region([scaled(capsule(*SLASH_KNOCK))]).scan(size)
        badge = Region([scaled(capsule(*SLASH))]).scan(size)
    else:
        knock = Region([scaled(circle(*BADGE, BADGE_KNOCK))]).scan(size)
        if state == "dot":
            badge = Region([scaled(circle(*BADGE, DOT_RADIUS))]).scan(size)
        else:
            badge = Region([scaled(circle(*BADGE, RING_RADIUS + RING_WIDTH / 2)), scaled(circle(*BADGE, RING_RADIUS - RING_WIDTH / 2))]).scan(size)
    return combine(union, combine(subtract, mark, knock), badge)


def tray_alpha(state, size):
    grid = coverage(tray_regions(size, state), size, size)
    return [[255 if c >= 0.5 else 0 for c in row] for row in grid]


def alpha_png(alpha, ink=None):
    ink = bytes(rgb_of(ink or LIGHT_ACCENT))
    raw = b"".join(b"\x00" + b"".join(ink + bytes([a]) for a in row) for row in alpha)
    return png(len(alpha), raw, False)


def tray_files():
    return {f"{TRAY_DIR}/tray-{state}-{size}.png": alpha_png(tray_alpha(state, size)) for state in TRAY_STATES for size in TRAY_SIZES}


def site_mark(colour):
    body, eyes = turned_parts(100, half_pose())
    left, right, top, bottom = bounds(body)

    def f(p):
        return f"{p[0]:.2f} {p[1]:.2f}"

    d = "M" + f(body[0]) + "".join(f" C{f(c1)} {f(c2)} {f(p)}" for _, c1, c2, p in bezier(body)) + " Z"
    d += "".join("M" + " ".join(f(p) for p in eye) + "Z" for eye in eyes)
    box = f"{left - 1:.2f} {top - 1:.2f} {right - left + 2:.2f} {bottom - top + 2:.2f}"
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{box}" role="img" aria-label="alpi logo">\n'
            f'  <path d="{d}" fill="{colour}" fill-rule="evenodd"/>\n</svg>\n').encode()


def build_icns(images):
    chunks = b"".join(tag + struct.pack(">I", 8 + len(images[size])) + images[size] for tag, size in ICNS_ENTRIES)
    return b"icns" + struct.pack(">I", 8 + len(chunks)) + chunks


def build_ico(images):
    count = len(ICO_SIZES)
    offset = 6 + 16 * count
    directory, payload = b"", b""
    for size in ICO_SIZES:
        data = images[size]
        directory += struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(data), offset + len(payload))
        payload += data
    return struct.pack("<HHH", 0, 1, count) + directory + payload


def generate():
    files = {}
    tiles = {size: tile_icon(size) for size in sorted({s for _, s in ICNS_ENTRIES} | set(ICO_SIZES) | {32, 64, 128, 256, 512})}
    for name, size in (("32x32", 32), ("64x64", 64), ("128x128", 128), ("128x128@2x", 256), ("icon", 512)):
        files[f"desktop/src-tauri/icons/{name}.png"] = tiles[size]
    files["desktop/src-tauri/icons/icon.icns"] = build_icns(tiles)
    files["desktop/src-tauri/icons/icon.ico"] = build_ico(tiles)
    close = bleed(close_pose())
    files["mobile/assets/ios-light.png"] = flat_icon(1024, PAPER, LIGHT_ACCENT, close)
    files["mobile/assets/ios-dark.png"] = flat_icon(1024, INK, DARK_ACCENT, close)
    files["mobile/assets/ios-tinted.png"] = flat_icon(1024, TINT_GROUND, hex_of(TINT_INK), close)
    files["mobile/assets/icon.png"] = flat_icon(1024, PAPER, LIGHT_ACCENT, close, rgb=True)
    files["mobile/assets/adaptive-icon.png"] = flat_icon(1024, None, LIGHT_ACCENT, safe_pose(held_pose()))
    splash = fit_pose(held_pose(), SPLASH_MARK)
    files["mobile/assets/splash-icon-light.png"] = flat_icon(1024, None, LIGHT_ACCENT, splash)
    files["mobile/assets/splash-icon-dark.png"] = flat_icon(1024, None, DARK_ACCENT, splash)
    files["mobile/assets/favicon.png"] = flat_icon(96, None, FAVICON_ACCENT, fit_pose(half_pose(), FAVICON_MARK), half_pose())
    files.update(tray_files())
    for rel, colour in SITE_MARKS.items():
        files[rel] = site_mark(colour)
    return files


def png_fingerprint(data):
    pos, header, idat = 8, None, b""
    while pos < len(data):
        length, tag = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + length]
        if tag == b"IHDR":
            header = body
        elif tag == b"IDAT":
            idat += body
        pos += 12 + length
    return ("png", header, zlib.decompress(idat))


def fingerprint(path, data):
    if path.endswith(".svg"):
        return ("svg", data)
    if path.endswith(".icns"):
        pos, out = 8, []
        while pos < len(data):
            tag, length = struct.unpack(">4sI", data[pos:pos + 8])
            out.append((tag, png_fingerprint(data[pos + 8:pos + length])))
            pos += length
        return ("icns", tuple(out))
    if path.endswith(".ico"):
        count = struct.unpack("<H", data[4:6])[0]
        out = []
        for k in range(count):
            w, h, _, _, _, bits, size, offset = struct.unpack("<BBBBHHII", data[6 + 16 * k:22 + 16 * k])
            out.append((w, h, bits, png_fingerprint(data[offset:offset + size])))
        return ("ico", tuple(out))
    return png_fingerprint(data)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Regenerate the app icons from Twin, the shared brand mark.")
    parser.add_argument("--check", action="store_true", help="exit 1 when a committed icon differs from the generated one")
    args = parser.parse_args(argv)
    files = generate()
    if args.check:
        stale = []
        for rel, data in files.items():
            path = REPO / rel
            if not path.exists() or fingerprint(rel, path.read_bytes()) != fingerprint(rel, data):
                stale.append(rel)
        for rel in stale:
            print(f"stale: {rel}", file=sys.stderr)
        return 1 if stale else 0
    for rel, data in files.items():
        (REPO / rel).parent.mkdir(parents=True, exist_ok=True)
        (REPO / rel).write_bytes(data)
        print(f"wrote {rel} ({len(data)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
