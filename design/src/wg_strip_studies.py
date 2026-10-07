from notif_studies import MONO, ell, flex, spacer, stack, wrap
from wg_settings_studies import (P, PIPELINES, WG_NAME, crease_name, glyph, mono, obj, phase_chip, phone, rippling)

CHAIN = PIPELINES[0][1]
STATES = {**{slug: "completed" for slug in CHAIN[:-1]}, "qa": "current"}
BLOCKED = {**STATES, "qa": "blocked"}
COST = {"setup": ("$0.01", "3,880"), "enrich": ("$0.02", "7,940"), "intake": ("$0.02", "8,310"), "assets": ("$0.02", "6,720"), "content": ("$0.03", "12,450"),
        "translation": ("$0.03", "13,060"), "build": ("$0.01", "4,120"), "qa": ("$0.02", "8,400")}
TASK = {"build": "run npm run build exactly once and record the selected dist tier",
        "qa": "audit the built dist read-only and report every finding before internal review"}
QA_LINE = "audit the built dist read-only…"
REPAIR_LINE = "restore the fr strings lens flagged…"


def arrow_sep(size=11):
    return f'<span style="font-size: {size}px; color: {P["ink3"]}; flex-shrink: 0" aria-hidden="true">→</span>'


def sep(size=11):
    return f'<span style="font-size: {size}px; color: {P["ink4"]}; flex-shrink: 0" aria-hidden="true">›</span>'


def bullet():
    return mono("·", 11, P["ink4"])


def wave():
    bars = "".join(f'<span style="width: 2px; height: {h}px; border-radius: 1px; background: {P["ink3"]}"></span>' for h in (5, 9, 6, 11, 7))
    return f'<span style="display: inline-flex; align-items: center; gap: 2px; height: 22px; padding: 0 4px; flex-shrink: 0">{bars}</span>'


def meter():
    return flex(mono("$0.16", 10.5, P["ink2"]), mono("/$5.00", 10.5, P["ink3"]), gap=0, extra="flex-shrink: 0")


def d_meta():
    return flex(mono("hub", 10, P["ink3"]), obj("mira", 12), mono("@mira", 10.5, P["ink2"]), bullet(), mono("members", 10, P["ink3"]), mono("7", 10.5, P["ink2"]),
                bullet(), meter(), gap=4)


def d_header(right):
    left = stack(crease_name("mira", 17, WG_NAME), d_meta(), gap=6, extra="flex: 1; overflow: hidden")
    more = f'<span style="width: 24px; height: 24px; display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0">{glyph("more", 14, P["ink2"])}</span>'
    return flex(left, right, wave(), more, gap=8, extra=f"padding: 12px 12px 10px 16px; box-shadow: inset 0 -0.5px 0 {P['line']}")


def ghost_button(inner, w=None):
    width = f"width: {w}px;" if w else ""
    return (f'<span style="display: inline-flex; align-items: center; gap: 6px; {width} height: 28px; padding: 0 8px; border-radius: 4px; background: {P["hover"]}; '
            f'box-sizing: border-box; min-width: 0; flex-shrink: 1">{inner}</span>')


def progress_trigger(lead, phase_line, line, tone="ink"):
    top = flex(lead, phase_line, spacer(), mono("7 of 8", 11, P["ink"], 600), glyph("chevron-down", 11, P["ink3"]), gap=5)
    bottom = ell(line, 11.5, P["danger"] if tone == "danger" else P["ink3"])
    return (f'<span style="display: flex; flex-direction: column; justify-content: center; gap: 3px; width: 196px; height: 44px; padding: 0 8px; border-radius: 4px; '
            f'background: {P["hover"]}; box-sizing: border-box; flex-shrink: 0">{top}{bottom}</span>')


def owner_trigger(key="hd"):
    return progress_trigger(rippling("lens", 13, key), flex(mono("#qa", 11.5, P["ink"], 600), mono("@lens", 11, P["ink2"]), gap=5), QA_LINE)


def repair_trigger(key="hr"):
    return progress_trigger(rippling("lingua", 13, key), flex(mono("#qa", 11.5, P["ink"], 600), mono("@lingua", 11, P["ink2"]), gap=5), REPAIR_LINE)


def blocked_trigger():
    return progress_trigger(obj("lens", 13), flex(mono("#qa", 11.5, P["ink"], 600), mono("@lens", 11, P["ink2"]), gap=5), "blocked · dist/fr has no index page", "danger")


