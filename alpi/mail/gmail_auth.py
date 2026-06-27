"""Gmail OAuth2 — Authorization Code + PKCE flow.

Scopes requested:
  - https://www.googleapis.com/auth/gmail.modify
  - https://www.googleapis.com/auth/gmail.send

Token lifecycle (per account_id):
  - First run: browser consent → callback delivers ``code`` → exchange
    for access + refresh tokens. Saved to
    ``<home>/secrets/gmail_tokens/<account_id>.json`` (mode 0600).
  - Subsequent: ``get_access_token()`` refreshes if <120s of
    lifetime remain. ``fcntl`` lock avoids TUI + scheduler +
    service daemon racing on the same file.

Client credentials (``GMAIL_CLIENT_ID`` / ``GMAIL_CLIENT_SECRET``)
are read from the profile's ``.env``.

The flow is **split** into ``prepare`` (build auth URL, allocate
state + PKCE verifier) and ``exchange`` (swap code for tokens).
Callers compose them:

  - ``first_run(home)`` — CLI local: opens a loopback on the
    *same* machine that runs the wizard and the browser.
  - ``first_run_paste(home)`` — CLI headless: prints URL, reads
    pasted callback URL from stdin. No loopback. Use over SSH.
  - desktop / remote daemons — ``prepare`` runs on the daemon,
    the **client** runs the loopback against its own browser,
    then calls ``exchange`` over the host plane. The daemon
    never touches a browser or a local port.
"""

from __future__ import annotations

import base64
import hashlib
import http.server
import json
import secrets
import socket
import time
import urllib.parse
import webbrowser
from contextlib import contextmanager
from dataclasses import dataclass
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
_OAUTH_TIMEOUT_SECONDS = 300


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


@dataclass
class AuthHandle:
    """Opaque-from-the-outside handle returned by ``prepare``. The caller passes ``code_verifier`` and ``redirect_uri`` back into ``exchange``; the verifier never leaves the host (it's the PKCE secret)."""
    auth_url: str
    state: str
    code_verifier: str
    redirect_uri: str


def token_path(home: Path, account_id: str) -> Path:
    from alpi.mail.accounts import gmail_token_path
    return gmail_token_path(home, account_id)


def _client_credentials(home: Path) -> tuple[str, str]:
    # Read from the profile's effective env so each profile uses its own OAuth client; never reach into os.environ blindly — under the daemon two profiles can have independent Gmail tokens.
    from alpi.home import effective_profile_env
    env = effective_profile_env(home)
    cid = (env.get("GMAIL_CLIENT_ID") or "").strip()
    csec = (env.get("GMAIL_CLIENT_SECRET") or "").strip()
    if not cid or not csec:
        raise GmailAuthError(
            "GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET must be set in ~/.alpi/.env "
            "— create an OAuth Desktop client in Google Cloud Console first."
        )
    return cid, csec


@contextmanager
def _lock(home: Path, account_id: str):
    import fcntl
    lock_path = home / "secrets" / "gmail_tokens" / f".{account_id}.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    f = open(lock_path, "w")
    try:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        f.close()


def _load(home: Path, account_id: str) -> Optional[GmailToken]:
    p = token_path(home, account_id)
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


def _save(home: Path, account_id: str, token: GmailToken) -> None:
    from alpi.secrets_io import safe_write_secret
    safe_write_secret(token_path(home, account_id), json.dumps({
        "email": token.email,
        "access_token": token.access_token,
        "refresh_token": token.refresh_token,
        "expires_at": token.expires_at,
    }, indent=2))


def clear(home: Path, account_id: str) -> None:
    p = token_path(home, account_id)
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


def prepare(home: Path, *, redirect_uri: str) -> AuthHandle:
    """Build the Google consent URL and stash a fresh PKCE verifier.

    Does no I/O beyond reading the profile env. Safe to run on a
    daemon: no browser, no loopback. The caller decides where the
    redirect lands (their own loopback, or a paste flow)."""
    client_id, _ = _client_credentials(home)
    verifier, challenge = _pkce_pair()
    state = secrets.token_urlsafe(24)
    qs = urllib.parse.urlencode({
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": SCOPES,
        "access_type": "offline",
        "prompt": "consent",
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": state,
    })
    return AuthHandle(
        auth_url=f"{_AUTH_URL}?{qs}",
        state=state,
        code_verifier=verifier,
        redirect_uri=redirect_uri,
    )


