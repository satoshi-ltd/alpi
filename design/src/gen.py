import re
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
    "terminal": '<path d="M4 17l6-5-6-5"/><path d="M12 19h8"/>',
    "globe": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>',
    "file": '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><path d="M14 3v6h6"/>',
    "link": '<path d="M10 14a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1"/><path d="M14 10a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1"/>',
    "mic": '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/>',
    "pin": '<path d="M12 17v5"/><path d="M8 3h8l-1 7 3 3v2H6v-2l3-3z"/>',
    "activity": '<path d="M3 12h4l3-8 4 16 3-8h4"/>',
    "alert": '<path d="M12 3l10 18H2z"/><path d="M12 10v5M12 18v.5"/>',
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
    "history": '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l4 2"/>',
    "sparkle": '<path d="M9.94 15.5a2 2 0 0 0-1.44-1.44l-6.13-1.58a.5.5 0 0 1 0-.96L8.5 9.94A2 2 0 0 0 9.94 8.5l1.58-6.14a.5.5 0 0 1 .96 0L14.06 8.5a2 2 0 0 0 1.44 1.44l6.13 1.58a.5.5 0 0 1 0 .96L15.5 14.06a2 2 0 0 0-1.44 1.44l-1.58 6.14a.5.5 0 0 1-.96 0z"/>',
    "moon": '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>',
    "pin-off": '<path d="M12 17v5"/><path d="M15 9.34V6h1a2 2 0 0 0 0-4H7.89"/><path d="M2 2l20 20"/><path d="M9 9v1.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V16a1 1 0 0 0 1 1h11"/>',
    "trash": '<path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>',
    "pause": '<rect x="6" y="4" width="4" height="16" rx="1"/><rect x="14" y="4" width="4" height="16" rx="1"/>',
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
        return f'<span style="display: inline-flex; align-items: center; padding: 4px 10px; border-radius: 999px; background: rgba(224,138,60,0.16); font-family: {MONO}; font-size: 12px; color: #b3470e">{text}</span>'
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



def button_heights(client):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "common", "button.mjs")
    with open(path) as f:
        src = f.read()
    return {size: int(value) for size, value in re.findall(r"(\w+): \{[^}]*" + client + r": (\d+)", src)}

def m_button(title, variant="secondary", size="sm", accent=None):
    h = button_heights("mobile")[size]
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

WARNING_TEXT = "#b3470e"
M_STATES = {"alpi": ("working", None), "abby": ("needs-you", None), "clonara": ("failed", None)}
M_STATE_TEXT = {"needs-you": "needs you", "failed": "failed", "working": "working"}
M_PINNED = ("doc",)
PREVIEWS = {"doc": "Triglycerides moved most: 142 → 88 mg/dL", "alpi": "Summarizing yesterday’s deploys…", "abby": "Wants to send the invoice reminder",
            "clonara": "weekly labs failed · timeout", "galt": "Filed the Q3 receipts", "lingo": "Ready for today’s Basque drill?", "yuri": "Translation of the letter is in",
            "etxea": "needs provider — tap to set up"}


def m_row_state(state, phases=None):
    color = {"needs-you": WARNING_TEXT, "failed": DANGER, "working": ALPI_ACCENT}[state]
    font = f"font-family: {MONO}; font-weight: 500;" if phases else "font-weight: 500;"
    return (f'<span data-state="{state}" style="display: inline-flex; align-items: center; gap: 6px; white-space: nowrap">'
            f'<span style="width: 6px; height: 6px; border-radius: 999px; background: {color}"></span>'
            f'<span style="{font} font-size: 11px; line-height: 14.3px; color: {color}">{phases or M_STATE_TEXT[state]}</span></span>')


def m_count_badge(n, tone="danger", ring="#f5f6f8"):
    bg = "#e08a3c" if tone == "warning" else "#c14545"
    fg = "#0b1117" if tone == "warning" else "#ffffff"
    return (f'<span style="position: absolute; top: -6px; right: -8px; min-width: 18px; height: 18px; padding: 0 6px; border-radius: 999px; border: 1.5px solid {ring}; background: {bg}; '
            f'color: {fg}; font-weight: 600; font-size: 11px; line-height: 15px; text-align: center; box-sizing: border-box; white-space: nowrap">{n}</span>')


def m_glyph(kind, color):
    if kind == "workgroup":
        from desktop_boards import diamond_stack
        return diamond_stack(color, 10)
    return diamond(color, 16)


