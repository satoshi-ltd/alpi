"""ALP client — dial a peer, send a signed envelope, verify the reply.

``call()`` goes over a Unix socket; ``call_tcp()`` over Noise_XK+TCP;
``call_peer()`` resolves a peer id from ``peers.yaml`` and routes to the
right transport based on whether the peer carries an ``address`` field.
"""

from __future__ import annotations
import asyncio
import json
from pathlib import Path
from typing import Any
from alpi.alp import envelope as env
from alpi.alp import peers as peers_mod
from alpi.alp import transport_tcp as tcp
from alpi.alp.keys import Keypair, decode_pubkey
from alpi.alp.noise import (
    ed25519_to_x25519_private,
    ed25519_to_x25519_public,
)


PING_TIMEOUT_SECONDS = 5.0
"""Default ``link.ping`` timeout shared by every liveness probe.
Set high enough to ride out a daemon that's still warming up its
Engine on first call and to tolerate real WAN latency on Tailscale
peers. ALP probes run concurrently so wall-clock with N peers is
still bounded by this value, not N×."""


class ClientError(Exception):
    """Generic client-side failure (transport + response errors)."""


class TargetOffline(ClientError):
    """Peer socket / host could not be reached."""


class RemoteError(ClientError):
    """Remote server returned a JSON-RPC error response."""

    def __init__(self, code: int, message: str, data: Any = None):
        super().__init__(f"{code} {message}")
        self.code = code
        self.message = message
        self.data = data


