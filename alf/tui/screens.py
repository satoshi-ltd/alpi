"""Modal screens — /help, /memory, /tools, /cost, /skills."""

from __future__ import annotations

import shutil
from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Markdown, OptionList, Static
from textual.widgets.option_list import Option


class HelpScreen(ModalScreen):
    BINDINGS = [Binding("escape,q", "dismiss", "close")]

    def compose(self) -> ComposeResult:
        body = (
            "# alf · help\n\n"
            "**Slash commands**\n\n"
            "- `/help` — this screen\n"
            "- `/memory` — show USER.md + MEMORY.md\n"
            "- `/tools` — list available tools\n"
            "- `/cost` — session cost breakdown\n"
            "- `/clear` — clear chat history\n"
            "- `/compact` — summarize history to save tokens\n"
            "- `/model` — change model / provider\n"
            "- `/skills` — review skills (approve/reject proposals)\n"
            "- `/workspace` — show or set the sandbox root\n"
            "- `/exit` — quit\n\n"
            "**Keybindings**\n\n"
            "- `Enter` — send message\n"
            "- `Ctrl+C` — quit\n"
            "- `Ctrl+L` — clear chat\n"
            "- `Ctrl+Y` — copy last assistant reply to clipboard\n"
            "- `Ctrl+P` — command palette\n"
            "- `Esc` — close modal\n\n"
            "**Copy arbitrary text**\n\n"
            "Click-drag to select inside alf (Textual highlights it). "
            "On macOS, hold `⌥ Option` while dragging in Terminal.app or "
            "iTerm2 to bypass capture and use the terminal's native "
            "select+copy. Or use `Ctrl+Y` to grab the last reply.\n"
        )
        with Vertical():
            yield Markdown(body)


class MemoryScreen(ModalScreen):
    BINDINGS = [Binding("escape,q", "dismiss", "close")]

    def __init__(self, home: Path) -> None:
        super().__init__()
        self.home = home

    def compose(self) -> ComposeResult:
        from alf import memory
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
            f"# memory\n\n"
            f"## USER.md — {user_pct}%  ({user_used:,}/{user_limit:,} chars)\n\n"
            f"```\n{snap['USER.md'] or '(empty)'}\n```\n\n"
            f"## MEMORY.md — {mem_pct}%  ({mem_used:,}/{mem_limit:,} chars)\n\n"
            f"```\n{snap['MEMORY.md'] or '(empty)'}\n```\n\n"
            f"## personality.md\n\n"
            f"```\n{personality or '(empty)'}\n```\n"
        )
        with Vertical():
            with VerticalScroll():
                yield Markdown(body)


class ToolsScreen(ModalScreen):
    BINDINGS = [Binding("escape,q", "dismiss", "close")]

    def compose(self) -> ComposeResult:
        from alf import tools
        rows = ["# tools\n"]
        for cls in tools.all_tools():
            rows.append(f"- **{cls.name}** — {cls.description}")
        body = "\n\n".join(rows)
        with Vertical():
            with VerticalScroll():
                yield Markdown(body)


