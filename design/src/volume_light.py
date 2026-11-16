import itertools
import math

import agent_marks as am
import volume_marks as vm

LIGHT = (-0.55, -0.62, 0.56)
SHADE_SHIFT = 13.0
SHADE_BLUR = 7.0
SHADE_ALPHA = {"light": 0.34, "dark": 0.5}
GLOW_SCALE = 0.62
GLOW_SHIFT = 15.0
GLOW_BLUR = 9.0
GLOW_ALPHA = 0.55
SPOT_RX, SPOT_RY = 9.0, 6.5
SPOT_SHIFT = 27.0
SPOT_BLUR = 3.2
SPOT_ALPHA = 0.85
_IDS = itertools.count()


def centroid(shape):
    pts = [am.place(shape, x, y) for x, y in am.frame(shape)[0]]
    a = cx = cy = 0.0
    for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
        c = x0 * y1 - x1 * y0
        a, cx, cy = a + c, cx + (x0 + x1) * c, cy + (y0 + y1) * c
    return cx / (3 * a), cy / (3 * a)


def local_light(pose):
    ry, rx = math.radians(pose[0]), math.radians(pose[1])
    x, y, z = LIGHT
    x, z = x * math.cos(ry) - z * math.sin(ry), x * math.sin(ry) + z * math.cos(ry)
    y, z = y * math.cos(rx) + z * math.sin(rx), -y * math.sin(rx) + z * math.cos(rx)
    n = math.sqrt(x * x + y * y + z * z)
    return x / n, y / n, z / n


def offsets(pose):
    lx, ly, _ = local_light(pose)
    return {"shade": (lx * SHADE_SHIFT, ly * SHADE_SHIFT), "glow": (lx * GLOW_SHIFT, ly * GLOW_SHIFT), "spot": (lx * SPOT_SHIFT, ly * SPOT_SHIFT)}


def _move(dx, dy):
    return f"translate({dx:.1f}px, {dy:.1f}px)"


def style():
    rules = []
    for s, (sec, seq) in vm.TURN.items():
        for layer in ("shade", "glow", "spot"):
            frames = "".join(f"{at}{{transform: {_move(*offsets((ry, rx, rz))[layer])}}}" for at, ry, rx, rz in seq)
            rules.append(f".vx-{layer}-{s}{{animation-name: vx-{layer}-{s}; animation-duration: {sec}s}}@keyframes vx-{layer}-{s}{{{frames}}}")
    return f"<style>{''.join(rules)}@media (prefers-reduced-motion: reduce){{.vt-a{{animation: none}}}}</style>"


def layer(shape, glow, theme="light", pose=(0, 0, 0), state="idle", live=False):
    d = am.outline(shape)["d"]
    key = next(_IDS)
    cx, cy = centroid(shape)
    moved = offsets(pose)

    def motion(name):
        if live and state in vm.TURN:
            return f'class="vt-a vx-{name}-{state}"'
        return f'style="transform: {_move(*moved[name])}"'

    blur = lambda name, sd: f'<filter id="vx{name}{key}" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="{sd}"/></filter>'
    shade = (f'<g {motion("shade")}><path d="M-60 -60H160V160H-60Z {d}" fill-rule="evenodd" fill="#000" fill-opacity="{SHADE_ALPHA[theme]}" '
             f'filter="url(#vxs{key})"/></g>')
    k = GLOW_SCALE
    inner = f'<path d="{d}" transform="translate({cx * (1 - k):.2f} {cy * (1 - k):.2f}) scale({k})" fill="{glow}" fill-opacity="{GLOW_ALPHA}" filter="url(#vxg{key})"/>'
    spot = f'<ellipse cx="{cx:.1f}" cy="{cy:.1f}" rx="{SPOT_RX}" ry="{SPOT_RY}" fill="{glow}" fill-opacity="{SPOT_ALPHA}" filter="url(#vxp{key})"/>'
    return (f'<defs>{blur("s", SHADE_BLUR)}{blur("g", GLOW_BLUR)}{blur("p", SPOT_BLUR)}<clipPath id="vxc{key}"><path d="{d}"/></clipPath></defs>'
            f'<g clip-path="url(#vxc{key})">{shade}<g {motion("glow")}>{inner}</g><g {motion("spot")}>{spot}</g></g>')
