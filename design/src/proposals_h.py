from desktop_boards import DANGER, HOVER, INK, INK2, INK3, INK4, LINE, LINE2, MONO, PANE, SELECTED, banner_bar, button, chip, field_input, ic as dic, row, seg, section
from gen import DOC_ACCENT, FIELD, FLOAT_EDGE, WELL, m_banner, m_button, m_confirm_dialog, m_count_badge, m_group, m_row, m_segmented, m_toast, meter as m_meter, mi, pill
from mobile_overlays import backdrop
from panel_kit import alert_banner, phone_banner

PHONE_W = 390
SCALE = 0.68
ELEV = "var(--bg-elev, #ffffff)"
RING_LG = "box-shadow: 0 0 0 1px #b4b4b4"
WARNING = "#e08a3c"
DANGER_FILL = "#c14545"
FILTERS = ("All", "Needs you", "Failing", "Running")


def stage(inner, w, h, bg="#f6f6f6"):
    return f'<div style="position: relative; width: {w}px; height: {h}px; border-radius: 12px; background: {bg}; border: 0.5px solid {LINE}; overflow: hidden; flex-shrink: 0">{inner}</div>'


def phone(inner, h, bg="#ececec"):
    frame = stage(inner, PHONE_W, h, bg)
    return (f'<div style="width: {PHONE_W * SCALE:.0f}px; height: {h * SCALE:.0f}px; overflow: hidden; flex-shrink: 0">'
            f'<div style="width: {PHONE_W}px; height: {h}px; transform: scale({SCALE}); transform-origin: top left">{frame}</div></div>')


def pair(*items):
    return f'<div style="display: flex; gap: 16px; align-items: flex-start; flex-wrap: wrap">{"".join(items)}</div>'


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


def m_segmented_ink(options, value):
    cells = "".join(
        f'<span role="radio" aria-checked="{"true" if o == value else "false"}" style="flex: 1; min-height: 44px; padding: 0 2px; box-sizing: border-box; display: inline-flex; align-items: center; justify-content: center; border-radius: 4px; '
        f'background: {INK if o == value else "transparent"}; font-size: 14px; font-weight: {600 if o == value else 400}; color: {PANE if o == value else INK2}">{o}</span>' for o in options)
    return f'<div role="radiogroup" style="display: flex; padding: 2px; border-radius: 4px; background: {SELECTED}">{cells}</div>'


def segmented_now_mobile():
    return phone_panel(labelled("Activity", m_segmented(FILTERS, "Needs you")), 140)


def segmented_proposed_mobile():
    return phone_panel(labelled("Activity", m_segmented_ink(FILTERS, "Needs you")), 140)


def segmented_now_desktop():
    return desk_panel(labelled("Workgroups", seg(FILTERS, "Needs you")), h=110)


def floating_mobile(elevated):
    dialog = m_confirm_dialog("Delete doc?", "Its sessions and memory go with it. Skills and knowledge stay.", "Delete", typed="doc", value="doc", ready=True)
    toast = m_toast("Draft saved.", "info", dismiss=True, bottom=24)
    if elevated:
        dialog = dialog.replace(f"background: #ffffff; {FLOAT_EDGE}", f"background: {ELEV}; {RING_LG}")
        toast = toast.replace(f"background: #ffffff; {FLOAT_EDGE}", f"background: {ELEV}; {RING_LG}")
    body = f'{backdrop(PHONE_W, 640)}<div style="position: absolute; left: 24px; right: 24px; top: 72px">{dialog}</div>{toast}'
    return phone(f'<div style="height: 100%; background: {PANE}">{body}</div>', 640)


def floating_now_mobile():
    return floating_mobile(False)


def floating_proposed_mobile():
    return floating_mobile(True)


def floating_now_desktop():
    modal = (f'<div style="width: 420px; padding: 24px; box-sizing: border-box; border-radius: 4px; background: {ELEV}; box-shadow: var(--shadow-edge-lg, 0 0 0 1px #b4b4b4); display: flex; flex-direction: column; gap: 12px">'
             f'<span style="font-size: 18px; font-weight: 600; color: {INK}">Delete doc?</span><span style="font-size: 13px; line-height: 1.5; color: {INK2}">Its sessions and memory go with it. Skills and knowledge stay.</span>'
             f'<div style="display: flex; justify-content: flex-end; gap: 8px; margin-top: 8px">{button("Cancel", "ghost")}{button("Delete", "danger")}</div></div>')
    veil = f'<div style="position: absolute; inset: 0; background: color-mix(in srgb, #ffffff 72%, transparent)"></div>'
    return stage(f'<div style="height: 100%; background: {PANE}">{veil}<div style="position: absolute; left: 60px; top: 40px">{modal}</div></div>', 540, 260)


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
    return phone_panel(inner, 280)


