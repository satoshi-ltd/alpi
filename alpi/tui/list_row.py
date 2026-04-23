"""Shared list-row rendering for TUI panels.

Every floating panel that shows a list of items (models, providers,
tools, MCP servers, skills, approval choices) renders each row in the
same shape as the CLI ``alpi/ui.py::row`` helpers:

    <name padded to column width>  · <muted description>

with the active entry (the currently-configured model, the running
provider, …) rendered in the profile accent. The cursor highlight is a
separate concern owned by Textual's OptionList.

The helpers below build the Rich Text for one row and the list of
``Option`` objects for an OptionList. Panels that are display-only
(``/tools``, ``/mcps``, ``/skills``) use ``row_text`` directly with a
Static widget per row.
"""

from __future__ import annotations

from rich.text import Text
from textual.widgets.option_list import Option

_FLOOR = 14
_MUTED = "dim"
_SEP = "  · "
_ACTIVE_GLYPH = "◆ "
_INACTIVE_PAD = "  "


def name_width(names: list[str], floor: int = _FLOOR) -> int:
    """Column width for the name slot — max of ``names``, clamped to a floor."""
    widest = max((len(n) for n in names), default=0)
    return max(floor, widest)


def row_text(name: str, description: str, *, active: bool = False,
             width: int, accent: str | None = None,
             with_marker: bool = True) -> Text:
    """Render one row as Rich Text in the CLI list shape.

    If ``with_marker`` is True, every row starts with a two-character
    prefix slot so the active one (``◆`` in the profile accent) aligns
    with the inactive ones (two spaces). If the list has no concept of
    active (``/help`` command palette), pass ``with_marker=False`` so
    rows start at column 0 and align with the section header.

    Rows never wrap to a second line in narrow terminals — descriptions
    are ellipsis-truncated instead. A two-line row looks broken next to
    a single-line sibling; one line + "…" is the lesser evil.
    """
    t = Text(no_wrap=True, overflow="ellipsis")
    if with_marker:
        if active and accent:
            t.append(_ACTIVE_GLYPH, style=accent)
        else:
            t.append(_INACTIVE_PAD)
    t.append(name.ljust(width))
    if description:
        t.append(_SEP + description, style=_MUTED)
    return t


def build_options(items: list[tuple[str, str, str]], *,
                  active_key: str | None = None,
                  accent: str | None = None,
                  floor: int = _FLOOR,
                  with_marker: bool | None = None) -> list[Option]:
    """Turn ``[(key, name, description), …]`` into OptionList options.

    ``with_marker`` defaults to True when an ``active_key`` is given,
    False otherwise. Callers that want the active-marker slot even with
    no preselection can pass ``with_marker=True`` explicitly.
    """
    if with_marker is None:
        with_marker = active_key is not None
    width = name_width([n for _, n, _ in items], floor=floor)
    out: list[Option] = []
    for key, n, desc in items:
        out.append(Option(
            row_text(n, desc, active=(key == active_key),
                     width=width, accent=accent, with_marker=with_marker),
            id=key,
        ))
    return out
