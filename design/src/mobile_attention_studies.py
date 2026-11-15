import panel_kit as pk
import profile_panel_studies as pps
from desktop_boards import INK, INK2, INK3, INK4, LINE2, MONO
from gen import R_SURFACE, DANGER, DOC_ACCENT, HOVER_FILL, mi as ic, identity_glyph, m_activity_row, m_eyebrow, m_screen_header, m_sidebar
from notif_studies import flex, stack
from paper_studies import PAPER, button, text
from wg_settings_studies import P, glyph

WARNING_TEXT = "#b3470e"
ABBY, CLONARA, SCOUT = "#df4b9d", "#f05940", "#e5533d"

MJOBS = [
    {"id": "a3f9c21e", "title": "Weekly listing refresh", "about": "Compares every hotel’s listings with its intake and posts the differences to the hub.", "cron": "0 6 * * 1",
     "when": "every Monday at 06:00", "next": "Mon 12 Oct at 06:00", "word": "in 2d", "last": "ran 2d ago", "state": "active"},
    {"id": "7be40d19", "title": "Daily review digest", "about": "Summarises new guest reviews into strengths and complaints.", "cron": "30 7 * * *",
     "when": "every day at 07:30", "next": "Sat 10 Oct at 07:30", "countdown": "in 23h", "word": "failed", "last": "last run failed · 1h ago", "state": "failed"},
    {"id": "c02a77f4", "title": "Price check before launch", "about": "Reads the live rates once before the launch and flags any gap.", "cron": "",
     "when": "once, Wed 14 Oct at 09:00", "next": "Wed 14 Oct at 09:00", "word": "in 4d", "last": "never run", "state": "active"},
    {"id": "91d3e6b0", "title": "Nudge after a quiet week", "about": "Asks the hub for news when nobody has written for seven days.", "cron": "",
     "when": "after 7 days without a message", "next": "", "word": "paused", "last": "ran 3w ago", "state": "paused"},
]
JOB_BANNER = ("Last run failed", "timed out after 20 min while reading reviews. Last good run: Thu 8 Oct at 07:30.")


def cap(value):
    return f'<span style="font-family: {MONO}; font-size: 12px; line-height: 1.5; color: {INK3}">{value}</span>'


def wide_button(label, kind, height=44):
    html = button(label, kind, P, PAPER, height)
    html = html.replace("position: relative; display: inline-flex; flex-shrink: 0", "position: relative; display: flex; flex: 1; min-width: 0", 1)
    return html.replace("display: inline-flex; align-items: center; justify-content: center; height", "display: flex; flex: 1; align-items: center; justify-content: center; height", 1)


def tagged(title, inner):
    return stack(cap(title), inner, gap=8)


def frame(inner, w=390):
    return f'<div style="width: {w}px; max-width: 100%; border-radius: 12px; border: 0.5px solid {LINE2}; overflow: hidden; background: #ffffff">{inner}</div>'


def phone_header(title, subtitle):
    return m_screen_header(title, subtitle, glyph="")


def section_head(value, color=INK3, right=""):
    return (f'<div role="heading" style="display: flex; align-items: center; gap: 12px; min-height: 32px; padding: 0 16px; box-sizing: border-box; background: #ffffff">'
            f'{m_eyebrow(value, color, 500, 0, 14, "flex: 1")}{right}</div>')


def chip(label, count, on=False, danger=False):
    n = f'<span style="font-size: 12px; color: {DANGER if danger else INK3}">{count}</span>'
    return (f'<span role="radio" aria-checked="{"true" if on else "false"}" style="display: inline-flex; align-items: center; gap: 8px; min-height: 32px; padding: 0 12px; box-sizing: border-box; border-radius: 999px; '
            f'background: {"rgba(20,20,20,0.08)" if on else "transparent"}; font-size: 14px; white-space: nowrap; font-weight: {600 if on else 400}; color: {INK if on else INK2}">{label}{n}</span>')


def chips_row(counts, current="all"):
    items = (("all", "All"), ("needs", "Needs you"), ("failing", "Failing"), ("running", "Running"), ("upcoming", "Upcoming"))
    inner = "".join(chip(label, counts[k], k == current, k == "failing" and counts[k] > 0) for k, label in items)
    return (f'<div role="radiogroup" aria-label="Filter activity" style="display: flex; align-items: center; gap: 8px; min-height: 44px; padding: 0 16px; box-sizing: border-box; overflow: hidden; '
            f'background: #ffffff; ">{inner}</div>')


