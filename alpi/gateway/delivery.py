"""Message delivery."""

from __future__ import annotations

import os

import httpx

TELEGRAM_MAX_CHARS = 4096


def _allowlist_env(platform: str) -> str:
    if platform == "email":
        return "IMAP_ALLOWED_SENDERS"
    if platform == "gmail":
        return "GMAIL_ALLOWED_SENDERS"
    return f"{platform.upper()}_ALLOWED_CHAT_IDS"


class DeliveryError(Exception):
    """Raised when delivery fails."""



def allowed_chat_ids(platform: str, env: dict | None = None) -> list[str]:
    """Return the ordered, de-duplicated allowlist for ``platform``."""
    src = env if env is not None else os.environ
    raw = src.get(_allowlist_env(platform), "")
    seen: list[str] = []
    for part in raw.split(","):
        cid = part.strip()
        if platform in ("email", "gmail"):
            cid = cid.lower()
        if cid and cid not in seen:
            seen.append(cid)
    return seen


def is_allowed(platform: str, chat_id: str, env: dict | None = None) -> bool:
    """True iff ``chat_id`` is in the platform's allowlist."""
    needle = chat_id.lower() if platform in ("email", "gmail") else chat_id
    return needle in allowed_chat_ids(platform, env)


def default_chat_id(platform: str, env: dict | None = None) -> str | None:
    """First allowed chat for ``platform``."""
    ids = allowed_chat_ids(platform, env)
    return ids[0] if ids else None



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


# Outbound send (sync)


def send_to(
    platform: str, chat_id: str, text: str,
    attachment: str | None = None,
    env: dict | None = None,
) -> None:
    """Deliver text, optionally with an attachment."""
    if not is_allowed(platform, chat_id, env):
        raise DeliveryError(
            f"chat {chat_id!r} is not in {_allowlist_env(platform)}"
        )
    if not attachment and (not text or not text.strip()):
        raise DeliveryError("empty message")

    if platform == "telegram":
        _send_telegram_sync(chat_id, text, attachment=attachment, env=env)
    elif platform == "email":
        if attachment:
            raise DeliveryError("attachment on email not supported via send_message; use the `email` tool")
        _send_email_sync(chat_id, text, env=env)
    elif platform == "gmail":
        if attachment:
            raise DeliveryError("attachment on gmail not supported via send_message; use the `email` tool")
        _send_gmail_sync(chat_id, text)
    elif platform == "webhook":
        if attachment:
            raise DeliveryError("attachment not supported on webhook")
        _send_webhook_sync(chat_id, text, env=env)
    else:
        raise DeliveryError(f"unknown platform: {platform}")


def _send_telegram_sync(
    chat_id: str, text: str, attachment: str | None = None,
    env: dict | None = None,
) -> None:
    src = env if env is not None else os.environ
    token = src.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        raise DeliveryError("TELEGRAM_BOT_TOKEN not set")
    base = f"https://api.telegram.org/bot{token}"

    with httpx.Client(timeout=60) as client:
        if attachment:
            from pathlib import Path as _Path
            p = _Path(attachment).expanduser()
            if not p.exists() or not p.is_file():
                raise DeliveryError(f"attachment not found: {attachment}")
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
            if text:
                data["caption"] = text[:1024]
            with p.open("rb") as fh:
                files = {field: (p.name, fh)}
                resp = client.post(base + endpoint, data=data, files=files)
            if resp.status_code >= 400:
                raise DeliveryError(
                    f"telegram {endpoint} failed "
                    f"(status={resp.status_code}): {resp.text[:200]}"
                )
            return
        url = base + "/sendMessage"
        for chunk in format_for_telegram(text):
            resp = client.post(url, json={"chat_id": chat_id, "text": chunk})
            if resp.status_code >= 400:
                raise DeliveryError(
                    f"telegram sendMessage failed "
                    f"(status={resp.status_code}): {resp.text[:200]}"
                )


def _send_email_sync(chat_id: str, text: str, env: dict | None = None) -> None:
    from alpi.mail.imap import ImapClient, ImapError
    try:
        client = (
            ImapClient.from_env_map(env)
            if env is not None
            else ImapClient.from_env()
        )
    except ImapError as e:
        raise DeliveryError(str(e))
    try:
        client.send(to=[chat_id], subject="[alpi]", body=text)
    except ImapError as e:
        raise DeliveryError(str(e))


def _send_gmail_sync(chat_id: str, text: str) -> None:
    from alpi.home import get_home
    from alpi.mail.gmail import GmailClient, GmailError
    try:
        GmailClient(get_home()).send(to=[chat_id], subject="[alpi]", body=text)
    except GmailError as e:
        raise DeliveryError(str(e))


def _send_webhook_sync(chat_id: str, text: str, env: dict | None = None) -> None:
    # Webhook is still a stub; POST to a configured URL if present.
    src = env if env is not None else os.environ
    url = src.get("WEBHOOK_POST_URL", "")
    if not url:
        raise DeliveryError("webhook platform has no WEBHOOK_POST_URL configured")
    with httpx.Client(timeout=30) as client:
        resp = client.post(url, json={"chat_id": chat_id, "text": text})
        if resp.status_code >= 400:
            raise DeliveryError(
                f"webhook POST failed (status={resp.status_code}): {resp.text[:200]}"
            )
