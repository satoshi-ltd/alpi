"""Floating chat-overlay panels for /help, /memory, /tools, /cost, /skills."""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Markdown, Static


class FloatingPanel(Container):

    DEFAULT_CSS = """
    FloatingPanel {
        layer: overlay;
        dock: bottom;
        margin: 0 0 7 0;
        padding: 0 1;
        width: 1fr;
        min-height: 0;
        height: auto;
        max-height: 24;
        background: transparent;
        border: none;
    }
    FloatingPanel > .panel-frame {
        width: 1fr;
        min-height: 0;
        height: auto;
        max-height: 24;
        background: $surface;
    }
    FloatingPanel > .panel-frame > .panel-header {
        background: $surface-lighten-1;
        height: 3;
        padding: 1 2;
        margin: 0;
    }
    FloatingPanel:light > .panel-frame > .panel-header {
        background: $surface-darken-1;
    }
    FloatingPanel > .panel-frame > .panel-header > .panel-title {
        color: $foreground;
        text-style: bold;
        width: 1fr;
        height: 1;
    }
    FloatingPanel > .panel-frame > .panel-header > .panel-hint {
        color: $text-muted;
        width: auto;
        height: 1;
    }
    FloatingPanel > .panel-frame > .panel-content {
        padding: 1 3;
        min-height: 0;
        height: auto;
    }
    FloatingPanel > .panel-frame > .panel-content > VerticalScroll {
        min-height: 0;
        height: auto;
        max-height: 18;
        scrollbar-size: 0 0;
    }
    FloatingPanel .entry-name {
        color: $accent;
        text-style: bold;
        height: auto;
    }
    FloatingPanel .entry-desc {
        color: $text-muted;
        height: auto;
        margin-bottom: 1;
    }
    FloatingPanel Markdown {
        background: transparent;
        padding: 0;
        margin: 0;
    }
    FloatingPanel MarkdownBullet {
        color: $text-muted;
    }
    FloatingPanel MarkdownBlock > .code_inline {
        background: transparent;
        color: $accent-darken-1;
        text-style: none;
    }
    FloatingPanel MarkdownHeader {
        background: transparent;
        border: none;
    }
    """

    panel_title: str = ""

    def compose(self) -> ComposeResult:
        with Container(classes="panel-frame"):
            with Horizontal(classes="panel-header"):
                yield Static(self.panel_title, classes="panel-title")
                yield Static("esc or click outside to close", classes="panel-hint")
            with Container(classes="panel-content"):
                yield from self.compose_body()

    def compose_body(self) -> ComposeResult:
        return
        yield  # pragma: no cover — make this a generator


class HelpPanel(FloatingPanel):
    panel_title = "/help"

    def compose_body(self) -> ComposeResult:
        body = (
            "**Slash commands**\n\n"
            "- `/help` — this panel\n"
            "- `/memory` — show USER.md, MEMORY.md and personality.md\n"
            "- `/tools` — list available tools\n"
            "- `/mcps` — list running MCP servers\n"
            "- `/cost` — session cost breakdown\n"
            "- `/skills` — list installed skills\n"
            "- `/clear` — clear chat history (keeps session)\n"
            "- `/new` — start a fresh session (new id, history wiped)\n"
            "- `/compact` — summarize history to save tokens\n"
            "- `/model` — change model / provider\n"
            "- `/workspace` — show or set the sandbox root\n"
            "- `/exit` — quit\n\n"
            "**Keybindings**\n\n"
            "- `Enter` — send message\n"
            "- `Ctrl+C` — quit\n"
            "- `Ctrl+L` — clear chat\n"
            "- `Ctrl+Y` — copy last assistant reply\n"
            "- `Esc` — close panel\n"
        )
        yield VerticalScroll(Markdown(body))


