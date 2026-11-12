import math
import re

import agent_marks as am
import folds
from desktop_boards import d_hero, eyebrow, h1 as d_h1, iconbtn, mono12, sb_row, selectish, small_diamond, state_chip
from gen import WELL, m_row, m_group, DOC_ACCENT, diamond, identity_glyph, m_chat_header, m_eyebrow, m_glyph, m_roster_row
from mobile_overlays import sheet as msheet
from desktop_boards import DANGER, INK, INK2, INK3, LINE, MONO, PANE, banner_bar, button, ic as dic
from gen import FLOAT_EDGE, m_banner, m_confirm_dialog, m_toast, mi
from mobile_overlays import backdrop
from panel_kit import alert_banner, phone_banner

PHONE_W = 390
ELEV = "var(--bg-elev, #ffffff)"
EDGE_LG = "box-shadow: 0 0 0 1px EDGE_LG"
RING_LG = "box-shadow: 0 0 0 1px #b4b4b4"
LIGHT = {"BRAND_INK": "#14110c", "EDGE_LG": "#b4b4b4", "ON_INK": "#ffffff", "SCREEN": "#ffffff", "CARD_M": "#f4f4f4"}
DARK = {"BRAND_INK": "#f3efe6", "SCREEN": "#0b0b0b", "CARD_M": "#151515", "var(--bg-elev, #ffffff)": "#202020", "var(--field)": "#1f1f1f", "background: #ffffff": "background: #151515", "#f6f6f6": "#0f0f0f", "#ececec": "#0b0b0b",
        "#141414": "#ededed", "#454545": "#b4b4b4", "#6b6b6b": "#8a8a8a", "#b4b4b4": "#4a4a4a", "#b73737": "#f08080", "rgba(20,20,20,0.07)": "rgba(237,237,237,0.08)",
        "rgba(20,20,20,0.14)": "rgba(237,237,237,0.16)", "rgba(20,20,20,0.04)": "rgba(237,237,237,0.04)", "rgba(20,20,20,0.06)": "rgba(237,237,237,0.07)", "rgba(20,20,20,0.5)": "rgba(237,237,237,0.5)",
        "EDGE_LG": "rgba(237,237,237,0.16)", "ON_INK": "#151515", "color-mix(in srgb, #ffffff 72%, transparent)": "rgba(11,11,11,0.72)"}
DARK_RE = re.compile("|".join(re.escape(k) for k in sorted(DARK, key=len, reverse=True)))
WARNING = "#e08a3c"
DANGER_FILL = "#c14545"


def stage(inner, w, h, bg="#f6f6f6"):
    return f'<div style="position: relative; width: {w}px; height: {h}px; border-radius: 12px; background: {bg}; border: 0.5px solid {LINE}; overflow: hidden; flex-shrink: 0">{inner}</div>'


def phone(inner, h, bg="#ececec"):
    return stage(inner, PHONE_W, h, bg)


def in_light(html):
    for marker, value in LIGHT.items():
        html = html.replace(marker, value)
    return html


def fixed_light(html):
    html = in_light(html).replace("var(--bg-elev, #ffffff)", "#ffffff").replace("var(--field)", "#ececec").replace("rgba(20,20,20,", "rgba(20, 20, 20, ")
    return as_rgb(html)


def as_rgb(html):
    return re.sub(r"#([0-9a-fA-F]{6})\b", lambda m: "rgb({}, {}, {})".format(*(int(m.group(1)[i:i + 2], 16) for i in (0, 2, 4))), html)


def in_dark(html):
    return as_rgb(DARK_RE.sub(lambda m: DARK[m.group(0)], html))


def modes(draw):
    return stack(labelled("Light", fixed_light(draw())), labelled("Dark", in_dark(draw())), caption("Both rows keep their palette whatever the kit's theme."), gap=16)


def stack(*items, gap=10):
    return f'<div style="display: flex; flex-direction: column; gap: {gap}px">{"".join(items)}</div>'


def hrow(*items, gap=8):
    return f'<div style="display: flex; flex-wrap: wrap; gap: {gap}px; align-items: center">{"".join(items)}</div>'


def caption(text):
    return f'<span style="font-size: 12px; line-height: 1.45; color: {INK3}">{text}</span>'


def labelled(text, inner):
    return stack(f'<span style="font-family: {MONO}; font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase; color: {INK3}">{text}</span>', inner, gap=6)


def desk_panel(inner, w=540, h=200):
    return stage(f'<div style="padding: 20px 24px; display: flex; flex-direction: column; gap: 16px">{inner}</div>', w, h, bg=PANE)


def phone_panel(inner, h=240):
    return phone(f'<div style="padding: 16px; display: flex; flex-direction: column; gap: 16px; background: {PANE}; height: 100%; box-sizing: border-box">{inner}</div>', h)


