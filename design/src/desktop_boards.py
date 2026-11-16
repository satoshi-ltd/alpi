import re
from gen import BANNER_DOT, BANNER_TEXT, HOVER_FILL, SELECTED_FILL, R_XS, R_CONTROL, R_SURFACE, R_SHEET, banner_surface, app_version, button_heights, ALPI_ACCENT, DANGER, DOC_ACCENT, FRONT, PROFILES, di as ic, identity_glyph, profile_mark, page, usage_chart

INK, INK2, INK3, INK4 = "#141414", "#454545", "#6b6b6b", "#b4b4b4"
LINE, LINE2, HOVER, SELECTED = "rgba(20,20,20,0.07)", "rgba(20,20,20,0.14)", HOVER_FILL, SELECTED_FILL
SIDE, PANE, BG = "#f6f6f6", "#ffffff", "#f0f0f0"
AMBER = "#14110c"
EDGE = "#8c8c8c"
RING = f"0 0 0 1px {EDGE}"
ELEV = "var(--bg-elev, #ffffff)"
FLOAT = "box-shadow: var(--shadow-float, 0 12px 32px rgba(0, 0, 0, 0.10), 0 1px 3px rgba(0, 0, 0, 0.06))"
SM_FLOAT = FLOAT
LG_FLOAT = FLOAT
CARD = "var(--card, #f2f2f2)"
FILL = "#f2f2f2"
PRESSED = "rgba(20,20,20,0.12)"
NAME = "'Bricolage Grotesque', Geist, sans-serif"
SIDEBAR_W, STREAM_W, HEADER_H, COMPOSER_H = 272, 760, 56, 56
MONO = "'Geist Mono', monospace"
TITLEBAR_H = 38


def eyebrow(text, color=INK3, weight=500, track=0, size=14, extra=""):
    return f'<span style="font-weight: {weight}; font-size: {max(size, 14)}px; line-height: 1.45; color: {color}; {extra}">{text}</span>'


def iconbtn(name, label, size=32, icon=16, color=INK2, width=None):
    return (f'<button aria-label="{label}" style="width: {width or size}px; height: {size}px; border: 0; border-radius: 999px; background: transparent; '
            f'display: inline-flex; align-items: center; justify-content: center; padding: 0; cursor: pointer; flex-shrink: 0">{ic(name, icon, color)}</button>')


def button(label, variant="ghost", size="md", icon=None, icon_only=False):
    h = button_heights("desktop")[size]
    fs = 14 if h <= 32 else 15
    padx = {32: 12, 40: 16, 48: 24}.get(h, 16)
    if variant == "primary":
        bg, fg = AMBER, PANE
    elif variant == "secondary":
        bg, fg = FILL, INK
    elif variant == "danger":
        bg, fg = "#c14545", "#fffffe"
    elif variant == "danger-ghost":
        bg, fg = "transparent", DANGER
    else:
        bg, fg = "transparent", INK
    glyph = 16 if h <= 32 else 20
    if icon_only:
        return (f'<button aria-label="{label}" style="display: inline-flex; align-items: center; justify-content: center; width: {h}px; height: {h}px; padding: 0; border: 0; border-radius: 999px; '
                f'background: {bg}; cursor: pointer; flex-shrink: 0">{ic(icon, glyph, fg)}</button>')
    i = ic(icon, glyph, fg) if icon else ""
    return (f'<button style="display: inline-flex; align-items: center; gap: 8px; height: {h}px; padding: 0 {padx}px; border: 0; border-radius: 999px; box-sizing: border-box; '
            f'background: {bg}; color: {fg}; font-family: Geist, sans-serif; font-weight: 500; font-size: {fs}px; line-height: 1; cursor: pointer; white-space: nowrap; flex-shrink: 0">{i}{label}</button>')


MODIFIERS = "⌘⇧⌥⌃"


def key_hint(hint):
    chars = list(hint.strip())
    i = 0
    while i < len(chars) and chars[i] in MODIFIERS:
        i += 1
    rest = "".join(chars[i:])
    if not rest or " " in rest or len(rest) > 5:
        return f'<span style="font-size: 12px; color: {INK3}; white-space: nowrap; flex-shrink: 0">{hint}</span>'
    return f'<span data-keys="{hint}" style="display: inline-flex; align-items: center; gap: 2px; flex-shrink: 0">{"".join(kbd(t) for t in chars[:i] + [rest])}</span>'


STATE_TEXT = {"needs-you": "needs you", "failed": "failed", "working": "working"}
STATE_COLOR = {"needs-you": "#b3470e", "failed": DANGER, "working": INK2}


def state_chip(state, profile=None):
    color = {"needs-you": "#b3470e", "failed": DANGER}.get(state, INK3)
    return (f'<span data-state="{state}" style="display: inline-flex; align-items: center; flex-shrink: 0; font-family: Geist, sans-serif; font-weight: 500; font-size: 12px; line-height: 1; white-space: nowrap; color: {color}">'
            f'{STATE_TEXT[state]}</span>')


def phase_count(done, total, accent=None):
    from gen import PALETTES
    import marks
    colour = f'light-dark({marks.name_tone(accent, PALETTES["light"]["bgSide"])}, {marks.name_tone(accent, PALETTES["dark"]["bgSide"])})' if accent else INK2
    return f'<span aria-label="phase {done} of {total}" style="flex-shrink: 0; font-family: Geist, sans-serif; font-weight: 500; font-size: 12px; color: {colour}">{done}/{total}</span>'


def bell_dot():
    return '<span style="position: absolute; top: 0; right: 0; width: 8px; height: 8px; border-radius: 999px; background: #c14545; transform: translate(25%, -25%); pointer-events: none"></span>'


def badged(icon, label, n, width=None):
    mark = bell_dot() if n else ""
    glyph = f'<span style="position: relative; display: inline-flex">{ic(icon, 16, INK2)}{mark}</span>'
    return (f'<button aria-label="{label}" style="width: {width or 32}px; height: {width or 32}px; border: 0; border-radius: 999px; background: transparent; '
            f'display: inline-flex; align-items: center; justify-content: center; padding: 0; cursor: pointer">{glyph}</button>')


def footer_button(label, icon, color=None):
    return (f'<button aria-label="{label}" style="width: 32px; height: 32px; border: 0; border-radius: 999px; background: transparent; display: inline-flex; align-items: center; justify-content: center; padding: 0; cursor: pointer">{ic(icon, 16, color or INK2)}</button>')


def footer_icons(theme="system"):
    icon = {"system": "sun-moon", "light": "sun", "dark": "moon"}[theme]
    label = {"system": "System", "light": "Light", "dark": "Dark"}
    return (badged("role:notifications", "Notifications · 1 unread · ⌘O", 1)
            + badged("role:activity", "Activity · 2 need you · ⌘J", 2) + footer_button("Search · ⌘K", "search") + footer_button(f"Theme: {label[theme]}", icon))