def eyebrow(value):
    return mono(value, 10, P["ink3"], extra="letter-spacing: 0.08em; text-transform: uppercase; margin-right: 2px")


def strip_row(chips, pad="9px 16px"):
    return (f'<div style="display: flex; flex-wrap: wrap; align-items: center; gap: 6px 5px; padding: {pad}; box-shadow: inset 0 -0.5px 0 {P["line"]}">'
            f'{eyebrow("pipeline")}{chips}</div>')


def chips(states, key, owner=True, assignee=None, chain=CHAIN, size=10.5, height=21):
    out = []
    for i, slug in enumerate(chain):
        state = states.get(slug)
        out.append((arrow_sep() if i else "") + phase_chip(slug, state, f"{key}{i}", owner, assignee if state == "current" else None, True, height, size))
    return "".join(out)


def strip(states, key, owner=True, assignee=None):
    return strip_row(chips(states, key, owner, assignee))


def hub_task(slug, line, target):
    head = flex(obj("mira", 13), mono("mira", 11, P["ink2"], 600), mono("#231", 10, P["ink4"]), gap=5)
    card = (f'<div style="padding: 9px 11px; border-radius: 4px; background: {P["pane"]}; box-shadow: 0 0 0 0.5px {P["line2"]}; display: flex; flex-direction: column; gap: 5px">'
            f'{flex(mono("task", 9.5, P["ink3"], extra="letter-spacing: 0.08em; text-transform: uppercase"), mono("#" + slug, 11, P["ink"], 600), gap=6)}'
            f'{wrap(target + line, 12, P["ink2"], lh=1.45)}</div>')
    return f'<div style="padding: 12px 16px 14px; display: flex; flex-direction: column; gap: 6px; background: {P["bg"]}">{head}{card}</div>'


def frame(*parts):
    return (f'<div style="border-radius: 4px; background: {P["pane"]}; box-shadow: 0 0 0 1px {P["line2"]}; overflow: hidden; display: flex; flex-direction: column; min-width: 0">'
            f'{"".join(parts)}</div>')


def d_proposed():
    return frame(d_header(owner_trigger()), strip(STATES, "ds"), hub_task("qa", TASK["qa"], '<span style="font-family: ' + MONO + '">@lens</span> '))


def fact(label, value):
    return flex(mono(label, 10, P["ink3"], extra="width: 64px"), value, gap=8, align="baseline")


def tooltip(slug, state, owner, word, seq, assignee=None):
    usd, tokens = COST[slug]
    on_ink = P["pane"]
    note = lambda v: mono(v, 10, on_ink, extra="opacity: 0.7")
    head = flex(mono("#" + slug, 11, on_ink, 600), note(word), note(f"post #{seq}"), gap=6, align="baseline")
    who = flex(obj(owner, 13), mono("@" + owner, 11, on_ink, 600), note("declared owner"), gap=6)
    if assignee:
        who = stack(who, flex(obj(assignee, 13), mono("@" + assignee, 11, on_ink, 600), note("assigned by the hub"), gap=6), gap=5)
    rows = stack(wrap(TASK[slug], 11.5, on_ink, lh=1.45), note(f"{usd} · {tokens} tokens"), note("Click to jump to the post"), gap=6)
    return (f'<div style="width: 280px; padding: 6px 10px; border-radius: 4px; background: {P["ink"]}; '
            f'display: flex; flex-direction: column; gap: 6px; box-sizing: border-box">{head}{who}{rows}</div>')


def anchored(chip, card):
    return stack(f'<div style="display: flex">{chip}</div>', f'<div style="display: flex; padding-left: 10px">{card}</div>', gap=5)


def hover_pair():
    return anchored(phase_chip("build", "completed", "hb", strong=True), tooltip("build", "completed", "pixel", "completed", 212))


def excerpt(states, key, assignee=None):
    tail = CHAIN[-3:]
    return (f'<div style="display: flex; flex-wrap: wrap; align-items: center; gap: 6px 5px; padding: 9px 12px; border-radius: 4px; background: {P["pane"]}; '
            f'box-shadow: 0 0 0 1px {P["line2"]}">{mono("…", 11, P["ink4"])}{arrow_sep()}{chips(states, key, True, assignee, tail)}</div>')


