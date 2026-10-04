import folds
from brand_boards import PAL, PAIR_COLOUR
from gen import ic
from notif_studies import MONO, VIEW, dot, ell, flex, spacer, stack, wrap
from paper_studies import text

P = VIEW
GREEN_BG, GREEN_FG = "rgba(63,179,122,0.16)", "#217a45"

PROFILES = {"mira": "crown", "scout": "house", "muse": "star", "quill": "feather", "lingua": "plane", "pixel": "rocket", "lens": "shield"}
BIOS = {
    "mira": "Project manager. Coordinates one hotel workgroup through setup, enrich, intake, assets, content, translation, build, and QA.",
    "scout": "Intake producer. Converts the hotel brief into factual canonical inputs for the Astro template.",
    "muse": "Asset producer. Maps approved hotel media to manifest slots and records explicit placeholders for gaps.",
    "quill": "Content producer. Writes complete source-locale hotel content without touching configuration or runtime code.",
    "lingua": "Localization producer. Produces a structurally complete and natural version of every enabled page, collection, and post for every configured locale.",
    "pixel": "Setup and build producer. Initializes a cloned hotel project and runs the template’s deterministic asset, build, and verification commands.",
    "lens": "QA gate. Audits the selected-tier dist for factual, localization, routing, SEO, asset, and integration quality before internal review.",
}
RECIPE = [
    ("setup", [("setup", "pixel"), ("enrich", "scout"), ("intake", "scout"), ("assets", "muse"), ("content", "quill"), ("translation", "lingua"), ("build", "pixel"), ("qa", "lens")]),
    ("media-update", [("media-update", "muse"), ("media-build", "pixel"), ("media-qa", "lens")]),
    ("content-update", [("content-update", "scout"), ("content-media", "muse"), ("content-copy", "quill"), ("content-locales", "lingua"), ("content-build", "pixel"), ("content-qa", "lens")]),
    ("review", [("review", "scout"), ("review-config", "scout"), ("review-content", "quill"), ("review-translation", "lingua"), ("review-media", "muse"), ("review-build", "pixel"),
                ("review-qa", "lens"), ("review-close", "lens")]),
    ("upgrade", [("upgrade", "pixel"), ("upgrade-build", "pixel"), ("upgrade-qa", "lens")]),
]
PIPELINES = [(key, [slug for slug, _ in chain]) for key, chain in RECIPE]
LAUNCH = "setup"
OWNER = {slug: name for _, chain in RECIPE for slug, name in chain}
WG_NAME = "site-hotel-victoire-v109"
RUN = {"setup": "completed", "enrich": "completed", "intake": "completed", "assets": "skipped", "content": "current"}
DATABASE = '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5V19A9 3 0 0 0 21 19V5"/><path d="M3 12A9 3 0 0 0 21 12"/>'


def owned(name):
    return [slug for _, chain in PIPELINES for slug in chain if OWNER[slug] == name]


def accent(name):
    return PAL[PAIR_COLOUR[PROFILES[name]]]


def obj(name, size=14):
    return f'<span style="display: inline-flex; flex-shrink: 0">{folds.fold(PROFILES[name], accent(name), size)}</span>'


def rippling(name, size=14, key="rip"):
    style = folds.sweep_style(key, accent(name), 2.4)
    svg = folds.fold(PROFILES[name], accent(name), size, facet_attrs=folds.sweep_attrs(key, 2.4))
    return f'<span style="display: inline-flex; flex-shrink: 0">{style}{svg}</span>'


def unfolded(name, size=14):
    return f'<span style="display: inline-flex; flex-shrink: 0">{folds.outline(PROFILES[name], P["ink4"], size)}</span>'


