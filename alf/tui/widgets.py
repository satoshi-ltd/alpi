"""Message widgets used in the chat view."""

from __future__ import annotations

import time
from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widget import Widget
from textual.widgets import Markdown, Static


# User & assistant messages

class UserMessage(Static):
    """User input row, rendered with a green chevron."""

    def __init__(self, text: str) -> None:
        super().__init__(Text.assemble(("› ", "bold"), (text, "bold")))


class AssistantMessage(Widget):
    """Markdown-rendered assistant response. Supports incremental streaming.

    Accepts an ``initial`` string so callers can mount a widget with its
    final text already set (used during session resume). Streaming callers
    create it with no args and then call :meth:`append` repeatedly.

    Markdown is expensive to re-parse; calling ``_md.update()`` on every
    token stalls the event loop and makes the whole UI jumpy. We batch
    appends and flush at most ``_FLUSH_EVERY_S`` seconds — the buffer
    keeps accumulating, the widget repaints at a sustainable cadence.
    """

    _FLUSH_EVERY_S = 0.08  # ~12 Hz max repaints

    def __init__(self, initial: str = "") -> None:
        super().__init__()
        self._md: Markdown | None = None
        self._buffer: str = initial
        self._last_flushed: str = initial
        self._flush_scheduled: bool = False

    def compose(self) -> ComposeResult:
        self._md = Markdown(self._buffer)
        yield self._md

    def append(self, delta: str) -> None:
        if not delta:
            return
        self._buffer += delta
        self._schedule_flush()

    def _schedule_flush(self) -> None:
        if self._flush_scheduled or self._md is None:
            return
        self._flush_scheduled = True
        self.set_timer(self._FLUSH_EVERY_S, self._flush)

    def _flush(self) -> None:
        self._flush_scheduled = False
        if self._md is None:
            return
        if self._buffer == self._last_flushed:
            return
        self._md.update(self._buffer)
        self._last_flushed = self._buffer

    @property
    def text(self) -> str:
        return self._buffer


class ErrorLine(Static):
    def __init__(self, text: str) -> None:
        super().__init__(Text.assemble(("✗ ", "bold red"), (text, "red")))


class DimLine(Static):
    def __init__(self, text: str) -> None:
        super().__init__(Text(text, style="dim"))


class ReasoningLine(Static):
    MAX_CHARS = 400

    def __init__(self, text: str) -> None:
        from rich.markup import escape
        compact = " ".join(text.split())
        if len(compact) > self.MAX_CHARS:
            compact = compact[: self.MAX_CHARS - 1] + "…"
        super().__init__(Text.from_markup(f"[dim]» {escape(compact)}[/dim]"))


# Tool card — spinner while running, result when done

_SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


def _fmt_cost(cost: float) -> str:
    if cost <= 0:
        return "$0"
    if cost < 0.01:
        return f"${cost:.4f}"       # $0.0003 — precision for micro-costs
    if cost < 1:
        return f"${cost:.3f}"       # $0.234 — mid range
    return f"${cost:.2f}"           # $12.34 — dollars


# Tools that represent "alf is learning something" — rendered with the
# accent color so the user can see at a glance when memory/skills change.
LEARNING_TOOLS = {"memory", "skill"}


# Thinking indicator — shown immediately after a user message and removed
# on the first assistant_delta or tool_start. Gives feedback while the
# LLM is receiving the prompt and deciding what to do.