def exchange(
    home: Path,
    account_id: str,
    *,
    code: str,
    code_verifier: str,
    redirect_uri: str,
) -> GmailToken:
    """Swap the authorization ``code`` for tokens and persist them.

    ``redirect_uri`` must match the one passed to ``prepare`` —
    Google requires byte-equality on the token endpoint."""
    client_id, client_secret = _client_credentials(home)
    with httpx.Client(timeout=10.0) as client:
        r = client.post(_TOKEN_URL, data={
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
            "code_verifier": code_verifier,
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
    if not account_id:
        from alpi.mail.accounts import slug
        account_id = slug(email)
    with _lock(home, account_id):
        _save(home, account_id, token)
    return token


def first_run(home: Path, account_id: str = "") -> GmailToken:
    """Browser + local loopback flow. Requires a usable browser and a
    loopback socket on the **same machine** running this function.

    Falls back to ``first_run_paste`` automatically if ``webbrowser.open``
    reports failure (typical on headless boxes)."""
    port = _find_free_port()
    redirect_uri = f"http://127.0.0.1:{port}"
    handle = prepare(home, redirect_uri=redirect_uri)

    opened = False
    try:
        opened = webbrowser.open(handle.auth_url)
    except Exception:  # noqa: BLE001
        opened = False
    if not opened:
        return _paste_flow(home, account_id, handle, port)

    print(f"\nIf the browser did not open, visit:\n  {handle.auth_url}\n")
    server = _CallbackServer(("127.0.0.1", port), _CallbackHandler)
    server.timeout = _OAUTH_TIMEOUT_SECONDS
    deadline = time.time() + _OAUTH_TIMEOUT_SECONDS
    while server.received_code is None and server.received_error is None:
        server.handle_request()
        if time.time() > deadline:
            raise GmailAuthError("OAuth timed out after 5 min waiting for consent")

    if server.received_error:
        raise GmailAuthError(f"OAuth denied: {server.received_error}")
    if server.received_state != handle.state:
        raise GmailAuthError("OAuth state mismatch — possible CSRF")

    return exchange(
        home,
        account_id,
        code=server.received_code or "",
        code_verifier=handle.code_verifier,
        redirect_uri=redirect_uri,
    )


def first_run_paste(home: Path, account_id: str = "") -> GmailToken:
    """Headless flow: print the consent URL, accept the pasted callback URL from stdin. No loopback, no browser-opening assumption — use this over SSH or inside a container."""
    port = _find_free_port()
    redirect_uri = f"http://127.0.0.1:{port}"
    handle = prepare(home, redirect_uri=redirect_uri)
    return _paste_flow(home, account_id, handle, port)


def _paste_flow(home: Path, account_id: str, handle: AuthHandle, port: int) -> GmailToken:
    print(
        "\nGmail OAuth — paste flow (no local browser available).\n\n"
        "1. Open this URL in any browser, on any device:\n"
        f"     {handle.auth_url}\n\n"
        "2. Authorize Gmail access. Google will redirect to a URL like:\n"
        f"     http://127.0.0.1:{port}/?code=...&state=...\n"
        "   The page WILL fail to load — that's expected. Copy the FULL\n"
        "   URL from your browser's address bar.\n",
        flush=True,
    )
    try:
        pasted = input("3. Paste the callback URL here: ").strip()
    except EOFError:
        raise GmailAuthError("OAuth aborted — no input received")
    parsed = urlparse(pasted)
    params = parse_qs(parsed.query)
    code = (params.get("code") or [None])[0]
    state = (params.get("state") or [None])[0]
    error = (params.get("error") or [None])[0]
    if error:
        raise GmailAuthError(f"OAuth denied: {error}")
    if not code:
        raise GmailAuthError(
            "no `code` parameter found in pasted URL — did you copy the "
            "redirect URL from your browser's address bar?"
        )
    if state != handle.state:
        raise GmailAuthError("OAuth state mismatch — possible CSRF or stale paste")
    return exchange(
        home,
        account_id,
        code=code,
        code_verifier=handle.code_verifier,
        redirect_uri=handle.redirect_uri,
    )


def _refresh(home: Path, account_id: str, token: GmailToken) -> GmailToken:
    client_id, client_secret = _client_credentials(home)
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
    with _lock(home, account_id):
        _save(home, account_id, token)
    return token


def get_access_token(home: Path, account_id: str) -> str:
    """Return a valid access token, refreshing if needed."""
    with _lock(home, account_id):
        token = _load(home, account_id)
    if token is None:
        raise GmailAuthError(
            "no Gmail token — run `alpi setup → Email → Gmail` first"
        )
    if token.needs_refresh():
        token = _refresh(home, account_id, token)
    return token.access_token


def get_email(home: Path, account_id: str) -> Optional[str]:
    """Return the email address bound to the stored token, if any."""
    token = _load(home, account_id)
    return token.email if token else None
