import itertools
import json
import math
import os
import subprocess
from functools import lru_cache

import agent_marks as am
import marks
import volume_marks as vm
from desktop_boards import INK, INK2, INK3, LINE, MONO

LIFT = {"subtle": (0.04, 0.025), "medium": (0.07, 0.045), "strong": (0.2, 0.15)}
CHOSEN = "strong"
CAP_RADIUS = 62
SOFT_RADIUS = 66
SHADE = 0.42
CAP_LEFT = 38
LIGHT_SLIDE = 1.1
EYE_FLOOR = 3
EYE_PAPER = {"light": "#ffffff", "dark": "#000000"}
TWIN_HEX = {"light": am.BRAND_INK, "dark": am.CREAM}
CAST = [("round", "orange"), ("squircle", "blue"), ("drop", "magenta"), ("dome", "amber"), ("clover", "violet"), ("pebble", "lime"), ("heart", "rose"), ("arch", "indigo")]
GROUNDS = (("side", "#f6f6f6", None), ("pane", "#ffffff", None), ("fill", "#f2f2f2", None), ("selected", "#f6f6f6", "rgba(20,20,20,0.08)"))
SIZES = (16, 28, 48, 72)
THRESHOLDS = (("A", 28, "cap from the header, 28 px"), ("B", 48, "cap from the tile, 48 px"))
POSES = (("frontal", (0, 0, 0)), ("held turn", vm.STILL["idle"]), ("turned away", vm.STILL["busy"]))
CHECK_STATES = ("idle", "busy", "working", "needs", "done", "failed")
_CLIPS = itertools.count()


@lru_cache(maxsize=None)
def tones():
    inks = [(name, hex_, hex_) for name, hex_ in am.PALETTE] + [("twin", TWIN_HEX["light"], TWIN_HEX["dark"])]
    common = am.COMMON
    script = (f"import {{markTone}} from {json.dumps(os.path.join(common, 'markTone.mjs'))};"
              f"import {{shiftLightness}} from {json.dumps(os.path.join(common, 'shapes.mjs'))};"
              f"import {{contrastRatio}} from {json.dumps(os.path.join(common, 'name.mjs'))};"
              f"const inks = {json.dumps(inks)}; const lifts = {json.dumps(LIFT)}; const eye = {json.dumps(EYE_PAPER)}; const out = {{}};"
              "for (const [name, light, dark] of inks) {"
              " const body = {light: markTone(light, 'light'), dark};"
              " const caps = {};"
              " for (const [k, [l, d]] of Object.entries(lifts)) {"
              "  const cap = {light: shiftLightness(body.light, l), dark: shiftLightness(body.dark, d)};"
              "  caps[k] = {...cap, eyeCap: {light: contrastRatio(eye.light, cap.light), dark: contrastRatio(eye.dark, cap.dark)}};"
              " }"
              " out[name] = {body, caps, eyeBody: {light: contrastRatio(eye.light, body.light), dark: contrastRatio(eye.dark, body.dark)}};"
              "}"
              "process.stdout.write(JSON.stringify(out));")
    run = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True, check=True)
    return json.loads(run.stdout)


def cap_fill(name, lift=CHOSEN):
    cap = tones()[name]["caps"][lift]
    return f"light-dark({am.rgb(cap['light'])}, {am.rgb(cap['dark'])})"


def held(size, state="idle"):
    k = 1 if size > am.MARK_SIZES["row"] else vm.SMALL_TURN
    return tuple(a * k for a in vm.STILL[state])


def eye_points(shape, size, state, pose):
    ey, _, cx = am._anchor(shape)
    p = am.POSE[state]
    ox, oy = cx + p["shift"], ey + p["lift"]
    sy, sx = math.sin(math.radians(pose[0])), math.sin(math.radians(pose[1]))
    tx, ty = vm.SLIDE[0] * sy, -vm.SLIDE[1] * sx
    kx, ky = 1 - vm.SQUEEZE * abs(sy), 1 - vm.SQUEEZE * abs(sx)
    return [(ox + tx + (x - ox) * kx, oy + ty + (y - oy) * ky) for eye in am.eye_pair(shape, size, am.STILL[state]) for x, y in eye]


