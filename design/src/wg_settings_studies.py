import marks
from gen import ic, mono_px, section_label as gen_section_label
from notif_studies import MONO, VIEW, dot, ell, flex, spacer, stack, wrap
from paper_studies import text

P = VIEW
GREEN_BG, GREEN_FG = "rgba(63,179,122,0.16)", "#217a45"

PROFILES = {"mira": "dome", "scout": "arch", "muse": "clover", "quill": "cloud", "lingua": "drop", "pixel": "pill", "lens": "bell"}
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
    return marks.accent_of(PROFILES[name])


def obj(name, size=14, state="idle"):
    return f'<span style="display: inline-flex; flex-shrink: 0">{marks.shape_mark(PROFILES[name], accent(name), size, state, seed=name + str(size))}</span>'


def unfolded(name, size=14):
    return obj(name, size, "paused")


def name_text(name, size=16, label=None, colour=None):
    tone = marks.name_tone(colour or accent(name), "#ffffff") or P["ink"]
    return (f'<span style="font-family: \'Bricolage Grotesque\', Geist, sans-serif; font-size: {size}px; font-weight: 800; letter-spacing: -0.04em; line-height: 1.05; '
            f'color: {tone}; white-space: nowrap; flex-shrink: 0">{label or name}</span>')


def mono(value, size=11, color=None, weight=400, extra=""):
    return f'<span style="font-family: {MONO}; font-size: {mono_px(size)}px; font-weight: {weight}; color: {color or P["ink3"]}; white-space: nowrap; flex-shrink: 0; {extra}">{value}</span>'


def glyph(name, size=12, color=None):
    if name == "database":
        return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color or P["ink3"]}" stroke-width="2" stroke-linecap="round" '
                f'stroke-linejoin="round" aria-hidden="true" data-icon="database" style="flex-shrink: 0; display: block">{DATABASE}</svg>')
    return ic(name, size, color or P["ink3"])


def tag(value, size=10.5, color=None, bg=None):
    return (f'<span style="display: inline-flex; align-items: center; height: {round(size * 1.75)}px; padding: 0 5px; border-radius: 6px; background: {bg or P["hover"]}; '
            f'font-family: {MONO}; font-size: {mono_px(size)}px; color: {color or P["ink2"]}; white-space: nowrap; flex-shrink: 0">{value}</span>')


def tags(values, size=10.5, gap=4):
    return f'<div style="display: flex; flex-wrap: wrap; gap: {gap}px; min-width: 0">{"".join(tag(v, size) for v in values)}</div>'


def status(word, tone="ink", size=11):
    colour = {"ink": P["ink"], "off": P["ink4"], "danger": P["danger"]}[tone]
    label = {"ink": P["ink2"], "off": P["ink3"], "danger": P["danger"]}[tone]
    return flex(dot(colour, 6), mono(word, size, label), gap=5, extra="flex-shrink: 0")


def sheet(inner, h=None, pad=0, bg=None):
    height = f"height: {h}px;" if h else ""
    return (f'<div style="{height} box-sizing: border-box; padding: {pad}px; border-radius: 20px; background: {bg or P["pane"]}; box-shadow: 0 0 0 1px {P["line2"]}; '
            f'overflow: hidden; display: flex; flex-direction: column; min-width: 0">{inner}</div>')


def phone(inner, h, w=340):
    return (f'<div style="width: {w}px; height: {h}px; flex-shrink: 0; box-sizing: border-box; border-radius: 16px; background: {P["bg"]}; box-shadow: 0 0 0 1px {P["line2"]}; '
            f'overflow: hidden; display: flex; flex-direction: column">{inner}</div>')


def section_label(value, pad="14px 18px 6px"):
    return f'<div style="padding: {pad}; font-size: 14px; font-weight: 500; color: {P["ink3"]}">{value}</div>'


def group(inner, margin="0 16px"):
    return f'<div style="margin: {margin}; border-radius: 20px; background: var(--card); overflow: hidden">{inner}</div>'


def seam():
    return ""


def caption(value):
    return wrap(value, 11.5, P["ink3"], lh=1.5)


def labelled(title, inner, note=""):
    return stack(gen_section_label(title, P["ink3"], ""), inner, caption(note) if note else "", gap=8)


def green_pill(value):
    return (f'<span style="display: inline-flex; align-items: center; gap: 4px; height: 18px; padding: 0 6px; border-radius: 6px; background: {GREEN_BG}; '
            f'font-family: {MONO}; font-size: 12px; color: {GREEN_FG}; flex-shrink: 0">{dot("#3fb37a", 7)}{value}</span>')


def arrow():
    return f'<span style="font-size: 12px; color: {P["ink3"]}; flex-shrink: 0">→</span>'