def m_roster_row(name, color, kind="profile", ts="", state=None, phases=None, selected=False, unread=False, compact=True, dim=False, href="Fold-Chat.dc.html"):
    needs = state == "needs-you"
    meta = []
    if ts:
        meta.append(f'<span style="font-family: {MONO}; font-weight: {600 if unread else 500}; font-size: 11px; line-height: 1; color: {"#0b1117" if unread else "#626e7d"}">{ts}</span>')
    if state:
        meta.append(m_row_state(state, phases))
    meta_html = f'<span style="display: flex; flex-direction: column; align-items: flex-end; gap: 4px; flex-shrink: 0">{"".join(meta)}</span>' if meta else ""
    if compact:
        weight = 600 if (unread or needs) else (500 if selected else 400)
        ink = "#0b1117" if (unread or selected or needs) else "#3d4955"
        return (f'<a href="{href}" style="display: flex; align-items: center; gap: 12px; min-height: 44px; margin: 0 12px; padding: 6px 10px; border-radius: 10px; box-sizing: border-box; '
                f'background: {"rgba(11,17,23,0.06)" if selected else "transparent"}; text-decoration: none; color: inherit; opacity: {0.55 if dim else 1}">'
                f'<span style="width: 24px; display: inline-flex; justify-content: center">{m_glyph(kind, color)}</span>'
                f'<span style="flex: 1; min-width: 0; font-size: 14px; font-weight: {weight}; line-height: 18.2px; color: {ink}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis">{name}</span>{meta_html}</a>')
    weight = 700 if (unread or needs) else 600
    preview = PREVIEWS.get(name, "3 members · hub @doc")
    return (f'<a href="Phone-Chat.dc.html" style="display: flex; align-items: center; gap: 12px; min-height: 64px; padding: 12px 16px; box-sizing: border-box; text-decoration: none; color: inherit; opacity: {0.55 if dim else 1}">'
            f'<span style="width: 24px; display: inline-flex; justify-content: center">{m_glyph(kind, color)}</span>'
            f'<span style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px"><span style="font-size: 15px; font-weight: {weight}; line-height: 19.5px; color: #0b1117">{name}</span>'
            f'<span style="font-size: 14px; line-height: 18.2px; color: #626e7d; white-space: nowrap; overflow: hidden; text-overflow: ellipsis">{preview}</span></span>{meta_html}</a>')


def m_roster_label(label, add=True, gutter=12):
    plus = f'<button aria-label="New {label.lower()[:-1]}" class="m-chrome" style="width: 28px; height: 28px; margin: -6px 0">{ic("plus", 14, "#626e7d")}</button>' if add else ""
    return f'<div style="display: flex; align-items: center; gap: 8px; padding: 12px {gutter}px 6px">{m_eyebrow(label, "#626e7d", 500, 0.06, 11, "flex: 1")}{plus}</div>'


def m_roster(selected="doc", compact=True, wg_selected=False):
    sep = "" if compact else '<div style="height: 0.5px; background: rgba(11,17,23,0.07); margin-left: 52px"></div>'
    gutter = 12 if compact else 16

    def prow(name, col, ts):
        state, phases = M_STATES.get(name, (None, None))
        return m_roster_row(name, col, ts=ts, state=state, phases=phases, selected=compact and name == selected, unread=name == "yuri", compact=compact, dim=name == "etxea")

    pinned = sep.join(prow(n, c, t) for n, c, t, _ in PROFILES if n in M_PINNED)
    rows = sep.join(prow(n, c, t) for n, c, t, _ in PROFILES if n not in M_PINNED)
    wgs = sep.join((m_roster_row("alpha", DOC_ACCENT, "workgroup", state="working", phases="2/4", selected=wg_selected, compact=compact),
                    m_roster_row("launch-crew", "#f0b447", "workgroup", ts="2h", compact=compact)))
    return (f'{m_roster_label("Pinned", False, gutter)}{pinned}{m_roster_label("Profiles", True, gutter)}{rows}{m_roster_label("Workgroups", True, gutter)}{wgs}')


