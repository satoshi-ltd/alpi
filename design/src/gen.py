import json
import os
from datetime import datetime, timezone

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "project")
os.makedirs(ROOT, exist_ok=True)

FONT_LINK = '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700&amp;family=Geist+Mono:wght@400;500;600&amp;display=swap">'

DOC_ACCENT = "#3d7ea6"
ALPI_ACCENT = "#8a5a0a"
DANGER = "#b73737"
MONO = "'Geist Mono', monospace"


PATHS = {
    "back": '<path d="M15 18l-6-6 6-6"/>',
    "chev-r": '<path d="M9 18l6-6-6-6"/>',
    "chev-d": '<path d="M6 9l6 6 6-6"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "more": '<circle cx="5" cy="12" r="1.4" fill="currentColor"/><circle cx="12" cy="12" r="1.4" fill="currentColor"/><circle cx="19" cy="12" r="1.4" fill="currentColor"/>',
    "panel": '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 3v18"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "gear": '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
    "bell": '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.7 21a2 2 0 0 1-3.4 0"/>',
    "clip": '<path d="M21.4 11.05l-9.2 9.2a6 6 0 0 1-8.5-8.5l9.2-9.2a4 4 0 0 1 5.7 5.7l-9.2 9.2a2 2 0 0 1-2.8-2.8l8.5-8.5"/>',
    "up": '<path d="M12 19V5M5 12l7-7 7 7"/>',
    "arrow-left": '<path d="M12 19l-7-7 7-7M19 12H5"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
    "x": '<path d="M18 6L6 18M6 6l12 12"/>',
    "chip": '<rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><path d="M9 1v3M15 1v3M9 20v3M15 20v3M20 9h3M20 14h3M1 9h3M1 14h3"/>',
    "copy": '<rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>',
    "check": '<path d="M20 6L9 17l-5-5"/>',
    "refresh": '<path d="M21 12a9 9 0 1 1-2.6-6.4"/><path d="M21 3v6h-6"/>',
    "pencil": '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/>',
    "volume": '<path d="M11 5 6 9H2v6h4l5 4V5Z"/><path d="M15.5 8.5a5 5 0 0 1 0 7"/><path d="M19 5a10 10 0 0 1 0 14"/>',
    "qr": '<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><path d="M14 14h3v3h-3zM20 14v3M17 20h3"/>',
}


def ic(name, size=16, color="currentColor", stroke=2):
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" '
        f'stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" '
        f'style="flex-shrink: 0; display: block">{PATHS[name]}</svg>'
    )


def diamond(color, size=16):
    r = 3
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" aria-hidden="true" style="flex-shrink: 0; display: block">'
        f'<rect x="4" y="4" width="16" height="16" rx="{r}" transform="rotate(45 12 12)" fill="{color}"/></svg>'
    )


def page(title, w, h, body, bg="#ffffff", lang="en"):
    return f"""<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<title>{title}</title>
<script src="./support.js"></script>
{FONT_LINK}
<link rel="stylesheet" href="parity.css">
</head>
<body>
<x-dc>
<helmet>
{FONT_LINK}
<style>
body{{margin:0;background:{bg};font-family:"Geist",ui-sans-serif,system-ui,sans-serif;color:#0b1117}}
a{{color:#8a5a0a}}a:hover{{color:#6b4608}}
</style>
</helmet>
<div style="position: relative; width: {w}px; height: {h}px; box-sizing: border-box; overflow: hidden; background: {bg}; font-family: Geist, ui-sans-serif, system-ui, sans-serif; color: #0b1117">
{body}
</div>
</x-dc>
<script type="text/x-dc" data-dc-script data-props='{{"$preview":{{"width":{w},"height":{h}}}}}'>
class Component extends DCLogic {{
renderVals() {{ return {{}}; }}
}}
</script>
</body>
</html>
"""



def m_eyebrow(text, color="#626e7d", weight=500, track=0.06, size=11, extra=""):
    return (
        f'<span style="font-family: {MONO}; font-weight: {weight}; font-size: {size}px; '
        f'line-height: 1.3; letter-spacing: {track}em; text-transform: uppercase; color: {color}; {extra}">{text}</span>'
    )


def m_meta_strip(items, gap=14):
    parts = []
    for i, it in enumerate(items):
        if i > 0:
            parts.append('<span style="width: 1px; height: 10px; background: rgba(11,17,23,0.14); display: inline-block"></span>')
        parts.append(it)
    return f'<div style="display: flex; align-items: center; gap: {gap}px; white-space: nowrap; overflow: hidden">{"".join(parts)}</div>'


def m_screen_header(title, subtitle, accent=DOC_ACCENT, glyph=None, back=True, wide=False, right="", sidebar_toggle=False, meta=None):
    padx = 24 if wide else 20
    padt = 12 if wide else 8
    parts = []
    if sidebar_toggle:
        parts.append(f'<button aria-label="Show sidebar" class="m-chrome" style="margin-left: -6px">{ic("panel", 20, "#3d4955")}</button>')
    if back and not wide:
        parts.append(f'<button aria-label="Back" class="m-chrome" style="width: 28px; height: 36px; margin-left: -6px">{ic("back", 20, "#3d4955")}</button>')
    g = glyph if glyph is not None else diamond(accent, 20)
    stripe = f'<div style="position: absolute; left: {padx}px; bottom: -0.5px; height: 1.5px; width: 36px; background: {accent}"></div>' if wide else ""
    if wide:
        sub = f'<span style="font-family: {MONO}; font-size: 11px; line-height: 1.3; letter-spacing: 0.06em; color: #626e7d; margin-top: 4px">{subtitle}</span>'
        title_row = f'<div style="display: flex; align-items: center; gap: 10px">{g}<span style="font-weight: 600; font-size: 18px; line-height: 1.3; white-space: nowrap; overflow: hidden; text-overflow: ellipsis">{title}</span>{sub}</div>'
        meta_row = f'<div style="margin-top: 8px">{m_meta_strip(meta)}</div>' if meta else ""
        back_btn = f'<button aria-label="Back" class="m-chrome">{ic("arrow-left", 16, "#3d4955")}</button>' if back else ""
        return f"""<div style="position: relative; display: flex; align-items: flex-start; gap: 10px; padding: {padt}px {padx}px 12px; background: #ffffff; border-bottom: 0.5px solid rgba(11,17,23,0.07)">
{''.join(parts)}
<div style="flex: 1; min-width: 0; display: flex; flex-direction: column">{title_row}{meta_row}</div>
{right}{back_btn}
{stripe}
</div>"""
    return f"""<div style="position: relative; display: flex; align-items: center; gap: 10px; padding: {padt}px {padx}px 12px; background: #ffffff; border-bottom: 0.5px solid rgba(11,17,23,0.07)">
{''.join(parts)}
<div style="flex: 1; min-width: 0; display: flex; flex-direction: column">
<div style="display: flex; align-items: center; gap: 6px">{g}<span style="font-weight: 600; font-size: 18px; line-height: 1.3; white-space: nowrap; overflow: hidden; text-overflow: ellipsis">{title}</span></div>
{m_eyebrow(subtitle, "#626e7d", 400, 0.06, 11)}
</div>
{right}
</div>"""


