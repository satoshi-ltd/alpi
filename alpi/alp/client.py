"""ALP client — dial a peer, send a signed envelope, verify the reply.

``call()`` goes over a Unix socket; ``call_tcp()`` over Noise_XK+TCP;
``call_peer()`` resolves a peer id from ``peers.yaml`` and routes to the
right transport based on whether the peer carries an ``address`` field.
"""

from __future__ import annotations
import asyncio
import json
import time
from dataclasses import dataclass, field
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


_TRANSIENT_REMOTE_ERRORS = frozenset({
    (-32005, "rate-limited"),
    (-32007, "target-busy"),
})


def is_transient_link_error(exc: BaseException) -> bool:
    """Return whether a failed peer call is safe to retry later."""
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, RemoteError):
            return (current.code, current.message) in _TRANSIENT_REMOTE_ERRORS
        if isinstance(current, (TargetOffline, asyncio.TimeoutError, OSError)):
            return True
        if isinstance(current, tcp.TransportError):
            detail = str(current).lower()
            if "peer closed" in detail or "timeout" in detail:
                return True
        if isinstance(current, ClientError) and str(current) == "empty response":
            return True
        current = current.__cause__ or current.__context__
    return False


@dataclass
class _TcpSession:
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter
    cs_send: Any
    cs_recv: Any
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    last_used: float = field(default_factory=time.monotonic)

    async def close(self) -> None:
        self.writer.close()
        try:
            await self.writer.wait_closed()
        except Exception:  # noqa: BLE001
            pass


@dataclass
class _TcpPool:
    sessions: dict[tuple[str, int, str, str, str], _TcpSession] = field(
        default_factory=dict,
    )
    connect_locks: dict[tuple[str, int, str, str, str], asyncio.Lock] = field(
        default_factory=dict,
    )


_TCP_SESSION_MAX_IDLE_S = 60.0


async def _wait_with_timeout(awaitable, timeout: float):
    if timeout <= 0:
        return await awaitable
    return await asyncio.wait_for(awaitable, timeout=timeout)


def _tcp_pool() -> _TcpPool:
    loop = asyncio.get_running_loop()
    pool = getattr(loop, "_alpi_tcp_pool", None)
    if pool is None:
        pool = _TcpPool()
        setattr(loop, "_alpi_tcp_pool", pool)
    return pool


def _tcp_lane(method: str, params: dict[str, Any]) -> str:
    if method == "workgroup.pull":
        return f"pull:{str(params.get('workgroup_id') or '')}"
    if method == "link.ask":
        return "ask"
    return "rpc"


async def _open_tcp_session(
    host: str,
    port: int,
    sender: Keypair,
    recipient_pubkey_b64: str,
    timeout: float,
) -> _TcpSession:
    recipient_x = ed25519_to_x25519_public(decode_pubkey(recipient_pubkey_b64))
    sender_x = ed25519_to_x25519_private(sender.private)
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=timeout,
        )
    except OSError as e:
        raise TargetOffline(f"{host}:{port}: {e}") from e
    try:
        cs_send, cs_recv, _ = await tcp.perform_handshake_initiator(
            reader,
            writer,
            sender_x,
            recipient_x,
        )
    except tcp.TransportError as e:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:  # noqa: BLE001
            pass
        raise ClientError(f"handshake failed: {e}") from e
    return _TcpSession(reader, writer, cs_send, cs_recv)


async def _get_tcp_session(
    *,
    host: str,
    port: int,
    sender: Keypair,
    recipient_pubkey_b64: str,
    timeout: float,
    lane: str,
) -> tuple[_TcpPool, tuple[str, int, str, str, str], _TcpSession]:
    pool = _tcp_pool()
    key = (
        host,
        port,
        sender.pubkey_b64(),
        recipient_pubkey_b64,
        lane,
    )
    connect_lock = pool.connect_locks.setdefault(key, asyncio.Lock())
    async with connect_lock:
        session = pool.sessions.get(key)
        reusable = (
            session is not None
            and not session.writer.is_closing()
            and time.monotonic() - session.last_used < _TCP_SESSION_MAX_IDLE_S
        )
        if reusable:
            return pool, key, session
        if session is not None:
            pool.sessions.pop(key, None)
            await session.close()
        session = await _open_tcp_session(
            host,
            port,
            sender,
            recipient_pubkey_b64,
            timeout,
        )
        pool.sessions[key] = session
        return pool, key, session


