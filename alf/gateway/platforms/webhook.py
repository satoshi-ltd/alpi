"""Generic webhook adapter (skeleton)."""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator

from alf.gateway.base import IncomingMessage, OutgoingMessage, Platform

log = logging.getLogger("alf.gateway.webhook")


class Webhook(Platform):
    name = "webhook"

    async def listen(self) -> AsyncIterator[IncomingMessage]:
        log.info("Webhook listener stub (v0.1 will start the FastAPI server).")
        while True:
            await asyncio.sleep(3600)
            if False:  # pragma: no cover
                yield  # type: ignore[misc]

    async def send(self, message: OutgoingMessage) -> None:
        log.info("→ webhook[%s]: %s", message.external_chat_id, message.text[:80])
