from notif_studies import MONO, dot, ell, flex, spacer, stack, wrap
from paper_studies import PAPER, button, text
from panel_kit import (ENTRIES, IDENTITY, JOB_GROUPS, JOBS, MEMORY_FILES, MEMORY_USE, DANGER_FILL, PROMPT, SANS, SIDE_W, SKILLS, TOOLS, alert_banner, attention_value, chips, detail_meta,
                       detail_scroll, fact, group_header, grouped, icon_cell, job_banner, job_mark, kw, list_box, memory_banner, phone_banner, phone_body, phone_fact, phone_group, phone_head, phone_row,
                       phone_status, reading, row, size_tag, skill_banner, skill_mark, usage, window, word)
from wg_settings_studies import P, glyph, labelled, mono, phone


def memory_row(label, name, used, limit, on, flagged):
    over = flagged and used >= limit * 0.9
    tail = word("over" if used > limit else "full", "danger") if over else ""
    head = f'<div style="display: flex; align-items: baseline; gap: 8px">{text(label, 12, P["ink"], 500)}{mono(name, 11, P["ink3"])}<span style="flex: 1"></span>{tail}</div>'
    return row(head + usage(used, limit), on, gap=8)


def memory_window(flagged, side_w=SIDE_W):
    use = MEMORY_USE["flagged" if flagged else "healthy"]
    pick = "AGENT.md" if flagged else "MEMORY.md"
    rows = [memory_row(label, name, *use[name], name == pick, flagged) for label, name, _ in MEMORY_FILES]
    label, name, caption = next(f for f in MEMORY_FILES if f[1] == pick)
    used, limit = use[pick]
    meta = detail_meta(text(label, 15, P["ink"], 600), mono(name, 11, P["ink3"]), spacer(), mono("Oct 3", 11, P["ink3"]), icon_cell("pencil", 14))
    banner = alert_banner(*memory_banner((used, limit)), "Edit") if flagged else ""
    captioned = flex(text(caption, 12, P["ink3"]), usage(used, limit, True), gap=12)
    body = [wrap(IDENTITY, 13, P["ink"], 400, 1.5)] if flagged else [entry_block(*e) for e in ENTRIES]
    flow = f'<div style="display: flex; flex-direction: column; gap: 14px">{"".join(body)}</div>'
    return window("Memories", 3, {"Memories": 2} if flagged else None, "Search memory…", list_box(*rows), meta + detail_scroll(banner, captioned, flow, gap=12), 400, side_w)


def entry_block(value, note):
    return f'<div style="display: flex; flex-direction: column; gap: 6px">{wrap(value, 13, P["ink"], 400, 1.5)}{mono(note, 11, P["ink3"])}</div>'


def skill_row(name, state, size, blurb, on=False, flag=""):
    word_ = word(flag, "danger") if flag else word(state, "off") if state != "active" else ""
    head = flex(skill_mark("flag" if flag else state), mono(name, 12, P["ink"], 500, "flex: 1; overflow: hidden; text-overflow: ellipsis"), word_, size_tag(size), gap=8)
    clamp = (f'<span style="margin-left: 14px; font-size: 11px; line-height: 1.3; color: {P["ink3"]}; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; overflow-wrap: anywhere">{blurb}</span>')
    return row(head + clamp, on, state != "active" and not flag, gap=4)


def tree_row(icon, name, on=False, indent=0, meta=""):
    tail = mono(meta, 11, P["ink3"]) if meta else ""
    return flex(glyph(icon, 14, P["ink3"]), mono(name, 12, P["ink"] if on else P["ink2"], extra="flex: 1"), tail, gap=6,
                extra=f"padding: 6px 8px 6px {8 + indent}px; border-radius: 4px; background: {P['selected'] if on else 'transparent'}")


