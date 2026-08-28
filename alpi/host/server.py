from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import os
import time
from collections import defaultdict
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path
from typing import Any, Awaitable, Callable

import websockets
from websockets.asyncio.server import ServerConnection, serve as ws_serve

from alpi.host.tailscale import is_tailscale_ip


log = logging.getLogger("alpi.host.server")

DEFAULT_TCP_PORT = 49200
WS_AUTH_TIMEOUT_SECONDS = 10.0
WS_AUTH_RECHECK_SECONDS = 1.0
WS_CLOSE_TIMEOUT_SECONDS = 1.0
WS_REVOCATION_RETRY_SECONDS = 5.0
WS_MAX_CONNECTIONS = 128
WS_MAX_CONNECTIONS_PER_DEVICE = 8
WS_MAX_RPCS_PER_DEVICE = 8
WS_MAX_QUEUE = (16, 4)


def _env_number(
    name: str, default: int | float, *, minimum: float, maximum: float,
) -> int | float:
    raw = str(os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        value = int(raw) if isinstance(default, int) else float(raw)
    except ValueError:
        log.warning("ignoring invalid %s=%r", name, raw)
        return default
    if not minimum <= value <= maximum:
        log.warning("ignoring out-of-range %s=%r", name, raw)
        return default
    return value


def _max_message_bytes() -> int:
    # Sized to the attachment contract: staging inlines a whole file as base64 in one JSON-RPC message.
    from alpi.attachments import MAX_FILE_BYTES
    return MAX_FILE_BYTES * 4 // 3 + 64 * 1024

# Reserved for the local Unix socket — even an admin remote device cannot rebind the network or restart the daemon.
_LOCAL_ONLY_METHODS = frozenset({
    "host.chat.delegate",
    "host.network.status",
    "host.network.set_advertised",
    "host.network.restart_host_server",
})

_LOCAL_ONLY_CONFIG_KEYS = frozenset({
    "alp.tcp_port",
    "host.tcp_port",
    "host.allow_public_bind",
    "host.endpoints",
    "network.host",
})

# Require ``role == "admin"`` when called over WS. Local socket bypasses (see ``devices.validate_and_lookup_role`` for the empty-store bootstrap).
_ADMIN_METHODS = frozenset({
    "host.providers.set_key",
    "host.providers.unset_key",
    "host.providers.add_ollama",
    "host.providers.remove_ollama",
    "host.providers.add_openrouter_model",
    "host.providers.remove_openrouter_model",
    "host.peers.add",
    "host.peers.remove",
    "host.peers.pending_list",
    "host.peers.pending_accept",
    "host.peers.pending_discard",
    "host.peers.ping",
    "host.identity.draft",
    "host.profile.create",
    "host.profile.delete",
    "host.profile.storage",
    "host.config.set_field",
    "host.config.unset_field",
    "host.profile.memory_read",
    "host.profile.memory_usage",
    "host.profile.memory_write",
    "host.skills.list",
    "host.skill.read",
    "host.skill.file",
    "host.schedule.list",
    "host.outputs.list",
    "host.outputs.read",
    "host.outputs.mark_read",
    "host.outputs.mark_all_read",
    "host.outputs.delete",
    "host.cleanup.plan",
    "host.cleanup.apply",
    "host.mcp.add",
    "host.mcp.remove",
    "host.mcp.tools",
    "host.email.status",
    "host.email.config",
    "host.email.probe",
    "host.email.add",
    "host.email.remove",
    "host.email.gmail.begin",
    "host.email.gmail.exchange",
    "host.sandbox.set",
    "host.sandbox.network",
    "host.voice.set_voice",
    "host.voice.set_auto_read",
    "host.sessions.delete",
    "host.schedule.fire",
    "host.schedule.remove",
    "host.schedule.set_paused",
    "host.workgroup.create",
    "host.workgroup.update",
    "host.workgroup.add_member",
    "host.workgroup.kick",
    "host.workgroup.remove",
    "host.workgroup.action",
    "host.workgroup.trigger",
    "host.workgroup.recipes.list",
    "host.workgroup.launch_recipe",
    "host.approval.respond",
    "host.daemon.restart",
    "host.daemon.update",
    "host.devices.list",
    "host.devices.generate",
    "host.devices.revoke",
    "host.devices.rename",
    "host.devices.promote",
    "host.devices.demote",
    "host.devices.set_profiles",
    "host.connections.list",
    "host.connections.create",
    "host.connections.add_device",
    "host.connections.pairing_status",
    "host.connections.cancel_pairing",
    "host.connections.update",
    "host.connections.set_status",
    "host.connections.delete",
    "host.connections.revoke_device",
    "host.connections.summary",
    "host.connections.usage_daily",
    "host.audit.list",
    "host.usage.daily",
    "host.usage.workgroup.daily",
})

# host.profile.detail leaks Settings-only fields (providers, mcps, peers, sandbox, workspace path…) inside its result blob. Members hit it from ChatPane for `models` + `voice_id`, so we can't gate the whole verb — instead redact the result down to the chat-essential fields when role != admin.
_MEMBER_DETAIL_KEEP = frozenset({"models", "voice_id", "voice_auto_read"})

# Sections of host.settings.profile_snapshot whose standalone verb is admin-only — stripped for members so the aggregate never leaks what the per-section RPC would reject.
_SNAPSHOT_ADMIN_SECTIONS = frozenset({"usage", "schedules", "email", "storage"})

# Dropped from a member's live stream AND history — else the event bus re-exposes what host.outputs.*/schedule.*/usage.* deny (schedule.* matched by prefix in _is_member_blocked_event).
_MEMBER_BLOCKED_EVENTS = frozenset({
    "agent.message",
    "output.created",
    "output.updated",
    "budget.threshold",
})


def _is_member_blocked_event(kind: Any) -> bool:
    return isinstance(kind, str) and (
        kind in _MEMBER_BLOCKED_EVENTS or kind.startswith("schedule.")
    )

# Methods that don't operate on a single profile — exempt from the scope gate. New profile-handling RPCs MUST default to denied for scoped members; add here only when the verb is truly profile-agnostic (or aggregates across profiles and the response gets scope-filtered downstream).
_SCOPE_FREE_METHODS = frozenset({
    "host.version",
    "host.profiles.list",
    "host.profile.summaries",
    "host.workgroups.list",
    "host.tools.list",
    "host.events.subscribe",
    "host.events.history",
    "host.approval.pending",
    "host.clarification.pending",
    "host.approval.respond",
    "host.connections.register_device",
    "host.workgroup.recipes.describe",
})


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


@dataclass
class WebSocketMetrics:
    handshakes: int = 0
    handshakes_rejected: int = 0
    auth_failures: int = 0
    auth_timeouts: int = 0
    protocol_failures: int = 0
    device_connections_rejected: int = 0
    device_rpcs_rejected: int = 0
    peak_connections: int = 0
    revoked_connections: int = 0
    pairing_exchange_attempts: int = 0


class Server:
    def __init__(
        self,
        home: Path,
        tcp_bind: tuple[str, int] | None = None,
        allow_public_bind: bool = False,
    ) -> None:
        self.home = home
        self.handlers: dict[str, Handler] = {}
        self.stream_handlers: dict[str, StreamHandler] = {}
        self._server: asyncio.AbstractServer | None = None
        self._ws_server: Any | None = None
        self._ws_auth_watch_task: asyncio.Task[None] | None = None
        self._allow_public_bind = allow_public_bind
        self._tcp_bind: tuple[str, int] | None = (
            self._validate_tcp_bind(tcp_bind, allow_public_bind) if tcp_bind else None
        )
        self._ws_connections: set[ServerConnection] = set()
        self._ws_tasks: dict[ServerConnection, asyncio.Task[Any]] = {}
        self._ws_identities: dict[ServerConnection, tuple[str, str]] = {}
        self._ws_by_device: dict[tuple[str, str], set[ServerConnection]] = defaultdict(set)
        self._ws_revoking: dict[ServerConnection, tuple[float, int]] = {}
        self._ws_rpc_counts: dict[tuple[str, str], int] = {}
        self._ws_metrics = WebSocketMetrics()
        self._ws_auth_timeout = float(_env_number(
            "ALPI_HOST_WS_AUTH_TIMEOUT", WS_AUTH_TIMEOUT_SECONDS,
            minimum=1.0, maximum=120.0,
        ))
        self._ws_auth_recheck = float(_env_number(
            "ALPI_HOST_WS_AUTH_RECHECK", WS_AUTH_RECHECK_SECONDS,
            minimum=0.1, maximum=60.0,
        ))
        self._ws_close_timeout = float(_env_number(
            "ALPI_HOST_WS_CLOSE_TIMEOUT", WS_CLOSE_TIMEOUT_SECONDS,
            minimum=0.1, maximum=10.0,
        ))
        self._ws_revocation_retry = float(_env_number(
            "ALPI_HOST_WS_REVOCATION_RETRY", WS_REVOCATION_RETRY_SECONDS,
            minimum=1.0, maximum=60.0,
        ))
        self._ws_max_connections = int(_env_number(
            "ALPI_HOST_WS_MAX_CONNECTIONS", WS_MAX_CONNECTIONS,
            minimum=1, maximum=10_000,
        ))
        self._ws_max_connections_per_device = int(_env_number(
            "ALPI_HOST_WS_MAX_CONNECTIONS_PER_DEVICE", WS_MAX_CONNECTIONS_PER_DEVICE,
            minimum=1, maximum=1_000,
        ))
        self._ws_max_rpcs_per_device = int(_env_number(
            "ALPI_HOST_WS_MAX_RPCS_PER_DEVICE", WS_MAX_RPCS_PER_DEVICE,
            minimum=1, maximum=1_000,
        ))

    @staticmethod
    def _validate_tcp_bind(
        bind: tuple[str, int], allow_public_bind: bool = False
    ) -> tuple[str, int]:
        host, port = bind
        if not (0 < port < 65536):
            raise ValueError(f"invalid host TCP port {port!r}")
        if not _is_safe_bind(host, allow_public_bind):
            raise ValueError(
                f"host TCP listener refuses to bind to {host!r}: a public IP "
                "exposes the host control plane. Set `host.allow_public_bind: "
                "true` to override (or use a private network / private "
                "hostname address)."
            )
        # Auto-detected binds are private addresses (and 0.0.0.0 in docker);
        # anything else here is the operator's explicit choice (public IP or
        # custom hostname) — flag it.
        if host != "0.0.0.0" and not _is_private_or_overlay(host):
            log.warning(
                "host TCP listener bound to %r — this is outside private "
                "network ranges; ensure device-pairing is your only access control.",
                host,
            )
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
            self._handle_unix, path=str(sock), limit=_max_message_bytes(),
        )
        sock.chmod(0o600)
        log.info("host server listening on %s", sock)
        if self._tcp_bind is not None:
            await self._start_ws(*self._tcp_bind)

    async def _start_ws(self, host: str, port: int) -> None:
        # permessage-deflate: 50–80% off JSON-RPC payloads on remote Tailscale; clients that don't negotiate fall back to raw.
        self._ws_server = await ws_serve(
            self._handle_websocket, host=host, port=port,
            compression="deflate", max_size=_max_message_bytes(),
            process_request=self._process_ws_handshake,
            close_timeout=self._ws_close_timeout,
            max_queue=WS_MAX_QUEUE,
        )
        self._ws_auth_watch_task = asyncio.create_task(
            self._watch_websocket_authorizations(),
        )
        log.info("host server listening on ws://%s:%d", host, port)

    async def enable_tcp(self, bind: tuple[str, int]) -> None:
        # Bind the TCP/WS listener after start(), so host.sock (Unix) comes up first — the bind address needs slow network detection.
        if self._ws_server is not None:
            return
        host, port = self._validate_tcp_bind(bind, self._allow_public_bind)
        self._tcp_bind = (host, port)
        await self._start_ws(host, port)

    async def stop(self) -> None:
        if self._ws_auth_watch_task is not None:
            self._ws_auth_watch_task.cancel()
            try:
                await self._ws_auth_watch_task
            except asyncio.CancelledError:
                pass
            self._ws_auth_watch_task = None
        if self._ws_server is not None:
            self._ws_server.close(close_connections=False)
            connections = list(self._ws_connections)
            close_tasks = [
                asyncio.create_task(ws.close(code=1001, reason="Server shutting down"))
                for ws in connections
            ]
            if close_tasks:
                _done, pending_close = await asyncio.wait(
                    close_tasks, timeout=self._ws_close_timeout * 2,
                )
                for task in pending_close:
                    task.cancel()
            current = asyncio.current_task()
            tasks = [task for task in self._ws_tasks.values() if task is not current]
            for task in tasks:
                task.cancel("server-stop")
            if tasks:
                _done, pending_handlers = await asyncio.wait(
                    tasks, timeout=self._ws_close_timeout,
                )
            else:
                pending_handlers = set()
            for ws in connections:
                if not ws.transport.is_closing():
                    ws.transport.abort()
            if close_tasks:
                await asyncio.gather(*close_tasks, return_exceptions=True)
            for task in pending_handlers:
                task.cancel("server-stop")
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

    def _process_ws_handshake(self, connection: ServerConnection, request):
        try:
            upgrades = request.headers.get_all("Upgrade")
        except Exception:  # noqa: BLE001
            self._ws_metrics.protocol_failures += 1
            return connection.respond(HTTPStatus.BAD_REQUEST, "Invalid WebSocket handshake\n")
        if not any(str(value).lower() == "websocket" for value in upgrades):
            return None
        self._ws_metrics.handshakes += 1
        if len(self._ws_connections) >= self._ws_max_connections:
            self._ws_metrics.handshakes_rejected += 1
            return connection.respond(HTTPStatus.SERVICE_UNAVAILABLE, "WebSocket capacity reached\n")
        return None

    def websocket_status(self) -> dict[str, int | float]:
        metrics = self._ws_metrics
        return {
            "active_connections": len(self._ws_connections),
            "authenticated_connections": len(self._ws_identities),
            "active_devices": len(self._ws_by_device),
            "connection_limit": self._ws_max_connections,
            "connections_per_device_limit": self._ws_max_connections_per_device,
            "rpcs_per_device_limit": self._ws_max_rpcs_per_device,
            "auth_timeout_seconds": self._ws_auth_timeout,
            "auth_recheck_seconds": self._ws_auth_recheck,
            "close_timeout_seconds": self._ws_close_timeout,
            "revocation_retry_seconds": self._ws_revocation_retry,
            "peak_connections": metrics.peak_connections,
            "handshakes": metrics.handshakes,
            "handshakes_rejected": metrics.handshakes_rejected,
            "auth_failures": metrics.auth_failures,
            "auth_timeouts": metrics.auth_timeouts,
            "protocol_failures": metrics.protocol_failures,
            "device_connections_rejected": metrics.device_connections_rejected,
            "device_rpcs_rejected": metrics.device_rpcs_rejected,
            "revoked_connections": metrics.revoked_connections,
            "pairing_exchange_attempts": metrics.pairing_exchange_attempts,
        }

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

        if len(self._ws_connections) >= self._ws_max_connections:
            self._ws_metrics.handshakes_rejected += 1
            await ws.close(code=1013, reason="WebSocket capacity reached")
            return
        self._ws_connections.add(ws)
        task = asyncio.current_task()
        if task is not None:
            self._ws_tasks[ws] = task
        self._ws_metrics.peak_connections = max(
            self._ws_metrics.peak_connections,
            len(self._ws_connections),
        )
        try:
            try:
                message = await asyncio.wait_for(ws.recv(), timeout=self._ws_auth_timeout)
            except asyncio.TimeoutError:
                self._ws_metrics.auth_timeouts += 1
                await ws.close(code=1008, reason="Authentication timeout")
                return
            pairing_request = _preauth_pairing_request(message)
            if pairing_request is not None:
                self._ws_metrics.pairing_exchange_attempts += 1
                await self._handle_request(pairing_request, send, bootstrap=True)
                await ws.close(code=1000, reason="Pairing exchange complete")
                return
            authenticated = await self._authenticate_websocket_message(message, send)
            if authenticated is None:
                await ws.close(code=1008, reason="Authentication failed")
                return
            line, body, meta = authenticated
            if not self._register_websocket_identity(ws, meta):
                self._ws_metrics.device_connections_rejected += 1
                await send({
                    "id": body.get("id"),
                    "error": {
                        "code": -32029,
                        "message": "too-many-connections",
                        "data": {"detail": "device WebSocket limit reached"},
                    },
                })
                await ws.close(code=1013, reason="Device connection limit reached")
                return
            await self._handle_request(
                line, send, require_token=True, authenticated=meta,
            )
            async for message in ws:
                authenticated = await self._authenticate_websocket_message(message, send)
                if authenticated is None:
                    await ws.close(code=1008, reason="Authentication failed")
                    return
                line, body, meta = authenticated
                if (meta.connection_id, meta.device_id) != self._ws_identities.get(ws):
                    self._ws_metrics.auth_failures += 1
                    await send({
                        "id": body.get("id"),
                        "error": {
                            "code": -32000,
                            "message": "auth-failed",
                            "data": {"reason": "socket-identity-changed"},
                        },
                    })
                    await ws.close(code=1008, reason="Socket identity changed")
                    return
                await self._handle_request(
                    line, send, require_token=True, authenticated=meta,
                )
        except websockets.ConnectionClosed:
            return
        except Exception:  # noqa: BLE001
            log.exception("host websocket connection crashed")
        finally:
            self._unregister_websocket(ws)

    async def _authenticate_websocket_message(
        self, message: str | bytes, send: SendCoro,
    ) -> tuple[str, dict[str, Any], "AuthMeta"] | None:
        try:
            line = message if isinstance(message, str) else message.decode("utf-8")
            body = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._ws_metrics.protocol_failures += 1
            await send({
                "id": None,
                "error": {"code": -32700, "message": "parse-error"},
            })
            return None
        if not isinstance(body, dict):
            self._ws_metrics.protocol_failures += 1
            await send({
                "id": None,
                "error": {"code": -32600, "message": "invalid-request"},
            })
            return None
        meta = await asyncio.to_thread(_check_token_meta, body)
        if not meta.valid:
            self._ws_metrics.auth_failures += 1
            error: dict[str, Any] = {"code": -32000, "message": "auth-failed"}
            if meta.reason:
                error["data"] = {"reason": meta.reason}
            await send({"id": body.get("id"), "error": error})
            return None
        return line, body, meta

    def _register_websocket_identity(self, ws: ServerConnection, meta: "AuthMeta") -> bool:
        key = (meta.connection_id, meta.device_id)
        sockets = self._ws_by_device[key]
        if len(sockets) >= self._ws_max_connections_per_device:
            if not sockets:
                self._ws_by_device.pop(key, None)
            return False
        sockets.add(ws)
        self._ws_identities[ws] = key
        return True

    def _unregister_websocket(self, ws: ServerConnection) -> None:
        self._ws_connections.discard(ws)
        self._ws_revoking.pop(ws, None)
        self._ws_tasks.pop(ws, None)
        key = self._ws_identities.pop(ws, None)
        if key is None:
            return
        sockets = self._ws_by_device.get(key)
        if sockets is not None:
            sockets.discard(ws)
            if not sockets:
                self._ws_by_device.pop(key, None)

    def _begin_device_rpc(self, meta: "AuthMeta") -> bool:
        key = (meta.connection_id, meta.device_id)
        active = self._ws_rpc_counts.get(key, 0)
        if active >= self._ws_max_rpcs_per_device:
            self._ws_metrics.device_rpcs_rejected += 1
            return False
        self._ws_rpc_counts[key] = active + 1
        return True

    def _end_device_rpc(self, meta: "AuthMeta") -> None:
        key = (meta.connection_id, meta.device_id)
        active = self._ws_rpc_counts.get(key, 0)
        if active <= 1:
            self._ws_rpc_counts.pop(key, None)
        else:
            self._ws_rpc_counts[key] = active - 1

    async def close_device_websockets(
        self, connection_id: str, device_id: str, *,
        exclude_task: asyncio.Task[Any] | None = None,
    ) -> int:
        sockets = list(self._ws_by_device.get((connection_id, device_id), ()))
        if not sockets:
            return 0
        now = time.monotonic()
        cancel: list[ServerConnection] = []
        for ws in sockets:
            state = self._ws_revoking.get(ws)
            if state is None:
                state = (now, 0)
                self._ws_metrics.revoked_connections += 1
            first_seen, attempts = state
            if attempts == 0 or now >= first_seen + attempts * self._ws_revocation_retry:
                cancel.append(ws)
                attempts += 1
            self._ws_revoking[ws] = (first_seen, attempts)
        await asyncio.gather(*(
            ws.close(code=1008, reason="Device authorization revoked")
            for ws in sockets
        ), return_exceptions=True)
        caller = exclude_task or asyncio.current_task()
        for ws in cancel:
            task = self._ws_tasks.get(ws)
            if task is not None and task is not caller:
                task.cancel()
        return len(sockets)

    async def close_connection_websockets(self, connection_id: str) -> int:
        identities = [key for key in self._ws_by_device if key[0] == connection_id]
        if not identities:
            return 0
        caller = asyncio.current_task()
        closed = await asyncio.gather(*(
            self.close_device_websockets(*key, exclude_task=caller)
            for key in identities
        ))
        return sum(closed)

    async def _watch_websocket_authorizations(self) -> None:
        while True:
            await asyncio.sleep(self._ws_auth_recheck)
            if not self._ws_identities:
                continue
            try:
                active = await asyncio.to_thread(_active_authorizations)
            except Exception:  # noqa: BLE001
                log.exception("cannot verify active WebSocket authorizations")
                active = set()
            stale = [key for key in self._ws_by_device if key not in active]
            if stale:
                caller = asyncio.current_task()
                await asyncio.gather(*(
                    self.close_device_websockets(*key, exclude_task=caller)
                    for key in stale
                ))

    async def _handle_request(
        self, line: str, send: SendCoro, require_token: bool = False,
        authenticated: "AuthMeta | None" = None,
        bootstrap: bool = False,
    ) -> None:
        try:
            body = json.loads(line)
        except json.JSONDecodeError:
            log.debug("malformed JSON on host transport; dropping")
            return
        # Unix socket is the source of trust; treat as admin-equivalent.
        role = "admin"
        profile_scope: list[str] = []
        from alpi.host.connection_context import ConnectionContext, use as use_connection
        request_context = ConnectionContext(
            connection_id="bootstrap" if bootstrap else "host",
            source="bootstrap" if bootstrap else "local",
            role="member" if bootstrap else "admin",
        )
        method = str(body.get("method") or "")
        audit_params = body.get("params") if isinstance(body.get("params"), dict) else {}
        remote_meta: AuthMeta | None = None
        if require_token:
            meta = authenticated or await asyncio.to_thread(_check_token_meta, body)
            valid, role, profile_scope = meta
            if not valid:
                from alpi.host import admin_audit
                denied_context = ConnectionContext(
                    connection_id=meta.connection_id or "unauthenticated",
                    device_id=meta.device_id or None,
                    source="remote",
                    role=meta.role or "",
                )
                await asyncio.to_thread(
                    admin_audit.record_auth_failed,
                    self.home,
                    method,
                    denied_context,
                )
                error: dict[str, Any] = {"code": -32000, "message": "auth-failed"}
                if meta.reason:
                    error["data"] = {"reason": meta.reason}
                await send({
                    "id": body.get("id"),
                    "error": error,
                })
                return
            if isinstance(meta, AuthMeta):
                request_context = ConnectionContext(
                    connection_id=meta.connection_id,
                    device_id=meta.device_id,
                    source="remote",
                    role=meta.role or "member",
                )
                remote_meta = meta
        if bootstrap and method != "host.connections.exchange_pairing":
            await send({
                "id": body.get("id"),
                "error": {"code": -32001, "message": "forbidden"},
            })
            return
        if require_token and method == "host.connections.exchange_pairing":
            from alpi.host import admin_audit
            await asyncio.to_thread(
                admin_audit.record_denied,
                self.home,
                method,
                audit_params,
                request_context,
            )
            await send({
                "id": body.get("id"),
                "error": {
                    "code": -32001,
                    "message": "forbidden",
                    "data": {"detail": "pairing exchange is pre-authentication only"},
                },
            })
            return
        if require_token and method in _LOCAL_ONLY_METHODS:
            log.warning("host forbidden: %s blocked over remote transport", method)
            from alpi.host import admin_audit
            await asyncio.to_thread(
                admin_audit.record_denied,
                self.home,
                method,
                audit_params,
                request_context,
            )
            await send({
                "id": body.get("id"),
                "error": {
                    "code": -32001,
                    "message": "forbidden",
                    "data": {"detail": "method is local-only"},
                },
            })
            return
        if require_token and method in ("host.config.set_field", "host.config.unset_field"):
            params = body.get("params") if isinstance(body.get("params"), dict) else {}
            if str(params.get("key") or "") in _LOCAL_ONLY_CONFIG_KEYS:
                log.warning("host forbidden: config key %r is local-only", params.get("key"))
                from alpi.host import admin_audit
                await asyncio.to_thread(
                    admin_audit.record_denied,
                    self.home,
                    method,
                    audit_params,
                    request_context,
                )
                await send({
                    "id": body.get("id"),
                    "error": {
                        "code": -32001,
                        "message": "forbidden",
                        "data": {"detail": "config key is local-only"},
                    },
                })
                return
        if require_token and method in _ADMIN_METHODS and role != "admin":
            log.warning("host forbidden: %s blocked for role=%s", method, role)
            from alpi.host import admin_audit
            await asyncio.to_thread(
                admin_audit.record_denied,
                self.home,
                method,
                audit_params,
                request_context,
            )
            await send({
                "id": body.get("id"),
                "error": {
                    "code": -32001,
                    "message": "forbidden",
                    "data": {"detail": "admin role required"},
                },
            })
            return
        # Empty profile_scope = unrestricted; admin role bypasses by design. For scoped members, REQUIRE params.profile explicit + in scope on every profile-aware method (default would otherwise let a missing/empty profile fall through to the daemon's "default" profile).
        if (
            require_token
            and role != "admin"
            and profile_scope
            and method not in _SCOPE_FREE_METHODS
        ):
            params = body.get("params") if isinstance(body.get("params"), dict) else {}
            target = params.get("profile")
            if (not isinstance(target, str) or not target) and method == "host.clarification.respond":
                from alpi.host import clarification
                target = clarification.pending_profile(params.get("request_id"))
            if not isinstance(target, str) or not target:
                log.warning(
                    "host forbidden: %s requires explicit profile for scoped token",
                    method,
                )
                await send({
                    "id": body.get("id"),
                    "error": {
                        "code": -32001,
                        "message": "forbidden",
                        "data": {"detail": "method requires an explicit profile for scoped device"},
                    },
                })
                return
            if target not in profile_scope:
                log.warning(
                    "host forbidden: %s blocked for token, profile=%r not in scope=%s",
                    method, target, profile_scope,
                )
                await send({
                    "id": body.get("id"),
                    "error": {
                        "code": -32001,
                        "message": "forbidden",
                        "data": {"detail": "profile not in device scope"},
                    },
                })
                return
        # Normalise `params` to dict up front — handlers assume `(params or {}).get(...)` shape; an array/string body otherwise surfaces as a confusing internal-error.
        raw_params = body.get("params")
        if raw_params is not None and not isinstance(raw_params, dict):
            await send({
                "id": body.get("id"),
                "error": {
                    "code": -32602,
                    "message": "invalid-params",
                    "data": {"detail": "params must be an object"},
                },
            })
            return
        scoped = require_token and role != "admin" and bool(profile_scope)
        member = require_token and role != "admin"
        if scoped or member:
            async def send_filtered(payload: dict[str, Any]) -> None:
                out = payload
                if scoped:
                    out = _filter_payload_by_scope(method, out, profile_scope)
                    if out is None:
                        return
                if member:
                    out = _redact_payload_by_role(method, out)
                    if out is None:
                        return
                await send(out)
            delivery = send_filtered
        else:
            delivery = send
        with use_connection(request_context):
            if remote_meta is not None and not self._begin_device_rpc(remote_meta):
                await delivery({
                    "id": body.get("id"),
                    "error": {
                        "code": -32029,
                        "message": "too-many-requests",
                        "data": {"detail": "device RPC concurrency limit reached"},
                    },
                })
                return
            try:
                if method in self.stream_handlers:
                    await self._dispatch_stream(body, delivery)
                    return
                response = await self._dispatch(body, expose_internal_errors=not bootstrap)
                from alpi.host import admin_audit
                if admin_audit.is_audited(method):
                    await asyncio.to_thread(
                        admin_audit.record_request,
                        self.home,
                        method,
                        raw_params or {},
                        response,
                    )
                if response is not None:
                    await delivery(response)
            finally:
                if remote_meta is not None:
                    self._end_device_rpc(remote_meta)

    async def _dispatch(
        self, body: dict[str, Any], *, expose_internal_errors: bool = True,
    ) -> dict[str, Any] | None:
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
            error: dict[str, Any] = {
                "code": -32603,
                "message": "internal-error",
            }
            if expose_internal_errors:
                error["data"] = {"detail": str(e)}
            return {
                "id": request_id,
                "error": error,
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
        except (websockets.ConnectionClosed, ConnectionResetError, BrokenPipeError):
            return
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


def _is_private_or_overlay(addr: str) -> bool:
    if is_tailscale_ip(addr):
        return True
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return False
    return any(ip in net for net in _PRIVATE_RANGES)


def _is_safe_bind(addr: str, allow_public: bool = False) -> bool:
    # Inputs come from resolve_bind_host: 0.0.0.0, a local IP, or a hostname —
    # public IPs are already gated there. This is defence-in-depth.
    if not str(addr).strip():
        return False
    if addr == "0.0.0.0":  # all interfaces; resolve_bind_host's safe default
        return True
    if is_tailscale_ip(addr):
        return True
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return True  # hostname — resolved at bind time, a bad one fails there
    if ip.is_loopback:
        return False
    if any(ip in net for net in _PRIVATE_RANGES):
        return True
    return allow_public  # a public IP only with the explicit opt-in


def _redact_payload_by_role(method: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    # Strip Settings-only fields from rich profile.detail blob; admin role bypasses this wrapper entirely so the redaction only kicks in for member tokens.
    if not isinstance(payload, dict):
        return payload
    # Live event frame: {event, data, at, seq}. Drop entirely when its kind exposes an admin-only surface.
    if "data" in payload and _is_member_blocked_event(payload.get("event")):
        return None
    result = payload.get("result")
    if not isinstance(result, dict):
        return payload
    if method == "host.profile.detail":
        redacted = {k: v for k, v in result.items() if k in _MEMBER_DETAIL_KEEP}
        return {**payload, "result": redacted}
    if method == "host.settings.profile_snapshot":
        redacted = {k: v for k, v in result.items() if k not in _SNAPSHOT_ADMIN_SECTIONS}
        detail = redacted.get("detail")
        if isinstance(detail, dict):
            redacted["detail"] = {k: v for k, v in detail.items() if k in _MEMBER_DETAIL_KEEP}
        return {**payload, "result": redacted}
    if method == "host.events.history":
        events = result.get("events")
        if isinstance(events, list):
            result["events"] = [
                ev for ev in events
                if not (isinstance(ev, dict) and _is_member_blocked_event(ev.get("event")))
            ]
    return payload


def _filter_payload_by_scope(
    method: str, payload: dict[str, Any], scope: list[str],
) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return payload
    # Event-stream frame: {event, data: {profile, …}, at, seq}. Drop entirely when out of scope.
    if "event" in payload and "data" in payload:
        target = (payload.get("data") or {}).get("profile")
        if target and target not in scope:
            return None
        return payload
    result = payload.get("result")
    if not isinstance(result, dict):
        return payload
    if method == "host.profiles.list":
        rows = result.get("profiles")
        if isinstance(rows, list):
            result["profiles"] = [
                r for r in rows
                if (isinstance(r, str) and r in scope)
                or (isinstance(r, dict) and r.get("name") in scope)
            ]
    elif method == "host.profile.summaries":
        rows = result.get("profiles")
        if isinstance(rows, list):
            result["profiles"] = [
                r for r in rows
                if isinstance(r, dict) and r.get("name") in scope
            ]
    elif method == "host.workgroups.list":
        rows = result.get("workgroups")
        if isinstance(rows, list):
            result["workgroups"] = [
                w for w in rows
                if isinstance(w, dict) and w.get("profile") in scope
            ]
    elif method == "host.settings.profile_snapshot":
        wg = result.get("workgroups")
        if isinstance(wg, dict) and isinstance(wg.get("workgroups"), list):
            wg["workgroups"] = [
                w for w in wg["workgroups"]
                if isinstance(w, dict) and w.get("profile") in scope
            ]
    elif method in ("host.approval.pending", "host.clarification.pending"):
        rows = result.get("requests")
        if isinstance(rows, list):
            result["requests"] = [
                r for r in rows
                if isinstance(r, dict) and r.get("profile") in scope
            ]
    elif method == "host.events.history":
        events = result.get("events")
        if isinstance(events, list):
            result["events"] = [
                ev for ev in events
                if not (
                    isinstance(ev, dict)
                    and isinstance(ev.get("data"), dict)
                    and ev["data"].get("profile")
                    and ev["data"]["profile"] not in scope
                )
            ]
    return payload


def _check_token(body: dict[str, Any]) -> bool:
    return bool(_check_token_meta(body).valid)


def _check_token_role(body: dict[str, Any]) -> tuple[bool, str]:
    valid, role, _ = _check_token_meta(body)
    return valid, role


def _active_authorizations() -> set[tuple[str, str]]:
    from alpi.host import connections as connections_mod

    if connections_mod.store_path().exists():
        data = connections_mod.load_auth_store()
        return {
            (connection["id"], device["id"])
            for connection in data["connections"]
            if connection["status"] == "active"
            for device in connection["devices"]
            if device["status"] == "active" and device.get("token")
        }
    from alpi.host import devices as devices_mod

    return {
        (f"legacy_{row['token'][-8:]}", f"legacy_{row['token'][-8:]}")
        for row in devices_mod.load()
        if row.get("token")
    }


@dataclass(frozen=True)
class AuthMeta:
    valid: bool
    role: str
    scope: list[str]
    connection_id: str = ""
    device_id: str = ""
    reason: str = ""

    def __iter__(self):
        yield self.valid
        yield self.role
        yield self.scope


def _preauth_pairing_request(message: str | bytes) -> str | None:
    try:
        line = message if isinstance(message, str) else message.decode("utf-8")
        body = json.loads(line)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(body, dict) or body.get("method") != "host.connections.exchange_pairing":
        return None
    return line


def _check_token_meta(body: dict[str, Any]) -> AuthMeta:
    from alpi.host import connections as connections_mod

    params = body.get("params") or {}
    token = str(params.get("auth_token") or "")
    method = str(body.get("method") or "?")
    if connections_mod.store_path().exists():
        auth = connections_mod.authenticate(token)
    else:
        from alpi.host import devices as devices_mod
        valid, role, scope = devices_mod.validate_and_lookup(token)
        if valid:
            return AuthMeta(True, role, scope, f"legacy_{token[-8:]}", f"legacy_{token[-8:]}")
        auth = connections_mod.AuthResult(False)
    if not auth.valid:
        if not token:
            log.warning("host auth-failed: no token sent (method=%s)", method)
        elif auth.reason == "connection-disabled":
            log.warning("host auth-failed: connection disabled (method=%s)", method)
        else:
            log.warning(
                "host auth-failed: invalid token (len=%d, method=%s)",
                len(token), method,
            )
        return AuthMeta(
            False,
            "",
            [],
            auth.connection_id,
            auth.device_id,
            auth.reason,
        )
    return AuthMeta(
        True,
        auth.role,
        list(auth.profile_scope),
        auth.connection_id,
        auth.device_id,
    )
