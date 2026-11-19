from __future__ import annotations

import asyncio
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from functools import partial
from typing import Any, Callable, TypeVar

T = TypeVar("T")

TURN_WORKERS = max(16, min(32, (os.cpu_count() or 1) + 4))
PROBE_WORKERS = 2
AUTH_WORKERS = 4

_pools: dict[str, ThreadPoolExecutor] = {}
_guard = threading.Lock()
_SIZES = {"turn": TURN_WORKERS, "probe": PROBE_WORKERS, "auth": AUTH_WORKERS, "sidecar": 4}


def pool(name: str) -> ThreadPoolExecutor:
    with _guard:
        executor = _pools.get(name)
        if executor is None:
            executor = ThreadPoolExecutor(max_workers=_SIZES[name], thread_name_prefix=f"alpi-{name}")
            _pools[name] = executor
        return executor


# submit() does not carry context variables, like run_in_executor; run() does, like asyncio.to_thread.
def submit(name: str, fn: Callable[..., T], *args: Any) -> asyncio.Future[T]:
    return asyncio.get_running_loop().run_in_executor(pool(name), fn, *args)


async def run(name: str, fn: Callable[..., T], *args: Any) -> T:
    return await submit(name, partial(copy_context().run, fn, *args))


# Waits like asyncio.run waits for the default executor, so the daemon keeps its pidfile and lock until its turns end.
def shutdown() -> None:
    with _guard:
        executors = list(_pools.values())
        _pools.clear()
    for executor in executors:
        executor.shutdown(wait=True)


def _reset_after_fork() -> None:
    global _guard
    _guard = threading.Lock()
    _pools.clear()


os.register_at_fork(after_in_child=_reset_after_fork)
