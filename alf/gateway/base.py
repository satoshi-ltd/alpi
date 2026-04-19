"""Platform base — every channel (Telegram, webhook, ...) subclasses this."""

from __future__ import annotations

import abc
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator


@dataclass
class IncomingMessage:
    platform: str
    external_user_id: str
    external_chat_id: str
    text: str
    reply_to: str | None = None


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
