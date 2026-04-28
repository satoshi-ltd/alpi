"""Gmail REST client — paridad IMAP via gmail.googleapis.com.

Implements the same 9 operations the ``ImapClient`` exposes, so the
agent-facing ``email`` tool works identically regardless of backend.

Gmail concepts mapped:
  - IMAP folder → Gmail label. ``INBOX``/``SENT``/``TRASH``/``SPAM``
    are system labels (always present). Custom folder names are
    resolved to label IDs on demand.
  - IMAP UID → Gmail message ID (``18f2a9b4d5e6f7a8`` hex). Both
    are opaque strings from the tool's POV.
  - ``move(dest_folder)`` = add dest label + remove source label.
    ``move(dest_folder="ARCHIVE")`` = just remove INBOX (Gmail's
    archive semantics).
"""

from __future__ import annotations

import base64
import email.utils
import html
import re
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any

import httpx

from alpi.mail.gmail_auth import GmailAuthError, get_access_token
from alpi.mail.imap import EmailEnvelope, EmailMessageFull, MAX_BODY_CHARS

_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"
_UPLOAD_BASE = "https://gmail.googleapis.com/upload/gmail/v1/users/me"


class GmailError(Exception):
    pass


_SYSTEM_LABELS = {
    "INBOX", "SENT", "DRAFT", "SPAM", "TRASH", "STARRED",
    "IMPORTANT", "UNREAD",
}


