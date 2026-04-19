"""Message delivery — outbound sending + allowlist check.

Single source of truth for two things:

- **Who is allowed to talk to alf.** The allowlist lives in
  ``~/.alf/.env``, one env var per platform. Most platforms use the
  natural ``{PLATFORM}_ALLOWED_CHAT_IDS`` shape (Telegram, webhook);
  email uses ``EMAIL_ALLOWED_SENDERS`` because "sender address" is
  the right vocabulary for an email. The gateway listener and the
  ``send_message`` tool share this check — fail-closed when the env
  var is missing or empty.

- **How to actually send a message.** Gateway and tool both deliver
  through ``send_to(platform, chat_id, text)``. Sync call — no
  gateway process required, because "send an outgoing message with
  our own bot token / mailbox creds" adds zero inbound attack
  surface over what a running gateway already exposes.

Split for reuse: ``format_for_telegram`` stays for chunking long
messages to fit Telegram's 4096 char limit.
"""

from __future__ import annotations

import os

import httpx

TELEGRAM_MAX_CHARS = 4096


def _allowlist_env(platform: str) -> str:
    """Env var holding the allowlist for ``platform``.

    Email uses ``EMAIL_ALLOWED_SENDERS`` (sender addresses, not chat
    ids); everything else follows the ``{PLATFORM}_ALLOWED_CHAT_IDS``
    pattern. Central mapping so the setup wizards, the gateway run
    loop, and the tool layer all agree.
    """
    if platform == "email":
        return "EMAIL_ALLOWED_SENDERS"
    return f"{platform.upper()}_ALLOWED_CHAT_IDS"


class DeliveryError(Exception):
    """Raised when a message can't be delivered (permission, unknown platform, HTTP)."""


# ----------------------------------------------------------------------
# Allowlist
# ----------------------------------------------------------------------


def allowed_chat_ids(platform: str) -> list[str]:
    """Return the ordered, de-duplicated allowlist for ``platform``.

    Empty list if the env var is unset/empty. Caller decides what to do
    with an empty allowlist (usually: reject). Email addresses are
    normalised to lowercase so allowlist matching doesn't care about
    the casing a sender happened to use.
    """
    raw = os.environ.get(_allowlist_env(platform), "")
    seen: list[str] = []
    for part in raw.split(","):
        cid = part.strip()
        if platform == "email":
            cid = cid.lower()
        if cid and cid not in seen:
            seen.append(cid)
    return seen


def is_allowed(platform: str, chat_id: str) -> bool:
    """True iff ``chat_id`` is in the platform's allowlist."""
    needle = chat_id.lower() if platform == "email" else chat_id
    return needle in allowed_chat_ids(platform)


def default_chat_id(platform: str) -> str | None:
    """First allowed chat for ``platform`` — useful as a fallback target.

    The schedule daemon and the ``send_message`` tool use this when the
    caller didn't pick a specific chat.
    """
    ids = allowed_chat_ids(platform)
    return ids[0] if ids else None


# ----------------------------------------------------------------------
# Formatting
# ----------------------------------------------------------------------


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


# ----------------------------------------------------------------------
# Outbound send (sync)
# ----------------------------------------------------------------------


def send_to(platform: str, chat_id: str, text: str) -> None:
    """Deliver ``text`` to ``(platform, chat_id)``. Raises ``DeliveryError``.

    Sync API — safe to call from non-async contexts (tools, schedule
    scheduler). The gateway's async ``Platform.send`` uses the same
    underlying HTTP/SMTP call but on top of an async wrapper.
    """
    if not is_allowed(platform, chat_id):
        raise DeliveryError(
            f"chat {chat_id!r} is not in {_allowlist_env(platform)}"
        )
    if not text or not text.strip():
        raise DeliveryError("empty message")

    if platform == "telegram":
        _send_telegram_sync(chat_id, text)
    elif platform == "email":
        _send_email_sync(chat_id, text)
    elif platform == "webhook":
        _send_webhook_sync(chat_id, text)
    else:
        raise DeliveryError(f"unknown platform: {platform}")


def _send_telegram_sync(chat_id: str, text: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        raise DeliveryError("TELEGRAM_BOT_TOKEN not set")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    with httpx.Client(timeout=30) as client:
        for chunk in format_for_telegram(text):
            resp = client.post(url, json={"chat_id": chat_id, "text": chunk})
            if resp.status_code >= 400:
                raise DeliveryError(
                    f"telegram sendMessage failed "
                    f"(status={resp.status_code}): {resp.text[:200]}"
                )


def _send_email_sync(chat_id: str, text: str) -> None:
    """Outbound email via SMTP using the EmailClient shared with the tool.

    ``chat_id`` is the recipient address. Subject is a short ``[alf]``
    prefix — proactive messages don't reply to an existing thread, so
    there's no original subject to echo. For threaded replies the
    ``email`` tool's ``reply`` action is the right path.
    """
    from alf.email.client import EmailClient, EmailError
    try:
        client = EmailClient.from_env()
    except EmailError as e:
        raise DeliveryError(str(e))
    try:
        client.send(to=[chat_id], subject="[alf]", body=text)
    except EmailError as e:
        raise DeliveryError(str(e))


def _send_webhook_sync(chat_id: str, text: str) -> None:
    # Webhook is a stub in v0.1 — the gateway adapter doesn't actually
    # listen yet. We accept the call and POST to a configured URL if set,
    # so scheduled jobs targeting "webhook" at least try something.
    url = os.environ.get("WEBHOOK_POST_URL", "")
    if not url:
        raise DeliveryError("webhook platform has no WEBHOOK_POST_URL configured")
    with httpx.Client(timeout=30) as client:
        resp = client.post(url, json={"chat_id": chat_id, "text": text})
        if resp.status_code >= 400:
            raise DeliveryError(
                f"webhook POST failed (status={resp.status_code}): {resp.text[:200]}"
            )