class MemoryPanel(FloatingPanel):
    panel_title = "/memory"

    def __init__(self, home: Path) -> None:
        super().__init__()
        self.home = home

    def compose_body(self) -> ComposeResult:
        from alpi import memory
        store = memory.MemoryStore(home=self.home)
        store.seed_defaults()
        snap = store.snapshot()
        usage = store.usage()

        user_used, user_limit = usage["USER.md"]
        mem_used, mem_limit = usage["MEMORY.md"]
        user_pct = int(user_used / user_limit * 100) if user_limit else 0
        mem_pct = int(mem_used / mem_limit * 100) if mem_limit else 0

        personality_path = self.home / "personality.md"
        personality = personality_path.read_text() if personality_path.exists() else ""

        body = (
            f"**USER.md** — {user_pct}% ({user_used:,}/{user_limit:,} chars)\n\n"
            f"```\n{snap['USER.md'] or '(empty)'}\n```\n\n"
            f"**MEMORY.md** — {mem_pct}% ({mem_used:,}/{mem_limit:,} chars)\n\n"
            f"```\n{snap['MEMORY.md'] or '(empty)'}\n```\n\n"
            f"**personality.md**\n\n"
            f"```\n{personality or '(empty)'}\n```\n"
        )
        yield VerticalScroll(Markdown(body))


class ToolsPanel(FloatingPanel):
    panel_title = "/tools"

    def compose_body(self) -> ComposeResult:
        from alpi import tools
        with VerticalScroll():
            for cls in tools.all_tools():
                yield Static(cls.name, classes="entry-name")
                yield Static(_short(cls.description), classes="entry-desc")


class McpPanel(FloatingPanel):
    panel_title = "/mcps"

    def __init__(self, clients: list) -> None:
        super().__init__()
        self.clients = clients

    def compose_body(self) -> ComposeResult:
        if not self.clients:
            yield Static(
                "No MCP servers running. Run `alpi setup` from the shell "
                "and pick 'MCP servers' to add one.",
                classes="entry-desc",
            )
            return
        with VerticalScroll():
            for client in self.clients:
                tools = client.list_tools()
                status = "running" if client.is_running() else "stopped"
                summary = f"{status} · {len(tools)} tool{'' if len(tools) == 1 else 's'}"
                if tools:
                    summary += " — " + ", ".join(t.name for t in tools[:6])
                    if len(tools) > 6:
                        summary += f", +{len(tools) - 6} more"
                yield Static(client.name, classes="entry-name")
                yield Static(summary, classes="entry-desc")


def _short(desc: str, max_chars: int = 130) -> str:
    head = desc.split("\n\n", 1)[0].strip()
    head = " ".join(head.split())
    if len(head) > max_chars:
        head = head[: max_chars - 1].rsplit(" ", 1)[0] + "…"
    return head


class CostPanel(FloatingPanel):
    panel_title = "/cost"

    def __init__(self, session) -> None:  # noqa: ANN001
        super().__init__()
        self.sess = session

    def compose_body(self) -> ComposeResult:
        mins, secs = divmod(int(self.sess.elapsed), 60)
        body = (
            f"- **session** `{self.sess.id}`\n"
            f"- **model** `{self.sess.model}`\n"
            f"- **elapsed** {mins:02d}:{secs:02d}\n\n"
            f"**tokens**\n\n"
            f"- input: {self.sess.input_tokens:,}\n"
            f"- output: {self.sess.output_tokens:,}\n"
            f"- total: {self.sess.input_tokens + self.sess.output_tokens:,}\n\n"
            f"**cost** ${self.sess.cost_usd:.4f}\n"
        )
        yield VerticalScroll(Markdown(body))


class SkillsPanel(FloatingPanel):
    panel_title = "/skills"

    def __init__(self, home: Path) -> None:
        super().__init__()
        self.home = home

    def compose_body(self) -> ComposeResult:
        entries = self._collect()
        if not entries:
            yield Static("no skills installed yet", classes="entry-desc")
            return
        with VerticalScroll():
            for name, desc in entries:
                yield Static(name, classes="entry-name")
                yield Static(desc, classes="entry-desc")

    def _collect(self) -> list[tuple[str, str]]:
        root = self.home / "skills"
        if not root.exists():
            return []
        out: list[tuple[str, str]] = []
        for cat in sorted(root.iterdir()):
            if not cat.is_dir() or cat.name.startswith("_"):
                continue
            for skill in sorted(cat.iterdir()):
                if not skill.is_dir():
                    continue
                meta = _read_frontmatter(skill / "SKILL.md")
                out.append((skill.name, meta.get("description", "")))
        return out


def _read_frontmatter(path: Path) -> dict:
    if not path.exists():
        return {}
    text = path.read_text()
    if not text.startswith("---"):
        return {}
    try:
        _, raw, _ = text.split("---", 2)
    except ValueError:
        return {}
    meta: dict = {}
    for line in raw.strip().splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        meta[k.strip()] = v.strip()
    return meta