class GmailClient:
    """Mirrors ``ImapClient``'s surface against the Gmail REST API."""

    def __init__(self, home: Path) -> None:
        self.home = home
        self._label_cache: dict[str, str] | None = None

    @classmethod
    def from_home(cls, home: Path) -> "GmailClient":
        return cls(home)

    def _token(self) -> str:
        try:
            return get_access_token(self.home)
        except GmailAuthError as e:
            raise GmailError(str(e)) from None

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token()}"}

    def _get(self, path: str, **params: Any) -> dict:
        with httpx.Client(timeout=15.0) as client:
            r = client.get(f"{_BASE}/{path}", headers=self._headers(), params=params)
        return _check(r)

    def _post(self, path: str, *, json: dict | None = None,
              base: str = _BASE) -> dict:
        with httpx.Client(timeout=30.0) as client:
            r = client.post(f"{base}/{path}", headers=self._headers(), json=json)
        return _check(r)

    def test(self) -> None:
        """Verify auth works. Raises on failure."""
        self._get("profile")

    def list(self, folder: str = "INBOX", limit: int = 20,
             unread_only: bool = False) -> list[EmailEnvelope]:
        q = f"label:{_label_token(folder)}"
        if unread_only:
            q += " is:unread"
        return self._search_envelopes(q, limit, folder)

    def search(self, folder: str = "INBOX", limit: int = 20,
               unread_only: bool = False, from_: str = "", to: str = "",
               subject: str = "", body: str = "",
               since: str = "") -> list[EmailEnvelope]:
        parts = []
        if folder:
            parts.append(f"label:{_label_token(folder)}")
        if unread_only:
            parts.append("is:unread")
        if from_:
            parts.append(f'from:"{from_}"')
        if to:
            parts.append(f'to:"{to}"')
        if subject:
            parts.append(f'subject:"{subject}"')
        if body:
            parts.append(f'"{body}"')
        if since:
            parts.append(f"after:{_gmail_date(since)}")
        q = " ".join(parts) or "in:anywhere"
        return self._search_envelopes(q, limit, folder)

    def _search_envelopes(self, q: str, limit: int,
                          folder: str) -> list[EmailEnvelope]:
        resp = self._get("messages", q=q, maxResults=limit)
        out: list[EmailEnvelope] = []
        for m in resp.get("messages") or []:
            meta = self._get(
                f"messages/{m['id']}", format="metadata",
                metadataHeaders=["From", "To", "Subject", "Date"],
            )
            out.append(_envelope(meta, folder))
        return out

    def read(self, uid: str, folder: str = "INBOX") -> EmailMessageFull:
        msg = self._get(f"messages/{uid}", format="full")
        h = _headers_map(msg)
        if "multipart/encrypted" in h.get("content-type", "").lower():
            raw_msg = self._get(f"messages/{uid}", format="raw")
            raw = base64.urlsafe_b64decode(raw_msg.get("raw", ""))
            em = email.message_from_bytes(raw, policy=email.policy.default)
            from alpi.mail import pgp
            from alpi.mail.imap import _parse_full
            return _parse_full(pgp.maybe_decrypt(em), uid, folder)
        return _message_full(msg, folder)

    def send(self, to: list[str], subject: str, body: str,
             cc: list[str] | None = None,
             attachments: list[str] | None = None) -> None:
        mime = _build_mime(to, subject, body, cc or [], attachments or [])
        from alpi.mail import pgp
        mime = pgp.maybe_sign_and_encrypt(mime)
        raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()
        self._post("messages/send", json={"raw": raw})

    def reply(self, uid: str, body: str, reply_all: bool = False,
              attachments: list[str] | None = None,
              folder: str = "INBOX") -> None:
        meta = self._get(
            f"messages/{uid}", format="metadata",
            metadataHeaders=["From", "To", "Cc", "Subject", "Message-Id"],
        )
        headers = _headers_map(meta)
        reply_to = headers.get("from", "")
        if not reply_to:
            raise GmailError(f"cannot reply: original message {uid} has no From")
        cc_list: list[str] = []
        if reply_all:
            cc_list = _parse_addresses(headers.get("cc", ""))
        subj = headers.get("subject", "")
        if not subj.lower().startswith("re:"):
            subj = f"Re: {subj}"
        mime = _build_mime(
            [reply_to], subj, body, cc_list, attachments or [],
        )
        msg_id = headers.get("message-id", "")
        if msg_id:
            mime["In-Reply-To"] = msg_id
            mime["References"] = msg_id
        raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()
        self._post("messages/send", json={
            "raw": raw, "threadId": meta.get("threadId", ""),
        })

    def forward(self, uid: str, to: list[str], body: str = "",
                attachments: list[str] | None = None,
                folder: str = "INBOX") -> None:
        orig = self.read(uid, folder)
        preface = body.strip() + "\n\n" if body else ""
        forwarded = (
            f"{preface}---------- Forwarded message ---------\n"
            f"From: {orig.from_}\n"
            f"Date: {orig.date.isoformat() if orig.date else ''}\n"
            f"Subject: {orig.subject}\n"
            f"To: {', '.join(orig.to)}\n\n{orig.body}"
        )
        subj = orig.subject if orig.subject.lower().startswith("fwd:") else f"Fwd: {orig.subject}"
        mime = _build_mime(to, subj, forwarded, [], attachments or [])
        raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()
        self._post("messages/send", json={"raw": raw})

    def move(self, uid: str, dest_folder: str,
             folder: str = "INBOX") -> None:
        add_labels: list[str] = []
        remove_labels: list[str] = [_label_id(self, folder)]
        dest = dest_folder.upper()
        if dest in ("ARCHIVE", "ARCHIVED", ""):
            pass
        else:
            add_labels.append(_label_id(self, dest_folder))
        self._post(
            f"messages/{uid}/modify",
            json={
                "addLabelIds": add_labels,
                "removeLabelIds": remove_labels,
            },
        )

    def delete(self, uid: str, folder: str = "INBOX") -> None:
        self._post(f"messages/{uid}/trash")

    def download_attachment(self, uid: str, attachment_name: str,
                            dest_path: Path, folder: str = "INBOX") -> int:
        msg = self._get(f"messages/{uid}", format="full")
        part = _find_attachment(msg.get("payload", {}), attachment_name)
        if part is None:
            raise GmailError(f"attachment not found: {attachment_name!r}")
        body = part.get("body", {})
        if "data" in body:
            raw = base64.urlsafe_b64decode(_pad(body["data"]))
        else:
            att_id = body.get("attachmentId")
            if not att_id:
                raise GmailError(f"attachment has no data: {attachment_name!r}")
            resp = self._get(f"messages/{uid}/attachments/{att_id}")
            raw = base64.urlsafe_b64decode(_pad(resp["data"]))
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_bytes(raw)
        return len(raw)

    def mark_seen(self, uid: str) -> None:
        """Remove the UNREAD label (Gmail equivalent of IMAP \\Seen)."""
        self._post(
            f"messages/{uid}/modify",
            json={"removeLabelIds": ["UNREAD"]},
        )

    def _labels(self) -> dict[str, str]:
        if self._label_cache is None:
            resp = self._get("labels")
            self._label_cache = {
                l["name"].upper(): l["id"]
                for l in resp.get("labels") or []
            }
        return self._label_cache


def _label_token(folder: str) -> str:
    if not folder:
        return "INBOX"
    f = folder.upper()
    if f in _SYSTEM_LABELS:
        return f
    return folder.replace(" ", "-")


def _label_id(client: "GmailClient", folder: str) -> str:
    f = (folder or "INBOX").upper()
    if f in _SYSTEM_LABELS:
        return f
    labels = client._labels()
    if f in labels:
        return labels[f]
    raise GmailError(
        f"label {folder!r} not found. Existing: {sorted(labels)}"
    )


def _gmail_date(s: str) -> str:
    try:
        dt = datetime.fromisoformat(s)
        return dt.strftime("%Y/%m/%d")
    except ValueError:
        return s


