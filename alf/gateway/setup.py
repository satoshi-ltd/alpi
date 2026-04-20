"""Interactive setup for the Telegram platform."""

from __future__ import annotations

import os
from pathlib import Path

from alf import ui
from alf.model_selector import _append_env


def run(home: Path) -> None:
    ui.banner(
        ui.crumb("setup", "gateways", "telegram"),
        subtitle="bot + allowlist",
        home=home,
    )

    current_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    current_chats = os.environ.get("TELEGRAM_ALLOWED_CHAT_IDS", "")

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
    # Mirror to os.environ so the setup menu's status line updates
    # immediately, without requiring a restart.
    os.environ["TELEGRAM_BOT_TOKEN"] = token
    os.environ["TELEGRAM_ALLOWED_CHAT_IDS"] = ",".join(chat_ids)

    ui.saved(env_path)
    ui.press_enter()
