from __future__ import annotations

import io
import json
import random
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

import pytest
from rich.cells import cell_len
from rich.text import Text

from alpi import appearance, fold_art, mark_shapes, palette

REPO = Path(__file__).resolve().parents[2]
TRUECOLOR = {"COLORTERM": "truecolor", "TERM": "xterm-256color", "LANG": "en_US.UTF-8"}
SHAPES = (*mark_shapes.SHAPE_ORDER, fold_art.TWIN, fold_art.TWIN_SMALL)


class FakeTTY(io.StringIO):
    encoding = "utf-8"

    def isatty(self) -> bool:
        return True


def _node(script: str, *args: str):
    out = subprocess.run(
        ["node", "--input-type=module", "-e", script, *args],
        capture_output=True, text=True, check=True,
    )
    return json.loads(out.stdout)


def _uri(name: str) -> str:
    return (REPO / "common" / name).as_uri()


def _rows(fold: str, rows: int) -> list[str]:
    return ["".join("#" if cell else "." for cell in line) for line in fold_art.mask(fold, rows)]


def test_mark_shapes_file_is_not_stale() -> None:
    done = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "sync_marks.py"), "--check"],
        capture_output=True, text=True,
    )
    assert done.returncode == 0, done.stderr


def test_the_generated_marks_carry_every_shared_shape_the_legacy_map_and_the_eyes() -> None:
    sys.path.insert(0, str(REPO / "design" / "src"))
    import agent_marks

    script = (
        "const m = await import(process.argv[1]); const w = await import(process.argv[2]);"
        "process.stdout.write(JSON.stringify({shapes: Object.keys(m.SHAPES), order: m.SHAPE_ORDER, legacy: 'LEGACY_SHAPE' in m,"
        " eyes: Object.fromEntries(Object.entries(m.SHAPES).map(([k, v]) => [k, [v.eyeX, v.eyeY, v.eyeDx]])),"
        " gaps: Object.keys(w.WG_CELLS).map(Number), order3: w.WG_ORDER}));"
    )
    shared = _node(script, _uri("agentMarks.mjs"), _uri("workgroupMark.mjs"))
    assert set(mark_shapes.OUTLINES) == set(shared["shapes"]) == set(SHAPES)
    assert list(mark_shapes.SHAPE_ORDER) == shared["order"]
    assert shared["legacy"] is False
    assert mark_shapes.LEGACY_SHAPE == agent_marks.LEGACY_SHAPE
    assert set(mark_shapes.LEGACY_SHAPE.values()) == set(palette.SHAPES)
    assert {name: list(spec) for name, spec in mark_shapes.EYES.items()} == shared["eyes"]
    assert sorted(mark_shapes.HONEYCOMB) == sorted(shared["gaps"])
    assert all(list(cells) == shared["order3"] for cells in mark_shapes.HONEYCOMB.values())


def test_the_flattened_outlines_stay_on_the_shared_paths() -> None:
    script = (
        "const m = await import(process.argv[1]);"
        "process.stdout.write(JSON.stringify(Object.fromEntries(Object.entries(m.SHAPES).map(([k, v]) => [k, v.d]))));"
    )
    shared = _node(script, _uri("agentMarks.mjs"))
    for name, d in shared.items():
        numbers = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", d)]
        ends = {(round(numbers[i], 2), round(numbers[i + 1], 2)) for i in range(len(numbers) - 2, 0, -6)}
        flattened = set(mark_shapes.OUTLINES[name])
        assert ends <= flattened | {(numbers[0], numbers[1])}, name
        assert all(-5 <= x <= 105 and -5 <= y <= 105 for x, y in mark_shapes.OUTLINES[name]), name


