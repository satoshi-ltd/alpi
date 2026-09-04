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


# Cap concurrent unauthenticated handshakes — bounds responder keygen/DH CPU before the per-pubkey rate limiter applies.
_MAX_INFLIGHT_HANDSHAKES = 32


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
        self.replay = env.ReplayCache(
            path=home / "alp" / "secrets" / "replay.jsonl",
        )
        self.rate_limiter = rl.RateLimiter()
        self.pull_rate_limiter = rl.RateLimiter(default_per_minute=600)
        self.file_rate_limiter = rl.RateLimiter(default_per_minute=600)
        self.handlers: dict[str, Handler] = {}
        self._handshake_sem: asyncio.Semaphore | None = None
        self._server: asyncio.AbstractServer | None = None
        self._tcp_server: asyncio.AbstractServer | None = None
        self._tcp_writers: set[asyncio.StreamWriter] = set()
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
            limit=tcp.MAX_FRAME_BYTES + 1,
        )
        sock.chmod(0o600)
        log.info("alp server listening on %s", sock)
        if self._tcp_port is not None:
            try:
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
            except OSError as e:
                # TCP bind failed (Tailscale/VPN down, port in use, IP not
                # local). The Unix socket still works for intra-machine
                # peers, so we degrade gracefully instead of taking the
                # whole listener down. Inter-machine peers won't reach us
                # until the operator fixes the network.
                log.warning(
                    "alp tcp bind failed on %s:%d (%s) — "
                    "running unix-socket-only",
                    self._tcp_host, self._tcp_port, e,
                )
                self._tcp_server = None

    async def stop(self) -> None:
        for s in (self._server, self._tcp_server):
            if s is not None:
                s.close()
                await s.wait_closed()
        writers = list(self._tcp_writers)
        for writer in writers:
            writer.close()
        if writers:
            await asyncio.gather(
                *(writer.wait_closed() for writer in writers),
                return_exceptions=True,
            )
        self._tcp_writers.clear()
        self.replay.close()
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
            async for response in self._dispatch_envelopes(body):
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
        except (BrokenPipeError, ConnectionResetError):
            log.info("alp unix client disconnected before the response completed")
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
        self._tcp_writers.add(writer)
        try:
            static_x = ed25519_to_x25519_private(self.kp.private)
            sem = self._handshake_sem
            if sem is None:
                sem = self._handshake_sem = asyncio.Semaphore(_MAX_INFLIGHT_HANDSHAKES)
            try:
                async with sem:
                    cs_send, cs_recv, remote_x = await tcp.perform_handshake_responder(
                        reader,
                        writer,
                        static_x,
                    )
            except tcp.TransportError as e:
                log.info("alp tcp: handshake failed from %s: %s", peername, e)
                return

            expected_peer = tcp.find_peer_by_x25519(self.home, remote_x)
            while True:
                try:
                    idle_timeout = (
                        tcp.SESSION_IDLE_TIMEOUT
                        if expected_peer is not None
                        else tcp.HANDSHAKE_TIMEOUT
                    )
                    plaintext = await asyncio.wait_for(
                        tcp.recv_envelope(reader, cs_recv),
                        timeout=idle_timeout,
                    )
                except asyncio.TimeoutError:
                    log.debug("alp tcp: idle session closed from %s", peername)
                    break
                except tcp.TransportError as e:
                    log.debug("alp tcp: session ended from %s: %s", peername, e)
                    break
                try:
                    body = json.loads(plaintext)
                except json.JSONDecodeError:
                    log.debug("alp tcp: malformed JSON after decrypt; dropping")
                    break

                responses = 0
                async for response in self._dispatch_envelopes(
                    body,
                    pinned_peer=expected_peer,
                ):
                    responses += 1
                    payload = json.dumps(
                        response,
                        separators=(",", ":"),
                        ensure_ascii=False,
                    ).encode("utf-8")
                    try:
                        await tcp.send_envelope(writer, cs_send, payload)
                    except tcp.TransportError as e:
                        log.debug("alp tcp: send failed: %s", e)
                        return
                if responses == 0:
                    break
        except Exception:  # noqa: BLE001
            log.exception("alp tcp connection crashed")
        finally:
            self._tcp_writers.discard(writer)
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
        """Thin wrapper that drains the streaming dispatcher into the
        first envelope. Used by tests and any caller that doesn't want
        to iterate frames (single-response handlers always yield one)."""
        async for envelope in self._dispatch_envelopes(body, pinned_peer=pinned_peer):
            return envelope
        return None

    async def _dispatch_envelopes(
        self,
        body: dict[str, Any],
        *,
        pinned_peer: peers_mod.Peer | None = None,
    ):
        """Envelope verify → peer lookup → capability → invoke → reply.

        Yields one or more signed response envelopes for the request.
        Non-streaming handlers (return dict or coroutine of dict) yield
        exactly one envelope. Streaming handlers (return async generator
        of dicts) yield one envelope per chunk, with the last marked
        ``stream="final"`` and the intermediates ``stream="chunk"``.

        ``pinned_peer`` is set by the TCP path once the Noise handshake
        authenticated the sender's static key; we still verify the
        envelope's Ed25519 signature and insist the envelope's
        ``alp.from`` matches the Noise-authenticated identity."""
        import inspect

        try:
            parsed = env.verify(
                body,
                replay_cache=self.replay,
                expected_to=self.kp.pubkey_b64(),
            )
        except env.EnvelopeError as e:
            log.debug("envelope rejected: %s", e)
            return

        sender_pk = parsed.alp["from"]

        peer = peers_mod.get_by_pubkey(self.home, sender_pk)
        if peer is None:
            log.info("alp drop: unpinned sender %s...", sender_pk[:12])
            from alpi.alp import pending as _pending
            _pending.record(self.home, sender_pk)
            return

        if pinned_peer is not None and pinned_peer.pubkey != peer.pubkey:
            log.info(
                "alp tcp drop: noise=%s... envelope=%s...",
                pinned_peer.pubkey[:12],
                peer.pubkey[:12],
            )
            return

        method = parsed.method
        request_id = parsed.id

        def _err(code: int, message: str, data: dict | None = None) -> dict:
            return env.build_response(
                sender=self.kp,
                recipient_pubkey_b64=sender_pk,
                request_id=request_id,
                error={"code": code, "message": message, "data": data},
            )

        try:
            request_offset = int((parsed.params or {}).get("offset", 0) or 0)
        except (TypeError, ValueError):
            request_offset = 0
        continuation = (
            method in {"workgroup.file_put", "workgroup.file_get"}
            and request_offset > 0
        )
        if continuation:
            limiter = self.file_rate_limiter
        elif method == "workgroup.pull":
            limiter = self.pull_rate_limiter
        else:
            limiter = self.rate_limiter
        rate_config = (
            None if continuation or method == "workgroup.pull"
            else peer.rate_limit
        )
        if not limiter.admit(peer.pubkey, rate_config):
            log.info("alp: rate-limit %s pubkey=%s...", peer.id, peer.pubkey[:12])
            yield _err(-32005, "rate-limited", {"window_seconds": int(rl.WINDOW_SECONDS)})
            return

        if method is None or not peer.may_call(method):
            yield _err(-32001, "capability-denied", {"method": method})
            return

        handler = self.handlers.get(method)
        if handler is None:
            yield _err(-32601, "method-not-found", None)
            return

        from alpi import config as _cfg_mod
        from alpi import ledger as _ledger

        try:
            _ledger.check(self.home, _cfg_mod.load(self.home).budget)
        except _ledger.BudgetExceeded as e:
            log.info("alp: budget-exceeded %s (%s)", peer.id, e)
            yield _err(
                -32005, "budget-exceeded",
                {"cap_kind": e.cap_kind, "cap": e.cap, "used": e.used},
            )
            return

        import time as _time

        t0 = _time.monotonic()
        try:
            out = handler(parsed.params or {}, peer, self)
            if asyncio.iscoroutine(out):
                out = await out
        except HandlerError as e:
            log.info(
                "alp: %s from %s · rejected %d %s",
                method, peer.id, e.code, e.message,
            )
            yield _err(e.code, e.message, e.data)
            return
        except Exception as e:  # noqa: BLE001
            log.exception("handler %s crashed", method)
            yield _err(-32603, "internal-error", {"detail": str(e)})
            return

        if inspect.isasyncgen(out):
            # Streaming handler. Convention: each yielded dict carries a
            # ``"kind"`` key, ``"chunk"`` for intermediate frames or
            # ``"final"`` for the last. Server strips ``kind`` and sets
            # the envelope ``stream`` marker so clients can correlate
            # frames to the same request without inspecting the payload.
            try:
                n = 0
                async for chunk in out:
                    n += 1
                    kind = chunk.pop("kind", "chunk") if isinstance(chunk, dict) else "chunk"
                    yield env.build_response(
                        sender=self.kp,
                        recipient_pubkey_b64=sender_pk,
                        request_id=request_id,
                        result=chunk,
                        stream=kind,
                    )
                log.info(
                    "alp: %s from %s · stream %d frames · %.2fs",
                    method, peer.id, n, _time.monotonic() - t0,
                )
            except Exception as e:  # noqa: BLE001
                log.exception("handler %s stream crashed", method)
                yield _err(-32603, "internal-error", {"detail": str(e)})
            finally:
                await out.aclose()
            return

        log.info(
            "alp: %s from %s · %.2fs",
            method, peer.id, _time.monotonic() - t0,
        )
        yield env.build_response(
            sender=self.kp,
            recipient_pubkey_b64=sender_pk,
            request_id=request_id,
            result=out or {},
        )
