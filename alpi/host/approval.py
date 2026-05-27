"""Host-plane approval bridge: turn the synchronous ``_prompt_callback``
contract from ``alpi.tools._approval`` into a request/response over the
``host.*`` event stream so desktop/mobile clients can answer approval
prompts without the TUI being present.

Lifecycle of one approval:

1. Tool execution thread calls ``check(cmd)`` in ``_approval.check``.
2. ``check`` sees a CAUTION pattern and invokes the registered
   ``_prompt_callback`` — in daemon mode that is ``host_approval_callback``.
3. ``host_approval_callback`` creates a ``request_id`` + asyncio Future,
   stores it in ``_pending``, emits ``approval.request`` on the event bus,
   and blocks the tool thread on ``Future.result(timeout=PROMPT_TIMEOUT_S)``.
4. A subscribed client renders an approval sheet, then calls
   ``host.approval.respond`` with ``{request_id, choice}``. The RPC
   handler pops the Future from ``_pending`` and sets the choice on it,
   waking the tool thread.
5. If no client responds within ``PROMPT_TIMEOUT_S`` the Future times
   out, the request is pruned from ``_pending``, and the callback
   returns ``"deny"`` so ``_approval.check`` produces an auto-deny
   ``Decision``. Late responses are no-ops (idempotent).

The TUI path is unaffected: ``alpi/tui/app.py`` still installs its own
blocking prompt callback on mount, which overrides this one. On unmount
the daemon callback is restored by the caller (typically the test or the
service bootstrap, not this module).
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
import time
import uuid
from typing import Any

from alpi import home as home_mod
from alpi.host import events as host_events
from alpi.host import server as host_server
from alpi.tools import _approval


log = logging.getLogger("alpi.host.approval")

# 60s matches the TUI ApprovalPanel timeout — both surfaces look identical to the engine.
PROMPT_TIMEOUT_S = 60.0
_VALID_CHOICES = frozenset({"once", "session", "always", "deny"})


_pending_lock = threading.Lock()
# request_id -> Future (on the daemon's running loop)
_pending: dict[str, asyncio.Future] = {}
# request_id -> sanitized payload (mirror of what was emitted), so a cold-start client can fetch the queue.
_pending_meta: dict[str, dict[str, Any]] = {}

# The daemon loop, captured once on register(). The tool thread uses it to
# schedule Future creation/wait via run_coroutine_threadsafe.
_loop_ref: asyncio.AbstractEventLoop | None = None


def register(server: host_server.Server) -> None:
    """Wire the RPC handler and install the host-plane prompt callback.

    Called from ``alpi/service.py`` next to ``host_events.register(server)``.
    Stores the running loop so the synchronous prompt callback can schedule
    coroutines on it from the tool thread.
    """
    global _loop_ref
    try:
        _loop_ref = asyncio.get_event_loop()
    except RuntimeError:
        _loop_ref = asyncio.new_event_loop()
    server.register("host.approval.respond", _respond_handler)
    server.register("host.approval.pending", _pending_handler)
    _approval.set_prompt_callback(host_approval_callback)


def _client_id_hint() -> str | None:
    """Best-effort responder tag for the audit log; ``None`` if unknown."""
    return os.environ.get("ALPI_HOST_CLIENT_ID") or None


def host_approval_callback(
    cmd: str,
    pattern: str,
    severity: _approval.Severity,
    cwd: str | None = None,
) -> str:
    """Synchronous prompt callback signature expected by ``_approval.check``.

    Runs on the tool execution thread; bridges to the asyncio loop, awaits
    a client response, and returns one of ``"once" | "session" | "always" |
    "deny"``. Any failure (no loop, timeout, bus down) falls back to
    ``"deny"`` so caution commands never auto-allow on missing clients.
    """
    loop = _loop_ref
    if loop is None or loop.is_closed():
        log.warning("host approval requested but daemon loop is not bound; auto-deny")
        return "deny"

    request_id = uuid.uuid4().hex
    # ALPI_PROFILE env is the legacy path and is unreliable in the multi-profile daemon (Engine.run_turn binds get_home() via ContextVar). Derive from the active home so each per-profile turn carries the right tag into the modal.
    try:
        profile = home_mod.profile_name(home_mod.get_home())
    except Exception:  # noqa: BLE001
        profile = os.environ.get("ALPI_PROFILE") or None

    # Collapse $HOME→~ on the daemon side so every client renders the same
    # display string without needing access to the daemon's filesystem.
    cwd_display: str | None = None
    if cwd:
        try:
            home_path = os.path.expanduser("~")
            cwd_display = cwd.replace(home_path, "~", 1) if home_path and cwd.startswith(home_path) else cwd
        except Exception:  # noqa: BLE001
            cwd_display = cwd

    payload = {
        "request_id": request_id,
        "command": cmd,
        "severity": severity.value if hasattr(severity, "value") else str(severity),
        "pattern": pattern,
        "profile": profile,
        "cwd": cwd_display,
        "ts": time.time(),
        "timeout_s": PROMPT_TIMEOUT_S,
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
        log.warning("host approval arm failed: %s; auto-deny", e)
        return "deny"

    host_events.emit("approval.request", payload)

    wait_future = asyncio.run_coroutine_threadsafe(
        _await_choice(fut_holder["f"], PROMPT_TIMEOUT_S), loop,
    )
    try:
        choice = wait_future.result(timeout=PROMPT_TIMEOUT_S + 5.0)
    except Exception as e:  # noqa: BLE001
        log.warning("host approval wait failed for %s: %s; auto-deny", request_id, e)
        choice = "deny"
    finally:
        with _pending_lock:
            _pending.pop(request_id, None)
            _pending_meta.pop(request_id, None)

    host_events.emit("approval.resolved", {
        "request_id": request_id,
        "choice": choice,
        "pattern": pattern,
        "severity": payload["severity"],
        "responder": _client_id_hint(),
        "ts": time.time(),
    })
    return choice


async def _arm_coro(arm_fn) -> None:
    arm_fn()


async def _await_choice(fut: asyncio.Future, timeout_s: float) -> str:
    try:
        return await asyncio.wait_for(fut, timeout=timeout_s)
    except asyncio.TimeoutError:
        return "deny"


async def _respond_handler(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    """``host.approval.respond`` — resolve a pending approval Future.

    Idempotent: a late response, a duplicate response, or a response for
    an unknown ``request_id`` returns ``{"ok": False, "reason": ...}`` and
    does not raise — the client may have raced the timeout.
    """
    request_id = params.get("request_id")
    choice = (params.get("choice") or "").lower()
    if not isinstance(request_id, str) or not request_id:
        return {"ok": False, "reason": "request_id required"}
    if choice not in _VALID_CHOICES:
        return {"ok": False, "reason": f"choice must be one of {sorted(_VALID_CHOICES)}"}
    with _pending_lock:
        fut = _pending.pop(request_id, None)
        _pending_meta.pop(request_id, None)
    if fut is None:
        return {"ok": False, "reason": "unknown or already resolved"}
    if fut.done():
        return {"ok": False, "reason": "already resolved"}
    fut.set_result(choice)
    return {"ok": True}


async def _pending_handler(
    _params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    """``host.approval.pending`` — return currently-pending approvals.

    Clients call this on mount/reconnect: a request emitted before the
    client subscribed will not arrive via the live stream (subscribe
    anchors at ``next_seq``) and ``approval.*`` events are deliberately
    excluded from history backfill in clients to avoid surfacing already-
    resolved prompts. Without this, a 60-second approval window with no
    active client just auto-denies invisibly.
    """
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


__all__ = ["register", "host_approval_callback", "PROMPT_TIMEOUT_S"]
