"""Shared UI primitives for every ``alpi setup`` wizard + menu."""

from __future__ import annotations

from pathlib import Path
from typing import Any, NamedTuple, Sequence

from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.text import Text
from rich.theme import Theme

_THEME = Theme(
    {
        "muted": "dim",
        "error": "red",
        "success": "green",
        "prompt": "default",
        "prompt.default": "dim",
        "prompt.choices": "dim",
        "prompt.invalid": "red",
        "prompt.invalid.choice": "red",
        "repr.str": "default",
        "repr.number": "default",
        "repr.bool_true": "default",
        "repr.bool_false": "default",
        "repr.none": "default",
        "repr.url": "default",
        "repr.path": "default",
        "repr.filename": "default",
        "repr.call": "default",
        "repr.attrib_name": "default",
        "repr.attrib_value": "default",
    }
)

_console = Console(theme=_THEME, highlight=False)

_MUTED_STYLE = "fg:#888888"

LABEL_WIDTH = 16

POINTER = "◆"
NAV_HINT = "(↑↓ navigate  ENTER select  ESC cancel)"


def crumb(*parts: str) -> str:
    from alpi import __version__
    segments = [f"alpi v{__version__}", *[p for p in parts if p]]
    return " › ".join(segments)


def banner(title: str, subtitle: str = "", hint: str = "",
           home: Path | None = None) -> None:
    _console.clear()
    line = _render_title(title, home=home)
    if subtitle:
        line += f"[dim] › {subtitle}[/dim]"
    _console.print(line)
    if hint:
        _console.print(f"[dim]{hint}[/dim]")
    _console.print("")


def _render_title(title: str, *, home: Path | None) -> str:
    accent = _accent_hex(home)
    if accent and title.startswith("alpi "):
        return f"[b {accent}]alpi[/b {accent}][b] {title[4:]}[/b]"
    return f"[b]{title}[/b]"


def _accent_hex(home: Path | None) -> str:
    try:
        from alpi import config as config_mod
        from alpi import home as home_mod
        resolved = home or home_mod.get_home()
        cfg = config_mod.load(resolved)
        return (cfg.tui or {}).get("accent", "") or ""
    except Exception:  # noqa: BLE001
        return ""


_TRAILING_PAREN = __import__("re").compile(r"\s*\([^)]*\)\s*$")


def row(label: str, status: str = "", width: int | None = None):
    if not status:
        return label
    w = width if width is not None else LABEL_WIDTH
    left = f"{label:<{w}}"
    return [
        ("", left),
        (_MUTED_STYLE, f" · {status}"),
    ]


def row_accent(label: str, status: str, accent: str, width: int | None = None):
    if not accent or not accent.strip():
        return row(label, status, width=width)
    w = width if width is not None else LABEL_WIDTH
    left = f"{label:<{w}}"
    parts = [(f"fg:{accent.strip()} bold", left)]
    if status:
        parts.append((_MUTED_STYLE, f" · {status}"))
    return parts


# Separator sentinel — pass `None` in the items list to get a blank row.
_SEPARATOR = object()


class Heading(NamedTuple):
    """Non-selectable section label inside a ``menu()`` items list."""
    text: str


def menu(
    title: str,
    items: Sequence[Any],
    *,
    subtitle: str = "",
    home: Path | None = None,
    close: str = "Exit",
) -> Any:
    """Render a banner + arrow-key select list + muted close row.

    Items accept the same shapes as before:
        - ``(label, value)``
        - ``(label, value, status)`` → rendered via ``row(label, status)``
        - ``None`` → blank separator row
        - ``Heading("Section")`` → muted-bold uppercase divider, non-selectable
        - bare string → used as both label and value
    """
    if title:
        _console.clear()
        line = _render_title(title, home=home)
        if subtitle:
            line += f"[dim] › {subtitle}[/dim]"
        _console.print(line)
        _console.print(f"[dim]{NAV_HINT}[/dim]")
        _console.print("")

    # First pass: find the widest plain-text label across 3-tuple items
    # so the muted status column lines up per menu, independent of the
    # module-level LABEL_WIDTH floor.
    auto_width = LABEL_WIDTH
    for item in items:
        if isinstance(item, tuple) and len(item) == 3:
            label, _value, status = item
            if status:
                auto_width = max(auto_width, len(str(label)))

    entries: list[tuple[Any, Any, bool]] = []  # (title_ft, value, selectable)
    for item in items:
        if item is None:
            entries.append((" ", _SEPARATOR, False))
        elif isinstance(item, Heading):
            # Visually breathe between sections — every heading after the
            # first one gets an automatic blank row above it.
            if entries:
                entries.append((" ", _SEPARATOR, False))
            entries.append((
                [(f"{_MUTED_STYLE} bold", item.text)],
                _SEPARATOR, False,
            ))
        elif isinstance(item, tuple):
            if len(item) == 3:
                label, value, status = item
                entries.append((
                    row(str(label), str(status or ""), width=auto_width),
                    value, True,
                ))
            elif len(item) == 2:
                label, value = item
                entries.append((label, value, True))
        else:
            entries.append((str(item), item, True))

    close_sentinel: Any = object()
    if close:
        if entries:
            entries.append((" ", _SEPARATOR, False))
        entries.append((
            [(_MUTED_STYLE, close)],
            close_sentinel,
            True,
        ))

    result = _run_select(entries, home=home)
    if result is None or result is close_sentinel:
        return None
    return result


