"""Interactive setup for the Telegram platform."""

from __future__ import annotations

import os
from pathlib import Path

from alpi import ui
from alpi.model_selector import _append_env


def run(home: Path) -> None:
    ui.banner(
        ui.crumb("setup", "gateways", "telegram"),
        subtitle="bot + allowlist",
        home=home,
    )

    current_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    current_chats = os.environ.get("TELEGRAM_ALLOWED_CHAT_IDS", "")

    if not current_token:
        ui.dim(
            "You need a Telegram bot token and the chat IDs you want to\n"
            "allowlist. ~2 min:\n"
            "\n"
            "  1. Open Telegram and message @BotFather → /newbot.\n"
            "  2. Pick a display name and a unique username ending in 'bot'.\n"
            "  3. Copy the HTTP API token BotFather replies with.\n"
            "  4. Get your chat id: message @userinfobot → it replies with\n"
            "     your numeric id. For a group, add @userinfobot to it\n"
            "     (the group id is negative).\n"
            "  5. Start a chat with your new bot and send any message so\n"
            "     Telegram lets it reply back.\n"
            "\n"
            "The allowlist is fail-closed — any chat id not listed is\n"
            "silently ignored, so the bot can be public without you\n"
            "worrying about strangers triggering it.\n"
        )
        ui._console.print("")

    token = ui.password("Telegram bot token (from @BotFather):", current=current_token)
    if not token:
        return ui.cancelled()

    chat_ids_raw = ui.text(
        "Allowed chat IDs (comma-separated, e.g. 12345,67890):",
        default=current_chats,
    )
    if not chat_ids_raw:
        return ui.cancelled()
    chat_ids = [c.strip() for c in chat_ids_raw.split(",") if c.strip()]

    env_path = home / ".env"
    _append_env(env_path, "TELEGRAM_BOT_TOKEN", token)
    _append_env(env_path, "TELEGRAM_ALLOWED_CHAT_IDS", ",".join(chat_ids))
    # Mirror to os.environ so the status line updates immediately.
    os.environ["TELEGRAM_BOT_TOKEN"] = token
    os.environ["TELEGRAM_ALLOWED_CHAT_IDS"] = ",".join(chat_ids)

    ui.saved_and_wait(env_path)