@pytest.mark.parametrize("size", [8, 12, 16, 24, 40, 72])
def test_eye_pair_matches_the_shared_eye_rule(size: int) -> None:
    script = (
        "const { eyePair } = await import(process.argv[1]); const { SHAPES, STILL } = await import(process.argv[2]);"
        "const size = Number(process.argv[3]);"
        "process.stdout.write(JSON.stringify(Object.fromEntries(Object.keys(SHAPES).flatMap((name) =>"
        " Object.keys(STILL).map((state) => [`${name}:${state}`, eyePair(SHAPES[name], size, STILL[state])])))));"
    )
    shared = _node(script, _uri("markEyes.mjs"), _uri("agentMarks.mjs"), str(size))
    for key, eyes in shared.items():
        name, state = key.split(":")
        mine = fold_art.eye_pair(name, size, mark_shapes.STILL[state])
        for expected, actual in zip(eyes, mine):
            assert len(expected) == len(actual) == 48
            for (ex, ey), (x, y) in zip(expected, actual):
                assert abs(ex - x) <= 0.02 and abs(ey - y) <= 0.02, key


def test_the_name_tone_matches_the_shared_rule_on_both_grounds() -> None:
    rng = random.Random(7)
    accents = [hex_ for _, hex_ in appearance.ACCENTS] + [f"#{rng.randrange(1 << 24):06x}" for _ in range(30)]
    accents += ["#000000", "#ffffff", "#abc", "#14110c", "#f3efe6", "#nonsense", ""]
    grounds = [palette.DARK["bg"], palette.LIGHT["bg"], "#ffffff", "#000000", "#808080", "nope"]
    script = (
        "const { nameTone } = await import(process.argv[1]);"
        "const [accents, grounds] = JSON.parse(process.argv[2]);"
        "process.stdout.write(JSON.stringify(accents.map((a) => grounds.map((g) => nameTone(a, g)))));"
    )
    expected = _node(script, _uri("name.mjs"), json.dumps([accents, grounds]))
    for accent, tones in zip(accents, expected):
        assert [fold_art.name_tone(accent, ground) for ground in grounds] == tones, accent


def test_the_mark_tone_matches_the_shared_rule_in_both_themes() -> None:
    rng = random.Random(11)
    accents = [hex_ for _, hex_ in appearance.ACCENTS] + [f"#{rng.randrange(1 << 24):06x}" for _ in range(40)]
    accents += ["#ffffff", "#000000", "#F0B447", "#abc", "#nonsense", "", " #f0b447"]
    script = (
        "const { markTone } = await import(process.argv[1]);"
        "const accents = JSON.parse(process.argv[2]);"
        "process.stdout.write(JSON.stringify(accents.map((a) => ['light', 'dark'].map((t) => markTone(a, t)))));"
    )
    expected = _node(script, _uri("markTone.mjs"), json.dumps(accents))
    for accent, tones in zip(accents, expected):
        assert [fold_art.mark_tone(accent, theme) for theme in ("light", "dark")] == tones, accent


def test_a_pale_accent_paints_a_deeper_body_in_light_so_the_white_eyes_hold_3_to_1() -> None:
    light = {"amber": "#c08915", "lime": "#799f08", "sky": "#10a1c7", "green": "#2aa961", "orange": "#dd7a28", "teal": "#20a2a4", "rose": "#ec6a88"}
    for name, accent in appearance.ACCENTS:
        tone = fold_art.body_colour(accent, {"theme": "light"})
        assert tone == light.get(name, accent), name
        assert fold_art.contrast_ratio(tone, palette.EYE_INK["light"]) >= 3, name
        assert fold_art.body_colour(accent, {"theme": "dark"}) == accent, name


def test_a_name_is_legible_on_the_terminal_ground_of_its_theme() -> None:
    for _, accent in appearance.ACCENTS:
        dark = fold_art.name_colour(accent, {"theme": "dark"})
        light = fold_art.name_colour(accent, {"theme": "light"})
        assert fold_art.contrast_ratio(dark, palette.DARK["bg"]) >= 4.5
        assert fold_art.contrast_ratio(light, palette.LIGHT["bg"]) >= 4.5
        assert fold_art.luminance(dark) > fold_art.luminance(light)


def test_the_accent_list_is_the_shared_one() -> None:
    script = "const { ACCENT_HEXES } = await import(process.argv[1]); process.stdout.write(JSON.stringify(ACCENT_HEXES));"
    assert _node(script, _uri("accents.mjs")) == [h for _, h in appearance.ACCENTS]


