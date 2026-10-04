from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Markdown, OptionList, Static, TextArea
from textual.widgets.option_list import Option

from alpi.tool_hints import FAMILY_GLYPHS, arg_hint, result_hint, tool_family, truncate
from alpi.tui.formatting import fmt_count, fmt_duration
from alpi.tui.turns import reasoning_duration, steps_span, thought_label

_SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
_CLOSED = "▸"
_OPEN = "▾"


def _spinner() -> str:
    return _SPINNER_FRAMES[int(time.time() * 8) % len(_SPINNER_FRAMES)]


def _tv(widget: Widget, name: str, fallback: str = "") -> str:
    try:
        return widget.app.theme_variables.get(name, fallback) or fallback
    except Exception:  # noqa: BLE001
        return fallback


class ChatInput(TextArea):
    class Submitted(Message):
        def __init__(self, chat_input: "ChatInput", value: str) -> None:
            super().__init__()
            self.chat_input = chat_input
            self.value = value

        @property
        def control(self) -> "ChatInput":
            return self.chat_input

    BINDINGS = [
        Binding("shift+enter,alt+enter,ctrl+j", "newline", "New line", show=False),
    ]

    def __init__(self, *, placeholder: str = "", id: str | None = None) -> None:
        super().__init__(
            "", soft_wrap=True, tab_behavior="focus", compact=True,
            highlight_cursor_line=False, placeholder=placeholder, id=id,
        )
        self.sent: list[str] = []
        self._history_idx: int | None = None
        self._recalled = False
        self.completion: "CompletionPopup | None" = None

    @property
    def value(self) -> str:
        return self.text

    @value.setter
    def value(self, text: str) -> None:
        self.load_text(text)
        self.move_cursor(self.document.end)

    def take_recalled(self) -> bool:
        recalled, self._recalled = self._recalled, False
        return recalled

    def remember(self, text: str) -> None:
        if text and (not self.sent or self.sent[-1] != text):
            self.sent.append(text)
        self._history_idx = None

    def action_newline(self) -> None:
        self.replace("\n", *self.selection, maintain_selection_offset=False)

    def _recall(self, step: int) -> bool:
        if not self.sent:
            return False
        if self._history_idx is None:
            if step > 0 or self.text:
                return False
            idx = len(self.sent) - 1
        else:
            idx = self._history_idx + step
        self._recalled = True
        if idx >= len(self.sent):
            self._history_idx = None
            self.value = ""
            return True
        self._history_idx = max(0, idx)
        self.value = self.sent[self._history_idx]
        return True

    async def _on_key(self, event: events.Key) -> None:
        key = event.key
        popup = self.completion
        if popup is not None and popup.active and key in ("up", "down", "tab", "enter"):
            event.stop()
            event.prevent_default()
            if key == "up":
                popup.move(-1)
            elif key == "down":
                popup.move(1)
            else:
                popup.accept(submit=key == "enter")
            return
        if key == "tab":
            event.stop()
            event.prevent_default()
            return
        if key == "enter":
            event.stop()
            event.prevent_default()
            row, col = self.cursor_location
            if col > 0 and self.document[row][:col].endswith("\\"):
                self.replace("\n", (row, col - 1), (row, col), maintain_selection_offset=False)
                return
            self.post_message(self.Submitted(self, self.text))
            return
        if key == "up" and self.cursor_at_first_line and self._recall(-1):
            event.stop()
            event.prevent_default()
            return
        if key == "down" and self._history_idx is not None and self.cursor_at_last_line and self._recall(1):
            event.stop()
            event.prevent_default()
            return
        await super()._on_key(event)


