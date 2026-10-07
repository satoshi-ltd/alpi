from notif_studies import MONO, dot, flex, spacer, stack, wrap
from paper_studies import PAPER, button, text
from wg_settings_studies import P, crease_name, glyph, mono, obj, section_label

SANS = "Geist, ui-sans-serif, system-ui, sans-serif"
TABS = ("Memories", "Skills", "Tools", "Schedules")
SIDE_W = 340
JOB_GROUPS = (("needs", "Needs you"), ("active", "Active"), ("paused", "Paused"))
OWNER = "scout"
DANGER_FILL = "#c14545"
ON_DANGER = "#fffffe"


def icon_cell(name, size=14, color=None, box=28):
    return f'<span style="width: {box}px; height: {box}px; display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0">{glyph(name, size, color or P["ink2"])}</span>'


def count_pill(value):
    return (f'<span data-part="count" style="display: inline-block; min-width: 18px; padding: 0 6px; box-sizing: border-box; border-radius: 2px; background: {P["hover"]}; '
            f'font-family: {MONO}; font-size: 11px; line-height: 18px; text-align: center; color: {P["ink3"]}">{value}</span>')


def flag_badge(value):
    return (f'<span data-part="flag" style="display: inline-block; min-width: 14px; height: 14px; padding: 0 4px; box-sizing: border-box; border-radius: 4px; background: {DANGER_FILL}; '
            f'font-family: {MONO}; font-size: 9px; line-height: 14px; text-align: center; color: {ON_DANGER}">{value}</span>')


def tab(label, on=False, count=None, flag=0):
    pill = count_pill(count) if on and count is not None else ""
    badge = flag_badge(flag) if flag else ""
    return (f'<span style="display: inline-flex; align-items: center; gap: 6px; height: 32px; padding: 0 10px; box-sizing: border-box; border-radius: 4px; '
            f'background: {P["selected"] if on else "transparent"}; font-size: 13px; font-weight: {500 if on else 400}; color: {P["ink"] if on else P["ink2"]}; white-space: nowrap">{label}{pill}{badge}</span>')


def head(on, count, flags=None):
    flags = flags or {}
    tabs = "".join(tab(label, label == on, count, flags.get(label, 0)) for label in TABS)
    owner = f'<span style="display: inline-flex; align-items: center; gap: 8px; margin-right: 12px">{obj(OWNER, 18)}{crease_name(OWNER, 17)}</span>'
    return (f'<div style="display: flex; align-items: center; gap: 8px; padding: 12px 16px; flex-shrink: 0; box-shadow: inset 0 -0.5px 0 {P["line"]}">{owner}'
            f'<span style="display: inline-flex; align-items: center; gap: 4px">{tabs}</span>{spacer()}{icon_cell("x")}</div>')


def search_row(label):
    return (f'<div style="display: flex; align-items: center; gap: 8px; min-height: 48px; padding: 0 12px; box-sizing: border-box; flex-shrink: 0; '
            f'box-shadow: inset 0 -0.5px 0 {P["line"]}; font-size: 13px; color: {P["ink3"]}">{glyph("search", 14)}{label}</div>')


def group_header(value, first=False):
    return (f'<div style="padding: {6 if first else 10}px 10px 6px; font-family: {MONO}; font-size: 11px; font-weight: 500; letter-spacing: 0.06em; text-transform: uppercase; '
            f'line-height: 1.1; color: {P["ink3"]}; white-space: nowrap">{value}</div>')


def list_box(*items):
    return f'<div style="flex: 1; min-height: 0; padding: 8px; display: flex; flex-direction: column; gap: 4px; overflow: hidden">{"".join(items)}</div>'


def row(inner, on=False, muted=False, gap=2):
    return (f'<div style="padding: 8px 10px; border-radius: 4px; background: {P["selected"] if on else "transparent"}; opacity: {0.7 if muted else 1}; '
            f'display: flex; flex-direction: column; gap: {gap}px; min-width: 0">{inner}</div>')


def grouped(*groups):
    out = []
    for i, (label, rows) in enumerate(groups):
        out.append(group_header(label, i == 0))
        out.extend(rows)
    return list_box(*out)


