import hashlib
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
UNTOUCHED_SHA256 = {
    "desktop/src-tauri/icons/tray-template.png": "de7eeed708de3c3f53369f3fe9dfc55a16ebd789d5b8023331c33b1e51b24334",
    "desktop/src-tauri/icons/tray-template-notification.png": "ab5de37b8f28e781197dc2fc1f671c359582c315dc8bac6cb579309ff02cac0b",
    "mobile/assets/ios-tinted.png": "0cc40dc3f2250b5708c5d1d3db4756f7dab079013ef73c8f7f335e6963db2711",
}
PAPER = (0xFF, 0xFF, 0xFF)
INK = (0x0C, 0x0B, 0x09)


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
            seen[row[x:x + channels]] = seen.get(row[x:x + channels], 0) + 1
    return seen


def tones(accent=None):
    return gen.load_mark(accent or gen.LIGHT_ACCENT)[1]


@pytest.mark.parametrize("rel", sorted(SIZES))
def test_every_icon_keeps_its_pixel_size_and_colour_type(rel):
    size, ctype = SIZES[rel]
    width, height, got, _, _ = decode(rel)
    assert (width, height, got) == (size, size, ctype)


@pytest.mark.parametrize("rel", ["mobile/assets/ios-light.png", "mobile/assets/ios-dark.png", "mobile/assets/icon.png", "desktop/src-tauri/icons/icon.png"])
def test_opaque_and_tile_icons_draw_the_alpaca_in_one_flat_ink(rel):
    seen = colours(decode(rel))
    ink = tones(gen.DARK_ACCENT if "dark" in rel else gen.LIGHT_ACCENT)
    assert len(set(ink)) == 1
    assert any(near(c[:3], ink[0], 2) and n > 500 for c, n in seen.items()), rel
    assert len({c[:3] for c, n in seen.items() if n > 5000 and (len(c) == 3 or c[3] == 255)}) == 2


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
    assert any(c[3] == 255 and near(c[:3], tones()[0], 2) and n > 500 for c, n in seen.items())


def test_favicon_is_a_transparent_flat_mark():
    image = decode("mobile/assets/favicon.png")
    assert pixel(image, 0, 0)[3] == 0
    seen = colours(image)
    assert any(c[3] == 255 and near(c[:3], tones(gen.FAVICON_ACCENT)[0], 2) for c in seen)


def test_single_ink_icons_are_untouched():
    for rel, digest in UNTOUCHED_SHA256.items():
        assert hashlib.sha256((REPO / rel).read_bytes()).hexdigest() == digest, rel
    assert set(UNTOUCHED_SHA256) == set(gen.UNTOUCHED)


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
    first = gen.render(96, gen.PAPER, "none", gen.FAVICON_ACCENT, mark_height=gen.FAVICON_MARK).png()
    assert first == gen.render(96, gen.PAPER, "none", gen.FAVICON_ACCENT, mark_height=gen.FAVICON_MARK).png()


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
    for tone in tones(gen.DARK_ACCENT):
        assert contrast(tone, INK) >= 3, tone


def test_the_dark_splash_wears_the_dark_accent_and_the_light_splash_the_light_one():
    for rel, accent in (("mobile/assets/splash-icon-light.png", gen.LIGHT_ACCENT), ("mobile/assets/splash-icon-dark.png", gen.DARK_ACCENT)):
        seen = colours(decode(rel))
        assert any(c[3] == 255 and near(c[:3], tones(accent)[1], 2) and n > 500 for c, n in seen.items()), rel


def test_icons_up_to_64_px_use_the_nine_facet_alpaca_and_larger_ones_the_twelve():
    assert [len(gen.mark_polygons(size, 0.5)) for size in (16, 32, 64, 128, 512)] == [9, 9, 9, 12, 12]
