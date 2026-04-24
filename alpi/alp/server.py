"""ALP listener — Unix socket (always) plus an optional Noise_XK TCP port.

Both transports share the same envelope, dispatch, and capability model;
they differ only on the wire. A Noise-authenticated peer still has to
match a pinned entry in ``peers.yaml``, same silent-drop posture as the
Unix socket when the envelope signer is unknown.
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
from alpi.alp import rate_limit as rl
from alpi.alp import transport_tcp as tcp
from alpi.alp.keys import Keypair, load_or_generate
from alpi.alp.noise import ed25519_to_x25519_private


log = logging.getLogger("alpi.alp.server")


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
    def __init__(
        self,
        home: Path,
        agent_name: str = "alpi",
        *,
        tcp_host: str | None = None,
        tcp_port: int | None = None,
    ) -> None:
        """``tcp_port`` enables ALP.2 — the Noise_XK transport on TCP.
        Leave both TCP knobs None to keep ALP.1-only behaviour (Unix
        socket). ``tcp_host`` defaults to ``127.0.0.1`` when the port is
        set; operators who want remote peers typically front the port
        with Tailscale / WireGuard and bind the local VPN address."""
        self.home = home
        self.agent_name = agent_name
        self.kp: Keypair = load_or_generate(home)
        self.replay = env.ReplayCache()
        self.rate_limiter = rl.RateLimiter()
        self.handlers: dict[str, Handler] = {}
        self._server: asyncio.AbstractServer | None = None
        self._tcp_server: asyncio.AbstractServer | None = None
        self._tcp_host = tcp_host or ("127.0.0.1" if tcp_port else None)
        self._tcp_port = tcp_port
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
        self,
        params: dict[str, Any],
        peer: peers_mod.Peer,
        server: "Server",
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
            self._handle_unix_connection,
            path=str(sock),
        )
        sock.chmod(0o600)
        log.info("alp server listening on %s", sock)
        if self._tcp_port is not None:
            self._tcp_server = await asyncio.start_server(
                self._handle_tcp_connection,
                host=self._tcp_host,
                port=self._tcp_port,
            )
            log.info(
                "alp tcp listening on %s:%d (Noise_XK)",
                self._tcp_host,
                self._tcp_port,
            )

    async def stop(self) -> None:
        for s in (self._server, self._tcp_server):
            if s is not None:
                s.close()
                await s.wait_closed()
        self._server = None
        self._tcp_server = None
        sock = self.socket_path()
        if sock.exists():
            try:
                sock.unlink()
            except OSError:
                pass

    async def serve_forever(self) -> None:
        assert self._server is not None, "call start() first"
        tasks = [asyncio.create_task(self._server.serve_forever())]
        if self._tcp_server is not None:
            tasks.append(asyncio.create_task(self._tcp_server.serve_forever()))
        try:
            await asyncio.gather(*tasks)
        finally:
            for t in tasks:
                t.cancel()

    async def _handle_unix_connection(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
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
            payload = (
                json.dumps(
                    response,
                    separators=(",", ":"),
                    ensure_ascii=False,
                ).encode("utf-8")
                + b"\n"
            )
            writer.write(payload)
            await writer.drain()
        except Exception:  # noqa: BLE001
            log.exception("alp unix connection crashed")
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:  # noqa: BLE001
                pass

    async def _handle_tcp_connection(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        peername = writer.get_extra_info("peername")
        try:
            static_x = ed25519_to_x25519_private(self.kp.private)
            try:
                cs_send, cs_recv, remote_x = await tcp.perform_handshake_responder(
                    reader,
                    writer,
                    static_x,
                )
            except tcp.TransportError as e:
                log.info("alp tcp: handshake failed from %s: %s", peername, e)
                return

            # Noise proved the peer owns *some* static key; still require
            # that key to be pinned in peers.yaml before we dispatch.
            expected_peer = tcp.find_peer_by_x25519(self.home, remote_x)
            if expected_peer is None:
                log.info("alp tcp: unpinned peer from %s — silent drop", peername)
                return

            # One request per connection, mirroring the Unix socket shape.
            try:
                plaintext = await tcp.recv_envelope(reader, cs_recv)
            except tcp.TransportError as e:
                log.debug("alp tcp: frame read failed: %s", e)
                return
            try:
                body = json.loads(plaintext)
            except json.JSONDecodeError:
                log.debug("alp tcp: malformed JSON after decrypt; dropping")
                return

            response = await self._dispatch(body, pinned_peer=expected_peer)
            if response is None:
                return
            payload = json.dumps(
                response,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            try:
                await tcp.send_envelope(writer, cs_send, payload)
            except tcp.TransportError as e:
                log.debug("alp tcp: send failed: %s", e)
        except Exception:  # noqa: BLE001
            log.exception("alp tcp connection crashed")
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:  # noqa: BLE001
                pass

    async def _dispatch(
        self,
        body: dict[str, Any],
        *,
        pinned_peer: peers_mod.Peer | None = None,
    ) -> dict[str, Any] | None:
        """Envelope verify → peer lookup → capability → invoke → reply.

        ``pinned_peer`` is set by the TCP path once the Noise handshake
        authenticated the sender's static key; we still verify the
        envelope's Ed25519 signature and insist the envelope's
        ``alp.from`` matches the Noise-authenticated identity."""
        try:
            parsed = env.verify(body, replay_cache=self.replay)
        except env.EnvelopeError as e:
            log.debug("envelope rejected: %s", e)
            return None

        sender_pk = parsed.alp["from"]

        peer = peers_mod.get_by_pubkey(self.home, sender_pk)
        if peer is None:
            log.info("alp drop: unpinned sender %s...", sender_pk[:12])
            return None

        # A peer that passes Noise as A but signs the envelope as B is
        # silently dropped — the TCP path has already authenticated a
        # specific pinned peer via the handshake.
        if pinned_peer is not None and pinned_peer.pubkey != peer.pubkey:
            log.info(
                "alp tcp drop: noise=%s... envelope=%s...",
                pinned_peer.pubkey[:12],
                peer.pubkey[:12],
            )
            return None

        method = parsed.method
        request_id = parsed.id

        # Check rate limit before capability so unauthorised calls still
        # surface as capability-denied in the operator log instead of
        # getting swallowed by a 429.
        if not self.rate_limiter.admit(peer.pubkey, peer.rate_limit):
            log.info("alp: rate-limit %s pubkey=%s...", peer.id, peer.pubkey[:12])
            return env.build_response(
                sender=self.kp,
                recipient_pubkey_b64=sender_pk,
                request_id=request_id,
                error={
                    "code": -32005,
                    "message": "rate-limited",
                    "data": {"window_seconds": int(rl.WINDOW_SECONDS)},
                },
            )

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

        handler = self.handlers.get(method)
        if handler is None:
            return env.build_response(
                sender=self.kp,
                recipient_pubkey_b64=sender_pk,
                request_id=request_id,
                error={"code": -32601, "message": "method-not-found"},
            )

        import time as _time

        t0 = _time.monotonic()
        try:
            out = handler(parsed.params or {}, peer, self)
            if asyncio.iscoroutine(out):
                out = await out
            log.info(
                "alp: %s from %s · %.2fs",
                method,
                peer.id,
                _time.monotonic() - t0,
            )
        except HandlerError as e:
            log.info(
                "alp: %s from %s · rejected %d %s",
                method,
                peer.id,
                e.code,
                e.message,
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
