from notif_studies import MONO, dot, ell, flex, spacer, stack, wrap
from paper_studies import PAPER, button, text
from wg_settings_studies import P, crease_name, glyph, group, labelled, mono, obj, phone, section_label, status, tag, tags

SANS = "Geist, ui-sans-serif, system-ui, sans-serif"
SKILLS = [
    ("research", "hotel-intake", "active", "4.2kb", "Turns the official site, listings and reviews into the intake the factory builds from."),
    ("research", "listing-scrape", "inactive", "2.8kb", "Reads a listing page into rooms, amenities and rates."),
    ("research", "local-context", "active", "1.9kb", "Finds what is near the hotel and why a guest would care."),
    ("research", "review-digest", "invalid", "3.1kb", "Summarises guest reviews into strengths and complaints."),
    ("writing", "brief-writer", "active", "2.2kb", "Writes the one-page brief the hub hands to every phase."),
]
FILES = [("file-text", "SKILL.md", ""), ("file-code", "scripts/normalize.py", "3.4kb"), ("file-text", "references/fields.md", "1.1kb"),
         ("database", "state/db.sqlite", "48kb"), ("lock", "secrets/", "2 · 0600")]
JOBS = [
    ("Weekly listing refresh", "cron", "0 6 * * 1", "every Monday at 06:00", "Mon 06:00", "ok", "2d", False),
    ("Daily review digest", "cron", "30 7 * * *", "every day at 07:30", "tomorrow 07:30", "error", "1h", False),
    ("Price check before launch", "once", "2026-10-10 09:00", "once, Sat 10 Oct at 09:00", "Sat 09:00", "", "", False),
    ("Nudge after a quiet week", "inactivity", "after 168h", "after 7 days without a message", "", "ok", "3w", True),
]
MEMORIES = [
    ("Identity", "AGENT.md", 3050, 8000, "who scout is"),
    ("Learned", "MEMORY.md", 4610, 5000, "what scout has learned"),
    ("About you", "USER.md", 360, 3000, "what scout knows about you"),
]
ENTRIES = [
    ("Hotel Victoire’s official site lists 42 rooms; Booking lists 40. The two suites are only bookable by phone.", "Sep 28", "×3", ""),
    ("The owner prefers “boutique hotel” over “hostel” in every language, even where the listing says otherwise.", "Sep 30", "×1", ""),
    ("Reviews mention street noise on the Rue Cler side; quill should not promise quiet rooms there.", "Oct 2", "", "low confidence"),
]
SKILL_BODY_MD = ("# Hotel intake", "Use this skill when the hub opens #intake for a hotel.", "## Steps",
                 "1. Read brief.md and the official site.", "2. Pull the listings named in the brief.", "3. Normalise everything into intake.json:",
                 "    python scripts/normalize.py --in raw/ --out intake.json")


def icon_cell(name, size=13, color=None, box=22):
    return f'<span style="width: {box}px; height: {box}px; display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0">{glyph(name, size, color or P["ink2"])}</span>'


def search_field(w=150, label="Search…"):
    return (f'<span style="width: {w}px; height: 24px; padding: 0 8px; box-sizing: border-box; display: inline-flex; align-items: center; gap: 6px; border-radius: 4px; '
            f'background: {P["hover"]}; font-size: 11px; color: {P["ink3"]}; flex-shrink: 0">{glyph("search", 11)}{label}</span>')


def modal(head, side, main, h, side_w=176):
    return (f'<div style="height: {h}px; border-radius: 4px; overflow: hidden; background: {P["elev"]}; box-shadow: 0 0 0 1px {P["line2"]}; display: flex; flex-direction: column">'
            f'<div style="flex-shrink: 0; padding: 9px 10px 9px 14px; box-shadow: inset 0 -0.5px 0 {P["line2"]}">{head}</div>'
            f'<div style="flex: 1; min-height: 0; display: flex"><div style="width: {side_w}px; flex-shrink: 0; background: {P["side"]}; overflow: hidden">{side}</div>'
            f'<div style="flex: 1; min-width: 0; overflow: hidden; background: {P["pane"]}">{main}</div></div></div>')


