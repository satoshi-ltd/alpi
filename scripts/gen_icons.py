#!/usr/bin/env python3
import argparse
import json
import math
import struct
import subprocess
import sys
import zlib
from functools import lru_cache
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
COMMON = REPO / "common" / "folds.mjs"
CREASE = REPO / "common" / "crease.mjs"
DESKTOP = REPO / "desktop" / "src-tauri" / "icons"
MOBILE = REPO / "mobile" / "assets"

DARK_ACCENT = "#f3efe6"
LIGHT_ACCENT = "#14110c"
FAVICON_ACCENT = "#7a7468"
BRAND_INK = {"light": LIGHT_ACCENT, "dark": DARK_ACCENT}
PAPER = (0xFF, 0xFF, 0xFF)
INK = (0x0C, 0x0B, 0x09)
LOW_MAX = 64
SUPERSAMPLE = 8
TILE_EXPONENT = 5
TILE_FRACTION = 824 / 1024
FILL_HEIGHT = 0.82
TILE_MARK = FILL_HEIGHT * TILE_FRACTION
FULL_MARK = FILL_HEIGHT
FAVICON_MARK = 0.92
FAVICON_NOMINAL = 32
TRAY_MARK = 0.96
TRAY_NOMINAL = 32
THICK_BASE = 0.3
THICK_SLOPE = 0.012
THICK_MAX = 0.9
DOT_CENTER = 0.8
DOT_RADIUS = 0.13
DOT_RING = 0.045
TINT_GROUND = (0, 0, 0)
TINT_INK = (255, 255, 255)
SAFE_RADIUS = 0.306
SPLASH_MARK = 0.88
SAFE_FILL = 0.97
ICNS_ENTRIES = ((b"ic07", 128), (b"ic08", 256), (b"ic09", 512), (b"ic10", 1024), (b"ic11", 32), (b"ic12", 64), (b"ic13", 256), (b"ic14", 512))
ICO_SIZES = (16, 32, 48, 64, 128, 256)
SINGLE_INK = ("desktop/src-tauri/icons/tray-template.png", "desktop/src-tauri/icons/tray-template-notification.png", "mobile/assets/ios-tinted.png", "mobile/assets/favicon.png")


def node(script):
    try:
        out = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True, check=True)
    except FileNotFoundError:
        raise SystemExit("gen_icons.py needs node on PATH to read the shared folds in common/")
    return json.loads(out.stdout)


def rgb_of(hex_colour):
    return tuple(int(hex_colour[i:i + 2], 16) for i in (1, 3, 5))


def luminance(rgb):
    lin = [(v / 255 / 12.92) if v / 255 <= 0.04045 else ((v / 255 + 0.055) / 1.055) ** 2.4 for v in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


@lru_cache(maxsize=None)
def load_facets(low=False):
    script = (
        f"import {{foldFacets}} from {json.dumps(str(COMMON))};"
        f"process.stdout.write(JSON.stringify(foldFacets({json.dumps('alpaca-low' if low else 'alpaca')})));"
    )
    return [(f["tone"], [tuple(p) for p in f["points"]]) for f in node(script)]


@lru_cache(maxsize=None)
def crease_tones(accent, ground):
    script = (
        f"import {{creaseTones}} from {json.dumps(str(CREASE))};"
        f"process.stdout.write(JSON.stringify(creaseTones({json.dumps(accent)}, {json.dumps(ground)})));"
    )
    return sorted((rgb_of(h) for h in node(script)), key=luminance, reverse=True)


def hex_of(rgb):
    return "#" + "".join(f"{v:02x}" for v in rgb)


def tone_set(accent, background, flat):
    if flat:
        return [rgb_of(accent)] * 3
    return crease_tones(accent, hex_of(background))


def thickness(nominal):
    if nominal > LOW_MAX:
        return 0.0
    return min(THICK_MAX, THICK_BASE + THICK_SLOPE * (LOW_MAX - nominal))


def outset(points, d):
    n = len(points)
    area = sum(points[i][0] * points[(i + 1) % n][1] - points[(i + 1) % n][0] * points[i][1] for i in range(n))
    sign = -1 if area > 0 else 1
    lines = []
    for i, (x1, y1) in enumerate(points):
        x2, y2 = points[(i + 1) % n]
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy) or 1.0
        lines.append((x1 + (-dy / length) * sign * d, y1 + (dx / length) * sign * d, dx, dy))
    out = []
    for i, point in enumerate(points):
        px, py, ax, ay = lines[(i - 1) % n]
        qx, qy, bx, by = lines[i]
        det = ax * by - ay * bx
        if abs(det) < 1e-9:
            out.append(point)
            continue
        t = ((qx - px) * by - (qy - py) * bx) / det
        x, y = px + ax * t, py + ay * t
        vx, vy = x - point[0], y - point[1]
        reach = math.hypot(vx, vy)
        if reach > 3 * d:
            x, y = point[0] + vx * 3 * d / reach, point[1] + vy * 3 * d / reach
        out.append((x, y))
    return out