def m_conn_header(ring="#f5f6f8", collapse=True, bg="#f5f6f8", selected=False):
    dot = f'<span style="position: absolute; top: 6px; right: 6px; width: 8px; height: 8px; border-radius: 4px; background: #e08a3c; border: 1.5px solid {ring}; box-sizing: border-box"></span>'
    hide = f'<button aria-label="Hide sidebar" class="m-chrome">{ic("panel", 16, "#3d4955")}</button>' if collapse else ""
    return f"""<div style="padding: 6px 12px 8px; background: {bg}; display: flex; flex-direction: column; gap: 4px">
<div style="display: flex; align-items: center">{m_eyebrow("Connection", "#626e7d", 500, 0.06, 11, "flex: 1")}{hide}<button aria-label="Activity · 2 need you" class="m-chrome" style="position: relative">{ic("activity", 16, WARNING_TEXT)}{dot}</button><button aria-label="Filter profiles and workgroups" class="m-chrome">{ic("search", 16, "#3d4955")}</button></div>
<div style="padding: 6px 12px; border-radius: 12px; border: 0.5px solid rgba(11,17,23,0.07); background: {"rgba(11,17,23,0.06)" if selected else "#ffffff"}; display: flex; align-items: center; gap: 10px">
<span style="position: relative">{ic("chip", 16, "#3d4955")}<span style="position: absolute; right: -2px; bottom: -2px; width: 8px; height: 8px; border-radius: 4px; background: #3fb37a; border: 2px solid #fff; box-sizing: border-box"></span></span>
<div style="flex: 1; min-width: 0; display: flex; flex-direction: column"><span style="font-weight: 600; font-size: 14px; line-height: 1.3">casa</span><span style="font-family: {MONO}; font-size: 11px; line-height: 1.3; color: #626e7d">ws://100.99.29.84:49200</span></div>
{ic("chev-d", 12, "#626e7d")}
</div>
</div>"""


def m_shell_footer(version="v0.6.0", theme=True, ring="#f5f6f8", border=False):
    entry = lambda inner, label: f'<span aria-label="{label}" style="display: inline-flex; align-items: center; gap: 6px; min-height: 36px; padding: 0 8px; border-radius: 10px">{inner}</span>'
    top = "border-top: 0.5px solid rgba(11,17,23,0.07);" if border else ""
    theme_html = entry(ic("sun", 16, "#3d4955"), "Theme: Light") if theme else ""
    wrap = '<span style="position: relative; display: inline-flex">'
    bell = wrap + ic("bell", 16, "#3d4955") + m_count_badge(1, "danger", ring) + "</span>"
    activity = wrap + ic("activity", 16, WARNING_TEXT) + m_count_badge(2, "warning", ring) + "</span>"
    return (f'<div style="height: 44px; padding: 0 12px; display: flex; align-items: center; gap: 6px; {top}">'
            f'<a href="Phone-Settings.dc.html" style="display: inline-flex; align-items: center; gap: 6px; min-height: 36px; padding: 0 8px; border-radius: 10px; text-decoration: none; color: #3d4955; font-weight: 500; font-size: 12px">{ic("gear", 16, "#3d4955")}Settings</a>'
            f'{entry(bell, "Notifications · 1 unread")}{entry(activity, "Activity · 2 need you")}'
            f'{theme_html}<span style="flex: 1"></span><span style="font-family: {MONO}; font-weight: 500; font-size: 11px; color: #b1bac4">{version}</span></div>')


def m_sidebar(h, selected="doc", badge="1", version="v0.6.0", conn_selected=False, wg_selected=False):
    return f"""<div style="width: 280px; height: {h}px; flex-shrink: 0; box-sizing: border-box; background: #f5f6f8; border-right: 0.5px solid rgba(11,17,23,0.07); display: flex; flex-direction: column">
{m_conn_header(selected=conn_selected)}
<div style="flex: 1; min-height: 0; overflow: hidden; display: flex; flex-direction: column">{m_roster(selected, True, wg_selected)}</div>
{m_shell_footer(version)}
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
    from conversation_boards import m_agent_text, m_process, m_reasoning, m_tool, m_user
    return f"""<div style="flex: 1; min-height: 0; overflow: hidden; display: flex; flex-direction: column; justify-content: flex-end; gap: 10px; padding-bottom: 12px">
{m_user("Pull my last three lipid panels and tell me what moved.", accent, pane)}
{m_process(m_reasoning(secs="4s"), m_tool("memory", "lipid panels · 3 results"), m_tool("read_file", "labs/2026-08-lipids.pdf"))}
{m_agent_text("Triglycerides moved most: <strong>142 → 88 mg/dL</strong> since March. LDL-P eased to 1,180 nmol/L; HDL held at 68.")}
</div>"""


def m_composer(name="doc"):
    from conversation_boards import m_composer as composer
    return composer(name=name, chip="deepseek-v4.1-flash · medium", accent=DOC_ACCENT)


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
<div style="flex: 1; min-height: 0; display: flex; flex-direction: column; max-width: 720px; width: 100%; align-self: center; box-sizing: border-box">{m_thread(DOC_ACCENT, pane=True)}</div>
<div style="max-width: 720px; width: 100%; align-self: center; box-sizing: border-box">{m_composer()}</div>
</div>
</div>
"""
    return page("Fold · chat, two panes", 852, 884, body)


