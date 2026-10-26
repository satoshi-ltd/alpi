from gen import LIGHT_ACCENT, FIELD, GROUP_TONE, app_version, button_heights, ALPI_ACCENT, DANGER, DOC_ACCENT, FRONT, PROFILES, diamond, di as ic, identity_glyph, mix, profile_mark, page, usage_chart

INK, INK2, INK3, INK4 = "#141414", "#454545", "#6b6b6b", "#b4b4b4"
LINE, LINE2, HOVER, SELECTED = "rgba(20,20,20,0.07)", "rgba(20,20,20,0.14)", "rgba(20,20,20,0.04)", "rgba(20,20,20,0.06)"
SIDE, PANE, BG = "#f6f6f6", "#ffffff", "#f0f0f0"
AMBER = "#14110c"
EDGE = "#8c8c8c"
RING = f"0 0 0 1px {EDGE}"
ELEV = "var(--bg-elev, #ffffff)"
SM_FLOAT = "box-shadow: var(--shadow-edge-sm, 0 0 0 1px #8c8c8c)"
LG_FLOAT = "box-shadow: var(--shadow-edge-lg, 0 0 0 1px #b4b4b4)"
RING_CTRL = "box-shadow: 0 0 0 1px #b4b4b4"
CARD = "var(--card, #f4f4f4)"
MONO = "'Geist Mono', monospace"


def eyebrow(text, color=INK3, weight=500, track=0.08, size=11, extra=""):
    return (f'<span style="font-family: {MONO}; font-weight: {weight}; font-size: {size}px; line-height: 1; '
            f'letter-spacing: {track}em; text-transform: uppercase; color: {color}; {extra}">{text}</span>')


def iconbtn(name, label, size=28, icon=16, color=INK2, width=None):
    return (f'<button aria-label="{label}" style="width: {width or size}px; height: {size}px; border: 0; border-radius: 4px; background: transparent; '
            f'display: inline-flex; align-items: center; justify-content: center; padding: 0; cursor: pointer">{ic(name, icon, color)}</button>')


def button(label, variant="ghost", size="md", icon=None, icon_only=False):
    h = button_heights("desktop")[size]
    fs = {"sm": 11, "md": 13, "lg": 13, "hero": 13}[size]
    padx = {"sm": 12, "md": 12, "lg": 16, "hero": 24}[size]
    if variant == "primary":
        bg, fg = INK, PANE
    elif variant == "secondary":
        bg, fg = SELECTED, INK
    elif variant == "danger":
        bg, fg = "#c14545", "#ffffff"
    elif variant == "danger-ghost":
        bg, fg = "transparent", DANGER
    else:
        bg, fg = "transparent", INK2
    if icon_only:
        return (f'<button aria-label="{label}" style="display: inline-flex; align-items: center; justify-content: center; width: {h}px; height: {h}px; padding: 0; border: 0; border-radius: 4px; '
                f'background: {bg}; cursor: pointer; flex-shrink: 0">{ic(icon, 14 if size == "sm" else 16, fg)}</button>')
    i = ic(icon, 14, fg) if icon else ""
    return (f'<button style="display: inline-flex; align-items: center; gap: 8px; height: {h}px; padding: 0 {padx}px; border: 0; border-radius: 4px; '
            f'background: {bg}; color: {fg}; font-family: Geist, sans-serif; font-weight: 500; font-size: {fs}px; line-height: 1; cursor: pointer; white-space: nowrap">{i}{label}</button>')


MODIFIERS = "⌘⇧⌥⌃"


def key_hint(hint):
    chars = list(hint.strip())
    i = 0
    while i < len(chars) and chars[i] in MODIFIERS:
        i += 1
    rest = "".join(chars[i:])
    if not rest or " " in rest or len(rest) > 5:
        return f'<span style="font-size: 11px; color: {INK3}; white-space: nowrap; flex-shrink: 0">{hint}</span>'
    return f'<span data-keys="{hint}" style="display: inline-flex; align-items: center; gap: 2px; flex-shrink: 0">{"".join(kbd(t) for t in chars[:i] + [rest])}</span>'


STATE_TEXT = {"needs-you": "needs you", "failed": "failed", "working": "working"}
STATE_COLOR = {"needs-you": "#b3470e", "failed": DANGER, "working": INK2}


def state_chip(state, profile=None):
    color = mix(profile, 0.5, INK) if state == "working" and profile else STATE_COLOR[state]
    dot = "" if state == "working" else f'<span style="width: 6px; height: 6px; border-radius: 999px; background: {color}; flex-shrink: 0"></span>'
    return (f'<span data-state="{state}" style="display: inline-flex; align-items: center; gap: 4px; font-family: Geist, sans-serif; font-weight: 500; font-size: 11px; line-height: 1; white-space: nowrap; color: {color}">'
            f'{dot}{STATE_TEXT[state]}</span>')


def phase_count(done, total):
    return f'<span aria-label="phase {done} of {total}" style="font-family: Geist, sans-serif; font-weight: 500; font-size: 11px; color: {ALPI_ACCENT}">{done}/{total}</span>'


def bell_dot():
    return '<span style="position: absolute; top: 0; right: 0; width: 8px; height: 8px; border-radius: 999px; background: #c14545; transform: translate(25%, -25%); pointer-events: none"></span>'


def badged(icon, label, n, width=None):
    mark = bell_dot() if n else ""
    glyph = f'<span style="position: relative; display: inline-flex">{ic(icon, 14, INK2)}{mark}</span>'
    return (f'<button aria-label="{label}" style="width: {width or 28}px; height: {width or 28}px; border: 0; border-radius: 4px; background: transparent; '
            f'display: inline-flex; align-items: center; justify-content: center; padding: 0; cursor: pointer">{glyph}</button>')


def footer_button(label, icon, color=None):
    return (f'<button aria-label="{label}" style="width: 24px; height: 24px; border: 0; border-radius: 4px; background: transparent; display: inline-flex; align-items: center; justify-content: center; padding: 0; cursor: pointer">{ic(icon, 14, color or INK2)}</button>')