def skill_markdown():
    def h(value, s):
        return f'<div style="font-size: {s}px; font-weight: 600; color: {P["ink"]}; margin: 6px 0 4px; font-family: {SANS}">{value}</div>'

    items = "".join(f'<li style="margin: 1px 0">{v}</li>' for v in ("Read brief.md and the official site.", "Pull the listings named in the brief.", "Normalise everything into intake.json:"))
    steps = f'<ol style="margin: 0; padding-left: 18px; font-size: 13px; line-height: 1.5; color: {P["ink2"]}; font-family: {SANS}">{items}</ol>'
    code = (f'<div style="margin-top: 6px; padding: 6px 8px; border-radius: 4px; background: {P["hover"]}; font-family: {MONO}; font-size: 11px; color: {P["ink"]}; '
            f'white-space: nowrap; overflow: hidden">python scripts/normalize.py --in raw/ --out intake.json</div>')
    return h("Hotel intake", 16) + reading("Use this skill when the hub opens #intake for a hotel.") + h("Steps", 14) + steps + code


def dir_box(tree, viewer):
    side = (f'<div style="width: 184px; flex-shrink: 0; box-sizing: border-box; padding: 8px; display: flex; flex-direction: column; gap: 2px; background: {P["side"]}; '
            f'box-shadow: inset -0.5px 0 0 {P["line"]}">{mono("files", 11, P["ink3"], 500, "letter-spacing: 0.06em; text-transform: uppercase; padding: 6px 8px 8px")}{tree}</div>')
    return (f'<div style="flex: 1; min-height: 0; display: flex; border-radius: 4px; box-shadow: 0 0 0 0.5px {P["line"]}; overflow: hidden">{side}'
            f'<div style="flex: 1; min-width: 0; padding: 12px 16px; background: {P["pane"]}; overflow: hidden">{viewer}</div></div>')


def requires_row(name, resolved=True):
    return flex(skill_mark("active" if resolved else "inactive"), mono(name, 11, P["ink2"] if resolved else P["ink3"]), gap=6)


def skills_window(flagged, side_w=SIDE_W):
    rows = []
    if flagged:
        rows.append(group_header("Needs you · 1"))
        rows.append(skill_row("review-digest", "active", "3.1kb", SKILLS[3][4], True, "lint"))
    for cat in ("research", "writing"):
        rows.append(group_header(cat))
        for c, name, state, size, blurb in SKILLS:
            if c == cat and not (flagged and name == "review-digest"):
                rows.append(skill_row(name, state, size, blurb, not flagged and name == "hotel-intake"))
    side = list_box(*rows)
    if flagged:
        meta = detail_meta(mono("research/", 15, P["ink3"]) + mono("review-digest", 15, P["ink"], 600), flex(skill_mark("invalid"), mono("invalid", 11, P["danger"]), gap=6), spacer(), mono("v0.3.0", 11, P["ink3"]))
        main = (alert_banner(*skill_banner()),
                f'<div>{fact("about", SKILLS[3][4])}{fact("tools", chips(["web_fetch", "browser"]))}{fact("keywords", chips(["reviews", "digest"]))}</div>')
        tree = tree_row("file-text", "SKILL.md", True) + tree_row("chevron-right", "scripts/")
        viewer = reading(f"Summarise the reviews for the hotel in <code style=\"font-family: {MONO}; font-size: 11px\">brief.md</code>.")
    else:
        meta = detail_meta(mono("research/", 15, P["ink3"]) + mono("hotel-intake", 15, P["ink"], 600), flex(skill_mark("active"), mono("active", 11, P["ink2"]), gap=6), spacer(), mono("v1.2 · agent · Sep 14", 11, P["ink3"]))
        about = fact("about", SKILLS[0][4])
        needs = fact("requires", f'<span style="display: flex; flex-wrap: wrap; gap: 6px 12px">{requires_row("FIRECRAWL_KEY")}{requires_row("BOOKING_TOKEN", False)}</span>')
        main = (f'<div>{about}{needs}{fact("tools", chips(["web_fetch", "browser", "file_write", "workgroup_post"]))}{fact("keywords", chips(["intake", "hotel", "listings", "brief"]))}</div>',)
        tree = (tree_row("file-text", "SKILL.md", True) + tree_row("chevron-down", "scripts/") + tree_row("file-code", "normalize.py", indent=14)
                + tree_row("chevron-right", "references/") + tree_row("chevron-right", "state/") + tree_row("lock", "secrets/", meta="2 · 0600"))
        viewer = skill_markdown()
    article = f'<div style="flex: 1; min-height: 0; padding: 12px 24px 24px; display: flex; flex-direction: column; gap: 12px; overflow: hidden">{"".join(main)}{dir_box(tree, viewer)}</div>'
    return window("Skills", 5, {"Skills": 1} if flagged else None, "Search skills…", side, meta + article, 520, side_w)