def m_section(title, kicker="", first=False):
    k = f' · {kicker}' if kicker else ""
    return f'<div style="padding: {0 if first else 24}px 20px 8px">{m_eyebrow(title + k)}</div>'


def m_row(label, helper="", value="", chevron=True, control="", danger=False, sep=True):
    color = DANGER if danger else "#0b1117"
    val = f'<span style="font-size: 14px; color: #626e7d; text-align: right; max-width: 55%; white-space: nowrap; overflow: hidden; text-overflow: ellipsis">{value}</span>' if value else ""
    chev = ic("chev-r", 16, "#b1bac4") if chevron and not danger else ""
    help_ = f'<span style="font-family: {MONO}; font-weight: 500; font-size: 11px; line-height: 1.3; color: #626e7d; white-space: nowrap; overflow: hidden; text-overflow: ellipsis">{helper}</span>' if helper else ""
    sepd = '<div style="height: 0.5px; background: rgba(11,17,23,0.07); margin-left: 20px"></div>' if sep else ""
    return f"""<div style="display: flex; align-items: center; gap: 12px; padding: 14px 20px; background: #ffffff">
<div style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px"><span style="font-size: 15px; line-height: 1.3; color: {color}">{label}</span>{help_}</div>
{val}{control}{chev}
</div>{sepd}"""


def pill(text, on=False, tone="off"):
    if tone == "success":
        return f'<span style="display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 999px; background: rgba(63,179,122,0.16); font-family: {MONO}; font-size: 12px; color: #217a45"><span style="width: 7px; height: 7px; border-radius: 999px; background: #217a45"></span>{text}</span>'
    if tone == "warning":
        return f'<span style="display: inline-flex; align-items: center; padding: 4px 10px; border-radius: 999px; background: rgba(224,138,60,0.16); font-family: {MONO}; font-size: 12px; color: #8a5a0a">{text}</span>'
    dot = "#217a45" if on else "#b1bac4"
    return f'<span style="display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 999px; background: #f1f3f5; font-family: {MONO}; font-size: 12px; color: {"#217a45" if on else "#626e7d"}"><span style="width: 7px; height: 7px; border-radius: 999px; background: {dot}"></span>{"on" if on else "off"}</span>'


def m_wide_section(title, kicker="", first=False):
    k = f'<span style="font-size: 11px; color: #b1bac4">{kicker}</span>' if kicker else ""
    return f'<div style="display: flex; align-items: baseline; gap: 10px; margin: {0 if first else 36}px 0 12px">{m_eyebrow(title, "#3d4955", 600, 0.1, 11)}{k}</div>'


def m_wide_row(label, helper="", value="", chevron=True, control="", danger=False, value_html="", item=False):
    color = DANGER if danger else "#626e7d"
    help_col = "#626e7d" if item else "#b1bac4"
    help_ = f'<span style="font-family: {MONO}; font-size: 11px; line-height: 1.3; color: {help_col}; margin-top: 4px">{helper}</span>' if helper else ""
    lab = (f'<span style="font-weight: 600; font-size: 14px; line-height: 1.3; color: {DANGER if danger else "#0b1117"}">{label}</span>' if item
           else m_eyebrow(label, color))
    val = value_html or (f'<span style="font-family: {MONO}; font-size: 12px; color: #3d4955; text-align: right; white-space: nowrap; overflow: hidden; text-overflow: ellipsis">{value}</span>' if value else "")
    gutter = "" if danger else f'<span style="width: 14px; display: inline-flex; justify-content: flex-end">{ic("chev-r", 14, "#b1bac4") if chevron else ""}</span>'
    return f"""<div style="display: flex; align-items: center; gap: 24px; min-height: 36px; padding: 8px 0">
<div style="flex: 1 1 148px; min-width: 0; display: flex; flex-direction: column">{lab}{help_}</div>
<div style="flex-shrink: 1; min-width: 0; max-width: 60%; display: flex; align-items: center; justify-content: flex-end; gap: 10px">{val}{control}{gutter}</div>
</div>"""


def switch(on=False, accent=DOC_ACCENT, label="", disabled=False):
    bg = accent if on else "rgba(11,17,23,0.14)"
    return (f'<button role="switch" aria-checked="{"true" if on else "false"}" aria-label="{label}" style="position: relative; width: 44px; height: 24px; border: 0; border-radius: 999px; '
            f'background: {bg}; opacity: {0.45 if disabled else 1}; padding: 0; cursor: pointer; flex-shrink: 0">'
            f'<span style="position: absolute; top: 3px; left: {23 if on else 3}px; width: 18px; height: 18px; border-radius: 999px; background: #ffffff; box-shadow: 0 1px 2px rgba(11,17,23,0.2)"></span></button>')


def textbox(text, rows=3, placeholder=False):
    color = "#626e7d" if placeholder else "#0b1117"
    return (f'<div style="min-height: {rows * 22 + 24}px; padding: 12px; border-radius: 12px; border: 0.5px solid rgba(11,17,23,0.14); background: #f1f3f5; '
            f'font-size: 15px; line-height: 1.5; color: {color}">{text}</div>')


def m_button(title, variant="secondary", size="sm", accent=None):
    h = {"sm": 40, "md": 40, "lg": 48}[size]
    padx = {"sm": 12, "md": 14, "lg": 18}[size]
    fs = {"sm": 12, "md": 14, "lg": 15}[size]
    if variant == "primary":
        bg, fg, fw = (accent or "#0b1117"), "#ffffff", 600
    elif variant == "danger":
        bg, fg, fw = "#c14545", "#ffffff", 600
    elif variant == "ghost":
        bg, fg, fw = "transparent", "#3d4955", 500
    elif variant == "danger-ghost":
        bg, fg, fw = "transparent", DANGER, 500
    else:
        bg, fg, fw = "rgba(11,17,23,0.04)", "#0b1117", 600
    return (
        f'<button style="min-height: {h}px; padding: 6px {padx}px; border: 0; border-radius: 10px; background: {bg}; '
        f'color: {fg}; font-family: Geist, sans-serif; font-weight: {fw}; font-size: {fs}px; cursor: pointer">{title}</button>'
    )


def meter(value, tail, pct, color=DOC_ACCENT, percent=True):
    p = f'<span style="font-family: {MONO}; font-size: 11px; color: #626e7d">{round(pct * 100)}%</span>' if percent else ""
    return f"""<span style="display: inline-flex; align-items: center; gap: 8px"><span style="font-family: 'Geist Mono', monospace; font-size: 11px; color: #3d4955">{value}<span style="color: #626e7d">{tail}</span></span><span role="progressbar" aria-label="{value}{tail}" style="width: 56px; height: 5px; border-radius: 999px; background: rgba(11,17,23,0.14); overflow: hidden; display: inline-block"><span style="display: block; width: {pct * 100}%; height: 100%; background: {color}"></span></span>{p}</span>"""


