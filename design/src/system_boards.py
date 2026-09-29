from gen import DANGER, DOC_ACCENT, ic, m_button, m_row, m_wide_row, meter, page, pill, switch, textbox
from desktop_boards import HOVER, INK, INK2, INK3, INK4, LINE, LINE2, MONO, PANE, SELECTED, SIDE, alink, button, chip, code_chip, field_input, iconbtn, kbd, meterchip, selectish, textarea
from desktop_overlays import checkbox, dialog_footer, dropdown_row, dropdown_trigger, ds_field, menu_item, modal
from mobile_overlays import action_item, picker_row, separator, sheet_header

AMBER, ACCENT_LIGHT, ACCENT_DARK = "#f0b447", "#8a5a0a", "#f0b447"
LIGHT = [("bg", "#eef0f2"), ("bgPane", "#ffffff"), ("bgSide", "#f5f6f8"), ("bgElev", "#ffffff"), ("bgInput", "#ffffff"), ("ink", "#0b1117"), ("ink2", "#3d4955"), ("ink3", "#626e7d"), ("ink4", "#b1bac4"), ("accent", "#8a5a0a"), ("successText", "#217a45"), ("warningText", "#8a5a0a"), ("dangerText", "#b73737")]
DARK = [("bg", "#0a0d11"), ("bgPane", "#11151a"), ("bgSide", "#0c1014"), ("bgElev", "#161b22"), ("bgInput", "#11151a"), ("ink", "#e6edf3"), ("ink2", "#b1bac4"), ("ink3", "#828b97"), ("ink4", "#484f58"), ("accent", "#f0b447"), ("successText", "#70c592"), ("warningText", "#efb254"), ("dangerText", "#f08080")]
STATUS = [("success", "#3fb37a"), ("warning", "#e08a3c"), ("danger", "#c14545")]
FS = [("xxs", 9), ("label", 10), ("xs", 11), ("sm", 12), ("base", 13), ("md", 14), ("lg", 15), ("xl", 18), ("xxl", 22), ("display", 28), ("hero", 56)]
SPACE = [("s1", 4), ("s2", 6), ("s3", 8), ("s4", 10), ("s5", 12), ("s6", 14), ("s7", 16), ("s8", 20), ("s9", 24), ("s10", 32), ("s11", 40)]
RADII = [("xs", 4), ("sm", 6), ("md", 8), ("lg", 10), ("xl", 12), ("2xl", 14), ("3xl", 16), ("pill", 999)]
CTRL = [("2xs", 18), ("xs", 22), ("sm", 28), ("md", 32), ("lg", 40)]


def h1(text, sub):
    return f'<div style="display: flex; flex-direction: column; gap: 6px"><span style="font-size: 28px; font-weight: 600; letter-spacing: -0.02em; line-height: 1.15">{text}</span><span style="font-size: 13px; line-height: 1.5; color: {INK3}; max-width: 880px">{sub}</span></div>'


def h2(text, n):
    return f'<div style="display: flex; align-items: baseline; gap: 10px; margin-top: 8px"><span style="font-size: 18px; font-weight: 600; letter-spacing: -0.01em">{text}</span><span style="font-family: {MONO}; font-size: 11px; color: {INK4}">{n:02d}</span></div>'


def label(text):
    return f'<span style="font-family: {MONO}; font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase; color: {INK3}">{text}</span>'


def specimen(title, inner, w=None, bg=PANE):
    width = f"width: {w}px;" if w else ""
    return (f'<div style="display: flex; flex-direction: column; gap: 8px; {width} flex-shrink: 0">{label(title)}'
            f'<div style="display: flex; flex-wrap: wrap; align-items: center; gap: 12px; padding: 16px; border-radius: 12px; background: {bg}; border: 0.5px solid {LINE}">{inner}</div></div>')


def swatch(name, hexv, on_dark=False):
    fg = "#e6edf3" if on_dark else INK
    return (f'<div style="display: flex; flex-direction: column; gap: 6px; width: 96px"><div style="height: 44px; border-radius: 8px; background: {hexv}; border: 0.5px solid {LINE2}"></div>'
            f'<span style="font-size: 12px; font-weight: 500; color: {fg}">{name}</span><span style="font-family: {MONO}; font-size: 11px; color: {INK3}">{hexv}</span></div>')