def m_activity_row(icon, title, sub, tone="quiet", action=""):
    tint = {"warning": WARNING_TEXT, "accent": ALPI_ACCENT, "danger": DANGER, "quiet": "#626e7d"}[tone]
    btn = f'<span style="padding: 6px 12px; border-radius: 10px; background: #0b1117; color: #ffffff; font-weight: 600; font-size: 12px">{action}</span>' if action else ""
    return (f'<div role="button" style="display: flex; align-items: center; gap: 12px; min-height: 56px; padding: 8px 16px; box-sizing: border-box">{ic(icon, 16, tint)}'
            f'<div style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px"><span style="font-weight: 500; font-size: 15px; line-height: 19.5px; color: #0b1117">{title}</span>'
            f'<span style="font-family: {MONO}; font-size: 12px; line-height: 15.6px; color: {tint if tone == "danger" else "#626e7d"}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis">{sub}</span></div>{btn}</div>')


def m_activity_list():
    group = lambda label, rows, color="#626e7d": f'<div role="list"><div style="padding: 16px 16px 6px">{m_eyebrow(label, color)}</div>{"".join(rows)}</div>'
    return (group("Needs you · 2", [m_activity_row("alert", "abby · wants to run a command", "approval · 2m ago", "warning", "Review"),
                                    m_activity_row("alert", "doc · Which lab should I book?", "question · 12s ago", "warning", "Review")], WARNING_TEXT)
            + group("Running · 2", [m_activity_row("activity", "alpha · #collect", "phase 2 of 4 · daily-digest", "accent"),
                                    m_activity_row("activity", "alpi · Summarize yesterday’s deploys", "4m · chat", "accent")])
            + group("Scheduled", [m_activity_row("x", "clonara · weekly labs", "failed 3h ago", "danger"),
                                  m_activity_row("clock", "doc · Daily brief", "in 14h")]))


def phone_activity():
    body = f"""<div style="display: flex; flex-direction: column">
{m_screen_header("Activity", "WHAT IS RUNNING", glyph="")}
{m_activity_list()}
</div>
"""
    return page("Phone · activity", 390, PHONE_ACTIVITY_H, body)


def fold_activity():
    body = f"""<div style="display: flex; height: 100%">
{m_sidebar(FOLD_ACTIVITY_H, selected="")}
<div style="flex: 1; min-width: 0; display: flex; flex-direction: column; background: #ffffff">
{m_screen_header("Activity", "WHAT IS RUNNING", glyph="", wide=True, back=False)}
<div style="max-width: 720px; width: 100%; align-self: center">{m_activity_list()}</div>
</div>
</div>
"""
    return page("Fold · activity", 852, FOLD_ACTIVITY_H, body)


def phone_roster():
    body = f"""<div style="display: flex; flex-direction: column; height: 100%; background: #ffffff">
{m_conn_header(ring="#ffffff", collapse=False, bg="#ffffff")}
<div style="height: 0.5px; background: rgba(11,17,23,0.07)"></div>
<div style="flex: 1; min-height: 0; overflow: hidden">{m_roster(compact=False)}</div>
{m_shell_footer(theme=False, ring="#ffffff", border=True)}
</div>
"""
    return page("Phone · roster", 390, 844, body)


