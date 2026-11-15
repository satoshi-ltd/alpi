from gen import m_group, m_screen_header, m_section, BADGE, BADGE_FONT, R_PILL, R_CHIP, R_CONTROL, R_SURFACE, R_SHEET, TILE_GAP, banner_surface, ladder_px
from notif_studies import MONO, flex, spacer, stack, wrap
from paper_studies import text
from wg_settings_studies import P, accent, name_text, glyph, mono, obj, section_label

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
    return (f'<span data-part="count" style="display: inline-block; min-width: 18px; padding: 0 6px; box-sizing: border-box; border-radius: {R_CHIP}px; background: {P["hover"]}; '
            f'font-family: {MONO}; font-size: 12px; line-height: 18px; text-align: center; color: {P["ink3"]}">{value}</span>')


def flag_badge(value):
    size = BADGE["size"]["desktop"]
    return (f'<span data-part="flag" style="display: inline-block; min-width: {size}px; height: {size}px; padding: 0 4px; box-sizing: border-box; border-radius: {R_PILL}px; background: {DANGER_FILL}; '
            f'font-family: {BADGE_FONT}; font-weight: {BADGE["weight"]}; font-size: 12px; line-height: {size}px; text-align: center; color: {ON_DANGER}">{value}</span>')


def tab(label, on=False, count=None, flag=0):
    pill = count_pill(count) if on and count is not None else ""
    badge = flag_badge(flag) if flag else ""
    return (f'<span style="display: inline-flex; align-items: center; gap: 8px; height: 32px; padding: 0 12px; box-sizing: border-box; border-radius: {R_CONTROL}px; '
            f'background: {P["selected"] if on else "transparent"}; font-size: 15px; font-weight: {500 if on else 400}; color: {P["ink"] if on else P["ink2"]}; white-space: nowrap">{label}{pill}{badge}</span>')


def head(on, count, flags=None):
    flags = flags or {}
    tabs = "".join(tab(label, label == on, count, flags.get(label, 0)) for label in TABS)
    owner = f'<span style="display: inline-flex; align-items: center; gap: 8px; margin-right: 12px">{obj(OWNER, 18)}<span style="font-size: 20px; font-weight: 600; line-height: 1.3; color: {P["ink"]}">{OWNER}</span></span>'
    return (f'<div style="display: flex; align-items: center; gap: 8px; padding: 12px 16px; flex-shrink: 0">{owner}'
            f'<span style="display: inline-flex; align-items: center; gap: 4px">{tabs}</span>{spacer()}{icon_cell("x")}</div>')


def search_row(label):
    return (f'<div style="display: flex; align-items: center; gap: 8px; min-height: 48px; padding: 0 12px; box-sizing: border-box; flex-shrink: 0; '
            f'font-size: 15px; color: {P["ink3"]}">{glyph("search", 14)}{label}</div>')


def group_header(value, first=False):
    return (f'<div style="padding: {8 if first else 12}px 12px 8px; font-size: 14px; font-weight: 500; '
            f'line-height: 20px; color: {P["ink3"]}; white-space: nowrap">{value}</div>')


def list_box(*items):
    return f'<div style="flex: 1; min-height: 0; padding: 8px; display: flex; flex-direction: column; gap: 4px; overflow: hidden">{"".join(items)}</div>'


TABULAR = "font-variant-numeric: tabular-nums"
ELLIPSIS = "white-space: nowrap; overflow: hidden; text-overflow: ellipsis"
MONO_ID = 12.88


def span(value, size, colour, weight=400, lh=None, extra=""):
    leading = f"line-height: {lh}px;" if lh else "line-height: 1.3;"
    return f'<span style="font-size: {size}px; font-weight: {weight}; {leading} color: {colour}; {extra}">{value}</span>'


def mono_id(value, colour=None, size=MONO_ID, extra=""):
    return f'<span style="font-family: {MONO}; font-size: {size}px; color: {colour or P["ink2"]}; white-space: nowrap; {extra}">{value}</span>'