def footer_icons(theme="system"):
    icon = {"system": "sun-moon", "light": "sun", "dark": "moon"}[theme]
    label = {"system": "System", "light": "Light", "dark": "Dark"}
    return (badged("role:notifications", "Notifications · 1 unread · ⌘O", 1, 24)
            + badged("role:activity", "Activity · 2 need you · ⌘J", 2, 24) + footer_button(f"Theme: {label[theme]}", icon))


def sidebar_footer(version, update=False, width=None):
    w = f"width: {width}px; " if width else ""
    color = "#217a45" if update else INK3
    return (f'<div style="{w}box-sizing: border-box; display: flex; align-items: center; gap: 4px; padding: 12px 14px; border-top: 0.5px solid {LINE}">'
            f'{footer_button("Settings", "role:settings", INK)}{footer_icons()}'
            f'<span style="flex: 1 1 0; min-width: 0; display: flex; justify-content: flex-end; padding-right: 5px; font-family: {MONO}; font-size: 11px; line-height: 24px; color: {color}; white-space: nowrap">{version}</span></div>')


def diamond_stack(color, size=8):
    off = size // 2
    return (f'<span style="position: relative; width: {size + off + 2}px; height: {size + off + 2}px; display: inline-block">'
            f'{small_diamond(mix(color, 0.35), size).replace("display: inline-block", f"display: inline-block; position: absolute; left: {off}px; top: 0")}'
            f'{small_diamond(color, size).replace("display: inline-block", f"display: inline-block; position: absolute; left: 0; top: {off}px")}</span>')


def wg_mark(color, size=16):
    import folds
    return folds.fold("honeycomb", color, max(size, 16))


def alink(label, icon=None, danger=False):
    color = DANGER if danger else INK2
    i = ic(icon, 12, color) if icon else ""
    return (f'<button style="display: inline-flex; align-items: center; gap: 6px; padding: 4px 8px; margin: -4px -8px; border: 0; border-radius: 4px; '
            f'background: transparent; color: {color}; font-family: Geist, sans-serif; font-weight: 500; font-size: 13px; line-height: 1; cursor: pointer">{i}{label}</button>')


def chip(text, state="plain", size="md", clickable=False):
    h = 24 if size == "md" else 18
    fs = 11
    dot = 12 if size == "md" else 8
    bg, fg, dotc, op = HOVER, INK2, None, 1
    if state == "on":
        bg, fg, dotc = mix("#3fb37a", 0.16), "#217a45", "#3fb37a"
    elif state == "off":
        dotc, op = INK3, 0.55
    elif state == "error":
        bg, fg, dotc = mix("#c14545", 0.16), DANGER, "#c14545"
    elif state == "warn":
        fg, dotc = INK, "#e08a3c"
    elif state == "accent":
        bg, fg = mix(ALPI_ACCENT, 0.18), INK
    d = f'<span style="width: {dot}px; height: {dot}px; border-radius: 999px; background: {dotc}; flex-shrink: 0"></span>' if dotc else ""
    return (f'<span style="display: inline-flex; align-items: center; gap: {8 if size == "md" else 4}px; height: {h}px; padding: 0 8px; border-radius: 2px; '
            f'background: {bg}; color: {fg}; font-family: {MONO}; font-size: {fs}px; line-height: 1; opacity: {op}; white-space: nowrap; box-sizing: border-box">{d}{text}</span>')


def code_chip(text):
    return (f'<span style="display: inline-flex; align-items: center; padding: 4px 8px; border-radius: 2px; background: {HOVER}; '
            f'font-family: {MONO}; font-size: 11px; color: {INK2}; max-width: 360px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis">{text}</span>')


def selectish(inner, mono=True):
    fam = MONO if mono else "Geist, sans-serif"
    return (f'<span style="display: inline-flex; align-items: center; gap: 8px; height: 32px; padding: 0 12px; border-radius: 4px; background: {FIELD}; '
            f'font-family: {fam}; font-size: {11 if mono else 13}px; font-weight: {400 if mono else 500}; color: {INK if mono else INK2}; box-sizing: border-box">{inner}{ic("chev-d", 14, INK3)}</span>')


def field_input(value, w=520, placeholder=False):
    color = INK3 if placeholder else INK
    return (f'<span style="display: inline-flex; align-items: center; height: 32px; max-width: {w}px; flex: 1; padding: 0 12px; border-radius: 4px; background: {FIELD}; '
            f'font-size: 13px; color: {color}; box-sizing: border-box">{value}</span>')


def textarea(text, rows=3, w=520, placeholder=False):
    color = INK3 if placeholder else INK
    return (f'<div style="width: 100%; max-width: {w}px; min-height: {max(88, rows * 21 + 20)}px; padding: 12px; border-radius: 4px; background: {FIELD}; '
            f'font-size: 13px; line-height: 1.5; color: {color}; box-sizing: border-box">{text}</div>')


def muted(text):
    return f'<span style="font-size: 11px; color: {INK3}">{text}</span>'


def mono12(text, color=INK2):
    return f'<span style="font-family: {MONO}; font-size: 11px; color: {color}">{text}</span>'


def meterchip(value, tail, pct, color=ALPI_ACCENT):
    drawn = pct >= 0.01
    bar = (f'<span role="progressbar" aria-label="{value}{tail}" style="width: 56px; height: 5px; border-radius: 999px; background: {LINE}; overflow: hidden; display: inline-block"><span style="display: block; width: {pct * 100}%; height: 100%; background: {color}"></span></span>') if drawn else ""
    return (f'<span style="display: inline-flex; align-items: center; gap: 8px"><span style="font-family: {MONO}; font-size: 11px; color: {INK2}">{value}<span style="color: {INK3}">{tail}</span></span>'
            f'{bar}<span style="font-family: {MONO}; font-size: 11px; color: {INK3}">{f"{round(pct * 100)}%" if drawn else "—"}</span></span>')


SEP = f'<span style="width: 1px; height: 10px; background: {LINE2}; display: inline-block"></span>'


