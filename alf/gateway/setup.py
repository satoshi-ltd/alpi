"""Interactive setup for the Telegram platform.

Writes TELEGRAM_BOT_TOKEN and TELEGRAM_ALLOWED_CHAT_IDS to ~/.alf/.env —
the single source of truth for both secrets and allowlist. These
credentials power the gateway's inbound listener AND the outbound
``send_message`` tool; both read the same env vars.
"""

from __future__ import annotations

import os
from pathlib import Path

import questionary
from rich.console import Console

from alf.model_selector import _append_env, _ask

_console = Console()


def run(home: Path) -> None:
    _console.print("[b]Telegram setup[/b]  [dim](bot + allowlist)[/dim]")
    _console.print(
        "[dim]You need a Telegram bot token from @BotFather and your chat ID. "
        "To get the chat ID: send a message to your bot, then visit "
        "https://api.telegram.org/bot<TOKEN>/getUpdates[/dim]\n"
    )

    current_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    current_chats = os.environ.get("TELEGRAM_ALLOWED_CHAT_IDS", "")

    if current_token:
        _console.print(
            f"[dim]Current token: …{current_token[-4:]}  "
            f"(press ENTER to keep, or paste a new one)[/dim]"
        )
        token = _ask(questionary.password(
            "Telegram bot token (from @BotFather):",
        )) or current_token
    else:
        token = _ask(questionary.password("Telegram bot token (from @BotFather):"))
    if not token:
        _console.print("[yellow]cancelled[/yellow]")
        return

    chat_ids_raw = _ask(questionary.text(
        "Allowed chat IDs (comma-separated, e.g. 12345,67890):",
        default=current_chats,
    ))
    if not chat_ids_raw:
        _console.print("[yellow]cancelled[/yellow]")
        return
    chat_ids = [c.strip() for c in chat_ids_raw.split(",") if c.strip()]

    env_path = home / ".env"
    _append_env(env_path, "TELEGRAM_BOT_TOKEN", token)
    _append_env(env_path, "TELEGRAM_ALLOWED_CHAT_IDS", ",".join(chat_ids))
    # Keep os.environ in sync so the setup menu's status line updates
    # immediately after the wizard returns.
    os.environ["TELEGRAM_BOT_TOKEN"] = token
    os.environ["TELEGRAM_ALLOWED_CHAT_IDS"] = ",".join(chat_ids)

    _console.print(f"[green]✓[/green] saved token + {len(chat_ids)} chat(s) to [dim]{env_path}[/dim]")
    _console.print("[dim]Next:[/dim] [b]alf gateway start[/b]")