def fail_head(name, color, count, since, open_):
    jobs = "job" if count == 1 else "jobs"
    return (f'<div role="button" aria-expanded="{"true" if open_ else "false"}" style="display: flex; align-items: center; gap: 8px; min-height: 48px; padding: 0 16px; box-sizing: border-box">'
            f'{ic("chev-d" if open_ else "chev-r", 16, INK3)}{identity_glyph(name, color, 24)}'
            f'<span style="flex: 1; min-width: 0; font-weight: 500; font-size: 16px; color: {INK}">{name}</span>'
            f'<span style="font-size: 12px; color: {INK3}; white-space: nowrap">{count} {jobs} · <span style="color: {DANGER}">{since}</span></span></div>')


def fail_job(title, failed_ago, ok_ago=None, retry=True):
    last_ok = f" · last ok {ok_ago}" if ok_ago else ""
    btn = (f'<span role="button" style="display: inline-flex; align-items: center; justify-content: center; min-width: 44px; min-height: 44px; margin-right: 8px; padding: 0 12px; box-sizing: border-box; '
           f'border-radius: 999px; font-weight: 500; font-size: 14px; color: {INK2}">Retry</span>') if retry else ""
    return (f'<div style="display: flex; align-items: center"><div role="button" style="flex: 1; min-width: 0; min-height: 56px; box-sizing: border-box; display: flex; flex-direction: column; justify-content: center; gap: 4px; '
            f'padding: 8px {8 if retry else 16}px 8px 32px"><span style="font-weight: 500; font-size: 16px; line-height: 20.8px; color: {INK}">{title}</span>'
            f'<span style="font-size: 14px; line-height: 18.2px; color: {INK3}"><span style="color: {DANGER}">failed {failed_ago}</span>{last_ok}</span></div>{btn}</div>')


def day_label(value):
    return f'<div style="padding: 8px 16px 4px">{m_eyebrow(value, INK3, 500, 0, 14)}</div>'


def next_row(glyph_html, title, sub, when):
    return m_activity_row(glyph_html, title, sub, "quiet", when=when)


def activity_list():
    counts = {"all": 10, "needs": 2, "failing": 3, "running": 2, "upcoming": 3}
    needs = (section_head("Needs you · 2", WARNING_TEXT)
             + m_activity_row(identity_glyph("abby", ABBY, 28), "abby · wants to run a command", "approval · 2m ago", "warning", "Review")
             + m_activity_row(identity_glyph("doc", DOC_ACCENT, 28), "doc · Which lab should I book?", "question · 12s ago", "warning", "Review"))
    failing = (section_head("Failing · 3", DANGER, f'<span role="button" style="font-weight: 500; font-size: 14px; color: {INK2}">Retry all</span>')
               + fail_head("clonara", CLONARA, 2, "3h ago", True)
               + fail_job("weekly labs", "3h ago", "2d ago")
               + fail_job("lab results digest", "9h ago", "1d ago")
               + fail_head("scout", SCOUT, 1, "1h ago", False))
    running = (section_head("Running · 2")
               + m_activity_row(identity_glyph("alpha", DOC_ACCENT, 28), "alpha · #collect", "phase 2 of 4 · daily-digest", "accent")
               + m_activity_row(identity_glyph("doc", DOC_ACCENT, 28), "doc · Daily brief", "40s · scheduled", "accent"))
    upcoming = (section_head("Upcoming · 3")
                + day_label("Today")
                + next_row(identity_glyph("abby", ABBY, 28), "abby · Invoice reminder", "in 3h", "18:00")
                + day_label("Tomorrow")
                + next_row(identity_glyph("doc", DOC_ACCENT, 28), "doc · Daily brief", "in 17h", "07:30")
                + next_row(identity_glyph("scout", SCOUT, 28), "scout · Weekly listing refresh", "in 19h", "09:00"))
    return chips_row(counts) + needs + failing + running + upcoming


def job_page_head():
    return pk.phone_head("Schedules", more_button())


def half(label, kind, disabled=False):
    opacity = "opacity: 0.55;" if disabled else ""
    return f'<span style="flex: 1; display: flex; {opacity}">{wide_button(label, kind)}</span>'


def ask_agent_row():
    return (f'<div style="display: flex; align-items: center; justify-content: center; gap: 8px; min-height: 44px; border-radius: 999px">'
            f'{glyph("sparkle", 16, P["ink2"])}{text("Ask the agent to change this", 15, P["ink2"], 500)}</div>')


def job_status(job, running):
    if running:
        return "running", "meta"
    state = {"failed": "failed", "paused": "paused"}.get(job["state"], "active")
    return state, "danger" if state == "failed" else "meta"