class ThinkingIndicator(Static):
    _REASONING_TAIL_CHARS = 80

    def __init__(self, accent: str = "") -> None:
        super().__init__("")
        self.started = time.time()
        self.accent = accent
        self._timer = None
        self._reasoning: str = ""

    def on_mount(self) -> None:
        self._tick()
        self._timer = self.set_interval(1 / 6, self._tick)

    def append_reasoning(self, delta: str) -> None:
        if not delta:
            return
        self._reasoning += delta

    def _tick(self) -> None:
        from rich.markup import escape
        from alf.tui.formatting import fmt_duration
        frame = _SPINNER_FRAMES[int(time.time() * 6) % len(_SPINNER_FRAMES)]
        elapsed = fmt_duration(time.time() - self.started)
        spinner_markup = f"[{self.accent}]{frame}[/{self.accent}]" if self.accent else frame
        if self._reasoning:
            compact = " ".join(self._reasoning.split())
            tail = compact[-self._REASONING_TAIL_CHARS:]
            if len(compact) > self._REASONING_TAIL_CHARS:
                tail = "…" + tail
            body = f"[dim]{escape(tail)}[/dim]  [dim]{elapsed}[/dim]"
        else:
            body = f"[dim] thinking…  {elapsed}[/dim]"
        self.update(Text.from_markup(f"{spinner_markup} {body}"))

    def stop(self) -> None:
        if self._timer is not None:
            try:
                self._timer.stop()
            except Exception:
                pass
            self._timer = None
        try:
            self.remove()
        except Exception:
            pass


class ToolCard(Widget):
    """Single-line live tool invocation indicator.

    Shows: ◆ tool_name   args   ⠋   elapsed
    When the tool completes, switches to: ◆ tool_name   args   →   result   dur
    """

    TOOL_COL_WIDTH = 14

    def __init__(self, tool_id: str, name: str, args: dict,
                 accent: str = "") -> None:
        super().__init__()
        self.tool_id = tool_id
        self.tool_name = name
        self.args = args
        self.accent = accent
        self.started = time.time()
        self._done = False
        self._result_markup: str = ""
        self._elapsed_final: float | None = None
        self._timer = None
        self._state_label: str = ""
        self._state_is_error: bool = False
        self.add_class("-running")

    def on_mount(self) -> None:
        # Re-render 6×/s — smoother spinner + visible ms ticking, still
        # cheap enough that many live cards don't saturate the event loop.
        self._timer = self.set_interval(1 / 6, self._tick)

    def _tick(self) -> None:
        if not self._done:
            self.refresh()

    def set_state(self, label: str, is_error: bool = False) -> None:
        self._state_label = label or ""
        self._state_is_error = bool(is_error)
        self.refresh()

    def finish(self, output: str, ok: bool, *, skip_duration: bool = False) -> None:
        self._done = True
        # Set to None when we don't have a real duration (e.g. replaying a
        # saved session on --continue). render() hides the duration if None.
        self._elapsed_final = None if skip_duration else (time.time() - self.started)
        from rich.markup import escape
        from alf.tui.formatting import result_hint, truncate
        if ok:
            self._result_markup = result_hint(self.tool_name, output)
        else:
            # Strip the "ERROR:" prefix the engine adds — the red ✗ already says it.
            msg = output.removeprefix("ERROR:").strip() or "failed"
            self._result_markup = f"[red]✗ {escape(truncate(msg, 80))}[/red]"
        if self._timer is not None:
            try:
                self._timer.stop()
            except Exception:
                pass
        self.remove_class("-running")
        self.add_class("-error" if not ok else "-done")
        self.refresh()

    def render(self):
        from alf.tui.formatting import arg_hint, fmt_duration
        arg = arg_hint(self.tool_name, self.args)
        name_col = self.tool_name.ljust(self.TOOL_COL_WIDTH)
        is_learning = self.tool_name in LEARNING_TOOLS and bool(self.accent)
        learn_color = self.accent if is_learning else ""
        text = Text()
        if self._done:
            if "-error" in self.classes:
                diamond_style = "red"
            elif is_learning:
                diamond_style = learn_color
            elif self.accent:
                diamond_style = self.accent
            else:
                diamond_style = "cyan"
            name_style = f"bold {learn_color}" if is_learning else "bold"
            text.append("◆ ", style=diamond_style)
            text.append(name_col, style=name_style)
            text.append(" ")
            text.append(arg, style="dim")
            text.append("  ")
            text.append("→", style="dim")
            text.append("  ")
            text.append_text(Text.from_markup(self._result_markup))
            # Only show duration when we actually measured it.
            if self._elapsed_final is not None and self._elapsed_final > 0:
                text.append(f"   {fmt_duration(self._elapsed_final)}", style="dim")
        else:
            elapsed = time.time() - self.started
            # Spinner frame advances at the refresh rate (6 Hz) — avoids
            # aliasing against the tick interval.
            frame = _SPINNER_FRAMES[int(time.time() * 6) % len(_SPINNER_FRAMES)]
            if self._state_is_error:
                icon_style = "red"
            elif is_learning:
                icon_style = learn_color
            elif self.accent:
                icon_style = self.accent
            else:
                icon_style = "cyan"
            if self._state_is_error:
                spinner_style = "red"
            elif self.accent:
                spinner_style = self.accent
            else:
                spinner_style = "yellow"
            label_style = "red" if self._state_is_error else "dim"
            name_style = f"bold {learn_color}" if is_learning else "bold"

            text.append("◆ ", style=icon_style)
            text.append(name_col, style=name_style)
            text.append(" ")
            # While running, show the live state label instead of args.
            live = self._state_label or arg
            text.append(live, style=label_style)
            text.append("  ")
            text.append(frame, style=spinner_style)
            text.append("  ")
            text.append(fmt_duration(elapsed), style="dim")
        return text