def tool_row(name, on=False):
    return row(mono(name, 12, P["ink"]), on)


def tool_params():
    head = "".join(mono(h, 11, P["ink3"], 500, "letter-spacing: 0.06em; text-transform: uppercase; flex: " + f) for h, f in (("Parameter", "1.2"), ("Type", "1"), ("Required", "0.8"), ("Default", "1")))
    def cells(*v):
        return "".join(mono(c, 11, colour, wt, "flex: " + f) for c, colour, wt, f in v)

    rows = ((("url", P["ink"], 500, "1.2"), ("string", P["ink2"], 400, "1"), ("yes", P["ink3"], 400, "0.8"), ("—", P["ink3"], 400, "1")),
            (("max_chars", P["ink"], 500, "1.2"), ("integer", P["ink2"], 400, "1"), ("—", P["ink3"], 400, "0.8"), ("20000", P["ink3"], 400, "1")),
            (("format", P["ink"], 500, "1.2"), ("enum: text | markdown", P["ink2"], 400, "1"), ("—", P["ink3"], 400, "0.8"), ("markdown", P["ink3"], 400, "1")))
    seam = f"padding: 6px 6px; box-shadow: inset 0 -0.5px 0 {P['line']}"
    body = "".join(flex(cells(*r), gap=8, extra=seam + "; align-items: baseline") for r in rows)
    return f'<div style="margin-top: 12px">{flex(head, gap=8, extra=seam)}{body}</div>'


def tools_window():
    groups = [(cat, [tool_row(n, n == "web_fetch") for n in names]) for cat, names in TOOLS]
    meta = detail_meta(mono("web/", 15, P["ink3"]) + mono("web_fetch", 15, P["ink"], 600))
    body = detail_scroll(reading("Fetches a URL and returns its readable text. Use it for pages that need no login; prefer `browser` when the page needs scripts to render."), tool_params())
    return window("Tools", 37, None, "Search tools…", grouped(*groups), meta + body, 470)


def job_row(job, on=False):
    failed = job["state"] == "failed"
    title = f'<span style="font-size: 12px; font-weight: 600; line-height: 1.3; color: {P["ink"]}; display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap">{job["title"]}</span>'
    about = f'<span style="margin-left: 16px; font-size: 11px; line-height: 1.3; color: {P["ink3"]}; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; overflow-wrap: anywhere">{job["about"]}</span>'
    tail = mono(job["word"], 11, P["danger"] if failed else P["ink3"]) if job["word"] else ""
    head = flex(job_mark(job["state"]), f'<div style="flex: 1; min-width: 0">{title}</div>', tail, gap=8)
    return row(head + about, on, gap=4)


def job_groups(jobs):
    return [(label, [j for j in jobs if (j["state"] == "paused" and key == "paused") or (j["state"] == "failed" and key == "needs") or (j["state"] == "active" and key == "active")])
            for key, label in JOB_GROUPS]