def banners_proposed_mobile():
    inner = stack(labelled("Status banner", m_banner(PAUSED, "Resume", kind="warning")), labelled("Alert banner · Memory panel", m_alert_tinted(MEMORY_LEAD, MEMORY_DETAIL)), gap=20)
    return phone_panel(inner, 280)


def banners_now_desktop():
    inner = stack(labelled("Status banner", stack(banner_bar("warning", PAUSED, "Resume", pad="16px"), banner_bar("info", "Reconnecting…", pad="16px"), gap=8)),
                  labelled("Alert banner · Memory panel", alert_banner(MEMORY_LEAD, MEMORY_DETAIL)), gap=20)
    return desk_panel(inner, h=250)


def banners_proposed_desktop():
    inner = stack(labelled("Status banner", stack(banner_bar_icon("warning", PAUSED, "Resume"), banner_bar("info", "Reconnecting…", pad="16px"), gap=8)),
                  labelled("Alert banner · Memory panel", d_alert_banner(MEMORY_LEAD, MEMORY_DETAIL, DANGER)), gap=20)
    return desk_panel(inner, h=250)


def d_meter(value, tail, pct, track, fill):
    return (f'<span style="display: inline-flex; align-items: center; gap: 8px"><span style="font-family: {MONO}; font-size: 11px; color: {INK2}">{value}<span style="color: {INK3}">{tail}</span></span>'
            f'<span role="progressbar" aria-label="{value}{tail}" style="width: 56px; height: 5px; border-radius: 999px; background: {track}; overflow: hidden; display: inline-block"><span style="display: block; width: {pct * 100}%; height: 100%; background: {fill}"></span></span>'
            f'<span style="font-family: {MONO}; font-size: 11px; color: {INK3}">{round(pct * 100)}%</span></span>')


def meter_desktop(track, fill):
    rows = row("budget", d_meter("$0.42", "/$1.00", 0.42, track, fill)) + row("memory", d_meter("4,800", "/5,000", 0.96, track, fill))
    return desk_panel(section("Overview", "", rows, first=True), h=170)


def meter_now_desktop():
    return meter_desktop(LINE, INK2)


def meter_proposed_desktop():
    return meter_desktop(LINE2, DOC_ACCENT)


def meter_now_mobile():
    rows = m_row("Budget", "today", control=m_meter("$0.42", "/$1.00", 0.42), chevron=False) + m_row("Memory", "MEMORY.md", control=m_meter("4,800", "/5,000", 0.96), chevron=False, sep=False)
    return phone(f'<div style="padding-top: 16px; background: {PANE}; height: 100%; box-sizing: border-box">{m_group(rows)}</div>', 180)


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
    return desk_panel(inner, h=300)


def chips_proposed_desktop():
    inner = stack(labelled("Chip · the one family", hrow(chip("running", "on"), chip("needs you", "warn"), chip("paused", "off"), chip("failed", "error"))),
                  labelled("Count badge · --badge-size 14, mono", hrow(d_flag("3"))),
                  caption("ds-pill and StatusPill render through Chip: 24 px, 8 px dot, warn untinted."), gap=16)
    return desk_panel(inner, h=200)


def m_pill2(text, tone):
    bg, fg, dot = {"success": ("rgba(63,179,122,0.16)", "#217a45", "#3fb37a"), "warning": (HOVER, INK, WARNING), "off": (HOVER, INK2, INK3), "danger": ("rgba(193,69,69,0.16)", DANGER, DANGER_FILL)}[tone]
    return (f'<span style="display: inline-flex; align-items: center; gap: 8px; min-height: 24px; padding: 0 8px; box-sizing: border-box; border-radius: 2px; background: {bg}; opacity: {0.55 if tone == "off" else 1}; '
            f'font-family: {MONO}; font-weight: 500; font-size: 11px; line-height: 1.3; color: {fg}"><span style="width: 8px; height: 8px; border-radius: 999px; background: {dot}"></span>{text}</span>')


def m_badge_block(badge):
    return f'<span style="position: relative; display: inline-flex; margin: 10px 14px 0 0">{mi("bell", 20, INK2)}{badge}</span>'


