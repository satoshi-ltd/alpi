"""Main Textual App for alpi."""

from __future__ import annotations

import time
from pathlib import Path

from textual import events, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.message import Message
from textual.widgets import Input

from alpi import config, home, memory
from alpi.engine import AgentEvent, Engine
from alpi.tui.screens import (
    StatusPanel,
    DiffPanel,
    FloatingPanel,
    HelpPanel,
    McpPanel,
    MemoryPanel,
    PeersPanel,
    SkillsPanel,
    ToolsPanel,
)
from alpi.tui.widgets import (
    AlpiHeader,
    AlpiTopBar,
    AssistantMessage,
    ChatInput,
    DimLine,
    ErrorLine,
    ReasoningLine,
    ResumeActivity,
    ThinkingIndicator,
    ToolCard,
    UserMessage,
)


class EngineEvent(Message):
    """Message posted from the engine worker to the UI thread."""

    def __init__(self, event: AgentEvent) -> None:
        super().__init__()
        self.event = event


class MentionChunk(Message):
    """One streamed delta from ``link.ask`` — posted from the worker."""

    def __init__(self, widget: "AssistantMessage", text: str) -> None:
        super().__init__()
        self.widget = widget
        self.text = text


class MentionDone(Message):
    """ALP ``link.ask`` finished — posted from the worker to the UI."""

    def __init__(
        self,
        card: "ToolCard",
        ok: bool,
        output: str,
        reply: str,
        peer_id: str = "",
        prompt: str = "",
        started: float = 0.0,
    ) -> None:
        super().__init__()
        self.card = card
        self.ok = ok
        self.output = output
        self.peer_id = peer_id
        self.prompt = prompt
        self.started = started
        self.reply = reply


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