def margin(size):
    return max(5.0, 150 / size)


def clearance(points, cx, cy):
    return min(math.hypot(x - cx, y - cy) for x, y in points) - CAP_RADIUS


def cap_circle(shape, size, state, pose):
    points = eye_points(shape, size, state, pose)
    cx = CAP_LEFT - LIGHT_SLIDE * vm.SLIDE[0] * math.sin(math.radians(pose[0]))
    lo, hi = -200.0, 100.0
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if clearance(points, cx, mid) >= margin(size) else (lo, mid)
    return cx, lo, clearance(points, cx, lo)


def light_shift(pose):
    ry, rx = pose[0], pose[1]
    return (-LIGHT_SLIDE * vm.SLIDE[0] * math.sin(math.radians(ry)), LIGHT_SLIDE * vm.SLIDE[1] * math.sin(math.radians(rx)))


def light_style():
    frames = lambda seq: "".join(f"{at}{{transform: translate({light_shift((ry, rx))[0]:.1f}px, {light_shift((ry, rx))[1]:.1f}px)}}" for at, ry, rx, rz in seq)
    rules = "".join(f".vl-{s}{{animation-name: vl-{s}; animation-duration: {sec}s}}@keyframes vl-{s}{{{frames(seq)}}}" for s, (sec, seq) in vm.TURN.items())
    return f"<style>{rules}@media (prefers-reduced-motion: reduce){{.vt-a{{animation: none}}}}</style>"


def capped(shape, colour, size, state="idle", pose=None, lift=CHOSEN, cap=True, ink=None, live=False):
    pose = held(size, state) if pose is None else pose
    html = vm.mark(shape, colour, size, state, still=not live, pose=None if live else pose, seed="cap" + shape)
    if not cap:
        return html
    body = f'<path d="{am.outline(shape)["d"]}" fill="{am.body_fill(colour)}"/>'
    assert body in html, shape
    cx, cy, _ = cap_circle(shape, size, state, (0, 0, 0))
    tone = cap_fill(ink or accent_name(colour), lift)
    key = next(_CLIPS)
    clip, grad = f"vc-{key}", f"vg-{key}"
    stops = "".join(f'<stop offset="{at}" style="stop-color: {tone}; stop-opacity: {op}"/>' for at, op in ((0, 1), (0.35, 0.92), (0.7, 0.4), (1, 0)))
    dx, dy = light_shift(pose)
    motion = f'class="vt-a vl-{state}"' if live and state in vm.TURN else f'style="transform: translate({dx:.1f}px, {dy:.1f}px)"'
    shade_stops = "".join(f'<stop offset="{at}" style="stop-color: #000000; stop-opacity: {op}"/>' for at, op in ((0, SHADE), (0.5, SHADE * 0.55), (1, 0)))
    layer = (f'<defs><radialGradient id="{grad}" cx="50%" cy="50%" r="50%">{stops}</radialGradient>'
             f'<radialGradient id="{grad}s" cx="50%" cy="50%" r="50%">{shade_stops}</radialGradient>'
             f'<clipPath id="{clip}"><path d="{am.outline(shape)["d"]}"/></clipPath></defs>'
             f'<g clip-path="url(#{clip})"><g {motion}><circle cx="{100 - cx:.1f}" cy="{125 - cy:.1f}" r="{SOFT_RADIUS}" fill="url(#{grad}s)"/><circle cx="{cx:.1f}" cy="{cy:.1f}" r="{SOFT_RADIUS}" fill="url(#{grad})"/></g></g>')
    return html.replace(body, body + layer, 1)


def accent_name(colour):
    return next(name for name, hex_ in am.PALETTE if hex_ == colour)


def twin(size, cap=False, pose=None):
    return capped(am._variant(marks.TWIN, size), marks.TWIN_INK, size, pose=pose, cap=cap, ink="twin")


def cast(size=64, lift=CHOSEN, cap=True, pose=None, shapes=CAST, live=False, state="idle"):
    return [capped(shape, am.COLOUR[name], size, state=state, pose=pose, lift=lift, cap=cap, live=live) for shape, name in shapes]