def window(on, count, flags, search, rows, main, h, side_w=SIDE_W):
    side = (f'<div style="width: {side_w}px; flex-shrink: 0; display: flex; flex-direction: column; background: {P["side"]}; box-shadow: inset -0.5px 0 0 {P["line"]}; overflow: hidden">'
            f'{search_row(search)}{rows}</div>')
    detail = f'<div style="flex: 1; min-width: 0; display: flex; flex-direction: column; overflow: hidden">{main}</div>'
    return (f'<div style="height: {h}px; border-radius: 4px; overflow: hidden; background: {P["elev"]}; box-shadow: 0 0 0 0.5px {P["line2"]}; display: flex; flex-direction: column">'
            f'{head(on, count, flags)}<div style="flex: 1; min-height: 0; display: flex">{side}{detail}</div></div>')


def detail_meta(*items):
    return (f'<div style="display: flex; align-items: center; gap: 8px; min-height: 48px; padding: 0 24px; flex-shrink: 0; box-sizing: border-box; '
            f'box-shadow: inset 0 -0.5px 0 {P["line"]}">{"".join(items)}</div>')


def detail_scroll(*items, gap=12):
    return f'<div style="flex: 1; min-height: 0; padding: 16px 24px 24px; display: flex; flex-direction: column; gap: {gap}px; overflow: hidden">{"".join(items)}</div>'


def word(value, tone="off"):
    colour = {"off": P["ink3"], "danger": P["danger"], "ink": P["ink2"]}[tone]
    return mono(value, 11, colour)


def ring(colour, size=6, width=1):
    return f'<span style="width: {size}px; height: {size}px; box-sizing: border-box; border-radius: 999px; border: {width}px solid {colour}; flex-shrink: 0; display: inline-block"></span>'


def skill_mark(state):
    if state == "flag":
        return dot(DANGER_FILL, 6)
    if state == "active":
        return dot(P["ink"], 6)
    return ring(DANGER_FILL if state == "invalid" else P["ink4"])


def job_mark(state):
    if state == "failed":
        return dot(DANGER_FILL, 8)
    if state == "paused":
        return ring(P["ink4"], 8, 1.5)
    return dot(P["ink"], 8)


def size_tag(value):
    return (f'<span style="flex-shrink: 0; font-family: {MONO}; font-size: 11px; color: {P["ink3"]}; background: {P["hover"]}; border-radius: 2px; padding: 0 6px">{value}</span>')


def kw(value):
    return (f'<span style="font-family: {MONO}; font-size: 11px; color: {P["ink3"]}; background: {P["hover"]}; border-radius: 2px; padding: 2px 8px; white-space: nowrap">{value}</span>')


def chips(values):
    return f'<div style="display: flex; flex-wrap: wrap; gap: 6px; min-width: 0">{"".join(kw(v) for v in values)}</div>'


def fact(label, content, label_w=70):
    return (f'<div style="display: flex; align-items: baseline; gap: 12px; padding: 3px 0">{mono(label, 11, P["ink3"], 500, f"width: {label_w}px; letter-spacing: 0.06em; text-transform: uppercase")}'
            f'<span style="flex: 1; min-width: 0; font-size: 12px; line-height: 1.5; color: {P["ink2"]}; display: flex; align-items: center; flex-wrap: wrap; gap: 8px">{content}</span></div>')


def alert_banner(lead, detail, action=""):
    btn = button(action, "secondary", P, PAPER, 28) if action else ""
    return (f'<div role="alert" style="display: flex; align-items: flex-start; gap: 10px; padding: 10px 12px; flex-shrink: 0; border-radius: 4px; background: {P["hover"]}; '
            f'box-shadow: 0 0 0 0.5px {P["line"]}"><span style="margin-top: 4px; display: inline-flex">{glyph("alert", 14, P["danger"])}</span>'
            f'<div style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px">{wrap(lead, 12, P["ink"], 600, 1.3)}{wrap(detail, 11, P["ink3"], 400, 1.3)}</div>{btn}</div>')


def meter(used, limit, over=False, w=None):
    pct = min(round(used / limit * 100), 100)
    size = f"width: {w}px; flex-shrink: 0;" if w else "flex: 1; min-width: 60px;"
    return (f'<span style="{size} height: 3px; border-radius: 4px; background: {P["hover"]}; overflow: hidden; display: inline-block">'
            f'<span style="display: block; width: {pct}%; height: 100%; background: {DANGER_FILL if over else P["ink2"]}"></span></span>')


