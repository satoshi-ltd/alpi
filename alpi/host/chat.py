from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from typing import Any

from alpi.host import server as host_server


_active_lock = threading.Lock()
_active: dict[str, Any] = {}  # request_id -> Engine


def register(server: host_server.Server) -> None:
    server.register_stream("host.chat.send", _data_chat_send)
    server.register("host.chat.cancel", _data_chat_cancel)


def _resolve_home(profile: str) -> Path:
    from alpi.host.handlers import _resolve_home as _r

    return _r(profile)


async def _data_chat_send(
    params: dict[str, Any],
    server: host_server.Server,
    send_frame,
) -> None:
    profile = str(params.get("profile") or "")
    text = str(params.get("text") or "").strip()
    request_id = str(params.get("request_id") or "")
    session_id = params.get("session_id")
    rewrite_from_turn = params.get("rewrite_from_turn")
    model_override = params.get("model")
    if not text or not request_id:
        await send_frame({
            "event": "error",
            "text": "text and request_id required",
        })
        return

    home = _resolve_home(profile)

    # @-mention shortcut mirrors the TUI.
    from alpi.alp import mention as alp_mention
    parsed = alp_mention.parse(text, home=home)
    if parsed is not None:
        await _send_mention(home, parsed, request_id, session_id, send_frame)
        return

    from alpi import config as cfg_mod
    from alpi.cli import _continue_specific_session
    from alpi.engine import AgentEvent, Engine
    from alpi.tui.formatting import arg_hint

    cfg = cfg_mod.load(home)
    if isinstance(model_override, str) and model_override:
        cfg.model = model_override
    engine = Engine(home=home, cfg=cfg)
    if isinstance(session_id, str) and session_id:
        from alpi.host.handlers import _check_id
        _check_id(session_id, "session_id")
        _continue_specific_session(engine, home, session_id)
        if rewrite_from_turn is not None:
            _truncate_hydrated_session(engine, rewrite_from_turn)

    with _active_lock:
        _active[request_id] = engine

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()
    SENTINEL = object()

    def sink(ev: AgentEvent) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, ev)

    parts: list[str] = []

    def run_engine() -> None:
        try:
            engine.run_turn(text, emit=sink)
            try:
                engine.save_session()
            except Exception:  # noqa: BLE001
                pass
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, SENTINEL)

    task = loop.run_in_executor(None, run_engine)

    try:
        while True:
            item = await queue.get()
            if item is SENTINEL:
                break
            ev: AgentEvent = item
            if ev.kind == "tool_start":
                await send_frame({
                    "event": "tool_start",
                    "tool_id": ev.tool_id,
                    "name": ev.name,
                    "preview": arg_hint(ev.name, ev.args or {}),
                    "args": ev.args or {},
                })
            elif ev.kind == "tool_state":
                await send_frame({
                    "event": "tool_state",
                    "tool_id": ev.tool_id,
                    "name": ev.name,
                    "text": ev.text,
                    "ok": ev.ok,
                })
            elif ev.kind == "tool_end":
                await send_frame({
                    "event": "tool_end",
                    "tool_id": ev.tool_id,
                    "name": ev.name,
                    "ok": ev.ok,
                    "output": _truncate(ev.output, 4000),
                })
            elif ev.kind == "reasoning_delta":
                await send_frame({"event": "reasoning_delta", "text": ev.text})
            elif ev.kind == "assistant_delta":
                await send_frame({"event": "assistant_delta", "text": ev.text})
            elif ev.kind == "error":
                await send_frame({"event": "error", "text": ev.text})
            elif ev.kind == "interrupted":
                await send_frame({"event": "interrupted"})
            elif ev.kind == "assistant_done" and ev.text.strip():
                parts.append(ev.text)
        final = "\n\n".join(parts).strip()
        await send_frame({
            "event": "reply",
            "text": final,
            "session_id": engine.session.id,
        })
        await send_frame({"event": "done", "session_id": engine.session.id})
    finally:
        await task
        with _active_lock:
            _active.pop(request_id, None)


