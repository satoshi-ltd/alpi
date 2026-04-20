"""Shared UI primitives for every ``alf setup`` wizard + menu."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Sequence

import questionary
from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.text import Text
from rich.theme import Theme

# Palette
# Only five semantic colours are allowed anywhere in the UI:
#   accent   — profile identity, tints ``alf`` prefix + menu pointer
#   default  — normal text (terminal's foreground colour)
#   muted    — ``dim`` grey — hints, subtitles, Back/Exit, statuses
#   error    — ``red`` — rejected / failed
#   success  — ``green`` — saved / ok
# Everything else (rich's default magenta for ``[brackets]`` prompt
# defaults, cyan for quoted strings, blue for URLs, yellow for
# repr numbers) is explicitly overridden below so the setup flow
# looks consistent instead of the Python REPL of colours rich ships
# by default.

_THEME = Theme(
    {
        # Semantic aliases.
        "muted": "dim",
        "error": "red",
        "success": "green",
        # Strip rich's rainbow defaults — all the prompt chrome drops
        # to dim so it reads as "contextual info, not actionable".
        "prompt": "default",
        "prompt.default": "dim",
        "prompt.choices": "dim",
        "prompt.invalid": "red",
        "prompt.invalid.choice": "red",
        # Kill rich's repr auto-highlighting (`"quoted"` in cyan,
        # numbers in yellow, URLs in blue, etc.). We want plain text
        # unless we marked it up explicitly.
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

# ``highlight=False`` also disables rich's automatic regex-based repr
# detection, so ``'some string'`` stops coming out cyan even when it
# matches rich's Python-literal patterns.
_console = Console(theme=_THEME, highlight=False)

# Muted foreground for Back/Exit labels so they fade compared to the
# action rows. Neutral grey works on light and dark terminals.
_MUTED_STYLE = "fg:#888888"

# Sentinel used as the Choice.value for the auto-appended close row.
# Can't be ``None`` — questionary.Choice treats ``value=None`` as
# "unset" and falls back to the title, which for our FormattedText
# close label resolves to the string "← Back" / "← Exit". Using a
# unique object avoids that collision and lets ``menu()`` return
# ``None`` to the caller consistently.
_CLOSE_SENTINEL = object()

# Width used for menu labels before the status ``·`` separator. Chosen
# so the longest label in any current menu (``Model / Provider``,
# ``OpenRouter``, ``Telegram``, ``filesystem``) fits without truncation
# while still leaving a single alignment grid across screens.
LABEL_WIDTH = 16

POINTER = "◆"
NAV_HINT = "(↑↓ navigate  ENTER select  ESC cancel)"



def crumb(*parts: str) -> str:
    """Build the canonical ``alf v<version> > section > subsection``"""
    from alf import __version__
    segments = [f"alf v{__version__}", *[p for p in parts if p]]
    return " › ".join(segments)


def banner(title: str, subtitle: str = "", hint: str = "",
           home: Path | None = None) -> None:
    """Clear-screen + render a wizard/menu header."""
    _console.clear()
    # Title + description on ONE line: breadcrumb bold (with ``alf``
    # accent-tinted), then a muted ``› description`` tail. Keeps the
    # header tight — every screen starts with 1 canonical line of
    # context instead of 2 competing ones.
    line = _render_title(title, home=home)
    if subtitle:
        line += f"[dim] › {subtitle}[/dim]"
    _console.print(line)
    if hint:
        _console.print(f"[dim]{hint}[/dim]")
    _console.print("")


def _render_title(title: str, *, home: Path | None) -> str:
    accent = _accent_hex(home)
    if accent and title.startswith("alf "):
        return f"[b {accent}]alf[/b {accent}][b] {title[4:]}[/b]"
    return f"[b]{title}[/b]"


def _accent_hex(home: Path | None) -> str:
    try:
        from alf import config as config_mod
        from alf import home as home_mod
        resolved = home or home_mod.get_home()
        cfg = config_mod.load(resolved)
        return (cfg.tui or {}).get("accent", "") or ""
    except Exception:  # noqa: BLE001
        return ""


# Trailing ``(...)`` inside a label — stripped when a default is
# already supplied since the hint is only useful on first setup.
_TRAILING_PAREN = __import__("re").compile(r"\s*\([^)]*\)\s*$")


def row(label: str, status: str = ""):
    """Build a menu-row title."""
    if not status:
        return label
    left = f"{label:<{LABEL_WIDTH}}"
    return [
        ("", left),
        (_MUTED_STYLE, f" · {status}"),
    ]



def menu(
    title: str,
    items: Sequence[Any],
    *,
    subtitle: str = "",
    home: Path | None = None,
    close: str = "Exit",
) -> Any:
    """Render a banner + a questionary.select + a muted close item."""
    if title:
        # Canonical header block:
        #   alf v0.1.0 › setup › gateways › inbound channels alf listens on   ← bold crumb + muted tail
        #   (↑↓ navigate  ENTER select  ESC cancel)                           ← muted hint
        # Questionary renders an (empty) prompt line of its own right
        # below — that's the single separator between header and
        # options. Printing our own blank here doubled the gap.
        _console.clear()
        line = _render_title(title, home=home)
        if subtitle:
            line += f"[dim] › {subtitle}[/dim]"
        _console.print(line)
        _console.print(f"[dim]{NAV_HINT}[/dim]")

    style = _style_for(home)
    choices = []
    for item in items:
        if item is None:
            choices.append(questionary.Separator(" "))
        elif isinstance(item, (questionary.Choice, questionary.Separator)):
            choices.append(item)
        elif isinstance(item, tuple):
            if len(item) == 3:
                label, value, status = item
                choices.append(questionary.Choice(
                    title=row(str(label), str(status or "")),
                    value=value,
                ))
            elif len(item) == 2:
                label, value = item
                # Labels can be either plain strings OR pre-built
                # ``row()`` output (a list of ``(style, text)`` tuples
                # for mixed styling). str()-ing the list would turn
                # it into Python ``repr`` — which is exactly what the
                # user saw rendered verbatim in the menu. Pass lists
                # through; only coerce genuinely bare values.
                if isinstance(label, (list, str)):
                    choices.append(questionary.Choice(title=label, value=value))
                else:
                    choices.append(questionary.Choice(title=str(label), value=value))
        else:
            # Bare string — use as both label and value.
            choices.append(questionary.Choice(title=str(item), value=item))

    # Close item — separated from content by a blank separator, and
    # rendered in a muted colour so it visually fades to the
    # background. The ``class:separator`` tag is applied to the row so
    # our stylesheet below can dim it without having to patch every
    # caller.
    if close:
        # Close sits directly below the last option — no blank
        # separator above it. The muted colour already sets it apart
        # visually; adding a gap just wastes vertical space.
        choices.append(questionary.Choice(
            title=[(f"class:close {_MUTED_STYLE}", close)],
            value=_CLOSE_SENTINEL,
        ))

    # Empty ``message`` + ``qmark=""`` yields no duplicate prompt line
    # above the choices — the banner IS the title.
    result = _ask(questionary.select(
        "",
        choices=choices,
        qmark="",
        pointer=POINTER,
        style=style,
        instruction=" ",
    ))
    # Questionary's post-selection echo renders the chosen title under
    # ``class:answer`` and leaves it on screen. Style overrides can
    # recolour it but not hide it — so we wipe the line ourselves
    # (cursor up one row, erase entire line, cursor to column 0) the
    # moment the prompt returns. Downstream wizards can then print
    # straight into the vacated spot and the selection reads as a
    # transient choice, not a persistent headline.
    try:
        # Trailing newline keeps the wiped line as a visible blank
        # separator between the menu above and whatever prompt comes
        # next — otherwise downstream output glues against the nav
        # hint and the page reads cramped.
        sys.stdout.write("\033[1A\033[2K\r\n")
        sys.stdout.flush()
    except Exception:  # noqa: BLE001
        pass
    if result is _CLOSE_SENTINEL:
        return None
    return result



def text(label: str, default: str = "") -> str | None:
    """Ask for free text. Rich's ``Prompt.ask`` renders cleanly"""
    clean = _clean_label(label)
    if default:
        # User has a hydrated value — strip any trailing ``(...)``
        # hint from the label. The ``(e.g. ...)`` reminder is useful
        # on first setup and noise once the user knows the format.
        clean = _TRAILING_PAREN.sub("", clean).rstrip()
    try:
        prompt_arg = _styled_prompt(clean, default)
        return Prompt.ask(
            prompt_arg,
            default=default or None,
            show_default=not bool(default),  # we embed it styled ourselves
            console=_console,
        )
    except (KeyboardInterrupt, EOFError):
        return None