def tokens_board():
    light = "".join(swatch(n, v) for n, v in LIGHT)
    dark = "".join(swatch(n, v, True) for n, v in DARK)
    status = "".join(swatch(n, v) for n, v in STATUS)
    types = "".join(f'<div style="display: flex; align-items: baseline; gap: 14px"><span style="width: 64px; font-family: {MONO}; font-size: 11px; color: {INK3}">{n} · {px}</span><span style="font-size: {px}px; line-height: 1.2; color: {INK}">Every view says what happened</span></div>' for n, px in FS)
    space = "".join(f'<div style="display: flex; flex-direction: column; align-items: center; gap: 6px"><div style="width: {px}px; height: {px}px; background: {SELECTED}; border-radius: 3px"></div><span style="font-family: {MONO}; font-size: 11px; color: {INK3}">{n}</span><span style="font-family: {MONO}; font-size: 11px; color: {INK4}">{px}</span></div>' for n, px in SPACE)
    radii = "".join(f'<div style="display: flex; flex-direction: column; align-items: center; gap: 6px"><div style="width: 44px; height: 44px; border: 1.5px solid {INK2}; border-radius: {min(px, 22)}px"></div><span style="font-family: {MONO}; font-size: 11px; color: {INK3}">{n} · {px}</span></div>' for n, px in RADII)
    ctrl = "".join(f'<div style="display: flex; flex-direction: column; align-items: center; gap: 6px"><div style="width: 72px; height: {px}px; border-radius: 8px; background: {HOVER}; border: 0.5px solid {LINE2}"></div><span style="font-family: {MONO}; font-size: 11px; color: {INK3}">ctrl-{n} · {px}</span></div>' for n, px in CTRL)
    icons = "".join(f'<div style="display: flex; flex-direction: column; align-items: center; gap: 6px; width: 56px">{ic(n, 20, INK2, 1.75)}<span style="font-family: {MONO}; font-size: 10px; color: {INK3}">{n}</span></div>' for n in ("plus", "search", "gear", "bell", "check", "x", "chev-d", "chev-r", "copy", "refresh", "clock", "chip", "sun", "panel", "qr", "more"))
    body = f"""<div style="padding: 40px 48px; display: flex; flex-direction: column; gap: 28px; height: 100%; box-sizing: border-box">
{h1("alpi design system", "One token file, <span style='font-family: " + MONO + "'>common/tokens.mjs</span>, feeds both clients: desktop reads it as CSS custom properties (tokens.css, parity-tested), mobile through useTheme(). Geist for text, Geist Mono for labels and numbers, Lucide icons at 1.75 stroke. The brand accent is Continuity amber: deep on light, signal on dark; the alpaca stays black on white.")}
{h2("Colour · light", 1)}
<div style="display: flex; flex-wrap: wrap; gap: 14px">{light}</div>
{h2("Colour · dark", 2)}
<div style="display: flex; flex-wrap: wrap; gap: 14px; padding: 16px; border-radius: 12px; background: #0a0d11">{dark}</div>
{h2("Status", 3)}
<div style="display: flex; gap: 14px">{status}<div style="font-size: 12px; color: {INK3}; max-width: 520px; line-height: 1.5; align-self: center">Fills for dots, meters and danger buttons. Text on light uses the *Text variants above so it clears 4.5:1; the site shows warnings in red, the apps in orange.</div></div>
{h2("Type scale", 4)}
<div style="display: flex; flex-direction: column; gap: 10px">{types}</div>
<div style="display: flex; gap: 24px; font-size: 12px; color: {INK3}"><span>chat · lg / relaxed</span><span>dialog title · xl / cozy</span><span>body · md / normal</span><span>caption · sm / cozy</span><span>metadata · xs / cozy</span><span>weights 400 · 500 · 600 · 700</span></div>
{h2("Space, radius, control heights", 5)}
<div style="display: flex; gap: 18px; align-items: flex-end">{space}</div>
<div style="display: flex; gap: 22px">{radii}</div>
<div style="display: flex; gap: 22px; align-items: flex-end">{ctrl}</div>
{h2("Iconography", 6)}
<div style="display: flex; flex-wrap: wrap; gap: 10px">{icons}</div>
</div>"""
    return page("System · tokens", 1280, 2000, body)


