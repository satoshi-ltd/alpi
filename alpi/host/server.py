from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
from pathlib import Path
from typing import Any, Awaitable, Callable

import websockets
from websockets.asyncio.server import ServerConnection, serve as ws_serve

from alpi.host.tailscale import is_tailscale_ip


log = logging.getLogger("alpi.host.server")

DEFAULT_TCP_PORT = 49200


HandlerResult = dict[str, Any]
Handler = Callable[
    [dict[str, Any], "Server"],
    "HandlerResult | Awaitable[HandlerResult]",
]
StreamFrameSender = Callable[[dict[str, Any]], Awaitable[None]]
StreamHandler = Callable[
    [dict[str, Any], "Server", StreamFrameSender],
    Awaitable[None],
]
SendCoro = Callable[[dict[str, Any]], Awaitable[None]]


class HandlerError(Exception):
    def __init__(self, code: int, message: str, data: Any = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


class Server:
    def __init__(
        self,
        home: Path,
        tcp_bind: tuple[str, int] | None = None,
    ) -> None:
        self.home = home
        self.handlers: dict[str, Handler] = {}
        self.stream_handlers: dict[str, StreamHandler] = {}
        self._server: asyncio.AbstractServer | None = None
        self._ws_server: Any | None = None
        self._tcp_bind: tuple[str, int] | None = (
            self._validate_tcp_bind(tcp_bind) if tcp_bind else None
        )

    @staticmethod
    def _validate_tcp_bind(bind: tuple[str, int]) -> tuple[str, int]:
        host, port = bind
        if not _is_safe_bind(host):
            raise ValueError(
                f"host TCP listener refuses to bind to {host!r}: "
                "must be a Tailscale (100.64.0.0/10) or private LAN "
                "(10/8, 172.16/12, 192.168/16) address"
            )
        if not (0 < port < 65536):
            raise ValueError(f"invalid host TCP port {port!r}")
        return host, port

    def socket_path(self) -> Path:
        return self.home / "host" / "host.sock"

    def register(self, method: str, handler: Handler) -> None:
        if not method.startswith("host."):
            raise ValueError("methods must use the 'host.' namespace")
        self.handlers[method] = handler

    def register_stream(self, method: str, handler: StreamHandler) -> None:
        if not method.startswith("host."):
            raise ValueError("methods must use the 'host.' namespace")
        self.stream_handlers[method] = handler

    async def start(self) -> None:
        sock = self.socket_path()
        sock.parent.mkdir(parents=True, exist_ok=True)
        if sock.exists():
            sock.unlink()
        self._server = await asyncio.start_unix_server(
            self._handle_unix, path=str(sock),
        )
        sock.chmod(0o600)
        log.info("host server listening on %s", sock)
        if self._tcp_bind is not None:
            host, port = self._tcp_bind
            self._ws_server = await ws_serve(
                self._handle_websocket, host=host, port=port,
            )
            log.info("host server listening on ws://%s:%d", host, port)

    async def stop(self) -> None:
        if self._ws_server is not None:
            self._ws_server.close()
            await self._ws_server.wait_closed()
            self._ws_server = None
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
        tasks = [asyncio.create_task(self._server.serve_forever())]
        if self._ws_server is not None:
            tasks.append(asyncio.create_task(self._ws_server.serve_forever()))
        await asyncio.gather(*tasks)

    async def _handle_unix(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        async def send(payload: dict[str, Any]) -> None:
            data = (
                json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
                + "\n"
            ).encode("utf-8")
            writer.write(data)
            await writer.drain()

        try:
            line = await reader.readline()
            if not line:
                return
            # Unix socket = local trust, no token required.
            await self._handle_request(line.decode("utf-8"), send)
        except (ConnectionResetError, BrokenPipeError):
            return
        except Exception:  # noqa: BLE001
            log.exception("host unix connection crashed")
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:  # noqa: BLE001
                pass

    async def _handle_websocket(self, ws: ServerConnection) -> None:
        async def send(payload: dict[str, Any]) -> None:
            await ws.send(
                json.dumps(payload, separators=(",", ":"), ensure_ascii=False),
            )

        try:
            message = await ws.recv()
            line = message if isinstance(message, str) else message.decode("utf-8")
            # Remote (TCP/WS) = require a paired-device token.
            await self._handle_request(line, send, require_token=True)
        except websockets.ConnectionClosed:
            return
        except Exception:  # noqa: BLE001
            log.exception("host websocket connection crashed")

    async def _handle_request(
        self, line: str, send: SendCoro, require_token: bool = False,
    ) -> None:
        try:
            body = json.loads(line)
        except json.JSONDecodeError:
            log.debug("malformed JSON on host transport; dropping")
            return
        if require_token and not _check_token(body):
            await send({
                "id": body.get("id"),
                "error": {"code": -32000, "message": "auth-failed"},
            })
            return
        method = str(body.get("method") or "")
        if method in self.stream_handlers:
            await self._dispatch_stream(body, send)
            return
        response = await self._dispatch(body)
        if response is not None:
            await send(response)

    async def _dispatch(self, body: dict[str, Any]) -> dict[str, Any] | None:
        request_id = body.get("id")
        method = str(body.get("method") or "")
        params = body.get("params") or {}
        handler = self.handlers.get(method)
        if handler is None:
            return {
                "id": request_id,
                "error": {"code": -32601, "message": "method-not-found"},
            }
        try:
            out = handler(params, self)
            if asyncio.iscoroutine(out):
                out = await out
        except HandlerError as e:
            return {
                "id": request_id,
                "error": {"code": e.code, "message": e.message, "data": e.data},
            }
        except Exception as e:  # noqa: BLE001
            log.exception("handler %s crashed", method)
            return {
                "id": request_id,
                "error": {
                    "code": -32603,
                    "message": "internal-error",
                    "data": {"detail": str(e)},
                },
            }
        return {"id": request_id, "result": out or {}}

    async def _dispatch_stream(
        self, body: dict[str, Any], send: SendCoro,
    ) -> None:
        request_id = body.get("id")
        method = str(body.get("method") or "")
        params = body.get("params") or {}
        handler = self.stream_handlers[method]

        async def send_frame(frame: dict[str, Any]) -> None:
            await send({"id": request_id, **frame})

        try:
            await handler(params, self, send_frame)
        except HandlerError as e:
            await send_frame({
                "error": {"code": e.code, "message": e.message, "data": e.data},
            })
        except Exception as e:  # noqa: BLE001
            log.exception("stream handler %s crashed", method)
            await send_frame({
                "error": {
                    "code": -32603,
                    "message": "internal-error",
                    "data": {"detail": str(e)},
                },
            })


_PRIVATE_RANGES = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
)


def _is_safe_bind(addr: str) -> bool:
    if is_tailscale_ip(addr):
        return True
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return False
    if ip.is_loopback or ip.is_unspecified:
        return False
    return any(ip in net for net in _PRIVATE_RANGES)


def _check_token(body: dict[str, Any]) -> bool:
    # Empty store = migration window (open until first "Add device" flips enforcement on).
    from alpi.host import devices as devices_mod

    devices = devices_mod.load()
    if not devices:
        return True
    params = body.get("params") or {}
    token = str(params.get("auth_token") or "")
    method = str(body.get("method") or "?")
    if not token:
        log.warning("host auth-failed: no token sent (method=%s)", method)
        return False
    if not devices_mod.is_valid(token):
        log.warning(
            "host auth-failed: token …%s not in store (method=%s)",
            token[-8:], method,
        )
        return False
    devices_mod.touch(token)
    return True