def sb_row(glyph, name, ts="", active=False, unread=False, dim=False, href="Desktop-Chat.dc.html", trailing="", accent=None, hover=False):
    hover = hover and not active
    state_row = "data-state" in trailing or dim
    bg = SELECTED if active else (HOVER if hover else "transparent")
    bar = f"box-shadow: inset 3px 0 0 {accent or AMBER};" if active else ""
    shape = "margin: 0 -12px; padding: 0 24px; border-radius: 0;" if active or hover else "padding: 0 12px; border-radius: 4px;"
    fw = 500 if active else (600 if unread else 400)
    color = INK if (active or unread) else (INK3 if dim else INK2)
    if dim and not trailing:
        trailing = f'<span style="flex-shrink: 0; margin-left: auto; font-weight: 500; font-size: 11px; line-height: 1; color: {INK3}">paused</span>'
    t = trailing or (f'<span style="font-weight: {600 if unread else 500}; font-size: 11px; line-height: 1; font-variant-numeric: tabular-nums slashed-zero; color: {INK if unread else INK3}">{ts}</span>' if ts else "")
    return (f'<a href="{href}" style="display: flex; align-items: center; gap: 8px; height: 32px; {shape} background: {bg}; {bar} '
            f'text-decoration: none"><span style="width: 16px; display: inline-flex; justify-content: center">{glyph}</span>'
            f'<span style="{"flex: 0 0 auto" if state_row else "flex: 1; min-width: 0"}; font-size: 13px; font-weight: {fw}; color: {color}; line-height: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis">{name}</span>{t}</a>')


def small_diamond(color, size=8):
    return f'<span style="width: {size}px; height: {size}px; border-radius: 1.5px; background: {color}; transform: rotate(45deg); display: inline-block"></span>'


ROSTER_STATES = {"alpi": "working", "abby": "needs-you", "clonara": "failed"}
PINNED = ("doc",)


def sb_section(label, add=True):
    plus = (f'<button aria-label="New {label.lower()[:-1]}" style="width: 24px; height: 24px; border: 0; border-radius: 4px; background: transparent; display: inline-flex; align-items: center; justify-content: center; padding: 0; cursor: pointer">{ic("plus", 14, INK2)}</button>') if add else ""
    return f'<div style="display: flex; align-items: center; min-height: 24px; padding: 16px 12px 8px">{eyebrow(label, INK3, 500, 0.08, 11, "flex: 1")}{plus}</div>'


def d_sidebar(h, selected="doc", settings_mode=False, wg_selected=False, states=None, version=None, hover=None):
    version = version or app_version("desktop")
    states = ROSTER_STATES if states is None else states

    def prow(name, col, ts):
        state = states.get(name)
        return sb_row(identity_glyph(name, col, 16, small_diamond(col)), name, ts, active=name == selected, unread=name == "yuri" and not state, dim=name == "etxea", trailing=state_chip(state, col) if state else "", accent=col, hover=name == hover)

    front = "".join(prow(n, c, t) for n, c, t, _ in PROFILES if n == FRONT)
    pinned = "".join(prow(n, c, t) for n, c, t, _ in PROFILES if n in PINNED)
    rows = "".join(prow(n, c, t) for n, c, t, _ in PROFILES if n not in PINNED and n != FRONT)
    wgs = (sb_row(wg_mark(DOC_ACCENT), "alpha", active=wg_selected, href="Desktop-WorkgroupSettings.dc.html", trailing=phase_count(2, 4), accent=DOC_ACCENT)
           + sb_row(wg_mark(AMBER), "launch-crew", "2h", href="Desktop-WorkgroupSettings.dc.html"))
    return f"""<div style="width: 248px; height: {h}px; flex-shrink: 0; box-sizing: border-box; background: {SIDE}; border-right: 0.5px solid {LINE}; display: flex; flex-direction: column">
<div style="height: 38px; flex-shrink: 0"></div>
<div style="padding: 8px 12px 4px; display: flex; flex-direction: column">
<div style="padding: 16px 12px 8px">{eyebrow("Connection")}</div>
<div style="display: flex; align-items: center; gap: 8px; height: 40px; padding: 0 12px; border-radius: 4px; background: var(--bg-elev); box-shadow: 0 0 0 0.5px {LINE}; box-sizing: border-box">
<span style="position: relative; display: inline-flex">{ic("chip", 16, INK2)}<span style="position: absolute; right: -2px; bottom: -2px; width: 8px; height: 8px; border-radius: 999px; background: #3fb37a; border: 1.5px solid var(--bg-elev); box-sizing: content-box"></span></span>
<span style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px"><span style="font-size: 13px; font-weight: 500; color: {INK}; line-height: 1.3">casa</span><span style="font-family: {MONO}; font-size: 11px; color: {INK3}; line-height: 1.3; white-space: nowrap; overflow: hidden; text-overflow: ellipsis">100.99.29.84</span></span>
{ic("chev-d", 14, INK3)}
</div>
</div>
<div style="padding: 0 12px 12px; display: flex; flex-direction: column">
<div style="padding-top: 8px">{front}</div>
{sb_section("Pinned", add=False)}
{pinned}
{sb_section("Profiles")}
{rows}
{sb_section("Workgroups")}
{wgs}
</div>
<div style="flex: 1"></div>
{sidebar_footer(version)}
</div>"""


def d_hero(title_html, meta_html, actions_html, accent):
    return f"""<div style="position: relative; display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; padding: 46px 56px 18px; background: {PANE}; border-bottom: 0.5px solid {LINE}">
<div style="display: flex; flex-direction: column; gap: 8px; min-width: 0">
<div style="display: flex; align-items: center; gap: 12px">{title_html}</div>
<div style="display: flex; align-items: center; gap: 12px; font-size: 11px; color: {INK3}">{meta_html}</div>
</div>
<div style="display: flex; align-items: center; gap: 2px; height: 32px; margin-top: -2px; flex-shrink: 0">{actions_html}</div>
</div>"""


def h1(text, glyph, crease_accent=None):
    if crease_accent:
        from brand_boards import app_crease
        return f'{glyph}{app_crease(text, 28, crease_accent, PANE, track="-0.018em")}'
    return f'{glyph}<span style="font-size: 28px; font-weight: 600; letter-spacing: -0.018em; line-height: 1; color: {INK}">{text}</span>'