def floating_mobile(elevated):
    dialog = m_confirm_dialog("Delete doc?", "Its sessions and memory go with it. Skills and knowledge stay.", "Delete", typed="doc", value="doc", ready=True)
    toast = m_toast("Draft saved.", "info", dismiss=True, bottom=24)
    if elevated:
        dialog = dialog.replace(f"background: #ffffff; {FLOAT_EDGE}", f"background: {ELEV}; {EDGE_LG}")
        toast = toast.replace(f"background: #ffffff; {FLOAT_EDGE}", f"background: {ELEV}; {EDGE_LG}")
    body = f'{backdrop(PHONE_W, 470)}<div style="position: absolute; left: 24px; right: 24px; top: 24px">{dialog}</div>{toast}'
    return phone(f'<div style="height: 100%; background: SCREEN">{body}</div>', 470)


def floating_now_mobile():
    return modes(lambda: floating_mobile(False))


def floating_proposed_mobile():
    return modes(lambda: floating_mobile(True))


def floating_now_desktop():
    modal = (f'<div style="width: 420px; padding: 24px; box-sizing: border-box; border-radius: 4px; background: {ELEV}; {EDGE_LG}; display: flex; flex-direction: column; gap: 12px">'
             f'<span style="font-size: 18px; font-weight: 600; color: {INK}">Delete doc?</span><span style="font-size: 13px; line-height: 1.5; color: {INK2}">Its sessions and memory go with it. Skills and knowledge stay.</span>'
             f'<div style="display: flex; justify-content: flex-end; gap: 8px; margin-top: 8px">{button("Cancel", "ghost")}{button("Delete", "danger")}</div></div>')
    veil = f'<div style="position: absolute; inset: 0; background: color-mix(in srgb, #ffffff 72%, transparent)"></div>'
    return modes(lambda: stage(f'<div style="height: 100%; background: {PANE}">{veil}<div style="position: absolute; left: 60px; top: 30px">{modal}</div></div>', 540, 230))


def d_alert_banner(lead, detail, icon_color):
    return (f'<div role="alert" style="display: flex; align-items: center; gap: 8px; padding: 8px 12px; border-radius: 4px; background: color-mix(in srgb, {DANGER_FILL} 10%, {PANE}); {RING_LG}">'
            f'<span style="display: inline-flex">{dic("alert", 16, icon_color)}</span><div style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px">'
            f'<span style="font-size: 11px; font-weight: 600; line-height: 1.3; color: {INK}">{lead}</span><span style="font-size: 11px; line-height: 1.3; color: {INK3}">{detail}</span></div></div>')


def banner_bar_icon(kind, message, action=""):
    tint = {"warning": WARNING, "danger": DANGER_FILL}[kind]
    bar = banner_bar(kind, message, action, pad="16px")
    dot = f'<span style="width: 8px; height: 8px; border-radius: 50%; background: {tint}"></span>'
    return bar.replace(dot, dic("alert", 14, tint), 1)


MEMORY_LEAD = "Nearly full: 96% of its limit"
MEMORY_DETAIL = "4,800 / 5,000. The next additions will be refused until it is consolidated."
PAUSED = "This profile is paused. You can read the history; resume to chat."


def m_alert_tinted(lead, detail):
    return (f'<div role="alert" style="display: flex; align-items: center; gap: 8px; padding: 10px; border-radius: 4px; background: color-mix(in srgb, {DANGER_FILL} 10%, {PANE}); {RING_LG}">'
            f'{mi("alert", 13, DANGER)}<div style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px">'
            f'<span style="font-size: 12px; font-weight: 600; line-height: 1.3; color: {INK}">{lead}</span><span style="font-size: 10.5px; line-height: 1.3; color: {INK3}">{detail}</span></div></div>')


def banners_now_mobile():
    inner = stack(labelled("Status banner", m_banner(PAUSED, "Resume", kind="warning")), labelled("Alert banner · Memory panel", phone_banner(MEMORY_LEAD, MEMORY_DETAIL)), gap=20)
    return phone_panel(inner, 210)


def banners_proposed_mobile():
    inner = stack(labelled("Status banner", m_banner(PAUSED, "Resume", kind="warning")), labelled("Alert banner · Memory panel", m_alert_tinted(MEMORY_LEAD, MEMORY_DETAIL)), gap=20)
    return phone_panel(inner, 210)


def banners_now_desktop():
    inner = stack(labelled("Status banner", stack(banner_bar("warning", PAUSED, "Resume", pad="16px"), banner_bar("info", "Reconnecting…", pad="16px"), gap=8)),
                  labelled("Alert banner · Memory panel", alert_banner(MEMORY_LEAD, MEMORY_DETAIL)), gap=20)
    return desk_panel(inner, h=250)


def banners_proposed_desktop():
    inner = stack(labelled("Status banner", stack(banner_bar_icon("warning", PAUSED, "Resume"), banner_bar("info", "Reconnecting…", pad="16px"), gap=8)),
                  labelled("Alert banner · Memory panel", d_alert_banner(MEMORY_LEAD, MEMORY_DETAIL, DANGER)), gap=20)
    return desk_panel(inner, h=250)


