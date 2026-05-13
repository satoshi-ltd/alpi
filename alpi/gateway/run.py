"""Gateway entry point."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

from alpi import config as config_mod
from alpi.gateway import delivery
from alpi.gateway.base import IncomingMessage, OutgoingMessage, Platform
from alpi.gateway.platforms.gmail import Gmail
from alpi.gateway.platforms.imap import Imap
from alpi.gateway.platforms.matrix import Matrix
from alpi.gateway.platforms.telegram import Telegram
from alpi.gateway.platforms.webhook import Webhook

log = logging.getLogger("alpi.gateway")

# Refresh typing slightly before Telegram times out.
_TYPING_REFRESH_SECONDS = 4.0


async def _handle_platform(platform: Platform, home: Path) -> None:
    async for msg in platform.listen():
        if not _is_allowed(msg):
            log.warning(
                "Dropping message from disallowed chat: %s:%s",
                msg.platform, msg.external_chat_id,
            )
            continue
        if msg.ack is not None:
            await msg.ack()
        # Flatten newlines so logs stay single-line.
        preview = " ".join(msg.text.split())[:120]
        log.info("[%s] %s: %s", msg.platform, msg.external_user_id, preview)
        asyncio.create_task(_process(platform, msg, home))


async def _process(platform: Platform, msg: IncomingMessage, home: Path) -> None:
    # Handle slash commands before spawning an agent turn.
    from alpi.gateway import shortcuts as shortcuts_mod

    # Route @mentions directly without an LLM turn.
    from alpi.alp import mention as alp_mention

    parsed_mention = alp_mention.parse(msg.text, home=home)
    if parsed_mention is not None:
        # Mirror the LLM tool-trace UX.
        platform_cfg = _load_platform_cfg(home, platform.name)
        if _show_tool_trace(platform.name, platform_cfg):
            trace = _format_tool_trace({
                "name": "peer",
                "preview": f"peer_id={parsed_mention.peer_id}",
            })
            await platform.send(OutgoingMessage(
                external_chat_id=msg.external_chat_id, text=trace,
            ))
        result = await alp_mention.execute(
            home, parsed_mention.peer_id, parsed_mention.prompt,
        )
        reply_text = result.reply if result.ok else f"[{parsed_mention.peer_id}] {result.error}"
        if reply_text.strip():
            await platform.send(OutgoingMessage(
                external_chat_id=msg.external_chat_id, text=reply_text,
            ))
        return

    cmd = shortcuts_mod.parse(msg.text)
    if cmd is not None:
        # Telegram opens the inline picker; others reply in text.
        if cmd.name == "model" and hasattr(platform, "send_model_picker"):
            await platform.send_model_picker(msg.external_chat_id)  # type: ignore[attr-defined]
            return
        reply = shortcuts_mod.handle(cmd, msg.external_chat_id, home)
        if reply.strip():
            await platform.send(OutgoingMessage(
                external_chat_id=msg.external_chat_id, text=reply,
            ))
        return

    # Per-platform UX config.
    platform_cfg = _load_platform_cfg(home, platform.name)
    typing_task: asyncio.Task | None = None
    if _typing_indicator_enabled(platform.name):
        typing_task = asyncio.create_task(_typing_loop(platform, msg.external_chat_id))

    show_trace = _show_tool_trace(platform.name, platform_cfg)

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
        return
    await platform.send(OutgoingMessage(
        external_chat_id=msg.external_chat_id,
        text=reply,
    ))


async def _typing_loop(platform: Platform, chat_id: str) -> None:
    while True:
        try:
            await platform.send_typing(chat_id)
        except Exception as e:  # noqa: BLE001
            log.debug("typing ping failed: %s", e)
        await asyncio.sleep(_TYPING_REFRESH_SECONDS)


def _llm_prompt(msg: IncomingMessage) -> str:
    """Build the LLM-facing prompt."""
    if msg.platform == "telegram":
        return f"[INBOUND TELEGRAM from {msg.external_user_id}]\n{msg.text}"
    if msg.platform == "matrix":
        return f"[INBOUND MATRIX from {msg.external_user_id} in {msg.external_chat_id}]\n{msg.text}"
    if msg.platform in ("email", "gmail"):
        subject = msg.subject or "(no subject)"
        return (
            f"[INBOUND EMAIL from {msg.external_user_id}]\n"
            f"Subject: {subject}\n\n{msg.text}"
        )
    if msg.platform == "webhook":
        return f"[INBOUND WEBHOOK from {msg.external_user_id}]\n{msg.text}"
    return msg.text


async def _run_agent(msg: IncomingMessage, platform: Platform, home: Path,
                     show_trace: bool) -> str:
    env = dict(os.environ)
    env["ALPI_HOME"] = str(home)
    env["ALPI_GATEWAY"] = "1"
    env["ALPI_PLATFORM"] = msg.platform
    prompt = _llm_prompt(msg)
    argv = [
        sys.executable, "-m", "alpi", "chat", "--once", prompt,
        "--emit-events",
    ]
    # Resume the chat-bound session if one exists.
    if msg.external_chat_id:
        argv += ["--resume-chat", msg.external_chat_id]
    proc = await asyncio.create_subprocess_exec(
        *argv,
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
    try:
        cfg = config_mod.load(home)
        return dict((cfg.gateway or {}).get(platform, {}))
    except Exception as e:  # noqa: BLE001
        log.warning("Could not load gateway config for %s: %s", platform, e)
        return {}


_CHAT_PLATFORMS = frozenset({"telegram", "matrix"})


def _typing_indicator_enabled(platform: str) -> bool:
    return platform in _CHAT_PLATFORMS


def _show_tool_trace(platform: str, platform_cfg: dict[str, Any]) -> bool:
    if platform in _CHAT_PLATFORMS:
        return bool(platform_cfg.get("show_tool_trace", True))
    return False  # email → tool traces would each be a separate message


def _is_allowed(msg: IncomingMessage) -> bool:
    return delivery.is_allowed(msg.platform, msg.external_chat_id)


async def serve(home: Path) -> None:
    """Async entry point for the orchestrator. Returns when cancelled.
    Logging + env are owned by the orchestrator now (one shared
    config), so this only spins up the platform listeners."""
    platforms: list[Platform] = [
        Telegram(home), Imap(home), Gmail(home), Matrix(home), Webhook(home),
    ]
    await asyncio.gather(*(_handle_platform(p, home) for p in platforms))
