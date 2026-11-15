import json
import os
import re
import subprocess

import volume_marks as vm
from notif_studies import flex, stack, wrap
from paper_studies import text
from wg_settings_studies import P, mono

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
FRAMES = 4


def _read(*parts):
    with open(os.path.join(ROOT, *parts)) as f:
        return f.read()


def _load_busy():
    script = (
        f"import {{BUSY_CYCLE_S, BUSY_DELAY_MS, BUSY_MIN_MS, BUSY_MIN_MARK_PX}} from {json.dumps(os.path.join(ROOT, 'common', 'busy.mjs'))};"
        "process.stdout.write(JSON.stringify({cycle: BUSY_CYCLE_S, delay: BUSY_DELAY_MS, min: BUSY_MIN_MS, mark: BUSY_MIN_MARK_PX}));"
    )
    out = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


BUSY = _load_busy()
BUSY_TURN_S = vm.TURN["busy"][0]
TOKENS = _read("desktop", "src", "styles", "tokens.css")
DUR_LOOP = float(re.search(r"--dur-loop:\s*([\d.]+)s", TOKENS).group(1))
DUR_SPIN = float(re.search(r"--dur-spin:\s*([\d.]+)s", TOKENS).group(1))
SPINNER_TURN_MS = round(BUSY["cycle"] * 1000 / 2)
BREATH_S = 1.6
STAGGER_MS = 90
SK = "rgba(20,20,20,0.07)"
BAR_SHAPES = tuple(float(n) for n in re.search(r"BAR_SHAPES = \[([\d., ]+)\]", _read("mobile", "src", "components", "UsageSkeleton.jsx")).group(1).split(","))
DAY_BARS = tuple(int(n) for n in re.search(r"DAY_BARS = \[([\d, ]+)\]", _read("desktop", "src", "primitives", "UsageSkeleton.jsx")).group(1).split(","))
DESKTOP_CIRCLE = re.search(r'<circle cx="8" cy="8" r="(\d+)" strokeDasharray="([\d ]+)"', _read("desktop", "src", "primitives", "icons.jsx")).groups()
MOBILE_ARC = re.search(r'<Path d="([^"]+)"', _read("mobile", "src", "components", "Spinner.jsx")).group(1)


def busy_mark(size, still=False):
    import marks
    mark = marks.twin(size, "busy", seed="busy", still=still)
    return f'<span role="img" aria-label="Loading" style="display: inline-flex; flex-shrink: 0">{mark}</span>'


def spin_style(key, seconds):
    return (f"<style>@keyframes {key}{{to{{transform: rotate(360deg)}}}}.{key}{{animation: {key} {seconds}s linear infinite}}"
            f"@media (prefers-reduced-motion: reduce){{.{key}{{animation: none}}}}</style>")


def desktop_spinner(size, colour, stroke=1.5, opacity=1, key="dspin"):
    r, dash = DESKTOP_CIRCLE
    return (f'{spin_style(key, DUR_SPIN)}<svg class="{key}" viewBox="0 0 16 16" width="{size}" height="{size}" fill="none" stroke="{colour}" stroke-width="{stroke}" stroke-linecap="round" '
            f'style="flex-shrink: 0; opacity: {opacity}"><circle cx="8" cy="8" r="{r}" stroke-dasharray="{dash}"/></svg>')


def mobile_spinner(size, colour, key="mspin"):
    return (f'{spin_style(key, SPINNER_TURN_MS / 1000)}<svg class="{key}" viewBox="0 0 16 16" width="{size}" height="{size}" fill="none" stroke="{colour}" stroke-width="1.5" '
            f'stroke-linecap="round" style="flex-shrink: 0"><path d="{MOBILE_ARC}"/></svg>')


def specimen(mark, name, note, w=200):
    return stack(f'<div style="height: 96px; display: flex; align-items: center; justify-content: center; border-radius: 20px; background: {P["pane"]}; '
                 f'box-shadow: 0 0 0 1px {P["line2"]}">{mark}</div>', mono(name, 10.5, P["ink2"]), wrap(note, 11, P["ink3"], lh=1.4), gap=6, extra=f"width: {w}px")


def frames():
    import marks
    seconds = marks.vm.TURN["busy"][0]
    cells = "".join(stack(f'<div style="height: 56px; display: flex; align-items: center; justify-content: center">'
                          f'{marks.twin(44, "busy", pose=marks.vm.pose_at("busy", k / FRAMES))}</div>',
                          mono(f"{seconds * k / FRAMES:.1f} s", 10, P["ink3"], extra="text-align: center"), gap=4, extra="width: 76px")
                    for k in range(FRAMES))
    return f'<div style="display: flex; gap: 6px; padding: 10px 12px; border-radius: 20px; background: {P["pane"]}; box-shadow: 0 0 0 1px {P["line2"]}">{cells}</div>'