class AlpiApp(App):
    CSS_PATH = "theme.tcss"
    TITLE = "alpi"
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
        # (fires before AlpiApp.on_mount), so the theme must be installed here.
        self._install_theme()
        self.engine = Engine(home=home_dir, cfg=self.cfg)

        self._current_assistant: AssistantMessage | None = None
        self._active_tools: dict[str, ToolCard] = {}
        self._thinking: ThinkingIndicator | None = None
        self._turn_worker = None  # Worker returned by _run_turn
        self._pending_attachments: list[dict] = []  # MM.1: /attach staging for the next turn


    def compose(self) -> ComposeResult:
        from textual.suggester import SuggestFromList
        from alpi import __version__ as alpi_version
        slash_commands = [
            "/help", "/memory", "/tools", "/mcps", "/status", "/clear", "/new",
            "/compact", "/skills", "/model", "/peers", "/diff",
            "/attach", "/attachments", "/clear-attachments",
            "/exit", "/quit",
        ]
        # Peer mentions share the same popup — typing ``@`` surfaces pinned
        # peers so the user can route a one-shot ask without remembering ids.
        try:
            from alpi.alp import peers as _peers_mod
            slash_commands.extend(f"@{p.id}" for p in _peers_mod.load(self.home))
        except Exception:  # noqa: BLE001
            pass
        from alpi import updater as _updater
        yield AlpiTopBar(
            version=alpi_version,
            profile=self._profile_name(),
            path=str(self._effective_workspace()),
            workspace_set=self.cfg.workspace_path is not None,
            sandbox=self.cfg.tools.terminal.sandbox,
            network_locked=(
                self.cfg.tools.terminal.sandbox
                and not self.cfg.tools.terminal.allow_network
            ),
            profile_size=home.profile_size_label(self.home),
            update_available=_updater.available_update() or "",
        )
        with VerticalScroll(id="chat"):
            pass
        yield AlpiHeader()
        yield ChatInput(
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
            f"no workspace set — alpi can touch everything under {short}. "
            f"Pin one via `alpi setup → Workspace` to narrow the scope."
        ))

    def _maybe_warn_model(self) -> None:
        model = (self.cfg.model or "").strip()
        if not model:
            self._mount_message(ErrorLine(
                "no model configured. Run `alpi setup` to add a provider "
                "and pick a model, or /model to switch among configured ones."
            ))
            return
        head = model.split("/", 1)[0]
        from alpi import providers as prov_mod
        from alpi.home import effective_profile_env
        env = effective_profile_env(self.cfg.home)
        for p in prov_mod.builtin():
            if p.name == head:
                if p.api_key_env and not p.has_key(env):
                    self._mount_message(ErrorLine(
                        f"model `{model}` needs {p.api_key_env} — "
                        f"not set. Run `alpi setup` to add the key."
                    ))
                return
        ollamas = self.cfg.providers.get("ollama", []) or []
        if any((e.get("name") or "") == head for e in ollamas):
            return
        self._mount_message(ErrorLine(
            f"model `{model}` points at unknown provider `{head}`. "
            f"Run `alpi setup`."
        ))

    def _install_theme(self) -> None:
        from alpi.tui.themes import build_theme
        tui = self.cfg.tui or {}
        accent = tui.get("accent") or "#c8a24e"
        dark = str(tui.get("theme") or "dark").lower() != "light"
        theme = build_theme(accent=accent, dark=dark)
        self.register_theme(theme)
        self.theme = theme.name
        # Force theme_variables to rebuild now — setting `self.theme`
        # schedules an async refresh that lands AFTER child on_mount.
        self.get_css_variables()

    def _profile_name(self) -> str:
        import os
        from alpi.home import _ROOT  # pyright: ignore[reportPrivateUsage]
        if os.environ.get("ALPI_HOME"):
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
            # Full TUI renders immediately; rehydration runs as a worker.
            # A thin ResumeActivity bar sits between the top bar and the
            # chat scroll with a spinner + "resuming…" text. Messages
            # stream into the chat below as they mount; when the worker
            # finishes it removes the activity bar.
            activity = ResumeActivity()
            self.mount(activity, before=self.query_one("#chat"))
            self.call_after_refresh(self._kick_resume, activity)

        from alpi.tools import session_search
        session_search.set_current_session_id(self.engine.session.id)

        from alpi.tools._approval import set_prompt_callback
        set_prompt_callback(self._approval_prompt_blocking)
        from alpi.tools._clarification import set_handler as _set_clarify
        _set_clarify(self._clarification_prompt_blocking)

    async def on_unmount(self) -> None:
        from alpi.tools._approval import set_prompt_callback
        set_prompt_callback(None)
        from alpi.tools._clarification import set_handler as _set_clarify
        _set_clarify(None)

    def _approval_prompt_blocking(self, command: str, pattern: str, severity, cwd: str | None = None) -> str:
        import threading
        from alpi.tui.screens import ApprovalPanel

        result: list[str] = ["deny"]
        done = threading.Event()
        sev_str = severity.value if hasattr(severity, "value") else str(severity)

        def _on_choice(choice: str) -> None:
            result[0] = choice or "deny"
            done.set()

        def _show() -> None:
            self._show_panel(ApprovalPanel(command, pattern, sev_str, _on_choice))

        self.call_from_thread(_show)
        if not done.wait(60):
            self.call_from_thread(self._dismiss_panels)
            return "deny"
        return result[0]

    def _clarification_prompt_blocking(
        self,
        question: str,
        choices: list[dict],
        allow_other: bool,
        multi: bool = False,
    ) -> str:
        import threading
        from alpi.tui.screens import ClarificationPanel

        result: list[str] = [""]
        done = threading.Event()

        def _on_choice(choice: str) -> None:
            result[0] = choice or ""
            done.set()

        def _show() -> None:
            self._show_panel(
                ClarificationPanel(
                    question, choices, bool(allow_other), bool(multi), _on_choice,
                ),
            )

        self.call_from_thread(_show)
        if not done.wait(300):
            self.call_from_thread(self._dismiss_panels)
            return ""
        return result[0]

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        event.input.value = ""
        if not text and not self._pending_attachments:
            return
        if text.startswith("/"):
            self._handle_slash(text)
            return
        from alpi.alp import mention as alp_mention
        parsed = alp_mention.parse(text, home=self.home)
        if parsed is not None:
            if self._pending_attachments:
                self._mount_message(ErrorLine("attachments aren't supported with @mentions — clear them first"))
                return
            self._handle_mention(text, parsed=parsed)
            return
        # @work(exclusive=True) replaces the old worker; we still set the
        # engine interrupt flag so the in-flight LLM call unwinds promptly.
        if self._turn_in_progress():
            self._interrupt_current_turn()
        self._scroll_end()
        if text:
            self._mount_message(UserMessage(text))
        self._thinking = ThinkingIndicator()
        self._mount_message(self._thinking)
        # Defer so the UserMessage paints before the LLM round-trip starts.
        self.call_after_refresh(self._kickoff_turn, text)

    def _kickoff_turn(self, text: str) -> None:
        attachments = self._pending_attachments or None
        self._pending_attachments = []
        self._turn_worker = self._run_turn(text, attachments)

    def _turn_in_progress(self) -> bool:
        from textual.worker import WorkerState
        w = self._turn_worker
        return w is not None and w.state == WorkerState.RUNNING

    def _interrupt_current_turn(self) -> None:
        self.engine.request_interrupt("tui-stop")
        self._stop_thinking()
        self._mount_message(DimLine("↯ interrupted previous turn"))
        for tid, card in list(self._active_tools.items()):
            card.finish("[interrupted]", ok=False)
            self._active_tools.pop(tid, None)

    @work(thread=True, exclusive=True, name="_run_turn")
    def _run_turn(self, text: str, attachments: list[dict] | None = None) -> None:
        def sink(ev: AgentEvent) -> None:
            self.post_message(EngineEvent(ev))
        try:
            self.engine.run_turn(text, emit=sink, attachments=attachments)
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
            text = ev.text
            if ev.final and ev.attachments:
                from alpi.attachments import render_output_attachments
                listing = render_output_attachments(ev.attachments)
                text = "\n\n".join(x for x in (text, listing) if x)
            if self._current_assistant is not None:
                self._current_assistant.replace(text)
            elif text:
                msg = AssistantMessage()
                self._mount_message(msg)
                msg.replace(text)
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
        elif ev.kind == "auto_compact":
            self._mount_message(DimLine(f"↺ {ev.text}"))
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

    def _handle_mention(self, text: str, parsed=None) -> None:
        """``@peer ...`` anywhere in the input — one-shot ALP
        ``link.ask`` to a pinned peer, bypassing the local LLM.
        Renders exactly like a tool call so the transcript reads the
        same whether the user or the agent invoked it. Caller passes
        ``parsed`` (already validated against the roster) so we don't
        re-parse here."""
        if parsed is None:
            from alpi.alp import mention as alp_mention
            parsed = alp_mention.parse(text, home=self.home)
        if parsed is None:
            self._mount_message(ErrorLine("usage: @<peer> <prompt>"))
            return

        self._scroll_end()
        self._mount_message(UserMessage(text))
        card = ToolCard(
            tool_id=f"mention-{parsed.peer_id}-{id(parsed)}",
            name="peer",
            args={"peer_id": parsed.peer_id, "prompt": parsed.prompt},
        )
        self._mount_message(card)
        asst = AssistantMessage()
        self._mount_message(asst)
        self._run_mention(parsed.peer_id, parsed.prompt, card, asst)

    @work(thread=True, name="_run_mention")
    def _run_mention(
        self, peer_id: str, prompt: str, card: ToolCard, asst: "AssistantMessage",
    ) -> None:
        import asyncio
        import time
        from alpi.alp import mention as alp_mention

        started = time.time()

        async def consume() -> tuple[bool, str, str]:
            parts: list[str] = []
            ok = True
            error_text = ""
            final_text = ""
            async for frame in alp_mention.execute_stream(self.home, peer_id, prompt):
                kind = frame.get("kind")
                if kind == "chunk":
                    delta = str(frame.get("text") or "")
                    if delta:
                        parts.append(delta)
                        self.post_message(MentionChunk(asst, delta))
                elif kind == "final":
                    final_text = str(frame.get("text") or "")
                elif kind == "error":
                    ok = False
                    error_text = str(frame.get("text") or "unknown")
                    break
            reply = final_text.strip() or "".join(parts).strip()
            return ok, reply, error_text

        ok, reply, error_text = asyncio.run(consume())
        if not ok:
            self.post_message(MentionDone(
                card, ok=False, output=error_text, reply="",
                peer_id=peer_id, prompt=prompt, started=started,
            ))
            return
        summary = (f"{reply[:60]}…" if len(reply) > 60 else reply) or "(empty reply)"
        self.post_message(MentionDone(
            card, ok=True, output=summary, reply=reply,
            peer_id=peer_id, prompt=prompt, started=started,
        ))

    def on_mention_chunk(self, message: MentionChunk) -> None:
        message.widget.append(message.text)

    def on_mention_done(self, message: MentionDone) -> None:
        message.card.finish(message.output, ok=message.ok)
        if not message.ok or not message.reply or not message.peer_id:
            return
        # Mirror cli.py:224-239 — session write makes the host watcher fire.
        from alpi.session import ToolLog
        user_text = f"@{message.peer_id} {message.prompt}"
        self.engine.session.messages.append({"role": "user", "content": user_text})
        self.engine.session.messages.append({"role": "assistant", "content": message.reply})
        try:
            self.engine.session.log_turn(
                user=user_text,
                assistant=message.reply,
                tools=[ToolLog(
                    at=message.started,
                    name="peer",
                    args={"peer_id": message.peer_id, "prompt": message.prompt},
                    result=message.reply,
                    ok=True,
                    duration_s=time.time() - message.started,
                )],
                started_at=message.started,
            )
            self.engine.save_session()
        except Exception:  # noqa: BLE001
            pass

    def _handle_slash(self, text: str) -> None:
        parts = text[1:].split(maxsplit=1)
        cmd = parts[0].lower() if parts else ""
        arg = parts[1].strip() if len(parts) > 1 else ""
        handlers: dict = {
            "help": lambda _a: self._show_panel(HelpPanel()),
            "memory": lambda _a: self._show_panel(MemoryPanel(self.home)),
            "tools": lambda _a: self._show_panel(ToolsPanel()),
            "mcps": lambda _a: self._show_panel(McpPanel(self.engine._mcp_clients)),
            "status": lambda _a: self._show_panel(StatusPanel(
                self.engine.session,
                home=self.engine.home,
                cfg_budget=self.engine.cfg.budget,
            )),
            "clear": lambda _a: self._cmd_clear(),
            "new": lambda _a: self._cmd_new(),
            "compact": lambda _a: self._cmd_compact(),
            "skills": lambda _a: self._cmd_skills(),
            "model": lambda _a: self._cmd_model(),
            "peers": lambda _a: self._show_panel(PeersPanel(self.home)),
            "diff": lambda a: self._show_panel(DiffPanel(self.home, since=a or "24h")),
            "attach": lambda a: self._cmd_attach(a),
            "attachments": lambda _a: self._cmd_attachments(),
            "clear-attachments": lambda _a: self._cmd_clear_attachments(),
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

    def _cmd_attach(self, arg: str) -> None:
        from pathlib import Path
        from alpi import attachments as att
        if not arg.strip():
            self._mount_message(ErrorLine("usage: /attach <path>"))
            return
        p = str(Path(arg.strip()).expanduser().resolve())
        try:
            validated = att.validate([{"path": p}])
        except att.AttachmentError as e:
            self._mount_message(ErrorLine(str(e)))
            return
        a = validated[0]
        self._pending_attachments.append({"path": str(a.path), "mime": a.mime, "name": a.name})
        self._mount_message(DimLine(
            f"📎 {a.name} ({a.mime}) · {len(self._pending_attachments)} pending — send a message to include"
        ))

    def _cmd_attachments(self) -> None:
        if not self._pending_attachments:
            self._mount_message(DimLine("no pending attachments"))
            return
        lines = "\n".join(f"  • {a['name']} ({a['mime']})" for a in self._pending_attachments)
        self._mount_message(DimLine(f"pending attachments:\n{lines}"))

    def _cmd_clear_attachments(self) -> None:
        n = len(self._pending_attachments)
        self._pending_attachments = []
        self._mount_message(DimLine(f"cleared {n} pending attachment(s)"))

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
        """Force the auto-compact pipeline NOW (manual recovery)."""
        if self._turn_in_progress():
            self._mount_message(DimLine("(turn in progress — wait for it to finish)"))
            return
        self._mount_message(DimLine("↺ compacting…"))
        self._run_compact_worker()

    @work(thread=True, exclusive=True, name="_run_compact")
    def _run_compact_worker(self) -> None:
        def sink(ev: AgentEvent) -> None:
            self.post_message(EngineEvent(ev))
        try:
            self.engine.compact_now(emit=sink)
            self.engine.save_session()
        except Exception as e:  # noqa: BLE001
            self.post_message(EngineEvent(AgentEvent(kind="error", text=f"compact failed: {e}")))
        self.call_from_thread(self._update_header)

    def _stop_thinking(self) -> None:
        if self._thinking is not None:
            self._thinking.stop()
            self._thinking = None

    def _drop_active_tool(self, tool_id: str) -> None:
        self._active_tools.pop(tool_id, None)

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
        # If the clicked widget is already detached from the DOM (e.g. the
        # click selected an OptionList row which swapped panels), leave the
        # new panel alone — otherwise the post-swap bubble dismisses it.
        if w is None or not getattr(w, "is_mounted", True):
            return
        while w is not None:
            if isinstance(w, FloatingPanel):
                return
            w = w.parent
        self._dismiss_panels()

    def _cmd_model(self) -> None:
        from alpi.tui.model_panel import ProviderPanel
        self.cfg = config.load(self.home)
        self._show_panel(ProviderPanel(self.cfg, self.home))

    def _update_header(self) -> None:
        from alpi import ledger

        hdr = self.query_one(AlpiHeader)
        s = self.engine.session
        kind, cap = ledger._budget(self.cfg.budget)
        used = 0.0
        if kind:
            snap = ledger.snapshot(self.home)
            prof = snap.get("profile", {})
            used = float(prof.get(kind, 0))
        hdr.update_usage(
            model=s.model,
            tokens=s.last_ctx_tokens,
            cost=s.cost_usd,
            ctx_window=self._resolve_ctx_window(s.model),
            budget_kind=kind,
            budget_used=used,
            budget_cap=cap,
        )

    def _resolve_ctx_window(self, model: str) -> int:
        from alpi import ctx_window

        return ctx_window.resolve(self.home, self.cfg, model)

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

    def _kick_resume(self, activity: "ResumeActivity | None" = None) -> None:
        """Launch the async resume worker after the activity bar paints."""
        self.run_worker(
            self._resume_last_session(activity), exclusive=True,
        )

    async def _resume_last_session(
        self, activity: "ResumeActivity | None" = None,
    ) -> None:
        """Rehydrate the last session and reveal its replay atomically.

        Three phases:
          1. Activity bar visible. Read the session JSON, build every
             replay widget IN MEMORY (no mounting yet).
          2. Drop the activity bar. Single ``chat.mount(*widgets)``
             call so Textual processes all of them in one Mount
             event → one layout pass → one repaint. No widget-by-
             widget streaming.
          3. Resolve tool cards (``finish``), scroll to end, refresh
             the header.
        """
        from alpi.cli import _continue_last_session

        def _drop_activity() -> None:
            if activity is not None:
                try:
                    activity.remove()
                except Exception:  # noqa: BLE001
                    pass

        resumed = _continue_last_session(self.engine, self.home)
        if not resumed:
            _drop_activity()
            return

        turns = self.engine.session.turns
        widgets: list = []
        cards_to_finish: list[tuple[ToolCard, object]] = []
        for t in turns:
            if t.user:
                widgets.append(UserMessage(t.user))
            for tl in t.tools:
                if tl.reasoning and self._show_reasoning():
                    widgets.append(ReasoningLine(tl.reasoning))
                card = ToolCard(
                    tool_id=f"replay-{id(tl)}", name=tl.name, args=tl.args,
                )
                widgets.append(card)
                cards_to_finish.append((card, tl))
            if t.assistant or getattr(t, "output_attachments", None):
                text = t.assistant
                if getattr(t, "output_attachments", None):
                    from alpi.attachments import render_output_attachments
                    listing = render_output_attachments(t.output_attachments)
                    text = "\n\n".join(x for x in (text, listing) if x)
                if text:
                    widgets.append(AssistantMessage(initial=text))
            elif t.user or t.tools:
                widgets.append(DimLine("⋯ interrupted — no final reply"))

        widgets.append(DimLine(
            f"✦ continuing session {self.engine.session.id} — "
            f"{len(turns)} turns loaded"
        ))

        chat = self.query_one("#chat", VerticalScroll)
        _drop_activity()
        await chat.mount(*widgets)

        for card, tl in cards_to_finish:
            card.finish(tl.result, ok=tl.ok, skip_duration=True)

        chat.scroll_end(animate=False)
        self._update_header()
