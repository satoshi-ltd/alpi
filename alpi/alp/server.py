"""ALP Unix-socket listener — accepts requests from pinned peers.

Intra-profile transport (ALP.1). Each profile's gateway daemon
spins up a Server bound to ``~/.alpi/<profile>/alp.sock`` (0600).
The server verifies every envelope (signature, version, ts,
replay), checks capability against ``peers.yaml``, dispatches to
a registered handler, and signs the response.

Protocol on the socket: newline-delimited canonical JSON. One
request per connection, one response, connection closes. Small
per-message overhead, trivial to debug with ``nc -U``.

Handlers for ``link.ping`` is built-in. Other verbs (``link.ask``,
``link.cancel``) register from outside this module so the server
stays dependency-free at the level of envelope + peers.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Awaitable, Callable

from alpi.alp import PROTOCOL_VERSION
from alpi.alp import envelope as env
from alpi.alp import peers as peers_mod
from alpi.alp.keys import Keypair, load_or_generate


log = logging.getLogger("alpi.alp.server")


# A handler takes (params, peer, server) and returns a result dict,
# optionally as a coroutine. Raising JSON-RPC-compatible errors is
# done by raising ``HandlerError`` so the dispatcher maps to the
# right response shape.
HandlerResult = dict[str, Any]
Handler = Callable[
    [dict[str, Any], peers_mod.Peer, "Server"],
    "HandlerResult | Awaitable[HandlerResult]",
]


class HandlerError(Exception):
    """A handler-visible error that maps to a JSON-RPC error reply.

    ``code`` follows the ALP error code table in ``docs/ALP.md``.
    """

    def __init__(self, code: int, message: str, data: Any = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


class Server:
    def __init__(self, home: Path, agent_name: str = "alpi") -> None:
        self.home = home
        self.agent_name = agent_name
        self.kp: Keypair = load_or_generate(home)
        self.replay = env.ReplayCache()
        self.handlers: dict[str, Handler] = {}
        self._server: asyncio.AbstractServer | None = None
        self._register_defaults()

    @property
    def pubkey_b64(self) -> str:
        return self.kp.pubkey_b64()

    def socket_path(self) -> Path:
        return self.home / "alp" / "alp.sock"

    def register(self, method: str, handler: Handler) -> None:
        self.handlers[method] = handler

    def _register_defaults(self) -> None:
        self.register("link.ping", self._handle_ping)

    async def _handle_ping(
        self, params: dict[str, Any], peer: peers_mod.Peer, server: "Server",
    ) -> HandlerResult:
        return {
            "nonce": str((params or {}).get("nonce", "")),
            "version": PROTOCOL_VERSION,
            "agent_name": server.agent_name,
        }

    # Lifecycle

    async def start(self) -> None:
        sock = self.socket_path()
        sock.parent.mkdir(parents=True, exist_ok=True)
        if sock.exists():
            sock.unlink()
        self._server = await asyncio.start_unix_server(
            self._handle_connection, path=str(sock),
        )
        sock.chmod(0o600)
        log.info("alp server listening on %s", sock)

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        sock = self.socket_path()
        if sock.exists():
            try:
                sock.unlink()
            except OSError:
                pass

    async def serve_forever(self) -> None:
        assert self._server is not None, "call start() first"
        async with self._server:
            await self._server.serve_forever()

    # Wire handling

    async def _handle_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter,
    ) -> None:
        try:
            line = await reader.readline()
            if not line:
                return
            try:
                body = json.loads(line)
            except json.JSONDecodeError:
                log.debug("malformed JSON on alp socket; dropping")
                return
            response = await self._dispatch(body)
            if response is None:
                return
            payload = json.dumps(
                response, separators=(",", ":"), ensure_ascii=False,
            ).encode("utf-8") + b"\n"
            writer.write(payload)
            await writer.drain()
        except Exception:  # noqa: BLE001
            log.exception("alp connection crashed")
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:  # noqa: BLE001
                pass

    async def _dispatch(self, body: dict[str, Any]) -> dict[str, Any] | None:
        # 1. Envelope verification (signature, version, ts, replay).
        #    Silent drop per spec — don't leak oracle responses.
        try:
            parsed = env.verify(body, replay_cache=self.replay)
        except env.EnvelopeError as e:
            log.debug("envelope rejected: %s", e)
            return None

        sender_pk = parsed.alp["from"]

        # 2. Unknown peer → silent drop. Only pinned pubkeys reach
        #    the method layer.
        peer = peers_mod.get_by_pubkey(self.home, sender_pk)
        if peer is None:
            log.info("alp drop: unpinned sender %s...", sender_pk[:12])
            return None

        method = parsed.method
        request_id = parsed.id

        # 3. Capability check.
        if method is None or not peer.may_call(method):
            return env.build_response(
                sender=self.kp,
                recipient_pubkey_b64=sender_pk,
                request_id=request_id,
                error={
                    "code": -32001,
                    "message": "capability-denied",
                    "data": {"method": method},
                },
            )

        # 4. Method existence.
        handler = self.handlers.get(method)
        if handler is None:
            return env.build_response(
                sender=self.kp,
                recipient_pubkey_b64=sender_pk,
                request_id=request_id,
                error={"code": -32601, "message": "method-not-found"},
            )

        # 5. Invoke.
        import time as _time
        t0 = _time.monotonic()
        try:
            out = handler(parsed.params or {}, peer, self)
            if asyncio.iscoroutine(out):
                out = await out
            log.info(
                "alp: %s from %s · %.2fs", method, peer.id, _time.monotonic() - t0,
            )
        except HandlerError as e:
            log.info(
                "alp: %s from %s · rejected %d %s",
                method, peer.id, e.code, e.message,
            )
            return env.build_response(
                sender=self.kp,
                recipient_pubkey_b64=sender_pk,
                request_id=request_id,
                error={"code": e.code, "message": e.message, "data": e.data},
            )
        except Exception as e:  # noqa: BLE001
            log.exception("handler %s crashed", method)
            return env.build_response(
                sender=self.kp,
                recipient_pubkey_b64=sender_pk,
                request_id=request_id,
                error={
                    "code": -32603,
                    "message": "internal-error",
                    "data": {"detail": str(e)},
                },
            )

        return env.build_response(
            sender=self.kp,
            recipient_pubkey_b64=sender_pk,
            request_id=request_id,
            result=out or {},
        )