BREATH = (f"<style>@keyframes skBreath{{0%, 100%{{opacity: 1}}50%{{opacity: 0.55}}}}"
          f".sk-bone, .pl-ghost, .pl-bar{{animation: skBreath {BREATH_S}s ease-in-out infinite}}"
          f"@media (prefers-reduced-motion: reduce){{.sk-bone, .pl-ghost, .pl-bar{{animation: none}}}}</style>")


BREATH_M = (f"<style>@keyframes skBreathM{{0%, 100%{{opacity: 1}}50%{{opacity: 0.4}}}}"
            f".sk-bone-m{{animation: skBreathM {BREATH_S}s ease-in-out infinite}}"
            f"@media (prefers-reduced-motion: reduce){{.sk-bone-m{{animation: none}}}}</style>")


def mbone(w, h, r=4, index=0):
    return bone(w, h, r, index, "sk-bone-m")


def bone(w, h, r=4, index=0, cls="sk-bone"):
    return (f'<span class="{cls}" style="display: block; width: {w}; height: {h}px; border-radius: {r}px; background: {SK}; flex-shrink: 0; '
            f'animation-delay: {index * STAGGER_MS}ms"></span>')


def silhouette(narrow):
    slot = lambda h, inner: f'<div style="height: {h}px; display: flex; align-items: center">{inner}</div>'

    def tile(i, label_w, value_w, big=False, end=False):
        return (f'<div style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 6px; align-items: {"flex-end" if end else "flex-start"}">'
                f'{slot(11, mbone(f"{label_w}px", 8, 4, i))}{slot(28 if big else 18, mbone(f"{value_w}px", 22 if big else 14, 4, i))}</div>')
    if narrow:
        stats = (f'<div style="display: flex; align-items: flex-end">{tile(0, 34, 84, True)}{tile(1, 52, 58, end=True)}</div>'
                 f'<div style="display: flex; align-items: flex-start; margin-top: 14px">{tile(2, 38, 52)}{tile(3, 44, 40)}</div>')
    else:
        stats = f'<div style="display: flex; align-items: flex-start">{tile(0, 34, 96, True)}{tile(1, 38, 56)}{tile(2, 44, 44)}{tile(3, 52, 60)}</div>'
    bars = "".join(f'<div style="flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: flex-end">'
                   f'<span class="sk-bone-m" style="display: block; width: 100%; max-width: 20px; height: {round(104 * shape)}px; border-radius: 3px; background: {SK}; animation-delay: {i * STAGGER_MS}ms"></span></div>'
                   for i, shape in enumerate(BAR_SHAPES))
    days = "".join(f'<div style="flex: 1; height: 11px; display: flex; align-items: center; justify-content: center">{mbone("8px", 6, 4, i)}</div>' for i in range(len(BAR_SHAPES)))
    legend = f'<div style="height: 14px; margin-top: 14px; display: flex; justify-content: space-between; align-items: center">{mbone("96px", 8, 4, 0)}{mbone("150px", 8, 4, 1)}</div>'
    return (f'{BREATH_M}<div><div style="padding-bottom: 14px; ">{stats}</div>'
            f'<div style="margin-top: 20px"><div style="height: 104px; display: flex; align-items: flex-end; gap: 4px">{bars}</div>'
            f'<div style="display: flex; gap: 4px; margin-top: 8px">{days}</div></div>{legend}</div>')


def desktop_silhouette():
    tiles = ((34, 96, 28, True), (38, 56, 18, False), (44, 44, 18, False), (52, 60, 18, False))
    tile = lambda i, lw, vw, vh, lead: (f'<div style="flex: 1; min-width: 0"><div style="display: flex; align-items: center; height: 16.5px; margin-bottom: 8px">{bone(f"{lw}px", 8, 4, i)}</div>'
                                        f'<div style="display: flex; align-items: center; height: {vh}px">{bone(f"{vw}px", vh, 4, i + 0.5)}</div></div>')
    stats = f'<div style="display: flex; align-items: flex-start; padding-bottom: 16px; ">{"".join(tile(i, *t) for i, t in enumerate(tiles))}</div>'
    bars = "".join(f'<div style="flex: 1; height: 100%; display: flex; flex-direction: column; justify-content: flex-end; align-items: center"><span class="sk-bone" style="display: block; width: 100%; max-width: 20px; height: {h}%; border-radius: 3px; background: {SK}; animation-delay: {i * STAGGER_MS}ms"></span></div>' for i, h in enumerate(DAY_BARS))
    track = f'<div style="height: 104px; margin-top: 24px; display: flex; align-items: flex-end; gap: 4px">{bars}</div>'
    foot = (f'<div style="height: 11px; margin-top: 8px"></div><div style="display: flex; justify-content: space-between; align-items: center; gap: 8px; margin-top: 16px">'
            f'<div style="display: flex; align-items: center; height: 16.5px">{bone("96px", 8, 4, 0)}</div><div style="display: flex; align-items: center; height: 16.5px">{bone("150px", 8, 4, 1)}</div></div>')
    return f'{BREATH}<div>{stats}{track}{foot}</div>'