def text(t, size=12, colour=INK3, mono=False):
    family = f"font-family: {MONO}; " if mono else ""
    return f'<span style="{family}font-size: {size}px; line-height: 1.5; color: {colour}">{t}</span>'


def strip(*items, gap=18, align="flex-end"):
    return f'<div style="display: flex; flex-wrap: wrap; gap: {gap}px; align-items: {align}">{"".join(items)}</div>'


def column(*items, gap=10):
    return f'<div style="display: flex; flex-direction: column; gap: {gap}px">{"".join(items)}</div>'


def cell(inner, caption, w=None):
    width = f"width: {w}px; " if w else ""
    return (f'<span style="{width}display: inline-flex; flex-direction: column; align-items: center; gap: 8px">{inner}'
            f'<span style="font-family: {MONO}; font-size: 11px; color: {INK3}; white-space: nowrap">{caption}</span></span>')


def section(title, *items):
    return column(f'<span style="font-size: 17px; font-weight: 600; color: {INK}">{title}</span>', *items, gap=12)


def well(inner, bg="#f6f6f6", pad=20):
    return f'<div style="padding: {pad}px; border-radius: 12px; background: {bg}; border: 0.5px solid {LINE}">{inner}</div>'


def body_now():
    return column(light_style(), strip(*cast(56, cap=False, live=True), twin(56), gap=14), text("Flat paper: the marks turn, but the body never changes."))


def body_proposed():
    return column(strip(*cast(56, live=True), twin(56), gap=14),
                  text("A soft highlight sits on the upper body and glides across it as each mark turns; Twin stays one flat ink."))


def turn_set(cap):
    return strip(*(cell(capped("round", am.COLOUR["orange"], 72, pose=pose, cap=cap), name) + cell(capped("clover", am.COLOUR["violet"], 72, pose=pose, cap=cap), name)
                   for name, pose in POSES), gap=16)


def turn_now():
    return turn_set(False)


def turn_proposed():
    return column(turn_set(True), text("The highlight is feathered, with no edge to read, and slides against the turn like a light that stays put while the mark looks away."))


def intensities():
    rows = []
    for name, (light, dark) in LIFT.items():
        head = column(text(name + (" · recommended" if name == CHOSEN else ""), 13, INK), text(f"ΔL +{light:.3f} light · +{dark:.3f} dark", 11, INK3, mono=True), gap=2)
        rows.append(f'<div style="display: grid; grid-template-columns: 200px 1fr; gap: 16px; align-items: center">{head}{strip(*cast(64, lift=name), gap=16)}</div>')
    return well(column(*rows, gap=18))


def rule():
    lines = (
        "body = markTone(accent, theme)",
        "glow = shiftLightness(body, ΔL[theme])",
        f"ΔL   = {{ light: {LIFT[CHOSEN][0]}, dark: {LIFT[CHOSEN][1]} }}   subtle {LIFT['subtle'][0]} / {LIFT['subtle'][1]} · strong {LIFT['strong'][0]} / {LIFT['strong'][1]}",
        f"fade = radial, r {SOFT_RADIUS}: opaque to 35 %, 40 % at 70 %, clear at the rim; centre x {CAP_LEFT} − {LIGHT_SLIDE} · {vm.SLIDE[0]:g} · sin(turnY), y {LIGHT_SLIDE} · {vm.SLIDE[1]:g} · sin(turnX)",
    )
    code = "".join(f'<span style="font-family: {MONO}; font-size: 12px; line-height: 1.7; color: {INK}; white-space: pre">{line}</span>' for line in lines)
    return well(column(f'<div style="display: flex; flex-direction: column">{code}</div>',
                       text("<code>shiftLightness</code> is the OKLab helper in <code>common/shapes.mjs</code> that <code>nameTone</code> and <code>markTone</code> already use: L + ΔL, "
                            "chroma × 0.85 when lifting, hue kept. In light it starts from the deepened body, so a pale accent's cap lands near its stored accent; "
                            "dark lifts about 0.65 of the light step, so a mark on a dark ground reads lit from above, not lit from within. "
                            "One new shared function, <code>capTone(accent, theme)</code>, beside <code>markTone</code>; the stored accent never changes."), gap=12))


