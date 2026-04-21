"""EmailClient — IMAP + SMTP wrapper built on Python stdlib."""

from __future__ import annotations

import email
import email.header
import email.utils
import imaplib
import os
import re
import smtplib
import ssl
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Iterator


class EmailError(Exception):
    """Any failure the caller can report back — auth, network, protocol."""


DEFAULT_IMAP_PORT = 993
DEFAULT_SMTP_PORT = 587
# Cap on message body length we hand back to the agent. Long emails get
# truncated with a marker; the agent can request more via a specific
# action later if we add one. Keeps prompt size predictable.
MAX_BODY_CHARS = 8000


# Data classes


@dataclass
class EmailEnvelope:
    """Lightweight header-only record returned by list/search."""
    uid: str
    from_: str
    to: list[str]
    subject: str
    date: datetime | None
    unread: bool
    has_attachments: bool
    folder: str


@dataclass
class EmailMessageFull:
    """Full message — envelope + body + attachment names."""
    uid: str
    from_: str
    to: list[str]
    cc: list[str]
    subject: str
    date: datetime | None
    body: str
    body_truncated: bool
    message_id: str                          # RFC Message-Id header
    in_reply_to: str
    references: str
    attachments: list[str] = field(default_factory=list)
    folder: str = "INBOX"



