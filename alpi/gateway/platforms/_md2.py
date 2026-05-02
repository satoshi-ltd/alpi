"""Convert Markdown to Telegram MarkdownV2."""

from __future__ import annotations

import re

_MDV2_SPECIAL_RE = re.compile(r'([_*\[\]()~`>#\+\-=|{}.!\\])')


def to_markdown_v2(src: str) -> str:
    """Rewrite `src` for Telegram MarkdownV2."""
    if not src:
        return src

    placeholders: dict[str, str] = {}
    counter = [0]

    def stash(value: str) -> str:
        key = f"\x00MD{counter[0]}\x00"
        counter[0] += 1
        placeholders[key] = value
        return key

    text = src

    # 1. Fenced code blocks.
    def _fenced(m: re.Match) -> str:
        raw = m.group(0)
        nl = raw.find('\n', 3)
        if nl == -1:
            opening, body = '```', raw[3:-3]
        else:
            opening, body = raw[:nl + 1], raw[nl + 1:-3]
        body = body.replace('\\', '\\\\').replace('`', '\\`')
        return stash(opening + body + '```')

    text = re.sub(r'```[\s\S]*?```', _fenced, text)

    # 2. Inline code.
    text = re.sub(
        r'`[^`]+`',
        lambda m: stash(m.group(0).replace('\\', '\\\\')),
        text,
    )

    # 3. Links.
    def _link(m: re.Match) -> str:
        display = _escape_plain(m.group(1))
        url = m.group(2).replace('\\', '\\\\').replace(')', '\\)')
        return stash(f'[{display}]({url})')

    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', _link, text)

    # 4. Headers.
    def _header(m: re.Match) -> str:
        inner = m.group(1).strip()
        inner = re.sub(r'\*\*(.+?)\*\*', r'\1', inner)
        return stash(f'*{_escape_plain(inner)}*')

    text = re.sub(r'^#{1,6}\s+(.+)$', _header, text, flags=re.MULTILINE)

    # 5. Bold.
    text = re.sub(
        r'\*\*(.+?)\*\*',
        lambda m: stash(f'*{_escape_plain(m.group(1))}*'),
        text,
    )

    # 6. Italic.
    text = re.sub(
        r'(?<!\*)\*([^*\n]+)\*(?!\*)',
        lambda m: stash(f'_{_escape_plain(m.group(1))}_'),
        text,
    )

    # 7. Escape plain text.
    text = _escape_plain(text)

    # 8. Restore placeholders.
    for key in reversed(list(placeholders.keys())):
        text = text.replace(key, placeholders[key])

    return text


def _escape_plain(text: str) -> str:
    """Escape Telegram MarkdownV2 specials."""
    return _MDV2_SPECIAL_RE.sub(r'\\\1', text)