def m_header(right):
    back = f'<span style="width: 24px; height: 44px; display: inline-flex; align-items: center; flex-shrink: 0">{glyph("chevron-left", 20, P["ink2"])}</span>'
    meta = flex(obj("mira", 11), mono("@mira", 10.5, P["ink3"]), bullet(), mono("7", 10.5, P["ink3"]), bullet(), mono("$0.16/$5.00", 10.5, P["ink3"]), gap=4)
    title = stack(crease_name("mira", 15, WG_NAME), meta, gap=4, extra="flex: 1; overflow: hidden")
    return flex(back, title, right, gap=6, extra=f"padding: 8px 10px 8px 6px; background: {P['bg']}")


def m_owner_button(key="mh"):
    return (f'<span style="display: inline-flex; align-items: center; gap: 5px; height: 44px; padding: 0 9px; border-radius: 4px; background: {P["hover"]}; flex-shrink: 0">'
            f'{rippling("lens", 14, key)}{mono("7 of 8", 11, P["ink"], 600)}</span>')


def fade(side):
    direction = "90deg" if side == "left" else "270deg"
    return (f'<span style="position: absolute; top: 0; bottom: 0; {side}: 0; width: 28px; background: linear-gradient({direction}, {P["pane"]}, transparent); '
            f'pointer-events: none"></span>')


def m_strip(key="ms"):
    before = "".join(phase_chip(s, "completed", f"{key}{i}", strong=True, height=30, size=12) + sep(12) for i, s in enumerate(CHAIN[4:7]))
    current = phase_chip("qa", "current", f"{key}q", strong=True, height=30, size=12)
    left = f'<div style="display: flex; justify-content: flex-end; align-items: center; gap: 6px; overflow: hidden; white-space: nowrap; min-width: 0">{before}</div>'
    return (f'<div style="position: relative; display: grid; grid-template-columns: 1fr auto 1fr; align-items: center; column-gap: 6px; height: 46px; background: {P["pane"]}; '
            f'box-shadow: inset 0 -0.5px 0 {P["line"]}">{left}{current}<span></span>{fade("left")}</div>')


def m_chat(slug, line):
    return (f'<div style="flex: 1; padding: 12px; display: flex; flex-direction: column; gap: 8px; background: {P["bg"]}">'
            f'{flex(obj("mira", 14), mono("mira", 11.5, P["ink2"], 600), gap=6)}'
            f'<div style="padding: 10px 12px; border-radius: 4px; background: {P["pane"]}; display: flex; flex-direction: column; gap: 5px">'
            f'{flex(mono("task", 9.5, P["ink3"], extra="letter-spacing: 0.08em; text-transform: uppercase"), mono("#" + slug, 12, P["ink"], 600), gap=6)}'
            f'{wrap(line, 13, P["ink2"], lh=1.45)}</div></div>')


def m_proposed():
    return phone(m_header(m_owner_button()) + m_strip() + m_chat("qa", "@lens " + TASK["qa"]), 262)


def sheet_button(label, primary=False):
    bg = P["ink"] if primary else P["hover"]
    fg = P["pane"] if primary else P["ink"]
    return (f'<span style="flex: 1; height: 44px; display: inline-flex; align-items: center; justify-content: center; border-radius: 4px; background: {bg}; '
            f'font-size: 14px; font-weight: 600; color: {fg}">{label}</span>')


def m_sheet(key="sh"):
    usd, tokens = COST["qa"]
    grab = f'<span style="width: 36px; height: 4px; border-radius: 2px; background: {P["line2"]}; align-self: center"></span>'
    head = flex(stack(wrap("#qa", 18, P["ink"], 600), mono("running · setup", 11, P["ink3"]), gap=2), spacer(), glyph("x", 16, P["ink2"]), gap=8, align="flex-start")
    who = flex(obj("lens", 16), mono("@lens", 13, P["ink"], 600), wrap("declared owner", 12, P["ink3"]), gap=8)
    rows = stack(wrap(TASK["qa"], 13.5, P["ink"], lh=1.45), mono(f"{usd} · {tokens} tokens", 11.5, P["ink2"]), mono("opened at post #231", 11.5, P["ink2"]), gap=10)
    body = stack(grab, head, who, rows, flex(sheet_button("Jump to #qa", True)), gap=14)
    scrim = "rgba(20,20,20,0.32)"
    return (f'<div style="flex: 1; position: relative; display: flex; flex-direction: column; justify-content: flex-end; background: {P["bg"]}">'
            f'<div style="position: absolute; inset: 0; background: {scrim}"></div>'
            f'<div style="position: relative; padding: 10px 16px 18px; border-radius: 12px 12px 0 0; background: {P["elev"]}">{body}</div></div>')


