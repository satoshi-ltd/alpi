from gen import DANGER, DOC_ACCENT, diamond, ic, page
from desktop_boards import (ALPI_ACCENT, AMBER, HOVER, INK, INK2, INK3, INK4, LINE, LINE2, MONO, PANE, SELECTED, SIDE, button, d_sidebar, diamond_stack, eyebrow, field_input,
                            iconbtn, kbd, key_hint, palette, palette_row, selectish, small_diamond)

SHADOW = "0 0 0 0.5px rgba(11,17,23,0.08), 0 18px 50px rgba(11,17,23,0.10)"


def panel(title, inner, w, h, bg=SIDE):
    return (f'<div style="display: flex; flex-direction: column; gap: 10px; width: {w}px; flex-shrink: 0">'
            f'<span style="font-family: {MONO}; font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase; color: {INK3}">{title}</span>'
            f'<div style="position: relative; width: {w}px; height: {h}px; border-radius: 12px; background: {bg}; border: 0.5px solid {LINE}; overflow: hidden; box-sizing: border-box">{inner}</div></div>')


def raw_select(value, w=200):
    return (f'<span style="display: inline-flex; align-items: center; justify-content: space-between; width: {w}px; height: 38px; padding: 0 10px; box-sizing: border-box; '
            f'border-radius: 6px; border: 1px solid {LINE2}; background: #ffffff; font-family: -apple-system, system-ui, sans-serif; font-size: 13px; color: {INK}">{value}{ic("chev-d", 12, INK3)}</span>')


def native_select(value):
    return (f'<span style="display: inline-flex; align-items: center; gap: 18px; height: 22px; padding: 0 8px; border-radius: 5px; border: 1px solid #8f8f8f; '
            f'background: linear-gradient(#ffffff, #ededed); font-family: -apple-system, system-ui, sans-serif; font-size: 13px; color: #000000">{value}{ic("chev-d", 10, "#000000")}</span>')


def dropdown_trigger(label):
    return selectish(f'<span style="max-width: 240px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap">{label}</span>', mono=False)


def ds_field(value, w=200):
    return (f'<span style="display: inline-flex; align-items: center; width: {w}px; height: 32px; padding: 0 12px; box-sizing: border-box; border-radius: 8px; '
            f'background: #ffffff; border: 0.5px solid {LINE2}; font-size: 13px; color: {INK}">{value}</span>')


def checkbox(on=False):
    return (f'<span style="width: 16px; height: 16px; border-radius: 4px; box-sizing: border-box; display: inline-flex; align-items: center; justify-content: center; '
            f'border: 1.5px solid {INK if on else INK4}; background: {INK if on else "transparent"}">{ic("check", 12, PANE) if on else ""}</span>')


def label_row(label, control):
    return f'<div style="display: flex; flex-direction: column; gap: 6px"><span style="font-size: 12px; color: {INK3}">{label}</span>{control}</div>'


def dialog_footer(primary, secondary="Cancel", variant="primary"):
    return f'<div style="display: flex; justify-content: flex-end; gap: 8px; margin-top: 10px">{button(secondary, "ghost")}{button(primary, variant)}</div>'


def modal(title, body, footer, w=520, x=40, y=28):
    return (f'<div style="position: absolute; inset: 0; background: rgba(11,17,23,0.32)"></div>'
            f'<div style="position: absolute; left: {x}px; top: {y}px; width: {w}px; box-sizing: border-box; border-radius: 14px; padding: 24px; background: {PANE}; '
            f'border: 0.5px solid {LINE2}; box-shadow: {SHADOW}; display: flex; flex-direction: column; gap: 8px">'
            f'<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px"><span style="font-size: 18px; font-weight: 600; letter-spacing: -0.005em; color: {INK}">{title}</span></div>'
            f'{body}{footer}</div>')


def edit_connection_panel():
    profiles = "".join(f'<label style="display: inline-flex; align-items: center; gap: 8px; font-size: 13px; color: {INK}">{checkbox(on)}{name}</label>'
                       for name, on in (("doc", True), ("abby", True), ("etxea", False)))
    profiles_row = f'<div style="display: flex; gap: 16px">{profiles}</div>'
    body = (f'<div style="display: flex; flex-direction: column; gap: 14px">'
            f'{label_row("Label", ds_field("phone", 472))}'
            f'<div style="display: flex; gap: 16px">{label_row("Role", dropdown_trigger("Member"))}{label_row("Sessions", dropdown_trigger("Shared across its devices"))}</div>'
            f'{label_row("Profiles", profiles_row)}'
            f'</div>')
    inner = modal("Edit connection", body, dialog_footer("Save"))
    return panel("Modal · edit connection (Dropdown field for role and sessions)", inner, 600, 360)