def mark_polygons(size, height=None, safe=False, nominal=None, low=None):
    nominal = nominal or size
    facets = load_facets(nominal <= LOW_MAX if low is None else low)
    pts = [p for _, poly in facets for p in poly]
    xc = (min(p[0] for p in pts) + max(p[0] for p in pts)) / 2
    yc = (min(p[1] for p in pts) + max(p[1] for p in pts)) / 2
    if safe:
        scale = SAFE_RADIUS * size * SAFE_FILL / max(math.hypot(x - xc, y - yc) for x, y in pts)
    else:
        scale = height * size / (max(p[1] for p in pts) - min(p[1] for p in pts))
    mid = size / 2
    grow = thickness(nominal) * size / nominal
    polys = [(tone + 1, [(mid + (x - xc) * scale, mid + (y - yc) * scale) for x, y in poly]) for tone, poly in facets]
    return [(tone, outset(poly, grow) if grow else poly) for tone, poly in polys]


def circle(cx, cy, r, steps=96):
    return [(cx + r * math.cos(2 * math.pi * k / steps), cy + r * math.sin(2 * math.pi * k / steps)) for k in range(steps)]


class Row:
    def __init__(self, size):
        self.size = size
        self.cov = [{} for _ in range(4)]
        self.diff = [{} for _ in range(4)]
        self.touched = {0}

    def span(self, cls, xa, xb):
        xa, xb = max(xa, 0.0), min(xb, float(self.size))
        if xb <= xa:
            return
        w = 1 / SUPERSAMPLE
        cov, diff = self.cov[cls], self.diff[cls]
        i0, i1 = int(xa), int(xb)
        if i0 == i1:
            cov[i0] = cov.get(i0, 0.0) + (xb - xa) * w
            self.touched.add(i0)
            return
        cov[i0] = cov.get(i0, 0.0) + (i0 + 1 - xa) * w
        self.touched.add(i0)
        if i1 < self.size:
            cov[i1] = cov.get(i1, 0.0) + (xb - i1) * w
            self.touched.add(i1)
        diff[i0 + 1] = diff.get(i0 + 1, 0.0) + w
        diff[i1] = diff.get(i1, 0.0) - w
        self.touched.update((i0 + 1, i1))


def compose_factory(tones, background, tile, rgb):
    cache = {}

    def compose(tile_cov, m1, m2, m3):
        key = (round(tile_cov, 7), round(m1, 7), round(m2, 7), round(m3, 7))
        hit = cache.get(key)
        if hit is not None:
            return hit
        t = 1.0 if tile == "full" else min(tile_cov, 1.0)
        ms = (m1, m2, m3)
        total = sum(ms)
        if total > 1:
            ms = tuple(m / total for m in ms)
            total = 1.0
        alpha = total + (1 - total) * t
        if alpha <= 1e-9:
            out = b"\x00\x00\x00" if rgb else b"\x00\x00\x00\x00"
        else:
            chans = []
            for k in range(3):
                prem = sum(m * tones[i][k] for i, m in enumerate(ms)) + (1 - total) * t * background[k]
                chans.append(max(0, min(255, round(prem / alpha))))
            out = bytes(chans) if rgb else bytes(chans) + bytes([max(0, min(255, round(alpha * 255)))])
        cache[key] = out
        return out

    return compose


def resolve(intervals):
    placed = []
    for a, b, cls in intervals:
        kept = []
        for pa, pb, pc in placed:
            if pb <= a or pa >= b:
                kept.append((pa, pb, pc))
                continue
            if pa < a:
                kept.append((pa, a, pc))
            if b < pb:
                kept.append((b, pb, pc))
        if cls is not None:
            kept.append((a, b, cls))
        placed = kept
    return placed


