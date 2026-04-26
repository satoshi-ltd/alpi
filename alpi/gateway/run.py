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
from alpi.gateway.platforms.telegram import Telegram
from alpi.gateway.platforms.webhook import Webhook

log = logging.getLogger("alpi.gateway")

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
        if msg.ack is not None:
            await msg.ack()
        # Flatten newlines so multi-line inbound (email bodies with
        # a Subject line + blank line + body) stays a single log entry.
        preview = " ".join(msg.text.split())[:120]
        log.info("[%s] %s: %s", msg.platform, msg.external_user_id, preview)
        asyncio.create_task(_process(platform, msg, home))


async def _process(platform: Platform, msg: IncomingMessage, home: Path) -> None:
    # Intercept slash-command shortcuts before we spawn an agent turn.
    # Every shortcut (`/help`, `/status`, `/new`, `/continue`, `/model`)
    # resolves locally from session_map + config.yaml — no LLM round-trip.
    from alpi.gateway import shortcuts as shortcuts_mod

    # ALP @peer mentions route directly through link.ask — no local
    # LLM turn. Same parser + executor as the TUI so ``@mirai hi``
    # from Telegram behaves exactly like it does in the TUI.
    from alpi.alp import mention as alp_mention

    parsed_mention = alp_mention.parse(msg.text, home=home)
    if parsed_mention is not None:
        # Mirror the tool-trace UX from the LLM path: if the platform has
        # ``show_tool_trace`` on, emit a ``◆ peer · peer_id=…`` line first
        # so the user sees the same "tool call happened" feedback whether
        # the ``peer`` tool was invoked by the LLM or by an @-mention.
        platform_cfg = _load_platform_cfg(home, platform.name)
        if bool(platform_cfg.get("show_tool_trace", True)):
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
        # /model on Telegram opens an interactive inline-keyboard picker —
        # other platforms (IMAP, Gmail) fall through to the plain-text
        # handler which just reports the currently configured model.
        if cmd.name == "model" and hasattr(platform, "send_model_picker"):
            await platform.send_model_picker(msg.external_chat_id)  # type: ignore[attr-defined]
            return
        reply = shortcuts_mod.handle(cmd, msg.external_chat_id, home)
        if reply.strip():
            await platform.send(OutgoingMessage(
                external_chat_id=msg.external_chat_id, text=reply,
            ))
        return

    # Per-platform UX config. Telegram has typing + tool traces; email has
    # different concepts and reads its own sub-dict. Stays platform-agnostic.
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
    """Build the LLM-facing prompt from an inbound message.

    Platforms yield the user's raw text; the agent-boundary prefix
    (`[INBOUND TELEGRAM from …]`, email subject line) is constructed
    here so ``IncomingMessage.text`` stays a clean single source of
    truth for shortcut parsing, logging, and tests.
    """
    if msg.platform == "telegram":
        return f"[INBOUND TELEGRAM from {msg.external_user_id}]\n{msg.text}"
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
    # Per-chat session threading: the CLI consults `sessions/_gateway_map.json`
    # and resumes whichever session was last bound to this chat id, or starts
    # fresh and binds it after save.
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


def _is_allowed(msg: IncomingMessage) -> bool:
    return delivery.is_allowed(msg.platform, msg.external_chat_id)


async def serve(home: Path) -> None:
    """Async entry point for the orchestrator. Returns when cancelled.
    Logging + env are owned by the orchestrator now (one shared
    config), so this only spins up the platform listeners."""
    platforms: list[Platform] = [
        Telegram(home), Imap(home), Gmail(home), Webhook(home),
    ]
    await asyncio.gather(*(_handle_platform(p, home) for p in platforms))
