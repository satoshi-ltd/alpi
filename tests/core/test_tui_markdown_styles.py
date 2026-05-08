"""Guard rules in ``alpi/tui/theme.tcss`` for Textual Markdown widgets."""

from __future__ import annotations

from importlib.resources import files


def _read_theme() -> str:
    return files("alpi.tui").joinpath("theme.tcss").read_text()


def test_theme_styles_heading_hierarchy() -> None:
    css = _read_theme()
    for level in ("MarkdownH1", "MarkdownH2", "MarkdownH3", "MarkdownH4"):
        assert f"AssistantMessage {level}" in css


def test_theme_styles_fenced_code_blocks() -> None:
    css = _read_theme()
    assert "AssistantMessage MarkdownFence" in css
    fence_rule = css.split("AssistantMessage MarkdownFence", 1)[1].split("}", 1)[0]
    assert ("background" in fence_rule) or ("border" in fence_rule)


def test_theme_styles_blockquote() -> None:
    assert "AssistantMessage MarkdownBlockQuote" in _read_theme()


def test_theme_styles_tables() -> None:
    css = _read_theme()
    assert "AssistantMessage MarkdownTable" in css
    assert "AssistantMessage MarkdownTH" in css


def test_theme_styles_horizontal_rule() -> None:
    assert "AssistantMessage MarkdownHorizontalRule" in _read_theme()