def desktop_components_board():
    buttons = "".join(button(t, v) for t, v in (("Primary", "primary"), ("Secondary", "secondary"), ("Ghost", "ghost"), ("Danger", "danger"), ("Danger ghost", "danger-ghost"))) + button("sm", "secondary", "sm") + button("lg", "secondary", "lg") + button("hero", "primary", "hero") + iconbtn("gear", "Settings") + alink("Action link") + alink("Remove", danger=True)
    chips = chip("plain") + chip("on", "on") + chip("off", "off") + chip("warn", "warn") + chip("clickable", clickable=True) + code_chip("deepseek-v4.1-flash") + kbd("⌘") + kbd("K")
    fields = field_input("phone") + textarea("Identity as the agent sees itself", rows=2, w=300) + ds_field("phone", 160) + selectish("nova") + dropdown_trigger("medium") + f'<span class="ds-seg" style="display: inline-flex; gap: 2px; padding: 2px; border-radius: 8px; background: {SELECTED}"><span style="height: 22px; padding: 0 8px; border-radius: 6px; background: {INK}; color: {PANE}; font-size: 12px; font-weight: 500; display: inline-flex; align-items: center">All</span><span style="height: 22px; padding: 0 8px; font-size: 12px; font-weight: 500; color: {INK3}; display: inline-flex; align-items: center">Working</span><span style="height: 22px; padding: 0 8px; font-size: 12px; font-weight: 500; color: {INK3}; display: inline-flex; align-items: center">Paused</span></span>' + checkbox(True) + checkbox(False) + f'<span style="width: 16px; height: 16px; border-radius: 999px; border: 1.5px solid {INK}; display: inline-flex; align-items: center; justify-content: center"><span style="width: 8px; height: 8px; border-radius: 999px; background: {INK}"></span></span>'
    meters = meterchip("$0.40", "/$5.00", 0.08) + meterchip("24K", "/1.0M", 0.024) + f'<span style="display: inline-flex; align-items: center; gap: 6px; font-family: {MONO}; font-size: 11px; color: {INK3}"><span style="width: 7px; height: 7px; border-radius: 999px; background: #3fb37a"></span>online</span>' + f'<span style="display: inline-flex; align-items: center; gap: 6px; font-family: {MONO}; font-size: 11px; color: {INK3}"><span style="width: 7px; height: 7px; border-radius: 999px; background: #e08a3c"></span>probing</span>'
    menu = (f'<div style="width: 210px; padding: 4px; border-radius: 10px; background: {PANE}; border: 0.5px solid {LINE2}; box-shadow: 0 18px 50px rgba(11,17,23,0.10)">{menu_item("gear", "Workgroup settings")}{menu_item("copy", "Pin")}<div style="height: 1px; background: {LINE}; margin: 4px 6px"></div>{menu_item("x", "Delete workgroup…", danger=True)}</div>')
    dropdown = f'<div style="width: 260px; padding: 6px; border-radius: 12px; background: {PANE}; border: 0.5px solid {LINE2}; box-shadow: 0 18px 50px rgba(11,17,23,0.10)">{dropdown_row("Default", "use provider default")}{dropdown_row("Medium", "balanced", True)}{dropdown_row("High", "slower, more thorough")}</div>'
    banner = (f'<div style="display: flex; align-items: center; gap: 10px; width: 100%; padding: 8px 14px; border-radius: 8px; background: rgba(193,69,69,0.10); font-size: 13px; color: {INK}"><span style="width: 7px; height: 7px; border-radius: 999px; background: #c14545"></span><span style="flex: 1">Local daemon unreachable — reconnecting…</span>{button("Retry", "ghost", "sm")}</div>'
              f'<div style="display: flex; align-items: center; gap: 10px; width: 100%; padding: 8px 14px; border-radius: 8px; background: rgba(224,138,60,0.12); font-size: 13px; color: {INK}"><span style="width: 7px; height: 7px; border-radius: 999px; background: #e08a3c"></span><span style="flex: 1">This profile is paused. Resume from the header to chat.</span></div>')
    load_failed = (f'<div style="display: flex; flex-direction: column; align-items: center; gap: 12px; padding: 24px 16px; text-align: center; width: 100%"><span style="font-size: 13px; font-weight: 500">Couldn’t load this conversation</span><span style="font-family: {MONO}; font-size: 11px; color: {INK3}">read timeout</span>{button("Retry", "secondary")}</div>'
                   f'<span style="display: inline-flex; align-items: center; gap: 8px; color: {DANGER}; font-size: 13px">Couldn’t load members {alink("Retry")}</span>')
    empty = f'<div style="display: flex; flex-direction: column; align-items: center; gap: 16px; padding: 24px; width: 100%; text-align: center"><span style="font-family: {MONO}; font-size: 56px; font-weight: 500; color: {INK4}; line-height: 1">#</span><span style="font-size: 28px; font-weight: 600; letter-spacing: -0.02em">No workgroups yet</span><span style="font-family: {MONO}; font-size: 12px; color: {INK3}">a hub profile plus the members it directs</span>{button("New workgroup", "secondary")}</div>'
    mbody = (f'<div style="display: flex; flex-direction: column; gap: 6px"><span style="font-size: 12px; color: {INK3}">Label</span>{field_input("phone", 380)}</div>'
             f'<div style="display: flex; gap: 16px"><div style="display: flex; flex-direction: column; gap: 6px"><span style="font-size: 12px; color: {INK3}">Role</span>{dropdown_trigger("Member")}</div><div style="display: flex; flex-direction: column; gap: 6px"><span style="font-size: 12px; color: {INK3}">Sessions</span>{dropdown_trigger("Shared across its devices")}</div></div>')
    modal_spec = f'<div style="position: relative; width: 520px; height: 300px; border-radius: 12px; background: {SIDE}; overflow: hidden">{modal("Edit connection", mbody, dialog_footer("Save changes"), w=440, x=40, y=24)}</div>'
    confirm_body = (f'<span style="font-size: 13px; line-height: 1.5; color: {INK2}">Permanently removes identity, memory, skills, schedule and chat history. This cannot be undone.</span>'
                    f'<div style="display: flex; flex-direction: column; gap: 6px; margin-top: 8px"><span style="font-family: {MONO}; font-size: 11px; letter-spacing: 0.06em; color: {INK3}">TYPE <b style="color: {INK}">doc</b> TO CONFIRM</span>{ds_field("d", 360)}</div>')
    confirm_spec = f'<div style="position: relative; width: 460px; height: 300px; border-radius: 12px; background: {SIDE}; overflow: hidden">{modal("Delete profile @doc", confirm_body, dialog_footer("Delete profile", variant="danger"), w=400, x=30, y=24)}</div>'
    body = f"""<div style="padding: 40px 48px; display: flex; flex-direction: column; gap: 22px; height: 100%; box-sizing: border-box">
{h1("Components · desktop", "Every primitive lives in desktop/src/primitives and paints with the .ds-* classes from design-system.css. Buttons are 28 px by default, fields 32, dialogs 520 with a shared DialogFooter; menus and confirms register on useOverlay so Escape, focus and layering behave the same everywhere.")}
{specimen("Buttons · sizes sm 24 · md 28 · lg 32 · hero 40 · IconBtn · action links", buttons)}
{specimen("Chips, code chip, keys", chips)}
{specimen("Fields · Field 32 · Textarea · ds-field · Selectish (mono, voice + budget) · Dropdown field (every choice) · ds-seg · Checkbox · Radio", fields)}
{specimen("Meters and status dots", meters)}
<div style="display: flex; gap: 22px; align-items: flex-start">{specimen("Context menu · 6/10 rows, radius 10", menu, 260)}{specimen("Dropdown menu · 8/10 rows, caption mono 11, active = selected fill", dropdown, 300)}{specimen("Banners · danger with Retry · warning", banner, 560)}</div>
<div style="display: flex; gap: 22px; align-items: flex-start">{specimen("Modal 520 · title 18 · content scrolls · DialogFooter (ghost Cancel, primary)", modal_spec, 552, SIDE)}{specimen("ConfirmDelete · typed only for irreversible deletes · waits for the delete", confirm_spec, 492, SIDE)}</div>
<div style="display: flex; gap: 22px; align-items: flex-start">{specimen("LoadFailed · card and inline (role alert)", load_failed, 420)}{specimen("EmptyState · glyph, display heading, mono subtitle, one action", empty, 620)}</div>
</div>"""
    return page("System · desktop components", 1280, 1900, body)