class CompletionPopup(OptionList):
    can_focus = False

    DEFAULT_CSS = """
    CompletionPopup {
        display: none;
        height: auto;
        max-height: 10;
        margin: 0 1;
        padding: 0 1;
        background: $panel;
        border: none;
        scrollbar-size: 0 0;
    }
    CompletionPopup.-visible {
        display: block;
    }
    """

    def __init__(self, target: ChatInput, on_accept) -> None:
        super().__init__(id="completion", compact=True)
        self._target = target
        self._on_accept = on_accept
        self._values: list[tuple[str, bool, bool]] = []

    @property
    def active(self) -> bool:
        return self.has_class("-visible") and bool(self._values)

    def show(self, items: list[tuple[str, str, bool, bool]]) -> None:
        self.clear_options()
        self._values = [(value, takes_arg, requires_arg) for value, _, takes_arg, requires_arg in items]
        if not items:
            self.remove_class("-visible")
            return
        width = max(len(item[0]) for item in items)
        muted = _tv(self, "text-muted", "dim")
        for value, desc, _, _ in items:
            t = Text(no_wrap=True, overflow="ellipsis")
            t.append(value.ljust(width))
            if desc:
                t.append(f"  {desc}", style=muted)
            self.add_option(Option(t))
        self.highlighted = 0
        self.add_class("-visible")

    def hide(self) -> None:
        self._values = []
        self.clear_options()
        self.remove_class("-visible")

    def move(self, delta: int) -> None:
        if not self._values:
            return
        idx = (self.highlighted or 0) + delta
        self.highlighted = idx % len(self._values)

    def accept(self, submit: bool) -> None:
        if not self._values:
            return
        value, takes_arg, requires_arg = self._values[self.highlighted or 0]
        self.hide()
        self._on_accept(value, takes_arg, requires_arg, submit)


class UserMessage(Widget):
    PLAIN_CHARS = 4000
    PLAIN_LINES = 60

    def __init__(self, text: str) -> None:
        super().__init__()
        self._text = text

    @property
    def plain(self) -> bool:
        return len(self._text) > self.PLAIN_CHARS or self._text.count("\n") >= self.PLAIN_LINES

    def compose(self) -> ComposeResult:
        body = Static(Text(self._text), classes="user-plain") if self.plain else Markdown(self._text)
        yield Horizontal(Static(Text("› ", style="bold")), body)


class AssistantMessage(Widget):
    # Streaming renders into a Static; the Markdown swap happens once on replace().
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


class ResumeActivity(Static):
    DEFAULT_CSS = """
    ResumeActivity {
        height: 1;
        padding: 0 2;
        color: $text-muted;
    }
    """

    def __init__(self, message: str = "resuming last session…") -> None:
        super().__init__("")
        self._message = message
        self._timer = None

    def on_mount(self) -> None:
        self._timer = self.set_interval(1 / 10, self._refresh_label)
        self._refresh_label()

    def _refresh_label(self) -> None:
        t = Text()
        t.append(_spinner(), style=_tv(self, "accent", "cyan"))
        t.append(f"  {self._message}")
        self.update(t)

    def on_unmount(self) -> None:
        if self._timer is not None:
            self._timer.stop()
            self._timer = None


def _fmt_cost(cost: float) -> str:
    if cost <= 0:
        return "$0"
    if cost < 0.01:
        return f"${cost:.4f}"
    return f"${cost:.2f}"


class ThinkingIndicator(Static):
    def __init__(self, label: str = "Thinking…") -> None:
        super().__init__("")
        self.started = time.time()
        self.label = label
        self._timer = None

    def on_mount(self) -> None:
        self._tick()
        self._timer = self.set_interval(1 / 4, self._tick)

    def set_label(self, label: str) -> None:
        self.label = label
        self._tick()

    def _tick(self) -> None:
        t = Text()
        t.append(_spinner(), style=_tv(self, "accent", "cyan"))
        t.append(f" {self.label}", style=_tv(self, "text-secondary", ""))
        t.append(f"  {reasoning_duration(time.time() - self.started)}", style=_tv(self, "text-muted", "dim"))
        self.update(t)

    def stop(self) -> None:
        if self._timer is not None:
            self._timer.stop()
            self._timer = None
        self.remove()