def section(title, kicker="", body="", first=False):
    k = f'<span style="font-size: 11px; color: {INK3}">{kicker}</span>' if kicker else ""
    if body.count('data-row=""') and body.rstrip().endswith("</div></div>"):
        i = body.rindex('data-row=""')
        j = body.index(f"border-bottom: 0.5px solid {LINE}", i)
        body = body[:j] + "border-bottom: 0" + body[j + len(f"border-bottom: 0.5px solid {LINE}"):]
    return f"""<div style="margin-top: {0 if first else 32}px; display: flex; flex-direction: column">
<div style="display: flex; align-items: baseline; gap: 8px; margin-bottom: 8px"><span style="font-size: 15px; font-weight: 600; letter-spacing: -0.005em; line-height: 1.3; color: {INK}">{title}</span>{k}</div>
{body}
</div>"""


def ringed(control):
    if control.lstrip().startswith("<div"):
        return control
    return control.replace("background: transparent; color:", f"background: transparent; {RING_CTRL}; color:")


def row(label, control, align_top=False):
    pt = "padding-top: 8px;" if align_top else ""
    text = label[:1].upper() + label[1:]
    return (f'<div data-row="" style="display: flex; align-items: {"flex-start" if align_top else "center"}; gap: 24px; min-height: 40px; padding: 4px 0; box-sizing: border-box; border-bottom: 0.5px solid {LINE}">'
            f'<div style="width: 120px; flex-shrink: 0; {pt}"><span style="font-size: 13px; line-height: 1.3; color: {INK2}">{text}</span></div>'
            f'<div style="flex: 1; min-width: 0; display: flex; align-items: center; flex-wrap: wrap; gap: 8px">{ringed(control)}</div></div>')


def d_body(inner, pad_bottom=80):
    return f'<div style="padding: 24px 32px {pad_bottom}px; display: flex; flex-direction: column"><div style="max-width: 920px; width: 100%; align-self: center; display: flex; flex-direction: column">{inner}</div></div>'


def settings_rail(sections, active=0, query=""):
    value = f'<span style="font-size: 13px; color: {INK}">{query}</span>' if query else f'<span style="font-size: 13px; color: {INK3}">Search settings…</span>'
    search = (f'<label style="display: flex; align-items: center; gap: 8px; height: 28px; padding: 0 8px; margin-bottom: 8px; border-radius: 4px; background: {FIELD}; box-sizing: border-box">'
              f'{ic("search", 14, INK3)}{value}</label>')
    rows = "".join(f'<span style="display: flex; align-items: center; height: 28px; padding: 0 12px; border-radius: 4px; background: {SELECTED if i == active else "transparent"}; font-size: 13px; font-weight: 500; color: {INK}">{t}</span>'
                   for i, t in enumerate(sections))
    return f'<nav aria-label="Settings sections" style="width: 168px; flex-shrink: 0; display: flex; flex-direction: column; gap: 2px">{search}{rows}</nav>'


def railed_body(rail, inner, pad_bottom=80):
    return (f'<div style="padding: 24px 32px {pad_bottom}px"><div style="display: flex; align-items: flex-start; gap: 32px; max-width: 1120px">'
            f'{rail}<div style="flex: 1; min-width: 0; display: flex; flex-direction: column">{inner}</div></div></div>')


def kbd(t):
    return f'<kbd style="display: inline-flex; align-items: center; font-family: {MONO}; font-size: 11px; font-weight: 500; line-height: 1; padding: 1px 5px; border-radius: 4px; background: {HOVER}; border: 0.5px solid {LINE}; color: {INK2}; opacity: 0.9; white-space: nowrap">{t}</kbd>'


def desktop_chat():
    from conversation_boards import d_assistant, d_composer, d_step, d_user, inline_request, process, d_thought
    meta = (f'{mono12("deepseek-v4.1-flash")}{SEP}{meterchip("24K", "/1.0M", 0.024, DOC_ACCENT)}{SEP}{meterchip("$0.00", "/$1.00", 0, DOC_ACCENT)}')
    actions = (f'{button("Sessions", "ghost", "md")}{ic("chev-d", 12, INK2)}'.replace('</button>' + ic("chev-d", 12, INK2), ic("chev-d", 12, INK2) + '</button>')
               + f'<span style="display: inline-flex; align-items: flex-end; gap: 2px; height: 18px; padding: 0 4px">' + ''.join(f'<span style="width: 2px; height: {h}px; border-radius: 1px; background: {INK3}"></span>' for h in (6, 12, 8, 14, 7)) + '</span>'
               + iconbtn("more", "More"))
    header = d_hero(h1("doc", identity_glyph("doc", DOC_ACCENT, 20, diamond(DOC_ACCENT, 14)), DOC_ACCENT), meta, actions, DOC_ACCENT)
    turn = lambda *parts: f'<div style="display: flex; flex-direction: column; gap: 8px">{"".join(parts)}</div>'
    first = turn(
        d_user("Pull my last three lipid panels and tell me what moved.", DOC_ACCENT),
        process(d_thought(secs="4s"), d_step("memory", "lipid panels · 3 results", "0.4s"), d_step("read_file", "labs/2026-08-lipids.pdf", "0.3s")),
        d_assistant("Triglycerides moved most: <strong>142 → 88 mg/dL</strong> since March. LDL-P eased to 1,180 nmol/L; HDL held at 68.", hover=False),
    )
    second = turn(
        d_user("Book a follow-up draw for early November.", DOC_ACCENT),
        inline_request("@doc", "open https://labs.example.com/book?date=2026-11-04"),
    )
    transcript = f"""<div style="flex: 1; min-height: 0; overflow: hidden; padding: 24px 32px 16px; display: flex; flex-direction: column; justify-content: flex-end">
<div style="max-width: 920px; width: 100%; align-self: center; display: flex; flex-direction: column; gap: 32px">{first}{second}</div>
</div>"""
    composer = f'<div style="padding: 16px 32px 24px; background: {PANE}; border-top: 0.5px solid {LINE}"><div style="max-width: 920px; margin: 0 auto">{d_composer(state="busy", name="doc", model_name="deepseek-v4.1-flash")}</div></div>'
    body = f"""<div style="display: flex; height: 100%">
{d_sidebar(800)}
<div style="flex: 1; min-width: 0; display: flex; flex-direction: column; background: {PANE}">
{header}{transcript}{composer}
</div>
</div>
"""
    return page("Desktop · chat", 1280, 800, body, bg=BG)


