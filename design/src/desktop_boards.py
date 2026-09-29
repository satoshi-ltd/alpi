from gen import ALPI_ACCENT, DANGER, DOC_ACCENT, PROFILES, callout, diamond, ic, mix, page, usage_chart

INK, INK2, INK3, INK4 = "#0b1117", "#3d4955", "#626e7d", "#b1bac4"
LINE, LINE2, HOVER, SELECTED = "rgba(11,17,23,0.07)", "rgba(11,17,23,0.14)", "rgba(11,17,23,0.04)", "rgba(11,17,23,0.06)"
SIDE, PANE, BG = "#f5f6f8", "#ffffff", "#eef0f2"
AMBER = "#f0b447"
MONO = "'Geist Mono', monospace"


def eyebrow(text, color=INK3, weight=500, track=0.06, size=11, extra=""):
    return (f'<span style="font-family: {MONO}; font-weight: {weight}; font-size: {size}px; line-height: 1; '
            f'letter-spacing: {track}em; text-transform: uppercase; color: {color}; {extra}">{text}</span>')


def iconbtn(name, label, size=28, icon=16, color=INK2):
    return (f'<button aria-label="{label}" style="width: {size}px; height: {size}px; border: 0; border-radius: 8px; background: transparent; '
            f'display: inline-flex; align-items: center; justify-content: center; padding: 0; cursor: pointer">{ic(name, icon, color)}</button>')


def button(label, variant="ghost", size="md", icon=None):
    h = {"sm": 24, "md": 28, "lg": 32, "hero": 40}[size]
    fs = {"sm": 12, "md": 13, "lg": 14, "hero": 14}[size]
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
    i = ic(icon, 12, fg) if icon else ""
    return (f'<button style="display: inline-flex; align-items: center; gap: 6px; height: {h}px; padding: 0 {padx}px; border: 0; border-radius: 8px; '
            f'background: {bg}; color: {fg}; font-family: Geist, sans-serif; font-weight: 500; font-size: {fs}px; line-height: 1; cursor: pointer; white-space: nowrap">{i}{label}</button>')


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


def sb_row(glyph, name, ts="", active=False, unread=False, dim=False, href="Desktop-Chat.dc.html"):
    bg = SELECTED if active else "transparent"
    fw = 500 if active else (600 if unread else 400)
    color = INK if (active or unread) else INK2
    t = f'<span style="font-family: {MONO}; font-weight: 500; font-size: 11px; color: {INK3}">{ts}</span>' if ts else ""
    return (f'<a href="{href}" style="display: flex; align-items: center; gap: 8px; height: 30px; padding: 0 10px; border-radius: 8px; background: {bg}; '
            f'text-decoration: none; opacity: {0.55 if dim else 1}"><span style="width: 14px; display: inline-flex; justify-content: center">{glyph}</span>'
            f'<span style="flex: 1; font-size: 13px; font-weight: {fw}; color: {color}; line-height: 1">{name}</span>{t}</a>')


def small_diamond(color, size=8):
    return f'<span style="width: {size}px; height: {size}px; border-radius: 1.5px; background: {color}; transform: rotate(45deg); display: inline-block"></span>'


