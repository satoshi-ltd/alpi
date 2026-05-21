"""Matrix adapter (no-E2EE MVP) — sync loop against any homeserver."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import AsyncIterator

from alpi.gateway import breaker as _breaker
from alpi.gateway.base import IncomingMessage, OutgoingMessage, Platform
from alpi.gateway.delivery import allowed_chat_ids

log = logging.getLogger("alpi.gateway.matrix")


def _state_path(home: Path) -> Path:
    return home / "gateway" / "matrix-state.json"


def _allowed_senders(env: dict[str, str]) -> list[str]:
    raw = env.get("MATRIX_ALLOWED_SENDERS", "")
    return [s.strip() for s in raw.split(",") if s.strip()]


class Matrix(Platform):
    name = "matrix"

    def __init__(self, home: Path) -> None:
        super().__init__(home)
        self._next_batch = self._load_cursor()
        self._client = None

    def _load_cursor(self) -> str | None:
        p = _state_path(self.home)
        if not p.exists():
            return None
        try:
            return (json.loads(p.read_text()) or {}).get("next_batch")
        except (json.JSONDecodeError, ValueError, TypeError):
            return None

    def _save_cursor(self, token: str) -> None:
        p = _state_path(self.home)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".json.tmp")
        tmp.write_text(json.dumps({"next_batch": token}))
        tmp.replace(p)
        self._next_batch = token

    def _build_client(self):
        from nio import AsyncClient
        homeserver = self.env["MATRIX_HOMESERVER_URL"]
        user_id = self.env["MATRIX_USER_ID"]
        token = self.env["MATRIX_ACCESS_TOKEN"]
        device_id = self.env.get("MATRIX_DEVICE_ID", "")
        client = AsyncClient(homeserver, user_id)
        client.access_token = token
        client.user_id = user_id
        if device_id:
            client.device_id = device_id
        return client

    async def listen(self) -> AsyncIterator[IncomingMessage]:
        if not all(self.env.get(k) for k in (
            "MATRIX_HOMESERVER_URL", "MATRIX_USER_ID", "MATRIX_ACCESS_TOKEN",
        )):
            log.info("MATRIX credentials not set — matrix listener idle.")
            while True:
                await asyncio.sleep(3600)
                if False:  # pragma: no cover
                    yield  # type: ignore[misc]

        try:
            from nio import RoomMessageText
        except ImportError:
            log.warning("matrix-nio not installed — `pip install matrix-nio`. Listener idle.")
            while True:
                await asyncio.sleep(3600)
                if False:  # pragma: no cover
                    yield  # type: ignore[misc]

        self._client = self._build_client()
        log.info("Matrix listener starting (sync, since=%s).", self._next_batch or "<fresh>")

        allowed_rooms = set(allowed_chat_ids("matrix", env=self.env))
        allowed_senders = set(_allowed_senders(self.env))
        own_user = self._client.user_id

        first_sync = True
        breaker = _breaker.for_home(self.home)
        while True:
            if breaker.should_skip("matrix"):
                await asyncio.sleep(30)
                continue
            try:
                resp = await self._client.sync(timeout=30000, since=self._next_batch)
            except Exception as e:  # noqa: BLE001
                log.warning("matrix sync failed: %s", e)
                prev, curr = breaker.record_failure("matrix", str(e))
                if prev != curr:
                    st = breaker.state_of("matrix")
                    _breaker.emit_state_event(
                        self.home, "matrix", prev, curr,
                        reason=str(e), disabled_until=st.disabled_until,
                    )
                await asyncio.sleep(5)
                continue

            new_token = getattr(resp, "next_batch", None)
            if not new_token:
                err = getattr(resp, "message", str(resp))
                log.warning("matrix sync returned no next_batch: %s", err)
                prev, curr = breaker.record_failure("matrix", err[:200])
                if prev != curr:
                    st = breaker.state_of("matrix")
                    _breaker.emit_state_event(
                        self.home, "matrix", prev, curr,
                        reason=err[:200], disabled_until=st.disabled_until,
                    )
                await asyncio.sleep(5)
                continue

            prev, curr = breaker.record_success("matrix")
            if prev != curr:
                _breaker.emit_state_event(self.home, "matrix", prev, curr)

            # First sync after a fresh start: skip backlog (we don't replay
            # history). Save the cursor and continue.
            if self._next_batch is None and first_sync:
                self._save_cursor(new_token)
                first_sync = False
                continue
            first_sync = False

            joined = getattr(resp.rooms, "join", {}) or {}
            for room_id, room in joined.items():
                if allowed_rooms and room_id not in allowed_rooms:
                    continue
                for ev in (room.timeline.events or []):
                    if not isinstance(ev, RoomMessageText):
                        continue
                    if ev.sender == own_user:
                        continue
                    if allowed_senders and ev.sender not in allowed_senders:
                        log.info("matrix: ignored msg from non-allowed sender %s in %s",
                                 ev.sender, room_id)
                        continue
                    yield IncomingMessage(
                        platform="matrix",
                        external_user_id=ev.sender,
                        external_chat_id=room_id,
                        text=ev.body or "",
                        reply_to=ev.event_id,
                    )

            self._save_cursor(new_token)

    async def send(self, message: OutgoingMessage) -> None:
        if self._client is None:
            self._client = self._build_client()
        await self._client.room_send(
            room_id=message.external_chat_id,
            message_type="m.room.message",
            content={"msgtype": "m.text", "body": message.text},
        )

    async def send_typing(self, chat_id: str) -> None:
        if self._client is None:
            return
        try:
            await self._client.room_typing(chat_id, typing_state=True, timeout=5000)
        except Exception:  # noqa: BLE001
            pass
