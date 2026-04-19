"""Telegram adapter — long-poll via getUpdates."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import AsyncIterator

import httpx

from alf.gateway.base import IncomingMessage, OutgoingMessage, Platform
from alf.gateway.delivery import format_for_telegram

log = logging.getLogger("alf.gateway.telegram")

API_BASE = "https://api.telegram.org/bot{token}"


class Telegram(Platform):
    name = "telegram"

    def __init__(self, home) -> None:
        super().__init__(home)
        self._offset = 0

    async def listen(self) -> AsyncIterator[IncomingMessage]:
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        if not token:
            log.info("TELEGRAM_BOT_TOKEN not set — telegram listener idle.")
            while True:
                await asyncio.sleep(3600)
                if False:  # pragma: no cover
                    yield  # type: ignore[misc]

        url_base = API_BASE.format(token=token)
        log.info("Telegram listener starting (long-poll).")

        async with httpx.AsyncClient(timeout=60) as client:
            while True:
                try:
                    resp = await client.get(
                        f"{url_base}/getUpdates",
                        params={"offset": self._offset, "timeout": 30},
                    )
                    resp.raise_for_status()
                    data = resp.json()
                except Exception as e:  # noqa: BLE001
                    log.warning("getUpdates failed: %s", e)
                    await asyncio.sleep(5)
                    continue

                for update in data.get("result", []):
                    self._offset = update["update_id"] + 1
                    msg = update.get("message") or update.get("edited_message")
                    if not msg:
                        continue
                    chat = msg.get("chat") or {}
                    sender = msg.get("from") or {}
                    text = msg.get("text") or ""
                    if not text:
                        continue
                    yield IncomingMessage(
                        platform="telegram",
                        external_user_id=str(sender.get("id", "")),
                        external_chat_id=str(chat.get("id", "")),
                        text=text,
                    )

    async def send(self, message: OutgoingMessage) -> None:
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        if not token:
            return
        url = API_BASE.format(token=token) + "/sendMessage"
        async with httpx.AsyncClient(timeout=30) as client:
            for chunk in format_for_telegram(message.text):
                try:
                    await client.post(url, json={
                        "chat_id": message.external_chat_id,
                        "text": chunk,
                    })
                except Exception as e:  # noqa: BLE001
                    log.warning("sendMessage failed: %s", e)