DAYS = [("W", 0.22, 0.02), ("T", 0.30, 0.02), ("F", 0.10, 0.01), ("S", 0.24, 0.02), ("S", 0.78, 0.05), ("M", 0.14, 0.01),
        ("T", 0.20, 0.02), ("W", 0.20, 0.02), ("T", 0.08, 0.01), ("F", 0.18, 0.02), ("S", 0.12, 0.01), ("S", 1.0, 0.06),
        ("M", 0.34, 0.03), ("T", 0.16, 0.02)]


def usage_chart(accent=DOC_ACCENT, today="$0.00", tin="102K", tout="831", cap="$1.00", left="100% left",
                footer="30-day total $1.61 · 17.2M in / 277K out", days=DAYS, mobile=True, empty=False):
    in_col = mix(accent, 0.24)
    bars = []
    labels = []
    n = len(days)
    for i, (d, t, o) in enumerate(days):
        last = i == n - 1
        total = 0 if empty else max(3, round(t * 104))
        out = 0 if empty else max(0, round(o * 104))
        bar = (f'<div style="width: 100%; max-width: 20px; height: {total}px; border-radius: 3px; overflow: hidden; display: flex; flex-direction: column">'
               f'<div style="height: {out}px; background: {accent}"></div><div style="flex: 1; background: {in_col}"></div></div>')
        if last and total > 0:
            bar = (f'<div style="width: 100%; max-width: 26px; padding: 1.5px; border-radius: 6px; border: 1.5px solid {accent}; '
                   f'background: #ffffff; display: flex; justify-content: center; box-sizing: border-box">{bar}</div>')
        bars.append(f'<div style="flex: 1; height: 100%; display: flex; justify-content: flex-end; align-items: center; flex-direction: column">{bar}</div>')
        labels.append(f'<span style="flex: 1; text-align: center; font-family: {MONO}; font-weight: {600 if last else 400}; font-size: 9px; line-height: 1; color: {accent if last else "#626e7d"}">{d}</span>')
    track = (f'<div style="margin-top: 20px; display: flex; flex-direction: column">'
             f'<div style="height: 104px; display: flex; align-items: flex-end; gap: 4px">{"".join(bars)}</div>'
             f'<div style="display: flex; gap: 4px; margin-top: 8px">{"".join(labels)}</div></div>'
             f'<div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; margin-top: 14px">'
             f'<span style="display: inline-flex; align-items: center; gap: 6px; font-size: 11px; color: #626e7d"><span style="width: 9px; height: 9px; border-radius: 2px; background: {in_col}"></span>input <span style="color: #b1bac4">·</span> <span style="width: 9px; height: 9px; border-radius: 2px; background: {accent}"></span>output</span>'
             f'<span style="font-family: {MONO}; font-size: 11px; color: #626e7d">{footer}</span></div>')
    empty_line = f'<span style="font-family: {MONO}; font-size: 11px; color: #b1bac4; margin-top: 14px">no usage in the last {n} days</span>'
    tile = lambda label, body: f'<div style="flex: 1; min-width: 0; display: flex; flex-direction: column">{m_eyebrow(label, "#626e7d", 400, 0.1, 11, "margin-bottom: 6px")}{body}</div>'
    def mono(v, u):
        unit = f'<span style="font-weight: 400; font-size: 11px; color: #626e7d"> {u}</span>' if u else ""
        return f'<span style="font-family: {MONO}; font-weight: 500; font-size: 18px; line-height: 1; color: #0b1117">{v}{unit}</span>'
    return f"""<div style="display: flex; flex-direction: column">
<div style="display: flex; align-items: flex-start; padding-bottom: 14px; border-bottom: 0.5px solid rgba(11,17,23,0.14)">
{tile("Today", f'<span style="font-weight: 600; font-size: 28px; line-height: 1; letter-spacing: -0.018em; color: {accent}">{today}</span>')}
{tile("Input", mono(tin, "tok"))}
{tile("Output", mono(tout, "tok"))}
{tile("Cap / day" if cap else "Avg / day", mono(cap or "$0.00", left))}
</div>
{empty_line if empty else track}
</div>"""


def mix(color, amount, over="var(--bg-pane, #ffffff)"):
    return f"color-mix(in srgb, {color} {round(amount * 100)}%, {over})"



PROFILES = [("doc", DOC_ACCENT, "6w", True), ("alpi", "#c9a227", "", False), ("abby", "#c33d7e", "", False),
            ("clonara", "#e2704a", "", False), ("galt", "#5b6670", "", False), ("lingo", "#8a5cf6", "", False),
            ("yuri", "#f0a58f", "6w", False), ("etxea", "#9ccf95", "", False)]


def m_sidebar(h, selected="doc", badge="1", version="v0.5.0", conn_selected=False):
    rows = []
    for name, col, ts, sel in PROFILES:
        sel = name == selected
        dim = name == "etxea"
        stamp = f'<span style="font-family: {MONO}; font-size: 11px; color: #626e7d">{ts}</span>' if ts else ""
        bg = "rgba(11,17,23,0.06)" if sel else "transparent"
        rows.append(
            f'<a href="Fold-Chat.dc.html" style="display: flex; align-items: center; gap: 12px; min-height: 44px; padding: 8px 10px; border-radius: 10px; '
            f'background: {bg}; text-decoration: none; color: inherit; opacity: {0.55 if dim else 1}">'
            f'{diamond(col, 16)}<span style="flex: 1; font-size: 14px; line-height: 1.3; color: #0b1117">{name}</span>{stamp}</a>')
    badge_html = (f'<span style="position: absolute; top: -4px; right: -6px; min-width: 16px; height: 16px; padding: 0 4px; border-radius: 999px; '
                  f'background: #c14545; border: 1.5px solid #f5f6f8; color: #fff; font-family: {MONO}; font-size: 9px; line-height: 13px; text-align: center; box-sizing: border-box">{badge}</span>') if badge else ""
    return f"""<div style="width: 280px; height: {h}px; flex-shrink: 0; box-sizing: border-box; background: #f5f6f8; border-right: 0.5px solid rgba(11,17,23,0.07); display: flex; flex-direction: column">
<div style="padding: 6px 12px 8px; display: flex; align-items: center; gap: 4px">{m_eyebrow("Connection", "#626e7d", 500, 0.06, 11, "flex: 1")}<button aria-label="Hide sidebar" class="m-chrome">{ic("panel", 16, "#3d4955")}</button><button aria-label="Filter" class="m-chrome">{ic("search", 16, "#3d4955")}</button></div>
<div style="margin: 0 12px; padding: 12px 14px; border-radius: 12px; background: {"rgba(11,17,23,0.06)" if conn_selected else "#ffffff"}; display: flex; align-items: center; gap: 12px">
<span style="position: relative">{ic("chip", 18, "#3d4955")}<span style="position: absolute; right: -2px; bottom: -2px; width: 7px; height: 7px; border-radius: 999px; background: #3fb37a; border: 1.5px solid #fff"></span></span>
<div style="flex: 1; min-width: 0; display: flex; flex-direction: column"><span style="font-weight: 600; font-size: 14px; line-height: 1.3">casa</span><span style="font-family: 'Geist Mono', monospace; font-size: 11px; line-height: 1.3; color: #626e7d">ws://100.99.29.84:49200</span></div>
{ic("chev-d", 16, "#3d4955")}
</div>
<div style="padding: 24px 12px 8px; display: flex; align-items: center">{m_eyebrow("Profiles", "#626e7d", 500, 0.06, 11, "flex: 1")}<button aria-label="New profile" class="m-chrome">{ic("plus", 16, "#3d4955")}</button></div>
<div style="padding: 0 12px; display: flex; flex-direction: column">{''.join(rows)}</div>
<div style="padding: 24px 12px 8px; display: flex; align-items: center">{m_eyebrow("Workgroups", "#626e7d", 500, 0.06, 11, "flex: 1")}<button aria-label="New workgroup" class="m-chrome">{ic("plus", 16, "#3d4955")}</button></div>
<div style="flex: 1"></div>
<div style="height: 44px; padding: 0 12px; display: flex; align-items: center; gap: 10px; border-top: 0.5px solid rgba(11,17,23,0.07)">
<a href="Phone-Settings.dc.html" style="display: inline-flex; align-items: center; gap: 8px; padding: 6px 8px; border-radius: 10px; text-decoration: none; color: #3d4955; font-weight: 500; font-size: 12px">{ic("gear", 18, "#3d4955")}Settings</a>
<span style="position: relative; display: inline-flex; padding: 6px 8px">{ic("bell", 18, "#3d4955")}{badge_html}</span>
<button aria-label="Theme: Light" class="m-chrome" style="padding: 6px 8px">{ic("sun", 18, "#3d4955")}</button>
<span style="flex: 1"></span>
<span style="font-family: 'Geist Mono', monospace; font-weight: 500; font-size: 11px; color: #b1bac4">{version}</span>
</div>
</div>"""