class SkillsScreen(ModalScreen):
    """List live + pending skills. Approve/reject pending ones.

    Key bindings on a highlighted pending row:
      a — approve (move from _pending to <category>/<name>/)
      r — reject (delete pending dir)
      v — view SKILL.md body
    """

    BINDINGS = [
        Binding("escape,q", "dismiss", "close"),
        Binding("a", "approve", "approve"),
        Binding("r", "reject", "reject"),
        Binding("v", "view", "view"),
    ]

    def __init__(self, home: Path) -> None:
        super().__init__()
        self.home = home
        # opt_id -> (kind, path)  kind ∈ {"pending", "live"}
        self._items: dict[str, tuple[str, Path]] = {}

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("Skills", classes="modal-title")
            yield OptionList(*self._build_options(), id="skills-options")
            yield Static(
                "[dim]↑↓ navigate  a approve  r reject  v view  ESC close[/dim]",
                classes="modal-hint",
            )

    def _build_options(self) -> list[Option]:
        from alf.tools.create_skill import pending_skills, pending_dir

        options: list[Option] = []
        self._items.clear()

        pending = pending_skills(self.home)
        if pending:
            options.append(Option(Text("── pending approval ──", style="dim"), disabled=True))
            for i, path in enumerate(pending):
                meta = _read_frontmatter(path / "SKILL.md")
                label = Text()
                label.append(path.name, style="bold yellow")
                cat = meta.get("category", "")
                if cat:
                    label.append(f"  {cat}", style="dim")
                desc = meta.get("description", "")
                if desc:
                    label.append(f"  {desc}", style="dim")
                opt_id = f"pending-{i}"
                self._items[opt_id] = ("pending", path)
                options.append(Option(label, id=opt_id))

        root = self.home / "skills"
        live_entries: list[tuple[str, Path, dict]] = []
        if root.exists():
            for cat in sorted(root.iterdir()):
                if not cat.is_dir() or cat.name.startswith("_"):
                    continue
                for skill in sorted(cat.iterdir()):
                    if not skill.is_dir():
                        continue
                    meta = _read_frontmatter(skill / "SKILL.md")
                    live_entries.append((cat.name, skill, meta))

        if live_entries:
            if pending:
                options.append(Option(Text(" ", style="dim"), disabled=True))
            options.append(Option(Text("── installed ──", style="dim"), disabled=True))
            for i, (cat, skill, meta) in enumerate(live_entries):
                origin = meta.get("origin", "user")
                label = Text()
                label.append(skill.name, style="bold")
                label.append(f"  {cat}", style="dim")
                label.append(f"  ({origin})", style="green" if origin == "user" else "cyan")
                desc = meta.get("description", "")
                if desc:
                    label.append(f"  {desc}", style="dim")
                opt_id = f"live-{i}"
                self._items[opt_id] = ("live", skill)
                options.append(Option(label, id=opt_id))

        if not options:
            options.append(Option(Text("(no skills yet)", style="dim"), disabled=True))
        return options

    def _selected_pending(self) -> Path | None:
        olist = self.query_one(OptionList)
        idx = olist.highlighted
        if idx is None:
            return None
        opt = olist.get_option_at_index(idx)
        if opt.id is None:
            return None
        kind, path = self._items.get(opt.id, ("", Path()))
        return path if kind == "pending" else None

    def action_approve(self) -> None:
        path = self._selected_pending()
        if path is None:
            return
        meta = _read_frontmatter(path / "SKILL.md")
        category = meta.get("category") or "meta"
        dest = self.home / "skills" / category / path.name
        if dest.exists():
            self.notify(f"target exists: {dest} — rejecting instead", severity="warning")
            shutil.rmtree(path, ignore_errors=True)
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), str(dest))
            self.notify(f"approved: {dest}", severity="information")
        self._rebuild()

    def action_reject(self) -> None:
        path = self._selected_pending()
        if path is None:
            return
        shutil.rmtree(path, ignore_errors=True)
        self.notify(f"rejected: {path.name}", severity="warning")
        self._rebuild()

    def action_view(self) -> None:
        olist = self.query_one(OptionList)
        idx = olist.highlighted
        if idx is None:
            return
        opt = olist.get_option_at_index(idx)
        if opt.id is None or opt.id not in self._items:
            return
        _kind, path = self._items[opt.id]
        body_path = path / "SKILL.md"
        if not body_path.exists():
            return
        self.app.push_screen(_SkillBodyScreen(body_path))

    def _rebuild(self) -> None:
        olist = self.query_one(OptionList)
        olist.clear_options()
        for opt in self._build_options():
            olist.add_option(opt)


class _SkillBodyScreen(ModalScreen):
    BINDINGS = [Binding("escape,q", "dismiss", "close")]

    def __init__(self, path: Path) -> None:
        super().__init__()
        self.path = path

    def compose(self) -> ComposeResult:
        body = self.path.read_text()
        with Vertical():
            with VerticalScroll():
                yield Markdown(f"```\n{body}\n```")


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


class CostScreen(ModalScreen):
    BINDINGS = [Binding("escape,q", "dismiss", "close")]

    def __init__(self, session) -> None:  # noqa: ANN001
        super().__init__()
        self.sess = session

    def compose(self) -> ComposeResult:
        mins, secs = divmod(int(self.sess.elapsed), 60)
        body = (
            f"# cost\n\n"
            f"- **session** `{self.sess.id}`\n"
            f"- **model** `{self.sess.model}`\n"
            f"- **elapsed** {mins:02d}:{secs:02d}\n\n"
            f"**tokens**\n\n"
            f"- input: {self.sess.input_tokens:,}\n"
            f"- output: {self.sess.output_tokens:,}\n"
            f"- total: {self.sess.input_tokens + self.sess.output_tokens:,}\n\n"
            f"**cost** ${self.sess.cost_usd:.4f}\n"
        )
        with Vertical():
            yield Markdown(body)
