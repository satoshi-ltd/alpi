"""Convert agent-emitted Markdown to Telegram MarkdownV2.

The agent writes standard GFM-flavoured Markdown: ``**bold**``, ``*italic*``,
``` `inline code` ```, fenced code blocks, ``[text](url)`` links, ``#``
headers. Telegram's MarkdownV2 uses slightly different syntax (single
asterisk for bold, underscore for italic) AND demands 18 specific
characters be backslash-escaped everywhere they appear literally:
``_ * [ ] ( ) ~ ` > # + - = | { } . !``.

Strategy is a two-pass tokeniser:

1. Pull *protected* regions out of the text into placeholders — fenced
   code blocks, inline code, links. These already carry their own
   escape rules (only ``\\`` and `` ` `` inside code; ``\\`` and ``)``
   inside URLs) and must not be touched by the generic escape pass.
2. Rewrite remaining Markdown (headers, bold, italic) into their
   MarkdownV2 equivalents, stashing each behind a placeholder too.
3. Escape every special character that survived into plain text.
4. Restore placeholders.

Scope intentionally excludes Telegram-native features the agent never
emits: tables, blockquotes, spoilers, strikethrough. Fold them in if
they show up in production transcripts — don't pre-write them.
"""

from __future__ import annotations

import re

_MDV2_SPECIAL_RE = re.compile(r'([_*\[\]()~`>#\+\-=|{}.!\\])')


def to_markdown_v2(src: str) -> str:
    """Return ``src`` rewritten for Telegram's MarkdownV2 parse mode."""
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

    # 1. Fenced code blocks (```lang\n … ```). Escape ``\`` and `` ` ``
    # inside the body — nothing else.
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

    # 2. Inline code `…`. Same escape rules as above (just backslash; a
    # literal backtick inside inline code is impossible because the
    # regex stops at the first `.
    text = re.sub(
        r'`[^`]+`',
        lambda m: stash(m.group(0).replace('\\', '\\\\')),
        text,
    )

    # 3. Links [display](url). Display text goes through the plain
    # escape pass; URL only needs ``\`` and ``)`` escaped.
    def _link(m: re.Match) -> str:
        display = _escape_plain(m.group(1))
        url = m.group(2).replace('\\', '\\\\').replace(')', '\\)')
        return stash(f'[{display}]({url})')

    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', _link, text)

    # 4. Headers (``# Title``). Telegram has no native heading —
    # render as bold and drop the leading hashes.
    def _header(m: re.Match) -> str:
        inner = m.group(1).strip()
        inner = re.sub(r'\*\*(.+?)\*\*', r'\1', inner)
        return stash(f'*{_escape_plain(inner)}*')

    text = re.sub(r'^#{1,6}\s+(.+)$', _header, text, flags=re.MULTILINE)

    # 5. Bold ``**text**`` → ``*text*``. Match double-asterisks; inner
    # content gets the plain escape pass so ``**foo.bar**`` becomes
    # ``*foo\.bar*`` as MarkdownV2 expects.
    text = re.sub(
        r'\*\*(.+?)\*\*',
        lambda m: stash(f'*{_escape_plain(m.group(1))}*'),
        text,
    )

    # 6. Italic ``*text*`` → ``_text_``. Single asterisk only, and
    # refuse to cross newlines — a bullet list that starts with ``* ``
    # would otherwise get mangled. The negative lookarounds keep a
    # stray ``**`` from being re-matched (bold is already consumed).
    text = re.sub(
        r'(?<!\*)\*([^*\n]+)\*(?!\*)',
        lambda m: stash(f'_{_escape_plain(m.group(1))}_'),
        text,
    )

    # 7. Escape what's left of the plain text.
    text = _escape_plain(text)

    # 8. Restore placeholders in reverse so nested stashes resolve.
    for key in reversed(list(placeholders.keys())):
        text = text.replace(key, placeholders[key])

    return text


def _escape_plain(text: str) -> str:
    """Backslash-escape Telegram MarkdownV2 specials in plain text."""
    return _MDV2_SPECIAL_RE.sub(r'\\\1', text)
