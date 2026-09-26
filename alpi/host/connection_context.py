from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Iterator


HOST_CONNECTION_ID = "host"


@dataclass(frozen=True)
class ConnectionContext:
    connection_id: str = HOST_CONNECTION_ID
    device_id: str | None = None
    source: str = "host"
    # Local socket is sovereign; remote contexts carry the authenticated role for role-aware handlers.
    role: str = "admin"
    session_scope: str = "connection"
    provisioner: bool = False


_current: ContextVar[ConnectionContext] = ContextVar(
    "host_connection_context",
    default=ConnectionContext(),
)


def current() -> ConnectionContext:
    return _current.get()


def can_read_connection(owner_connection_id: str | None) -> bool:
    """Legacy ownerless sessions belong to host for member reads."""
    ctx = current()
    if ctx.role == "admin":
        return True
    return (owner_connection_id or HOST_CONNECTION_ID) == ctx.connection_id


def owns_connection(owner_connection_id: str | None) -> bool:
    """Host-plane session ownership: no admin bypass, unlike can_read_connection."""
    return (owner_connection_id or HOST_CONNECTION_ID) == current().connection_id


def _device_clause(ctx: ConnectionContext, owner_device_id: str | None) -> bool:
    # Sessions saved before alpi 0.15.20 carry no device_id and stay visible to every device of the connection.
    if ctx.source != "remote" or ctx.session_scope != "device" or not owner_device_id:
        return True
    return owner_device_id == ctx.device_id


def owns_session(owner_connection_id: str | None, owner_device_id: str | None = None) -> bool:
    ctx = current()
    if (owner_connection_id or HOST_CONNECTION_ID) != ctx.connection_id:
        return False
    return _device_clause(ctx, owner_device_id)


def owns_session_row(row: dict[str, Any]) -> bool:
    return owns_session(row.get("connection_id"), row.get("device_id"))


def can_handle_prompt(owner_connection_id: str | None, owner_device_id: str | None = None) -> bool:
    ctx = current()
    if ctx.source != "remote" or ctx.role == "admin":
        return True
    return owns_session(owner_connection_id, owner_device_id)


def can_read_session(data: dict[str, Any]) -> bool:
    ctx = current()
    if ctx.role == "admin":
        return True
    if (data.get("connection_id") or HOST_CONNECTION_ID) != ctx.connection_id:
        return False
    return _device_clause(ctx, data.get("device_id"))


@contextmanager
def use(context: ConnectionContext) -> Iterator[None]:
    token = _current.set(context)
    try:
        yield
    finally:
        _current.reset(token)
