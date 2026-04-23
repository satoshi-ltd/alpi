"""ALP method handlers that need the rest of alpi — kept out of
``alpi/alp/server.py`` so the transport core stays dependency-free.

Currently: ``link.ask`` + ``link.cancel``. Wiring happens from
``alpi alp start`` (dev + service entrypoint).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
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


def register_link_ask(server: alp_server.Server, home: Path) -> None:
    """Register ``link.ask`` + ``link.cancel``. Both verbs share the
    same active-turn state so cancel can target the live engine."""
    lock = asyncio.Lock()
    active = _ActiveTurn()

    async def link_ask(
        params: dict[str, Any],
        peer: peers_mod.Peer,
        srv: alp_server.Server,
    ) -> dict[str, Any]:
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

        async with lock:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                None, _run_turn, home, prompt, peer.id, active,
            )

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
        if eng is not None and (not target_sid or target_sid == active.session_id):
            eng.request_interrupt()
            return {"cancelled": True, "session_id": active.session_id}
        return {"cancelled": False}

    server.register("link.ask", link_ask)
    server.register("link.cancel", link_cancel)


def _run_turn(
    home: Path, prompt: str, peer_id: str, active: _ActiveTurn,
) -> dict[str, Any]:
    """Synchronous turn — runs in a thread so the ALP server event
    loop stays responsive while the engine blocks on LLM calls."""
    cfg = cfg_mod.load(home)
    engine = Engine(home=home, cfg=cfg)

    # Expose the live engine so ``link.cancel`` can reach in and flip
    # the interrupt flag. Cleared on exit regardless of success/failure.
    active.engine = engine
    active.session_id = engine.session.id

    parts: list[str] = []
    tokens_in = 0
    tokens_out = 0
    cost = 0.0
    interrupted = False

    def sink(ev: AgentEvent) -> None:
        nonlocal tokens_in, tokens_out, cost, interrupted
        if ev.kind == "assistant_done" and ev.text.strip():
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
        engine.run_turn(prompt, emit=sink)
        try:
            engine.save_session()
        except Exception:  # noqa: BLE001
            pass
    finally:
        active.engine = None
        active.session_id = ""

    text = "\n\n".join(parts).strip()
    if interrupted and not text:
        text = "[cancelled]"

    return {
        "text": text,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cost": cost,
        "session_id": engine.session.id,
        "interrupted": interrupted,
    }