def _child(widget: Widget, selector: str, kind=Static):
    try:
        return widget.query_one(selector, kind)
    except Exception:  # noqa: BLE001
        return None


class _Toggle(Static):
    def on_click(self, event: events.Click) -> None:
        event.stop()
        parent = self.parent
        if parent is not None and hasattr(parent, "toggle"):
            parent.toggle()


class _Collapsible(Widget):
    def toggle(self) -> None:
        self.set_expanded(not self.expanded)

    @property
    def expanded(self) -> bool:
        return self.has_class("-expanded")

    def set_expanded(self, value: bool) -> None:
        self.set_class(value, "-expanded")
        self.refresh_head()

    def refresh_head(self) -> None:
        pass


class ReasoningBlock(_Collapsible):
    DEFAULT_CSS = """
    ReasoningBlock { height: auto; margin: 0; }
    ReasoningBlock > .reasoning-head { height: 1; color: $text-muted; }
    ReasoningBlock > .reasoning-body {
        display: none; height: auto; color: $text-muted; padding: 0 0 0 2;
    }
    ReasoningBlock.-expanded > .reasoning-body { display: block; }
    """

    def __init__(self, text: str = "", seconds: float | None = None) -> None:
        super().__init__()
        self.text = text.strip()
        self.seconds = seconds

    def compose(self) -> ComposeResult:
        yield _Toggle(classes="reasoning-head")
        yield Static(Text(self.text), classes="reasoning-body")

    def on_mount(self) -> None:
        self.refresh_head()

    @property
    def label(self) -> str:
        return thought_label(self.seconds)

    def append(self, text: str) -> None:
        text = (text or "").strip()
        if not text:
            return
        self.text = f"{self.text}\n\n{text}" if self.text else text
        body = _child(self, ".reasoning-body")
        if body is not None:
            body.update(Text(self.text))

    def set_seconds(self, seconds: float) -> None:
        self.seconds = seconds
        self.refresh_head()

    def add_seconds(self, seconds: float) -> None:
        self.set_seconds((self.seconds or 0.0) + seconds)

    def refresh_head(self) -> None:
        head = _child(self, ".reasoning-head")
        if head is not None:
            caret = _OPEN if self.expanded else _CLOSED
            head.update(Text(f"{caret} {self.label}"))