def field_bone(index=0):
    return bone("112px", 22, 4, index)


def desktop_rows():
    widths = (("46%", "72%"), ("58%", "64%"), ("40%", "78%"))
    rows = "".join(flex(bone("14px", 14, 4, i),
                        stack(bone(a, 11, 4, i), bone(b, 8, 4, i + 1), gap=8, extra="flex: 1"), gap=8, extra="padding: 8px 12px")
                   for i, (a, b) in enumerate(widths))
    return f'<div style="width: 240px; padding: 8px; display: flex; flex-direction: column; gap: 4px; border-radius: 20px; background: {P["side"]}; box-shadow: 0 0 0 1px {P["line2"]}">{BREATH}{rows}</div>'


def mobile_rows():
    shapes = ((120, 200), (90, 230), (140, 170))
    line = lambda h, box, w, i: f'<div style="height: {box}px; display: flex; align-items: center">{mbone(f"{w}px", h, 4, i)}</div>'
    rows = "".join(f'<div style="min-height: 44px; padding: 14px 16px; box-sizing: border-box; display: flex; flex-direction: column; gap: 4px">'
                   f'{line(15, 19.5, a, i * 2)}{line(11, 14.3, b, i * 2 + 1)}</div>'
                   + ""
                   for i, (a, b) in enumerate(shapes))
    return f'<div style="width: 358px; border-radius: 20px; background: var(--card); overflow: hidden">{BREATH_M}{rows}</div>'


def mobile_settings_rows():
    rows = "".join(f'<div style="display: flex; align-items: center; justify-content: space-between; gap: 12px">{mbone(f"{w}px", 10, 4, i)}{mbone("64px", 14, 4, i)}</div>' for i, w in enumerate((180, 220, 160, 200, 150)))
    return f'<div style="width: 390px; box-sizing: border-box; padding: 24px 20px; display: flex; flex-direction: column; gap: 20px; border-radius: 20px; background: {P["pane"]}; box-shadow: 0 0 0 1px {P["line2"]}">{BREATH_M}{rows}</div>'


def usage_card(narrow, mobile=False):
    inner = silhouette(narrow) if mobile else desktop_silhouette()
    return (f'<div style="width: {(326 if narrow else 520) if mobile else 500}px; padding: {"16px" if mobile else "16px"}; box-sizing: border-box; border-radius: 20px; background: {"var(--card)" if mobile else P["pane"]}; '
            f'{"" if mobile else "box-shadow: 0 0 0 1px " + P["line2"]}">{inner}</div>')


def desktop_button():
    return (f'<span style="height: 28px; padding: 0 12px; border-radius: 999px; background: {P["ink"]}; display: inline-flex; align-items: center; gap: 8px; '
            f'font-size: 12px; font-weight: 500; color: {P["pane"]}">{desktop_spinner(12, P["pane"], 2, 0.6, "dspin1")}Save</span>')


def desktop_stopping():
    return (f'<span aria-label="Stopping" style="width: 32px; height: 32px; border-radius: 999px; background: {P["ink"]}; opacity: 0.65; display: inline-grid; place-items: center">'
            f'{desktop_spinner(14, P["pane"], 1.5, 1, "dspin2")}</span>')


def mobile_button():
    return (f'<span style="height: 40px; min-width: 120px; padding: 0 16px; border-radius: 999px; background: {P["ink"]}; display: inline-flex; align-items: center; justify-content: center">'
            f'{mobile_spinner(20, P["pane"], "mspin1")}</span>')


def busy_inline(label):
    return flex(busy_mark(BUSY["mark"]), text(label, 12, P["ink2"]), gap=6)


def busy_page(label, size, gap):
    return stack(busy_mark(size), text(label, 12, P["ink2"]), gap=gap, extra="align-items: center")


MOBILE_BONES_NOTE = f"bones in the 7 % line ink, flat, breathing opacity 0.4 ↔ 1 over {BREATH_S} s, {STAGGER_MS} ms apart; static under reduced motion"
BONES_NOTE = f"bones in the 7 % line ink, flat, breathing opacity 0.55 ↔ 1 over {BREATH_S} s, {STAGGER_MS} ms apart; static under reduced motion"