class EmailClient:
    """IMAP+SMTP operations against a single mailbox."""

    def __init__(
        self,
        address: str,
        password: str,
        imap_host: str,
        smtp_host: str,
        imap_port: int = DEFAULT_IMAP_PORT,
        smtp_port: int = DEFAULT_SMTP_PORT,
    ) -> None:
        if not (address and password and imap_host and smtp_host):
            raise EmailError(
                "EmailClient requires address, password, imap_host, smtp_host"
            )
        self.address = address
        self.password = password
        self.imap_host = imap_host
        self.smtp_host = smtp_host
        self.imap_port = imap_port
        self.smtp_port = smtp_port

    # Construction from environment

    @classmethod
    def from_env(cls) -> "EmailClient":
        """Build a client from ``EMAIL_*`` variables in the current env."""
        addr = os.environ.get("EMAIL_ADDRESS", "").strip()
        pwd = os.environ.get("EMAIL_PASSWORD", "")
        imap = os.environ.get("EMAIL_IMAP_HOST", "").strip()
        smtp = os.environ.get("EMAIL_SMTP_HOST", "").strip()
        missing = [
            name for name, val in (
                ("EMAIL_ADDRESS", addr), ("EMAIL_PASSWORD", pwd),
                ("EMAIL_IMAP_HOST", imap), ("EMAIL_SMTP_HOST", smtp),
            ) if not val
        ]
        if missing:
            raise EmailError(
                f"email not configured: missing {', '.join(missing)} in "
                f"~/.alpi/.env. Run `alpi setup` and pick 'Email (IMAP/SMTP)'."
            )
        return cls(
            address=addr,
            password=pwd,
            imap_host=imap,
            smtp_host=smtp,
            imap_port=int(os.environ.get("EMAIL_IMAP_PORT") or DEFAULT_IMAP_PORT),
            smtp_port=int(os.environ.get("EMAIL_SMTP_PORT") or DEFAULT_SMTP_PORT),
        )

    # Connectivity test (used by the setup wizard)

    def test(self) -> None:
        """Open + login on IMAP and SMTP. Raises ``EmailError`` on failure."""
        try:
            with self._imap() as imap:
                imap.select("INBOX", readonly=True)
        except imaplib.IMAP4.error as e:
            raise EmailError(f"IMAP login failed: {e}")
        except (OSError, ssl.SSLError) as e:
            raise EmailError(f"IMAP connect failed: {e}")
        try:
            with self._smtp():
                pass
        except smtplib.SMTPException as e:
            raise EmailError(f"SMTP login failed: {e}")
        except (OSError, ssl.SSLError) as e:
            raise EmailError(f"SMTP connect failed: {e}")

    # Read-side: list + search + read + download_attachment

    def list(
        self, folder: str = "INBOX",
        limit: int = 20, unread_only: bool = False,
    ) -> list[EmailEnvelope]:
        """Most-recent first. ``unread_only=True`` filters to UNSEEN."""
        query = ["UNSEEN"] if unread_only else ["ALL"]
        with self._imap() as imap:
            self._select(imap, folder)
            uids = self._uid_search(imap, query)
            uids = uids[-limit:]  # most recent last, we want them
            return list(reversed(list(self._fetch_envelopes(imap, uids, folder))))

    def search(
        self, folder: str = "INBOX", limit: int = 20,
        from_: str = "", to: str = "", subject: str = "",
        body: str = "", since: str = "", unread_only: bool = False,
    ) -> list[EmailEnvelope]:
        """Basic header/body search — translated to IMAP criteria."""
        query: list[Any] = []
        if unread_only:
            query.append("UNSEEN")
        if from_:
            query += ["FROM", from_]
        if to:
            query += ["TO", to]
        if subject:
            query += ["SUBJECT", subject]
        if body:
            query += ["BODY", body]
        if since:
            query += ["SINCE", _imap_date(since)]
        if not query:
            query = ["ALL"]
        with self._imap() as imap:
            self._select(imap, folder)
            uids = self._uid_search(imap, query)
            uids = uids[-limit:]
            return list(reversed(list(self._fetch_envelopes(imap, uids, folder))))

    def read(self, uid: str, folder: str = "INBOX") -> EmailMessageFull:
        with self._imap() as imap:
            self._select(imap, folder)
            msg = self._fetch_message(imap, uid)
            if msg is None:
                raise EmailError(f"message {uid} not found in {folder}")
            return _parse_full(msg, uid, folder)

    def download_attachment(
        self, uid: str, attachment_name: str, dest: Path,
        folder: str = "INBOX",
    ) -> Path:
        """Write the named attachment's bytes to ``dest``. Returns dest."""
        with self._imap() as imap:
            self._select(imap, folder)
            msg = self._fetch_message(imap, uid)
            if msg is None:
                raise EmailError(f"message {uid} not found in {folder}")
            for part in msg.iter_attachments():
                name = part.get_filename() or ""
                name = _decode_header(name)
                if name == attachment_name:
                    payload = part.get_payload(decode=True) or b""
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(payload)
                    return dest
            raise EmailError(
                f"attachment {attachment_name!r} not found on message {uid}"
            )

    # Write-side: send / reply / forward

    def send(
        self, to: list[str], subject: str, body: str,
        cc: list[str] | None = None,
        in_reply_to: str = "", references: str = "",
        attachments: list[Path] | None = None,
    ) -> None:
        msg = EmailMessage()
        msg["From"] = self.address
        msg["To"] = ", ".join(to)
        if cc:
            msg["Cc"] = ", ".join(cc)
        msg["Subject"] = subject
        if in_reply_to:
            msg["In-Reply-To"] = in_reply_to
        if references:
            msg["References"] = references
        msg["Date"] = email.utils.formatdate(localtime=True)
        msg["Message-Id"] = email.utils.make_msgid(domain=self._msgid_domain())
        msg.set_content(body)
        for path in attachments or []:
            data = path.read_bytes()
            maintype, _, subtype = _guess_mime(path).partition("/")
            msg.add_attachment(
                data, maintype=maintype, subtype=subtype or "octet-stream",
                filename=path.name,
            )
        recipients = list(to) + (cc or [])
        with self._smtp() as smtp:
            smtp.send_message(msg, from_addr=self.address, to_addrs=recipients)

    def reply(self, uid: str, body: str, reply_all: bool = False,
              folder: str = "INBOX") -> None:
        orig = self.read(uid, folder=folder)
        to = [orig.from_]
        cc: list[str] = []
        if reply_all:
            cc = [addr for addr in orig.to + orig.cc
                  if addr and addr.lower() != self.address.lower()]
        subject = orig.subject
        if not subject.lower().startswith("re:"):
            subject = f"Re: {subject}"
        references = (orig.references + " " + orig.message_id).strip()
        self.send(
            to=to, cc=cc, subject=subject, body=body,
            in_reply_to=orig.message_id, references=references,
        )

    def forward(self, uid: str, to: list[str], body: str = "",
                folder: str = "INBOX") -> None:
        orig = self.read(uid, folder=folder)
        subject = orig.subject
        if not subject.lower().startswith("fwd:"):
            subject = f"Fwd: {subject}"
        wrapped = (
            f"{body}\n\n---------- Forwarded message ----------\n"
            f"From: {orig.from_}\n"
            f"Date: {orig.date.isoformat() if orig.date else ''}\n"
            f"Subject: {orig.subject}\n"
            f"To: {', '.join(orig.to)}\n\n"
            f"{orig.body}"
        )
        self.send(to=to, subject=subject, body=wrapped)

    # Organize: move + delete

    def move(self, uid: str, dest_folder: str, folder: str = "INBOX") -> None:
        with self._imap() as imap:
            self._select(imap, folder)
            typ, _ = imap.uid("MOVE", uid, dest_folder)
            if typ != "OK":
                # Some servers lack MOVE; fall back to COPY + flag + expunge.
                typ, _ = imap.uid("COPY", uid, dest_folder)
                if typ != "OK":
                    raise EmailError(f"could not move uid {uid} to {dest_folder}")
                imap.uid("STORE", uid, "+FLAGS", r"(\Deleted)")
                imap.expunge()

    def delete(self, uid: str, folder: str = "INBOX") -> None:
        """Move to Trash (soft delete). We don't expose hard delete."""
        # "Trash" is a common alias but not universal. We try a couple
        # of well-known names before giving up; if the server has none
        # of them, the caller can pass an explicit folder via move().
        for candidate in ("Trash", "[Gmail]/Trash", "Deleted", "Deleted Items"):
            try:
                self.move(uid, candidate, folder=folder)
                return
            except EmailError:
                continue
        raise EmailError(
            "could not find a Trash folder; use `move` with an explicit folder"
        )

    def _imap(self) -> "_ImapCtx":
        return _ImapCtx(self)

    def _smtp(self) -> "_SmtpCtx":
        return _SmtpCtx(self)

    def _msgid_domain(self) -> str:
        _, _, domain = self.address.partition("@")
        return domain or "alf.local"

    def _select(self, imap: imaplib.IMAP4, folder: str) -> None:
        typ, _ = imap.select(_imap_folder(folder))
        if typ != "OK":
            raise EmailError(f"cannot select folder {folder!r}")

    def _uid_search(self, imap: imaplib.IMAP4, criteria: list[Any]) -> list[str]:
        typ, data = imap.uid("SEARCH", None, *criteria)  # type: ignore[arg-type]
        if typ != "OK":
            raise EmailError(f"IMAP search failed: {data!r}")
        raw = data[0].decode() if data and data[0] else ""
        return raw.split()

    def _fetch_envelopes(
        self, imap: imaplib.IMAP4, uids: list[str], folder: str,
    ) -> Iterator[EmailEnvelope]:
        if not uids:
            return
        # BODY.PEEK avoids marking messages as read.
        typ, data = imap.uid(
            "FETCH", ",".join(uids),
            "(UID FLAGS BODY.PEEK[HEADER.FIELDS (FROM TO SUBJECT DATE)] BODYSTRUCTURE)",
        )
        if typ != "OK":
            raise EmailError("IMAP fetch failed")
        for item in data:
            if not isinstance(item, tuple) or len(item) < 2:
                continue
            meta = item[0].decode(errors="replace") if isinstance(item[0], bytes) else str(item[0])
            uid = _extract_field(meta, "UID")
            flags_raw = _extract_parens(meta, "FLAGS") or ""
            unread = "\\Seen" not in flags_raw
            has_att = "attachment" in (meta.lower())
            raw_headers = item[1] if isinstance(item[1], bytes) else b""
            msg = email.message_from_bytes(raw_headers)
            yield EmailEnvelope(
                uid=uid or "",
                from_=_clean_addr(msg.get("From", "")),
                to=[_clean_addr(a) for a in (msg.get_all("To") or [])],
                subject=_decode_header(msg.get("Subject", "")),
                date=_parse_date(msg.get("Date", "")),
                unread=unread,
                has_attachments=has_att,
                folder=folder,
            )

    def _fetch_message(self, imap: imaplib.IMAP4, uid: str) -> EmailMessage | None:
        typ, data = imap.uid("FETCH", uid, "(BODY.PEEK[])")
        if typ != "OK" or not data or not isinstance(data[0], tuple):
            return None
        raw = data[0][1]
        if not isinstance(raw, bytes):
            return None
        return email.message_from_bytes(raw, policy=email.policy.default)


