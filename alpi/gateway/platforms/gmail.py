"""Gmail platform adapter — inbound poll + outbound send via Gmail REST API.

Uses Google's history API for delta polling (``users.history.list``):
start from the user's current ``historyId`` and ask Google what's new
since, instead of scanning the whole inbox every cycle.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import AsyncIterator

import httpx

from alpi.gateway.base import IncomingMessage, OutgoingMessage, Platform
from alpi.gateway.platforms.imap import _is_automated
from alpi.mail.gmail import GmailClient, GmailError
from alpi.mail.gmail_auth import GmailAuthError, get_access_token, get_email, token_path

log = logging.getLogger("alpi.gateway.gmail")

DEFAULT_POLL_INTERVAL = 60
_HISTORY_URL = "https://gmail.googleapis.com/gmail/v1/users/me/history"
_PROFILE_URL = "https://gmail.googleapis.com/gmail/v1/users/me/profile"


def _state_path(home: Path) -> Path:
    return home / "gateway" / "gmail-state.json"


class Gmail(Platform):
    """Gateway inbound/outbound adapter for a Gmail mailbox via OAuth."""

    name = "gmail"

    def __init__(self, home: Path) -> None:
        super().__init__(home)
        self._poll_interval = DEFAULT_POLL_INTERVAL
        self._mark_as_read = True
        self._reload_config()

    async def listen(self) -> AsyncIterator[IncomingMessage]:
        if not token_path(self.home).exists():
            log.info("Gmail token missing — listener idle.")
            while True:
                await asyncio.sleep(3600)
                if False:  # pragma: no cover
                    yield  # type: ignore[misc]

        log.info("Gmail listener starting (poll every %ss).", self._poll_interval)

        last_history = self._load_last_history()
        if last_history is None:
            try:
                last_history = await asyncio.to_thread(self._baseline_history)
            except (GmailAuthError, GmailError) as e:
                log.warning("Gmail baseline failed: %s", e)
                return
            self._save_last_history(last_history)
            log.info("Gmail baseline historyId: %s", last_history)

        client = GmailClient(self.home)

        while True:
            try:
                events = await asyncio.to_thread(self._list_history, last_history)
            except (GmailAuthError, GmailError) as e:
                log.warning("Gmail poll failed: %s", e)
                events = {"messages": [], "newHistoryId": last_history}
            except Exception as e:  # noqa: BLE001
                log.exception("Gmail poll crashed: %s", e)
                events = {"messages": [], "newHistoryId": last_history}

            new_history = events.get("newHistoryId") or last_history
            for msg_id in events.get("messages") or []:
                try:
                    full = await asyncio.to_thread(client.read, msg_id)
                except GmailError as e:
                    log.debug("Gmail: failed to read %s: %s", msg_id, e)
                    continue

                sender = _clean_addr(full.from_)
                if not sender:
                    continue
                if _is_automated(sender, {"From": full.from_}):
                    log.debug("Gmail: dropping automated/bulk from %s", sender)
                    continue

                prompt = (
                    f"[INBOUND EMAIL from {sender}]\n"
                    f"Subject: {full.subject}\n\n{full.body}"
                )
                ack = None
                if self._mark_as_read:
                    mid_copy = msg_id
                    async def ack() -> None:
                        try:
                            await asyncio.to_thread(client.mark_seen, mid_copy)
                        except GmailError as e:
                            log.debug("Gmail: failed to mark %s seen: %s", mid_copy, e)
                yield IncomingMessage(
                    platform="gmail",
                    external_user_id=sender,
                    external_chat_id=sender,
                    text=prompt,
                    ack=ack,
                )

            if new_history != last_history:
                last_history = new_history
                self._save_last_history(last_history)
            await asyncio.sleep(self._poll_interval)

    async def send(self, message: OutgoingMessage) -> None:
        def _do_send() -> None:
            GmailClient(self.home).send(
                to=[message.external_chat_id],
                subject="[alpi] re:",
                body=message.text,
            )
        try:
            await asyncio.to_thread(_do_send)
        except (GmailAuthError, GmailError) as e:
            log.warning("Gmail send failed: %s", e)

    def _baseline_history(self) -> str:
        token = get_access_token(self.home)
        with httpx.Client(timeout=10.0) as client:
            r = client.get(
                _PROFILE_URL,
                headers={"Authorization": f"Bearer {token}"},
            )
            r.raise_for_status()
        return str(r.json().get("historyId") or "0")

    def _list_history(self, start: str) -> dict:
        token = get_access_token(self.home)
        params = {
            "startHistoryId": start,
            "historyTypes": "messageAdded",
        }
        with httpx.Client(timeout=15.0) as client:
            r = client.get(
                _HISTORY_URL,
                headers={"Authorization": f"Bearer {token}"},
                params=params,
            )
            r.raise_for_status()
            data = r.json()
        msg_ids: list[str] = []
        for h in data.get("history") or []:
            for added in h.get("messagesAdded") or []:
                m = added.get("message") or {}
                labels = set(m.get("labelIds") or [])
                if labels & {"SPAM", "TRASH", "DRAFT", "CHAT", "SENT"}:
                    continue
                mid = m.get("id")
                if mid:
                    msg_ids.append(mid)
        return {
            "messages": msg_ids,
            "newHistoryId": str(data.get("historyId") or start),
        }

    def _load_last_history(self) -> str | None:
        p = _state_path(self.home)
        if not p.exists():
            return None
        try:
            data = json.loads(p.read_text() or "{}")
        except json.JSONDecodeError:
            return None
        addr = (get_email(self.home) or "").lower()
        val = data.get(addr)
        return str(val) if val is not None else None

    def _save_last_history(self, history_id: str) -> None:
        p = _state_path(self.home)
        p.parent.mkdir(parents=True, exist_ok=True)
        try:
            data = json.loads(p.read_text() or "{}") if p.exists() else {}
        except json.JSONDecodeError:
            data = {}
        addr = (get_email(self.home) or "").lower()
        data[addr] = history_id
        tmp = p.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=2))
        tmp.replace(p)

    def _reload_config(self) -> None:
        try:
            from alpi import config as config_mod
            cfg = config_mod.load(self.home)
            gmail_cfg = (cfg.gateway or {}).get("gmail", {})
            self._poll_interval = int(
                gmail_cfg.get("poll_interval", DEFAULT_POLL_INTERVAL)
            )
            self._mark_as_read = bool(gmail_cfg.get("mark_as_read", True))
        except Exception as e:  # noqa: BLE001
            log.warning("gmail: falling back to defaults (%s)", e)


def _clean_addr(raw: str) -> str:
    if not raw:
        return ""
    import email.utils
    _, addr = email.utils.parseaddr(raw)
    return addr.strip().lower()