def more_button():
    return f'<span style="width: 44px; height: 44px; display: inline-flex; align-items: center; justify-content: center">{glyph("more", 20, P["ink2"])}</span>'


def job_body(job, running=False, more=False):
    failed = job["state"] == "failed"
    word, tone = job_status(job, running)
    title = pk.phone_detail_head(job["title"], word, job["id"], tone, more_button() if more else "")
    banner = pk.phone_banner(*JOB_BANNER) if failed else ""
    run = half("Running · 0:42" if running else "Run now", "primary", running)
    toggle = half("Resume" if job["state"] == "paused" else "Pause", "secondary", running)
    last = "running since 07:31" if running else job["last"]
    rows = [("About", job["about"]), ("When", job["when"] + (f' · {pk.mono_id(job["cron"], P["ink3"])}' if job["cron"] else ""))]
    if job["state"] != "paused":
        rows.append(("Next", " · ".join(filter(None, (job["next"], job.get("countdown") or (job["word"] if job["state"] == "active" else ""))))))
    rows += [("Last run", last, "danger" if failed and not running else None), ("Runs", "agent · 20 min timeout"), ("Notify", "silent — failures still alert" if failed else "pushes to your apps")]
    prompt = (f'<div style="padding: 12px; border-radius: {R_SURFACE}px; background: #ffffff; display: flex; flex-direction: column; gap: 8px">{text("Prompt", 12, P["ink3"])}'
              f'{pps.reading(pk.PROMPT, 15)}</div>')
    return [banner, title, flex(run, toggle, gap=8), ask_agent_row(), pk.facts_table(*rows, w=72), prompt]


def job_page(job, running=False, h=840):
    return pk.phone(job_page_head() + pk.phone_body(*job_body(job, running)), h)


def job_failed():
    return job_page(MJOBS[1], h=842)


def job_healthy():
    return job_page(MJOBS[0], h=742)


def job_running():
    return job_page(MJOBS[1], running=True, h=842)


def job_more():
    dimmed = job_page_head() + pk.phone_body(pk.phone_detail_head("Daily review digest", "failed", "7be40d19", "danger"))
    from mobile_overlays import action_item, sheet_header
    items = action_item("file-text", "Last output", "opens the notification") + action_item("copy", "Copy job id", "7be40d19") + action_item("trash-2", "Delete job…", danger=True)
    sheet = (f'<div style="position: absolute; left: 0; right: 0; bottom: 0; border-radius: 28px 28px 0 0; background: var(--bg-elev, #ffffff); box-shadow: 0 -1px 0 0 #8c8c8c; overflow: hidden">'
             f'{sheet_header("Daily review digest", "")}<div style="padding-bottom: 24px">{items}</div></div>')
    dim = f'<div style="position: absolute; inset: 0; background: color-mix(in srgb, {P["pane"]} 72%, transparent)"></div>'
    return pk.phone(f'<div style="position: relative; flex: 1; min-height: 0; display: flex; flex-direction: column">{dimmed}<div style="flex: 1; background: #ffffff"></div>{dim}{sheet}</div>', 460)


def fold_pane(selected):
    groups = [(f"{label} · {len(items)}", items) for label, items in pps.job_groups(MJOBS) if items]
    return groups, MJOBS[selected]


def fold_list(width, groups, chosen, h):
    body = "".join(pk.phone_group(label, [list_row(j, selected=j is chosen) for j in items]) for label, items in groups)
    return (f'<div style="width: {width}px; flex-shrink: 0; height: {h}px; display: flex; flex-direction: column; overflow: hidden; background: #ffffff">'
            f'{search_field("Search jobs…")}<div>{body}</div></div>')


def fold_detail(chosen, h):
    pieces = job_body(chosen, more=True)
    body = f'<div style="padding: 24px; display: flex; flex-direction: column; gap: 16px; overflow: hidden">{"".join(x for x in pieces if x)}</div>'
    return f'<div style="flex: 1; min-width: 0; height: {h}px; display: flex; flex-direction: column; overflow: hidden; background: #ffffff">{body}</div>'