def _run_select(entries, *, home: Path | None):
    from prompt_toolkit.application import Application
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import Layout
    from prompt_toolkit.layout.containers import HSplit, Window
    from prompt_toolkit.layout.controls import FormattedTextControl

    accent = _accent_hex(home)
    selectable_idx = [i for i, (_, _, sel) in enumerate(entries) if sel]
    if not selectable_idx:
        return None
    state = {"cursor": selectable_idx[0]}

    def _render():
        out: list[tuple[str, str]] = []
        for i, (title_ft, _, selectable) in enumerate(entries):
            is_cursor = (i == state["cursor"])
            pointer = f"{POINTER} " if is_cursor else "  "
            pointer_style = (
                f"fg:{accent} bold" if (is_cursor and accent) else
                ("bold" if is_cursor else "")
            )
            if not selectable:
                out.append(("", pointer))
            else:
                out.append((pointer_style, pointer))
            if isinstance(title_ft, list):
                for style, text in title_ft:
                    out.append((style, text))
            else:
                out.append(("", str(title_ft)))
            out.append(("", "\n"))
        # Strip final newline so the control doesn't render an extra
        # blank row under the last entry.
        if out and out[-1] == ("", "\n"):
            out.pop()
        return out

    kb = KeyBindings()

    def _move(delta: int) -> None:
        pos = selectable_idx.index(state["cursor"])
        pos = (pos + delta) % len(selectable_idx)
        state["cursor"] = selectable_idx[pos]

    @kb.add("up")
    @kb.add("c-p")
    @kb.add("k")
    def _(event):  # noqa: ARG001
        _move(-1)

    @kb.add("down")
    @kb.add("c-n")
    @kb.add("j")
    def _(event):  # noqa: ARG001
        _move(1)

    @kb.add("home")
    def _(event):  # noqa: ARG001
        state["cursor"] = selectable_idx[0]

    @kb.add("end")
    def _(event):  # noqa: ARG001
        state["cursor"] = selectable_idx[-1]

    @kb.add("enter")
    def _(event) -> None:
        _, value, _ = entries[state["cursor"]]
        event.app.exit(result=value)

    @kb.add("escape", eager=True)
    @kb.add("c-c")
    @kb.add("c-d")
    @kb.add("q")
    def _(event) -> None:
        event.app.exit(result=None)

    control = FormattedTextControl(_render, focusable=True, show_cursor=False)
    layout = Layout(HSplit([Window(content=control, always_hide_cursor=True)]))
    app = Application(
        layout=layout,
        key_bindings=kb,
        full_screen=False,
        mouse_support=False,
    )
    try:
        return app.run()
    except KeyboardInterrupt:
        return None


