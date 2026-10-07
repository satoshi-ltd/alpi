import json
import os
import re
import subprocess

from notif_studies import flex, stack, wrap
from paper_studies import text
from wg_settings_studies import P, mono

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
BRAND_INK = "#8a5a0a"
FRAME_TIMES = (0.0, 0.4, 0.8, 1.2)


def _read(*parts):
    with open(os.path.join(ROOT, *parts)) as f:
        return f.read()


def _load_busy():
    common = os.path.join(ROOT, "common")
    script = (
        f"import {{ALPACA_FOLD, foldPolygons}} from {json.dumps(os.path.join(common, 'folds.mjs'))};"
        f"import {{BUSY_WAVE_S, BUSY_DIM, BUSY_DELAY_MS, BUSY_MIN_MS, BUSY_MIN_MARK_PX, busyFacetDelays, busyFacetOrder}} from {json.dumps(os.path.join(common, 'busy.mjs'))};"
        "const polygons = foldPolygons(ALPACA_FOLD, '#14110c', 100).map((p) => p.points);"
        "process.stdout.write(JSON.stringify({polygons, delays: busyFacetDelays(polygons.length), order: busyFacetOrder(), wave: BUSY_WAVE_S, dim: BUSY_DIM,"
        " delay: BUSY_DELAY_MS, min: BUSY_MIN_MS, mark: BUSY_MIN_MARK_PX}));"
    )
    out = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


BUSY = _load_busy()
TOKENS = _read("desktop", "src", "styles", "tokens.css")
DUR_LOOP = float(re.search(r"--dur-loop:\s*([\d.]+)s", TOKENS).group(1))
DUR_SPIN = float(re.search(r"--dur-spin:\s*([\d.]+)s", TOKENS).group(1))
SPINNER_TURN_MS = round(BUSY["wave"] * 1000 / 2)
PULSE_MS = int(re.search(r"duration:\s*(\d+)", _read("mobile", "src", "components", "SkeletonBar.jsx")).group(1))
DESKTOP_CIRCLE = re.search(r'<circle cx="8" cy="8" r="(\d+)" strokeDasharray="([\d ]+)"', _read("desktop", "src", "primitives", "icons.jsx")).groups()
MOBILE_ARC = re.search(r'<Path d="([^"]+)"', _read("mobile", "src", "components", "Spinner.jsx")).group(1)


def wave_level(phase):
    u = phase % 1
    dim = BUSY["dim"]
    return 1 - (1 - dim) * 2 * u if u <= 0.5 else dim + (1 - dim) * (2 * u - 1)


def frame_levels(t):
    return [round(wave_level((t - d) / BUSY["wave"]), 2) for d in BUSY["delays"]]


def _points(points):
    return " ".join(f"{x:.2f},{y:.2f}" for x, y in points)


def alpaca(size, key=None, at=None):
    style = ""
    polys = []
    if key:
        style = (f"<style>@keyframes {key}{{0%, 100%{{opacity: 1}} 50%{{opacity: {BUSY['dim']}}}}}.{key}-f{{animation: {key} {BUSY['wave']}s linear infinite}}"
                 f"@media (prefers-reduced-motion: reduce){{.{key}-f{{animation: none}}}}</style>")
    levels = frame_levels(at) if at is not None else None
    for i, pts in enumerate(BUSY["polygons"]):
        if key:
            extra = f' class="{key}-f" style="fill: {BRAND_INK}; animation-delay: {BUSY["delays"][i]}s"'
        elif levels:
            extra = f' style="fill: {BRAND_INK}; opacity: {levels[i]}"'
        else:
            extra = f' style="fill: {BRAND_INK}"'
        polys.append(f'<polygon points="{_points(pts)}"{extra}/>')
    svg = f'<svg viewBox="0 0 100 100" width="{size}" height="{size}" style="display: block; overflow: visible; flex-shrink: 0">{"".join(polys)}</svg>'
    return f'<span role="img" aria-label="Loading" style="display: inline-flex; flex-shrink: 0">{style}{svg}</span>'


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
    return stack(f'<div style="height: 96px; display: flex; align-items: center; justify-content: center; border-radius: 4px; background: {P["pane"]}; '
                 f'box-shadow: 0 0 0 1px {P["line2"]}">{mark}</div>', mono(name, 10.5, P["ink2"]), wrap(note, 11, P["ink3"], lh=1.4), gap=6, extra=f"width: {w}px")


