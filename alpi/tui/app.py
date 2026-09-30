from __future__ import annotations

import threading
import time
from pathlib import Path

from textual import events, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.message import Message

from alpi import config, home
from alpi.engine import AgentEvent, Engine
from alpi.tui import commands as slash
from alpi.tui.screens import (
    ApprovalPanel,
    ClarificationPanel,
    DiffPanel,
    FloatingPanel,
    HelpPanel,
    McpPanel,
    MemoryPanel,
    OutputsPanel,
    PeersPanel,
    PromptPanel,
    RunsPanel,
    SessionsPanel,
    SkillsPanel,
    StatusPanel,
    ToolsPanel,
)
from alpi.tui.turns import turn_parts
from alpi.tui.widgets import (
    AlpiTopBar,
    AskUserLine,
    AssistantMessage,
    ChatInput,
    CompletionPopup,
    DimLine,
    ErrorLine,
    ReasoningBlock,
    ResumeActivity,
    StatusLine,
    StepsGroup,
    ThinkingIndicator,
    ToolCard,
    UserMessage,
)


class EngineEvent(Message):
    def __init__(self, event: AgentEvent) -> None:
        super().__init__()
        self.event = event


class MentionChunk(Message):
    def __init__(self, widget: "AssistantMessage", text: str) -> None:
        super().__init__()
        self.widget = widget
        self.text = text


class MentionDone(Message):
    def __init__(
        self,
        card: "ToolCard",
        ok: bool,
        output: str,
        reply: str,
        peer_id: str = "",
        prompt: str = "",
        started: float = 0.0,
        bubble: "AssistantMessage | None" = None,
    ) -> None:
        super().__init__()
        self.card = card
        self.ok = ok
        self.output = output
        self.peer_id = peer_id
        self.prompt = prompt
        self.started = started
        self.reply = reply
        self.bubble = bubble


