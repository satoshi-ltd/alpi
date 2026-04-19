"""Gateway entry point.

Starts each enabled platform as an asyncio task. For every incoming message,
the gateway spawns a subprocess running ``alf chat --once --input "<text>"``
and sends stdout back to the platform. This keeps the gateway small and
isolates agent crashes from the listener.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

from alf.gateway.base import IncomingMessage, OutgoingMessage, Platform
from alf.gateway.pairing import PairingStore
from alf.gateway.platforms.telegram import Telegram
from alf.gateway.platforms.webhook import Webhook

log = logging.getLogger("alf.gateway")


async def _handle_platform(platform: Platform, pairings: PairingStore, home: Path) -> None:
    async for msg in platform.listen():
        if not _is_allowed(msg, pairings):
            log.warning(
                "Dropping message from unpaired chat: %s:%s",
                msg.platform, msg.external_chat_id,
            )
            continue
        log.info("[%s] %s: %s", msg.platform, msg.external_user_id, msg.text[:100])
        asyncio.create_task(_process(platform, msg, home))


async def _process(platform: Platform, msg: IncomingMessage, home: Path) -> None:
    reply = await _run_agent(msg.text, home)
    if not reply.strip():
        reply = "(no response)"
    await platform.send(OutgoingMessage(
        external_chat_id=msg.external_chat_id,
        text=reply,
    ))


async def _run_agent(user_text: str, home: Path) -> str:
    """Invoke ``alf chat --once`` in a subprocess and capture stdout."""
    env = dict(os.environ)
    env["ALF_HOME"] = str(home)
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "alf", "chat", "--once", user_text,
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        log.error("agent subprocess failed (rc=%s): %s", proc.returncode, stderr.decode()[:500])
        return f"(agent error, rc={proc.returncode})"
    return stdout.decode().strip()


def _is_allowed(msg: IncomingMessage, pairings: PairingStore) -> bool:
    pair = pairings.get(msg.platform, msg.external_chat_id)
    return bool(pair and pair.allow)


def run(home: Path) -> None:
    _configure_logging(home)
    _load_env(home)
    _write_pid(home)
    try:
        pairings = PairingStore(home)
        platforms: list[Platform] = [Telegram(home), Webhook(home)]

        async def _main() -> None:
            await asyncio.gather(*(_handle_platform(p, pairings, home) for p in platforms))

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
