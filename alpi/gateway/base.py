"""Platform base."""

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
    subject: str = ""
    reply_to: str | None = None
    ack: Callable[[], Awaitable[Any]] | None = field(default=None, repr=False)


@dataclass
class OutgoingMessage:
    external_chat_id: str
    text: str
    attachment: str | None = None
    reply_markup: dict[str, Any] | None = None


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
        """Optional typing signal."""
        return None
