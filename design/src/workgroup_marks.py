import math
from functools import lru_cache

import agent_marks as am
import volume_marks as vm
from marks import CAST, name_tone, twin

SQ3 = math.sqrt(3)
PITCH = 43.0
GAP = 5.0
GAP_PX = 1.3
SOFT = 0.55
ORDER = ("left", "top", "right")
FAINT_ALPHA, CHASE_ALPHA, OFFLINE_ALPHA = 0.35, 0.35, 0.3
DANGER = "#c14545"
LIGHT_GROUND = am.LIGHT_GROUNDS[0]
INK = "#6b6b6b"
RING = (7.0, 4.5)
POP = (10.0, 1.04)
ROW, HEADER, PREVIEW, INLINE = am.MARK_SIZES["row"], am.MARK_SIZES["header"], am.MARK_SIZES["list"], am.MARK_SIZES["inline"]
WG_STATES = ("idle", "queued", "running", "needs", "failed", "paused", "offline", "done")
WG_LABEL = {"idle": "idle", "queued": "queued", "running": "running", "needs": "needs you", "failed": "failed", "paused": "paused", "offline": "offline", "done": "done"}
FRONTAL = ("paused", "offline")
SIDE = {"left": 1, "top": 0, "right": -1}
PEOPLE = {c[0]: (c[3], am.COLOUR[c[2]]) for c in CAST}
HUB = "doc"
PIPE = (("fetch", "otto"), ("read", "doc"), ("translate", "lingo"), ("file", "yuri"))
RUN = (2, 4)
WORKING = PIPE[RUN[0]][1]



def gap_for(size):
    return round(max(GAP, GAP_PX * 100 / size), 1)


def _centres():
    y0 = 50 - PITCH * SQ3 * 7 / 24
    low = y0 + PITCH * SQ3 / 2
    return {"left": (50 - PITCH / 2, low), "top": (50, y0), "right": (50 + PITCH / 2, low)}


CENTRES = _centres()
CENTROID = (50.0, sum(y for _, y in CENTRES.values()) / 3)


def _cell_field(cx, cy, gap):
    apothem = (PITCH - gap) / 2
    r = apothem * SOFT
    radius = (apothem - r) / (SQ3 / 2)
    points = [(cx + radius * math.cos(math.radians(-90 + 60 * k)), cy + radius * math.sin(math.radians(-90 + 60 * k))) for k in range(6)]
    return am._poly(points, r)


@lru_cache(maxsize=None)
def _loops(gap):
    return {name: am._march(_cell_field(cx, cy, gap), -8, 112) for name, (cx, cy) in CENTRES.items()}


@lru_cache(maxsize=None)
def cells(gap):
    return {name: am._bezier(am._closed_rdp(loop, 0.14)) for name, loop in _loops(gap).items()}


