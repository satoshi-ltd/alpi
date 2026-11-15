import math

import agent_marks as am

ROW, HEADER = am.MARK_SIZES["row"], am.MARK_SIZES["header"]
DEPTH = 2.6
SLIDE = (18.0, 13.0)
SQUEEZE = 0.32
SMALL_TURN = 0.5
FLAT = ("paused", "offline")
ORIGIN = (50, 55)

TURN = {
    "idle": (9.6, (("0%,18%", 24, 5, -3), ("26%,42%", -26, 4, 3), ("50%,64%", 4, 22, 0), ("72%,100%", 24, 5, -3))),
    "busy": (2.8, (("0%,12%", -22, 16, -3), ("38%,62%", 22, 14, 3), ("88%,100%", -22, 16, -3))),
    "working": (2.4, (("0%,14%", -16, -8, 0), ("24%,38%", -6, -8, 0), ("48%,62%", 6, -8, 0), ("72%,86%", 16, -8, 0), ("100%", -16, -8, 0))),
    "needs": (2.8, (("0%,64%", 0, 8, 0), ("78%,88%", 16, 5, -2), ("100%", 0, 8, 0))),
    "done": (2.4, (("0%,28%", 18, 6, -2), ("50%", -28, 14, 7), ("68%", 10, 4, -2), ("82%,100%", 18, 6, -2))),
    "failed": (5.6, (("0%,12%", 8, 0, 0), ("36%,82%", -28, -20, -5), ("100%", 8, 0, 0))),
}
STILL = {"idle": (22, 5, -3), "busy": (-20, 16, -3), "working": (-12, -8, 0), "needs": (0, 8, 0), "done": (-24, 12, 6), "failed": (-26, -20, -5)}

TURN_TABLE = {
    "idle": ("a slow look around: left, right, then up", "slide where it faces; blinks", "breathes"),
    "busy": ("tilted up, turning side to side, thinking", "raised to one side", "bobs and leans"),
    "working": ("quick small turns, reading across", "slanted, looking down", "squash and stretch"),
    "needs": ("turns to face you square, then hops", "wide ovals, on you", "hop and settle"),
    "done": ("a playful turn at the top", "happy arcs", "a little bounce"),
    "failed": ("turns down and away", "bars slanted down", "shiver, then sink"),
    "paused": ("frontal and still", "closed arcs, grey", "none, dashed outline"),
    "offline": ("frontal and still", "none", "none, at 30 %"),
}


def rotation(ry, rx, rz):
    return f"rotateY({ry:.1f}deg) rotateX({rx:.1f}deg) rotateZ({rz:.1f}deg)"


def parallax(ry, rx):
    sy, sx = math.sin(math.radians(ry)), math.sin(math.radians(rx))
    return (f"translate({SLIDE[0] * sy:.1f}px, {-SLIDE[1] * sx:.1f}px) "
            f"scale({1 - SQUEEZE * abs(sy):.3f}, {1 - SQUEEZE * abs(sx):.3f})")


def _keyframes(name, seconds, frames):
    return f".vt-{name}{{animation-name: vt-{name}; animation-duration: {seconds}s}}@keyframes vt-{name}{{{frames}}}"


QUADRANTS = ((-14, 10), (14, 10), (-14, -8), (14, -8))
CORNERS = (("left", "top"), ("right", "top"), ("left", "bottom"), ("right", "bottom"))
TURN_STYLE = ("<style>.vt-a{animation-delay: var(--d, 0s); animation-iteration-count: infinite; animation-timing-function: cubic-bezier(0.45, 0, 0.25, 1)}"
              ".vt-held{display: block; transform-style: preserve-3d; transition: transform 0.5s cubic-bezier(0.3, 0, 0.2, 1)}"
              ".vt-q{position: absolute; width: 50%; height: 50%}"
              + "".join(f".vt:has(.vt-q{i}:hover) .vt-held{{transform: rotateY({ry}deg) rotateX({rx}deg)}}" for i, (ry, rx) in enumerate(QUADRANTS))
              + "".join(_keyframes("turn-" + s, sec, "".join(f"{at}{{transform: {rotation(ry, rx, rz)}}}" for at, ry, rx, rz in frames))
                        + _keyframes("eyes-" + s, sec, "".join(f"{at}{{transform: {parallax(ry, rx)}}}" for at, ry, rx, rz in frames))
                        for s, (sec, frames) in TURN.items())
              + "@media (prefers-reduced-motion: reduce){.vt-a{animation: none}.vt-turn,.vt-eyes{transform: none !important}.vt-held{transition: none}}</style>")