MARK_BLUE = am.COLOUR["blue"]
MARK_META = (f'<span style="font-family: {MONO}; font-size: 11px; color: #454545; white-space: nowrap">deepseek-v4.1-flash</span>'
             f'<span style="font-family: {MONO}; font-size: 11px; color: #454545; white-space: nowrap">· 2% ctx</span>')
CAST = [
    ("doc", DOC_ACCENT, "blue", "gem", "oval", "headset", "idle", dict(selected=True, ts="6w")),
    ("lingo", "#9b5ad9", "violet", "cloud", "seed", None, "working", dict(state="working")),
    ("abby", "#df4b9d", "magenta", "drop", "oval", "flower", "needs", dict(state="needs-you")),
    ("clonara", "#f05940", "vermilion", "ears", "bead", "antenna", "failed", dict(state="failed")),
    ("galt", "#3ac9f3", "sky", "peanut", "bead", None, "paused", dict(paused=True)),
    ("etxea", "#3ec173", "green", "sprout", "oval", None, "no-provider", dict(dim=True)),
    ("yuri", "#f36a8a", "rose", "bean", "seed", "chullo", "idle", dict(unread=True, ts="6w")),
]
DOC_CAST = CAST[0]


def cast_mark(c, size, ink="BRAND_INK", state=None):
    name, _, colour, shape, style, wear, cast_state, _ = c
    return am.mark(shape, am.COLOUR[colour], size, state or cast_state, style, wear, seed=name, ink=ink)


def swap(html, old, new):
    assert old in html, "glyph not found in the shipped helper"
    return html.replace(old, new, 1)


def mark_label(text, sub=""):
    tail = f'<span style="font-family: {MONO}; font-size: 10px; color: {INK3}">{sub}</span>' if sub else ""
    return f'<span style="display: flex; flex-direction: column; align-items: center; gap: 2px; font-size: 11px; color: {INK2}; text-align: center">{text}{tail}</span>'


def mark_cell(inner, text="", sub="", w=72):
    return f'<span style="width: {w}px; display: inline-flex; flex-direction: column; align-items: center; gap: 8px">{inner}{mark_label(text, sub) if text else ""}</span>'


def mark_appearance_control(glyph, name):
    return f'<span style="display: inline-flex; align-items: center; gap: 8px; flex-shrink: 0">{glyph}<span style="font-size: 13px; color: #141414; white-space: nowrap">{name}</span></span>'


def mark_phone_stage(proposed):
    colour = MARK_BLUE if proposed else DOC_ACCENT
    header = m_chat_header("doc", colour, MARK_META)
    if proposed:
        header = swap(header, identity_glyph("doc", colour, 20, diamond(colour, 18)), cast_mark(DOC_CAST, 20))
    rows = [m_roster_row("alpi", "#f0b447")]
    for c in CAST:
        name, now_colour, colour_name, *_, kw = c
        col = am.COLOUR[colour_name] if proposed else now_colour
        html = m_roster_row(name, col, **kw)
        if proposed:
            html = swap(html, m_glyph("profile", col, name, kw.get("paused", False) or kw.get("offline", False), kw.get("dim", False)), cast_mark(c, 16))
        rows.append(html)
    control = (mark_appearance_control(cast_mark(DOC_CAST, 16), "blue gem · headset") if proposed
               else mark_appearance_control(identity_glyph("doc", DOC_ACCENT, 16), "blue shield"))
    appearance = m_group(m_row("Appearance", "", control=control, sep=False)).replace("var(--card)", "CARD_M", 1)
    body = f'{header}<div style="padding: 8px 0 16px">{"".join(rows)}</div>{appearance}'
    return phone(f'<div style="height: 100%; background: SCREEN">{body}</div>', 520)


def m_pick_cell(inner, selected=False):
    edge = "2px solid #141414" if selected else "0.5px solid rgba(20,20,20,0.14)"
    return (f'<span style="width: 16.6667%; min-height: 56px; display: inline-flex; align-items: center; justify-content: center">'
            f'<span style="width: 48px; height: 48px; box-sizing: border-box; border-radius: 4px; border: {edge}; display: inline-flex; align-items: center; justify-content: center">{inner}</span></span>')


def m_pick_group(title, cells):
    return (f'<div style="padding: 12px 16px 0; display: flex; flex-direction: column; gap: 8px">{m_eyebrow(title)}'
            f'<div style="display: flex; flex-wrap: wrap">{"".join(cells)}</div></div>')


def m_pick_preview(glyph, name, meta, reset):
    return (f'<div style="padding: 16px 16px 0; display: flex; align-items: center; gap: 16px">{glyph}'
            f'<div style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px"><span style="font-weight: 600; font-size: 17px; color: #141414">{name}</span>'
            f'<span style="font-family: {MONO}; font-size: 11px; line-height: 1.4; color: #6b6b6b">{meta}</span></div>'
            f'<span style="font-family: {MONO}; font-size: 11px; color: #454545; white-space: nowrap">{reset}</span></div>')


