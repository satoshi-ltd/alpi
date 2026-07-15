from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Iterator


HOST_CONNECTION_ID = "host"


@dataclass(frozen=True)
class ConnectionContext:
    connection_id: str = HOST_CONNECTION_ID
    device_id: str | None = None
    source: str = "host"
    # Local socket is sovereign; remote contexts carry the authenticated role for role-aware handlers.
    role: str = "admin"


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


@contextmanager
def use(context: ConnectionContext) -> Iterator[None]:
    token = _current.set(context)
    try:
        yield
    finally:
        _current.reset(token)
