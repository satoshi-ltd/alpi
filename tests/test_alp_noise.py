"""Unit tests for alpi.alp.noise — Noise_XK handshake + Ed25519 → X25519."""

from __future__ import annotations

import pytest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from alpi.alp.noise import (
    CipherState,
    HandshakeState,
    NoiseError,
    ed25519_to_x25519_private,
    ed25519_to_x25519_public,
)


def _identities():
    a = Ed25519PrivateKey.generate()
    b = Ed25519PrivateKey.generate()
    return a, b


# ── derivation ──────────────────────────────────────────────────────────────

def test_derive_public_matches_derived_from_private():
    ed = Ed25519PrivateKey.generate()
    x_priv = ed25519_to_x25519_private(ed)
    x_pub_direct = ed25519_to_x25519_public(ed.public_key())
    assert x_pub_direct.public_bytes_raw() == x_priv.public_key().public_bytes_raw()


def test_derivation_is_deterministic():
    ed = Ed25519PrivateKey.generate()
    one = ed25519_to_x25519_private(ed).private_bytes_raw()
    two = ed25519_to_x25519_private(ed).private_bytes_raw()
    assert one == two


# ── handshake happy path ────────────────────────────────────────────────────

def _run_xk_handshake(payload_a=b"", payload_b=b"", payload_c=b""):
    a_ed, b_ed = _identities()
    a_x = ed25519_to_x25519_private(a_ed)
    b_x = ed25519_to_x25519_private(b_ed)
    b_pub_x = ed25519_to_x25519_public(b_ed.public_key())

    init = HandshakeState.new_initiator(a_x, b_pub_x)
    resp = HandshakeState.new_responder(b_x)

    m1 = init.write_message(payload_a)
    assert resp.read_message(m1) == payload_a

    m2 = resp.write_message(payload_b)
    assert init.read_message(m2) == payload_b

    m3 = init.write_message(payload_c)
    assert resp.read_message(m3) == payload_c

    return init, resp, a_ed, b_ed


def test_xk_handshake_completes_with_empty_payloads():
    init, resp, _, _ = _run_xk_handshake()
    assert init.finished()
    assert resp.finished()


def test_xk_handshake_carries_optional_payloads():
    init, resp, _, _ = _run_xk_handshake(b"hi", b"hello", b"final")
    assert init.finished()
    assert resp.finished()


def test_responder_authenticates_initiator_static():
    init, resp, a_ed, _ = _run_xk_handshake()
    expected = ed25519_to_x25519_public(a_ed.public_key()).public_bytes_raw()
    assert resp.remote_static().public_bytes_raw() == expected


def test_bulk_traffic_roundtrip_both_directions():
    init, resp, _, _ = _run_xk_handshake()
    a_send, a_recv = init.finalize()
    b_send, b_recv = resp.finalize()

    ct = a_send.encrypt(b"", b"request")
    assert b_recv.decrypt(b"", ct) == b"request"

    ct2 = b_send.encrypt(b"", b"reply")
    assert a_recv.decrypt(b"", ct2) == b"reply"


def test_cipher_state_counter_advances():
    init, resp, _, _ = _run_xk_handshake()
    a_send, _ = init.finalize()
    _, b_recv = resp.finalize()

    before = a_send.n
    a_send.encrypt(b"", b"msg1")
    a_send.encrypt(b"", b"msg2")
    assert a_send.n == before + 2


# ── handshake error paths ───────────────────────────────────────────────────

def test_responder_rejects_tampered_static():
    """Flip a byte inside the encrypted static pubkey; the AEAD tag fails."""
    a_ed, b_ed = _identities()
    a_x = ed25519_to_x25519_private(a_ed)
    b_x = ed25519_to_x25519_private(b_ed)
    b_pub_x = ed25519_to_x25519_public(b_ed.public_key())

    init = HandshakeState.new_initiator(a_x, b_pub_x)
    resp = HandshakeState.new_responder(b_x)

    m1 = init.write_message(b"")
    resp.read_message(m1)
    m2 = resp.write_message(b"")
    init.read_message(m2)
    m3 = bytearray(init.write_message(b""))
    # Flip a byte inside the encrypted-static block (first 48 bytes).
    m3[5] ^= 0x01
    with pytest.raises(NoiseError):
        resp.read_message(bytes(m3))


def test_wrong_responder_pubkey_breaks_handshake():
    """If the initiator has the wrong ``rs``, the ``es`` token in msg1
    mixes in a DH output the responder can't reproduce; the AEAD tag on
    msg1's trailing ciphertext fails on the responder side immediately."""
    a_ed, b_ed = _identities()
    other_ed = Ed25519PrivateKey.generate()
    a_x = ed25519_to_x25519_private(a_ed)
    b_x = ed25519_to_x25519_private(b_ed)
    wrong_pub_x = ed25519_to_x25519_public(other_ed.public_key())

    init = HandshakeState.new_initiator(a_x, wrong_pub_x)
    resp = HandshakeState.new_responder(b_x)

    m1 = init.write_message(b"")
    with pytest.raises(NoiseError):
        resp.read_message(m1)


def test_cipher_state_without_key_is_passthrough():
    cs = CipherState()
    assert not cs.has_key()
    assert cs.encrypt(b"", b"hello") == b"hello"
    assert cs.decrypt(b"", b"hello") == b"hello"