COST_DAYS = [("W", 0.16, 0.02), ("T", 0.22, 0.02), ("F", 0.08, 0.01), ("S", 0.18, 0.02), ("S", 0.96, 0.06), ("M", 0.10, 0.01),
             ("T", 0.14, 0.02), ("W", 0.15, 0.02), ("T", 0.06, 0.01), ("F", 0.13, 0.02), ("S", 0.09, 0.01), ("S", 0.30, 0.02),
             ("M", 0.26, 0.03), ("T", 0.12, 0.02)]


WG_SECTIONS = ("Overview", "Budget", "Usage", "Briefing", "Pipelines", "Members", "Invitations", "Danger zone")
PROFILE_SECTIONS = ("Overview", "Usage", "Service", "ALP", "Sandbox", "Voice", "MCP servers", "Email", "Storage", "Danger zone")


def desktop_profile_settings():
    meta = f'{mono12("deepseek-v4.1-flash")}{SEP}{meterchip("$0.00", "/$1.00", 0, DOC_ACCENT)}'
    hero = d_hero(h1("doc", identity_glyph("doc", DOC_ACCENT, 20, diamond(DOC_ACCENT, 14)), DOC_ACCENT) + eyebrow("settings"), meta, button("Connections", "ghost", "md", "globe") + iconbtn("back", "Back to chat"), DOC_ACCENT)
    clean = lambda: button("Clean", "ghost", "sm")
    delete = lambda text: button(text, "danger-ghost", "sm")
    group = lambda name, size, files, *actions: row(name, chip(size, "plain", "sm") + chip(files, "plain", "sm") + "".join(actions))
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
            row("budget", selectish("$1.00/day")),
            row("workspace", field_input("/data/workspace/doc") + button("Browse…", "ghost", "sm")),
            row("appearance", selectish(f'<span style="display: inline-flex; align-items: center; gap: 8px">{identity_glyph("doc", DOC_ACCENT, 16)}blue shield</span>')),
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
        + section("Danger zone", "", row("delete", button("Delete profile", "danger-ghost", "md") + muted("removes identity, memory, skills, schedule from disk. Cannot be undone.")))
    )
    body = f"""<div style="display: flex; height: 100%">
{d_sidebar(2420, settings_mode=True)}
<div style="flex: 1; min-width: 0; display: flex; flex-direction: column; background: {PANE}">
<div style="height: 2px; background: {LINE}"></div>
{hero}{railed_body(settings_rail(PROFILE_SECTIONS), inner)}
</div>
</div>
"""
    return page("Desktop · profile settings", 1280, 2420, body, bg=BG)


def member_row(name, color, bio, hub=False, removable=True):
    tag = f'<span style="font-size: 11px; color: {INK3}">hub</span>' if hub else ""
    x = iconbtn("x", f"Remove @{name}", 28, 14) if removable and not hub else ""
    return (f'<div style="display: flex; align-items: center; gap: 16px; padding: 14px 0; border-top: 0.5px solid {LINE}">'
            f'<div style="width: 130px; flex-shrink: 0; display: flex; align-items: center; gap: 7px">{profile_mark(color)}<span style="font-family: {MONO}; font-size: 13px; font-weight: 600; color: {INK}">@{name}</span>{tag}</div>'
            f'<span style="flex: 1; font-size: 13px; line-height: 1.5; color: {INK2}">{bio}</span>{x}</div>')


def desktop_wg_settings():
    from wg_settings_studies import LAUNCH, PIPELINES, RUN, invited_block, member_block, pipeline_block
    stack = wg_mark(ALPI_ACCENT, 20)
    meta = (f'<span>hub</span>{__import__("folds").fold("crown", "#6572e4", 14)}{mono12("@mira")}{SEP}<span>members</span>{mono12("7")}{SEP}'
            f'<span style="display: inline-flex; align-items: center; gap: 6px"><span style="width: 8px; height: 8px; border-radius: 999px; background: #3fb37a"></span>active</span>{SEP}{mono12("wg_4f2a…9c1e", INK3)}')
    hero = d_hero(h1("alpha", stack, ALPI_ACCENT) + eyebrow("settings"), meta, iconbtn("pause", "Pause") + iconbtn("back", "Back to chat"), ALPI_ACCENT)
    inner = (
        section("Overview", "", ''.join([
            row("hub", f'<span style="display: inline-flex; align-items: center; gap: 8px">{__import__("folds").fold("crown", "#6572e4", 14)}{mono12("@mira")}</span>'),
            row("status", chip("active", "on") + button("Pause", "ghost", "sm")),
            row("auto-read", chip("off", "off") + button("Enable", "ghost", "sm")),
            row("id", mono12("wg_4f2a…9c1e") + button("Copy", "ghost", "sm")),
        ]))
        + section("Budget", "workgroup spend cap", row("used", f'<div style="flex: 1; display: flex; flex-direction: column; gap: 10px"><div style="display: flex; align-items: baseline; gap: 10px"><span style="font-size: 28px; font-weight: 600; letter-spacing: -0.018em; line-height: 1">$0.40</span><span style="font-family: {MONO}; font-size: 12px; color: {INK3}">of <span style="color: {INK2}">$5.00</span> · 8%</span><span style="flex: 1"></span>{selectish("Edit cap")}</div><div style="height: 6px; border-radius: 4px; background: {LINE}; overflow: hidden"><div style="width: 8%; height: 100%; background: {ALPI_ACCENT}"></div></div></div>', align_top=True))
        + section("Usage", "last 14 days", usage_chart(ALPI_ACCENT, "$0.00", "12K", "310", None, None, "bars by cost · 14-day total $0.40 · 0.9M in / 22K out"))
        + section("Briefing", "what this workgroup decides", row("brief", f'<div style="flex: 1; display: flex; flex-direction: column; gap: 8px">{textarea("Weekly digest of lab results for the household; doc leads, alpi formats, yuri translates.", rows=4)}<div style="display: flex; max-width: 520px"><span style="flex: 1"></span>{button("Draft", "ghost", "sm")}</div></div>', align_top=True))
        + section("Pipelines", "declared by the recipe · read-only", '<div style="flex: 1; display: flex; flex-direction: column">' + "".join(pipeline_block(k, c, RUN if k == LAUNCH else None, pad="12px 0") for k, c in PIPELINES) + '</div>')
        + section("Members", "7 profiles", '<div style="flex: 1; display: flex; flex-direction: column">' + "".join(member_block(n) for n in ("mira", "scout", "muse", "quill", "lingua", "pixel", "lens")) + '</div>'
                  + row("add", selectish("Add member…", mono=False)))
        + section("Invitations", "pending member invites", row("join command", mono12("alpi workgroup join mira wg_4f2a…9c1e") + button("Copy", "ghost", "sm")) + '<div style="flex: 1; display: flex; flex-direction: column">' + invited_block("lingo", "star", "#9b5ad9", "Language coach; invited, not yet joined.") + '</div>')
        + section("Danger zone", "", row("delete", alink("Delete workgroup…", danger=True)))
    )
    body = f"""<div style="display: flex; height: 100%">
{d_sidebar(2620, selected="", settings_mode=True, wg_selected=True)}
<div style="flex: 1; min-width: 0; display: flex; flex-direction: column; background: {PANE}">
<div style="height: 2px; background: {LINE}"></div>
{hero}{railed_body(settings_rail(WG_SECTIONS), inner)}
</div>
</div>
"""
    return page("Desktop · workgroup settings", 1280, 2620, body, bg=BG)


