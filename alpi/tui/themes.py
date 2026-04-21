"""Alf theme factory — builds a Textual Theme from the user's accent."""

from __future__ import annotations

from textual.theme import Theme


_DARK = {
    "background": "#1a1a1a",
    "surface":    "#2d2d2d",
    "foreground": "#e0e0e0",
    "muted":      "#8a8a8a",
}

_LIGHT = {
    "background": "#f5f5f5",
    "surface":    "#ffffff",
    "foreground": "#1a1a1a",
    "muted":      "#6a6a6a",
}


def build_theme(accent: str, dark: bool = True) -> Theme:
    palette = _DARK if dark else _LIGHT
    fg = palette["foreground"]

    return Theme(
        name=f"alf-{'dark' if dark else 'light'}",
        accent=accent,
        primary=accent,
        secondary=accent,
        foreground=fg,
        background=palette["background"],
        surface=palette["surface"],
        # Status colors need explicit values — omitting falls back to primary
        # (= accent), which would make errors/warnings read as accent.
        warning="#ffa62b",
        error="#ba3c5b",
        success="#4EBF71",
        dark=dark,
        variables={
            # Textual's default `text-muted` is `"auto 60%"` (valid CSS,
            # invalid Rich markup). Concrete hex so our markup spans work.
            "text-muted": palette["muted"],
            "markdown-h1-color": fg,
            "markdown-h2-color": fg,
            "markdown-h3-color": fg,
            "markdown-h4-color": fg,
            "markdown-h5-color": fg,
            "markdown-h2-text-style": "bold",
            "markdown-h4-text-style": "bold",
        },
    )