def chips_now_mobile():
    inner = stack(labelled("Pill · 22 pt, 6 pt dot, mono 12", hrow(pill("running", on=True), pill("needs you", tone="warning"), pill("paused"), pill("failed", tone="danger"))),
                  labelled("Count badge · 18 pt, sans 600", m_badge_block(m_count_badge(3))), gap=20)
    return phone_panel(inner, 220)


def chips_proposed_mobile():
    badge = m_count_badge(3).replace("font-weight: 600;", f"font-family: {MONO}; font-weight: 600;")
    inner = stack(labelled("Pill · 24 pt, 8 pt dot, mono 11", hrow(m_pill2("running", "success"), m_pill2("needs you", "warning"), m_pill2("paused", "off"), m_pill2("failed", "danger"))),
                  labelled("Count badge · 18 pt, mono 600", m_badge_block(badge)), gap=20)
    return phone_panel(inner, 220)


def spinner(color, size=12):
    return f'<span style="width: {size}px; height: {size}px; border-radius: 50%; border: 2px solid {color}; border-right-color: transparent; box-sizing: border-box; display: inline-block; flex-shrink: 0"></span>'


def d_button_weight(label, variant, weight):
    return button(label, variant).replace("font-weight: 500", f"font-weight: {weight}", 1)


def d_disabled(html):
    return html.replace('<button style="', '<button disabled style="opacity: 0.45; ', 1)


def d_loading(html, color):
    return html.replace(">" + html.split(">")[-1], f">{spinner(color)}" + html.split(">")[-1], 1)


def buttons_desktop(fill_weight):
    rows = []
    for label, variant, fg in (("Save", "primary", PANE), ("Cancel", "secondary", INK), ("Later", "ghost", INK2), ("Delete", "danger", "#ffffff")):
        base = d_button_weight(label, variant, fill_weight if variant in ("primary", "danger") else 500)
        rows.append(hrow(base, d_disabled(base), d_loading(base, fg), gap=12))
    header = hrow(*(f'<span style="width: 80px; font-family: {MONO}; font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase; color: {INK3}">{t}</span>' for t in ("rest", "disabled", "loading")), gap=12)
    return desk_panel(stack(header, *rows, gap=12), h=250)


def buttons_now_desktop():
    return buttons_desktop(500)


def buttons_proposed_desktop():
    return buttons_desktop(600)


def m_loading(html, fg, keep):
    label = html.split(">")[-2].split("<")[0]
    body = f'{spinner(fg, 14)}' + (f'<span style="margin-left: 8px">{label}</span>' if keep else "")
    return html.replace(f">{label}<", f' aria-busy="true"><span style="display: inline-flex; align-items: center">{body}</span><', 1)


def m_disabled_alpha(html):
    return html.replace('<button style="', '<button disabled style="opacity: 0.45; ', 1)


def buttons_mobile(alpha_disabled, keep_label):
    rows = []
    for label, variant, fg in (("Save", "primary", "#ffffff"), ("Cancel", "secondary", INK), ("Later", "ghost", INK2), ("Delete", "danger", "#ffffff")):
        base = m_button(label, variant, "md")
        disabled = m_disabled_alpha(base) if alpha_disabled else m_button(label, variant, "md", disabled=True)
        rows.append(hrow(base, disabled, m_loading(base, fg, keep_label), gap=12))
    header = hrow(*(f'<span style="width: 84px; font-family: {MONO}; font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase; color: {INK3}">{t}</span>' for t in ("rest", "disabled", "loading")), gap=12)
    return phone_panel(stack(header, *rows, gap=12), 300)


def buttons_now_mobile():
    return buttons_mobile(False, False)


def buttons_proposed_mobile():
    return buttons_mobile(True, True)


def d_field(value, state="rest", w=260):
    html = field_input(value, w=w).replace(f"max-width: {w}px; flex: 1;", f"width: {w}px;", 1)
    if state == "invalid":
        html = html.replace(WELL, f"background: var(--bg-elev, #ffffff); box-shadow: inset 0 0 0 1px {DANGER_FILL}", 1)
    if state == "disabled":
        html = html.replace('<span style="', '<span style="opacity: 0.45; ', 1)
    return html


def d_field_line(html, text, error=False):
    return stack(html, f'<span style="font-size: 12px; line-height: 1.3; color: {DANGER if error else INK3}">{text}</span>', gap=6)


def fields_now_desktop():
    rows = row("name", d_field("doc")) + row("name", d_field("doc", "invalid")) + row("name", d_field("doc", "disabled"))
    return desk_panel(stack(section("Rest · invalid · disabled", "", rows, first=True), caption("No helper or error line; the ring is the danger fill, disabled fades."), gap=12), h=230)


