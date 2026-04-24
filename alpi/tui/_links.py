from __future__ import annotations

from textual.content import Content, Span
from textual.style import Style
from textual.widgets._markdown import MarkdownBlock


_LINK_DECORATION = Style(bold=True, underline=True)


def _has_click_meta(style) -> bool:
    if not isinstance(style, Style):
        return False
    return "@click" in (style.meta or {})


def _wrap(_original):
    def _patched(self, token) -> Content:
        content = _original(self, token)
        if not any(_has_click_meta(s.style) for s in content.spans):
            return content
        new_spans = [
            Span(
                s.start, s.end,
                s.style + _LINK_DECORATION if _has_click_meta(s.style) else s.style,
            )
            for s in content.spans
        ]
        return Content(content.plain, new_spans)

    return _patched


def install() -> None:
    if getattr(MarkdownBlock._token_to_content, "_alpi_link_patched", False):
        return
    patched = _wrap(MarkdownBlock._token_to_content)
    patched._alpi_link_patched = True  # type: ignore[attr-defined]
    MarkdownBlock._token_to_content = patched