def sidebar_footer(version, update=False, width=None):
    w = f"width: {width}px; " if width else ""
    color = "#217a45" if update else INK3
    return (f'<div style="{w}box-sizing: border-box; display: flex; align-items: center; gap: 2px; padding: 12px 16px 14px">'
            f'{footer_button("Settings", "role:settings", INK2)}{footer_icons()}'
            f'<span style="flex: 1 1 0; min-width: 0; display: flex; justify-content: flex-end; font-size: 12px; font-weight: 500; line-height: 32px; color: {color}; white-space: nowrap">{version}</span></div>')


def wg_mark(color, size=16, state="idle", **kw):
    import marks
    return marks.workgroup(color, size, state, **kw)




def alink(label, icon=None, danger=False):
    color = DANGER if danger else INK2
    i = ic(icon, 12, color) if icon else ""
    return (f'<button style="display: inline-flex; align-items: center; gap: 6px; padding: 4px 8px; margin: -4px -8px; border: 0; border-radius: {R_CONTROL}px; '
            f'background: transparent; color: {color}; font-family: Geist, sans-serif; font-weight: 500; font-size: 15px; line-height: 1; cursor: pointer">{i}{label}</button>')


def chip(text, state="plain", size="md", clickable=False):
    h = 32 if size == "md" else 24
    dot = 8
    bg, fg, dotc, op = FILL, INK, None, 1
    if state == "on":
        dotc = "#3fb37a"
    elif state == "off":
        fg, dotc = INK3, INK3
    elif state == "error":
        fg, dotc = DANGER, "#c14545"
    elif state == "warn":
        dotc = "#e08a3c"
    elif state == "accent":
        bg, fg = AMBER, PANE
    d = f'<span style="width: {dot}px; height: {dot}px; border-radius: 999px; background: {dotc}; flex-shrink: 0"></span>' if dotc else ""
    return (f'<span style="display: inline-flex; align-items: center; gap: 6px; height: {h}px; padding: 0 {12 if size == "md" else 10}px; border-radius: 999px; '
            f'background: {bg}; color: {fg}; font-family: Geist, sans-serif; font-size: {14 if size == "md" else 12}px; font-weight: 500; line-height: 1; opacity: {op}; white-space: nowrap; box-sizing: border-box; flex-shrink: 0">{d}{text}</span>')


def code_chip(text):
    return (f'<span style="display: inline-flex; align-items: center; padding: 4px 8px; border-radius: {R_XS}px; background: {FILL}; '
            f'font-family: {MONO}; font-size: 13px; color: {INK2}; max-width: 360px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis">{text}</span>')


def selectish(inner, mono=True):
    fam = MONO if mono else "Geist, sans-serif"
    return (f'<span style="display: inline-flex; align-items: center; gap: 8px; height: 40px; padding: 0 12px 0 16px; border-radius: 999px; background: {FILL}; '
            f'font-family: {fam}; font-size: {14 if mono else 15}px; font-weight: 400; color: {INK}; box-sizing: border-box; white-space: nowrap; flex-shrink: 0">{inner}{ic("chev-d", 16, INK3)}</span>')


def field_input(value, w=520, placeholder=False, focus=False, mono=False):
    color = INK3 if placeholder else INK
    ring = f"box-shadow: inset 0 0 0 1.5px {INK3};" if focus else ""
    fam = f"font-family: {MONO}; font-size: 14px;" if mono and not placeholder else "font-size: 15px;"
    return (f'<span style="display: inline-flex; align-items: center; height: 40px; max-width: {w}px; flex: 1; padding: 0 14px; border-radius: {R_CONTROL}px; background: {FILL}; {ring} '
            f'{fam} color: {color}; box-sizing: border-box">{value}</span>')


def textarea(text, rows=3, w=520, placeholder=False):
    color = INK3 if placeholder else INK
    return (f'<div style="width: 100%; max-width: {w}px; min-height: {max(88, rows * 24 + 24)}px; padding: 12px 14px; border-radius: {R_CONTROL}px; background: {FILL}; '
            f'font-size: 15px; line-height: 1.5; color: {color}; box-sizing: border-box">{text}</div>')


def muted(text):
    return f'<span style="font-size: 14px; color: {INK3}">{text}</span>'


def mono12(text, color=INK2):
    return f'<span style="font-family: {MONO}; font-size: 13px; color: {color}">{text}</span>'


def meterchip(value, tail, pct, color=ALPI_ACCENT):
    drawn = pct >= 0.01
    bar = (f'<span role="progressbar" aria-label="{value}{tail}" style="width: 56px; height: 5px; border-radius: 999px; background: {LINE2}; overflow: hidden; display: inline-block"><span style="display: block; width: {pct * 100}%; height: 100%; background: {color}"></span></span>') if drawn else ""
    return (f'<span style="display: inline-flex; align-items: center; gap: 8px"><span style="font-family: {MONO}; font-size: 12px; color: {INK2}">{value}<span style="color: {INK3}">{tail}</span></span>'
            f'{bar}<span style="font-family: {MONO}; font-size: 12px; color: {INK3}">{f"{round(pct * 100)}%" if drawn else "—"}</span></span>')


SEP = f'<span style="width: 1px; height: 10px; background: {LINE2}; display: inline-block"></span>'


def sb_row(glyph, name, ts="", active=False, unread=False, dim=False, href="Desktop-Chat.dc.html", trailing="", accent=None, hover=False):
    hover = hover and not active
    bg = SELECTED if active else (HOVER if hover else "transparent")
    fw = 600 if (active or unread) else 400
    if dim and not trailing:
        trailing = f'<span style="flex-shrink: 0; font-weight: 500; font-size: 12px; line-height: 1; color: {INK3}">paused</span>'
    t = trailing or (f'<span style="flex-shrink: 0; font-weight: 500; font-size: 12px; line-height: 1; font-variant-numeric: tabular-nums slashed-zero; color: {INK3}">{ts}</span>' if ts else "")
    current = ' aria-current="page"' if active else ""
    return (f'<a href="{href}"{current} style="display: flex; align-items: center; gap: 12px; height: 40px; padding: 0 12px; border-radius: {R_CONTROL}px; background: {bg}; '
            f'text-decoration: none; {"opacity: 0.55;" if dim else ""}"><span style="width: 24px; height: 24px; display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0">{glyph}</span>'
            f'<span style="flex: 1; min-width: 0; font-size: 15px; font-weight: {fw}; color: {INK}; line-height: 1.4; white-space: nowrap; overflow: hidden; text-overflow: ellipsis">{name}</span>{t}</a>')


ROSTER_STATES = {"alpi": "working", "abby": "needs-you", "clonara": "failed"}
PINNED = ("doc",)


