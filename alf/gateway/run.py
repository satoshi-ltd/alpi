"""Gateway entry point.

Starts each enabled platform as an asyncio task. For every incoming message,
the gateway spawns a subprocess running ``alf chat --once --input "<text>"``
and sends stdout back to the platform. This keeps the gateway small and
isolates agent crashes from the listener.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

from alf import config as config_mod
from alf.gateway.base import IncomingMessage, OutgoingMessage, Platform
from alf.gateway.platforms.telegram import Telegram
from alf.gateway.platforms.webhook import Webhook

log = logging.getLogger("alf.gateway")

# Telegram's "typing…" indicator drops after ~5s, so we refresh slightly
# sooner to keep it steady while a turn is in flight.
_TYPING_REFRESH_SECONDS = 4.0


async def _handle_platform(platform: Platform, home: Path) -> None:
    async for msg in platform.listen():
        if not _is_allowed(msg):
            log.warning(
                "Dropping message from disallowed chat: %s:%s",
                msg.platform, msg.external_chat_id,
            )
            continue
        log.info("[%s] %s: %s", msg.platform, msg.external_user_id, msg.text[:100])
        asyncio.create_task(_process(platform, msg, home))


async def _process(platform: Platform, msg: IncomingMessage, home: Path) -> None:
    gw_cfg = _load_gateway_cfg(home)
    typing_task: asyncio.Task | None = None
    if gw_cfg.get("typing_indicator", True):
        typing_task = asyncio.create_task(_typing_loop(platform, msg.external_chat_id))

    show_trace = bool(gw_cfg.get("show_tool_trace", True))

    try:
        reply = await _run_agent(msg, platform, home, show_trace=show_trace)
    finally:
        if typing_task is not None:
            typing_task.cancel()
            try:
                await typing_task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass

    if not reply.strip():
        reply = "(no response)"
    await platform.send(OutgoingMessage(
        external_chat_id=msg.external_chat_id,
        text=reply,
    ))


async def _typing_loop(platform: Platform, chat_id: str) -> None:
    """Keep the typing indicator alive until cancelled."""
    while True:
        try:
            await platform.send_typing(chat_id)
        except Exception as e:  # noqa: BLE001
            log.debug("typing ping failed: %s", e)
        await asyncio.sleep(_TYPING_REFRESH_SECONDS)


async def _run_agent(msg: IncomingMessage, platform: Platform, home: Path,
                     show_trace: bool) -> str:
    """Invoke ``alf chat --once --emit-events`` and stream events.

    Each stdout line is a JSON object describing one event from the agent
    loop (``tool_start`` / ``tool_end`` / ``error`` / ``reply``). We relay
    tool activity to the chat as it happens (when ``show_trace``) and
    return the final reply text for the caller to deliver.
    """
    env = dict(os.environ)
    env["ALF_HOME"] = str(home)
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "alf", "chat", "--once", msg.text, "--emit-events",
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    assert proc.stdout is not None

    reply = ""
    while True:
        line = await proc.stdout.readline()
        if not line:
            break
        try:
            event = json.loads(line.decode().strip())
        except json.JSONDecodeError:
            continue
        kind = event.get("kind")
        if kind == "reply":
            reply = event.get("text", "")
        elif kind == "tool_start" and show_trace:
            trace = _format_tool_trace(event)
            await platform.send(OutgoingMessage(
                external_chat_id=msg.external_chat_id, text=trace,
            ))
        elif kind == "error" and show_trace:
            await platform.send(OutgoingMessage(
                external_chat_id=msg.external_chat_id,
                text=f"⚠︎ {event.get('text', 'error')}",
            ))

    rc = await proc.wait()
    if rc != 0:
        stderr = (await proc.stderr.read()).decode()[:500] if proc.stderr else ""
        log.error("agent subprocess failed (rc=%s): %s", rc, stderr)
        return reply or f"(agent error, rc={rc})"
    return reply


def _format_tool_trace(event: dict[str, Any]) -> str:
    name = event.get("name", "?")
    preview = (event.get("preview") or "").strip()
    if preview:
        return f"◆ {name} · {preview}"
    return f"◆ {name}"


def _load_gateway_cfg(home: Path) -> dict[str, Any]:
    try:
        cfg = config_mod.load(home)
        return dict(cfg.gateway or {})
    except Exception as e:  # noqa: BLE001
        log.warning("Could not load gateway config: %s", e)
        return {"show_tool_trace": True, "typing_indicator": True}


def _is_allowed(msg: IncomingMessage) -> bool:
    """Check the incoming chat against the per-platform allowlist in env.

    Each platform has its own env var (e.g. ``TELEGRAM_ALLOWED_CHAT_IDS``,
    ``WEBHOOK_ALLOWED_CHAT_IDS``) — a comma-separated list of chat IDs.
    Empty or unset → no chats are allowed (fail closed).
    """
    raw = os.environ.get(f"{msg.platform.upper()}_ALLOWED_CHAT_IDS", "")
    allowed = {c.strip() for c in raw.split(",") if c.strip()}
    return msg.external_chat_id in allowed


def run(home: Path) -> None:
    _configure_logging(home)
    _load_env(home)
    _write_pid(home)
    try:
        platforms: list[Platform] = [Telegram(home), Webhook(home)]

        async def _main() -> None:
            await asyncio.gather(*(_handle_platform(p, home) for p in platforms))

        try:
            asyncio.run(_main())
        except KeyboardInterrupt:
            log.info("Gateway stopped.")
    finally:
        _clear_pid(home)


# ----------------------------------------------------------------------
# PID file helpers (used by start/stop/status commands)
# ----------------------------------------------------------------------

def pid_path(home: Path) -> Path:
    return home / "gateway" / "gateway.pid"


def _write_pid(home: Path) -> None:
    p = pid_path(home)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(str(os.getpid()))


def _clear_pid(home: Path) -> None:
    p = pid_path(home)
    if p.exists():
        p.unlink()


def _load_env(home: Path) -> None:
    env_path = home / ".env"
    if env_path.exists():
        from dotenv import load_dotenv
        load_dotenv(env_path, override=False)
        log.info("Loaded env from %s", env_path)


def _configure_logging(home: Path) -> None:
    from logging.handlers import RotatingFileHandler

    log_dir = home / "gateway" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "gateway.log"
    # Single file, auto-truncated at 1 MB.
    file_handler = RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=0)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[file_handler, logging.StreamHandler()],
    )