def test_art_is_half_blocks_two_cells_wide_per_row_in_one_flat_colour() -> None:
    picture = fold_art.art("round", "#3899e2", rows=8)
    lines = picture.plain.split("\n")
    assert len(lines) == 8
    assert {len(line) for line in lines} == {16}
    assert set(picture.plain) <= {"█", "▀", "▄", " ", "\n"}
    assert {str(span.style) for span in picture.spans} == {"#3899e2"}


def test_art_leaves_the_background_transparent_outside_the_shape_and_in_the_eyes() -> None:
    cells = fold_art.grid("round", "#f0b447", rows=8)
    assert cells[0][0] == (None, None) and cells[-1][-1] == (None, None)
    assert all(colour in {None, "#f0b447"} for line in cells for pair in line for colour in pair)
    for r, c in fold_art.eye_cells("round", 16):
        assert cells[r // 2][c][r % 2] is None


@pytest.mark.parametrize("theme,eye", [("dark", "#000000"), ("light", "#ffffff")])
@pytest.mark.parametrize("shape", ["round", "bell", palette.TWIN_SHAPE])
def test_eyes_are_filled_in_the_paper_ink_of_the_theme(shape: str, theme: str, eye: str) -> None:
    ink = palette.eye_ink({"theme": theme})
    assert ink == eye
    cells = fold_art.grid(shape, "#f0b447", rows=8, eye=ink)
    name = fold_art.outline_of(shape, 16)
    for r, c in fold_art.eye_cells(name, 16):
        assert cells[r // 2][c][r % 2] == eye
    assert {colour for line in cells for pair in line for colour in pair} == {None, "#f0b447", eye}
    styles = {str(span.style) for span in fold_art.art(shape, "#f0b447", rows=8, eye=ink).spans}
    assert any(eye in style for style in styles)


def test_the_honeycomb_has_no_eyes_to_fill() -> None:
    plain = fold_art.grid(palette.WORKGROUP_SHAPE, "#f0b447", rows=8)
    assert fold_art.grid(palette.WORKGROUP_SHAPE, "#f0b447", rows=8, eye="#000000") == plain


@pytest.mark.parametrize("rows", [4, 6, 8, 12])
@pytest.mark.parametrize("shape", [*palette.SHAPES, palette.TWIN_SHAPE])
def test_every_mark_shows_two_separate_eye_holes_inside_the_body(shape: str, rows: int) -> None:
    size = rows * 2
    name = fold_art.outline_of(shape, size)
    pixels = fold_art.mask(shape, rows)
    holes = fold_art.eye_cells(name, size)
    columns = sorted({c for _, c in holes})
    left = [c for c in columns if c < (columns[0] + columns[-1]) / 2]
    right = [c for c in columns if c > (columns[0] + columns[-1]) / 2]
    assert left and right and len(left) == len(right)
    assert right[0] - left[-1] >= 2
    assert all(not pixels[r][c] for r, c in holes)
    for r in {r for r, _ in holes}:
        row = pixels[r]
        filled = [c for c in range(size) if row[c]]
        if filled and filled[0] < left[0] and filled[-1] > right[-1]:
            assert any(row[c] for c in range(left[-1] + 1, right[0])), (shape, rows, r)
    carved = sum(1 for r, c in holes if fold_art.coverage([mark_shapes.OUTLINES[name]], size)[r][c] >= fold_art.FILL_COVER)
    assert carved >= 2 * len(left) * 2


def test_the_round_and_the_bell_read_as_their_shapes() -> None:
    assert _rows("round", 6) == [
        "............",
        ".....##.....",
        "...######...",
        "..##.##.##..",
        "..##.##.##..",
        "..##.##.##..",
        "..##.##.###.",
        "..########..",
        "..########..",
        "...######...",
        ".....##.....",
        "............",
    ]
    bell = _rows("bell", 8)
    assert bell[1].strip(".") == "####" and bell[-3].strip(".") == "##########"
    assert bell[-2].strip(".") == "##"


def test_the_default_profile_is_twin_with_two_antenna_balls() -> None:
    assert fold_art.outline_of(palette.TWIN_SHAPE, 16) == fold_art.TWIN_SMALL
    assert fold_art.outline_of(palette.TWIN_SHAPE, 24) == fold_art.TWIN
    rows = _rows(palette.TWIN_SHAPE, 8)
    balls = [row for row in rows[:4] if "#" in row]
    assert balls and all(re.fullmatch(r"\.+##\.+##\.+", row) for row in balls)
    assert rows[1] == "....##....##...."
    head = [row for row in rows[4:] if "#" in row]
    assert max(row.count("#") for row in head) >= 3 * max(row.count("#") for row in balls)


def test_the_workgroup_is_the_soft_honeycomb_of_three_cells() -> None:
    for rows in (6, 8):
        pixels = _rows(palette.WORKGROUP_SHAPE, rows)
        top = [row for row in pixels if "#" in row and "..#" not in row.strip(".")]
        lower = [row for row in pixels if re.search(r"#\.+#", row.strip("."))]
        assert top and lower
        assert all(re.fullmatch(r"\.*#+\.+#+\.*", row) for row in lower)
    gap = mark_shapes.HONEYCOMB[min(mark_shapes.HONEYCOMB, key=lambda g: abs(g - 8.1))]
    assert fold_art.honeycomb_cells(16) is gap
    assert fold_art.honeycomb_cells(400) is mark_shapes.HONEYCOMB[5.0]


def test_art_scales_with_rows_and_draws_every_mark() -> None:
    for shape in [*palette.SHAPES, palette.WORKGROUP_SHAPE, palette.TWIN_SHAPE]:
        small = fold_art.art(shape, "#f0b447", rows=4)
        large = fold_art.art(shape, "#f0b447", rows=12)
        assert len(small.plain.split("\n")) == 4
        assert len(large.plain.split("\n")) == 12
        assert small.plain.strip() and large.plain.strip()


def test_an_unknown_shape_draws_the_round_and_a_bad_colour_falls_back_to_amber() -> None:
    assert fold_art.mask("pencil", 6) == fold_art.mask("round", 6)
    assert fold_art.mask("shield", 6) == fold_art.mask("round", 6)
    assert {str(span.style) for span in fold_art.art("round", "nonsense", 4).spans} == {"#f0b447"}


def test_glyph_map_covers_every_shape_distinct_narrow_and_bmp() -> None:
    shapes = [*palette.SHAPES, palette.WORKGROUP_SHAPE, palette.TWIN_SHAPE]
    assert set(fold_art.GLYPHS) == set(shapes)
    assert set(fold_art.SHAPE_GLYPHS) == set(mark_shapes.SHAPE_ORDER)
    glyphs = [fold_art.glyph(shape) for shape in shapes]
    assert len(set(glyphs)) == len(glyphs)
    assert fold_art.FALLBACK_GLYPH not in glyphs
    for shape, char in zip(shapes, glyphs):
        assert len(char) == 1, shape
        assert ord(char) < 0x10000, shape
        assert unicodedata.east_asian_width(char) in {"N", "Na"}, shape
        assert cell_len(char) == 1, shape
        assert unicodedata.category(char).startswith(("S", "L")), shape
    assert fold_art.glyph("bell") == fold_art.SHAPE_GLYPHS["bell"]


def test_an_unknown_shape_gets_the_diamond_glyph() -> None:
    assert fold_art.glyph("pencil") == fold_art.FALLBACK_GLYPH


def test_no_glyph_has_an_emoji_presentation() -> None:
    script = "const g = JSON.parse(process.argv[1]); process.stdout.write(JSON.stringify(g.filter((c) => /\\p{Emoji}/u.test(c))));"
    out = subprocess.run(["node", "-e", script, json.dumps(list(fold_art.GLYPHS.values()))], capture_output=True, text=True, check=True)
    assert json.loads(out.stdout) == []


@pytest.mark.parametrize(
    "mutate",
    [
        {"COLORTERM": "256color"},
        {"COLORTERM": ""},
        {"NO_COLOR": "1"},
        {"TERM": "dumb"},
        {"LANG": "C"},
        {"LC_ALL": "POSIX"},
    ],
)
def test_art_is_off_without_truecolor_colour_or_utf8_locale(mutate) -> None:
    env = {**TRUECOLOR, **mutate}
    assert not fold_art.supports_fold_art(FakeTTY(), env)


def test_art_is_off_for_a_pipe_and_for_a_non_utf8_stream() -> None:
    assert not fold_art.supports_fold_art(io.StringIO(), TRUECOLOR)
    ascii_tty = FakeTTY()
    ascii_tty.encoding = "ascii"
    assert not fold_art.supports_fold_art(ascii_tty, TRUECOLOR)


def test_art_is_on_for_a_truecolor_utf8_terminal() -> None:
    assert fold_art.supports_fold_art(FakeTTY(), TRUECOLOR)
    assert fold_art.supports_fold_art(FakeTTY(), {**TRUECOLOR, "COLORTERM": "24bit"})
    assert fold_art.supports_fold_art(FakeTTY(), {"COLORTERM": "truecolor"})


def test_the_default_profile_wears_twin_in_the_brand_ink_of_the_theme(tmp_path: Path) -> None:
    shapes = (REPO / "common" / "shapes.mjs").read_text()
    shipped = dict(re.findall(r'(light|dark): "(#[0-9a-f]{6})"', shapes.split("BRAND_INK =")[1].split("}")[0]))
    assert palette.BRAND_INK == shipped
    default_home = tmp_path / ".alpi"
    assert fold_art.identity(default_home, {"shape": "bell", "accent": "#3899e2"})[0] == palette.TWIN_SHAPE
    assert fold_art.identity(default_home, None) == (palette.TWIN_SHAPE, "#f3efe6")
    assert fold_art.identity(default_home, {"theme": "light"}) == (palette.TWIN_SHAPE, "#14110c")
    assert {str(s.style) for s in fold_art.art(*fold_art.identity(default_home, {"theme": "light"})).spans} == {"#14110c"}


def test_a_named_profile_wears_its_own_pair_and_defaults_to_the_round(tmp_path: Path) -> None:
    home = tmp_path / ".alpi" / "profiles" / "work"
    assert fold_art.identity(home, {"shape": "pill", "accent": "#2cb3b5"}) == ("pill", "#2cb3b5")
    assert fold_art.identity(home, {"fold": "rocket", "accent": "#2cb3b5"}) == ("pill", "#2cb3b5")
    assert fold_art.identity(home, {"shape": "pencil"}) == ("round", palette.DARK["accent"])
    assert fold_art.identity(home, None) == ("round", palette.DARK["accent"])
    assert fold_art.outline_of("rocket") == "round"


def test_marker_is_the_shape_glyph_when_supported_and_the_diamond_otherwise(tmp_path: Path) -> None:
    home = tmp_path / ".alpi" / "profiles" / "work"
    tui = {"shape": "heart", "accent": "#f36a8a"}
    assert fold_art.marker(home, tui, stream=FakeTTY(), env=TRUECOLOR) == (fold_art.SHAPE_GLYPHS["heart"], "#f36a8a")
    assert fold_art.marker(home, tui, stream=io.StringIO(), env=TRUECOLOR) == ("◆", "#f36a8a")
    assert fold_art.marker(home, tui, stream=FakeTTY(), env={**TRUECOLOR, "NO_COLOR": "1"}) == ("◆", "#f36a8a")
    assert fold_art.marker(tmp_path / ".alpi", None, stream=FakeTTY(), env=TRUECOLOR)[0] == fold_art.glyph(palette.TWIN_SHAPE)


def test_beside_aligns_the_lines_next_to_the_picture() -> None:
    picture = fold_art.art("diamond", "#f0b447", rows=4)
    joined = fold_art.beside(picture, [Text("name"), Text("model")], gap=2)
    rows = joined.plain.split("\n")
    assert len(rows) == 4
    assert re.search(r"name$", rows[1]) and re.search(r"model$", rows[2])
    assert {cell_len(row[: 8]) for row in rows} == {8}


def test_the_console_eye_ink_is_the_apps_mark_eye_token():
    import json
    import subprocess
    from pathlib import Path

    from alpi import palette

    tokens = Path(__file__).resolve().parents[2] / "common" / "tokens.mjs"
    script = f"import {{palettes}} from {json.dumps(str(tokens))};process.stdout.write(JSON.stringify([palettes.light.markEye, palettes.dark.markEye]));"
    light, dark = json.loads(subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True, check=True).stdout)
    assert palette.EYE_INK == {"light": light, "dark": dark}