def m_chat_header(title, accent, meta_html, two_pane=False, back=True, meta_items=None):
    gap = 12 if two_pane else 6
    back_html = f'<button aria-label="Back" class="m-chrome" style="margin-left: -6px">{ic("back", 20, "#3d4955")}</button>' if back else ""
    return f"""<div style="position: relative; display: flex; align-items: flex-start; gap: 10px; padding: 6px 16px 8px; background: #ffffff; border-bottom: 0.5px solid rgba(11,17,23,0.07)">
{back_html}
<div style="flex: 1; min-width: 0; display: flex; flex-direction: column">
<div style="display: flex; align-items: center; gap: {gap}px">{diamond(accent, 18)}<span style="flex: 1; font-weight: 600; font-size: 18px; line-height: 1.3; white-space: nowrap; overflow: hidden; text-overflow: ellipsis">{title}</span>
<span style="display: flex; align-items: center; flex-shrink: 0"><button aria-label="Sessions" class="m-chrome">{ic("clock", 20, "#3d4955")}</button><button aria-label="More" class="m-chrome">{ic("more", 20, "#3d4955")}</button></span></div>
{m_meta_strip(meta_items, 14) if two_pane else f'<div style="display: flex; align-items: center; gap: 6px; margin-top: 1px; white-space: nowrap; overflow: hidden">{meta_html}</div>'}
</div>
<div style="position: absolute; left: 16px; bottom: -0.5px; height: 1.5px; width: 36px; background: {accent}"></div>
</div>"""


def m_thread(accent, pane=False):
    cap = "76%" if pane else "82%"
    return f"""<div style="flex: 1; display: flex; flex-direction: column; justify-content: flex-end; gap: 4px; padding-bottom: 12px">
<div style="display: flex; flex-direction: column; align-items: flex-end; gap: 4px; padding: 0 16px">
<div style="max-width: {cap}; padding: 12px 16px; border-radius: 18px; border-bottom-right-radius: 6px; background: {mix(accent, 0.12)}; font-size: 15px; line-height: 1.65">Hi</div>
<span style="font-family: 'Geist Mono', monospace; font-size: 11px; color: #626e7d">42d</span>
</div>
<div style="padding: 10px 16px 0; display: flex; align-items: center; gap: 8px; font-family: 'Geist Mono', monospace; font-size: 12px; color: #626e7d; white-space: nowrap; overflow: hidden">{ic("chev-r", 12, "#626e7d")}<span style="overflow: hidden; text-overflow: ellipsis">thinking · 4s The user just said "Hi". A greeting. Reply warmly and ask what they need…</span></div>
<div style="padding: 8px 16px 0; font-size: 15px; line-height: 1.65; color: #0b1117; max-width: 90%">Morning. What do you have for me today: labs, sleep, training, or something deeper?</div>
</div>"""


def m_composer(name="doc"):
    return f"""<div style="padding: 8px 16px 12px; border-top: 0.5px solid rgba(11,17,23,0.07); background: #ffffff">
<div style="display: flex; flex-direction: column; gap: 6px; padding: 12px 12px 8px; border: 0.5px solid rgba(11,17,23,0.14); border-radius: 16px">
<label style="display: block"><span style="position: absolute; left: -9999px">Message</span><input placeholder="Message @{name}…" style="width: 100%; border: 0; outline: 0; background: transparent; font-family: Geist, sans-serif; font-size: 15px; color: #0b1117; padding: 4px 4px 8px; box-sizing: border-box"></label>
<div style="display: flex; justify-content: flex-end; align-items: center; gap: 10px"><button aria-label="Attach" class="m-chrome" style="width: 36px; height: 36px">{ic("clip", 20, "#3d4955")}</button><button aria-label="Send" style="width: 36px; height: 36px; border: 0; border-radius: 10px; background: #f1f3f5; display: flex; align-items: center; justify-content: center; cursor: pointer">{ic("up", 18, "#626e7d")}</button></div>
</div>
</div>"""


def phone_chat():
    meta = (f'<span style="font-family: {MONO}; font-size: 11px; color: #3d4955">deepseek-v4.1-flash</span>'
            f'{meter("24K", "/1.0M", 0.024, DOC_ACCENT, False)}{meter("$0.00", "/$1.00", 0, DOC_ACCENT, False)}')
    body = f"""<div style="display: flex; flex-direction: column; height: 100%">
{m_chat_header("doc", DOC_ACCENT, meta)}
{m_thread(DOC_ACCENT)}
{m_composer()}
</div>
"""
    return page("Phone · chat", 390, 844, body)


def fold_chat():
    meta = (f'<span style="font-family: {MONO}; font-size: 11px; color: #3d4955">deepseek-v4.1-flash</span>'
            f'{meter("24K", "/1.0M", 0.024)}{meter("$0.00", "/$1.00", 0)}')
    items = [f'<span style="font-family: {MONO}; font-size: 11px; color: #3d4955">deepseek-v4.1-flash</span>',
             meter("24K", "/1.0M", 0.024), meter("$0.00", "/$1.00", 0)]
    body = f"""<div style="display: flex; height: 100%">
{m_sidebar(884)}
<div style="flex: 1; min-width: 0; display: flex; flex-direction: column; background: #ffffff">
{m_chat_header("doc", DOC_ACCENT, meta, two_pane=True, back=False, meta_items=items)}
<div style="flex: 1; display: flex; flex-direction: column; max-width: 720px; width: 100%; align-self: center; box-sizing: border-box">{m_thread(DOC_ACCENT, pane=True)}</div>
<div style="max-width: 720px; width: 100%; align-self: center; box-sizing: border-box">{m_composer()}</div>
</div>
</div>
"""
    return page("Fold · chat, two panes", 852, 884, body)