class ToolCard(_Collapsible):
    DEFAULT_CSS = """
    ToolCard { height: auto; margin: 0; padding: 0; color: $text-muted; }
    ToolCard > .tool-head { height: 1; color: $text-muted; }
    ToolCard > .tool-detail {
        display: none; height: auto; color: $text-muted; padding: 0 0 0 2;
    }
    ToolCard.-expanded > .tool-detail { display: block; }
    """

    DETAIL_LINES = 12

    def __init__(self, tool_id: str, name: str, args: dict, *, started: float | None = None) -> None:
        super().__init__()
        self.tool_id = tool_id
        self.tool_name = name
        self.args = args or {}
        self.started = started if started is not None else time.time()
        self.ended: float | None = None
        self.done = False
        self.ok = True
        self.output = ""
        self.duration_s: float | None = None
        self._state_label = ""
        self._state_is_error = False
        self._timer = None
        self.add_class("-running")

    @property
    def family(self) -> str:
        return tool_family(self.tool_name)

    def compose(self) -> ComposeResult:
        yield _Toggle(classes="tool-head")
        yield Static("", classes="tool-detail")

    def on_mount(self) -> None:
        self.refresh_head()
        self._refresh_detail()
        if not self.done:
            self._timer = self.set_interval(1 / 4, self.refresh_head)

    def set_state(self, label: str, is_error: bool = False) -> None:
        self._state_label = label or ""
        self._state_is_error = bool(is_error)
        self.refresh_head()

    def finish(self, output: str, ok: bool, *, duration_s: float | None = None, skip_duration: bool = False) -> None:
        self.done = True
        self.ok = bool(ok)
        self.output = output or ""
        if skip_duration:
            self.duration_s = None
        elif duration_s is not None:
            self.duration_s = max(0.0, float(duration_s))
        else:
            self.duration_s = time.time() - self.started
        self.ended = self.started + (self.duration_s or 0.0)
        if self._timer is not None:
            self._timer.stop()
            self._timer = None
        self.remove_class("-running")
        self.add_class("-done" if ok else "-error")
        if not ok:
            self.add_class("-expanded")
        self._refresh_detail()
        self.refresh_head()

    def head_text(self) -> Text:
        accent = _tv(self, "accent", "cyan")
        muted = _tv(self, "text-muted", "dim")
        error = _tv(self, "error", "red")
        glyph = FAMILY_GLYPHS.get(self.family, FAMILY_GLYPHS["chip"])
        text = Text(no_wrap=True, overflow="ellipsis")
        if self.done:
            text.append(f"{_OPEN if self.expanded else _CLOSED} ", style=muted)
            text.append(f"{glyph} ", style=error if not self.ok else muted)
            text.append(self.tool_name, style=muted)
            hint = arg_hint(self.tool_name, self.args)
            if hint:
                text.append(f"  {hint}", style=muted)
            text.append("  → ", style=muted)
            if self.ok:
                text.append_text(Text.from_markup(result_hint(self.tool_name, self.output, muted=muted)))
            else:
                msg = self.output.removeprefix("ERROR:").strip() or "failed"
                text.append(f"✗ {truncate(msg, 80)}", style=error)
            if self.duration_s:
                text.append(f"  {fmt_duration(self.duration_s)}", style=muted)
            return text
        live_style = error if self._state_is_error else muted
        text.append(f"{_spinner()} ", style=error if self._state_is_error else accent)
        text.append(f"{glyph} ", style=muted)
        text.append(self.tool_name, style=muted)
        text.append(f"  {self._state_label or arg_hint(self.tool_name, self.args)}", style=live_style)
        text.append(f"  {fmt_duration(time.time() - self.started)}", style=muted)
        return text

    def refresh_head(self) -> None:
        head = _child(self, ".tool-head")
        if head is not None:
            head.update(self.head_text())

    def detail_text(self) -> str:
        lines: list[str] = []
        if self.args:
            try:
                pretty = json.dumps(self.args, indent=2, ensure_ascii=False, default=str)
            except (TypeError, ValueError):
                pretty = str(self.args)
            arg_lines = pretty.splitlines()
            lines.extend(truncate(ln, 160) if len(ln) > 160 else ln for ln in arg_lines[:20])
            if len(arg_lines) > 20:
                lines.append(f"… +{len(arg_lines) - 20} more lines")
        if self.done and self.output.strip():
            out_lines = self.output.strip().splitlines()
            if lines:
                lines.append("")
            lines.extend(ln if len(ln) <= 160 else ln[:159] + "…" for ln in out_lines[: self.DETAIL_LINES])
            if len(out_lines) > self.DETAIL_LINES:
                lines.append(f"… +{len(out_lines) - self.DETAIL_LINES} more lines")
        return "\n".join(lines)

    def _refresh_detail(self) -> None:
        detail = _child(self, ".tool-detail")
        if detail is not None:
            detail.update(Text(self.detail_text()))