def frames():
    cells = "".join(stack(f'<div style="height: 56px; display: flex; align-items: center; justify-content: center">{alpaca(44, at=t)}</div>',
                          mono(f"{t:.1f} s", 10, P["ink3"], extra="text-align: center"), gap=4, extra="width: 76px")
                    for t in FRAME_TIMES)
    return f'<div style="display: flex; gap: 6px; padding: 10px 12px; border-radius: 4px; background: {P["pane"]}; box-shadow: 0 0 0 1px {P["line2"]}">{cells}</div>'


def desktop_line(width, height=11, delay=0.0):
    return (f'<span class="sk-line" style="display: block; width: {width}; height: {height}px; border-radius: 2px; animation-delay: {delay:.2f}s"></span>')


DESKTOP_SHIMMER = (f"<style>@keyframes skShimmer{{0%{{background-position: -180% 0}}100%{{background-position: 180% 0}}}}"
                   f".sk-line{{background: linear-gradient(100deg, {P['hover']} 30%, color-mix(in srgb, {P['ink']} 9%, {P['pane']}) 50%, {P['hover']} 70%); "
                   f"background-size: 220% 100%; animation: skShimmer {DUR_LOOP}s ease-in-out infinite}}"
                   f"@media (prefers-reduced-motion: reduce){{.sk-line{{animation: none; background: {P['hover']}}}}}</style>")
MOBILE_PULSE = (f"<style>@keyframes skPulse{{0%, 100%{{opacity: 0.4}}50%{{opacity: 0.8}}}}"
                f".sk-bar{{background: {P['hover']}; animation: skPulse {PULSE_MS * 2 / 1000}s ease-in-out infinite}}"
                f"@media (prefers-reduced-motion: reduce){{.sk-bar{{animation: none; opacity: 0.6}}}}</style>")


def desktop_rows():
    widths = (("46%", "72%"), ("58%", "64%"), ("40%", "78%"))
    rows = "".join(flex(f'<span class="sk-line" style="display: block; width: 14px; height: 14px; border-radius: 2px; flex-shrink: 0; animation-delay: {i * 0.12:.2f}s"></span>',
                        stack(desktop_line(a, 11, i * 0.12), desktop_line(b, 8, i * 0.12 + 0.06), gap=6, extra="flex: 1"), gap=10, extra="padding: 8px 10px")
                   for i, (a, b) in enumerate(widths))
    return f'<div style="width: 240px; padding: 8px; display: flex; flex-direction: column; gap: 4px; border-radius: 4px; background: {P["side"]}; box-shadow: 0 0 0 1px {P["line2"]}">{DESKTOP_SHIMMER}{rows}</div>'


def mobile_bar(width, height, delay):
    return f'<span class="sk-bar" style="display: block; width: {width * 0.72:.0f}px; height: {height}px; border-radius: 4px; animation-delay: {delay}ms"></span>'


def mobile_rows():
    shapes = ((120, 200), (90, 230), (140, 170))
    rows = "".join(f'<div style="min-height: 44px; padding: 12px 16px; display: flex; flex-direction: column; gap: 8px; {"" if i == 0 else "box-shadow: inset 0 0.5px 0 " + P["line"]}">'
                   f'{mobile_bar(a, 12, i * 80)}{mobile_bar(b, 9, i * 80 + 40)}</div>' for i, (a, b) in enumerate(shapes))
    return (f'<div style="width: 240px; padding: 12px; box-sizing: border-box; border-radius: 4px; background: {P["bg"]}; box-shadow: 0 0 0 1px {P["line2"]}">{MOBILE_PULSE}'
            f'<div style="border-radius: 4px; background: {P["pane"]}; overflow: hidden">{rows}</div></div>')


def desktop_button():
    return (f'<span style="height: 28px; padding: 0 12px; border-radius: 4px; background: {P["ink"]}; display: inline-flex; align-items: center; gap: 6px; '
            f'font-size: 12px; font-weight: 500; color: {P["pane"]}">{desktop_spinner(12, P["pane"], 2, 0.6, "dspin1")}Save</span>')


