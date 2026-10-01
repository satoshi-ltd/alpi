from gen import app_version, button_heights, ALPI_ACCENT, DANGER, DOC_ACCENT, PROFILES, diamond, ic, mix, page, usage_chart

INK, INK2, INK3, INK4 = "#0b1117", "#3d4955", "#626e7d", "#b1bac4"
LINE, LINE2, HOVER, SELECTED = "rgba(11,17,23,0.07)", "rgba(11,17,23,0.14)", "rgba(11,17,23,0.04)", "rgba(11,17,23,0.06)"
SIDE, PANE, BG = "#f5f6f8", "#ffffff", "#eef0f2"
AMBER = "#f0b447"
MONO = "'Geist Mono', monospace"


def eyebrow(text, color=INK3, weight=500, track=0.06, size=11, extra=""):
    return (f'<span style="font-family: {MONO}; font-weight: {weight}; font-size: {size}px; line-height: 1; '
            f'letter-spacing: {track}em; text-transform: uppercase; color: {color}; {extra}">{text}</span>')


def iconbtn(name, label, size=28, icon=16, color=INK2, width=None):
    return (f'<button aria-label="{label}" style="width: {width or size}px; height: {size}px; border: 0; border-radius: 8px; background: transparent; '
            f'display: inline-flex; align-items: center; justify-content: center; padding: 0; cursor: pointer">{ic(name, icon, color)}</button>')