class StepsGroup(_Collapsible):
    DEFAULT_CSS = """
    StepsGroup { height: auto; margin: 0; }
    StepsGroup > .steps-head { height: 1; color: $text-muted; }
    StepsGroup > .steps-body { display: none; height: auto; padding: 0 0 0 2; }
    StepsGroup.-expanded > .steps-body { display: block; }
    """

    def __init__(self, cards: list[ToolCard] | None = None) -> None:
        super().__init__()
        self.cards: list[ToolCard] = list(cards or [])
        self._timer = None

    def compose(self) -> ComposeResult:
        yield _Toggle(classes="steps-head")
        yield Vertical(*self.cards, classes="steps-body")

    def on_mount(self) -> None:
        self.refresh_head()
        self._arm()

    def _arm(self) -> None:
        if self._timer is None and self.running and self.is_attached:
            self._timer = self.set_interval(1 / 4, self._tick)

    def _disarm(self) -> None:
        if self._timer is not None:
            self._timer.stop()
            self._timer = None

    @property
    def live(self) -> bool:
        return self._timer is not None

    def _tick(self) -> None:
        self.refresh_head()
        if not self.running:
            self._disarm()

    def on_unmount(self) -> None:
        self._disarm()

    @property
    def running(self) -> bool:
        return any(not c.done for c in self.cards)

    @property
    def failed(self) -> int:
        return sum(1 for c in self.cards if c.done and not c.ok)

    def add(self, card: ToolCard) -> None:
        self.cards.append(card)
        body = _child(self, ".steps-body", Vertical)
        if body is not None:
            body.mount(card)
        self.refresh_head()
        self._arm()

    def card_finished(self, card: ToolCard) -> None:
        if not card.ok:
            self.add_class("-expanded")
        self.refresh_head()
        if not self.running:
            self._disarm()

    def span_s(self) -> float:
        now = time.time()
        return steps_span([(c.started, c.ended if c.ended is not None else now) for c in self.cards])

    def head_text(self) -> Text:
        muted = _tv(self, "text-muted", "dim")
        error = _tv(self, "error", "red")
        accent = _tv(self, "accent", "cyan")
        n = len(self.cards)
        text = Text(no_wrap=True, overflow="ellipsis")
        if self.running:
            text.append(f"{_spinner()} ", style=accent)
        else:
            text.append(f"{_OPEN if self.expanded else _CLOSED} ", style=muted)
        text.append(f"{n} step{'' if n == 1 else 's'}", style=muted)
        span = self.span_s()
        if span > 0:
            text.append(f" · {fmt_duration(span)}", style=muted)
        if self.failed:
            text.append(f" · {self.failed} failed", style=error)
        live = next((c for c in reversed(self.cards) if not c.done), None)
        if live is not None and not self.expanded:
            glyph = FAMILY_GLYPHS.get(live.family, FAMILY_GLYPHS["chip"])
            text.append(f"   {glyph} {live.tool_name}", style=muted)
            hint = live._state_label or arg_hint(live.tool_name, live.args)
            if hint:
                text.append(f"  {hint}", style=muted)
        return text

    def refresh_head(self) -> None:
        head = _child(self, ".steps-head")
        if head is not None:
            head.update(self.head_text())


class AskUserLine(Static):
    DEFAULT_CSS = """
    AskUserLine { height: auto; color: $text-muted; margin: 0; }
    """

    def __init__(self, question: str, answer: str) -> None:
        t = Text()
        t.append("? ")
        t.append(question.strip())
        t.append("  → ")
        t.append(answer.strip())
        super().__init__(t)


class ProcessBlock(Vertical):
    DEFAULT_CSS = """
    ProcessBlock { height: auto; margin: 1 0 0 0; color: $text-muted; }
    """

    @property
    def details(self) -> list[_Collapsible]:
        return [c for c in self.children if isinstance(c, (ReasoningBlock, StepsGroup))]