def phone_profile_settings():
    body = f"""<div style="display: flex; flex-direction: column">
{m_screen_header("doc", "Profile · settings")}
{m_section("Overview", first=False)}
{m_row("Paused", "paused profiles can't be chatted and sort last in new-chat", control=switch(False, DOC_ACCENT, "Paused"), chevron=False)}
{m_row("Providers", "openrouter", "1")}
{m_row("Model", "", "deepseek-v4.1-flash")}
{m_row("Reasoning", "how hard the model thinks before answering", "default")}
{m_row("Fast model", "cheap model for side-tasks &amp; delegation", "main model")}
{m_row("Deep model", "stronger model for escalation &amp; deep research", "main model")}
{m_row("Vision model", "image inspection via read_image", "main model")}
{m_row("Budget", "daily spend cap", control=meter("$0.00", "/$1.00", 0))}
{m_row("Workspace", "", "/data/workspace/doc")}
{m_row("Accent", "", control='<span style="display: inline-flex; align-items: center; gap: 8px"><span style="width: 16px; height: 16px; border-radius: 999px; background: ' + DOC_ACCENT + '"></span><span style="font-family: {MONO}; font-size: 12px; color: #3d4955">#3d7ea6</span></span>')}
{m_row("Home", "", "~/.alpi/profiles/doc", chevron=False, sep=False)}
{m_section("Usage", "last 14 days")}
<div style="padding: 16px 20px; background: #ffffff">{usage_chart()}</div>
{m_section("Identity", "how peers see this agent")}
{m_row("Ancestral, lab-savvy personal doctor; food-first, skeptical of mainstream dogma", sep=False)}
{m_section("Service", "daemon")}
{m_row("Update alpi", "installs the newest alpi and restarts", control=m_button("Update"), chevron=False)}
{m_row("Restart daemon", "exits the daemon · supervisor relaunches · reconnects automatically", control=m_button("Restart"), chevron=False)}
{m_row("Email", "IMAP / Gmail accounts", control=pill("none"), sep=False)}
{m_section("ALP", "peers + workgroups")}
{m_row("Public key", "tap to copy", "X+iAJ/6f…lNs=", chevron=False)}
{m_row("Port", "ALP listener · set from alpi setup on the daemon's machine", "7423", chevron=False)}
{m_row("Concurrency", "active workgroup pipelines at once", "unlimited")}
{m_row("Peers", "", "0")}
{m_row("Workgroups", "", "0", chevron=False, sep=False)}
{m_section("Schedule")}
{m_row("Cron jobs", "disable · fire · delete · add new", "5", sep=False)}
{m_section("Sandbox")}
{m_row("Terminal", "wraps shell tools in sandbox-exec / bubblewrap", control=switch(False, DOC_ACCENT, "Terminal sandbox"), chevron=False)}
{m_row("Network", "enable terminal sandbox first", control=switch(False, DOC_ACCENT, "Sandbox network", disabled=True), chevron=False, sep=False)}
{m_section("Voice")}
{m_row("Voice", "", "Alvaro · Spanish (ES) · male")}
{m_row("Auto-read replies", "reads each agent reply aloud as it arrives — never your messages", control=switch(False, DOC_ACCENT, "Auto-read replies"), chevron=False, sep=False)}
{m_section("Danger zone")}
{m_row("Delete profile", "removes identity, memory, skills, schedule from disk. Cannot be undone.", danger=True, sep=False)}
</div>
"""
    return page("Phone · profile settings", 390, 2360, body)


def fold_profile_settings():
    inner = f"""<div style="max-width: 968px; padding: 20px 24px 40px; box-sizing: border-box; display: flex; flex-direction: column">
{m_wide_section("Overview", first=True)}
{m_wide_row("Paused", "paused profiles can't be chatted and sort last in new-chat", control=switch(False, DOC_ACCENT, "Paused"), chevron=False)}
{m_wide_row("Providers", "API keys + local Ollama", control='<span style="display: inline-flex; align-items: center; padding: 4px 10px; border-radius: 999px; background: #f1f3f5; font-family: {MONO}; font-size: 12px; color: #3d4955">openrouter</span>')}
{m_wide_row("Model", "", "deepseek-v4.1-flash")}
{m_wide_row("Reasoning", "how hard the model thinks before answering", "default")}
{m_wide_row("Fast model", "cheap model for side-tasks &amp; delegation", "main model")}
{m_wide_row("Deep model", "stronger model for escalation &amp; deep research", "main model")}
{m_wide_row("Vision model", "image inspection via read_image", "main model")}
{m_wide_row("Budget", "daily spend cap", control=meter("$0.00", "/$1.00", 0))}
{m_wide_row("Workspace", "", "/data/workspace/doc")}
{m_wide_row("Accent", "", control='<span style="display: inline-flex; align-items: center; gap: 8px"><span style="width: 16px; height: 16px; border-radius: 999px; background: ' + DOC_ACCENT + '"></span><span style="font-family: {MONO}; font-size: 12px; color: #3d4955">#3d7ea6</span></span>')}
{m_wide_row("Home", "", "~/.alpi/profiles/doc", chevron=False)}
{m_wide_section("Usage", "last 14 days")}
{usage_chart()}
{m_wide_section("Identity", "how peers see this agent")}
<div style="display: flex; align-items: flex-start; gap: 24px; padding: 8px 0">
<div style="width: 148px; padding-top: 8px">{m_eyebrow("Identity", "#626e7d")}</div>
<div style="flex: 1; max-width: 520px; display: flex; flex-direction: column; gap: 8px">{textbox("Ancestral, lab-savvy personal doctor; food-first, skeptical of mainstream dogma")}<div style="display: flex; justify-content: flex-end">{m_button("Draft", "ghost")}</div></div>
</div>
{m_wide_section("Service", "daemon")}
{m_wide_row("Daemon", "update installs the newest alpi · restart exits and the supervisor relaunches", control='<span style="display: inline-flex; gap: 8px">' + m_button("Update alpi") + m_button("Restart daemon") + '</span>', chevron=False)}
{m_wide_row("Email", "IMAP / Gmail accounts", control=pill("none"))}
{m_wide_section("ALP", "peers + workgroups")}
{m_wide_row("Public key", "tap to copy", "X+iAJ/6f…lNs=", chevron=False)}
{m_wide_row("Port", "ALP listener · set from alpi setup on the daemon's machine", "7423", chevron=False)}
{m_wide_row("Concurrency", "active workgroup pipelines at once", "unlimited")}
{m_wide_row("Peers", "", "0")}
{m_wide_row("Workgroups", "", "0", chevron=False)}
{m_wide_section("Sandbox")}
{m_wide_row("Terminal", "wraps shell tools in sandbox-exec / bubblewrap", control=switch(False, DOC_ACCENT, "Terminal sandbox"), chevron=False)}
{m_wide_row("Network", "enable terminal sandbox first", control=switch(False, DOC_ACCENT, "Sandbox network", disabled=True), chevron=False)}
{m_wide_section("Voice")}
{m_wide_row("Voice", "", "Alvaro · Spanish (ES) · male")}
{m_wide_row("Auto-read replies", "reads each agent reply aloud as it arrives — never your messages", control=switch(False, DOC_ACCENT, "Auto-read replies"), chevron=False)}
{m_wide_section("Danger zone")}
{m_wide_row("Delete profile", "removes identity, memory, skills, schedule from disk. Cannot be undone.", danger=True)}
</div>"""
    body = f"""<div style="display: flex; height: 100%">
{m_sidebar(2000)}
<div style="flex: 1; min-width: 0; display: flex; flex-direction: column; background: #ffffff">
{m_screen_header("doc", "Settings", wide=True, meta=[f'<span style="font-family: {MONO}; font-size: 12px; color: #3d4955">deepseek-v4.1-flash</span>', meter("$0.00", "/$1.00", 0)])}
{inner}
</div>
</div>
"""
    return page("Fold · profile settings", 852, 2000, body)