# Connection context managers (thin; tests can monkeypatch easily)


class _ImapCtx:
    def __init__(self, client: EmailClient) -> None:
        self._client = client
        self._conn: imaplib.IMAP4 | None = None

    def __enter__(self) -> imaplib.IMAP4:
        try:
            self._conn = imaplib.IMAP4_SSL(
                self._client.imap_host, self._client.imap_port,
            )
            self._conn.login(self._client.address, self._client.password)
        except imaplib.IMAP4.error as e:
            raise EmailError(f"IMAP login failed: {e}")
        except (OSError, ssl.SSLError) as e:
            raise EmailError(f"IMAP connect failed: {e}")
        return self._conn

    def __exit__(self, *_: Any) -> None:
        if self._conn is None:
            return
        try:
            self._conn.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            self._conn.logout()
        except Exception:  # noqa: BLE001
            pass


class _SmtpCtx:
    """SMTP connection — picks SMTPS vs STARTTLS by port.

    Port 465 is SMTPS (implicit TLS from the TCP handshake). Every
    other port we treat as STARTTLS-capable submission (587 is the
    canonical one; 25 also works over STARTTLS on many servers).
    Getting this wrong means the server hangs up as soon as we speak
    plain-text SMTP on an SSL-only port — which is what we saw with
    PrivateEmail before this fix.
    """

    def __init__(self, client: EmailClient) -> None:
        self._client = client
        self._conn: smtplib.SMTP | None = None

    def __enter__(self) -> smtplib.SMTP:
        try:
            ctx = ssl.create_default_context()
            if self._client.smtp_port == 465:
                self._conn = smtplib.SMTP_SSL(
                    self._client.smtp_host, self._client.smtp_port,
                    timeout=30, context=ctx,
                )
                self._conn.ehlo()
            else:
                self._conn = smtplib.SMTP(
                    self._client.smtp_host, self._client.smtp_port,
                    timeout=30,
                )
                self._conn.ehlo()
                self._conn.starttls(context=ctx)
                self._conn.ehlo()
            self._conn.login(self._client.address, self._client.password)
        except smtplib.SMTPException as e:
            raise EmailError(f"SMTP login failed: {e}")
        except (OSError, ssl.SSLError) as e:
            raise EmailError(f"SMTP connect failed: {e}")
        return self._conn

    def __exit__(self, *_: Any) -> None:
        if self._conn is None:
            return
        try:
            self._conn.quit()
        except Exception:  # noqa: BLE001
            pass



