"""Best-effort redaction before session JSON serialization."""

from __future__ import annotations

import time

import pytest

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


def test_a_megabyte_of_scheme_like_text_redacts_quickly() -> None:
    for text in ("a" * 1_000_000, "ab+" * 333_000, "a.b-" * 250_000):
        started = time.perf_counter()
        assert redact(text) == text
        assert time.perf_counter() - started < 1.0


def test_a_credential_url_after_a_long_run_of_scheme_characters_still_loses_its_userinfo() -> None:
    out = redact("x" * 5000 + "https://alice:s3cr3t@host/p")
    assert "s3cr3t" not in out and "alice" not in out
    assert out.endswith("https://[REDACTED]@host/p")
    for run in ("a" + "1" * 32, "a" + "." * 40, "a" + "-" * 33, "a" + "+" * 100, "1" * 40):
        out = redact(f"{run}://alice:s3cr3t@host/p")
        assert "s3cr3t" not in out and "alice" not in out
        assert out.endswith("://[REDACTED]@host/p")


def test_pem_private_key_block_redacted() -> None:
    pem = (
        "-----BEGIN OPENSSH PRIVATE KEY-----\n"
        "b3BlbnNzaC1rZXktdjEAAAAA...\nmoremoremore\n"
        "-----END OPENSSH PRIVATE KEY-----"
    )
    assert redact(f"key:\n{pem}\ndone") == "key:\n[REDACTED]\ndone"


def test_repeated_pem_markers_without_an_end_redact_quickly() -> None:
    for text in (
        "-----BEGIN RSA PRIVATE KEY-----\n" * 32_000,
        "-----BEGIN PRIVATE KEY-----\n-----END PUBLIC KEY-----\n" * 20_000,
    ):
        started = time.perf_counter()
        assert redact(text) == text
        assert time.perf_counter() - started < 1.0


def test_pem_blocks_redact_whole_with_or_without_headers_and_around_other_text() -> None:
    plain = "-----BEGIN PRIVATE KEY-----\nMIIE+/=\n-----END PRIVATE KEY-----"
    headed = "-----BEGIN RSA PRIVATE KEY-----\nProc-Type: 4,ENCRYPTED\nDEK-Info: AES\n\nMIIE\n-----END RSA PRIVATE KEY-----"
    assert redact(f"a {plain} b {headed} c") == f"a {_REDACTED} b {_REDACTED} c"
    assert redact(f"-----BEGIN PRIVATE KEY-----\n{plain}") == _REDACTED
    assert redact("-----BEGIN PRIVATE KEY-----\nMIIE\n-----END RSA PRIVATE KEY-----") == _REDACTED


def test_a_pem_begin_without_an_end_and_public_keys_pass_through() -> None:
    text = "-----BEGIN PRIVATE KEY-----\nMIIE truncated"
    assert redact(text) == text
    public = "-----BEGIN PUBLIC KEY-----\nMIIB\n-----END PUBLIC KEY-----"
    assert redact(public) == public


def test_attachment_metadata_redacted_recursively() -> None:
    out = redact([{"name": "sk-1234567890abcdefABCDEF.png", "size": 10, "mime": "image/png"}])
    assert out == [{"name": "[REDACTED].png", "size": 10, "mime": "image/png"}]


@pytest.mark.parametrize("text,secret", [
    ("jwt eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.SflKxwRJSMeKKF2QT4fwpMeJf36", "SflKxwRJSMeKKF2QT4fwpMeJf36"),
    ("Authorization: Bearer abcdefghijklmnop1234567890", "abcdefghijklmnop1234567890"),
    ("google ya29.a0AfH6SMBx1234567890abcdefghij", "a0AfH6SMBx1234567890abcdefghij"),
    ("refresh 1//0gAbCdEfGhIjKlMnOpQrStUv", "gAbCdEfGhIjKlMnOpQrStUv"),
    ("github_pat_11ABCDEFG0123456789_abcdefghijkl", "11ABCDEFG0123456789_abcdefghijkl"),
    ("gitlab glpat-abcdefghij0123456789", "abcdefghij0123456789"),
    ("groq gsk_abcdefghijklmnopqrstuvwxyz0123", "abcdefghijklmnopqrstuvwxyz0123"),
    ("https://x/cb?access_token=abcdefghijklmnopqrst&state=1", "abcdefghijklmnopqrst"),
    ("https://x/?api_key=0123456789abcdefghij", "0123456789abcdefghij"),
    ("Cookie: session=abc123; csrf=def456", "session=abc123; csrf=def456"),
    ("GET /\nSet-Cookie: sid=abcdef; HttpOnly", "sid=abcdef"),
    ("x-api-key: k-0123456789abcdefgh", "k-0123456789abcdefgh"),
    ('{"Cookie": "session=abcdef0123"}', "session=abcdef0123"),
    ('{"x-api-key": "abcdef0123456789abcdef"}', "abcdef0123456789abcdef"),
    ("Authorization: Basic dXNlcjpwYXNzd29yZA==", "dXNlcjpwYXNzd29yZA"),
    ("https://x/cb?id_token=abcdefghijklmnopqrst", "abcdefghijklmnopqrst"),
    ("client_secret=abcdefghijklmnopqrst", "abcdefghijklmnopqrst"),
    ("2026-10-29 INFO alpi.x Cookie: session=abc123; csrf=def456", "session=abc123"),
    ("cmd='curl -H Cookie: sid=abcdef0123 https://x'", "sid=abcdef0123"),
    ("INFO hdr x-api-key: k-0123456789abcdefgh", "k-0123456789abcdefgh"),
])
def test_audit_secret_shapes_are_redacted(text: str, secret: str) -> None:
    out = redact(text)
    assert secret not in out
    assert _REDACTED in out


def test_pgp_private_key_block_redacted() -> None:
    block = (
        "-----BEGIN PGP PRIVATE KEY BLOCK-----\nlQOYBF0AAAAB\n"
        "-----END PGP PRIVATE KEY BLOCK-----"
    )
    assert redact(f"key:\n{block}\nend") == f"key:\n{_REDACTED}\nend"


@pytest.mark.parametrize("text", [
    "max_tokens=4096 and csrf_token=abcdefghijklmnopqrstu",
    "the bearer of bad news",
    "eyJ is a prefix",
    "PGP PUBLIC KEY BLOCK stays",
    "const cookie = document.cookie.split(';')",
    "self.cookie: str = ''",
    "cookie = request.cookies.get('sid')",
    "## Cookie: banner copy updated, legal approved, ship Monday",
    "we fixed the Set-Cookie: SameSite bug in 3 services",
    "Bearer tokens/credentials/refresh are rotated weekly",
    "x-api-key: required header",
    "Basic internationalization support",
])
def test_ordinary_text_is_untouched(text: str) -> None:
    assert redact(text) == text


def test_http_credential_headers_in_dicts_are_redacted() -> None:
    frame = {"output": {"headers": {
        "Cookie": "sid=abcdef0123", "X-Api-Key": "k-0123456789abcdefgh",
        "Authorization": "Bearer abc", "Content-Type": "application/json",
    }}}
    headers = redact(frame)["output"]["headers"]
    assert headers["Cookie"] == headers["X-Api-Key"] == headers["Authorization"] == _REDACTED
    assert headers["Content-Type"] == "application/json"


def test_generic_secret_names_still_pass_through() -> None:
    assert redact({"token_count": "12", "cookie_banner": "shown"}) == {"token_count": "12", "cookie_banner": "shown"}
