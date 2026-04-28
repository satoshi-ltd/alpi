"""PGP signing + encryption for the IMAP/Gmail outbound path
(roadmap: Email PGP). Opt-in via per-profile ``email`` config:

    email:
      signing_key: 0xABCD1234DEADBEEF
      encrypt_when_pubkey_available: true

When ``signing_key`` is absent the entire module is a no-op and the
mail path stays plaintext. The crypto backend is the user's existing
``~/.gnupg`` keyring via ``python-gnupg``; we never own keys.
"""

from __future__ import annotations

from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import getaddresses


def _config() -> tuple[str, bool]:
    """Return ``(signing_key, encrypt_when_pubkey_available)`` for the
    active profile, or ``("", False)`` if PGP is not configured."""
    try:
        from alpi import config as cfg_mod, home as home_mod
        cfg = cfg_mod.load(home_mod.get_home())
    except Exception:
        return ("", False)
    raw = cfg.raw.get("email") or {}
    return (
        str(raw.get("signing_key") or "").strip(),
        bool(raw.get("encrypt_when_pubkey_available") or False),
    )


def _gpg():
    import gnupg
    return gnupg.GPG()


def _recipient_addrs(*headers: str | None) -> list[str]:
    out: list[str] = []
    for h in headers:
        if not h:
            continue
        for _, addr in getaddresses([h]):
            if addr and addr not in out:
                out.append(addr)
    return out


def _have_pubkey(gpg, addr: str) -> bool:
    keys = gpg.list_keys(keys=[addr])
    return bool(keys)


def _payload_part(msg: EmailMessage) -> EmailMessage:
    """Strip routing headers — the inner part that gets signed/encrypted
    must carry only Content-* headers per RFC 3156."""
    inner = EmailMessage(policy=policy.SMTP)
    for k, v in msg.items():
        if k.lower().startswith("content-") or k.lower() == "mime-version":
            inner[k] = v
    inner.set_payload(msg.get_payload())
    if not inner.get_content_type():
        inner["Content-Type"] = msg.get_content_type()
    return inner


def _build_signed(msg: EmailMessage, signature_ascii: str) -> EmailMessage:
    out = EmailMessage(policy=policy.SMTP)
    for k, v in msg.items():
        if k.lower().startswith("content-") or k.lower() == "mime-version":
            continue
        out[k] = v
    out.make_mixed()
    # Replace top type with signed; preserve micalg per RFC 3156.
    out.replace_header("Content-Type", "multipart/signed")
    out.set_param("protocol", "application/pgp-signature")
    out.set_param("micalg", "pgp-sha256")
    body_part = _payload_part(msg)
    sig_part = EmailMessage(policy=policy.SMTP)
    sig_part["Content-Type"] = 'application/pgp-signature; name="signature.asc"'
    sig_part["Content-Description"] = "OpenPGP digital signature"
    sig_part["Content-Disposition"] = 'attachment; filename="signature.asc"'
    sig_part.set_payload(signature_ascii)
    out.set_payload([body_part, sig_part])
    return out


def _build_encrypted(msg: EmailMessage, ciphertext_ascii: str) -> EmailMessage:
    out = EmailMessage(policy=policy.SMTP)
    for k, v in msg.items():
        if k.lower().startswith("content-") or k.lower() == "mime-version":
            continue
        out[k] = v
    out["Content-Type"] = (
        'multipart/encrypted; protocol="application/pgp-encrypted"'
    )
    version_part = EmailMessage(policy=policy.SMTP)
    version_part["Content-Type"] = "application/pgp-encrypted"
    version_part["Content-Description"] = "PGP/MIME version identification"
    version_part.set_payload("Version: 1\n")
    cipher_part = EmailMessage(policy=policy.SMTP)
    cipher_part["Content-Type"] = 'application/octet-stream; name="encrypted.asc"'
    cipher_part["Content-Description"] = "OpenPGP encrypted message"
    cipher_part["Content-Disposition"] = 'inline; filename="encrypted.asc"'
    cipher_part.set_payload(ciphertext_ascii)
    out.set_payload([version_part, cipher_part])
    return out


def maybe_sign_and_encrypt(msg: EmailMessage) -> EmailMessage:
    """No-op if PGP is not configured. Otherwise sign with the
    configured key, and additionally encrypt when every recipient has
    a public key on the local keyring (and the encrypt knob is on)."""
    signing_key, want_encrypt = _config()
    if not signing_key:
        return msg
    try:
        gpg = _gpg()
    except Exception:
        return msg
    recipients = _recipient_addrs(msg.get("To"), msg.get("Cc"), msg.get("Bcc"))
    payload = _payload_part(msg).as_bytes()

    if want_encrypt and recipients and all(_have_pubkey(gpg, r) for r in recipients):
        result = gpg.encrypt(
            payload, recipients=recipients, sign=signing_key, always_trust=True,
        )
        if result.ok and str(result):
            return _build_encrypted(msg, str(result))

    sig = gpg.sign(payload, keyid=signing_key, detach=True, clearsign=False)
    if not sig or not str(sig):
        return msg
    return _build_signed(msg, str(sig))


def maybe_decrypt(msg: EmailMessage) -> EmailMessage:
    """If ``msg`` is ``multipart/encrypted`` (PGP/MIME) and we hold a
    secret key that can open it, return the decrypted message. Falls
    through to the original on any failure so the agent always sees
    *something* — silent breakage hurts more than a visible blob."""
    signing_key, _ = _config()
    if not signing_key:
        return msg
    if msg.get_content_type() != "multipart/encrypted":
        return msg
    parts = list(msg.iter_parts()) if msg.is_multipart() else []
    cipher_part = next(
        (p for p in parts if p.get_content_type() == "application/octet-stream"),
        None,
    )
    if cipher_part is None:
        return msg
    payload = cipher_part.get_payload(decode=True)
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    if not payload:
        return msg
    try:
        gpg = _gpg()
        decrypted = gpg.decrypt(payload)
    except Exception:
        return msg
    if not decrypted or not decrypted.data:
        return msg
    try:
        inner = BytesParser(policy=policy.default).parsebytes(decrypted.data)
    except Exception:
        return msg
    out = EmailMessage(policy=policy.default)
    for k, v in msg.items():
        if k.lower().startswith("content-") or k.lower() == "mime-version":
            continue
        out[k] = v
    for k, v in inner.items():
        if k.lower().startswith("content-") or k.lower() == "mime-version":
            out[k] = v
    out.set_payload(inner.get_payload())
    return out
