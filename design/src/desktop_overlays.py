from gen import DANGER, DOC_ACCENT, FOCUS_OUT, R_XS, R_CONTROL, R_SURFACE, R_SHEET, di as ic, identity_glyph, page, profile_mark
from desktop_boards import (FILL, FLOAT, ALPI_ACCENT, AMBER, EDGE, ELEV, RING, INK, INK2, INK3, LINE2, MONO, PANE, SELECTED, SIDE, button, d_sidebar, wg_mark, eyebrow, iconbtn, kbd, key_hint, palette, palette_row, selectish)

SHADOW = RING
VEIL = "var(--veil, rgba(20, 20, 20, 0.22))"
MENU_R = R_SURFACE


def panel(title, inner, w, h, bg=SIDE):
    return (f'<div style="display: flex; flex-direction: column; gap: 10px; width: {w}px; flex-shrink: 0">'
            f'<span style="font-size: 14px; color: {INK3}">{title}</span>'
            f'<div style="position: relative; width: {w}px; height: {h}px; border-radius: 12px; background: {bg}; box-shadow: 0 0 0 0.5px {LINE2}; overflow: hidden; box-sizing: border-box">{inner}</div></div>')


def raw_select(value, w=200):
    return (f'<span style="display: inline-flex; align-items: center; justify-content: space-between; width: {w}px; height: 38px; padding: 0 10px; box-sizing: border-box; '
            f'border-radius: 6px; border: 1px solid {LINE2}; background: #ffffff; font-family: -apple-system, system-ui, sans-serif; font-size: 15px; color: {INK}">{value}{ic("chev-d", 12, INK3)}</span>')


def native_select(value):
    return (f'<span style="display: inline-flex; align-items: center; gap: 18px; height: 22px; padding: 0 8px; border-radius: 5px; border: 1px solid #8f8f8f; '
            f'background: linear-gradient(#ffffff, #EDEDED); font-family: -apple-system, system-ui, sans-serif; font-size: 15px; color: #000000">{value}{ic("chev-d", 10, "#000000")}</span>')


def dropdown_trigger(label):
    return selectish(f'<span style="max-width: 240px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap">{label}</span>', mono=False)


def ds_field(value, w=200, focus=False):
    ring = f"box-shadow: inset 0 0 0 1.5px {INK3};" if focus else ""
    return (f'<span style="display: inline-flex; align-items: center; width: {w}px; height: 40px; padding: 0 14px; box-sizing: border-box; border-radius: {R_CONTROL}px; '
            f'background: var(--well, {FILL}); {ring} font-size: 15px; color: {INK}">{value}</span>')


def checkbox(on=False, focus=False, disabled=False):
    extra = (f"; {FOCUS_OUT}" if focus else "") + ("; opacity: 0.45" if disabled else "")
    edge = "" if on else f"box-shadow: inset 0 0 0 1.5px {EDGE}; "
    return (f'<span role="checkbox" aria-checked="{"true" if on else "false"}" style="width: 20px; height: 20px; border-radius: {R_XS}px; box-sizing: border-box; display: inline-flex; align-items: center; justify-content: center; '
            f'{edge}background: {AMBER if on else "transparent"}{extra}">{ic("check", 16, PANE) if on else ""}</span>')


def radio(on=False):
    if on:
        return f'<span role="radio" aria-checked="true" style="width: 20px; height: 20px; border-radius: 999px; display: inline-flex; align-items: center; justify-content: center; background: {AMBER}"><span style="width: 8px; height: 8px; border-radius: 999px; background: {PANE}"></span></span>'
    return f'<span role="radio" aria-checked="false" style="width: 20px; height: 20px; border-radius: 999px; box-sizing: border-box; display: inline-flex; box-shadow: inset 0 0 0 1.5px {EDGE}"></span>'


def label_row(label, control):
    return f'<div style="display: flex; flex-direction: column; gap: 6px"><span style="font-size: 14px; color: {INK3}">{label}</span>{control}</div>'


def dialog_footer(primary, secondary="Cancel", variant="primary"):
    return (f'<div data-dialog-footer="" style="display: flex; justify-content: flex-end; gap: 8px; margin-top: 12px">'
            f'{button(secondary, "secondary")}{button(primary, variant)}</div>')