def eyebrow(value, pad="10px 10px 4px"):
    return f'<div style="padding: {pad}; font-family: {MONO}; font-size: 9.5px; letter-spacing: 0.08em; text-transform: uppercase; color: {P["ink3"]}">{value}</div>'


def tab(label, count, on=False):
    bg, fg = (P["selected"], P["ink"]) if on else ("transparent", P["ink3"])
    return (f'<span style="display: inline-flex; align-items: center; gap: 5px; height: 24px; padding: 0 8px; border-radius: 4px; background: {bg}; font-size: 11.5px; '
            f'font-weight: {600 if on else 500}; color: {fg}; white-space: nowrap; flex-shrink: 0">{label}{mono(count, 9.5, P["ink3"])}</span>')


def new_head(on):
    tabs = "".join(tab(label, count if label == on else "", label == on) for label, count in (("Memories", "3"), ("Skills", "5"), ("Tools", "37"), ("Schedules", "4")))
    return flex(obj("scout", 18), crease_name("scout", 17), '<span style="width: 6px"></span>', tabs, spacer(), icon_cell("x"), gap=6)


def side_search(label):
    return f'<div style="padding: 8px 10px; box-shadow: inset 0 -0.5px 0 {P["line"]}">{search_field(150, label)}</div>'


def word(value, tone):
    colour = {"off": P["ink3"], "danger": P["danger"], "ink": P["ink2"]}[tone]
    return mono(value, 9.5, colour, 500 if tone == "danger" else 400)


def new_skill_rows():
    out, last = [], None
    for cat, name, state, size, blurb in SKILLS:
        if cat != last:
            out.append(eyebrow(cat))
            last = cat
        mark = dot(P["ink"], 6) if state == "active" else dot(P["danger"], 6) if state == "invalid" else dot(P["ink4"], 6)
        tail = "" if state == "active" else word(state, "danger" if state == "invalid" else "off")
        bg = P["pane"] if name == "hotel-intake" else "transparent"
        out.append(f'<div style="padding: 6px 10px; background: {bg}">{flex(mark, text(name, 11.5, P["ink"] if state == "active" else P["ink2"], 500), spacer(), tail, tag(size, 9, P["ink3"]), gap=6)}'
                   f'<div style="padding-left: 12px; margin-top: 2px">{ell(blurb, 10.5, P["ink3"])}</div></div>')
    return "".join(out)


def file_chip(icon, name, meta, on=False):
    bg = P["selected"] if on else P["hover"]
    return (f'<span style="display: inline-flex; align-items: center; gap: 5px; height: 22px; padding: 0 7px; border-radius: 2px; background: {bg}; flex-shrink: 0">'
            f'{glyph(icon, 11, P["ink2"])}{mono(name, 10, P["ink"] if on else P["ink2"])}{mono(meta, 9, P["ink3"]) if meta else ""}</span>')


def facts(rows, label_w=58):
    return "".join(flex(mono(k, 9.5, P["ink3"], extra=f"width: {label_w}px"), v, gap=8, align="flex-start", extra="padding: 2px 0") for k, v in rows)


def reading(size=12):
    h = lambda value, s: f'<div style="font-size: {s}px; font-weight: 600; color: {P["ink"]}; margin: 8px 0 3px; font-family: {SANS}">{value}</div>'
    para = lambda value: f'<div style="font-size: {size}px; line-height: 1.55; color: {P["ink2"]}; font-family: {SANS}">{value}</div>'
    items = "".join(f'<li style="margin: 1px 0">{v}</li>' for v in ("Read brief.md and the official site.", "Pull the listings named in the brief.", "Normalise everything into intake.json:"))
    code = (f'<div style="margin-top: 5px; padding: 6px 8px; border-radius: 4px; background: {P["hover"]}; font-family: {MONO}; font-size: {size - 2}px; color: {P["ink"]}; '
            f'white-space: nowrap; overflow: hidden">python scripts/normalize.py --in raw/ --out intake.json</div>')
    steps = f'<ol style="margin: 0; padding-left: 18px; font-size: {size}px; line-height: 1.55; color: {P["ink2"]}; font-family: {SANS}">{items}</ol>'
    return h("Hotel intake", size + 3) + para("Use this skill when the hub opens #intake for a hotel.") + h("Steps", size + 1) + steps + code


