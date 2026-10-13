import math

from brand_boards import PAL, PAIR_COLOUR
from conversation_boards import mono
from notif_studies import MONO, VIEW, flex
from paper_studies import text

P = VIEW
ACCENT = PAL[PAIR_COLOUR["tree"]]
SOFT = f"color-mix(in oklch, {ACCENT} 58%, {P['ink']})"
DAYS = ["Oct 4", "Oct 5", "Oct 6", "Oct 7", "Oct 8", "Oct 9", "Oct 10", "Oct 11"]
CHATS = [2161, 1987, 2034, 1902, 1811, 1694, 1915, 1743]
LAST_WEEK = [2050, 2102, 1968, 1990, 1876, 1801, 1940, 1888]
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
AI = [1420, 1310, 1352, 1270, 1215, 1140, 1288]
HUMAN = [741, 677, 682, 632, 596, 554, 627]
TOPICS = [("Booking and availability", 744), ("Amenities and spa", 401), ("Dining and breakfast", 363), ("Transfers and parking", 188)]


def fmt(n):
    return f"{n:,}"


def nice_range(values, zero=False):
    vals = [v for v in values if v is not None]
    lo, hi = (0 if zero else min(vals)), max(vals)
    step = 10 ** math.floor(math.log10(max(hi - lo, 1))) / 2
    while (hi - lo) / step > 4:
        step *= 2
    lo = math.floor(lo / step) * step
    hi = math.ceil(hi / step) * step
    return lo, hi, step


def svg_frame(w, h, inner, label):
    return f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{label}">{inner}</svg>'


def y_grid(lo, hi, step, y_of, x0, x1, size):
    out, v = "", lo
    while v <= hi + 1e-9:
        out += (f'<line x1="{x0}" x2="{x1}" y1="{y_of(v):.1f}" y2="{y_of(v):.1f}" stroke="{P["line2"]}" stroke-width="0.5"/>'
                f'<text x="{x0 - 5}" y="{y_of(v) + 3:.1f}" text-anchor="end" font-family="{MONO}" font-size="{size}" fill="{P["ink3"]}">{fmt(int(v))}</text>')
        v += step
    return out


def chart_card(title, sub, svg, legend=""):
    head = flex(text(title, 12, P["ink"], 600), mono(sub, 10, P["ink3"]), gap=8)
    return f'<div style="display: flex; flex-direction: column; gap: 6px">{head}{svg}{legend}</div>'


def legend_of(items, size=10):
    parts = []
    for name, colour, dashed in items:
        mark_ = (f'<span style="width: 12px; border-top: 1.5px dashed {colour}"></span>' if dashed
                 else f'<span style="width: 9px; height: 9px; border-radius: 2px; background: {colour}"></span>')
        parts.append(f'<span style="display: inline-flex; align-items: center; gap: 5px">{mark_}{mono(name, size, P["ink2"])}</span>')
    return flex(*parts, gap=12)


