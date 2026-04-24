"""Noise_XK_25519_ChaChaPoly_SHA256 over ``cryptography`` primitives.
The pinned identity is Ed25519; Noise needs X25519. We derive X25519 from
the Ed25519 seed with the standard birational map so peers still exchange
a single pubkey. Spec: https://noiseprotocol.org/noise.html (rev 34).
"""

from __future__ import annotations
import hashlib
import os
from dataclasses import dataclass, field
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey,
    X25519PublicKey,
)
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

PROTOCOL_NAME = b"Noise_XK_25519_ChaChaPoly_SHA256"
# Curve25519 prime for the Edwards→Montgomery map.
_P25519 = (1 << 255) - 19
_DHLEN = 32
_HASHLEN = 32


class NoiseError(Exception):
    """Parent for every handshake-layer failure (bad tag, short buffer, …)."""


def ed25519_to_x25519_private(ed: Ed25519PrivateKey) -> X25519PrivateKey:
    seed = ed.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    h = hashlib.sha512(seed).digest()[:32]
    clamped = bytearray(h)
    clamped[0] &= 248
    clamped[31] &= 127
    clamped[31] |= 64
    return X25519PrivateKey.from_private_bytes(bytes(clamped))


def ed25519_to_x25519_public(ed: Ed25519PublicKey) -> X25519PublicKey:
    raw = ed.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    # Ed25519 compressed form: 32 bytes, y-coord little-endian, sign bit
    # in top bit of last byte. Drop the sign bit before the conversion.
    y = int.from_bytes(raw, "little") & ((1 << 255) - 1)
    # Montgomery u = (1 + y) / (1 - y)  (mod p)
    denom = (1 - y) % _P25519
    if denom == 0:
        raise NoiseError("degenerate Ed25519 pubkey — cannot derive X25519")
    u = ((1 + y) * pow(denom, -1, _P25519)) % _P25519
    return X25519PublicKey.from_public_bytes(u.to_bytes(32, "little"))


def _hkdf(chaining_key: bytes, ikm: bytes, n: int) -> list[bytes]:
    """HKDF-SHA256 as defined in §4.3 of the Noise spec — returns ``n`` outputs,
    each 32 bytes. Uses HMAC-SHA256."""
    import hmac

    prk = hmac.new(chaining_key, ikm, hashlib.sha256).digest()
    outs: list[bytes] = []
    prev = b""
    for i in range(1, n + 1):
        prev = hmac.new(prk, prev + bytes([i]), hashlib.sha256).digest()
        outs.append(prev)
    return outs


def _dh(priv: X25519PrivateKey, pub: X25519PublicKey) -> bytes:
    return priv.exchange(pub)


def _pub_bytes(pub: X25519PublicKey) -> bytes:
    return pub.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def _nonce_bytes(n: int) -> bytes:
    # Noise: 32 bits of zeros, 64-bit little-endian counter = 12 bytes.
    return b"\x00\x00\x00\x00" + n.to_bytes(8, "little")


@dataclass
class CipherState:
    """Pair of (key, counter) used after the handshake for bulk traffic.
    Callers never construct these directly — ``HandshakeState.finalize()``
    returns two (one per direction). A nonce overflow raises rather than
    wrapping (we rekey session rather than risk a reused nonce)."""

    key: bytes | None = None
    n: int = 0

    def has_key(self) -> bool:
        return self.key is not None

    def encrypt(self, ad: bytes, plaintext: bytes) -> bytes:
        if self.key is None:
            return plaintext
        if self.n >= (1 << 64) - 1:
            raise NoiseError("nonce exhausted; re-handshake required")
        ct = ChaCha20Poly1305(self.key).encrypt(_nonce_bytes(self.n), plaintext, ad)
        self.n += 1
        return ct

    def decrypt(self, ad: bytes, ciphertext: bytes) -> bytes:
        if self.key is None:
            return ciphertext
        if self.n >= (1 << 64) - 1:
            raise NoiseError("nonce exhausted; re-handshake required")
        try:
            pt = ChaCha20Poly1305(self.key).decrypt(_nonce_bytes(self.n), ciphertext, ad)
        except Exception as e:
            raise NoiseError(f"decrypt failed: {e}") from e
        self.n += 1
        return pt