def clamp(value, size, lh, colour, lines=2):
    return (f'<span style="font-size: {size}px; line-height: {lh}px; color: {colour}; display: -webkit-box; -webkit-line-clamp: {lines}; '
            f'-webkit-box-orient: vertical; overflow: hidden; overflow-wrap: anywhere">{value}</span>')


def bar_line(pct, over=False):
    return (f'<span data-part="row-bar" style="display: block; margin-top: 4px; height: 3px; border-radius: {R_PILL}px; background: {P["line2"]}; overflow: hidden">'
            f'<span style="display: block; width: {min(pct, 100)}%; height: 100%; background: {DANGER_FILL if over else P["ink2"]}"></span></span>')


def row_lines(title, sub="", meta="", tone="meta", bar=None, on=False, off=False):
    lift = P["ink2"] if on else P["ink3"]
    trail = span(meta, 12, P["danger"] if tone == "danger" else lift, lh=16, extra=f"flex-shrink: 0; white-space: nowrap; {TABULAR}") if meta else ""
    head = flex(span(title, 15, P["ink2"] if off else P["ink"], 500, 20, f"flex: 1; min-width: 0; {ELLIPSIS}"), trail, gap=8, align="baseline")
    return head + (clamp(sub, 14, 18, lift) if sub else "") + (bar_line(*bar) if bar is not None else "")


def browse_row(title, sub="", meta="", tone="meta", bar=None, on=False, hover=False, off=False):
    fill = P["selected"] if on else P["hover"] if hover else "transparent"
    return (f'<div data-part="browse-row" style="padding: 8px 12px; border-radius: {R_CONTROL}px; background: {fill}; display: flex; flex-direction: column; gap: 2px; min-width: 0">'
            f'{row_lines(title, sub, meta, tone, bar, on, off)}</div>')


def copy_id(ident):
    return flex(mono_id(ident, P["ink3"]), icon_cell("copy", 12, P["ink3"], 24), gap=4)


def detail_head(title, state, ident, tone="meta", actions=""):
    word_ = span(state, 14, P["danger"] if tone == "danger" else P["ink3"], lh=20, extra="white-space: nowrap") if state else ""
    left = (f'<div style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px">'
            f'{flex(span(title, 20, P["ink"], 600, 24, f"letter-spacing: -0.01em; {ELLIPSIS}"), word_, gap=8, align="baseline")}{copy_id(ident)}</div>')
    tail = flex(actions, gap=8) if actions else ""
    return f'<div data-part="detail-head" style="display: flex; align-items: flex-start; gap: 8px; padding: 16px 24px 12px; flex-shrink: 0">{left}{tail}</div>'


def fact_row(label, value, w=84, tone=None):
    colour = P["danger"] if tone == "danger" else P["ink2"]
    return (f'<div style="display: grid; grid-template-columns: {w}px 1fr; gap: 12px; padding: 4px 0; align-items: baseline">{span(label, 14, P["ink3"], lh=20)}'
            f'<span style="min-width: 0; font-size: 14px; line-height: 20px; color: {colour}">{value}</span></div>')


def facts_table(*pairs, w=84):
    return f'<div data-part="facts">{"".join(fact_row(*p[:2], w=w, tone=p[2] if len(p) > 2 else None) for p in pairs)}</div>'


def ids(*names, missing=()):
    return ", ".join(mono_id(n, P["ink3"] if n in missing else P["ink2"]) + (f' <span style="color: {P["ink3"]}">missing</span>' if n in missing else "") for n in names)


def usage_fact(used, limit, w=120):
    pct = round(used / limit * 100)
    over = used > limit
    bar = (f'<span style="display: inline-block; width: {w}px; height: 3px; border-radius: {R_PILL}px; background: {P["line2"]}; overflow: hidden; vertical-align: middle; margin-right: 8px">'
           f'<span style="display: block; width: {min(pct, 100)}%; height: 100%; background: {DANGER_FILL if over else P["ink2"]}"></span></span>')
    return f'{bar}<span style="{TABULAR}; color: {P["danger"] if over else P["ink2"]}">{used:,} / {limit:,} · {pct}%</span>'


