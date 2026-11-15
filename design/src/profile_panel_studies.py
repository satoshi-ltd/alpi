from gen import R_SURFACE, ladder_px, section_label
from notif_studies import MONO, flex, stack, wrap
from paper_studies import PAPER, button, text
from panel_kit import (ENTRIES, IDENTITY, JOB_GROUPS, JOBS, MEMORY_FILES, MEMORY_USE, PROMPT, SANS, SIDE_W, SKILLS, TOOL_ABOUT, TOOL_DENIED, TOOLS, WEB_FETCH_ABOUT, alert_banner,
                       attention_value, browse_row, detail_head, facts_table, group_header, grouped, icon_cell, ids, job_banner, kb, list_box, memory_banner, mono_id, phone_banner,
                       phone, phone_body, phone_detail_head, phone_group, phone_head, phone_list, phone_panel_row, reading, skill_banner, usage_fact, window)
from wg_settings_studies import P, glyph, labelled, mono


def memory_row(label, name, caption, used, limit, on, flagged):
    pct = round(used / limit * 100)
    flag = flagged and used >= limit * 0.9
    meta = ("over" if used > limit else "full") if flag else f"{pct}%"
    return browse_row(label, caption, meta, "danger" if flag else "meta", (pct, used > limit), on)


def memory_window(flagged, side_w=SIDE_W):
    use = MEMORY_USE["flagged" if flagged else "healthy"]
    pick = "AGENT.md" if flagged else "MEMORY.md"
    rows = [memory_row(label, name, caption, *use[name], name == pick, flagged) for label, name, caption in MEMORY_FILES]
    label, name, caption = next(f for f in MEMORY_FILES if f[1] == pick)
    used, limit = use[pick]
    state = ("over" if used > limit else "full") if flagged else ""
    head = detail_head(label, state, name, "danger", icon_cell("pencil", 14))
    banner = alert_banner(*memory_banner((used, limit)), "Edit") if flagged else ""
    entries = 1 if flagged else len(ENTRIES)
    facts = facts_table(("About", caption), ("Usage", usage_fact(used, limit)), ("Entries", str(entries)), ("Updated", "Oct 3"))
    body = [wrap(IDENTITY, 13, P["ink"], 400, 1.5)] if flagged else [entry_block(*e) for e in ENTRIES]
    flow = f'<div style="display: flex; flex-direction: column; gap: 14px">{"".join(body)}</div>'
    return window("Memories", 3, {"Memories": 2} if flagged else None, "Search memory…", list_box(*rows), head + detail_body(banner, facts, flow), 470, side_w)


def detail_body(*items, gap=12):
    return f'<div style="flex: 1; min-height: 0; padding: 0 24px 24px; display: flex; flex-direction: column; gap: {gap}px; overflow: hidden">{"".join(i for i in items if i)}</div>'


def entry_block(value, note):
    return f'<div style="display: flex; flex-direction: column; gap: 6px">{wrap(value, 13, P["ink"], 400, 1.5)}{text(note, 12, P["ink3"])}</div>'


def skill_row(name, state, size, blurb, on=False, flag="", hover=False):
    meta, tone = (flag, "danger") if flag else (state, "meta") if state != "active" else (kb(size), "meta")
    return browse_row(name, blurb, meta, tone, on=on, hover=hover, off=state != "active")


def tree_row(icon, name, on=False, indent=0, meta=""):
    tail = mono(meta, 11, P["ink3"]) if meta else ""
    return flex(glyph(icon, 14, P["ink3"]), mono(name, 11, P["ink"] if on else P["ink2"], extra="flex: 1"), tail, gap=6,
                extra=f"padding: 6px 8px 6px {8 + indent}px; border-radius: 12px; background: {P['selected'] if on else 'transparent'}")


def skill_markdown():
    def h(value, s):
        return f'<div style="font-size: {ladder_px(s)}px; font-weight: 600; color: {P["ink"]}; margin: 6px 0 4px; font-family: {SANS}">{value}</div>'

    items = "".join(f'<li style="margin: 1px 0">{v}</li>' for v in ("Read brief.md and the official site.", "Pull the listings named in the brief.", "Normalise everything into intake.json:"))
    steps = f'<ol style="margin: 0; padding-left: 18px; font-size: 15px; line-height: 1.5; color: {P["ink2"]}; font-family: {SANS}">{items}</ol>'
    code = (f'<div style="margin-top: 6px; padding: 6px 8px; border-radius: 20px; background: {P["hover"]}; font-family: {MONO}; font-size: 12px; color: {P["ink"]}; '
            f'white-space: nowrap; overflow: hidden">python scripts/normalize.py --in raw/ --out intake.json</div>')
    return h("Hotel intake", 16) + reading("Use this skill when the hub opens #intake for a hotel.") + h("Steps", 14) + steps + code