@dataclass
class _SymmetricState:
    """MixKey + MixHash + Split bookkeeping (spec §5.2)."""

    h: bytes = b""
    ck: bytes = b""
    cs: CipherState = field(default_factory=CipherState)

    @classmethod
    def initialize(cls, protocol_name: bytes) -> "_SymmetricState":
        if len(protocol_name) <= _HASHLEN:
            h = protocol_name + b"\x00" * (_HASHLEN - len(protocol_name))
        else:
            h = hashlib.sha256(protocol_name).digest()
        return cls(h=h, ck=h, cs=CipherState())

    def mix_hash(self, data: bytes) -> None:
        self.h = hashlib.sha256(self.h + data).digest()

    def mix_key(self, ikm: bytes) -> None:
        ck, temp_k = _hkdf(self.ck, ikm, 2)
        self.ck = ck
        self.cs = CipherState(key=temp_k, n=0)

    def encrypt_and_hash(self, plaintext: bytes) -> bytes:
        ct = self.cs.encrypt(self.h, plaintext)
        self.mix_hash(ct)
        return ct

    def decrypt_and_hash(self, ciphertext: bytes) -> bytes:
        pt = self.cs.decrypt(self.h, ciphertext)
        self.mix_hash(ciphertext)
        return pt

    def split(self) -> tuple[CipherState, CipherState]:
        k1, k2 = _hkdf(self.ck, b"", 2)
        return CipherState(key=k1, n=0), CipherState(key=k2, n=0)


