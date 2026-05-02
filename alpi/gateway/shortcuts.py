"""Gateway slash-command shortcuts."""

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
    ("peers",    "List ALP peers and their reachability"),
)

SHORTCUTS: tuple[str, ...] = tuple(name for name, _ in _COMMANDS)


def catalog() -> list[tuple[str, str]]:
    """Public command list used by Telegram."""
    return list(_COMMANDS)


@dataclass
class Shortcut:
    name: str      # one of SHORTCUTS
    arg: str       # remainder of the line (may be empty)


def parse(raw_text: str) -> Shortcut | None:
    """Return a Shortcut for a leading `/cmd [arg]`, else `None`."""
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
    """Render a reply for ``shortcut``."""
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
    if shortcut.name == "peers":
        return _peers(home)
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

    from alpi import config as cfg_mod
    from alpi.status import status_rows, status_title

    cfg = cfg_mod.load(home)
    rows = status_rows(
        session_id=sid,
        model=data.get("model", "?"),
        turns=len(data.get("turns") or []),
        elapsed_seconds=None,  # session file does not persist clock-time
        input_tokens=data.get("input_tokens", 0),
        output_tokens=data.get("output_tokens", 0),
        cost_usd=data.get("cost_usd", 0.0),
        home=home,
        cfg_budget=cfg.budget,
    )

    # Fenced block keeps alignment and skips MarkdownV2 escaping.
    label_w = max(len(label) for label, _ in rows)
    body = "\n".join(
        f"{label.ljust(label_w)}  {value}" for label, value in rows
    )
    return f"**{status_title(sid)}**\n\n```\n{body}\n```"


def _peers(home: Path) -> str:
    """Render pinned peers from ``peers.yaml``."""
    from alpi.alp import peers as peers_mod

    entries = peers_mod.load(home)
    if not entries:
        return (
            "no peers pinned yet.\n"
            "Exchange pubkeys out-of-band and run `alpi setup → Peers → "
            "+ Add peer` on the machine."
        )
    lines = ["**Peers**", ""]
    for peer in entries:
        allow = ", ".join(sorted(peer.allow)) or "no capabilities"
        lines.append(f"@{peer.id}  —  {allow}")
    lines.append("")
    lines.append("Send `@<peer> <prompt>` to route a message directly.")
    return "\n".join(lines)


def _model(home: Path) -> str:
    from alpi import config as cfg_mod
    try:
        cfg = cfg_mod.load(home)
    except Exception:  # noqa: BLE001
        return "can't read config.yaml."
    if not cfg.model:
        return "no model configured. Run `alpi setup → Model` on the machine."
    return f"active model: {cfg.model}"