def d_sidebar(h, selected="doc", settings_mode=False, new_session=False, wg_selected=False):
    rows = []
    for name, col, ts, _ in PROFILES:
        rows.append(sb_row(small_diamond(col), name, ts, active=name == selected, dim=name == "etxea"))
    wg = sb_row(f'<span style="position: relative; width: 14px; height: 14px; display: inline-block">{small_diamond(mix(ALPI_ACCENT, 0.35), 8).replace("display: inline-block", "display: inline-block; position: absolute; left: 4px; top: 0")}{small_diamond(ALPI_ACCENT, 8).replace("display: inline-block", "display: inline-block; position: absolute; left: 0; top: 4px")}</span>',
                "alpha", "2h", active=wg_selected, href="Desktop-WorkgroupSettings.dc.html")
    section = lambda label: (f'<div style="display: flex; align-items: center; min-height: 22px; padding: 14px 10px 6px">{eyebrow(label, INK3, 500, 0.06, 11, "padding-left: 2px; flex: 1")}'
                             f'<button aria-label="New {label.lower()}" style="width: 18px; height: 18px; border: 0; border-radius: 6px; background: transparent; display: inline-flex; align-items: center; justify-content: center; padding: 0; cursor: pointer">{ic("plus", 12, INK2)}</button></div>')
    if settings_mode:
        footer_main = (f'<button style="display: inline-flex; align-items: center; gap: 8px; height: 28px; padding: 0 10px; border: 0; border-radius: 8px; background: transparent; color: {INK2}; font-family: Geist, sans-serif; font-size: 13px; font-weight: 500; cursor: pointer">Command…'
                       f'<span style="display: inline-flex; gap: 2px"><kbd style="font-family: {MONO}; font-size: 11px; font-weight: 500; padding: 1px 5px; border-radius: 4px; background: {HOVER}; border: 0.5px solid {LINE}; color: {INK2}">⌘</kbd><kbd style="font-family: {MONO}; font-size: 11px; font-weight: 500; padding: 1px 5px; border-radius: 4px; background: {HOVER}; border: 0.5px solid {LINE}; color: {INK2}">K</kbd></span></button>')
    else:
        badge = (f'<span style="position: absolute; top: 2px; right: 2px; min-width: 14px; height: 14px; padding: 0 4px; border-radius: 999px; background: #c14545; color: #fff; '
                 f'font-size: 9px; font-weight: 600; line-height: 14px; text-align: center; box-sizing: border-box">1</span>')
        footer_main = (f'<a href="Desktop-AppSettings.dc.html" style="display: inline-flex; align-items: center; gap: 8px; height: 28px; padding: 0 10px; border-radius: 8px; color: {INK2}; font-size: 13px; text-decoration: none">{ic("gear", 14, INK2)}Settings</a>'
                       f'<span style="position: relative; display: inline-flex">{iconbtn("bell", "Notifications", 28, 14)}{badge}</span>{iconbtn("sun", "Theme", 28, 14)}')
    return f"""<div style="width: 248px; height: {h}px; flex-shrink: 0; box-sizing: border-box; background: {SIDE}; border-right: 0.5px solid {LINE}; display: flex; flex-direction: column">
<div style="height: 38px; flex-shrink: 0"></div>
<div style="padding: 6px 12px 4px; display: flex; flex-direction: column">
<div style="padding: 14px 10px 6px 4px">{eyebrow("Connection")}</div>
<div style="display: flex; align-items: center; gap: 10px; height: 38px; padding: 0 12px; border-radius: 10px; background: #ffffff; border: 0.5px solid {LINE}; box-sizing: border-box">
<span style="position: relative; display: inline-flex">{ic("chip", 16, INK2)}<span style="position: absolute; right: -2px; bottom: -2px; width: 7px; height: 7px; border-radius: 999px; background: #3fb37a; border: 1.5px solid #fff; box-sizing: content-box"></span></span>
<span style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px"><span style="font-size: 13px; font-weight: 500; color: {INK}; line-height: 1">casa</span><span style="font-family: {MONO}; font-size: 11px; color: {INK3}; line-height: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis">ws://100.99.29.84:49200</span></span>
{ic("chev-d", 14, INK3)}
</div>
<div style="margin-top: 8px">{sb_row(ic("plus", 14, INK2), "New session", active=new_session)}</div>
</div>
<div style="padding: 0 12px 12px; display: flex; flex-direction: column">
{section("Profiles")}
{''.join(rows)}
{section("Workgroups")}
{wg}
</div>
<div style="flex: 1"></div>
<div style="display: flex; align-items: center; gap: 4px; padding: 10px 12px; border-top: 0.5px solid {LINE}">
{footer_main}
<span style="flex: 1"></span>
<span style="font-family: {MONO}; font-size: 11px; color: {INK4}; padding: 2px 4px">0.6.2</span>
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
    k = f'<span style="font-size: 11px; color: {INK4}">{kicker}</span>' if kicker else ""
    return f"""<div style="margin-top: 36px; display: flex; flex-direction: column">