def dir_box(tree, viewer):
    side = (f'<div style="width: 184px; flex-shrink: 0; box-sizing: border-box; padding: 8px; display: flex; flex-direction: column; gap: 2px; background: {P["side"]}; '
            f'">{section_label("Files", P["ink3"], "padding: 8px")}{tree}</div>')
    return (f'<div style="flex: 1; min-height: 0; display: flex; border-radius: 4px; box-shadow: 0 0 0 0.5px {P["line"]}; overflow: hidden">{side}'
            f'<div style="flex: 1; min-width: 0; padding: 12px 16px; background: {P["pane"]}; overflow: hidden">{viewer}</div></div>')


def skills_window(flagged, side_w=SIDE_W):
    rows = []
    if flagged:
        rows.append(group_header("Needs you · 1", True))
        rows.append(skill_row("review-digest", "active", "3.1kb", SKILLS[3][4], True, "lint"))
    for i, cat in enumerate(("research", "writing")):
        rows.append(group_header(cat.capitalize(), i == 0 and not flagged))
        for c, name, state, size, blurb in SKILLS:
            if c == cat and not (flagged and name == "review-digest"):
                rows.append(skill_row(name, state, size, blurb, not flagged and name == "hotel-intake", hover=not flagged and name == "local-context"))
    side = list_box(*rows)
    if flagged:
        head = detail_head("review-digest", "invalid", "research/review-digest", "danger")
        main = (alert_banner(*skill_banner()),
                facts_table(("About", SKILLS[3][4]), ("Tools", ids("web_fetch", "browser")), ("Keywords", "reviews, digest"), ("Version", "v0.3.0 · agent · Sep 30")))
        tree = tree_row("file-text", "SKILL.md", True) + tree_row("chevron-right", "scripts/")
        viewer = reading(f"Summarise the reviews for the hotel in <code style=\"font-family: {MONO}; font-size: 12px\">brief.md</code>.")
    else:
        head = detail_head("hotel-intake", "active", "research/hotel-intake")
        main = (facts_table(("About", SKILLS[0][4]), ("Requires", ids("FIRECRAWL_KEY", "BOOKING_TOKEN", missing=("BOOKING_TOKEN",))),
                            ("Tools", ids("web_fetch", "browser", "file_write", "workgroup_post")), ("Keywords", "intake, hotel, listings, brief"), ("Version", "v1.2 · agent · Sep 14")),)
        tree = (tree_row("file-text", "SKILL.md", True) + tree_row("chevron-down", "scripts/") + tree_row("file-code", "normalize.py", indent=14)
                + tree_row("chevron-right", "references/") + tree_row("chevron-right", "state/") + tree_row("lock", "secrets/", meta="2 · 0600"))
        viewer = skill_markdown()
    return window("Skills", 5, {"Skills": 1} if flagged else None, "Search skills…", side, head + detail_body(*main, dir_box(tree, viewer)), 600, side_w)


def tool_row(name, on=False):
    denied = name in TOOL_DENIED
    return browse_row(name, TOOL_ABOUT.get(name, ""), "denied" if denied else "", on=on, off=denied)


def tool_params():
    head = "".join(text(h, 14, P["ink3"], extra="flex: " + f) for h, f in (("Parameter", "1.2"), ("Type", "1"), ("Required", "0.8"), ("Default", "1")))

    def cells(*v):
        return "".join(mono_id(c, colour, extra="flex: " + f) for c, colour, f in v)

    rows = ((("url", P["ink"], "1.2"), ("string", P["ink2"], "1"), ("yes", P["ink3"], "0.8"), ("—", P["ink3"], "1")),
            (("max_chars", P["ink"], "1.2"), ("integer", P["ink2"], "1"), ("—", P["ink3"], "0.8"), ("20000", P["ink3"], "1")),
            (("format", P["ink"], "1.2"), ("enum: text | markdown", P["ink2"], "1"), ("—", P["ink3"], "0.8"), ("markdown", P["ink3"], "1")))
    seam = "padding: 4px 0; "
    body = "".join(flex(cells(*r), gap=8, extra=seam + "; align-items: baseline") for r in rows)
    return f'<div>{flex(head, gap=8, extra=seam)}{body}</div>'