def m_sheet_phone():
    return phone(m_header(m_owner_button("mh2")) + m_strip("ms2") + m_sheet(), 540)



def _source(*parts):
    import os
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", *parts)) as f:
        return f.read()


def _widths(src, name):
    import re
    return [int(v) for v in re.search(name + r"\s*=\s*\[([\d,\s]+)\]", src).group(1).split(",")]


GHOST_WIDTHS = _widths(_source("desktop", "src", "primitives", "PipelineStages.jsx"), "GHOST_WIDTHS")
PLACEHOLDER_WIDTHS = _widths(_source("mobile", "src", "features", "chat", "PipelineStrip.jsx"), "PLACEHOLDER_WIDTHS")
GHOST_STYLE = (f"<style>@keyframes ghostShimmer{{0%{{background-position: 100% 0}}100%{{background-position: -100% 0}}}}"
               f".pl-ghost{{background: linear-gradient(90deg, {P['hover']} 0%, {P['selected']} 50%, {P['hover']} 100%); background-size: 200% 100%; animation: ghostShimmer 1.4s ease-in-out infinite}}"
               f"@keyframes ghostPulse{{0%, 100%{{opacity: 0.4}}50%{{opacity: 0.8}}}}.pl-bar{{background: {P['hover']}; animation: ghostPulse 1.4s ease-in-out infinite}}"
               f"@media (prefers-reduced-motion: reduce){{.pl-ghost, .pl-bar{{animation: none}}}}</style>")


def ghost_chips(count):
    n = min(max(count, 1), len(GHOST_WIDTHS))
    return GHOST_STYLE + "".join((arrow_sep() if i else "") + f'<span class="pl-ghost" style="display: inline-block; width: {GHOST_WIDTHS[i]}px; height: 21px; border-radius: 2px; flex-shrink: 0"></span>'
                                 for i in range(n))


def d_before_run():
    one = frame(d_header(""), strip({}, "dbr"))
    several = frame(d_header(""), strip_row(ghost_chips(len(CHAIN))))
    return stack(
        stack(mono("one pipeline · the chain drawn from the row, every phase pending, each owner standing still", 10.5, P["ink3"]), one, gap=6),
        stack(mono("several pipelines · skeleton chips the size of a phase until the run arrives", 10.5, P["ink3"]), several, gap=6),
        gap=16,
    )


def m_pending_strip(key="mbr"):
    items = "".join((sep(12) if i else "") + phase_chip(slug, None, f"{key}{i}", True, None, True, 30, 12) for i, slug in enumerate(CHAIN))
    return (f'<div style="position: relative; display: flex; align-items: center; gap: 8px; height: 46px; padding: 0 16px; overflow: hidden; white-space: nowrap; background: {P["pane"]}; '
            f'box-shadow: inset 0 -0.5px 0 {P["line"]}">{items}{fade("right")}</div>')


def m_placeholder_strip():
    n = min(len(CHAIN), len(PLACEHOLDER_WIDTHS))
    bars = "".join((sep(12) if i else "") + f'<span class="pl-bar" style="display: inline-block; width: {PLACEHOLDER_WIDTHS[i]}px; height: 30px; border-radius: 4px; flex-shrink: 0; animation-delay: {i * 80}ms"></span>'
                   for i in range(n))
    return (f'<div style="display: flex; align-items: center; gap: 8px; height: 46px; padding: 0 16px; overflow: hidden; background: {P["pane"]}; '
            f'box-shadow: inset 0 -0.5px 0 {P["line"]}">{GHOST_STYLE}{bars}</div>')


def m_before_run():
    body = f'<div style="flex: 1; background: {P["bg"]}"></div>'
    one = stack(mono("one pipeline · every phase pending", 10.5, P["ink3"]), phone(m_header("") + m_pending_strip() + body, 200), gap=6)
    several = stack(mono("several pipelines · placeholder chips", 10.5, P["ink3"]), phone(m_header("") + m_placeholder_strip() + body, 200), gap=6)
    return f'<div style="display: flex; gap: 24px; align-items: flex-start">{one}{several}</div>'