def password(label: str, current: str = "") -> str | None:
    """Secret input with ``keep-current`` semantics."""
    import getpass

    clean = _clean_label(label)
    if current:
        clean = _TRAILING_PAREN.sub("", clean).rstrip()

    # Render the prompt (with optional styled hint) via rich so the
    # accent colour still applies — then feed an EMPTY string as the
    # getpass prompt so it doesn't print anything of its own.
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
    """Yes/No prompt. Ctrl-C returns ``default``."""
    try:
        return Confirm.ask(label, default=default, console=_console)
    except (KeyboardInterrupt, EOFError):
        return default


# Feedback — consistent success/error/status affordances


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
    """Spinner context manager for slow operations."""
    return _console.status(f"[dim]{message}[/dim]")


def press_enter(message: str = "Press ENTER to continue") -> None:
    """Hold the current screen until the user acks."""
    _console.print(f"\n[dim]{message}[/dim]", end="")
    try:
        input()
    except (KeyboardInterrupt, EOFError):
        pass



def accent_style(accent: str):
    """Return a prompt_toolkit Style that tints the ``◆`` pointer with"""
    if not accent or not accent.strip():
        return None
    try:
        from prompt_toolkit.styles import Style
    except Exception:  # noqa: BLE001
        return None
    return Style([
        ("pointer", f"fg:{accent.strip()} bold"),
        # Questionary applies ``class:highlighted`` (not ``selected``)
        # to the row under the cursor. Pin both variants to the muted
        # grey so the Back/Exit title never flashes in the accent tint.
        ("close", _MUTED_STYLE),
        ("highlighted close", _MUTED_STYLE),
        ("selected close", _MUTED_STYLE),
    ])


def _style_for(home: Path | None):
    try:
        from alf import config as config_mod
        from alf import home as home_mod
        resolved = home or home_mod.get_home()
        cfg = config_mod.load(resolved)
        return accent_style((cfg.tui or {}).get("accent", ""))
    except Exception:  # noqa: BLE001
        return None


# ESC-aware question asker (single place)


def _ask(question) -> Any:
    try:
        app = question.application
        app.key_bindings.add("escape", eager=True)(
            lambda event: event.app.exit(result=None)
        )
    except Exception:  # noqa: BLE001
        pass
    try:
        return question.unsafe_ask()
    except KeyboardInterrupt:
        return None
