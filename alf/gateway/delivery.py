"""Format outgoing messages per platform (Markdown, length limits, etc.)."""

from __future__ import annotations

TELEGRAM_MAX_CHARS = 4096


def format_for_telegram(text: str) -> list[str]:
    """Split long messages into chunks that fit Telegram's limit."""
    if len(text) <= TELEGRAM_MAX_CHARS:
        return [text]
    chunks: list[str] = []
    remaining = text
    while remaining:
        chunks.append(remaining[:TELEGRAM_MAX_CHARS])
        remaining = remaining[TELEGRAM_MAX_CHARS:]
    return chunks
