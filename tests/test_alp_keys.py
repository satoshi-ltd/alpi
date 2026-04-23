"""ALP per-profile Ed25519 identity."""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from alpi.alp import keys


def test_generate_creates_both_files(tmp_path: Path) -> None:
    kp = keys.generate(tmp_path)
    assert keys.private_path(tmp_path).exists()
    assert keys.public_path(tmp_path).exists()
    assert isinstance(kp.pubkey_b64(), str) and len(kp.pubkey_b64()) > 0


def test_private_key_mode_is_0600(tmp_path: Path) -> None:
    keys.generate(tmp_path)
    mode = stat.S_IMODE(os.stat(keys.private_path(tmp_path)).st_mode)
    # 0o600 = owner rw only. Public-group-world bits must be zero.
    assert mode == 0o600, f"expected 0600, got {oct(mode)}"


def test_load_reconstructs_same_pubkey(tmp_path: Path) -> None:
    kp_a = keys.generate(tmp_path)
    kp_b = keys.load(tmp_path)
    assert kp_a.pubkey_b64() == kp_b.pubkey_b64()


def test_load_or_generate_idempotent(tmp_path: Path) -> None:
    kp_a = keys.load_or_generate(tmp_path)
    kp_b = keys.load_or_generate(tmp_path)
    # Second call must NOT have regenerated — pubkey stable.
    assert kp_a.pubkey_b64() == kp_b.pubkey_b64()


def test_exists_false_on_empty_home(tmp_path: Path) -> None:
    assert keys.exists(tmp_path) is False


def test_exists_true_after_generate(tmp_path: Path) -> None:
    keys.generate(tmp_path)
    assert keys.exists(tmp_path) is True


def test_pubkey_b64_roundtrips_to_public_key(tmp_path: Path) -> None:
    kp = keys.generate(tmp_path)
    decoded = keys.decode_pubkey(kp.pubkey_b64())
    # Round-trip: encode-then-decode matches the key we exported.
    from cryptography.hazmat.primitives import serialization
    raw_a = kp.public.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    raw_b = decoded.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    assert raw_a == raw_b


def test_sign_produces_verifiable_signature(tmp_path: Path) -> None:
    kp = keys.generate(tmp_path)
    payload = b"hello alpi"
    sig = kp.sign(payload)
    # Using the cryptography library directly to verify — that's the
    # real contract any consumer would rely on.
    kp.public.verify(sig, payload)


def test_load_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        keys.load(tmp_path)