def crease_name(name, size=16, label=None, colour=None):
    colour = colour or accent(name)
    tones = [f"color-mix(in srgb, {colour} {pct}%, {P['ink']})" for pct in (82, 66, 52)]
    slit = max(0.6, round(size * 0.011, 2))
    stops = (f"{tones[0]} 0 calc(33% - {slit}px), transparent calc(33% - {slit}px) calc(33% + {slit}px), {tones[1]} calc(33% + {slit}px) calc(66% - {slit}px), "
             f"transparent calc(66% - {slit}px) calc(66% + {slit}px), {tones[2]} calc(66% + {slit}px) 100%")
    return (f'<span style="font-family: \'Bricolage Grotesque\', Geist, sans-serif; font-size: {size}px; font-weight: 800; letter-spacing: -0.02em; line-height: 1.05; '
            f'background: linear-gradient(115deg, {stops}); -webkit-background-clip: text; background-clip: text; color: transparent; white-space: nowrap; flex-shrink: 0">{label or name}</span>')


def mono(value, size=11, color=None, weight=400, extra=""):
    return f'<span style="font-family: {MONO}; font-size: {size}px; font-weight: {weight}; color: {color or P["ink3"]}; white-space: nowrap; flex-shrink: 0; {extra}">{value}</span>'


def glyph(name, size=12, color=None):
    if name == "database":
        return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color or P["ink3"]}" stroke-width="2" stroke-linecap="round" '
                f'stroke-linejoin="round" aria-hidden="true" data-icon="database" style="flex-shrink: 0; display: block">{DATABASE}</svg>')
    return ic(name, size, color or P["ink3"])


def tag(value, size=10.5, color=None, bg=None):
    return (f'<span style="display: inline-flex; align-items: center; height: {round(size * 1.75)}px; padding: 0 5px; border-radius: 2px; background: {bg or P["hover"]}; '
            f'font-family: {MONO}; font-size: {size}px; color: {color or P["ink2"]}; white-space: nowrap; flex-shrink: 0">{value}</span>')


def tags(values, size=10.5, gap=4):
    return f'<div style="display: flex; flex-wrap: wrap; gap: {gap}px; min-width: 0">{"".join(tag(v, size) for v in values)}</div>'


def status(word, tone="ink", size=11):
    colour = {"ink": P["ink"], "off": P["ink4"], "danger": P["danger"]}[tone]
    label = {"ink": P["ink2"], "off": P["ink3"], "danger": P["danger"]}[tone]
    return flex(dot(colour, 6), mono(word, size, label), gap=5, extra="flex-shrink: 0")


def sheet(inner, h=None, pad=0, bg=None):
    height = f"height: {h}px;" if h else ""
    return (f'<div style="{height} box-sizing: border-box; padding: {pad}px; border-radius: 4px; background: {bg or P["pane"]}; box-shadow: 0 0 0 1px {P["line2"]}; '
            f'overflow: hidden; display: flex; flex-direction: column; min-width: 0">{inner}</div>')


def phone(inner, h, w=340):
    return (f'<div style="width: {w}px; height: {h}px; flex-shrink: 0; box-sizing: border-box; border-radius: 16px; background: {P["bg"]}; box-shadow: 0 0 0 1px {P["line2"]}; '
            f'overflow: hidden; display: flex; flex-direction: column">{inner}</div>')


def section_label(value, pad="14px 18px 6px"):
    return f'<div style="padding: {pad}; font-family: {MONO}; font-size: 10.5px; letter-spacing: 0.08em; text-transform: uppercase; color: {P["ink3"]}">{value}</div>'


def group(inner, margin="0 12px"):
    return f'<div style="margin: {margin}; border-radius: 4px; background: {P["pane"]}; overflow: hidden">{inner}</div>'


def seam():
    return f'<div style="height: 0.5px; background: {P["line"]}"></div>'


def caption(value):
    return wrap(value, 11.5, P["ink3"], lh=1.5)


def labelled(title, inner, note=""):
    return stack(mono(title, 10.5, P["ink3"], extra="letter-spacing: 0.06em; text-transform: uppercase"), inner, caption(note) if note else "", gap=8)


def green_pill(value):
    return (f'<span style="display: inline-flex; align-items: center; gap: 4px; height: 18px; padding: 0 6px; border-radius: 2px; background: {GREEN_BG}; '
            f'font-family: {MONO}; font-size: 10.5px; color: {GREEN_FG}; flex-shrink: 0">{dot("#3fb37a", 7)}{value}</span>')