def mark_sheet_body(proposed):
    if not proposed:
        shipped = am.shipped_accents()
        shapes = [m_pick_cell(folds.fold(f, DOC_ACCENT, 28), f == "shield") for f in folds.SHAPE_ORDER]
        colours = [m_pick_cell(f'<span style="width: 28px; height: 28px; border-radius: 4px; background: {h}"></span>', h == DOC_ACCENT) for _, h in shipped]
        return (m_pick_group("Object", shapes) + m_pick_group("Colour", colours)
                + m_pick_preview(folds.fold("shield", DOC_ACCENT, 40), "Blue shield", f"fold: shield · accent: {DOC_ACCENT}", "Reset to diamond"))
    ink = "BRAND_INK"
    shapes = [m_pick_cell(am.mark(s, MARK_BLUE, 28, "idle", "oval", seed=s, ink=ink, still=True), s == "gem") for s in am.SHAPE_ORDER]
    colours = [m_pick_cell(am.mark("gem", h, 28, "idle", "oval", seed=n, ink=ink, still=True), n == "blue") for n, h in am.PALETTE]
    eyes = [m_pick_cell(am.mark("gem", MARK_BLUE, 38, "idle", e, seed=e, ink=ink, still=True), e == "oval") for e in am.EYE_STYLES]
    none = m_pick_cell(f'<span style="font-family: {MONO}; font-size: 11px; color: #6b6b6b">none</span>')
    wears = [none] + [m_pick_cell(am.mark("gem", MARK_BLUE, 28, "idle", "oval", w, seed=w, ink=ink, still=True), w == "headset") for w in am.ACCESSORIES]
    return (m_pick_group("Shape", shapes) + m_pick_group("Colour", colours) + m_pick_group("Eyes", eyes) + m_pick_group("Accessory · optional, from 24 px", wears)
            + m_pick_preview(cast_mark(DOC_CAST, 72), "Blue gem · headset", f"shape: gem · eyes: oval<br>accessory: headset · {MARK_BLUE}", "Reset to kite"))


def mark_phone_sheet(proposed):
    h = 770 if proposed else 560
    subtitle = "@doc · make your mark" if proposed else "@doc · object and colour"
    inner = msheet(PHONE_W, h, "Appearance", subtitle, mark_sheet_body(proposed), primary="Save appearance")
    return phone(f'<div style="height: 100%; background: SCREEN">{inner}</div>', h)


def mark_family():
    cells = "".join(mark_cell(am.mark(am.PAIRED_SHAPE[n], h, 56, "idle", "oval", seed=n), n, am.PAIRED_SHAPE[n]) for n, h in am.PALETTE)
    return f'<div style="display: grid; grid-template-columns: repeat(6, 72px); gap: 18px 10px; justify-content: space-between">{cells}</div>'


def mark_states():
    head = "".join(f'<span style="width: 60px; text-align: center; font-family: {MONO}; font-size: 10px; color: {INK3}">{am.STATE_LABEL[s]}</span>' for s in am.STATES)
    lines = [f'<div style="display: flex; gap: 6px; padding-left: 52px">{head}</div>']
    for style, (colour, shape) in zip(am.EYE_STYLES, (("blue", "gem"), ("violet", "cloud"), ("vermilion", "ears"))):
        marks = "".join(f'<span style="width: 60px; display: inline-flex; justify-content: center">{am.mark(shape, am.COLOUR[colour], 40, s, style, seed=style + s)}</span>' for s in am.STATES)
        lines.append(f'<div style="display: flex; align-items: center; gap: 6px"><span style="width: 46px; font-family: {MONO}; font-size: 10px; color: {INK3}">{style}</span>{marks}</div>')
    small = "".join(f'<span style="width: 60px; display: inline-flex; justify-content: center">{am.mark("gem", MARK_BLUE, 16, s, seed="s" + s)}</span>' for s in am.STATES)
    lines.append(f'<div style="display: flex; align-items: center; gap: 6px"><span style="width: 46px; font-family: {MONO}; font-size: 10px; color: {INK3}">16 px</span>{small}</div>')
    return stack(*lines, gap=12)