def pose_at(state, t):
    stops = sorted((float(at.rstrip("%")) / 100, (ry, rx, rz)) for ats, ry, rx, rz in TURN[state][1] for at in ats.split(","))
    for (t0, a), (t1, b) in zip(stops, stops[1:]):
        if t0 <= t <= t1:
            k = 0 if t1 == t0 else (t - t0) / (t1 - t0)
            k = k * k * (3 - 2 * k)
            return tuple(x + (y - x) * k for x, y in zip(a, b))
    return stops[-1][1]


def _eyes(shape, colour, size, state, pose, live):
    pair = am.eyes(shape, colour, size, state, True, am.EYE_INK)
    ey, _, cx = am._anchor(shape)
    p = am.POSE[state]
    origin = f"transform-origin: {cx + p['shift']:.1f}px {ey + p['lift']:.1f}px"
    if live and state in am.LOOK:
        pair = f'<g class="am-a am-lid-{am.LOOK[state]}" style="{origin}">{pair}</g>'
    cls = f"vt-a vt-eyes-{state} vt-eyes" if live else "vt-eyes"
    return f'<g class="{cls}" style="{origin}; transform: {parallax(pose[0], pose[1])}">{pair}</g>'


def figure(shape, colour, size, state, pose, live, theme=None):
    o = am.outline(shape)
    if state == "paused":
        thin = size < am.SMALL
        return (f'<path d="{o["d"]}" fill="none" stroke="{am.rgb(am.NEUTRAL)}" stroke-width="{5.5 if thin else 3.6}" '
                f'stroke-dasharray="{"8 6" if thin else "6.5 5"}" stroke-linecap="round"/>' + am.eyes(shape, colour, size, state, True, fill=am.rgb(am.NEUTRAL)))
    if state in FLAT:
        return am.figure(shape, colour, size, state, True, theme=theme)
    return am._filled(o["d"], am.body_fill(colour, theme), _eyes(shape, colour, size, state, pose, live) + am._signature(shape, state, not live))


def mark(shape, colour, size=16, state="idle", seed="", still=False, held=False, pose=None, theme=None):
    live = not still and size > ROW and state in TURN and pose is None
    if pose is None:
        k = 1 if size > ROW else SMALL_TURN
        pose = tuple(a * k for a in STILL.get(state, (0, 0, 0)))
    inner = figure(shape, colour, size, state, pose, live, theme)
    if live and state in am.BODY:
        o = am.outline(shape)
        stretch, wobble, pivot = am.CHARACTER[shape]
        oy = {"bottom": o["bottom"], "top": o["top"], "centre": 50}[pivot]
        inner = f'<g class="am-a am-body-{am.BODY[state]}" style="--s: {stretch}; --w: {wobble}; transform-origin: 50px {oy:.1f}px">{inner}</g>'
    turn = f"vt-a vt-turn-{state} vt-turn" if live else "vt-turn"
    svg = (f'<svg class="{turn}" viewBox="0 0 100 100" width="{size}" height="{size}" role="img" aria-label="{shape} turning {am.STATE_LABEL[state]}" data-mark="{shape}" '
           f'style="display: block; overflow: visible; transform-origin: 50% 55%; transform: {rotation(*pose)}">{inner}</svg>')
    if live and held:
        svg = f'<span class="vt-held">{svg}</span>' + "".join(f'<span class="vt-q vt-q{i}" style="{x}: 0; {y}: 0"></span>' for i, (x, y) in enumerate(CORNERS))
    delay = f"; --d: {am._delay((seed or shape) + 'turn'):.1f}s" if live else ""
    return (f'<span class="vt" style="position: relative; display: inline-flex; flex-shrink: 0; width: {size}px; height: {size}px; '
            f'perspective: {size * DEPTH:.0f}px{delay}">{svg}</span>')