@dataclass
class HandshakeState:
    """The Noise_XK handshake driver. One instance per direction.
    Usage (initiator):
        hs = HandshakeState.new_initiator(static_priv, responder_static_pub)
        msg1 = hs.write_message(b"")         # -> e, es
        # ...send msg1, receive msg2...
        _ = hs.read_message(msg2)            # <- e, ee
        msg3 = hs.write_message(b"")         # -> s, se
        cs_send, cs_recv = hs.finalize()
    Usage (responder):
        hs = HandshakeState.new_responder(static_priv, static_pub)
        _ = hs.read_message(msg1)
        msg2 = hs.write_message(b"")
        _ = hs.read_message(msg3)
        cs_recv, cs_send = hs.finalize()     # note: direction flipped
    """

    initiator: bool
    sym: _SymmetricState
    s_priv: X25519PrivateKey
    s_pub: X25519PublicKey
    e_priv: X25519PrivateKey | None = None
    e_pub: X25519PublicKey | None = None
    rs: X25519PublicKey | None = None
    re: X25519PublicKey | None = None
    _message_patterns: list[list[str]] = field(default_factory=list)
    _msg_index: int = 0

    @classmethod
    def _init(
        cls,
        initiator: bool,
        static_priv: X25519PrivateKey,
        responder_static_pub: X25519PublicKey,
    ) -> "HandshakeState":
        sym = _SymmetricState.initialize(PROTOCOL_NAME)
        sym.mix_hash(b"")  # empty prologue
        # Pre-message: responder's static is known to both sides.
        sym.mix_hash(_pub_bytes(responder_static_pub))
        return cls(
            initiator=initiator,
            sym=sym,
            s_priv=static_priv,
            s_pub=static_priv.public_key(),
            rs=responder_static_pub if initiator else None,
            # XK message pattern:
            #   -> e, es
            #   <- e, ee
            #   -> s, se
            _message_patterns=[
                ["e", "es"],
                ["e", "ee"],
                ["s", "se"],
            ],
        )

    @classmethod
    def new_initiator(
        cls,
        static_priv: X25519PrivateKey,
        responder_static_pub: X25519PublicKey,
    ) -> "HandshakeState":
        return cls._init(True, static_priv, responder_static_pub)

    @classmethod
    def new_responder(cls, static_priv: X25519PrivateKey) -> "HandshakeState":
        return cls._init(False, static_priv, static_priv.public_key())

    def write_message(self, payload: bytes) -> bytes:
        tokens = self._message_patterns[self._msg_index]
        self._msg_index += 1
        buf = b""
        for t in tokens:
            if t == "e":
                self.e_priv = X25519PrivateKey.generate()
                self.e_pub = self.e_priv.public_key()
                eb = _pub_bytes(self.e_pub)
                buf += eb
                self.sym.mix_hash(eb)
            elif t == "s":
                # Encrypt-and-hash our static pubkey; ciphertext goes on wire.
                s_bytes = _pub_bytes(self.s_pub)
                buf += self.sym.encrypt_and_hash(s_bytes)
            elif t == "ee":
                assert self.e_priv is not None and self.re is not None
                self.sym.mix_key(_dh(self.e_priv, self.re))
            elif t == "es":
                if self.initiator:
                    assert self.e_priv is not None and self.rs is not None
                    self.sym.mix_key(_dh(self.e_priv, self.rs))
                else:
                    assert self.re is not None
                    self.sym.mix_key(_dh(self.s_priv, self.re))
            elif t == "se":
                if self.initiator:
                    assert self.re is not None
                    self.sym.mix_key(_dh(self.s_priv, self.re))
                else:
                    assert self.e_priv is not None and self.rs is not None
                    self.sym.mix_key(_dh(self.e_priv, self.rs))
            else:
                raise NoiseError(f"unknown token: {t}")
        buf += self.sym.encrypt_and_hash(payload)
        return buf

    def read_message(self, message: bytes) -> bytes:
        tokens = self._message_patterns[self._msg_index]
        self._msg_index += 1
        rest = message
        for t in tokens:
            if t == "e":
                if len(rest) < _DHLEN:
                    raise NoiseError("short message: missing ephemeral pubkey")
                eb, rest = rest[:_DHLEN], rest[_DHLEN:]
                self.re = X25519PublicKey.from_public_bytes(eb)
                self.sym.mix_hash(eb)
            elif t == "s":
                # Encrypted static — size depends on whether we have a key.
                tag_len = 16 if self.sym.cs.has_key() else 0
                take = _DHLEN + tag_len
                if len(rest) < take:
                    raise NoiseError("short message: missing encrypted static")
                ct, rest = rest[:take], rest[take:]
                s_bytes = self.sym.decrypt_and_hash(ct)
                self.rs = X25519PublicKey.from_public_bytes(s_bytes)
            elif t == "ee":
                assert self.e_priv is not None and self.re is not None
                self.sym.mix_key(_dh(self.e_priv, self.re))
            elif t == "es":
                if self.initiator:
                    assert self.e_priv is not None and self.rs is not None
                    self.sym.mix_key(_dh(self.e_priv, self.rs))
                else:
                    assert self.re is not None
                    self.sym.mix_key(_dh(self.s_priv, self.re))
            elif t == "se":
                if self.initiator:
                    assert self.re is not None
                    self.sym.mix_key(_dh(self.s_priv, self.re))
                else:
                    assert self.e_priv is not None and self.rs is not None
                    self.sym.mix_key(_dh(self.e_priv, self.rs))
            else:
                raise NoiseError(f"unknown token: {t}")
        return self.sym.decrypt_and_hash(rest)

    def finished(self) -> bool:
        return self._msg_index >= len(self._message_patterns)

    def finalize(self) -> tuple[CipherState, CipherState]:
        """After the final message, split into (send, recv) cipher states.
        The Noise spec says Split returns (temp_k1, temp_k2) where k1 is
        the initiator→responder key. We return (send, recv) from the
        caller's perspective so each side uses its pair symmetrically."""
        if not self.finished():
            raise NoiseError("handshake not finished")
        k_i_to_r, k_r_to_i = self.sym.split()
        if self.initiator:
            return k_i_to_r, k_r_to_i
        return k_r_to_i, k_i_to_r

    def remote_static(self) -> X25519PublicKey:
        """Peer's authenticated static pubkey after the handshake. For
        the responder, this is the value learned in msg3; for the
        initiator, it is the pre-shared ``rs`` (unchanged). Callers use
        this to cross-check the Noise-layer identity against the
        peer list (pinned Ed25519 pubkey, converted on the fly)."""
        if self.rs is None:
            raise NoiseError("remote static not yet known")
        return self.rs