def phone_wg_settings():
    body = f"""<div style="display: flex; flex-direction: column">
{m_screen_header("#alpha", "Workgroup · settings", accent=ALPI_ACCENT, glyph='<span style="font-family: {MONO}; font-weight: 500; font-size: 18px; color: #626e7d">#</span>')}
{m_section("Overview")}
{m_row("Hub", "", "@doc", chevron=False)}
{m_row("Status", "pause stops dispatch · leave drops membership", control=pill("active", tone="success"), chevron=False)}
{m_row("Auto-read messages", "reads agents' automatic messages aloud — never your directives", control=switch(False, ALPI_ACCENT, "Auto-read messages"), chevron=False)}
{m_row("Accent", "", control='<span style="display: inline-flex; align-items: center; gap: 8px"><span style="width: 16px; height: 16px; border-radius: 999px; background: ' + ALPI_ACCENT + '"></span><span style="font-family: {MONO}; font-size: 12px; color: #3d4955">#8a5a0a</span></span>')}
{m_row("Id", "", "wg_4f2a…9c1e", chevron=False, sep=False)}
{m_section("Budget", "workgroup spend cap")}
<div style="padding: 16px 20px; background: #ffffff; display: flex; flex-direction: column; gap: 10px"><div style="display: flex; align-items: baseline; gap: 10px"><span style="font-weight: 600; font-size: 28px; line-height: 1; letter-spacing: -0.018em; color: #0b1117">$0.40</span><span style="font-family: {MONO}; font-size: 14px; color: #626e7d">of <span style="color: #3d4955">$5.00</span> · 8%</span><span style="flex: 1"></span>{m_button("Edit", "ghost")}</div><span style="display: block; height: 6px; border-radius: 999px; background: rgba(11,17,23,0.07); overflow: hidden"><span style="display: block; width: 8%; height: 100%; background: {ALPI_ACCENT}"></span></span></div>
{m_section("Usage", "last 14 days")}
<div style="padding: 16px 20px; background: #ffffff">{usage_chart(ALPI_ACCENT, "$0.00", "12K", "310", None, None, "14-day total $0.40 · 0.9M in / 22K out")}</div>
{m_section("Briefing")}
{m_row("Edit briefing", "shared context every member reads first", sep=False)}
{m_section("Pipelines")}
{m_row("Daily digest", "3 stages · last run 2h ago", "ok")}
{m_row("+ New pipeline", "", chevron=False, sep=False)}
{m_section("Members", "3")}
{m_row("@doc", "hub", control='<span style="font-family: {MONO}; font-size: 12px; color: #626e7d">hub</span>', chevron=False)}
{m_row("@alpi", "joined 6w ago", control=f'<button aria-label="Remove @alpi" class="m-chrome">{ic("x", 16, "#3d4955")}</button>', chevron=False)}
{m_row("@yuri", "joined 6w ago", control=f'<button aria-label="Remove @yuri" class="m-chrome">{ic("x", 16, "#3d4955")}</button>', chevron=False)}
{m_row("+ Add member", "", chevron=False, sep=False)}
{m_section("Invitations", "1 pending")}
{m_row("@lingo", "alpi workgroup join doc wg_4f2a…9c1e", control=f'<button aria-label="Copy join command" class="m-chrome">{ic("copy", 16, "#3d4955")}</button>', chevron=False, sep=False)}
{m_section("Danger zone")}
{m_row("Leave workgroup", "drops this profile's membership", danger=True)}
{m_row("Delete workgroup", "removes it for every member. Cannot be undone.", danger=True, sep=False)}
</div>
"""
    return page("Phone · workgroup settings", 390, 1700, body)


def fold_wg_settings():
    inner = f"""<div style="max-width: 968px; padding: 20px 24px 40px; box-sizing: border-box; display: flex; flex-direction: column">
{m_wide_section("Overview", first=True)}
{m_wide_row("Hub", "", "@doc", chevron=False)}
{m_wide_row("Status", "pause stops dispatch · leave drops membership", control=pill("active", tone="success"), chevron=False)}
{m_wide_row("Auto-read messages", "reads agents' automatic messages aloud — never your directives", control=switch(False, ALPI_ACCENT, "Auto-read messages"), chevron=False)}
{m_wide_row("Id", "", "wg_4f2a…9c1e", chevron=False)}
{m_wide_section("Budget", "workgroup spend cap")}
<div style="display: flex; flex-direction: column; gap: 10px; padding: 8px 0"><div style="display: flex; align-items: baseline; gap: 10px"><span style="font-weight: 600; font-size: 28px; line-height: 1; letter-spacing: -0.018em; color: #0b1117">$0.40</span><span style="font-family: {MONO}; font-size: 14px; color: #626e7d">of <span style="color: #3d4955">$5.00</span> · 8%</span><span style="flex: 1"></span>{m_button("Edit", "ghost")}</div><span style="display: block; height: 6px; border-radius: 999px; background: rgba(11,17,23,0.07); overflow: hidden"><span style="display: block; width: 8%; height: 100%; background: {ALPI_ACCENT}"></span></span></div>
{m_wide_section("Usage", "last 14 days")}
{usage_chart(ALPI_ACCENT, "$0.00", "12K", "310", None, None, "14-day total $0.40 · 0.9M in / 22K out")}
{m_wide_section("Briefing")}
{m_wide_row("Edit briefing", "shared context every member reads first")}
{m_wide_section("Members", "3")}
{m_wide_row("@doc", "Ancestral, lab-savvy personal doctor; food-first, skeptical of mainstream dogma", "hub", chevron=False, item=True)}
{m_wide_row("@alpi", "Household operator: schedules, reminders, the boring glue.", control=pill("joined", tone="success") + f'<button aria-label="Remove @alpi" class="m-chrome">{ic("x", 16, "#3d4955")}</button>', chevron=False, item=True)}
{m_wide_row("@yuri", "Translator and editor; keeps the tone consistent across languages.", control=pill("joined", tone="success") + f'<button aria-label="Remove @yuri" class="m-chrome">{ic("x", 16, "#3d4955")}</button>', chevron=False, item=True)}
{m_wide_section("Invitations", "1 pending")}
{m_wide_row("@lingo", "alpi workgroup join doc wg_4f2a…9c1e", control=f'<button aria-label="Copy join command" class="m-chrome">{ic("copy", 16, "#3d4955")}</button>', chevron=False, item=True)}
{m_wide_section("Danger zone")}
{m_wide_row("Leave workgroup", "drops this profile's membership", danger=True)}
{m_wide_row("Delete workgroup", "removes it for every member. Cannot be undone.", danger=True)}
</div>"""
    body = f"""<div style="display: flex; height: 100%">
{m_sidebar(1300, selected="")}
<div style="flex: 1; min-width: 0; display: flex; flex-direction: column; background: #ffffff">
{m_screen_header("alpha", "Settings", accent=ALPI_ACCENT, glyph='<span style="font-family: {MONO}; font-weight: 500; font-size: 18px; color: #626e7d">#</span>', wide=True, meta=['<span style="font-family: {MONO}; font-size: 12px; color: #3d4955">hub @doc</span>', '<span style="font-family: {MONO}; font-size: 12px; color: #3d4955">3 members</span>', '<span style="font-family: {MONO}; font-size: 12px; color: #217a45">active</span>', '<span style="font-family: {MONO}; font-size: 12px; color: #626e7d">wg_4f2a…9c1e</span>'])}
{inner}
</div>
</div>
"""
    return page("Fold · workgroup settings", 852, 1300, body)



