"""ALP method handlers that need the rest of alpi — kept out of
``alpi/alp/server.py`` so the transport core stays dependency-free.

Turn handlers: ``link.ask`` + ``link.cancel``. Wiring happens from
``alpi alp start`` (dev + service entrypoint).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from alpi import config as cfg_mod
from alpi.alp import peers as peers_mod
from alpi.alp import server as alp_server
from alpi.engine import AgentEvent, Engine


@dataclass
class _ActiveTurn:
    """State shared between ``link.ask`` (sets it) and ``link.cancel``
    (reads + interrupts it). Reject-fast reentrancy keeps at most one
    active at a time, so a single reference is enough — no dict keyed
    by session_id."""
    engine: Engine | None = None
    session_id: str = ""
    peer_pubkey: str = ""


_LINK_PROGRESS_INTERVAL_SECONDS = 15.0


def register_link_ask(server: alp_server.Server, home: Path) -> None:
    """Register ``link.ask`` + ``link.cancel``. Both verbs share the
    same active-turn state so cancel can target the live engine."""
    lock = asyncio.Lock()
    active = _ActiveTurn()

    def link_ask(
        params: dict[str, Any],
        peer: peers_mod.Peer,
        srv: alp_server.Server,
    ):
        """Returns either a coroutine resolving to a dict (no-stream)
        or an async generator yielding chunks (stream). The server
        dispatcher detects which and frames accordingly."""
        prompt = str((params or {}).get("prompt") or "").strip()
        if not prompt:
            raise alp_server.HandlerError(
                -32602, "invalid-params", data={"detail": "prompt required"},
            )

        if lock.locked():
            raise alp_server.HandlerError(
                -32007, "target-busy",
                data={"detail": "another turn is already in flight"},
            )

        stream = bool((params or {}).get("stream"))
        if stream:
            return _run_turn_stream(
                home, prompt, peer.id, active, lock, peer.pubkey,
            )

        async def _solo() -> dict[str, Any]:
            async with lock:
                loop = asyncio.get_running_loop()
                return await loop.run_in_executor(
                    None, _run_turn, home, prompt, peer.id, active, peer.pubkey,
                )

        return _solo()

    async def link_cancel(
        params: dict[str, Any],
        peer: peers_mod.Peer,
        srv: alp_server.Server,
    ) -> dict[str, Any]:
        """Idempotent — a cancel for an already-finished turn is a no-op.
        Silent-success simplifies the caller; they don't need to know if
        their cancel "arrived in time"."""
        target_sid = str((params or {}).get("session_id") or "").strip()
        eng = active.engine
        same_caller = active.peer_pubkey == peer.pubkey
        if (
            eng is not None
            and same_caller
            and (not target_sid or target_sid == active.session_id)
        ):
            eng.request_interrupt("alp-cancel")
            return {"cancelled": True, "session_id": active.session_id}
        return {"cancelled": False}

    server.register("link.ask", link_ask)
    server.register("link.cancel", link_cancel)


async def _run_turn_stream(
    home: Path,
    prompt: str,
    peer_id: str,
    active: _ActiveTurn,
    lock: asyncio.Lock,
    peer_pubkey: str = "",
):
    """Streaming variant: runs the engine in a thread, yields one
    chunk per ``assistant_delta`` event, ends with a ``final`` chunk
    carrying the aggregated text + token/cost totals. Mirrors what
    ``_run_turn`` collects, just exposed incrementally."""
    async with lock:
        from alpi import config as cfg_mod
        from alpi import ledger
        from alpi.alp import mention_thread
        from alpi.engine import Engine
        from alpi.host import connection_context as conn_ctx

        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()
        SENTINEL = object()
        cfg = cfg_mod.load(home)
        engine = Engine(home=home, cfg=cfg)
        engine.connection_context = conn_ctx.ConnectionContext(
            connection_id=f"peer:{peer_id}", source="peer",
        )
        thread = mention_thread.load(home, peer_id)
        mention_thread.hydrate(engine.session.messages, thread)
        _prior = getattr(thread, "turns", None)
        if _prior:
            from alpi.session import relay_peer_from_host_context
            engine._last_relay_peer = relay_peer_from_host_context(
                getattr(_prior[-1], "host_context", "") or "",
            )
        active.engine = engine
        active.session_id = engine.session.id
        active.peer_pubkey = peer_pubkey

        state = {
            "parts": [],
            "produced": [],
            "tokens_in": 0,
            "tokens_out": 0,
            "cost": 0.0,
            "interrupted": False,
        }

        def sink(ev: AgentEvent) -> None:
            if ev.kind == "assistant_delta" and ev.text:
                loop.call_soon_threadsafe(queue.put_nowait, ("delta", ev.text))
            elif ev.kind == "assistant_done" and ev.final:
                if ev.attachments:
                    state["produced"].extend(ev.attachments)
                if ev.text.strip():
                    state["parts"].append(ev.text)
            elif ev.kind == "usage":
                state["tokens_in"] += ev.tokens_in
                state["tokens_out"] += ev.tokens_out
                state["cost"] += ev.cost
            elif ev.kind == "error":
                state["parts"].append(f"[error] {ev.text}")
            elif ev.kind == "interrupted":
                state["interrupted"] = True

        def worker() -> None:
            try:
                with ledger.peer_context(peer_id):
                    engine.run_turn(
                        prompt, emit=sink, source="peer",
                        persist_inflight=False,
                    )
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, SENTINEL)

        worker_task = loop.run_in_executor(None, worker)
        try:
            yield {
                "kind": "chunk",
                "event": "started",
                "session_id": engine.session.id,
            }
            while True:
                try:
                    item = await asyncio.wait_for(
                        queue.get(), timeout=_LINK_PROGRESS_INTERVAL_SECONDS,
                    )
                except asyncio.TimeoutError:
                    yield {
                        "kind": "chunk",
                        "event": "progress",
                        "session_id": engine.session.id,
                    }
                    continue
                if item is SENTINEL:
                    break
                tag, payload = item
                if tag == "delta":
                    yield {"kind": "chunk", "text": payload}
            await worker_task
        finally:
            if not worker_task.done():
                engine.request_interrupt("alp-disconnect")
                await worker_task
            active.engine = None
            active.session_id = ""
            active.peer_pubkey = ""

        full = "\n\n".join(state["parts"]).strip()
        if state["interrupted"] and not full:
            full = "[cancelled]"
        if not state["interrupted"]:
            from alpi.attachments import render_output_attachments
            listing = render_output_attachments(state["produced"])
            if listing:
                full = "\n\n".join(x for x in (full, listing) if x)
        if full and not state["interrupted"]:
            mention_thread.append(
                home, peer_id, prompt, full,
                host_context=getattr(engine, "last_host_context", ""),
            )
        yield {
            "kind": "final",
            "text": full,
            "tokens_in": state["tokens_in"],
            "tokens_out": state["tokens_out"],
            "cost": state["cost"],
            "session_id": engine.session.id,
            "interrupted": state["interrupted"],
        }


def _run_turn(
    home: Path,
    prompt: str,
    peer_id: str,
    active: _ActiveTurn,
    peer_pubkey: str = "",
) -> dict[str, Any]:
    """Synchronous turn — runs in a thread so the ALP server event
    loop stays responsive while the engine blocks on LLM calls."""
    from alpi.alp import mention_thread

    cfg = cfg_mod.load(home)
    engine = Engine(home=home, cfg=cfg)
    from alpi.host import connection_context as conn_ctx
    engine.connection_context = conn_ctx.ConnectionContext(
        connection_id=f"peer:{peer_id}", source="peer",
    )

    thread = mention_thread.load(home, peer_id)
    mention_thread.hydrate(engine.session.messages, thread)
    _prior = getattr(thread, "turns", None)
    if _prior:
        from alpi.session import relay_peer_from_host_context
        engine._last_relay_peer = relay_peer_from_host_context(
            getattr(_prior[-1], "host_context", "") or "",
        )

    # Expose the live engine so ``link.cancel`` can reach in and flip
    # the interrupt flag. Cleared on exit regardless of success/failure.
    active.engine = engine
    active.session_id = engine.session.id
    active.peer_pubkey = peer_pubkey

    parts: list[str] = []
    produced: list[dict] = []
    tokens_in = 0
    tokens_out = 0
    cost = 0.0
    interrupted = False

    def sink(ev: AgentEvent) -> None:
        nonlocal tokens_in, tokens_out, cost, interrupted
        if ev.kind == "assistant_done" and ev.final:
            if ev.attachments:
                produced.extend(ev.attachments)
            if ev.text.strip():
                parts.append(ev.text)
        elif ev.kind == "usage":
            tokens_in += ev.tokens_in
            tokens_out += ev.tokens_out
            cost += ev.cost
        elif ev.kind == "error":
            parts.append(f"[error] {ev.text}")
        elif ev.kind == "interrupted":
            interrupted = True

    try:
        from alpi import ledger

        with ledger.peer_context(peer_id):
            engine.run_turn(
                prompt, emit=sink, source="peer",
                persist_inflight=False,
            )
    finally:
        active.engine = None
        active.session_id = ""
        active.peer_pubkey = ""

    text = "\n\n".join(parts).strip()
    if not interrupted:
        from alpi.attachments import render_output_attachments
        listing = render_output_attachments(produced)
        if listing:
            text = "\n\n".join(x for x in (text, listing) if x)
    if interrupted and not text:
        text = "[cancelled]"
    # Mention threads live in ``mentions/<sender>.json``, not ``sessions/``.
    if text and not interrupted:
        mention_thread.append(
            home, peer_id, prompt, text,
            host_context=getattr(engine, "last_host_context", ""),
        )

    return {
        "text": text,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cost": cost,
        "session_id": engine.session.id,
        "interrupted": interrupted,
    }