<div style="display: flex; align-items: baseline; gap: 10px; margin-bottom: 12px">{eyebrow(title, INK2, 600, 0.1, 11)}{k}</div>
{body}
</div>"""


def row(label, control, align_top=False):
    pt = "padding-top: 6px" if align_top else ""
    return (f'<div style="display: flex; align-items: {"flex-start" if align_top else "center"}; gap: 24px; padding: 8px 0">'
            f'<div style="width: 96px; flex-shrink: 0; {pt}">{eyebrow(label)}</div>'
            f'<div style="flex: 1; min-width: 0; display: flex; align-items: center; flex-wrap: wrap; gap: 10px">{control}</div></div>')


def d_body(inner, pad_bottom=80):
    return f'<div style="padding: 24px 32px {pad_bottom}px; display: flex; flex-direction: column"><div style="max-width: 920px; width: 100%; align-self: center; display: flex; flex-direction: column">{inner}</div></div>'


def kbd(t):
    return f'<kbd style="font-family: {MONO}; font-size: 11px; font-weight: 500; padding: 1px 5px; border-radius: 4px; background: {HOVER}; border: 0.5px solid {LINE}; color: {INK2}; opacity: 0.9">{t}</kbd>'


def desktop_chat():
    meta = (f'{mono12("deepseek-v4.1-flash")}{SEP}{meterchip("24K", "/1.0M", 0.024, DOC_ACCENT)}{SEP}{meterchip("$0.00", "/$1.00", 0, DOC_ACCENT)}')
    actions = (f'{button("Sessions", "ghost", "md")}{ic("chev-d", 12, INK2)}'.replace('</button>' + ic("chev-d", 12, INK2), ic("chev-d", 12, INK2) + '</button>')
               + f'<span style="display: inline-flex; align-items: flex-end; gap: 2px; height: 18px; padding: 0 4px">' + ''.join(f'<span style="width: 2px; height: {h}px; border-radius: 1px; background: {INK3}"></span>' for h in (6, 12, 8, 14, 7)) + '</span>'
               + iconbtn("more", "More"))
    header = d_hero(h1("doc", diamond(DOC_ACCENT, 14)), meta, actions, DOC_ACCENT)
    transcript = f"""<div style="flex: 1; padding: 24px 32px 16px; display: flex; flex-direction: column; justify-content: flex-end">
<div style="max-width: 920px; width: 100%; align-self: center; display: flex; flex-direction: column; gap: 24px">
<div style="display: flex; flex-direction: column; align-items: flex-end; gap: 4px">
<div style="max-width: 76%; padding: 12px 16px; border-radius: 14px 6px 14px 14px; background: {mix(DOC_ACCENT, 0.12)}; font-size: 15px; line-height: 1.65">Hi</div>
<div style="display: flex; align-items: center; gap: 4px"><span style="font-family: {MONO}; font-size: 11px; color: {INK3}">42d</span>{iconbtn("refresh", "Edit", 24, 12)}{iconbtn("copy", "Copy", 24, 12)}</div>
</div>
<div style="display: flex; flex-direction: column; gap: 6px">
<div style="display: flex; align-items: center; gap: 8px; font-family: {MONO}; font-size: 12px; color: {INK3}">{ic("chev-r", 11, INK3)}<span>thinking · 4s</span><span style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis">The user just said "Hi". A greeting. Reply warmly and ask what they need…</span></div>
<div style="font-size: 15px; line-height: 1.65; letter-spacing: -0.003em; color: {INK}">Morning. What do you have for me today: labs, sleep, training, or something deeper?</div>
</div>
</div>
</div>"""
    composer = f"""<div style="padding: 16px 32px 24px; background: {PANE}; border-top: 0.5px solid {LINE}">
