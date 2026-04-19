"""Interactive setup for the Telegram gateway.

Writes TELEGRAM_BOT_TOKEN and TELEGRAM_ALLOWED_CHAT_IDS to ~/.alf/.env —
the single source of truth for both secrets and allowlist.
"""

from __future__ import annotations

from pathlib import Path

import questionary
from rich.console import Console

from alf.model_selector import _ask, _append_env

_console = Console()


def run(home: Path) -> None:
    _console.print("[b]Gateway setup[/b]  [dim](Telegram)[/dim]")
    _console.print(
        "[dim]You need a Telegram bot token from @BotFather and your chat ID. "
        "To get the chat ID: send a message to your bot, then visit "
        "https://api.telegram.org/bot<TOKEN>/getUpdates[/dim]\n"
    )

    token = _ask(questionary.password("Telegram bot token (from @BotFather):"))
    if not token:
        _console.print("[yellow]cancelled[/yellow]")
        return

    chat_ids_raw = _ask(questionary.text(
        "Allowed chat IDs (comma-separated, e.g. 12345,67890):"
    ))
    if not chat_ids_raw:
        _console.print("[yellow]cancelled[/yellow]")
        return
    chat_ids = [c.strip() for c in chat_ids_raw.split(",") if c.strip()]

    env_path = home / ".env"
    _append_env(env_path, "TELEGRAM_BOT_TOKEN", token)
    _append_env(env_path, "TELEGRAM_ALLOWED_CHAT_IDS", ",".join(chat_ids))

    _console.print(f"[green]✓[/green] saved token + {len(chat_ids)} chat(s) to [dim]{env_path}[/dim]")
    _console.print("[dim]Next:[/dim] [b]alf gateway start[/b]")
