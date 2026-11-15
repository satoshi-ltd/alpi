import json
import os

import agent_marks as am
import volume_marks as vm
import workgroup_marks as wg

COMMON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "common")
WG_SIZES = (12, 14, 16, 20, 24, 28)


def r(v):
    return round(v, 2)


def _shape(name):
    o = am.outline(name)
    ey, dx, cx = am._anchor(name)
    stretch, wobble, pivot = am.CHARACTER[name]
    origin = {"bottom": o["bottom"], "top": o["top"], "centre": 50}[pivot]
    spec = {"d": o["d"], "eyeY": r(ey), "eyeDx": r(dx), "eyeX": r(cx), "stretch": stretch, "wobble": wobble, "originY": r(origin)}
    sig = am.BRAND.get(name, {})
    if "ball" in sig or "balls" in sig:
        spec["balls"] = [{"x": r(x), "y": r(y), "r": r(rad)} for x, y, rad in am.balls(name)]
    return spec


def _key(k):
    t, gx, gy, left, right = k
    return [t, gx, gy, list(left), list(right)]


def _bare(style):
    return style.replace("<style>", "").replace("</style>", "")


def render():
    names = am.SHAPE_ORDER + ["alpi-twin", "alpi-twin-small"]
    data = {
        "SHAPES": {n: _shape(n) for n in names}, "SHAPE_ORDER": am.SHAPE_ORDER,
        "EXPRESSIONS": {name: [[r(x), r(y)] for x, y in am.expression(name)] for name in am.EXPRESSIONS},
        "SEQUENCE": {state: {"dur": dur, "keys": [_key(k) for k in keys]} for state, (dur, keys) in am.SEQUENCE.items()},
        "STILL": {state: _key(k) for state, k in am.STILL.items()},
        "POSE": am.POSE, "LOOK": am.LOOK, "BODY": am.BODY, "MOTION_MIN": am.MOTION_MIN, "MARK_SIZES": am.MARK_SIZES, "SMALL": am.SMALL,
        "EYE_MIN_PX": am.EYE_MIN_PX, "EYE_CAP": am.EYE_CAP, "EYE_PILL_HALF": am.EYE["pill"][0], "EYE_GAP_PX": am.EYE_GAP_PX,
        "EYE_SPLINE": am.EYE_SPLINE,
    }
    out = "".join(f"export const {k} = {json.dumps(v)};\n" for k, v in data.items())
    out += f"export const TURN_CSS = {json.dumps(_bare(vm.TURN_STYLE))};\n"
    out += f"export const TURN = {json.dumps({'still': vm.STILL, 'depth': vm.DEPTH, 'slide': vm.SLIDE, 'squeeze': vm.SQUEEZE, 'smallTurn': vm.SMALL_TURN, 'live': list(vm.TURN)})};\n"
    out += f"export const MOTION_CSS = {json.dumps(_bare(am.MOTION_STYLE))};\n"
    return out


def _turn(spec):
    sec, rows = spec
    out = sorted(([float(pct.rstrip("%")) / 100, r(ry), r(rx), r(rz)] for at, ry, rx, rz in rows for pct in at.split(",")), key=lambda f: f[0])
    return {"dur": sec, "frames": out}


def render_workgroup():
    gaps = sorted({wg.gap_for(s) for s in WG_SIZES})
    data = {
        "WG_ORDER": list(wg.ORDER),
        "WG_CELLS": {str(g): wg.cells(g) for g in gaps},
        "WG_GAP": wg.GAP,
        "WG_GAP_PX": wg.GAP_PX,
        "WG_CENTRES": {k: [r(x), r(y)] for k, (x, y) in wg.CENTRES.items()},
        "WG_OUTWARD": {k: [r(x) for x in wg._outward(k)] for k in wg.ORDER},
        "WG_POP": list(wg.POP),
        "WG_ALPHA": {"faint": wg.FAINT_ALPHA, "chase": wg.CHASE_ALPHA, "offline": wg.OFFLINE_ALPHA},
        "WG_RING": list(wg.RING),
        "WG_DANGER": wg.DANGER,
        "WG_FRONTAL": list(wg.FRONTAL),
        "WG_STATES": list(wg.WG_STATES),
        "WG_TURNS": {k: _turn(v) for k, v in wg.TURNS.items()},
        "WG_STILLS": {k: [r(a) for a in v] for k, v in wg.STILLS.items()},
    }
    return "".join(f"export const {k} = {json.dumps(v)};\n" for k, v in data.items())


GENERATED = {"agentMarks.mjs": render, "workgroupMark.mjs": render_workgroup}


def write(common=COMMON):
    for name, draw in GENERATED.items():
        path = os.path.join(common, name)
        text = draw()
        if os.path.exists(path):
            with open(path) as f:
                if f.read() == text:
                    continue
        tmp = f"{path}.tmp"
        with open(tmp, "w") as f:
            f.write(text)
        os.replace(tmp, path)