def _decode_header(raw: str) -> str:
    if not raw:
        return ""
    try:
        parts = email.header.decode_header(raw)
    except Exception:  # noqa: BLE001
        return raw
    out = []
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
    _, addr = email.utils.parseaddr(_decode_header(raw))
    return addr.strip().lower()


def _parse_date(raw: str) -> datetime | None:
    if not raw:
        return None
    try:
        dt = email.utils.parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _imap_folder(folder: str) -> str:
    if " " in folder or "/" in folder:
        return f'"{folder}"'
    return folder


def _imap_date(value: str) -> str:
    try:
        dt = datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return value  # pass through — caller may already have IMAP format
    return dt.strftime("%d-%b-%Y")


def _extract_field(meta: str, key: str) -> str:
    m = re.search(rf"{re.escape(key)} (\S+)", meta)
    return m.group(1) if m else ""


def _extract_parens(meta: str, key: str) -> str:
    m = re.search(rf"{re.escape(key)} \(([^)]*)\)", meta)
    return m.group(1) if m else ""


def _parse_full(msg: EmailMessage, uid: str, folder: str) -> EmailMessageFull:
    body, truncated = _pick_body(msg)
    attachments = [
        _decode_header(p.get_filename() or "")
        for p in msg.iter_attachments()
        if p.get_filename()
    ]
    return EmailMessageFull(
        uid=uid,
        from_=_clean_addr(msg.get("From", "")),
        to=[_clean_addr(a) for a in (msg.get_all("To") or [])],
        cc=[_clean_addr(a) for a in (msg.get_all("Cc") or [])],
        subject=_decode_header(msg.get("Subject", "")),
        date=_parse_date(msg.get("Date", "")),
        body=body,
        body_truncated=truncated,
        message_id=msg.get("Message-Id", "") or "",
        in_reply_to=msg.get("In-Reply-To", "") or "",
        references=msg.get("References", "") or "",
        attachments=[a for a in attachments if a],
        folder=folder,
    )


def _pick_body(msg: EmailMessage) -> tuple[str, bool]:
    plain = msg.get_body(preferencelist=("plain",))
    if plain is not None:
        text = _coerce_str(plain)
    else:
        html = msg.get_body(preferencelist=("html",))
        text = _strip_html(_coerce_str(html)) if html is not None else ""
    if len(text) > MAX_BODY_CHARS:
        return text[:MAX_BODY_CHARS] + "\n\n[… truncated]", True
    return text, False


def _coerce_str(part: EmailMessage | None) -> str:
    if part is None:
        return ""
    try:
        content = part.get_content()
    except (LookupError, KeyError, TypeError):
        payload = part.get_payload(decode=True) or b""
        content = payload.decode(
            part.get_content_charset() or "utf-8", errors="replace",
        )
    return content if isinstance(content, str) else ""


_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\n\s*\n\s*\n+")


def _strip_html(html: str) -> str:
    text = _HTML_TAG_RE.sub("", html)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&")
    text = text.replace("&lt;", "<").replace("&gt;", ">")
    return _WHITESPACE_RE.sub("\n\n", text).strip()


def _guess_mime(path: Path) -> str:
    import mimetypes
    mime, _ = mimetypes.guess_type(path.name)
    return mime or "application/octet-stream"