def desktop_connections():
    meta = f'<span>2 paired · 2 connected</span>{SEP}<span>14-day spend {mono12("$1.49")}</span>{SEP}<span>14 sessions</span>'
    hero = d_hero(h1("alpi", identity_glyph("alpi", AMBER, 20), AMBER) + eyebrow("connections"), meta, button("Audit log", "ghost", "md", "history") + button("New connection", "ghost", "md", "plus") + iconbtn("back", "Back to chat"), AMBER)
    head = (f'<div style="display: grid; grid-template-columns: minmax(240px, 1fr) 126px 88px 112px; {BLEED}; min-height: 32px; align-items: center; padding: 0 12px; font-family: {MONO}; font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase; color: {INK3}">'
            f'<span>Connection</span><span style="text-align: right">Last activity</span><span style="text-align: right">Sessions</span><span style="text-align: right">14-day spend</span></div>')

    def metric(v, cap):
        return f'<span style="display: flex; flex-direction: column; align-items: flex-end; gap: 4px"><span style="font-family: {MONO}; font-size: 11px; font-weight: 500; color: {INK}">{v}</span><span style="font-family: {MONO}; font-size: 11px; color: {INK3}">{cap}</span></span>'

    def crow(label, sub, seen, sessions, spend, expanded=False, host=False):
        return (f'<div style="display: grid; grid-template-columns: minmax(240px, 1fr) 126px 88px 112px; min-height: 74px; align-items: center; padding: 0 12px; {"" if expanded else BLEED}; border-bottom: 0.5px solid {LINE}">'
                f'<span style="display: flex; flex-direction: column; gap: 3px"><strong style="font-size: 13px; font-weight: 600; line-height: 1.3; color: {INK}">{label}</strong><span style="font-family: {MONO}; font-size: 11px; color: {INK3}">{sub}</span></span>'
                f'{metric(seen, "last seen")}{metric(sessions, "sessions")}{metric(spend, "14-day")}</div>')

    detail = f"""<div style="padding: 16px 12px 12px; display: flex; flex-direction: column; gap: 16px">
<div style="display: flex; align-items: baseline; gap: 8px"><span style="font-size: 15px; font-weight: 600; color: {INK}">Usage</span><span style="font-size: 11px; color: {INK3}">last 14 days</span></div>
{usage_chart(ALPI_ACCENT, "$0.00", "0", "0", None, None, "14-day total $0.00 · 0 in / 0 out", empty=True)}
<div style="border-top: 0.5px solid {LINE}; padding-top: 16px; display: flex; flex-direction: column">
<div style="display: flex; align-items: center; justify-content: space-between"><h2 style="margin: 0; font-size: 15px; font-weight: 600; color: {INK}">Devices</h2><span style="display: inline-flex; align-items: center; gap: 10px"><label style="display: inline-flex; align-items: center; gap: 8px; font-size: 11px; color: {INK3}"><input type="checkbox" style="width: 16px; height: 16px; margin: 0">may add and revoke devices</label>{button("Add device", "ghost", "sm", "plus")}</span></div>
<div style="display: flex; align-items: center; min-height: 56px; border-bottom: 0.5px solid {LINE}"><span style="flex: 1; display: flex; flex-direction: column; gap: 3px"><span style="font-size: 13px; font-weight: 500">sdk_gphone64_arm64</span><span style="font-size: 11px; color: {INK3}">mobile · 0.4.11</span></span>{mono12("7d ago", INK3)}<span style="width: 16px"></span>{alink("Revoke", danger=True)}</div>
<div style="display: flex; align-items: center; min-height: 56px; border-bottom: 0.5px solid {LINE}"><span style="flex: 1; display: flex; flex-direction: column; gap: 3px"><span style="font-size: 13px; font-weight: 500">sdk_gphone64_arm64</span><span style="font-size: 11px; color: {INK3}">mobile · 0.5.0</span></span>{mono12("now", INK3)}<span style="width: 16px"></span>{alink("Revoke", danger=True)}</div>
</div>
</div>"""
    toolbar = search_toolbar("Search connections…", f'<span style="font-family: {MONO}; font-size: 11px; color: {INK3}">3 of 3</span>')
    table = f"""<div style="display: flex; flex-direction: column">
{toolbar}
{head}
{crow("Local host", "host.sock", "now", "10", "$1.09", host=True)}
<div style="{BLEED}; border-radius: 4px; box-shadow: inset 0 0 0 0.5px {LINE2}"><div style="border-bottom: 0.5px solid {LINE}">{crow("emulator-android", "2 devices · admin · all profiles", "now", "4", "$0.00", expanded=True).replace("border-bottom: 0.5px solid " + LINE, "border-bottom: 0")}</div>{detail}</div>
<div style="opacity: 0.55">{crow("remote", "2 devices · admin · all profiles", "now", "4", "$0.40")}</div>
</div>"""
    body = f"""<div style="display: flex; height: 100%">
{d_sidebar(850, selected="", settings_mode=True)}
<div style="flex: 1; min-width: 0; display: flex; flex-direction: column; background: {PANE}">
<div style="height: 2px; background: {LINE}"></div>
{hero}{d_body(table)}
</div>
</div>
"""
    return page("Desktop · connections", 1280, 850, body, bg=BG)