def sb_section(label, add=True):
    plus = (f'<button aria-label="New {label.lower()[:-1]}" style="width: 28px; height: 28px; border: 0; border-radius: 999px; background: transparent; display: inline-flex; align-items: center; justify-content: center; padding: 0; cursor: pointer">{ic("plus", 16, INK2)}</button>') if add else ""
    return f'<div style="display: flex; align-items: center; height: 32px; margin-top: 16px; padding: 0 4px 0 12px">{eyebrow(label, INK3, 500, 0, 14, "flex: 1")}{plus}</div>'


TILE_CELL = (SIDEBAR_W - 24 - 8) // 3


def tile(name, color, state="idle", selected=False, width=None, roster_state=None):
    from brand_boards import app_name
    width = width or TILE_CELL
    pip = ""
    if state in ("needs", "failed"):
        pip = (f'<span style="position: absolute; top: 4px; right: {(width - 48) / 2 - 2:.0f}px; width: 10px; height: 10px; border-radius: 999px; '
               f'background: {"#e08a3c" if state == "needs" else "#c14545"}; box-shadow: 0 0 0 2px {SIDE}"></span>')
    current = ' aria-current="page"' if selected else ""
    flag = f' data-state="{roster_state}"' if roster_state else ""
    return (f'<a href="Desktop-Chat.dc.html" data-tile="{name}"{flag}{current} style="position: relative; display: flex; flex-direction: column; align-items: center; gap: 6px; width: {width}px; min-width: 0; box-sizing: border-box; padding: 8px 4px; '
            f'border-radius: {R_SURFACE - 4}px; text-decoration: none; background: {SELECTED if selected else "transparent"}">{identity_glyph(name, color, 48, state)}'
            f'{app_name(name, 14, None if name == FRONT else color, SIDE)}{pip}</a>')


def conn_head(name="This computer", host="host.sock"):
    return (f'<div style="padding: 8px 12px 0"><div data-conn="" style="display: flex; align-items: center; gap: 8px; height: 40px; padding: 0 12px; box-sizing: border-box; border-radius: {R_CONTROL}px; background: {SELECTED_FILL}">'
            f'<span style="position: relative; display: inline-flex">{ic("chip", 16, INK2)}<span style="position: absolute; right: -2px; bottom: -2px; width: 8px; height: 8px; box-sizing: border-box; border-radius: 50%; background: #3fb37a; border: 1.5px solid {PANE}"></span></span>'
            f'<span style="flex: 1; min-width: 0; display: flex; flex-direction: column"><span style="font-size: 15px; font-weight: 500; line-height: 1.1; color: {INK}">{name}</span>'
            f'<span style="font-family: {MONO}; font-size: 12px; line-height: 1.2; color: {INK3}">{host}</span></span>{ic("chev-d", 16, INK3)}</div></div>')


def d_sidebar(h, selected="doc", settings_mode=False, wg_selected=False, states=None, version=None, hover=None):
    version = version or app_version("desktop")
    states = ROSTER_STATES if states is None else states

    def mark_state(name, state):
        return "paused" if name == "etxea" else {"needs-you": "needs", "failed": "failed", "working": "working"}.get(state, "done" if name == "yuri" else "idle")

    def prow(name, col, ts):
        state = states.get(name)
        return sb_row(identity_glyph(name, col, 24, mark_state(name, state)), name, ts, active=name == selected, unread=name == "yuri" and not state, dim=name == "etxea", trailing=state_chip(state, col) if state else "", accent=col, hover=name == hover)

    tiles = "".join(tile(n, AMBER if n == FRONT else c, mark_state(n, states.get(n)), selected=n == selected, roster_state=states.get(n)) for n, c, t, _ in sorted(PROFILES, key=lambda p: p[0] != FRONT) if n == FRONT or n in PINNED)
    rows = "".join(prow(n, c, t) for n, c, t, _ in PROFILES if n not in PINNED and n != FRONT)
    wgs = (sb_row(wg_mark(DOC_ACCENT, 24, state="running", phase=(2, 4), still=True), "alpha", active=wg_selected, href="Desktop-WorkgroupSettings.dc.html", trailing=phase_count(2, 4, DOC_ACCENT), accent=DOC_ACCENT)
           + sb_row(wg_mark(AMBER, 24), "launch-crew", "2h", href="Desktop-WorkgroupSettings.dc.html"))
    return f"""<div style="width: {SIDEBAR_W}px; height: {h}px; flex-shrink: 0; box-sizing: border-box; background: {SIDE}; display: flex; flex-direction: column">
<div style="height: 38px; flex-shrink: 0"></div>
{conn_head()}
<div aria-label="Pinned" style="display: grid; grid-template-columns: repeat(3, {TILE_CELL}px); gap: 4px; padding: 12px 12px 0">{tiles}</div>
<div style="padding: 0 12px; display: flex; flex-direction: column; gap: 2px">
{sb_section("Profiles")}
{rows}
{sb_section("Workgroups")}
{wgs}
</div>
<div style="flex: 1"></div>
{sidebar_footer(version)}
</div>"""


def d_hero(title_html, meta_html, actions_html, accent):
    return (f'<div data-header="" style="position: relative; z-index: 2; box-sizing: content-box; height: {HEADER_H}px; flex-shrink: 0; display: flex; align-items: center; padding: {TITLEBAR_H}px 24px 0 32px; background: {PANE}">'
            f'<span style="display: inline-flex; align-items: center; gap: 4px; height: 40px; margin-left: -4px; padding: 0 8px 0 4px; border-radius: 999px">{title_html}{ic("chev-d", 16, INK3)}</span>'
            f'<span style="flex: 1"></span><span style="display: flex; align-items: center; gap: 4px">{actions_html}</span>'
            f'<div style="position: absolute; left: 0; right: 0; top: 100%; height: 24px; background: linear-gradient({PANE}, transparent); pointer-events: none"></div></div>')


def h1(text, glyph, name_accent=None):
    from brand_boards import app_name
    accent = None if name_accent in (None, "ink") else name_accent
    return f'{glyph}{app_name(text, 20, accent, PANE)}'


def section(title, kicker="", body="", first=False):
    k = f'<span style="font-size: 14px; color: {INK3}">{kicker}</span>' if kicker else ""
    return f"""<div style="margin-top: {0 if first else 32}px; display: flex; flex-direction: column">
<div style="display: flex; align-items: baseline; gap: 8px; margin-bottom: 8px"><span style="font-size: 20px; font-weight: 600; line-height: 1.25; color: {INK}">{title}</span>{k}</div>
{body}
</div>"""


