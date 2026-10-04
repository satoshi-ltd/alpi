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

from alpi import appearance, fold_art, palette
from alpi.fold_shapes import SHAPES

REPO = Path(__file__).resolve().parents[2]
TRUECOLOR = {"COLORTERM": "truecolor", "TERM": "xterm-256color", "LANG": "en_US.UTF-8"}


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


def test_shapes_match_the_shared_folds_module() -> None:
    script = (
        "const m = await import(process.argv[1]);"
        "const ids = [...m.FOLD_IDS, m.WORKGROUP_FOLD, m.ALPACA_FOLD];"
        "process.stdout.write(JSON.stringify(Object.fromEntries(ids.map((id) => [id, m.foldFacets(id)]))));"
    )
    shared = _node(script, (REPO / "common" / "folds.mjs").as_uri())
    assert set(shared) == set(SHAPES) == {*palette.FOLDS, "honeycomb", "alpaca"}
    for fold, facets in shared.items():
        assert len(facets) == len(SHAPES[fold]), fold
        for expected, (tone, points) in zip(facets, SHAPES[fold]):
            assert expected["tone"] == tone
            assert len(expected["points"]) == len(points)
            for (ex, ey), (x, y) in zip(expected["points"], points):
                assert abs(ex - x) <= 0.0051 and abs(ey - y) <= 0.0051, fold


def test_shapes_file_is_not_stale() -> None:
    done = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "sync_fold_shapes.py"), "--check"],
        capture_output=True, text=True,
    )
    assert done.returncode == 0, done.stderr


def test_tones_match_the_shared_rule_for_every_accent_and_random_colours() -> None:
    rng = random.Random(7)
    randoms = [f"#{rng.randrange(1 << 24):06x}" for _ in range(40)]
    edge = ["#000000", "#ffffff", "#ff0000", "#00ff00", "#0000ff", "#abc", "#nonsense", ""]
    accents = [hex_ for _, hex_ in appearance.ACCENTS]
    script = (
        "const { foldTones } = await import(process.argv[1]);"
        "const hexes = JSON.parse(process.argv[2]);"
        "process.stdout.write(JSON.stringify(hexes.map((h) => foldTones(h))));"
    )
    inputs = accents + randoms + edge + ["#14110c", "#F3EFE6"]
    expected = _node(script, (REPO / "common" / "folds.mjs").as_uri(), json.dumps(inputs))
    for value, tones in zip(inputs, expected):
        assert list(fold_art.fold_tones(value)) == tones, value


def test_the_accent_list_the_tones_are_checked_against_is_the_shared_one() -> None:
    script = (
        "const { ACCENT_HEXES } = await import(process.argv[1]);"
        "process.stdout.write(JSON.stringify(ACCENT_HEXES));"
    )
    assert _node(script, (REPO / "common" / "accents.mjs").as_uri()) == [h for _, h in appearance.ACCENTS]


def test_art_is_half_blocks_two_cells_wide_per_row_in_the_three_tones() -> None:
    picture = fold_art.art("diamond", "#3899e2", rows=8)
    lines = picture.plain.split("\n")
    assert len(lines) == 8
    assert {len(line) for line in lines} == {16}
    assert set(picture.plain) <= {"▀", "▄", " ", "\n"}
    colours = {
        part for span in picture.spans for part in str(span.style).split(" on ")
    }
    assert set(fold_art.fold_tones("#3899e2")) <= colours


def test_art_leaves_the_background_transparent_outside_the_shape() -> None:
    cells = fold_art.grid("diamond", "#f0b447", rows=8)
    assert cells[0][0] == (None, None)
    assert cells[0][-1] == (None, None)
    assert cells[-1][0] == (None, None)
    assert any(top and bottom for line in cells for top, bottom in line)
    picture = fold_art.art("diamond", "#f0b447", rows=8)
    assert picture.plain.split("\n")[0].startswith(" ")


def test_art_cell_pairs_top_as_foreground_and_bottom_as_background() -> None:
    cells = fold_art.grid("diamond", "#f0b447", rows=8)
    light, base, shade = fold_art.fold_tones("#f0b447")
    middle = cells[3][8]
    assert middle[0] and middle[1]
    picture = fold_art.art("diamond", "#f0b447", rows=8)
    first_filled = next(span for span in picture.spans if " on " in str(span.style))
    top, bottom = str(first_filled.style).split(" on ")
    assert {top, bottom} <= {light, base, shade}


def test_art_scales_with_rows_and_draws_every_shape() -> None:
    for fold in SHAPES:
        small = fold_art.art(fold, "#f0b447", rows=4)
        large = fold_art.art(fold, "#f0b447", rows=12)
        assert len(small.plain.split("\n")) == 4
        assert len(large.plain.split("\n")) == 12
        assert small.plain.strip() and large.plain.strip()


