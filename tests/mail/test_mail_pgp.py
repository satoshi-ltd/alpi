"""PGP signing + encryption on the IMAP/Gmail outbound path
(roadmap: Email PGP). Mocks the ``gnupg.GPG`` backend so tests don't
need a real keyring; verifies the MIME wrapping shape, opt-in
behaviour, and graceful fallthrough on failure paths.
"""

from __future__ import annotations

from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from pathlib import Path

import pytest

from alpi.mail import pgp


def _build_msg(to: str = "alice@example.com", body: str = "hello") -> EmailMessage:
    m = EmailMessage(policy=policy.SMTP)
    m["From"] = "me@example.com"
    m["To"] = to
    m["Subject"] = "test"
    m.set_content(body)
    return m


class _FakeSig:
    def __init__(self, text: str = "-----BEGIN PGP SIGNATURE-----\nABC\n-----END PGP SIGNATURE-----\n"):
        self.text = text

    def __str__(self) -> str:
        return self.text

    def __bool__(self) -> bool:
        return True


class _FakeCipher:
    def __init__(self, ok: bool = True, text: str = "-----BEGIN PGP MESSAGE-----\nXYZ\n-----END PGP MESSAGE-----\n"):
        self.ok = ok
        self.text = text

    def __str__(self) -> str:
        return self.text


class _FakeDecrypt:
    def __init__(self, data: bytes):
        self.data = data

    def __bool__(self) -> bool:
        return bool(self.data)


class _FakeGPG:
    def __init__(self, *, have_keys: list[str] | None = None,
                 sign_result: _FakeSig | None = None,
                 encrypt_result: _FakeCipher | None = None,
                 decrypt_result: _FakeDecrypt | None = None) -> None:
        self.have_keys = have_keys or []
        self.sign_result = sign_result if sign_result is not None else _FakeSig()
        self.encrypt_result = encrypt_result
        self.decrypt_result = decrypt_result
        self.calls: list[tuple] = []

    def list_keys(self, keys=None):
        if keys and any(k in self.have_keys for k in keys):
            return [{"fingerprint": "X" * 40}]
        return []

    def sign(self, payload, *, keyid, detach=True, clearsign=False):
        self.calls.append(("sign", keyid, detach, clearsign))
        return self.sign_result

    def encrypt(self, payload, *, recipients, sign, always_trust):
        self.calls.append(("encrypt", tuple(recipients), sign))
        return self.encrypt_result

    def decrypt(self, payload):
        return self.decrypt_result


def _set_config(monkeypatch: pytest.MonkeyPatch, signing_key: str = "",
                encrypt: bool = False) -> None:
    monkeypatch.setattr(pgp, "_config", lambda: (signing_key, encrypt))


def _set_gpg(monkeypatch: pytest.MonkeyPatch, gpg: _FakeGPG | None) -> None:
    if gpg is None:
        def _raise():
            raise RuntimeError("no gpg")
        monkeypatch.setattr(pgp, "_gpg", _raise)
    else:
        monkeypatch.setattr(pgp, "_gpg", lambda: gpg)


def test_no_signing_key_is_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_config(monkeypatch, signing_key="")
    msg = _build_msg()
    out = pgp.maybe_sign_and_encrypt(msg)
    assert out is msg
    assert "multipart" not in out.get_content_type()


def test_sign_only_when_no_recipient_pubkey(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_config(monkeypatch, signing_key="0xABC", encrypt=True)
    _set_gpg(monkeypatch, _FakeGPG(have_keys=[]))
    out = pgp.maybe_sign_and_encrypt(_build_msg())
    ctype = out.get_content_type()
    assert ctype == "multipart/signed"
    assert out.get_param("protocol") == "application/pgp-signature"
    parts = list(out.iter_parts())
    assert len(parts) == 2
    assert parts[1].get_content_type() == "application/pgp-signature"


def test_encrypt_when_pubkey_available(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_config(monkeypatch, signing_key="0xABC", encrypt=True)
    _set_gpg(monkeypatch, _FakeGPG(
        have_keys=["alice@example.com"],
        encrypt_result=_FakeCipher(ok=True),
    ))
    out = pgp.maybe_sign_and_encrypt(_build_msg())
    assert out.get_content_type() == "multipart/encrypted"
    assert out.get_param("protocol") == "application/pgp-encrypted"
    parts = list(out.iter_parts())
    assert parts[0].get_content_type() == "application/pgp-encrypted"
    assert parts[1].get_content_type() == "application/octet-stream"


def test_encrypt_off_means_sign_only(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_config(monkeypatch, signing_key="0xABC", encrypt=False)
    _set_gpg(monkeypatch, _FakeGPG(have_keys=["alice@example.com"]))
    out = pgp.maybe_sign_and_encrypt(_build_msg())
    assert out.get_content_type() == "multipart/signed"


def test_routing_headers_preserved(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_config(monkeypatch, signing_key="0xABC", encrypt=False)
    _set_gpg(monkeypatch, _FakeGPG(have_keys=[]))
    msg = _build_msg()
    msg["Message-Id"] = "<abc@x>"
    msg["Cc"] = "bob@example.com"
    out = pgp.maybe_sign_and_encrypt(msg)
    assert out["From"] == "me@example.com"
    assert out["To"] == "alice@example.com"
    assert out["Cc"] == "bob@example.com"
    assert out["Subject"] == "test"
    assert out["Message-Id"] == "<abc@x>"


def test_gpg_unavailable_is_passthrough(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_config(monkeypatch, signing_key="0xABC", encrypt=True)
    _set_gpg(monkeypatch, None)
    msg = _build_msg()
    out = pgp.maybe_sign_and_encrypt(msg)
    assert out is msg


def test_decrypt_unwraps_pgp_mime(monkeypatch: pytest.MonkeyPatch) -> None:
    inner_bytes = (
        b"Content-Type: text/plain; charset=utf-8\r\n"
        b"Content-Transfer-Encoding: 7bit\r\n"
        b"\r\n"
        b"the secret\r\n"
    )
    _set_config(monkeypatch, signing_key="0xABC")
    _set_gpg(monkeypatch, _FakeGPG(decrypt_result=_FakeDecrypt(inner_bytes)))
    fake_encrypted = _FakeCipher(ok=True)
    encrypted = pgp._build_encrypted(_build_msg(), str(fake_encrypted))
    out = pgp.maybe_decrypt(encrypted)
    assert out.get_content_type() == "text/plain"
    payload = out.get_payload()
    assert "the secret" in (payload if isinstance(payload, str) else "")


def test_decrypt_noop_on_plain_message(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_config(monkeypatch, signing_key="0xABC")
    _set_gpg(monkeypatch, _FakeGPG())
    msg = _build_msg()
    out = pgp.maybe_decrypt(msg)
    assert out is msg


def test_decrypt_falls_through_on_no_secret_key(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_config(monkeypatch, signing_key="0xABC")
    _set_gpg(monkeypatch, _FakeGPG(decrypt_result=_FakeDecrypt(b"")))
    encrypted = pgp._build_encrypted(_build_msg(), "BLOB")
    out = pgp.maybe_decrypt(encrypted)
    assert out.get_content_type() == "multipart/encrypted"


def test_decrypt_disabled_when_no_signing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_config(monkeypatch, signing_key="")
    encrypted = pgp._build_encrypted(_build_msg(), "BLOB")
    out = pgp.maybe_decrypt(encrypted)
    assert out is encrypted