def line_svg(series, labels, w, h, size=10):
    lo, hi, step = nice_range([v for _, vals, _, _ in series for v in vals])
    pl, pr, pt, pb = 40, 40, 6, 18
    x_of = lambda i: pl + i * (w - pl - pr) / (len(labels) - 1)
    y_of = lambda v: pt + (hi - v) * (h - pt - pb) / (hi - lo)
    body = y_grid(lo, hi, step, y_of, pl, w - pr, size)
    ticks = [(0, "start"), (len(labels) - 1, "end")] if w < 250 else [(0, "start"), (len(labels) // 2, "middle"), (len(labels) - 1, "end")]
    body += "".join(f'<text x="{x_of(i):.1f}" y="{h - 3}" text-anchor="{a}" font-family="{MONO}" font-size="{size}" fill="{P["ink3"]}">{labels[i]}</text>' for i, a in ticks)
    for name, vals, colour, dashed in series:
        runs, run = [], []
        for i, v in enumerate(vals):
            if v is None:
                runs.append(run); run = []
            else:
                run.append(f"{x_of(i):.1f},{y_of(v):.1f}")
        runs.append(run)
        dash = ' stroke-dasharray="3 3"' if dashed else ""
        width = 1.5 if dashed else 2
        body += "".join(f'<polyline points="{" ".join(r)}" fill="none" stroke="{colour}" stroke-width="{width}"{dash} stroke-linejoin="round"/>' for r in runs if len(r) > 1)
    name, vals, colour, _ = series[0]
    last = len(vals) - 1
    body += (f'<circle cx="{x_of(last):.1f}" cy="{y_of(vals[last]):.1f}" r="3" fill="{colour}"/>'
             f'<text x="{x_of(last) + 6:.1f}" y="{y_of(vals[last]) + 3:.1f}" font-family="{MONO}" font-size="{size}" fill="{P["ink"]}">{fmt(vals[last])}</text>')
    return svg_frame(w, h, body, "line chart")


def vbar_svg(series, labels, w, h, stacked=False, size=10):
    totals = [sum(s[1][i] for s in series) for i in range(len(labels))] if stacked else [v for s in series for v in s[1]]
    lo, hi, step = nice_range(totals, zero=True)
    pl, pr, pt, pb = 40, 8, 6, 18
    band = (w - pl - pr) / len(labels)
    y_of = lambda v: pt + (hi - v) * (h - pt - pb) / (hi - lo)
    body = y_grid(lo, hi, step, y_of, pl, w - pr, size)
    for i, lab in enumerate(labels):
        x = pl + i * band
        body += f'<text x="{x + band / 2:.1f}" y="{h - 3}" text-anchor="middle" font-family="{MONO}" font-size="{size}" fill="{P["ink3"]}">{lab}</text>'
        if stacked:
            base = 0
            for name, vals, colour in series:
                top = base + vals[i]
                body += f'<rect x="{x + band * 0.2:.1f}" y="{y_of(top):.1f}" width="{band * 0.6:.1f}" height="{y_of(base) - y_of(top):.1f}" fill="{colour}"/>'
                base = top
        else:
            bw = band * 0.6 / len(series)
            for k, (name, vals, colour) in enumerate(series):
                body += (f'<rect x="{x + band * 0.2 + k * bw:.1f}" y="{y_of(vals[i]):.1f}" width="{bw - 1:.1f}" height="{y_of(0) - y_of(vals[i]):.1f}" '
                         f'fill="{colour}"/>')
    return svg_frame(w, h, body, "bar chart")


def hbar_html(rows, w, size=11, compact=False):
    top = max(v for _, v in rows)
    label_w = 0 if compact else min(max(len(name) for name, _ in rows) * 6.2 + 10, w * 0.45)
    track = w - label_w - (max(len(fmt(v)) for _, v in rows) * 6.2 + 8)
    bar = lambda v: (f'<span style="display: inline-flex; align-items: center; gap: 6px"><span style="width: {max(round(track * v / top), 1)}px; height: 9px; background: {ACCENT}"></span>'
                     f'<span style="font-family: {MONO}; font-size: {size - 1}px; color: {P["ink"]}">{fmt(v)}</span></span>')
    name_of = lambda name: f'<span style="{"" if compact else f"width: {label_w}px; "}font-size: {size}px; color: {P["ink2"]}; white-space: nowrap">{name}</span>'
    direction = "column; align-items: flex-start; gap: 3px" if compact else "row; align-items: center; gap: 0"
    out = "".join(f'<div style="display: flex; flex-direction: {direction}">{name_of(name)}{bar(v)}</div>' for name, v in rows)
    return f'<div style="display: flex; flex-direction: column; gap: 8px; width: {w}px">{out}</div>'


def chart_gallery(w=300, compact=False):
    size = 9 if compact else 10
    second = SOFT
    line = chart_card("Chats per day", "line · 8 days", line_svg([("This week", CHATS, ACCENT, False), ("Last week", LAST_WEEK, second, True)], DAYS, w, 120, size),
                      legend_of([("This week", ACCENT, False), ("Last week", second, True)], size))
    stacked = chart_card("Chats per day", "stacked bar", vbar_svg([("AI", AI, ACCENT), ("Human", HUMAN, second)], WEEKDAYS, w, 120, stacked=True, size=size),
                         legend_of([("AI", ACCENT, False), ("Human", second, False)], size))
    rows = chart_card("Chats by topic", "bar · long labels lie down", hbar_html(TOPICS, w, size + 1, compact))
    return line, stacked, rows