def schedules_window(flagged, side_w=SIDE_W):
    jobs = JOBS if flagged else [j for j in JOBS if j["state"] != "failed"]
    groups = [(f"{label} · {len(items)}", items) for label, items in job_groups(jobs) if items]
    chosen = groups[0][1][0]
    rows = grouped(*[(label, [job_row(j, j is chosen) for j in items]) for label, items in groups])
    failed = chosen["state"] == "failed"
    shown = {"active": "active", "paused": "paused", "failed": "failed"}[chosen["state"]]
    meta = detail_meta(text(chosen["title"], 15, P["ink"], 600), flex(job_mark(chosen["state"]), mono(shown, 11, P["ink2"]), gap=6), spacer(), mono(chosen["id"], 11, P["ink3"]))
    banner = alert_banner(*job_banner(), "Run now") if failed else ""
    run = "" if failed else button("Run now", "secondary", P, PAPER, 28)
    actions = f'<div style="display: flex; align-items: center; justify-content: flex-end; gap: 8px">{run}{button("Pause", "ghost", P, PAPER, 28)}{icon_cell("trash", 14)}</div>'
    cron = kw(chosen["cron"]) if chosen["cron"] else ""
    fields = "".join((fact("about", chosen["about"]), fact("when", f'{chosen["when"]}{cron}'), fact("next", chosen["next"]),
                      fact("last run", f'<span style="color: {P["danger"] if failed else P["ink2"]}">{chosen["last"]}</span>'), fact("runs", "agent · 20 min timeout"), fact("notify", "silent — failures still alert")))
    rail = (f'<div style="width: 148px; flex-shrink: 0; box-sizing: border-box; padding: 8px; background: {P["side"]}; box-shadow: inset -0.5px 0 0 {P["line"]}">'
            f'{mono("prompt", 11, P["ink3"], 500, "letter-spacing: 0.06em; text-transform: uppercase; padding: 6px 8px 8px")}'
            f'<div style="padding: 6px 8px; border-radius: 4px; background: {P["selected"]}; font-family: {MONO}; font-size: 12px; color: {P["ink"]}">Prompt</div></div>')
    box = (f'<div style="display: flex; border-radius: 4px; box-shadow: 0 0 0 0.5px {P["line"]}; overflow: hidden">{rail}'
           f'<div style="flex: 1; min-width: 0; padding: 12px 14px; background: {P["pane"]}">{reading(PROMPT)}</div></div>')
    return window("Schedules", len(jobs), {"Schedules": 1} if flagged else None, "Search jobs…", rows, meta + detail_scroll(banner, actions, f"<div>{fields}</div>", box, gap=12), 560 if flagged else 520, side_w)


def m_skill_row(name, state, blurb, flag=""):
    mark = dot(DANGER_FILL, 6) if flag else ""
    tail = mono(flag, 10, P["danger"]) if flag else mono(state, 10, P["ink3"]) if state != "active" else ""
    return phone_row(flex(mark, text(name, 13.5, P["ink"], 600, "flex: 1"), tail, gap=6) + wrap(blurb, 11, P["ink3"], 400, 1.3))


def m_skill_list(flagged):
    groups = []
    if flagged:
        groups.append(("Needs you · 1", [m_skill_row("review-digest", "active", SKILLS[3][4], "lint")]))
    for cat in ("research", "writing"):
        items = [m_skill_row(n, s, b) for c, n, s, _, b in SKILLS if c == cat and not (flagged and n == "review-digest")]
        groups.append((cat.capitalize(), items))
    inner = phone_head("SKILLS · 5") + phone_body(*[phone_group(label, rows) for label, rows in groups], gap=0, pad="0 10px")
    return phone(inner, 560)


def m_file_row(icon, name, meta, chevron=True):
    return flex(glyph(icon, 13, P["ink2"]), mono(name, 10.5, P["ink"], extra="flex: 1"), mono(meta, 10, P["ink3"]), glyph("chevron-right", 12, P["ink4"]) if chevron else "", gap=7,
                extra="min-height: 36px; padding: 0 10px")


def m_skill_page(flagged):
    name = "review-digest" if flagged else "hotel-intake"
    blurb = SKILLS[3][4] if flagged else SKILLS[0][4]
    banner = phone_banner(*skill_banner()) if flagged else ""
    state = phone_status("invalid", "danger") if flagged else phone_status("active")
    meta = flex(state, mono("v0.3.0" if flagged else "v1.2", 10, P["ink3"]), mono("agent", 10, P["ink3"]), gap=8)
    tools = f'<div style="display: flex; flex-wrap: wrap; gap: 5px">{"".join(kw(t) for t in ("web_fetch", "browser"))}</div>'
    files = "".join(f'<div style="box-shadow: inset 0 -0.5px 0 {P["line"]}">{m_file_row(i, n, m)}</div>' for i, n, m in (("file-code", "scripts/normalize.py", "3.4kb"), ("file-text", "references/fields.md", "1.1kb")))
    box = f'<div style="border-radius: 4px; background: {P["pane"]}; overflow: hidden">{files}{m_file_row("lock", "secrets/", "2 · 0600", False)}</div>'
    inner = phone_head("SKILLS · RESEARCH") + phone_body(banner, text(name, 19, P["ink"], 600), meta, wrap(blurb, 12.5, P["ink"], 400, 1.5), tools, box, reading("Use this skill when the hub opens #intake for a hotel.", 12), gap=10)
    return phone(inner, 560)


