"""Gateway slash-command shortcuts — intercepted before the LLM.

A handful of operations that don't need an agent turn: reset the
chat's thread, inspect what's active, list the commands. Runs
cheap + instant; no tokens spent.

Cross-platform: every platform that sets ``IncomingMessage.raw_text``
(Telegram, IMAP, Gmail, webhook) reuses the same handler. The
shortcut scope deliberately stays narrow — anything useful beyond
these five should go through the agent so the behaviour is
consistent with the TUI surface.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from alpi import session_map


_COMMANDS: tuple[tuple[str, str], ...] = (
    ("help",     "List available commands"),
    ("status",   "Show active session (id, model, tokens, cost)"),
    ("new",      "Start a fresh session for this chat"),
    ("continue", "Show which session is being resumed"),
    ("model",    "Show the currently configured model"),
)

SHORTCUTS: tuple[str, ...] = tuple(name for name, _ in _COMMANDS)


def catalog() -> list[tuple[str, str]]:
    """Public (name, description) list — used by Telegram's setMyCommands
    so typing `/` opens the native command menu."""
    return list(_COMMANDS)


@dataclass
class Shortcut:
    name: str      # one of SHORTCUTS
    arg: str       # remainder of the line (may be empty)


def parse(raw_text: str) -> Shortcut | None:
    """Return a Shortcut if the first line is ``/cmd [arg]``, else None."""
    if not raw_text:
        return None
    first = raw_text.strip().splitlines()[0].strip()
    if not first.startswith("/"):
        return None
    head, _, rest = first[1:].partition(" ")
    head = head.lower()
    if head not in SHORTCUTS:
        return None
    return Shortcut(name=head, arg=rest.strip())


def handle(shortcut: Shortcut, chat_id: str, home: Path) -> str:
    """Render the reply for ``shortcut``. Returns empty string on unknown."""
    if shortcut.name == "help":
        return _help()
    if shortcut.name == "new":
        return _new(chat_id, home)
    if shortcut.name == "continue":
        return _continue(chat_id, home)
    if shortcut.name == "status":
        return _status(chat_id, home)
    if shortcut.name == "model":
        return _model(home)
    return ""


# Handlers


def _help() -> str:
    width = max(len(name) for name, _ in _COMMANDS)
    lines = ["Commands"]
    for name, desc in _COMMANDS:
        lines.append(f"  /{name.ljust(width)}  — {desc.lower()}")
    return "\n".join(lines) + "\n"


def _new(chat_id: str, home: Path) -> str:
    if not chat_id:
        return "no chat id — can't reset anything."
    dropped = session_map.forget(home, chat_id)
    if dropped:
        return "started a new session for this chat."
    return "no active session to reset; next message starts fresh."


def _continue(chat_id: str, home: Path) -> str:
    if not chat_id:
        return "no chat id — can't identify this thread."
    current = session_map.get(home, chat_id)
    if not current:
        return "no active session yet; next message will open one."
    return f"resuming session {current}."


def _status(chat_id: str, home: Path) -> str:
    sid = session_map.get(home, chat_id) if chat_id else None
    if not sid:
        return "no active session yet for this chat."
    session_file = home / "sessions" / f"{sid}.json"
    if not session_file.exists():
        return f"session {sid} is pointed to but the file is missing."
    try:
        data = json.loads(session_file.read_text())
    except Exception:  # noqa: BLE001
        return f"session {sid}: (unreadable)"
    turns = len(data.get("turns") or [])
    tok_in = data.get("input_tokens", 0)
    tok_out = data.get("output_tokens", 0)
    # Rendered with MarkdownV2 (see alpi/gateway/platforms/_md2.py):
    # `**x**` becomes bold, specials in values are auto-escaped.
    return (
        f"**session {sid}**\n"
        f"\n"
        f"**model**  {data.get('model', '?')}\n"
        f"**turns**  {turns}\n"
        f"**tokens** in={tok_in:,}  out={tok_out:,}  total={tok_in + tok_out:,}\n"
        f"**cost**   ${data.get('cost_usd', 0.0):.4f}"
    )


def _model(home: Path) -> str:
    from alpi import config as cfg_mod
    try:
        cfg = cfg_mod.load(home)
    except Exception:  # noqa: BLE001
        return "can't read config.yaml."
    if not cfg.model:
        return "no model configured. Run `alpi setup → Model` on the machine."
    return f"active model: {cfg.model}"