WG_GRID = "grid-template-columns: minmax(240px, 1fr) 10.5rem 76px 112px 92px; gap: 12px; padding: 0 12px"
BLEED = "width: calc(100% + 24px); margin: 0 -12px; box-sizing: border-box"


def search_toolbar(placeholder, right):
    return (f'<div style="display: flex; align-items: center; gap: 16px; min-height: 42px; padding: 0 12px; {BLEED}; border-bottom: 0.5px solid {LINE}; color: {INK3}">'
            f'<label style="display: inline-flex; align-items: center; gap: 8px; width: 360px; height: 28px; padding: 0 12px; border-radius: 4px; background: {FIELD}; box-sizing: border-box">{ic("search", 14, INK3)}<span style="font-size: 13px; color: {INK3}">{placeholder}</span></label>'
            f'<span style="margin-left: auto; display: flex; align-items: center; gap: 16px">{right}</span></div>')


def seg(options, on):
    cells = "".join(f'<span style="display: inline-flex; align-items: center; min-height: 24px; padding: 0 8px; border-radius: 4px; font-size: 11px; font-weight: 500; line-height: 1; background: {INK if o == on else "transparent"}; color: {PANE if o == on else INK3}">{o}</span>' for o in options)
    return f'<span style="display: inline-flex; align-items: center; gap: 2px; padding: 2px; border-radius: 4px; background: {SELECTED}">{cells}</span>'


def desktop_workgroups(stale=False):
    head = "".join(f'<span style="{"text-align: right" if i > 2 else ""}">{t}</span>' for i, t in enumerate(("Workgroup", "Status", "Members", "Spend", "Updated"), start=1))
    head = f'<div style="display: grid; {WG_GRID}; {BLEED}; align-items: center; min-height: 32px; font-family: {MONO}; font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase; color: {INK3}">{head}</div>'

    def wrow(name, accent, dot, status, members, spend, age, note=""):
        lines = (f'<span style="display: inline-flex; align-items: center; gap: 8px; font-size: 11px; color: {INK2}; white-space: nowrap">'
                 f'<span style="width: 8px; height: 8px; border-radius: 999px; background: {dot}; flex-shrink: 0"></span>{status}</span>')
        if note:
            lines += f'<span style="min-width: 0; font-family: {MONO}; font-size: 11px; color: {INK3}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis">{note}</span>'
        cell = lambda v, color: f'<span style="text-align: right; font-family: {MONO}; font-size: 11px; color: {color}">{v}</span>'
        return (f'<div style="display: grid; {WG_GRID}; {BLEED}; align-items: center; min-height: 40px; border-bottom: 0.5px solid {LINE}">'
                f'<span style="display: flex; align-items: center; gap: 12px; min-width: 0">{wg_mark(accent)}<strong style="font-size: 13px; font-weight: 600; color: {INK}">{name}</strong></span>'
                f'<span style="display: flex; align-items: center; gap: 8px; min-width: 0">{lines}</span>{cell(members, INK2)}{cell(spend, INK2)}{cell(age, INK3)}</div>')

    toolbar = search_toolbar("Search workgroups…", seg(("All", "Active", "Queued", "Paused"), "All") + f'<span style="font-family: {MONO}; font-size: 11px; color: {INK3}">3 of 3</span>')
    table = (toolbar + head
             + wrow("alpha", DOC_ACCENT, "#3fb37a", "Working · media", 3, "$0.40", "2m", "setup done")
             + wrow("launch-crew", AMBER, "#e08a3c", "Queued · #2", 4, "$1.12", "9m", "setup done · media next")
             + wrow("digest", "#9b5ad9", INK4, "Idle", 2, "$0.08", "1d"))
    meta = f'<span>3 workgroups</span>{SEP}<span>1 working · 1 queued · 1 idle</span>'
    hero = d_hero(h1("Workgroups", wg_mark(AMBER, 20), INK3), meta, button("New workgroup", "ghost", "md", "plus"), AMBER)
    warning = banner_bar("warning", "Workgroups may be out of date. Retrying automatically.", "Retry") if stale else ""
    body = f"""<div style="display: flex; height: 100%">
{d_sidebar(740, selected="", settings_mode=False)}
<div style="flex: 1; min-width: 0; display: flex; flex-direction: column; background: {PANE}">
<div style="height: 2px; background: {LINE}"></div>
{hero}{warning}{d_body(table)}
</div>
</div>
"""
    return page("Desktop · workgroups", 1280, 740, body, bg=BG)


def banner_bar(kind, message, action="", pad="56px"):
    dot = {"warning": "#e08a3c", "danger": "#c14545", "info": INK3}[kind]
    act = f'<button style="border: 0; background: transparent; padding: 4px 8px; margin: -4px -8px; border-radius: 4px; font-family: Geist, sans-serif; font-size: 11px; font-weight: 600; line-height: 16px; color: {INK}">{action}</button>' if action else ""
    return (f'<div role="status" style="display: flex; align-items: center; gap: 8px; padding: 8px {pad}; flex-shrink: 0; border-bottom: 1px solid {INK4}; background: color-mix(in srgb, {dot} {10 if kind == "danger" else 12 if kind == "warning" else 5}%, {PANE}); font-size: 11px; color: {INK2}; line-height: 16px">'
            f'<span style="width: 16px; display: inline-flex; justify-content: center; flex-shrink: 0"><span style="width: 8px; height: 8px; border-radius: 50%; background: {dot}"></span></span><span style="flex: 1">{message}</span>{act}</div>')


