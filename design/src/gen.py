import re
import json
import os
import subprocess
from datetime import datetime, timezone

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "project")
os.makedirs(ROOT, exist_ok=True)

FONT_LINK = '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700&amp;family=Geist+Mono:wght@400;500;600&amp;display=swap">'

DOC_ACCENT = "#3899e2"
UPDATE_STEP = "Set the image tag to 0.16.19 in docker-compose.yml, then docker compose up -d."
ALPI_ACCENT = "#14110c"
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


COMMON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "common")
DESIGN_TO_SHARED = {
    "back": "chevron-left", "chev-d": "chevron-down", "chev-r": "chevron-right", "chip": "cpu", "clip": "paperclip",
    "gear": "settings", "more": "ellipsis", "panel": "panel-left", "refresh": "refresh-cw", "trash": "trash-2",
    "up": "arrow-up", "volume": "volume-2", "alert": "triangle-alert",
}


def _load_shared():
    script = (
        "const [{ICONS}, {ICON_ROLES}] = await Promise.all(["
        f"import({json.dumps(os.path.join(COMMON, 'iconPaths.mjs'))}), import({json.dumps(os.path.join(COMMON, 'iconRoles.mjs'))})]);"
        "process.stdout.write(JSON.stringify({icons: ICONS, roles: ICON_ROLES}));"
    )
    try:
        out = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True, check=True)
    except FileNotFoundError:
        raise SystemExit("design/build.py needs node on PATH to read the shared icons in common/")
    return json.loads(out.stdout)


_SHARED = _load_shared()
SHARED_ICONS, ICON_ROLES = _SHARED["icons"], _SHARED["roles"]


def _svg_children(elements):
    return "".join("<" + tag + "".join(f' {k}="{v}"' for k, v in attrs.items()) + "/>" for tag, attrs in elements)


def ic(name, size=16, color="currentColor", stroke=2):
    if name.startswith("role:"):
        return role_ic(name[5:], size, color, stroke)
    shared = SHARED_ICONS.get(DESIGN_TO_SHARED.get(name, name))
    inner = _svg_children(shared) if shared else PATHS[name]
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" '
        f'stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" '
        f'data-icon="{DESIGN_TO_SHARED.get(name, name)}" style="flex-shrink: 0; display: block">{inner}</svg>'
    )


def role_ic(role, size=16, color="currentColor", stroke=2):
    return ic(ICON_ROLES[role], size, color, stroke).replace("<svg ", f'<svg data-icon-role="{role}" ', 1)


LIGHT_ACCENT = "#14110c"
THEMED_ACCENT = "#8a5a0a"
FOLD_OF = {"alpi": "alpaca", "doc": "shield", "abby": "plane", "galt": "box", "lingo": "star"}


def identity_glyph(name, color, px=16, legacy=None):
    import folds
    shape = FOLD_OF.get(name)
    if shape == "alpaca":
        big = round(px * 1.3)
        themed = folds.fold(shape, LIGHT_ACCENT, big, facet_attrs=lambda i, n, tone: f' style="fill: {THEMED_ACCENT}"')
        return f'<span style="width: {px}px; height: {px}px; display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0">{themed}</span>'
    if shape:
        return folds.fold(shape, color, px)
    return folds.fold("diamond", color, px)