def fold_open(total_w, with_sidebar, list_w, master_detail, h):
    groups, chosen = fold_pane(1)
    side = m_sidebar(h, selected="") if with_sidebar else ""
    pane_w = total_w - (280 if with_sidebar else 0)
    head = pane_head(not with_sidebar)
    if master_detail:
        body = f'<div style="flex: 1; min-height: 0; display: flex">{fold_list(list_w, groups, chosen, h - 64)}{fold_detail(chosen, h - 64)}</div>'
    else:
        rows = "".join(pk.phone_group(label, [list_row(j) for j in items]) for label, items in groups)
        body = f'<div style="flex: 1; min-height: 0; overflow: hidden; background: #ffffff">{rows}</div>'
    pane = f'<div style="width: {pane_w}px; height: {h}px; display: flex; flex-direction: column; background: #ffffff">{head}{body}</div>'
    return f'<div style="width: {total_w}px; height: {h}px; display: flex; overflow: hidden; border-radius: 4px; box-shadow: 0 0 0 0.5px {P["line2"]}">{side}{pane}</div>'


def pane_head(sidebar_toggle):
    return m_screen_header("scout", "Schedules · 4", wide=True, back=not sidebar_toggle, named=True, accent=SCOUT, glyph=obj_scout(), sidebar_toggle=sidebar_toggle)


def obj_scout():
    from wg_settings_studies import obj
    return obj("scout", 20)


def needs_band():
    rows = (m_activity_row(identity_glyph("abby", ABBY, 28), "abby · wants to run a command", "approval · 2m ago", "warning", "Review")
            + m_activity_row(identity_glyph("clonara", CLONARA, 28), "clonara · weekly labs", "failed 3h ago", "danger", "Run again", separate=True))
    link = (f'<span role="button" style="display: inline-flex; align-items: center; gap: 4px; min-height: 44px; padding: 0 16px; margin-top: -8px; box-sizing: border-box">'
            f'<span style="font-size: 12px; color: {INK3}">Activity</span>{ic("chev-r", 16, INK4)}</span>')
    head = f'<div style="display: flex; align-items: center; padding: 8px 0 0 16px">{m_eyebrow("Needs you · 2", WARNING_TEXT, 500, 0, 14, "flex: 1")}{link}</div>'
    return f'<div role="list" style="background: {HOVER_FILL}">{head}{rows}</div>'


def chat_menu_row(icon, label, detail="", dot_color=None):
    mark = f'<span style="position: relative; display: inline-flex">{ic(icon, 20, INK2)}' + (f'<span style="position: absolute; top: -2px; right: -3px; width: 8px; height: 8px; border-radius: 4px; background: {dot_color}; border: 1.5px solid #ffffff; box-sizing: border-box"></span>' if dot_color else "") + "</span>"
    det = f'<span style="font-family: {MONO}; font-weight: 500; font-size: 14px; color: {DANGER if dot_color else INK3}">{detail}</span>' if detail else ""
    return (f'<div style="display: flex; align-items: center; gap: 12px; min-height: 48px; padding: 0 16px"><span style="width: 24px; display: inline-flex; justify-content: center">{mark}</span>'
            f'<span style="flex: 1; font-size: 16px; color: {INK}">{label}</span>{det}</div>')


def settings_head_chips(selected):
    names = ("Overview", "Usage", "Identity", "Service", "ALP", "Schedule", "Sandbox", "Voice", "MCP", "Brain", "Storage")
    chips = "".join(
        f'<span style="display: inline-flex; align-items: center; min-height: 44px; padding: 0 12px; border-radius: 12px; font-size: 15px; white-space: nowrap; '
        f'background: {"rgba(20,20,20,0.08)" if n == selected else "transparent"}; color: {INK if n == selected else INK2}; font-weight: {600 if n == selected else 400}">{n}</span>'
        for n in names)
    fade = '<div style="position: absolute; right: 0; top: 0; bottom: 0; width: 28px; pointer-events: none; background: linear-gradient(to right, rgba(255,255,255,0), #ffffff)"></div>'
    return f'<div style="position: relative; flex-shrink: 0; background: #ffffff"><div style="display: flex; gap: 2px; padding: 0 16px; overflow: hidden">{chips}</div>{fade}</div>'


def settings_summary():
    return (f'<div style="margin: 12px 16px 0; padding: 12px 16px; border-radius: 20px; background: rgba(20,20,20,0.04); display: flex; flex-direction: column; gap: 8px">'
            f'<span style="font-size: 14px; color: {WARNING_TEXT}">Needs you · 2</span>'
            f'<div style="display: flex; align-items: center; gap: 10px; min-height: 44px"><span style="width: 6px; height: 6px; border-radius: 999px; background: {DANGER}"></span><span style="flex: 1; font-size: 15px; color: {INK}">1 job failed</span><span style="font-family: {MONO}; font-size: 12px; color: {INK3}">Schedule</span>{ic("chev-r", 14, INK4)}</div>'
            f'<div style="display: flex; align-items: center; gap: 10px; min-height: 44px"><span style="width: 6px; height: 6px; border-radius: 999px; background: {DANGER}"></span><span style="flex: 1; font-size: 15px; color: {INK}">2 memory files over their limit</span><span style="font-family: {MONO}; font-size: 12px; color: {INK3}">Brain</span>{ic("chev-r", 14, INK4)}</div></div>')