def tools_window():
    groups = [(cat, [tool_row(n, n == "web_fetch") for n in names]) for cat, names in TOOLS]
    head = detail_head("web_fetch", "", "web_fetch")
    body = detail_body(facts_table(("About", WEB_FETCH_ABOUT), ("Category", "Web")), tool_params())
    return window("Tools", 37, None, "Search tools…", grouped(*groups), head + body, 640)


def job_row(job, on=False):
    return browse_row(job["title"], job["about"], job["word"], "danger" if job["state"] == "failed" else "meta", on=on, off=job["state"] == "paused")


def job_groups(jobs):
    return [(label, [j for j in jobs if (j["state"] == "paused" and key == "paused") or (j["state"] == "failed" and key == "needs") or (j["state"] == "active" and key == "active")])
            for key, label in JOB_GROUPS]


def schedules_window(flagged, side_w=SIDE_W, running=False):
    jobs = JOBS if flagged else [j for j in JOBS if j["state"] != "failed"]
    groups = [(f"{label} · {len(items)}", items) for label, items in job_groups(jobs) if items]
    chosen = groups[0][1][0]
    rows = grouped(*[(label, [job_row({**j, "word": "running"} if running and j is chosen else j, j is chosen) for j in items]) for label, items in groups])
    failed = chosen["state"] == "failed"
    shown = "running" if running else chosen["state"]
    run = "" if failed else button("Running · 0:42" if running else "Run now", "secondary", P, PAPER, 28)
    actions = run + button("Pause", "ghost", P, PAPER, 28) + icon_cell("trash", 14)
    if running:
        actions = f'<div aria-disabled="true" style="display: flex; align-items: center; gap: 8px; opacity: 0.5">{actions}</div>'
    head = detail_head(chosen["title"], shown, chosen["id"], "danger" if failed else "meta", actions)
    banner = alert_banner(*job_banner(), "Run now") if failed else ""
    when = chosen["when"] + (f' · {mono_id(chosen["cron"], P["ink3"])}' if chosen["cron"] else "")
    facts = facts_table(("About", chosen["about"]), ("When", when), ("Next", " · ".join(filter(None, (chosen["next"], chosen.get("countdown") or (chosen["word"] if chosen["state"] == "active" else ""))))),
                        ("Last run", "running now" if running else chosen["last"], "danger" if failed else None), ("Runs", "agent · 20 min timeout"), ("Notify", "silent — failures still alert"))
    rail = (f'<div style="width: 148px; flex-shrink: 0; box-sizing: border-box; padding: 8px; background: {P["side"]}; ">'
            f'{section_label("Prompt", P["ink3"], "padding: 8px")}'
            f'<div style="padding: 6px 8px; border-radius: 12px; background: {P["selected"]}; font-size: 12px; color: {P["ink"]}">Prompt</div></div>')
    box = (f'<div style="display: flex; border-radius: 4px; box-shadow: 0 0 0 0.5px {P["line"]}; overflow: hidden">{rail}'
           f'<div style="flex: 1; min-width: 0; padding: 12px 14px; background: {P["pane"]}">{reading(PROMPT)}</div></div>')
    return window("Schedules", len(jobs), {"Schedules": 1} if flagged else None, "Search jobs…", rows, head + detail_body(banner, facts, box), 600 if flagged else 560, side_w)


def m_skill_row(name, state, size, blurb, flag=""):
    meta, tone = (flag, "danger") if flag else (state, "meta") if state != "active" else (kb(size), "meta")
    return phone_panel_row(name, blurb, meta, tone, off=state != "active")


def m_skill_list(flagged):
    groups = []
    if flagged:
        groups.append(("Needs you · 1", [m_skill_row("review-digest", "active", "3.1kb", SKILLS[3][4], "lint")]))
    for cat in ("research", "writing"):
        items = [m_skill_row(n, st, z, b) for c, n, st, z, b in SKILLS if c == cat and not (flagged and n == "review-digest")]
        groups.append((cat.capitalize(), items))
    inner = phone_head("Skills · 5") + phone_list(*[phone_group(label, rows) for label, rows in groups])
    return phone(inner, 664 if flagged else 612)


def m_file_row(icon, name, meta, chevron=True):
    return flex(glyph(icon, 16, P["ink2"]), mono(name, 14, P["ink"], extra="flex: 1"), text(meta, 12, P["ink3"]), glyph("chevron-right", 16, P["ink4"]) if chevron else "", gap=8,
                extra="min-height: 44px; padding: 0 12px")