<div style="max-width: 920px; width: 100%; margin: 0 auto; display: flex; flex-direction: column; gap: 8px; padding: 14px 16px 10px; border-radius: 16px; background: #ffffff; border: 0.5px solid {LINE2}; box-sizing: border-box">
<label style="display: block"><span style="position: absolute; left: -9999px">Message</span><input placeholder="Message doc…" style="width: 100%; min-height: 22px; border: 0; outline: 0; background: transparent; font-family: Geist, sans-serif; font-size: 14px; line-height: 1.5; color: {INK}; padding: 0; box-sizing: border-box"></label>
<div style="display: flex; align-items: center; gap: 8px">
<span style="display: inline-flex; align-items: center; gap: 10px; font-size: 11px; color: {INK3}"><span>@ mention</span><span style="display: inline-flex; align-items: center; gap: 4px">{kbd("⌘")}{kbd("↵")} send</span></span>
<span style="flex: 1"></span>
{iconbtn("clip", "Attach", 28, 14)}
<button style="display: inline-flex; align-items: center; gap: 6px; height: 28px; padding: 0 10px; border: 0; border-radius: 8px; background: transparent; color: {INK2}; font-family: {MONO}; font-size: 12px; cursor: pointer">deepseek-v4.1-flash {ic("chev-d", 12, INK3)}</button>
<button aria-label="Send" style="width: 30px; height: 30px; border: 0; border-radius: 10px; background: {LINE}; display: inline-flex; align-items: center; justify-content: center; cursor: pointer">{ic("up", 14, INK3)}</button>
</div>
</div>
</div>"""
    body = f"""<div style="display: flex; height: 100%">
{d_sidebar(800)}
<div style="flex: 1; min-width: 0; display: flex; flex-direction: column; background: {PANE}">
{header}{transcript}{composer}
</div>
</div>
{callout(1, 640, 78)}{callout(2, 232, 300)}{callout(3, 232, 752)}{callout(6, 1230, 730)}"""
    return page("Desktop · chat", 1280, 800, body, bg=BG)


def desktop_profile_settings():
    meta = f'{mono12("deepseek-v4.1-flash")}{SEP}{meterchip("$0.00", "/$1.00", 0, DOC_ACCENT)}'
    hero = d_hero(h1("doc", diamond(DOC_ACCENT, 14)) + eyebrow("settings"), meta, iconbtn("back", "Back to chat"), DOC_ACCENT)
    storage = [("sessions", "6.5 MB", "56 files"), ("skills", "133 KB", "22 files"), ("memories", "15 KB", "5 files"), ("knowledge", "4.5 MB", "1 file"),
               ("outputs", "34 KB", "1 file"), ("logs", "1.1 MB", "11 files"), ("runs", "21.8 MB", "135 files")]
    storage_rows = ''.join(row(k, chip(a, "plain", "sm") + chip(b, "plain", "sm")) for k, a, b in storage)
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
        + section("Usage", "last 14 days", usage_chart())
        + section("Service", "daemon + network", row("daemon", button("Update alpi", "ghost", "sm") + button("Restart daemon", "ghost", "sm")))
        + section("ALP", "peers + workgroups", ''.join([
            row("pubkey", code_chip("X+iAJ/6fQm3v…lNs=") + alink("Copy", "copy")),
            row("identity", f'<div style="flex: 1; display: flex; flex-direction: column; gap: 8px">{textarea("Ancestral, lab-savvy personal doctor; food-first, skeptical of mainstream dogma")}<div style="display: flex; align-items: center; gap: 10px; max-width: 520px"><span style="flex: 1"></span>{button("Draft", "ghost", "sm")}</div></div>', align_top=True),
            row("port", chip("unix", "on") + chip("100.99.29.84:7423", "plain", clickable=True)),
            row("peers", selectish("0 peers · 0 online", mono=False) + button("+ Add peer", "ghost", "sm")),
            row("concurrency", chip("unlimited", "plain")),
        ]))
        + section("Sandbox", "isolate shell commands", row("terminal", chip("off", "off") + button("Enable", "ghost", "sm")) + row("network", chip("n/a", "off") + button("Allow", "ghost", "sm")))
        + section("Voice", "text-to-speech voice", row("voice", selectish("Alvaro · Spanish (ES) · male") + button("Test", "ghost", "sm")) + row("auto-read", chip("off", "off") + button("Enable", "ghost", "sm")))
        + section("MCP servers", "external tool servers", row("mcps", muted("none") + button("+ Add MCP", "ghost", "sm")))
        + section("Email", "IMAP + Gmail accounts", row("accounts", button("+ Add account", "ghost", "sm")))
        + section("Storage", "disk + data usage", storage_rows + row("reclaim", button("Clean · 21.8 MB · 135 items", "ghost", "sm") + muted("runs older than 30 days")))
        + section("Danger zone", "", row("delete", button("Delete profile", "danger-ghost", "md") + muted("removes identity, memory, skills, schedule from disk. Cannot be undone.")))
    )
    body = f"""<div style="display: flex; height: 100%">
{d_sidebar(2600, settings_mode=True)}
<div style="flex: 1; min-width: 0; display: flex; flex-direction: column; background: {PANE}">
<div style="height: 2px; background: {LINE}"></div>
{hero}{d_body(inner)}
</div>
</div>
{callout(8, 640, 60)}{callout(9, 300, 240)}{callout(4, 300, 350)}{callout(10, 300, 940)}{callout(5, 300, 1100)}{callout(7, 300, 1330)}"""
    return page("Desktop · profile settings", 1280, 2600, body, bg=BG)


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
    hero = d_hero(h1("alpha", stack) + eyebrow("settings"), meta, iconbtn("clock", "Pause") + iconbtn("back", "Back to chat"), ALPI_ACCENT)
    stages = ''.join(f'{chip("#" + s, "plain", "sm")}<span style="font-size: 11px; color: {INK3}">→</span>' for s in ("collect", "write")) + chip("#send", "plain", "sm")
    inner = (
        section("Overview", "", ''.join([
            row("hub", f'<span style="display: inline-flex; align-items: center; gap: 8px">{small_diamond(DOC_ACCENT)}{mono12("@doc")}</span>'),
            row("status", chip("active", "on") + button("Pause", "ghost", "sm")),
            row("auto-read", chip("off", "off") + button("Enable", "ghost", "sm")),
            row("id", mono12("wg_4f2a…9c1e") + button("Copy", "ghost", "sm")),
        ]), first=True)
        + section("Budget", "workgroup spend cap", row("used", f'<div style="flex: 1; display: flex; flex-direction: column; gap: 10px"><div style="display: flex; align-items: baseline; gap: 10px"><span style="font-size: 28px; font-weight: 600; letter-spacing: -0.018em; line-height: 1">$0.40</span><span style="font-family: {MONO}; font-size: 12px; color: {INK3}">of <span style="color: {INK2}">$5.00</span> · 8%</span><span style="flex: 1"></span>{button("Edit", "ghost", "sm")}</div><div style="height: 6px; border-radius: 16px; background: {LINE}; overflow: hidden"><div style="width: 8%; height: 100%; background: {ALPI_ACCENT}"></div></div></div>', align_top=True))
        + section("Usage", "last 14 days", usage_chart(ALPI_ACCENT, "$0.00", "12K", "310", None, None, "14-day total $0.40 · 0.9M in / 22K out"))
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
{d_sidebar(1900, selected="", settings_mode=True, wg_selected=True)}
<div style="flex: 1; min-width: 0; display: flex; flex-direction: column; background: {PANE}">
<div style="height: 2px; background: {LINE}"></div>
{hero}{d_body(inner)}
</div>
</div>
{callout(8, 640, 60)}{callout(11, 300, 400)}{callout(13, 300, 1020)}{callout(12, 300, 1130)}"""
    return page("Desktop · workgroup settings", 1280, 1900, body, bg=BG)


