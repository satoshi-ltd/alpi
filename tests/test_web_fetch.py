"""Unit tests for web_fetch (HTML → Markdown conversion)."""

from __future__ import annotations

from alpi.tools.web_fetch import _html_to_markdown


def test_strips_scripts_and_styles() -> None:
    html = """
    <html><head><style>body{color:red}</style>
    <script>alert('hi')</script></head>
    <body><h1>Hello</h1><p>World</p></body></html>
    """
    md = _html_to_markdown(html)
    assert "alert" not in md
    assert "color:red" not in md
    assert "Hello" in md
    assert "World" in md


def test_keeps_links_by_default() -> None:
    html = '<p>Go to <a href="https://example.com">example</a> now.</p>'
    md = _html_to_markdown(html, strip_links=False)
    assert "example" in md
    assert "https://example.com" in md


def test_strip_links_removes_urls() -> None:
    html = '<p>Go to <a href="https://example.com">example</a> now.</p>'
    md = _html_to_markdown(html, strip_links=True)
    assert "example" in md
    assert "https://example.com" not in md


def test_headings_preserved() -> None:
    html = "<h1>Title</h1><h2>Subtitle</h2><p>Body</p>"
    md = _html_to_markdown(html)
    assert "# Title" in md
    assert "## Subtitle" in md


def test_collapses_blank_lines() -> None:
    html = "<p>a</p><br/><br/><br/><br/><p>b</p>"
    md = _html_to_markdown(html)
    assert "\n\n\n" not in md
