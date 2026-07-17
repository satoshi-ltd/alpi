"""ALP inter-machine transport — Noise_XK handshake then AEAD-framed envelopes.

Handshake frames are u16-length-prefixed plaintext; post-handshake bulk
frames are u32-length-prefixed AEAD ciphertext capped at ``MAX_FRAME_BYTES``.
The Ed25519 envelope signature is still checked after decrypt, giving two
layers of authenticated encryption per the ALP spec. Any failure during
handshake, decrypt, or pinned-key cross-check closes the connection silently.
"""

from __future__ import annotations
import asyncio
import logging
import struct
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey,
    X25519PublicKey,
)
from alpi.alp import keys as keys_mod
from alpi.alp import noise as noise_mod
from alpi.alp import peers as peers_mod

log = logging.getLogger("alpi.alp.transport_tcp")
DEFAULT_PORT = 7423
MAX_FRAME_BYTES = 1 * 1024 * 1024  # 1 MiB — soft cap on a single envelope
HANDSHAKE_TIMEOUT = 10.0  # seconds; handshake must complete within
FRAME_TIMEOUT = 30.0  # seconds per bulk frame
SESSION_IDLE_TIMEOUT = 90.0


class TransportError(Exception):
    """Parent for transport-layer failures at the TCP/Noise boundary."""


async def _read_exactly(reader: asyncio.StreamReader, n: int) -> bytes:
    """asyncio's readexactly raises IncompleteReadError on EOF; wrap it
    so callers see a single exception shape."""
    try:
        return await reader.readexactly(n)
    except asyncio.IncompleteReadError as e:
        raise TransportError(f"peer closed while expecting {n} bytes") from e


async def _read_handshake_frame(reader: asyncio.StreamReader) -> bytes:
    """u16-length-prefixed handshake frame."""
    raw_len = await _read_exactly(reader, 2)
    (n,) = struct.unpack(">H", raw_len)
    if n == 0:
        return b""
    return await _read_exactly(reader, n)


async def _write_handshake_frame(writer: asyncio.StreamWriter, payload: bytes) -> None:
    if len(payload) > 0xFFFF:
        raise TransportError("handshake frame too large")
    writer.write(struct.pack(">H", len(payload)) + payload)
    await writer.drain()


async def _read_bulk_frame(reader: asyncio.StreamReader) -> bytes:
    """u32-length-prefixed ciphertext frame (post-handshake)."""
    raw_len = await _read_exactly(reader, 4)
    (n,) = struct.unpack(">I", raw_len)
    if n == 0:
        return b""
    if n > MAX_FRAME_BYTES:
        raise TransportError(f"frame too large: {n} > {MAX_FRAME_BYTES}")
    return await _read_exactly(reader, n)


async def _write_bulk_frame(writer: asyncio.StreamWriter, payload: bytes) -> None:
    if len(payload) > MAX_FRAME_BYTES:
        raise TransportError(f"frame too large: {len(payload)} > {MAX_FRAME_BYTES}")
    writer.write(struct.pack(">I", len(payload)) + payload)
    await writer.drain()


async def perform_handshake_initiator(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    static_priv_x: "X25519PrivateKey",
    responder_static_x: X25519PublicKey,
) -> tuple[noise_mod.CipherState, noise_mod.CipherState, X25519PublicKey]:
    """Drive the initiator half of Noise_XK. Returns (send_cipher,
    recv_cipher, remote_static_pub). Raises TransportError on timeout or
    protocol failure."""

    async def _do() -> tuple[noise_mod.CipherState, noise_mod.CipherState, X25519PublicKey]:
        hs = noise_mod.HandshakeState.new_initiator(static_priv_x, responder_static_x)
        try:
            await _write_handshake_frame(writer, hs.write_message(b""))
            msg2 = await _read_handshake_frame(reader)
            hs.read_message(msg2)
            await _write_handshake_frame(writer, hs.write_message(b""))
        except noise_mod.NoiseError as e:
            raise TransportError(f"noise handshake failed: {e}") from e
        cs_send, cs_recv = hs.finalize()
        return cs_send, cs_recv, hs.remote_static()

    try:
        return await asyncio.wait_for(_do(), timeout=HANDSHAKE_TIMEOUT)
    except asyncio.TimeoutError as e:
        raise TransportError("handshake timeout") from e


async def perform_handshake_responder(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    static_priv_x: "X25519PrivateKey",
) -> tuple[noise_mod.CipherState, noise_mod.CipherState, X25519PublicKey]:
    """Drive the responder half. Returns (send_cipher, recv_cipher,
    remote_static_pub). The remote_static is what we authenticate against
    the peer list."""

    async def _do() -> tuple[noise_mod.CipherState, noise_mod.CipherState, X25519PublicKey]:
        hs = noise_mod.HandshakeState.new_responder(static_priv_x)
        try:
            msg1 = await _read_handshake_frame(reader)
            hs.read_message(msg1)
            await _write_handshake_frame(writer, hs.write_message(b""))
            msg3 = await _read_handshake_frame(reader)
            hs.read_message(msg3)
        except noise_mod.NoiseError as e:
            raise TransportError(f"noise handshake failed: {e}") from e
        cs_send, cs_recv = hs.finalize()
        return cs_send, cs_recv, hs.remote_static()

    try:
        return await asyncio.wait_for(_do(), timeout=HANDSHAKE_TIMEOUT)
    except asyncio.TimeoutError as e:
        raise TransportError("handshake timeout") from e


async def send_envelope(
    writer: asyncio.StreamWriter,
    cs_send: noise_mod.CipherState,
    plaintext: bytes,
) -> None:
    ct = cs_send.encrypt(b"", plaintext)
    await _write_bulk_frame(writer, ct)


async def recv_envelope(
    reader: asyncio.StreamReader,
    cs_recv: noise_mod.CipherState,
) -> bytes:
    ct = await _read_bulk_frame(reader)
    return cs_recv.decrypt(b"", ct)


def find_peer_by_x25519(
    home: Path,
    remote_x: X25519PublicKey,
) -> peers_mod.Peer | None:
    """Match a Noise-authenticated X25519 pubkey against peers.yaml.
    Peers pin Ed25519 pubkeys; we derive the X25519 equivalent from each
    and compare. Typical peer list sizes are small (< 50) so linear scan
    is fine. Returns None if no peer matches — caller should silently
    drop the connection per the ALP silent-drop policy."""
    from alpi.alp import noise as _n

    target = remote_x.public_bytes_raw()
    for p in peers_mod.load(home):
        try:
            derived = _n.ed25519_to_x25519_public(keys_mod.decode_pubkey(p.pubkey))
        except Exception:  # noqa: BLE001
            # Malformed pubkey in peers.yaml — skip rather than raise; the
            # peer-list loader already tolerates junk entries.
            continue
        if derived.public_bytes_raw() == target:
            return p
    return None