def desktop_connections():
    meta = f'<span>2 paired · 2 connected</span>{SEP}<span>14-day spend {mono12("$1.49")}</span>{SEP}<span>14 sessions</span>'
    hero = d_hero(h1("alpi", diamond(AMBER, 14)) + eyebrow("connections"), meta, button("Activity", "ghost", "md", "clock") + button("New connection", "ghost", "md", "plus") + iconbtn("back", "Back to chat"), AMBER)
    head = (f'<div style="display: grid; grid-template-columns: minmax(240px, 1fr) 126px 88px 112px; min-height: 32px; align-items: center; padding: 0 10px; font-family: {MONO}; font-size: 10px; text-transform: uppercase; color: {INK4}">'
            f'<span>Connection</span><span style="text-align: right">Last activity</span><span style="text-align: right">Sessions</span><span style="text-align: right">14-day spend</span></div>')

    def metric(v, cap):
        return f'<span style="display: flex; flex-direction: column; align-items: flex-end; gap: 3px"><span style="font-family: {MONO}; font-size: 12px; font-weight: 500; color: {INK}">{v}</span><span style="font-family: {MONO}; font-size: 10px; color: {INK3}">{cap}</span></span>'

    def crow(label, sub, seen, sessions, spend, expanded=False, host=False):
        ring = f'box-shadow: inset 0 0 0 0.5px {LINE2}; border-radius: 6px;' if expanded else ""
        return (f'<div style="display: grid; grid-template-columns: minmax(240px, 1fr) 126px 88px 112px; min-height: 74px; align-items: center; padding: 0 10px; border-bottom: 0.5px solid {LINE}; {ring}">'
                f'<span style="display: flex; flex-direction: column; gap: 3px"><strong style="font-size: 13px; font-weight: 700; line-height: 1.3; color: {INK}">{label}</strong><span style="font-family: {MONO}; font-size: 11px; color: {INK3}">{sub}</span></span>'
                f'{metric(seen, "last seen")}{metric(sessions, "sessions")}{metric(spend, "14-day")}</div>')

    detail = f"""<div style="padding: 16px 10px 12px; display: flex; flex-direction: column; gap: 16px">
<div style="display: flex; align-items: baseline"><span style="font-family: {MONO}; font-size: 11px; color: {INK3}">USAGE</span><span style="margin-left: 12px; font-size: 11px; color: {INK4}">last 14 days</span></div>
{usage_chart(ALPI_ACCENT, "$0.00", "0", "0", None, None, "14-day total $0.00 · 0 in / 0 out", empty=True)}
<div style="border-top: 0.5px solid {LINE}; padding-top: 16px; display: flex; flex-direction: column">
<div style="display: flex; align-items: center; justify-content: space-between"><h2 style="margin: 0; font-family: {MONO}; font-size: 10px; font-weight: 400; text-transform: uppercase; color: {INK4}">Devices</h2><span style="display: inline-flex; align-items: center; gap: 10px"><label style="display: inline-flex; align-items: center; gap: 6px; font-size: 12px; color: {INK3}"><input type="checkbox" style="width: 16px; height: 16px; margin: 0">may add and revoke devices</label>{button("Add device", "ghost", "sm", "plus")}</span></div>
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
{d_sidebar(1300, selected="", settings_mode=True)}
<div style="flex: 1; min-width: 0; display: flex; flex-direction: column; background: {PANE}">
<div style="height: 2px; background: {LINE}"></div>
{hero}{d_body(table)}
</div>
</div>
{callout(14, 300, 300)}{callout(15, 300, 470)}"""
    return page("Desktop · connections", 1280, 1300, body, bg=BG)