def m_memory_row(label, name, used, limit, flagged, entries):
    over = flagged and used >= limit * 0.9
    tail = mono("over" if used > limit else "full", 10, P["danger"]) if over else mono(entries, 10, P["ink3"])
    head = flex(dot(DANGER_FILL, 6) if over else "", text(label, 13.5, P["ink"], 600), mono(name, 10, P["ink3"], extra="flex: 1"), tail, gap=6)
    caption = next(c for lbl, n, c in MEMORY_FILES if n == name)
    meter_row = flex(usage(used, limit), gap=6)
    return phone_row(head + wrap(caption, 11, P["ink3"], 400, 1.3) + meter_row, 4)


def m_memory_list(flagged):
    use = MEMORY_USE["flagged" if flagged else "healthy"]
    entries = {"AGENT.md": "", "MEMORY.md": "3 entries", "USER.md": "2 entries"}
    rows = {name: m_memory_row(label, name, *use[name], flagged, entries[name]) for label, name, _ in MEMORY_FILES}
    needs = [n for _, n, _ in MEMORY_FILES if flagged and use[n][0] >= use[n][1] * 0.9]
    rest = [n for _, n, _ in MEMORY_FILES if n not in needs]
    groups = ([(f"Needs you · {len(needs)}", [rows[n] for n in needs])] if needs else []) + [("", [rows[n] for n in rest])]
    inner = phone_head("MEMORIES · 3") + phone_body(*[phone_group(label, r) if label else f'<div style="margin-top: 10px">{phone_group("", r)}</div>' for label, r in groups], gap=0, pad="0 10px")
    return phone(inner, 560)


def m_memory_page(flagged):
    use = MEMORY_USE["flagged" if flagged else "healthy"]
    name = "AGENT.md" if flagged else "MEMORY.md"
    label, _, caption = next(f for f in MEMORY_FILES if f[1] == name)
    banner = phone_banner(*memory_banner(use[name])) if flagged else ""
    heading = flex(text(label, 19, P["ink"], 600), mono(name, 10, P["ink3"]), gap=8, align="baseline")
    entries = [wrap(IDENTITY, 12.5, P["ink"], 400, 1.5)] if flagged else [f'<div style="display: flex; flex-direction: column; gap: 4px">{wrap(v, 12.5, P["ink"], 400, 1.5)}{mono(n, 10, P["ink3"])}</div>' for v, n in ENTRIES]
    edit = f'<span style="width: 44px; height: 44px; display: inline-flex; align-items: center; justify-content: center">{glyph("pencil", 16, P["ink2"])}</span>'
    inner = phone_head("MEMORIES", edit) + phone_body(banner, stack(heading, wrap(caption, 11.5, P["ink3"], 400, 1.3), gap=2), *entries, gap=12)
    return phone(inner, 560)


def m_schedule_list(flagged):
    import mobile_attention_studies as ms
    return ms.schedule_list(flagged)


def m_schedule_page(flagged):
    import mobile_attention_studies as ms
    return ms.job_failed() if flagged else ms.job_healthy()


def m_tools_list():
    descriptions = {"read_file": "Reads a file from the workspace.", "web_fetch": "Fetches a URL and returns its readable text.", "memory": "Reads and writes the profile’s memory files.",
                    "workgroup_post": "Posts a message to a workgroup channel."}
    groups = []
    for cat, names in TOOLS[:3]:
        rows = [phone_row(mono(n, 13, P["ink"], 500) + wrap(descriptions.get(n, "Calls a native function of the agent."), 11, P["ink3"], 400, 1.3)) for n in names[:2]]
        groups.append((cat, rows))
    return phone(phone_head("TOOLS · 37") + phone_body(*[phone_group(label, rows) for label, rows in groups], gap=0, pad="0 10px"), 600)