def test_glyph_map_covers_every_object_distinct_narrow_and_bmp() -> None:
    folds = [*palette.FOLDS, "honeycomb", palette.ALPACA_FOLD]
    assert set(fold_art.GLYPHS) == set(folds)
    glyphs = [fold_art.glyph(fold) for fold in folds]
    assert len(set(glyphs)) == len(glyphs)
    assert fold_art.FALLBACK_GLYPH not in glyphs
    for fold, char in zip(folds, glyphs):
        assert len(char) == 1, fold
        assert ord(char) < 0x10000, fold
        assert unicodedata.east_asian_width(char) in {"N", "Na"}, fold
        assert cell_len(char) == 1, fold
        assert unicodedata.category(char).startswith(("S", "L")), fold


def test_an_unknown_fold_gets_the_diamond_glyph() -> None:
    assert fold_art.glyph("pencil") == fold_art.FALLBACK_GLYPH


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


def test_the_default_profile_wears_the_alpaca_in_the_brand_accent(tmp_path: Path) -> None:
    default_home = tmp_path / ".alpi"
    assert fold_art.identity(default_home, {"fold": "shield", "accent": "#3899e2"})[0] == "alpaca"
    assert fold_art.identity(default_home, None) == ("alpaca", palette.BRAND_INK["dark"])
    assert fold_art.identity(default_home, {"theme": "light"}) == ("alpaca", palette.BRAND_INK["light"])


def test_a_named_profile_wears_its_own_pair_and_defaults_to_the_diamond(tmp_path: Path) -> None:
    home = tmp_path / ".alpi" / "profiles" / "work"
    assert fold_art.identity(home, {"fold": "rocket", "accent": "#2cb3b5"}) == ("rocket", "#2cb3b5")
    assert fold_art.identity(home, {"fold": "pencil"}) == ("diamond", palette.DARK["accent"])
    assert fold_art.identity(home, None) == ("diamond", palette.DARK["accent"])


def test_marker_is_the_fold_glyph_when_supported_and_the_diamond_otherwise(tmp_path: Path) -> None:
    home = tmp_path / ".alpi" / "profiles" / "work"
    tui = {"fold": "heart", "accent": "#f36a8a"}
    assert fold_art.marker(home, tui, stream=FakeTTY(), env=TRUECOLOR) == (fold_art.glyph("heart"), "#f36a8a")
    assert fold_art.marker(home, tui, stream=io.StringIO(), env=TRUECOLOR) == ("◆", "#f36a8a")
    assert fold_art.marker(home, tui, stream=FakeTTY(), env={**TRUECOLOR, "NO_COLOR": "1"}) == ("◆", "#f36a8a")
    assert fold_art.marker(tmp_path / ".alpi", None, stream=FakeTTY(), env=TRUECOLOR)[0] == fold_art.glyph("alpaca")


def test_beside_aligns_the_lines_next_to_the_picture() -> None:
    from rich.text import Text

    picture = fold_art.art("diamond", "#f0b447", rows=4)
    joined = fold_art.beside(picture, [Text("name"), Text("model")], gap=2)
    rows = joined.plain.split("\n")
    assert len(rows) == 4
    assert re.search(r"name$", rows[1]) and re.search(r"model$", rows[2])
    assert {cell_len(row[: 8]) for row in rows} == {8}


def test_no_glyph_has_an_emoji_presentation() -> None:
    import json
    import subprocess

    script = "const g = JSON.parse(process.argv[1]); process.stdout.write(JSON.stringify(g.filter((c) => /\\p{Emoji}/u.test(c))));"
    out = subprocess.run(["node", "-e", script, json.dumps(list(fold_art.GLYPHS.values()))], capture_output=True, text=True, check=True)
    assert json.loads(out.stdout) == []


def test_the_console_alpaca_wears_the_brand_ink_of_the_theme(tmp_path) -> None:
    folds = (Path(__file__).resolve().parents[2] / "common" / "folds.mjs").read_text()
    shipped = dict(re.findall(r'(light|dark): "(#[0-9a-f]{6})"', folds.split("BRAND_INK =")[1].split("}")[0]))
    assert palette.BRAND_INK == shipped
    root = tmp_path / "root"
    root.mkdir()
    assert fold_art.identity(root, {"theme": "light"}) == (palette.ALPACA_FOLD, "#14110c")
    assert fold_art.identity(root, {"theme": "dark"}) == (palette.ALPACA_FOLD, "#f3efe6")
    assert fold_art.identity(tmp_path / "profiles" / "doc", {"theme": "light", "fold": "shield", "accent": "#3899e2"})[1] == "#3899e2"