def tree_row(icon, name, meta, on=False, indent=0):
    return flex(glyph(icon, 11, P["ink2"]), mono(name, 10, P["ink"] if on else P["ink2"]), spacer(), mono(meta, 9, P["ink3"]) if meta else "", gap=5,
                extra=f"padding: 3px 6px 3px {6 + indent}px; border-radius: 2px; background: {P['selected'] if on else 'transparent'}")


def skill_reader():
    bar = flex(mono("research/", 12, P["ink3"]), mono("hotel-intake", 12, P["ink"], 600), status("active"), spacer(), mono("v1.2 · agent · Sep 14", 9.5, P["ink3"]), gap=6,
               extra=f"padding: 9px 16px; box-shadow: inset 0 -0.5px 0 {P['line']}")
    grid = facts((("about", wrap(SKILLS[0][4], 11.5, P["ink2"], lh=1.5)), ("tools", tags(["web_fetch", "browser", "file_write", "workgroup_post"], 9.5, 3)),
                  ("keywords", tags(["intake", "hotel", "listings", "brief"], 9.5, 3))))
    tree = stack(mono("FILES", 9, P["ink3"], extra="letter-spacing: 0.08em; padding: 2px 6px 4px"), tree_row("file-text", "SKILL.md", "", True),
                 tree_row("chevron-down", "scripts/", ""), tree_row("file-code", "normalize.py", "3.4kb", indent=12), tree_row("chevron-down", "references/", ""),
                 tree_row("file-text", "fields.md", "1.1kb", indent=12), tree_row("chevron-down", "state/", ""), tree_row("database", "db.sqlite", "48kb", indent=12),
                 tree_row("lock", "secrets/", "2 · 0600"), gap=1)
    box = (f'<div style="display: flex; border-radius: 4px; box-shadow: 0 0 0 0.5px {P["line"]}; overflow: hidden">'
           f'<div style="width: 150px; flex-shrink: 0; padding: 6px 4px; box-shadow: inset -0.5px 0 0 {P["line"]}">{tree}</div>'
           f'<div style="flex: 1; min-width: 0; padding: 4px 14px 10px; background: {P["bg"]}">{reading(11.5)}</div></div>')
    return f'{bar}<div style="padding: 10px 16px; display: flex; flex-direction: column; gap: 10px">{grid}{box}</div>'


def skills_new():
    return modal(new_head("Skills"), side_search("Search skills…") + new_skill_rows(), skill_reader(), 440, 220)


def job_row(job, on=False):
    title, kind, expr, human, nxt, last, ago, paused = job
    mark = dot(P["ink4"], 6) if paused else dot(P["ink"], 6)
    tail = word("paused", "off") if paused else word("failed", "danger") if last == "error" else mono(ago, 9.5, P["ink3"])
    return (f'<div style="padding: 6px 10px; background: {P["pane"] if on else "transparent"}">{flex(mark, ell(title, 11.5, P["ink"] if not paused else P["ink3"], 500), spacer(), tail, gap=6)}'
            f'<div style="padding-left: 12px; margin-top: 2px">{ell(human, 10.5, P["ink3"])}</div></div>')


def prompt_text(size=12):
    return wrap("Refresh the listings for every hotel in projects/. Compare rooms, amenities and rates with <code style=\"font-family: " + MONO + f"; font-size: {size - 1.5}px\">intake.json</code> and post the differences to the hub.",
                size, P["ink2"], lh=1.55)


