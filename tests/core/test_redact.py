"""Best-effort redaction before session JSON serialization."""

from __future__ import annotations

from alpi._redact import redact, _REDACTED


def test_short_legit_password_passes_through() -> None:
    # Key-name based redaction is OFF: legit values don't get clobbered.
    out = redact({"password": "hunter2", "username": "alice"})
    assert out == {"password": "hunter2", "username": "alice"}


def test_openai_key_inside_value_redacted_regardless_of_key() -> None:
    # The KEY name is irrelevant; the VALUE pattern is what matches.
    out = redact({"any_field": "sk-1234567890abcdefABCDEF"})
    assert out["any_field"] == _REDACTED


def test_openai_key_pattern_in_string() -> None:
    text = "running with key sk-1234567890abcdefABCDEF for the model"
    out = redact(text)
    assert "sk-" not in out
    assert _REDACTED in out


def test_github_token_pattern() -> None:
    text = "ghp_aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789"
    assert redact(text) == _REDACTED


def test_google_api_key_pattern() -> None:
    text = "AIzaSyDABCDEFGhiJKLMNOPQRSTUVWXYZ123456789"
    assert redact(text) == _REDACTED


def test_telegram_bot_token_pattern() -> None:
    text = "1234567890:ABCDEFghijklmnopqrstuvwxyz0123456789"
    assert redact(text) == _REDACTED


def test_nested_structures_redacted_by_value() -> None:
    payload = {
        "tool": "email_send",
        "args": {
            "recipients": ["alice@x.com"],
            "subject": "hi",
            "body": "find token sk-abcdefghijklmnopqr in this body",
            "note": "ghp_aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789",
        },
    }
    out = redact(payload)
    assert out["args"]["recipients"] == ["alice@x.com"]
    assert out["args"]["subject"] == "hi"
    assert "sk-" not in out["args"]["body"]
    assert out["args"]["note"] == _REDACTED


def test_non_secret_passes_through() -> None:
    payload = {"path": "/Users/javi/file.txt", "lines": [1, 2, 3]}
    assert redact(payload) == payload


def test_short_strings_not_falsely_matched() -> None:
    # "sk-" alone (no key body) shouldn't trip the key pattern.
    assert redact("sk-12") == "sk-12"


def test_credential_url_keeps_scheme_drops_userinfo() -> None:
    out = redact("clone https://alice:s3cr3t@github.com/x.git now")
    assert out == "clone https://[REDACTED]@github.com/x.git now"
    out2 = redact("postgres://admin:pw@db.internal:5432/app")
    assert out2 == "postgres://[REDACTED]@db.internal:5432/app"


def test_url_without_userinfo_passes_through() -> None:
    assert redact("see https://example.com/path?x=1") == "see https://example.com/path?x=1"


def test_pem_private_key_block_redacted() -> None:
    pem = (
        "-----BEGIN OPENSSH PRIVATE KEY-----\n"
        "b3BlbnNzaC1rZXktdjEAAAAA...\nmoremoremore\n"
        "-----END OPENSSH PRIVATE KEY-----"
    )
    assert redact(f"key:\n{pem}\ndone") == "key:\n[REDACTED]\ndone"


def test_attachment_metadata_redacted_recursively() -> None:
    out = redact([{"name": "sk-1234567890abcdefABCDEF.png", "size": 10, "mime": "image/png"}])
    assert out == [{"name": "[REDACTED].png", "size": 10, "mime": "image/png"}]
