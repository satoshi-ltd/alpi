"""Shared UI primitives for every ``alf setup`` wizard + menu.

Every interactive prompt in alf passes through this module so the look
and feel stays uniform: same pointer (``◆``), same accent colour (from
``tui.accent`` of the active profile), same close/cancel wording, same
success/error affordances.

Rule (enforced by convention, not by code): ``alf/gateway/setup.py``,
``alf/email/setup.py``, ``alf/mcp/setup.py``, ``alf/model_selector.py``
and the top-level menus in ``alf/cli.py`` MUST use helpers from here.
Raw ``questionary.*`` calls are allowed only when the helper below
genuinely doesn't fit — and then a new helper should be considered.

**When to use which helper — this separation matters for UX:**

- ``menu()`` — full-screen navigation. Clears the screen, draws
  title + description + options, returns a choice. Use for top-level
  sections (``setup``, ``Gateways``, ``MCPs list``). Never inside a
  wizard flow: the clear wipes any fields the user already filled in.

- ``text() / password() / confirm()`` — inline prompts. Leave prior
  output on screen, append a line, return a value. Use inside wizards
  so the whole conversation stays visible while the user progresses
  through the fields. When a wizard needs to branch (keep vs.
  replace, etc.), do it with ``password()`` / ``text()`` hydration
  — ENTER keeps the default, typing replaces. Never reach for a
  nested ``menu()`` inside a wizard: the clear wipes context.

Terminology:

- ``Exit``   — closes the program. Used at the top-level menu only.
- ``Back``   — returns to the parent menu. Used inside sub-menus.
- ``cancelled`` — user aborted a multi-step wizard mid-flow.

Each menu item line follows the pattern:

    <label, padded to LABEL_WIDTH>  <bullet ·>  <status>

``Telegram       · ready · 2 allowlisted chats``
``Email          · not set up``

Status is optional; the padding ensures columns align across menus.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Sequence

import questionary
from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.text import Text
from rich.theme import Theme

# --------------------------------------------------------------------
# Palette
# --------------------------------------------------------------------
#
# Only five semantic colours are allowed anywhere in the UI:
#
#   accent   — profile identity, tints ``alf`` prefix + menu pointer
#   default  — normal text (terminal's foreground colour)
#   muted    — ``dim`` grey — hints, subtitles, Back/Exit, statuses
#   error    — ``red`` — rejected / failed
#   success  — ``green`` — saved / ok
#
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


# ----------------------------------------------------------------------
# Banners
# ----------------------------------------------------------------------


def crumb(*parts: str) -> str:
    """Build the canonical ``alf v<version> > section > subsection``
    breadcrumb used as the title of every menu and wizard.

    Version is pulled from ``alf.__version__`` so we keep it in one
    place — bumping alf's version auto-updates every screen. Empty
    parts are dropped so ``crumb("setup", "")`` and ``crumb("setup")``
    render the same.
    """
    from alf import __version__
    segments = [f"alf v{__version__}", *[p for p in parts if p]]
    return " › ".join(segments)


def banner(title: str, subtitle: str = "", hint: str = "",
           home: Path | None = None) -> None:
    """Clear-screen + render a wizard/menu header.

    The clear makes each navigation step a fresh canvas — hermes-style.
    Lose the accumulated scrollback of the previous screen, gain a
    clean focused view. Menus also emit the nav hint line inside
    ``menu()`` rather than here so plain text-only wizards (``email``
    setup, ``profile create``) don't get an irrelevant
    ``↑↓ ENTER ESC`` reminder.

    The ``alf`` prefix at the start of a breadcrumb title is tinted
    with the profile's ``tui.accent`` colour so the user has a
    consistent visual brand per profile — orange on ``default``, red
    on ``personal``, whatever they chose. Same colour already tints
    the menu pointer, so title + pointer feel of-a-piece.

    If alf's output isn't going to a TTY (CI, piped into another
    tool, or scripted), ``Console.clear()`` is a no-op — safe.
    """
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
    """Return the Rich-markup title with ``alf`` tinted by accent.

    Non-breadcrumb titles (anything that doesn't start with ``"alf "``)
    render plain-bold — we don't re-style arbitrary user-supplied
    strings.
    """
    accent = _accent_hex(home)
    if accent and title.startswith("alf "):
        return f"[b {accent}]alf[/b {accent}][b] {title[4:]}[/b]"
    return f"[b]{title}[/b]"


def _accent_hex(home: Path | None) -> str:
    """Return the profile's accent colour as a hex/name string, or ``""``.

    Shared lookup used by ``banner()`` and ``_style_for()`` so the
    pointer and the title always agree on the same shade.
    """
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
    """Build a menu-row title.

    Returns a list of ``(style, text)`` tuples when there's a status —
    that's the shape ``questionary.Choice.title`` renders as mixed
    styles. The status chunk carries the muted foreground so
    descriptions read quieter than labels. Plain-label rows stay
    strings (simpler for questionary and cheaper to construct).
    """
    if not status:
        return label
    left = f"{label:<{LABEL_WIDTH}}"
    return [
        ("", left),
        (_MUTED_STYLE, f" · {status}"),
    ]


# ----------------------------------------------------------------------
# Menus
# ----------------------------------------------------------------------


def menu(
    title: str,
    items: Sequence[Any],
    *,
    subtitle: str = "",
    home: Path | None = None,
    close: str = "Exit",
) -> Any:
    """Render a banner + a questionary.select + a muted close item.

    Visual shape (canonical across every alf menu):

        title                ← bold
        subtitle             ← dim (optional)
        {blank line}
         ◆ option
           option
           option
        {blank line}
           ← Back / Exit     ← dim

    ``items`` accepts:
    - ``(label, value)`` tuples → Choice
    - ``(label, value, status)`` tuples → Choice with a status suffix
    - a literal ``None`` → blank separator (visual gap inside the list)
    - a ``questionary.Choice`` / ``Separator`` — passed through

    Close label: ``"Exit"`` (top-level) or ``"Back"`` (sub-menu). The
    arrow is added automatically. Callers get ``None`` back when the
    user picks the close row or hits ESC.
    """
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


# ----------------------------------------------------------------------
# Input prompts
# ----------------------------------------------------------------------


def text(label: str, default: str = "") -> str | None:
    """Ask for free text. Rich's ``Prompt.ask`` renders cleanly
    without questionary's leading ``" "`` padding around the message,
    and shows the default in ``(brackets)`` — visible hydration with
    ENTER-keeps-it semantics, all in one line.

    Trailing ``":"`` or whitespace is stripped because rich appends
    its own ``": "`` suffix; callers passing ``"Email address:"``
    shouldn't end up with ``"Email address:: "`` on screen.
    """
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
    """Secret input with ``keep-current`` semantics.

    Uses ``getpass.getpass`` directly instead of rich's ``password=True``
    path. Rationale: rich's wrapper delegates to the same stdlib
    ``getpass`` but adds buffering and falls back to a mode that
    dropped keystrokes for some users (Warthog, iTerm with custom
    shell integrations). Going through ``getpass`` straight is more
    reliable and what hermes does for the same reason.

    Matches the text-input look: when a current value exists, the
    prompt itself carries an inline ``(…XXXX)`` hint with the last
    four characters of the current value, tinted with accent. ENTER
    keeps the existing value; typing replaces it.
    """
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
    """Build a rich ``Text`` prompt with ``(default)`` tinted in accent.

    Using ``rich.Text`` directly avoids pushing a theme layer onto
    the console — earlier attempts via ``Console.use_theme`` broke
    input handling on some terminals. With ``show_default=False``
    upstream, this is the *only* place the default renders, so the
    tint applies uniformly.
    """
    text = Text()
    text.append(label)
    if default:
        accent = _accent_hex(None) or "dim"
        text.append(" (")
        text.append(default, style=accent)
        text.append(")")
    return text


def _clean_label(label: str) -> str:
    """Drop trailing ``":"`` or whitespace so rich's own ``": "``
    suffix doesn't render a doubled colon."""
    return (label or "").rstrip(": \t\n")


def confirm(label: str, default: bool = True) -> bool:
    """Yes/No. Ctrl-C treats as ``default`` — same contract as before,
    just on top of rich.prompt now."""
    try:
        return Confirm.ask(label, default=default, console=_console)
    except (KeyboardInterrupt, EOFError):
        return default


# ----------------------------------------------------------------------
# Feedback — consistent success/error/status affordances
# ----------------------------------------------------------------------


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
    """Spinner context manager for slow operations.

    Use around network-bound work (IMAP login, MCP handshake, HTTP
    probes) so the user sees *something* happening instead of an
    apparent hang. Returns rich's status context unchanged — a no-op
    on non-interactive stdout.
    """
    return _console.status(f"[dim]{message}[/dim]")


def press_enter(message: str = "Press ENTER to continue") -> None:
    """Hold the current screen until the user acks.

    The parent menu clears on re-entry, which was eating wizard
    success/error output in a blink. This pause gives the user a
    moment to read the outcome before the next navigation frame.
    """
    _console.print(f"\n[dim]{message}[/dim]", end="")
    try:
        input()
    except (KeyboardInterrupt, EOFError):
        pass


# ----------------------------------------------------------------------
# Style resolution
# ----------------------------------------------------------------------


def accent_style(accent: str):
    """Return a prompt_toolkit Style that tints the ``◆`` pointer with
    ``accent`` (hex or named). Empty string returns None — questionary
    falls back to its built-in style.

    The ``class:close`` rule keeps the Back/Exit row muted even when the
    cursor lands on it — without this, questionary's default
    ``selected`` styling repaints the whole row in the accent colour.
    The close row is deliberately low-signal; highlighting it would
    defeat the whole reason it lives in a muted tone.
    """
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
    """Resolve the accent style for the profile at ``home``.

    If ``home`` is None, use the default resolution
    (``home.get_home()``). Failures fall back silently to questionary's
    default — never let a config hiccup prevent a menu from rendering.
    """
    try:
        from alf import config as config_mod
        from alf import home as home_mod
        resolved = home or home_mod.get_home()
        cfg = config_mod.load(resolved)
        return accent_style((cfg.tui or {}).get("accent", ""))
    except Exception:  # noqa: BLE001
        return None


# ----------------------------------------------------------------------
# ESC-aware question asker (single place)
# ----------------------------------------------------------------------


def _ask(question) -> Any:
    """Invoke a questionary prompt with ESC bound to cancel.

    Returns ``None`` on cancel (ESC, Ctrl-C, or a bare exit). Every
    helper above funnels through here so the cancel contract is
    uniform across the app.
    """
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