def arrow():
    return f'<span style="font-size: 10px; color: {P["ink3"]}; flex-shrink: 0">→</span>'


def phase_chip(slug, state=None, key="rip", owner=True, assignee=None, strong=False, height=21, size=10.5):
    name = OWNER.get(slug) if owner else None
    working = state == "current" and not assignee
    lead = (rippling(name, size + 1.5, key) if working else obj(name, size + 1.5)) if name else ""
    slug_colour = {"completed": P["ink"], "current": P["ink"], "skipped": P["ink3"], "blocked": P["ink"]}.get(state, P["ink2"])
    deco = "text-decoration: line-through;" if state == "skipped" else ""
    weight = "font-weight: 600;" if strong and state in ("current", "blocked") else ""
    handoff = ""
    if assignee:
        handoff = flex(arrow(), rippling(assignee, size + 1.5, key) if state == "current" else obj(assignee, size + 1.5), mono("@" + assignee, size, P["ink"], 600 if strong else 400), gap=3,
                       extra="flex-shrink: 0")
    tail = ""
    if state == "completed":
        tail = glyph("check", 10, P["ink"])
    elif state == "current":
        tail = mono("running", size - 1, P["ink2"])
    elif state == "skipped":
        tail = mono("skipped", size - 1, P["ink3"])
    elif state == "blocked":
        tail = mono("blocked", size - 1, P["danger"], 500)
    bg = P["selected"] if state in ("current", "blocked") else P["hover"]
    ring = f"box-shadow: inset 0 0 0 1px color-mix(in srgb, {P['danger']} 45%, transparent);" if state == "blocked" else ""
    title = f"{slug} · {name}" if name else slug
    pad = "0 6px 0 4px" if name else "0 6px"
    return (f'<span title="{title}" style="display: inline-flex; align-items: center; gap: 4px; height: {height}px; padding: {pad}; border-radius: 2px; background: {bg}; {ring} flex-shrink: 0">'
            f'{lead}<span style="font-family: {MONO}; font-size: {size}px; color: {slug_colour}; white-space: nowrap; {weight} {deco}">#{slug}</span>{handoff}{tail}</span>')


def chain_flow(chain, states=None, key="rip", gap=4):
    states = states or {}
    parts = []
    for i, slug in enumerate(chain):
        parts.append(f'<span style="display: inline-flex; align-items: center; gap: {gap}px">{phase_chip(slug, states.get(slug), key)}{arrow() if i < len(chain) - 1 else ""}</span>')
    return f'<div style="display: flex; flex-wrap: wrap; align-items: center; gap: 5px {gap}px; min-width: 0">{"".join(parts)}</div>'


def run_summary(states, chain):
    done = sum(1 for s in chain if states.get(s) in ("completed", "skipped"))
    return flex(mono("last run", 10, P["ink3"]), mono(f"running · {done} of {len(chain)}", 10, P["ink2"]), mono("$2.41", 10, P["ink3"]), gap=6)


def trigger_word(key):
    return mono("starts at launch" if key == LAUNCH else "on demand", 10, P["ink3"])


def pipeline_block(key, chain, states=None, pad="10px 16px", key_id="rip"):
    head = flex(mono(key, 12, P["ink"], 600), trigger_word(key), spacer(), run_summary(states, chain) if states else "", gap=8)
    return f'<div style="padding: {pad}; box-shadow: inset 0 0.5px 0 {P["line"]}; display: flex; flex-direction: column; gap: 8px">{head}{chain_flow(chain, states, key_id)}</div>'


def legend():
    items = [phase_chip("intake", "completed"), phase_chip("assets", "skipped"), phase_chip("content", "current", "lg"), phase_chip("content", "blocked"), phase_chip("translation")]
    return f'<div style="display: flex; flex-wrap: wrap; gap: 6px; align-items: center">{"".join(items)}</div>'


