import importlib.util
import json
import math
import re
import struct
import subprocess
import sys
import zlib
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("gen_icons", REPO / "scripts" / "gen_icons.py")
gen = importlib.util.module_from_spec(SPEC)
sys.modules["gen_icons"] = gen
SPEC.loader.exec_module(gen)

SIZES = {
    "desktop/src-tauri/icons/32x32.png": (32, 6),
    "desktop/src-tauri/icons/64x64.png": (64, 6),
    "desktop/src-tauri/icons/128x128.png": (128, 6),
    "desktop/src-tauri/icons/128x128@2x.png": (256, 6),
    "desktop/src-tauri/icons/icon.png": (512, 6),
    "mobile/assets/icon.png": (1024, 2),
    "mobile/assets/ios-light.png": (1024, 6),
    "mobile/assets/ios-dark.png": (1024, 6),
    "mobile/assets/ios-tinted.png": (1024, 6),
    "mobile/assets/adaptive-icon.png": (1024, 6),
    "mobile/assets/favicon.png": (96, 6),
    "mobile/assets/splash-icon-light.png": (1024, 6),
    "mobile/assets/splash-icon-dark.png": (1024, 6),
}
PAPER = (0xFF, 0xFF, 0xFF)
INK = (0x0C, 0x0B, 0x09)
BRAND = (0x14, 0x11, 0x0C)
CREAM = (0xF3, 0xEF, 0xE6)
BLEED = {
    "mobile/assets/ios-light.png": (PAPER, BRAND),
    "mobile/assets/ios-dark.png": (INK, CREAM),
    "mobile/assets/ios-tinted.png": ((0, 0, 0), (255, 255, 255)),
    "mobile/assets/icon.png": (PAPER, BRAND),
}
TRAY_DIR = "desktop/src-tauri/icons/tray"
PLATFORM_SIZES = {"macos": (36,), "windows": (16, 20, 24, 32), "linux": (22, 24)}
TRAY_SIZES = sorted({n for sizes in PLATFORM_SIZES.values() for n in sizes})
STATES = ("quiet", "dot", "needs", "offline")
TRAY_FILES = [f"{TRAY_DIR}/tray-{state}-{size}.png" for state in STATES for size in TRAY_SIZES]


def decode_bytes(data):
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    pos, header, idat = 8, None, b""
    while pos < len(data):
        length, tag = struct.unpack(">I4s", data[pos:pos + 8])
        if tag == b"IHDR":
            header = struct.unpack(">IIBBBBB", data[pos + 8:pos + 21])
        elif tag == b"IDAT":
            idat += data[pos + 8:pos + 8 + length]
        pos += 12 + length
    width, height, depth, ctype, *_ = header
    assert depth == 8 and ctype in (2, 6)
    channels = 3 if ctype == 2 else 4
    raw = zlib.decompress(idat)
    stride = width * channels
    assert len(raw) == height * (stride + 1) and all(raw[y * (stride + 1)] == 0 for y in range(height))
    rows = [[tuple(raw[y * (stride + 1) + 1 + x * channels:y * (stride + 1) + 1 + (x + 1) * channels]) + ((255,) if channels == 3 else ()) for x in range(width)] for y in range(height)]
    return width, height, ctype, rows


def decode(rel):
    return decode_bytes((REPO / rel).read_bytes())


def colours(rows):
    seen = {}
    for row in rows:
        for p in row:
            seen[p] = seen.get(p, 0) + 1
    return seen


def near(p, rgb, tol=60):
    return sum(abs(p[k] - rgb[k]) for k in range(3)) < tol


def ink_mask(rows, ink):
    return [[p[3] > 127 and near(p, ink) for p in row] for row in rows]


def flood(mask, starts, want):
    h, w = len(mask), len(mask[0])
    seen = {c for c in starts if mask[c[1]][c[0]] == want}
    stack = list(seen)
    while stack:
        x, y = stack.pop()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h and mask[ny][nx] == want and (nx, ny) not in seen:
                seen.add((nx, ny))
                stack.append((nx, ny))
    return seen


def components(mask, want=True, minimum=1):
    cells = {(x, y) for y, row in enumerate(mask) for x, v in enumerate(row) if v == want}
    found = []
    while cells:
        part = flood(mask, [next(iter(cells))], want)
        cells -= part
        if len(part) >= minimum:
            found.append(part)
    return found