async def call(
    *,
    socket_path: Path,
    sender: Keypair,
    recipient_pubkey_b64: str,
    method: str,
    params: dict[str, Any] | None = None,
    timeout: float = 30.0,
    replay_cache: env.ReplayCache | None = None,
) -> dict[str, Any]:
    """Send one ALP request over the Unix socket and wait for the reply.
    Raises:
      TargetOffline: socket missing or refused connection.
      RemoteError: remote returned an ALP/JSON-RPC error.
      env.BadSignature, env.StaleTimestamp, env.BadVersion,
        env.ReplayDetected: response envelope failed verification.
      asyncio.TimeoutError: no response within ``timeout`` seconds.
    """
    body = env.build_request(
        sender=sender,
        recipient_pubkey_b64=recipient_pubkey_b64,
        method=method,
        params=params or {},
    )
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_unix_connection(str(socket_path)),
            timeout=timeout,
        )
    except (FileNotFoundError, ConnectionRefusedError) as e:
        raise TargetOffline(f"{socket_path}: {e}") from e
    try:
        payload = (
            json.dumps(
                body,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            + b"\n"
        )
        writer.write(payload)
        await writer.drain()
        response_line = await asyncio.wait_for(reader.readline(), timeout=timeout)
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:  # noqa: BLE001
            pass
    if not response_line:
        raise ClientError("empty response")
    try:
        response = json.loads(response_line)
    except json.JSONDecodeError as e:
        raise ClientError(f"malformed response: {e}") from e
    parsed = env.verify(
        response,
        replay_cache=replay_cache,
        expected_to=sender.pubkey_b64(),
        expected_from=recipient_pubkey_b64,
        expected_id=body.get("id"),
    )
    if parsed.error is not None:
        err = parsed.error
        raise RemoteError(
            code=int(err.get("code", -32603)),
            message=str(err.get("message", "unknown")),
            data=err.get("data"),
        )
    return parsed.result or {}


async def call_tcp(
    *,
    host: str,
    port: int,
    sender: Keypair,
    recipient_pubkey_b64: str,
    method: str,
    params: dict[str, Any] | None = None,
    timeout: float = 30.0,
    replay_cache: env.ReplayCache | None = None,
) -> dict[str, Any]:
    """Send one ALP request over TCP (Noise_XK handshake + AEAD).
    The caller supplies the pinned pubkey of the recipient as the
    Ed25519 identity; we derive the X25519 static needed by Noise on
    the fly. Same error semantics as ``call()``."""
    recipient_x = ed25519_to_x25519_public(decode_pubkey(recipient_pubkey_b64))
    sender_x = ed25519_to_x25519_private(sender.private)
    body = env.build_request(
        sender=sender,
        recipient_pubkey_b64=recipient_pubkey_b64,
        method=method,
        params=params or {},
    )
    plaintext = json.dumps(
        body,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=timeout,
        )
    except (OSError, ConnectionRefusedError) as e:
        raise TargetOffline(f"{host}:{port}: {e}") from e
    try:
        try:
            cs_send, cs_recv, _ = await tcp.perform_handshake_initiator(
                reader,
                writer,
                sender_x,
                recipient_x,
            )
        except tcp.TransportError as e:
            raise ClientError(f"handshake failed: {e}") from e
        await tcp.send_envelope(writer, cs_send, plaintext)
        try:
            response_bytes = await asyncio.wait_for(
                tcp.recv_envelope(reader, cs_recv),
                timeout=timeout,
            )
        except tcp.TransportError as e:
            raise ClientError(f"read failed: {e}") from e
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:  # noqa: BLE001
            pass
    if not response_bytes:
        raise ClientError("empty response")
    try:
        response = json.loads(response_bytes)
    except json.JSONDecodeError as e:
        raise ClientError(f"malformed response: {e}") from e
    parsed = env.verify(
        response,
        replay_cache=replay_cache,
        expected_to=sender.pubkey_b64(),
        expected_from=recipient_pubkey_b64,
        expected_id=body.get("id"),
    )
    if parsed.error is not None:
        err = parsed.error
        raise RemoteError(
            code=int(err.get("code", -32603)),
            message=str(err.get("message", "unknown")),
            data=err.get("data"),
        )
    return parsed.result or {}


async def call_peer(
    *,
    home: Path,
    peer_id: str,
    sender: Keypair,
    method: str,
    params: dict[str, Any] | None = None,
    timeout: float = 30.0,
    replay_cache: env.ReplayCache | None = None,
) -> dict[str, Any]:
    """Resolve a peer by id, then dispatch to Unix or TCP based on
    whether the peer's ``address`` field is set. This is the verb
    most callers want."""
    peer = peers_mod.get_by_id(home, peer_id)
    if peer is None:
        raise ClientError(f"peer {peer_id!r} not in peers.yaml")
    if peer.address:
        host, _, port_s = peer.address.rpartition(":")
        if not host or not port_s.isdigit():
            raise ClientError(f"peer {peer_id!r} has invalid address {peer.address!r}")
        return await call_tcp(
            host=host,
            port=int(port_s),
            sender=sender,
            recipient_pubkey_b64=peer.pubkey,
            method=method,
            params=params,
            timeout=timeout,
            replay_cache=replay_cache,
        )
    raise ClientError(
        f"peer {peer_id!r} has no address; use call() with an explicit "
        "socket_path for intra-profile dispatch"
    )


def _verify_response(
    response: dict[str, Any],
    *,
    sender: Keypair,
    recipient_pubkey_b64: str,
    request_id: str,
    replay_cache: env.ReplayCache | None,
) -> tuple[dict[str, Any], str | None]:
    """Verify a response envelope and return (result, stream_marker).
    Raises ``RemoteError`` if the body contains an error."""
    parsed = env.verify(
        response,
        replay_cache=replay_cache,
        expected_to=sender.pubkey_b64(),
        expected_from=recipient_pubkey_b64,
        expected_id=request_id,
    )
    if parsed.error is not None:
        err = parsed.error
        raise RemoteError(
            code=int(err.get("code", -32603)),
            message=str(err.get("message", "unknown")),
            data=err.get("data"),
        )
    stream = response.get("stream") if isinstance(response, dict) else None
    return parsed.result or {}, stream


async def call_stream(
    *,
    socket_path: Path,
    sender: Keypair,
    recipient_pubkey_b64: str,
    method: str,
    params: dict[str, Any] | None = None,
    timeout: float = 30.0,
    replay_cache: env.ReplayCache | None = None,
):
    """Async generator over a streaming ALP request via Unix socket.
    Yields ``(result, stream)`` per frame — ``stream`` is one of
    ``"chunk"``, ``"final"``, or ``None`` (non-streaming reply)."""
    body = env.build_request(
        sender=sender,
        recipient_pubkey_b64=recipient_pubkey_b64,
        method=method,
        params=params or {},
    )
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_unix_connection(str(socket_path)),
            timeout=timeout,
        )
    except (FileNotFoundError, ConnectionRefusedError) as e:
        raise TargetOffline(f"{socket_path}: {e}") from e
    try:
        payload = (
            json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            + b"\n"
        )
        writer.write(payload)
        await writer.drain()
        while True:
            line = await asyncio.wait_for(reader.readline(), timeout=timeout)
            if not line:
                return
            try:
                response = json.loads(line)
            except json.JSONDecodeError as e:
                raise ClientError(f"malformed response: {e}") from e
            result, stream = _verify_response(
                response,
                sender=sender,
                recipient_pubkey_b64=recipient_pubkey_b64,
                request_id=body.get("id"),
                replay_cache=replay_cache,
            )
            yield result, stream
            if stream != "chunk":
                return
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:  # noqa: BLE001
            pass


