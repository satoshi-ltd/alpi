import colorsys
import importlib.util
import json
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
    "mobile/assets/adaptive-icon.png": (1024, 6),
    "mobile/assets/favicon.png": (96, 6),
    "mobile/assets/splash-icon-light.png": (1024, 6),
    "mobile/assets/splash-icon-dark.png": (1024, 6),
}
PAPER = (0xFF, 0xFF, 0xFF)
INK = (0x0C, 0x0B, 0x09)
SINGLE_INK = {
    "mobile/assets/ios-tinted.png": (1024, 6),
    "mobile/assets/favicon.png": (96, 6),
}
FULL_COLOUR = {
    "mobile/assets/ios-light.png": ("light", PAPER),
    "mobile/assets/ios-dark.png": ("dark", INK),
    "mobile/assets/icon.png": ("light", PAPER),
    "desktop/src-tauri/icons/icon.png": ("light", PAPER),
}
SMALL_SIZES = (180, 60, 40, 29)
MIN_FILL = 0.15


def decode(path):
    data = (REPO / path).read_bytes()
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
    rows = [raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)] for y in range(height)]
    return width, height, ctype, channels, rows


def pixel(image, x, y):
    _, _, _, channels, rows = image
    p = rows[y][x * channels:(x + 1) * channels]
    return tuple(p) if channels == 4 else tuple(p) + (255,)


def near(a, b, tol=3):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def colours(image):
    _, _, _, channels, rows = image
    seen = {}
    for row in rows:
        for x in range(0, len(row), channels):
            key = tuple(row[x:x + channels])
            seen[key] = seen.get(key, 0) + 1
    return seen


def tones(accent=None, ground=PAPER):
    return gen.crease_tones(accent or gen.LIGHT_ACCENT, gen.hex_of(ground))


def pixels(img):
    n, px = img.size, img.pixel
    stride = n * px + 1
    return [[tuple(img.raw[y * stride + 1 + x * px:y * stride + 1 + (x + 1) * px]) for x in range(n)] for y in range(n)]


def ink_mask(img, ground):
    return [[(len(p) == 3 or p[3] != 0) and sum(abs(p[k] - ground[k]) for k in range(3)) > 60 for p in row] for row in pixels(img)]


def fill_of(mask):
    return sum(map(sum, mask)) / (len(mask) * len(mask))


def flood(mask, start_cells, want):
    n = len(mask)
    seen = {c for c in start_cells if mask[c[1]][c[0]] == want}
    stack = list(seen)
    while stack:
        x, y = stack.pop()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < n and 0 <= ny < n and mask[ny][nx] == want and (nx, ny) not in seen:
                seen.add((nx, ny))
                stack.append((nx, ny))
    return seen


def components(mask):
    cells = {(x, y) for y, row in enumerate(mask) for x, v in enumerate(row) if v}
    count = 0
    while cells:
        count += 1
        cells -= flood(mask, [next(iter(cells))], True)
    return count


def enclosed_gaps(mask):
    n = len(mask)
    border = [(x, y) for x in range(n) for y in range(n) if x in (0, n - 1) or y in (0, n - 1)]
    outside = flood(mask, border, False)
    return n * n - sum(map(sum, mask)) - len(outside)


def ear_ink(mask):
    rows = [y for y, row in enumerate(mask) if any(row)]
    band = int((rows[-1] - rows[0] + 1) * 0.14) + 1
    return sum(sum(mask[y]) for y in range(rows[0], rows[0] + band))


def full_render(size):
    return gen.render(size, gen.PAPER, "full", gen.LIGHT_ACCENT, mark_height=gen.FULL_MARK, rgb=True)


@pytest.mark.parametrize("rel", sorted(SIZES))
def test_every_icon_keeps_its_pixel_size_and_colour_type(rel):
    size, ctype = SIZES[rel]
    width, height, got, _, _ = decode(rel)
    assert (width, height, got) == (size, size, ctype)