def palette_row(glyph, label, sub="", hint="", selected=False, hit=""):
    text = label.replace(hit, f'<b style="font-weight: 600">{hit}</b>', 1) if hit else label
    sub_html = f'<span style="flex-shrink: 0; font-family: {MONO}; font-size: 11px; color: {INK3}">{sub}</span>' if sub else ""
    return (f'<div role="option" style="display: flex; align-items: center; gap: 8px; padding: 8px 12px; border-radius: 4px; background: {SELECTED if selected else "transparent"}">'
            f'<span style="width: 16px; display: inline-flex; justify-content: center; flex-shrink: 0; color: {INK3}">{glyph or ic("chev-r", 14, INK3)}</span>'
            f'<span style="min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 13px; color: {INK}">{text}</span>{sub_html}'
            f'<span style="flex: 1"></span>{key_hint(hint) if hint else ""}</div>')


def palette(query, groups, w=560, placeholder="Search profiles, sessions and commands…"):
    value = f'<span style="font-size: 13px; color: {INK}">{query}</span>' if query else f'<span style="font-size: 13px; color: {INK3}">{placeholder}</span>'
    body = "".join(f'<div role="presentation" style="padding: 16px 12px 8px">{eyebrow(label)}</div>' + "".join(rows) for label, rows in groups)
    return (f'<div style="width: {w}px; border-radius: 4px; background: {ELEV}; {LG_FLOAT}; overflow: hidden; display: flex; flex-direction: column">'
            f'<div style="display: flex; align-items: center; gap: 8px; height: 40px; padding: 0 16px; border-bottom: 0.5px solid {LINE}">{ic("search", 14, INK3)}{value}</div>'
            f'<div role="listbox" style="padding: 8px 8px 12px">{body}</div></div>')


def desktop_app_settings():
    card = lambda title, inner, w, big=True: (f'<div style="width: {w}px; display: flex; flex-direction: column; gap: 12px"><span style="font-size: 12px; color: {INK3}">{title}</span>'
                                              f'<div style="background: {ELEV}; {LG_FLOAT if big else SM_FLOAT}; border-radius: 4px; overflow: hidden">{inner}</div></div>')
    footer = f'<div style="background: {SIDE}; width: 248px">{sidebar_footer(app_version("desktop"), update=True)}</div>'
    from brand_boards import alpaca, app_crease
    locked_row = (f'<div style="width: 360px; padding: 16px; box-sizing: border-box; display: flex; align-items: center; justify-content: space-between"><span style="font-size: 13px; color: {INK2}">Appearance</span>'
                  f'<span style="display: inline-flex; align-items: center; gap: 10px; color: {INK3}">{identity_glyph("alpi", AMBER, 28)}{mono12("alpaca · brand accent")}</span></div>')
    popover = (f'<div style="width: 220px; padding: 16px; box-sizing: border-box; display: flex; flex-direction: column; gap: 10px">'
               f'<span style="display: inline-flex; align-items: center; gap: 8px">{alpaca(LIGHT_ACCENT, 26)}{app_crease("alpi", 26, AMBER, PANE)}</span>'
               f'<span style="display: inline-flex; align-items: center; gap: 8px; font-size: 13px; font-weight: 500"><span style="width: 8px; height: 8px; border-radius: 999px; background: #3fb37a"></span>Update available</span>'
               f'<span style="font-family: {MONO}; font-size: 12px; color: {INK2}">0.7.0 → 0.7.1</span>'
               f'<div style="display: flex; align-items: center; justify-content: flex-end; gap: 12px">{alink("Later")}{button("Restart &amp; install", "primary", "sm")}</div></div>')
    from notif_studies import VIEW, a_panel
    panel = a_panel(VIEW, 500)
    zoom = palette("zoom", [("View", [palette_row("", "Zoom in", hint="⌘+", selected=True, hit="Zoom"), palette_row("", "Zoom out", hint="⌘-", hit="Zoom"), palette_row("", "Reset zoom", hint="⌘0", hit="zoom")])], w=460)
    body = f"""<div style="padding: 40px; display: flex; flex-direction: column; gap: 28px; box-sizing: border-box">
<div style="display: flex; flex-direction: column; gap: 6px"><span style="font-size: 22px; font-weight: 600; letter-spacing: -0.018em; line-height: 1.3">Desktop has no settings page</span><span style="font-size: 13px; color: {INK3}; max-width: 720px; line-height: 1.5">Updates, notifications, Activity and the theme button live in the one sidebar footer; the default profile’s settings carry the same System / Light / Dark control, and text size is a command in the palette (window zoom). Mobile groups the equivalents plus pairing and biometrics under one Settings screen.</span></div>
<div style="display: flex; gap: 28px; align-items: flex-start; flex-wrap: wrap">
{card("Sidebar footer · Settings (icon, ⌘,), Notifications (⌘O, a danger dot when unread), Activity (⌘J, a danger dot when something needs you), Theme (cycles System / Light / Dark), version, in every view · version turns green when an update exists", footer, 248)}
{card("Default profile · appearance is read-only: always the alpaca in the brand accent", locked_row, 360)}
{card("Version popover · from the footer version, the alpaca and wordmark in crease type · a small float", popover, 220, False)}
</div>
{card("Notifications · from the bell or ⌘O: a Needs you group, All / Needs you / Unread carrying the counts, an ink dot for unread and the level Chip; rows read @handle · connection · time over the title and a two-line summary; the reader’s meta bar holds Reply, Mark unread and ••• above the title, the summary and the body; ↑↓ ⏎ R ⌫ ? on one line, ? opens the rest", panel, 1200)}
<div style="display: flex; flex-direction: column; gap: 12px"><span style="font-size: 12px; color: {INK3}">Command palette · the View group carries zoom, Preferences carries Switch theme (the footer theme button cycles the same three)</span>{zoom}</div>
</div>"""
    return page("Desktop · app-level settings", 1280, 1250, body, bg=BG)


DESKTOP = {
    "chat": desktop_chat(),
    "profile": desktop_profile_settings(),
    "wg": desktop_wg_settings(),
    "workgroups": desktop_workgroups(),
    "workgroups-stale": desktop_workgroups(stale=True),
    "connections": desktop_connections(),
    "app": desktop_app_settings(),
}