def conn_row(label, meta, cost):
    return m_row(label, meta, cost)


def phone_connections():
    body = f"""<div style="display: flex; flex-direction: column">
{m_screen_header("Connections", "Daemon · paired apps", glyph="", right=m_button("New", "primary", "md"))}
{m_section("Host", "local socket · setup, TUI, CLI")}
{m_row("Local host", "14 sessions · seen now", "$6.28", sep=False)}
{m_section("Connections", "2 paired")}
{m_row("emulator-android", "admin · all profiles · 2 devices · 4 sessions · seen now", "$0.00")}
{m_row("remote", "admin · all profiles · 2 devices · 4 sessions · seen now", "$0.44", sep=False)}
</div>
"""
    return page("Phone · connections", 390, 844, body)


def device_row(name, meta, wide=False):
    ctl = f'<button aria-label="Revoke {name}" class="m-chrome">{ic("x", 16, "#3d4955")}</button>'
    return m_wide_row(name, meta, control=ctl, chevron=False, item=True) if wide else m_row(name, meta, control=ctl, chevron=False)


def phone_connection_detail():
    body = f"""<div style="display: flex; flex-direction: column">
{m_screen_header("emulator-android", "Connection · admin", glyph="")}
{m_section("Overview")}
{m_row("Label", "", "emulator-android")}
{m_row("Role", "manages profiles and connections", control=pill("admin", tone="warning"), chevron=False)}
{m_row("Profiles", "", "all")}
{m_row("Session scope", "one thread per connection, or one per device", "connection")}
{m_row("Enabled", "this phone goes offline with it · an admin elsewhere must re-enable it", control=switch(True, ALPI_ACCENT, "Enabled"), chevron=False)}
{m_row("Sessions", "", "4", chevron=False)}
{m_row("Last seen", "", "now", chevron=False, sep=False)}
{m_section("Usage", "last 14 days")}
<div style="padding: 16px 20px; background: #ffffff">{usage_chart(ALPI_ACCENT, "$0.00", "0", "0", None, None, "14-day total $0.00 · 0 in / 0 out", empty=True)}</div>
{m_section("Devices", "2 paired")}
{device_row("sdk_gphone64_arm64", "mobile · 0.4.11 · 7d ago")}
{device_row("sdk_gphone64_arm64", "mobile · 0.5.0 · now")}
{m_row("+ Add device", "one-time pairing link", chevron=False, sep=False)}
{m_section("Danger zone")}
{m_row("Delete connection", "revokes every device and its sessions. Cannot be undone.", danger=True, sep=False)}
</div>
"""
    return page("Phone · connection detail", 390, 1500, body)


def fold_connection_detail():
    inner = f"""<div style="max-width: 968px; padding: 20px 24px 40px; box-sizing: border-box; display: flex; flex-direction: column">
{m_wide_section("Overview", first=True)}
{m_wide_row("Label", "", "emulator-android")}
{m_wide_row("Role", "manages profiles and connections", control=pill("admin", tone="warning"), chevron=False)}
{m_wide_row("Profiles", "", "all")}
{m_wide_row("Session scope", "one thread per connection, or one per device", "connection")}
{m_wide_row("Enabled", "this phone goes offline with it · an admin elsewhere must re-enable it", control=switch(True, ALPI_ACCENT, "Enabled"), chevron=False)}
{m_wide_row("Sessions", "", "4", chevron=False)}
{m_wide_row("Last seen", "", "now", chevron=False)}
{m_wide_section("Usage", "last 14 days")}
{usage_chart(ALPI_ACCENT, "$0.00", "0", "0", None, None, "14-day total $0.00 · 0 in / 0 out", empty=True)}
{m_wide_section("Devices", "2 paired")}
{device_row("sdk_gphone64_arm64", "mobile · 0.4.11 · 7d ago", wide=True)}
{device_row("sdk_gphone64_arm64", "mobile · 0.5.0 · now", wide=True)}
{m_wide_row("+ Add device", "one-time pairing link", chevron=False)}
{m_wide_section("Danger zone")}
{m_wide_row("Delete connection", "revokes every device and its sessions. Cannot be undone.", danger=True)}
</div>"""
    body = f"""<div style="display: flex; height: 100%">
{m_sidebar(1300, selected="", conn_selected=True)}
<div style="flex: 1; min-width: 0; display: flex; flex-direction: column; background: #ffffff">
{m_screen_header("emulator-android", "Connection · admin", glyph="", wide=True, accent=ALPI_ACCENT, meta=None)}
{inner}
</div>
</div>
"""
    return page("Fold · connection detail", 852, 1300, body)



def phone_settings():
    body = f"""<div style="display: flex; flex-direction: column">
{m_screen_header("Settings", "This phone", glyph="")}
{m_section("This phone")}
{m_row("Re-pair this phone", "opens QR scanner")}
{m_row("Fingerprint unlock", "not enrolled in OS settings", control=pill("off"), chevron=False, sep=False)}
{m_section("Daemon")}
{m_row("Connections", "paired apps, devices, pairing links, usage", sep=False)}
{m_section("Notifications")}
{m_row("System permission", "instant while alpi is open · in the background via push", control=pill("off"))}
{m_row("Delivery status", "Permission denied — enable alpi in system notifications", control=pill("off"), chevron=False)}
{m_row("Test notifications", "dev-only · sample notifications + routing check", sep=False)}
{m_section("Appearance")}
{m_row("Theme", "", "Light")}
{m_row("Text size", "multiplies your OS text size · long-press resets", control='<span style="display: inline-flex; align-items: center; gap: 10px"><span style="font-size: 14px; color: #626e7d">Default</span>' + m_button("−") + m_button("+") + '</span>', chevron=False, sep=False)}
{m_section("Danger zone")}
{m_row("Sign out", "forgets the pairing on this phone", danger=True, sep=False)}
<div style="padding: 24px 20px; display: flex; justify-content: space-between; align-items: center">{m_eyebrow("About")}<span style="font-family: 'Geist Mono', monospace; font-size: 11px; color: #b1bac4">Alpi mobile · v0.5.0</span></div>
</div>
"""
    return page("Phone · app settings", 390, 1100, body)