def project(points, pose):
    ry, rx, rz = (math.radians(a) for a in pose)
    ox, oy = ORIGIN
    out = []
    for x, y in points:
        px, py, pz = x - ox, y - oy, 0.0
        px, py = px * math.cos(rz) - py * math.sin(rz), px * math.sin(rz) + py * math.cos(rz)
        py, pz = py * math.cos(rx) - pz * math.sin(rx), py * math.sin(rx) + pz * math.cos(rx)
        px, pz = px * math.cos(ry) + pz * math.sin(ry), -px * math.sin(ry) + pz * math.cos(ry)
        w = 1 - pz / (100 * DEPTH)
        out.append((50 + (px + ox - 50) / w, 50 + (py + oy - 50) / w))
    return out


def turned_parts(shape, size, pose):
    shape = am._variant(shape, size)
    body = project(am._closed_rdp([am.place(shape, x, y) for x, y in am.frame(shape)[0]], 0.14), pose)
    ey, _, cx = am._anchor(shape)
    still = am.POSE["idle"]
    ox, oy = cx + still["shift"], ey + still["lift"]
    sy, sx = math.sin(math.radians(pose[0])), math.sin(math.radians(pose[1]))
    slide, squeeze = (SLIDE[0] * sy, -SLIDE[1] * sx), (1 - SQUEEZE * abs(sy), 1 - SQUEEZE * abs(sx))
    eyes = [project([(ox + slide[0] + (x - ox) * squeeze[0], oy + slide[1] + (y - oy) * squeeze[1]) for x, y in eye], pose)
            for eye in am.eye_pair(shape, size, am.STILL["idle"])]
    return body, eyes


def turned_figure(shape, colour, size, pose=None, eye=None):
    body, eyes = turned_parts(shape, size, pose or STILL["idle"])
    if eye is None:
        return am._masked(am._bezier(body), am.rgb(colour), "".join(f'<path d="{am._d(e)}" fill="#000"/>' for e in eyes))
    return am._filled(am._bezier(body), am.rgb(colour), "".join(f'<path d="{am._d(e)}" fill="{eye}"/>' for e in eyes))


def turned(shape, colour, size, pose=None, eye=am.EYE_INK):
    return (f'<svg viewBox="0 0 100 100" width="{size}" height="{size}" role="img" aria-label="{shape} turned" data-mark="{shape}" '
            f'style="flex-shrink: 0; display: block; overflow: visible">{turned_figure(shape, colour, size, pose, eye)}</svg>')


def turned_icon(shape, concept, size, bleed=False, pose=None):
    pose = pose or STILL["idle"]
    body, _ = turned_parts(shape, 100, pose)
    xs, ys = [x for x, _ in body], [y for _, y in body]
    left, right, top, bottom = min(xs), max(xs), min(ys), max(ys)
    if am.ICONS[concept]["zoom"] is None:
        scale, edge = am.CLOSE[shape]
        ty = edge - scale * (top - 50)
    else:
        scale = am.ICON_SIDE * am.ICON_FILL / max(right - left, bottom - top)
        ty = 50 - scale * ((top + bottom) / 2 - 50)
    tx = 50 - scale * ((left + right) / 2 - 50)
    px = size * scale / (am.ICON_SIDE / 100 if bleed else 1)
    return am.icon_svg(shape, concept, size, turned_figure(shape, am.ICONS[concept]["body"], px, pose), (scale, tx, ty), not bleed, bleed)