def desktop_app_settings():
    card = lambda title, inner, w: (f'<div style="width: {w}px; display: flex; flex-direction: column; gap: 12px"><span style="font-size: 12px; color: {INK3}">{title}</span>'
                                    f'<div style="background: #ffffff; border: 0.5px solid {LINE2}; border-radius: 14px; box-shadow: 0 0 0 .5px rgba(11,17,23,.08), 0 18px 50px rgba(11,17,23,.10); overflow: hidden">{inner}</div></div>')
    footer = (f'<div style="display: flex; align-items: center; gap: 4px; padding: 10px 12px; background: {SIDE}; border-top: 0.5px solid {LINE}; width: 248px; box-sizing: border-box">'
              f'<span style="display: inline-flex; align-items: center; gap: 8px; height: 28px; padding: 0 10px; color: {INK2}; font-size: 13px">{ic("gear", 14, INK2)}Settings</span>'
              f'<span style="position: relative; display: inline-flex">{iconbtn("bell", "Notifications", 28, 14)}<span style="position: absolute; top: 2px; right: 2px; min-width: 14px; height: 14px; padding: 0 4px; border-radius: 999px; background: #c14545; color: #fff; font-size: 9px; font-weight: 600; line-height: 14px; text-align: center; box-sizing: border-box">1</span></span>'
              f'{iconbtn("sun", "Theme: light → dark → system", 28, 14)}<span style="flex: 1"></span><span style="font-family: {MONO}; font-size: 11px; color: #217a45; padding: 2px 4px">0.6.2</span></div>')
    popover = (f'<div style="width: 220px; padding: 16px; display: flex; flex-direction: column; gap: 10px">'
               f'<span style="display: inline-flex; align-items: center; gap: 8px; font-size: 13px; font-weight: 500"><span style="width: 7px; height: 7px; border-radius: 999px; background: #3fb37a"></span>Update available</span>'
               f'<span style="font-family: {MONO}; font-size: 12px; color: {INK2}">0.6.2 → 0.6.3</span>'
               f'<div style="display: flex; align-items: center; justify-content: flex-end; gap: 12px">{alink("Later")}<button style="height: 26px; padding: 0 10px; border: 0; border-radius: 8px; background: {INK}; color: {PANE}; font-family: Geist, sans-serif; font-size: 12px; font-weight: 500; cursor: pointer">Restart &amp; install</button></div></div>')
    notif_row = lambda color, title, sub: (f'<div style="display: flex; align-items: flex-start; gap: 10px; padding: 10px 12px; border-radius: 8px"><span style="width: 6px; height: 6px; border-radius: 999px; background: {color}; margin-top: 6px"></span>'
                                           f'<span style="flex: 1; display: flex; flex-direction: column; gap: 2px"><span style="font-size: 13px; color: {INK}">{title}</span><span style="font-family: {MONO}; font-size: 11px; color: {INK3}">{sub}</span></span></div>')
    modal = (f'<div style="width: 460px; padding: 24px; display: flex; flex-direction: column; gap: 12px">'
             f'<div style="display: flex; align-items: center; justify-content: space-between"><span style="font-size: 18px; font-weight: 600; line-height: 1.3">Notifications</span>{button("Mark all read", "ghost", "sm")}</div>'
             f'{notif_row("#3fb37a", "Daily brief delivered", "doc · schedule · 2h ago")}{notif_row("#c14545", "Cron job failed: weekly labs", "doc · timeout after 20m · 1d ago")}{notif_row("#e08a3c", "Provider key expiring", "openrouter · 3d ago")}</div>')
    palette = (f'<div style="width: 460px; padding: 8px; display: flex; flex-direction: column; gap: 2px">'
               f'<div style="display: flex; align-items: center; gap: 8px; height: 36px; padding: 0 10px; border-bottom: 0.5px solid {LINE}; margin-bottom: 6px">{ic("search", 14, INK3)}<span style="font-size: 13px; color: {INK3}">zoom</span></div>'
               + ''.join(f'<div style="display: flex; align-items: center; justify-content: space-between; height: 32px; padding: 0 10px; border-radius: 8px; {"background: " + SELECTED if i == 0 else ""}"><span style="font-size: 13px; color: {INK}">{t}</span><span style="display: inline-flex; gap: 4px">{"".join(kbd(x) for x in k)}</span></div>' for i, (t, k) in enumerate((("Switch theme", ()), ("Zoom in", ("⌘", "+")), ("Zoom out", ("⌘", "−")), ("Reset zoom", ("⌘", "0")))))
               + '</div>')
    body = f"""<div style="padding: 40px; display: flex; flex-direction: column; gap: 28px; height: 100%; box-sizing: border-box">
<div style="display: flex; flex-direction: column; gap: 6px"><span style="font-size: 22px; font-weight: 600; letter-spacing: -0.018em; line-height: 1.3">Desktop has no settings page</span><span style="font-size: 13px; color: {INK3}; max-width: 720px; line-height: 1.5">Theme, updates and notifications live in the sidebar footer; text size is the window zoom in the command palette. Mobile groups the equivalents plus pairing and biometrics under one Settings screen.</span></div>
<div style="display: flex; gap: 28px; align-items: flex-start; flex-wrap: wrap">
{card("Sidebar footer · theme cycles light → dark → system · version turns green when an update exists", footer, 248)}
{card("Version popover · from the footer version", popover, 220)}
{card("Notifications modal · from the bell", modal, 460)}
{card("Command palette · Preferences: theme, text size", palette, 460)}
</div>
{callout(16, 1230, 110)}{callout(3, 300, 210)}
</div>"""
    return page("Desktop · app-level settings", 1280, 800, body, bg=BG)


DESKTOP = {
    "chat": desktop_chat(),
    "profile": desktop_profile_settings(),
    "wg": desktop_wg_settings(),
    "connections": desktop_connections(),
    "app": desktop_app_settings(),
}
