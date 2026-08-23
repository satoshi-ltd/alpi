from __future__ import annotations

import contextvars
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


@dataclass(frozen=True)
class RunContext:
    run_id: str
    home: Path
    workspace: Path
    profile: str
    source: str
    session_id: str
    connection_id: str
    device_id: str | None = None
    role: str = "admin"
    job_id: str | None = None
    workgroup_id: str | None = None

    @classmethod
    def create(
        cls,
        *,
        home: Path,
        workspace: Path,
        profile: str,
        source: str,
        session_id: str,
        connection_id: str,
        device_id: str | None = None,
        role: str = "admin",
        job_id: str | None = None,
        workgroup_id: str | None = None,
        run_id: str | None = None,
    ) -> "RunContext":
        return cls(
            run_id=run_id or uuid.uuid4().hex,
            home=home,
            workspace=workspace,
            profile=profile,
            source=source,
            session_id=session_id,
            connection_id=connection_id,
            device_id=device_id,
            role=role,
            job_id=job_id,
            workgroup_id=workgroup_id,
        )


_current: contextvars.ContextVar[RunContext | None] = contextvars.ContextVar(
    "alpi_run_context", default=None,
)


def current() -> RunContext | None:
    return _current.get()


@contextmanager
def use(context: RunContext) -> Iterator[RunContext]:
    token = _current.set(context)
    try:
        yield context
    finally:
        _current.reset(token)


__all__ = ["RunContext", "current", "use"]