def dropdown_row(label, caption="", active=False):
    cap = f'<span style="font-family: {MONO}; font-size: 11px; color: {INK3}; margin-top: 4px">{caption}</span>' if caption else ""
    return (f'<div style="display: flex; flex-direction: column; padding: 8px 10px; border-radius: 8px; background: {SELECTED if active else "transparent"}">'
            f'<span style="font-size: 13px; color: {INK}">{label}</span>{cap}</div>')


def dropdown_panel():
    menu = "".join(dropdown_row(*r) for r in (("Default", "use provider default"), ("Low", "fastest, cheapest"), ("Medium", "balanced", True), ("High", "slower, more thorough")))
    model = button('deepseek-v4.1-flash', "ghost", "md", icon="chip").replace("font-family: Geist, sans-serif", f"font-family: {MONO}").replace("font-size: 13px", "font-size: 12px")
    inner = (f'<div style="padding: 28px 32px; display: flex; flex-direction: column; gap: 22px; background: {PANE}; height: 100%; box-sizing: border-box">'
             f'<div style="display: flex; align-items: center; gap: 24px"><span style="width: 120px; font-family: {MONO}; font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase; color: {INK3}">Fast model</span>{model}{dropdown_trigger("medium")}</div>'
             f'<div style="display: flex; align-items: center; gap: 24px"><span style="width: 120px; font-family: {MONO}; font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase; color: {INK3}">Reasoning</span>'
             f'<div style="position: relative">{dropdown_trigger("medium")}'
             f'<div style="position: absolute; left: 0; top: 38px; width: 280px; padding: 6px; box-sizing: border-box; border-radius: 12px; background: {PANE}; border: 0.5px solid {LINE2}; box-shadow: {SHADOW}">{menu}</div>'
             f'</div></div></div>')
    return panel("Dropdown field · open, current choice highlighted, beside a ModelPicker", inner, 600, 360)


def menu_item(icon, label, danger=False, hint=""):
    return (f'<div style="display: flex; align-items: center; gap: 10px; padding: 6px 10px; border-radius: 6px; font-size: 13px; color: {DANGER if danger else INK}">'
            f'{ic(icon, 14, DANGER if danger else INK3)}<span style="flex: 1">{label}</span>{key_hint(hint) if hint else ""}</div>')


def menu_sep():
    return f'<div style="height: 1px; background: {LINE}; margin: 4px 6px"></div>'


def context_menu_panel():
    menu = (f'<div style="position: absolute; left: 130px; top: 150px; width: 210px; padding: 4px; box-sizing: border-box; border-radius: 10px; background: {PANE}; border: 0.5px solid {LINE2}; box-shadow: {SHADOW}">'
            f'{menu_item("pin", "Pin to top")}{menu_sep()}{menu_item("gear", "Open settings", hint="⌘,")}{menu_sep()}{menu_item("trash", "Delete workgroup…", danger=True)}</div>')
    inner = f'<div style="display: flex; height: 100%">{d_sidebar(300, selected="", wg_selected=True)}<div style="flex: 1; background: {PANE}"></div></div>{menu}'
    return panel("Context menu · pin, settings, delete", inner, 356, 300)


def confirm_panel():
    body = (f'<span style="font-size: 13px; line-height: 1.5; color: {INK2}">Permanently removes <span style="font-family: {MONO}">~/.alpi/profiles/doc/</span> — identity, memory, skills, schedule and chat history. This cannot be undone.</span>'
            f'<div style="display: flex; flex-direction: column; gap: 6px; margin-top: 8px"><span style="font-family: {MONO}; font-size: 11px; letter-spacing: 0.06em; color: {INK3}">TYPE <b style="color: {INK}">doc</b> TO CONFIRM</span>{ds_field("d", 352)}</div>')
    inner = modal("Delete profile @doc", body, dialog_footer("Delete profile", variant="danger"), w=400, x=28, y=24)
    return panel("ConfirmDelete · typed, submits on Enter", inner, 456, 300)


