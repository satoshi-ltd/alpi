"""Tests for the TUI list-row helper (alpi/tui/list_row.py)."""

from __future__ import annotations

from alpi.tui import list_row


def test_name_width_respects_floor() -> None:
    assert list_row.name_width(["a", "b"]) == 14  # default floor


def test_name_width_grows_with_content() -> None:
    assert list_row.name_width(["short", "a-very-long-provider-name"]) == len(
        "a-very-long-provider-name"
    )


def test_name_width_floor_override() -> None:
    assert list_row.name_width(["x"], floor=8) == 8


def test_row_text_pads_name_and_muted_desc() -> None:
    t = list_row.row_text("foo", "bar", width=10)
    plain = t.plain
    # Inactive rows get a 2-space pad instead of the active glyph.
    assert plain.startswith("  foo       ")   # "  " + "foo".ljust(10)
    assert "  · bar" in plain
    # Description is in a dim span.
    styles = [str(span.style) for span in t.spans]
    assert any("dim" in s for s in styles)


def test_row_text_active_uses_accent_glyph() -> None:
    t = list_row.row_text("foo", "bar", width=10, active=True, accent="#ff8800")
    plain = t.plain
    # Active row has the ◆ glyph, then the (still-uncoloured) name.
    assert plain.startswith("◆ foo       ")
    # Accent style applies to the GLYPH, not the name — avoids clashing
    # with OptionList's accent-background highlight bar.
    styles = [str(span.style) for span in t.spans]
    assert any("#ff8800" in s for s in styles)
    # No span should carry both bold AND accent on the name text.
    assert not any("bold" in s and "#ff8800" in s for s in styles)


def test_row_text_active_without_accent_falls_back() -> None:
    """Active + no accent → indistinguishable from inactive (safe fallback)."""
    t = list_row.row_text("foo", "bar", width=10, active=True, accent=None)
    assert t.plain.startswith("  foo")   # same 2-space pad as inactive


def test_row_text_no_description_has_no_separator() -> None:
    t = list_row.row_text("foo", "", width=10)
    assert "·" not in t.plain


def test_build_options_uses_common_width_without_marker() -> None:
    """Without an active_key, the marker slot is omitted by default."""
    items = [
        ("k1", "short", "aaa"),
        ("k2", "very-long-name", "bbb"),
    ]
    opts = list_row.build_options(items, floor=5)
    # Both rows use the max of the names, no prefix.
    assert opts[0].prompt.plain.startswith("short         ")
    assert opts[1].prompt.plain.startswith("very-long-name")


def test_build_options_adds_marker_slot_when_active_key_given() -> None:
    items = [
        ("k1", "short", "aaa"),
        ("k2", "very-long-name", "bbb"),
    ]
    opts = list_row.build_options(items, active_key="k2", accent="#ff8800", floor=5)
    assert opts[0].prompt.plain.startswith("  short         ")
    assert opts[1].prompt.plain.startswith("◆ very-long-name")


def test_build_options_marks_active_key_with_glyph() -> None:
    items = [("a", "A", "x"), ("b", "B", "y")]
    opts = list_row.build_options(items, active_key="b", accent="#ff8800")
    # Active row has the accent glyph prefix; inactive rows have "  ".
    assert opts[0].prompt.plain.startswith("  A")
    assert opts[1].prompt.plain.startswith("◆ B")


def test_build_options_with_marker_false_strips_prefix() -> None:
    items = [("a", "A", "x"), ("b", "B", "y")]
    opts = list_row.build_options(items, with_marker=False)
    assert opts[0].prompt.plain.startswith("A")
    assert opts[1].prompt.plain.startswith("B")


def test_build_options_preserves_ids_and_order() -> None:
    items = [("x", "Xname", "xd"), ("y", "Yname", "yd"), ("z", "Zname", "zd")]
    opts = list_row.build_options(items)
    assert [o.id for o in opts] == ["x", "y", "z"]