class _LiveTurn:
    def __init__(self) -> None:
        self.started = time.time()
        self.reasoned_s: float | None = None
        self.reasoning_buffer: list[str] = []
        self.reasoning: ReasoningBlock | None = None
        self.steps: StepsGroup | None = None
        self.ask_users: dict[str, dict] = {}


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
    ENABLE_COMMAND_PALETTE = False

    APPROVAL_TIMEOUT_S = 60.0
    CLARIFY_TIMEOUT_S = 300.0
    QUIT_WINDOW_S = 2.0
    ACTIVITY_POLL_S = 15.0

    BINDINGS = [
        Binding("ctrl+c", "ctrl_c", "Stop / quit", priority=True),
        Binding("escape", "escape", "Stop / close", priority=True, show=False),
        Binding("ctrl+l", "clear_chat", "Clear"),
        Binding("ctrl+y", "copy_last", "Copy last reply"),
        Binding("ctrl+o", "toggle_details", "Toggle details"),
    ]

    def __init__(self, home_dir: Path, continue_last: bool = False) -> None:
        self.home = home_dir
        self.continue_last = continue_last
        self.cfg = config.load(home_dir)
        super().__init__()
        # Child widgets read theme_variables in their own on_mount, which fires before ours.
        self._install_theme()
        self.engine = Engine(home=home_dir, cfg=self.cfg)

        self._current_assistant: AssistantMessage | None = None
        self._active_tools: dict[str, ToolCard] = {}
        self._thinking: ThinkingIndicator | None = None
        self._turn: _LiveTurn | None = None
        self._turn_worker = None
        self._pending_attachments: list[dict] = []
        self._prompts: list[PromptPanel] = []
        self._last_ctrl_c = 0.0
        self._remote_waiting = 0
        self._peer_ids: list[str] = []

    def compose(self) -> ComposeResult:
        from alpi import __version__ as alpi_version
        from alpi import updater as _updater
        try:
            from alpi.alp import peers as _peers_mod
            self._peer_ids = [p.id for p in _peers_mod.load(self.home)]
        except Exception:  # noqa: BLE001
            self._peer_ids = []
        yield AlpiTopBar(
            version=alpi_version,
            profile=self._profile_name(),
            path=str(self._effective_workspace()),
            workspace_set=self.cfg.workspace_path is not None,
            profile_size=home.profile_size_label(self.home),
            update_available=_updater.available_update() or "",
        )
        with VerticalScroll(id="chat"):
            pass
        chat_input = ChatInput(
            placeholder="Message alpi — / commands · @ peers · ctrl+j (or \\ then enter) for a new line",
            id="chat-input",
        )
        popup = CompletionPopup(chat_input, self._accept_completion)
        chat_input.completion = popup
        with Vertical(id="dock"):
            yield popup
            yield chat_input
            yield StatusLine()

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
        dark = str(tui.get("theme") or "dark").lower() != "light"
        theme = build_theme(accent=tui.get("accent"), dark=dark)
        self.register_theme(theme)
        self.theme = theme.name
        # Setting self.theme refreshes asynchronously, after child on_mount; force it now.
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

    @property
    def chat_input(self) -> ChatInput:
        return self.query_one(ChatInput)

    @property
    def status_line(self) -> StatusLine:
        return self.query_one(StatusLine)

    async def on_mount(self) -> None:
        self.chat_input.focus()
        self._update_header()
        self._maybe_warn_workspace()
        self._maybe_warn_model()

        self.query_one("#chat", VerticalScroll).anchor()

        if self.continue_last:
            activity = ResumeActivity()
            self.mount(activity, before=self.query_one("#chat"))
            self.call_after_refresh(self._kick_resume, activity)

        from alpi.tools import session_search
        session_search.set_current_session_id(self.engine.session.id)

        from alpi.tools._approval import set_prompt_callback
        set_prompt_callback(self._approval_prompt_blocking)
        from alpi.tools._clarification import set_handler as _set_clarify
        _set_clarify(self._clarification_prompt_blocking)

        self.set_interval(self.ACTIVITY_POLL_S, self._poll_activity)
        self.set_interval(1.0, self._refresh_hints)
        self._poll_activity()

    async def on_unmount(self) -> None:
        self._resolve_all_prompts()
        from alpi.tools._approval import set_prompt_callback
        set_prompt_callback(None)
        from alpi.tools._clarification import set_handler as _set_clarify
        _set_clarify(None)

    def _open_session(self, session_id: str) -> None:
        if self._turn_in_progress():
            self._mount_message(DimLine("(turn in progress — wait for it to finish)"))
            return
        if session_id == self.engine.session.id:
            return
        self.run_worker(self._resume_session_by_id(session_id), exclusive=True)

    async def _resume_session_by_id(self, session_id: str) -> None:
        from alpi.cli import _continue_specific_session

        self.cfg = config.load(self.home)
        self.engine.cfg = self.cfg
        self.engine.reset_session()
        self._turn = None
        chat = self.query_one("#chat", VerticalScroll)
        await chat.remove_children()
        if not _continue_specific_session(self.engine, self.home, session_id):
            chat.mount(ErrorLine(f"session not found: {session_id}"))
            return
        from alpi.tools import session_search
        session_search.set_current_session_id(self.engine.session.id)
        await self._replay_session_turns()

    def _await_prompt(self, panel: PromptPanel, timeout_s: float, default: str, box: list[str], done: threading.Event) -> str:
        try:
            self.call_from_thread(self._enqueue_prompt, panel)
        except Exception:  # noqa: BLE001
            return default
        if not done.wait(timeout_s):
            try:
                self.call_from_thread(panel.expire)
            except Exception:  # noqa: BLE001
                return default
        return box[0]

    def _approval_prompt_blocking(self, command: str, pattern: str, severity, cwd: str | None = None) -> str:
        box: list[str] = ["deny"]
        done = threading.Event()
        sev_str = severity.value if hasattr(severity, "value") else str(severity)

        def _on_choice(choice: str) -> None:
            box[0] = choice or "deny"
            done.set()

        panel = ApprovalPanel(command, pattern, sev_str, _on_choice, cwd=cwd, timeout_s=self.APPROVAL_TIMEOUT_S)
        return self._await_prompt(panel, self.APPROVAL_TIMEOUT_S, "deny", box, done)

    def _clarification_prompt_blocking(
        self,
        question: str,
        choices: list[dict],
        allow_other: bool,
        multi: bool = False,
    ) -> str:
        from alpi.host.clarification import CANCEL_SENTINEL

        box: list[str] = [""]
        done = threading.Event()

        def _on_choice(choice: str) -> None:
            box[0] = choice or ""
            done.set()

        panel = ClarificationPanel(
            question, choices, bool(allow_other), bool(multi), _on_choice,
            timeout_s=self.CLARIFY_TIMEOUT_S, cancel_choice=CANCEL_SENTINEL,
        )
        return self._await_prompt(panel, self.CLARIFY_TIMEOUT_S, "", box, done)

    @property
    def pending_prompts(self) -> list[PromptPanel]:
        return list(self._prompts)

    def _enqueue_prompt(self, panel: PromptPanel) -> None:
        if panel.resolved:
            return
        panel.on_finished = self._prompt_finished
        self._prompts.append(panel)
        if len(self._prompts) == 1:
            self._mount_prompt(panel)
        else:
            self._retitle_head()
        self._update_header()

    def _mount_prompt(self, panel: PromptPanel) -> None:
        self._dismiss_panels()
        self._hide_completion()
        self.mount(panel)
        self.screen.set_focus(None)
        self._retitle_head()

    def _retitle_head(self) -> None:
        if not self._prompts:
            return
        head = self._prompts[0]
        base = head.panel_title.split("  (+", 1)[0]
        queued = len(self._prompts) - 1
        head.set_title(f"{base}  (+{queued} queued)" if queued else base)

    def _prompt_finished(self, panel: PromptPanel) -> None:
        was_head = bool(self._prompts) and self._prompts[0] is panel
        if panel.expired:
            self._mount_message(DimLine(f"({panel.expiry_note(shown=was_head)})"))
        if panel in self._prompts:
            self._prompts.remove(panel)
        if panel.is_mounted:
            panel.remove()
        if was_head and self._prompts:
            self._mount_prompt(self._prompts[0])
        elif not self._prompts:
            try:
                self.chat_input.focus()
            except Exception:  # noqa: BLE001
                pass
        else:
            self._retitle_head()
        self._update_header()

    def _resolve_all_prompts(self) -> None:
        for panel in list(self._prompts):
            try:
                panel.cancel()
            except Exception:  # noqa: BLE001
                self._prompts = [p for p in self._prompts if p is not panel]

    def on_chat_input_submitted(self, event: ChatInput.Submitted) -> None:
        raw = event.value
        text = raw.strip()
        self._hide_completion()
        if not text and not self._pending_attachments:
            return
        event.chat_input.value = ""
        event.chat_input.remember(raw.rstrip())
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
        if self._turn_in_progress():
            self._interrupt_current_turn()
        self._scroll_end()
        if text:
            self._mount_message(UserMessage(text))
        self._turn = _LiveTurn()
        self._show_thinking()
        self.call_after_refresh(self._kickoff_turn, text)

    def on_text_area_changed(self, event) -> None:
        if isinstance(event.text_area, ChatInput):
            if event.text_area.take_recalled():
                self._hide_completion()
            else:
                self._update_completion(event.text_area.text)
            self._refresh_hints()

    def _completion_items(self, text: str) -> list[tuple[str, str, bool, bool]]:
        if not text or "\n" in text or " " in text:
            return []
        if text.startswith("/"):
            return [(f"/{c.name}", c.summary, c.takes_arg, c.requires_arg) for c in slash.complete(text)]
        if text.startswith("@"):
            needle = text[1:].lower()
            return [(f"@{pid}", "ask this peer", True, True) for pid in self._peer_ids if pid.lower().startswith(needle)]
        return []

    def _update_completion(self, text: str) -> None:
        try:
            popup = self.query_one(CompletionPopup)
        except Exception:  # noqa: BLE001
            return
        items = self._completion_items(text)
        if items:
            popup.show(items)
        else:
            popup.hide()

    def _hide_completion(self) -> None:
        try:
            self.query_one(CompletionPopup).hide()
        except Exception:  # noqa: BLE001
            pass

    def _accept_completion(self, value: str, takes_arg: bool, requires_arg: bool, submit: bool) -> None:
        inp = self.chat_input
        if submit and not requires_arg:
            inp.value = ""
            inp.remember(value)
            self._handle_slash(value)
            return
        inp.value = f"{value} "
        self._hide_completion()

    def _prefill_input(self, text: str) -> None:
        inp = self.chat_input
        inp.value = text
        inp.focus()

    def _kickoff_turn(self, text: str) -> None:
        attachments = self._pending_attachments or None
        self._pending_attachments = []
        self._turn_worker = self._run_turn(text, attachments)

    def _turn_in_progress(self) -> bool:
        from textual.worker import WorkerState
        w = self._turn_worker
        return w is not None and w.state in (WorkerState.PENDING, WorkerState.RUNNING)

    def _interrupt_current_turn(self) -> None:
        self._resolve_all_prompts()
        self.engine.request_interrupt("tui-stop")
        self._stop_thinking()
        self._mount_message(DimLine("↯ interrupted"))
        for tid, card in list(self._active_tools.items()):
            card.finish("[interrupted]", ok=False)
            self._active_tools.pop(tid, None)
            if self._turn is not None and self._turn.steps is not None:
                self._turn.steps.card_finished(card)
        self._refresh_hints()

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
        try:
            self.call_from_thread(self._update_header)
        except Exception:  # noqa: BLE001
            pass
        try:
            self.engine.save_session()
        except Exception:
            pass

    def on_engine_event(self, message: EngineEvent) -> None:
        ev = message.event
        kind = ev.kind
        if kind == "reasoning_delta":
            if self._turn is not None and self._show_reasoning():
                self._turn.reasoning_buffer.append(ev.text)
            self._show_thinking()
            return
        if kind == "model_state":
            if self._thinking is not None:
                self._thinking.set_label("Preparing a step…")
            return
        if kind in ("assistant_delta", "tool_start", "error", "done", "interrupted"):
            self._stop_thinking()
        if kind in ("assistant_delta", "tool_start", "done", "interrupted", "error"):
            self._flush_reasoning()
        if kind == "assistant_delta":
            self._on_assistant_delta(ev.text)
        elif kind == "assistant_done":
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
        elif kind == "tool_start":
            self._on_tool_start(ev)
        elif kind == "tool_state":
            self._on_tool_state(ev)
        elif kind == "tool_end":
            self._on_tool_end(ev)
        elif kind in ("done", "interrupted"):
            self._current_assistant = None
            self._refresh_hints()
        elif kind == "error":
            self._mount_message(ErrorLine(ev.text))
        elif kind == "usage":
            self._update_header()
        elif kind == "routing":
            self._mount_message(DimLine(f"⇢ {ev.text}"))
        elif kind == "auto_compact":
            self._mount_message(DimLine(f"↺ {ev.text}"))
            self._update_header()

    def _mark_reasoned(self) -> None:
        turn = self._turn
        if turn is not None and turn.reasoned_s is None:
            turn.reasoned_s = max(0.0, time.time() - turn.started)
            if turn.reasoning is not None:
                turn.reasoning.set_seconds(turn.reasoned_s)

    def _add_reasoning(self, text: str) -> None:
        turn = self._turn
        text = (text or "").strip()
        if turn is None or not text or not self._show_reasoning():
            return
        if turn.reasoning is None:
            turn.reasoning = ReasoningBlock(text, seconds=turn.reasoned_s)
            chat = self.query_one("#chat", VerticalScroll)
            if turn.steps is not None and turn.steps.is_attached:
                chat.mount(turn.reasoning, before=turn.steps)
            else:
                chat.mount(turn.reasoning)
        else:
            turn.reasoning.append(text)

    def _flush_reasoning(self) -> None:
        turn = self._turn
        if turn is None or not turn.reasoning_buffer:
            return
        text = "".join(turn.reasoning_buffer)
        turn.reasoning_buffer = []
        self._add_reasoning(text)

    def _on_assistant_delta(self, delta: str) -> None:
        if not delta:
            return
        self._mark_reasoned()
        if self._current_assistant is None:
            self._current_assistant = AssistantMessage()
            self._mount_message(self._current_assistant)
        self._current_assistant.append(delta)

    def _on_tool_start(self, ev: AgentEvent) -> None:
        self._mark_reasoned()
        if self._current_assistant is not None:
            preamble = (self._current_assistant.text or "").strip()
            self._current_assistant.remove()
            self._current_assistant = None
            self._add_reasoning(preamble)
        if self._turn is None:
            self._turn = _LiveTurn()
        if ev.name == "ask_user":
            self._turn.ask_users[ev.tool_id] = dict(ev.args or {})
            return
        card = ToolCard(tool_id=ev.tool_id, name=ev.name, args=ev.args)
        self._active_tools[ev.tool_id] = card
        steps = self._turn.steps
        if steps is None or not steps.is_attached:
            self._turn.steps = StepsGroup([card])
            self._mount_message(self._turn.steps)
        else:
            steps.add(card)

    def _show_reasoning(self) -> bool:
        return bool((self.cfg.tui or {}).get("show_reasoning", True))

    def _on_tool_state(self, ev: AgentEvent) -> None:
        card = self._active_tools.get(ev.tool_id)
        if card is not None:
            card.set_state(ev.text, is_error=not ev.ok)

    def _on_tool_end(self, ev: AgentEvent) -> None:
        turn = self._turn
        if turn is not None and ev.tool_id in turn.ask_users:
            args = turn.ask_users.pop(ev.tool_id)
            answer = (ev.output or "").strip()
            if answer:
                self._mount_message(AskUserLine(str(args.get("question") or ""), answer))
        card = self._active_tools.pop(ev.tool_id, None)
        if card is not None:
            card.finish(ev.output, ev.ok)
            if turn is not None and turn.steps is not None:
                turn.steps.card_finished(card)
        if not self._active_tools and self._turn_in_progress():
            self._show_thinking()

    def _handle_mention(self, text: str, parsed=None) -> None:
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
            final_payload: dict = {}
            async for frame in alp_mention.execute_stream(
                self.home, peer_id, prompt, source_session=self.engine.session.id,
            ):
                kind = frame.get("kind")
                if kind == "chunk":
                    delta = str(frame.get("text") or "")
                    if delta:
                        parts.append(delta)
                        self.post_message(MentionChunk(asst, delta))
                elif kind == "final":
                    final_payload = frame
                elif kind == "error":
                    ok = False
                    error_text = str(frame.get("text") or "unknown")
                    break
            reply = alp_mention.reply_text(peer_id, final_payload, parts)
            return ok, reply, error_text

        ok, reply, error_text = asyncio.run(consume())
        if not ok:
            self.post_message(MentionDone(
                card, ok=False, output=error_text, reply="",
                peer_id=peer_id, prompt=prompt, started=started, bubble=asst,
            ))
            return
        summary = (f"{reply[:60]}…" if len(reply) > 60 else reply) or "(empty reply)"
        self.post_message(MentionDone(
            card, ok=True, output=summary, reply=reply,
            peer_id=peer_id, prompt=prompt, started=started, bubble=asst,
        ))

    def on_mention_chunk(self, message: MentionChunk) -> None:
        message.widget.append(message.text)

    def on_mention_done(self, message: MentionDone) -> None:
        message.card.finish(message.output, ok=message.ok)
        if message.ok and message.reply and message.bubble is not None:
            message.bubble.replace(message.reply)
        if not message.ok or not message.reply or not message.peer_id:
            return
        # Mirror cli.py's once-path: the session write is what makes the host watcher fire.
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
        name, arg = slash.parse(text)
        cmd = slash.lookup(name)
        if cmd is None:
            self._mount_message(ErrorLine(f"unknown command: /{name} — /help lists them"))
            return
        getattr(self, cmd.method)(arg)

    def _cmd_help(self, _arg: str = "") -> None:
        self._show_panel(HelpPanel())

    def _cmd_memory(self, _arg: str = "") -> None:
        self._show_panel(MemoryPanel(self.home))

    def _cmd_tools(self, _arg: str = "") -> None:
        self._show_panel(ToolsPanel())

    def _cmd_mcps(self, _arg: str = "") -> None:
        self._show_panel(McpPanel(self.engine._mcp_clients))

    def _cmd_status(self, _arg: str = "") -> None:
        self._show_panel(StatusPanel(
            self.engine.session, home=self.engine.home, cfg_budget=self.engine.cfg.budget,
        ))

    def _cmd_skills(self, _arg: str = "") -> None:
        self._show_panel(SkillsPanel(self.home))

    def _cmd_peers(self, _arg: str = "") -> None:
        self._show_panel(PeersPanel(self.home))

    def _cmd_sessions(self, _arg: str = "") -> None:
        self._show_panel(SessionsPanel(self.home, current_id=self.engine.session.id))

    def _cmd_outputs(self, _arg: str = "") -> None:
        self._show_panel(OutputsPanel(self.home))

    def _cmd_runs(self, _arg: str = "") -> None:
        self._show_panel(RunsPanel(self.home))

    def _cmd_diff(self, arg: str = "") -> None:
        self._show_panel(DiffPanel(self.home, since=arg or "24h"))

    def _cmd_activity(self, _arg: str = "") -> None:
        from alpi.tui.activity import ActivityPanel
        self._show_panel(ActivityPanel())

    def _cmd_quit(self, _arg: str = "") -> None:
        self.action_quit()

    def _review_remote(self, item: dict) -> None:
        from alpi.tui.activity import open_review

        async def _open() -> None:
            result = await open_review(self, item)
            if isinstance(result, str):
                self._activity_note(result)
                return
            self._show_panel(result)

        self.run_worker(_open(), group="activity-review")

    def _activity_note(self, text: str) -> None:
        self._mount_message(DimLine(f"(activity: {text})"))
        self._poll_activity()

    def _poll_activity(self) -> None:
        from alpi.tui import host_client
        if not host_client.daemon_present():
            if self._remote_waiting:
                self._remote_waiting = 0
                self._update_header()
            return

        async def _poll() -> None:
            try:
                data = await host_client.acall("host.activity.list", timeout=1.5)
                count = len(data.get("needs_you") or []) if isinstance(data, dict) else 0
            except Exception:  # noqa: BLE001
                count = 0
            if count != self._remote_waiting:
                self._remote_waiting = count
                self._update_header()

        self.run_worker(_poll(), exclusive=True, group="activity-poll")

    def _busy(self) -> bool:
        if self._turn_in_progress():
            self._mount_message(DimLine("(turn in progress — esc stops it first)"))
            return True
        return False

    def _fresh_session(self, note: str) -> None:
        from alpi.tools import session_search

        # reset_session instead of filtering messages in place: a mid-history rewrite would bust the prefix cache.
        self.engine.reset_session()
        session_search.set_current_session_id(self.engine.session.id)
        self._turn = None
        chat = self.query_one("#chat", VerticalScroll)
        chat.remove_children()
        chat.mount(DimLine(note.format(id=self.engine.session.id)))
        self._update_header()

    def _cmd_clear(self, _arg: str = "") -> None:
        if self._busy():
            return
        self._fresh_session("(transcript cleared — new session {id})")

    def _cmd_attach(self, arg: str) -> None:
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

    def _cmd_attachments(self, _arg: str = "") -> None:
        if not self._pending_attachments:
            self._mount_message(DimLine("no pending attachments"))
            return
        lines = "\n".join(f"  • {a['name']} ({a['mime']})" for a in self._pending_attachments)
        self._mount_message(DimLine(f"pending attachments:\n{lines}"))

    def _cmd_clear_attachments(self, _arg: str = "") -> None:
        n = len(self._pending_attachments)
        self._pending_attachments = []
        self._mount_message(DimLine(f"cleared {n} pending attachment(s)"))

    def _cmd_new(self, _arg: str = "") -> None:
        if self._busy():
            return
        # Reload cfg from disk so a session-only /model switch is forgotten.
        self.cfg = config.load(self.home)
        self.engine.cfg = self.cfg
        self._fresh_session("(new session — {id})")

    def _cmd_compact(self, _arg: str = "") -> None:
        if self._busy():
            return
        self._mount_message(DimLine("↺ compacting…"))
        self._run_compact_worker()

    def _cmd_model(self, _arg: str = "") -> None:
        from alpi.tui.model_panel import ProviderPanel
        self.cfg = config.load(self.home)
        self._show_panel(ProviderPanel(self.cfg, self.home))

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

    def _show_thinking(self) -> None:
        if self._thinking is not None:
            if self._thinking.label != "Thinking…":
                self._thinking.set_label("Thinking…")
            return
        self._thinking = ThinkingIndicator()
        self._mount_message(self._thinking)

    def _stop_thinking(self) -> None:
        if self._thinking is not None:
            self._thinking.stop()
            self._thinking = None

    def _show_panel(self, panel: FloatingPanel) -> None:
        if isinstance(panel, PromptPanel) and panel.blocking:
            self._enqueue_prompt(panel)
            return
        if self._prompts:
            self._mount_message(DimLine("(answer the open prompt first — esc denies it)"))
            return
        self._dismiss_panels()
        self._hide_completion()
        self.mount(panel)
        self.screen.set_focus(None)
        self._refresh_hints()

    def _open_panels(self) -> list[FloatingPanel]:
        return [p for p in self.query(FloatingPanel) if not (isinstance(p, PromptPanel) and p.blocking)]

    def _dismiss_panels(self) -> bool:
        open_panels = self._open_panels()
        for p in open_panels:
            p.remove()
        if open_panels and not self._prompts:
            self.chat_input.focus()
        self._refresh_hints()
        return bool(open_panels)

    def action_dismiss_panel(self) -> None:
        self.action_escape()

    def action_escape(self) -> None:
        popup = self.query_one(CompletionPopup)
        if popup.active:
            popup.hide()
            return
        if self._prompts:
            self._prompts[0].cancel()
            return
        if self._dismiss_panels():
            return
        if self._turn_in_progress():
            self._interrupt_current_turn()

    def action_ctrl_c(self) -> None:
        if self._prompts or self._turn_in_progress():
            self._resolve_all_prompts()
            if self._turn_in_progress():
                self._interrupt_current_turn()
            self._last_ctrl_c = 0.0
            return
        now = time.monotonic()
        if self._last_ctrl_c and now - self._last_ctrl_c <= self.QUIT_WINDOW_S:
            self.action_quit()
            return
        self._last_ctrl_c = now
        self._refresh_hints()

    def action_toggle_details(self) -> None:
        chat = self.query_one("#chat", VerticalScroll)
        targets: list = []
        for child in reversed(list(chat.children)):
            if isinstance(child, (ReasoningBlock, StepsGroup)):
                targets.append(child)
            elif targets and isinstance(child, UserMessage):
                break
        if not targets:
            return
        expand = not any(t.expanded for t in targets)
        for t in targets:
            t.set_expanded(expand)

    def on_click(self, event: events.Click) -> None:
        if self._prompts:
            return
        panels = self._open_panels()
        if not panels:
            return
        w = event.widget
        # A click that already swapped panels arrives with a detached widget; leave the new panel alone.
        if w is None or not getattr(w, "is_mounted", True):
            return
        while w is not None:
            if isinstance(w, FloatingPanel):
                return
            w = w.parent
        self._dismiss_panels()

    def key_hints(self) -> str:
        if self._prompts:
            verb = self._prompts[0].cancel_verb
            return f"↑↓ choose · enter confirm · esc {verb}"
        if self._last_ctrl_c and time.monotonic() - self._last_ctrl_c <= self.QUIT_WINDOW_S:
            return "press ctrl+c again to quit"
        try:
            if self._open_panels():
                return "↑↓ move · enter select · esc close"
            popup = self.query_one(CompletionPopup)
            text = self.chat_input.text
        except Exception:  # noqa: BLE001
            return ""
        if popup.active:
            return "↑↓ move · tab complete · enter run · esc close"
        if self._turn_in_progress():
            return "esc stop · ctrl+o details"
        if text:
            return "enter send · ctrl+j new line"
        return "/ commands · ↑ history · ctrl+c twice quits"

    def _refresh_hints(self) -> None:
        if self._last_ctrl_c and time.monotonic() - self._last_ctrl_c > self.QUIT_WINDOW_S:
            self._last_ctrl_c = 0.0
        try:
            self.status_line.set_state(hints=self.key_hints())
        except Exception:  # noqa: BLE001
            pass

    def _unread_count(self) -> int:
        from alpi import outputs as outputs_mod
        try:
            return len(outputs_mod.list_outputs(self.home, status="unread", limit=0))
        except Exception:  # noqa: BLE001
            return 0

    def _sandbox_label(self) -> str:
        term = self.cfg.tools.terminal
        if not term.sandbox:
            return ""
        return "sandbox · offline" if not term.allow_network else "sandbox"

    def _update_header(self) -> None:
        from alpi import ledger

        try:
            line = self.status_line
        except Exception:  # noqa: BLE001
            return
        s = self.engine.session
        kind, cap = ledger._budget(self.cfg.budget)
        used = 0.0
        if kind:
            snap = ledger.snapshot(self.home)
            prof = snap.get("profile", {})
            used = float(prof.get(kind, 0))
        line.set_state(
            model=s.model or "",
            tokens=s.last_ctx_tokens,
            cost=s.cost_usd,
            ctx_window=self._resolve_ctx_window(s.model),
            budget_kind=kind,
            budget_used=used,
            budget_cap=cap,
            sandbox=self._sandbox_label(),
            unread=self._unread_count(),
            waiting=len(self._prompts) + self._remote_waiting,
            hints=self.key_hints(),
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
        self._resolve_all_prompts()
        if self._turn_in_progress():
            try:
                self.engine.request_interrupt("tui-quit")
            except Exception:  # noqa: BLE001
                pass
        # cancel_all keeps a mid-turn quit from leaving the terminal in mouse-reporting mode.
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
        self.run_worker(
            self._resume_last_session(activity), exclusive=True,
        )

    async def _resume_last_session(
        self, activity: "ResumeActivity | None" = None,
    ) -> None:
        from alpi.cli import _continue_last_session

        resumed = _continue_last_session(self.engine, self.home)
        if activity is not None:
            try:
                activity.remove()
            except Exception:  # noqa: BLE001
                pass
        if resumed:
            await self._replay_session_turns()

    def replay_widgets(self, turns: list) -> list:
        widgets: list = []
        for t in turns:
            if t.user:
                widgets.append(UserMessage(t.user))
            parts = turn_parts(t)
            if parts["reasoning"] and self._show_reasoning():
                widgets.append(ReasoningBlock(parts["reasoning"], seconds=parts["reasoned_s"]))
            if parts["tools"]:
                cards = []
                for i, tl in enumerate(parts["tools"]):
                    card = ToolCard(tool_id=f"replay-{id(t)}-{i}", name=tl.name, args=tl.args, started=tl.at)
                    card.finish(tl.result, ok=tl.ok, duration_s=tl.duration_s)
                    cards.append(card)
                group = StepsGroup(cards)
                if any(not c.ok for c in cards):
                    group.add_class("-expanded")
                widgets.append(group)
            for a in parts["ask_users"]:
                widgets.append(AskUserLine(a["question"], a["result"]))
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
        return widgets

    async def _replay_session_turns(self) -> None:
        turns = self.engine.session.turns
        widgets = self.replay_widgets(turns)
        widgets.append(DimLine(
            f"✦ continuing session {self.engine.session.id} — "
            f"{len(turns)} turns loaded"
        ))
        chat = self.query_one("#chat", VerticalScroll)
        await chat.mount(*widgets)
        chat.scroll_end(animate=False)
        self._update_header()
