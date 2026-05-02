from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Awaitable, Callable


log = logging.getLogger("alpi.host.server")


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


class HandlerError(Exception):
    def __init__(self, code: int, message: str, data: Any = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


class Server:
    def __init__(self, home: Path) -> None:
        self.home = home
        self.handlers: dict[str, Handler] = {}
        self.stream_handlers: dict[str, StreamHandler] = {}
        self._server: asyncio.AbstractServer | None = None

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
            self._handle_connection, path=str(sock),
        )
        sock.chmod(0o600)
        log.info("host server listening on %s", sock)

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
        await self._server.serve_forever()

    async def _handle_connection(
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
                log.debug("malformed JSON on host socket; dropping")
                return
            method = str(body.get("method") or "")
            if method in self.stream_handlers:
                await self._dispatch_stream(body, writer)
                return
            response = await self._dispatch(body)
            if response is None:
                return
            await self._send_line(writer, response)
        except Exception:  # noqa: BLE001
            log.exception("host connection crashed")
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:  # noqa: BLE001
                pass

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
        self, body: dict[str, Any], writer: asyncio.StreamWriter,
    ) -> None:
        request_id = body.get("id")
        method = str(body.get("method") or "")
        params = body.get("params") or {}
        handler = self.stream_handlers[method]

        async def send_frame(frame: dict[str, Any]) -> None:
            await self._send_line(writer, {"id": request_id, **frame})

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

    async def _send_line(
        self, writer: asyncio.StreamWriter, payload: dict[str, Any],
    ) -> None:
        line = (
            json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
            + "\n"
        ).encode("utf-8")
        try:
            writer.write(line)
            await writer.drain()
        except (ConnectionResetError, BrokenPipeError):
            raise