def write(name, html):
    with open(os.path.join(ROOT, name), "w") as f:
        f.write(html)


CSS = """
.m-chrome{width:28px;height:28px;border:0;border-radius:8px;background:transparent;display:inline-flex;align-items:center;justify-content:center;padding:0;cursor:pointer;color:#3d4955}
.m-chrome:hover{background:rgba(11,17,23,0.06)}
button,input{font-family:inherit}
"""


def build(desktop_boards):
    with open(os.path.join(ROOT, "parity.css"), "w") as f:
        f.write(CSS)

    boards = {}
    order = []
    notes = {}

    def place(name, html, x, y, w, h, title, page):
        write(name, html)
        boards[name] = {"x": x, "y": y, "w": w, "h": h, "title": title, "page": page}
        order.append(name)

    def title(id_, text, y, page, x=0, max_w=2600):
        notes[id_] = {"x": x, "y": y, "text": text, "kind": "title1", "maxW": max_w, "page": page}

    from audit2 import audit2_board
    from desktop_overlays import desktop_overlays
    from mobile_overlays import MOBILE_OVERLAYS
    from system_boards import SYSTEM

    from conversation_boards import CONVERSATION

    y = 0
    for label, items in (
        ("Foundations", [("System-Tokens.dc.html", SYSTEM["tokens"](), 2000, "System · tokens")]),
        ("Controls and feedback", [("System-DesktopComponents.dc.html", SYSTEM["desktop"](), 1900, "Desktop · controls and feedback"), ("System-MobileComponents.dc.html", SYSTEM["mobile"](), 2300, "Mobile · controls and feedback")]),
        ("Conversation", [("System-DesktopConversation.dc.html", CONVERSATION["desktop"](), 2560, "Desktop · conversation"), ("System-MobileConversation.dc.html", CONVERSATION["mobile"](), 1340, "Mobile · conversation")]),
        ("Workgroups", [("System-DesktopWorkgroup.dc.html", CONVERSATION["desktop_wg"](), 1200, "Desktop · workgroups"), ("System-MobileWorkgroup.dc.html", CONVERSATION["mobile_wg"](), 760, "Mobile · workgroups")]),
    ):
        y += 240
        title(f"s-{label}", label, y - 223, "system")
        for i, (name, html, h, t) in enumerate(items):
            place(name, html, i * 1360, y, 1280, h, t, "system")
        y += max(h for _, _, h, _ in items)

    y = 0
    for name, html, h, label in (
        ("Desktop-Chat.dc.html", desktop_boards["chat"], 800, "Chat"),
        ("Desktop-ProfileSettings.dc.html", desktop_boards["profile"], 2600, "Profile settings"),
        ("Desktop-WorkgroupSettings.dc.html", desktop_boards["wg"], 1900, "Workgroup settings"),
        ("Desktop-Connections.dc.html", desktop_boards["connections"], 1300, "Connections"),
        ("Desktop-AppSettings.dc.html", desktop_boards["app"], 800, "App settings"),
        ("Desktop-Overlays.dc.html", desktop_overlays(), 860, "Overlays"),
    ):
        y += 240
        title(f"d-{label}", label, y - 223, "desktop")
        place(name, html, 0, y, 1280, h, f"Desktop · {label.lower()}", "desktop")
        y += h

    X_FOLD, X_PHONE = 0, 932
    y = 0
    rows = (
        ("Chat", [("Fold-Chat.dc.html", fold_chat(), X_FOLD, 852, 884, "Fold · chat"), ("Phone-Chat.dc.html", phone_chat(), X_PHONE, 390, 844, "Phone · chat")]),
        ("Profile settings", [("Fold-ProfileSettings.dc.html", fold_profile_settings(), X_FOLD, 852, 2000, "Fold · profile settings"), ("Phone-ProfileSettings.dc.html", phone_profile_settings(), X_PHONE, 390, 2360, "Phone · profile settings")]),
        ("Workgroup settings", [("Fold-WorkgroupSettings.dc.html", fold_wg_settings(), X_FOLD, 852, 1300, "Fold · workgroup settings"), ("Phone-WorkgroupSettings.dc.html", phone_wg_settings(), X_PHONE, 390, 1700, "Phone · workgroup settings")]),
        ("Connections", [("Fold-ConnectionDetail.dc.html", fold_connection_detail(), X_FOLD, 852, 1300, "Fold · connection detail"), ("Phone-Connections.dc.html", phone_connections(), X_PHONE, 390, 844, "Phone · connections"), ("Phone-ConnectionDetail.dc.html", phone_connection_detail(), X_PHONE + 470, 390, 1500, "Phone · connection detail")]),
        ("App settings", [("Phone-Settings.dc.html", phone_settings(), X_PHONE, 390, 1100, "Phone · app settings")]),
        ("Overlays", [("Fold-Sheet.dc.html", MOBILE_OVERLAYS["fold_sheet"](), X_FOLD, 852, 884, "Fold · sheet as a centred dialog"), ("Phone-Sheet.dc.html", MOBILE_OVERLAYS["phone_sheet"](), X_PHONE, 390, 844, "Phone · sheet"), ("Phone-ActionSheet.dc.html", MOBILE_OVERLAYS["phone_action"](), X_PHONE + 470, 390, 844, "Phone · action sheet"), ("Phone-TypedConfirm.dc.html", MOBILE_OVERLAYS["phone_confirm"](), X_PHONE + 940, 390, 844, "Phone · typed confirm")]),
    )
    for label, items in rows:
        y += 240
        title(f"m-{label}", label, y - 223, "mobile")
        for name, html, x, w, h, t in items:
            place(name, html, x, y, w, h, t, "mobile")
        y += max(h for _, _, _, _, h, _ in items)

    place("Main.dc.html", audit2_board(), 0, 0, 1280, 140 + 90 * 6 + 120, "Open work", "audit")

    live_path = os.path.join(os.path.dirname(ROOT), "live", "project", "canvas.json")
    index = {
        "v": 3,
        "createdOnFiles": {"v": 1, "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")},
        "title": "Alpi desktop and mobile parity",
        "launch": {"view": "canvas", "page": "system"},
        "pages": [{"id": "system", "name": "System"}, {"id": "desktop", "name": "Desktop"}, {"id": "mobile", "name": "Mobile"}, {"id": "audit", "name": "Open work"}],
        "boards": boards,
        "order": order,
        "notes": notes,
        "designSystems": [],
    }
    if os.path.exists(live_path):
        # Keys the page added (attachments, …) survive; frames are the generator's, the layout moved to pages on purpose.
        with open(live_path) as f:
            live = json.load(f)
        for k, v in live.items():
            if k not in index:
                index[k] = v
    with open(os.path.join(ROOT, "canvas.json"), "w") as f:
        json.dump(index, f, indent=1)
    return order


if __name__ == "__main__":
    from desktop_boards import DESKTOP
    names = build(DESKTOP)
    print("\n".join(names))