def desktop_stopping():
    return (f'<span aria-label="Stopping" style="width: 32px; height: 32px; border-radius: 4px; background: {P["ink"]}; opacity: 0.65; display: inline-grid; place-items: center">'
            f'{desktop_spinner(14, P["pane"], 1.5, 1, "dspin2")}</span>')


def mobile_button():
    return (f'<span style="height: 40px; min-width: 120px; padding: 0 16px; border-radius: 4px; background: {P["ink"]}; display: inline-flex; align-items: center; justify-content: center">'
            f'{mobile_spinner(20, P["pane"], "mspin1")}</span>')


def busy_inline(label, key):
    return flex(alpaca(BUSY["mark"], key), text(label, 12, P["ink2"]), gap=6)


def busy_page(label, size, key, gap):
    return stack(alpaca(size, key), text(label, 12, P["ink2"]), gap=gap, extra="align-items: center")


def waiting(mobile=False):
    timing = f"after {BUSY['delay']} ms, at least {BUSY['min']} ms on screen, {BUSY['wave']} s wave, opacity only"
    if mobile:
        marks = flex(
            specimen(busy_page("Reaching the daemon", 40, "wm1", 12), "components/Busy · fill", f"the brand alpaca, 40 pt by default; {timing}"),
            specimen(busy_inline("Earlier messages", "wm2"), "components/Busy · 18 + words", "24 pt or less sits in a row with its words; chat history, MCP handshakes"),
            specimen(flex(mobile_button(), mobile_spinner(20, P["ink3"], "mspin2"), gap=14), "components/Spinner",
                     f"a 270° arc turning every {SPINNER_TURN_MS} ms; Button hides its label under it; attachment cards, rich text images, member and model sheets in ink-3"),
            specimen(flex(alpaca(BUSY["mark"]), text("Reaching the daemon", 12, P["ink2"]), gap=6), "reduce motion", "the alpaca stands still and the words carry the wait"),
            gap=14, align="flex-start", extra="flex-wrap: wrap",
        )
        rows = stack(mobile_rows(), mono("ListSkeleton · ReaderSkeleton · SkeletonBar", 10.5, P["ink2"]),
                     wrap(f"no mark: SkeletonBar rows inside the RowGroup card they will fill, opacity 0.4 ↔ 0.8 every {PULSE_MS} ms, 80 ms apart; 0.6 and still under reduce motion", 11, P["ink3"], lh=1.4),
                     gap=6, extra="width: 240px")
    else:
        marks = flex(
            specimen(busy_page("Reaching the daemon", 56, "wd1", 10), "primitives/Busy · page", f"the brand alpaca at 56 px; {timing}"),
            specimen(busy_inline("Fetching latest settings", "wd2"), "primitives/Busy · 18 + words", "a section that waits says for what, in ink-2"),
            specimen(flex(desktop_button(), desktop_stopping(), gap=14), "SpinnerIcon · Button, Chip, Send",
                     f"a dashed circle (r {DESKTOP_CIRCLE[0]}, dash {DESKTOP_CIRCLE[1]}) turning every {DUR_SPIN} s; Send is icon-only and spins only while stopping; also attachments and read aloud"),
            specimen(flex(alpaca(BUSY["mark"]), text("Fetching latest settings", 12, P["ink2"]), gap=6), "reduced motion", "the alpaca stands still and the words carry the wait"),
            gap=14, align="flex-start", extra="flex-wrap: wrap",
        )
        rows = stack(desktop_rows(), mono("SkeletonRows · SkeletonReader", 10.5, P["ink2"]),
                     wrap(f"a 14 px mark and two lines per row, skShimmer every {DUR_LOOP} s with an ink 9 % highlight; flat hover under reduced motion", 11, P["ink3"], lh=1.4),
                     gap=6, extra="width: 240px")
    places = flex(stack(frames(), mono("the wave, frame by frame", 10.5, P["ink2"]),
                        wrap("each facet dims to 0.28 and back over 1.6 s, its delay from the tail to the head", 11, P["ink3"], lh=1.4), gap=6, extra="width: 340px"),
                  rows, gap=22, align="flex-start", extra="flex-wrap: wrap")
    return stack(marks, places, wrap("Colour says who; the wait is always the brand ink. A profile's object never animates to mean waiting: its sweep is a phase at work.", 11.5, P["ink3"]), gap=16)