PHONE_ACTIVITY_H = 540
FOLD_ACTIVITY_H = 700


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
{m_sidebar(1300, selected="", wg_selected=True)}
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
.m-chrome{width:36px;height:36px;border:0;border-radius:10px;background:transparent;display:inline-flex;align-items:center;justify-content:center;padding:0;cursor:pointer;color:#3d4955}
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
    from desktop_overlays import OVERLAYS_H, desktop_overlays
    from mobile_overlays import MOBILE_OVERLAYS
    from system_boards import DESKTOP_COMPONENTS_H, MOBILE_COMPONENTS_H, SYSTEM, TOKENS_H

    from conversation_boards import CONVERSATION

    y = 0
    for label, items in (
        ("Foundations", [("System-Tokens.dc.html", SYSTEM["tokens"](), TOKENS_H, "System · tokens"), ("System-Motion.dc.html", SYSTEM["motion"](), 900, "System · motion and feel")]),
        ("Controls and feedback", [("System-DesktopComponents.dc.html", SYSTEM["desktop"](), DESKTOP_COMPONENTS_H, "Desktop · controls and feedback"), ("System-MobileComponents.dc.html", SYSTEM["mobile"](), MOBILE_COMPONENTS_H, "Mobile · controls and feedback")]),
        ("Conversation", [("System-DesktopConversation.dc.html", CONVERSATION["desktop"](), 2900, "Desktop · conversation"), ("System-MobileConversation.dc.html", CONVERSATION["mobile"](), 1400, "Mobile · conversation")]),
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
        ("Desktop-ProfileSettings.dc.html", desktop_boards["profile"], 2400, "Profile settings"),
        ("Desktop-WorkgroupSettings.dc.html", desktop_boards["wg"], 1760, "Workgroup settings"),
        ("Desktop-Connections.dc.html", desktop_boards["connections"], 820, "Connections"),
        ("Desktop-AppSettings.dc.html", desktop_boards["app"], 740, "App settings"),
        ("Desktop-Overlays.dc.html", desktop_overlays(), OVERLAYS_H, "Overlays"),
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
        ("Activity", [("Fold-Activity.dc.html", fold_activity(), X_FOLD, 852, FOLD_ACTIVITY_H, "Fold · activity"), ("Phone-Roster.dc.html", phone_roster(), X_PHONE, 390, 844, "Phone · roster"), ("Phone-Activity.dc.html", phone_activity(), X_PHONE + 470, 390, PHONE_ACTIVITY_H, "Phone · activity")]),
        ("Overlays", [("Fold-Sheet.dc.html", MOBILE_OVERLAYS["fold_sheet"](), X_FOLD, 852, 884, "Fold · sheet as a centred dialog"), ("Phone-Sheet.dc.html", MOBILE_OVERLAYS["phone_sheet"](), X_PHONE, 390, 844, "Phone · sheet"), ("Phone-ActionSheet.dc.html", MOBILE_OVERLAYS["phone_action"](), X_PHONE + 470, 390, 844, "Phone · action sheet"), ("Phone-TypedConfirm.dc.html", MOBILE_OVERLAYS["phone_confirm"](), X_PHONE + 940, 390, 844, "Phone · typed confirm")]),
        ("Sheets", [("Phone-ToolSheet.dc.html", MOBILE_OVERLAYS["phone_tool"](), X_PHONE, 390, 844, "Phone · tool step sheet"), ("Phone-SelectText.dc.html", MOBILE_OVERLAYS["phone_select"](), X_PHONE + 470, 390, 844, "Phone · select text"), ("Phone-MessageActions.dc.html", MOBILE_OVERLAYS["phone_message"](), X_PHONE + 940, 390, 844, "Phone · message actions")]),
    )
    for label, items in rows:
        y += 240
        title(f"m-{label}", label, y - 223, "mobile")
        for name, html, x, w, h, t in items:
            place(name, html, x, y, w, h, t, "mobile")
        y += max(h for _, _, _, _, h, _ in items)

    place("Main.dc.html", audit2_board(), 0, 0, 1280, 140 + 90 * 6 + 120, "Open work", "audit")

    from proposals_boards import PROPOSAL_BOARDS
    y = 0
    for name, fn, h, t in PROPOSAL_BOARDS:
        y += 240
        title(f"p-{t}", t, y - 223, "proposals")
        place(name, fn(), 0, y, 1280, h, f"Proposals · {t.lower()}", "proposals")
        y += h

    live_path = os.path.join(os.path.dirname(ROOT), "live", "project", "canvas.json")
    index = {
        "v": 3,
        "createdOnFiles": {"v": 1, "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")},
        "title": "Alpi desktop and mobile parity",
        "launch": {"view": "canvas", "page": "system"},
        "pages": [{"id": "system", "name": "System"}, {"id": "desktop", "name": "Desktop"}, {"id": "mobile", "name": "Mobile"}, {"id": "audit", "name": "Open work"}, {"id": "proposals", "name": "Proposals"}],
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
