"""Host-plane clarification bridge — paired with ``alpi.tools.ask_user``.

Owns the daemon-side handler for ``ask_user``: emits
``clarification.request`` on the host event bus, blocks the tool thread
on a per-request asyncio Future, and resolves on ``host.clarification.
respond``. ``host.clarification.pending`` lets a client that mounts
after the event was emitted recover the still-active queue.

Lifecycle of one clarification:

1. The agent calls ``ask_user(...)`` inside the tool execution thread.
2. The tool routes to the registered handler — in daemon mode that is
   ``host_clarification_handler`` (installed by ``register()`` below).
3. The handler creates a ``request_id`` + asyncio Future on the daemon
   loop, stores it in ``_pending``, emits ``clarification.request``,
   and blocks on ``Future.result(timeout=CLARIFICATION_TIMEOUT_S)``.
4. A subscribed client renders the choice surface, calls
   ``host.clarification.respond`` with ``{request_id, choice}``. The
   RPC handler pops the Future and sets the choice on it.
5. On timeout, the Future raises, the request is pruned, and the
   handler returns an empty string so the tool surfaces the graceful
   "no response" string to the model.

The TUI path is unaffected — ``alpi.cli`` installs its own inline
handler when running an interactive chat turn and undoes it on exit;
the daemon handler stays as the fallback for paired-client surfaces.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import time
import uuid
from typing import Any

from alpi import home as home_mod
from alpi.host import events as host_events
from alpi.host import server as host_server
from alpi.tools import _clarification


log = logging.getLogger("alpi.host.clarification")

CLARIFICATION_TIMEOUT_S = 300.0


_pending_lock = threading.Lock()
_pending: dict[str, asyncio.Future] = {}
_pending_meta: dict[str, dict[str, Any]] = {}

_loop_ref: asyncio.AbstractEventLoop | None = None


def register(server: host_server.Server) -> None:
    """Wire the RPC handlers and install the host-plane clarification handler. Called from ``alpi/service.py`` alongside ``host_events.register``."""
    global _loop_ref
    try:
        _loop_ref = asyncio.get_event_loop()
    except RuntimeError:
        _loop_ref = asyncio.new_event_loop()
    server.register("host.clarification.respond", _respond_handler)
    server.register("host.clarification.pending", _pending_handler)
    _clarification.set_handler(host_clarification_handler)


def host_clarification_handler(
    question: str,
    choices: list[dict[str, Any]],
    allow_other: bool,
    multi: bool = False,
) -> str:
    """Sync handler the ``ask_user`` tool invokes on the tool thread. Bridges to the asyncio loop, awaits a client response via ``host.clarification.respond``, returns the chosen string. Falls back to an empty string on timeout or bus failure so the tool can surface a graceful 'no response' result to the model. When ``multi`` is True the resolved string is the labels the user picked joined by ``", "``."""
    loop = _loop_ref
    if loop is None or loop.is_closed():
        log.warning("clarification requested but daemon loop is not bound")
        return ""

    request_id = uuid.uuid4().hex
    try:
        profile = home_mod.profile_name(home_mod.get_home())
    except Exception:  # noqa: BLE001
        profile = os.environ.get("ALPI_PROFILE") or None

    payload = {
        "request_id": request_id,
        "profile": profile,
        "question": question,
        "choices": choices,
        "allow_other": bool(allow_other),
        "multi": bool(multi),
        "ts": time.time(),
        "timeout_s": CLARIFICATION_TIMEOUT_S,
    }

    fut_holder: dict[str, asyncio.Future] = {}

    def _arm() -> None:
        fut = loop.create_future()
        fut_holder["f"] = fut
        with _pending_lock:
            _pending[request_id] = fut
            _pending_meta[request_id] = dict(payload)

    arm_future = asyncio.run_coroutine_threadsafe(_arm_coro(_arm), loop)
    try:
        arm_future.result(timeout=5.0)
    except Exception as e:  # noqa: BLE001
        log.warning("clarification arm failed: %s", e)
        return ""

    host_events.emit("clarification.request", payload)

    wait_future = asyncio.run_coroutine_threadsafe(
        _await_choice(fut_holder["f"], CLARIFICATION_TIMEOUT_S), loop,
    )
    timed_out = False
    try:
        choice = wait_future.result(timeout=CLARIFICATION_TIMEOUT_S + 5.0)
    except Exception as e:  # noqa: BLE001
        log.warning("clarification wait failed for %s: %s", request_id, e)
        choice = ""
        timed_out = True
    finally:
        with _pending_lock:
            existed = _pending.pop(request_id, None) is not None
            _pending_meta.pop(request_id, None)
        if existed and not choice:
            timed_out = True

    host_events.emit("clarification.resolved", {
        "request_id": request_id,
        "profile": profile,
        "choice": choice,
        "timed_out": timed_out,
        "ts": time.time(),
    })
    return choice


async def _arm_coro(arm_fn) -> None:
    arm_fn()


async def _await_choice(fut: asyncio.Future, timeout_s: float) -> str:
    try:
        return await asyncio.wait_for(fut, timeout=timeout_s)
    except asyncio.TimeoutError:
        return ""


CANCEL_SENTINEL = "User cancelled clarification."
"""Sentinel choice the UIs send when the user closes the modal/sheet. Always accepted regardless of ``allow_other``."""


async def _respond_handler(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    """``host.clarification.respond`` — resolve a pending Future. Idempotent: late / duplicate / unknown ids return ``{ok: False, reason}`` and never raise. Server-side validation:

    - ``multi=True``: ``choice`` MUST be a JSON-array string of labels (e.g. ``'["A","B"]'``). Each element must match one of the offered labels (``allow_other`` is treated as False). Order and dedupe preserved as the user picked.
    - ``multi=False`` + ``allow_other=False`` requires the whole answer to match a single label.
    - The cancel sentinel is always accepted regardless of mode.

    A malformed / stale / hostile client can't fabricate an answer the tool never offered. JSON-array protocol for multi means labels containing commas (e.g. ``"Research, quick"``) are safe.
    """
    request_id = params.get("request_id")
    choice = params.get("choice")
    if not isinstance(request_id, str) or not request_id:
        return {"ok": False, "reason": "request_id required"}
    if not isinstance(choice, str) or not choice.strip():
        return {"ok": False, "reason": "choice must be a non-empty string"}
    choice = choice.strip()
    with _pending_lock:
        meta = _pending_meta.get(request_id)
        if meta is None:
            return {"ok": False, "reason": "unknown or already resolved"}
        allow_other = bool(meta.get("allow_other"))
        multi = bool(meta.get("multi"))
        valid_labels = {
            c.get("label") for c in (meta.get("choices") or [])
            if isinstance(c, dict) and c.get("label")
        }
        resolved = choice
        if choice != CANCEL_SENTINEL:
            if multi:
                try:
                    parsed = json.loads(choice)
                except json.JSONDecodeError:
                    return {"ok": False, "reason": "multi answer must be a JSON array of labels"}
                if not isinstance(parsed, list):
                    return {"ok": False, "reason": "multi answer must be a JSON array of labels"}
                tokens: list[str] = []
                for item in parsed:
                    if not isinstance(item, str):
                        return {"ok": False, "reason": "multi answer must contain only string labels"}
                    label = item.strip()
                    if label and label not in tokens:
                        tokens.append(label)
                if not tokens:
                    return {"ok": False, "reason": "multi answer requires at least one label"}
                unknown = [t for t in tokens if t not in valid_labels]
                if unknown:
                    return {
                        "ok": False,
                        "reason": f"unknown label(s): {', '.join(unknown)}",
                    }
                # Tool result to the model stays the human-readable join. Labels
                # containing commas survive validation here even if they look
                # ambiguous in the rendered string — the model treats the
                # whole result as the user's choice, not as a parseable list.
                resolved = ", ".join(tokens)
            elif not allow_other and choice not in valid_labels:
                return {"ok": False, "reason": "choice does not match any offered label"}
        fut = _pending.pop(request_id, None)
        _pending_meta.pop(request_id, None)
    if fut is None:
        return {"ok": False, "reason": "unknown or already resolved"}
    if fut.done():
        return {"ok": False, "reason": "already resolved"}
    fut.set_result(resolved)
    return {"ok": True}


async def _pending_handler(
    _params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    """``host.clarification.pending`` — cold-start recovery. Clients call on mount/reconnect to fetch requests whose ``clarification.request`` event fired before the live subscription anchored."""
    with _pending_lock:
        items = list(_pending_meta.values())
    return {"requests": items}


def _reset_for_tests() -> None:
    """Drop all pending Futures + unbind the loop. Test fixture helper."""
    global _loop_ref
    with _pending_lock:
        for fut in _pending.values():
            if not fut.done():
                fut.cancel()
        _pending.clear()
        _pending_meta.clear()
    _loop_ref = None
    _clarification.set_handler(None)


__all__ = [
    "CANCEL_SENTINEL",
    "CLARIFICATION_TIMEOUT_S",
    "host_clarification_handler",
    "register",
]