def usage(used, limit, wide=False):
    over = used > limit
    label = f"{used:,} / {limit:,}" + (f" · {min(round(used / limit * 100), 100)}%" if wide else "")
    return flex(meter(used, limit, over), mono(label, 11, P["danger"] if over else P["ink3"]), gap=8, extra="flex: 1; max-width: 320px; margin-left: auto" if wide else "")


def entry_note(captured, reinforced=0, low=False):
    return " · ".join([f"captured {captured}"] + ([f"reinforced ×{reinforced}"] if reinforced else []) + (["low confidence"] if low else []))


SKILLS = [
    ("research", "hotel-intake", "active", "4.2kb", "Turns the official site, listings and reviews into the intake the factory builds from."),
    ("research", "listing-scrape", "inactive", "2.8kb", "Reads a listing page into rooms, amenities and rates."),
    ("research", "local-context", "active", "1.9kb", "Finds what is near the hotel and why a guest would care."),
    ("research", "review-digest", "active", "3.1kb", "Summarises guest reviews into strengths and complaints."),
    ("writing", "brief-writer", "active", "2.2kb", "Writes the one-page brief the hub hands to every phase."),
]
LINT = "SKILL.md line 4: requires names BOOKING_TOKEN, which is not a secret of this skill"
TOOLS = [
    ("Filesystem", ["read_file", "write_file", "edit_file", "list_dir"]),
    ("Web", ["web_fetch", "web_search", "browser"]),
    ("Memory", ["memory", "memory_search"]),
    ("Collab", ["workgroup_post", "workgroup_read"]),
]
JOBS = [
    {"title": "Weekly listing refresh", "about": "Compares every hotel’s listings with its intake and posts the differences to the hub.", "cron": "0 6 * * 1",
     "when": "Every Monday at 06:00", "next": "Mon 06:00", "word": "in 2d", "last": "ran 2d ago", "state": "active", "id": "a3f9c21e"},
    {"title": "Daily review digest", "about": "Summarises new guest reviews into strengths and complaints.", "cron": "30 7 * * *",
     "when": "Every day at 07:30", "next": "tomorrow 07:30", "word": "failed", "last": "last run failed · 1h ago", "state": "failed", "id": "7be40d19"},
    {"title": "Price check before launch", "about": "Reads the live rates once before the launch and flags any gap.", "cron": "",
     "when": "Once, Sat 10 Oct at 09:00", "next": "Sat 09:00", "word": "in 4d", "last": "never run", "state": "active", "id": "c02a77f4"},
    {"title": "Nudge after a quiet week", "about": "Asks the hub for news when nobody has written for seven days.", "cron": "",
     "when": "After 7 days without a message", "next": "", "word": "paused", "last": "ran 3w ago", "state": "paused", "id": "91d3e6b0"},
]
PROMPT = ("Refresh the listings for every hotel in projects/. Compare rooms, amenities and rates with "
          f'<code style="font-family: {MONO}; font-size: 11px">intake.json</code> and post the differences to the hub. '
          "If a listing cannot be read, say which one and keep going; never retry the same URL twice.")
MEMORY_FILES = [("Identity", "AGENT.md", "who scout is"), ("Learned", "MEMORY.md", "what scout has learned"), ("About you", "USER.md", "what scout knows about you")]
MEMORY_USE = {"healthy": {"AGENT.md": (3050, 8000), "MEMORY.md": (3200, 5000), "USER.md": (360, 3000)},
              "flagged": {"AGENT.md": (9454, 8000), "MEMORY.md": (6585, 5000), "USER.md": (360, 3000)}}
ENTRIES = [
    ("Hotel Victoire’s official site lists 42 rooms; Booking lists 40. The two suites are only bookable by phone.", entry_note("Sep 28", 3)),
    ("The owner prefers “boutique hotel” over “hostel” in every language, even where the listing says otherwise.", entry_note("Sep 30", 1)),
    ("Reviews mention street noise on the Rue Cler side; quill should not promise quiet rooms there.", entry_note("Oct 2", 0, True)),
]
IDENTITY = "You are scout, the intake producer for every hotel workgroup. You convert a brief into factual canonical inputs the Astro template builds from, and you never invent a fact the brief does not state."


