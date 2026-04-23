"""ALP client — dial a peer's socket, send a signed request, verify the reply.

Intra-profile transport (ALP.1) only. Inter-machine lands in
ALP.2 with a parallel ``client_tcp`` or similar; the same method
surface, different wire.

The caller supplies the local profile's keypair and the target
peer's pinned pubkey. We build + sign the envelope, write one
line of JSON, read one line back, verify the response envelope,
and return the ``result`` dict — or raise a typed error.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from alpi.alp import envelope as env
from alpi.alp.keys import Keypair


class ClientError(Exception):
    """Generic client-side failure (transport + response errors)."""


class TargetOffline(ClientError):
    """Peer socket could not be reached."""


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
    """Send one ALP request and wait for the response.

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
            asyncio.open_unix_connection(str(socket_path)), timeout=timeout,
        )
    except (FileNotFoundError, ConnectionRefusedError) as e:
        raise TargetOffline(f"{socket_path}: {e}") from e

    try:
        payload = json.dumps(
            body, separators=(",", ":"), ensure_ascii=False,
        ).encode("utf-8") + b"\n"
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

    parsed = env.verify(response, replay_cache=replay_cache)

    if parsed.error is not None:
        err = parsed.error
        raise RemoteError(
            code=int(err.get("code", -32603)),
            message=str(err.get("message", "unknown")),
            data=err.get("data"),
        )

    return parsed.result or {}