class AlpiTopBar(Static):
    def __init__(self, version: str, profile: str, path: str,
                 workspace_set: bool, profile_size: str = "",
                 update_available: str = "") -> None:
        super().__init__("")
        self._version = version
        self._profile = profile
        self._path = path
        self._workspace_set = workspace_set
        self._profile_size = profile_size
        self._update_available = update_available

    def on_mount(self) -> None:
        self._refresh()

    def on_resize(self, event) -> None:  # noqa: ARG002
        self._refresh()

    def _refresh(self) -> None:
        accent = _tv(self, "accent", "cyan")
        muted = _tv(self, "text-muted", "dim")
        error = _tv(self, "error", "red")
        narrow = (self.size.width or 80) < 60
        sep = ("  │  ", muted)
        t = Text(no_wrap=True, overflow="ellipsis")
        t.append("alpi", style="bold")
        t.append(f" {self._version}", style=muted)
        if self._update_available:
            t.append(f" ↑ v{self._update_available}", style=accent)
        t.append(*sep)
        if not narrow:
            t.append("profile ", style=muted)
        t.append(self._profile, style=f"bold {accent}")
        if self._profile_size and not narrow:
            t.append(f" {self._profile_size}", style=muted)
        t.append(*sep)
        if not narrow:
            t.append("workspace ", style=muted)
        if self._workspace_set:
            t.append(str(self._path).replace(str(Path.home()), "~"))
        else:
            t.append("not set", style=error)
        self.update(t)


class StatusLine(Static):
    def __init__(self) -> None:
        super().__init__("", id="status-line")
        self.model = ""
        self.tokens = 0
        self.ctx_window = 200_000
        self.cost = 0.0
        self.budget_kind: str | None = None
        self.budget_used = 0.0
        self.budget_cap = 0.0
        self.sandbox = ""
        self.unread = 0
        self.waiting = 0
        self.hints = ""
        self.marker = "◆"

    def on_mount(self) -> None:
        self._refresh()

    def on_resize(self, event) -> None:  # noqa: ARG002
        self._refresh()

    def set_state(self, **fields: Any) -> None:
        changed = False
        for key, value in fields.items():
            if getattr(self, key) != value:
                setattr(self, key, value)
                changed = True
        if changed:
            self._refresh()

    @property
    def ctx_pct(self) -> int:
        return int(self.tokens / self.ctx_window * 100) if self.ctx_window else 0

    @property
    def budget_pct(self) -> int | None:
        if not self.budget_kind or self.budget_cap <= 0:
            return None
        return max(0, min(100, int(self.budget_used / self.budget_cap * 100)))

    def left_text(self) -> Text:
        accent = _tv(self, "accent", "cyan")
        muted = _tv(self, "text-muted", "dim")
        warning = _tv(self, "warning", "yellow")
        error = _tv(self, "error", "red")
        width = self.size.width or 80
        t = Text(no_wrap=True, overflow="ellipsis")
        model = self.model if width >= 110 else self.model.split("/")[-1]
        t.append(f"{self.marker} ", style=accent)
        t.append(model or "no model", style=f"bold {accent}")

        def seg(label: str, style: str = muted) -> None:
            t.append(" · ", style=muted)
            t.append(label, style=style)

        pct = self.ctx_pct
        seg(f"ctx {pct}% of {fmt_count(self.ctx_window)}", error if pct >= 80 else warning if pct >= 60 else muted)
        if self.cost > 0:
            seg(_fmt_cost(self.cost))
        b_pct = self.budget_pct
        if b_pct is not None:
            seg(f"budget {b_pct}%", error if b_pct >= 90 else warning if b_pct >= 70 else muted)
        if self.sandbox:
            seg(self.sandbox)
        if self.unread:
            seg(f"{self.unread} unread", accent)
        if self.waiting:
            seg(f"{self.waiting} waiting on you", f"bold {warning}")
        return t

    def _refresh(self) -> None:
        left = self.left_text()
        width = (self.size.width or 80) - 4
        if self.hints and left.cell_len + len(self.hints) + 3 <= width:
            pad = width - left.cell_len - len(self.hints)
            left.append(" " * pad)
            left.append(self.hints, style=_tv(self, "text-muted", "dim"))
        self.update(left)

    @property
    def plain(self) -> str:
        t = self.left_text()
        return f"{t.plain}  {self.hints}".strip()