@pytest.mark.parametrize("rel", sorted(FULL_COLOUR))
def test_full_colour_icons_draw_the_alpaca_in_three_discrete_tones_of_one_hue(rel):
    mode, ground = FULL_COLOUR[rel]
    seen = {c[:3]: n for c, n in colours(decode(rel)).items() if len(c) == 3 or c[3] == 255}
    total = sum(seen.values())
    palette = set(tones(gen.BRAND_INK[mode], ground))
    dominant = {c for c, n in seen.items() if n > total * 0.002}
    assert dominant == palette | {ground}, rel
    assert len(palette) >= 3
    edge = sum(n for c, n in seen.items() if c not in dominant)
    assert edge < total * 0.04, rel
    chroma = [max(t) - min(t) for t in palette if max(t) - min(t) > 8]
    hues = [colorsys.rgb_to_hsv(*(v / 255 for v in t))[0] * 360 for t in palette if max(t) - min(t) > 8]
    assert chroma and max(hues) - min(hues) < 20


@pytest.mark.parametrize("rel", sorted(FULL_COLOUR))
def test_the_large_icons_carry_the_mark_on_about_a_sixth_of_the_tile(rel):
    mode, ground = FULL_COLOUR[rel]
    width, _, _, channels, raw = decode(rel)
    opaque = inked = 0
    for row in raw:
        for x in range(width):
            p = row[x * channels:(x + 1) * channels]
            if channels == 4 and p[3] == 0:
                continue
            opaque += 1
            inked += sum(abs(p[k] - ground[k]) for k in range(3)) > 60
    assert 0.15 <= inked / opaque <= 0.22, (rel, inked / opaque)


@pytest.mark.parametrize("size", SMALL_SIZES)
def test_small_renders_keep_the_fill_close_the_gaps_and_keep_the_ears(size):
    mask = ink_mask(full_render(size), gen.PAPER)
    assert fill_of(mask) >= MIN_FILL
    if size <= gen.LOW_MAX:
        assert components(mask) == 1
        assert enclosed_gaps(mask) == 0
    assert ear_ink(mask) >= {180: 150, 60: 35, 40: 18, 29: 12}[size]


def test_thickening_only_applies_below_64_px_and_grows_as_the_icon_shrinks():
    assert gen.thickness(65) == 0 == gen.thickness(1024)
    assert 0 < gen.thickness(64) < gen.thickness(40) < gen.thickness(29) <= gen.THICK_MAX
    assert gen.thickness(16) <= gen.THICK_MAX


def test_the_thickened_silhouette_is_wider_than_the_drawn_one():
    span = lambda polys: max(x for _, poly in polys for x, _ in poly) - min(x for _, poly in polys for x, _ in poly)
    drawn = gen.mark_polygons(29, gen.FULL_MARK, nominal=1024, low=True)
    assert span(gen.mark_polygons(29, gen.FULL_MARK)) > span(drawn) + 1


def test_the_tinted_icon_is_white_on_black_with_no_other_hue():
    seen = colours(decode("mobile/assets/ios-tinted.png"))
    assert all(c[0] == c[1] == c[2] and c[3] == 255 for c in seen)
    big = {c[:3] for c, n in seen.items() if n > 0.002 * 1024 * 1024}
    assert big == {(0, 0, 0), (255, 255, 255)}


def test_the_favicon_is_one_flat_ink_on_transparency():
    seen = colours(decode("mobile/assets/favicon.png"))
    assert {c[:3] for c in seen if c[3] > 0} == {gen.rgb_of(gen.FAVICON_ACCENT)}
    assert 0 in {c[3] for c in seen}


def test_every_single_ink_icon_is_generated():
    assert set(SINGLE_INK) == set(gen.SINGLE_INK)
    files = gen.generate()
    assert set(SINGLE_INK) <= set(files)
    for rel, (size, ctype) in SINGLE_INK.items():
        assert decode(rel)[:3] == (size, size, ctype)


def test_light_ios_icons_sit_on_paper_and_dark_on_near_black():
    for rel in ("mobile/assets/ios-light.png", "mobile/assets/icon.png"):
        image = decode(rel)
        assert all(pixel(image, x, y)[:3] == PAPER and pixel(image, x, y)[3] == 255 for x, y in ((0, 0), (1023, 0), (0, 1023), (1023, 1023), (512, 40)))
    dark = decode("mobile/assets/ios-dark.png")
    assert all(pixel(dark, x, y) == INK + (255,) for x, y in ((0, 0), (1023, 0), (0, 1023), (1023, 1023), (512, 40)))


def test_the_store_icon_is_opaque_rgb():
    width, height, ctype, channels, _ = decode("mobile/assets/icon.png")
    assert (ctype, channels) == (2, 3)


