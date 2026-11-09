from __future__ import annotations

import contextvars
import queue
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

from alpi.core.run_context import RunContext
from alpi.tools.base import ToolResult

_MIN_CALL_TIMEOUT_S = 1.0
# Under this much soft budget left the engine is about to wrap up; a call started now keeps the plain cap instead of a near-zero one.
_TURN_DEADLINE_FLOOR_S = 30.0


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
        deny_reasons: dict[str, str] | None = None,
        call_timeout_s: float = 0.0,
    ):
        self.context = context
        self.deny = frozenset(deny or ())
        self.deny_reasons = dict(deny_reasons or {})
        self.max_workers = max(1, int(max_workers))
        self.call_timeout_s = max(0.0, float(call_timeout_s or 0.0))
        # Monotonic turn deadline the engine sets once it knows the soft budget; the per-call cap never outlives it.
        self.turn_deadline: float | None = None

    def call_deadline(self, name: str) -> float | None:
        from alpi import tools

        cls = tools.get(name)
        if cls is not None and getattr(cls, "call_timeout_exempt", False):
            return None
        limits = []
        if self.call_timeout_s > 0:
            limits.append(self.call_timeout_s)
        if self.turn_deadline is not None:
            remaining = self.turn_deadline - time.monotonic()
            if remaining > _TURN_DEADLINE_FLOOR_S:
                limits.append(remaining)
        if not limits:
            return None
        return max(_MIN_CALL_TIMEOUT_S, min(limits))

    def execute(
        self,
        name: str,
        arguments: dict,
        deny: frozenset[str] | set[str] | None = None,
    ) -> ToolResult:
        from alpi import tools

        self._record("tool.dispatched", {"name": name, "arguments": arguments})
        effective_deny = self.deny if deny is None else frozenset(deny) | self.deny
        timeout = self.call_deadline(name)
        if timeout is None:
            result = tools._execute_registered(
                name, arguments, deny=effective_deny,
                deny_reasons=self.deny_reasons,
            )
        else:
            result = self._execute_bounded(name, arguments, effective_deny, timeout)
        self._record("tool.finished", {
            "name": name, "ok": result.ok, "output": result.output,
            "error": result.error,
        })
        return result

    def _execute_bounded(
        self, name: str, arguments: dict, deny: frozenset[str], timeout: float,
    ) -> ToolResult:
        from alpi import tools

        out: queue.Queue = queue.Queue(maxsize=1)
        ctx = contextvars.copy_context()

        def _run() -> None:
            try:
                out.put(tools._execute_registered(
                    name, arguments, deny=deny, deny_reasons=self.deny_reasons,
                ))
            except BaseException as exc:  # noqa: BLE001
                out.put(exc)

        # A daemon thread: a tool that never returns must not keep the turn, or the process, alive.
        threading.Thread(target=ctx.run, args=(_run,), name=f"alpi-tool-{name}", daemon=True).start()
        try:
            result = out.get(timeout=timeout)
        except queue.Empty:
            return ToolResult(
                ok=False, output="", transient=True,
                error=(
                    f"{name} did not finish within {int(timeout)}s; the engine moved on and "
                    "its side effects, if any, may still land. Do not repeat the call blindly."
                ),
            )
        if isinstance(result, BaseException):
            raise result
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
        except (OSError, ValueError):
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