def modal(title, body, footer, w=520, x=40, y=28):
    return (f'<div style="position: absolute; inset: 0; background: {VEIL}"></div>'
            f'<div role="dialog" style="position: absolute; left: {x}px; top: {y}px; width: {w}px; box-sizing: border-box; border-radius: {R_SHEET}px; padding: 24px; overflow: hidden; background: {ELEV}; --well: var(--well-float); '
            f'{FLOAT}; display: flex; flex-direction: column; gap: 12px">'
            f'<span style="font-size: 20px; font-weight: 600; line-height: 1.25; color: {INK}">{title}</span>'
            f'{body}{footer}</div>')


def edit_connection_panel():
    profiles = "".join(f'<label style="display: inline-flex; align-items: center; gap: 8px; font-size: 15px; color: {INK}">{checkbox(on)}{name}</label>'
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
    cap = f'<span style="font-size: 14px; color: {INK3}; white-space: nowrap">{caption}</span>' if caption else ""
    mark = ic("check", 16, INK) if active else ""
    return (f'<div role="menuitemradio" aria-checked="{"true" if active else "false"}" style="display: flex; align-items: center; gap: 12px; height: 40px; padding: 0 12px; box-sizing: border-box; border-radius: {R_CONTROL}px; background: {SELECTED if active else "transparent"}">'
            f'<span style="width: 20px; display: inline-flex; justify-content: center; flex-shrink: 0">{mark}</span>'
            f'<span style="flex: 1; font-size: 15px; font-weight: 400; color: {INK}">{label}</span>{cap}</div>')


def dropdown_panel():
    menu = "".join(dropdown_row(*r) for r in (("Default", "use provider default"), ("Low", "fastest, cheapest"), ("Medium", "balanced", True), ("High", "slower, more thorough")))
    model = button('deepseek-v4.1-flash', "ghost", "md", icon="chip").replace("font-family: Geist, sans-serif", f"font-family: {MONO}").replace("font-size: 15px", "font-size: 12px")
    inner = (f'<div style="padding: 28px 32px; display: flex; flex-direction: column; gap: 22px; background: {PANE}; height: 100%; box-sizing: border-box">'
             f'<div style="display: flex; align-items: center; gap: 24px"><span style="width: 120px; font-size: 14px; color: {INK3}">Fast model</span>{model}{dropdown_trigger("medium")}</div>'
             f'<div style="display: flex; align-items: center; gap: 24px"><span style="width: 120px; font-size: 14px; color: {INK3}">Reasoning</span>'
             f'<div style="position: relative">{dropdown_trigger("medium")}'
             f'<div style="position: absolute; left: 0; top: 48px; width: 280px; padding: 8px; box-sizing: border-box; border-radius: {MENU_R}px; background: {ELEV}; {FLOAT}">{menu}</div>'
             f'</div></div></div>')
    return panel("Dropdown field · open, current choice highlighted, beside a ModelPicker", inner, 600, 360)


def menu_item(icon, label, danger=False, hint="", highlight=False):
    lit = f" background: {SELECTED};" if highlight else ""
    return (f'<div role="menuitem" style="display: flex; align-items: center; gap: 12px; height: 40px; padding: 0 12px; box-sizing: border-box; border-radius: {R_CONTROL}px;{lit} font-size: 15px; color: {DANGER if danger else INK}">'
            f'<span style="width: 20px; display: inline-flex; justify-content: center; flex-shrink: 0">{ic(icon, 20, DANGER if danger else INK2)}</span><span style="flex: 1">{label}</span>{key_hint(hint) if hint else ""}</div>')


def menu_sep():
    return '<div role="presentation" style="height: 8px"></div>'


def context_menu_panel():
    menu = (f'<div style="position: absolute; left: 130px; top: 150px; width: 240px; padding: 8px; box-sizing: border-box; border-radius: {MENU_R}px; background: {ELEV}; {FLOAT}">'
            f'{menu_item("pin", "Pin to top")}{menu_sep()}{menu_item("gear", "Open settings", hint="⌘,", highlight=True)}{menu_sep()}{menu_item("trash", "Delete workgroup…", danger=True)}</div>')
    inner = f'<div style="display: flex; height: 100%">{d_sidebar(300, selected="", wg_selected=True)}<div style="flex: 1; background: {PANE}"></div></div>{menu}'
    return panel("Context menu · a workgroup row", inner, 352, 300)


def profile_menu_panel():
    from desktop_boards import d_hero, h1, chat_actions
    from gen import meter
    facts = (f'<div style="display: flex; flex-direction: column; gap: 8px; padding: 8px 12px 12px">'
             f'<div style="display: flex; align-items: center; gap: 8px"><span style="width: 64px; font-size: 14px; color: {INK3}">Model</span><span style="font-family: {MONO}; font-size: 13px; color: {INK}">deepseek-v4.1-flash</span></div>'
             f'<div style="display: flex; align-items: center; gap: 8px"><span style="width: 64px; font-size: 14px; color: {INK3}">Context</span>{meter("24K", "/1.0M", 0.024)}</div>'
             f'<div style="display: flex; align-items: center; gap: 8px"><span style="width: 64px; font-size: 14px; color: {INK3}">Cost</span>{meter("$0.00", "/$1.00", 0)}</div></div>')
    menu = (f'<div style="position: absolute; left: 18px; top: 52px; width: 300px; padding: 8px; box-sizing: border-box; border-radius: {MENU_R}px; background: {ELEV}; {FLOAT}">'
            f'{facts}{menu_item("plus", "New session", hint="⌘N")}{menu_item("pin", "Pin to top")}{menu_sep()}'
            f'{menu_item("pause", "Pause profile")}{menu_item("gear", "Open settings", hint="⌘,", highlight=True)}{menu_sep()}{menu_item("trash", "Delete profile…", danger=True)}</div>')
    head = d_hero(h1("doc", identity_glyph("doc", DOC_ACCENT, 28), DOC_ACCENT), "", chat_actions(), DOC_ACCENT)
    inner = f'<div style="position: absolute; inset: 0; background: {PANE}">{head}</div>{menu}'
    return panel("Profile menu · the chevron beside the name: model, context and cost on top, then the profile's actions", inner, 600, 520, bg=PANE)


def sessions_panel():
    from conversation_boards import d_header
    kbd_keys = f'<span style="display: inline-flex; gap: 2px">{kbd("⌘")}{kbd("N")}</span>'
    new_row = (f'<div role="menuitem" style="display: flex; align-items: center; gap: 12px; height: 40px; padding: 0 12px; border-radius: {R_CONTROL}px">'
               f'<span style="display: inline-flex; flex-shrink: 0">{ic("plus", 20, INK2)}</span><span style="flex: 1; font-size: 15px; color: {INK}">New session</span>{kbd_keys}</div>')
    bucket = lambda label: f'<div style="display: flex; align-items: center; height: 32px; padding: 0 12px; margin-top: 8px">{eyebrow(label)}</div>'
    row_ = lambda title, turns, current=False: (f'<div role="menuitem" style="display: flex; align-items: center; gap: 12px; height: 40px; padding: 0 12px; border-radius: {R_CONTROL}px; background: {SELECTED if current else "transparent"}">'
                                                f'<span style="flex: 1; min-width: 0; font-size: 15px; color: {INK}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis">{title}</span>'
                                                f'<span style="font-size: 12px; color: {INK3}">{turns} turns</span></div>')
    scroll = (f'{new_row}{bucket("Today")}{row_("Pull my last three lipid panels", 4, True)}{row_("Draft the doctor letter", 7)}'
              f'{bucket("Yesterday")}{row_("Quarterly labs review", 12)}{row_("Book a follow-up draw", 3)}'
              f'{bucket("This week")}{row_("Translate the lab report", 9)}')
    foot = (f'<div style="display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 8px 4px 0 12px">'
            f'<span style="font-size: 12px; color: {INK3}">6 sessions</span>{button("Manage sessions", "ghost", "sm")}</div>')
    menu = (f'<div style="position: absolute; right: 56px; top: 60px; width: 380px; padding: 8px; box-sizing: border-box; border-radius: {MENU_R}px; background: {ELEV}; {FLOAT}">{scroll}{foot}</div>')
    inner = f'<div style="position: absolute; inset: 0; background: {PANE}">{d_header("profile", 600)}</div>{menu}'
    return panel("Sessions popover · New session first, then the recent sessions by day with the current one marked, and Manage sessions", inner, 600, 520, bg=PANE)


def sidebar_hover_panel():
    inner = f'<div style="display: flex; height: 100%">{d_sidebar(300, selected="alpi", hover="doc")}<div style="flex: 1; background: {PANE}"></div></div>'
    return panel("Sidebar row · hover: half the chosen fill, rounded inside the gutter", inner, 330, 300)


def toast_box(message, tone, action="", persistent=False, w=380):
    act = button(action, "ghost", "sm") if action else ""
    close = iconbtn("x", "Dismiss", 32, 16) if persistent else ""
    return (f'<div role="{"alert" if persistent and tone == "#c14545" else "status"}" style="width: max-content; max-width: {w}px; min-height: 48px; box-sizing: border-box; display: flex; align-items: center; gap: 12px; padding: 6px 6px 6px 16px; border-radius: {R_SURFACE}px; background: {ELEV}; {FLOAT}">'
            f'<span style="width: 8px; height: 8px; flex-shrink: 0; border-radius: 999px; background: {tone}"></span>'
            f'<span style="min-width: 0; font-size: 15px; line-height: 1.4; color: {INK}; display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 2; overflow: hidden; overflow-wrap: anywhere">{message}</span>{act}{close}</div>')


def toast_panel():
    stack = (f'<div style="position: absolute; right: 32px; bottom: 16px; display: flex; flex-direction: column; align-items: flex-end; gap: 8px">'
             f'{toast_box("Could not forget the connection: the daemon refused the request for this device", "#c14545", "Retry", True, 340)}'
             f'{toast_box("Reasoning effort saved", "#3fb37a", w=340)}</div>')
    return panel("Toast · errors persist with a Dismiss and optional Retry; information fades", stack, 380, 300)


def model_picker_panel():
    from conversation_boards import d_composer
    from desktop_boards import seg
    option = lambda name, ctx, on=False: dropdown_row(name, ctx, on).replace("font-size: 15px; font-weight: 400", f"font-family: {MONO}; font-size: 14px; font-weight: 400", 1)
    pop = (f'<div style="position: absolute; left: 100px; bottom: 84px; width: 340px; padding: 8px; box-sizing: border-box; border-radius: {MENU_R}px; background: {ELEV}; {FLOAT}">'
           f'<div role="listbox">{option("deepseek-v4.1-flash", "128K ctx", True)}{option("deepseek-v4.1-pro", "128K ctx")}</div>'
           f'<div style="display: flex; flex-direction: column; gap: 8px; padding: 12px 8px 8px">{eyebrow("Reasoning effort · saved for this profile")}{seg(("Default", "Low", "Medium", "High"), "Medium", 36)}</div></div>')
    composer = f'<div style="position: absolute; left: 12px; right: 12px; bottom: 12px">{d_composer(name="doc", hint=False, model_name="deepseek-v4.1-flash", effort="medium")}</div>'
    return panel("ModelPicker popover · listbox on the menu rows, effort row when reasoning is supported", composer + pop, 456, 300, bg=PANE)


def confirm_panel():
    body = (f'<span style="font-size: 15px; line-height: 1.5; color: {INK2}">Permanently removes <span style="font-family: {MONO}; font-size: 14px">~/.alpi/profiles/doc/</span>: identity, memory, skills, schedule and chat history. This cannot be undone.</span>'
            f'<div style="display: flex; flex-direction: column; gap: 6px; margin-top: 4px"><span style="font-size: 14px; color: {INK3}">Type <b style="color: {INK}">doc</b> to confirm</span>{ds_field("d", 352, focus=True)}</div>')
    inner = modal("Delete profile doc?", body, dialog_footer("Delete profile", variant="danger"), w=400, x=28, y=12)
    return panel("ConfirmDelete · typed, submits on Enter", inner, 456, 340)


def ask_panel():
    from conversation_boards import inline_ask
    inner = f'<div style="padding: 20px; background: {PANE}; height: 100%; box-sizing: border-box">{inline_ask(question="Which lab should I book?")}</div>'
    return panel("Inline question · asked in the open chat", inner, 376, 300)


def scrim_frame(title, shell, w, h, top=28):
    inner = (f'<div style="position: absolute; inset: 0; background: {SIDE}"></div><div style="position: absolute; inset: 0; background: {VEIL}"></div>'
             f'<div style="position: absolute; left: 0; right: 0; top: {top}px; display: flex; justify-content: center">{shell}</div>')
    return panel(title, inner, w, h)


def shell(inner, w):
    return (f'<div style="width: {w}px; border-radius: {R_SHEET}px; background: {ELEV}; {FLOAT}; overflow: hidden; display: flex; flex-direction: column">{inner}</div>')


def sheet_head(icon, title, keys, pad_left=16):
    glyph = ic(icon, 20, INK) if icon else ""
    return (f'<div style="display: flex; align-items: center; gap: 10px; padding: 16px 16px 12px 20px">'
            f'{glyph}<span style="flex: 1; font-size: 20px; font-weight: 600; color: {INK}">{title}</span>{key_hint(keys)}{iconbtn("x", "Close", 32, 16)}</div>')


def activity_row(glyph, title, sub, tone=None, action="", nested=False, hover=False):
    color = {"warning": "#b3470e", "danger": DANGER, "accent": ALPI_ACCENT}.get(tone, INK3)
    left = 12 + 24 + 12 if nested else 12
    mark = "" if nested else f'<span style="width: 24px; display: inline-flex; justify-content: center; flex-shrink: 0; color: {color}">{glyph(color)}</span>'
    return (f'<li style="display: flex; align-items: center; gap: 8px; min-height: 52px; padding-right: 8px; border-radius: {R_CONTROL}px; background: {SELECTED if hover else "transparent"}">'
            f'<span style="flex: 1; min-width: 0; height: 100%; display: flex; align-items: center; gap: 12px; padding: 0 12px 0 {left}px">{mark}'
            f'<span style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px"><span style="font-size: 15px; line-height: 1.4; color: {INK}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis">{title}</span>'
            f'<span style="font-size: 14px; line-height: 1.45; color: {INK3}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis">{sub}</span></span></span>'
            f'<span style="display: flex; align-items: center; gap: 4px; flex-shrink: 0">{action}</span></li>')


def activity_group(label, rows, right="", first=False):
    return (f'<section aria-label="{label}" style="margin-top: {0 if first else 8}px"><div style="display: flex; align-items: center; justify-content: space-between; height: 32px; padding: 0 12px; background: {ELEV}">'
            f'<h3 style="margin: 0">{eyebrow(label)}</h3>{right}</div>'
            f'<ul style="margin: 0; padding: 0; list-style: none">{"".join(rows)}</ul></section>')


def timed_row(at, title, name, color):
    return (f'<li style="display: flex; align-items: center; gap: 12px; height: 32px; padding: 0 12px; border-radius: {R_CONTROL}px">'
            f'<span style="width: 64px; flex-shrink: 0; font-family: {MONO}; font-size: 12px; line-height: 16px; color: {INK3}">{at}</span>'
            f'<span style="flex: 1; min-width: 0; font-size: 15px; line-height: 16px; color: {INK}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis">{title}</span>'
            f'<span style="display: inline-flex; align-items: center; gap: 8px; flex-shrink: 0">{identity_glyph(name, color, 16)}'
            f'<span style="font-family: {MONO}; font-size: 12px; line-height: 16px; color: {INK3}">{name}</span></span></li>')


def day_head(label):
    return f'<li style="list-style: none"><h4 style="display: flex; align-items: center; height: 24px; margin: 0; padding: 0 12px">{eyebrow(label)}</h4></li>'


def activity_chip(label, count, on=False, danger=False):
    n = f'<span style="font-size: 14px; font-weight: 400; color: {PANE if on else (DANGER if danger else INK3)}">{count}</span>'
    return (f'<span role="radio" aria-checked="{"true" if on else "false"}" style="display: inline-flex; align-items: center; gap: 6px; height: 32px; padding: 0 12px; border-radius: 999px; box-sizing: border-box; '
            f'font-size: 14px; font-weight: 500; line-height: 1; white-space: nowrap; color: {PANE if on else INK}; background: {AMBER if on else FILL}">{label}{n}</span>')


def activity_filters(counts, current="all"):
    items = (("all", "All"), ("needs", "Needs you"), ("failing", "Failing"), ("running", "Running"), ("upcoming", "Upcoming"))
    chips = "".join(activity_chip(label, counts[k], k == current, k == "failing" and counts[k] > 0) for k, label in items)
    return f'<div role="radiogroup" aria-label="Filter activity" style="display: flex; gap: 8px; padding: 4px 16px 8px; overflow: hidden">{chips}</div>'


def activity_fail_head(name, color, count, since, open_, rows=""):
    chev = ic("chev-d" if open_ else "chev-r", 14, INK3)
    head = (f'<div style="display: flex; align-items: center; gap: 8px; height: 32px; padding: 0 12px; border-radius: {R_CONTROL}px; background: {SELECTED if open_ else "transparent"}">'
            f'<span style="width: 16px; display: inline-flex; justify-content: center; flex-shrink: 0">{chev}</span>'
            f'<span style="width: 16px; display: inline-flex; justify-content: center; flex-shrink: 0">{identity_glyph(name, color, 16)}</span>'
            f'<span style="flex: 1; min-width: 0; font-size: 15px; font-weight: 500; color: {INK}">{name}</span>'
            f'<span style="font-family: {MONO}; font-size: 12px; color: {DANGER}">{count} {"job" if count == 1 else "jobs"}</span>'
            f'<span style="font-family: {MONO}; font-size: 12px; color: {INK3}; min-width: 56px; text-align: right">{since}</span></div>')
    return f'<li style="list-style: none">{head}<ul style="margin: 0; padding: 0; list-style: none">{rows}</ul></li>'


def failed(when, ok=""):
    return f'<span style="color: {DANGER}">failed {when}</span>' + (f" · last ok {ok}" if ok else "")


def activity_panel_shell():
    review = button("Review", "primary", "sm")
    actions = button("Open", "ghost", "sm") + button("Retry", "ghost", "sm")
    glyph = lambda name, color: (lambda c: identity_glyph(name, color, 24))
    needs = activity_group("Needs you · 2", [
        activity_row(glyph("abby", "#df4b9d"), "wants to run a command", "abby · approval · 2m ago", "warning", review),
        activity_row(glyph("doc", DOC_ACCENT), "Which lab should I book with?", "doc · question · just now", "warning", review)], first=True)
    sentinel = (activity_row(None, "PR review", failed("19m ago", "1d ago"), None, actions, nested=True, hover=True)
                + activity_row(None, "Project learning", failed("8h ago", "1d ago"), None, "", nested=True))
    failing = activity_group("Failing · 3", [
        activity_fail_head("sentinel", "#3b6fe0", 2, "19m ago", True, sentinel),
        activity_fail_head("clonara", "#f05940", 1, "3h ago", False)], right=button("Retry all", "secondary", "sm"))
    running = activity_group("Running · 2", [
        activity_row(lambda c: wg_mark(DOC_ACCENT), "alpha · #collect", "alpha · phase 3 of 4", "accent"),
        activity_row(glyph("alpi", AMBER), "Summarize yesterday’s deploys", "alpi · 4m · schedule", "accent")])
    upcoming = activity_group("Upcoming · 2", [
        day_head("Tomorrow · 2"),
        timed_row("07:00 AM", "Daily brief", "doc", DOC_ACCENT),
        timed_row("09:00 AM", "Invoice reminder", "abby", "#df4b9d")])
    counts = {"all": 9, "needs": 2, "failing": 3, "running": 2, "upcoming": 2}
    body = f'<div style="padding: 0 8px 12px">{needs}{failing}{running}{upcoming}</div>'
    return shell(sheet_head("role:activity", "Activity", "⌘J") + activity_filters(counts) + body, 500)


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
        f'<section aria-label="{g}"><h3 style="margin: 0; padding: 16px 0 8px">{eyebrow(g)}</h3>'
        + "".join(f'<div style="display: flex; align-items: center; justify-content: space-between; gap: 8px; min-height: 28px"><span style="font-size: 15px; color: {INK2}">{t}</span>{key_hint(k)}</div>' for t, k in items)
        + '</section>' for g, items in SHORTCUT_GROUPS)
    body = f'<div style="display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px 24px; padding: 8px 24px 24px">{groups}</div>'
    return shell(sheet_head("", "Keyboard shortcuts", "⌘/") + body, 620)