def ground_tile(label, bg, over, shape, colour, start):
    marks_ = "".join(cell(capped(shape, colour, px, cap=px >= start), f"{px}{'' if px >= start else ' flat'}") for px in SIZES)
    inner = f'<div style="display: flex; gap: 14px; align-items: flex-end; justify-content: center">{marks_}</div>'
    if over:
        inner = f'<div style="padding: 12px; border-radius: 8px; background: {over}">{inner}</div>'
    return (f'<div style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 8px">{text(label, 12, INK2)}'
            f'<div style="padding: 18px 12px; border-radius: 12px; background: {bg}; border: 0.5px solid {LINE}; display: flex; justify-content: center">{inner}</div></div>')


def thresholds():
    picks = (("drop", "magenta"), ("pebble", "lime"), ("squircle", "blue"), ("heart", "rose"))
    rows = []
    for key, start, label in THRESHOLDS:
        tiles = "".join(ground_tile(g, bg, over, shape, am.COLOUR[name], start) for (g, bg, over), (shape, name) in zip(GROUNDS, picks))
        rows.append(column(text(f"{key} · {label}", 13, INK), f'<div style="display: flex; gap: 12px">{tiles}</div>', gap=8))
    return column(*rows, text("16 and 24 never wear a cap: the menu bar, the rows and the favicon keep one flat fill, where a 2 px band would read as a smudge. "
                              "A puts the highlight on the chat header, the panels and the tiles; B keeps every list and header flat and only tiles and the hero turn solid. "
                              "Recommended: A, the header is where a profile is looked at, not scanned."), gap=16)


def ratio(value, floor=EYE_FLOOR):
    colour = INK if value >= floor else "#b73737"
    return f'<span style="font-family: {MONO}; font-size: 12px; color: {colour}">{value:.2f}</span>'


def swatch(name, part):
    t = tones()[name]
    pair = t["body"] if part == "body" else t["caps"][CHOSEN]
    return f'<span style="width: 22px; height: 16px; border-radius: 4px; background: light-dark({am.rgb(pair["light"])}, {am.rgb(pair["dark"])})"></span>'


def contrast_table():
    head = ("", "accent", "body", "cap", "eye / body light", "eye / cap light", "eye / body dark", "eye / cap dark")
    grid = "display: grid; grid-template-columns: 40px 90px 50px 50px repeat(4, 1fr); gap: 6px 12px; align-items: center"
    out = [f'<div style="{grid}">' + "".join(text(h, 11, INK3, mono=True) for h in head) + "</div>"]
    rows = [(shape, name, capped(shape, am.COLOUR[name], 28)) for shape, name in am.FAMILY] + [("twin", "twin", twin(28, cap=True))]
    for shape, name, mark in rows:
        t = tones()[name]
        cap = t["caps"][CHOSEN]["eyeCap"]
        out.append(f'<div style="{grid}">{mark}{text(name, 12, INK2)}{swatch(name, "body")}{swatch(name, "cap")}'
                   f'{ratio(t["eyeBody"]["light"])}{ratio(cap["light"], 0)}{ratio(t["eyeBody"]["dark"])}{ratio(cap["dark"], 0)}</div>')
    floor = {k: min(min(tones()[n]["caps"][k]["eyeCap"][th] for n, _ in am.PALETTE) for th in ("light", "dark")) for k in LIFT}
    body_floor = min(tones()[n]["eyeBody"][th] for n, _ in am.PALETTE for th in ("light", "dark"))
    note = (f"Rule 3 still reads eye against body, and every body holds it: lowest {body_floor:.2f}:1. The highlight is drawn under the eyes and fades out well before the rim, "
            f"so the eyes always read against the body first. Eye against the lit centre is shown for the record and is no rule; its lowest across the twelve accents is "
            + ", ".join(f"{k} {floor[k]:.2f}:1" for k in LIFT) + ".")
    return column(well(column(*out, gap=6)), text(note))


def twin_study():
    sizes = (72, 48, 28)
    flat = strip(*(cell(twin(px), f"{px} flat") for px in sizes), gap=18)
    lit = strip(*(cell(twin(px, cap=True), f"{px} cap") for px in sizes), gap=18)
    return column(f'<div style="display: flex; gap: 24px">{well(flat)}{well(lit)}</div>',
                  text("Recommended: Twin stays flat. It is alpi's ink, set beside the wordmark and drawn in one colour on the app icon, menu bar and favicon; "
                       "a near-black cap reads as a smear in light and as a glow on cream in dark, and the cap is what tells a profile from alpi at a glance."))