def m_settings_rows(flagged):
    def settings_row(label, helper, value, count=0, danger=False):
        value_cell = attention_value(count, value) if count else text(value, 12, P["ink3"])
        return (f'<div style="display: flex; align-items: center; gap: 8px; padding: 10px 12px; min-height: 44px; box-sizing: border-box">'
                f'<div style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px">{text(label, 13.5, P["ink"], 600)}{mono(helper, 9.5, P["danger"] if danger else P["ink3"])}</div>'
                f'{value_cell}{glyph("chevron-right", 12, P["ink4"])}</div>')
    if flagged:
        brain = [settings_row("Skills", "1 fails lint", "5", 1, True), settings_row("Memories", "2 over their limit", "3 files", 2, True), settings_row("Tools", "native callable functions", "view")]
        sched = [settings_row("Cron jobs", "1 failed", "4", 1, True)]
    else:
        brain = [settings_row("Skills", "instructions loaded on demand", "5"), settings_row("Memories", "USER · MEMORY · AGENT", "3 files"), settings_row("Tools", "native callable functions", "view")]
        sched = [settings_row("Cron jobs", "disable · fire · delete · add new", "4")]
    return phone(phone_head("PROFILE") + phone_body(phone_group("Brain", brain), phone_group("Schedule", sched), gap=0, pad="0 10px"), 360)


def phones(*items):
    return f'<div style="display: flex; gap: 16px; align-items: flex-start; flex-wrap: wrap">{"".join(items)}</div>'


def desktop_panels_view():
    return stack(
        labelled("Memories · the files read on every turn, their use and entries", memory_window(False)),
        labelled("Memories · flagged: a red count on the tab, a word on the row, one banner above the file", memory_window(True)),
        labelled("Skills · categories, a status dot and a word, the file tree beside its reader", skills_window(False)),
        labelled("Skills · flagged: Needs you group, the lint banner", skills_window(True)),
        labelled("Tools · native functions by category, parameters as a table", tools_window()),
        labelled("Schedules · grouped by state, when in words with the cron as a chip", schedules_window(False)),
        labelled("Schedules · flagged: Needs you group, the failure banner with Run now", schedules_window(True)),
        gap=22,
    )


def _ms():
    import mobile_attention_studies as ms
    return ms


def mobile_panels_view():
    return stack(
        labelled("Skills · list and page, healthy", phones(m_skill_list(False), m_skill_page(False))),
        labelled("Skills · flagged: Needs you group, the lint banner on the page", phones(m_skill_list(True), m_skill_page(True))),
        labelled("Memories · list and page, healthy", phones(m_memory_list(False), m_memory_page(False))),
        labelled("Memories · flagged: Needs you group, the banner above the file", phones(m_memory_list(True), m_memory_page(True))),
        labelled("Schedules · list and page, healthy", phones(m_schedule_list(False), m_schedule_page(False))),
        labelled("Schedules · flagged: Needs you group, the failure banner on the page", phones(m_schedule_list(True), m_schedule_page(True))),
        labelled("Schedules · running again: the banner stays, Run now becomes Running · m:ss, and More holds the last output, the id and a typed delete", phones(_ms().job_running(), _ms().job_more())),
        labelled("Tools · list", phones(m_tools_list())),
        labelled("Profile settings · the Brain and Schedule rows, healthy and flagged", phones(m_settings_rows(False), m_settings_rows(True))),
        gap=22,
    )


PANELS_DESKTOP_H = 3860
PANELS_MOBILE_H = 6300


def panels_board(title, lede, inner, h):
    from conversation_boards import h1
    from gen import page
    body = f'<div style="padding: 40px 48px; display: flex; flex-direction: column; gap: 24px; box-sizing: border-box">{h1(title, lede)}{inner}</div>'
    return page(title, 1280, h, body)


def desktop_panels_board():
    return panels_board("Profile panels · desktop", "Memories, Skills, Tools and Schedules open as one window: the profile’s object and crease name, the four panels as tabs (the count on the open one, a red count on any that needs you), a search row, a list and a reader. Prose reads in Geist, only code in mono.",
                        desktop_panels_view(), PANELS_DESKTOP_H)


def mobile_panels_board():
    return panels_board("Profile panels · phone", "Each panel is a list that opens a page, headed by the profile’s object, crease name and the section. A flagged item rises to Needs you, and its page opens on one banner. Every target is 44 px.",
                        mobile_panels_view(), PANELS_MOBILE_H)