def m_skill_page(flagged):
    name = "review-digest" if flagged else "hotel-intake"
    banner = phone_banner(*skill_banner()) if flagged else ""
    head = phone_detail_head(name, "invalid" if flagged else "active", f"research/{name}", "danger" if flagged else "meta")
    if flagged:
        facts = facts_table(("About", SKILLS[3][4]), ("Tools", ids("web_fetch", "browser")), ("Keywords", "reviews, digest"), ("Version", "v0.3.0 · agent · Sep 30"), w=72)
    else:
        facts = facts_table(("About", SKILLS[0][4]), ("Requires", ids("FIRECRAWL_KEY", "BOOKING_TOKEN", missing=("BOOKING_TOKEN",))), ("Tools", ids("web_fetch", "browser")),
                            ("Keywords", "intake, hotel, listings, brief"), ("Version", "v1.2 · agent · Sep 14"), w=72)
    files = "".join(m_file_row(i, n, m) for i, n, m in (("file-code", "scripts/normalize.py", "3.4 KB"), ("file-text", "references/fields.md", "1.1 KB")))
    box = f'<div style="border-radius: {R_SURFACE}px; background: #ffffff; overflow: hidden">{files}{m_file_row("lock", "secrets/", "2 · 0600", False)}</div>'
    inner = phone_head("Skills · research") + phone_body(banner, head, facts, box, reading("Use this skill when the hub opens #intake for a hotel.", 15), gap=16)
    return phone(inner, 704 if flagged else 632)


def m_memory_row(label, name, caption, used, limit, flagged):
    pct = round(used / limit * 100)
    flag = flagged and used >= limit * 0.9
    meta = ("over" if used > limit else "full") if flag else f"{pct}%"
    return phone_panel_row(label, caption, meta, "danger" if flag else "meta", (pct, used > limit))


def m_memory_list(flagged):
    use = MEMORY_USE["flagged" if flagged else "healthy"]
    rows = {name: m_memory_row(label, name, caption, *use[name], flagged) for label, name, caption in MEMORY_FILES}
    needs = [n for _, n, _ in MEMORY_FILES if flagged and use[n][0] >= use[n][1] * 0.9]
    rest = [n for _, n, _ in MEMORY_FILES if n not in needs]
    groups = ([(f"Needs you · {len(needs)}", [rows[n] for n in needs])] if needs else []) + [("", [rows[n] for n in rest])]
    inner = phone_head("Memories · 3") + phone_list(*[phone_group(label, r) for label, r in groups])
    return phone(inner, 372 if flagged else 320)


def m_memory_page(flagged):
    use = MEMORY_USE["flagged" if flagged else "healthy"]
    name = "AGENT.md" if flagged else "MEMORY.md"
    label, _, caption = next(f for f in MEMORY_FILES if f[1] == name)
    used, limit = use[name]
    banner = phone_banner(*memory_banner(use[name])) if flagged else ""
    head = phone_detail_head(label, ("over" if used > limit else "full") if flagged else "", name, "danger")
    facts = facts_table(("About", caption), ("Usage", usage_fact(used, limit, 40)), ("Entries", "1" if flagged else str(len(ENTRIES))), ("Updated", "Oct 3"), w=72)
    entries = [wrap(IDENTITY, 15, P["ink"], 400, 1.6)] if flagged else [f'<div style="display: flex; flex-direction: column; gap: 8px">{wrap(v, 15, P["ink"], 400, 1.6)}{text(n, 12, P["ink3"])}</div>' for v, n in ENTRIES]
    edit = f'<span style="width: 44px; height: 44px; display: inline-flex; align-items: center; justify-content: center">{glyph("pencil", 20, P["ink2"])}</span>'
    inner = phone_head("Memories", edit) + phone_body(banner, head, facts, *entries)
    return phone(inner, 584 if flagged else 672)


def m_schedule_list(flagged):
    import mobile_attention_studies as ms
    return ms.schedule_list(flagged)


def m_schedule_page(flagged):
    import mobile_attention_studies as ms
    return ms.job_failed() if flagged else ms.job_healthy()


def m_tools_list():
    groups = [(cat, [phone_panel_row(n, TOOL_ABOUT.get(n, ""), "denied" if n in TOOL_DENIED else "", off=n in TOOL_DENIED) for n in names[:3]]) for cat, names in TOOLS[:3]]
    return phone(phone_head("Tools · 37") + phone_list(*[phone_group(label, rows) for label, rows in groups]), 792)