def _check(r: httpx.Response) -> dict:
    if r.status_code == 401:
        raise GmailError(
            "unauthorized — the stored token may be revoked. "
            "Run `alpi setup → Gateways → Gmail` to re-authorize."
        )
    if r.status_code >= 400:
        try:
            err = r.json().get("error", {})
            msg = err.get("message", r.text)
        except Exception:  # noqa: BLE001
            msg = r.text
        raise GmailError(f"gmail api error ({r.status_code}): {msg}")
    try:
        return r.json()
    except Exception:  # noqa: BLE001
        return {}


def _headers_map(msg: dict) -> dict[str, str]:
    headers = (msg.get("payload") or {}).get("headers") or []
    return {h["name"].lower(): h["value"] for h in headers}


def _envelope(meta: dict, folder: str) -> EmailEnvelope:
    h = _headers_map(meta)
    date = _parse_date(h.get("date", ""))
    label_ids = set(meta.get("labelIds") or [])
    return EmailEnvelope(
        uid=meta["id"],
        from_=h.get("from", ""),
        to=_parse_addresses(h.get("to", "")),
        subject=h.get("subject", ""),
        date=date,
        unread="UNREAD" in label_ids,
        has_attachments=_has_attachments(meta.get("payload", {})),
        folder=folder,
    )


def _message_full(msg: dict, folder: str) -> EmailMessageFull:
    h = _headers_map(msg)
    body, truncated = _extract_body(msg.get("payload", {}))
    return EmailMessageFull(
        uid=msg["id"],
        from_=h.get("from", ""),
        to=_parse_addresses(h.get("to", "")),
        cc=_parse_addresses(h.get("cc", "")),
        subject=h.get("subject", ""),
        date=_parse_date(h.get("date", "")),
        body=body,
        body_truncated=truncated,
        message_id=h.get("message-id", ""),
        in_reply_to=h.get("in-reply-to", ""),
        references=h.get("references", ""),
        attachments=_attachment_names(msg.get("payload", {})),
        folder=folder,
    )


def _parse_date(s: str):
    if not s:
        return None
    try:
        return email.utils.parsedate_to_datetime(s)
    except (TypeError, ValueError):
        return None


_ADDR_SPLIT = re.compile(r",\s*(?![^<]*>)")


def _parse_addresses(s: str) -> list[str]:
    if not s:
        return []
    parts = _ADDR_SPLIT.split(s)
    return [p.strip() for p in parts if p.strip()]


def _pad(s: str) -> str:
    return s + "=" * (-len(s) % 4)


def _walk_parts(payload: dict):
    yield payload
    for p in payload.get("parts") or []:
        yield from _walk_parts(p)


def _has_attachments(payload: dict) -> bool:
    for part in _walk_parts(payload):
        if part.get("filename"):
            return True
    return False


def _attachment_names(payload: dict) -> list[str]:
    return [p["filename"] for p in _walk_parts(payload) if p.get("filename")]


def _find_attachment(payload: dict, name: str) -> dict | None:
    for p in _walk_parts(payload):
        if p.get("filename") == name:
            return p
    return None


def _extract_body(payload: dict) -> tuple[str, bool]:
    text = _preferred_body(payload)
    if not text:
        return "", False
    if len(text) > MAX_BODY_CHARS:
        return text[:MAX_BODY_CHARS] + "\n…[truncated]", True
    return text, False


def _preferred_body(payload: dict) -> str:
    text_plain = None
    text_html = None
    for part in _walk_parts(payload):
        mt = part.get("mimeType", "")
        body = part.get("body") or {}
        data = body.get("data")
        if not data or part.get("filename"):
            continue
        if mt == "text/plain" and text_plain is None:
            text_plain = _decode_body(data)
        elif mt == "text/html" and text_html is None:
            text_html = _decode_body(data)
    if text_plain:
        return text_plain
    if text_html:
        return _html_to_text(text_html)
    return ""


def _decode_body(data: str) -> str:
    try:
        return base64.urlsafe_b64decode(_pad(data)).decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return ""


_TAG = re.compile(r"<[^>]+>")


def _html_to_text(s: str) -> str:
    s = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", s, flags=re.S | re.I)
    s = _TAG.sub("", s)
    return html.unescape(s).strip()


def _build_mime(to: list[str], subject: str, body: str,
                cc: list[str], attachments: list[str]) -> EmailMessage:
    msg = EmailMessage()
    msg["To"] = ", ".join(to)
    if cc:
        msg["Cc"] = ", ".join(cc)
    msg["Subject"] = subject
    msg.set_content(body)
    for path_str in attachments:
        p = Path(path_str)
        if not p.is_file():
            raise GmailError(f"attachment not found: {path_str}")
        data = p.read_bytes()
        msg.add_attachment(
            data, maintype="application", subtype="octet-stream",
            filename=p.name,
        )
    return msg