def text(label: str, default: str = "") -> str | None:
    """Single-line free-text input. ENTER submits, ESC/Ctrl-C return None.

    When ``default`` is provided and the user submits empty input, the
    default is returned.
    """
    from prompt_toolkit import PromptSession
    from prompt_toolkit.formatted_text import FormattedText
    from prompt_toolkit.key_binding import KeyBindings

    clean = _clean_label(label)
    if default:
        clean = _TRAILING_PAREN.sub("", clean).rstrip()

    accent = _accent_hex(None) or ""
    fragments: list[tuple[str, str]] = [("", clean)]
    if default:
        default_style = f"fg:{accent}" if accent else _MUTED_STYLE
        fragments.append(("", " ("))
        fragments.append((default_style, default))
        fragments.append(("", ")"))
    fragments.append(("", ": "))

    kb = KeyBindings()

    @kb.add("escape", eager=True)
    def _(event) -> None:
        event.app.exit(result=None)

    try:
        session = PromptSession(FormattedText(fragments), key_bindings=kb)
        result = session.prompt()
    except (KeyboardInterrupt, EOFError):
        return None
    if result is None:
        return None
    if default and result == "":
        return default
    return result


def password(label: str, current: str = "") -> str | None:
    import getpass

    clean = _clean_label(label)
    if current:
        clean = _TRAILING_PAREN.sub("", clean).rstrip()

    if current:
        _console.print(
            _styled_prompt(clean, f"…{current[-4:]}"),
            end=": ",
        )
    else:
        _console.print(clean, end=": ")

    try:
        entered = getpass.getpass("")
    except (KeyboardInterrupt, EOFError):
        _console.print()
        return None

    if current and entered == "":
        return current
    return entered


def _styled_prompt(label: str, default: str):
    text = Text()
    text.append(label)
    if default:
        accent = _accent_hex(None) or "dim"
        text.append(" (")
        text.append(default, style=accent)
        text.append(")")
    return text


def _clean_label(label: str) -> str:
    return (label or "").rstrip(": \t\n")


def confirm(label: str, default: bool = True) -> bool:
    try:
        return Confirm.ask(label, default=default, console=_console)
    except (KeyboardInterrupt, EOFError):
        return default


def ok(message: str) -> None:
    _console.print(f"[green]✓[/green] {message}")


def fail(message: str) -> None:
    _console.print(f"[red]✗[/red] {message}")


def warn(message: str) -> None:
    _console.print(f"[yellow]{message}[/yellow]")


def dim(message: str) -> None:
    _console.print(f"[dim]{message}[/dim]")


def saved(path: Path) -> None:
    ok(f"saved to [dim]{path}[/dim]")


def cancelled() -> None:
    warn("cancelled")


def activity(message: str):
    return _console.status(f"[dim]{message}[/dim]")


def press_enter(message: str = "Press ENTER to continue") -> None:
    _console.print(f"[dim]{message}[/dim]", end="")
    try:
        input()
    except (KeyboardInterrupt, EOFError):
        pass


def ok_and_wait(message: str) -> None:
    _console.print("")
    ok(message)
    press_enter()


def fail_and_wait(message: str) -> None:
    _console.print("")
    fail(message)
    press_enter()


def saved_and_wait(path: Path) -> None:
    _console.print("")
    saved(path)
    press_enter()


_MARKUP_RE = __import__("re").compile(r"\[/?[^\]]*\]")


def _visible_len(s: str) -> int:
    return len(_MARKUP_RE.sub("", str(s)))


def columns(rows: Sequence[Sequence[str]], gap: int = 2) -> None:
    """Print rows with per-column widths computed from the widest cell.

    Each row is a sequence of cell strings (Rich markup allowed — the
    visible length is computed by stripping ``[tag]`` markers). The last
    column is never padded so long right-hand values (paths, URLs) don't
    force trailing whitespace.
    """
    if not rows:
        return
    ncols = max(len(r) for r in rows)
    widths = [0] * ncols
    for r in rows:
        for i, cell in enumerate(r):
            widths[i] = max(widths[i], _visible_len(cell))
    sep = " " * max(1, gap)
    for r in rows:
        parts: list[str] = []
        for i, cell in enumerate(r):
            if i < ncols - 1:
                pad = widths[i] - _visible_len(cell)
                parts.append(f"{cell}{' ' * pad}")
            else:
                parts.append(str(cell))
        _console.print(sep.join(parts))


def accent_style(accent: str):
    """Legacy — returns a prompt_toolkit Style or None. Retained because
    a couple of model-selector helpers still import it to tint prompts
    outside of ``menu()``."""
    if not accent or not accent.strip():
        return None
    try:
        from prompt_toolkit.styles import Style
    except Exception:  # noqa: BLE001
        return None
    return Style([
        ("pointer", f"fg:{accent.strip()} bold"),
    ])
