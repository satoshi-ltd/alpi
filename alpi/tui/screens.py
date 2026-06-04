"""Floating chat-overlay panels for /help, /memory, /tools, /cost, /skills."""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Markdown, OptionList, Static
from textual.widgets.option_list import Option


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
        padding: 0 0;
    }
    FloatingPanel VerticalScroll {
        padding: 0 0;
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
    FloatingPanel .list-row {
        height: 1;
    }
    FloatingPanel .help-section {
        color: $text-muted;
        margin-top: 1;
        margin-bottom: 0;
    }
    FloatingPanel .memory-section {
        color: $accent;
        text-style: bold;
        margin-top: 1;
        margin-bottom: 0;
        height: auto;
    }
    FloatingPanel .memory-section:first-of-type {
        margin-top: 0;
    }
    FloatingPanel Markdown {
        background: transparent;
        padding: 0;
        margin: 0 0 1 0;
        height: auto;
    }
    FloatingPanel .help-section:first-of-type {
        margin-top: 0;
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

    _COMMANDS: list[tuple[str, str]] = [
        ("help",      "this panel"),
        ("memory",    "show USER.md, MEMORY.md and AGENT.md"),
        ("tools",     "list available tools"),
        ("mcps",      "list running MCP servers"),
        ("status",    "session snapshot — model, turns, tokens, cost"),
        ("skills",    "list installed skills"),
        ("peers",     "list ALP peers; pick one to drop @id into the input"),
        ("diff",      "what changed in this profile in the last 24h"),
        ("attach",    "attach an image/PDF to the next message: /attach <path>"),
        ("attachments", "list pending attachments"),
        ("clear-attachments", "drop pending attachments"),
        ("clear",     "clear chat history (keeps session)"),
        ("new",       "start a fresh session (new id, history wiped)"),
        ("compact",   "force auto-compact now (recovery)"),
        ("model",     "change model / provider"),
        ("exit",      "quit"),
    ]

    _KEYS: list[tuple[str, str]] = [
        ("Enter",  "send message"),
        ("Ctrl+C", "quit"),
        ("Ctrl+L", "clear chat"),
        ("Ctrl+Y", "copy last assistant reply"),
        ("Esc",    "close panel"),
    ]

    def compose_body(self) -> ComposeResult:
        from alpi.tui.list_row import build_options, name_width, row_text

        cmd_items = [(k, f"/{k}", desc) for k, desc in self._COMMANDS]
        # No active key: /help is a palette, nothing is selected.
        # with_marker=False kills the 2-char prefix so rows align with the
        # section header instead of sitting indented inside the highlight bar.
        options = build_options(cmd_items, with_marker=False)
        yield Static("slash commands — select to run", classes="help-section")
        yield OptionList(*options, id="help-commands", compact=True)

        key_width = name_width([k for k, _ in self._KEYS])
        yield Static("keybindings", classes="help-section")
        with VerticalScroll(id="help-keys"):
            for key, desc in self._KEYS:
                yield Static(
                    row_text(key, desc, width=key_width, with_marker=False),
                    classes="list-row",
                )

    def on_mount(self) -> None:
        self.call_after_refresh(self._focus_list)

    def _focus_list(self) -> None:
        if not self.is_mounted:
            return
        try:
            self.query_one("#help-commands", OptionList).focus()
        except Exception:  # noqa: BLE001
            pass

    def on_option_list_option_selected(
        self, event: OptionList.OptionSelected,
    ) -> None:
        cmd = event.option.id
        if not cmd:
            return
        self.remove()
        # Defer so the panel is fully gone before the next one mounts.
        self.app.call_after_refresh(self.app._handle_slash, f"/{cmd}")


class MemoryPanel(FloatingPanel):
    panel_title = "/memory"

    def __init__(self, home: Path) -> None:
        super().__init__()
        self.home = home

    def compose_body(self) -> ComposeResult:
        from alpi import memory
        from alpi.home import agent_path as _agent_path

        store = memory.MemoryStore(home=self.home)
        store.seed_defaults()
        snap = store.snapshot()
        usage = store.usage()

        user_used, user_limit = usage["USER.md"]
        mem_used, mem_limit = usage["MEMORY.md"]
        user_pct = int(user_used / user_limit * 100) if user_limit else 0
        mem_pct = int(mem_used / mem_limit * 100) if mem_limit else 0

        ap = _agent_path(self.home)
        agent_profile = ap.read_text() if ap.exists() else ""

        with VerticalScroll():
            yield Static(
                f"USER.md · {user_pct}% ({user_used:,}/{user_limit:,} chars)",
                classes="memory-section",
            )
            yield from _render_delimited(snap["USER.md"])
            yield Static(
                f"MEMORY.md · {mem_pct}% ({mem_used:,}/{mem_limit:,} chars)",
                classes="memory-section",
            )
            yield from _render_delimited(snap["MEMORY.md"])
            yield Static("AGENT.md", classes="memory-section")
            yield Markdown(agent_profile.strip() or "_(empty)_")


def _render_delimited(text: str):
    from alpi.memory import ENTRY_DELIMITER
    body = text.strip()
    if not body:
        yield Markdown("_(empty)_")
        return
    for entry in body.split(ENTRY_DELIMITER):
        entry = entry.strip()
        if entry:
            yield Markdown(entry)


class ToolsPanel(FloatingPanel):
    panel_title = "/tools"

    def compose_body(self) -> ComposeResult:
        from alpi import tools
        with VerticalScroll():
            for cls in tools.all_tools():
                if ":" in cls.name:
                    continue
                yield Static(cls.name, classes="entry-name")
                yield Static(_short(cls.description), classes="entry-desc")


class DiffPanel(FloatingPanel):
    """``/diff [since]`` — what changed in this profile since the cutoff.
    ``since`` accepts ``Nh`` / ``Nd`` / ``Nw`` (default ``24h``) or an
    ISO-8601 timestamp."""

    panel_title = "/diff"

    def __init__(self, home: Path, since: str = "24h") -> None:
        super().__init__()
        self.home = home
        self.since_spec = since or "24h"

    def compose_body(self) -> ComposeResult:
        from alpi import diff as diff_mod

        try:
            cutoff = diff_mod.parse_since(self.since_spec)
        except ValueError as e:
            yield Static(str(e), classes="entry-desc")
            return
        report = diff_mod.compute(self.home, cutoff)
        text = diff_mod.render(report, profile=self.home.name or "default")
        with VerticalScroll():
            yield Static(text, classes="entry-desc")


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


def _status_rows(
    session,  # noqa: ANN001
    *,
    home: Path | None = None,
    cfg_budget: dict | None = None,
) -> list[tuple[str, str]]:
    from alpi.status import status_rows

    return status_rows(
        session_id=session.id,
        model=session.model,
        turns=len(getattr(session, "turns", []) or []),
        elapsed_seconds=int(getattr(session, "elapsed", 0) or 0),
        input_tokens=session.input_tokens,
        output_tokens=session.output_tokens,
        cost_usd=session.cost_usd,
        home=home,
        cfg_budget=cfg_budget,
    )


class StatusPanel(FloatingPanel):
    """/status — session snapshot. Same shape as the Telegram ``/status``
    shortcut so users see one consistent view across surfaces."""

    panel_title = "/status"

    def __init__(
        self,
        session,  # noqa: ANN001
        *,
        home: Path | None = None,
        cfg_budget: dict | None = None,
    ) -> None:
        super().__init__()
        self.sess = session
        self.home = home
        self.cfg_budget = cfg_budget

    def compose_body(self) -> ComposeResult:
        from rich.text import Text

        rows = _status_rows(
            self.sess, home=self.home, cfg_budget=self.cfg_budget,
        )
        width = max(len(label) for label, _ in rows)

        title = Text()
        title.append("session ", style="bold")
        title.append(self.sess.id, style="bold")
        yield Static(title)
        yield Static("")
        for label, value in rows:
            row = Text()
            row.append(label.ljust(width), style="bold")
            row.append("  ")
            row.append(value)
            yield Static(row)


_LIST_PANEL_CSS = """
OptionList {
    background: transparent !important;
    margin: 0;
    max-height: 18;
}
"""


class PeersPanel(FloatingPanel):
    """List pinned ALP peers; selecting one drops ``@peer_id `` into the
    input so the user can type the prompt right after."""

    panel_title = "/peers"
    DEFAULT_CSS = _LIST_PANEL_CSS

    def __init__(self, home: Path) -> None:
        super().__init__()
        self.home = home

    def compose_body(self) -> ComposeResult:
        from alpi.alp import peers as peers_mod
        from alpi.tui.list_row import build_options

        entries = peers_mod.load(self.home)
        if not entries:
            yield Static(
                "no peers pinned yet. See `alpi peers add` or `alpi setup → Peers`.",
                classes="entry-desc",
            )
            return
        items: list[tuple[str, str, str]] = []
        for p in entries:
            verbs = ", ".join(sorted(p.allow)) or "no capabilities"
            address = f" · {p.address}" if p.address else ""
            items.append((p.id, f"@{p.id}", f"{verbs}{address}"))
        accent = self.app.theme_variables.get("accent")
        yield OptionList(*build_options(items, accent=accent), id="peers-options", compact=True)

    def on_mount(self) -> None:
        self.call_after_refresh(self._focus_list)

    def _focus_list(self) -> None:
        try:
            self.query_one(OptionList).focus()
        except Exception:  # noqa: BLE001
            pass

    def on_option_list_option_selected(
        self, event: OptionList.OptionSelected,
    ) -> None:
        peer_id = event.option.id or ""
        self.remove()
        if not peer_id:
            return
        try:
            from textual.widgets import Input
            inp = self.app.query_one(Input)
            inp.value = f"@{peer_id} "
            inp.cursor_position = len(inp.value)
            inp.focus()
        except Exception:  # noqa: BLE001
            pass


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


class ApprovalPanel(FloatingPanel):
    panel_title = "⚠ approval required"
    DEFAULT_CSS = _LIST_PANEL_CSS

    _OPTIONS: list[tuple[str, str, str]] = [
        ("once",    "Once",    "approve just this one call"),
        ("session", "Session", "approve for this session"),
        ("always",  "Always",  "persist to config.yaml allowlist"),
        ("deny",    "Deny",    "refuse"),
    ]

    def __init__(self, command: str, pattern: str, severity: str,
                 on_choice) -> None:
        super().__init__()
        self._command = command
        self._pattern = pattern
        self._severity = severity
        self._on_choice = on_choice
        self.panel_title = f"⚠ {severity.upper()} · {pattern}"

    def compose_body(self) -> ComposeResult:
        from alpi.tui.list_row import build_options
        yield Static(self._command, classes="entry-desc")
        accent = self.app.theme_variables.get("accent")
        options = build_options(list(self._OPTIONS), accent=accent)
        yield OptionList(*options, id="approval-options", compact=True)

    def on_mount(self) -> None:
        self.call_after_refresh(self._focus_list)

    def _focus_list(self) -> None:
        try:
            self.query_one(OptionList).focus()
        except Exception:  # noqa: BLE001
            pass

    def on_option_list_option_selected(
        self, event: OptionList.OptionSelected,
    ) -> None:
        choice = event.option.id or "deny"
        self.remove()
        self._on_choice(choice)


class ClarificationPanel(FloatingPanel):
    panel_title = "Question"
    DEFAULT_CSS = _LIST_PANEL_CSS + """
    ClarificationPanel #clarify-other {
        margin-top: 1;
    }
    """

    _OTHER_KEY = "__other__"

    def __init__(
        self,
        question: str,
        choices: list[dict],
        allow_other: bool,
        multi: bool,
        on_choice,
    ) -> None:
        super().__init__()
        self._question = question
        self._choices = choices
        self._allow_other = bool(allow_other) and not bool(multi)
        self._multi = bool(multi)
        self._on_choice = on_choice
        self._awaiting_input = False
        self._input_purpose = ""
        self.panel_title = "Question"

    def compose_body(self) -> ComposeResult:
        from alpi.tui.list_row import build_options
        yield Static(self._question, classes="entry-desc")
        if self._multi:
            from textual.widgets import Input
            yield Static(
                "Multi-select — type comma-separated numbers or labels.",
                classes="entry-desc",
            )
            for i, c in enumerate(self._choices, start=1):
                line = f"  {i}. {c['label']}"
                if c.get("description"):
                    line += f" — {c['description']}"
                yield Static(line, classes="entry-desc")
            self._awaiting_input = True
            self._input_purpose = "multi"
            yield Input(
                placeholder="e.g. 1,3 or Sleep summary, Training load",
                id="clarify-other",
            )
            return
        accent = self.app.theme_variables.get("accent")
        items: list[tuple[str, str, str]] = []
        for c in self._choices:
            items.append((c["label"], c["label"], c.get("description", "") or ""))
        if self._allow_other:
            items.append((
                self._OTHER_KEY, "Other",
                "type your own answer",
            ))
        options = build_options(items, accent=accent)
        yield OptionList(*options, id="clarify-options", compact=True)

    def on_mount(self) -> None:
        self.call_after_refresh(self._focus_first)

    def _focus_first(self) -> None:
        try:
            if self._multi:
                from textual.widgets import Input
                self.query_one(Input).focus()
            else:
                self.query_one(OptionList).focus()
        except Exception:  # noqa: BLE001
            pass

    def on_option_list_option_selected(
        self, event: OptionList.OptionSelected,
    ) -> None:
        choice = event.option.id or ""
        if choice == self._OTHER_KEY:
            self._show_other_input()
            return
        self.remove()
        self._on_choice(choice)

    def _show_other_input(self) -> None:
        from textual.widgets import Input
        self._awaiting_input = True
        self._input_purpose = "other"
        try:
            self.query_one(OptionList).remove()
        except Exception:  # noqa: BLE001
            pass
        inp = Input(
            placeholder="Type your answer, press Enter…",
            id="clarify-other",
        )
        self.mount(inp)
        inp.focus()

    def on_input_submitted(self, event) -> None:
        if not self._awaiting_input:
            return
        text = (event.value or "").strip()
        if self._input_purpose == "multi":
            picks = self._resolve_multi(text)
            if not picks:
                # Don't close — let the user retry (mirrors the inline TUI reprompt).
                self._show_multi_error(
                    "No valid picks recognised. Use the numbers shown or the "
                    "labels exactly; separate with commas."
                )
                return
            self.remove()
            self._on_choice(", ".join(picks))
            return
        self.remove()
        self._on_choice(text)

    def _show_multi_error(self, message: str) -> None:
        from textual.widgets import Input
        try:
            existing = self.query_one("#clarify-error", Static)
            existing.update(message)
        except Exception:  # noqa: BLE001
            try:
                inp = self.query_one(Input)
                err = Static(message, id="clarify-error", classes="entry-desc")
                self.mount(err, before=inp)
            except Exception:  # noqa: BLE001
                pass
        try:
            inp = self.query_one(Input)
            inp.value = ""
            inp.focus()
        except Exception:  # noqa: BLE001
            pass

    def _resolve_multi(self, raw: str) -> list[str]:
        picked: list[str] = []
        label_lookup = {c["label"].lower(): c["label"] for c in self._choices}
        for tok in (t.strip() for t in raw.split(",")):
            if not tok:
                continue
            if tok.isdigit():
                idx = int(tok)
                if 1 <= idx <= len(self._choices):
                    lab = self._choices[idx - 1]["label"]
                    if lab not in picked:
                        picked.append(lab)
                continue
            resolved = label_lookup.get(tok.lower())
            if resolved and resolved not in picked:
                picked.append(resolved)
        return picked