def test_desktop_icons_are_a_paper_tile_with_transparent_corners():
    for rel, size in (("desktop/src-tauri/icons/icon.png", 512), ("desktop/src-tauri/icons/128x128.png", 128)):
        image = decode(rel)
        assert all(pixel(image, x, y)[3] == 0 for x, y in ((0, 0), (size - 1, 0), (0, size - 1), (size - 1, size - 1)))
        assert pixel(image, size // 2, int(size * 0.14)) == PAPER + (255,)


@pytest.mark.parametrize("rel", ["mobile/assets/splash-icon-light.png", "mobile/assets/splash-icon-dark.png"])
def test_splash_marks_float_on_transparency_at_the_size_the_old_splash_had(rel):
    image = decode(rel)
    width, height, _, channels, rows = image
    assert all(pixel(image, x, y)[3] == 0 for x, y in ((0, 0), (1023, 0), (0, 1023), (1023, 1023)))
    ys = [y for y in range(height) if any(rows[y][x * 4 + 3] > 0 for x in range(width))]
    assert (ys[-1] - ys[0]) / height >= 0.85


@pytest.mark.parametrize("rel", ["mobile/assets/adaptive-icon.png"])
def test_floating_marks_are_transparent_and_inside_the_adaptive_safe_zone(rel):
    image = decode(rel)
    width, height, _, channels, rows = image
    assert all(pixel(image, x, y)[3] == 0 for x, y in ((0, 0), (1023, 0), (0, 1023), (1023, 1023), (512, 5)))
    radius = 0.306 * width + 1
    opaque = [(x, y) for y in range(height) for x in range(width) if rows[y][x * 4 + 3] > 0]
    assert opaque
    assert max(((x - width / 2) ** 2 + (y - height / 2) ** 2) ** 0.5 for x, y in opaque) <= radius
    seen = colours(image)
    assert {c[:3] for c, n in seen.items() if c[3] == 255 and n > 500} == set(tones())


def test_favicon_is_a_transparent_flat_mark():
    image = decode("mobile/assets/favicon.png")
    assert pixel(image, 0, 0)[3] == 0
    seen = colours(image)
    assert any(c[3] == 255 and c[:3] == gen.rgb_of(gen.FAVICON_ACCENT) for c in seen)


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


def test_ico_container_parses_with_png_entries():
    data = (REPO / "desktop/src-tauri/icons/icon.ico").read_bytes()
    reserved, kind, count = struct.unpack("<HHH", data[:6])
    assert (reserved, kind, count) == (0, 1, len(gen.ICO_SIZES))
    sizes = []
    for k in range(count):
        w, h, _, _, planes, bits, length, offset = struct.unpack("<BBBBHHII", data[6 + 16 * k:22 + 16 * k])
        size = w or 256
        assert (h or 256) == size and planes == 1 and bits == 32
        assert png_size(data[offset:offset + length]) == (size, size)
        sizes.append(size)
    assert sizes == list(gen.ICO_SIZES)


def test_generation_is_deterministic():
    first = gen.generate()
    again = gen.generate()
    assert first.keys() == again.keys() and all(first[k] == again[k] for k in first)


def test_committed_icons_match_the_generator():
    result = subprocess.run([sys.executable, str(REPO / "scripts" / "gen_icons.py"), "--check"], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_check_flags_a_drifted_icon(tmp_path, monkeypatch):
    monkeypatch.setattr(gen, "REPO", tmp_path)
    files = gen.generate()
    for rel, data in files.items():
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    assert gen.main(["--check"]) == 0
    (tmp_path / "mobile/assets/favicon.png").write_bytes(gen.render(96, gen.INK, "full", gen.DARK_ACCENT, mark_height=0.5).png())
    assert gen.main(["--check"]) == 1


def test_app_configs_still_name_the_same_files():
    app = json.loads((REPO / "mobile" / "app.json").read_text())["expo"]
    named = {app["icon"], app["ios"]["icon"]["light"], app["ios"]["icon"]["dark"], app["android"]["adaptiveIcon"]["foregroundImage"], app["web"]["favicon"]}
    splash = next(p[1] for p in app["plugins"] if p[0] == "expo-splash-screen")
    named |= {splash["image"], splash["dark"]["image"]}
    assert {Path(n).name for n in named} == {"icon.png", "ios-light.png", "ios-dark.png", "adaptive-icon.png", "favicon.png", "splash-icon-light.png", "splash-icon-dark.png"}
    assert all((REPO / "mobile" / n).is_file() for n in named)
    tauri = json.loads((REPO / "desktop" / "src-tauri" / "tauri.conf.json").read_text())["bundle"]["icon"]
    assert tauri == ["icons/icon.ico", "icons/32x32.png", "icons/128x128.png", "icons/128x128@2x.png", "icons/icon.icns"]
    assert all((REPO / "desktop" / "src-tauri" / n).is_file() for n in tauri)


def luminance(rgb):
    lin = [(v / 255 / 12.92) if v / 255 <= 0.04045 else ((v / 255 + 0.055) / 1.055) ** 2.4 for v in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a, b):
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def test_the_icons_use_the_brand_ink_of_each_theme_and_every_tone_holds_on_its_ground():
    folds = (REPO / "common" / "folds.mjs").read_text()
    assert f'light: "{gen.LIGHT_ACCENT}"' in folds and f'dark: "{gen.DARK_ACCENT}"' in folds
    for tone in tones(gen.LIGHT_ACCENT):
        assert contrast(tone, PAPER) >= 3, tone
    for tone in tones(gen.DARK_ACCENT, INK):
        assert contrast(tone, INK) >= 3, tone


def test_the_dark_splash_wears_the_dark_accent_and_the_light_splash_the_light_one():
    for rel, accent, ground in (("mobile/assets/splash-icon-light.png", gen.LIGHT_ACCENT, PAPER), ("mobile/assets/splash-icon-dark.png", gen.DARK_ACCENT, INK)):
        seen = colours(decode(rel))
        assert any(c[3] == 255 and near(c[:3], tones(accent, ground)[1], 2) and n > 500 for c, n in seen.items()), rel


def test_icons_up_to_64_px_use_the_nine_facet_alpaca_and_larger_ones_the_twelve():
    assert [len(gen.mark_polygons(size, 0.5)) for size in (16, 32, 64, 128, 512)] == [9, 9, 9, 12, 12]


TRAY_DIR = "desktop/src-tauri/icons/tray"
PLATFORM_SIZES = {"macos": (36,), "windows": (16, 20, 24, 32), "linux": (22, 24)}
TRAY_SIZES = sorted({n for sizes in PLATFORM_SIZES.values() for n in sizes})
STATES = ("quiet", "dot", "needs", "offline")
TRAY_FILES = [f"{TRAY_DIR}/tray-{state}-{size}.png" for state in STATES for size in TRAY_SIZES]


def tray_alpha(state, size):
    image = decode(f"{TRAY_DIR}/tray-{state}-{size}.png")
    return [[image[4][y][x * 4 + 3] for x in range(size)] for y in range(size)]


def diff_cells(a, b):
    return {(x, y) for y, row in enumerate(a) for x, v in enumerate(row) if v != b[y][x]}


def test_the_tray_set_is_exactly_the_state_by_size_matrix():
    on_disk = sorted(str(p.relative_to(REPO)) for p in (REPO / TRAY_DIR).glob("*.png"))
    assert on_disk == sorted(TRAY_FILES)
    assert set(gen.TRAY_SIZES) == set(TRAY_SIZES) and set(gen.TRAY_STATES) == set(STATES)


@pytest.mark.parametrize("rel", TRAY_FILES)
def test_each_tray_asset_has_its_exact_pixel_size_one_ink_and_binary_alpha(rel):
    size = int(rel.rsplit("-", 1)[1].split(".")[0])
    image = decode(rel)
    assert image[:3] == (size, size, 6)
    seen = colours(image)
    assert {c[3] for c in seen} == {0, 255}
    assert {c[:3] for c in seen if c[3] == 255} == {gen.rgb_of(gen.LIGHT_ACCENT)}
    assert {c[:3] for c in seen if c[3] == 0} == {gen.rgb_of(gen.LIGHT_ACCENT)}


@pytest.mark.parametrize("size", TRAY_SIZES)
def test_the_nine_facets_survive_snapping_with_whole_pixel_vertices(size):
    facets = gen.snap_facets(size)
    assert len(facets) == 9
    assert all(isinstance(v, int) for _, poly in facets for point in poly for v in point)
    grid = gen.fold_alpha(size)[1]
    assert all(sum(row.count(i) for row in grid) >= 2 for i in range(9))


@pytest.mark.parametrize("size", TRAY_SIZES)
def test_creases_are_one_pixel_gaps_from_32_px_and_absent_below(size):
    quiet = tray_alpha("quiet", size)
    raw = gen.owners(size, gen.snap_facets(size))
    cleared = {(x, y) for y in range(size) for x in range(size) if raw[y][x] >= 0 and quiet[y][x] == 0}
    if size < 32:
        assert not cleared
        return
    assert cleared
    assert not any({(x + 1, y), (x, y + 1), (x + 1, y + 1)} <= cleared for x, y in cleared)
    assert all(quiet[y][x] == 255 for y in range(size) for x in range(size) if raw[y][x] >= 0 and (x, y) not in cleared)


@pytest.mark.parametrize("size", TRAY_SIZES)
def test_the_quiet_silhouette_is_centred_in_its_square(size):
    alpha = tray_alpha("quiet", size)
    xs = [x for row in alpha for x, a in enumerate(row) if a]
    assert abs((min(xs) + max(xs) + 1) / 2 - size / 2) <= 0.5


@pytest.mark.parametrize("size", TRAY_SIZES)
def test_the_state_marks_change_the_quiet_icon_only_around_their_mark(size):
    quiet = tray_alpha("quiet", size)
    d, c = gen.dot_geometry(size)
    dot, needs, offline = (tray_alpha(s, size) for s in ("dot", "needs", "offline"))

    def near_disc(cells, radius):
        return all((x + 0.5 - c) ** 2 + (y + 0.5 - c) ** 2 <= radius ** 2 for x, y in cells)

    assert near_disc(diff_cells(dot, quiet), d / 2 + 1)
    assert near_disc(diff_cells(needs, quiet), d / 2 + 2)
    assert any(dot[y][x] == 255 and quiet[y][x] == 0 for x, y in diff_cells(dot, quiet))
    assert any(needs[y][x] == 255 and quiet[y][x] == 0 for x, y in diff_cells(needs, quiet))
    assert any(needs[y][x] == 0 for y in range(size) for x in range(size) if needs[y][x] == 0 and 0 < (x + 0.5 - c) ** 2 + (y + 0.5 - c) ** 2 <= (d / 2) ** 2)

    xs = [x for row in quiet for x, a in enumerate(row) if a]
    ys = [y for y, row in enumerate(quiet) if any(row)]
    cx, cy, w = (min(xs) + max(xs)) // 2, (min(ys) + max(ys)) // 2, gen.ring_thickness(size)
    cells = diff_cells(offline, quiet)
    assert cells and all(abs((x - cx) - (y - cy)) <= w for x, y in cells)
    assert any(offline[y][x] == 255 and quiet[y][x] == 0 for x, y in cells)
    assert any(offline[y][x] == 0 and quiet[y][x] == 255 for x, y in cells)


def test_every_state_differs_from_every_other_at_every_size():
    for size in TRAY_SIZES:
        assert len({str(tray_alpha(s, size)) for s in STATES}) == 4


def test_the_tray_assets_are_byte_identical_across_two_generator_runs():
    first, second = gen.tray_files(), gen.tray_files()
    assert first == second
    assert set(first) == set(TRAY_FILES)
    for rel, data in first.items():
        assert (REPO / rel).read_bytes() == data


@pytest.mark.parametrize("size, ink_cell", [(36, [(14, 13), (13, 14), (29, 30), (28, 29)]), (32, [(12, 12), (14, 14), (26, 26), (25, 23)])])
def test_the_offline_slash_runs_from_top_left_to_bottom_right(size, ink_cell):
    quiet, offline = tray_alpha("quiet", size), tray_alpha("offline", size)
    for x, y in ink_cell:
        assert quiet[y][x] == 0 and offline[y][x] == 255, (x, y)
        assert offline[y][size - 1 - x] == quiet[y][size - 1 - x]


@pytest.mark.parametrize("size", TRAY_SIZES)
def test_needs_you_is_a_ring_with_a_hole_and_the_dot_is_solid(size):
    _, c = gen.dot_geometry(size)
    cx = cy = int(c)
    dot, needs = tray_alpha("dot", size), tray_alpha("needs", size)
    assert dot[cy][cx] == 255 and needs[cy][cx] == 0
    d = round(gen.DOT_FRACTION * size)
    inside = [(x, y) for y in range(size) for x in range(size) if (x + 0.5 - c) ** 2 + (y + 0.5 - c) ** 2 <= (d / 2) ** 2]
    assert sum(dot[y][x] == 255 for x, y in inside) == len(inside)
    assert sum(needs[y][x] == 0 for x, y in inside) >= 1