def list_row(job, running=False, selected=False):
    word = "running" if running else job["word"]
    return pk.phone_panel_row(job["title"], job["about"], word, "danger" if job["state"] == "failed" and not running else "meta", on=selected, off=job["state"] == "paused")


def search_field(placeholder):
    return (f'<div style="padding: 12px 16px 0"><div style="display: flex; align-items: center; min-height: 48px; padding: 0 12px; box-sizing: border-box; border-radius: {R_SURFACE}px; '
            f'background: var(--field, #f2f2f2); font-size: 15px; line-height: 22px; color: {INK3}">{placeholder}</div></div>')


def schedule_list(flagged=True):
    jobs = MJOBS if flagged else [j for j in MJOBS if j["state"] != "failed"]
    groups = [(f"{label} · {len(items)}", [list_row(j, running=flagged and j["id"] == "a3f9c21e") for j in items]) for label, items in pps.job_groups(jobs) if items]
    body = pk.phone_list(search_field("Search jobs…"), *[pk.phone_group(label, rows) for label, rows in groups])
    return pk.phone(pk.phone_head(f"Schedules · {len(jobs)}") + body, 632 if flagged else 500)


FOLD_SCHEDULE_H = 620


def fold_schedule():
    from gen import page
    return page("Fold · schedule, list and job side by side", 1104, FOLD_SCHEDULE_H, fold_open(1104, True, 300, True, FOLD_SCHEDULE_H))


def notifications_fold(total_w, with_sidebar, master_detail, h):
    import notif_studies as ns
    side = m_sidebar(h, selected="") if with_sidebar else ""
    pane_w = total_w - (280 if with_sidebar else 0)
    mark_all = f'<span style="display: inline-flex; align-items: center; min-height: 44px; padding: 0 12px; font-weight: 500; font-size: 15px; color: {INK2}">Mark all read</span>'
    head = m_screen_header("Notifications", "2 unread", glyph="", wide=True, back=not with_sidebar, sidebar_toggle=not with_sidebar, right=mark_all)
    v = ns.VIEW
    filters = ns.phone_segmented(v, [("All", ""), ("Needs you", "1"), ("Unread", "2")])
    groups = [ns.eyebrow("Needs you · 1", v, "14px 16px 6px"), ns.phone_row(v, ns.ROWS[1]), ns.eyebrow("Today", v, "14px 16px 6px"), ns.phone_row(v, ns.ROWS[0]),
              ns.phone_row(v, ns.ROWS[2]), ns.phone_row(v, ns.ROWS[3]), ns.eyebrow("Yesterday", v, "14px 16px 6px"), ns.phone_row(v, ns.ROWS[4])]
    triage = f'<div style="flex: 1; min-height: 0; overflow: hidden; background: {v["pane"]}"><div style="padding: 8px 0 6px">{filters}</div>{"".join(groups)}</div>'
    list_col = f'<div style="width: {300 if master_detail else pane_w}px; flex-shrink: 0; display: flex; flex-direction: column; overflow: hidden; background: {v["pane"]}">{triage}</div>'
    if master_detail:
        nav = f'<div style="display: flex; justify-content: flex-end; padding: 8px 12px 0; background: {v["pane"]}">{ns.phone_page_nav(v)}</div>'
        reader = f'<div style="flex: 1; min-width: 0; display: flex; flex-direction: column; background: {v["pane"]}">{nav}{ns.phone_reader(v)}</div>'
        body = f'<div style="flex: 1; min-height: 0; display: flex">{list_col}{reader}</div>'
    else:
        body = f'<div style="flex: 1; min-height: 0; display: flex">{list_col}</div>'
    pane = f'<div style="width: {pane_w}px; height: {h}px; display: flex; flex-direction: column; background: #ffffff">{head}{body}</div>'
    return f'<div style="width: {total_w}px; height: {h}px; display: flex; overflow: hidden; border-radius: 4px; box-shadow: 0 0 0 0.5px {P["line2"]}">{side}{pane}</div>'


FOLD_NOTIFICATIONS_H = 620


def fold_notifications():
    from gen import page
    return page("Fold · notifications, list and reader side by side", 1104, FOLD_NOTIFICATIONS_H, notifications_fold(1104, True, True, FOLD_NOTIFICATIONS_H))
