"""Telegram adapter — long-poll via getUpdates."""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import AsyncIterator

import httpx

from alpi.gateway.base import IncomingMessage, OutgoingMessage, Platform
from alpi.gateway.delivery import format_for_telegram

log = logging.getLogger("alf.gateway.telegram")

API_BASE = "https://api.telegram.org/bot{token}"
FILE_BASE = "https://api.telegram.org/file/bot{token}"


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
                    user_id = str(sender.get("id", ""))

                    text = msg.get("text") or ""
                    voice = msg.get("voice") or msg.get("audio")
                    if not text and voice:
                        text = await _transcribe_voice(
                            client, token, self.home, voice,
                        )
                        if not text:
                            continue
                        text = f"[voice note] {text}"
                    if not text:
                        continue

                    prompt = f"[INBOUND TELEGRAM from {user_id}]\n{text}"
                    yield IncomingMessage(
                        platform="telegram",
                        external_user_id=user_id,
                        external_chat_id=str(chat.get("id", "")),
                        text=prompt,
                    )

    async def send_typing(self, chat_id: str) -> None:
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        if not token:
            return
        url = API_BASE.format(token=token) + "/sendChatAction"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(url, json={"chat_id": chat_id, "action": "typing"})
        except Exception as e:  # noqa: BLE001
            log.debug("sendChatAction failed: %s", e)

    async def send(self, message: OutgoingMessage) -> None:
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        if not token:
            return
        base = API_BASE.format(token=token)

        async with httpx.AsyncClient(timeout=60) as client:
            if message.attachment:
                await _send_attachment(
                    client, base, message.external_chat_id,
                    message.attachment, caption=message.text,
                )
                return
            url = base + "/sendMessage"
            for chunk in format_for_telegram(message.text):
                try:
                    await client.post(url, json={
                        "chat_id": message.external_chat_id,
                        "text": chunk,
                    })
                except Exception as e:  # noqa: BLE001
                    log.warning("sendMessage failed: %s", e)


async def _send_attachment(
    client: httpx.AsyncClient, base: str, chat_id: str,
    path: str, caption: str,
) -> None:
    from pathlib import Path as _Path
    p = _Path(path).expanduser()
    if not p.exists() or not p.is_file():
        log.warning("attachment not found: %s", path)
        return

    ext = p.suffix.lower()
    if ext in (".ogg", ".oga", ".opus"):
        endpoint, field = "/sendVoice", "voice"
    elif ext in (".mp3", ".m4a", ".wav", ".flac", ".aac"):
        endpoint, field = "/sendAudio", "audio"
    elif ext in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
        endpoint, field = "/sendPhoto", "photo"
    elif ext in (".mp4", ".mov", ".mkv"):
        endpoint, field = "/sendVideo", "video"
    else:
        endpoint, field = "/sendDocument", "document"

    data: dict[str, str] = {"chat_id": chat_id}
    if caption:
        data["caption"] = caption[:1024]

    try:
        with p.open("rb") as fh:
            files = {field: (p.name, fh)}
            resp = await client.post(base + endpoint, data=data, files=files)
        if resp.status_code >= 400:
            log.warning(
                "telegram %s failed (%s): %s",
                endpoint, resp.status_code, resp.text[:200],
            )
    except Exception as e:  # noqa: BLE001
        log.warning("telegram %s crashed: %s", endpoint, e)


async def _transcribe_voice(
    client: httpx.AsyncClient, token: str, home: Path, voice: dict,
) -> str:
    file_id = voice.get("file_id")
    if not file_id:
        return ""
    try:
        resp = await client.get(
            API_BASE.format(token=token) + "/getFile",
            params={"file_id": file_id},
        )
        data = resp.json()
    except Exception as e:  # noqa: BLE001
        log.warning("getFile failed: %s", e)
        return ""
    if not data.get("ok"):
        log.warning("getFile returned not-ok: %s", data)
        return ""
    file_path = (data.get("result") or {}).get("file_path") or ""
    if not file_path:
        return ""

    try:
        dl = await client.get(
            f"{FILE_BASE.format(token=token)}/{file_path}",
            timeout=60,
        )
        if dl.status_code != 200:
            log.warning("voice download failed (%s)", dl.status_code)
            return ""
        body = dl.content
    except Exception as e:  # noqa: BLE001
        log.warning("voice download crashed: %s", e)
        return ""

    cache = home / "cache" / "inbound"
    cache.mkdir(parents=True, exist_ok=True)
    suffix = Path(file_path).suffix or ".oga"
    dest = cache / f"{file_id}{suffix}"
    dest.write_bytes(body)

    from alpi.tools.stt import Stt
    result = await asyncio.to_thread(Stt().run, path=str(dest))
    if not result.ok:
        log.warning("stt failed on %s: %s", dest, result.error)
        return ""
    text = result.output
    if text.startswith("[lang="):
        _, _, rest = text.partition("\n")
        text = rest
    return text.strip()