def fallbacks_field(models=("claude-sonnet-5-5",)):
    def act(label, icon, off=False):
        html = button(label, "ghost", "sm", icon, icon_only=True)
        return html.replace("cursor: pointer", "cursor: default; opacity: 0.4") if off else html
    entries = "".join(
        f'<span style="display: flex; align-items: center; gap: 8px">{mono12(f"{i} · {m}")}'
        f'{act("Move up", "chevron-up", i == 1)}{act("Move down", "chevron-down", i == len(models))}{act("Remove", "x")}</span>'
        for i, m in enumerate(models, 1)
    ) or muted("none")
    add = f'<span style="display: flex; align-items: center; flex-wrap: wrap; gap: 8px">{selectish("Add")}{muted("Tried in order when the main model&#39;s provider fails.")}</span>'
    return f'<span style="display: flex; flex-direction: column; gap: 4px; min-width: 0">{entries}{add}</span>'


def bleed(control):
    at = control.rfind("<button ")
    if at < 0 or not control.rstrip().endswith("</button>"):
        return control
    tail = control[at:]
    pad = re.search(r"padding: 0 (\d+)px", tail)
    if "background: transparent" not in tail or not pad:
        return control
    return control[:at] + tail.replace('flex-shrink: 0">', f'flex-shrink: 0; margin-right: -{pad.group(1)}px">', 1)


def row(label, control, align_top=False, desc="", lines=None):
    text = label[:1].upper() + label[1:]
    note = f'<span style="font-size: 14px; line-height: 1.45; color: {INK3}">{desc}</span>' if desc else ""
    stacked = lines is not None
    top = "flex-start" if align_top or stacked else "center"
    label_pad = "padding-top: 8px;" if align_top else "padding-top: 5.5px;" if stacked else ""
    if stacked:
        control = "".join(f'<div style="display: flex; align-items: center; justify-content: flex-end; flex-wrap: wrap; gap: 8px; min-height: 32px">{bleed(line)}</div>' for line in lines)
        body = f'<div style="flex: 0 1 340px; min-width: 0; display: flex; flex-direction: column; align-items: flex-end; row-gap: 8px">{control}</div>'
    else:
        body = f'<div style="flex: 0 1 340px; min-width: 0; display: flex; align-items: center; justify-content: flex-end; flex-wrap: wrap; gap: 8px">{bleed(control)}</div>'
    pad = "12px 0" if stacked else "8px 0"
    return (f'<div data-row="" style="display: flex; align-items: {top}; gap: 24px; min-height: 56px; padding: {pad}; box-sizing: border-box">'
            f'<div style="flex: 1 1 0; min-width: 160px; display: flex; flex-direction: column; gap: 2px; {label_pad}"><span style="font-size: 15px; font-weight: 500; line-height: 1.4; color: {INK}">{text}</span>{note}</div>'
            f'{body}</div>')


def d_body(inner, pad_bottom=80):
    return f'<div style="padding: 16px 32px {pad_bottom}px; display: flex; flex-direction: column"><div style="max-width: 920px; width: 100%; align-self: center; display: flex; flex-direction: column">{inner}</div></div>'


def settings_rail(sections, active=0, query=""):
    value = f'<span style="font-size: 15px; color: {INK}">{query}</span>' if query else f'<span style="font-size: 15px; color: {INK3}">Search settings</span>'
    search = (f'<label style="display: flex; align-items: center; gap: 8px; height: 40px; padding: 0 14px; margin-bottom: 10px; border-radius: {R_CONTROL}px; background: {FILL}; box-sizing: border-box">'
              f'{ic("search", 16, INK3)}{value}</label>')
    rows = "".join(f'<span style="display: flex; align-items: center; height: 40px; padding: 0 14px; border-radius: {R_CONTROL}px; background: {SELECTED if i == active else "transparent"}; font-size: 15px; font-weight: {600 if i == active else 400}; color: {DANGER if t == "Danger zone" else INK}">{t}</span>'
                   for i, t in enumerate(sections))
    return f'<nav aria-label="Settings sections" style="width: 208px; flex-shrink: 0; display: flex; flex-direction: column; gap: 2px">{search}{rows}</nav>'


def railed_body(rail, inner, pad_bottom=80):
    return (f'<div style="padding: 16px 32px {pad_bottom}px"><div style="display: flex; align-items: flex-start; gap: 40px; max-width: 1040px">'
            f'{rail}<div style="flex: 1; min-width: 0; max-width: 680px; display: flex; flex-direction: column">{inner}</div></div></div>')


def kbd(t):
    return f'<kbd style="min-width: 20px; height: 20px; padding: 0 5px; box-sizing: border-box; display: inline-flex; align-items: center; justify-content: center; font-family: Geist, sans-serif; font-size: 12px; font-weight: 500; line-height: 1; border-radius: {R_XS}px; background: {FILL}; color: {INK3}; white-space: nowrap">{t}</kbd>'


def stream_shell(stream, composer):
    fade = f'<div style="height: 28px; margin-bottom: -28px; position: relative; z-index: 1; background: linear-gradient(transparent, {PANE})"></div>'
    return (f'<div style="flex: 1; min-height: 0; overflow: hidden; display: flex; flex-direction: column; justify-content: flex-end; padding: 0 32px">'
            f'<div style="max-width: {STREAM_W}px; margin: 0 auto; width: 100%; display: flex; flex-direction: column; gap: 24px; padding-bottom: 28px">{stream}</div></div>'
            f'{fade}<div style="position: relative; z-index: 2; padding: 0 32px 24px; background: {PANE}"><div style="max-width: {STREAM_W}px; margin: 0 auto">{composer}</div></div>')


def chat_actions():
    return button("Sessions", "ghost", "sm", "history") + iconbtn("role:activity", "Activity") + iconbtn("more", "More")


def desktop_chat():
    from conversation_boards import d_assistant, d_composer, d_step, d_user, inline_request, process, d_thought
    header = d_hero(h1("doc", identity_glyph("doc", DOC_ACCENT, 28), DOC_ACCENT), "", chat_actions(), DOC_ACCENT)
    turn = lambda *parts: f'<div style="display: flex; flex-direction: column; gap: 12px">{"".join(parts)}</div>'
    first = turn(
        d_user("Pull my last three lipid panels and tell me what moved.", DOC_ACCENT),
        process(d_thought(secs="4s"), d_step("memory", "lipid panels · 3 results", "0.4s"), d_step("read_file", "labs/2026-08-lipids.pdf", "0.3s")),
        d_assistant("Triglycerides moved most: <strong>142 → 88 mg/dL</strong> since March. LDL-P eased to 1,180 nmol/L; HDL held at 68.", hover=False),
    )
    second = turn(
        d_user("Book a follow-up draw for early November.", DOC_ACCENT),
        inline_request("@doc", "open https://labs.example.com/book?date=2026-11-04"),
    )
    body = f"""<div style="display: flex; height: 100%">
{d_sidebar(800)}
<div style="flex: 1; min-width: 0; display: flex; flex-direction: column; background: {PANE}">
{header}{stream_shell(first + second, d_composer(state="busy", name="doc", model_name="deepseek-v4.1-flash"))}
</div>
</div>
"""
    return page("Desktop · chat", 1280, 800, body, bg=PANE)