async def _send_mention(
    home: Path, parsed, request_id: str, session_id, send_frame,
) -> None:
    """Execute an @-mention via ALP and persist the turn."""
    import time as _time
    from alpi import config as cfg_mod
    from alpi import session as sess
    from alpi.alp import mention as alp_mention
    from alpi.cli import _continue_specific_session
    from alpi.engine import Engine

    engine = Engine(home=home, cfg=cfg_mod.load(home))
    if isinstance(session_id, str) and session_id:
        from alpi.host.handlers import _check_id
        _check_id(session_id, "session_id")
        _continue_specific_session(engine, home, session_id)

    tool_id = f"mention-{parsed.peer_id}-{request_id}"
    args = {"peer_id": parsed.peer_id, "prompt": parsed.prompt}
    started = _time.time()
    await send_frame({
        "event": "tool_start", "tool_id": tool_id, "name": "peer",
        "preview": f"peer_id={parsed.peer_id}", "args": args,
    })

    parts: list[str] = []
    final_payload: dict = {}
    ok = True
    error_text = ""
    async for frame in alp_mention.execute_stream(home, parsed.peer_id, parsed.prompt):
        kind = frame.get("kind")
        if kind == "chunk":
            delta = str(frame.get("text") or "")
            if delta:
                parts.append(delta)
                await send_frame({"event": "assistant_delta", "text": delta})
        elif kind == "final":
            final_payload = frame
        elif kind == "error":
            ok = False
            error_text = str(frame.get("text") or "unknown")
            break

    if ok:
        reply = str(final_payload.get("text") or "").strip() or "".join(parts).strip()
    else:
        reply = f"error: {error_text}"
    result_tokens_in = int(final_payload.get("tokens_in") or 0)
    result_tokens_out = int(final_payload.get("tokens_out") or 0)
    result_cost = float(final_payload.get("cost") or 0.0)

    await send_frame({
        "event": "tool_end", "tool_id": tool_id, "name": "peer",
        "ok": ok, "output": _truncate(reply, 4000),
    })

    engine.session.log_turn(
        user=f"@{parsed.peer_id} {parsed.prompt}",
        assistant=reply,
        tools=[sess.ToolLog(
            at=started, name="peer", args=args,
            result=reply[:sess.TOOL_RESULT_CAP], ok=ok,
            duration_s=_time.time() - started,
        )],
        started_at=started,
    )
    try:
        engine.session.save()
    except Exception:  # noqa: BLE001
        pass

    sid = engine.session.id
    await send_frame({"event": "reply", "text": reply, "session_id": sid})
    await send_frame({"event": "done", "session_id": sid})


async def _data_chat_cancel(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    request_id = str(params.get("request_id") or "").strip()
    if not request_id:
        return {"cancelled": False}
    with _active_lock:
        engine = _active.get(request_id)
    if engine is None:
        return {"cancelled": False}
    engine.request_interrupt()
    return {"cancelled": True}


def _truncate(text: str, cap: int) -> str:
    if not text:
        return ""
    if len(text) <= cap:
        return text
    return text[: cap - 1] + "…"


def _truncate_hydrated_session(engine, keep_turns: Any) -> None:  # noqa: ANN401
    try:
        keep = int(keep_turns)
    except (TypeError, ValueError):
        return
    keep = max(0, keep)
    turns = list(getattr(engine.session, "turns", []) or [])
    kept = turns[:keep]
    engine.session.turns = kept

    messages: list[dict[str, Any]] = [{
        "role": "system",
        "content": (
            "NOTE: the conversation below is a previous session that was "
            "resumed. You already have this context — do not call "
            "`session_search` to recover it. Refer to the messages directly."
        ),
    }]
    for turn in kept:
        if getattr(turn, "user", ""):
            messages.append({"role": "user", "content": turn.user})
        if getattr(turn, "assistant", ""):
            messages.append({"role": "assistant", "content": turn.assistant})
    engine.session.messages = messages
    engine.session.input_tokens = 0
    engine.session.output_tokens = 0
    engine.session.cost_usd = 0.0
    engine.session.last_ctx_tokens = 0


__all__ = ["register"]
