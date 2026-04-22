"""IMAP platform adapter — inbound IMAP poll + outbound SMTP reply."""

from __future__ import annotations

import asyncio
import email as email_lib
import json
import logging
import os
import re
from pathlib import Path
from typing import AsyncIterator

from alpi.mail.imap import ImapClient, ImapError
from alpi.gateway.base import IncomingMessage, OutgoingMessage, Platform

log = logging.getLogger("alpi.gateway.imap")

DEFAULT_POLL_INTERVAL = 60
# Folder alpi listens on. We deliberately don't look in Spam/Junk — the
# provider's DKIM/SPF checks already flagged those. Raising this to
# "All Mail" or similar would open us up to spoofs the provider already
# rejected.
INBOX = "INBOX"

# Noreply / auto / bounce / list-serv patterns. Matched against the
# sender address (lowercased, local-part included) as a substring —
# cheap and catches the common cases.
_NOREPLY_PATTERNS = (
    "noreply", "no-reply", "no_reply", "donotreply", "do-not-reply",
    "mailer-daemon", "postmaster", "bounce", "notifications@",
    "automated@", "auto-confirm", "auto-reply", "automailer",
)

# Headers that indicate bulk / automated mail. Any of these → skip.
_AUTOMATED_HEADERS = {
    "Auto-Submitted": lambda v: v.lower() != "no",
    "Precedence": lambda v: v.lower() in ("bulk", "list", "junk"),
    "X-Auto-Response-Suppress": lambda v: bool(v),
    "List-Unsubscribe": lambda v: bool(v),
}


def _state_path(home: Path) -> Path:
    return home / "gateway" / "imap-state.json"


class Imap(Platform):
    """Gateway inbound/outbound adapter for an IMAP+SMTP mailbox."""

    name = "email"

    def __init__(self, home: Path) -> None:
        super().__init__(home)
        self._poll_interval = DEFAULT_POLL_INTERVAL
        self._mark_as_read = True
        self._reload_config()

    # Listen — async IMAP poll driven by the gateway event loop

    async def listen(self) -> AsyncIterator[IncomingMessage]:
        required = ("IMAP_ADDRESS", "IMAP_PASSWORD", "IMAP_HOST", "SMTP_HOST")
        if not all(os.environ.get(v) for v in required):
            log.info("IMAP env incomplete — listener idle.")
            while True:
                await asyncio.sleep(3600)
                if False:  # pragma: no cover
                    yield  # type: ignore[misc]

        log.info("IMAP listener starting (poll every %ss).", self._poll_interval)

        last_uid = self._load_last_uid()
        if last_uid is None:
            try:
                last_uid = await asyncio.to_thread(self._discover_baseline_uid)
            except ImapError as e:
                log.warning("IMAP baseline failed: %s — listener idle.", e)
                while True:
                    await asyncio.sleep(3600)
                    if False:  # pragma: no cover
                        yield  # type: ignore[misc]
            self._save_last_uid(last_uid)
            log.info("IMAP baseline UID: %s (no backfill)", last_uid)

        while True:
            try:
                new_msgs = await asyncio.to_thread(
                    self._poll_once, last_uid,
                )
            except ImapError as e:
                log.warning("email poll failed: %s", e)
                new_msgs = []
            except Exception as e:  # noqa: BLE001
                log.exception("email poll crashed: %s", e)
                new_msgs = []

            for raw_uid, msg_obj in new_msgs:
                # Track max UID regardless of whether we surface it —
                # otherwise a noreply-filter chain re-processes the
                # same skipped message forever.
                try:
                    uid_int = int(raw_uid)
                except ValueError:
                    uid_int = last_uid
                if uid_int > last_uid:
                    last_uid = uid_int
                    self._save_last_uid(last_uid)

                sender, subject, body, headers = _extract(msg_obj)
                if _is_automated(sender, headers):
                    log.debug("email: dropping automated/bulk from %s", sender)
                    continue

                prompt = (
                    f"[INBOUND EMAIL from {sender}]\n"
                    f"Subject: {subject}\n\n{body}"
                )
                ack = None
                if self._mark_as_read:
                    uid_copy = raw_uid
                    async def ack() -> None:
                        try:
                            await asyncio.to_thread(self._mark_seen, uid_copy)
                        except ImapError as e:
                            log.debug("email mark-seen failed for %s: %s", uid_copy, e)
                yield IncomingMessage(
                    platform="email",
                    external_user_id=sender,
                    external_chat_id=sender,
                    text=prompt,
                    ack=ack,
                )

            await asyncio.sleep(self._poll_interval)

    # Send — used by the gateway to reply to the sender

    async def send(self, message: OutgoingMessage) -> None:
        def _do_send() -> None:
            client = ImapClient.from_env()
            client.send(
                to=[message.external_chat_id],
                subject="[alpi] re:",
                body=message.text,
            )
        try:
            await asyncio.to_thread(_do_send)
        except ImapError as e:
            log.warning("email send failed: %s", e)

    # Sync IMAP helpers (run under asyncio.to_thread to avoid blocking)

    def _discover_baseline_uid(self) -> int:
        client = ImapClient.from_env()
        with client._imap() as imap:
            client._select(imap, INBOX)
            uids = client._uid_search(imap, ["ALL"])
            return int(uids[-1]) if uids else 0

    def _poll_once(self, since_uid: int) -> list[tuple[str, object]]:
        client = ImapClient.from_env()
        results: list[tuple[str, object]] = []
        with client._imap() as imap:
            client._select(imap, INBOX)
            uids = client._uid_search(imap, ["UID", f"{since_uid + 1}:*"])
            for uid in uids:
                if int(uid) <= since_uid:
                    # IMAP UID range is inclusive, and `:*` returns the
                    # latest message even if nothing qualifies — filter.
                    continue
                typ, data = imap.uid("FETCH", uid, "(BODY.PEEK[])")
                if typ != "OK" or not data or not isinstance(data[0], tuple):
                    continue
                raw = data[0][1]
                if not isinstance(raw, bytes):
                    continue
                msg = email_lib.message_from_bytes(
                    raw, policy=email_lib.policy.default,
                )
                results.append((uid, msg))
        return results

    def _mark_seen(self, uid: str) -> None:
        client = ImapClient.from_env()
        with client._imap() as imap:
            client._select(imap, INBOX)
            typ, _ = imap.uid("STORE", uid, "+FLAGS", r"(\Seen)")
            if typ != "OK":
                raise ImapError(f"could not mark UID {uid} seen")

    def _load_last_uid(self) -> int | None:
        p = _state_path(self.home)
        if not p.exists():
            return None
        try:
            data = json.loads(p.read_text() or "{}")
        except json.JSONDecodeError:
            return None
        addr = os.environ.get("IMAP_ADDRESS", "").lower()
        val = data.get(addr)
        try:
            return int(val) if val is not None else None
        except (TypeError, ValueError):
            return None

    def _save_last_uid(self, uid: int) -> None:
        p = _state_path(self.home)
        p.parent.mkdir(parents=True, exist_ok=True)
        try:
            data = json.loads(p.read_text() or "{}") if p.exists() else {}
        except json.JSONDecodeError:
            data = {}
        addr = os.environ.get("IMAP_ADDRESS", "").lower()
        data[addr] = uid
        tmp = p.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=2))
        tmp.replace(p)

    def _reload_config(self) -> None:
        try:
            from alpi import config as config_mod
            cfg = config_mod.load(self.home)
            email_cfg = (cfg.gateway or {}).get("imap", {})
            self._poll_interval = int(
                email_cfg.get("poll_interval", DEFAULT_POLL_INTERVAL)
            )
            self._mark_as_read = bool(email_cfg.get("mark_as_read", True))
        except Exception as e:  # noqa: BLE001
            log.warning("email: falling back to defaults (%s)", e)