def phase_chip(slug, state=None, key="rip", owner=True, assignee=None, strong=False, height=21, size=10.5):
    name = OWNER.get(slug) if owner else None
    working = state == "current" and not assignee
    lead = (obj(name, size + 1.5, "working") if working else obj(name, size + 1.5)) if name else ""
    slug_colour = {"completed": P["ink"], "current": P["ink"], "skipped": P["ink3"], "blocked": P["ink"]}.get(state, P["ink2"])
    deco = "text-decoration: line-through;" if state == "skipped" else ""
    weight = "font-weight: 600;" if state in ("current", "blocked") else ""
    handoff = ""
    if assignee:
        handoff = flex(arrow(), obj(assignee, size + 1.5, "working") if state == "current" else obj(assignee, size + 1.5), mono("@" + assignee, size, P["ink"], 600 if strong else 400), gap=3,
                       extra="flex-shrink: 0")
    bg = ("color-mix(in srgb, #3fb37a 18%, transparent)" if state == "completed" else
          f"color-mix(in srgb, {P['danger']} 14%, transparent)" if state == "blocked" else
          P["selected"] if state == "current" else P["hover"])
    word = {"current": "running", None: "pending"}.get(state, state)
    title = " · ".join(filter(None, ("#" + slug, "@" + name if name else None, "→ @" + assignee if assignee else None, word)))
    pad = "0 6px 0 4px" if name else "0 6px"
    return (f'<span title="{title}" style="display: inline-flex; align-items: center; gap: 4px; height: {height}px; padding: {pad}; border-radius: 6px; background: {bg}; flex-shrink: 0">'
            f'{lead}<span style="font-family: {MONO}; font-size: {mono_px(size)}px; color: {slug_colour}; white-space: nowrap; {weight} {deco}">#{slug}</span>{handoff}</span>')


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
    return f'<div style="padding: {pad}; display: flex; flex-direction: column; gap: 8px">{head}{chain_flow(chain, states, key_id)}</div>'


def legend():
    items = [phase_chip("intake", "completed"), phase_chip("assets", "skipped"), phase_chip("content", "current", "lg"), phase_chip("content", "blocked"), phase_chip("translation")]
    return f'<div style="display: flex; flex-wrap: wrap; gap: 6px; align-items: center">{"".join(items)}</div>'


def row_menu():
    item = lambda label, colour, icon: flex(glyph(icon, 12, colour), text(label, 11.5, colour), gap=8, extra="padding: 6px 10px")
    return (f'<div style="position: absolute; right: 12px; top: 34px; z-index: 2; width: 196px; padding: 4px; border-radius: 20px; background: {P["elev"]}; '
            f'box-shadow: 0 0 0 1px {P["line2"]}">{item("Open @pixel", P["ink"], "chevron-right")}{item("Copy profile id", P["ink"], "copy")}'
            f'<div style="height: 8px"></div>{item("Remove from workgroup…", P["danger"], "x")}</div>')


def more_glyph(phone, active=False):
    return (f'<span style="width: {44 if phone else 28}px; height: {44 if phone else 28}px; margin: 0; display: inline-flex; '
            f'align-items: center; justify-content: center; flex-shrink: 0; border-radius: {999 if phone else 12}px; background: {P["hover"] if active else "transparent"}">{glyph("more", 20 if phone else 14, P["ink2"])}</span>')


def d_owns(phases):
    chip = lambda v: f'<span style="font-family: {MONO}; font-size: 12px; color: {P["ink2"]}; padding: 0 8px; border-radius: 6px; background: {P["hover"]}; line-height: 20px; white-space: nowrap">{v}</span>'
    held = "".join(chip("#" + v) for v in phases) if phases else f'<span style="font-size: 12px; color: {P["ink3"]}">none · the hub routes every phase</span>'
    return f'<div style="display: flex; flex-wrap: wrap; align-items: center; gap: 8px; padding-left: 24px"><span style="font-family: {MONO}; font-size: 12px; color: {P["ink3"]}">owns</span>{held}</div>'


def d_member(name, mark, bio, owns_html, tag=""):
    head = (f'<div style="display: flex; align-items: center; gap: 8px; min-height: 28px">{mark}<span style="font-size: 16px; font-weight: 600; color: {P["ink"]}">{name}</span>'
            f'{tag}<span style="flex: 1"></span>{more_glyph(False)}</div>')
    note = f'<span style="padding-left: 24px; font-size: 15px; line-height: 1.5; color: {P["ink2"]}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis">{bio}</span>'
    return f'<div style="position: relative; display: flex; flex-direction: column; gap: 8px; padding: 12px 0; ">{head}{note}{owns_html}</div>'


def member_block(name, expanded=False, menu=False, phone=False):
    if not phone:
        hub = f'<span style="font-size: 12px; color: {P["ink3"]}">hub</span>' if name == "mira" else ""
        return d_member(name, obj(name, 16), BIOS[name], d_owns(owned(name)), hub) + (row_menu() if menu else "")
    hub = text("hub", 14, P["ink3"]) if name == "mira" else ""
    head = flex(obj(name, 28), name_text(name, 20), hub, spacer(), more_glyph(True, menu), gap=8, extra="min-height: 44px")
    bio = (wrap(BIOS[name], 15, P["ink2"], lh=1.5) if expanded else ell(BIOS[name], 15, P["ink2"], extra="line-height: 1.5"))
    phases = owned(name)
    held = "".join(m_owns_tag("#" + v) for v in phases) if phases else text("none · the hub routes every phase", 12, P["ink3"])
    owns = f'<div style="display: flex; flex-wrap: wrap; align-items: center; gap: 8px">{text("owns", 12, P["ink3"])}{held}</div>'
    return (f'<div style="position: relative; display: flex; flex-direction: column; justify-content: center; gap: 8px; min-height: 64px; box-sizing: border-box; padding: 12px 16px">'
            f'{head}{bio}{owns}{row_menu() if menu else ""}</div>')


