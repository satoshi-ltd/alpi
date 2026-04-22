"""Unit tests for alpi/ui.py — the shared UI primitives.

UI is hard to test exhaustively without rendering a real terminal.
We focus on the pure bits: row formatting, accent_style, and the
password ``keep-current`` semantics.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from alpi import ui


# --------------------------------------------------------------------
# Row formatting — the thing every menu depends on for alignment
# --------------------------------------------------------------------


def _row_text(out) -> str:
    """Flatten either a FormattedText or a plain string to text."""
    if isinstance(out, str):
        return out
    return "".join(chunk for _, chunk in out)


def _row_styles(out) -> list[str]:
    if isinstance(out, str):
        return [""]
    return [style for style, _ in out]


def test_row_pads_label_to_column_width() -> None:
    out = ui.row("Telegram", "ready")
    # Label padded to LABEL_WIDTH before the separator.
    text = _row_text(out)
    assert text.startswith("Telegram")
    assert text[: ui.LABEL_WIDTH].rstrip() == "Telegram"
    assert "·" in text


def test_row_without_status_is_just_the_label() -> None:
    out = ui.row("Email")
    # Plain string when there's nothing to mute.
    assert isinstance(out, str)
    assert out == "Email"


def test_row_status_is_muted() -> None:
    """Status chunk renders dim so description reads quieter than label."""
    out = ui.row("Telegram", "ready · 2 allowlisted")
    styles = _row_styles(out)
    # First chunk (label) is unstyled, status chunk carries the muted fg.
    assert any(ui._MUTED_STYLE in s for s in styles)


def test_row_preserves_long_labels() -> None:
    out = ui.row("A very long label", "x")
    text = _row_text(out)
    assert "A very long label" in text
    assert "x" in text


# --------------------------------------------------------------------
# accent_style
# --------------------------------------------------------------------


def test_accent_style_hex_builds_style() -> None:
    s = ui.accent_style("#E60023")
    assert s is not None
    rules = dict(s.style_rules)
    assert rules["pointer"] == "fg:#E60023 bold"


def test_accent_style_empty_returns_none() -> None:
    assert ui.accent_style("") is None
    assert ui.accent_style("   ") is None


# --------------------------------------------------------------------
# Password "keep current" semantics
# --------------------------------------------------------------------


def test_password_empty_input_keeps_current(monkeypatch) -> None:
    # password() reads via getpass.getpass now — rich.Prompt dropped
    # keystrokes on some terminals, so we bypass it.
    import getpass
    monkeypatch.setattr(getpass, "getpass", lambda _prompt="": "")
    assert ui.password("Token:", current="keep-me-sekret") == "keep-me-sekret"


def test_password_new_input_replaces(monkeypatch) -> None:
    import getpass
    monkeypatch.setattr(getpass, "getpass", lambda _prompt="": "new-value")
    assert ui.password("Token:", current="old") == "new-value"


def test_password_no_current_passes_through(monkeypatch) -> None:
    import getpass
    monkeypatch.setattr(getpass, "getpass", lambda _prompt="": "from-scratch")
    assert ui.password("Token:") == "from-scratch"


def test_password_ctrl_c_returns_none(monkeypatch) -> None:
    import getpass
    def boom(_prompt=""):
        raise KeyboardInterrupt
    monkeypatch.setattr(getpass, "getpass", boom)
    assert ui.password("Token:") is None


# --------------------------------------------------------------------
# text — default + Ctrl-C
# --------------------------------------------------------------------


def _fake_session(monkeypatch, *, result: str | None, capture: dict | None = None):
    """Stub ``PromptSession`` so ``text()`` returns ``result`` without a TTY."""
    import prompt_toolkit

    class _S:
        def __init__(self, message=None, **_kw):
            if capture is not None:
                capture["message"] = message

        def prompt(self):
            return result

    monkeypatch.setattr(prompt_toolkit, "PromptSession", _S)


def test_text_returns_default_when_empty(monkeypatch) -> None:
    _fake_session(monkeypatch, result="")
    assert ui.text("name:", default="alice") == "alice"


def test_text_strips_trailing_colon(monkeypatch) -> None:
    """Labels that ship with ``:`` already (``"Email address:"``) must
    not render double-colons once we append our own prompt ``": "``."""
    captured: dict = {}
    _fake_session(monkeypatch, result="", capture=captured)

    ui.text("Email address:")
    text = "".join(chunk for _, chunk in captured["message"])
    assert text.startswith("Email address: ")
    assert "::" not in text


def test_text_ctrl_c_returns_none(monkeypatch) -> None:
    import prompt_toolkit

    class _S:
        def __init__(self, *a, **kw):
            pass

        def prompt(self):
            raise KeyboardInterrupt

    monkeypatch.setattr(prompt_toolkit, "PromptSession", _S)
    assert ui.text("name:") is None


def test_text_escape_returns_none(monkeypatch) -> None:
    # prompt_toolkit returns None from app.exit(result=None) on ESC.
    _fake_session(monkeypatch, result=None)
    assert ui.text("name:") is None


# --------------------------------------------------------------------
# confirm — cancel maps to default
# --------------------------------------------------------------------


def test_confirm_ctrl_c_returns_default(monkeypatch) -> None:
    def boom(*a, **kw):
        raise KeyboardInterrupt
    monkeypatch.setattr(ui.Confirm, "ask", boom)
    assert ui.confirm("OK?", default=True) is True
    assert ui.confirm("OK?", default=False) is False


# --------------------------------------------------------------------
# menu — minimal shape test
# --------------------------------------------------------------------


def test_menu_appends_close_entry(monkeypatch) -> None:
    """The close row is added automatically, styled muted, and picking
    it returns ``None`` to the caller."""
    captured: dict = {}

    def fake_run_select(entries, *, home):
        captured["entries"] = entries
        # Simulate user picking the close entry.
        return entries[-1][1]

    monkeypatch.setattr(ui, "_run_select", fake_run_select)
    result = ui.menu("pick", [("Item", "v")], home=None, close="Back")
    assert result is None

    close_title, _close_value, selectable = captured["entries"][-1]
    assert selectable is True
    text = "".join(chunk for _, chunk in close_title)
    assert "Back" in text


def test_menu_preserves_list_title_from_row(monkeypatch) -> None:
    """``(ui.row(...), value)`` must reach the renderer as a list of
    ``(style, text)`` chunks so the mixed styles render instead of
    being str()-ified to their Python repr."""
    captured: dict = {}

    def fake_run_select(entries, *, home):
        captured["entries"] = entries
        return None

    monkeypatch.setattr(ui, "_run_select", fake_run_select)

    styled_title = ui.row("Label", "status")
    assert isinstance(styled_title, list)

    ui.menu("pick", [(styled_title, "v")], home=None, close=None)

    first_title, _v, _sel = captured["entries"][0]
    assert isinstance(first_title, list)


def test_menu_close_uses_muted_style(monkeypatch) -> None:
    captured: dict = {}

    def fake_run_select(entries, *, home):
        captured["entries"] = entries
        return None

    monkeypatch.setattr(ui, "_run_select", fake_run_select)
    ui.menu("pick", [("Item", "v")], home=None, close="Exit")

    close_title, _v, _sel = captured["entries"][-1]
    styles = [style for style, _ in close_title]
    assert all(ui._MUTED_STYLE in s for s in styles)


def test_menu_selection_returns_value(monkeypatch) -> None:
    def fake_run_select(entries, *, home):
        # Pick first entry.
        return entries[0][1]

    monkeypatch.setattr(ui, "_run_select", fake_run_select)
    result = ui.menu("pick", [("Item", "v")], home=None, close=None)
    assert result == "v"


def test_menu_none_item_becomes_separator(monkeypatch) -> None:
    captured: dict = {}

    def fake_run_select(entries, *, home):
        captured["entries"] = entries
        return None

    monkeypatch.setattr(ui, "_run_select", fake_run_select)
    ui.menu("pick", [("A", "a"), None, ("B", "b")], home=None, close=None)
    # Middle entry is a non-selectable separator.
    assert captured["entries"][1][2] is False