RECENT_SESSIONS = (("Draft the Q3 incident review", "@doc · 3h"), ("Summarize yesterday’s deploys", "@alpi · 1d"), ("Reply to Lucy about the October shoot", "@abby · 2d"),
                   ("Translate the letter from the bank", "@yuri · 4d"), ("Lipid panel review", "@doc · 5d"))


def palette_idle():
    glyph = lambda name: ic(name, 14, INK3)
    return palette("", [
        ("Chat", [palette_row(glyph("plus"), "New session", hint="⌘N", selected=True), palette_row(glyph("search"), "Find in transcript", hint="⌘F")]),
        ("Recent sessions", [palette_row(glyph("clock"), title, sub) for title, sub in RECENT_SESSIONS]),
        ("General", [palette_row(glyph("search"), "Command palette", hint="⌘K")]),
    ])


def palette_search():
    return palette("doc", [
        ("Profiles", [palette_row(profile_mark(DOC_ACCENT), "doc", "profile", "⌘2", selected=True, hit="doc")]),
        ("Workgroups", [palette_row(wg_mark(INK3), "alpha", "#doc", "⌘9")]),
        ("Sessions", [palette_row(ic("clock", 14, INK3), "Draft the doctor letter", "@doc · 2h", hit="doc"), palette_row(ic("clock", 14, INK3), "Lipid panel review", "@doc · 3d")]),
    ])