def schedule_reader(job=JOBS[0]):
    title, kind, expr, human, nxt, last, ago, paused = job
    actions = flex(button("Run now", "secondary", P, PAPER, 24), button("Pause", "ghost", P, PAPER, 24), icon_cell("trash", 13), gap=4)
    head = flex(text(title, 15.5, P["ink"], 600), spacer(), actions, gap=8)
    meta = flex(status("active"), mono(human, 9.5, P["ink2"]), mono("next " + nxt, 9.5, P["ink3"]), gap=10)
    grid = facts(((kind, mono(expr, 10, P["ink"])), ("last run", mono(f"ran {ago} ago", 10, P["ink"])), ("runs", mono("agent · 20 min timeout", 10, P["ink"])),
                  ("notify", mono("pushes to your apps", 10, P["ink"])), ("id", mono("a3f9c21e7b", 10, P["ink"]))))
    return (f'<div style="padding: 12px 16px; display: flex; flex-direction: column; gap: 8px">{head}{meta}{grid}'
            f'<div style="height: 0.5px; background: {P["line"]}; margin: 2px 0"></div>{prompt_text(11.5)}</div>')


def schedules_new():
    rows = "".join(job_row(j, i == 0) for i, j in enumerate(JOBS))
    return modal(new_head("Schedules"), side_search("Search jobs…") + rows, schedule_reader(), 290)


def meter(used, limit, w=None):
    pct = round(used / limit * 100)
    width = f"width: {w}px;" if w else "flex: 1;"
    fill = P["danger"] if used > limit else P["ink2"]
    return (f'<span style="{width} height: 3px; border-radius: 2px; background: {P["line2"]}; overflow: hidden; display: inline-block; flex-shrink: 0">'
            f'<span style="display: block; width: {min(pct, 100)}%; height: 100%; background: {fill}"></span></span>')


def memory_row(m, on=False):
    label, name, used, limit, _ = m
    return (f'<div style="padding: 7px 10px; background: {P["pane"] if on else "transparent"}">{flex(text(label, 11.5, P["ink"], 500), mono(name, 9.5, P["ink3"]), spacer(), gap=6)}'
            f'<div style="margin-top: 5px">{flex(meter(used, limit), mono(f"{used:,} / {limit:,}", 9, P["ink3"]), gap=6)}</div></div>')


def entry(value, captured, reinforced, flag, size=11.5, pad="7px 0"):
    meta = [f"captured {captured}"] + ([f"reinforced {reinforced}"] if reinforced else [])
    tail = mono(" · ".join(meta), 9, P["ink3"])
    note = word(flag, "off") if flag else ""
    return (f'<div style="padding: {pad}; box-shadow: inset 0 -0.5px 0 {P["line"]}; display: flex; flex-direction: column; gap: 3px">'
            f'{wrap(value, size, P["ink"], lh=1.5)}{flex(tail, note, gap=8)}</div>')


def memory_reader():
    label, name, used, limit, what = MEMORIES[1]
    head = flex(text(label, 15.5, P["ink"], 600), mono(name, 10, P["ink3"]), spacer(), mono("Oct 3", 9.5, P["ink3"]), icon_cell("pencil", 12), gap=8)
    meta = flex(text(what, 11.5, P["ink3"]), spacer(), meter(used, limit, 120), mono(f"{used:,} / {limit:,} · 92%", 9.5, P["ink3"]), gap=8)
    entries = "".join(entry(*e) for e in ENTRIES)
    return f'<div style="padding: 12px 16px; display: flex; flex-direction: column; gap: 6px">{head}{meta}<div>{entries}</div></div>'


def memories_new():
    rows = "".join(memory_row(m, i == 1) for i, m in enumerate(MEMORIES))
    return modal(new_head("Memories"), side_search("Search memory…") + rows, memory_reader(), 300)