def holes(mask, minimum=1):
    h, w = len(mask), len(mask[0])
    border = [(x, y) for x in range(w) for y in range(h) if x in (0, w - 1) or y in (0, h - 1)]
    outside = flood(mask, border, False)
    inner = [[not v and (x, y) not in outside for x, v in enumerate(row)] for y, row in enumerate(mask)]
    return components(inner, True, minimum)


def antenna_balls(mask):
    ys = [y for y, row in enumerate(mask) if any(row)]
    band = int((ys[-1] - ys[0] + 1) * 0.12) + 1
    top = [row if ys[0] <= y < ys[0] + band else [False] * len(row) for y, row in enumerate(mask)]
    return components(top)


@pytest.mark.parametrize("rel", sorted(SIZES))
def test_every_icon_keeps_its_pixel_size_and_colour_type(rel):
    size, ctype = SIZES[rel]
    width, height, got, _ = decode(rel)
    assert (width, height, got) == (size, size, ctype)


@pytest.mark.parametrize("rel", sorted(BLEED))
def test_the_mobile_icons_are_twins_close_up_in_one_ink_on_a_flat_ground(rel):
    ground, ink = BLEED[rel]
    _, _, _, rows = decode(rel)
    seen = colours(rows)
    total = sum(seen.values())
    assert all(p[3] == 255 for p in seen)
    assert {p[:3] for p, n in seen.items() if n > total * 0.002} == {ground, ink}
    mask = ink_mask(rows, ink)
    fill = sum(map(sum, mask)) / total
    assert 0.45 <= fill <= 0.65, (rel, fill)
    assert [rows[y][x][:3] for x, y in ((0, 0), (1023, 0), (0, 1023), (1023, 1023), (512, 40))] == [ground] * 5
    assert len(holes(mask, 2000)) == 2
    assert len(antenna_balls(mask)) == 2


def test_the_tinted_icon_is_greyscale():
    _, _, _, rows = decode("mobile/assets/ios-tinted.png")
    assert all(p[0] == p[1] == p[2] for p in colours(rows))


def test_the_store_icon_is_opaque_rgb():
    assert decode("mobile/assets/icon.png")[2] == 2


