from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SlashCommand:
    name: str
    summary: str
    method: str
    usage: str = ""
    aliases: tuple[str, ...] = ()

    @property
    def takes_arg(self) -> bool:
        return bool(self.usage)

    @property
    def requires_arg(self) -> bool:
        return self.usage.startswith("<")

    @property
    def label(self) -> str:
        return f"/{self.name} {self.usage}".rstrip()


COMMANDS: tuple[SlashCommand, ...] = (
    SlashCommand("help", "commands and keys", "_cmd_help"),
    SlashCommand("activity", "what needs you, what runs, what is scheduled (daemon)", "_cmd_activity"),
    SlashCommand("status", "session snapshot — model, turns, tokens, cost", "_cmd_status"),
    SlashCommand("model", "switch model for this session", "_cmd_model"),
    SlashCommand("new", "fresh session on the saved default model", "_cmd_new"),
    SlashCommand("clear", "wipe the transcript and start a fresh session (keeps a /model switch)", "_cmd_clear"),
    SlashCommand("compact", "summarise older history now to free context", "_cmd_compact"),
    SlashCommand("sessions", "saved sessions — enter resumes, d twice deletes", "_cmd_sessions"),
    SlashCommand("outputs", "inbox — notifications, schedule replies, files", "_cmd_outputs"),
    SlashCommand("runs", "recent durable agent runs", "_cmd_runs"),
    SlashCommand("memory", "USER.md, MEMORY.md and AGENT.md", "_cmd_memory"),
    SlashCommand("skills", "installed skills", "_cmd_skills"),
    SlashCommand("tools", "available tools", "_cmd_tools"),
    SlashCommand("mcps", "running MCP servers", "_cmd_mcps"),
    SlashCommand("peers", "ALP peers — pick one to address it with @id", "_cmd_peers"),
    SlashCommand("diff", "what changed in this profile (default 24h)", "_cmd_diff", usage="[since]"),
    SlashCommand("fold", "this profile's origami object and colour for the apps", "_cmd_fold", usage="[object] [colour]"),
    SlashCommand("attach", "attach an image, PDF or text file to the next message", "_cmd_attach", usage="<path>"),
    SlashCommand("attachments", "list pending attachments", "_cmd_attachments"),
    SlashCommand("clear-attachments", "drop pending attachments", "_cmd_clear_attachments"),
    SlashCommand("quit", "save the session and quit", "_cmd_quit", aliases=("exit",)),
)

KEYS: tuple[tuple[str, str], ...] = (
    ("Enter", "send"),
    ("Ctrl+J", "new line — or end the line with \\ and press Enter (Shift+Enter on CSI-u terminals)"),
    ("↑ / ↓", "recall sent messages when the composer is empty"),
    ("Tab", "complete a /command or @peer"),
    ("Esc", "answer a prompt with deny/cancel · close a panel · stop the turn"),
    ("Ctrl+C", "stop the turn; press twice within 2s to quit"),
    ("Ctrl+O", "expand or collapse the last turn's reasoning and steps"),
    ("Ctrl+L", "clear the transcript (same as /clear)"),
    ("Ctrl+Y", "copy the last reply"),
)

_BY_NAME: dict[str, SlashCommand] = {}
for _c in COMMANDS:
    _BY_NAME[_c.name] = _c
    for _a in _c.aliases:
        _BY_NAME[_a] = _c


def lookup(name: str) -> SlashCommand | None:
    return _BY_NAME.get(name.lower().lstrip("/"))


def complete(prefix: str) -> list[SlashCommand]:
    needle = prefix.lower().lstrip("/")
    return [
        c for c in COMMANDS
        if c.name.startswith(needle) or any(a.startswith(needle) for a in c.aliases)
    ]


def parse(text: str) -> tuple[str, str]:
    parts = text.strip()[1:].split(maxsplit=1)
    name = parts[0].lower() if parts else ""
    arg = parts[1].strip() if len(parts) > 1 else ""
    return name, arg