def m_head(title, sub, right=""):
    back = f'<span style="width: 24px; height: 40px; display: inline-flex; align-items: center">{glyph("chevron-left", 18, P["ink2"])}</span>'
    names = stack(title, mono(sub, 9.5, P["ink3"], extra="letter-spacing: 0.06em") if sub else "", gap=1, extra="flex: 1")
    return f'<div style="padding: 8px 10px 6px 6px; background: {P["bg"]}">{flex(back, names, right, gap=4)}</div>'


def scroll(inner, pad="12px 14px", gap=9):
    return f'<div style="flex: 1; min-height: 0; overflow: hidden; padding: {pad}; display: flex; flex-direction: column; gap: {gap}px; background: {P["pane"]}">{inner}</div>'


def m_identity(section):
    return flex(obj("scout", 18), stack(crease_name("scout", 18), mono(section, 9.5, P["ink3"], extra="letter-spacing: 0.06em"), gap=1), gap=7)


def m_skill_list():
    rows, last = "", None
    for cat, name, state, _, blurb in SKILLS:
        if cat != last:
            rows += section_label(cat, "12px 16px 4px")
            last = cat
        tail = "" if state == "active" else word(state, "danger" if state == "invalid" else "off")
        rows += (f'<div style="margin: 0 10px; padding: 9px 12px; min-height: 44px; box-sizing: border-box; background: {P["pane"]}; box-shadow: inset 0 -0.5px 0 {P["line"]}">'
                 f'{flex(text(name, 13.5, P["ink"], 600), spacer(), tail, gap=7)}<div style="margin-top: 2px">{ell(blurb, 11.5, P["ink3"])}</div></div>')
    return phone(m_head(m_identity("SKILLS · 5"), "") + rows, 470, 262)


def m_skill_page():
    files = "".join(flex(glyph(i, 13, P["ink2"]), mono(n, 10.5, P["ink"]), spacer(), mono(m, 9.5, P["ink3"]), glyph("chevron-right", 12, P["ink4"]) if i != "lock" else "", gap=7,
                         extra=f"min-height: 30px; box-shadow: inset 0 -0.5px 0 {P['line']}") for i, n, m in FILES[1:])
    inner = (text("hotel-intake", 19, P["ink"], 600) + flex(status("active"), mono("v1.2 · agent", 9.5, P["ink3"]), gap=8)
             + wrap(SKILLS[0][4], 12.5, P["ink2"], lh=1.5) + tags(["web_fetch", "browser", "file_write"], 9.5, 3)
             + f'<div>{files}</div>' + reading(12))
    return phone(m_head(m_identity("SKILLS"), "") + scroll(inner, gap=8), 470, 262)


def m_schedule_page():
    job = JOBS[1]
    title, kind, expr, human, nxt, last, ago, paused = job
    half = lambda label, kind: f'<span style="flex: 1; display: flex">{button(label, kind, P, PAPER, 44)}</span>'
    actions = flex(half("Run now", "primary"), half("Pause", "secondary"), gap=6)
    more = icon_cell("more", 16, box=44)
    inner = (text(title, 18, P["ink"], 600, "white-space: normal") + flex(status("active"), wrap(human, 11.5, P["ink2"]), gap=8)
             + mono("last run failed · 1h ago", 9.5, P["danger"]) + actions
             + facts(((kind, mono(expr, 10, P["ink"])), ("next", mono("Mon 6 Oct at 07:30", 10, P["ink"])), ("runs", mono("agent", 10, P["ink"])),
                      ("notify", mono("pushes to your apps", 10, P["ink"]))), 50)
             + prompt_text(12.5))
    return phone(m_head(m_identity("SCHEDULES"), "", more) + scroll(inner, gap=9), 470, 262)