async def _discard_tcp_session(
    pool: _TcpPool,
    key: tuple[str, int, str, str, str],
    session: _TcpSession,
) -> None:
    if pool.sessions.get(key) is session:
        pool.sessions.pop(key, None)
    await session.close()


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
            asyncio.open_unix_connection(
                str(socket_path),
                limit=tcp.MAX_FRAME_BYTES + 1,
            ),
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
    """Send one ALP request over a reusable Noise/TCP session."""
    request_params = params or {}
    body = env.build_request(
        sender=sender,
        recipient_pubkey_b64=recipient_pubkey_b64,
        method=method,
        params=request_params,
    )
    plaintext = json.dumps(
        body,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    pool, key, session = await _get_tcp_session(
        host=host,
        port=port,
        sender=sender,
        recipient_pubkey_b64=recipient_pubkey_b64,
        timeout=timeout,
        lane=_tcp_lane(method, request_params),
    )
    try:
        async with session.lock:
            await asyncio.wait_for(
                tcp.send_envelope(session.writer, session.cs_send, plaintext),
                timeout=timeout,
            )
            response_bytes = await asyncio.wait_for(
                tcp.recv_envelope(session.reader, session.cs_recv),
                timeout=timeout,
            )
            session.last_used = time.monotonic()
    except (asyncio.TimeoutError, tcp.TransportError, OSError) as e:
        await _discard_tcp_session(pool, key, session)
        if isinstance(e, asyncio.TimeoutError):
            raise
        raise ClientError(f"transport failed: {e}") from e
    if not response_bytes:
        await _discard_tcp_session(pool, key, session)
        raise ClientError("empty response")
    try:
        response = json.loads(response_bytes)
    except json.JSONDecodeError as e:
        await _discard_tcp_session(pool, key, session)
        raise ClientError(f"malformed response: {e}") from e
    try:
        result, stream = _verify_response(
            response,
            sender=sender,
            recipient_pubkey_b64=recipient_pubkey_b64,
            request_id=str(body.get("id") or ""),
            replay_cache=replay_cache,
        )
    except RemoteError:
        raise
    except Exception:
        await _discard_tcp_session(pool, key, session)
        raise
    if stream == "chunk":
        await _discard_tcp_session(pool, key, session)
        raise ClientError("streaming response requires call_tcp_stream()")
    return result


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
    connect_timeout: float | None = None,
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
        connection = asyncio.open_unix_connection(
            str(socket_path),
            limit=tcp.MAX_FRAME_BYTES + 1,
        )
        reader, writer = await _wait_with_timeout(
            connection,
            timeout if connect_timeout is None else connect_timeout,
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
            line = await _wait_with_timeout(reader.readline(), timeout)
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
    connect_timeout: float | None = None,
    replay_cache: env.ReplayCache | None = None,
):
    """Async generator over a reusable streaming Noise/TCP session."""
    body = env.build_request(
        sender=sender,
        recipient_pubkey_b64=recipient_pubkey_b64,
        method=method,
        params=params or {},
    )
    plaintext = json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    pool, key, session = await _get_tcp_session(
        host=host,
        port=port,
        sender=sender,
        recipient_pubkey_b64=recipient_pubkey_b64,
        timeout=timeout if connect_timeout is None else connect_timeout,
        lane=f"stream:{method}",
    )
    complete = False
    try:
        async with session.lock:
            await _wait_with_timeout(
                tcp.send_envelope(session.writer, session.cs_send, plaintext),
                timeout if connect_timeout is None else connect_timeout,
            )
            while True:
                response_bytes = await _wait_with_timeout(
                    tcp.recv_envelope(session.reader, session.cs_recv),
                    timeout,
                )
                if not response_bytes:
                    raise ClientError("empty response")
                try:
                    response = json.loads(response_bytes)
                except json.JSONDecodeError as e:
                    raise ClientError(f"malformed response: {e}") from e
                result, stream = _verify_response(
                    response,
                    sender=sender,
                    recipient_pubkey_b64=recipient_pubkey_b64,
                    request_id=str(body.get("id") or ""),
                    replay_cache=replay_cache,
                )
                terminal = stream != "chunk"
                if terminal:
                    complete = True
                    session.last_used = time.monotonic()
                yield result, stream
                if terminal:
                    return
    except RemoteError:
        complete = True
        raise
    finally:
        if not complete:
            await _discard_tcp_session(pool, key, session)


async def call_peer_stream(
    *,
    home: Path,
    peer_id: str,
    sender: Keypair,
    method: str,
    params: dict[str, Any] | None = None,
    timeout: float = 30.0,
    connect_timeout: float | None = None,
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
            connect_timeout=connect_timeout,
            replay_cache=replay_cache,
        ):
            yield frame
        return
    raise ClientError(
        f"peer {peer_id!r} has no address; use call_stream() with an explicit "
        "socket_path for intra-profile dispatch"
    )
