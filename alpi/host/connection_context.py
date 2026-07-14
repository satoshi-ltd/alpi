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


_current: ContextVar[ConnectionContext] = ContextVar(
    "host_connection_context",
    default=ConnectionContext(),
)


def current() -> ConnectionContext:
    return _current.get()


@contextmanager
def use(context: ConnectionContext) -> Iterator[None]:
    token = _current.set(context)
    try:
        yield
    finally:
        _current.reset(token)