@pytest.mark.parametrize("rel, size", [("desktop/src-tauri/icons/icon.png", 512), ("desktop/src-tauri/icons/128x128.png", 128), ("desktop/src-tauri/icons/64x64.png", 64)])
def test_desktop_icons_are_a_white_tile_with_transparent_corners_and_the_ink_mark(rel, size):
    _, _, _, rows = decode(rel)
    assert all(rows[y][x][3] == 0 for x, y in ((0, 0), (size - 1, 0), (0, size - 1), (size - 1, size - 1)))
    assert rows[int(size * 0.13)][size // 2][3] == 255 and min(rows[int(size * 0.13)][size // 2][:3]) >= 250
    seen = colours(rows)
    assert all(max(p[:3]) - min(p[:3]) <= max(BRAND) - min(BRAND) for p in seen if p[3] > 0)
    assert seen.get(BRAND + (255,), 0) > size
    mask = ink_mask(rows, BRAND)
    assert len(holes(mask)) == 2
    assert len(antenna_balls(mask)) == 2


def test_the_large_desktop_icon_is_the_close_up_and_the_small_one_the_full_mark():
    def ink_box(rel):
        _, _, _, rows = decode(rel)
        n = len(rows)
        cells = [(x, y) for y, row in enumerate(rows) for x, p in enumerate(row) if p[3] == 255 and near(p, BRAND)]
        return n, max(y for _, y in cells) / n, sum(1 for _ in cells) / n / n

    n, bottom, fill = ink_box("desktop/src-tauri/icons/icon.png")
    assert bottom > 0.85 and 0.28 <= fill <= 0.42
    n, bottom, fill = ink_box("desktop/src-tauri/icons/64x64.png")
    assert bottom < 0.8 and 0.07 <= fill <= 0.16


def test_the_desktop_tile_carries_a_soft_shadow_below_it():
    _, _, _, rows = decode("desktop/src-tauri/icons/icon.png")
    below = rows[int(512 * 0.915)][256]
    above = rows[int(512 * 0.085)][256]
    assert 0 < below[3] < 255 and below[3] > above[3]


def test_the_favicon_is_one_flat_ink_on_transparency():
    _, _, _, rows = decode("mobile/assets/favicon.png")
    seen = colours(rows)
    assert {p[:3] for p in seen if p[3] > 0} == {gen.rgb_of(gen.FAVICON_ACCENT)}
    assert rows[0][0][3] == 0
    mask = [[p[3] > 127 for p in row] for row in rows]
    assert len(holes(mask)) == 2 and len(antenna_balls(mask)) == 2


def test_the_adaptive_foreground_stays_inside_the_safe_radius():
    _, _, _, rows = decode("mobile/assets/adaptive-icon.png")
    opaque = [(x, y) for y, row in enumerate(rows) for x, p in enumerate(row) if p[3] > 0]
    assert opaque and rows[0][0][3] == 0
    assert max(math.hypot(x + 0.5 - 512, y + 0.5 - 512) for x, y in opaque) <= gen.SAFE_RADIUS * 1024 + 1
    assert {p[:3] for p in colours(rows) if p[3] > 0} == {BRAND}
    assert 0.1 <= len(opaque) / 1024 ** 2 <= 0.2


@pytest.mark.parametrize("rel, ink", [("mobile/assets/splash-icon-light.png", BRAND), ("mobile/assets/splash-icon-dark.png", CREAM)])
def test_the_splash_marks_float_in_their_theme_ink(rel, ink):
    _, _, _, rows = decode(rel)
    assert all(rows[y][x][3] == 0 for x, y in ((0, 0), (1023, 0), (0, 1023), (1023, 1023)))
    assert {p[:3] for p in colours(rows) if p[3] > 0} == {ink}
    ys = [y for y, row in enumerate(rows) if any(p[3] > 0 for p in row)]
    assert (ys[-1] - ys[0]) / 1024 >= 0.85
    mask = [[p[3] > 127 for p in row] for row in rows]
    assert len(holes(mask, 2000)) == 2


def png_size(data):
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    return struct.unpack(">II", data[16:24])


def test_icns_container_parses_with_the_expected_png_entries():
    data = (REPO / "desktop/src-tauri/icons/icon.icns").read_bytes()
    assert data[:4] == b"icns" and struct.unpack(">I", data[4:8])[0] == len(data)
    pos, found = 8, {}
    while pos < len(data):
        tag, length = struct.unpack(">4sI", data[pos:pos + 8])
        found[tag] = png_size(data[pos + 8:pos + length])
        pos += length
    assert pos == len(data)
    assert found == {tag: (size, size) for tag, size in gen.ICNS_ENTRIES}


def test_ico_container_holds_png_entries_for_every_size():
    data = (REPO / "desktop/src-tauri/icons/icon.ico").read_bytes()
    reserved, kind, count = struct.unpack("<HHH", data[:6])
    assert (reserved, kind, count) == (0, 1, len(gen.ICO_SIZES))
    sizes = []
    for k in range(count):
        w, h, _, _, planes, bits, length, offset = struct.unpack("<BBBBHHII", data[6 + 16 * k:22 + 16 * k])
        size = w or 256
        assert (h or 256) == size and planes == 1 and bits == 32
        assert png_size(data[offset:offset + length]) == (size, size)
        assert decode_bytes(data[offset:offset + length])[0] == size
        sizes.append(size)
    assert sizes == list(gen.ICO_SIZES)


def test_the_geometry_comes_from_the_shared_twin_and_projects_like_the_clients():
    assert gen.MARKS == REPO / "common" / "agentMarks.mjs"
    flat = gen.knots(gen.TWIN)
    assert [v for p in gen.project(flat, (0, 0, 0)) for v in p] == pytest.approx([v for p in flat for v in p])
    assert gen.variant(23) == gen.TWIN_SMALL and gen.variant(24) == gen.TWIN
    assert gen.held_pose() == tuple(gen.marks()["turn"]["still"]["idle"])
    assert gen.half_pose() == tuple(a / 2 for a in gen.held_pose())
    body, eyes = gen.turned_parts(1024, gen.held_pose())
    assert len(body) == len(flat) and len(eyes) == 2
    left, right, top, bottom = gen.bounds(body)
    assert all(left < x < right and top < y < bottom for eye in eyes for x, y in eye)
    assert sum(x for x, _ in eyes[0]) < sum(x for x, _ in eyes[1])
    turned_width = right - left
    assert turned_width < gen.bounds(flat)[1] - gen.bounds(flat)[0]


def test_the_small_variant_grows_the_eyes():
    small, large = gen.eye_pair(gen.TWIN_SMALL, 12), gen.eye_pair(gen.TWIN, 512)

    def width(eye):
        return max(x for x, _ in eye) - min(x for x, _ in eye)

    assert width(small[0]) > width(large[0])


def test_rendering_is_deterministic():
    for _ in range(2):
        first = (gen.tile_icon(64), gen.tile_icon(128), gen.flat_icon(96, None, gen.FAVICON_ACCENT, gen.fit_pose(gen.half_pose(), gen.FAVICON_MARK), gen.half_pose()), gen.tray_files())
        again = (gen.tile_icon(64), gen.tile_icon(128), gen.flat_icon(96, None, gen.FAVICON_ACCENT, gen.fit_pose(gen.half_pose(), gen.FAVICON_MARK), gen.half_pose()), gen.tray_files())
        assert first == again


def test_committed_icons_match_the_generator():
    result = subprocess.run([sys.executable, str(REPO / "scripts" / "gen_icons.py"), "--check"], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_check_flags_a_drifted_icon(tmp_path, monkeypatch):
    files = {**gen.tray_files(), "mobile/assets/favicon.png": (REPO / "mobile/assets/favicon.png").read_bytes()}
    monkeypatch.setattr(gen, "generate", lambda: files)
    monkeypatch.setattr(gen, "REPO", tmp_path)
    for rel, data in files.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_bytes(data)
    assert gen.main(["--check"]) == 0
    (tmp_path / "mobile/assets/favicon.png").write_bytes(gen.tile_icon(96))
    assert gen.main(["--check"]) == 1
    (tmp_path / "mobile/assets/favicon.png").unlink()
    assert gen.main(["--check"]) == 1


def test_every_single_ink_icon_is_generated():
    assert set(gen.SINGLE_INK) == {"mobile/assets/ios-tinted.png", "mobile/assets/favicon.png"}
    for rel in gen.SINGLE_INK:
        _, _, _, rows = decode(rel)
        seen = colours(rows)
        assert len({p[:3] for p, n in seen.items() if p[3] == 255 and n > 0.002 * sum(seen.values())}) <= 2


def test_app_configs_still_name_the_same_files():
    app = json.loads((REPO / "mobile" / "app.json").read_text())["expo"]
    named = {app["icon"], app["ios"]["icon"]["light"], app["ios"]["icon"]["dark"], app["ios"]["icon"]["tinted"], app["android"]["adaptiveIcon"]["foregroundImage"], app["web"]["favicon"]}
    splash = next(p[1] for p in app["plugins"] if p[0] == "expo-splash-screen")
    named |= {splash["image"], splash["dark"]["image"]}
    assert {Path(n).name for n in named} == {"icon.png", "ios-light.png", "ios-dark.png", "ios-tinted.png", "adaptive-icon.png", "favicon.png", "splash-icon-light.png", "splash-icon-dark.png"}
    assert all((REPO / "mobile" / n).is_file() for n in named)
    tauri = json.loads((REPO / "desktop" / "src-tauri" / "tauri.conf.json").read_text())["bundle"]["icon"]
    assert tauri == ["icons/icon.ico", "icons/32x32.png", "icons/128x128.png", "icons/128x128@2x.png", "icons/icon.icns"]
    assert all((REPO / "desktop" / "src-tauri" / n).is_file() for n in tauri)


@pytest.mark.parametrize("rel, fill", sorted(gen.SITE_MARKS.items()))
def test_the_site_marks_are_twin_in_one_ink_with_the_eyes_cut(rel, fill):
    svg = (REPO / rel).read_text()
    paths = re.findall(r'<path d="([^"]+)" fill="([^"]+)" fill-rule="evenodd"/>', svg)
    assert len(paths) == 1 and paths[0][1] == fill
    assert paths[0][0].count("M") == 3
    assert "polygon" not in svg


def tray_alpha(state, size):
    _, _, _, rows = decode(f"{TRAY_DIR}/tray-{state}-{size}.png")
    return [[p[3] for p in row] for row in rows]


def diff_cells(a, b):
    return {(x, y) for y, row in enumerate(a) for x, v in enumerate(row) if v != b[y][x]}


def test_the_tray_set_is_exactly_the_state_by_size_matrix():
    on_disk = sorted(str(p.relative_to(REPO)) for p in (REPO / TRAY_DIR).glob("*.png"))
    assert on_disk == sorted(TRAY_FILES)
    assert set(gen.TRAY_SIZES) == set(TRAY_SIZES) and set(gen.TRAY_STATES) == set(STATES)


@pytest.mark.parametrize("rel", TRAY_FILES)
def test_each_tray_template_has_its_exact_size_one_ink_and_binary_alpha(rel):
    size = int(rel.rsplit("-", 1)[1].split(".")[0])
    width, height, ctype, rows = decode(rel)
    assert (width, height, ctype) == (size, size, 6)
    seen = colours(rows)
    assert {p[3] for p in seen} == {0, 255}
    assert {p[:3] for p in seen} == {BRAND}


@pytest.mark.parametrize("size", TRAY_SIZES)
def test_the_quiet_tray_icon_is_twin_with_two_eyes_and_two_balls(size):
    mask = [[a == 255 for a in row] for row in tray_alpha("quiet", size)]
    assert len(components(mask)) == 1
    assert len(antenna_balls(mask)) == 2
    assert len(holes(mask)) == 2
    fill = sum(map(sum, mask)) / size / size
    assert 0.35 <= fill <= 0.6, fill


@pytest.mark.parametrize("size", TRAY_SIZES)
def test_the_state_badges_change_the_quiet_icon_only_around_their_mark(size):
    quiet = tray_alpha("quiet", size)
    k = size / 100
    bx, by = gen.BADGE
    reach = (gen.BADGE_KNOCK + 1.5) * k + 1
    for state in ("dot", "needs"):
        cells = diff_cells(tray_alpha(state, size), quiet)
        assert cells and all(math.hypot(x + 0.5 - bx * k, y + 0.5 - by * k) <= reach for x, y in cells)
    (ax, ay), (cx, cy), width = gen.SLASH_KNOCK
    offline = tray_alpha("offline", size)
    cells = diff_cells(offline, quiet)
    assert cells and all(abs((x + 0.5 - y - 0.5) - (ax - ay) * k) / math.sqrt(2) <= width / 2 * k + 1 for x, y in cells)
    assert any(offline[y][x] == 255 and quiet[y][x] == 0 for x, y in cells)
    assert any(offline[y][x] == 0 and quiet[y][x] == 255 for x, y in cells)


@pytest.mark.parametrize("size", TRAY_SIZES)
def test_needs_you_is_a_ring_with_a_hole_and_the_dot_is_solid(size):
    k = size / 100
    cx, cy = int(gen.BADGE[0] * k), int(gen.BADGE[1] * k)
    dot, needs = tray_alpha("dot", size), tray_alpha("needs", size)
    assert dot[cy][cx] == 255 and needs[cy][cx] == 0
    ring = [(x, y) for y in range(size) for x in range(size) if abs(math.hypot(x + 0.5 - gen.BADGE[0] * k, y + 0.5 - gen.BADGE[1] * k) - gen.RING_RADIUS * k) < 0.5]
    assert ring and sum(needs[y][x] == 255 for x, y in ring) >= len(ring) * 0.7


def test_every_state_differs_from_every_other_at_every_size():
    for size in TRAY_SIZES:
        assert len({str(tray_alpha(s, size)) for s in STATES}) == 4


@pytest.mark.parametrize("size", (32, 36))
def test_the_offline_slash_runs_from_top_left_to_bottom_right(size):
    offline, quiet = tray_alpha("offline", size), tray_alpha("quiet", size)
    k = size / 100
    (ax, ay), (bx, by), _ = gen.SLASH
    for t in (0.0, 0.5, 1.0):
        x, y = int((ax + (bx - ax) * t) * k), int((ay + (by - ay) * t) * k)
        assert offline[y][x] == 255, (x, y)
    assert offline[int(0.12 * size)][int(0.88 * size)] == quiet[int(0.12 * size)][int(0.88 * size)]


def test_the_tray_assets_are_the_committed_bytes():
    for rel, data in gen.tray_files().items():
        assert (REPO / rel).read_bytes() == data


def test_the_desktop_close_up_reaches_both_sides_of_its_tile_and_keeps_both_eyes_inside_it():
    polys = gen.twin_polygons(100, gen.held_pose(), *gen.close_pose(gen.TILE_CLOSE_SCALE))
    body, eyes = polys[0], polys[1:]
    half = gen.ICON_SIDE / 2
    left, right = min(x for x, _ in body), max(x for x, _ in body)
    assert left <= 50 - half and right >= 50 + half
    for eye in eyes:
        assert all(gen.tile_distance(x, y, 100) < -1 for x, y in eye)
