"""Main Textual App for alf."""

from __future__ import annotations

from pathlib import Path

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.message import Message
from textual.widgets import Input

from alf import config, home, memory
from alf.engine import AgentEvent, Engine
from alf.tui.screens import CostScreen, HelpScreen, MemoryScreen, ToolsScreen
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
        # Linux — try Wayland first, then X11.
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
    ]

    def __init__(self, home_dir: Path, continue_last: bool = False) -> None:
        # Load cfg BEFORE super().__init__() — Textual calls
        # get_css_variables() from its constructor, and that reads self.cfg.
        self.home = home_dir
        self.continue_last = continue_last
        self.cfg = config.load(home_dir)
        super().__init__()
        self.engine = Engine(home=home_dir, cfg=self.cfg)

        self._current_assistant: AssistantMessage | None = None
        self._active_tools: dict[str, ToolCard] = {}
        self._thinking: ThinkingIndicator | None = None

    def get_css_variables(self) -> dict[str, str]:
        # Let the user override the accent color from config.yaml (tui.accent).
        variables = super().get_css_variables()
        accent = (self.cfg.tui or {}).get("accent") or ""
        if accent:
            variables["accent"] = accent
        return variables

    def compose(self) -> ComposeResult:
        from textual.suggester import SuggestFromList
        from alf import __version__ as alf_version
        slash_commands = [
            "/help", "/memory", "/tools", "/cost", "/clear", "/new",
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
            f"⚠ no workspace set — alf can touch everything under {short}. "
            f"Run /workspace <path> to narrow the scope."
        ))

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

        if self.continue_last:
            self._resume_last_session()

        # Let session_search exclude the currently-active session file.
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
        # If a turn is still running, ask the engine to stop at the next
        # check-point before starting a new one. The old worker will exit
        # on its own; we just flip the flag and mark visible tool cards as
        # interrupted so the UI doesn't look stuck.
        if self._turn_in_progress():
            self._interrupt_current_turn()
        self._mount_message(UserMessage(text))
        # Immediate activity feedback — removed as soon as the first
        # assistant_delta or tool_start arrives.
        self._thinking = ThinkingIndicator(accent=self._accent_color())
        self._mount_message(self._thinking)
        # Always jump to the bottom on new input — even if the user was
        # scrolled up reading history and their new message would otherwise
        # appear off-screen.
        self._scroll_end()
        self.call_after_refresh(self._scroll_end)
        # Defer the worker by one refresh cycle so the UserMessage paints
        # before the LLM round-trip starts.
        self.call_after_refresh(self._run_turn, text)

    def _turn_in_progress(self) -> bool:
        try:
            from textual.worker import WorkerState
        except Exception:
            return False
        for w in self.workers:
            if (getattr(w, "name", "") == "_run_turn"
                    and w.state == WorkerState.RUNNING):
                return True
        return False

    def _interrupt_current_turn(self) -> None:
        self.engine.request_interrupt()
        self._stop_thinking()
        self._mount_message(DimLine("↯ interrupted previous turn"))
        # Mark any live tool cards as cancelled — the engine will also emit
        # tool_end events but those arrive on the next event loop tick and
        # we want immediate visual feedback.
        for tid, card in list(self._active_tools.items()):
            try:
                card.finish("[interrupted]", ok=False)
            except Exception:
                pass
            self._active_tools.pop(tid, None)

    # Engine worker

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
        # Persist to disk after every turn, not only on clean exit.
        # Otherwise a crashed terminal / Cmd+W / power-off loses the whole
        # conversation and `session_search` never finds it next time.
        try:
            self.engine.save_session()
        except Exception:
            pass

    def on_engine_event(self, message: EngineEvent) -> None:
        ev = message.event
        # First real activity kills the "thinking" indicator. Explicit
        # kinds handled here so we don't race against intermediate kinds
        # like 'usage' (which can arrive before any visible output).
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
            # Do NOT clear _current_assistant here — tool_start may still
            # need to remove the interstitial reasoning widget. We clear it
            # when a tool starts (collapse reasoning) or when the turn ends.
            # But DO force a final flush so the last tokens aren't held by
            # the streaming throttle.
            if self._current_assistant is not None:
                try:
                    self._current_assistant._flush()  # noqa: SLF001
                except Exception:
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
            # The UI already showed "↯ interrupted previous turn" when the
            # new input arrived; nothing else to do here.
            self._current_assistant = None
        elif ev.kind == "error":
            self._mount_message(ErrorLine(ev.text))
        elif ev.kind == "usage":
            self._update_header()
        # 'user' and 'done' are informational only.

    def _on_assistant_delta(self, delta: str) -> None:
        if not delta:
            return
        first_delta = self._current_assistant is None
        if first_delta:
            self._current_assistant = AssistantMessage()
            self._mount_message(self._current_assistant)
        self._current_assistant.append(delta)
        # Don't force scroll on every token — the Markdown widget throttles
        # its repaints, and aggressive scrolls fight with the user if they
        # scrolled up to read something. Scroll on mount (via _mount_message)
        # and on natural widget growth, which Textual handles.
        if first_delta:
            self.call_after_refresh(self._scroll_end)

    def _on_tool_start(self, ev: AgentEvent) -> None:
        reasoning = ""
        if self._current_assistant is not None:
            reasoning = (self._current_assistant.text or "").strip()
            try:
                self._current_assistant.remove()
            except Exception:
                pass
            self._current_assistant = None
        if reasoning and self._show_reasoning():
            self._mount_message(ReasoningLine(reasoning))
        card = ToolCard(tool_id=ev.tool_id, name=ev.name, args=ev.args,
                        accent=self._accent_color())
        self._active_tools[ev.tool_id] = card
        self._mount_message(card)

    def _accent_color(self) -> str:
        return (self.cfg.tui or {}).get("accent") or ""

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
        self._scroll_end()

    def _handle_slash(self, text: str) -> None:
        parts = text[1:].split(maxsplit=1)
        cmd = parts[0].lower() if parts else ""
        arg = parts[1].strip() if len(parts) > 1 else ""
        handlers: dict = {
            "help": lambda _a: self.push_screen(HelpScreen()),
            "memory": lambda _a: self.push_screen(MemoryScreen(self.home)),
            "tools": lambda _a: self.push_screen(ToolsScreen()),
            "cost": lambda _a: self.push_screen(CostScreen(self.engine.session)),
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
        self.engine.reset_session()
        chat = self.query_one("#chat", VerticalScroll)
        chat.remove_children()
        chat.mount(DimLine(f"(new session — {self.engine.session.id})"))
        self._update_header()

    def _cmd_compact(self) -> None:
        # Mount a ToolCard so the user sees compact with the same visual
        # format as tool calls (spinner + elapsed + final summary line).
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
        # Estimate current ctx size (chars/4 is a rough but useful heuristic).
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
        # Show the compacted summary as a normal assistant message.
        msg = AssistantMessage()
        self._mount_message(msg)
        msg.append(f"**Compacted summary**\n\n{summary}")

    def _cmd_skills(self) -> None:
        from alf.tui.screens import SkillsScreen
        self.push_screen(SkillsScreen(self.home))

    def _cmd_workspace(self, arg: str) -> None:
        if not arg:
            suggested = self.cfg.workspace or str(self._effective_workspace())
            inp = self.query_one(Input)
            inp.value = f"/workspace {suggested}"
            # Cursor at end so the path is easy to edit.
            try:
                inp.action_end()
            except Exception:
                pass
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
        from alf import __version__ as alf_version
        try:
            old = self.query_one(AlfTopBar)
            old.remove()
        except Exception:
            pass
        self.mount(
            AlfTopBar(
                version=alf_version,
                profile=self._profile_name(),
                path=str(self._effective_workspace()),
                workspace_set=self.cfg.workspace_path is not None,
            ),
            before=self.query_one("#chat"),
        )

    def _cmd_model(self) -> None:
        # Native Textual flow — no suspend, no terminal juggling.
        from alf.tui.model_screen import ProviderScreen
        self.cfg = config.load(self.home)
        self.push_screen(ProviderScreen(self.cfg, self.home))

    def _update_header(self) -> None:
        hdr = self.query_one(AlfHeader)
        s = self.engine.session
        hdr.update_usage(
            model=s.model,
            tokens=s.last_ctx_tokens,  # current context window, not cumulative
            cost=s.cost_usd,
            accent=(self.cfg.tui or {}).get("accent") or "yellow",
        )

    def _mount_message(self, widget) -> None:
        chat = self.query_one("#chat", VerticalScroll)
        chat.mount(widget)
        # mount() is async AND Markdown widgets re-layout themselves after
        # their first render. We fire scroll at three stages to catch
        # every phase: immediately after the next refresh, ~80ms after
        # (first layout settled), and ~300ms after (Markdown tall-content
        # re-layout). Without this, long conversations can fail to follow
        # the new bottom even with force=True.
        self.call_after_refresh(self._scroll_end)
        self.set_timer(0.08, self._scroll_end)
        self.set_timer(0.3, self._scroll_end)

    def _scroll_end(self) -> None:
        try:
            chat = self.query_one("#chat", VerticalScroll)
            # Belt: use Textual's scroll_end with force when available.
            try:
                chat.scroll_end(animate=False, immediate=True, force=True)
            except TypeError:
                chat.scroll_end(animate=False, immediate=True)
            # Braces: raw scroll_y assignment. Some Textual versions don't
            # jump to the new bottom until max_scroll_y has been recomputed
            # after a child's async layout — this assignment takes effect
            # the next time layout runs.
            try:
                chat.scroll_y = chat.max_scroll_y
            except Exception:
                pass
        except Exception:
            pass

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
        # Always also try Textual's OSC-52 — harmless if terminal ignores it.
        try:
            self.copy_to_clipboard(last_text)
        except Exception:
            pass
        self._mount_message(
            DimLine(f"(copied {len(last_text):,} chars via {method})")
        )

    def action_quit(self) -> None:
        # Cancel any running workers so shutdown doesn't block on an
        # in-flight LLM call. Without this, a mid-turn Ctrl+C can leave
        # the terminal in mouse-reporting mode.
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

        accent = self._accent_color()
        for t in turns:
            if t.user:
                self._mount_message(UserMessage(t.user))
            for tl in t.tools:
                if tl.reasoning and self._show_reasoning():
                    self._mount_message(ReasoningLine(tl.reasoning))
                card = ToolCard(
                    tool_id=f"replay-{id(tl)}", name=tl.name,
                    args=tl.args, accent=accent,
                )
                self._mount_message(card)
                card.finish(tl.result, ok=tl.ok, skip_duration=True)
            if t.assistant:
                self._mount_message(AssistantMessage(initial=t.assistant))

        self._update_header()
        # Long transcripts need time for all Markdown widgets to finish
        # their layout before scroll_end lands at the true bottom.
        self.set_timer(0.15, self._scroll_end)
        self.set_timer(0.4, self._scroll_end)
