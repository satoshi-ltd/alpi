"""MarkdownV2 renderer for Telegram."""

from __future__ import annotations

from alpi.gateway.platforms._md2 import to_markdown_v2


def test_empty_input_returns_empty() -> None:
    assert to_markdown_v2("") == ""


def test_plain_text_escapes_specials() -> None:
    out = to_markdown_v2("Hello, world! Version 1.2.3.")
    # . , ! are escaped; comma is not in the spec so stays as-is.
    assert out == r"Hello, world\! Version 1\.2\.3\."


def test_bold_converts_to_single_asterisk() -> None:
    out = to_markdown_v2("**important**")
    assert out == "*important*"


def test_italic_single_asterisk_becomes_underscore() -> None:
    out = to_markdown_v2("*accent*")
    assert out == "_accent_"


def test_bold_inside_plain_text() -> None:
    out = to_markdown_v2("say **hi** to me")
    assert out == r"say *hi* to me"


def test_inline_code_preserved_and_specials_not_escaped_inside() -> None:
    out = to_markdown_v2("run `rm -rf .` now")
    # Inside code, `.` and `-` stay literal.
    assert out == r"run `rm -rf .` now"


def test_inline_code_protects_asterisks() -> None:
    out = to_markdown_v2("use `**` for bold")
    # `**` inside code must NOT be interpreted as bold.
    assert out == r"use `**` for bold"


def test_fenced_code_block_keeps_body_verbatim() -> None:
    src = "```python\nif x == 1.0: pass\n```"
    out = to_markdown_v2(src)
    assert out == "```python\nif x == 1.0: pass\n```"


def test_fenced_code_block_escapes_backticks_and_backslashes() -> None:
    src = "```\nhello `world` \\n\n```"
    out = to_markdown_v2(src)
    assert "\\`world\\`" in out
    assert "\\\\n" in out


def test_link_display_escapes_but_url_preserves_dots() -> None:
    out = to_markdown_v2("see [the docs](https://example.com/path.html)")
    assert r"\(https://example.com/path.html\)" not in out
    assert out == r"see [the docs](https://example.com/path.html)"


def test_header_renders_as_bold() -> None:
    out = to_markdown_v2("# Intro\nbody")
    assert out.startswith("*Intro*\n")
    assert "body" in out


def test_header_strips_redundant_bold_inside() -> None:
    out = to_markdown_v2("## **Section**")
    assert "*Section*" in out


def test_dots_escaped_outside_code_but_not_inside() -> None:
    out = to_markdown_v2("v1.2.3 vs `v4.5.6`")
    assert r"v1\.2\.3" in out
    assert "`v4.5.6`" in out


def test_parens_escaped_outside_link() -> None:
    out = to_markdown_v2("(see above) and [link](https://x.com)")
    assert r"\(see above\)" in out
    assert "[link](https://x.com)" in out


def test_italic_does_not_mangle_bullet_list_marker() -> None:
    src = "* one\n* two\n* three"
    out = to_markdown_v2(src)
    # Each ``* `` starts its own line; the regex requires the italic to
    # sit on a single line without other asterisks — bullets survive.
    assert "* one" in out  # leading * escaped
    # verify the * is escaped, not converted to underscore
    assert r"\* one" in out or "\\* one" in out


def test_mixed_markdown_roundtrip() -> None:
    src = "**Bold** and *italic* with `code` and a [link](https://a.b)."
    out = to_markdown_v2(src)
    # Bold segment
    assert "*Bold*" in out
    # Italic segment
    assert "_italic_" in out
    # Inline code preserved
    assert "`code`" in out
    # Link preserved (display has no specials to escape here)
    assert "[link](https://a.b)" in out
    # Trailing dot escaped
    assert out.endswith(r"\.")


def test_nested_bold_inside_link_display() -> None:
    """The agent sometimes wraps link text in bold — display escapes
    apply, but `*` is a special char, so the `**` becomes `\\*\\*` in
    the display. That's correct — we don't re-interpret Markdown
    inside a link display."""
    out = to_markdown_v2("[**click**](https://x.com)")
    # Display part has literal ** because inside [] we treat as plain.
    assert r"[\*\*click\*\*](https://x.com)" == out


def test_code_block_without_language_tag() -> None:
    src = "```\nplain\n```"
    out = to_markdown_v2(src)
    assert out == "```\nplain\n```"


def test_backslash_in_plain_text_escaped() -> None:
    out = to_markdown_v2(r"path\to\file")
    assert out == r"path\\to\\file"