def desktop_overlays():
    body = (f'<div style="padding: 28px 32px; display: flex; flex-direction: column; gap: 24px; box-sizing: border-box">'
            f'<div style="display: flex; flex-direction: column; gap: 4px"><span style="font-size: 20px; font-weight: 600; letter-spacing: -0.018em">Desktop overlays</span>'
            f'<span style="font-size: 15px; color: {INK3}; max-width: 900px; line-height: 1.5">Palette, Activity and shortcuts share one Scrim and PanelShell; Activity opens on counts and filters, groups the failing jobs per profile (the first group open, Open and Retry on the hovered row, Retry all for admins), keeps Running and Upcoming apart and its eyebrows sticky; shortcuts render as KeyHint chips everywhere. Modals, dropdowns and menus register on useOverlay so Escape, focus and layering behave the same.</span></div>'
            f'<div style="display: flex; gap: 16px">{scrim_frame("Command palette ⌘K · New session first, recent sessions below", palette_idle(), 600, 400)}{scrim_frame("Command palette · a query searches profiles, workgroups and sessions", palette_search(), 600, 400)}</div>'
            f'<div style="display: flex; gap: 16px">{scrim_frame("Activity ⌘J · filters, failing jobs per profile, running, upcoming", activity_panel_shell(), 520, 700)}{scrim_frame("Keyboard shortcuts ⌘/", shortcuts_shell(), 680, 700)}</div>'
            f'<div style="display: flex; gap: 16px">{edit_connection_panel()}{dropdown_panel()}</div>'
            f'<div style="display: flex; gap: 16px">{profile_menu_panel()}{sessions_panel()}</div>'
            f'<div style="display: flex; gap: 14px">{confirm_panel()}{ask_panel()}{sidebar_hover_panel()}</div>'
            f'<div style="display: flex; gap: 14px">{context_menu_panel()}{model_picker_panel()}{toast_panel()}</div></div>')
    return page("Desktop · overlays", 1280, OVERLAYS_H, body)


OVERLAYS_H = 3380