def mark_wears():
    big = "".join(mark_cell(am.mark(shape, am.COLOUR[colour], 72, "idle", style, wear, seed=wear), wear, f"{colour} {shape}", 84)
                  for wear, colour, shape, style in (("antenna", "orange", "bubble", "bead"), ("headset", "blue", "gem", "oval"), ("chullo", "rose", "bean", "seed"), ("flower", "magenta", "drop", "oval")))
    small = "".join(f'<span style="width: 84px; display: inline-flex; justify-content: center; gap: 10px; align-items: center">{am.mark(shape, am.COLOUR[colour], 20, "idle", "oval", wear, seed=wear)}{am.mark(shape, am.COLOUR[colour], 16, "idle", "oval", wear, seed=wear)}</span>'
                    for wear, colour, shape in (("antenna", "orange", "bubble"), ("headset", "blue", "gem"), ("chullo", "rose", "bean"), ("flower", "magenta", "drop")))
    return stack(f'<div style="display: flex; gap: 22px; align-items: flex-end">{big}</div>',
                 f'<div style="display: flex; gap: 22px; align-items: center">{small}</div>', gap=14)


def floor2(value):
    return f"{math.floor(value * 100) / 100:.2f}"


def mark_palette():
    cells = []
    for n, h in am.PALETTE:
        c = am.contrasts(h)
        cells.append(f'<div style="display: flex; align-items: center; gap: 10px">{am.mark("gem", h, 28, "idle", seed=n)}'
                     f'<span style="display: flex; flex-direction: column; gap: 2px"><span style="font-size: 12px; color: {INK}">{n} <span style="font-family: {MONO}; font-size: 11px; color: {INK3}">{h}</span></span>'
                     f'<span style="font-family: {MONO}; font-size: 10px; color: {INK3}">{floor2(c["light"])} · {floor2(c["dark"])} · {floor2(c["eyes"])}</span></span></div>')
    return f'<div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px 12px">{"".join(cells)}</div>'


def mark_sizes():
    groups = []
    for c in (DOC_CAST, CAST[2], CAST[6]):
        trio = "".join(f'<span style="display: inline-flex; flex-direction: column; align-items: center; gap: 6px">{cast_mark(c, px, state="idle")}<span style="font-family: {MONO}; font-size: 10px; color: #6b6b6b">{px}</span></span>' for px in (16, 20, 72))
        groups.append(f'<div style="display: flex; align-items: flex-end; gap: 14px">{trio}</div>')
    return stage(f'<div style="height: 100%; padding: 16px 20px; box-sizing: border-box; display: flex; justify-content: space-between; align-items: flex-end; background: SCREEN">{"".join(groups)}</div>', 540, 128)


def d_pick_cell(inner, selected=False):
    ring = "box-shadow: 0 0 0 1.5px #141414;" if selected else ""
    return f'<span style="width: 42px; height: 42px; border-radius: 4px; {ring} display: inline-flex; align-items: center; justify-content: center">{inner}</span>'


def d_pick_grid(title, cells):
    return (f'{eyebrow(title)}<div style="display: grid; grid-template-columns: repeat(6, 1fr); gap: 8px; justify-items: center">{"".join(cells)}</div>')


def d_picker(proposed):
    if proposed:
        ink = "BRAND_INK"
        shapes = [d_pick_cell(am.mark(s, MARK_BLUE, 28, "idle", "oval", seed=s, ink=ink, still=True), s == "gem") for s in am.SHAPE_ORDER]
        colours = [d_pick_cell(am.mark("gem", h, 28, "idle", "oval", seed=n, ink=ink, still=True), n == "blue") for n, h in am.PALETTE]
        eyes = [d_pick_cell(am.mark("gem", MARK_BLUE, 36, "idle", e, seed=e, ink=ink, still=True), e == "oval") for e in am.EYE_STYLES]
        wears = [d_pick_cell(f'<span style="font-family: {MONO}; font-size: 10px; color: #6b6b6b">none</span>')] + [d_pick_cell(am.mark("gem", MARK_BLUE, 28, "idle", "oval", w, seed=w, ink=ink, still=True), w == "headset") for w in am.ACCESSORIES]
        grids = d_pick_grid("Shape", shapes) + d_pick_grid("Colour", colours) + d_pick_grid("Eyes", eyes) + d_pick_grid("Accessory", wears)
        preview, name, meta, reset = cast_mark(DOC_CAST, 72), "Blue gem · headset", f'shape: gem · eyes: oval · accessory: headset · "{MARK_BLUE}"', "Reset to kite"
        hexv = MARK_BLUE
    else:
        shipped = am.shipped_accents()
        shapes = [d_pick_cell(folds.fold(f, DOC_ACCENT, 28), f == "shield") for f in folds.SHAPE_ORDER]
        colours = [d_pick_cell(f'<span style="width: 28px; height: 28px; border-radius: 4px; background: {h}"></span>', h == DOC_ACCENT) for _, h in shipped]
        grids = d_pick_grid("Object", shapes) + d_pick_grid("Colour", colours)
        preview, name, meta, reset = folds.fold("shield", DOC_ACCENT, 40), "Blue shield", f'fold: shield · accent: "{DOC_ACCENT}"', "Reset to diamond"
        hexv = DOC_ACCENT
    field = f'<span style="display: flex; align-items: center; height: 32px; padding: 0 12px; border-radius: 4px; {WELL}; font-family: {MONO}; font-size: 11px; color: {INK}">{hexv}</span>'
    foot = (f'<div style="display: flex; align-items: center; gap: 12px">{preview}<span style="display: flex; flex-direction: column; gap: 2px; min-width: 0">'
            f'<span style="font-size: 13px; font-weight: 600; color: {INK}">{name}</span><span style="font-family: {MONO}; font-size: 11px; line-height: 1.4; color: {INK3}">{meta}</span></span></div>'
            f'<span style="font-size: 12px; color: {INK2}; text-decoration: underline; text-underline-offset: 3px">{reset}</span>')
    return (f'<div style="width: 340px; box-sizing: border-box; padding: 16px; border-radius: 4px; background: {ELEV}; box-shadow: 0 0 0 1px #8c8c8c; display: flex; flex-direction: column; gap: 8px">'
            f'{grids}{field}{foot}</div>')


