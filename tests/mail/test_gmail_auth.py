"""Unit tests for the split prepare/exchange OAuth flow."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from alpi.mail import gmail_auth


def _seed_creds(home: Path) -> None:
    home.mkdir(parents=True, exist_ok=True)
    (home / ".env").write_text(
        "GMAIL_CLIENT_ID=cid-123\nGMAIL_CLIENT_SECRET=sec-456\n"
    )


def test_prepare_returns_auth_url_and_pkce(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("GMAIL_CLIENT_ID", raising=False)
    monkeypatch.delenv("GMAIL_CLIENT_SECRET", raising=False)
    _seed_creds(tmp_path)
    handle = gmail_auth.prepare(tmp_path, redirect_uri="http://127.0.0.1:42")

    assert handle.redirect_uri == "http://127.0.0.1:42"
    assert handle.auth_url.startswith(
        "https://accounts.google.com/o/oauth2/v2/auth?"
    )
    assert "client_id=cid-123" in handle.auth_url
    assert "redirect_uri=http%3A%2F%2F127.0.0.1%3A42" in handle.auth_url
    assert "code_challenge_method=S256" in handle.auth_url
    assert f"state={handle.state}" in handle.auth_url
    # PKCE verifier: ≥43 chars, ≤128, urlsafe.
    assert 43 <= len(handle.code_verifier) <= 128


def test_prepare_raises_when_creds_missing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("GMAIL_CLIENT_ID", raising=False)
    monkeypatch.delenv("GMAIL_CLIENT_SECRET", raising=False)
    tmp_path.mkdir(parents=True, exist_ok=True)
    with pytest.raises(gmail_auth.GmailAuthError):
        gmail_auth.prepare(tmp_path, redirect_uri="http://127.0.0.1:1")


def test_exchange_posts_code_and_persists_token(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("GMAIL_CLIENT_ID", raising=False)
    monkeypatch.delenv("GMAIL_CLIENT_SECRET", raising=False)
    _seed_creds(tmp_path)

    captured: list[dict] = []

    class FakeResp:
        def __init__(self, status: int, data: dict) -> None:
            self.status_code = status
            self._data = data
            self.text = json.dumps(data)

        def json(self) -> dict:
            return self._data

    class FakeClient:
        def __init__(self, *a, **kw) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, url, data):
            captured.append({"post": url, "data": data})
            return FakeResp(200, {
                "access_token": "AT-xyz",
                "refresh_token": "RT-abc",
                "expires_in": 3600,
            })

        def get(self, url, headers):
            captured.append({"get": url, "headers": headers})
            return FakeResp(200, {"email": "alice@example.com"})

    monkeypatch.setattr(gmail_auth.httpx, "Client", FakeClient)

    token = gmail_auth.exchange(
        tmp_path,
        "alice_example_com",
        code="code-from-google",
        code_verifier="verifier-abc",
        redirect_uri="http://127.0.0.1:42",
    )

    assert token.email == "alice@example.com"
    assert token.access_token == "AT-xyz"
    assert token.refresh_token == "RT-abc"

    # Token persisted on disk at the per-account path.
    stored = json.loads(
        (tmp_path / "secrets" / "gmail_tokens" / "alice_example_com.json").read_text()
    )
    assert stored["email"] == "alice@example.com"
    assert stored["refresh_token"] == "RT-abc"

    post_body = next(c["data"] for c in captured if "post" in c)
    assert post_body["code"] == "code-from-google"
    assert post_body["code_verifier"] == "verifier-abc"
    assert post_body["redirect_uri"] == "http://127.0.0.1:42"
    assert post_body["client_id"] == "cid-123"
    assert post_body["client_secret"] == "sec-456"


def test_exchange_rejects_when_no_refresh_token(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("GMAIL_CLIENT_ID", raising=False)
    monkeypatch.delenv("GMAIL_CLIENT_SECRET", raising=False)
    _seed_creds(tmp_path)

    class FakeResp:
        status_code = 200
        text = "{}"

        def json(self):
            return {"access_token": "AT", "expires_in": 3600}

    class FakeClient:
        def __init__(self, *a, **kw) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, *a, **kw):
            return FakeResp()

        def get(self, *a, **kw):
            return FakeResp()

    monkeypatch.setattr(gmail_auth.httpx, "Client", FakeClient)
    with pytest.raises(gmail_auth.GmailAuthError, match="no refresh_token"):
        gmail_auth.exchange(
            tmp_path, "acc", code="c", code_verifier="v",
            redirect_uri="http://127.0.0.1:1",
        )


def test_first_run_paste_parses_callback_url(
    tmp_path: Path, monkeypatch,
) -> None:
    monkeypatch.delenv("GMAIL_CLIENT_ID", raising=False)
    monkeypatch.delenv("GMAIL_CLIENT_SECRET", raising=False)
    _seed_creds(tmp_path)

    fake_token = gmail_auth.GmailToken(
        email="bob@example.com", access_token="AT", refresh_token="RT",
        expires_at=1e12,
    )

    def fake_exchange(home, account_id, *, code, code_verifier, redirect_uri):
        assert code == "the-code"
        return fake_token

    monkeypatch.setattr(gmail_auth, "exchange", fake_exchange)

    # Capture the prepared handle so we can echo the same state back in
    # the pasted URL.
    captured_state: dict = {}
    real_prepare = gmail_auth.prepare

    def wrap_prepare(home, *, redirect_uri):
        h = real_prepare(home, redirect_uri=redirect_uri)
        captured_state["state"] = h.state
        return h

    monkeypatch.setattr(gmail_auth, "prepare", wrap_prepare)
    monkeypatch.setattr(
        "builtins.input",
        lambda *_a, **_kw: f"http://127.0.0.1:55555/?code=the-code&state={captured_state['state']}",
    )

    token = gmail_auth.first_run_paste(tmp_path)
    assert token.email == "bob@example.com"


def test_first_run_paste_rejects_state_mismatch(
    tmp_path: Path, monkeypatch,
) -> None:
    monkeypatch.delenv("GMAIL_CLIENT_ID", raising=False)
    monkeypatch.delenv("GMAIL_CLIENT_SECRET", raising=False)
    _seed_creds(tmp_path)

    monkeypatch.setattr(
        "builtins.input",
        lambda *_a, **_kw: "http://127.0.0.1:1/?code=c&state=WRONG",
    )
    with pytest.raises(gmail_auth.GmailAuthError, match="state mismatch"):
        gmail_auth.first_run_paste(tmp_path)


def test_first_run_paste_rejects_when_no_code(
    tmp_path: Path, monkeypatch,
) -> None:
    monkeypatch.delenv("GMAIL_CLIENT_ID", raising=False)
    monkeypatch.delenv("GMAIL_CLIENT_SECRET", raising=False)
    _seed_creds(tmp_path)

    monkeypatch.setattr(
        "builtins.input",
        lambda *_a, **_kw: "http://127.0.0.1:1/?state=anything",
    )
    with pytest.raises(gmail_auth.GmailAuthError, match="no `code`"):
        gmail_auth.first_run_paste(tmp_path)


def test_first_run_paste_propagates_oauth_error(
    tmp_path: Path, monkeypatch,
) -> None:
    monkeypatch.delenv("GMAIL_CLIENT_ID", raising=False)
    monkeypatch.delenv("GMAIL_CLIENT_SECRET", raising=False)
    _seed_creds(tmp_path)

    monkeypatch.setattr(
        "builtins.input",
        lambda *_a, **_kw: "http://127.0.0.1:1/?error=access_denied",
    )
    with pytest.raises(gmail_auth.GmailAuthError, match="access_denied"):
        gmail_auth.first_run_paste(tmp_path)


def test_first_run_falls_back_to_paste_when_browser_open_fails(
    tmp_path: Path, monkeypatch,
) -> None:
    monkeypatch.delenv("GMAIL_CLIENT_ID", raising=False)
    monkeypatch.delenv("GMAIL_CLIENT_SECRET", raising=False)
    _seed_creds(tmp_path)

    monkeypatch.setattr(gmail_auth.webbrowser, "open", lambda url: False)

    sentinel = gmail_auth.GmailToken(
        email="cara@example.com", access_token="AT",
        refresh_token="RT", expires_at=1e12,
    )

    def fake_paste(home, account_id, handle, port):
        return sentinel

    monkeypatch.setattr(gmail_auth, "_paste_flow", fake_paste)

    assert gmail_auth.first_run(tmp_path) is sentinel