def ask_panel():
    from conversation_boards import inline_ask
    inner = f'<div style="padding: 20px; background: {PANE}; height: 100%; box-sizing: border-box">{inline_ask(question="Which lab should I book?")}</div>'
    return panel("Inline question · asked in the open chat", inner, 376, 300)


def scrim_frame(title, shell, w, h, top=28):
    inner = (f'<div style="position: absolute; inset: 0; background: {SIDE}"></div><div style="position: absolute; inset: 0; background: rgba(11,17,23,0.20)"></div>'
             f'<div style="position: absolute; left: 0; right: 0; top: {top}px; display: flex; justify-content: center">{shell}</div>')
    return panel(title, inner, w, h)


def shell(inner, w):
    return (f'<div style="width: {w}px; border-radius: 14px; background: #ffffff; border: 0.5px solid {LINE2}; box-shadow: {SHADOW}; overflow: hidden; display: flex; flex-direction: column">{inner}</div>')


def sheet_head(icon, title, keys, pad_left=16):
    glyph = ic(icon, 14, INK) if icon else ""
    return (f'<div style="display: flex; align-items: center; gap: 8px; padding: 10px 12px 10px {pad_left}px; border-bottom: 0.5px solid {LINE}">'
            f'{glyph}<span style="flex: 1; font-size: 13px; font-weight: 600; color: {INK}">{title}</span>{key_hint(keys)}{iconbtn("x", "Close", 28, 14)}</div>')


def activity_row(glyph, title, sub, tone=None, action=""):
    color = {"warning": "#8a5a0a", "danger": DANGER, "accent": ALPI_ACCENT}.get(tone, INK3)
    return (f'<li style="display: flex; align-items: center; gap: 8px; padding-right: 8px; border-radius: 8px">'
            f'<span style="flex: 1; min-width: 0; display: flex; align-items: center; gap: 10px; padding: 8px 10px">'
            f'<span style="width: 16px; display: inline-flex; justify-content: center; flex-shrink: 0; color: {color}">{glyph(color)}</span>'
            f'<span style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px"><span style="font-size: 13px; color: {INK}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis">{title}</span>'
            f'<span style="font-family: {MONO}; font-size: 11px; color: {INK3}">{sub}</span></span></span>{action}</li>')


def activity_group(label, rows):
    return (f'<section aria-label="{label}" style="margin-top: 8px"><h3 style="margin: 0; padding: 12px 10px 6px">{eyebrow(label)}</h3>'
            f'<ul style="margin: 0; padding: 0; list-style: none">{"".join(rows)}</ul></section>')


def activity_panel_shell():
    review = button("Review", "primary", "sm")
    icon = lambda name: lambda c: ic(name, 14, c)
    body = (activity_group("Needs you · 2", [
                activity_row(icon("alert"), "abby · wants to run a command", "approval · 2m ago", "warning", review),
                activity_row(icon("alert"), "doc · Which lab should I book with?", "question · just now", "warning", review)])
            + activity_group("Running · 2", [
                activity_row(lambda c: diamond_stack(DOC_ACCENT), "alpha · #collect", "phase 3 of 4", "accent"),
                activity_row(lambda c: small_diamond(AMBER, 8), "alpi · Summarize yesterday’s deploys", "4m", "accent")])
            + activity_group("Scheduled", [
                activity_row(icon("x"), "clonara · weekly labs", "failed 3h ago", "danger"),
                activity_row(icon("clock"), "doc · Daily brief", "tomorrow 07:00")]))
    return shell(sheet_head("history", "Activity", "⌘J") + f'<div style="padding: 0 8px 12px">{body}</div>', 460)