def mark_desk_stage(proposed):
    colour = MARK_BLUE if proposed else DOC_ACCENT
    glyph20 = cast_mark(DOC_CAST, 20) if proposed else identity_glyph("doc", DOC_ACCENT, 20, diamond(DOC_ACCENT, 14))
    hero = d_hero(d_h1("doc", glyph20, colour), mono12("deepseek-v4.1-flash"), iconbtn("more", "More"), colour)
    rows = [sb_row(identity_glyph("alpi", "#f0b447", 16, small_diamond("#f0b447")), "alpi")]
    for c in CAST:
        name, now_colour, colour_name, *_, kw = c
        col = am.COLOUR[colour_name] if proposed else now_colour
        glyph = cast_mark(c, 16) if proposed else identity_glyph(name, col, 16, small_diamond(col))
        state = kw.get("state")
        trailing = state_chip(state, col) if state else (f'<span style="flex-shrink: 0; margin-left: auto; font-weight: 500; font-size: 11px; line-height: 1; color: {INK3}">no provider</span>' if kw.get("dim") else "")
        rows.append(sb_row(glyph, name, kw.get("ts", ""), active=kw.get("selected", False), unread=kw.get("unread", False), dim=kw.get("paused", False), trailing=trailing, accent=col))
    side = f'<div style="width: 248px; flex-shrink: 0; padding: 8px 12px; box-sizing: border-box; background: #f6f6f6; display: flex; flex-direction: column">{"".join(rows)}</div>'
    label = "blue gem · headset" if proposed else "blue shield"
    small = cast_mark(DOC_CAST, 16) if proposed else identity_glyph("doc", DOC_ACCENT, 16)
    trigger = selectish(f'<span style="display: inline-flex; align-items: center; gap: 8px; white-space: nowrap">{small}{label}</span>', mono=False).replace("display: inline-flex;", "display: inline-flex; align-self: flex-start;", 1)
    right = f'<div style="flex: 1; min-width: 0; padding: 12px 16px; display: flex; flex-direction: column; gap: 10px">{eyebrow("Appearance")}{trigger}</div>'
    body = f'{hero}<div style="display: flex">{side}{right}</div><div style="padding: 12px 16px 16px; background: {PANE}">{d_picker(proposed)}</div>'
    h = 960 if proposed else 830
    return stage(f'<div style="height: 100%; background: {PANE}">{body}</div>', 540, h, bg=PANE)


def app_tile(inner, caption_text, sub):
    return (f'<span style="display: inline-flex; flex-direction: column; align-items: center; gap: 6px; width: 120px">{inner}'
            f'<span style="font-size: 11px; color: {INK2}; text-align: center">{caption_text}</span><span style="font-family: {MONO}; font-size: 10px; color: {INK3}; text-align: center">{sub}</span></span>')


def mark_app_icons():
    from brand_boards import black_alpaca, tile
    today = (app_tile(tile(black_alpaca(98, "rgb(20, 17, 12)"), "rgb(254, 254, 254)", 120, 28), "Today · light", "origami alpaca")
             + app_tile(tile(black_alpaca(98, "rgb(243, 239, 230)"), "rgb(12, 11, 9)", 120, 28, border=False), "Today · dark", "origami alpaca"))
    sketches = (app_tile(am.app_mark("peek", 120, 23), "Sketch · peek", "blue gem rising from the edge")
                + app_tile(am.app_mark("ears", 120, 23), "Sketch · ears", "cream ears on night"))
    small = "".join(f'<span style="display: inline-flex; gap: 8px; align-items: center">{am.app_mark(k, 32, 23)}{am.app_mark(k, 20, 23)}</span>' for k in am.APP_MARKS)
    return stack(f'<div style="display: flex; gap: 12px; align-items: flex-start">{today}{sketches}</div>',
                 f'<div style="display: flex; gap: 20px; align-items: center">{small}<span style="font-size: 11px; color: {INK3}">32 and 20 px: the eyes still read</span></div>',
                 caption("One character from the set, large and cropped by the tile, eyes only: one fill plus ink, flat. Peek keeps a palette colour on paper; ears keeps the alpaca’s ears and its cream on night. A sketch, not a decision: the Brand tab stays as it ships."), gap=12)


