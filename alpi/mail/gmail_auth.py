"""Gmail OAuth2 — Authorization Code + PKCE flow (desktop loopback).

Scopes requested:
  - https://www.googleapis.com/auth/gmail.modify
  - https://www.googleapis.com/auth/gmail.send

Token lifecycle:
  - First run: browser consent → loopback callback → exchange code
    for access + refresh tokens. Saved to
    ``~/.alpi/profiles/<name>/gmail_token.json`` (mode 0600).
  - Subsequent: ``get_access_token()`` refreshes if <120s of
    lifetime remain. ``fcntl`` lock avoids TUI + gateway +
    schedule daemon racing on the same file.

Client credentials (``GMAIL_CLIENT_ID`` / ``GMAIL_CLIENT_SECRET``)
are read from the profile's ``.env``. Storing them there matches
the pattern used by every other secret in alpi.
"""

from __future__ import annotations

import base64
import hashlib
import http.server
import json
import os
import secrets
import socket
import time
import urllib.parse
import webbrowser
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlparse

import httpx

SCOPES = " ".join([
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/userinfo.email",
])

_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"

_REFRESH_SKEW_SECONDS = 120


class GmailAuthError(RuntimeError):
    pass


@dataclass
class GmailToken:
    email: str
    access_token: str
    refresh_token: str
    expires_at: float

    def expires_in(self) -> float:
        return self.expires_at - time.time()

    def needs_refresh(self) -> bool:
        return self.expires_in() < _REFRESH_SKEW_SECONDS


def token_path(home: Path) -> Path:
    return home / "secrets" / "gmail_token.json"


def _client_credentials() -> tuple[str, str]:
    cid = os.environ.get("GMAIL_CLIENT_ID", "").strip()
    csec = os.environ.get("GMAIL_CLIENT_SECRET", "").strip()
    if not cid or not csec:
        raise GmailAuthError(
            "GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET must be set in ~/.alpi/.env "
            "— create an OAuth Desktop client in Google Cloud Console first."
        )
    return cid, csec


@contextmanager
def _lock(home: Path):
    import fcntl
    lock_path = home / "secrets" / ".gmail_token.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    f = open(lock_path, "w")
    try:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        f.close()


def _load(home: Path) -> Optional[GmailToken]:
    p = token_path(home)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text())
        return GmailToken(
            email=data["email"],
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_at=float(data["expires_at"]),
        )
    except (json.JSONDecodeError, KeyError, ValueError):
        return None


def _save(home: Path, token: GmailToken) -> None:
    p = token_path(home)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps({
        "email": token.email,
        "access_token": token.access_token,
        "refresh_token": token.refresh_token,
        "expires_at": token.expires_at,
    }, indent=2))
    os.chmod(tmp, 0o600)
    tmp.replace(p)


def clear(home: Path) -> None:
    p = token_path(home)
    if p.exists():
        p.unlink()


def _pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)[:128]
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _CallbackServer(http.server.HTTPServer):
    received_code: Optional[str] = None
    received_state: Optional[str] = None
    received_error: Optional[str] = None


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        server: _CallbackServer = self.server  # type: ignore[assignment]
        server.received_code = (params.get("code") or [None])[0]
        server.received_state = (params.get("state") or [None])[0]
        server.received_error = (params.get("error") or [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        if server.received_error:
            body = f"<h1>alpi — OAuth error</h1><p>{server.received_error}</p>"
        else:
            body = (
                "<h1>alpi — Gmail authorized</h1>"
                "<p>You can close this tab and return to the terminal.</p>"
            )
        self.wfile.write(body.encode("utf-8"))

    def log_message(self, format: str, *args) -> None:  # noqa: A002, ARG002
        pass


def first_run(home: Path) -> GmailToken:
    """Open browser, wait for consent, save token to disk. Returns the token."""
    client_id, client_secret = _client_credentials()
    port = _find_free_port()
    redirect_uri = f"http://127.0.0.1:{port}"
    verifier, challenge = _pkce_pair()
    state = secrets.token_urlsafe(24)

    auth_params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": SCOPES,
        "access_type": "offline",
        "prompt": "consent",
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": state,
    }
    auth_url = f"{_AUTH_URL}?{urllib.parse.urlencode(auth_params)}"

    server = _CallbackServer(("127.0.0.1", port), _CallbackHandler)
    try:
        webbrowser.open(auth_url)
    except Exception:  # noqa: BLE001
        pass
    print(f"\nIf the browser did not open, visit:\n  {auth_url}\n")
    server.timeout = 300
    deadline = time.time() + 300
    while server.received_code is None and server.received_error is None:
        server.handle_request()
        if time.time() > deadline:
            raise GmailAuthError("OAuth timed out after 5 min waiting for consent")

    if server.received_error:
        raise GmailAuthError(f"OAuth denied: {server.received_error}")
    if server.received_state != state:
        raise GmailAuthError("OAuth state mismatch — possible CSRF")

    with httpx.Client(timeout=10.0) as client:
        r = client.post(_TOKEN_URL, data={
            "code": server.received_code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
            "code_verifier": verifier,
        })
        if r.status_code != 200:
            raise GmailAuthError(f"token exchange failed: {r.status_code} {r.text}")
        body = r.json()
        access_token = body["access_token"]
        refresh_token = body.get("refresh_token")
        if not refresh_token:
            raise GmailAuthError(
                "no refresh_token returned — did you already authorize this "
                "client before without revoking? Revoke at "
                "https://myaccount.google.com/permissions and retry."
            )
        expires_at = time.time() + float(body.get("expires_in", 3600))

        ui = client.get(_USERINFO_URL, headers={
            "Authorization": f"Bearer {access_token}",
        })
        email = ui.json().get("email", "") if ui.status_code == 200 else ""

    token = GmailToken(
        email=email,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=expires_at,
    )
    with _lock(home):
        _save(home, token)
    return token


def _refresh(home: Path, token: GmailToken) -> GmailToken:
    client_id, client_secret = _client_credentials()
    with httpx.Client(timeout=10.0) as client:
        r = client.post(_TOKEN_URL, data={
            "refresh_token": token.refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
        })
        if r.status_code != 200:
            raise GmailAuthError(
                f"token refresh failed ({r.status_code}): {r.text}. "
                "If the refresh token was revoked, run setup again."
            )
        body = r.json()
    token.access_token = body["access_token"]
    token.expires_at = time.time() + float(body.get("expires_in", 3600))
    if body.get("refresh_token"):
        token.refresh_token = body["refresh_token"]
    with _lock(home):
        _save(home, token)
    return token


def get_access_token(home: Path) -> str:
    """Return a valid access token, refreshing if needed."""
    with _lock(home):
        token = _load(home)
    if token is None:
        raise GmailAuthError(
            "no Gmail token — run `alpi setup → Gateways → Gmail` first"
        )
    if token.needs_refresh():
        token = _refresh(home, token)
    return token.access_token


def get_email(home: Path) -> Optional[str]:
    """Return the email address bound to the stored token, if any."""
    token = _load(home)
    return token.email if token else None
