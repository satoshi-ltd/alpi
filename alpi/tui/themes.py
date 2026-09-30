from __future__ import annotations

from textual.theme import Theme

from alpi.palette import DARK, DEFAULT_ACCENT, LIGHT, STATUS, resolve_accent

__all__ = ["DARK", "DEFAULT_ACCENT", "LIGHT", "STATUS", "build_theme", "resolve_accent"]


def build_theme(accent: str | None = None, dark: bool = True) -> Theme:
    palette = DARK if dark else LIGHT
    fg = palette["ink"]
    accent_hex = resolve_accent(accent, dark)
    return Theme(
        name=f"alpi-{'dark' if dark else 'light'}",
        accent=accent_hex,
        primary=accent_hex,
        secondary=accent_hex,
        foreground=fg,
        background=palette["bg"],
        surface=palette["bgPane"],
        panel=palette["bgElev"],
        warning=palette["warningText"],
        error=STATUS["danger"],
        success=STATUS["success"],
        dark=dark,
        variables={
            # Rich markup spans need a concrete hex; Textual's default is "auto 60%".
            "text-muted": palette["ink3"],
            "text-secondary": palette["ink2"],
            "markdown-h1-color": fg,
            "markdown-h2-color": fg,
            "markdown-h3-color": fg,
            "markdown-h4-color": fg,
            "markdown-h5-color": fg,
            "markdown-h2-text-style": "bold",
            "markdown-h4-text-style": "bold",
        },
    )
