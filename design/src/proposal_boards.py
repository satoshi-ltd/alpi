import re

from desktop_boards import DANGER, HOVER, INK, INK2, INK3, LINE, MONO, PANE, banner_bar, button, chip, ic as dic
from gen import FLOAT_EDGE, m_banner, m_confirm_dialog, m_count_badge, m_toast, mi, pill
from mobile_overlays import backdrop
from panel_kit import alert_banner, phone_banner

PHONE_W = 390
ELEV = "var(--bg-elev, #ffffff)"
EDGE_LG = "box-shadow: 0 0 0 1px EDGE_LG"
RING_LG = "box-shadow: 0 0 0 1px #b4b4b4"
LIGHT = {"EDGE_LG": "#b4b4b4", "ON_INK": "#ffffff", "SCREEN": "#ffffff", "CARD_M": "#f4f4f4"}
DARK = {"SCREEN": "#0b0b0b", "CARD_M": "#151515", "var(--bg-elev, #ffffff)": "#202020", "var(--field)": "#1f1f1f", "background: #ffffff": "background: #151515", "#f6f6f6": "#0f0f0f", "#ececec": "#0b0b0b",
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


def d_pill(text, warn=False):
    bg = f"color-mix(in srgb, {WARNING} 16%, {PANE})" if warn else HOVER
    dot = f'<span style="width: 8px; height: 8px; border-radius: 999px; background: {WARNING if warn else "#3fb37a"}"></span>'
    return (f'<span style="display: inline-flex; align-items: center; gap: 6px; height: 24px; padding: 0 8px; border-radius: 2px; background: {bg}; '
            f'font-family: {MONO}; font-size: 11px; color: {INK}">{dot}{text}</span>')


def d_status_pill(text, color):
    return (f'<span style="display: inline-flex; align-items: center; gap: 6px; padding: 4px 8px; border-radius: 2px; background: {HOVER}; '
            f'font-family: {MONO}; font-size: 11px; color: {INK2}"><span style="width: 6px; height: 6px; border-radius: 999px; background: {color}"></span>{text}</span>')


def d_flag(value, mono=True):
    return (f'<span style="display: inline-block; min-width: 14px; height: 14px; padding: 0 4px; box-sizing: border-box; border-radius: 4px; background: {DANGER_FILL}; '
            f'font-family: {MONO if mono else "Geist, sans-serif"}; font-size: 11px; font-weight: 600; line-height: 14px; text-align: center; color: #ffffff">{value}</span>')


def chips_now_desktop():
    inner = stack(labelled("Chip", hrow(chip("running", "on"), chip("needs you", "warn"), chip("paused", "off"), chip("failed", "error"))),
                  labelled("ds-pill", hrow(d_pill("running"), d_pill("needs you", warn=True))),
                  labelled("StatusPill", hrow(d_status_pill("running", "#3fb37a"), d_status_pill("needs you", WARNING))),
                  labelled("Count badge", hrow(d_flag("3"))), gap=16)
    return desk_panel(inner, h=250)


def chips_proposed_desktop():
    inner = stack(labelled("Chip · the one family", hrow(chip("running", "on"), chip("needs you", "warn"), chip("paused", "off"), chip("failed", "error"))),
                  labelled("Count badge · --badge-size 14, mono", hrow(d_flag("3"))),
                  caption("ds-pill and StatusPill render through Chip: 24 px, 8 px dot, warn untinted."), gap=16)
    return desk_panel(inner, h=150)


def m_pill2(text, tone):
    bg, fg, dot = {"success": ("rgba(63,179,122,0.16)", "#217a45", "#3fb37a"), "warning": (HOVER, INK, WARNING), "off": (HOVER, INK2, INK3), "danger": ("rgba(193,69,69,0.16)", DANGER, DANGER_FILL)}[tone]
    return (f'<span style="display: inline-flex; align-items: center; gap: 8px; min-height: 24px; padding: 0 8px; box-sizing: border-box; border-radius: 2px; background: {bg}; opacity: {0.55 if tone == "off" else 1}; '
            f'font-family: {MONO}; font-weight: 500; font-size: 11px; line-height: 1.3; color: {fg}"><span style="width: 8px; height: 8px; border-radius: 999px; background: {dot}"></span>{text}</span>')


def m_badge_block(badge):
    return f'<span style="align-self: flex-start; position: relative; display: inline-flex; margin: 10px 14px 0 0">{mi("bell", 20, INK2)}{badge}</span>'


def chips_now_mobile():
    inner = stack(labelled("Pill · 22 pt, 6 pt dot, mono 12", hrow(pill("running", on=True), pill("needs you", tone="warning"), pill("paused"), pill("failed", tone="danger"))),
                  labelled("Count badge · 18 pt, sans 600", m_badge_block(m_count_badge(3))), gap=20)
    return phone_panel(inner, 150)


def chips_proposed_mobile():
    badge = m_count_badge(3).replace("font-weight: 600;", f"font-family: {MONO}; font-weight: 600;")
    inner = stack(labelled("Pill · 24 pt, 8 pt dot, mono 11", hrow(m_pill2("running", "success"), m_pill2("needs you", "warning"), m_pill2("paused", "off"), m_pill2("failed", "danger"))),
                  labelled("Count badge · 18 pt, mono 600", m_badge_block(badge)), gap=20)
    return phone_panel(inner, 150)


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
        id="DS.STATUS-CHIPS", client="mobile · desktop", area="State chips and count badges",
        title="One chip rule on both clients: 24 px, 8 px dot, mono label, warn untinted",
        why=("Desktop has three state-chip primitives with three rules: <code>Chip</code> (24 px, 8 px dot, warn untinted, tested), <code>.ds-pill</code> (warn tinted 16 %, <code>design-system.css:155</code>) and <code>StatusPill</code> (6 px dot, 4/8 padding, <code>StatusPill.module.css:8-11</code>). "
             "The phone's <code>Pill</code> says it keeps in step with <code>Chip</code> (<code>Pill.jsx:15</code>) but draws a 6 pt dot at 22 pt with a 12 pt label (<code>:31,38,42</code>). The count badge is 14 px mono on desktop with a <code>--badge-size</code> token nobody reads (<code>BrowseModal.module.css:235-248</code>, <code>tokens.css:104</code>) and 18 pt sans on the phone (<code>CountBadge.jsx:9-11</code>), and the kit draws a third one. "
             "The proposal makes <code>Chip</code> the rule: desktop's two other primitives render through it, the phone's Pill takes the 8 pt dot, 24 pt and the 11 pt mono label, and <code>common/countBadge.mjs</code> fixes the badge as mono 600 at 14 px / 18 pt."),
        mobile=(chips_now_mobile, chips_proposed_mobile),
        desktop=(chips_now_desktop, chips_proposed_desktop),
        accept=("desktop tests assert <code>.ds-pill</code> and <code>StatusPill</code> define no rules of their own and <code>.flag</code> reads <code>--badge-size</code>; <code>Pill.test.jsx</code> asserts dot <code>dotScale.md</code>, <code>minHeight</code> 24 and the mono 11 label; "
                "<code>CountBadge.test.jsx</code> and <code>tests/test_design_kit.py</code> read the badge spec from <code>common/countBadge.mjs</code>; the kit's <code>attention_value</code> is regenerated."),
        h=1000,
    ),
]
