import json
import os
import subprocess
from functools import lru_cache

import agent_marks as am
import volume_marks as vm

TWIN = am.BRAND_TRIAL
TWIN_INK = "var(--accent, #14110c)"
ROW, HEADER = am.MARK_SIZES["row"], am.MARK_SIZES["header"]
VIEW_SIZE = {16: ROW, 20: HEADER}
SHAPE_OF = {"alpi": "twin", "mira": "dome", "doc": "bell", "abby": "drop", "galt": "squircle", "lingo": "clover", "etxea": "arch"}
MARK_BLUE = am.COLOUR["blue"]
CAST = [
    ("doc", "#3899e2", "blue", "squircle", "idle", dict(selected=True, ts="6w")),
    ("lingo", "#9b5ad9", "violet", "clover", "working", dict(state="working")),
    ("abby", "#df4b9d", "magenta", "drop", "needs", dict(state="needs-you")),
    ("clonara", "#f05940", "vermilion", "bell", "failed", dict(state="failed")),
    ("otto", "#3ac9f3", "sky", "cloud", "working", dict(ts="now")),
    ("galt", "#6572e4", "indigo", "arch", "paused", dict(paused=True)),
    ("etxea", "#3ec173", "green", "bean", "needs", dict(dim=True)),
    ("yuri", "#f36a8a", "rose", "heart", "done", dict(unread=True, ts="2m")),
]
DOC_CAST = CAST[0]
SHAPE_ACCENT = {"round": "amber", "arch": "vermilion", "heart": "rose", "drop": "magenta", "bell": "blue", "pill": "teal",
                "clover": "violet", "pebble": "green", "squircle": "sky", "dome": "indigo", "cloud": "lime", "bean": "orange"}
BRAND_LITERALS = ("#14110c", "#8a5a0a")


def shape_of(shape):
    if shape == "twin":
        return TWIN
    return shape if shape in am.SHAPE_ORDER else am.DEFAULT_SHAPE


def twin(px, state="idle", seed="", still=False, pose=None):
    return vm.mark(am._variant(TWIN, px), TWIN_INK, px, state, seed=seed or TWIN + state, still=still, pose=pose)


def shape_mark(shape, colour, px, state="idle", seed="", still=False):
    if shape_of(shape) == TWIN:
        return twin(px, state, seed)
    return vm.mark(shape_of(shape), colour, px, state, seed=seed or shape, still=still)


def profile(name, colour, px, state="idle"):
    return shape_mark(SHAPE_OF.get(name, am.DEFAULT_SHAPE), colour, VIEW_SIZE.get(px, px), state, seed=name + str(px))


def workgroup(colour, px, state="idle", **kw):
    import workgroup_marks as wg
    return wg.honeycomb(TWIN_INK if colour in BRAND_LITERALS else colour, VIEW_SIZE.get(px, px), state, **kw)


def cast_mark(c, size, state=None):
    name, _, colour, shape, cast_state, _ = c
    return vm.mark(shape, am.COLOUR[colour], size, state or cast_state, seed=name)


def styles():
    import workgroup_marks as wg
    return wg.STYLES


def animated(html):
    return any(k in html for k in ('class="am-', "am-a ", "vt-a ", 'class="vt-held"'))


def accent_of(shape):
    return am.COLOUR[SHAPE_ACCENT[shape_of(shape)]]


@lru_cache(maxsize=None)
def name_tone(accent, ground):
    script = (f"import {{nameTone}} from {json.dumps(os.path.join(am.COMMON, 'name.mjs'))};"
              f"process.stdout.write(JSON.stringify(nameTone({json.dumps(accent)}, {json.dumps(ground)})));")
    out = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)