def reading(value, size=13):
    return wrap(value, size, P["ink2"], 400, 1.5, "font-family: " + SANS)


def memory_banner(file_used):
    used, limit = file_used
    if used > limit:
        return f"Over its limit by {used - limit:,} characters", f"{used:,} / {limit:,}. Every turn pays for the part that does not fit. Shorten it or move durable facts to a skill’s state."
    pct = round(used / limit * 100)
    return f"Nearly full: {pct}% of its limit", f"{used:,} / {limit:,}. The next additions will be refused until it is consolidated."


def job_banner(when="yesterday"):
    return "Last run failed", f"The run hit its 1200 s timeout while reading reviews. Last good run: {when}."


def skill_banner():
    return "Does not pass lint", f"{LINT}. The skill is not offered to the model until it passes."


def phone_head(section, right=""):
    back = f'<span style="width: 28px; height: 36px; display: inline-flex; align-items: center">{glyph("chevron-left", 18, P["ink2"])}</span>'
    title = stack(crease_name(OWNER, 18), mono(section, 10, P["ink3"], extra="letter-spacing: 0.06em"), gap=1, extra="flex: 1")
    return (f'<div style="padding: 8px 10px 8px 6px; background: {P["bg"]}; box-shadow: inset 0 -0.5px 0 {P["line"]}; flex-shrink: 0">'
            f'{flex(back, obj(OWNER, 18), title, right, gap=6)}</div>')


def phone_body(*items, gap=10, pad="12px 14px"):
    return f'<div style="flex: 1; min-height: 0; overflow: hidden; padding: {pad}; display: flex; flex-direction: column; gap: {gap}px; background: {P["bg"]}">{"".join(items)}</div>'


def phone_group(label, rows):
    seamed = "".join(f'<div style="box-shadow: inset 0 -0.5px 0 {P["line"]}" >{r}</div>' if i < len(rows) - 1 else r for i, r in enumerate(rows))
    return (f'<div>{section_label(label, "12px 4px 6px")}<div style="border-radius: 4px; background: {P["pane"]}; overflow: hidden">{seamed}</div></div>')


def phone_row(inner, gap=3):
    return f'<div style="padding: 10px 12px; min-height: 44px; box-sizing: border-box; display: flex; flex-direction: column; justify-content: center; gap: {gap}px">{inner}</div>'


def phone_banner(lead, detail):
    return (f'<div role="alert" style="display: flex; align-items: center; gap: 8px; padding: 10px; border-radius: 4px; background: {P["hover"]}; box-shadow: 0 0 0 0.5px {P["line"]}">'
            f'{glyph("alert", 13, P["danger"])}<div style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px">'
            f'{wrap(lead, 12, P["ink"], 600, 1.3)}{wrap(detail, 10.5, P["ink3"], 400, 1.3)}</div></div>')


def phone_fact(label, content, w=60):
    return (f'<div style="display: flex; align-items: baseline; gap: 10px; min-height: 22px">{mono(label, 10, P["ink3"], extra=f"width: {w}px; letter-spacing: 0.06em")}'
            f'<div style="flex: 1; min-width: 0; display: flex; flex-direction: column; align-items: flex-start; gap: 4px; font-size: 12px; line-height: 1.45; color: {P["ink2"]}">{content}</div></div>')


def phone_status(label, tone="ink"):
    dot_ = {"ink": dot(P["ink"], 7), "off": ring(P["ink4"], 7), "danger": ring(DANGER_FILL, 7)}[tone]
    colour = P["danger"] if tone == "danger" else P["ink2"]
    return flex(dot_, mono(label, 10, colour), gap=5)


def attention_value(count, text_):
    pill = (f'<span style="min-width: 20px; min-height: 20px; padding: 0 5px; box-sizing: border-box; border-radius: 4px; background: {DANGER_FILL}; display: inline-flex; align-items: center; '
            f'justify-content: center; font-family: {MONO}; font-size: 10px; font-weight: 500; color: {ON_DANGER}">{count}</span>')
    return flex(pill, text(text_, 12, P["ink3"]), gap=6)