COST_DAYS = [("W", 0.16, 0.02), ("T", 0.22, 0.02), ("F", 0.08, 0.01), ("S", 0.18, 0.02), ("S", 0.96, 0.06), ("M", 0.10, 0.01),
             ("T", 0.14, 0.02), ("W", 0.15, 0.02), ("T", 0.06, 0.01), ("F", 0.13, 0.02), ("S", 0.09, 0.01), ("S", 0.30, 0.02),
             ("M", 0.26, 0.03), ("T", 0.12, 0.02)]


WG_SECTIONS = ("Overview", "Budget", "Usage", "Briefing", "Pipelines", "Members", "Invitations", "Danger zone")
PROFILE_SECTIONS = ("Overview", "Usage", "Service", "ALP", "Sandbox", "Voice", "MCP servers", "Email", "Storage", "Danger zone")


def desktop_profile_settings():
    hero = d_hero(h1("doc", identity_glyph("doc", DOC_ACCENT, 28), DOC_ACCENT) + '<span style="font-size: 20px; font-weight: 400; color: #6b6b6b; margin-left: 2px">Settings</span>', "", button("Connections", "ghost", "sm", "globe") + iconbtn("arrow-left", "Back to chat"), DOC_ACCENT)
    clean = lambda: button("Clean", "ghost", "sm")
    delete = lambda text: button(text, "danger-ghost", "sm")
    def group(name, size, files, *actions):
        facts = chip(size, "plain", "sm") + chip(files, "plain", "sm") + "".join(a for a in actions if "Delete" not in a)
        deletes = "".join(a for a in actions if "Delete" in a)
        return row(name, facts, lines=(facts, deletes)) if deletes else row(name, facts)
    storage_rows = (
        group("Conversations", "6.5 MB", "56 files", delete("Delete sessions"), delete("Delete workgroup transcripts"), delete("Delete @-mention threads"))
        + group("Skills", "133 KB", "22 files") + group("Memories", "15 KB", "5 files")
        + group("Files", "34 KB", "1 file", clean(), delete("Delete generated files"))
        + group("Knowledge", "4.5 MB", "1 file", clean())
        + group("Caches", "181 KB", "1 file", clean())
        + group("Logs", "23 MB", "146 files", clean(), delete("Delete run journals"))
        + row("everything", button("Clean everything safe · 1.3 MB · 14 items", "ghost", "sm"))
    )
    inner = (
        section("Overview", "", ''.join([
            row("home", mono12("~/.alpi/profiles/doc") + button("Reveal", "ghost", "sm")),
            row("providers", chip("openrouter", "on") + button("Providers", "ghost", "sm")),
            row("model", selectish("deepseek-v4.1-flash") + selectish("Default", mono=False)),
            row("fast model", muted("uses main model")),
            row("deep model", muted("uses main model")),
            row("vision model", muted("read_image uses main model")),
            row("fallbacks", fallbacks_field(), align_top=True),
            row("budget", selectish("$1.00/day")),
            row("workspace", field_input("/data/workspace/doc") + button("Browse…", "ghost", "sm")),
            row("appearance", selectish(f'<span style="display: inline-flex; align-items: center; gap: 8px">{identity_glyph("doc", DOC_ACCENT, 16)}blue bell</span>')),
        ]), first=True)
        + section("Usage", "last 14 days", usage_chart(days=COST_DAYS, footer="bars by cost · 30-day total $1.61 · 17.2M in / 277K out"))
        + section("Service", "daemon + network", row("daemon", button("Update alpi", "ghost", "sm") + button("Restart daemon", "ghost", "sm")))
        + section("Service", "daemon that cannot update itself", row("daemon", button("Restart daemon", "ghost", "sm")))
        + section("ALP", "peers + workgroups", ''.join([
            row("pubkey", code_chip("X+iAJ/6fQm3v…lNs=") + alink("Copy", "copy")),
            row("identity", f'<div style="flex: 1; display: flex; flex-direction: column; gap: 8px">{textarea("Ancestral, lab-savvy personal doctor; food-first, skeptical of mainstream dogma")}<div style="display: flex; align-items: center; gap: 10px; max-width: 520px"><span style="flex: 1"></span>{button("Draft", "ghost", "sm")}</div></div>', align_top=True),
            row("port", chip("unix", "on") + chip("100.99.29.84:7423", "plain", clickable=True)),
            row("peers", selectish("0 peers · 0 online", mono=False) + button("Add peer", "ghost", "sm", "plus")),
            row("concurrency", chip("unlimited", "plain")),
        ]))
        + section("Sandbox", "isolate shell commands", row("terminal", chip("off", "off") + button("Enable", "ghost", "sm")) + row("network", chip("n/a", "off") + button("Allow", "ghost", "sm")))
        + section("Voice", "text-to-speech voice", row("voice", selectish("Alvaro · Spanish (ES) · male") + button("Test", "ghost", "sm")) + row("auto-read", chip("off", "off") + button("Enable", "ghost", "sm")))
        + section("MCP servers", "external tool servers", row("servers", muted("No MCP servers yet") + button("Add MCP", "ghost", "sm", "plus")))
        + section("Email", "IMAP + Gmail accounts", row("accounts", button("Add account", "ghost", "sm", "plus")))
        + section("Storage", "disk + data usage", storage_rows)
        + section("Danger zone", "", row("Delete", button("Delete profile", "danger-ghost", "sm"), desc="Moves ~/.alpi/profiles/doc/ to ~/.alpi/.trash/. The daemon picks up the change on its next restart."))
    )
    body = f"""<div style="display: flex; height: 100%">
{d_sidebar(2420, settings_mode=True)}
<div style="flex: 1; min-width: 0; display: flex; flex-direction: column; background: {PANE}">
{hero}{railed_body(settings_rail(PROFILE_SECTIONS), inner)}
</div>
</div>
"""
    return page("Desktop · profile settings", 1280, 2420, body, bg=PANE)


def member_row(name, color, bio, hub=False, removable=True):
    tag = f'<span style="font-size: 12px; color: {INK3}">hub</span>' if hub else ""
    x = iconbtn("x", f"Remove @{name}", 28, 14) if removable and not hub else ""
    return (f'<div style="display: flex; align-items: center; gap: 16px; padding: 14px 0">'
            f'<div style="width: 130px; flex-shrink: 0; display: flex; align-items: center; gap: 7px">{profile_mark(color)}<span style="font-family: {MONO}; font-size: 15px; font-weight: 600; color: {INK}">@{name}</span>{tag}</div>'
            f'<span style="flex: 1; font-size: 15px; line-height: 1.5; color: {INK2}">{bio}</span>{x}</div>')