SHORTCUT_GROUPS = (
    ("General", (("Command palette", "⌘K"), ("Keyboard shortcuts", "⌘/"), ("Activity", "⌘J"), ("Jump to profile / workgroup", "⌘1–9"), ("Filter profiles &amp; workgroups", "⌘S"), ("Open or close settings", "⌘,"), ("Notifications", "⌘O"))),
    ("Chat", (("New session", "⌘N"), ("Send message", "⌘↵"), ("Find in transcript", "⌘F"), ("Read aloud", "⇧⌘L"))),
    ("Profile or workgroup", (("Sessions · task history", "⇧⌘H"), ("Refresh thread", "⇧⌘R"), ("Pause or resume", "⇧⌘P"))),
    ("Profile", (("Tools", "⇧⌘T"), ("Skills", "⇧⌘S"), ("Memory", "⇧⌘M"), ("Schedule", "⇧⌘E"))),
    ("Create", (("New profile", "⇧⌘N"), ("New workgroup", "⇧⌘W"))),
    ("View", (("Zoom in", "⌘+"), ("Zoom out", "⌘-"), ("Reset zoom", "⌘0"), ("Close / dismiss", "Esc"))),
)


def shortcuts_shell():
    groups = "".join(
        f'<section aria-label="{g}"><h3 style="margin: 0; padding: 14px 0 6px">{eyebrow(g)}</h3>'
        + "".join(f'<div style="display: flex; align-items: center; justify-content: space-between; gap: 10px; min-height: 28px; border-bottom: 0.5px solid {LINE}"><span style="font-size: 13px; color: {INK2}">{t}</span>{key_hint(k)}</div>' for t, k in items)
        + '</section>' for g, items in SHORTCUT_GROUPS)
    body = f'<div style="display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 6px 24px; padding: 8px 20px 20px">{groups}</div>'
    return shell(sheet_head("", "Keyboard shortcuts", "⌘/", 20) + body, 620)


def palette_idle():
    glyph = lambda name: ic(name, 14, INK3)
    return palette("", [
        ("General", [palette_row(glyph("search"), "Command palette", hint="⌘K", selected=True), palette_row(glyph("more"), "Keyboard shortcuts", hint="⌘/"),
                     palette_row(glyph("history"), "Activity", hint="⌘J"), palette_row(glyph("search"), "Filter profiles &amp; workgroups", hint="⌘S")]),
        ("Chat", [palette_row(glyph("plus"), "New session", hint="⌘N"), palette_row(glyph("search"), "Find in transcript", hint="⌘F"), palette_row(glyph("refresh"), "Refresh thread", hint="⇧⌘R")]),
    ])


def palette_search():
    return palette("doc", [
        ("Profiles", [palette_row(small_diamond(DOC_ACCENT, 8), "doc", "profile", "⌘1", selected=True, hit="doc")]),
        ("Workgroups", [palette_row(diamond_stack(INK3), "alpha", "#doc", "⌘9")]),
        ("Sessions", [palette_row(ic("clock", 14, INK3), "Draft the doctor letter", "@doc · 2h", hit="doc"), palette_row(ic("clock", 14, INK3), "Lipid panel review", "@doc · 3d")]),
    ])


def desktop_overlays():
    body = (f'<div style="padding: 28px 32px; display: flex; flex-direction: column; gap: 24px; box-sizing: border-box">'
            f'<div style="display: flex; flex-direction: column; gap: 4px"><span style="font-size: 22px; font-weight: 600; letter-spacing: -0.018em">Desktop overlays as of 0.7.0</span>'
            f'<span style="font-size: 13px; color: {INK3}; max-width: 900px; line-height: 1.5">Palette, Activity and shortcuts share one Scrim and PanelShell; shortcuts render as KeyHint chips everywhere. Modals, dropdowns and menus register on useOverlay so Escape, focus and layering behave the same.</span></div>'
            f'<div style="display: flex; gap: 16px">{scrim_frame("Command palette ⌘K · commands with KeyHint chips", palette_idle(), 600, 400)}{scrim_frame("Command palette · a query searches profiles, workgroups and sessions", palette_search(), 600, 400)}</div>'
            f'<div style="display: flex; gap: 16px">{scrim_frame("Activity ⌘J · needs you, running, scheduled", activity_panel_shell(), 520, 700)}{scrim_frame("Keyboard shortcuts ⌘/", shortcuts_shell(), 680, 700)}</div>'
            f'<div style="display: flex; gap: 16px">{edit_connection_panel()}{dropdown_panel()}</div>'
            f'<div style="display: flex; gap: 14px">{context_menu_panel()}{confirm_panel()}{ask_panel()}</div></div>')
    return page("Desktop · overlays", 1280, OVERLAYS_H, body)


OVERLAYS_H = 2090