GATE_NOW = "One flat fill on the body: no outline, no gradient, no shadow, no second colour but the eyes."
GATE_PROPOSED = ("One body fill and, from 28 px, one soft highlight: <code>capTone</code> of the body as a feathered radial fade under the eyes, moving opposite to the turn; "
                 "no outline, no hard edge, no cast shadow, no other colour but the eyes. Twin and every mark under 28 px stay one flat fill.")


def gate():
    def card(title, body):
        return f'<div style="flex: 1; min-width: 0">{well(column(text(title, 12, INK3, mono=True), text(body, 14, INK)), pad=16)}</div>'
    return f'<div style="display: flex; gap: 24px">{card("rule 2 · now", GATE_NOW)}{card("rule 2 · proposed", GATE_PROPOSED)}</div>'


MOTION_STATES = ("idle", "busy", "working", "needs", "done", "failed")


def motion():
    rows = []
    for state in MOTION_STATES:
        flat = strip(cell(capped("round", am.COLOUR["orange"], 72, state=state, cap=False, live=True), "now"), cell(capped("clover", am.COLOUR["violet"], 72, state=state, cap=False, live=True), "now"), gap=16)
        lit = strip(cell(capped("round", am.COLOUR["orange"], 72, state=state, live=True), "proposed"), cell(capped("clover", am.COLOUR["violet"], 72, state=state, live=True), "proposed"), gap=16)
        rows.append(f'<div style="display: grid; grid-template-columns: 110px 1fr 1fr; gap: 16px; align-items: center">{text(state, 13, INK, mono=True)}{well(flat)}{well(lit)}</div>')
    return column(*rows, text("Each row loops the real turn of that state. The highlight is one soft radial fade clipped to the body and drawn under the eyes: it travels opposite to the turn, so the mark reads as a solid lit from the top left. "
                              "It never stops moving with the body and falls still under reduce motion."), gap=14)


def extra():
    return column(light_style(), section("In motion · each turning state, flat paper against the soft highlight", motion()),
                  section("Three intensities · held turn, 64 px", intensities()),
                  section("The derivation", rule()),
                  section("Where the cap starts · 16, 28, 48 and 72 on side, pane, fill and selected", thresholds()),
                  section(f"Eyes against the body · {CHOSEN} cap, 28 px", contrast_table()),
                  section("Twin", twin_study()),
                  section("Brand gate, rule 2", gate()), gap=34)


PROPOSAL = {
    "id": "SHAPE.VOLUME",
    "client": "mobile · desktop",
    "area": "profile marks · Brand gate rule 2",
    "title": "A soft, moving highlight makes the twelve shapes read as 3D solids",
    "why": ("The marks already turn in 3D but are painted as cut paper, so the turn reads as a flat sheet sliding. A feathered highlight of the body's own lighter tone, lit from the top left, "
            "that glides across the body opposite to each turn makes them read as small solids. This is a test of the effect: the edge is soft and the light moves. The highlight is derived from the body, never stored, drawn under the eyes so rule 3 holds untouched, "
            "and is subtler in dark. Recommended: the strong highlight, from the 28 px header up, Twin left flat."),
    "rows": ("Held turn, 56 px", "Turning, 72 px"),
    "mobile": (body_now, body_proposed),
    "desktop": (turn_now, turn_proposed),
    "extra": extra,
    "accept": ("<code>capTone(accent, theme)</code> lives beside <code>markTone</code> in <code>common/markTone.mjs</code> with a test; <code>common/agentMarks.mjs</code> exports the highlight centre per shape; "
               "every profile mark from the chosen threshold draws the highlight, moving with its turn, in both clients and the kit, Twin and smaller marks stay flat; the Brand gate rule 2 reads the proposed wording "
               "and the kit test proves the fade is clear at the rim and the eyes keep their contrast in every still pose; Brand boards regenerated in light and dark."),
    "h": 3100,
}
