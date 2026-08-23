from __future__ import annotations

import contextvars
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

from alpi.core.run_context import RunContext
from alpi.tools.base import ToolResult


@dataclass(frozen=True)
class ToolCall:
    call_id: str
    name: str
    arguments: dict


@dataclass(frozen=True)
class ToolOutcome:
    call: ToolCall
    result: ToolResult
    started_at: float
    duration_s: float
    states: tuple[tuple[str, bool], ...] = ()


class ToolExecutor:
    def __init__(
        self,
        context: RunContext,
        deny: frozenset[str] | set[str] | None = None,
        max_workers: int = 4,
    ):
        self.context = context
        self.deny = frozenset(deny or ())
        self.max_workers = max(1, int(max_workers))

    def execute(
        self,
        name: str,
        arguments: dict,
        deny: frozenset[str] | set[str] | None = None,
    ) -> ToolResult:
        from alpi import tools

        self._record("tool.dispatched", {"name": name, "arguments": arguments})
        effective_deny = self.deny if deny is None else frozenset(deny) | self.deny
        result = tools._execute_registered(name, arguments, deny=effective_deny)
        self._record("tool.finished", {
            "name": name, "ok": result.ok, "output": result.output,
            "error": result.error,
        })
        return result

    def _record(self, kind: str, data: dict) -> None:
        try:
            from alpi import runs
            if kind == "tool.dispatched" and isinstance(data.get("arguments"), dict):
                data = {
                    **data,
                    "arguments": runs.persisted_tool_arguments(
                        str(data.get("name") or ""), data["arguments"],
                    ),
                }
            runs.append(self.context.home, self.context.run_id, kind, data)
        except OSError:
            pass

    def is_parallel_safe(self, name: str, arguments: dict) -> bool:
        from alpi import tools

        cls = tools.get(name)
        if cls is None:
            return False
        try:
            return cls.is_parallel_safe(arguments) is True
        except Exception:  # noqa: BLE001
            return False

    def execute_parallel(
        self,
        calls: list[ToolCall],
        *,
        deny: frozenset[str] | set[str] | None = None,
        max_workers: int | None = None,
    ) -> list[ToolOutcome]:
        if len(calls) < 2 or not all(
            self.is_parallel_safe(call.name, call.arguments) for call in calls
        ):
            return [self._execute_captured(call, deny=deny) for call in calls]
        workers = max(1, min(
            self.max_workers if max_workers is None else int(max_workers), len(calls),
        ))
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="alpi-tool") as pool:
            futures = []
            for call in calls:
                copied = contextvars.copy_context()
                futures.append(pool.submit(copied.run, self._execute_captured, call, deny))
            return [future.result() for future in futures]

    def _execute_captured(
        self,
        call: ToolCall,
        deny: frozenset[str] | set[str] | None = None,
    ) -> ToolOutcome:
        from alpi.tools import _state

        states: list[tuple[str, bool]] = []
        started_at = time.time()
        _state.set_emit(lambda label, error=False: states.append((label, bool(error))))
        try:
            result = self.execute(call.name, call.arguments, deny=deny)
        finally:
            _state.set_emit(None)
        return ToolOutcome(
            call=call,
            result=result,
            started_at=started_at,
            duration_s=time.time() - started_at,
            states=tuple(states),
        )


_current: contextvars.ContextVar[ToolExecutor | None] = contextvars.ContextVar(
    "alpi_tool_executor", default=None,
)


def current() -> ToolExecutor | None:
    return _current.get()


@contextmanager
def use(executor: ToolExecutor) -> Iterator[ToolExecutor]:
    token = _current.set(executor)
    try:
        yield executor
    finally:
        _current.reset(token)


__all__ = ["ToolCall", "ToolExecutor", "ToolOutcome", "current", "use"]
