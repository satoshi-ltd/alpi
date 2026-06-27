"""Per-profile Ed25519 keypair for ALP.

One keypair per profile at ``~/.alpi/<profile>/secrets/alp_key.{pem,pub}``.
The base64 of the public key IS the cryptographic identity;
``peers.yaml`` pins it verbatim. Rotation is manual — generating a
new pair invalidates every peer relationship that pinned the old
one, by design.
"""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


_ALP_DIR = "alp"
_KEY_DIR = "secrets"
_PRIVATE = "alp_key.pem"
_PUBLIC = "alp_key.pub"


@dataclass(frozen=True)
class Keypair:
    """A loaded ALP identity. Never logs the private key."""
    private: Ed25519PrivateKey
    public: Ed25519PublicKey

    def pubkey_b64(self) -> str:
        """Canonical base64 form — exactly what appears in ``peers.yaml``."""
        raw = self.public.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        return base64.b64encode(raw).decode("ascii")

    def sign(self, payload: bytes) -> bytes:
        return self.private.sign(payload)


def _secrets_dir(home: Path) -> Path:
    return home / _ALP_DIR / _KEY_DIR


def private_path(home: Path) -> Path:
    return _secrets_dir(home) / _PRIVATE


def public_path(home: Path) -> Path:
    return _secrets_dir(home) / _PUBLIC


def exists(home: Path) -> bool:
    return private_path(home).exists() and public_path(home).exists()


def generate(home: Path) -> Keypair:
    """Create a fresh keypair and persist it with the right modes.

    Overwrites any existing pair — callers who need "generate only
    if missing" must check ``exists(home)`` first.
    """
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key()

    d = _secrets_dir(home)
    d.mkdir(parents=True, exist_ok=True)

    priv_pem = priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub_pem = pub.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    from alpi.secrets_io import safe_write_secret
    safe_write_secret(private_path(home), priv_pem)
    public_path(home).write_bytes(pub_pem)
    os.chmod(public_path(home), 0o644)

    return Keypair(private=priv, public=pub)


def load(home: Path) -> Keypair:
    """Load the keypair. Raises ``FileNotFoundError`` if missing."""
    raw_priv = private_path(home).read_bytes()
    priv = serialization.load_pem_private_key(raw_priv, password=None)
    if not isinstance(priv, Ed25519PrivateKey):
        raise ValueError(
            f"private key at {private_path(home)} is not Ed25519",
        )
    return Keypair(private=priv, public=priv.public_key())


def load_or_generate(home: Path) -> Keypair:
    """Idempotent bootstrap — the daemon calls this at start."""
    if exists(home):
        return load(home)
    return generate(home)


def decode_pubkey(b64: str) -> Ed25519PublicKey:
    """Inverse of ``Keypair.pubkey_b64()`` — for verifying peer envelopes."""
    raw = base64.b64decode(b64.strip())
    return Ed25519PublicKey.from_public_bytes(raw)
