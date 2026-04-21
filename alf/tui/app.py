"""Main Textual App for alf."""

from __future__ import annotations

from pathlib import Path

from textual import events, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.message import Message
from textual.widgets import Input

from alf import config, home, memory
from alf.engine import AgentEvent, Engine
from alf.tui.screens import (
    CostPanel,
    FloatingPanel,
    HelpPanel,
    McpPanel,
    MemoryPanel,
    SkillsPanel,
    ToolsPanel,
)
from alf.tui.widgets import (
    AlfHeader,
    AlfTopBar,
    AssistantMessage,
    DimLine,
    ErrorLine,
    ReasoningLine,
    ThinkingIndicator,
    ToolCard,
    UserMessage,
)


class EngineEvent(Message):
    """Message posted from the engine worker to the UI thread."""

    def __init__(self, event: AgentEvent) -> None:
        super().__init__()
        self.event = event


def _copy_to_os_clipboard(text: str) -> str:
    import shutil
    import subprocess
    import sys

    candidates = []
    if sys.platform == "darwin":
        candidates.append(("pbcopy", ["pbcopy"]))
    else:
        if shutil.which("wl-copy"):
            candidates.append(("wl-copy", ["wl-copy"]))
        if shutil.which("xclip"):
            candidates.append(("xclip", ["xclip", "-selection", "clipboard"]))
        if shutil.which("xsel"):
            candidates.append(("xsel", ["xsel", "--clipboard", "--input"]))

    for name, cmd in candidates:
        try:
            proc = subprocess.run(
                cmd, input=text, text=True, check=True, timeout=3,
                capture_output=True,
            )
            if proc.returncode == 0:
                return name
        except Exception:
            continue
    return "osc52-only"