def m_owns_tag(value):
    return (f'<span style="padding: 2px 8px; border-radius: 999px; background: {P["selected"]}; font-family: {MONO}; font-size: 12px; line-height: 1.3; color: {P["ink2"]}; white-space: nowrap">{value}</span>')


def m_hairline():
    return ""


def m_phase_chip(slug, state=None):
    name = OWNER.get(slug)
    working = state == "current"
    lead = obj(name, 12, "working" if working else "idle") if name else ""
    slug_colour = {"completed": P["ink"], "current": P["ink"], "skipped": P["ink3"], "blocked": P["ink"]}.get(state, P["ink2"])
    deco = "text-decoration: line-through;" if state == "skipped" else ""
    weight = "font-weight: 600;" if state in ("current", "blocked") else ""
    bg = ("color-mix(in srgb, #3fb37a 18%, transparent)" if state == "completed" else
          f"color-mix(in srgb, {P['danger']} 14%, transparent)" if state == "blocked" else
          P["selected"] if state == "current" else P["hover"])
    return (f'<span style="display: inline-flex; align-items: center; gap: 8px; min-height: 28px; padding: 0 12px; box-sizing: border-box; border-radius: 999px; background: {bg}; flex-shrink: 0">'
            f'{lead}<span style="font-size: 14px; line-height: 1.3; color: {slug_colour}; white-space: nowrap; {weight} {deco}">#{slug}</span></span>')


def m_chain_flow(chain, states=None):
    states = states or {}
    parts = [f'<span style="display: inline-flex; align-items: center; gap: 8px">{m_phase_chip(slug, states.get(slug))}{text("→", 12, P["ink3"]) if i < len(chain) - 1 else ""}</span>'
             for i, slug in enumerate(chain)]
    return f'<div style="display: flex; flex-wrap: wrap; align-items: center; gap: 8px; padding: 12px 16px; min-width: 0">{"".join(parts)}</div>'


def m_pipeline_card(key, chain, states=None):
    head = f'<div style="display: flex; align-items: center; gap: 8px; padding: 12px 16px 0">{mono(key, 14, P["ink"], 600)}<span style="flex: 1; font-size: 14px; color: {P["ink3"]}">{"starts at launch" if key == LAUNCH else "on demand"}</span></div>'
    done = sum(1 for s in chain if (states or {}).get(s) in ("completed", "skipped"))
    run = f'<div style="padding: 8px 16px 0; font-size: 12px; color: {P["ink2"]}">last run running · {done} of {len(chain)} · $2.41</div>' if states else ""
    return f'<div>{head}{run}{m_chain_flow(chain, states)}</div>'


def m_pipelines_group(pipelines, launch, run):
    return group(m_hairline().join(m_pipeline_card(k, c, run if k == launch else None) for k, c in pipelines))


def m_members_group(names, invited=None, lead="", add=True):
    blocks = ([lead] if lead else []) + [member_block(n, phone=True) for n in names] + ([invited] if invited else [])
    if add:
        blocks.append(f'<div style="padding: 14px 16px; font-size: 16px; line-height: 1.3; color: {P["ink"]}">+ Add member</div>')
    return group(m_hairline().join(blocks))


def invited_block(name, shape, colour, bio, phone=False):
    if not phone:
        tag = f'<span style="font-size: 12px; color: {P["ink3"]}">invited</span>'
        return d_member(name, marks.shape_mark(shape, colour, 16), bio, "", tag)
    head = flex(marks.shape_mark(shape, colour, 28), f'<span style="font-family: Bricolage Grotesque, sans-serif; font-weight: 800; font-size: 20px; letter-spacing: -0.04em; color: {colour}">{name}</span>',
                text("invited", 14, P["ink3"]), spacer(), more_glyph(True), gap=8, extra="min-height: 44px")
    return (f'<div style="display: flex; flex-direction: column; justify-content: center; gap: 8px; min-height: 64px; box-sizing: border-box; padding: 12px 16px">'
            f'{head}{ell(bio, 15, P["ink2"], extra="line-height: 1.5")}</div>')


def m_invites_group():
    join = (f'<div style="display: flex; align-items: center; gap: 12px; padding: 14px 16px"><div style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px">'
            f'<span style="font-size: 16px; line-height: 1.3; color: {P["ink"]}">Join command</span>{mono("alpi workgroup join mira wg_4f2a…9c1e", 11, P["ink3"], 500, "white-space: normal")}</div>'
            f'<span style="font-size: 15px; color: {P["ink3"]}">Copy</span><span style="width: 16px"></span></div>')
    return group(m_hairline().join((join, invited_block("lingo", "clover", "#9b5ad9", "Language coach; invited, not yet joined.", phone=True))))
