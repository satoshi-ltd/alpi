import os
import re

from gen import app_version, FOCUS_OUT, R_CHIP, R_CONTROL, R_SURFACE, R_SHEET, R_XS, NEST, DANGER, DOC_ACCENT, FLOAT_EDGE, SHEET_EDGE, di, ic, m_row_below, m_segmented, mi, m_banner, m_button, m_conn_header, m_confirm_dialog, m_bell_dot, m_count_badge, m_empty_state, m_group, m_roster_row, m_row, m_row_state, m_shell_footer, m_toast, meter, page, pill, switch
from panel_kit import alert_banner
from desktop_boards import (ELEV, SM_FLOAT, banner_bar, mono12, row as settings_row, HOVER, INK, INK2, INK3, INK4, LINE, LINE2, MONO, PANE, SIDE, alink, badged, button, chip, code_chip, field_input, iconbtn, kbd, key_hint,
                            meterchip, phase_count, seg, selectish, settings_rail, sidebar_footer, state_chip, textarea, wg_mark)
from desktop_overlays import checkbox, radio, dialog_footer, dropdown_row, dropdown_trigger, ds_field, menu_item, menu_sep, modal, toast_box
from mobile_overlays import action_item, picker_row, separator, sheet_header
from loading_studies import BREATH_S, BUSY_TURN_S, DUR_SPIN, SPINNER_TURN_MS, STAGGER_MS, waiting

AMBER, ACCENT_LIGHT, ACCENT_DARK = "#14110c", "#14110c", "#f3efe6"
TOKENS_MJS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "common", "tokens.mjs")
MOBILE_TOKENS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "mobile", "src", "theme", "tokens.js")


def shared_tokens():
    import json
    import subprocess
    script = ("import * as t from './common/tokens.mjs'; import { MARK_SIZES } from './common/agentMarks.mjs';"
              "process.stdout.write(JSON.stringify({type: t.typeLadder, lead: t.typeLeading, mono: t.monoScale, space: t.spaceScale, radii: t.radii, role: t.radiusRole, heights: t.controlRole, icons: t.iconSizes,"
              " stroke: t.iconStrokeRendered, fills: t.stateFills, motion: t.motionTokens, focus: t.focusRing, field: t.fieldFocus, float: t.floatShadow, veils: t.veils, shell: t.shell, palettes: t.palettes, marks: MARK_SIZES}));")
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
    return json.loads(subprocess.run(["node", "--input-type=module", "-e", script], cwd=root, capture_output=True, text=True, check=True).stdout)


T = shared_tokens()
SWATCH_KEYS = tuple(k for k in T["palettes"]["light"] if k not in ("success", "warning", "danger"))


def token_block(name):
    with open(TOKENS_MJS) as f:
        src = f.read()
    body = re.search(r"const " + name + r" = \{(.*?)\};", src, re.S).group(1)
    return dict(re.findall(r"(\w+):\s*\"(#[0-9a-fA-F]{6}|rgba\([^)]*\))\"", body))


LIGHT = [(k, token_block("light")[k]) for k in SWATCH_KEYS]
DARK = [(k, token_block("dark")[k]) for k in SWATCH_KEYS]
STATUS = list(token_block("status").items())
TYPE_ROLE = {"meta": "timestamps, counts, hints, tab labels: the floor, nothing smaller ships",
             "small": "descriptions, previews, section labels, tool steps, chips",
             "ui": "rows, buttons, menus, fields, settings labels",
             "read": "messages and the composer: everything you read or write at length",
             "title": "screen, section, dialog and sheet titles; names in headers",
             "display": "first run, empty states, the phone's large titles"}
HEIGHT_ROLE = {"compact": "dense desktop rows, chips, header buttons", "control": "every desktop control", "touch": "every phone control and tap"}
ICON_TOKEN = {16: "sm", 20: "md", 24: "lg"}
ICON_ROLE = {"inline": "in text, rows and 32 px buttons", "control": "40 px buttons, menus, the composer", "nav": "phone navigation"}


def channels(hex_):
    return tuple(int(hex_[i:i + 2], 16) for i in (1, 3, 5))


def over(hex_, a, ground):
    return "#{:02x}{:02x}{:02x}".format(*(round(c * a + g * (1 - a)) for c, g in zip(channels(hex_), channels(ground))))