def profile_mark(color, px=16):
    import folds
    return folds.fold("diamond", color, px)


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
<link rel="icon" href="../../favicon.svg" type="image/svg+xml">
<script src="./support.js"></script>
{FONT_LINK}
<link rel="stylesheet" href="parity.css">
</head>
<body>
<x-dc>
<helmet>
{FONT_LINK}
<style>
body{{margin:0;background:{bg};font-family:"Geist",ui-sans-serif,system-ui,sans-serif;color:#141414}}
a{{color:#14110c}}a:hover{{color:#3b362d}}
</style>
</helmet>
<div style="position: relative; width: {w}px; height: {h}px; box-sizing: border-box; overflow: hidden; background: {bg}; font-family: Geist, ui-sans-serif, system-ui, sans-serif; color: #141414">
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



def m_eyebrow(text, color="#6b6b6b", weight=500, track=0.06, size=11, extra=""):
    return (
        f'<span style="font-family: {MONO}; font-weight: {weight}; font-size: {size}px; '
        f'line-height: 1.3; letter-spacing: {track}em; text-transform: uppercase; color: {color}; {extra}">{text}</span>'
    )


def m_meta_strip(items, gap=14):
    parts = []
    for i, it in enumerate(items):
        if i > 0:
            parts.append('<span style="width: 1px; height: 10px; background: rgba(20,20,20,0.14); display: inline-block"></span>')
        parts.append(it)
    return f'<div style="display: flex; align-items: center; gap: {gap}px; white-space: nowrap; overflow: hidden">{"".join(parts)}</div>'


def _wg_mark(color, size):
    from desktop_boards import wg_mark
    return wg_mark(color, size)


def m_screen_header(title, subtitle, accent=DOC_ACCENT, glyph=None, back=True, wide=False, right="", sidebar_toggle=False, meta=None, creased=False):
    from brand_boards import app_crease
    title_html = app_crease(title, 28, accent, "#ffffff", track="-0.018em") if creased else f'<span style="font-weight: 600; font-size: 18px; line-height: 1.3; white-space: nowrap; overflow: hidden; text-overflow: ellipsis">{title}</span>'
    padx = 24 if wide else 20
    padt = 12 if wide else 8
    parts = []
    if sidebar_toggle:
        parts.append(f'<button aria-label="Show sidebar" class="m-chrome" style="margin-left: -6px">{ic("panel", 20, "#454545")}</button>')
    if back and not wide:
        parts.append(f'<button aria-label="Back" class="m-chrome" style="width: 28px; height: 36px; margin-left: -6px">{ic("back", 20, "#454545")}</button>')
    g = glyph if glyph is not None else profile_mark(accent, 20)
    if wide:
        sub = f'<span style="font-family: {MONO}; font-size: 11px; line-height: 1.3; letter-spacing: 0.06em; color: #6b6b6b; margin-top: 4px">{subtitle}</span>'
        title_row = f'<div style="display: flex; align-items: center; gap: 10px">{g}{title_html}{sub}</div>'
        meta_row = f'<div style="margin-top: 8px">{m_meta_strip(meta)}</div>' if meta else ""
        back_btn = f'<button aria-label="Back" class="m-chrome">{ic("arrow-left", 16, "#454545")}</button>' if back else ""
        return f"""<div style="position: relative; display: flex; align-items: flex-start; gap: 10px; padding: {padt}px {padx}px 12px; background: #ffffff; border-bottom: 0.5px solid rgba(20,20,20,0.07)">
{''.join(parts)}
<div style="flex: 1; min-width: 0; display: flex; flex-direction: column">{title_row}{meta_row}</div>
{right}{back_btn}
</div>"""
    return f"""<div style="position: relative; display: flex; align-items: center; gap: 10px; padding: {padt}px {padx}px 12px; background: #ffffff; border-bottom: 0.5px solid rgba(20,20,20,0.07)">
{''.join(parts)}
<div style="flex: 1; min-width: 0; display: flex; flex-direction: column">
<div style="display: flex; align-items: center; gap: 6px">{g}{title_html}</div>
{m_eyebrow(subtitle, "#6b6b6b", 400, 0.06, 11)}
</div>
{right}
</div>"""


def m_section(title, kicker="", first=False):
    k = f' · {kicker}' if kicker else ""
    return f'<div style="padding: {0 if first else 24}px 20px 8px">{m_eyebrow(title + k)}</div>'


def m_row(label, helper="", value="", chevron=True, control="", danger=False, sep=True, helper_lines=1):
    color = DANGER if danger else "#141414"
    val = f'<span style="font-size: 14px; color: #6b6b6b; text-align: right; max-width: 55%; white-space: nowrap; overflow: hidden; text-overflow: ellipsis">{value}</span>' if value else ""
    chev = ic("chev-r", 16, "#b4b4b4") if chevron and not danger else ""
    help_ = f'<span style="font-family: {MONO}; font-weight: 500; font-size: 11px; line-height: 1.3; color: #6b6b6b; {"white-space: nowrap; overflow: hidden; text-overflow: ellipsis" if helper_lines == 1 else ""}">{helper}</span>' if helper else ""
    sepd = '<div style="height: 0.5px; background: rgba(20,20,20,0.07); margin-left: 20px"></div>' if sep else ""
    return f"""<div style="display: flex; align-items: center; gap: 12px; padding: 14px 20px">
<div style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px"><span style="font-size: 15px; line-height: 1.3; color: {color}">{label}</span>{help_}</div>
{val}{control}{chev}
</div>{sepd}"""


GROUP_TONE = "rgba(20,20,20,0.04)"


def m_group(*rows):
    return f'<div style="margin: 0 12px; border-radius: 4px; overflow: hidden; background: {GROUP_TONE}">{"".join(rows)}</div>'


def m_band(inner):
    return f'<div style="padding: 16px 20px">{inner}</div>'


def pill(text, on=False, tone="off"):
    if tone == "success":
        return f'<span style="display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 2px; background: rgba(63,179,122,0.16); font-family: {MONO}; font-size: 12px; color: #217a45"><span style="width: 7px; height: 7px; border-radius: 999px; background: #217a45"></span>{text}</span>'
    if tone == "warning":
        return f'<span style="display: inline-flex; align-items: center; padding: 4px 10px; border-radius: 2px; background: rgba(224,138,60,0.16); font-family: {MONO}; font-size: 12px; color: #b3470e">{text}</span>'
    dot = "#217a45" if on else "#b4b4b4"
    return f'<span style="display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 2px; background: #f2f2f2; font-family: {MONO}; font-size: 12px; color: {"#217a45" if on else "#6b6b6b"}"><span style="width: 7px; height: 7px; border-radius: 999px; background: {dot}"></span>{"on" if on else "off"}</span>'


def m_wide_section(title, kicker="", first=False):
    k = f'<span style="font-size: 11px; color: #b4b4b4">{kicker}</span>' if kicker else ""
    return f'<div style="display: flex; align-items: baseline; gap: 10px; margin: {0 if first else 36}px 0 12px">{m_eyebrow(title, "#454545", 600, 0.1, 11)}{k}</div>'


def m_wide_row(label, helper="", value="", chevron=True, control="", danger=False, value_html="", item=False):
    color = DANGER if danger else "#6b6b6b"
    help_col = "#6b6b6b" if item else "#b4b4b4"
    help_ = f'<span style="font-family: {MONO}; font-size: 11px; line-height: 1.3; color: {help_col}; margin-top: 4px">{helper}</span>' if helper else ""
    lab = (f'<span style="font-weight: 600; font-size: 14px; line-height: 1.3; color: {DANGER if danger else "#141414"}">{label}</span>' if item
           else m_eyebrow(label, color))
    val = value_html or (f'<span style="font-family: {MONO}; font-size: 12px; color: #454545; text-align: right; white-space: nowrap; overflow: hidden; text-overflow: ellipsis">{value}</span>' if value else "")
    gutter = "" if danger else f'<span style="width: 14px; display: inline-flex; justify-content: flex-end">{ic("chev-r", 14, "#b4b4b4") if chevron else ""}</span>'
    return f"""<div style="display: flex; align-items: center; gap: 24px; min-height: 36px; padding: 8px 0">
<div style="flex: 1 1 148px; min-width: 0; display: flex; flex-direction: column">{lab}{help_}</div>
<div style="flex-shrink: 1; min-width: 0; max-width: 60%; display: flex; align-items: center; justify-content: flex-end; gap: 10px">{val}{control}{gutter}</div>
</div>"""


def switch(on=False, accent=DOC_ACCENT, label="", disabled=False):
    bg = accent if on else "rgba(20,20,20,0.14)"
    return (f'<button role="switch" aria-checked="{"true" if on else "false"}" aria-label="{label}" style="position: relative; width: 44px; height: 24px; border: 0; border-radius: 999px; '
            f'background: {bg}; opacity: {0.45 if disabled else 1}; padding: 0; cursor: pointer; flex-shrink: 0">'
            f'<span style="position: absolute; top: 3px; left: {23 if on else 3}px; width: 18px; height: 18px; border-radius: 999px; background: #ffffff; box-shadow: 0 1px 2px rgba(20,20,20,0.2)"></span></button>')


def textbox(text, rows=3, placeholder=False):
    color = "#6b6b6b" if placeholder else "#141414"
    return (f'<div style="min-height: {rows * 22 + 24}px; padding: 12px; border-radius: 4px; background: #f2f2f2; '
            f'font-size: 15px; line-height: 1.5; color: {color}">{text}</div>')




def app_version(client):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", client, "package.json")
    with open(path) as f:
        return json.load(f)["version"]

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
        bg, fg, fw = (accent or "#141414"), "#ffffff", 600
    elif variant == "danger":
        bg, fg, fw = "#c14545", "#fffffe", 600
    elif variant == "ghost":
        bg, fg, fw = "transparent", "#454545", 500
    elif variant == "danger-ghost":
        bg, fg, fw = "transparent", DANGER, 500
    else:
        bg, fg, fw = "rgba(20,20,20,0.06)", "#141414", 600
    return (
        f'<button style="min-height: {h}px; padding: 6px {padx}px; border: 0; border-radius: 4px; background: {bg}; '
        f'color: {fg}; font-family: Geist, sans-serif; font-weight: {fw}; font-size: {fs}px; cursor: pointer">{title}</button>'
    )


def meter(value, tail, pct, color=DOC_ACCENT, percent=True):
    p = f'<span style="font-family: {MONO}; font-size: 11px; color: #6b6b6b">{round(pct * 100)}%</span>' if percent else ""
    return f"""<span style="display: inline-flex; align-items: center; gap: 8px"><span style="font-family: 'Geist Mono', monospace; font-size: 11px; color: #454545">{value}<span style="color: #6b6b6b">{tail}</span></span><span role="progressbar" aria-label="{value}{tail}" style="width: 56px; height: 5px; border-radius: 999px; background: rgba(20,20,20,0.14); overflow: hidden; display: inline-block"><span style="display: block; width: {pct * 100}%; height: 100%; background: {color}"></span></span>{p}</span>"""


DAYS = [("W", 0.22, 0.02), ("T", 0.30, 0.02), ("F", 0.10, 0.01), ("S", 0.24, 0.02), ("S", 0.78, 0.05), ("M", 0.14, 0.01),
        ("T", 0.20, 0.02), ("W", 0.20, 0.02), ("T", 0.08, 0.01), ("F", 0.18, 0.02), ("S", 0.12, 0.01), ("S", 1.0, 0.06),
        ("M", 0.34, 0.03), ("T", 0.16, 0.02)]


def usage_chart(accent=DOC_ACCENT, today="$0.00", tin="102K", tout="831", cap="$1.00", left="100% left",
                footer="30-day total $1.61 · 17.2M in / 277K out", days=DAYS, mobile=True, empty=False, ground=None, narrow=False):
    in_col = mix(accent, 0.24) if ground is None else mix(accent, 0.24, ground)
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
            bar = (f'<div style="width: 100%; max-width: 26px; padding: 1.5px; border-radius: 4px; border: 1.5px solid {accent}; '
                   f'background: {ground or "#ffffff"}; display: flex; justify-content: center; box-sizing: border-box">{bar}</div>')
        bars.append(f'<div style="flex: 1; height: 100%; display: flex; justify-content: flex-end; align-items: center; flex-direction: column">{bar}</div>')
        labels.append(f'<span style="flex: 1; text-align: center; font-family: {MONO}; font-weight: {600 if last else 400}; font-size: 9px; line-height: 1; color: {accent if last else "#6b6b6b"}">{d}</span>')
    track = (f'<div style="margin-top: 20px; display: flex; flex-direction: column">'
             f'<div style="height: 104px; display: flex; align-items: flex-end; gap: 4px">{"".join(bars)}</div>'
             f'<div style="display: flex; gap: 4px; margin-top: 8px">{"".join(labels)}</div></div>'
             f'<div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; margin-top: 14px">'
             f'<span style="display: inline-flex; align-items: center; gap: 6px; font-size: 11px; color: #6b6b6b"><span style="width: 9px; height: 9px; border-radius: 2px; background: {in_col}"></span>input <span style="color: #b4b4b4">·</span> <span style="width: 9px; height: 9px; border-radius: 2px; background: {accent}"></span>output</span>'
             f'<span style="font-family: {MONO}; font-size: 11px; color: #6b6b6b">{footer}</span></div>')
    empty_line = f'<span style="font-family: {MONO}; font-size: 11px; color: #b4b4b4; margin-top: 14px">No usage in the last {n} days</span>'
    tile = lambda label, body: f'<div style="flex: 1; min-width: 0; display: flex; flex-direction: column">{m_eyebrow(label, "#6b6b6b", 400, 0.1, 11, "margin-bottom: 6px")}{body}</div>'
    def mono(v, u):
        unit = f'<span style="font-weight: 400; font-size: 11px; color: #6b6b6b"> {u}</span>' if u else ""
        return f'<span style="font-family: {MONO}; font-weight: 500; font-size: 18px; line-height: 1; color: #141414">{v}{unit}</span>'
    return f"""<div style="display: flex; flex-direction: column">
<div style="display: flex; align-items: flex-start; padding-bottom: 14px; border-bottom: 0.5px solid rgba(20,20,20,0.14)">
{tile("Today", f'<span style="font-weight: 600; font-size: 28px; line-height: 1; letter-spacing: -0.018em; color: {accent}">{today}</span>')}
{tile("Input", mono(tin, None if narrow else "tok"))}
{tile("Output", mono(tout, None if narrow else "tok"))}
{tile(("Cap · " + left if narrow else "Cap / day") if cap else "Avg / day", mono(cap or "$0.00", None if narrow else left))}
</div>
{empty_line if empty else track}
</div>"""


def mix(color, amount, over="var(--bg-pane, #ffffff)"):
    return f"color-mix(in srgb, {color} {round(amount * 100)}%, {over})"



PROFILES = [("doc", DOC_ACCENT, "6w", True), ("alpi", "#f0b447", "", False), ("abby", "#df4b9d", "", False),
            ("clonara", "#f05940", "", False), ("galt", "#3ac9f3", "", False), ("lingo", "#9b5ad9", "", False),
            ("yuri", "#f36a8a", "6w", False), ("etxea", "#3ec173", "", False)]

WARNING_TEXT = "#b3470e"
M_STATES = {"alpi": ("working", None), "abby": ("needs-you", None), "clonara": ("failed", None)}
M_STATE_TEXT = {"needs-you": "needs you", "failed": "failed", "working": "working"}
M_PINNED = ("doc",)
FRONT = "alpi"
PREVIEWS = {"doc": "Triglycerides moved most: 142 → 88 mg/dL", "alpi": "Summarizing yesterday’s deploys…", "abby": "Wants to send the invoice reminder",
            "clonara": "weekly labs failed · timeout", "galt": "Filed the Q3 receipts", "lingo": "Ready for today’s Basque drill?", "yuri": "Translation of the letter is in",
            "etxea": "needs provider — tap to set up"}


def m_row_state(state, phases=None, profile=None):
    color = mix(profile, 0.5, "#141414") if state == "working" and profile else {"needs-you": WARNING_TEXT, "failed": DANGER, "working": "#454545"}[state]
    font = f"font-family: {MONO}; font-weight: 500;" if phases else "font-weight: 500;"
    dot = "" if state == "working" else f'<span style="width: 6px; height: 6px; border-radius: 999px; background: {color}"></span>'
    return (f'<span data-state="{state}" style="display: inline-flex; align-items: center; gap: 6px; white-space: nowrap">'
            f'{dot}'
            f'<span style="{font} font-size: 11px; line-height: 14.3px; color: {color}">{phases or M_STATE_TEXT[state]}</span></span>')


def m_count_badge(n, tone="danger", ring="#f6f6f6"):
    bg = "#e08a3c" if tone == "warning" else "#c14545"
    fg = "#141414" if tone == "warning" else "#ffffff"
    return (f'<span style="position: absolute; top: -12px; right: -8px; min-width: 18px; height: 18px; padding: 0 4px; border-radius: 999px; border: 1.5px solid {ring}; background: {bg}; '
            f'color: {fg}; font-weight: 600; font-size: 11px; line-height: 15px; text-align: center; box-sizing: border-box; white-space: nowrap">{n}</span>')


def m_glyph(kind, color, name=""):
    if kind == "workgroup":
        from desktop_boards import wg_mark
        return wg_mark(color, 16)
    return identity_glyph(name, color, 16)


def m_roster_row(name, color, kind="profile", ts="", state=None, phases=None, selected=False, unread=False, compact=True, dim=False, href="Fold-Chat.dc.html"):
    needs = state == "needs-you"
    meta = []
    if ts:
        meta.append(f'<span style="font-family: {MONO}; font-weight: {600 if unread else 500}; font-size: 11px; line-height: 1; color: {"#141414" if unread else "#6b6b6b"}">{ts}</span>')
    if state:
        meta.append(m_row_state(state, phases, color))
    meta_html = f'<span style="display: flex; flex-direction: column; align-items: flex-end; gap: 4px; flex-shrink: 0">{"".join(meta)}</span>' if meta else ""
    if compact:
        weight = 600 if (unread or needs) else (500 if selected else 400)
        ink = "#141414" if (unread or selected or needs) else "#454545"
        return (f'<a href="{href}" style="display: flex; align-items: center; gap: 12px; min-height: 44px; {"margin: 0; padding: 6px 22px; border-radius: 0;" if selected else "margin: 0 12px; padding: 6px 10px; border-radius: 4px;"} box-sizing: border-box; '
                f'background: {"#ffffff" if selected else "transparent"}; text-decoration: none; color: inherit; opacity: {0.55 if dim else 1}">'
                f'<span style="width: 24px; display: inline-flex; justify-content: center">{m_glyph(kind, color, name)}</span>'
                f'<span style="flex: 1; min-width: 0; font-size: 14px; font-weight: {weight}; line-height: 18.2px; color: {ink}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis">{name}</span>{meta_html}</a>')
    weight = 700 if (unread or needs) else 600
    preview = PREVIEWS.get(name, "3 members · hub @doc")
    return (f'<a href="Phone-Chat.dc.html" style="display: flex; align-items: center; gap: 12px; min-height: 64px; padding: 12px 16px; box-sizing: border-box; text-decoration: none; color: inherit; opacity: {0.55 if dim else 1}">'
            f'<span style="width: 24px; display: inline-flex; justify-content: center">{m_glyph(kind, color, name)}</span>'
            f'<span style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px"><span style="font-size: 15px; font-weight: {weight}; line-height: 19.5px; color: #141414">{name}</span>'
            f'<span style="font-size: 14px; line-height: 18.2px; color: #6b6b6b; white-space: nowrap; overflow: hidden; text-overflow: ellipsis">{preview}</span></span>{meta_html}</a>')


def m_roster_label(label, add=True, gutter=12):
    plus = f'<button aria-label="New {label.lower()[:-1]}" class="m-chrome" style="width: 28px; height: 28px; margin: -6px 0">{ic("plus", 14, "#6b6b6b")}</button>' if add else ""
    return f'<div style="display: flex; align-items: center; gap: 8px; padding: 12px {gutter}px 6px">{m_eyebrow(label, "#6b6b6b", 500, 0.06, 11, "flex: 1")}{plus}</div>'


def m_roster(selected="doc", compact=True, wg_selected=False):
    sep = "" if compact else '<div style="height: 0.5px; background: rgba(20,20,20,0.07); margin-left: 52px"></div>'
    gutter = 12 if compact else 16

    def prow(name, col, ts):
        state, phases = M_STATES.get(name, (None, None))
        return m_roster_row(name, col, ts=ts, state=state, phases=phases, selected=compact and name == selected, unread=name == "yuri", compact=compact, dim=name == "etxea")

    front = "".join(prow(n, c, t) for n, c, t, _ in PROFILES if n == FRONT)
    seam = '<div style="height: 0.5px; background: rgba(20,20,20,0.14)"></div>'
    pinned = sep.join(prow(n, c, t) for n, c, t, _ in PROFILES if n in M_PINNED)
    rows = sep.join(prow(n, c, t) for n, c, t, _ in PROFILES if n not in M_PINNED and n != FRONT)
    wgs = sep.join((m_roster_row("alpha", DOC_ACCENT, "workgroup", state="working", phases="2/4", selected=wg_selected, compact=compact),
                    m_roster_row("launch-crew", "#f0b447", "workgroup", ts="2h", compact=compact)))
    return (f'{front}{seam}{m_roster_label("Pinned", False, gutter)}{pinned}{m_roster_label("Profiles", True, gutter)}{rows}{m_roster_label("Workgroups", True, gutter)}{wgs}')


def m_conn_header(ring="#f6f6f6", collapse=True, bg="#f6f6f6", selected=False):
    hide = f'<button aria-label="Hide sidebar" class="m-chrome">{ic("panel", 16, "#454545")}</button>' if collapse else ""
    return f"""<div style="padding: 6px 12px 8px; background: {bg}; display: flex; flex-direction: column; gap: 4px">
<div style="display: flex; align-items: center">{m_eyebrow("Connection", "#6b6b6b", 500, 0.06, 11, "flex: 1")}{hide}<button aria-label="Filter profiles and workgroups" class="m-chrome">{ic("search", 16, "#454545")}</button></div>
<div style="padding: 6px 12px; border-radius: 4px; border: 0.5px solid rgba(20,20,20,0.07); background: {"rgba(20,20,20,0.06)" if selected else "#ffffff"}; display: flex; align-items: center; gap: 10px">
<span style="position: relative">{ic("chip", 16, "#454545")}<span style="position: absolute; right: -2px; bottom: -2px; width: 8px; height: 8px; border-radius: 4px; background: #3fb37a; border: 2px solid #fff; box-sizing: border-box"></span></span>
<div style="flex: 1; min-width: 0; display: flex; flex-direction: column"><span style="font-weight: 600; font-size: 14px; line-height: 1.3">casa</span><span style="font-family: {MONO}; font-size: 11px; line-height: 1.3; color: #6b6b6b">ws://100.99.29.84:49200</span></div>
{ic("chev-d", 12, "#6b6b6b")}
</div>
</div>"""


def m_shell_footer(version=None, theme=True, ring="#f6f6f6", border=False):
    version = version or "v" + app_version("mobile")
    entry = lambda inner, label: f'<span aria-label="{label}" style="display: inline-flex; align-items: center; gap: 6px; min-height: 36px; padding: 0 8px; border-radius: 4px">{inner}</span>'
    top = "border-top: 0.5px solid rgba(20,20,20,0.07);" if border else ""
    theme_html = entry(ic("sun", 16, "#454545"), "Theme: Light") if theme else ""
    wrap = '<span style="position: relative; display: inline-flex">'
    bell = wrap + ic("role:notifications", 16, "#454545") + m_count_badge(1, "danger", ring) + "</span>"
    activity = wrap + ic("role:activity", 16, "#454545") + m_count_badge(2, "danger", ring) + "</span>"
    return (f'<div style="height: 44px; padding: 0 12px; display: flex; align-items: center; {top}">'
            f'<a href="Phone-Settings.dc.html" style="display: inline-flex; align-items: center; gap: 6px; min-height: 36px; padding: 0 8px; border-radius: 4px; text-decoration: none; color: #454545; font-weight: 500; font-size: 12px">{ic("role:settings", 16, "#454545")}Settings</a>'
            f'{entry(bell, "Notifications · 1 unread")}{entry(activity, "Activity · 2 need you")}'
            f'{theme_html}<span style="flex: 1"></span><span style="font-family: {MONO}; font-weight: 500; font-size: 11px; color: #b4b4b4">{version}</span></div>')


def m_sidebar(h, selected="doc", badge="1", version=None, conn_selected=False, wg_selected=False):
    version = version or "v" + app_version("mobile")
    return f"""<div style="width: 280px; height: {h}px; flex-shrink: 0; box-sizing: border-box; background: #f6f6f6; border-right: 0.5px solid rgba(20,20,20,0.07); display: flex; flex-direction: column">
{m_conn_header(selected=conn_selected)}
<div style="flex: 1; min-height: 0; overflow: hidden; display: flex; flex-direction: column">{m_roster(selected, True, wg_selected)}</div>
{m_shell_footer(version)}
</div>"""


def m_chat_header(title, accent, meta_html, two_pane=False, back=True, meta_items=None):
    from brand_boards import app_crease
    gap = 12 if two_pane else 6
    back_html = f'<button aria-label="Back" class="m-chrome" style="margin-left: -6px">{ic("back", 20, "#454545")}</button>' if back else ""
    return f"""<div style="position: relative; display: flex; align-items: flex-start; gap: 10px; padding: 6px 16px 8px; background: #ffffff; border-bottom: 0.5px solid rgba(20,20,20,0.07)">
{back_html}
<div style="flex: 1; min-width: 0; display: flex; flex-direction: column">
<div style="display: flex; align-items: center; gap: {gap}px">{identity_glyph(title, accent, 20, diamond(accent, 18))}<span style="flex: 1; min-width: 0; overflow: hidden">{app_crease(title, 28, accent, "#ffffff", track="-0.018em")}</span>
<span style="display: flex; align-items: center; flex-shrink: 0"><button aria-label="Sessions" class="m-chrome">{ic("history", 20, "#454545")}</button><button aria-label="More" class="m-chrome">{ic("more", 20, "#454545")}</button></span></div>
{m_meta_strip(meta_items, 14) if two_pane else f'<div style="display: flex; align-items: center; gap: 6px; margin-top: 1px; white-space: nowrap; overflow: hidden">{meta_html}</div>'}
</div>
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
    meta = (f'<span style="font-family: {MONO}; font-size: 11px; color: #454545">deepseek-v4.1-flash</span>'
            f'{meter("24K", "/1.0M", 0.024, DOC_ACCENT, False)}{meter("$0.00", "/$1.00", 0, DOC_ACCENT, False)}')
    body = f"""<div style="display: flex; flex-direction: column; height: 100%">
{m_chat_header("doc", DOC_ACCENT, meta)}
{m_thread(DOC_ACCENT)}
{m_composer()}
</div>
"""
    return page("Phone · chat", 390, 844, body)


def fold_chat():
    meta = (f'<span style="font-family: {MONO}; font-size: 11px; color: #454545">deepseek-v4.1-flash</span>'
            f'{meter("24K", "/1.0M", 0.024)}{meter("$0.00", "/$1.00", 0)}')
    items = [f'<span style="font-family: {MONO}; font-size: 11px; color: #454545">deepseek-v4.1-flash</span>',
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
    tint = {"warning": WARNING_TEXT, "accent": ALPI_ACCENT, "danger": DANGER, "quiet": "#6b6b6b"}[tone]
    lead = icon if icon.startswith("<") else ic(icon, 16, tint)
    btn = f'<span style="padding: 6px 12px; border-radius: 4px; background: #141414; color: #ffffff; font-weight: 600; font-size: 12px">{action}</span>' if action else ""
    return (f'<div role="button" style="display: flex; align-items: center; gap: 12px; min-height: 56px; padding: 8px 16px; box-sizing: border-box">{lead}'
            f'<div style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px"><span style="font-weight: 500; font-size: 15px; line-height: 19.5px; color: #141414">{title}</span>'
            f'<span style="font-family: {MONO}; font-size: 12px; line-height: 15.6px; color: {tint if tone in ("danger", "warning") else "#6b6b6b"}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis">{sub}</span></div>{btn}</div>')


def m_activity_list():
    import mobile_attention_studies as ms
    return ms.activity_list()


def phone_activity():
    body = f"""<div style="display: flex; flex-direction: column">
{m_screen_header("Activity", "ACROSS PROFILES", glyph="")}
{m_activity_list()}
</div>
"""
    return page("Phone · activity", 390, PHONE_ACTIVITY_H, body)


def fold_activity():
    body = f"""<div style="display: flex; height: 100%">
{m_sidebar(FOLD_ACTIVITY_H, selected="")}
<div style="flex: 1; min-width: 0; display: flex; flex-direction: column; background: #ffffff">
{m_screen_header("Activity", "ACROSS PROFILES", glyph="", wide=True, back=False)}
<div style="max-width: 720px; width: 100%; align-self: center">{m_activity_list()}</div>
</div>
</div>
"""
    return page("Fold · activity", 852, FOLD_ACTIVITY_H, body)


def phone_roster():
    body = f"""<div style="display: flex; flex-direction: column; height: 100%; background: #ffffff">
{m_conn_header(ring="#ffffff", collapse=False, bg="#ffffff")}
<div style="height: 0.5px; background: rgba(20,20,20,0.07)"></div>
{_ms().needs_band()}
<div style="flex: 1; min-height: 0; overflow: hidden">{m_roster(compact=False)}</div>
{m_shell_footer(theme=False, ring="#ffffff", border=True)}
</div>
"""
    return page("Phone · roster", 390, 844, body)


def phone_notifications():
    from notif_studies import VIEW, phone_triage
    body = f"""<div style="display: flex; flex-direction: column; height: 100%; background: #ffffff">
{m_screen_header("Notifications", "2 UNREAD", glyph="", right=m_button("Mark all read", "ghost", "md"))}
{phone_triage(VIEW)}
</div>
"""
    return page("Phone · notifications", 390, 844, body)


def phone_notification_page():
    from notif_studies import VIEW, phone_page_nav, phone_reader
    body = f"""<div style="display: flex; flex-direction: column; height: 100%; background: #ffffff">
{m_screen_header("", "", glyph="", right=phone_page_nav(VIEW))}
{phone_reader(VIEW)}
</div>
"""
    return page("Phone · notification", 390, 844, body)


PHONE_ACTIVITY_H = 880
FOLD_ACTIVITY_H = 900


PHONE_SETTINGS_H = 3640
FOLD_SETTINGS_H = 3330


def _ms():
    import mobile_attention_studies as ms
    return ms


def phone_profile_settings():
    body = f"""<div style="display: flex; flex-direction: column">
{m_screen_header("doc", "Profile · settings", creased=True)}
{_ms().settings_head_chips("Overview")}
{_ms().settings_summary()}
{m_section("Overview", first=False)}
{m_group(
    m_row("Paused", "paused profiles can't be chatted and sort last in new-chat", control=switch(False, DOC_ACCENT, "Paused"), chevron=False),
    m_row("Providers", "openrouter", "1"),
    m_row("Model", "", "deepseek-v4.1-flash"),
    m_row("Reasoning", "how hard the model thinks before answering", "default"),
    m_row("Fast model", "cheap model for side-tasks &amp; delegation", "main model"),
    m_row("Deep model", "stronger model for escalation &amp; deep research", "main model"),
    m_row("Vision model", "image inspection via read_image", "main model"),
    m_row("Budget", "daily spend cap", control=meter("$0.00", "/$1.00", 0)),
    m_row("Workspace", "", "/data/workspace/doc"),
    m_row("Appearance", "", control='<span style="display: inline-flex; align-items: center; gap: 8px">' + identity_glyph("doc", DOC_ACCENT, 16) + '<span style="font-size: 13px; color: #141414">blue shield</span><span style="font-family: ' + MONO + '; font-size: 12px; color: #454545">#3899e2</span></span>'),
    m_row("Home", "", "~/.alpi/profiles/doc", chevron=False, sep=False),
)}
{m_section("Usage", "last 14 days")}
{m_group(
    m_band(usage_chart(ground="transparent", narrow=True)),
)}
{m_section("Identity", "how peers see this agent")}
{m_group(
    m_row("Ancestral, lab-savvy personal doctor; food-first, skeptical of mainstream dogma", sep=False),
)}
{m_section("Service", "daemon")}
{m_group(
    m_row("Update alpi", "installs the newest alpi and restarts", control=m_button("Update"), chevron=False),
    m_row("Restart daemon", "exits the daemon · supervisor relaunches · reconnects automatically", control=m_button("Restart"), chevron=False),
)}
{m_section("Service", "daemon that cannot update itself")}
{m_group(
    m_row("Update alpi", UPDATE_STEP, chevron=False, helper_lines=2),
    m_row("Restart daemon", "exits the daemon · supervisor relaunches · reconnects automatically", control=m_button("Restart"), chevron=False),
    m_row("Email", "IMAP / Gmail accounts", control=pill("No accounts yet"), sep=False),
)}
{m_section("ALP", "peers + workgroups")}
{m_group(
    m_row("Public key", "tap to copy", "X+iAJ/6f…lNs=", chevron=False),
    m_row("Port", "ALP listener · set from alpi setup on the daemon's machine", "7423", chevron=False),
    m_row("Concurrency", "active workgroup pipelines at once", "unlimited"),
    m_row("Peers", "", "0"),
    m_row("Workgroups", "", "0", chevron=False, sep=False),
)}
{m_section("Schedule")}
{m_group(
    m_row("Cron jobs", "disable · fire · delete · add new", "4", sep=False),
)}
{m_section("Sandbox")}
{m_group(
    m_row("Terminal", "wraps shell tools in sandbox-exec / bubblewrap", control=switch(False, DOC_ACCENT, "Terminal sandbox"), chevron=False),
    m_row("Network", "enable terminal sandbox first", control=switch(False, DOC_ACCENT, "Sandbox network", disabled=True), chevron=False, sep=False),
)}
{m_section("Voice")}
{m_group(
    m_row("Voice", "", "Alvaro · Spanish (ES) · male"),
    m_row("Auto-read replies", "reads each agent reply aloud as it arrives — never your messages", control=switch(False, DOC_ACCENT, "Auto-read replies"), chevron=False, sep=False),
)}
{m_section("MCP Servers")}
{m_group(
    m_row("Manage", "add, remove, inspect tools", "0", sep=False),
)}
{m_section("Brain", "skills, memories, tools")}
{m_group(
    m_row("Skills", "instructions loaded on demand", "5"),
    m_row("Memories", "USER · MEMORY · AGENT", "3 files"),
    m_row("Tools", "native callable functions", "view", sep=False),
)}
{m_section("Storage", "disk footprint")}
{m_group(
    m_row("sessions", "42 files", "3.1 MB", chevron=False),
    m_row("skills", "18 files", "212 KB", chevron=False),
    m_row("memories", "3 files", "14 KB", chevron=False),
    m_row("knowledge", "1 file", "6.4 MB", chevron=False),
    m_row("Reclaim space", "caches, logs, old transcripts, index bloat", sep=False),
)}
{m_section("Danger zone")}
{m_group(
    m_row("Delete profile", "removes identity, memory, skills, schedule from disk. Cannot be undone.", danger=True, sep=False),
)}
</div>
"""
    return page("Phone · profile settings", 390, PHONE_SETTINGS_H, body)


def fold_profile_settings():
    inner = f"""<div style="max-width: 968px; padding: 8px 24px 40px; box-sizing: border-box; display: flex; flex-direction: column">
{_ms().settings_summary()}
{m_wide_section("Overview", first=False)}
{m_wide_row("Paused", "paused profiles can't be chatted and sort last in new-chat", control=switch(False, DOC_ACCENT, "Paused"), chevron=False)}
{m_wide_row("Providers", "API keys + local Ollama", control='<span style="display: inline-flex; align-items: center; padding: 4px 10px; border-radius: 2px; background: #f2f2f2; font-family: ' + MONO + '; font-size: 12px; color: #454545">openrouter</span>')}
{m_wide_row("Model", "", "deepseek-v4.1-flash")}
{m_wide_row("Reasoning", "how hard the model thinks before answering", "default")}
{m_wide_row("Fast model", "cheap model for side-tasks &amp; delegation", "main model")}
{m_wide_row("Deep model", "stronger model for escalation &amp; deep research", "main model")}
{m_wide_row("Vision model", "image inspection via read_image", "main model")}
{m_wide_row("Budget", "daily spend cap", control=meter("$0.00", "/$1.00", 0))}
{m_wide_row("Workspace", "", "/data/workspace/doc")}
{m_wide_row("Appearance", "", control='<span style="display: inline-flex; align-items: center; gap: 8px">' + identity_glyph("doc", DOC_ACCENT, 16) + '<span style="font-size: 13px; color: #141414">blue shield</span><span style="font-family: ' + MONO + '; font-size: 12px; color: #454545">#3899e2</span></span>')}
{m_wide_row("Home", "", "~/.alpi/profiles/doc", chevron=False)}
{m_wide_section("Usage", "last 14 days")}
{usage_chart()}
{m_wide_section("Identity", "how peers see this agent")}
<div style="display: flex; align-items: flex-start; gap: 24px; padding: 8px 0">
<div style="width: 148px; padding-top: 8px">{m_eyebrow("Identity", "#6b6b6b")}</div>
<div style="flex: 1; max-width: 520px; display: flex; flex-direction: column; gap: 8px">{textbox("Ancestral, lab-savvy personal doctor; food-first, skeptical of mainstream dogma")}<div style="display: flex; justify-content: flex-end">{m_button("Draft", "ghost")}</div></div>
</div>
{m_wide_section("Service", "daemon")}
{m_wide_row("Daemon", "update installs the newest alpi · restart exits and the supervisor relaunches", control='<span style="display: inline-flex; gap: 8px">' + m_button("Update alpi") + m_button("Restart daemon") + '</span>', chevron=False)}
{m_wide_section("Service", "daemon that cannot update itself")}
{m_wide_row("Daemon", UPDATE_STEP + " Restart exits and the supervisor relaunches.", control=m_button("Restart daemon"), chevron=False)}
{m_wide_row("Email", "IMAP / Gmail accounts", control=pill("No accounts yet"))}
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
{m_wide_section("Schedule")}
{m_wide_row("Cron jobs", "disable · fire · delete · add new", "4")}
{m_wide_section("MCP Servers")}
{m_wide_row("Manage", "add, remove, inspect tools", "0")}
{m_wide_section("Brain", "skills, memories, tools")}
{m_wide_row("Skills", "instructions loaded on demand", "5")}
{m_wide_row("Memories", "USER · MEMORY · AGENT", "3 files")}
{m_wide_row("Tools", "native callable functions", "view")}
{m_wide_section("Storage", "disk footprint")}
{m_wide_row("sessions", "42 files", "3.1 MB", chevron=False)}
{m_wide_row("skills", "18 files", "212 KB", chevron=False)}
{m_wide_row("memories", "3 files", "14 KB", chevron=False)}
{m_wide_row("knowledge", "1 file", "6.4 MB", chevron=False)}
{m_wide_row("Reclaim space", "caches, logs, old transcripts, index bloat")}
{m_wide_section("Danger zone")}
{m_wide_row("Delete profile", "removes identity, memory, skills, schedule from disk. Cannot be undone.", danger=True)}
</div>"""
    body = f"""<div style="display: flex; height: 100%">
{m_sidebar(FOLD_SETTINGS_H)}
<div style="flex: 1; min-width: 0; display: flex; flex-direction: column; background: #ffffff">
{m_screen_header("doc", "Settings", wide=True, creased=True, meta=[f'<span style="font-family: {MONO}; font-size: 12px; color: #454545">deepseek-v4.1-flash</span>', meter("$0.00", "/$1.00", 0)])}
{_ms().settings_head_chips("Overview")}
{inner}
</div>
</div>
"""
    return page("Fold · profile settings", 852, FOLD_SETTINGS_H, body)



def wg_budget_band():
    return m_band(f'''<div style="display: flex; flex-direction: column; gap: 10px"><div style="display: flex; align-items: baseline; gap: 10px"><span style="font-weight: 600; font-size: 28px; line-height: 1; letter-spacing: -0.018em; color: #141414">$0.40</span><span style="font-family: {MONO}; font-size: 14px; color: #6b6b6b">of <span style="color: #454545">$5.00</span> · 8%</span><span style="flex: 1"></span>{m_button("Edit", "ghost")}</div><span style="display: block; height: 6px; border-radius: 999px; background: rgba(20,20,20,0.07); overflow: hidden"><span style="display: block; width: 8%; height: 100%; background: {ALPI_ACCENT}"></span></span></div>''')


def phone_wg_settings():
    from wg_settings_studies import LAUNCH, PIPELINES, RUN, group, invited_block, m_pipeline_card, member_block
    body = f"""<div style="display: flex; flex-direction: column">
{m_screen_header("#alpha", "Workgroup · settings", accent=ALPI_ACCENT, creased=True, glyph=_wg_mark(ALPI_ACCENT, 20))}
{m_section("Overview")}
{m_group(
    m_row("Hub", "", "@mira", chevron=False),
    m_row("Status", "pause stops dispatch · leave drops membership", control=pill("active", tone="success"), chevron=False),
    m_row("Auto-read messages", "reads agents' automatic messages aloud — never your directives", control=switch(False, ALPI_ACCENT, "Auto-read messages"), chevron=False),
    m_row("Accent", "", control='<span style="display: inline-flex; align-items: center; gap: 8px"><span style="width: 16px; height: 16px; border-radius: 4px; background: ' + ALPI_ACCENT + '"></span><span style="font-family: ' + MONO + '; font-size: 12px; color: #454545">&#35;14110c</span></span>'),
    m_row("Id", "", "wg_4f2a…9c1e", chevron=False, sep=False),
)}
{m_section("Budget", "workgroup spend cap")}
{m_group(
    wg_budget_band(),
)}
{m_section("Usage", "last 14 days")}
{m_group(
    m_band(usage_chart(ALPI_ACCENT, "$0.00", "12K", "310", None, None, "14-day total $0.40 · 0.9M in / 22K out", ground="transparent", narrow=True)),
)}
{m_section("Briefing")}
{m_group(
    m_row("Edit briefing", "shared context every member reads first", sep=False),
)}
{m_section("Pipelines", "declared by the recipe")}
{"".join(m_pipeline_card(k, c, RUN if k == LAUNCH else None) for k, c in PIPELINES)}
{m_section("Members", "7")}
{"".join(group(member_block(n, phone=True), "0 12px 8px") for n in ("mira", "scout", "muse", "quill", "lingua", "pixel", "lens"))}
{m_group(
    m_row("+ Add member", "", chevron=False, sep=False),
)}
{m_section("Invitations", "1 pending")}
{m_group(
    m_row("Join command", "alpi workgroup join mira wg_4f2a…9c1e", "Copy", chevron=False, sep=False),
)}
{group(invited_block("lingo", "star", "#9b5ad9", "Language coach; invited, not yet joined.", phone=True), "0 12px 8px")}
{m_section("Danger zone")}
{m_group(
    m_row("Leave workgroup", "drops this profile's membership", danger=True),
    m_row("Delete workgroup", "removes it for every member. Cannot be undone.", danger=True, sep=False),
)}
</div>
"""
    return page("Phone · workgroup settings", 390, 2960, body)


def fold_wg_settings():
    from wg_settings_studies import LAUNCH, PIPELINES, RUN, invited_block, member_block, pipeline_block
    inner = f"""<div style="max-width: 968px; padding: 20px 24px 40px; box-sizing: border-box; display: flex; flex-direction: column">
{m_wide_section("Overview", first=True)}
{m_wide_row("Hub", "", "@mira", chevron=False)}
{m_wide_row("Status", "pause stops dispatch · leave drops membership", control=pill("active", tone="success"), chevron=False)}
{m_wide_row("Auto-read messages", "reads agents' automatic messages aloud — never your directives", control=switch(False, ALPI_ACCENT, "Auto-read messages"), chevron=False)}
{m_wide_row("Id", "", "wg_4f2a…9c1e", chevron=False)}
{m_wide_section("Budget", "workgroup spend cap")}
<div style="display: flex; flex-direction: column; gap: 10px; padding: 8px 0"><div style="display: flex; align-items: baseline; gap: 10px"><span style="font-weight: 600; font-size: 28px; line-height: 1; letter-spacing: -0.018em; color: #141414">$0.40</span><span style="font-family: {MONO}; font-size: 14px; color: #6b6b6b">of <span style="color: #454545">$5.00</span> · 8%</span><span style="flex: 1"></span>{m_button("Edit", "ghost")}</div><span style="display: block; height: 6px; border-radius: 999px; background: rgba(20,20,20,0.07); overflow: hidden"><span style="display: block; width: 8%; height: 100%; background: {ALPI_ACCENT}"></span></span></div>
{m_wide_section("Usage", "last 14 days")}
{usage_chart(ALPI_ACCENT, "$0.00", "12K", "310", None, None, "14-day total $0.40 · 0.9M in / 22K out")}
{m_wide_section("Briefing")}
{m_wide_row("Edit briefing", "shared context every member reads first")}
{m_wide_section("Pipelines", "declared by the recipe")}
{"".join(pipeline_block(k, c, RUN if k == LAUNCH else None) for k, c in PIPELINES)}
{m_wide_section("Members", "7")}
{"".join(member_block(n) for n in ("mira", "scout", "muse", "quill", "lingua", "pixel", "lens"))}
{m_wide_section("Invitations", "1 pending")}
{m_wide_row("Join command", "alpi workgroup join mira wg_4f2a…9c1e", "Copy", chevron=False, item=True)}
{invited_block("lingo", "star", "#9b5ad9", "Language coach; invited, not yet joined.")}
{m_wide_section("Danger zone")}
{m_wide_row("Leave workgroup", "drops this profile's membership", danger=True)}
{m_wide_row("Delete workgroup", "removes it for every member. Cannot be undone.", danger=True)}
</div>"""
    body = f"""<div style="display: flex; height: 100%">
{m_sidebar(2400, selected="", wg_selected=True)}
<div style="flex: 1; min-width: 0; display: flex; flex-direction: column; background: #ffffff">
{m_screen_header("alpha", "Settings", accent=ALPI_ACCENT, creased=True, glyph=_wg_mark(ALPI_ACCENT, 20), wide=True, meta=['<span style="font-family: ' + MONO + '; font-size: 12px; color: #454545">hub @mira</span>', '<span style="font-family: ' + MONO + '; font-size: 12px; color: #454545">7 members</span>', '<span style="font-family: ' + MONO + '; font-size: 12px; color: #217a45">active</span>', '<span style="font-family: ' + MONO + '; font-size: 12px; color: #6b6b6b">wg_4f2a…9c1e</span>'])}
{inner}
</div>
</div>
"""
    return page("Fold · workgroup settings", 852, 2400, body)



def conn_row(label, meta, cost):
    return m_row(label, meta, cost)


def phone_connections():
    body = f"""<div style="display: flex; flex-direction: column">
{m_screen_header("Connections", "Daemon · paired apps", glyph="", right=m_button("New", "primary", "md"))}
{m_section("Host", "local socket · setup, TUI, CLI")}
{m_group(
    m_row("Local host", "14 sessions · seen now", "$6.28", sep=False),
)}
{m_section("Connections", "2 paired")}
{m_group(
    m_row("emulator-android", "admin · all profiles · 2 devices · 4 sessions · seen now", "$0.00"),
    m_row("remote", "admin · all profiles · 2 devices · 4 sessions · seen now", "$0.44", sep=False),
)}
</div>
"""
    return page("Phone · connections", 390, 844, body)


def device_row(name, meta, wide=False):
    ctl = f'<button aria-label="Revoke {name}" class="m-chrome">{ic("x", 16, "#454545")}</button>'
    return m_wide_row(name, meta, control=ctl, chevron=False, item=True) if wide else m_row(name, meta, control=ctl, chevron=False)


def phone_connection_detail():
    body = f"""<div style="display: flex; flex-direction: column">
{m_screen_header("emulator-android", "Connection · admin", glyph="")}
{m_section("Overview")}
{m_group(
    m_row("Label", "", "emulator-android"),
    m_row("Role", "manages profiles and connections", control=pill("admin", tone="warning"), chevron=False),
    m_row("Profiles", "", "all"),
    m_row("Session scope", "one thread per connection, or one per device", "connection"),
    m_row("Enabled", "this phone goes offline with it · an admin elsewhere must re-enable it", control=switch(True, ALPI_ACCENT, "Enabled"), chevron=False),
    m_row("Sessions", "", "4", chevron=False),
    m_row("Last seen", "", "now", chevron=False, sep=False),
)}
{m_section("Usage", "last 14 days")}
{m_group(
    m_band(usage_chart(ALPI_ACCENT, "$0.00", "0", "0", None, None, "14-day total $0.00 · 0 in / 0 out", empty=True, ground="transparent", narrow=True)),
)}
{m_section("Devices", "2 paired")}
{m_group(
    device_row("sdk_gphone64_arm64", "mobile · 0.4.11 · 7d ago"),
    device_row("sdk_gphone64_arm64", "mobile · 0.5.0 · now"),
    m_row("+ Add device", "one-time pairing link", chevron=False, sep=False),
)}
{m_section("Danger zone")}
{m_group(
    m_row("Delete connection", "revokes every device and its sessions. Cannot be undone.", danger=True, sep=False),
)}
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
    from brand_boards import app_crease, black_alpaca
    body = f"""<div style="display: flex; flex-direction: column">
{m_screen_header("Settings", "This phone", glyph="")}
{m_section("This phone")}
{m_group(
    m_row("Re-pair this phone", "opens QR scanner"),
    m_row("Fingerprint unlock", "not enrolled in OS settings", control=pill("off"), chevron=False, sep=False),
)}
{m_section("Daemon")}
{m_group(
    m_row("Connections", "paired apps, devices, pairing links, usage", sep=False),
)}
{m_section("Notifications")}
{m_group(
    m_row("System permission", "instant while alpi is open · in the background via push", control=pill("off")),
    m_row("Delivery status", "Permission denied — enable alpi in system notifications", control=pill("off"), chevron=False),
    m_row("Test notifications", "dev-only · sample notifications + routing check", sep=False),
)}
{m_section("Appearance")}
{m_group(
    m_row("Theme", "", "Light"),
    m_row("Text size", "multiplies your OS text size · long-press resets", control='<span style="display: inline-flex; align-items: center; gap: 10px"><span style="font-size: 14px; color: #6b6b6b">Default</span>' + m_button("−") + m_button("+") + '</span>', chevron=False, sep=False),
)}
{m_section("Danger zone")}
{m_group(
    m_row("Sign out", "forgets the pairing on this phone", danger=True, sep=False),
)}
<div style="padding: 24px 20px; display: flex; justify-content: space-between; align-items: center">{m_eyebrow("About")}<span style="font-family: 'Geist Mono', monospace; font-size: 11px; color: #b4b4b4">Alpi mobile · v{app_version('mobile')}</span></div>
<div style="padding: 0 20px 28px; display: flex; align-items: center; gap: 12px">{black_alpaca(36, "#141414")}{app_crease("alpi", 32, "#f0b447", "#ffffff")}</div>
</div>
"""
    return page("Phone · app settings", 390, 1100, body)



def write(name, html):
    with open(os.path.join(ROOT, name), "w") as f:
        f.write(html)


CSS = """
.m-chrome{width:36px;height:36px;border:0;border-radius:4px;background:transparent;display:inline-flex;align-items:center;justify-content:center;padding:0;cursor:pointer;color:#454545}
.m-chrome:hover{background:rgba(20,20,20,0.06)}
button,input{font-family:inherit}
"""


def build(desktop_boards):
    from profile_panel_studies import PANELS_DESKTOP_H, PANELS_MOBILE_H, desktop_panels_board, mobile_panels_board
    with open(os.path.join(ROOT, "parity.css"), "w") as f:
        f.write(CSS)

    boards = {}
    order = []
    notes = {}

    def place(name, html, x, y, w, h, title, page):
        write(name, html)
        drawn = re.search(r"position: relative; width: (\d+)px; height: (\d+)px", html)
        if drawn:
            w, h = int(drawn.group(1)), int(drawn.group(2))
        boards[name] = {"x": x, "y": y, "w": w, "h": h, "title": title, "page": page}
        order.append(name)

    def title(id_, text, y, page, x=0, max_w=2600):
        notes[id_] = {"x": x, "y": y, "text": text, "kind": "title1", "maxW": max_w, "page": page}

    from desktop_overlays import OVERLAYS_H, desktop_overlays
    from mobile_overlays import MOBILE_OVERLAYS
    from system_boards import DESKTOP_COMPONENTS_H, MOBILE_COMPONENTS_H, SYSTEM, TOKENS_H

    from conversation_boards import CONVERSATION
    from onboarding_studies import DESKTOP_ONBOARDING_H, desktop_onboarding, phone_onboarding
    from mobile_attention_studies import FOLD_NOTIFICATIONS_H, FOLD_SCHEDULE_H, fold_notifications, fold_schedule
    from mobile_state_studies import STATES_H, phone_states

    y = 0
    for label, items in (
        ("Foundations", [("System-Tokens.dc.html", SYSTEM["tokens"](), TOKENS_H, "System · tokens"), ("System-Motion.dc.html", SYSTEM["motion"](), 900, "System · motion and feel")]),
        ("Controls and feedback", [("System-DesktopComponents.dc.html", SYSTEM["desktop"](), DESKTOP_COMPONENTS_H, "Desktop · controls and feedback"), ("System-MobileComponents.dc.html", SYSTEM["mobile"](), MOBILE_COMPONENTS_H, "Mobile · controls and feedback")]),
        ("Conversation", [("System-DesktopConversation.dc.html", CONVERSATION["desktop"](), 2520, "Desktop · conversation"), ("System-MobileConversation.dc.html", CONVERSATION["mobile"](), 1400, "Mobile · conversation")]),
        ("Workgroups", [("System-DesktopWorkgroup.dc.html", CONVERSATION["desktop_wg"](), 2220, "Desktop · workgroups"), ("System-MobileWorkgroup.dc.html", CONVERSATION["mobile_wg"](), 1560, "Mobile · workgroups")]),
    ):
        y += 240
        title(f"s-{label}", label, y - 223, "system")
        for i, (name, html, h, t) in enumerate(items):
            place(name, html, i * 1360, y, 1280, h, t, "system")
        y += max(boards[name]["h"] for name, _, _, _ in items)

    y = 0
    for name, html, h, label in (
        ("Desktop-Chat.dc.html", desktop_boards["chat"], 800, "Chat"),
        ("Desktop-ProfileSettings.dc.html", desktop_boards["profile"], 2400, "Profile settings"),
        ("Desktop-WorkgroupSettings.dc.html", desktop_boards["wg"], 2480, "Workgroup settings"),
        ("Desktop-ProfilePanels.dc.html", desktop_panels_board(), PANELS_DESKTOP_H, "Profile panels"),
        ("Desktop-Workgroups.dc.html", desktop_boards["workgroups"], 560, "Workgroups"),
        ("Desktop-Connections.dc.html", desktop_boards["connections"], 820, "Connections"),
        ("Desktop-AppSettings.dc.html", desktop_boards["app"], 740, "App settings"),
        ("Desktop-FirstRun.dc.html", desktop_onboarding(), DESKTOP_ONBOARDING_H, "First run"),
        ("Desktop-Overlays.dc.html", desktop_overlays(), OVERLAYS_H, "Overlays"),
    ):
        y += 240
        title(f"d-{label}", label, y - 223, "desktop")
        place(name, html, 0, y, 1280, h, f"Desktop · {label.lower()}", "desktop")
        y += boards[name]["h"]

    X_FOLD, X_PHONE = 0, 932
    y = 0
    first_run = phone_onboarding()
    rows = (
        ("First run", [("Phone-PairWelcome.dc.html", first_run["welcome"], X_PHONE, 390, 844, "Phone · pair with your alpi"), ("Phone-Pairing.dc.html", first_run["connecting"], X_PHONE + 470, 390, 844, "Phone · pairing, each step named"), ("Phone-Paired.dc.html", first_run["paired"], X_PHONE + 940, 390, 844, "Phone · paired, host and role")]),
        ("Pairing failures", [("Phone-PairUnreachable.dc.html", first_run["unreachable"], X_PHONE, 390, 844, "Phone · host unreachable, link kept"), ("Phone-PairLinkUsed.dc.html", first_run["used"], X_PHONE + 470, 390, 844, "Phone · link used, cleared"), ("Phone-NothingShared.dc.html", first_run["member"], X_PHONE + 940, 390, 844, "Phone · member with nothing shared")]),
        ("Chat", [("Fold-Chat.dc.html", fold_chat(), X_FOLD, 852, 884, "Fold · chat"), ("Phone-Chat.dc.html", phone_chat(), X_PHONE, 390, 844, "Phone · chat")]),
        ("Profile settings", [("Fold-ProfileSettings.dc.html", fold_profile_settings(), X_FOLD, 852, 2000, "Fold · profile settings"), ("Phone-ProfileSettings.dc.html", phone_profile_settings(), X_PHONE, 390, 2360, "Phone · profile settings")]),
        ("Workgroup settings", [("Fold-WorkgroupSettings.dc.html", fold_wg_settings(), X_FOLD, 852, 2400, "Fold · workgroup settings"), ("Phone-WorkgroupSettings.dc.html", phone_wg_settings(), X_PHONE, 390, 2960, "Phone · workgroup settings")]),
        ("Profile panels", [("Phone-ProfilePanels.dc.html", mobile_panels_board(), X_FOLD, 1280, PANELS_MOBILE_H, "Phone · profile panels")]),
        ("Connections", [("Fold-ConnectionDetail.dc.html", fold_connection_detail(), X_FOLD, 852, 1300, "Fold · connection detail"), ("Phone-Connections.dc.html", phone_connections(), X_PHONE, 390, 844, "Phone · connections"), ("Phone-ConnectionDetail.dc.html", phone_connection_detail(), X_PHONE + 470, 390, 1500, "Phone · connection detail")]),
        ("App settings", [("Phone-Settings.dc.html", phone_settings(), X_PHONE, 390, 1100, "Phone · app settings")]),
        ("Notifications", [("Phone-Notifications.dc.html", phone_notifications(), X_PHONE, 390, 844, "Phone · notifications, filters and swipe"), ("Phone-NotificationPage.dc.html", phone_notification_page(), X_PHONE + 470, 390, 844, "Phone · notification page, actions at the thumb")]),
        ("Activity", [("Fold-Activity.dc.html", fold_activity(), X_FOLD, 852, FOLD_ACTIVITY_H, "Fold · activity"), ("Phone-Roster.dc.html", phone_roster(), X_PHONE, 390, 844, "Phone · roster"), ("Phone-Activity.dc.html", phone_activity(), X_PHONE + 470, 390, PHONE_ACTIVITY_H, "Phone · activity")]),
        ("Overlays", [("Fold-Sheet.dc.html", MOBILE_OVERLAYS["fold_sheet"](), X_FOLD, 852, 884, "Fold · sheet as a centred dialog"), ("Phone-Sheet.dc.html", MOBILE_OVERLAYS["phone_sheet"](), X_PHONE, 390, 844, "Phone · sheet"), ("Phone-ActionSheet.dc.html", MOBILE_OVERLAYS["phone_action"](), X_PHONE + 470, 390, 844, "Phone · action sheet"), ("Phone-TypedConfirm.dc.html", MOBILE_OVERLAYS["phone_confirm"](), X_PHONE + 940, 390, 844, "Phone · typed confirm")]),
        ("Sheets", [("Phone-ToolSheet.dc.html", MOBILE_OVERLAYS["phone_tool"](), X_PHONE, 390, 844, "Phone · tool step sheet"), ("Phone-SelectText.dc.html", MOBILE_OVERLAYS["phone_select"](), X_PHONE + 470, 390, 844, "Phone · select text"), ("Phone-MessageActions.dc.html", MOBILE_OVERLAYS["phone_message"](), X_PHONE + 940, 390, 844, "Phone · message actions")]),
        ("Schedule", [("Fold-Schedule.dc.html", fold_schedule(), X_FOLD, 1104, FOLD_SCHEDULE_H, "Fold · schedule, list and job side by side"), ("Fold-Notifications.dc.html", fold_notifications(), X_FOLD + 1180, 1104, FOLD_NOTIFICATIONS_H, "Fold · notifications, list and reader side by side")]),
        ("States", [("Phone-States.dc.html", phone_states(), X_FOLD, 1280, STATES_H, "Phone · empty, error and offline states")]),
    )
    for label, items in rows:
        y += 240
        title(f"m-{label}", label, y - 223, "mobile")
        for name, html, x, w, h, t in items:
            place(name, html, x, y, w, h, t, "mobile")
        y += max(boards[name]["h"] for name, *_ in items)

    from brand_boards import BRAND_BOARDS
    y = 0
    for name, fn, h, t in BRAND_BOARDS:
        y += 240
        title(f"b-{t}", t, y - 223, "brand")
        place(name, fn(), 0, y, 1280, h, f"Brand · {t.lower()}", "brand")
        y += boards[name]["h"]

    from proposals import PROPOSAL_BOARDS
    y = 0
    for name, fn, h, t in PROPOSAL_BOARDS:
        y += 240
        title(f"p-{t}", t, y - 223, "proposals")
        place(name, fn(), 0, y, 1280, h, f"Proposals · {t.lower()}", "proposals")
        y += boards[name]["h"]

    live_path = os.path.join(os.path.dirname(ROOT), "live", "project", "canvas.json")
    created = {"v": 1, "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    previous_path = os.path.join(ROOT, "canvas.json")
    try:
        with open(previous_path) as f:
            previous = json.load(f)
        if isinstance(previous, dict) and isinstance(previous.get("createdOnFiles"), dict):
            created = previous["createdOnFiles"]
    except (OSError, ValueError):
        pass
    index = {
        "v": 3,
        "createdOnFiles": created,
        "title": "Alpi desktop and mobile parity",
        "launch": {"view": "canvas", "page": "brand"},
        "pages": [{"id": "brand", "name": "Brand"}, {"id": "system", "name": "System"}, {"id": "desktop", "name": "Desktop"}, {"id": "mobile", "name": "Mobile"}, {"id": "proposals", "name": "Proposals"}],
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
