from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from alpi import charts

FIXTURES = Path(__file__).resolve().parents[1] / "common" / "chartSpec.fixtures.mjs"
CASE_ROW = re.compile(r'^\s*\[("(?:[^"\\]|\\.)*"), ("(?:[^"\\]|\\.)*"|null)\],$', re.M)
SOURCE = FIXTURES.read_text(encoding="utf-8")
CHART_BLOCK, FORMAT_BLOCK = SOURCE.split("export const FORMAT_CASES")
CASES = [(json.loads(src), json.loads(out)) for src, out in CASE_ROW.findall(CHART_BLOCK)]
FORMAT_ROW = re.compile(r'^\s*\[(\S+?), ("(?:[^"\\]|\\.)*"), ("(?:[^"\\]|\\.)*")\],$', re.M)
FORMATS = [(json.loads(v), json.loads(u), json.loads(t)) for v, u, t in FORMAT_ROW.findall(FORMAT_BLOCK)]

LINE = '{"type": "line", "title": "Chats per day", "x": ["Oct 4", "Oct 5", "Oct 6", "Oct 7"], "series": [{"name": "This week", "values": [2161, 1987, null, 1743]}, {"name": "Last week", "values": [2050, 2102, 1968, 1888]}]}'
BARS = '{"type": "bar", "title": "Chats by locale", "x": ["es-ES", "en-GB", "de-DE"], "series": [{"values": [863, 509, 214]}]}'
STACKED = '{"type": "bar", "stacked": true, "x": ["Mon", "Tue"], "series": [{"name": "AI", "values": [1420, 1310]}, {"name": "Human", "values": [741, 677]}]}'


def test_the_shared_chart_corpus_is_readable() -> None:
    assert len(CASES) == CHART_BLOCK.count("\n  [")
    assert len(FORMATS) == FORMAT_BLOCK.count("\n  [") > 10


@pytest.mark.parametrize(("source", "expected"), CASES, ids=lambda v: (v or "null")[:40])
def test_parse_chart_matches_the_shared_corpus(source: str, expected: str | None) -> None:
    got = charts.parse_chart(source)
    assert (json.dumps(got, ensure_ascii=False, sort_keys=True) if got else None) == (json.dumps(json.loads(expected), ensure_ascii=False, sort_keys=True) if expected else None)


def test_a_line_renders_as_one_sparkline_per_series_with_its_range() -> None:
    text = charts.render_text(charts.parse_chart(LINE))
    assert text.splitlines() == [
        "Chats per day",
        "This week  █▅ ▁  2,161 → 1,743",
        "Last week  ▆▇▅▃  2,050 → 1,888",
        "Oct 4 – Oct 7 · 1,743 – 2,161",
    ]


def test_bars_render_as_block_bars_scaled_to_the_largest() -> None:
    lines = charts.render_text(charts.parse_chart(BARS)).splitlines()
    assert lines[0] == "Chats by locale"
    assert lines[1].startswith("es-ES  " + "█" * 24) and lines[1].endswith("863")
    assert lines[3].startswith("de-DE  ██████ ") and lines[3].endswith("214")


def test_a_stacked_bar_fills_each_series_with_its_own_shade_and_shows_the_total() -> None:
    lines = charts.render_text(charts.parse_chart(STACKED)).splitlines()
    assert lines[0].startswith("Mon  ████") and "▓" in lines[0] and lines[0].endswith("2,161")
    assert lines[-1] == "█ AI  ▓ Human"


def test_textify_swaps_valid_blocks_and_leaves_broken_ones() -> None:
    md = f"Intro\n\n```chart\n{BARS}\n```\n\n```chart\n{{bad}}\n```\n"
    out = charts.textify(md)
    assert "````text\nChats by locale\nes-ES" in out
    assert "```chart\n{bad}\n```" in out
    assert BARS not in out


@pytest.mark.parametrize(("value", "unit", "text"), FORMATS)
def test_values_read_like_the_apps_label_them(value, unit, text) -> None:
    assert charts.format_value(value, unit) == text


def test_textify_reads_crlf_indented_and_annotated_fences() -> None:
    block = '{"type": "bar", "x": ["a", "b"], "series": [{"values": [1, 2]}]}'
    assert "````text" in charts.textify(f"```chart\r\n{block}\r\n```\r\n")
    indented = charts.textify(f"- item\n\n  ```chart weekly\n  {block}\n  ```")
    assert "  ````text\n  a  " in indented and block not in indented


def test_a_title_with_backticks_cannot_close_the_text_fence() -> None:
    out = charts.textify('```chart\n{"type": "bar", "title": "a ``` b", "x": ["a"], "series": [{"values": [1]}]}\n```')
    assert out.startswith("````text\na ``` b\n") and out.endswith("\n````")


def test_a_huge_integer_is_refused_instead_of_raising() -> None:
    assert charts.parse_chart('{"type": "bar", "x": ["a"], "series": [{"values": [1' + "0" * 400 + ']}]}') is None
    assert charts.textify('```chart\n{"type": "bar", "x": [1' + "0" * 400 + '], "series": [{"values": [1]}]}\n```').startswith("```chart")


def test_wide_labels_align_by_their_display_width() -> None:
    lines = charts.render_text(charts.parse_chart('{"type": "bar", "x": ["日本", "abcd"], "series": [{"values": [2, 1]}]}')).splitlines()
    columns = [charts._width(line[: line.index("█")]) for line in lines]
    assert columns[0] == columns[1] == 6


def test_a_long_unit_sits_once_beside_the_title_and_labels_keep_24_characters() -> None:
    spec = charts.parse_chart('{"type": "bar", "title": "Prices", "unit": "$/M tokens", "x": ["DeepSeek V4 Flash 0731", "An even longer model name here"], "series": [{"values": [0.016, 4]}]}')
    lines = charts.render_text(spec).splitlines()
    assert lines[0] == "Prices · $/M tokens"
    assert lines[1].startswith("DeepSeek V4 Flash 0731  ") and lines[1].endswith("0.016")
    assert lines[2].startswith("An even longer model na…")


def test_a_unit_the_title_already_says_is_not_repeated() -> None:
    spec = charts.parse_chart('{"type": "bar", "title": "Bookings per day", "unit": "bookings", "x": ["Mon"], "series": [{"values": [12]}]}')
    assert charts.render_text(spec).splitlines()[0] == "Bookings per day"


def test_a_short_unit_inside_a_word_of_the_title_still_shows() -> None:
    spec = charts.parse_chart('{"type": "bar", "title": "Response time", "unit": "s", "x": ["api"], "series": [{"values": [1.5]}]}')
    assert charts.render_text(spec).splitlines()[0] == "Response time · s"