def desktop_wg_settings():
    from wg_settings_studies import LAUNCH, PIPELINES, RUN, invited_block, member_block, pipeline_block
    stack = wg_mark(ALPI_ACCENT, 28, "running", phase=(2, 4))
    hero = d_hero(h1("alpha", stack, "ink") + '<span style="font-size: 20px; font-weight: 400; color: #6b6b6b; margin-left: 2px">Settings</span>', "", iconbtn("pause", "Pause") + iconbtn("arrow-left", "Back to chat"), ALPI_ACCENT)
    inner = (
        section("Overview", "", ''.join([
            row("hub", f'<span style="display: inline-flex; align-items: center; gap: 8px">{identity_glyph("mira", "#6572e4", 14)}{mono12("@mira")}</span>'),
            row("status", chip("active", "on") + button("Pause", "ghost", "sm")),
            row("auto-read", chip("off", "off") + button("Enable", "ghost", "sm")),
            row("waits for members", mono12("10 min, then the round goes on")),
            row("id", mono12("wg_4f2a…9c1e") + button("Copy", "ghost", "sm")),
        ]))
        + section("Budget", "workgroup spend cap", row("used", f'<div style="flex: 1; display: flex; flex-direction: column; gap: 10px"><div style="display: flex; align-items: baseline; gap: 10px"><span style="font-size: 28px; font-weight: 600; letter-spacing: -0.018em; line-height: 1">$0.40</span><span style="font-family: {MONO}; font-size: 14px; color: {INK3}">of <span style="color: {INK2}">$5.00</span> · 8%</span><span style="flex: 1"></span>{selectish("Edit cap")}</div><div style="height: 6px; border-radius: 999px; background: {LINE2}; overflow: hidden"><div style="width: 8%; height: 100%; background: {ALPI_ACCENT}"></div></div></div>', align_top=True))
        + section("Usage", "last 14 days", usage_chart(ALPI_ACCENT, "$0.00", "12K", "310", None, None, "bars by cost · 14-day total $0.40 · 0.9M in / 22K out"))
        + section("Briefing", "what this workgroup decides", row("brief", f'<div style="flex: 1; display: flex; flex-direction: column; gap: 8px">{textarea("Weekly digest of lab results for the household; doc leads, alpi formats, yuri translates.", rows=4)}<div style="display: flex; max-width: 520px"><span style="flex: 1"></span>{button("Draft", "ghost", "sm")}</div></div>', align_top=True))
        + section("Pipelines", "declared by the recipe · read-only", '<div style="flex: 1; display: flex; flex-direction: column">' + "".join(pipeline_block(k, c, RUN if k == LAUNCH else None, pad="12px 0") for k, c in PIPELINES) + '</div>')
        + section("Members", "7 profiles", '<div style="flex: 1; display: flex; flex-direction: column">' + "".join(member_block(n) for n in ("mira", "scout", "muse", "quill", "lingua", "pixel", "lens")) + '</div>'
                  + row("add", selectish("Add member…", mono=False)))
        + section("Invitations", "pending member invites", row("join command", mono12("alpi workgroup join mira wg_4f2a…9c1e") + button("Copy", "ghost", "sm")) + '<div style="flex: 1; display: flex; flex-direction: column">' + invited_block("lingo", "clover", "#9b5ad9", "Language coach; invited, not yet joined.") + '</div>')
        + section("Danger zone", "", row("delete", alink("Delete workgroup…", danger=True)))
    )
    body = f"""<div style="display: flex; height: 100%">
{d_sidebar(2620, selected="", settings_mode=True, wg_selected=True)}
<div style="flex: 1; min-width: 0; display: flex; flex-direction: column; background: {PANE}">
{hero}{railed_body(settings_rail(WG_SECTIONS), inner)}
</div>
</div>
"""
    return page("Desktop · workgroup settings", 1280, 2620, body, bg=PANE)


def desktop_connections():
    hero = d_hero(h1("alpi", identity_glyph("alpi", AMBER, 28), "ink") + '<span style="font-size: 20px; font-weight: 400; color: #6b6b6b; margin-left: 2px">Connections</span>', "", button("Audit log", "ghost", "sm", "history") + button("New connection", "ghost", "sm", "plus") + iconbtn("arrow-left", "Back to chat"), AMBER)
    head = (f'<div style="display: grid; grid-template-columns: minmax(240px, 1fr) 126px 88px 112px; {BLEED}; min-height: 32px; align-items: center; padding: 0 12px; font-size: 14px; color: {INK3}">'
            f'<span>Connection</span><span style="text-align: right">Last activity</span><span style="text-align: right">Sessions</span><span style="text-align: right">14-day spend</span></div>')

    def metric(v, cap):
        return f'<span style="display: flex; flex-direction: column; align-items: flex-end; gap: 4px"><span style="font-family: {MONO}; font-size: 12px; font-weight: 500; color: {INK}">{v}</span><span style="font-family: {MONO}; font-size: 12px; color: {INK3}">{cap}</span></span>'

    def crow(label, sub, seen, sessions, spend, expanded=False, host=False):
        return (f'<div style="display: grid; grid-template-columns: minmax(240px, 1fr) 126px 88px 112px; min-height: 74px; align-items: center; padding: 0 12px; {"" if expanded else BLEED}">'
                f'<span style="display: flex; flex-direction: column; gap: 3px"><strong style="font-size: 15px; font-weight: 600; line-height: 1.3; color: {INK}">{label}</strong><span style="font-family: {MONO}; font-size: 12px; color: {INK3}">{sub}</span></span>'
                f'{metric(seen, "last seen")}{metric(sessions, "sessions")}{metric(spend, "14-day")}</div>')

    detail = f"""<div style="padding: 16px 12px 12px; display: flex; flex-direction: column; gap: 16px">
<div style="display: flex; align-items: baseline; gap: 8px"><span style="font-size: 16px; font-weight: 600; color: {INK}">Usage</span><span style="font-size: 12px; color: {INK3}">last 14 days</span></div>
{usage_chart(ALPI_ACCENT, "$0.00", "0", "0", None, None, "14-day total $0.00 · 0 in / 0 out", empty=True)}
<div style="padding-top: 16px; display: flex; flex-direction: column">
<div style="display: flex; align-items: center; justify-content: space-between"><h2 style="margin: 0; font-size: 16px; font-weight: 600; color: {INK}">Devices</h2><span style="display: inline-flex; align-items: center; gap: 10px"><label style="display: inline-flex; align-items: center; gap: 8px; font-size: 12px; color: {INK3}"><input type="checkbox" style="width: 16px; height: 16px; margin: 0">may add and revoke devices</label>{button("Add device", "ghost", "sm", "plus")}</span></div>
<div style="display: flex; align-items: center; min-height: 56px"><span style="flex: 1; display: flex; flex-direction: column; gap: 3px"><span style="font-size: 15px; font-weight: 500">sdk_gphone64_arm64</span><span style="font-size: 12px; color: {INK3}">mobile · 0.4.11</span></span>{mono12("7d ago", INK3)}<span style="width: 16px"></span>{alink("Revoke", danger=True)}</div>
<div style="display: flex; align-items: center; min-height: 56px"><span style="flex: 1; display: flex; flex-direction: column; gap: 3px"><span style="font-size: 15px; font-weight: 500">sdk_gphone64_arm64</span><span style="font-size: 12px; color: {INK3}">mobile · 0.5.0</span></span>{mono12("now", INK3)}<span style="width: 16px"></span>{alink("Revoke", danger=True)}</div>
</div>
</div>"""
    toolbar = search_toolbar("Search connections…", f'<span style="font-family: {MONO}; font-size: 12px; color: {INK3}">3 of 3</span>')
    table = f"""<div style="display: flex; flex-direction: column">
{toolbar}
{head}
{crow("Local host", "host.sock", "now", "10", "$1.09", host=True)}
<div style="{BLEED}; border-radius: {R_SURFACE}px; background: {CARD}"><div>{crow("emulator-android", "2 devices · admin · all profiles", "now", "4", "$0.00", expanded=True)}</div>{detail}</div>
<div style="opacity: 0.55">{crow("remote", "2 devices · admin · all profiles", "now", "4", "$0.40")}</div>
</div>"""
    body = f"""<div style="display: flex; height: 100%">
{d_sidebar(850, selected="", settings_mode=True)}
<div style="flex: 1; min-width: 0; display: flex; flex-direction: column; background: {PANE}">
{hero}{d_body(table)}
</div>
</div>
"""
    return page("Desktop · connections", 1280, 850, body, bg=PANE)


