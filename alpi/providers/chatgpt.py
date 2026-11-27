from __future__ import annotations

import base64
import contextlib
import hashlib
import http.server
import json
import os
import secrets
import time
import urllib.parse
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import httpx

from alpi.providers.base import ModelInfo, Provider

try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None

PREFIX = "chatgpt-plan"
AGENT_NAME = "alpi"
ISSUER = "https://auth.openai.com"
AUTHORIZE_URL = f"{ISSUER}/api/accounts/authorize"
TOKEN_URL = f"{ISSUER}/api/accounts/oauth/token"
DISCOVERY_URL = f"{ISSUER}/.well-known/openid-configuration"
JWKS_URL = f"{ISSUER}/.well-known/jwks.json"
RESOURCE = "https://api.openai.com/v1"
MODELS_URL = f"{RESOURCE}/models"
RESPONSES_URL = f"{RESOURCE}/responses"
USAGE_URL = "https://chatgpt.com/settings/usage"
PLAN_SCOPE = "chatgpt.tokens.use.direct"
SCOPE = f"openid profile email offline_access resource.invoke {PLAN_SCOPE}"
FIRST_CLIENT = "dynamic_agent_client"
CALLBACK_PATH = "/auth/callback"
CALLBACK_PORT = 1455
LOGIN_TIMEOUT_S = 300
_REFRESH_SKEW_S = 300
_CLOCK_SKEW_S = 60
_UNUSABLE_REFRESH = frozenset({
    "invalid_grant", "invalid_refresh_token", "token_expired", "refresh_token_expired",
    "refresh_token_invalidated", "refresh_token_reused",
})


