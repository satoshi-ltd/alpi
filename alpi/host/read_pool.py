from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from functools import partial
from typing import Any, Callable


_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="alpi-host-read")


async def run_read(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    call = partial(copy_context().run, fn, *args, **kwargs)
    return await asyncio.get_running_loop().run_in_executor(_pool, call)