WG_GRID = "grid-template-columns: minmax(240px, 1fr) 10.5rem 76px 112px 92px; gap: 12px; padding: 0 12px"
BLEED = "width: calc(100% + 24px); margin: 0 -12px; box-sizing: border-box"


def search_toolbar(placeholder, right):
    return (f'<div style="display: flex; align-items: center; gap: 16px; min-height: 48px; padding: 0 12px; {BLEED}; color: {INK3}">'
            f'<label style="display: inline-flex; align-items: center; gap: 8px; width: 360px; height: 40px; padding: 0 14px; border-radius: {R_CONTROL}px; background: {FILL}; box-sizing: border-box">{ic("search", 16, INK3)}<span style="font-size: 15px; color: {INK3}">{placeholder}</span></label>'
            f'<span style="margin-left: auto; display: flex; align-items: center; gap: 16px">{right}</span></div>')


def seg(options, on, h=40):
    cells = "".join(f'<span role="radio" aria-checked="{"true" if o == on else "false"}" style="display: inline-flex; align-items: center; justify-content: center; height: {h - 8}px; padding: 0 14px; border-radius: 999px; font-size: {14 if h <= 32 else 15}px; font-weight: {600 if o == on else 400}; line-height: 1; color: {INK if o == on else INK2}; '
                    f'{"background: " + PANE + "; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.12)" if o == on else ""}">{o}</span>' for o in options)
    return f'<span role="radiogroup" style="display: inline-flex; align-items: center; gap: 2px; padding: 4px; border-radius: 999px; background: {FILL}; box-sizing: border-box">{cells}</span>'


def desktop_workgroups(stale=False):
    head = "".join(f'<span style="{"text-align: right" if i > 2 else ""}">{t}</span>' for i, t in enumerate(("Workgroup", "Status", "Members", "Spend", "Updated"), start=1))
    head = f'<div style="display: grid; {WG_GRID}; {BLEED}; align-items: center; min-height: 32px; font-size: 14px; color: {INK3}">{head}</div>'

    def wrow(name, accent, dot, status, members, spend, age, note="", mark=None):
        lines = (f'<span style="display: inline-flex; align-items: center; gap: 8px; font-size: 12px; color: {INK2}; white-space: nowrap">'
                 f'<span style="width: 8px; height: 8px; border-radius: 999px; background: {dot}; flex-shrink: 0"></span>{status}</span>')
        if note:
            lines += f'<span style="min-width: 0; font-family: {MONO}; font-size: 12px; color: {INK3}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis">{note}</span>'
        cell = lambda v, color: f'<span style="text-align: right; font-family: {MONO}; font-size: 12px; color: {color}">{v}</span>'
        return (f'<div style="display: grid; {WG_GRID}; {BLEED}; align-items: center; min-height: 40px">'
                f'<span style="display: flex; align-items: center; gap: 12px; min-width: 0">{wg_mark(accent, **(mark or {}))}<span style="font-size: 15px; font-weight: 400; line-height: 1; color: {INK2}">{name}</span></span>'
                f'<span style="display: flex; align-items: center; gap: 8px; min-width: 0">{lines}</span>{cell(members, INK2)}{cell(spend, INK2)}{cell(age, INK3)}</div>')

    toolbar = search_toolbar("Search workgroups…", seg(("All", "Active", "Queued", "Paused"), "All") + f'<span style="font-family: {MONO}; font-size: 12px; color: {INK3}">3 of 3</span>')
    table = (toolbar + head
             + wrow("alpha", DOC_ACCENT, "#3fb37a", "Working · media · @lingo", 3, "$0.40", "2m", "setup done", dict(state="running", phase=(2, 4)))
             + wrow("launch-crew", AMBER, "#e08a3c", "Queued · #2", 4, "$1.12", "9m", "setup done · media next", dict(state="queued"))
             + wrow("digest", "#9b5ad9", INK4, "Idle", 2, "$0.08", "1d"))
    hero = d_hero(wg_mark(AMBER, 28) + f'<span style="font-size: 20px; font-weight: 600; color: {INK}">Workgroups</span>', "", button("New workgroup", "ghost", "sm", "plus"), AMBER)
    warning = banner_bar("warning", "Workgroups may be out of date. Retrying automatically.", "Retry") if stale else ""
    body = f"""<div style="display: flex; height: 100%">
{d_sidebar(740, selected="", settings_mode=False)}
<div style="flex: 1; min-width: 0; display: flex; flex-direction: column; background: {PANE}">
{hero}{warning}{d_body(table)}
</div>
</div>
"""
    return page("Desktop · workgroups", 1280, 740, body, bg=PANE)


def banner_bar(kind, message, action="", pad="32px"):
    tone = BANNER_TEXT[kind]
    lead = f'<span style="width: 8px; height: 8px; border-radius: 50%; background: {BANNER_DOT[kind]}"></span>' if kind in BANNER_DOT else ic("alert", 16, tone)
    act = f'<button style="border: 0; background: transparent; padding: 4px 8px; margin: -4px -8px; font-family: Geist, sans-serif; font-size: 14px; font-weight: 600; line-height: 20px; color: {tone}">{action}</button>' if action else ""
    return (f'<div role="{"alert" if kind == "danger" else "status"}" style="display: flex; align-items: center; gap: 10px; padding: 12px {pad}; flex-shrink: 0; background: {banner_surface(kind)}; font-size: 14px; font-weight: 500; color: {tone}; line-height: 20px">'
            f'<span style="width: 16px; display: inline-flex; justify-content: center; flex-shrink: 0">{lead}</span><span style="flex: 1">{message}</span>{act}</div>')