# Static top header — identity line (version / profile / cwd)

class AlfTopBar(Static):
    """Static identity line: version · profile · workspace.

    Always shows the ``workspace`` label — never falls back to cwd. When
    no workspace is configured the slot reads ``not set`` in warning
    colour so the user knows to run ``/workspace <path>``.
    """

    def __init__(self, version: str, profile: str, path: str,
                 workspace_set: bool) -> None:
        from rich.markup import escape
        if workspace_set:
            short = str(path).replace(str(Path.home()), "~")
            workspace_txt = escape(short)
        else:
            workspace_txt = "[red]not set[/red]"
        markup = (
            f"[b]alf[/b] [dim]{escape(version)}[/dim]  "
            f"[dim]│[/dim]  "
            f"[dim]profile[/dim] {escape(profile)}  "
            f"[dim]│[/dim]  "
            f"[dim]workspace[/dim] {workspace_txt}"
        )
        super().__init__(Text.from_markup(markup))


# Status bar — single line above the input

class AlfHeader(Static):
    """Live status line: model · ctx · %context · cost."""

    def __init__(self) -> None:
        super().__init__("")
        self._model: str = ""
        self._tokens: int = 0
        self._cost: float = 0.0
        self._ctx_window: int = 200_000
        self._accent: str = "yellow"

    def on_mount(self) -> None:
        self._refresh()

    def update_usage(self, model: str, tokens: int, cost: float,
                     ctx_window: int = 200_000, accent: str = "") -> None:
        self._model = model
        self._tokens = tokens
        self._cost = cost
        self._ctx_window = ctx_window
        if accent:
            self._accent = accent
        self._refresh()

    def _refresh(self) -> None:
        from alf.tui.formatting import fmt_count, bar_10
        pct = int(self._tokens / self._ctx_window * 100) if self._ctx_window else 0
        model_short = self._model.split("/")[-1] if self._model else "—"
        bar = bar_10(self._tokens, self._ctx_window)
        accent = self._accent
        # Bar color shifts with context fill: accent → amber at 60% → red at 80%.
        if pct >= 80:
            bar_color = "red"
        elif pct >= 60:
            bar_color = "yellow"
        else:
            bar_color = accent
        markup = (
            f"[{accent}]◆[/{accent}] [b {accent}]{model_short}[/b {accent}]  "
            f"[dim]│[/dim]  "
            f"[dim]ctx[/dim] {fmt_count(self._tokens)}/{fmt_count(self._ctx_window)}  "
            f"[{bar_color}]{bar}[/{bar_color}] [dim]{pct}%[/dim]  "
            f"[dim]│[/dim]  "
            f"[dim]{_fmt_cost(self._cost)}[/dim]"
        )
        self.update(Text.from_markup(markup))
