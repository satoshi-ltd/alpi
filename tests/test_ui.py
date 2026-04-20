"""Unit tests for alf/ui.py — the shared UI primitives.

UI is hard to test exhaustively without rendering a real terminal.
We focus on the pure bits: row formatting, accent_style, and the
password ``keep-current`` semantics (via a monkeypatched questionary).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from alf import ui


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


def test_text_returns_default_when_empty(monkeypatch) -> None:
    # rich.Prompt.ask returns the default when the user just presses
    # Enter — we rely on that behaviour.
    monkeypatch.setattr(ui.Prompt, "ask", lambda *a, **kw: kw.get("default", ""))
    assert ui.text("name:", default="alice") == "alice"


def test_text_strips_trailing_colon(monkeypatch) -> None:
    """Rich's Prompt.ask adds ``": "`` automatically. Labels that
    ship with ``:`` already (``"Email address:"``) would render as
    ``"Email address:: "`` if we didn't strip. Guard against the
    regression explicitly — future callers will write ``"X:"`` out of
    habit."""
    captured: dict = {}
    def fake_ask(prompt, **kw):
        # Prompt is a rich.Text or str depending on whether a default
        # is in play. Both stringify to the plain label for asserting.
        captured["prompt"] = str(prompt) if not isinstance(prompt, str) else prompt
        return ""
    monkeypatch.setattr(ui.Prompt, "ask", fake_ask)
    ui.text("Email address:")
    assert captured["prompt"] == "Email address"
    ui.text("  Trim me:\t")
    assert captured["prompt"] == "  Trim me"   # only trailing is stripped


def test_text_ctrl_c_returns_none(monkeypatch) -> None:
    def boom(*a, **kw):
        raise KeyboardInterrupt
    monkeypatch.setattr(ui.Prompt, "ask", boom)
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


def test_menu_appends_close_choice(monkeypatch) -> None:
    """The close item is added automatically, carries the Back/Exit
    label, and its title is styled muted via FormattedText tuples."""
    captured: dict = {}

    class _FakeQ:
        def __init__(self, choices):
            captured["choices"] = choices

        def unsafe_ask(self):
            return None

        @property
        def application(self):
            raise AttributeError  # bypass ESC wiring

    def fake_select(message, choices, **kwargs):
        return _FakeQ(choices)

    monkeypatch.setattr(ui.questionary, "select", fake_select)
    ui.menu("pick", [("Item", "v")], home=None, close="Back")

    # Last choice is the close row. Its title is FormattedText (a
    # list of (style, text) tuples), NOT a plain string — that's how
    # we dim the Back/Exit label without patching every caller.
    close = captured["choices"][-1]
    assert close.value is ui._CLOSE_SENTINEL
    text = "".join(chunk for _, chunk in close.title)
    assert "Back" in text


def test_menu_preserves_list_title_from_row(monkeypatch) -> None:
    """Regression: when the caller passes ``(ui.row(...), value)`` the
    list-of-tuples title used to be str()-ified, which produced the
    literal Python repr (``[('', 'X'), ('fg:#888888', ' · Y')]``) in
    the rendered menu. Lists must pass through untouched so questionary
    can extend its tokens and render the mixed styles."""
    captured: dict = {}

    class _FakeQ:
        def __init__(self, choices):
            captured["choices"] = choices

        def unsafe_ask(self):
            return None

        @property
        def application(self):
            raise AttributeError

    monkeypatch.setattr(
        ui.questionary, "select",
        lambda message, choices, **kw: _FakeQ(choices),
    )

    styled_title = ui.row("Label", "status")
    assert isinstance(styled_title, list)

    ui.menu("pick", [(styled_title, "v")], home=None, close=None)

    first = captured["choices"][0]
    assert isinstance(first.title, list), (
        "row() output must reach questionary as a list so its mixed "
        "(style, text) chunks render styled instead of repr-printed"
    )


def test_menu_close_uses_muted_style(monkeypatch) -> None:
    captured: dict = {}

    class _FakeQ:
        def __init__(self, choices):
            captured["choices"] = choices

        def unsafe_ask(self):
            return None

        @property
        def application(self):
            raise AttributeError

    monkeypatch.setattr(
        ui.questionary, "select",
        lambda message, choices, **kw: _FakeQ(choices),
    )
    ui.menu("pick", [("Item", "v")], home=None, close="Exit")

    close = captured["choices"][-1]
    styles = [style for style, _ in close.title]
    # Every chunk on the close row uses the muted fg style so the
    # Back/Exit label visually fades vs the action rows above it.
    assert all(ui._MUTED_STYLE in s for s in styles)