def palette_row(glyph, label, sub="", hint="", selected=False, hit=""):
    text = label.replace(hit, f'<b style="font-weight: 600">{hit}</b>', 1) if hit else label
    sub_html = f'<span style="flex-shrink: 0; font-size: 14px; color: {INK3}">{sub}</span>' if sub else ""
    return (f'<div role="option" style="display: flex; align-items: center; gap: 12px; height: 44px; padding: 0 12px; border-radius: {R_CONTROL}px; background: {SELECTED if selected else "transparent"}">'
            f'<span style="width: 24px; display: inline-flex; justify-content: center; flex-shrink: 0; color: {INK3}">{glyph or ic("chev-r", 20, INK2)}</span>'
            f'<span style="min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 15px; color: {INK}">{text}</span>{sub_html}'
            f'<span style="flex: 1"></span>{key_hint(hint) if hint else ""}</div>')


def palette(query, groups, w=640, placeholder="Search profiles, sessions and commands"):
    value = f'<span style="font-size: 16px; color: {INK}">{query}</span>' if query else f'<span style="font-size: 16px; color: {INK3}">{placeholder}</span>'
    body = "".join(f'<div role="presentation" style="display: flex; align-items: center; height: 32px; padding: 0 12px; margin-top: 8px">{eyebrow(label)}</div>' + "".join(rows) for label, rows in groups)
    return (f'<div style="width: {w}px; border-radius: {R_SHEET}px; background: {ELEV}; {FLOAT}; overflow: hidden; display: flex; flex-direction: column">'
            f'<div style="display: flex; align-items: center; gap: 12px; height: 56px; padding: 0 16px">{ic("search", 20, INK3)}{value}<span style="flex: 1"></span>{kbd("esc")}</div>'
            f'<div role="listbox" style="padding: 0 8px 8px">{body}</div></div>')


def desktop_app_settings():
    card = lambda title, inner, w, big=True: (f'<div style="width: {w}px; display: flex; flex-direction: column; gap: 12px"><span style="font-size: 14px; color: {INK3}">{title}</span>'
                                              f'<div style="background: {ELEV}; {LG_FLOAT if big else SM_FLOAT}; border-radius: {R_SHEET if big else R_SURFACE}px; overflow: hidden">{inner}</div></div>')
    footer = f'<div style="background: {SIDE}; width: 248px">{sidebar_footer(app_version("desktop"), update=True)}</div>'
    import marks
    from brand_boards import app_name
    locked_row = (f'<div style="width: 360px; padding: 16px; box-sizing: border-box; display: flex; align-items: center; justify-content: space-between"><span style="font-size: 15px; color: {INK2}">Appearance</span>'
                  f'<span style="display: inline-flex; align-items: center; gap: 10px; color: {INK3}">{identity_glyph("alpi", AMBER, 28)}{mono12("Twin · brand ink")}</span></div>')
    popover = (f'<div style="width: 220px; padding: 16px; box-sizing: border-box; display: flex; flex-direction: column; gap: 10px">'
               f'<span style="display: inline-flex; align-items: center; gap: 8px">{marks.twin(26)}{app_name("alpi", 26, None, PANE)}</span>'
               f'<span style="display: inline-flex; align-items: center; gap: 8px; font-size: 15px; font-weight: 500"><span style="width: 8px; height: 8px; border-radius: 999px; background: #3fb37a"></span>Update available</span>'
               f'<span style="font-family: {MONO}; font-size: 14px; color: {INK2}">0.7.0 → 0.7.1</span>'
               f'<div style="display: flex; align-items: center; justify-content: flex-end; gap: 12px">{alink("Later")}{button("Restart &amp; install", "primary", "sm")}</div></div>')
    from notif_studies import VIEW, a_panel
    panel = a_panel(VIEW, 500)
    zoom = palette("zoom", [("View", [palette_row("", "Zoom in", hint="⌘+", selected=True, hit="Zoom"), palette_row("", "Zoom out", hint="⌘-", hit="Zoom"), palette_row("", "Reset zoom", hint="⌘0", hit="zoom")])], w=460)
    body = f"""<div style="padding: 40px; display: flex; flex-direction: column; gap: 28px; box-sizing: border-box">
<div style="display: flex; flex-direction: column; gap: 6px"><span style="font-size: 20px; font-weight: 600; letter-spacing: -0.018em; line-height: 1.3">Desktop has no settings page</span><span style="font-size: 15px; color: {INK3}; max-width: 720px; line-height: 1.5">Updates, notifications, Activity and the theme button live in the one sidebar footer; the default profile’s settings carry the same System / Light / Dark control, and text size is a command in the palette (window zoom). Mobile groups the equivalents plus pairing and biometrics under one Settings screen.</span></div>
<div style="display: flex; gap: 28px; align-items: flex-start; flex-wrap: wrap">
{card("Sidebar footer · Settings (icon, ⌘,), Notifications (⌘O, a danger dot when unread), Activity (⌘J, a danger dot when something needs you), Theme (cycles System / Light / Dark), version, in every view · version turns green when an update exists", footer, 248)}
{card("Default profile · appearance is read-only: always Twin in the brand ink", locked_row, 360)}
{card("Version popover · from the footer version, Twin and the solid ink wordmark · a small float", popover, 220, False)}
</div>
{card("Notifications · from the bell or ⌘O: a Needs you group, All / Needs you / Unread carrying the counts, unread rows in semibold (title, handle and time) with no dot, and the level Chip; rows read @handle · connection · time over the title and a two-line summary; the reader’s meta bar holds Reply, Mark unread and ••• above the title, the summary and the body; ↑↓ ⏎ R ⌫ ? on one line, ? opens the rest", panel, 1200)}
<div style="display: flex; flex-direction: column; gap: 12px"><span style="font-size: 14px; color: {INK3}">Command palette · the View group carries zoom, Preferences carries Switch theme (the footer theme button cycles the same three)</span>{zoom}</div>
</div>"""
    return page("Desktop · app-level settings", 1280, 1250, body, bg=PANE)


DESKTOP = {
    "chat": desktop_chat(),
    "profile": desktop_profile_settings(),
    "wg": desktop_wg_settings(),
    "workgroups": desktop_workgroups(),
    "workgroups-stale": desktop_workgroups(stale=True),
    "connections": desktop_connections(),
    "app": desktop_app_settings(),
}