class PlanError(RuntimeError):
    def __init__(self, message: str, *, code: str = "", status_code: int | None = None, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.retryable = retryable


class NotSignedIn(PlanError):
    def __init__(self, message: str = "") -> None:
        super().__init__(
            message or "no ChatGPT sign-in for this profile; run `alpi chatgpt login`",
            code="not_signed_in", status_code=401,
        )


@dataclass
class Attempt:
    url: str
    shown_url: str
    state: str
    nonce: str
    verifier: str
    redirect_uri: str
    client_id: str


def record_path(home: Path) -> Path:
    return Path(home) / "secrets" / "chatgpt.json"


def _write_private(path: Path, text: str) -> None:
    from alpi.secrets_io import safe_write_secret

    _private_dir(path.parent)
    safe_write_secret(path, text)


def _private_dir(path: Path) -> None:
    try:
        path.mkdir(parents=True)
    except FileExistsError:
        return
    # `alpi doctor` fails a secrets folder that group or others can enter.
    path.chmod(0o700)


def host_id() -> str:
    from alpi.home import alpi_root

    path = alpi_root() / "secrets" / "chatgpt-host"
    try:
        saved = path.read_text(encoding="utf-8").strip()
    except OSError:
        saved = ""
    if saved.startswith("urn:uuid:"):
        return saved
    # One per machine, kept apart from the credential so moving the record never carries it: OpenAI attributes usage to the host.
    fresh = f"urn:uuid:{uuid.uuid4()}"
    _write_private(path, fresh + "\n")
    return fresh


def load(home: Path) -> dict[str, Any]:
    try:
        data = json.loads(record_path(home).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _save(home: Path, record: dict[str, Any]) -> None:
    _write_private(record_path(home), json.dumps(record, indent=2) + "\n")


def signed_in(home: Path) -> bool:
    record = load(home)
    return bool(record.get("refresh_token")) and PLAN_SCOPE in (record.get("scopes") or [])


def models(home: Path) -> list[dict[str, str]]:
    rows = load(home).get("models") if signed_in(home) else None
    return [r for r in rows or [] if isinstance(r, dict) and r.get("slug")]


@contextlib.contextmanager
def _locked(home: Path):
    if fcntl is None:
        yield
        return
    path = record_path(home)
    _private_dir(path.parent)
    with os.fdopen(os.open(path.parent / "chatgpt.lock", os.O_CREAT | os.O_RDWR, 0o600), "r+") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _unb64url(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def begin(home: Path, port: int) -> Attempt:
    record = load(home)
    client_id = str(record.get("client_id") or "")
    verifier = _b64url(secrets.token_bytes(48))
    attempt = Attempt(
        url="", shown_url="", state=secrets.token_urlsafe(24), nonce=secrets.token_urlsafe(24), verifier=verifier,
        redirect_uri=f"http://127.0.0.1:{port}{CALLBACK_PATH}", client_id=client_id,
    )
    params = {
        "client_id": client_id or FIRST_CLIENT,
        "ext_agent_host_id": host_id(),
        "response_type": "code",
        "redirect_uri": attempt.redirect_uri,
        "scope": SCOPE,
        "resource": RESOURCE,
        "state": attempt.state,
        "nonce": attempt.nonce,
        "code_challenge_method": "S256",
        "code_challenge": _b64url(hashlib.sha256(verifier.encode()).digest()),
    }
    if client_id:
        if record.get("email"):
            params["login_hint"] = record["email"]
        if record.get("subject") and PLAN_SCOPE not in (record.get("scopes") or []):
            # A returning sign-in shows no consent screen, so plan use declined earlier could never be granted.
            params["prompt"] = "consent"
    else:
        params["agent_name_hint"] = AGENT_NAME
    attempt.shown_url = AUTHORIZE_URL + "?" + urllib.parse.urlencode(params)
    if client_id and record.get("id_token"):
        params["id_token_hint"] = record["id_token"]
    attempt.url = AUTHORIZE_URL + "?" + urllib.parse.urlencode(params)
    return attempt


def _oauth_error(response: httpx.Response) -> PlanError:
    try:
        body = response.json()
    except ValueError:
        body = {}
    error = body.get("error") if isinstance(body, dict) else None
    code = error.get("code") if isinstance(error, dict) else error
    detail = (error.get("message") if isinstance(error, dict) else None) or body.get("error_description") or ""
    return PlanError(
        f"OpenAI refused the sign-in request ({response.status_code} {code or 'error'}) {detail}".strip(),
        code=str(code or ""), status_code=response.status_code, retryable=response.status_code >= 500,
    )


def unreachable(exc: Exception, what: str) -> PlanError:
    return PlanError(f"could not reach OpenAI {what}: {type(exc).__name__}", code="unreachable", retryable=True)


def _token_request(form: dict[str, str]) -> dict[str, Any]:
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(TOKEN_URL, data=form)
    except httpx.HTTPError as exc:
        raise unreachable(exc, "to exchange the sign-in") from exc
    if response.status_code != 200:
        raise _oauth_error(response)
    try:
        tokens = response.json()
    except ValueError:
        tokens = None
    if not isinstance(tokens, dict) or not isinstance(tokens.get("access_token"), str) or not tokens["access_token"]:
        raise PlanError("OpenAI answered the sign-in without an access token", code="bad_token_response", retryable=True)
    try:
        tokens["expires_in"] = int(tokens.get("expires_in") or 3600)
    except (TypeError, ValueError):
        tokens["expires_in"] = 3600
    return tokens


def _verify_signature(header: dict[str, Any], signed: bytes, signature: bytes, keys: list[dict[str, Any]]) -> None:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa, utils

    key = next((k for k in keys if k.get("kid") == header.get("kid")), None)
    if key is None:
        raise PlanError("the ID token is signed with a key OpenAI does not publish", code="id_token_invalid")
    alg = header.get("alg")
    number = lambda name: int.from_bytes(_unb64url(key[name]), "big")  # noqa: E731
    try:
        if alg == "RS256" and key.get("kty") == "RSA":
            rsa.RSAPublicNumbers(number("e"), number("n")).public_key().verify(signature, signed, padding.PKCS1v15(), hashes.SHA256())
        elif alg == "ES256" and key.get("kty") == "EC" and key.get("crv") == "P-256" and len(signature) == 64:
            der = utils.encode_dss_signature(int.from_bytes(signature[:32], "big"), int.from_bytes(signature[32:], "big"))
            ec.EllipticCurvePublicNumbers(number("x"), number("y"), ec.SECP256R1()).public_key().verify(der, signed, ec.ECDSA(hashes.SHA256()))
        else:
            raise PlanError(f"the ID token uses an algorithm alpi does not accept ({alg})", code="id_token_invalid")
    except PlanError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise PlanError("the ID token signature does not verify", code="id_token_invalid") from exc


def verify_id_token(token: str, *, client_id: str, nonce: str, keys: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    try:
        head, body, signature = token.split(".")
        header = json.loads(_unb64url(head))
        claims = json.loads(_unb64url(body))
        raw_signature = _unb64url(signature)
    except (ValueError, AttributeError) as exc:
        raise PlanError("the ID token is not a signed token", code="id_token_invalid") from exc
    if not isinstance(header, dict) or not isinstance(claims, dict):
        raise PlanError("the ID token is not a signed token", code="id_token_invalid")
    if keys is None:
        try:
            with httpx.Client(timeout=30.0) as client:
                keys = client.get(JWKS_URL).raise_for_status().json().get("keys") or []
        except (httpx.HTTPError, ValueError, AttributeError) as exc:
            raise unreachable(exc, "for the keys that sign its ID tokens") from exc
    _verify_signature(header, f"{head}.{body}".encode(), raw_signature, keys)
    audience = claims.get("aud")
    audiences = audience if isinstance(audience, list) else [audience]
    try:
        expired = float(claims.get("exp")) + _CLOCK_SKEW_S <= time.time()
    except (TypeError, ValueError):
        expired = True
    if claims.get("iss") != ISSUER or client_id not in audiences or expired or claims.get("nonce") != nonce or not claims.get("sub"):
        raise PlanError("the ID token is not for this sign-in (issuer, audience, expiry or nonce)", code="id_token_invalid")
    return claims


def _fetch_models(access_token: str) -> list[dict[str, str]]:
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(MODELS_URL, headers={"Authorization": f"Bearer {access_token}"})
        rows = (response.json() or {}).get("models") if response.status_code == 200 else []
    except (httpx.HTTPError, ValueError, AttributeError):
        return []
    return [
        {"slug": str(r["slug"]), "display_name": str(r.get("display_name") or r["slug"])}
        for r in rows or [] if isinstance(r, dict) and r.get("slug") and r.get("visibility") == "list"
    ]


def _with_tokens(record: dict[str, Any], tokens: dict[str, Any]) -> dict[str, Any]:
    out = dict(record)
    out["access_token"] = tokens["access_token"]
    out["refresh_token"] = tokens.get("refresh_token") or record.get("refresh_token") or ""
    if tokens.get("id_token"):
        out["id_token"] = tokens["id_token"]
    out["token_type"] = tokens.get("token_type") or "Bearer"
    out["expires_in"] = int(tokens.get("expires_in") or 3600)
    out["scopes"] = sorted(str(tokens.get("scope") or " ".join(record.get("scopes") or [])).split())
    out["saved_at"] = time.time()
    return out


_SIGNED_OUT_MEANWHILE = "this profile signed out while the sign-in was finishing; nothing was saved"


def finish(home: Path, attempt: Attempt, query: dict[str, str], *, keys: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    if not secrets.compare_digest(str(query.get("state") or "").encode(), attempt.state.encode()):
        raise PlanError("the browser came back with a different sign-in attempt; nothing was saved", code="state_mismatch")
    if query.get("error"):
        declined = query["error"] == "access_denied"
        raise PlanError(
            "the sign-in was declined in the browser; nothing was saved" if declined
            else f"OpenAI returned {query['error']}: {query.get('error_description') or ''}".strip(),
            code=str(query["error"]),
        )
    issued = str(query.get("client_id") or "")
    if attempt.client_id:
        if issued and issued != attempt.client_id:
            raise PlanError("OpenAI answered for a different registration than the one saved; nothing was replaced", code="client_mismatch")
        client_id = attempt.client_id
    elif not issued or issued == FIRST_CLIENT:
        raise PlanError("OpenAI did not issue a client for this registration; sign in again", code="registration_incomplete")
    else:
        client_id = issued
    if not query.get("code"):
        raise PlanError("the browser came back without an authorization code", code="no_code")
    if not attempt.client_id:
        with _locked(home):
            saved = load(home)
            if saved.get("client_id") and saved["client_id"] != client_id:
                raise PlanError("another sign-in finished for this profile meanwhile; nothing was replaced", code="superseded")
            # A failure after this point must not register alpi a second time on the next attempt.
            _save(home, {**saved, "issuer": ISSUER, "client_id": client_id})
    ended = load(home).get("ended", 0)
    tokens = _token_request({
        "grant_type": "authorization_code", "client_id": client_id, "code": query["code"],
        "code_verifier": attempt.verifier, "redirect_uri": attempt.redirect_uri, "resource": RESOURCE,
    })
    claims = verify_id_token(str(tokens.get("id_token") or ""), client_id=client_id, nonce=attempt.nonce, keys=keys)
    with _locked(home):
        saved = load(home)
        if saved.get("client_id") != client_id or saved.get("ended", 0) != ended:
            raise PlanError(_SIGNED_OUT_MEANWHILE, code="superseded")
        if attempt.client_id and saved.get("subject") and saved["subject"] != claims["sub"]:
            raise PlanError(
                f"the browser signed in a different ChatGPT account than the one saved ({saved.get('email') or 'unknown'}); "
                "sign out first (in the app, or `alpi chatgpt logout --forget`) to use another account",
                code="account_mismatch",
            )
        record = _with_tokens(
            {**saved, "issuer": ISSUER, "subject": claims["sub"], "email": str(claims.get("email") or ""), "client_id": client_id},
            tokens,
        )
        granted = PLAN_SCOPE in record["scopes"]
        first = granted and not saved.get("welcomed")
        record["welcomed"] = bool(saved.get("welcomed")) or granted
        _save(home, record)
    if granted:
        rows = _fetch_models(record["access_token"])
        with _locked(home):
            current = load(home)
            if current.get("access_token") != record["access_token"]:
                raise PlanError(_SIGNED_OUT_MEANWHILE, code="superseded")
            if rows:
                record = {**current, "models": rows}
                _save(home, record)
    return {**record, "first_sign_in": first}


def callback_answer(path: str, state: str) -> tuple[int, dict[str, str] | None, str]:
    parsed = urllib.parse.urlsplit(path)
    if parsed.path != CALLBACK_PATH:
        return 404, None, "Not found."
    query = {k: v[0] for k, v in urllib.parse.parse_qs(parsed.query).items()}
    if not secrets.compare_digest(query.get("state", "").encode(), state.encode()):
        # Any page or local process can reach this port; only the browser that carries this attempt's state ends it.
        return 400, None, "This is not the sign-in alpi is waiting for."
    if query.get("error"):
        return 200, query, "The sign-in was not completed. Go back to alpi."
    return 200, query, "You can close this tab and go back to alpi, which is finishing the sign-in."


def pasted_callback(text: str) -> dict[str, str]:
    text = text.strip()
    try:
        parsed = urllib.parse.urlsplit(text)
        text.encode()
    except ValueError as exc:
        raise PlanError("that is not an address; copy the whole address the browser ended on", code="not_a_callback") from exc
    if parsed.scheme and parsed.path != CALLBACK_PATH:
        raise PlanError("that is not the address the sign-in ended on; it starts with http://127.0.0.1 and has /auth/callback in it", code="not_a_callback")
    query = {k: v[0] for k, v in urllib.parse.parse_qs(parsed.query if parsed.scheme else text.lstrip("?")).items()}
    if not query.get("state") or not (query.get("code") or query.get("error")):
        raise PlanError("that address carries no sign-in answer; copy the whole address the browser ended on", code="not_a_callback")
    return query


_PENDING: dict[str, tuple[Attempt, float]] = {}
PENDING_S = 600


def begin_pending(home: Path, port: Any) -> Attempt:
    try:
        port = int(port)
    except (TypeError, ValueError, OverflowError) as exc:
        raise PlanError("the callback port must be a number", code="bad_port") from exc
    if not 1024 <= port <= 65535:
        raise PlanError("the callback port must be between 1024 and 65535", code="bad_port")
    attempt = begin(home, int(port))
    # One per profile: a second attempt replaces the first, whose answer then no longer matches any state.
    _PENDING[str(Path(home))] = (attempt, time.monotonic() + PENDING_S)
    return attempt


def finish_pending(home: Path, callback: str) -> dict[str, Any]:
    attempt, deadline = _PENDING.get(str(Path(home)), (None, 0.0))
    if attempt is None or time.monotonic() > deadline:
        _PENDING.pop(str(Path(home)), None)
        raise PlanError("no sign-in is waiting for this profile, or it expired; start again", code="no_attempt")
    query = pasted_callback(callback)
    if not secrets.compare_digest(str(query.get("state") or "").encode(), attempt.state.encode()):
        raise PlanError("that address belongs to another sign-in attempt; use the one this attempt ended on", code="state_mismatch")
    _PENDING.pop(str(Path(home)), None)
    return finish(home, attempt, query)


def give_a_model(home: Path) -> str:
    from alpi import config as cfg_mod

    rows = models(home)
    cfg = cfg_mod.load(home)
    if cfg.model or not rows:
        return ""
    # A profile with no model cannot take a turn; one that already has a model keeps it.
    cfg.model = f"{PREFIX}/{rows[0]['slug']}"
    cfg_mod.save(cfg)
    return cfg.model


def status(home: Path) -> dict[str, Any]:
    record = load(home)
    active = signed_in(home)
    return {
        "signed_in": active,
        "email": str(record.get("email") or "") if record.get("subject") else "",
        "plan_declined": bool(record.get("refresh_token")) and not active,
        "registered": bool(record.get("client_id")),
        "models": [f"{PREFIX}/{m['slug']}" for m in models(home)],
        "usage_url": USAGE_URL,
    }


class _Callback(http.server.BaseHTTPRequestHandler):
    timeout = 5

    def do_GET(self) -> None:  # noqa: N802
        status, query, text = callback_answer(self.path, self.server.state)  # type: ignore[attr-defined]
        if query is not None:
            self.server.query = query  # type: ignore[attr-defined]
        body = f"<!doctype html><title>alpi</title><p>{text}</p>".encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: Any) -> None:
        return


class _Listener(http.server.ThreadingHTTPServer):
    # A thread per connection: a client that sends its request one byte at a time cannot hold the wait past its deadline.
    daemon_threads = True

    def handle_error(self, request: Any, client_address: Any) -> None:
        return


def _listener() -> http.server.HTTPServer:
    for port in (CALLBACK_PORT, 0):
        try:
            return _Listener(("127.0.0.1", port), _Callback)
        except OSError:
            continue
    raise PlanError("could not open a local port for the sign-in callback", code="no_port")


def login(home: Path, *, show: Callable[[str], None], open_browser: bool = True, timeout: float = LOGIN_TIMEOUT_S) -> dict[str, Any]:
    server = _listener()
    server.query = None  # type: ignore[attr-defined]
    try:
        attempt = begin(home, server.server_address[1])
        server.state = attempt.state  # type: ignore[attr-defined]
        show(attempt.shown_url)
        if open_browser:
            import webbrowser

            webbrowser.open(attempt.url)
        deadline = time.monotonic() + timeout
        while server.query is None:  # type: ignore[attr-defined]
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise PlanError("no answer from the browser; the sign-in was abandoned", code="timeout")
            server.timeout = min(remaining, 1.0)
            server.handle_request()
        return finish(home, attempt, server.query)  # type: ignore[attr-defined]
    finally:
        server.server_close()


def access_token(home: Path, *, refused: str = "") -> str:
    record = load(home)
    if not record.get("refresh_token") and not record.get("access_token"):
        raise NotSignedIn()
    if PLAN_SCOPE not in (record.get("scopes") or []):
        raise NotSignedIn("this ChatGPT sign-in does not allow plan usage; run `alpi chatgpt login` and accept it")
    if _fresh(record) and record.get("access_token") != refused:
        return str(record["access_token"])
    with _locked(home):
        # Refresh tokens rotate: a second process must read what the first one saved instead of spending the old one.
        record = load(home)
        if _fresh(record) and record.get("access_token") != refused:
            return str(record["access_token"])
        if not record.get("refresh_token"):
            raise NotSignedIn("the ChatGPT sign-in has expired; run `alpi chatgpt login`")
        try:
            tokens = _token_request({
                "grant_type": "refresh_token", "client_id": str(record.get("client_id") or ""),
                "refresh_token": str(record["refresh_token"]), "resource": RESOURCE,
            })
        except PlanError as exc:
            if exc.code in _UNUSABLE_REFRESH:
                _save(home, {k: v for k, v in record.items() if k not in ("access_token", "refresh_token")})
                raise NotSignedIn("the ChatGPT sign-in is no longer valid; run `alpi chatgpt login`") from exc
            raise
        record = _with_tokens(record, tokens)
        _save(home, record)
        return str(record["access_token"])


def _fresh(record: dict[str, Any]) -> bool:
    try:
        expires_at = float(record.get("saved_at") or 0) + float(record.get("expires_in") or 0)
    except (TypeError, ValueError):
        return False
    return bool(record.get("access_token")) and expires_at - time.time() > _REFRESH_SKEW_S


def refresh_models(home: Path) -> list[dict[str, str]]:
    token = access_token(home)
    rows = _fetch_models(token)
    with _locked(home):
        record = load(home)
        if rows and record:
            record["models"] = rows
            _save(home, record)
    return rows


def logout(home: Path, *, forget: bool = False) -> bool:
    _PENDING.pop(str(Path(home)), None)
    if not record_path(home).exists():
        return True
    with _locked(home):
        record = load(home)
        if not record:
            return True
        revoked = not record.get("refresh_token")
        if record.get("refresh_token"):
            try:
                with httpx.Client(timeout=30.0) as client:
                    endpoint = client.get(DISCOVERY_URL).raise_for_status().json()["revocation_endpoint"]
                    revoked = client.post(endpoint, data={
                        "token": record["refresh_token"], "token_type_hint": "refresh_token", "client_id": record.get("client_id") or "",
                    }).status_code == 200
            except Exception:  # noqa: BLE001
                revoked = False
        if forget:
            record_path(home).unlink(missing_ok=True)
        else:
            # The registration and the account it belongs to stay, so the next sign-in reuses the issued client.
            kept = {k: v for k, v in record.items() if k not in ("access_token", "refresh_token", "id_token", "models")}
            _save(home, {**kept, "ended": int(record.get("ended", 0)) + 1})
        return revoked


class ChatGPTPlan(Provider):
    name = PREFIX
    display = "ChatGPT plan"
    api_key_env = ""
    description = "your ChatGPT plan, with Sign in with ChatGPT"

    def has_key(self, env: dict[str, str] | None = None) -> bool:
        from alpi.home import get_home

        return signed_in(get_home())

    def list_models(self) -> list[ModelInfo]:
        from alpi.home import get_home

        return [ModelInfo(id=f"{PREFIX}/{m['slug']}", display=m["display_name"]) for m in models(get_home())]


def capability_id(model: str) -> str:
    return "openai/" + model.split("/", 1)[1] if model.startswith(PREFIX + "/") else model