def render(size, background, tile, accent, mark_height=None, safe=False, rgb=False, flat=False, nominal=None, low=None, dot=False):
    tones = tone_set(accent, background, flat)
    polys = mark_polygons(size, mark_height, safe, nominal, low)
    if dot:
        c = DOT_CENTER * size
        polys += [(None, circle(c, c, (DOT_RADIUS + DOT_RING) * size)), (1, circle(c, c, DOT_RADIUS * size))]
    edges = []
    for cls, poly in polys:
        es = [(x1, y1, x2, y2) if y1 < y2 else (x2, y2, x1, y1) for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]) if y1 != y2]
        edges.append((cls, min(e[1] for e in es), max(e[3] for e in es), es))
    compose = compose_factory(tones, background, tile, rgb)
    mid = size / 2
    half = size * TILE_FRACTION / 2
    pixel = 3 if rgb else 4
    out = bytearray()
    for y in range(size):
        row = Row(size)
        for sub in range(SUPERSAMPLE):
            ys = y + (sub + 0.5) / SUPERSAMPLE
            if tile == "tile":
                d = abs(ys - mid) / half
                if d < 1:
                    hw = half * (1 - d ** TILE_EXPONENT) ** (1 / TILE_EXPONENT)
                    row.span(0, mid - hw, mid + hw)
            intervals = []
            for cls, ymin, ymax, es in edges:
                if ys < ymin or ys >= ymax:
                    continue
                xs = sorted(x1 + (ys - y1) * (x2 - x1) / (y2 - y1) for x1, y1, x2, y2 in es if y1 <= ys < y2)
                intervals += [(a, b, cls) for a, b in zip(xs[::2], xs[1::2])]
            for a, b, cls in resolve(intervals):
                row.span(cls, a, b)
        run = [0.0] * 4
        xs = sorted(x for x in row.touched if x < size)
        out.append(0)
        for idx, x in enumerate(xs):
            for c in range(4):
                run[c] += row.diff[c].get(x, 0.0)
            out += compose(*(run[c] + row.cov[c].get(x, 0.0) for c in range(4)))
            nxt = xs[idx + 1] if idx + 1 < len(xs) else size
            if nxt > x + 1:
                out += compose(*run) * (nxt - x - 1)
    return Image(size, rgb, bytes(out), pixel)


class Image:
    def __init__(self, size, rgb, raw, pixel):
        self.size, self.rgb, self.raw, self.pixel = size, rgb, raw, pixel

    def png(self):
        def chunk(tag, data):
            body = tag + data
            return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

        header = struct.pack(">IIBBBBB", self.size, self.size, 8, 2 if self.rgb else 6, 0, 0, 0)
        return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(self.raw, 9)) + chunk(b"IEND", b"")


def tile_icon(size):
    return render(size, PAPER, "tile", LIGHT_ACCENT, mark_height=TILE_MARK)


def tray_icon(dot):
    return render(64, PAPER, "none", LIGHT_ACCENT, mark_height=TRAY_MARK, flat=True, nominal=TRAY_NOMINAL, low=True, dot=dot)


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
    tiles = {}
    for size in sorted({s for _, s in ICNS_ENTRIES} | set(ICO_SIZES) | {32, 64, 128, 256, 512}):
        tiles[size] = tile_icon(size).png()
    for name, size in (("32x32", 32), ("64x64", 64), ("128x128", 128), ("128x128@2x", 256), ("icon", 512)):
        files[f"desktop/src-tauri/icons/{name}.png"] = tiles[size]
    files["desktop/src-tauri/icons/icon.icns"] = build_icns(tiles)
    files["desktop/src-tauri/icons/icon.ico"] = build_ico(tiles)

    light = render(1024, PAPER, "full", LIGHT_ACCENT, mark_height=FULL_MARK)
    files["mobile/assets/ios-light.png"] = light.png()
    files["mobile/assets/ios-dark.png"] = render(1024, INK, "full", DARK_ACCENT, mark_height=FULL_MARK).png()
    files["mobile/assets/icon.png"] = render(1024, PAPER, "full", LIGHT_ACCENT, mark_height=FULL_MARK, rgb=True).png()
    files["mobile/assets/adaptive-icon.png"] = render(1024, PAPER, "none", LIGHT_ACCENT, safe=True).png()
    files["mobile/assets/splash-icon-light.png"] = render(1024, PAPER, "none", LIGHT_ACCENT, mark_height=SPLASH_MARK).png()
    files["mobile/assets/splash-icon-dark.png"] = render(1024, INK, "none", DARK_ACCENT, mark_height=SPLASH_MARK).png()
    files["mobile/assets/favicon.png"] = render(96, PAPER, "none", FAVICON_ACCENT, mark_height=FAVICON_MARK, flat=True, nominal=FAVICON_NOMINAL, low=True).png()
    files["mobile/assets/ios-tinted.png"] = render(1024, TINT_GROUND, "full", hex_of(TINT_INK), mark_height=FULL_MARK, flat=True).png()
    files["desktop/src-tauri/icons/tray-template.png"] = tray_icon(False).png()
    files["desktop/src-tauri/icons/tray-template-notification.png"] = tray_icon(True).png()
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
    parser = argparse.ArgumentParser(description="Regenerate the app icons from the shared alpaca fold.")
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
        (REPO / rel).write_bytes(data)
        print(f"wrote {rel} ({len(data)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