async def call_tcp_stream(
    *,
    host: str,
    port: int,
    sender: Keypair,
    recipient_pubkey_b64: str,
    method: str,
    params: dict[str, Any] | None = None,
    timeout: float = 30.0,
    replay_cache: env.ReplayCache | None = None,
):
    """Async generator over a streaming ALP request via Noise/TCP.
    Same yield contract as ``call_stream``."""
    recipient_x = ed25519_to_x25519_public(decode_pubkey(recipient_pubkey_b64))
    sender_x = ed25519_to_x25519_private(sender.private)
    body = env.build_request(
        sender=sender,
        recipient_pubkey_b64=recipient_pubkey_b64,
        method=method,
        params=params or {},
    )
    plaintext = json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=timeout,
        )
    except (OSError, ConnectionRefusedError) as e:
        raise TargetOffline(f"{host}:{port}: {e}") from e
    try:
        try:
            cs_send, cs_recv, _ = await tcp.perform_handshake_initiator(
                reader, writer, sender_x, recipient_x,
            )
        except tcp.TransportError as e:
            raise ClientError(f"handshake failed: {e}") from e
        await tcp.send_envelope(writer, cs_send, plaintext)
        while True:
            try:
                response_bytes = await asyncio.wait_for(
                    tcp.recv_envelope(reader, cs_recv),
                    timeout=timeout,
                )
            except tcp.TransportError:
                return
            if not response_bytes:
                return
            try:
                response = json.loads(response_bytes)
            except json.JSONDecodeError as e:
                raise ClientError(f"malformed response: {e}") from e
            result, stream = _verify_response(
                response,
                sender=sender,
                recipient_pubkey_b64=recipient_pubkey_b64,
                request_id=body.get("id"),
                replay_cache=replay_cache,
            )
            yield result, stream
            if stream != "chunk":
                return
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:  # noqa: BLE001
            pass


async def call_peer_stream(
    *,
    home: Path,
    peer_id: str,
    sender: Keypair,
    method: str,
    params: dict[str, Any] | None = None,
    timeout: float = 30.0,
    replay_cache: env.ReplayCache | None = None,
):
    """Same as ``call_peer`` but yields ``(result, stream)`` per frame."""
    peer = peers_mod.get_by_id(home, peer_id)
    if peer is None:
        raise ClientError(f"peer {peer_id!r} not in peers.yaml")
    if peer.address:
        host, _, port_s = peer.address.rpartition(":")
        if not host or not port_s.isdigit():
            raise ClientError(f"peer {peer_id!r} has invalid address {peer.address!r}")
        async for frame in call_tcp_stream(
            host=host,
            port=int(port_s),
            sender=sender,
            recipient_pubkey_b64=peer.pubkey,
            method=method,
            params=params,
            timeout=timeout,
            replay_cache=replay_cache,
        ):
            yield frame
        return
    raise ClientError(
        f"peer {peer_id!r} has no address; use call_stream() with an explicit "
        "socket_path for intra-profile dispatch"
    )