def m_schedule_list():
    rows = ""
    for title, kind, expr, human, nxt, last, ago, paused in JOBS:
        mark = dot(P["ink4"], 6) if paused else dot(P["ink"], 6)
        tail = word("paused", "off") if paused else word("failed", "danger") if last == "error" else mono(ago, 9.5, P["ink3"])
        rows += (f'<div style="padding: 9px 12px; min-height: 44px; box-sizing: border-box; box-shadow: inset 0 -0.5px 0 {P["line"]}">'
                 f'{flex(mark, ell(title, 13, P["ink3"] if paused else P["ink"], 600), spacer(), tail, gap=7)}<div style="padding-left: 13px; margin-top: 2px">{ell(human, 11.5, P["ink3"])}</div></div>')
    return phone(m_head(m_identity("SCHEDULES · 4"), "") + f'<div style="padding-top: 8px">{group(rows, "0 10px")}</div>', 470, 262)


def m_memory_page():
    label, name, used, limit, what = MEMORIES[1]
    edit = f'<span style="width: 44px; height: 44px; display: inline-flex; align-items: center; justify-content: center">{glyph("pencil", 16, P["ink2"])}</span>'
    inner = (flex(text(label, 19, P["ink"], 600), mono(name, 10, P["ink3"]), gap=8) + text(what, 11.5, P["ink3"])
             + f'<div>{"".join(entry(*e, size=12.5, pad="9px 0") for e in ENTRIES)}</div>')
    return phone(m_head(m_identity("MEMORIES"), "", edit) + scroll(inner, gap=8), 470, 262)


def m_memory_list():
    rows = ""
    for label, name, used, limit, what in MEMORIES:
        rows += (f'<div style="padding: 10px 12px; min-height: 44px; box-sizing: border-box; box-shadow: inset 0 -0.5px 0 {P["line"]}; display: flex; flex-direction: column; gap: 4px">'
                 f'{flex(text(label, 13.5, P["ink"], 600), mono(name, 9.5, P["ink3"]), spacer(), mono("3 entries", 9.5, P["ink3"]), gap=7)}{text(what, 11.5, P["ink3"])}'
                 f'{flex(meter(used, limit), mono(f"{used:,} / {limit:,}", 9.5, P["ink3"]), gap=6)}</div>')
    return phone(m_head(m_identity("MEMORIES · 3"), "") + f'<div style="padding-top: 8px">{group(rows, "0 10px")}</div>', 470, 262)


def desktop_panels_view():
    return stack(
        labelled("Skills · the profile heads the window, siblings as tabs", skills_new()),
        labelled("Schedules · when in words, the cron and id as facts", schedules_new()),
        labelled("Memories · entries with when they were captured and reinforced", memories_new()),
        gap=22,
    )


def mobile_panels_view():
    row = lambda *items: f'<div style="display: flex; gap: 16px; align-items: flex-start; flex-wrap: wrap">{"".join(items)}</div>'
    return stack(
        labelled("Skills · list → page", row(m_skill_list(), m_skill_page())),
        labelled("Schedules · list → page, no typed id to delete", row(m_schedule_list(), m_schedule_page())),
        labelled("Memories · list → page", row(m_memory_list(), m_memory_page())),
        gap=22,
    )


PANELS_DESKTOP_H = 1330
PANELS_MOBILE_H = 1720


def panels_board(title, lede, inner, h):
    from conversation_boards import h1
    from gen import page
    body = f'<div style="padding: 40px 48px; display: flex; flex-direction: column; gap: 24px; box-sizing: border-box">{h1(title, lede)}{inner}</div>'
    return page(title, 1280, h, body)


def desktop_panels_board():
    return panels_board("Profile panels · desktop", "Memories, Skills, Tools and Schedules open as one window headed by the profile’s object and crease name, list on the left and a reader on the right. Status is an ink dot and a word; prose reads in Geist, only code in mono.",
                        desktop_panels_view(), PANELS_DESKTOP_H)


def mobile_panels_board():
    return panels_board("Profile panels · phone", "Each panel is a list that opens a page, headed by the profile’s object, crease name and the section. Every target is 44 px; a schedule is a page with its actions, never a typed id.",
                        mobile_panels_view(), PANELS_MOBILE_H)