def m_param(name, kind, required=False):
    from gen import pill
    return (f'<div style="padding: 12px; border-radius: {R_SURFACE}px; background: var(--field, #f2f2f2); display: flex; flex-direction: column; gap: 8px">'
            f'<div style="display: flex; align-items: center; gap: 8px">{mono_id(name, P["ink"], 14, "font-weight: 500")}{pill(kind, tone="neutral")}{pill("required", on=True) if required else ""}</div></div>')


def m_tool_page():
    from gen import m_eyebrow
    head = phone_detail_head("web_fetch", "", "web_fetch")
    facts = facts_table(("About", WEB_FETCH_ABOUT), ("Category", "Web"), w=72)
    params = f'<div style="margin-top: 8px">{m_eyebrow("Parameters")}</div>' + m_param("url", "string", True) + m_param("max_chars", "integer")
    return phone(phone_head("Tools · Web") + phone_body(head, facts, params), 508)


def m_settings_rows(flagged):
    from gen import m_row
    def settings_row(label, helper, value, count=0, danger=False):
        return m_row(label, helper, "" if count else value, True, attention_value(count, value) if count else "", helper_danger=danger)
    if flagged:
        brain = [settings_row("Skills", "1 fails lint", "5", 1, True), settings_row("Memories", "2 over their limit", "3 files", 2, True), settings_row("Tools", "native callable functions", "view")]
        sched = [settings_row("Cron jobs", "1 failed", "4", 1, True)]
    else:
        brain = [settings_row("Skills", "instructions loaded on demand", "5"), settings_row("Memories", "User · memory · agent", "3 files"), settings_row("Tools", "native callable functions", "view")]
        sched = [settings_row("Cron jobs", "disable · fire · delete · add new", "4")]
    return phone(phone_head("Profile") + phone_list(phone_group("Brain", brain), phone_group("Schedule", sched)), 468)


def phones(*items):
    return f'<div style="display: flex; gap: 16px; align-items: flex-start; flex-wrap: wrap">{"".join(items)}</div>'


def desktop_panels_view():
    return stack(
        labelled("Memories · the files read on every turn: share and meter on the row, usage, entries and update among the facts", memory_window(False)),
        labelled("Memories · flagged: a red count on the tab, the word in the row’s meta, one banner above the file", memory_window(True)),
        labelled("Skills · one row per skill with its size, a hovered row, the id in mono with copy and the version among the facts", skills_window(False)),
        labelled("Skills · flagged: Needs you group, the lint banner", skills_window(True)),
        labelled("Tools · native functions by category with their first sentence, About and Category, parameters as a table", tools_window()),
        labelled("Schedules · grouped by state, Run now, Pause and Delete in the header, when in words with the cron in mono", schedules_window(False)),
        labelled("Schedules · flagged: Needs you group, the failure banner with Run now", schedules_window(True)),
        labelled("Schedules · running: the job row and detail agree, the clock advances, and Run now, Pause and Delete are disabled", schedules_window(False, running=True)),
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
        labelled("Tools · list and page: each tool’s first sentence under its name, the id in mono with copy on the page", phones(m_tools_list(), m_tool_page())),
        labelled("Profile settings · the Brain and Schedule rows, healthy and flagged", phones(m_settings_rows(False), m_settings_rows(True))),
        gap=22,
    )


PANELS_DESKTOP_H = 5000
PANELS_MOBILE_H = 7100


def panels_board(title, lede, inner, h):
    from conversation_boards import h1
    from gen import page
    body = f'<div style="padding: 40px 48px; display: flex; flex-direction: column; gap: 24px; box-sizing: border-box">{h1(title, lede)}{inner}</div>'
    return page(title, 1280, h, body)


def desktop_panels_board():
    return panels_board("Profile panels · desktop", "Memories, Skills, Tools and Schedules open as one window: the profile’s mark and name, the four panels as tabs (the count on the open one, a red count on any that needs you), a search row, a list and a reader. Every tab draws one row (a 15 px title, a 14 px second line, one 12 px meta a state word replaces) and one header (a 20 px title, the state as a word, the id in mono with copy), then one facts table. Mono only for ids and code.",
                        desktop_panels_view(), PANELS_DESKTOP_H)


def mobile_panels_board():
    return panels_board("Profile panels · phone", "Each panel is a list that opens a page, headed by the profile’s mark, its name and the section. The rows, the page header and the facts are the desktop’s, in the phone’s tiles. A flagged item rises to Needs you, and its page opens on one banner. Every target is 44 px.",
                        mobile_panels_view(), PANELS_MOBILE_H)
