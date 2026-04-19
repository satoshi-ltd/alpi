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
from alf.gateway import delivery
from alf.gateway.base import IncomingMessage, OutgoingMessage, Platform
from alf.gateway.platforms.email import Email
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
        # Flatten newlines so multi-line inbound (email bodies with
        # a Subject line + blank line + body) stays a single log entry.
        preview = " ".join(msg.text.split())[:120]
        log.info("[%s] %s: %s", msg.platform, msg.external_user_id, preview)
        asyncio.create_task(_process(platform, msg, home))


async def _process(platform: Platform, msg: IncomingMessage, home: Path) -> None:
    # Per-platform UX config. Telegram has typing + tool traces;
    # email (Commit 2 of this flow) has different concepts and reads
    # its own sub-dict. We hydrate the platform's sub-dict once and
    # default every flag from there — keeps this function platform-
    # agnostic even though today only telegram uses the flags below.
    platform_cfg = _load_platform_cfg(home, platform.name)
    typing_task: asyncio.Task | None = None
    if platform_cfg.get("typing_indicator", True):
        typing_task = asyncio.create_task(_typing_loop(platform, msg.external_chat_id))

    show_trace = bool(platform_cfg.get("show_tool_trace", True))

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


def _load_platform_cfg(home: Path, platform: str) -> dict[str, Any]:
    """Return the ``gateway.<platform>`` sub-dict merged with defaults.

    Falls through to an empty dict on load failure — every caller
    should supply its own defaults via ``.get(key, default)`` so a
    transient config bug doesn't crash the gateway.
    """
    try:
        cfg = config_mod.load(home)
        return dict((cfg.gateway or {}).get(platform, {}))
    except Exception as e:  # noqa: BLE001
        log.warning("Could not load gateway config for %s: %s", platform, e)
        return {}


def _is_allowed(msg: IncomingMessage) -> bool:
    return delivery.is_allowed(msg.platform, msg.external_chat_id)


def run(home: Path) -> None:
    _configure_logging(home)
    _load_env(home)
    _write_pid(home)
    try:
        platforms: list[Platform] = [Telegram(home), Email(home), Webhook(home)]

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
