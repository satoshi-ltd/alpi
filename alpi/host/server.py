from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable

import websockets
from websockets.asyncio.server import ServerConnection, serve as ws_serve

from alpi.host.tailscale import is_tailscale_ip


log = logging.getLogger("alpi.host.server")

DEFAULT_TCP_PORT = 49200

# Reserved for the local Unix socket — even an admin remote device cannot rebind the network or restart the daemon.
_LOCAL_ONLY_METHODS = frozenset({
    "host.network.status",
    "host.network.set_advertised",
    "host.network.restart_host_server",
})

_LOCAL_ONLY_CONFIG_KEYS = frozenset({
    "alp.tcp_port",
    "host.tcp_port",
    "host.allow_public_bind",
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
    "host.profile.memory_write",
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
    "host.connections.update",
    "host.connections.set_status",
    "host.connections.delete",
    "host.connections.revoke_device",
    "host.connections.summary",
    "host.connections.usage_daily",
    "host.usage.daily",
    "host.usage.workgroup.daily",
})

# host.profile.detail leaks Settings-only fields (providers, mcps, peers, sandbox, workspace path…) inside its result blob. Members hit it from ChatPane for `models` + `voice_id`, so we can't gate the whole verb — instead redact the result down to the chat-essential fields when role != admin.
_MEMBER_DETAIL_KEEP = frozenset({"models", "voice_id", "voice_auto_read"})

# Sections of host.settings.profile_snapshot whose standalone verb is admin-only — stripped for members so the aggregate never leaks what the per-section RPC would reject.
_SNAPSHOT_ADMIN_SECTIONS = frozenset({"usage", "schedules", "email", "storage"})

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
        self._allow_public_bind = allow_public_bind
        self._tcp_bind: tuple[str, int] | None = (
            self._validate_tcp_bind(tcp_bind, allow_public_bind) if tcp_bind else None
        )

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
                "true` to override (or use a Tailscale / private-LAN / private "
                "hostname address)."
            )
        # Auto-detected binds are Tailscale/private-LAN (and 0.0.0.0 in docker);
        # anything else here is the operator's explicit choice (public IP or
        # custom hostname) — flag it.
        if host != "0.0.0.0" and not _is_private_or_overlay(host):
            log.warning(
                "host TCP listener bound to %r — this is outside Tailscale/"
                "private LAN; ensure device-pairing is your only access control.",
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
            self._handle_unix, path=str(sock),
        )
        sock.chmod(0o600)
        log.info("host server listening on %s", sock)
        if self._tcp_bind is not None:
            await self._start_ws(*self._tcp_bind)

    async def _start_ws(self, host: str, port: int) -> None:
        # permessage-deflate: 50–80% off JSON-RPC payloads on remote Tailscale; clients that don't negotiate fall back to raw.
        self._ws_server = await ws_serve(
            self._handle_websocket, host=host, port=port,
            compression="deflate",
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
            async for message in ws:
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
        # Unix socket is the source of trust; treat as admin-equivalent.
        role = "admin"
        profile_scope: list[str] = []
        from alpi.host.connection_context import ConnectionContext, use as use_connection
        request_context = ConnectionContext(source="local")
        if require_token:
            meta = await asyncio.to_thread(_check_token_meta, body)
            valid, role, profile_scope = meta
            if not valid:
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
                )
        method = str(body.get("method") or "")
        if require_token and method in _LOCAL_ONLY_METHODS:
            log.warning("host forbidden: %s blocked over remote transport", method)
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
                await send(out)
            delivery = send_filtered
        else:
            delivery = send
        with use_connection(request_context):
            if method in self.stream_handlers:
                await self._dispatch_stream(body, delivery)
                return
            response = await self._dispatch(body)
            if response is not None:
                await delivery(response)

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


def _redact_payload_by_role(method: str, payload: dict[str, Any]) -> dict[str, Any]:
    # Strip Settings-only fields from rich profile.detail blob; admin role bypasses this wrapper entirely so the redaction only kicks in for member tokens.
    if not isinstance(payload, dict):
        return payload
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