def mobile_components_board():
    buttons = "".join(m_button(t, v, "lg") for t, v in (("Primary", "primary"), ("Secondary", "secondary"), ("Ghost", "ghost"), ("Danger", "danger"), ("Danger ghost", "danger-ghost"))) + m_button("md", "secondary", "md") + m_button("sm", "secondary", "sm")
    rows = f'<div style="width: 390px; border-radius: 12px; overflow: hidden; border: 0.5px solid {LINE}">{m_row("Reasoning effort", "how hard the model thinks", "Medium")}{m_row("Paused", "paused profiles can’t be chatted", control=switch(False, DOC_ACCENT, "Paused"), chevron=False)}{m_row("Delete profile", "cannot be undone", danger=True, sep=False)}</div>'
    wide = f'<div style="width: 520px; padding: 0 16px; border-radius: 12px; border: 0.5px solid {LINE}">{m_wide_row("Default model", value="deepseek-v4.1-flash")}{m_wide_row("Sandbox", "wraps shell tools", control=switch(True, DOC_ACCENT, "Sandbox"), chevron=False)}{m_wide_row("Workspace", value="/data/workspace/doc")}</div>'
    pills = pill("on", True) + pill("off") + pill("warn", tone="warning") + pill("2 sessions", tone="success") + meter("$0.40", "/$5.00", 0.08) + meter("24K", "/1.0M", 0.024)
    fields = f'<div style="width: 300px">{textbox("phone", rows=1)}</div><div style="width: 300px; display: flex; flex-direction: column; gap: 6px"><div style="height: 44px; border-radius: 12px; border: 1px solid {DANGER}; background: #f1f3f5; display: flex; align-items: center; padding: 0 12px; font-family: {MONO}; font-size: 14px">abc</div><span style="font-family: {MONO}; font-size: 11px; color: {DANGER}">Enter a number, or leave it empty for no cap</span></div>{switch(True, DOC_ACCENT)}{switch(False, DOC_ACCENT)}'
    picker = f'<div style="width: 360px; border-radius: 12px; border: 0.5px solid {LINE}; overflow: hidden">{picker_row("Low", "fastest, cheapest")}{separator()}{picker_row("Medium", "balanced", selected=True)}{separator()}{picker_row("High", "slower, more thorough")}</div>'
    actions = f'<div style="width: 360px; border-radius: 12px; border: 0.5px solid {LINE}; overflow: hidden">{action_item("gear", "Profile settings")}{separator(56)}{action_item("bell", "Auto-read replies", "off")}{separator(56)}{action_item("x", "Delete profile…", danger=True)}</div>'
    sheet_spec = f'<div style="width: 390px; border-radius: 28px 28px 0 0; background: #ffffff; border: 0.5px solid {LINE2}; overflow: hidden; box-shadow: 0 8px 24px rgba(11,17,23,0.08)">{sheet_header("Reasoning effort", "how hard the model thinks before answering")}<div style="padding: 0 0 8px">{picker_row("Medium", "balanced", selected=True)}</div><div style="display: flex; gap: 10px; padding: 20px 16px 24px"><span style="flex: 1; display: flex">{m_button("Not now", "ghost", "lg").replace("border-radius: 10px", "border-radius: 14px; width: 100%")}</span><span style="flex: 1; display: flex">{m_button("Save", "primary", "lg").replace("border-radius: 10px", "border-radius: 14px; width: 100%")}</span></div></div>'
    confirm = (f'<div style="width: 360px; border-radius: 28px; background: #ffffff; padding: 24px; box-sizing: border-box; display: flex; flex-direction: column; gap: 14px; box-shadow: 0 20px 60px rgba(0,0,0,0.3)"><span style="font-weight: 600; font-size: 18px; color: {DANGER}">Delete profile @doc</span><span style="font-size: 14px; line-height: 1.5; color: {INK2}">Permanently removes identity, memory, skills and chat history.</span><span style="font-family: {MONO}; font-size: 11px; letter-spacing: 0.06em; color: {INK3}">TYPE <b style="color: {INK}">doc</b> TO CONFIRM</span><div style="height: 44px; border-radius: 12px; background: #f1f3f5; border: 0.5px solid {LINE2}"></div>{m_button("Delete profile", "danger", "lg").replace("border-radius: 10px", "border-radius: 14px")}{m_button("Cancel", "ghost", "lg").replace("border-radius: 10px", "border-radius: 14px")}</div>'
               f'<div style="width: 360px; border-radius: 28px; background: #ffffff; padding: 24px; box-sizing: border-box; display: flex; flex-direction: column; gap: 14px; box-shadow: 0 20px 60px rgba(0,0,0,0.3)"><span style="font-weight: 600; font-size: 18px; color: {INK}">Restart the daemon</span><span style="font-size: 14px; line-height: 1.5; color: {INK2}">Every connected client briefly loses its socket.</span>{m_button("Restart", "primary", "lg").replace("border-radius: 10px", "border-radius: 14px")}{m_button("Cancel", "ghost", "lg").replace("border-radius: 10px", "border-radius: 14px")}</div>')
    toast = f'<div style="width: 360px; padding: 14px; border-radius: 12px; background: #ffffff; box-shadow: 0 8px 18px rgba(0,0,0,0.18); display: flex; gap: 10px; align-items: flex-start"><span style="width: 8px; height: 8px; border-radius: 4px; background: #c14545; margin-top: 6px"></span><div style="display: flex; flex-direction: column; gap: 2px"><span style="font-size: 14px; font-weight: 600">Save failed</span><span style="font-size: 14px; color: {INK2}">daemon said no</span></div></div>'
    banners = f'<div style="width: 360px; padding: 10px 14px; border-radius: 10px; background: rgba(193,69,69,0.12); display: flex; align-items: center; gap: 10px; font-size: 14px; color: {INK}"><span style="flex: 1">Daemon unreachable. Reconnecting…</span>{m_button("Retry", "ghost", "sm")}</div>'
    load_failed = f'<div style="width: 360px; display: flex; flex-direction: column; align-items: center; gap: 12px; padding: 20px; text-align: center"><span style="font-size: 18px; font-weight: 600">Couldn’t load this conversation</span><span style="font-family: {MONO}; font-size: 11px; color: {INK3}">read timeout</span>{m_button("Retry", "secondary", "md")}</div><div style="width: 360px; display: flex; align-items: center; gap: 10px; padding: 14px 20px"><span style="flex: 1; font-size: 14px; font-weight: 500; color: {DANGER}">Couldn’t load email accounts</span><span style="font-size: 14px; font-weight: 500; color: {INK2}">Retry</span></div>'
    jump = f'<span style="display: inline-flex; align-items: center; gap: 8px; height: 36px; padding: 0 14px; border-radius: 999px; background: #ffffff; border: 0.5px solid {LINE2}; box-shadow: 0 8px 24px rgba(11,17,23,0.08); font-size: 12px; font-weight: 500; color: {INK2}">{ic("chev-d", 14, INK2)}Latest</span>'
    body = f"""<div style="padding: 40px 48px; display: flex; flex-direction: column; gap: 22px; height: 100%; box-sizing: border-box">
{h1("Components · phone and Fold", "Every primitive lives in mobile/src/components and reads the same tokens through useTheme(). Touch targets stay at 44 px, rows at 44, buttons at 48. On a fold or tablet the wide layout borrows the desktop grammar: eyebrow rows, a chat-style header, sheets that open as centred 560 dialogs.")}
{specimen("Buttons · lg 48 · md 40 · sm 40 · radius 14 · haptic on press", buttons)}
<div style="display: flex; gap: 22px; align-items: flex-start">{specimen("Row · phone (15 px label, mono helper, chevron gutter, danger)", rows, 422)}{specimen("WideRow · fold and tablet (eyebrow label, control right, gutter reserved)", wide, 552)}</div>
{specimen("Pill, OnOff, Meter, Toggle (optimistic, snaps back on failure)", pills + switch(True, DOC_ACCENT) + switch(False, DOC_ACCENT))}
{specimen("Field · 44 high, radius 12 · error state (border and helper in dangerText)", fields)}
<div style="display: flex; gap: 22px; align-items: flex-start">{specimen("PickerRow · 7 px dot, selected fill, one style everywhere", picker, 392)}{specimen("ActionSheet items · 20 px icon slot, mono detail, danger", actions, 392)}</div>
<div style="display: flex; gap: 22px; align-items: flex-start">{specimen("Sheet · grabber, title 18, mono subtitle, X · primaryAction [secondary, primary] · dismissible=false for decisions", sheet_spec, 422, SIDE)}{specimen("TypedConfirm · danger + typed for deletes · neutral untyped for reversible actions", confirm, 400, SIDE)}</div>
<div style="display: flex; gap: 22px; align-items: flex-start">{specimen("Toast · top, max 560, 2.8 s", toast, 392)}{specimen("Banner · daemon states", banners, 392)}{specimen("JumpToLatest", jump, 200)}</div>
{specimen("LoadFailed · card and inline row (accessibilityRole alert)", load_failed, 780)}
</div>"""
    return page("System · mobile components", 1280, 2300, body)


SYSTEM = {"tokens": tokens_board, "desktop": desktop_components_board, "mobile": mobile_components_board}