def luminance(hex_):
    lin = [(v / 255) / 12.92 if v / 255 <= 0.04045 else ((v / 255 + 0.055) / 1.055) ** 2.4 for v in channels(hex_)]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def ratio(fg, bg):
    hi, lo = sorted((luminance(fg), luminance(bg)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


CONTRAST = (("ink3 on side", "ink3", "bgSide", 4.5), ("ink3 on pane", "ink3", "bgPane", 4.5), ("ink3 on fill", "ink3", "fill", 4.5), ("ink3 on raised", "ink3", "raised", 4.5),
            ("ink on a selected row", "ink", "sel", 4.5), ("pane on the primary", "bgPane", "accent", 4.5), ("dangerText on fill", "dangerText", "fill", 4.5), ("warningText on pane", "warningText", "bgPane", 4.5),
            ("field focus line on fill", "ink3", "fill", 3.0), ("switch off track on pane", "edge", "bgPane", 3.0), ("focus ring on pane", "ring", "bgPane", 3.0), ("focus ring on fill", "ring", "fill", 3.0))


def solid(mode, key, ground):
    p = T["palettes"][mode]
    if key == "sel":
        return over(p["ink"], T["fills"][mode]["selected"], p["bgPane"])
    if key == "ring":
        return over(p["ink"], T["focus"]["alpha"], ground)
    return p[key]


def contrast_rows():
    out = []
    for label_, fg, bg, floor in CONTRAST:
        cells = []
        for mode in ("light", "dark"):
            ground = solid(mode, bg, T["palettes"][mode]["bgPane"])
            cells.append(ratio(solid(mode, fg, ground), ground))
        out.append((label_, cells, floor))
    return out


def h1(text, sub):
    return f'<div style="display: flex; flex-direction: column; gap: 6px"><span style="font-size: 28px; font-weight: 600; letter-spacing: -0.02em; line-height: 1.15">{text}</span><span style="font-size: 15px; line-height: 1.5; color: {INK3}; max-width: 880px">{sub}</span></div>'


def h2(text, n):
    return f'<div style="display: flex; align-items: baseline; gap: 10px; margin-top: 8px"><span style="font-size: 20px; font-weight: 600; line-height: 1.25">{text}</span><span style="font-size: 12px; color: {INK4}">{n:02d}</span></div>'


def label(text):
    return f'<span style="font-size: 14px; font-weight: 500; color: {INK3}">{text}</span>'


def desktop_charts():
    from chart_studies import chart_gallery
    return "".join(f'<div style="width: 330px">{card}</div>' for card in chart_gallery(330))


def phone_charts():
    from chart_studies import chart_gallery
    return "".join(f'<div style="width: 240px">{card}</div>' for card in chart_gallery(240, compact=True))


def specimen(title, inner, w=None, bg=PANE):
    width = f"width: {w}px;" if w else ""
    return (f'<div style="display: flex; flex-direction: column; gap: 8px; {width} flex-shrink: 0">{label(title)}'
            f'<div style="display: flex; flex-wrap: wrap; align-items: center; gap: 12px; padding: 16px; border-radius: 12px; background: {bg}; box-shadow: 0 0 0 0.5px {LINE2}">{inner}</div></div>')


def swatch(name, hexv, on_dark=False):
    fg = "#ededed" if on_dark else INK
    shown = re.sub(r"rgba\((\d+),(\d+),(\d+),([\d.]+)\)", lambda m: f"{m[1]} · {float(m[4]) * 100:.0f}%", hexv.replace(" ", ""))
    return (f'<div style="display: flex; flex-direction: column; gap: 6px; width: 96px"><div style="height: 44px; border-radius: 6px; background: {hexv}; box-shadow: inset 0 0 0 0.5px {LINE2}"></div>'
            f'<span style="font-size: 12px; font-weight: 500; color: {fg}">{name}</span><span style="font-family: {MONO}; font-size: 11px; color: {"#969696" if on_dark else INK3}">{shown}</span></div>')


def tokens_board():
    from brand_boards import app_name
    import marks
    light = "".join(swatch(n, v) for n, v in LIGHT)
    dark = "".join(swatch(n, v, True) for n, v in DARK)
    dark_ground = dict(DARK)["bgPane"]
    status = "".join(swatch(n, v) for n, v in STATUS)
    small = lambda text, color=INK3: f'<span style="font-size: 12px; line-height: 1.4; color: {color}">{text}</span>'
    ladder = "".join(f'<div style="display: flex; align-items: baseline; gap: 16px"><span style="width: 110px; font-size: 12px; color: {INK3}">--text-{"read" if k == "read" else k} · {v}</span>'
                     f'<span style="width: 380px; font-size: {v}px; line-height: {T["lead"][k]}; font-weight: {600 if k in ("title", "display") else 400}; color: {INK}; white-space: nowrap">Pull my lipid panels</span>{small(TYPE_ROLE[k])}</div>' for k, v in T["type"].items())
    mono_scale = T["mono"]
    families = (f'<div style="display: flex; flex-direction: column; gap: 10px">'
                f'<div style="display: flex; align-items: baseline; gap: 16px"><span style="width: 160px; font-size: 15px; font-weight: 600">Geist</span>{small("every word of the interface, prose and labels; weights 400 · 500 · 600")}</div>'
                f'<div style="display: flex; align-items: baseline; gap: 16px"><span style="width: 160px; font-family: {MONO}; font-size: 14px">Geist Mono</span>{small(f"only machine text: code, paths, commands, model ids; at {mono_scale:g} of its line")}</div>'
                f'<div style="display: flex; align-items: baseline; gap: 16px"><span style="width: 160px">{app_name("doc", 20, "#3899e2", PANE, literal=True)}</span>{small("Bricolage 800 in nameTone, only where a name stands alone: a tile, a header, a hero")}</div></div>')
    space = "".join(f'<div style="display: flex; flex-direction: column; align-items: center; gap: 6px"><div style="width: {px}px; height: {px}px; background: {INK}; opacity: 0.8; border-radius: 3px"></div>{small(str(px))}</div>' for px in T["space"].values())
    radii = "".join(f'<div style="display: flex; flex-direction: column; align-items: center; gap: 6px; width: 150px"><div style="width: 88px; height: 56px; background: #f2f2f2; border-radius: {min(px, 28)}px"></div>'
                    f'<span style="font-size: 12px; font-weight: 500; color: {INK2}">--r-{n} · {"pill" if px >= 999 else px}</span><span style="font-size: 12px; line-height: 1.4; color: {INK3}; text-align: center">{T["role"][n]}</span></div>' for n, px in T["radii"].items())
    heights = "".join(f'<div style="display: flex; flex-direction: column; align-items: center; gap: 6px">{button(k.title(), "secondary", {"compact": "sm", "control": "md", "touch": "hero"}[k])}{small(f"--ctl-{v} · {HEIGHT_ROLE[k]}")}</div>' for k, v in T["heights"].items())
    icon_sizes = "".join(f'<div style="display: flex; flex-direction: column; align-items: center; gap: 6px">{di("gear", px, INK)}{small(f"--icon-{ICON_TOKEN[px]} · {px} · {ICON_ROLE[k]}")}</div>' for k, px in T["icons"].items())
    mark_sizes = "".join(f'<div style="display: flex; flex-direction: column; align-items: center; gap: 6px">{marks.profile("doc", "#3899e2", px, "idle")}{small(f"{k} {px}")}</div>' for k, px in T["marks"].items())
    surface_use = {"side": "sidebar, phone tab bar ground", "pane": "content, the phone ground", "fill": "bubbles, fields, composer, cards, groups, chips", "raised": "menus, dialogs, sheets, toasts, with the float shadow"}
    shadow = {"raised": T["float"]["light"]}
    surfaces = "".join(f'<div style="display: flex; flex-direction: column; gap: 6px; width: 140px"><div style="height: 64px; border-radius: 14px; background: {T["palettes"]["light"][key]}; box-shadow: {shadow.get(name, "inset 0 0 0 0.5px " + LINE2)}"></div>'
                       f'<span style="font-size: 14px; font-weight: 600">{name}</span>{small(surface_use[name])}<span style="font-family: {MONO}; font-size: 11px; color: {INK3}">{T["palettes"]["light"][key]} · {T["palettes"]["dark"][key]}</span></div>'
                       for name, key in (("side", "bgSide"), ("pane", "bgPane"), ("fill", "fill"), ("raised", "raised")))
    fills = T["fills"]
    states = "".join(f'<div style="display: flex; flex-direction: column; gap: 6px; width: 150px"><div style="height: 40px; border-radius: 999px; background: {fill}; {ring}"></div><span style="font-size: 12px; font-weight: 500; color: {INK2}">{n}</span>{small(use)}</div>'
                     for n, fill, ring, use in (("rest", "transparent", "box-shadow: inset 0 0 0 0.5px " + LINE2, "no fill, no rule"),
                                                (f"hover · {fills['light']['hover'] * 100:g} / {fills['dark']['hover'] * 100:g} %", "rgba(20,20,20,0.04)", "", f"fades in over fast {T['motion']['fast']} ms, out over exit {T['motion']['exit']} ms, colour only"),
                                                (f"selected · {fills['light']['selected'] * 100:g} / {fills['dark']['selected'] * 100:g} %", "rgba(20,20,20,0.08)", "", "the one selection look: a neutral fill, never an outline or stripe"),
                                                (f"pressed · {fills['light']['pressed'] * 100:g} / {fills['dark']['pressed'] * 100:g} %", "rgba(20,20,20,0.12)", "", "instant, no transition"),
                                                (f"focus · {T['focus']['width']} px · {T['focus']['alpha'] * 100:g} %", "transparent", f"outline: {T['focus']['width']}px solid rgba(20,20,20,{T['focus']['alpha']}); outline-offset: {T['focus']['offset']}px", "keyboard focus only, on both clients; never on the composer"),
                                                ("disabled · 0.45", "#f2f2f2; opacity: 0.45", "", "--alpha-disabled, every client")))
    field_states = (f'<div style="display: flex; gap: 12px; align-items: center">{field_input("Search", 200, placeholder=True)}{field_input("$1.00 / day", 160)}{field_input("/data/workspace", 220, focus=True, mono=True)}'
                    f'{field_input("1O.00", 120).replace("background: #f2f2f2;", "background: #f2f2f2; box-shadow: inset 0 0 0 1.5px #b73737;")}</div>')
    buttons = "".join((button("Primary", "primary"), button("Secondary", "secondary"), button("Ghost"), button("Delete", "danger-ghost"), button("Delete profile", "danger"), iconbtn("more", "More", 40, 20), button("Disabled", "secondary").replace("cursor: pointer", "cursor: default; opacity: 0.45")))
    picks = "".join((selectish("Default effort", mono=False), seg(("All", "Paused", "Failing"), "All"), switch(True), switch(False), checkbox(True), checkbox(False), chip("openrouter", "on"), chip("Needs you · 2")))
    contrast = "".join(f'<div style="display: flex; gap: 12px; font-size: 12px; line-height: 1.8"><span style="flex: 1; color: {INK2}">{label_}</span>'
                       + "".join(f'<span style="width: 70px; text-align: right; color: {INK if r >= floor else DANGER}; font-variant-numeric: tabular-nums">{m} {r:.2f}</span>' for m, r in zip(("L", "D"), cells))
                       + f'<span style="width: 44px; text-align: right; color: {INK3}">≥ {floor:g}</span></div>' for label_, cells, floor in contrast_rows())
    floating = (f'<div style="display: flex; gap: 24px; align-items: flex-start; flex-wrap: wrap">'
                f'<div style="width: 240px; padding: 8px; box-sizing: border-box; border-radius: {R_SURFACE}px; background: #ffffff; box-shadow: {T["float"]["light"]}">{menu_item("plus", "New session", hint="⌘N")}{menu_item("gear", "Open settings", hint="⌘,", highlight=True)}{menu_sep()}{menu_item("trash", "Delete profile…", danger=True)}</div>'
                f'<span style="display: inline-flex; padding: 6px 10px; border-radius: 8px; background: {INK}; color: {PANE}; font-size: 12px; font-weight: 500">Copy · ⌘C</span>'
                f'{toast_box("Reasoning effort saved", "#3fb37a", "Undo")}'
                f'<div style="width: 360px">{banner_bar("warning", "casa is updating; replies resume in a minute.", pad="16px")}</div></div>')
    shell = T["shell"]
    body = f"""<div style="padding: 40px 48px; display: flex; flex-direction: column; gap: 28px; box-sizing: border-box">
{h1("alpi design system", "One token file, <span style='font-family: " + MONO + "'>common/tokens.mjs</span>, feeds both clients: desktop reads it as CSS custom properties (tokens.css, parity-tested), mobile through useTheme(), with no per-client override. Six type sizes with a 12 px floor, one family per role, one 4-pt space grid, five radii that say what a thing does, three heights and four surfaces that are the same on both clients. The brand accent is the neutral ink: near-black on light, cream on dark.")}
{h2("Type · six sizes, one family per role", 1)}
<div style="display: flex; flex-direction: column; gap: 10px">{ladder}</div>
{families}
{h2("Surfaces · the same on both clients", 2)}
<div style="display: flex; gap: 16px; flex-wrap: wrap">{surfaces}</div>
{small("A floating surface is raised with a soft float shadow in light and a 1 px hairline edge in dark; the veil dims what it covers. No hairline parts rows, headers or the composer: space does, and the stream fades under the header and into the composer.")}
{h2("Colour · light", 3)}
<div style="display: flex; flex-wrap: wrap; gap: 14px">{light}</div>
{h2("Colour · dark", 4)}
<div style="display: flex; flex-wrap: wrap; gap: 14px; padding: 16px; border-radius: 12px; background: {dark_ground}">{dark}</div>
{h2("Status", 5)}
<div style="display: flex; gap: 14px">{status}<div style="font-size: 12px; color: {INK3}; max-width: 520px; line-height: 1.5; align-self: center">Fills for dots, meters and danger buttons. Text uses the *Text variants so it clears 4.5:1.</div></div>
{h2("Contrast · computed from the values, light and dark", 6)}
<div style="max-width: 600px">{contrast}</div>
{h2("Space, shape and size", 7)}
<div style="display: flex; gap: 18px; align-items: flex-end">{space}{small("one 4-pt grid on both clients")}</div>
<div style="display: flex; gap: 12px; flex-wrap: wrap; align-items: flex-start">{radii}</div>
{small("Press is a pill, type is 12, contain is 20, float is 28: buttons, chips, selects, segments, switches and icon buttons are pills; fields, list rows, menu items and the selection fill take 12; cards, groups, bubbles, menus and toasts 20; dialogs, sheets, the palette and the composer 28. A menu insets its rows by 8.")}
<div style="display: flex; gap: 24px; align-items: flex-start">{heights}</div>
<div style="display: flex; gap: 24px; align-items: flex-end">{icon_sizes}{small(f"stroke {T['stroke']:g} rendered at every size")}</div>
<div style="display: flex; gap: 20px; align-items: flex-end">{mark_sizes}</div>
{small(f"Shell: sidebar {shell['sidebar']} px, rows {shell['rowDesktop']} px with 24 px marks and 15 px names, pinned tiles of {shell['tile']} px; header {shell['header']} px; stream column {shell['stream']} px; composer one {shell['composer']} px pill; phone rows {shell['rowPhone']} px with 40 px marks.")}
{h2("States · every pressable", 8)}
<div style="display: flex; gap: 18px; flex-wrap: wrap">{states}</div>
{small(f"Hover is colour only: the state fill fades in over {T['motion']['fast']} ms on the enter curve and out over {T['motion']['exit']} ms on the exit curve, with no lift, scale or shadow; pressed is instant; reduced motion drops the transition. Focus is a {T['focus']['width']} px ring at {T['focus']['alpha'] * 100:g} % ink outside a pressable, only on keyboard focus (desktop :focus-visible, a hardware keyboard on the phone). A field shows focus as a {T['field']['width']:g} px inset {T['field']['ink']} line; the composer shows none.")}
{h2("Controls", 9)}
<div style="display: flex; gap: 10px; flex-wrap: wrap; align-items: center">{buttons}</div>
{field_states}
<div style="display: flex; gap: 12px; flex-wrap: wrap; align-items: center">{picks}</div>
{h2("Floating", 10)}
{floating}
</div>"""
    return page("System · tokens", 1280, TOKENS_H, body)


def notification_reader(w, size=13, mobile=False):
    entries = (("Ana Ruiz", "ana@example.com", "Can we move Friday’s review to Monday?"), ("Bob Lee", "bob@acme.io", f'Invoice 0412 is attached · <a href="#" style="color: {INK}; text-decoration: underline; text-underline-offset: 2px">open the invoice</a>'), ("Carmen", "", "Thanks, all set"))
    rows = "".join(f'<div style="display: flex; flex-direction: column; gap: 2px; padding: 8px 0; ">'
                   f'<span style="display: flex; align-items: baseline; gap: 8px"><span style="font-size: {size}px; font-weight: 600; color: {INK}">{n}</span>'
                   f'<span style="font-family: {MONO}; font-size: 11px; color: {INK3}">{m}</span></span><span style="font-size: {size}px; line-height: 1.45; color: {INK2}">{t}</span></div>'
                   for i, (n, m, t) in enumerate(entries))
    digest = (f'<div style="width: {w}px; display: flex; flex-direction: column; gap: 6px"><span style="font-size: {size + 3}px; font-weight: 600; color: {INK}">Daily mail digest</span>'
              f'<span style="font-size: {size}px; color: {INK2}">14 new emails since yesterday, 3 need a reply.</span><div>{rows}</div></div>')
    facts = (("Reason", "The mail account refused the saved token."), ("Exit", "1"), ("Timeout", "none"))
    kv = "".join(f'<div style="display: flex; gap: 10px; padding: 6px 0; ">'
                 f'<span style="min-width: 64px; padding-top: 2px; font-family: {MONO}; font-size: 11px; letter-spacing: 0.06em; color: {INK3}">{k.upper()}</span>'
                 f'<span style="flex: 1; font-size: {size}px; line-height: 1.4; color: {INK if i == 0 else INK2}">{v}</span></div>' for i, (k, v) in enumerate(facts))
    details = (f'<div style="display: flex; align-items: center; gap: 6px; padding: 8px 10px; border-radius: {R_CONTROL}px; background: rgba(20,20,20,0.04); font-family: {MONO}; font-size: 11px; color: {INK2}">'
               f'{ic("chev-r", 12, INK3)}Details</div>')
    actions = (m_button("Run again", "primary", "sm") + m_button("Open job", "secondary", "sm")) if mobile else (button("Run again", "primary") + button("Open job", "secondary"))
    card = (f'<div style="width: {w}px; box-sizing: border-box; display: flex; flex-direction: column; gap: 10px; padding: 14px 16px; border-radius: {R_SURFACE}px; background: var(--card, #f4f4f4)">'
            f'<span style="display: flex; align-items: center; gap: 8px; font-size: {size + 3}px; font-weight: 600; color: {INK}">{ic("triangle-alert", 14, DANGER)}Daily mail digest <span style="color: {DANGER}">failed</span></span>'
            f'<div>{kv}</div>{details}<div style="display: flex; gap: 6px">{actions}</div></div>')
    return f'<div style="display: flex; gap: 32px; align-items: flex-start">{digest}{card}</div>'


STATE_FILLS = {"primary": {"hover": "color-mix(in srgb, #14110c 88%, #ffffff)", "pressed": "color-mix(in srgb, #14110c 80%, #ffffff)"},
               "secondary": {"hover": "rgba(20,20,20,0.12)", "pressed": "rgba(20,20,20,0.16)"},
               "ghost": {"hover": "rgba(20,20,20,0.04)", "pressed": "rgba(20,20,20,0.08)"}}


def state_button(kind, state):
    html = button({"primary": "Send", "secondary": "Deny", "ghost": "Cancel"}[kind], kind)
    if state in STATE_FILLS[kind]:
        html = re.sub(r"background: [^;]+;", f"background: {STATE_FILLS[kind][state]};", html, count=1)
    extra = {"focus": FOCUS_OUT, "disabled": "opacity: 0.45"}.get(state)
    return html.replace('<button style="', f'<button style="{extra}; ', 1) if extra else html


def state_specimens():
    out = []
    for kind in ("primary", "secondary", "ghost"):
        out.extend((f"{kind} · {state}", state_button(kind, state)) for state in ("rest", "hover", "pressed", "focus", "disabled"))
    out.append(("well · focus", ds_field("doc", 140, focus=True)))
    out.append(("box · focus", checkbox(True, focus=True)))
    out.append(("box · disabled", checkbox(False, disabled=True)))
    return out


def desktop_components_board():
    buttons = "".join(button(t, v) for t, v in (("Primary", "primary"), ("Secondary", "secondary"), ("Ghost", "ghost"), ("Danger", "danger"), ("Danger ghost", "danger-ghost"))) + button("sm", "secondary", "sm") + button("lg", "secondary", "lg") + button("hero", "primary", "hero") + button("Connections", "ghost", "md", "globe") + alink("Action link") + alink("Remove", danger=True)
    icon_only = "".join(button("Settings", "ghost", z, "gear", True) for z in ("sm", "md", "lg", "hero")) + button("Close", "secondary", "md", "x", True) + button("Stop", "primary", "md", "x", True) + f'<span style="font-size: 12px; color: {INK3}">IconBtn is Button ghost iconOnly · square at the size height · scale .96 on press</span>'
    tip = (f'<span style="display: inline-flex; flex-direction: column; align-items: center; gap: 6px">{iconbtn("gear", "Settings")}'
           f'<span style="position: relative; padding: 4px 8px; border-radius: {R_XS}px; background: {INK}; color: {PANE}; font-size: 12px; font-weight: 500; line-height: 1.3">'
           f'<span style="position: absolute; left: 50%; top: -3px; width: 6px; height: 6px; background: {INK}; transform: translateX(-50%) rotate(45deg)"></span>Settings · ⌘,</span></span>'
           f'<span style="display: inline-flex; flex-direction: column; align-items: center; gap: 6px"><span style="position: relative; padding: 4px 8px; border-radius: {R_XS}px; background: {INK}; color: {PANE}; font-size: 12px; font-weight: 500; line-height: 1.3">'
           f'<span style="position: absolute; left: 50%; bottom: -3px; width: 6px; height: 6px; background: {INK}; transform: translateX(-50%) rotate(45deg)"></span>Activity · 2 need you · ⌘J</span>{iconbtn("role:activity", "Activity")}</span>')
    swatch = lambda c: f'<span style="width: 9px; height: 9px; border-radius: 2px; background: {c}; flex-shrink: 0"></span>'
    usage_tip = (f'<div style="min-width: 132px; box-sizing: border-box; padding: 12px; border-radius: {R_SURFACE}px; background: {ELEV}; {SM_FLOAT}">'
                 f'<div style="font-size: 12px; color: {INK3}; margin-bottom: 4px">Oct 21<span> · today</span></div>'
                 f'<div style="font-size: 20px; font-weight: 600; line-height: 1; color: {INK}; margin-bottom: 8px">$0.42</div>'
                 f'<div style="display: flex; align-items: center; gap: 8px; font-size: 12px; line-height: 1.4; color: {INK2}">{swatch("rgba(20,17,12,0.24)")}in<span style="margin-left: auto; padding-left: 12px; color: {INK}">102K</span></div>'
                 f'<div style="display: flex; align-items: center; gap: 8px; font-size: 12px; line-height: 1.4; color: {INK2}">{swatch("#14110c")}out<span style="margin-left: auto; padding-left: 12px; color: {INK}">831</span></div></div>')
    keys = "".join(f'<span style="display: inline-flex; align-items: center; gap: 8px"><span style="font-size: 12px; color: {INK3}">{h}</span>{key_hint(h)}</span>' for h in ("⌘K", "⌘/", "⇧⌘N", "⌘1–9", "Esc")) + f'<span style="display: inline-flex; align-items: center; gap: 8px"><span style="font-size: 12px; color: {INK3}">text hint</span>{key_hint("light · dark · system")}</span>'
    states = (state_chip("needs-you") + state_chip("failed") + state_chip("working", "#3899e2") + phase_count(2, 4)
              + badged("role:notifications", "Notifications · 1 unread", 1) + badged("role:activity", "Activity · 2 need you", 2))
    rail = f'<div style="display: flex; gap: 32px">{settings_rail(("Overview", "Usage", "Service", "ALP", "Sandbox"), 0)}{settings_rail(("Voice",), 0, "voice")}<span style="font-size: 12px; color: {INK3}; max-width: 280px; line-height: 1.5">Rail 168 wide, search 28 high; rows follow the section in view and jump on click. A query hides every section and row that does not match; Enter jumps to the first hit.</span></div>'
    chips = chip("plain") + chip("on", "on") + chip("off", "off") + chip("warn", "warn") + chip("clickable", clickable=True) + code_chip("deepseek-v4.1-flash") + kbd("⌘") + kbd("K")
    fields = field_input("phone") + textarea("Identity as the agent sees itself", rows=2, w=300) + ds_field("phone", 160) + selectish("nova") + dropdown_trigger("medium") + seg(("All", "Working", "Paused"), "All") + checkbox(True) + checkbox(False) + radio(True) + radio(False)
    ladder = "".join(f'<span style="display: inline-flex; flex-direction: column; align-items: flex-start; gap: 6px">{html}<span style="font-family: {MONO}; font-size: 10px; color: {INK3}">{name}</span></span>' for name, html in state_specimens())
    def invalid_field(value, note, note_id=""):
        ident = f' id="{note_id}"' if note_id else ""
        return (f'<span style="display: inline-flex; flex-direction: column; gap: 4px; width: 320px"><span style="display: inline-flex; align-items: center; height: 40px; padding: 0 12px; border-radius: {R_CONTROL}px; background: var(--well, #f2f2f2); box-shadow: inset 0 0 0 1.5px #b73737; font-size: 15px; color: {INK}; box-sizing: border-box">{value}</span>'
                f'<span{ident} style="font-size: 14px; line-height: 1.45; color: #b73737">{note}</span></span>')
    invalid = invalid_field("Doc!", "a–z, 0–9, '.', '_', '-'; must start with a letter or digit", "name-error") + invalid_field("alpi", "@alpi already exists")
    meters = meterchip("$0.40", "/$5.00", 0.08) + meterchip("24K", "/1.0M", 0.024) + f'<span style="display: inline-flex; align-items: center; gap: 6px; font-family: {MONO}; font-size: 11px; color: {INK3}"><span style="width: 8px; height: 8px; border-radius: 999px; background: #3fb37a"></span>online · 100.99.29.84</span>' + f'<span style="display: inline-flex; align-items: center; gap: 6px; font-family: {MONO}; font-size: 11px; color: {INK3}"><span style="width: 8px; height: 8px; border-radius: 999px; background: #c14545"></span>offline</span>' + f'<span style="display: inline-flex; align-items: center; gap: 6px; font-family: {MONO}; font-size: 11px; color: {INK3}"><span style="width: 8px; height: 8px; border-radius: 999px; background: #e08a3c"></span>connecting…</span>'
    menu = (f'<div style="width: 210px; padding: {NEST}px; border-radius: {R_SURFACE}px; background: {ELEV}; {SM_FLOAT}">{menu_item("pin", "Pin to top")}{menu_sep()}{menu_item("gear", "Open settings", hint="⌘,", highlight=True)}{menu_sep()}{menu_item("trash", "Delete workgroup…", danger=True)}</div>')
    dropdown = f'<div style="width: 260px; padding: {NEST}px; border-radius: {R_SURFACE}px; background: {ELEV}; {SM_FLOAT}">{dropdown_row("Default", "use provider default")}{dropdown_row("Medium", "balanced", True)}{dropdown_row("High", "slower, more thorough")}</div>'
    rows_spec = f'<div style="width: 100%; display: flex; flex-direction: column">{settings_row("home", mono12("~/.alpi/profiles/doc") + button("Reveal", "ghost", "sm"))}{settings_row("peers", selectish("0 peers · 0 online", mono=False) + button("Add peer", "ghost", "sm", "plus"))}{settings_row("delete", button("Delete profile", "danger-ghost", "sm"))}</div>'
    banner = (f'<div style="width: 100%; display: flex; flex-direction: column; gap: 8px">{banner_bar("danger", "alpi on this computer is not answering — reconnecting…", "Retry", "16px")}{banner_bar("warning", "This profile is paused. You can read the history; resume to chat.", "Resume", "16px")}'
              f'{banner_bar("info", "Connecting to casa…", pad="16px")}{banner_bar("success", "Connected to casa — syncing profiles…", pad="16px")}</div>'
              f'<div style="width: 100%">{alert_banner("Does not pass lint", "SKILL.md line 4 names a secret this skill does not own.", "Edit")}</div>')
    load_failed = (f'<div style="display: flex; flex-direction: column; align-items: center; gap: 12px; padding: 24px 16px; text-align: center; width: 100%"><span style="font-size: 15px; font-weight: 500; color: {INK}">Couldn’t load this conversation</span><span style="font-size: 12px; color: {INK3}">read timeout</span>{button("Retry", "secondary")}</div>'
                   f'<span style="display: inline-flex; align-items: center; gap: 8px; color: #b73737; font-size: 15px">Couldn’t load members {alink("Retry")}</span>')
    empty = f'<div style="display: flex; flex-direction: column; align-items: center; gap: 16px; padding: 24px; width: 100%; text-align: center">{wg_mark(INK3, 72)}<span style="font-size: 28px; font-weight: 600; letter-spacing: -0.02em">No workgroups yet</span><span style="font-size: 13px; color: {INK3}">A workgroup is a hub profile plus the members it directs.</span>{button("New workgroup", "primary", "md", "plus")}</div>'
    mbody = (f'<div style="display: flex; flex-direction: column; gap: 6px"><span style="font-size: 12px; color: {INK3}">Label</span>{ds_field("phone", 380)}</div>'
             f'<div style="display: flex; gap: 16px"><div style="display: flex; flex-direction: column; gap: 6px"><span style="font-size: 12px; color: {INK3}">Role</span>{dropdown_trigger("Member")}</div><div style="display: flex; flex-direction: column; gap: 6px"><span style="font-size: 12px; color: {INK3}">Sessions</span>{dropdown_trigger("Shared across its devices")}</div></div>')
    modal_spec = f'<div style="position: relative; width: 520px; height: 320px; border-radius: {R_SHEET}px; background: {SIDE}; overflow: hidden">{modal("Edit connection", mbody, dialog_footer("Save changes"), w=440, x=40, y=24)}</div>'
    confirm_body = (f'<span style="font-size: 15px; line-height: 1.5; color: {INK}">Permanently removes identity, memory, skills, schedule and chat history. This cannot be undone.</span>'
                    f'<div style="display: flex; flex-direction: column; gap: 8px; margin-top: 4px"><span style="display: flex; align-items: center; gap: 8px; font-size: 14px; font-weight: 500; color: {INK3}">Type <span style="font-family: {MONO}; font-size: 14px; font-weight: 600; color: {INK}; background: rgba(20,20,20,0.08); padding: 2px 8px; border-radius: {R_XS}px">doc</span> to confirm</span>{ds_field("d", 352)}</div>')
    confirm_spec = f'<div style="position: relative; width: 460px; height: 340px; border-radius: {R_SHEET}px; background: {SIDE}; overflow: hidden">{modal("Delete profile @doc", confirm_body, dialog_footer("Delete profile", variant="danger"), w=400, x=30, y=24)}</div>'
    body = f"""<div style="padding: 40px 48px; display: flex; flex-direction: column; gap: 22px; box-sizing: border-box">
{h1("Components · desktop", "Every primitive lives in desktop/src/primitives and paints with the .ds-* classes from design-system.css. One Button (IconBtn is its ghost iconOnly form) and one Tip; buttons and fields are 40 px (32 compact), pills to press and 12 px wells to type in, dialogs at radius 28 with a shared DialogFooter; one 4 · 8 · 12 · 16 · 24 · 32 · 48 space scale and 32 · 40 · 48 control heights; one focus-visible ring (2 px, offset 2, keyboard only); icons 16, 20 or 24 at a 1.5 rendered stroke; shortcuts show as KeyHint chips; menus and confirms register on useOverlay so Escape, focus and layering behave the same everywhere.")}
{specimen("Button · primary, secondary, ghost, danger, danger ghost · pills · sm 32 · md 40 · lg 40 · hero 48 · labels 500 · leading icon · action links", buttons)}
{specimen("Button iconOnly · round · sm 32 · md 40 · lg 40 · hero 48", icon_only)}
<div style="display: flex; gap: 22px; align-items: flex-start">{specimen("Tip · ink fill, 11 medium, chip radius 6, no edge, arrow", tip, 300)}{specimen("Usage tooltip · day, cost, in and out, surface 14, edge ring", usage_tip, 200)}{specimen("KeyHint · modifiers and key as Kbd chips, text when it is not a chord", keys, 560)}</div>
{specimen("Roster state chips · needs you · failed · working (pulses on --dur-loop) · workgroup phase · footer dots (bell and Activity: one plain danger dot, the count stays in the label)", states)}
{specimen("Chips, code chip, keys", chips)}
{specimen("Chart · a ```chart block in a reply, a notification or a workgroup post: line, bar (lying down when labels are long) and stacked bar, the first series in the profile’s accent, a comparison in ink", desktop_charts())}
{specimen("SettingsNav · section rail with search", rail)}
{specimen("Settings rows · a 15 px label with a 14 px sans description below and the control right, parted by space with no rule; add buttons carry a plus icon and a verb", rows_spec, 620)}
{specimen("Fields · 40 px on the fill at radius 12 with no edge, a 1.5 px inset ink3 line on focus · Textarea · Selectish and Dropdown field as pills · ds-seg (a pill track, inset 4, the chosen cell raised) · Checkbox at xs 6 and Radio: checked is one ink fill with its mark cut out, unchecked the edge outline that means off", fields)}
{specimen("States · one ladder: hover 4 % fades in on fast and out on exit, colour only; pressed 12 % instant; the primary steps 86 / 78 % toward the pane; focus is the 2 px ink ring at 60 % offset 2 on keyboard focus only; disabled 0.45; a well focuses with a 1.5 px inset ink3 line", ladder)}
{specimen("Field · invalid: the well keeps its fill and takes an inset 1.5 px danger line, kept while focused, and the message below is linked by aria-describedby", invalid)}
{specimen("Meters and status dots · every desktop dot is 8 px (--dot-md), on whole pixels", meters)}
{specimen("Sidebar footer · round 32 px icon buttons for Settings, Notifications, Activity and the theme, the version at the right", f'<div style="width: 248px; background: {SIDE}">{sidebar_footer(app_version("desktop"))}</div>', 280, SIDE)}
<div style="display: flex; gap: 22px; align-items: flex-start">{specimen("Context menu · surface 14 with a 4 px inset, 32 px items at control 10, groups parted by 8 px of space, the highlighted item on --selected with the ring inside, danger variant, 1 px edge ring", menu, 260)}{specimen("Dropdown menu · surface 14, inset 4, exactly 32 px rows at control 10 even with a caption, menuitemradio rows, 16 px check slot, caption inline, 1 px edge ring (a searchable one takes the large ring)", dropdown, 300)}{specimen("Banners · one flat square tint of the kind’s hue over the pane (10 % light, 14 % dark; info a 5 % / 6 % ink), no rule, ring or shadow, text at 14 px; a 16 px lead lane with the alert glyph in the kind’s text colour for danger and warning, the ink-3 dot for info, the success dot for success; the action plain text in the kind’s text colour · AlertBanner below: the danger tint, lead ink, detail ink-2, action as text", banner, 560)}</div>
<div style="display: flex; gap: 22px; align-items: flex-start">{specimen("Modal 520 · sheet 20 · title 18 · 24 px padding · content scrolls · DialogFooter on the dialog's own surface, no seam (ghost Cancel, primary) · large ring", modal_spec, 552, SIDE)}{specimen("ConfirmDelete · typed only for irreversible deletes · waits for the delete", confirm_spec, 492, SIDE)}</div>
{specimen("Toast · raised with the float shadow, radius 20, 15 px text, 8 px dot, errors persist with a Dismiss and Retry, two lines · information fades", toast_box("Could not forget the connection: the daemon refused the request for this device", "#c14545", "Retry", True) + toast_box("Reasoning effort saved", "#3fb37a"))}
{specimen("NotificationBody · a digest as entries (name, address in mono, text) · a failed run as a flat card: red on the mark and the word failed, facts, trace folded under Details, Run again and Open job", notification_reader(420))}
{specimen("Waiting · Busy for a page or a section, SpinnerIcon inside controls, skeleton bones that breathe for lists, readers and the usage widget", waiting())}
<div style="display: flex; gap: 22px; align-items: flex-start">{specimen("LoadFailed · card and inline (role alert)", load_failed, 420)}{specimen("EmptyState · glyph, display heading, subtitle, one primary action with a plus icon (the empty roster and workgroups)", empty, 620)}</div>
</div>"""
    return page("System · desktop components", 1280, DESKTOP_COMPONENTS_H, body)


def mobile_components_board():
    buttons = "".join(m_button(t, v, "lg") for t, v in (("Primary", "primary"), ("Secondary", "secondary"), ("Ghost", "ghost"), ("Danger", "danger"), ("Danger ghost", "danger-ghost"))) + m_button("md", "secondary", "md") + m_button("sm", "secondary", "sm")
    rows = f'<div style="width: 414px">{m_group(m_row("Reasoning effort", "how hard the model thinks", "Medium"), m_row("Paused", "paused profiles can’t be chatted", control=switch(False, DOC_ACCENT, "Paused"), chevron=False), m_row("Delete profile", "cannot be undone", danger=True, sep=False))}</div>'
    wide = f'<div style="width: 560px; padding: 12px 0">{m_group(m_row("Default model", "", "deepseek-v4.1-flash"), m_row("Sandbox", "wraps shell tools", control=switch(True, DOC_ACCENT, "Sandbox"), chevron=False), m_row("Workspace", "", "/data/workspace/doc", sep=False))}</div>'
    pills = pill("on", True) + pill("off") + pill("warning", tone="warning") + pill("error", tone="danger") + pill("2 sessions", tone="success") + meter("$0.40", "/$5.00", 0.08) + meter("24K", "/1.0M", 0.024)
    fields = (f'<div style="width: 300px; display: flex; flex-direction: column; gap: 6px"><div style="height: 44px; box-sizing: border-box; border-radius: {R_CONTROL}px; background: var(--field, #f2f2f2); box-shadow: inset 0 0 0 1.5px #6b6b6b; display: flex; align-items: center; padding: 0 14px; font-size: 15px">phone</div><span style="font-size: 12px; color: #6b6b6b">Helper text, 12 pt sans in the secondary ink</span></div>'
              f'<div style="width: 300px; display: flex; flex-direction: column; gap: 6px"><div style="height: 44px; box-sizing: border-box; border-radius: {R_CONTROL}px; box-shadow: inset 0 0 0 1px #c14545; background: var(--field, #ececec); display: flex; align-items: center; padding: 0 12px; font-family: {MONO}; font-size: 14px">abc</div><span role="alert" style="font-size: 12px; color: {DANGER}">Enter a number, or leave it empty for no cap</span></div>{switch(True, DOC_ACCENT)}{switch(False, DOC_ACCENT)}')
    picker = f'<div style="width: 360px; border-radius: {R_SURFACE}px; overflow: hidden">{picker_row("Low", "fastest, cheapest")}{separator()}{picker_row("Medium", "balanced", selected=True)}{separator()}{picker_row("High", "slower, more thorough")}</div>'
    actions = f'<div style="width: 360px; border-radius: {R_SURFACE}px; overflow: hidden">{action_item("gear", "Profile settings")}{separator(52)}{action_item("bell", "Auto-read replies", toggle=True)}{separator(52)}{action_item("x", "Delete profile…", danger=True)}</div>'
    sheet_spec = f'<div style="width: 390px; border-radius: {R_SHEET}px {R_SHEET}px 0 0; background: var(--bg-elev, #ffffff); overflow: hidden; {SHEET_EDGE}">{sheet_header("Reasoning effort", "how hard the model thinks before answering")}<div style="padding: 0 0 8px">{picker_row("Medium", "balanced", selected=True)}</div><div style="display: flex; gap: 10px; padding: 20px 16px 24px"><span style="flex: 1; display: flex">{m_button("Not now", "ghost", "lg").replace("border-radius: 999px", "border-radius: 999px; width: 100%")}</span><span style="flex: 1; display: flex">{m_button("Save", "primary", "lg").replace("border-radius: 999px", "border-radius: 999px; width: 100%")}</span></div></div>'
    confirm = (f'<div style="width: 360px">{m_confirm_dialog("Delete profile @doc", "Permanently removes identity, memory, skills and chat history.", "Delete profile", typed="doc")}</div>'
               f'<div style="width: 360px">{m_confirm_dialog("Restart the daemon", "Every connected client briefly loses its socket.", "Restart", tone="neutral")}</div>'
               f'<div style="width: 360px">{m_confirm_dialog("Changed elsewhere", "This file changed since you opened it. Overwrite it with your edits, or reload it and discard them?", "Overwrite", alternate="Reload (discard)", cancel="Keep editing")}</div>'
               f'<div style="width: 360px">{m_confirm_dialog("Pair with this daemon?", "This link was opened from outside the app. Pair only if you created it: casa · wss://casa.example.net", "Pair", tone="neutral")}</div>')
    toast = (f'<div style="position: relative; width: 360px; height: 84px">{m_toast("Deleted 3 notifications", action="Undo", bottom=0)}</div>'
             f'<div style="position: relative; width: 360px; height: 112px">{m_toast("The daemon refused the request for this device.", kind="danger", title="Save failed", retry=True, dismiss=True, bottom=0)}</div>')
    banners = (f'<div style="width: 360px">{m_banner("Daemon unreachable. Reconnecting…", "Retry", "danger", secondary="Manage")}</div>'
               f'<div style="width: 360px">{m_banner("This profile is paused. You can read the history.", "Resume", "warning")}</div>')
    empty = f'<div style="width: 360px; display: flex; flex-direction: column">{m_empty_state("Nothing running", "Running turns, workgroup phases and anything waiting on you show up here.")}</div><div style="width: 360px; display: flex; flex-direction: column">{m_empty_state("Couldn’t load schedule", "Cannot reach the daemon.", "Retry")}</div>'
    load_failed = f'<div style="width: 360px; display: flex; align-items: center; gap: 10px; padding: 14px 16px"><span style="flex: 1; font-size: 14px; font-weight: 500; color: {DANGER}">Couldn’t load email accounts</span>{m_button("Retry", "secondary", "sm")}</div>'
    from conversation_boards import m_mention_chip, m_model_chip, m_tool
    m_scale = [("meta", 12), ("small", 14), ("ui", 15), ("chat", 16), ("title", 20), ("display", 28)]
    m_types = "".join(f'<div style="display: flex; align-items: baseline; gap: 14px"><span style="width: 96px; font-family: {MONO}; font-size: 11px; color: {INK3}">{n} · {px}</span><span style="font-size: {px}px; line-height: 1.2; font-weight: {600 if n in ("title", "detail", "display") else 400}; letter-spacing: {"-0.018em" if n == "detail" else "0"}; color: {INK}">{"Chat text reads at 16" if n == "chat" else "Made for the thumb"}</span></div>' for n, px in m_scale)
    m_types = f'<div style="display: flex; flex-direction: column; gap: 8px">{m_types}<span style="font-size: 12px; color: {INK3}">the six steps of the shared type ladder, chat reading at 16 on both clients; section labels are 14 sans in ink3, sentence case; mono only for machine text; every size follows the text-size setting</span></div>'
    seg = f'<div style="width: 360px; border-radius: {R_SURFACE}px; overflow: hidden; background: var(--card)">{m_row_below("Theme", "", m_segmented(("System", "Light", "Dark"), "System"))}{m_row_below("Text size", "multiplies your OS text size", m_segmented(("Small", "Default", "Large", "Largest"), "Default"), sep=False)}</div>'
    popover = f'<div style="position: relative; width: 360px; height: 190px"><span style="position: absolute; right: 0; top: 0; width: 44px; height: 44px; display: inline-flex; align-items: center; justify-content: center">{mi("more", 16, INK2)}</span><div style="position: absolute; right: 0; top: 50px; width: 280px; padding: 4px 0; padding: {NEST}px; border-radius: {R_SURFACE}px; background: var(--bg-elev, #ffffff); overflow: hidden; {FLOAT_EDGE}">{action_item("gear", "Profile settings")}{action_item("bell", "Auto-read replies", toggle=False)}{action_item("x", "Delete profile…", danger=True)}</div></div>'
    row_states = f'<div style="display: flex; gap: 22px; align-items: center">{m_row_state("needs-you")}{m_row_state("failed")}{m_row_state("working", profile=DOC_ACCENT)}{m_row_state("working", "2/4", DOC_ACCENT)}</div>'
    roster = (f'<div style="width: 300px; padding: 6px 0; border-radius: {R_SURFACE}px; background: {SIDE}">{m_roster_row("abby", "#c33d7e", state="needs-you")}{m_roster_row("alpha", DOC_ACCENT, "workgroup", state="working", phases="2/4")}{m_roster_row("yuri", "#f0a58f", ts="6w", unread=True)}{m_roster_row("doc", DOC_ACCENT, selected=True)}{m_roster_row("galt", "#3ac9f3", paused=True)}</div>'
              f'<div style="width: 390px; border-radius: {R_SURFACE}px; overflow: hidden">{m_roster_row("clonara", "#e2704a", state="failed", compact=False)}</div>')
    badges = (f'<span style="position: relative; display: inline-flex; margin: 8px">{ic("role:notifications", 16, INK2)}{m_bell_dot()}</span>'
              f'<span style="position: relative; display: inline-flex; margin: 8px">{ic("role:activity", 16, INK2)}{m_bell_dot()}</span>'
              f'<span style="position: relative; display: inline-flex; margin: 8px">{ic("role:activity", 16, "#454545")}{m_count_badge(2, "danger", "#ffffff")}</span>'
              f'<span style="font-size: 12px; color: {INK3}">footer: bell and Activity draw a plain danger dot, the count stays in the label; the count shape (2 here, capped at 9+) serves the attention pill</span>')
    targets = ('<div style="display: flex; gap: 18px; align-items: center">'
               + "".join(f'<span style="display: inline-flex; flex-direction: column; align-items: center; gap: 6px"><span style="width: {w}px; height: {h}px; border-radius: 4px; background: {HOVER}; border: 0.5px dashed {LINE2}; display: inline-flex; align-items: center; justify-content: center">{ic(i, 16, INK2) if i else ""}</span><span style="font-family: {MONO}; font-size: 11px; color: {INK3}">{t}</span></span>'
                         for w, h, i, t in ((44, 44, "gear", "tap 44"), (36, 36, "search", "chrome 36 + slop"), (80, 44, "", "row 44"), (120, 48, "", "button 48")))
               + '</div>')
    tools = f'<div style="width: 390px; border-radius: {R_SURFACE}px">{m_tool("read_file", "labs/2026-08-lipids.pdf")}{m_tool("shell", "src/app.ts:14  no-unused-vars", "failed")}{m_tool("web_fetch", "status.example.com", "running")}</div>'
    jump = f'<span style="display: inline-flex; align-items: center; gap: 8px; height: 36px; padding: 0 14px; border-radius: {R_CONTROL}px; background: var(--bg-elev, #ffffff); {FLOAT_EDGE}; font-size: 12px; font-weight: 500; color: {INK2}">{ic("chev-d", 14, INK2)}Latest</span>'
    shell = (f'<div style="width: 300px; border-radius: {R_SURFACE}px; overflow: hidden; background: #f6f6f6">{m_conn_header()}{m_shell_footer(border=True)}</div>'
             f'<div style="width: 300px; display: flex; flex-direction: column; border-radius: {R_SURFACE}px; overflow: hidden; background: #f6f6f6">{"".join(m_conn_header(status=st) for st in ("offline", "connecting", "auth-failed", "disabled"))}</div>'
             f'<div style="width: 300px; border-radius: {R_SURFACE}px; overflow: hidden; background: #f6f6f6; align-self: flex-start">{m_shell_footer(border=True, icons_only=True)}</div>')
    body = f"""<div style="padding: 40px 48px; display: flex; flex-direction: column; gap: 22px; box-sizing: border-box">
{h1("Components · phone and Fold", "Every primitive lives in mobile/src/components and reads the same tokens through useTheme(). Every target is at least 44 pt and controls are 48, roster rows 64 with 40 pt marks, chat text at 16, and no hairline anywhere. On a fold or tablet the same rows and cards sit in a column of at most 560, the header is chat-style, a sheet opens as a centred 560 dialog and an action sheet as a popover under its trigger.")}
<div style="display: flex; gap: 22px; align-items: flex-start">{specimen("Type scale · mobile", m_types, 560)}{specimen("Targets · 44 pt minimum, 48 pt controls", targets, 600)}</div>
{specimen("Buttons · pills · lg 48 · md 48 · sm 44 · hero 56 · haptic on press · labels 500 · disabled fades to 45 % · loading keeps the label beside the spinner", buttons)}
<div style="display: flex; gap: 22px; align-items: flex-start">{specimen("RowState · needs you · failed · working · phases in mono", row_states, 560)}{specimen("Model chip and mention chip · pills, one height (36) · the model gives way before the effort · @ mention is a chip too", m_mention_chip() + m_model_chip("deepseek-v4.1-flash · medium"), 600)}</div>
{specimen("Roster rows · Fold compact 44 with a 24 pt mark and phone 64 with a 40 pt mark and a preview · selected: the neutral 8 % fill only · paused: faded with a label", roster)}
{specimen("ConnHeader (44 pt or more, the status dot sits on the corner of the connection icon with a 1.5 pt ring, and trouble is said in words: offline · retrying…, connecting…, sign-in failed, disabled) and ShellFooter (destinations only, sharing the full width on the phone, with no version: Settings shows it; on the Fold sidebar 44 pt icons and the version as plain mono ink3 text at the right; Settings, Notifications with a danger dot (owners), Activity with a danger dot; the theme lives in Settings → Appearance; the last specimen is the icon-only form: always on the Fold sidebar, and on the phone only when a slot is narrower than the widest label at the current text size, labels kept as accessibility labels)", shell)}
<div style="display: flex; gap: 22px; align-items: flex-start">{specimen("ToolCallRow · 44 pt, family icon, tap opens the sheet", tools, 422)}{specimen("CountBadge · 18 pt pill, no ring, overlapping the glyph", badges, 400)}</div>
<div style="display: flex; gap: 22px; align-items: flex-start">{specimen("Row · phone (15 label, 14 sans description, one trailing lane for the chevron, danger) inside one fill group at radius 20, no rule between rows", rows, 422)}{specimen("Fold and tablet settings · the same RowGroup cards in a column of at most 560, left aligned", wide, 592)}</div>
{specimen("Chart · the same blocks at phone width; ticks that would crowd thin out, labels are never cut", phone_charts())}
{specimen("Pill (32 pt on the fill, an 8 pt dot, a 14 pt sans label; delivery failure is the danger pill blocked), OnOff, Meter, Toggle (optimistic, snaps back on failure; biometric unlock is one)", pills + pill("blocked", tone="danger") + switch(True, DOC_ACCENT) + switch(False, DOC_ACCENT))}
{specimen("Field · 48 high on the fill at radius 12, no edge · a 1.5 pt inset ink3 line when focused · a 1.5 pt danger line when invalid · disabled fades to 45 % · helper and error 14 pt sans (error in dangerText)", fields)}
<div style="display: flex; gap: 22px; align-items: flex-start">{specimen("PickerRow · 56 pt rows at radius 12, label and description, the chosen one on the neutral fill with a check", picker, 392)}{specimen("ActionSheet items · 52 pt rows, 24 pt icon slot, sans detail, danger · a switch row keeps the sheet open", actions, 392)}</div>
<div style="display: flex; gap: 22px; align-items: flex-start">{specimen("Sheet · raised at radius 28 on top with the float shadow, a grabber, a 20 pt title, a sans subtitle, X · on the fold: a centred dialog at radius 28, no grabber · primaryAction [secondary, primary] · dismissible=false for decisions", sheet_spec, 422, SIDE)}{specimen("ConfirmDialog · raised at radius 28 with the float shadow, 20 pt title · danger + typed field for deletes · neutral without it for reversible actions · an optional secondary third action between confirm and cancel", confirm, 400, SIDE)}</div>
<div style="display: flex; gap: 22px; align-items: flex-start">{specimen("Toast · raised with the float shadow at radius 20, 15 pt text, bottom, above the edge · wraps to two lines · errors last 6 s with a 44 pt Dismiss, and stay while Retry is offered", toast, 392)}{specimen("Banner · one flat square tint of the kind’s hue, no rule or radius; the alert glyph in the kind’s text colour, the action text in that colour on a 44 pt target, alert role · daemon states and paused", banners, 392)}{specimen("JumpToLatest · raised with the float shadow", jump, 200)}</div>
<div style="display: flex; gap: 22px; align-items: flex-start">{specimen("Segmented · theme (System, Light, Dark) and text size (Small, Default, Large, Largest) as rows with the control below, a pill track with the chosen cell raised", seg, 392)}{specimen("ActionSheet on the fold · a 280 pt popover under its trigger at radius 20, right edges aligned, no veil, no title, raised with the float shadow", popover, 392)}</div>
{specimen("Waiting · Busy for a page or a section, the Spinner arc inside controls, breathing skeleton bones inside the cards they will fill, the usage widget as its own silhouette · no ActivityIndicator", waiting(mobile=True))}
<div style="display: flex; gap: 22px; align-items: flex-start">{specimen("EmptyState · title 18, one sentence in the secondary ink, an optional secondary button, centred · Activity, notifications, schedule, roster, LoadFailed card", empty, 780)}{specimen("LoadFailed · inline row (alert role)", load_failed, 392)}</div>
{specimen("NotificationBody · digest entries · a failed run as a flat card on the group tone, Details folds at 44 pt, Run again and Open job", notification_reader(360, 14, mobile=True))}
</div>"""
    return page("System · mobile components", 1280, MOBILE_COMPONENTS_H, body)


TOKENS_H = 3760
DESKTOP_COMPONENTS_H = 4110
MOBILE_COMPONENTS_H = 6180

DESKTOP_MOTION = [
    ("Hover, press, tooltip", "--dur-1 · 120 ms", "colour and opacity only"),
    ("New turn", "--dur-2 · 200 ms", "rises 8 px and fades in; only turns appended after the thread is on screen"),
    ("Streaming text", "150 ms", "only the newest chunk fades; nothing already shown re-animates"),
    ("Steps and reasoning open", "--dur-2 · 200 ms", "grid-rows reveal; reasoning folds itself when the answer lands"),
    ("Menus, popovers, dialogs, toasts in", "--dur-enter · 180 ms", "fade only on the enter curve; no rise and no scale"),
    ("Modal and dialog exit", "--dur-exit · 130 ms", "fade only on the exit curve; a timer closes it if the animation never ends"),
    ("Easing", "enter (.2, .7, .2, 1) · exit (.8, 0, .8, .3)", "one pair of curves for everything that enters or leaves"),
    ("Working pulse, dots", "--dur-loop · 1.4 s", "a phase or a profile at work; the only loop that carries a profile colour"),
    ("Busy mark", f"{BUSY_TURN_S} s turn", "Twin busy for a page or section wait: after 300 ms, at least 400 ms on screen; still below 20 px and under reduced motion"),
    ("Spinner", f"--dur-spin · {DUR_SPIN} s", "SpinnerIcon, a dashed circle inside Button, Chip, the stopping Send, attachments and read aloud"),
    ("Skeleton breath", f"{BREATH_S} s · {STAGGER_MS} ms apart", "opacity 0.55 ↔ 1 over bones in the 7 % line ink; static under reduced motion"),
    ("Reduced motion", "global rule", "one prefers-reduced-motion rule stops every animation and transition"),
]
MOBILE_MOTION = [
    ("New message", "enter · 180 ms", "only rows that arrive after the first page fade in; recycled rows never fade again"),
    ("Pane replace", "120 ms crossfade", "Fold and tablet two-pane navigation"),
    ("Sidebar open and close", "enter 180 · exit 130 ms", "the Fold and tablet roster slides and narrows instead of snapping"),
    ("Thought, group, step", "enter · 180 ms", "opening and closing measure the height and fade the content"),
    ("Latest button", "enter 180 · exit 130 ms", "fades in with an 8 pt rise when the reader scrolls away"),
    ("Sheet in and out", "enter 180 · exit 130 ms", "drag to dismiss on the header when the sheet is dismissible"),
    ("Dialog and toast", "enter 180 · exit 130 ms", "the dialog fades and scales from 0.96; the toast slides and fades"),
    ("Easing", "enter (.2, .7, .2, 1) · exit (.8, 0, .8, .3)", "one pair of curves for everything that enters or leaves"),
    ("Keyboard", "frame by frame", "the composer rides the keyboard with useAnimatedKeyboard; swipe down dismisses"),
    ("Long press", "350 ms · pulse 160 ms", "nothing moves on a tap or a scroll; only a recognised long press pulses once with the haptic as the menu opens"),
    ("Working pulse", "pulse · 1600 ms", "roster state dot and thinking dots dip to 0.4 opacity and back; static under reduce motion"),
    ("Busy mark", f"{BUSY_TURN_S} s turn", "Twin busy for a page or section wait: after 300 ms, at least 400 ms on screen; still under reduce motion"),
    ("Spinner", f"{SPINNER_TURN_MS} ms turn", "a 270° arc inside Button, attachment cards, rich text images, the member sheet and the model sheets; RefreshControl stays the system gesture"),
    ("Skeleton", f"{BREATH_S} s breath", f"bones in the 7 % line ink, opacity 0.4 ↔ 1, rows {STAGGER_MS} ms apart; static under reduce motion"),
    ("Reduce motion", "one shared value", "every fade, pulse and breath reads one app-wide setting"),
]
HAPTICS = [
    ("tap", "light impact", "send, stop"),
    ("selection", "selection tick", "long press, pull to refresh, action sheet open, toggles, roster create buttons"),
    ("warning", "warning notification", "an approval or a question sheet opens; a destructive typed confirm"),
    ("success", "success notification", "available for confirmations; unused today"),
]


def motion_board():
    def table(rows, cols="200px 170px 1fr"):
        return "".join(
            f'<div style="display: grid; grid-template-columns: {cols}; gap: 14px; padding: 9px 0; border-top: 0.5px solid {LINE}; align-items: baseline">'
            f'<span style="font-size: 13px; color: {INK}">{a}</span><span style="font-family: {MONO}; font-size: 12px; color: {INK2}">{b}</span><span style="font-size: 12.5px; line-height: 1.5; color: {INK3}">{c}</span></div>'
            for a, b, c in rows)
    body = f"""<div style="padding: 40px 48px; display: flex; flex-direction: column; gap: 22px; box-sizing: border-box">
{h1("Motion and feel", "Still boards cannot move, so this page states what moves, for how long and what it answers to. Motion marks change: a new turn, the streaming edge, a step opening, the keyboard. Nothing loops except the working pulse, the brand busy wave, the control spinner and the skeleton breath, and reduced motion turns it all off.")}
<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 28px; align-items: start">
<div style="display: flex; flex-direction: column">{label("Desktop")}<div style="height: 8px"></div>{table(DESKTOP_MOTION, "170px 140px 1fr")}</div>
<div style="display: flex; flex-direction: column">{label("Phone and Fold")}<div style="height: 8px"></div>{table(MOBILE_MOTION, "150px 130px 1fr")}</div>
</div>
<div style="display: flex; flex-direction: column">{label("Haptics · src/lib/haptics.js")}<div style="height: 8px"></div>{table(HAPTICS, "120px 180px 1fr")}</div>
</div>"""
    return page("System · motion and feel", 1280, 1340, body)


SYSTEM = {"tokens": tokens_board, "motion": motion_board, "desktop": desktop_components_board, "mobile": mobile_components_board}