def row_menu():
    item = lambda label, colour, icon: flex(glyph(icon, 12, colour), text(label, 11.5, colour), gap=8, extra="padding: 6px 10px")
    return (f'<div style="position: absolute; right: 12px; top: 34px; z-index: 2; width: 196px; padding: 4px 0; border-radius: 4px; background: {P["elev"]}; '
            f'box-shadow: 0 0 0 1px {P["line2"]}">{item("Open @pixel", P["ink"], "chevron-right")}{item("Copy profile id", P["ink"], "copy")}'
            f'<div style="height: 0.5px; margin: 4px 0; background: {P["line"]}"></div>{item("Remove from workgroup…", P["danger"], "x")}</div>')


def more_glyph(phone, active=False):
    return (f'<span style="width: {44 if phone else 24}px; height: {44 if phone else 22}px; margin: {"-12px -12px -12px 0" if phone else "-3px 0"}; display: inline-flex; '
            f'align-items: center; justify-content: center; flex-shrink: 0; border-radius: 4px; background: {P["hover"] if active else "transparent"}">{glyph("more", 14, P["ink2"])}</span>')


def member_block(name, expanded=False, menu=False, phone=False):
    hub = mono("hub", 10, P["ink3"], extra="letter-spacing: 0.04em") if name == "mira" else ""
    head = flex(crease_name(name, 17 if phone else 16), hub, spacer(), more_glyph(phone, menu), gap=7)
    size = 12.5 if phone else 11.5
    if expanded:
        bio = flex(wrap(BIOS[name], size, P["ink2"], lh=1.45, extra="flex: 1"), gap=6, align="flex-start")
    else:
        bio = ell(BIOS[name], size, P["ink2"], extra="flex: 1")
    phases = owned(name)
    held = tags(["#" + s for s in phases], 10) if phases else mono("none · the hub routes every phase", 10, P["ink3"])
    owns = flex(mono("owns", 9.5, P["ink4"], extra="width: 30px"), held, gap=6, align="flex-start")
    body = stack(head, bio, owns, gap=5, extra="flex: 1")
    edge = "" if phone else f"box-shadow: inset 0 0.5px 0 {P['line']};"
    pad = "12px 14px" if phone else "10px 14px 10px 16px"
    return (f'<div style="position: relative; display: flex; gap: 10px; align-items: flex-start; padding: {pad}; {edge}">'
            f'<span style="padding-top: 1px; display: inline-flex">{obj(name, 18 if phone else 16)}</span>{body}{row_menu() if menu else ""}</div>')


def m_pipeline_card(key, chain, states=None):
    head = flex(mono(key, 14, P["ink"], 600), trigger_word(key), spacer(), gap=8)
    done = sum(1 for s in chain if (states or {}).get(s) in ("completed", "skipped"))
    run = flex(mono("last run", 10.5, P["ink3"]), mono(f"running · {done} of {len(chain)}", 10.5, P["ink2"]), gap=6) if states else ""
    return group(f'<div style="padding: 12px 14px; display: flex; flex-direction: column; gap: 9px">{head}{run}{chain_flow(chain, states, "mrip")}</div>', "0 12px 8px")


def invited_block(name, fold_name, colour, bio, phone=False):
    head = flex(f'<span style="font-family: Bricolage Grotesque, sans-serif; font-weight: 800; font-size: {17 if phone else 16}px; color: {colour}">{name}</span>',
                mono("invited", 10, P["ink3"]), spacer(), more_glyph(phone), gap=7)
    body = stack(head, ell(bio, 12.5 if phone else 11.5, P["ink2"]), gap=5, extra="flex: 1")
    edge = "" if phone else f"box-shadow: inset 0 0.5px 0 {P['line']};"
    mark = folds.fold(fold_name, colour, 18 if phone else 16)
    return (f'<div style="display: flex; gap: 10px; align-items: flex-start; padding: {"12px 14px" if phone else "10px 14px 10px 16px"}; {edge}">'
            f'<span style="padding-top: 1px; display: inline-flex">{mark}</span>{body}</div>')