# Parsing + anti-bulk helpers


def _extract(msg: object) -> tuple[str, str, str, dict[str, str]]:
    sender = _clean_addr(getattr(msg, "__getitem__", lambda k: "")("From") or "")
    subject = _decode(getattr(msg, "__getitem__", lambda k: "")("Subject") or "")
    headers = {k: v for k, v in getattr(msg, "items", list)()}
    body = _pick_body(msg)
    return sender, subject, body, headers


def _decode(raw: str) -> str:
    if not raw:
        return ""
    try:
        parts = email_lib.header.decode_header(raw)
    except Exception:  # noqa: BLE001
        return raw
    out: list[str] = []
    for chunk, enc in parts:
        if isinstance(chunk, bytes):
            try:
                out.append(chunk.decode(enc or "utf-8", errors="replace"))
            except LookupError:
                out.append(chunk.decode("utf-8", errors="replace"))
        else:
            out.append(chunk)
    return "".join(out).strip()


def _clean_addr(raw: str) -> str:
    if not raw:
        return ""
    _, addr = email_lib.utils.parseaddr(_decode(raw))
    return addr.strip().lower()


_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _pick_body(msg: object) -> str:
    plain = getattr(msg, "get_body", lambda **kw: None)(preferencelist=("plain",))
    if plain is not None:
        try:
            return plain.get_content().strip()
        except Exception:  # noqa: BLE001
            pass
    html = getattr(msg, "get_body", lambda **kw: None)(preferencelist=("html",))
    if html is not None:
        try:
            return _HTML_TAG_RE.sub("", html.get_content()).strip()
        except Exception:  # noqa: BLE001
            pass
    return ""


def _is_automated(sender: str, headers: dict[str, str]) -> bool:
    addr = (sender or "").lower()
    if any(p in addr for p in _NOREPLY_PATTERNS):
        return True
    for header, check in _AUTOMATED_HEADERS.items():
        value = headers.get(header, "")
        if value and check(value):
            return True
    return False