def waiting(mobile=False):
    timing = f"after {BUSY['delay']} ms, at least {BUSY['min']} ms on screen"
    if mobile:
        marks = flex(
            specimen(busy_page("Reaching the daemon", 40, 12), "components/Busy · fill", f"Twin busy, 40 pt by default; {timing}"),
            specimen(busy_inline("Earlier messages"), "components/Busy · 18 + words", "24 pt or less sits in a row with its words; chat history, MCP handshakes"),
            specimen(flex(mobile_button(), mobile_spinner(20, P["ink3"], "mspin2"), gap=14), "components/Spinner",
                     f"a 270° arc turning every {SPINNER_TURN_MS} ms; Button hides its label under it; attachment cards, rich text images, member and model sheets in ink-3"),
            specimen(flex(busy_mark(BUSY["mark"], still=True), text("Reaching the daemon", 12, P["ink2"]), gap=6), "reduce motion", "Twin faces you, still, and the words carry the wait"),
            gap=14, align="flex-start", extra="flex-wrap: wrap",
        )
        rows = stack(mobile_rows(), mono("ListSkeleton · rows of two lines", 10.5, P["ink2"]),
                     wrap(f"{MOBILE_BONES_NOTE}; bones show after 150 ms, stay at least 400 ms, then the content fades in; the title bone is a 15 px bar in a 19.5 px line box, the helper 11 px in 14.3", 11, P["ink3"], lh=1.4), gap=6, extra="width: 358px")
        settings = stack(mobile_settings_rows(), mono("SettingsSkeleton · phone", 10.5, P["ink2"]),
                         wrap("one 10 px helper bone and a 64 × 14 value bone per row, 20 pt apart, no group card", 11, P["ink3"], lh=1.4), gap=6, extra="width: 390px")
        usage = stack(usage_card(True, True), mono("UsageSkeleton · phone, under 520 pt of tiles", 10.5, P["ink2"]),
                      wrap("same silhouette as the loaded card: label and value slots on the chart's own line boxes, Today and Cap on one row, Input and Output below, fourteen bars and a 14 px day-label row, a two-bone legend; titles stay text", 11, P["ink3"], lh=1.4),
                      gap=6, extra="width: 326px")
        usage_wide = stack(usage_card(False, True), mono("UsageSkeleton · fold and tablet", 10.5, P["ink2"]),
                           wrap("four tiles in one row from 520 pt of tiles; the bones are the line ink, breathing 90 ms apart", 11, P["ink3"], lh=1.4),
                           gap=6, extra="width: 520px")
    else:
        marks = flex(
            specimen(busy_inline("Fetching latest settings"), "primitives/Busy · 18 + words", f"a section that waits says for what, in ink-2; {timing}"),
            specimen(flex(desktop_button(), desktop_stopping(), gap=14), "SpinnerIcon · Button, Chip, Send",
                     f"a dashed circle (r {DESKTOP_CIRCLE[0]}, dash {DESKTOP_CIRCLE[1]}) turning every {DUR_SPIN} s; Send is icon-only and spins only while stopping; also attachments and read aloud"),
            specimen(flex(busy_mark(BUSY["mark"], still=True), text("Fetching latest settings", 12, P["ink2"]), gap=6), "reduced motion", "Twin faces you, still, and the words carry the wait"),
            gap=14, align="flex-start", extra="flex-wrap: wrap",
        )
        rows = stack(desktop_rows(), mono("SkeletonRows · SkeletonReader", 10.5, P["ink2"]),
                     wrap(f"a 14 px mark and two lines per row; {BONES_NOTE}", 11, P["ink3"], lh=1.4), gap=6, extra="width: 240px")
        usage = stack(usage_card(False), mono("Usage silhouette · field value", 10.5, P["ink2"]),
                      flex(text("Workgroups", 12, P["ink2"]), field_bone(5), gap=16, extra="margin-top: 2px"),
                      wrap("four tiles each with a label slot and a value slot, a hairline, fourteen day bars (20 px wide at most), a two-bone legend, then the chart fades in; a field value loads as a 112 × 22 pill; bones breathe 90 ms apart; titles and labels stay text", 11, P["ink3"], lh=1.4),
                      gap=6, extra="width: 500px")
    places = flex(stack(frames(), mono("busy, frame by frame", 10.5, P["ink2"]),
                        wrap("Twin turns side to side, thinking, while its antenna balls pulse in turn", 11, P["ink3"], lh=1.4), gap=6, extra="width: 340px"),
                  rows, *([settings] if mobile else []), usage, *([usage_wide] if mobile else []), gap=22, align="flex-start", extra="flex-wrap: wrap")
    return stack(marks, places, wrap("Colour says who; the wait is always the brand ink. A profile's mark never animates to mean waiting: its working state is a phase at work.", 11.5, P["ink3"]), gap=16)
