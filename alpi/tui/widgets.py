"""Message widgets used in the chat view."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widget import Widget
from textual.widgets import Input, Markdown, Static


class ChatInput(Input):
    # Textual's Input keeps only the first line on paste. Flatten
    # newlines to spaces so multi-line clipboard content reaches the
    # agent intact instead of being silently truncated. prevent_default
    # is required (not stop()) because Textual's MRO dispatch otherwise
    # also runs the base Input._on_paste after this one.
    def _on_paste(self, event: events.Paste) -> None:
        if event.text:
            text = event.text.replace("\r\n", "\n").replace("\r", "\n")
            text = text.replace("\n", " ")
            selection = self.selection
            if selection.is_empty:
                self.insert_text_at_cursor(text)
            else:
                self.replace(text, *selection)
        event.prevent_default()
        event.stop()


class UserMessage(Static):
    def __init__(self, text: str) -> None:
        super().__init__(Text.assemble(("› ", "bold"), (text, "bold")))


class AssistantMessage(Widget):
    # Streaming renders into a Static (cheap text replace). On
    # finalisation (replace()) the Static is swapped for a Markdown
    # widget — markdown re-parse runs once at the end, not 12.5×/sec.
    _FLUSH_INTERVAL = 0.15

    def __init__(self, initial: str = "") -> None:
        super().__init__()
        self._body: Static | Markdown | None = None
        self._initial: str = initial
        self._buffer: str = initial
        self._finalized: bool = bool(initial)
        self._flush_buffer: str = ""
        self._flush_timer = None

    def compose(self) -> ComposeResult:
        if self._finalized:
            self._body = Markdown(self._initial)
        else:
            self._body = Static("")
        yield self._body

    def on_mount(self) -> None:
        self._flush_timer = self.set_interval(
            self._FLUSH_INTERVAL, self._flush_deltas,
        )

    async def on_unmount(self) -> None:
        if self._flush_timer is not None:
            self._flush_timer.stop()
            self._flush_timer = None
        await self._flush_deltas()

    def append(self, delta: str) -> None:
        if not delta or self._finalized:
            return
        self._buffer += delta
        self._flush_buffer += delta

    async def _flush_deltas(self) -> None:
        if not self._flush_buffer or self._finalized:
            return
        self._flush_buffer = ""
        if isinstance(self._body, Static):
            self._body.update(self._buffer)

    def replace(self, text: str) -> None:
        self._buffer = text
        self._flush_buffer = ""
        self._finalized = True
        if self._body is None:
            return
        old = self._body
        new = Markdown(text)
        self._body = new
        if self.is_mounted:
            asyncio.create_task(self._swap_body(old, new))

    async def _swap_body(self, old: Widget, new: Widget) -> None:
        await self.mount(new, after=old)
        await old.remove()

    @property
    def text(self) -> str:
        return self._buffer


class ErrorLine(Static):
    def __init__(self, text: str) -> None:
        super().__init__(Text.assemble(("✗ ", "bold"), (text, "")))


class DimLine(Static):
    def __init__(self, text: str) -> None:
        super().__init__(Text(text))


class ReasoningLine(Static):
    MAX_CHARS = 400

    def __init__(self, text: str) -> None:
        compact = " ".join(text.split())
        if len(compact) > self.MAX_CHARS:
            compact = compact[: self.MAX_CHARS - 1] + "…"
        super().__init__(Text(f"» {compact}"))


class ResumeActivity(Static):
    """One-line activity indicator shown between the top bar and the
    chat scroll while a long session rehydrates. Spinner + message,
    auto-animating at 10 fps via a Textual timer. Removed when the
    resume worker finishes.
    """

    DEFAULT_CSS = """
    ResumeActivity {
        height: 1;
        padding: 0 2;
        color: $text-muted;
    }
    """

    _FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

    def __init__(self, message: str = "resuming last session…") -> None:
        super().__init__("")
        self._message = message
        self._idx = 0
        self._timer = None

    def on_mount(self) -> None:
        self._timer = self.set_interval(1 / 10, self._tick)
        self._refresh_label()

    def _tick(self) -> None:
        self._idx = (self._idx + 1) % len(self._FRAMES)
        self._refresh_label()

    def _refresh_label(self) -> None:
        tv = self.app.theme_variables
        accent = tv.get("accent", "cyan")
        t = Text()
        t.append(self._FRAMES[self._idx], style=accent)
        t.append(f"  {self._message}")
        self.update(t)

    def on_unmount(self) -> None:
        if self._timer is not None:
            self._timer.stop()
            self._timer = None


_SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


def _fmt_cost(cost: float) -> str:
    if cost <= 0:
        return "$0"
    if cost < 0.01:
        return f"${cost:.4f}"
    return f"${cost:.2f}"


class ThinkingIndicator(Static):
    _REASONING_TAIL_CHARS = 80

    def __init__(self) -> None:
        super().__init__("")
        self.started = time.time()
        self._timer = None
        self._reasoning: str = ""

    def on_mount(self) -> None:
        self._tick()
        self._timer = self.set_interval(1 / 4, self._tick)

    def append_reasoning(self, delta: str) -> None:
        if not delta:
            return
        self._reasoning += delta

    def _tick(self) -> None:
        from rich.markup import escape
        from alpi.tui.formatting import fmt_duration
        tv = self.app.theme_variables
        accent = tv.get("accent", "")
        muted = tv.get("text-muted", "")
        frame = _SPINNER_FRAMES[int(time.time() * 4) % len(_SPINNER_FRAMES)]
        elapsed = fmt_duration(time.time() - self.started)
        spinner_markup = f"[{accent}]{frame}[/{accent}]" if accent else frame
        if self._reasoning:
            compact = " ".join(self._reasoning.split())
            tail = compact[-self._REASONING_TAIL_CHARS:]
            if len(compact) > self._REASONING_TAIL_CHARS:
                tail = "…" + tail
            body = f"[{muted}]{escape(tail)}  {elapsed}[/{muted}]"
        else:
            body = f"[{muted}] thinking…  {elapsed}[/{muted}]"
        self.update(Text.from_markup(f"{spinner_markup} {body}"))

    def stop(self) -> None:
        if self._timer is not None:
            self._timer.stop()
            self._timer = None
        self.remove()


class ToolCard(Widget):
    TOOL_COL_WIDTH = 14

    def __init__(self, tool_id: str, name: str, args: dict) -> None:
        super().__init__()
        self.tool_id = tool_id
        self.tool_name = name
        self.args = args
        self.started = time.time()
        self._done = False
        self._result_markup: str = ""
        self._elapsed_final: float | None = None
        self._timer = None
        self._state_label: str = ""
        self._state_is_error: bool = False
        self.add_class("-running")

    def on_mount(self) -> None:
        self._timer = self.set_interval(1 / 4, self._tick)

    def _tick(self) -> None:
        if not self._done:
            self.refresh()

    def set_state(self, label: str, is_error: bool = False) -> None:
        self._state_label = label or ""
        self._state_is_error = bool(is_error)
        self.refresh()

    def finish(self, output: str, ok: bool, *, skip_duration: bool = False) -> None:
        self._done = True
        # None means "no real duration"; render() hides it.
        self._elapsed_final = None if skip_duration else (time.time() - self.started)
        from rich.markup import escape
        from alpi.tui.formatting import result_hint, truncate
        tv = self.app.theme_variables
        error_color = tv.get("error", "red")
        muted = tv.get("text-muted", "dim")
        if ok:
            self._result_markup = result_hint(self.tool_name, output, muted=muted)
        else:
            msg = output.removeprefix("ERROR:").strip() or "failed"
            self._result_markup = (
                f"[{error_color}]✗ {escape(truncate(msg, 80))}[/{error_color}]"
            )
        if self._timer is not None:
            self._timer.stop()
        self.remove_class("-running")
        self.add_class("-error" if not ok else "-done")
        self.refresh()

    def render(self):
        from alpi.tui.formatting import arg_hint, fmt_duration
        tv = self.app.theme_variables
        accent = tv.get("accent", "cyan")
        accent_muted = tv.get("accent-darken-1", accent)
        muted = tv.get("text-muted", "")
        error_color = tv.get("error", "red")
        arg = arg_hint(self.tool_name, self.args)
        name_col = self.tool_name.ljust(self.TOOL_COL_WIDTH)
        text = Text()
        if self._done:
            is_error = "-error" in self.classes
            diamond_style = error_color if is_error else accent_muted
            text.append("◆ ", style=diamond_style)
            text.append(name_col, style="bold")
            text.append(" ")
            text.append(arg, style=muted)
            text.append("  ")
            text.append("→", style=muted)
            text.append("  ")
            text.append_text(Text.from_markup(self._result_markup))
            if self._elapsed_final is not None and self._elapsed_final > 0:
                text.append(f"   {fmt_duration(self._elapsed_final)}", style=muted)
        else:
            elapsed = time.time() - self.started
            frame = _SPINNER_FRAMES[int(time.time() * 4) % len(_SPINNER_FRAMES)]
            icon_style = error_color if self._state_is_error else accent_muted
            spinner_style = error_color if self._state_is_error else accent
            label_style = error_color if self._state_is_error else muted

            text.append("◆ ", style=icon_style)
            text.append(name_col, style="bold")
            text.append(" ")
            live = self._state_label or arg
            text.append(live, style=label_style)
            text.append("  ")
            text.append(frame, style=spinner_style)
            text.append("  ")
            text.append(fmt_duration(elapsed), style=muted)
        return text


class AlpiTopBar(Static):
    def __init__(self, version: str, profile: str, path: str,
                 workspace_set: bool, sandbox: bool = False,
                 network_locked: bool = False, profile_size: str = "",
                 update_available: str = "") -> None:
        super().__init__("")
        self._version = version
        self._profile = profile
        self._path = path
        self._workspace_set = workspace_set
        self._sandbox = sandbox
        self._network_locked = network_locked
        self._profile_size = profile_size
        # Empty when up-to-date or the cache hasn't been written yet.
        # When set (e.g. ``"0.2.95"``), the top bar shows a small
        # ``↑ v0.2.95`` badge; the user runs ``alpi update`` to act.
        self._update_available = update_available

    def on_mount(self) -> None:
        self._refresh()

    def on_resize(self, event) -> None:  # noqa: ARG002
        self._refresh()

    def set_state(self, *, profile: str, path: str, workspace_set: bool,
                  sandbox: bool = False, network_locked: bool = False,
                  profile_size: str = "", update_available: str = "") -> None:
        self._profile = profile
        self._path = path
        self._workspace_set = workspace_set
        self._sandbox = sandbox
        self._network_locked = network_locked
        self._profile_size = profile_size
        self._update_available = update_available
        self._refresh()

    def _refresh(self) -> None:
        from rich.markup import escape
        tv = self.app.theme_variables
        accent = tv.get("accent", "")
        muted = tv.get("text-muted", "")
        error = tv.get("error", "red")
        width = self.size.width or 80
        narrow = width < 60
        if self._workspace_set:
            short = str(self._path).replace(str(Path.home()), "~")
            workspace_txt = escape(short)
        else:
            workspace_txt = f"[{error}]not set[/{error}]"
        profile_esc = escape(self._profile)
        profile_txt = (
            f"[b {accent}]{profile_esc}[/b {accent}]"
            if accent else f"[b]{profile_esc}[/b]"
        )
        if self._profile_size and not narrow:
            profile_txt += f" [{muted}]{escape(self._profile_size)}[/{muted}]"
        sep = f"  [{muted}]│[/{muted}]  "
        profile_label = "" if narrow else f"[{muted}]profile[/{muted}] "
        workspace_label = "" if narrow else f"[{muted}]workspace[/{muted}] "
        version_block = f"[b]alpi[/b] [{muted}]{escape(self._version)}[/{muted}]"
        if self._update_available:
            badge_color = accent or "yellow"
            version_block += (
                f" [{badge_color}]↑ v{escape(self._update_available)}[/{badge_color}]"
            )
        markup = (
            f"{version_block}"
            f"{sep}"
            f"{profile_label}{profile_txt}"
        )
        if self._sandbox:
            label = "offline" if self._network_locked else "sandbox"
            markup += f"{sep}[{muted}]{label}[/{muted}]"
        markup += (
            f"{sep}"
            f"{workspace_label}{workspace_txt}"
        )
        self.update(Text.from_markup(markup))


class AlpiHeader(Static):
    def __init__(self) -> None:
        super().__init__("")
        self._model: str = ""
        self._tokens: int = 0
        self._cost: float = 0.0
        self._ctx_window: int = 200_000
        self._budget_kind: str | None = None
        self._budget_used: float = 0.0
        self._budget_cap: float = 0.0

    def on_mount(self) -> None:
        self._refresh()

    def on_resize(self, event) -> None:  # noqa: ARG002
        self._refresh()

    def update_usage(
        self,
        model: str,
        tokens: int,
        cost: float,
        ctx_window: int = 200_000,
        budget_kind: str | None = None,
        budget_used: float = 0.0,
        budget_cap: float = 0.0,
    ) -> None:
        self._model = model
        self._tokens = tokens
        self._cost = cost
        self._ctx_window = ctx_window
        self._budget_kind = budget_kind
        self._budget_used = budget_used
        self._budget_cap = budget_cap
        self._refresh()

    def _refresh(self) -> None:
        from alpi.tui.formatting import fmt_count, bar
        tv = self.app.theme_variables
        accent = tv.get("accent", "cyan")
        warning = tv.get("warning", "yellow")
        error = tv.get("error", "red")
        muted = tv.get("text-muted", "")
        pct = int(self._tokens / self._ctx_window * 100) if self._ctx_window else 0
        width = self.size.width or 80
        wide = width >= 100
        narrow = width < 60
        if wide:
            model_label = self._model if self._model else "—"
        else:
            model_label = self._model.split("/")[-1] if self._model else "—"
        bar_cells = 5 if narrow else 10
        bar_str = bar(self._tokens, self._ctx_window, bar_cells)
        if pct >= 80:
            bar_color = error
        elif pct >= 60:
            bar_color = warning
        else:
            bar_color = accent
        sep = f"  [{muted}]│[/{muted}]  "
        markup = (
            f"[{accent}]◆[/{accent}] [b {accent}]{model_label}[/b {accent}]"
            f"{sep}"
            f"{fmt_count(self._tokens)}/{fmt_count(self._ctx_window)}  "
            f"[{bar_color}]{bar_str}[/{bar_color}] [{muted}]{pct}%[/{muted}]"
        )
        if self._cost > 0:
            markup += f"{sep}[{muted}]{_fmt_cost(self._cost)}[/{muted}]"
        if self._budget_kind and self._budget_cap > 0:
            b_pct = int(self._budget_used / self._budget_cap * 100)
            b_pct = max(0, min(100, b_pct))
            if b_pct >= 90:
                b_color = error
            elif b_pct >= 70:
                b_color = warning
            else:
                b_color = accent
            b_bar = bar(int(self._budget_used * 1000), int(self._budget_cap * 1000), bar_cells)
            if self._budget_kind == "usd":
                b_label = f"{_fmt_cost(self._budget_used)}/${self._budget_cap:.2f}"
            else:
                b_label = (
                    f"{fmt_count(int(self._budget_used))}/"
                    f"{fmt_count(int(self._budget_cap))} tok"
                )
            markup += (
                f"{sep}{b_label}  "
                f"[{b_color}]{b_bar}[/{b_color}] [{muted}]{b_pct}%[/{muted}]"
            )
        self.update(Text.from_markup(markup))