def kb(size):
    return size.replace("kb", " KB")


def grouped(*groups):
    out = []
    for i, (label, rows) in enumerate(groups):
        out.append(group_header(label, i == 0))
        out.extend(rows)
    return list_box(*out)


def window(on, count, flags, search, rows, main, h, side_w=SIDE_W):
    side = (f'<div style="width: {side_w}px; flex-shrink: 0; display: flex; flex-direction: column; background: {P["side"]}; overflow: hidden">'
            f'{search_row(search)}{rows}</div>')
    detail = f'<div style="flex: 1; min-width: 0; display: flex; flex-direction: column; overflow: hidden">{main}</div>'
    return (f'<div style="height: {h}px; border-radius: {R_SHEET}px; overflow: hidden; background: var(--bg-elev, #ffffff); box-shadow: var(--shadow-edge-lg, 0 0 0 1px #b4b4b4); display: flex; flex-direction: column">'
            f'{head(on, count, flags)}<div style="flex: 1; min-height: 0; display: flex">{side}{detail}</div></div>')




















def banner_action(label, size):
    return f'<span role="button" style="flex-shrink: 0; padding: 4px 8px; margin: -4px -8px -4px 0; font-size: {ladder_px(size)}px; font-weight: 600; line-height: 16px; color: {P["danger"]}">{label}</span>'