def current_cell(phase):
    done, total = phase
    return ORDER[min(2, 3 * done // total)]


def _outward(name):
    cx, cy = CENTRES[name]
    dx, dy = cx - CENTROID[0], cy - CENTROID[1]
    n = math.hypot(dx, dy)
    return dx / n * POP[0], dy / n * POP[0]


def _lean(cell, k=1.0):
    s = SIDE[cell]
    return (26 * s * k, (6 if s else -22) * k, -1.5 * s * k)


def _away(cell):
    s = SIDE[cell]
    return (-24 * s, -16, (5 if s else -6) * (s or 1))


TURNS = {
    "idle": (9.6, (("0%,18%", 14, 3, -2), ("26%,42%", -16, 3, 2), ("50%,64%", 2, 13, 0), ("72%,100%", 14, 3, -2))),
    "needs": (2.8, (("0%,6%,60%,100%", 0, 0, 0), ("14%", 0, 4, 0), ("24%", 0, -9, 0), ("33%", 0, 2, 0), ("47%", 0, 0, 0))),
    **{f"running-{c}": (2.4, (("0%,100%", *_lean(c)), ("50%", *_lean(c, 1.25)))) for c in ORDER},
    **{f"failed-{c}": (5.6, (("0%,12%", *_lean(c, 0.25)), ("36%,82%", *_away(c)), ("100%", *_lean(c, 0.25)))) for c in ORDER},
}
STILLS = {"idle": (14, 3, -2), "queued": (14, 3, -2), "needs": (0, 0, 0), **{f"running-{c}": _lean(c) for c in ORDER}, **{f"failed-{c}": _away(c) for c in ORDER}}


def _pop_frames():
    at = lambda k, s: f"transform: translate(calc(var(--ox) * {k}), calc(var(--oy) * {k})) scale({s})"
    return (f"0%,6%,60%,100%{{{at(1, POP[1])}}}14%{{{at(0.4, 0.95)}}}24%{{{at(1.6, 1.12)}}}33%{{{at(0.9, 1.02)}}}40%{{{at(1.15, 1.07)}}}47%{{{at(1, POP[1])}}}")


WG_MOTION = vm.TURN_STYLE + "<style>" + "".join((
    am._keyframes("wg-fill", 2.4, f"0%,100%{{opacity: {CHASE_ALPHA}}}50%{{opacity: 1}}"),
    am._keyframes("wg-chase", 2.4, f"0%,46%,100%{{opacity: {CHASE_ALPHA}}}12%,30%{{opacity: 1}}"),
    am._keyframes("wg-pop", 2.8, _pop_frames()),
    am._keyframes("wg-shiver", 5.6, "0%,14%,100%{transform: none}2%,6%,10%{transform: translate(-1.4px, 0)}4%,8%,12%{transform: translate(1.4px, 0)}"),
    *(vm._keyframes("wg-" + key, sec, "".join(f"{at}{{transform: {vm.rotation(ry, rx, rz)}}}" for at, ry, rx, rz in frames)) for key, (sec, frames) in TURNS.items()),
)) + "</style>"
STYLES = am.MOTION_STYLE + WG_MOTION


def _fill(d, colour, alpha=1.0, cls="", style=""):
    op = f' fill-opacity="{alpha}"' if alpha < 1 else ""
    c = f' class="am-a {cls}"' if cls else ""
    s = f' style="{style}"' if style else ""
    return f'<path d="{d}" fill="{colour}"{op}{c}{s}/>'


def _dashed(d, colour, thin):
    return (f'<path d="{d}" fill="none" stroke="{colour}" stroke-width="{5.5 if thin else 3.6}" '
            f'stroke-dasharray="{"8 6" if thin else "6.5 5"}" stroke-linecap="round"/>')


def _popped(d, name, colour, still):
    cx, cy = CENTRES[name]
    ox, oy = _outward(name)
    if still:
        return f'<g transform="translate({cx + ox:.1f} {cy + oy:.1f}) scale({POP[1]}) translate({-cx:.1f} {-cy:.1f})">{_fill(d, colour)}</g>'
    style = f"transform-origin: {cx:.1f}px {cy:.1f}px; --ox: {ox:.2f}px; --oy: {oy:.2f}px"
    return f'<g class="am-a am-wg-pop" style="{style}">{_fill(d, colour)}</g>'


def _ring(d, colour, thin):
    return f'<path d="{d}" fill="none" stroke="{colour}" stroke-width="{RING[0] if thin else RING[1]}"/>'


def lit_tone(colour, ground=LIGHT_GROUND):
    return (name_tone(colour, ground) or colour) if str(colour).startswith("#") else colour


def _cells(colour, size, state, phase, cell, still, ink, ground=LIGHT_GROUND):
    paths = cells(gap_for(size))
    thin = size < am.SMALL
    pop = size > ROW
    hub = am.rgb(lit_tone(colour, ground))
    lead = cell or (current_cell(phase) if phase else "top")
    k = ORDER.index(lead)
    out = []
    for i, name in enumerate(ORDER):
        d = paths[name]
        if state == "paused":
            out.append(_dashed(d, am.rgb(am.NEUTRAL), thin))
        elif state == "queued":
            out.append(_ring(d, ink, thin))
        elif state == "offline":
            out.append(_fill(d, ink, OFFLINE_ALPHA))
        elif state == "failed":
            out.append(_fill(d, DANGER) if name == lead else _fill(d, ink, FAINT_ALPHA))
        elif state == "needs":
            out.append((_popped(d, name, hub, still) if pop else _fill(d, hub)) if name == lead else _fill(d, ink))
        elif state == "running" and phase:
            if i < k:
                out.append(_fill(d, ink, FAINT_ALPHA))
            elif i == k:
                out.append(_fill(d, hub, 1.0, "" if still else "am-wg-fill"))
            else:
                out.append(_ring(d, ink, thin))
        elif state == "running":
            lag = f"animation-delay: calc(var(--d, 0s) + {0.8 * i:.1f}s)"
            out.append(_fill(d, hub, 1.0 if name == "top" else CHASE_ALPHA, "" if still else "am-wg-chase", "" if still else lag))
        else:
            out.append(_fill(d, ink))
    return "".join(out)


def turn_key(state, phase=None, cell=None):
    if state == "running":
        return "running-" + current_cell(phase) if phase else "idle"
    if state == "failed":
        return "failed-" + (cell or (current_cell(phase) if phase else "top"))
    if state in ("needs", "queued"):
        return state
    return "idle"


def honeycomb(colour, size=ROW, state="idle", phase=None, cell=None, seed="", still=False, pose=None, ink=INK, ground=LIGHT_GROUND):
    live = not still and size > ROW and pose is None
    inner = _cells(colour, size, state, phase, cell, not live, ink, ground)
    if state == "failed" and live:
        inner = f'<g class="am-a am-wg-shiver">{inner}</g>'
    key = turn_key(state, phase, cell)
    if pose is None:
        k = 1 if size > ROW else vm.SMALL_TURN
        pose = (0, 0, 0) if state in FRONTAL else tuple(a * k for a in STILLS[key])
    moving = live and state not in FRONTAL and key in TURNS
    turn = f"vt-a vt-wg-{key} vt-turn" if moving else "vt-turn"
    svg = (f'<svg class="{turn}" viewBox="0 0 100 100" width="{size}" height="{size}" role="img" aria-label="workgroup {WG_LABEL[state]}" data-mark="soft-honeycomb" '
           f'style="display: block; overflow: visible; transform-origin: 50% 50%; transform: {vm.rotation(*pose)}">{inner}</svg>')
    delay = f"; --d: {am._delay((seed or str(colour)) + 'wg'):.1f}s" if live else ""
    return (f'<span class="vt" style="position: relative; display: inline-flex; flex-shrink: 0; width: {size}px; height: {size}px; '
            f'perspective: {size * vm.DEPTH:.0f}px{delay}">{svg}</span>')


def person(name, size=ROW, state="idle", still=False):
    if name == "alpi":
        return twin(size, state)
    shape, colour = PEOPLE[name]
    return vm.mark(shape, colour, size, state, seed=name + str(size), still=still)


def hub_colour(hub):
    return PEOPLE[hub][1]


def running_hub(size, seed):
    return honeycomb(hub_colour(HUB), size, "running", phase=RUN, seed=seed)