class AlfApp(App):
    CSS_PATH = "theme.tcss"
    TITLE = "alf"
    ENABLE_COMMAND_PALETTE = False  # hide the built-in Ctrl+P palette

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", priority=True),
        Binding("ctrl+l", "clear_chat", "Clear"),
        Binding("ctrl+y", "copy_last", "Copy last reply"),
        Binding("escape", "dismiss_panel", "Close panel", priority=True, show=False),
    ]

    def __init__(self, home_dir: Path, continue_last: bool = False) -> None:
        self.home = home_dir
        self.continue_last = continue_last
        self.cfg = config.load(home_dir)
        super().__init__()
        # Child widgets read `self.app.theme_variables` in their own on_mount
        # (fires before AlfApp.on_mount), so the theme must be installed here.
        self._install_theme()
        self.engine = Engine(home=home_dir, cfg=self.cfg)

        self._current_assistant: AssistantMessage | None = None
        self._active_tools: dict[str, ToolCard] = {}
        self._thinking: ThinkingIndicator | None = None
        self._turn_worker = None  # Worker returned by _run_turn


    def compose(self) -> ComposeResult:
        from textual.suggester import SuggestFromList
        from alf import __version__ as alf_version
        slash_commands = [
            "/help", "/memory", "/tools", "/mcps", "/cost", "/clear", "/new",
            "/compact", "/skills", "/model", "/workspace",
            "/exit", "/quit",
        ]
        yield AlfTopBar(
            version=alf_version,
            profile=self._profile_name(),
            path=str(self._effective_workspace()),
            workspace_set=self.cfg.workspace_path is not None,
        )
        with VerticalScroll(id="chat"):
            pass
        yield AlfHeader()
        yield Input(
            placeholder="Type a message or /help for commands…",
            id="chat-input",
            suggester=SuggestFromList(slash_commands, case_sensitive=False),
        )

    def _effective_workspace(self) -> Path:
        import os
        wp = self.cfg.workspace_path
        return wp if wp is not None else Path(os.getcwd()).resolve()

    def _maybe_warn_workspace(self) -> None:
        if self.cfg.workspace_path is not None:
            return
        cwd = self._effective_workspace()
        short = str(cwd).replace(str(Path.home()), "~")
        self._mount_message(ErrorLine(
            f"no workspace set — alf can touch everything under {short}. "
            f"Run /workspace <path> to narrow the scope."
        ))

    def _maybe_warn_model(self) -> None:
        model = (self.cfg.model or "").strip()
        if not model:
            self._mount_message(ErrorLine(
                "no model configured. Run `alf setup` to add a provider "
                "and pick a model, or /model to switch among configured ones."
            ))
            return
        head = model.split("/", 1)[0]
        from alf import providers as prov_mod
        for p in prov_mod.builtin():
            if p.name == head:
                if p.api_key_env and not p.has_key():
                    self._mount_message(ErrorLine(
                        f"model `{model}` needs {p.api_key_env} — "
                        f"not set. Run `alf setup` to add the key."
                    ))
                return
        customs = self.cfg.providers.get("custom", []) or []
        if any((c.get("name") or "") == head for c in customs):
            return
        self._mount_message(ErrorLine(
            f"model `{model}` points at unknown provider `{head}`. "
            f"Run `alf setup`."
        ))

    def _install_theme(self) -> None:
        from alf.tui.themes import build_theme
        tui = self.cfg.tui or {}
        accent = tui.get("accent") or "#ff8800"
        dark = str(tui.get("theme") or "dark").lower() != "light"
        theme = build_theme(accent=accent, dark=dark)
        self.register_theme(theme)
        self.theme = theme.name
        # Force theme_variables to rebuild now — setting `self.theme`
        # schedules an async refresh that lands AFTER child on_mount.
        self.get_css_variables()

    def _profile_name(self) -> str:
        import os
        from alf.home import _ROOT  # pyright: ignore[reportPrivateUsage]
        if os.environ.get("ALF_HOME"):
            return "override"
        if self.home == _ROOT:
            return "default"
        try:
            return self.home.relative_to(_ROOT / "profiles").parts[0]
        except Exception:
            return self.home.name

    async def on_mount(self) -> None:
        self.query_one(Input).focus()
        self._update_header()
        self._maybe_warn_workspace()
        self._maybe_warn_model()

        self.query_one("#chat", VerticalScroll).anchor()

        if self.continue_last:
            self._resume_last_session()

        from alf.tools import session_search
        session_search.set_current_session_id(self.engine.session.id)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        event.input.value = ""
        if not text:
            return
        if text.startswith("/"):
            self._handle_slash(text)
            return
        # @work(exclusive=True) replaces the old worker; we still set the
        # engine interrupt flag so the in-flight LLM call unwinds promptly.
        if self._turn_in_progress():
            self._interrupt_current_turn()
        self._scroll_end()
        self._mount_message(UserMessage(text))
        self._thinking = ThinkingIndicator()
        self._mount_message(self._thinking)
        # Defer so the UserMessage paints before the LLM round-trip starts.
        self.call_after_refresh(self._kickoff_turn, text)

    def _kickoff_turn(self, text: str) -> None:
        self._turn_worker = self._run_turn(text)

    def _turn_in_progress(self) -> bool:
        from textual.worker import WorkerState
        w = self._turn_worker
        return w is not None and w.state == WorkerState.RUNNING

    def _interrupt_current_turn(self) -> None:
        self.engine.request_interrupt()
        self._stop_thinking()
        self._mount_message(DimLine("↯ interrupted previous turn"))
        for tid, card in list(self._active_tools.items()):
            card.finish("[interrupted]", ok=False)
            self._active_tools.pop(tid, None)

    @work(thread=True, exclusive=True, name="_run_turn")
    def _run_turn(self, text: str) -> None:
        def sink(ev: AgentEvent) -> None:
            self.post_message(EngineEvent(ev))
        try:
            self.engine.run_turn(text, emit=sink)
        except Exception as e:  # noqa: BLE001
            self.post_message(EngineEvent(AgentEvent(kind="error", text=str(e))))
        self._after_turn()

    def _after_turn(self) -> None:
        self.call_from_thread(self._update_header)
        # Persist on every turn so a crashed terminal doesn't lose the log.
        try:
            self.engine.save_session()
        except Exception:
            pass

    def on_engine_event(self, message: EngineEvent) -> None:
        ev = message.event
        if ev.kind in ("assistant_delta", "tool_start", "error",
                       "done", "interrupted"):
            self._stop_thinking()
        if ev.kind == "reasoning_delta":
            if self._thinking is not None and self._show_reasoning():
                self._thinking.append_reasoning(ev.text)
            return
        if ev.kind == "assistant_delta":
            self._on_assistant_delta(ev.text)
        elif ev.kind == "assistant_done":
            pass
        elif ev.kind == "tool_start":
            self._on_tool_start(ev)
        elif ev.kind == "tool_state":
            self._on_tool_state(ev)
        elif ev.kind == "tool_end":
            self._on_tool_end(ev)
        elif ev.kind == "done":
            self._current_assistant = None
        elif ev.kind == "interrupted":
            self._current_assistant = None
        elif ev.kind == "error":
            self._mount_message(ErrorLine(ev.text))
        elif ev.kind == "usage":
            self._update_header()

    def _on_assistant_delta(self, delta: str) -> None:
        if not delta:
            return
        first_delta = self._current_assistant is None
        if first_delta:
            self._current_assistant = AssistantMessage()
            self._mount_message(self._current_assistant)
        self._current_assistant.append(delta)

    def _on_tool_start(self, ev: AgentEvent) -> None:
        reasoning = ""
        if self._current_assistant is not None:
            reasoning = (self._current_assistant.text or "").strip()
            self._current_assistant.remove()
            self._current_assistant = None
        if reasoning and self._show_reasoning():
            self._mount_message(ReasoningLine(reasoning))
        card = ToolCard(tool_id=ev.tool_id, name=ev.name, args=ev.args)
        self._active_tools[ev.tool_id] = card
        self._mount_message(card)

    def _show_reasoning(self) -> bool:
        return bool((self.cfg.tui or {}).get("show_reasoning", True))

    def _on_tool_state(self, ev: AgentEvent) -> None:
        card = self._active_tools.get(ev.tool_id)
        if card is not None:
            card.set_state(ev.text, is_error=not ev.ok)

    def _on_tool_end(self, ev: AgentEvent) -> None:
        card = self._active_tools.pop(ev.tool_id, None)
        if card is not None:
            card.finish(ev.output, ev.ok)

    def _handle_slash(self, text: str) -> None:
        parts = text[1:].split(maxsplit=1)
        cmd = parts[0].lower() if parts else ""
        arg = parts[1].strip() if len(parts) > 1 else ""
        handlers: dict = {
            "help": lambda _a: self._show_panel(HelpPanel()),
            "memory": lambda _a: self._show_panel(MemoryPanel(self.home)),
            "tools": lambda _a: self._show_panel(ToolsPanel()),
            "mcps": lambda _a: self._show_panel(McpPanel(self.engine._mcp_clients)),
            "cost": lambda _a: self._show_panel(CostPanel(self.engine.session)),
            "clear": lambda _a: self._cmd_clear(),
            "new": lambda _a: self._cmd_new(),
            "compact": lambda _a: self._cmd_compact(),
            "skills": lambda _a: self._cmd_skills(),
            "model": lambda _a: self._cmd_model(),
            "workspace": lambda a: self._cmd_workspace(a),
            "exit": lambda _a: self.action_quit(),
            "quit": lambda _a: self.action_quit(),
        }
        handler = handlers.get(cmd)
        if handler is None:
            self._mount_message(ErrorLine(f"unknown command: /{cmd}"))
            return
        handler(arg)

    def _cmd_clear(self) -> None:
        chat = self.query_one("#chat", VerticalScroll)
        chat.remove_children()
        self.engine.session.messages = [
            m for m in self.engine.session.messages if m.get("role") == "system"
        ]
        chat.mount(DimLine("(chat cleared)"))

    def _cmd_new(self) -> None:
        # Reload cfg from disk so any session-only `/model` switch is
        # forgotten — /new returns to the saved default.
        self.cfg = config.load(self.home)
        self.engine.cfg = self.cfg
        self.engine.reset_session()
        chat = self.query_one("#chat", VerticalScroll)
        chat.remove_children()
        chat.mount(DimLine(f"(new session — {self.engine.session.id})"))
        self._update_header()

    def _cmd_compact(self) -> None:
        import uuid
        tid = f"compact-{uuid.uuid4().hex[:8]}"
        convo_len = sum(
            1 for m in self.engine.session.messages if m.get("role") != "system"
        )
        card = ToolCard(
            tool_id=tid,
            name="compact",
            args={"messages": convo_len},
        )
        self._active_tools[tid] = card
        self._mount_message(card)
        self._do_compact(tid)

    @work(thread=True)
    def _do_compact(self, tool_id: str) -> None:
        from alf import llm

        card = self._active_tools.get(tool_id)
        convo = [m for m in self.engine.session.messages if m.get("role") != "system"]
        if not convo:
            if card is not None:
                self.call_from_thread(card.finish, "nothing to compact", False)
                self.call_from_thread(self._drop_active_tool, tool_id)
            return

        if card is not None:
            self.call_from_thread(card.set_state, "summarizing history…")

        prompt = (
            "Summarize the conversation so far as a concise bulleted briefing that "
            "preserves decisions, facts, open questions and any still-relevant tool "
            "outputs. Keep under 600 chars."
        )
        messages = list(self.engine.session.messages) + [{"role": "user", "content": prompt}]
        try:
            out = llm.complete(messages=messages, **config.resolve_model(self.cfg))
        except Exception as e:  # noqa: BLE001
            if card is not None:
                self.call_from_thread(card.finish, f"compact failed: {e}", False)
                self.call_from_thread(self._drop_active_tool, tool_id)
            return

        summary = (out.content or "").strip() or "(empty summary)"
        new_msgs = [m for m in self.engine.session.messages if m.get("role") == "system"]
        new_msgs.append({"role": "assistant", "content": f"[compacted summary]\n{summary}"})
        self.engine.session.messages = new_msgs
        total_chars = sum(len(m.get("content", "") or "") for m in new_msgs)
        self.engine.session.last_ctx_tokens = max(1, total_chars // 4)

        if card is not None:
            self.call_from_thread(card.finish, f"{len(summary)} char summary", True)
            self.call_from_thread(self._drop_active_tool, tool_id)
        self.call_from_thread(self._after_compact, summary)
        self.call_from_thread(self._update_header)

    def _stop_thinking(self) -> None:
        if self._thinking is not None:
            self._thinking.stop()
            self._thinking = None

    def _drop_active_tool(self, tool_id: str) -> None:
        self._active_tools.pop(tool_id, None)

    def _after_compact(self, summary: str) -> None:
        msg = AssistantMessage()
        self._mount_message(msg)
        msg.append(f"**Compacted summary**\n\n{summary}")

    def _cmd_skills(self) -> None:
        self._show_panel(SkillsPanel(self.home))

    def _show_panel(self, panel: FloatingPanel) -> None:
        self._dismiss_panels()
        self.mount(panel)
        self.screen.set_focus(None)

    def _dismiss_panels(self) -> bool:
        open_panels = list(self.query(FloatingPanel))
        for p in open_panels:
            p.remove()
        if open_panels:
            self.query_one("#chat-input").focus()
        return bool(open_panels)

    def action_dismiss_panel(self) -> None:
        self._dismiss_panels()

    def on_click(self, event: events.Click) -> None:
        panels = list(self.query(FloatingPanel))
        if not panels:
            return
        w = event.widget
        while w is not None:
            if isinstance(w, FloatingPanel):
                return
            w = w.parent
        self._dismiss_panels()

    def _cmd_workspace(self, arg: str) -> None:
        if not arg:
            suggested = self.cfg.workspace or str(self._effective_workspace())
            inp = self.query_one(Input)
            inp.value = f"/workspace {suggested}"
            inp.action_end()
            inp.focus()
            return
        if arg.lower() == "clear":
            self._apply_workspace("")
            return
        self._apply_workspace(arg)

    def _apply_workspace(self, raw: str) -> None:
        raw = (raw or "").strip()
        if not raw:
            self._mount_message(DimLine("workspace unchanged"))
            return
        if raw.lower() == "clear":
            self.cfg.workspace = ""
            config.save(self.cfg)
            self.cfg = config.load(self.home)
            self._mount_message(DimLine("workspace cleared — using cwd"))
            self._refresh_top_bar()
            return
        try:
            p = Path(raw).expanduser().resolve()
        except Exception as e:  # noqa: BLE001
            self._mount_message(ErrorLine(f"bad path: {e}"))
            return
        if not p.is_dir():
            self._mount_message(ErrorLine(
                f"not a directory (or doesn't exist): {p}"
            ))
            return
        self.cfg.workspace = str(p)
        config.save(self.cfg)
        self.cfg = config.load(self.home)
        self._mount_message(DimLine(f"workspace set to {p}"))
        self._refresh_top_bar()

    def _refresh_top_bar(self) -> None:
        self.query_one(AlfTopBar).set_state(
            profile=self._profile_name(),
            path=str(self._effective_workspace()),
            workspace_set=self.cfg.workspace_path is not None,
        )

    def _cmd_model(self) -> None:
        from alf.tui.model_panel import ProviderPanel
        self.cfg = config.load(self.home)
        self._show_panel(ProviderPanel(self.cfg, self.home))

    def _update_header(self) -> None:
        hdr = self.query_one(AlfHeader)
        s = self.engine.session
        hdr.update_usage(
            model=s.model,
            tokens=s.last_ctx_tokens,
            cost=s.cost_usd,
        )

    def _mount_message(self, widget) -> None:
        self.query_one("#chat", VerticalScroll).mount(widget)

    def _scroll_end(self) -> None:
        self.query_one("#chat", VerticalScroll).anchor()

    def action_clear_chat(self) -> None:
        self._cmd_clear()

    def action_copy_last(self) -> None:
        """Copy the last assistant response to the system clipboard."""
        chat = self.query_one("#chat", VerticalScroll)
        last_text = ""
        for child in reversed(list(chat.children)):
            if isinstance(child, AssistantMessage):
                last_text = child.text
                break
        if not last_text:
            self._mount_message(DimLine("(nothing to copy)"))
            return

        method = _copy_to_os_clipboard(last_text)
        try:
            self.copy_to_clipboard(last_text)
        except Exception:
            pass
        self._mount_message(
            DimLine(f"(copied {len(last_text):,} chars via {method})")
        )

    def action_quit(self) -> None:
        # cancel_all prevents mid-turn Ctrl+C from leaving the terminal in
        # mouse-reporting mode if an LLM request is in flight.
        try:
            self.workers.cancel_all()
        except Exception:
            pass
        try:
            self.engine.save_session()
        except Exception:
            pass
        self.exit()

    def _resume_last_session(self) -> None:
        from alf.cli import _continue_last_session
        resumed = _continue_last_session(self.engine, self.home)
        if not resumed:
            return

        turns = self.engine.session.turns
        self._mount_message(DimLine(
            f"✦ continuing session {self.engine.session.id} — "
            f"{len(turns)} turns loaded"
        ))

        for t in turns:
            if t.user:
                self._mount_message(UserMessage(t.user))
            for tl in t.tools:
                if tl.reasoning and self._show_reasoning():
                    self._mount_message(ReasoningLine(tl.reasoning))
                card = ToolCard(
                    tool_id=f"replay-{id(tl)}", name=tl.name, args=tl.args,
                )
                self._mount_message(card)
                card.finish(tl.result, ok=tl.ok, skip_duration=True)
            if t.assistant:
                self._mount_message(AssistantMessage(initial=t.assistant))

        self._update_header()
