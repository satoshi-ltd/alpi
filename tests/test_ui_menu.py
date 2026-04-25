from __future__ import annotations

from alpi import ui


def test_heading_is_a_namedtuple_with_text_field() -> None:
    h = ui.Heading("Agent")
    assert h.text == "Agent"
    assert isinstance(h, tuple)


def test_menu_entries_skip_heading_in_selectable_mask(monkeypatch) -> None:
    """``Heading`` items produce non-selectable entries so the cursor
    never lands on them. Subsequent headings auto-prepend a blank
    spacer to give the section visual breathing room."""
    captured: dict = {}

    def fake_run_select(entries, *, home):
        captured["entries"] = entries
        return None

    monkeypatch.setattr(ui, "_run_select", fake_run_select)
    ui.menu(
        "",
        [
            ui.Heading("Agent"),
            ("Model", "model", ""),
            ui.Heading("Workspace"),
            ("Workspace", "workspace", ""),
        ],
        close="",
    )
    entries = captured["entries"]
    selectable = [sel for _, _, sel in entries]
    # heading, model, blank, heading, workspace
    assert selectable == [False, True, False, False, True]


def test_menu_renders_heading_as_passed(monkeypatch) -> None:
    """Headings render their text verbatim — no auto upper/lowercase. So
    ``ALP (Alpi Link Protocol)`` and ``Agent`` survive intact."""
    captured: dict = {}

    def fake_run_select(entries, *, home):
        captured["entries"] = entries
        return None

    monkeypatch.setattr(ui, "_run_select", fake_run_select)
    ui.menu(
        "",
        [
            ui.Heading("ALP (Alpi Link Protocol)"),
            ("Peers", "peers", ""),
        ],
        close="",
    )
    title_ft, _, _ = captured["entries"][0]
    assert isinstance(title_ft, list)
    assert title_ft[0][1] == "ALP (Alpi Link Protocol)"
    assert "bold" in title_ft[0][0]


def test_menu_does_not_prepend_blank_before_first_heading(monkeypatch) -> None:
    """The first heading sits flush at the top — only later headings
    pick up the auto blank row."""
    captured: dict = {}

    def fake_run_select(entries, *, home):
        captured["entries"] = entries
        return None

    monkeypatch.setattr(ui, "_run_select", fake_run_select)
    ui.menu(
        "",
        [ui.Heading("First"), ("a", "a", "")],
        close="",
    )
    title_ft, _, _ = captured["entries"][0]
    assert isinstance(title_ft, list)
    assert title_ft[0][1] == "First"