def marks_now_mobile():
    return stack(modes(lambda: mark_phone_stage(False)), modes(lambda: mark_phone_sheet(False)), gap=24)


def marks_proposed_mobile():
    return stack(am.MOTION_STYLE + labelled("The set · twelve shapes, each dealt with its colour", mark_family()),
                 labelled("Accent palette · one luminance; worst light ground · worst dark ground · ink eyes", mark_palette()),
                 labelled("Animations · the eyes carry state: resting style × state, 40 px and 16 px", mark_states()),
                 caption("Idle blinks every ~6 s, phase per profile; working scans side to side; needs you raises the eyes and hops; failed crosses them; paused closes them; "
                         "no provider drains the body to 30 % and colours the eyes; offline leaves the faded body. Reduce motion holds each still form."),
                 labelled("Accessory · one at most, in the theme's ink, from 24 px; 20 and 16 drop it", mark_wears()),
                 labelled("Roster, chat header and settings row", modes(lambda: mark_phone_stage(True))),
                 labelled("AppearanceSheet · make your mark", modes(lambda: mark_phone_sheet(True))), gap=24)


def marks_now_desktop():
    return modes(lambda: mark_desk_stage(False))


def marks_proposed_desktop():
    return stack(labelled("16 · 20 · 72 px (row, header, empty thread and picker preview)", modes(mark_sizes)),
                 labelled("Sidebar, chat hero, settings row and AppearancePicker", modes(lambda: mark_desk_stage(True))),
                 labelled("App mark from the same family · today and two sketches", mark_app_icons()), gap=24)


