import folds
from brand_boards import PAL, PAIR_COLOUR
from conversation_boards import mono
from desktop_boards import INK, INK3

def palette(bg, side, pane, elev, inks, rgb, dark=False):
    a = (0.08, 0.16, 0.045, 0.07) if dark else (0.07, 0.14, 0.04, 0.06)
    return {"bg": bg, "side": side, "pane": pane, "elev": elev, "ink": inks[0], "ink2": inks[1], "ink3": inks[2], "ink4": inks[3],
            "line": f"rgba({rgb}, {a[0]})", "line2": f"rgba({rgb}, {a[1]})", "hover": f"rgba({rgb}, {a[2]})", "selected": f"rgba({rgb}, {a[3]})",
            "danger": "#F08080" if dark else "#B73737", "dark": dark}

NEUTRAL = {
    "light": palette("#F0F0F0", "#F6F6F6", "#FFFFFF", "#FFFFFF", ("rgb(20, 20, 20)", "rgb(69, 69, 69)", "#6B6B6B", "#B4B4B4"), "20, 20, 20"),
    "dark": palette("#0B0B0B", "#0F0F0F", "#151515", "#1B1B1B", ("#EDEDED", "#B4B4B4", "#8A8A8A", "#4A4A4A"), "237, 237, 237", True),
}

NOW = {"radius": 8, "card": 12, "edge": "ring", "pop": "shadow", "button": "soft", "field": "box", "select": "fill", "chip": "pill"}
PAPER = {"radius": 4, "card": 4, "edge": "tone", "pop": "seam", "button": "crisp", "field": "well", "select": "tab", "chip": "tag"}

def object_mark(shape, size):
    return folds.fold(shape, PAL[PAIR_COLOUR[shape]], size)

def text(value, size, color, weight=400, extra=""):
    return f'<span style="font-size: {size}px; font-weight: {weight}; line-height: 1.3; color: {color}; white-space: nowrap; {extra}">{value}</span>'

def caption(value):
    return mono(value, 11, INK3)

def note(title, body):
    return (f'<div style="display: flex; flex-direction: column; gap: 4px"><span style="font-size: 14px; font-weight: 600; color: {INK}">{title}</span>'
            f'<span style="font-size: 12px; line-height: 1.5; color: {INK3}; max-width: 520px">{body}</span></div>')

def column(*items, gap=10):
    return f'<div style="display: flex; flex-direction: column; gap: {gap}px">{"".join(items)}</div>'

def line_up(*items, gap=10, wrap=True):
    return f'<div style="display: flex; align-items: center; gap: {gap}px; flex-wrap: {"wrap" if wrap else "nowrap"}">{"".join(items)}</div>'

def clip(kind, r):
    if kind == "dogear":
        return "clip-path: polygon(0 0, calc(100% - 8px) 0, 100% 8px, 100% 100%, 0 100%);"
    if kind == "chamfer":
        return "clip-path: polygon(4px 0, calc(100% - 4px) 0, 100% 4px, 100% calc(100% - 4px), calc(100% - 4px) 100%, 4px 100%, 0 calc(100% - 4px), 0 4px);"
    return f"border-radius: {r}px;"

def button(label, kind, p, s, height=32, icon=False):
    filled = kind in ("primary", "danger")
    bg = {"primary": p["ink"], "danger": "#C14545", "secondary": p["selected"] if s["button"] != "soft" else p["hover"], "ghost": "transparent"}[kind]
    fg = {"primary": p["pane"], "danger": "#FFFFFE", "secondary": p["ink"], "ghost": p["ink2"]}[kind]
    radius = s["radius"] if s["button"] != "soft" else 8
    shape = clip(s["button"], radius) if filled or s["button"] != "dogear" else f"border-radius: {radius}px;"
    width = f"width: {height}px; padding: 0;" if icon else f"padding: 0 {12 if height <= 32 else 16}px;"
    flap = ""
    if filled and s["button"] == "dogear":
        flap = (f'<span style="position: absolute; top: 0; right: 0; width: 8px; height: 8px; background: color-mix(in srgb, {bg} 55%, {p["pane"]}); '
                f'clip-path: polygon(0 0, 0 100%, 100% 100%)"></span>')
    body = "+" if icon else label
    return (f'<span style="position: relative; display: inline-flex; flex-shrink: 0"><span style="display: inline-flex; align-items: center; justify-content: center; height: {height}px; {width} '
            f'{shape} background: {bg}; color: {fg}; font-size: {12 if height < 32 else 13}px; font-weight: 500; line-height: 1; white-space: nowrap; box-sizing: border-box">{body}</span>{flap}</span>')

def field(placeholder, p, s, width=None, focus=False):
    w = f"width: {width}px;" if width else "flex: 1; min-width: 0;"
    if s["field"] == "box":
        edge = f"background: {p['pane']}; border: 0.5px solid {p['ink3'] if focus else p['line2']}; border-radius: 8px;"
        if focus:
            edge += f" box-shadow: 0 0 0 4px {p['hover']};"
    elif s["field"] == "well":
        ring = f" box-shadow: inset 0 0 0 1px color-mix(in srgb, {p['ink']} 30%, transparent);" if focus else ""
        edge = f"background: {p['selected'] if focus else p['hover']}; border-radius: {s['radius']}px;{ring}"
    else:
        edge = f"background: transparent; border-bottom: {'1.5px' if focus else '1px'} solid {p['ink'] if focus else p['line2']};"
    return (f'<span style="{w} height: 32px; padding: 0 10px; box-sizing: border-box; display: inline-flex; align-items: center; {edge} '
            f'font-size: 13px; color: {p["ink3"]}; white-space: nowrap">{placeholder}</span>')

def themed(title, body, render):
    return column(note(title, body), caption("light"), render("light"), caption("dark"), render("dark"), gap=8)

def deep(colour, p):
    return f"color-mix(in srgb, {colour} {78 if p['dark'] else 62}%, {p['ink']})"