def button(label, variant="ghost", size="md", icon=None, icon_only=False):
    h = button_heights("desktop")[size]
    fs = {"sm": 12, "md": 13, "lg": 13, "hero": 13}[size]
    padx = {"sm": 10, "md": 12, "lg": 14, "hero": 20}[size]
    if variant == "primary":
        bg, fg = INK, PANE
    elif variant == "secondary":
        bg, fg = HOVER, INK
    elif variant == "danger":
        bg, fg = "#c14545", "#ffffff"
    elif variant == "danger-ghost":
        bg, fg = "transparent", DANGER
    else:
        bg, fg = "transparent", INK2
    if icon_only:
        return (f'<button aria-label="{label}" style="display: inline-flex; align-items: center; justify-content: center; width: {h}px; height: {h}px; padding: 0; border: 0; border-radius: 8px; '
                f'background: {bg}; cursor: pointer; flex-shrink: 0">{ic(icon, 14 if size == "sm" else 16, fg)}</button>')
    i = ic(icon, 14, fg) if icon else ""
    return (f'<button style="display: inline-flex; align-items: center; gap: 6px; height: {h}px; padding: 0 {padx}px; border: 0; border-radius: 8px; '
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
STATE_COLOR = {"needs-you": "#b3470e", "failed": DANGER, "working": ALPI_ACCENT}


def state_chip(state):
    color = STATE_COLOR[state]
    return (f'<span data-state="{state}" style="display: inline-flex; align-items: center; gap: 5px; font-family: {MONO}; font-size: 11px; line-height: 1; white-space: nowrap; color: {color}">'
            f'<span style="width: 6px; height: 6px; border-radius: 999px; background: {color}; flex-shrink: 0"></span>{STATE_TEXT[state]}</span>')


def phase_count(done, total):
    return f'<span aria-label="phase {done} of {total}" style="font-family: {MONO}; font-size: 11px; color: {ALPI_ACCENT}">{done}/{total}</span>'


def count_badge(n, tone="danger", ring="#f5f6f8"):
    bg = "#e08a3c" if tone == "warning" else "#c14545"
    return (f'<span style="position: absolute; top: -9px; right: -4px; min-width: 14px; height: 14px; padding: 0 4px; border-radius: 999px; background: {bg}; color: #fff; '
            f'font-size: 11px; font-weight: 600; line-height: 14px; white-space: nowrap; text-align: center; box-sizing: border-box">{n}</span>')


def badged(icon, label, n, tone, width=None):
    glyph = f'<span style="position: relative; display: inline-flex">{ic(icon, 14, INK2)}{count_badge(n, tone) if n else ""}</span>'
    return (f'<button aria-label="{label}" style="width: {width or 28}px; height: 28px; border: 0; border-radius: 8px; background: transparent; '
            f'display: inline-flex; align-items: center; justify-content: center; padding: 0; cursor: pointer">{glyph}</button>')


def diamond_stack(color, size=8):
    off = size // 2
    return (f'<span style="position: relative; width: {size + off + 2}px; height: {size + off + 2}px; display: inline-block">'
            f'{small_diamond(mix(color, 0.35), size).replace("display: inline-block", f"display: inline-block; position: absolute; left: {off}px; top: 0")}'
            f'{small_diamond(color, size).replace("display: inline-block", f"display: inline-block; position: absolute; left: 0; top: {off}px")}</span>')


def alink(label, icon=None, danger=False):
    color = DANGER if danger else INK2
    i = ic(icon, 12, color) if icon else ""
    return (f'<button style="display: inline-flex; align-items: center; gap: 6px; padding: 4px 8px; margin: -4px -8px; border: 0; border-radius: 6px; '
            f'background: transparent; color: {color}; font-family: Geist, sans-serif; font-weight: 500; font-size: 13px; line-height: 1; cursor: pointer">{i}{label}</button>')


def chip(text, state="plain", size="md", clickable=False):
    h = 22 if size == "md" else 18
    fs = 12 if size == "md" else 11
    dot = 10 if size == "md" else 8
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
    return (f'<span style="display: inline-flex; align-items: center; gap: {6 if size == "md" else 4}px; height: {h}px; padding: 0 8px; border-radius: 16px; '
            f'background: {bg}; color: {fg}; font-family: {MONO}; font-size: {fs}px; line-height: 1; opacity: {op}; white-space: nowrap; box-sizing: border-box">{d}{text}</span>')


def code_chip(text):
    return (f'<span style="display: inline-flex; align-items: center; padding: 4px 8px; border-radius: 6px; background: {HOVER}; '
            f'font-family: {MONO}; font-size: 12px; color: {INK2}; max-width: 360px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis">{text}</span>')


def selectish(inner, mono=True):
    fam = MONO if mono else "Geist, sans-serif"
    return (f'<span style="display: inline-flex; align-items: center; gap: 8px; height: 32px; padding: 0 12px; border-radius: 8px; background: #ffffff; '
            f'border: 0.5px solid {LINE2}; font-family: {fam}; font-size: {12 if mono else 13}px; font-weight: {400 if mono else 500}; color: {INK if mono else INK2}; box-sizing: border-box">{inner}{ic("chev-d", 12, INK3)}</span>')


def field_input(value, w=520, placeholder=False):
    color = INK3 if placeholder else INK
    return (f'<span style="display: inline-flex; align-items: center; height: 32px; max-width: {w}px; flex: 1; padding: 0 12px; border-radius: 10px; background: #ffffff; '
            f'border: 0.5px solid {LINE2}; font-size: 13px; color: {color}; box-sizing: border-box">{value}</span>')


def textarea(text, rows=3, w=520, placeholder=False):
    color = INK3 if placeholder else INK
    return (f'<div style="width: 100%; max-width: {w}px; min-height: {max(88, rows * 21 + 20)}px; padding: 8px 12px; border-radius: 8px; background: #ffffff; '
            f'border: 0.5px solid {LINE2}; font-size: 13px; line-height: 1.5; color: {color}; box-sizing: border-box">{text}</div>')


def muted(text):
    return f'<span style="font-size: 12px; color: {INK3}">{text}</span>'


def mono12(text, color=INK2):
    return f'<span style="font-family: {MONO}; font-size: 12px; color: {color}">{text}</span>'


def meterchip(value, tail, pct, color=ALPI_ACCENT):
    return (f'<span style="display: inline-flex; align-items: center; gap: 8px"><span style="font-family: {MONO}; font-size: 11px; color: {INK2}">{value}<span style="color: {INK3}">{tail}</span></span>'
            f'<span role="progressbar" aria-label="{value}{tail}" style="width: 56px; height: 5px; border-radius: 999px; background: {LINE}; overflow: hidden; display: inline-block"><span style="display: block; width: {pct * 100}%; height: 100%; background: {color}"></span></span>'
            f'<span style="font-family: {MONO}; font-size: 11px; color: {INK3}">{round(pct * 100)}%</span></span>')


SEP = f'<span style="width: 1px; height: 10px; background: {LINE2}; display: inline-block"></span>'


def sb_row(glyph, name, ts="", active=False, unread=False, dim=False, href="Desktop-Chat.dc.html", trailing=""):
    bg = SELECTED if active else "transparent"
    fw = 500 if active else (600 if unread else 400)
    color = INK if (active or unread) else INK2
    t = trailing or (f'<span style="font-family: {MONO}; font-weight: {600 if unread else 500}; font-size: 11px; color: {INK if unread else INK3}">{ts}</span>' if ts else "")
    return (f'<a href="{href}" style="display: flex; align-items: center; gap: 8px; height: 30px; padding: 0 10px; border-radius: 8px; background: {bg}; '
            f'text-decoration: none; opacity: {0.55 if dim else 1}"><span style="width: 14px; display: inline-flex; justify-content: center">{glyph}</span>'
            f'<span style="flex: 1; min-width: 0; font-size: 13px; font-weight: {fw}; color: {color}; line-height: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis">{name}</span>{t}</a>')


def small_diamond(color, size=8):
    return f'<span style="width: {size}px; height: {size}px; border-radius: 1.5px; background: {color}; transform: rotate(45deg); display: inline-block"></span>'


ROSTER_STATES = {"alpi": "working", "abby": "needs-you", "clonara": "failed"}
PINNED = ("doc",)


def sb_section(label, add=True):
    plus = (f'<button aria-label="New {label.lower()[:-1]}" style="width: 18px; height: 18px; border: 0; border-radius: 6px; background: transparent; display: inline-flex; align-items: center; justify-content: center; padding: 0; cursor: pointer">{ic("plus", 12, INK2)}</button>') if add else ""
    return f'<div style="display: flex; align-items: center; min-height: 22px; padding: 14px 10px 6px">{eyebrow(label, INK3, 500, 0.06, 11, "padding-left: 2px; flex: 1")}{plus}</div>'


def d_sidebar(h, selected="doc", settings_mode=False, new_session=False, wg_selected=False, states=None, version=None):
    version = version or app_version("desktop")
    states = ROSTER_STATES if states is None else states

    def prow(name, col, ts):
        state = states.get(name)
        return sb_row(small_diamond(col), name, ts, active=name == selected, unread=name == "yuri" and not state, dim=name == "etxea", trailing=state_chip(state) if state else "")

    pinned = "".join(prow(n, c, t) for n, c, t, _ in PROFILES if n in PINNED)
    rows = "".join(prow(n, c, t) for n, c, t, _ in PROFILES if n not in PINNED)
    wgs = (sb_row(diamond_stack(DOC_ACCENT), "alpha", active=wg_selected, href="Desktop-WorkgroupSettings.dc.html", trailing=phase_count(2, 4))
           + sb_row(diamond_stack(AMBER), "launch-crew", "2h", href="Desktop-WorkgroupSettings.dc.html"))
    if settings_mode:
        footer_main = (f'<button style="display: inline-flex; align-items: center; gap: 10px; height: 28px; padding: 0 10px; border: 0; border-radius: 8px; background: transparent; color: {INK}; font-family: Geist, sans-serif; font-size: 13px; font-weight: 500; cursor: pointer">'
                       f'{ic("search", 14, INK)}Command…{key_hint("⌘K")}</button>')
    else:
        footer_main = (f'<a href="Desktop-AppSettings.dc.html" style="display: inline-flex; align-items: center; gap: 6px; height: 28px; padding: 0 4px 0 10px; border-radius: 8px; color: {INK}; font-size: 13px; font-weight: 500; text-decoration: none">{ic("role:settings", 14, INK)}Settings</a>'
                       f'{badged("role:notifications", "Notifications · 1 unread · ⌘O", 1, "danger", 22)}{badged("role:activity", "Activity · 2 need you · ⌘J", 2, "danger", 22)}{iconbtn("sun", "Theme", 28, 14, width=22)}')
    return f"""<div style="width: 248px; height: {h}px; flex-shrink: 0; box-sizing: border-box; background: {SIDE}; border-right: 0.5px solid {LINE}; display: flex; flex-direction: column">
<div style="height: 38px; flex-shrink: 0"></div>
<div style="padding: 6px 12px 4px; display: flex; flex-direction: column">
<div style="padding: 14px 10px 6px 4px">{eyebrow("Connection")}</div>
<div style="display: flex; align-items: center; gap: 10px; height: 38px; padding: 0 12px; border-radius: 10px; background: #ffffff; border: 0.5px solid {LINE}; box-sizing: border-box">
<span style="position: relative; display: inline-flex">{ic("chip", 16, INK2)}<span style="position: absolute; right: -2px; bottom: -2px; width: 7px; height: 7px; border-radius: 999px; background: #3fb37a; border: 1.5px solid #fff; box-sizing: content-box"></span></span>
<span style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px"><span style="font-size: 13px; font-weight: 500; color: {INK}; line-height: 1">casa</span><span style="font-family: {MONO}; font-size: 11px; color: {INK3}; line-height: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis">ws://100.99.29.84:49200</span></span>
{ic("chev-d", 14, INK3)}
</div>
{"" if settings_mode else '<div style="margin-top: 8px">' + sb_row(ic("plus", 14, INK2), "New session", active=new_session) + '</div>'}
</div>
<div style="padding: 0 12px 12px; display: flex; flex-direction: column">
{sb_section("Pinned", add=False)}
{pinned}
{sb_section("Profiles")}
{rows}
{sb_section("Workgroups")}
{wgs}
</div>
<div style="flex: 1"></div>
<div style="display: flex; align-items: center; gap: {10 if settings_mode else 4}px; padding: 10px 12px; border-top: 0.5px solid {LINE}">
{footer_main}
<span style="flex: 1"></span>
<span style="font-family: {MONO}; font-size: 11px; color: {INK3}; padding: 2px 4px">{version}</span>
</div>
</div>"""


def d_hero(title_html, meta_html, actions_html, accent):
    return f"""<div style="position: relative; display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; padding: 46px 32px 18px; background: {PANE}; border-bottom: 0.5px solid {LINE}">
<div style="display: flex; flex-direction: column; gap: 8px; min-width: 0">
<div style="display: flex; align-items: baseline; gap: 12px">{title_html}</div>
<div style="display: flex; align-items: center; gap: 14px; font-size: 12px; color: {INK3}">{meta_html}</div>
</div>
<div style="display: flex; align-items: center; gap: 2px">{actions_html}</div>
<div style="position: absolute; left: 32px; bottom: -0.5px; height: 1.5px; width: 40px; background: {accent}"></div>
</div>"""


def h1(text, glyph):
    return f'{glyph}<span style="font-size: 28px; font-weight: 600; letter-spacing: -0.018em; line-height: 1; color: {INK}">{text}</span>'


def section(title, kicker="", body="", first=False):
    k = f'<span style="font-size: 12px; color: {INK3}">{kicker}</span>' if kicker else ""
    return f"""<div style="margin-top: {0 if first else 36}px; display: flex; flex-direction: column">
<div style="display: flex; align-items: baseline; gap: 10px; margin-bottom: 12px"><span style="font-size: 15px; font-weight: 600; letter-spacing: -0.005em; line-height: 1.3; color: {INK}">{title}</span>{k}</div>
{body}
</div>"""


def row(label, control, align_top=False):
    pt = "padding-top: 6px;" if align_top else ""
    text = label[:1].upper() + label[1:]
    return (f'<div style="display: flex; align-items: {"flex-start" if align_top else "center"}; gap: 24px; padding: 8px 0">'
            f'<div style="width: 120px; flex-shrink: 0; {pt}"><span style="font-size: 13px; line-height: 1.3; color: {INK2}">{text}</span></div>'
            f'<div style="flex: 1; min-width: 0; display: flex; align-items: center; flex-wrap: wrap; gap: 10px">{control}</div></div>')


def d_body(inner, pad_bottom=80):
    return f'<div style="padding: 24px 32px {pad_bottom}px; display: flex; flex-direction: column"><div style="max-width: 920px; width: 100%; align-self: center; display: flex; flex-direction: column">{inner}</div></div>'


def settings_rail(sections, active=0, query=""):
    value = f'<span style="font-size: 12px; color: {INK}">{query}</span>' if query else f'<span style="font-size: 12px; color: {INK3}">Search settings</span>'
    search = (f'<label style="display: flex; align-items: center; gap: 6px; height: 28px; padding: 0 8px; margin-bottom: 8px; border-radius: 8px; border: 0.5px solid {LINE2}; background: #ffffff; box-sizing: border-box">'
              f'{ic("search", 14, INK3)}{value}</label>')
    rows = "".join(f'<span style="display: flex; align-items: center; height: 28px; padding: 0 10px; border-radius: 8px; background: {SELECTED if i == active else "transparent"}; font-size: 13px; font-weight: 500; color: {INK}">{t}</span>'
                   for i, t in enumerate(sections))
    return f'<nav aria-label="Settings sections" style="width: 168px; flex-shrink: 0; display: flex; flex-direction: column; gap: 2px">{search}{rows}</nav>'


def railed_body(rail, inner, pad_bottom=80):
    return (f'<div style="padding: 24px 32px {pad_bottom}px"><div style="display: flex; align-items: flex-start; gap: 32px; max-width: 1120px">'
            f'{rail}<div style="flex: 1; min-width: 0; display: flex; flex-direction: column">{inner}</div></div></div>')


def kbd(t):
    return f'<kbd style="display: inline-flex; align-items: center; font-family: {MONO}; font-size: 11px; font-weight: 500; line-height: 1; padding: 1px 5px; border-radius: 4px; background: {HOVER}; border: 0.5px solid {LINE}; color: {INK2}; opacity: 0.9; white-space: nowrap">{t}</kbd>'


def desktop_chat():
    from conversation_boards import d_assistant, d_composer, d_step, d_user, inline_request, process, thought
    meta = (f'{mono12("deepseek-v4.1-flash")}{SEP}{meterchip("24K", "/1.0M", 0.024, DOC_ACCENT)}{SEP}{meterchip("$0.00", "/$1.00", 0, DOC_ACCENT)}')
    actions = (f'{button("Sessions", "ghost", "md")}{ic("chev-d", 12, INK2)}'.replace('</button>' + ic("chev-d", 12, INK2), ic("chev-d", 12, INK2) + '</button>')
               + f'<span style="display: inline-flex; align-items: flex-end; gap: 2px; height: 18px; padding: 0 4px">' + ''.join(f'<span style="width: 2px; height: {h}px; border-radius: 1px; background: {INK3}"></span>' for h in (6, 12, 8, 14, 7)) + '</span>'
               + iconbtn("more", "More"))
    header = d_hero(h1("doc", diamond(DOC_ACCENT, 14)), meta, actions, DOC_ACCENT)
    turn = lambda *parts: f'<div style="display: flex; flex-direction: column; gap: 10px">{"".join(parts)}</div>'
    first = turn(
        d_user("Pull my last three lipid panels and tell me what moved.", DOC_ACCENT),
        process(thought(secs="4s"), d_step("memory", "lipid panels · 3 results", "0.4s"), d_step("read_file", "labs/2026-08-lipids.pdf", "0.3s")),
        d_assistant("Triglycerides moved most: <strong>142 → 88 mg/dL</strong> since March. LDL-P eased to 1,180 nmol/L; HDL held at 68.", hover=False),
    )
    second = turn(
        d_user("Book a follow-up draw for early November.", DOC_ACCENT),
        inline_request("@doc", "open https://labs.example.com/book?date=2026-11-04"),
    )
    transcript = f"""<div style="flex: 1; min-height: 0; overflow: hidden; padding: 24px 32px 16px; display: flex; flex-direction: column; justify-content: flex-end">
<div style="max-width: 920px; width: 100%; align-self: center; display: flex; flex-direction: column; gap: 40px">{first}{second}</div>
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
PROFILE_SECTIONS = ("Overview", "Usage", "Service", "ALP", "Sandbox", "Voice", "MCP Servers", "Email", "Storage", "Danger Zone")


def desktop_profile_settings():
    meta = f'{mono12("deepseek-v4.1-flash")}{SEP}{meterchip("$0.00", "/$1.00", 0, DOC_ACCENT)}'
    hero = d_hero(h1("doc", diamond(DOC_ACCENT, 14)) + eyebrow("settings"), meta, button("Connections", "ghost", "md", "globe") + iconbtn("back", "Back to chat"), DOC_ACCENT)
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
            row("accent", selectish(f'<span style="display: inline-flex; align-items: center; gap: 8px">{small_diamond(DOC_ACCENT)}#3d7ea6</span>')),
        ]), first=True)
        + section("Usage", "last 14 days", usage_chart(days=COST_DAYS, footer="bars by cost · 30-day total $1.61 · 17.2M in / 277K out"))
        + section("Service", "daemon + network", row("daemon", button("Update alpi", "ghost", "sm") + button("Restart daemon", "ghost", "sm")))
        + section("Service", "daemon that cannot update itself", row("daemon", button("Restart daemon", "ghost", "sm")))
        + section("ALP", "peers + workgroups", ''.join([
            row("pubkey", code_chip("X+iAJ/6fQm3v…lNs=") + alink("Copy", "copy")),
            row("identity", f'<div style="flex: 1; display: flex; flex-direction: column; gap: 8px">{textarea("Ancestral, lab-savvy personal doctor; food-first, skeptical of mainstream dogma")}<div style="display: flex; align-items: center; gap: 10px; max-width: 520px"><span style="flex: 1"></span>{button("Draft", "ghost", "sm")}</div></div>', align_top=True),
            row("port", chip("unix", "on") + chip("100.99.29.84:7423", "plain", clickable=True)),
            row("peers", selectish("0 peers · 0 online", mono=False) + button("+ Add peer", "ghost", "sm")),
            row("concurrency", chip("unlimited", "plain")),
        ]))
        + section("Sandbox", "isolate shell commands", row("terminal", chip("off", "off") + button("Enable", "ghost", "sm")) + row("network", chip("n/a", "off") + button("Allow", "ghost", "sm")))
        + section("Voice", "text-to-speech voice", row("voice", selectish("Alvaro · Spanish (ES) · male") + button("Test", "ghost", "sm")) + row("auto-read", chip("off", "off") + button("Enable", "ghost", "sm")))
        + section("MCP Servers", "external tool servers", row("servers", muted("No MCP servers yet") + button("+ Add MCP", "ghost", "sm")))
        + section("Email", "IMAP + Gmail accounts", row("accounts", button("+ Add account", "ghost", "sm")))
        + section("Storage", "disk + data usage", storage_rows)
        + section("Danger Zone", "", row("delete", button("Delete profile", "danger-ghost", "md") + muted("removes identity, memory, skills, schedule from disk. Cannot be undone.")))
    )
    body = f"""<div style="display: flex; height: 100%">
{d_sidebar(2400, settings_mode=True)}
<div style="flex: 1; min-width: 0; display: flex; flex-direction: column; background: {PANE}">
<div style="height: 2px; background: {LINE}"></div>
{hero}{railed_body(settings_rail(PROFILE_SECTIONS), inner)}
</div>
</div>
"""
    return page("Desktop · profile settings", 1280, 2520, body, bg=BG)


def member_row(name, color, bio, hub=False, removable=True):
    tag = f'<span style="font-family: {MONO}; font-size: 11px; letter-spacing: 0.06em; color: {INK4}; padding-left: 15px">HUB</span>' if hub else ""
    x = iconbtn("x", f"Remove @{name}", 28, 14) if removable and not hub else ""
    return (f'<div style="display: flex; align-items: center; gap: 16px; padding: 14px 0; border-top: 0.5px solid {LINE}">'
            f'<div style="width: 130px; flex-shrink: 0; display: flex; flex-direction: column; gap: 4px"><span style="display: inline-flex; align-items: center; gap: 7px">{small_diamond(color, 7)}<span style="font-family: {MONO}; font-size: 13px; font-weight: 600; color: {INK}">@{name}</span></span>{tag}</div>'
            f'<span style="flex: 1; font-size: 13px; line-height: 1.5; color: {INK2}">{bio}</span>{x}</div>')


def desktop_wg_settings():
    stack = f'<span style="position: relative; width: 14px; height: 14px; display: inline-block">{small_diamond(mix(ALPI_ACCENT, 0.35), 8).replace("display: inline-block", "display: inline-block; position: absolute; left: 4px; top: 0")}{small_diamond(ALPI_ACCENT, 8).replace("display: inline-block", "display: inline-block; position: absolute; left: 0; top: 4px")}</span>'
    meta = (f'<span>hub</span>{small_diamond(DOC_ACCENT, 7)}{mono12("@doc")}{SEP}<span>members</span>{mono12("3")}{SEP}'
            f'<span style="display: inline-flex; align-items: center; gap: 6px"><span style="width: 7px; height: 7px; border-radius: 999px; background: #3fb37a"></span>active</span>{SEP}{mono12("wg_4f2a…9c1e", INK3)}')
    hero = d_hero(h1("alpha", stack) + eyebrow("settings"), meta, iconbtn("pause", "Pause") + iconbtn("back", "Back to chat"), ALPI_ACCENT)
    stages = ''.join(f'{chip("#" + s, "plain", "sm")}<span style="font-size: 11px; color: {INK3}">→</span>' for s in ("collect", "write")) + chip("#send", "plain", "sm")
    inner = (
        section("Overview", "", ''.join([
            row("hub", f'<span style="display: inline-flex; align-items: center; gap: 8px">{small_diamond(DOC_ACCENT)}{mono12("@doc")}</span>'),
            row("status", chip("active", "on") + button("Pause", "ghost", "sm")),
            row("auto-read", chip("off", "off") + button("Enable", "ghost", "sm")),
            row("id", mono12("wg_4f2a…9c1e") + button("Copy", "ghost", "sm")),
        ]))
        + section("Budget", "workgroup spend cap", row("used", f'<div style="flex: 1; display: flex; flex-direction: column; gap: 10px"><div style="display: flex; align-items: baseline; gap: 10px"><span style="font-size: 28px; font-weight: 600; letter-spacing: -0.018em; line-height: 1">$0.40</span><span style="font-family: {MONO}; font-size: 12px; color: {INK3}">of <span style="color: {INK2}">$5.00</span> · 8%</span><span style="flex: 1"></span>{selectish("Edit cap")}</div><div style="height: 6px; border-radius: 16px; background: {LINE}; overflow: hidden"><div style="width: 8%; height: 100%; background: {ALPI_ACCENT}"></div></div></div>', align_top=True))
        + section("Usage", "last 14 days", usage_chart(ALPI_ACCENT, "$0.00", "12K", "310", None, None, "bars by cost · 14-day total $0.40 · 0.9M in / 22K out"))
        + section("Briefing", "what this workgroup decides", row("brief", f'<div style="flex: 1; display: flex; flex-direction: column; gap: 8px">{textarea("Weekly digest of lab results for the household; doc leads, alpi formats, yuri translates.", rows=4)}<div style="display: flex; max-width: 520px"><span style="flex: 1"></span>{button("Draft", "ghost", "sm")}</div></div>', align_top=True))
        + section("Pipelines", "declared chains the hub runs", row("daily-digest", chip("launch", "on", "sm") + stages))
        + section("Members", "3 profiles", member_row("doc", DOC_ACCENT, "Ancestral, lab-savvy personal doctor; food-first, skeptical of mainstream dogma", hub=True)
                  + member_row("alpi", AMBER, "Household operator: schedules, reminders, the boring glue.")
                  + member_row("yuri", "#f0a58f", "Translator and editor; keeps the tone consistent across languages.")
                  + row("add", selectish("Add member…", mono=False)))
        + section("Invitations", "pending member invites", row("join command", mono12("alpi workgroup join doc wg_4f2a…9c1e") + button("Copy", "ghost", "sm")) + member_row("lingo", "#8a5cf6", "Language coach; invited, not yet joined.", removable=False))
        + section("Danger zone", "", row("delete", alink("Delete workgroup…", danger=True)))
    )
    body = f"""<div style="display: flex; height: 100%">
{d_sidebar(1760, selected="", settings_mode=True, wg_selected=True)}
<div style="flex: 1; min-width: 0; display: flex; flex-direction: column; background: {PANE}">
<div style="height: 2px; background: {LINE}"></div>
{hero}{railed_body(settings_rail(WG_SECTIONS), inner)}
</div>
</div>
"""
    return page("Desktop · workgroup settings", 1280, 1760, body, bg=BG)


def desktop_connections():
    meta = f'<span>2 paired · 2 connected</span>{SEP}<span>14-day spend {mono12("$1.49")}</span>{SEP}<span>14 sessions</span>'
    hero = d_hero(h1("alpi", diamond(AMBER, 14)) + eyebrow("connections"), meta, button("Audit log", "ghost", "md", "history") + button("New connection", "ghost", "md", "plus") + iconbtn("back", "Back to chat"), AMBER)
    head = (f'<div style="display: grid; grid-template-columns: minmax(240px, 1fr) 126px 88px 112px; min-height: 32px; align-items: center; padding: 0 10px; font-family: {MONO}; font-size: 11px; text-transform: uppercase; color: {INK3}">'
            f'<span>Connection</span><span style="text-align: right">Last activity</span><span style="text-align: right">Sessions</span><span style="text-align: right">14-day spend</span></div>')

    def metric(v, cap):
        return f'<span style="display: flex; flex-direction: column; align-items: flex-end; gap: 3px"><span style="font-family: {MONO}; font-size: 12px; font-weight: 500; color: {INK}">{v}</span><span style="font-family: {MONO}; font-size: 11px; color: {INK3}">{cap}</span></span>'

    def crow(label, sub, seen, sessions, spend, expanded=False, host=False):
        ring = f'box-shadow: inset 0 0 0 0.5px {LINE2}; border-radius: 6px;' if expanded else ""
        return (f'<div style="display: grid; grid-template-columns: minmax(240px, 1fr) 126px 88px 112px; min-height: 74px; align-items: center; padding: 0 10px; border-bottom: 0.5px solid {LINE}; {ring}">'
                f'<span style="display: flex; flex-direction: column; gap: 3px"><strong style="font-size: 13px; font-weight: 700; line-height: 1.3; color: {INK}">{label}</strong><span style="font-family: {MONO}; font-size: 11px; color: {INK3}">{sub}</span></span>'
                f'{metric(seen, "last seen")}{metric(sessions, "sessions")}{metric(spend, "14-day")}</div>')

    detail = f"""<div style="padding: 16px 10px 12px; display: flex; flex-direction: column; gap: 16px">
<div style="display: flex; align-items: baseline; gap: 8px"><span style="font-size: 15px; font-weight: 600; color: {INK}">Usage</span><span style="font-size: 12px; color: {INK3}">last 14 days</span></div>
{usage_chart(ALPI_ACCENT, "$0.00", "0", "0", None, None, "14-day total $0.00 · 0 in / 0 out", empty=True)}
<div style="border-top: 0.5px solid {LINE}; padding-top: 16px; display: flex; flex-direction: column">
<div style="display: flex; align-items: center; justify-content: space-between"><h2 style="margin: 0; font-size: 15px; font-weight: 600; color: {INK}">Devices</h2><span style="display: inline-flex; align-items: center; gap: 10px"><label style="display: inline-flex; align-items: center; gap: 6px; font-size: 12px; color: {INK3}"><input type="checkbox" style="width: 16px; height: 16px; margin: 0">may add and revoke devices</label>{button("Add device", "ghost", "sm", "plus")}</span></div>
<div style="display: flex; align-items: center; min-height: 56px; border-bottom: 0.5px solid {LINE}"><span style="flex: 1; display: flex; flex-direction: column; gap: 3px"><span style="font-size: 13px; font-weight: 500">sdk_gphone64_arm64</span><span style="font-size: 11px; color: {INK3}">mobile · 0.4.11</span></span>{mono12("7d ago", INK3)}<span style="width: 16px"></span>{alink("Revoke", danger=True)}</div>
<div style="display: flex; align-items: center; min-height: 56px; border-bottom: 0.5px solid {LINE}"><span style="flex: 1; display: flex; flex-direction: column; gap: 3px"><span style="font-size: 13px; font-weight: 500">sdk_gphone64_arm64</span><span style="font-size: 11px; color: {INK3}">mobile · 0.5.0</span></span>{mono12("now", INK3)}<span style="width: 16px"></span>{alink("Revoke", danger=True)}</div>
</div>
</div>"""
    table = f"""<div style="display: flex; flex-direction: column">
<div style="display: flex; align-items: center; gap: 12px; min-height: 42px; padding: 0 10px; border-bottom: 0.5px solid {LINE}">
<label style="display: inline-flex; align-items: center; gap: 8px; width: 360px; height: 28px; padding: 0 10px; border-radius: 8px; background: #ffffff; border: 0.5px solid {LINE2}; box-sizing: border-box">{ic("search", 12, INK3)}<span style="position: absolute; left: -9999px">Search</span><input placeholder="Search connections…" style="flex: 1; border: 0; outline: 0; background: transparent; font-family: Geist, sans-serif; font-size: 13px; color: {INK}"></label>
<span style="flex: 1"></span><span style="font-family: {MONO}; font-size: 11px; color: {INK3}">3 of 3</span>
</div>
{head}
{crow("Local host", "host.sock", "now", "10", "$1.09", host=True)}
<div style="opacity: 1">{crow("emulator-android", "2 devices · admin · all profiles", "now", "4", "$0.00", expanded=True)}{detail}</div>
<div style="opacity: 0.55">{crow("remote", "2 devices · admin · all profiles", "now", "4", "$0.40")}</div>
</div>"""
    body = f"""<div style="display: flex; height: 100%">
{d_sidebar(820, selected="", settings_mode=True)}
<div style="flex: 1; min-width: 0; display: flex; flex-direction: column; background: {PANE}">
<div style="height: 2px; background: {LINE}"></div>
{hero}{d_body(table)}
</div>
</div>
"""
    return page("Desktop · connections", 1280, 820, body, bg=BG)


WG_GRID = "grid-template-columns: minmax(240px, 1fr) 10.5rem 76px 112px 92px; gap: 20px; padding: 0 10px"


def desktop_workgroups():
    head = "".join(f'<span style="{"text-align: right" if i > 2 else ""}">{t}</span>' for i, t in enumerate(("Workgroup", "Status", "Members", "Spend", "Updated"), start=1))
    head = f'<div style="display: grid; {WG_GRID}; align-items: center; min-height: 32px; font-family: {MONO}; font-size: 11px; text-transform: uppercase; color: {INK3}">{head}</div>'

    def wrow(name, accent, dot, status, members, spend, age, note=""):
        lines = (f'<span style="display: inline-flex; align-items: center; gap: 6px; font-size: 12px; color: {INK2}; white-space: nowrap">'
                 f'<span style="width: 7px; height: 7px; border-radius: 999px; background: {dot}; flex-shrink: 0"></span>{status}</span>')
        if note:
            lines += f'<span style="padding-left: 13px; font-family: {MONO}; font-size: 11px; color: {INK3}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis">{note}</span>'
        cell = lambda v, size: f'<span style="text-align: right; font-family: {MONO}; font-size: {size}px; color: {INK2 if size == 12 else INK3}">{v}</span>'
        return (f'<div style="display: grid; {WG_GRID}; align-items: center; min-height: 64px; border-bottom: 0.5px solid {LINE}">'
                f'<span style="display: flex; align-items: center; gap: 10px; min-width: 0">{diamond_stack(accent)}<strong style="font-size: 13px; font-weight: 700; color: {INK}">{name}</strong></span>'
                f'<span style="display: flex; flex-direction: column; gap: 3px; min-width: 0">{lines}</span>{cell(members, 12)}{cell(spend, 12)}{cell(age, 11)}</div>')

    table = (head
             + wrow("alpha", DOC_ACCENT, "#3fb37a", "Working · media", 3, "$0.40", "2m", "setup done")
             + wrow("launch-crew", AMBER, "#e08a3c", "Queued · #2", 4, "$1.12", "9m", "setup done · media next")
             + wrow("digest", "#8a5cf6", INK4, "Idle", 2, "$0.08", "1d"))
    meta = f'<span>3 workgroups</span>{SEP}<span>1 working · 1 queued · 1 idle</span>'
    hero = d_hero(h1("workgroups", diamond(AMBER, 14)) + eyebrow("all profiles"), meta, button("New workgroup", "ghost", "md", "plus"), AMBER)
    body = f"""<div style="display: flex; height: 100%">
{d_sidebar(560, selected="", settings_mode=False)}
<div style="flex: 1; min-width: 0; display: flex; flex-direction: column; background: {PANE}">
<div style="height: 2px; background: {LINE}"></div>
{hero}{d_body(table)}
</div>
</div>
"""
    return page("Desktop · workgroups", 1280, 560, body, bg=BG)


def palette_row(glyph, label, sub="", hint="", selected=False, hit=""):
    text = label.replace(hit, f'<b style="font-weight: 600">{hit}</b>', 1) if hit else label
    sub_html = f'<span style="flex-shrink: 0; font-family: {MONO}; font-size: 11px; color: {INK3}">{sub}</span>' if sub else ""
    return (f'<div role="option" style="display: flex; align-items: center; gap: 10px; padding: 7px 12px; border-radius: 8px; background: {SELECTED if selected else "transparent"}">'
            f'<span style="width: 16px; display: inline-flex; justify-content: center; flex-shrink: 0; color: {INK3}">{glyph or ic("chev-r", 14, INK3)}</span>'
            f'<span style="min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 13px; color: {INK}">{text}</span>{sub_html}'
            f'<span style="flex: 1"></span>{key_hint(hint) if hint else ""}</div>')


def palette(query, groups, w=560, placeholder="Search profiles, sessions and commands…"):
    value = f'<span style="font-size: 13px; color: {INK}">{query}</span>' if query else f'<span style="font-size: 13px; color: {INK3}">{placeholder}</span>'
    body = "".join(f'<div role="presentation" style="padding: 14px 12px 6px">{eyebrow(label)}</div>' + "".join(rows) for label, rows in groups)
    return (f'<div style="width: {w}px; border-radius: 14px; background: #ffffff; border: 0.5px solid {LINE2}; box-shadow: 0 0 0 .5px rgba(11,17,23,.08), 0 18px 50px rgba(11,17,23,.10); overflow: hidden; display: flex; flex-direction: column">'
            f'<div style="display: flex; align-items: center; gap: 8px; height: 44px; padding: 0 16px; border-bottom: 0.5px solid {LINE}">{ic("search", 14, INK3)}{value}</div>'
            f'<div role="listbox" style="padding: 6px 6px 10px">{body}</div></div>')


def desktop_app_settings():
    card = lambda title, inner, w: (f'<div style="width: {w}px; display: flex; flex-direction: column; gap: 12px"><span style="font-size: 12px; color: {INK3}">{title}</span>'
                                    f'<div style="background: #ffffff; border: 0.5px solid {LINE2}; border-radius: 14px; box-shadow: 0 0 0 .5px rgba(11,17,23,.08), 0 18px 50px rgba(11,17,23,.10); overflow: hidden">{inner}</div></div>')
    footer = (f'<div style="display: flex; align-items: center; gap: 4px; padding: 10px 12px; background: {SIDE}; border-top: 0.5px solid {LINE}; width: 248px; box-sizing: border-box">'
              f'<span style="display: inline-flex; align-items: center; gap: 6px; height: 28px; padding: 0 4px 0 10px; color: {INK}; font-size: 13px; font-weight: 500">{ic("role:settings", 14, INK)}Settings</span>'
              f'{badged("role:notifications", "Notifications", 1, "danger", 22)}{badged("role:activity", "Activity · 2 need you", 2, "danger", 22)}'
              f'{iconbtn("sun", "Theme: light → dark → system", 28, 14, width=22)}<span style="flex: 1"></span><span style="font-family: {MONO}; font-size: 11px; color: #217a45; padding: 2px 4px">{app_version("desktop")}</span></div>')
    popover = (f'<div style="width: 220px; padding: 16px; box-sizing: border-box; display: flex; flex-direction: column; gap: 10px">'
               f'<span style="display: inline-flex; align-items: center; gap: 8px; font-size: 13px; font-weight: 500"><span style="width: 7px; height: 7px; border-radius: 999px; background: #3fb37a"></span>Update available</span>'
               f'<span style="font-family: {MONO}; font-size: 12px; color: {INK2}">0.7.0 → 0.7.1</span>'
               f'<div style="display: flex; align-items: center; justify-content: flex-end; gap: 12px">{alink("Later")}{button("Restart &amp; install", "primary", "sm")}</div></div>')
    notif_row = lambda color, title, sub: (f'<div style="display: flex; align-items: flex-start; gap: 10px; padding: 10px 12px; border-radius: 8px"><span style="width: 6px; height: 6px; border-radius: 999px; background: {color}; margin-top: 6px"></span>'
                                           f'<span style="flex: 1; display: flex; flex-direction: column; gap: 2px"><span style="font-size: 13px; color: {INK}">{title}</span><span style="font-family: {MONO}; font-size: 11px; color: {INK3}">{sub}</span></span></div>')
    modal = (f'<div style="width: 460px; padding: 24px; box-sizing: border-box; display: flex; flex-direction: column; gap: 12px">'
             f'<div style="display: flex; align-items: center; justify-content: space-between"><span style="font-size: 18px; font-weight: 600; line-height: 1.3">Notifications</span>{button("Mark all read", "ghost", "sm")}</div>'
             f'{notif_row("#3fb37a", "Daily brief delivered", "doc · schedule · 2h ago")}{notif_row("#c14545", "Cron job failed: weekly labs", "doc · timeout after 20m · 1d ago")}{notif_row("#e08a3c", "Provider key expiring", "openrouter · 3d ago")}</div>')
    zoom = palette("zoom", [("View", [palette_row("", "Zoom in", hint="⌘+", selected=True, hit="Zoom"), palette_row("", "Zoom out", hint="⌘-", hit="Zoom"), palette_row("", "Reset zoom", hint="⌘0", hit="zoom")])], w=460)
    body = f"""<div style="padding: 40px; display: flex; flex-direction: column; gap: 28px; box-sizing: border-box">
<div style="display: flex; flex-direction: column; gap: 6px"><span style="font-size: 22px; font-weight: 600; letter-spacing: -0.018em; line-height: 1.3">Desktop has no settings page</span><span style="font-size: 13px; color: {INK3}; max-width: 720px; line-height: 1.5">Theme, updates, notifications and Activity live in the sidebar footer; text size is the window zoom in the command palette. Mobile groups the equivalents plus pairing and biometrics under one Settings screen.</span></div>
<div style="display: flex; gap: 28px; align-items: flex-start; flex-wrap: wrap">
{card("Sidebar footer · Settings, Notifications (⌘O), Activity (⌘J, needs-you count), theme · version turns green when an update exists", footer, 248)}
{card("Version popover · from the footer version", popover, 220)}
{card("Notifications modal · from the bell", modal, 460)}
</div>
<div style="display: flex; flex-direction: column; gap: 12px"><span style="font-size: 12px; color: {INK3}">Command palette · the View group carries zoom, Preferences carries Switch theme</span>{zoom}</div>
</div>"""
    return page("Desktop · app-level settings", 1280, 740, body, bg=BG)


DESKTOP = {
    "chat": desktop_chat(),
    "profile": desktop_profile_settings(),
    "wg": desktop_wg_settings(),
    "workgroups": desktop_workgroups(),
    "connections": desktop_connections(),
    "app": desktop_app_settings(),
}