def fields_proposed_desktop():
    rows = (row("name", d_field_line(d_field("doc"), "Letters, digits and dashes."), align_top=True)
            + row("name", d_field_line(d_field("doc", "invalid"), "That name is taken.", error=True), align_top=True)
            + row("name", d_field("doc", "disabled")))
    return desk_panel(stack(section("Rest · invalid · disabled", "", rows, first=True), caption("Helper and error lines under the field, described to assistive tech."), gap=12), h=290)


def m_field(value, state, ring=None, alpha=False):
    base = f"background: {ELEV}; box-shadow: inset 0 0 0 1px {LINE2}"
    if state == "invalid":
        base = f"background: {ELEV}; box-shadow: inset 0 0 0 1px {ring}"
    if state == "disabled" and not alpha:
        base = f"background: {FIELD}; box-shadow: none"
    opacity = "opacity: 0.45; " if state == "disabled" and alpha else ""
    color = INK2 if state == "disabled" and not alpha else INK
    return (f'<div style="{opacity}min-height: 44px; box-sizing: border-box; border-radius: 4px; {base}; display: flex; align-items: center; padding: 0 12px; font-size: 15px; color: {color}">{value}</div>')


def m_field_block(label, field, line="", error=False):
    lines = [f'<span style="font-size: 13px; font-weight: 500; color: {INK2}">{label}</span>', field]
    if line:
        lines.append(f'<span style="font-size: 12px; line-height: 1.3; color: {DANGER if error else INK3}">{line}</span>')
    return stack(*lines, gap=6)


def fields_mobile(ring, alpha):
    inner = stack(m_field_block("Name", m_field("doc", "rest"), "Letters, digits and dashes."),
                  m_field_block("Name", m_field("doc", "invalid", ring=ring), "That name is taken.", error=True),
                  m_field_block("Name", m_field("doc", "disabled", alpha=alpha)), gap=18)
    return phone_panel(inner, 330)


def fields_now_mobile():
    return fields_mobile(DANGER, False)


def fields_proposed_mobile():
    return fields_mobile(DANGER_FILL, True)


PROPOSALS_H = [
    dict(
        id="DS.SEGMENTED", client="mobile", area="Segmented control",
        title="The selected segment is drawn in ink on the phone, as on desktop",
        why=("Desktop draws the selected segment as an ink block on the selected tone (<code>design-system.css:53-94</code>, fixed by <code>segmented.test.js</code>); "
             "the phone draws it as a pane-tone card on the hover tone (<code>Segmented.jsx:15,37,45</code>). In dark mode the phone's card, #151515 on 4 % ink, is barely distinguishable from its track. "
             "The proposal takes desktop's contrast rule to the phone: ink fill, pane-tone label, selected-tone track, the same 44 pt cells and radio semantics it has today."),
        mobile=(segmented_now_mobile, segmented_proposed_mobile),
        desktop=(segmented_now_desktop, None),
        accept=("<code>Segmented.test.jsx</code> asserts the selected cell's background is <code>colors.ink</code>, its label <code>colors.bgPane</code> and the track <code>colors.selected</code>; "
                "<code>m_segmented</code> in the kit draws the same and the Mobile tab is regenerated."),
        h=780,
    ),
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
        h=1230,
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
        h=1010,
    ),
    dict(
        id="DS.METER", client="desktop", area="Budget and memory meters",
        title="Desktop's meter uses the visible track and the accent fill the phone and the kit already draw",
        why=("The phone's Meter runs on a <code>line2</code> track with the accent fill (<code>Meter.jsx:44,53</code>) and the kit draws desktop the same way (<code>desktop_boards.py:178-182</code>), but desktop's <code>.ds-meter</code> paints a <code>--line</code> track at 7 % ink with an ink-2 fill (<code>design-system.css:311,331-335</code>, <code>Bar.jsx:10</code>): "
             "the same budget reads as grey on almost nothing on the Mac and as a clear bar on the phone. The proposal moves desktop to the <code>--line-2</code> track and the accent fill by default, so the kit stops lying about it."),
        mobile=(meter_now_mobile, None),
        desktop=(meter_now_desktop, meter_proposed_desktop),
        accept=("a desktop style test asserts <code>.ds-meter .bar</code> uses <code>--line-2</code> and <code>.ds-bar &gt; i</code> defaults to <code>--accent</code>; <code>MeterChip.test.jsx</code> renders the accent; the System tab's meter row is regenerated and matches."),
        h=830,
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
        h=1040,
    ),
]