def alert_banner(lead, detail, action=""):
    return (f'<div role="group" aria-label="{lead}" style="display: flex; align-items: center; gap: 8px; padding: 8px 12px; flex-shrink: 0; background: {banner_surface("danger")}">'
            f'<span style="display: inline-flex">{glyph("alert", 16, P["danger"])}</span>'
            f'<div style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px">{wrap(lead, 11, P["ink"], 600, 1.3)}{wrap(detail, 11, P["ink2"], 400, 1.3)}</div>'
            f'{banner_action(action, 11) if action else ""}</div>')






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
TOOL_ABOUT = {
    "read_file": "Reads a file from the workspace.", "write_file": "Writes a file in the workspace, creating folders as needed.",
    "edit_file": "Replaces one exact passage of a file.", "list_dir": "Lists a folder of the workspace.",
    "web_fetch": "Fetches a URL and returns its readable text.", "web_search": "Searches the web and returns the top results.",
    "browser": "Drives a headless browser for pages that need scripts.", "memory": "Reads and writes the profile’s memory files.",
    "memory_search": "Searches past sessions for a phrase.", "workgroup_post": "Posts a message to a workgroup channel.",
    "workgroup_read": "Reads the latest messages of a workgroup channel.",
}
TOOL_DENIED = {"browser"}
WEB_FETCH_ABOUT = "Fetches a URL and returns its readable text. Use it for pages that need no login; prefer browser when the page needs scripts to render."
JOBS = [
    {"title": "Weekly listing refresh", "about": "Compares every hotel’s listings with its intake and posts the differences to the hub.", "cron": "0 6 * * 1",
     "when": "Every Monday at 06:00", "next": "Mon 06:00", "word": "in 2d", "last": "ran 2d ago", "state": "active", "id": "a3f9c21e"},
    {"title": "Daily review digest", "about": "Summarises new guest reviews into strengths and complaints.", "cron": "30 7 * * *",
     "when": "Every day at 07:30", "next": "tomorrow 07:30", "countdown": "in 23h", "word": "failed", "last": "last run failed · 1h ago", "state": "failed", "id": "7be40d19"},
    {"title": "Price check before launch", "about": "Reads the live rates once before the launch and flags any gap.", "cron": "",
     "when": "Once, Sat 10 Oct at 09:00", "next": "Sat 09:00", "word": "in 4d", "last": "never run", "state": "active", "id": "c02a77f4"},
    {"title": "Nudge after a quiet week", "about": "Asks the hub for news when nobody has written for seven days.", "cron": "",
     "when": "After 7 days without a message", "next": "", "word": "paused", "last": "ran 3w ago", "state": "paused", "id": "91d3e6b0"},
]
PROMPT = ("Refresh the listings for every hotel in projects/. Compare rooms, amenities and rates with "
          f'<code style="font-family: {MONO}; font-size: 12px">intake.json</code> and post the differences to the hub. '
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


def phone(inner, h, w=390):
    return (f'<div style="width: {w}px; height: {h}px; flex-shrink: 0; box-sizing: border-box; border-radius: 16px; background: #ffffff; box-shadow: 0 0 0 1px {P["line2"]}; '
            f'overflow: hidden; display: flex; flex-direction: column">{inner}</div>')


def phone_head(section, right=""):
    return m_screen_header(OWNER, section, glyph=obj(OWNER, 28), named=True, accent=accent(OWNER), right=right)


def phone_body(*items, gap=16, pad="24px 24px"):
    return f'<div style="flex: 1; min-height: 0; overflow: hidden; padding: {pad}; display: flex; flex-direction: column; gap: {gap}px; background: #ffffff">{"".join(items)}</div>'


def phone_list(*items):
    return f'<div style="flex: 1; min-height: 0; overflow: hidden; display: flex; flex-direction: column; background: #ffffff">{"".join(items)}</div>'


def phone_group(label, rows, gap_top=12):
    head = m_section(label) if label else f'<div style="height: {gap_top}px"></div>'
    return head + m_group(*rows)


def phone_panel_row(title, sub="", meta="", tone="meta", bar=None, on=False, off=False):
    fill = P["selected"] if on else "transparent"
    return (f'<div data-part="panel-row" style="padding: 12px 16px; min-height: 44px; box-sizing: border-box; background: {fill}; display: flex; flex-direction: column; justify-content: center; gap: 2px; min-width: 0">'
            f'{row_lines(title, sub, meta, tone, bar, on, off)}</div>')


def phone_copy_id(ident):
    button = f'<span style="width: 44px; height: 44px; margin: -12px 0; display: inline-flex; align-items: center; justify-content: center">{glyph("copy", 16, P["ink3"])}</span>'
    return flex(mono_id(ident, P["ink3"]), button, gap=4)


def phone_detail_head(title, state, ident, tone="meta", right=""):
    word_ = span(state, 14, P["danger"] if tone == "danger" else P["ink3"], lh=20) if state else ""
    head = stack(flex(span(title, 20, P["ink"], 600, 26, "letter-spacing: -0.018em"), word_, gap=8, align="baseline"), phone_copy_id(ident), gap=4)
    return flex(f'<div style="flex: 1; min-width: 0">{head}</div>', right, gap=4, align="flex-start") if right else head


def phone_banner(lead, detail):
    return (f'<div role="alert" style="display: flex; align-items: center; gap: 12px; padding: 12px; background: {banner_surface("danger")}">'
            f'{glyph("alert", 16, P["danger"])}<div style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px">'
            f'{wrap(lead, 15, P["ink"], 600, 1.3)}{wrap(detail, 14, P["ink2"], 400, 1.3)}</div></div>')


def attention_value(count, text_):
    size = BADGE["size"]["mobile"]
    pill = (f'<span style="min-width: {size}px; min-height: {size}px; padding: 0 4px; box-sizing: border-box; border-radius: {R_PILL}px; background: {DANGER_FILL}; display: inline-flex; align-items: center; '
            f'justify-content: center; font-family: {BADGE_FONT}; font-size: 12px; font-weight: {BADGE["weight"]}; color: {ON_DANGER}">{count}</span>')
    return flex(pill, text(text_, 15, P["ink3"]), gap=8)
