"""Platform base — every channel (Telegram, webhook, ...) subclasses this."""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator, Awaitable, Callable


@dataclass
class IncomingMessage:
    platform: str
    external_user_id: str
    external_chat_id: str
    text: str
    reply_to: str | None = None
    # Optional per-platform commit hook. Called *after* allowlist passes
    # and before agent dispatch — used by mail platforms to mark \Seen /
    # remove UNREAD only on messages we actually own. Never called for
    # disallowed senders so we don't touch unrelated inbox traffic.
    ack: Callable[[], Awaitable[Any]] | None = field(default=None, repr=False)


@dataclass
class OutgoingMessage:
    external_chat_id: str
    text: str


class Platform(abc.ABC):
    """Abstract channel adapter.

    ``listen()`` yields incoming messages forever.
    ``send()`` delivers an outgoing message.
    """

    name: str

    def __init__(self, home: Path):
        self.home = home

    @abc.abstractmethod
    async def listen(self) -> AsyncIterator[IncomingMessage]: ...

    @abc.abstractmethod
    async def send(self, message: OutgoingMessage) -> None: ...

    async def send_typing(self, chat_id: str) -> None:
        """Optional: signal that the agent is working."""
        return None
