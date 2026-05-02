"""Markdown link styling patch (BB)."""

from __future__ import annotations

from textual.content import Content
from textual.style import Style
from textual.widgets._markdown import MarkdownBlock


class _Node:
    def __init__(self, type_: str, content: str = "", attrs: dict | None = None):
        self.type = type_
        self.content = content
        self.attrs = attrs or {}
        self.children: list | None = None


def _link_token(href: str, text: str) -> _Node:
    root = _Node("inline")
    root.children = [
        _Node("link_open", attrs={"href": href}),
        _Node("text", content=text),
        _Node("link_close"),
    ]
    return root


def _plain_token(text: str) -> _Node:
    root = _Node("inline")
    root.children = [
        _Node("strong_open"),
        _Node("text", content=text),
        _Node("strong_close"),
    ]
    return root


def test_install_is_idempotent() -> None:
    from alpi.tui._links import install
    install()
    first = MarkdownBlock._token_to_content
    install()
    assert MarkdownBlock._token_to_content is first


def test_link_span_gets_bold_and_underline() -> None:
    from alpi.tui._links import install
    install()

    block = MarkdownBlock.__new__(MarkdownBlock)
    content = block._token_to_content(_link_token("https://alpi.dev", "alpi"))

    assert isinstance(content, Content)
    link_spans = [s for s in content.spans
                  if isinstance(s.style, Style) and "@click" in (s.style.meta or {})]
    assert link_spans, f"expected @click span, got {content.spans}"
    for span in link_spans:
        assert span.style.bold is True
        assert span.style.underline is True
        assert span.style.meta.get("@click") == "link('https://alpi.dev')"


def test_non_link_spans_are_untouched() -> None:
    from alpi.tui._links import install
    install()

    block = MarkdownBlock.__new__(MarkdownBlock)
    content = block._token_to_content(_plain_token("hey"))
    for span in content.spans:
        meta = span.style.meta if isinstance(span.style, Style) else {}
        assert "@click" not in (meta or {})