PROPOSALS = [
    dict(
        id="DS.FLOATING", client="mobile", area="Sheets, dialogs and toasts",
        title="Floating surfaces on the phone sit on the elevated step with a 1 px edge",
        why=("Desktop floats every modal, popover and toast on <code>--bg-elev</code> with the large edge ring (<code>Modal.module.css:12-14</code>, <code>Popover.jsx:63-65</code>, <code>Notification.module.css:18-21</code>). "
             "The phone's Sheet, ActionSheet, ConfirmDialog, TextPrompt and Toast all use <code>colors.bgPane</code> with a 0.5 pt ink3 edge (<code>Sheet.jsx:127</code>, <code>ConfirmDialog.jsx:132</code>, <code>Toast.jsx:179</code>); "
             "<code>bgElev</code> is used only by the input well. In light both are white; in dark the phone's dialog is #151515 on a #151515 card and never climbs the ladder the tokens promise. "
             "The proposal moves those five surfaces to <code>colors.bgElev</code> with the 1 px edge the desktop ring uses."),
        mobile=(floating_now_mobile, floating_proposed_mobile),
        desktop=(floating_now_desktop, None),
        accept=("a mobile test asserts every component that spreads <code>shadows.dialog</code>, <code>popover</code>, <code>toast</code> or <code>sheet</code> uses <code>colors.bgElev</code>, and <code>shadowsFor</code> draws a 1 px edge in <code>ink4</code> (light) or <code>line2</code> (dark); "
                "<code>uxTokens.test.js</code> on both clients asserts the floating step is <code>bgElev</code>; the kit's sheet and dialog helpers are regenerated."),
        h=2160,
    ),
    dict(
        id="DS.BANNERS", client="mobile · desktop", area="Status banner and alert banner",
        title="Warnings carry the alert glyph on both clients and the memory alert is tinted on the phone",
        why=("Desktop's status banner puts a dot in front of every kind, danger included (<code>Banner.jsx:21</code>), while the phone shows the alert glyph for danger and warning and keeps the dot for info (<code>Banner.jsx:15,48</code>); "
             "desktop's own AlertBanner already uses the glyph. The memory alert is a danger-tinted panel with a ring on desktop (<code>AlertBanner.module.css:5-15</code>) and a grey card with a hairline on the phone (<code>AlertBanner.jsx:14-23</code>). "
             "The proposal: the glyph for danger and warning on desktop, the dot for info, and the phone's alert banner in the danger tint with the ink4 ring and the icon in the danger text colour, as desktop. Sizes stay per client."),
        mobile=(banners_now_mobile, banners_proposed_mobile),
        desktop=(banners_now_desktop, banners_proposed_desktop),
        accept=("<code>Banner.test.jsx</code> on desktop asserts the alert glyph for danger and warning and the dot otherwise; <code>AlertBanner.test.jsx</code> on the phone asserts the background is the danger mix at 10 %, the ring <code>ink4</code> and the icon <code>dangerText</code>; "
                "<code>banner_bar</code> and <code>phone_banner</code> in the kit draw the same."),
        h=1040,
    ),
    dict(
        id="ID.PROFILE-MARK", client="mobile · desktop", area="Profile identity: roster, headers, settings and the appearance picker",
        title="A family of marks with eyes: twelve shapes, one accent palette, and eyes that animate the state",
        why=("Both x.ai (its row of bots) and OpenAI (“create your dot”) give their agents a face: a flat body with two eyes reads as someone rather than something, and the eyes have room to say what the agent is doing. "
             "Today a profile is an origami model and an accent from twelve pairs (<code>common/folds.mjs</code>, <code>common/accents.mjs</code>, <code>PAIR_COLOUR</code> in <code>brand_boards.py</code>); its state is a facet ripple, a dashed unfold or the row’s words. "
             "The first step is the set itself, alpi’s own and not a copy of either: twelve soft shapes (kite, gem, onigiri, drop, bell, bean, peanut, cloud, ears, tadpole, bubble, sprout), one flat fill, two ink eyes high on the body, no mouth, outline or shading. "
             "The default stays the kite, now a true kite with the longer lower half, so a new profile still starts from the shape today’s kite-base diamond names. "
             "The accent palette is twelve colours at one luminance (0.249), so no profile shouts: against every ground the clients paint (light bg, side, card and pane; dark bg, side, pane and elevated) each body holds at least 3.06:1 on light and 4.63:1 on dark, and its ink eyes at least 5.35:1; a custom hex still works and its eyes flip to paper when ink falls under 4.5:1. "
             "The eyes are the state channel, the same forms on every mark: idle blinks, working scans, needs you looks up and hops, failed crosses, paused closes, no provider drains the body to 30 % and colours the eyes, offline leaves the faded body; reduce motion holds each still form. "
             "Making a profile’s mark is shape × colour × eyes (oval, bead, seed) × at most one accessory (antenna, headset, chullo, flower), drawn flat in the theme’s ink from 24 px and dropped at 20 and 16, inside the shipped AppearanceSheet and AppearancePicker. "
             "<code>appearance.next_pair</code> deals the least-worn of the 144 pairs, ties broken by colour order and then shape order, so no worn pair is dealt while any is free; a worn pair can still be picked by hand. Old profiles map fold to shape (diamond → kite, shield → gem, …) and accent to the nearest colour. "
             "Workgroups keep their honeycomb in this step; a workgroup mark from the family is a later board. "
             "Today the origami alpaca is the brand: the app icon, the wordmark and the default profile’s mark, under the Brand tab’s origami gate (<code>design/AGENTS.md</code>, Tabs). If the creator adopts this family, the app icon could come from it too; the last section sketches that next to today’s icon. "
             "Either way it is a contract change approved with this board: the gate would cover only what stays origami, or be rewritten for the new mark. The Brand tab is not touched until then."),
        mobile=(marks_now_mobile, marks_proposed_mobile),
        desktop=(marks_now_desktop, marks_proposed_desktop),
        accept=("<code>common/agentMarks.mjs</code> is the single source (shapes, eye anchors, eye styles, accessories, palette, the state → eye table and the legacy fold map), read by both clients and by the kit through node as <code>folds.mjs</code> is today; "
                "<code>common/agentMarks.test.mjs</code> asserts every colour at least 3:1 on the four light grounds and 4.5:1 on the four dark ones, ink eyes at least 4.5:1 and the paper flip below, every eye inside its body, no accessory under 24 px and a shape for every legacy fold; "
                "a <code>Mark</code> component replaces <code>Fold</code> for profiles on both clients (the workgroup honeycomb stays) and <code>Mark.test.jsx</code> on each asserts the eye form per state, no animation under reduce motion and the default profile’s mark as the brand decides; "
                "<code>AppearanceSheet.test.jsx</code>, <code>IdentityEditor.test.jsx</code> and <code>AppearancePicker.test.jsx</code> assert the four rows and the saved keys <code>shape</code>, <code>accent</code>, <code>eyes</code>, <code>accessory</code>; "
                "the daemon’s appearance tests deal the least-worn of the 144 pairs (colour, then shape, on ties) and read <code>tui.fold</code> as a legacy alias; <code>LOCKED_KEYS</code> in <code>alpi/appearance.py</code> and the <code>tui.fold</code> validation in <code>alpi/host/device_state.py</code> take <code>tui.shape</code>, <code>tui.eyes</code> and <code>tui.accessory</code>; "
                "console parity: the TUI’s <code>/fold</code> and <code>alpi setup</code> → Appearance choose shape, colour, eyes and accessory, and <code>alpi/fold_art.py</code> draws the shape with its eyes; "
                "<code>alpi/knowledge/references/config.md</code> and <code>architecture.md</code> describe the new keys and marks; "
                "<code>tests/test_design_kit.py</code> and <code>design/AGENTS.md</code> carry the Brand gate the creator approves (origami for what stays origami, or the family’s rules for a new app mark), and every view that draws a profile fold (roster, headers, settings, empty thread, picker) is regenerated."),
        h=7600,
    ),
]
