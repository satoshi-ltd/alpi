import panel_kit as pk
import profile_panel_studies as pps
from desktop_boards import INK, INK2, INK3, INK4, LINE, LINE2, MONO
from gen import DANGER, DOC_ACCENT, ic, identity_glyph, m_activity_list, m_activity_row, m_conn_header, m_eyebrow, m_group, m_roster, m_row, m_screen_header, m_section, m_shell_footer, m_sidebar
from notif_studies import dot, ell, flex, stack, wrap
from paper_studies import PAPER, button, text
from wg_settings_studies import P, glyph, mono
from wg_settings_studies import phone as panel_phone

WARNING_TEXT = "#b3470e"
ABBY, CLONARA, SCOUT = "#df4b9d", "#f05940", "#e5533d"

MJOBS = [
    {"id": "a3f9c21e", "title": "Weekly listing refresh", "about": "Compares every hotel’s listings with its intake and posts the differences to the hub.", "cron": "0 6 * * 1",
     "when": "every Monday at 06:00", "next": "Mon 12 Oct at 06:00", "word": "in 2d", "last": "ran 2d ago", "state": "active"},
    {"id": "7be40d19", "title": "Daily review digest", "about": "Summarises new guest reviews into strengths and complaints.", "cron": "30 7 * * *",
     "when": "every day at 07:30", "next": "Sat 10 Oct at 07:30", "word": "failed", "last": "last run failed · 1h ago", "state": "failed"},
    {"id": "c02a77f4", "title": "Price check before launch", "about": "Reads the live rates once before the launch and flags any gap.", "cron": "",
     "when": "once, Wed 14 Oct at 09:00", "next": "Wed 14 Oct at 09:00", "word": "in 4d", "last": "never run", "state": "active"},
    {"id": "91d3e6b0", "title": "Nudge after a quiet week", "about": "Asks the hub for news when nobody has written for seven days.", "cron": "",
     "when": "after 7 days without a message", "next": "", "word": "paused", "last": "ran 3w ago", "state": "paused"},
]
JOB_BANNER = ("Last run failed", "timed out after 20 min while reading reviews. Last good run: Thu 8 Oct at 07:30.")


def cap(value):
    return f'<span style="font-family: {MONO}; font-size: 11px; line-height: 1.5; color: {INK3}">{value}</span>'


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


def day_label(value):
    return f'<div style="padding: 14px 16px 2px">{m_eyebrow(value, INK3, 400, 0.1, 11)}</div>'


def group_label(value, color=INK3):
    return f'<div style="padding: 16px 16px 6px">{m_eyebrow(value, color)}</div>'


def next_row(glyph_html, title, sub, when):
    return (f'<div role="button" style="display: flex; align-items: center; gap: 12px; min-height: 56px; padding: 8px 16px; box-sizing: border-box">{glyph_html}'
            f'<div style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px"><span style="font-weight: 500; font-size: 15px; line-height: 19.5px; color: {INK}">{title}</span>'
            f'<span style="font-family: {MONO}; font-size: 12px; line-height: 15.6px; color: {INK3}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis">{sub}</span></div>'
            f'<span style="font-family: {MONO}; font-weight: 500; font-size: 13px; color: {INK2}">{when}</span></div>')


def activity_list():
    needs = (group_label("Needs you · 3", WARNING_TEXT)
             + m_activity_row(identity_glyph("abby", ABBY, 20), "abby · wants to run a command", "approval · 2m ago", "warning", "Review")
             + m_activity_row(identity_glyph("doc", DOC_ACCENT, 20), "doc · Which lab should I book?", "question · 12s ago", "warning", "Review")
             + m_activity_row(identity_glyph("clonara", CLONARA, 20), "clonara · weekly labs", "failed 3h ago", "danger", "Run again"))
    running = (group_label("Running · 2")
               + m_activity_row(identity_glyph("alpha", DOC_ACCENT, 20), "alpha · #collect", "phase 2 of 4 · daily-digest", "accent")
               + m_activity_row(identity_glyph("doc", DOC_ACCENT, 20), "doc · Daily brief", "40s · scheduled", "accent"))
    nxt = (group_label("Next up · 4")
           + day_label("Today")
           + next_row(identity_glyph("abby", ABBY, 20), "abby · Invoice reminder", "in 3h", "18:00")
           + day_label("Tomorrow")
           + next_row(identity_glyph("doc", DOC_ACCENT, 20), "doc · Daily brief", "in 17h", "07:30")
           + next_row(identity_glyph("clonara", CLONARA, 20), "clonara · weekly labs", "in 19h", "09:00")
           + day_label("Mon 12 Oct")
           + next_row(identity_glyph("scout", SCOUT, 20), "scout · Weekly listing refresh", "in 3d", "06:00"))
    return needs + running + nxt


def job_page_head():
    more = f'<span style="width: 44px; height: 44px; display: inline-flex; align-items: center; justify-content: center">{glyph("more", 16, P["ink2"])}</span>'
    return pk.phone_head("SCHEDULES", more)


def half(label, kind, disabled=False):
    opacity = "opacity: 0.55;" if disabled else ""
    return f'<span style="flex: 1; display: flex; {opacity}">{wide_button(label, kind)}</span>'


def ask_agent_row():
    return (f'<div style="display: flex; align-items: center; justify-content: center; gap: 8px; min-height: 44px; border-radius: 4px; box-shadow: 0 0 0 0.5px {P["line2"]}">'
            f'{glyph("sparkle", 14, P["ink2"])}{text("Ask the agent to change this", 13, P["ink2"], 500)}</div>')


def job_facts(rows):
    return "<div>" + "".join(pk.phone_fact(label, content, 62) for label, content in rows) + "</div>"


def job_title(title, status, when):
    return stack(text(title, 18, P["ink"], 600, "white-space: normal"), flex(status, pmono_(when), gap=8), gap=4)


def pmono_(value):
    return mono(value, 10, P["ink3"])


def sheet_item(icon, label, detail="", danger=False):
    color = P["danger"] if danger else P["ink"]
    det = mono(detail, 11, P["ink3"]) if detail else ""
    return (f'<div style="display: flex; align-items: center; gap: 12px; min-height: 48px; padding: 0 16px; box-shadow: inset 0 -0.5px 0 {P["line"]}">'
            f'<span style="width: 20px; display: inline-flex; justify-content: center">{glyph(icon, 16, P["danger"] if danger else P["ink2"])}</span>'
            f'<span style="flex: 1; font-size: 14px; color: {color}">{label}</span>{det}</div>')


def job_status(job, running):
    if running:
        return flex(dot(P["ink"], 7, "box-shadow: 0 0 0 3px " + P["selected"]), mono("running", 10, P["ink2"]), gap=5)
    return pk.phone_status({"failed": "failed", "paused": "paused"}.get(job["state"], "active"), "danger" if job["state"] == "failed" else "ink")


def job_body(job, running=False, more=False):
    failed = job["state"] == "failed"
    title = job_title(job["title"], job_status(job, running), job["when"])
    if more:
        title = flex(f'<div style="flex: 1; min-width: 0">{title}</div>', f'<span style="width: 44px; height: 44px; display: inline-flex; align-items: center; justify-content: center">{glyph("more", 16, P["ink2"])}</span>', gap=4)
    banner = pk.phone_banner(*JOB_BANNER) if failed else ""
    run = half(f"Running · 0:42" if running else "Run now", "primary", running)
    toggle = half("Resume" if job["state"] == "paused" else "Pause", "secondary", running)
    last = "running since 07:31" if running else job["last"]
    last_html = f'<span style="color: {P["danger"]}">{last}</span>' if failed and not running else last
    rows = [("ABOUT", job["about"]), ("WHEN", job["when"] + (pk.kw(job["cron"]) if job["cron"] else ""))]
    if job["state"] != "paused":
        rows.append(("NEXT", f'{job["next"]} · {job["word"]}'))
    rows += [("LAST RUN", last_html), ("RUNS", "agent · 20 min timeout"), ("NOTIFY", "silent — failures still alert" if failed else "pushes to your apps")]
    prompt = (f'<div style="padding: 8px 10px 10px; border-radius: 4px; box-shadow: 0 0 0 0.5px {P["line"]}; background: {P["bg"]}">{mono("PROMPT", 10, P["ink3"], extra="letter-spacing: 0.06em")}'
              f'<div style="margin-top: 4px">{pps.reading(pk.PROMPT, 11.5)}</div></div>')
    return [banner, title, flex(run, toggle, gap=6), ask_agent_row(), job_facts(rows), prompt]


def job_page(job, running=False, h=800):
    return panel_phone(job_page_head() + pk.phone_body(*job_body(job, running), gap=10), h)


def job_failed():
    return job_page(MJOBS[1], h=870)


def job_healthy():
    return job_page(MJOBS[0], h=760)


def job_running():
    return job_page(MJOBS[1], running=True, h=870)


def sheet_item(icon, label, detail="", danger=False):
    color = P["danger"] if danger else P["ink"]
    det = mono(detail, 11, P["ink3"]) if detail else ""
    return (f'<div style="display: flex; align-items: center; gap: 12px; min-height: 48px; padding: 0 16px; box-shadow: inset 0 -0.5px 0 {P["line"]}">'
            f'<span style="width: 20px; display: inline-flex; justify-content: center">{glyph(icon, 16, P["danger"] if danger else P["ink2"])}</span>'
            f'<span style="flex: 1; font-size: 14px; color: {color}">{label}</span>{det}</div>')


def job_more():
    dimmed = job_page_head() + pk.phone_body(job_title("Daily review digest", pk.phone_status("failed", "danger"), "every day at 07:30"), gap=10)
    sheet = (f'<div style="position: absolute; left: 0; right: 0; bottom: 0; border-radius: 4px 4px 0 0; background: {P["pane"]}; box-shadow: 0 0 0 0.5px {P["line2"]}; padding-top: 8px">'
             f'<div style="display: flex; justify-content: center; padding-bottom: 10px"><span style="width: 36px; height: 4px; border-radius: 2px; background: {P["ink4"]}; opacity: 0.6"></span></div>'
             f'{sheet_item("file-text", "Last output", "opens the notification")}{sheet_item("copy", "Copy job id", "7be40d19")}{sheet_item("trash-2", "Delete job…", "", True)}'
             f'<div style="height: 16px"></div></div>')
    dim = f'<div style="position: absolute; inset: 0; background: color-mix(in srgb, {P["pane"]} 72%, transparent)"></div>'
    return panel_phone(f'<div style="position: relative; flex: 1; min-height: 0; display: flex; flex-direction: column">{dimmed}<div style="flex: 1; background: {P["bg"]}"></div>{dim}{sheet}</div>', 330)


def fold_pane(selected):
    groups = [(f"{label} · {len(items)}", items) for label, items in pps.job_groups(MJOBS) if items]
    return groups, MJOBS[selected]


def fold_list(width, groups, chosen, h):
    body = "".join(pk.phone_group(label, [list_row(j, selected=j is chosen) for j in items]) for label, items in groups)
    return (f'<div style="width: {width}px; flex-shrink: 0; height: {h}px; display: flex; flex-direction: column; overflow: hidden; background: {P["bg"]}; box-shadow: inset -0.5px 0 0 {P["line"]}">'
            f'<div style="padding: 8px 10px 0">{pk.search_row("Search jobs…")}</div><div style="padding: 0 10px">{body}</div></div>')


def fold_detail(chosen, h):
    pieces = job_body(chosen, more=True)
    body = f'<div style="padding: 12px 20px 20px; display: flex; flex-direction: column; gap: 10px; overflow: hidden">{"".join(x for x in pieces if x)}</div>'
    return f'<div style="flex: 1; min-width: 0; height: {h}px; display: flex; flex-direction: column; overflow: hidden; background: {P["bg"]}">{body}</div>'


def fold_open(total_w, with_sidebar, list_w, master_detail, h):
    groups, chosen = fold_pane(1)
    side = m_sidebar(h, selected="") if with_sidebar else ""
    pane_w = total_w - (280 if with_sidebar else 0)
    head = pane_head(not with_sidebar)
    if master_detail:
        body = f'<div style="flex: 1; min-height: 0; display: flex">{fold_list(list_w, groups, chosen, h - 64)}{fold_detail(chosen, h - 64)}</div>'
    else:
        rows = "".join(pk.phone_group(label, [list_row(j) for j in items]) for label, items in groups)
        body = f'<div style="flex: 1; min-height: 0; overflow: hidden; background: {P["bg"]}; padding: 0 10px">{rows}</div>'
    pane = f'<div style="width: {pane_w}px; height: {h}px; display: flex; flex-direction: column; background: #ffffff">{head}{body}</div>'
    return f'<div style="width: {total_w}px; height: {h}px; display: flex; overflow: hidden; border-radius: 4px; box-shadow: 0 0 0 0.5px {P["line2"]}">{side}{pane}</div>'


def pane_head(sidebar_toggle):
    return m_screen_header("scout", "SCHEDULES · 4", wide=True, back=not sidebar_toggle, creased=True, accent=SCOUT, glyph=obj_scout(), sidebar_toggle=sidebar_toggle)


def obj_scout():
    from wg_settings_studies import obj
    return obj("scout", 20)


def needs_band():
    rows = (m_activity_row(identity_glyph("abby", ABBY, 20), "abby · wants to run a command", "approval · 2m ago", "warning", "Review")
            + m_activity_row(identity_glyph("clonara", CLONARA, 20), "clonara · weekly labs", "failed 3h ago", "danger", "Run again"))
    head = (f'<div style="display: flex; align-items: center; padding: 12px 16px 4px">{m_eyebrow("Needs you · 2", WARNING_TEXT, 500, 0.06, 11, "flex: 1")}'
            f'<span style="font-family: {MONO}; font-size: 11px; color: {INK3}">Activity</span>{ic("chev-r", 14, INK4)}</div>')
    return f'<div style="background: rgba(20,20,20,0.04); border-bottom: 0.5px solid rgba(20,20,20,0.07)">{head}{rows}</div>'


def chat_menu_row(icon, label, detail="", dot_color=None):
    mark = f'<span style="position: relative; display: inline-flex">{ic(icon, 20, INK2)}' + (f'<span style="position: absolute; top: -2px; right: -3px; width: 8px; height: 8px; border-radius: 4px; background: {dot_color}; border: 1.5px solid #ffffff; box-sizing: border-box"></span>' if dot_color else "") + "</span>"
    det = f'<span style="font-family: {MONO}; font-weight: 500; font-size: 12px; color: {DANGER if dot_color else INK3}">{detail}</span>' if detail else ""
    return (f'<div style="display: flex; align-items: center; gap: 14px; min-height: 48px; padding: 0 20px"><span style="width: 24px; display: inline-flex; justify-content: center">{mark}</span>'
            f'<span style="flex: 1; font-size: 15px; color: {INK}">{label}</span>{det}</div>')


def settings_head_chips(selected):
    names = ("Overview", "Usage", "Identity", "Service", "ALP", "Schedule", "Sandbox", "Voice", "MCP", "Brain", "Storage")
    chips = "".join(
        f'<span style="display: inline-flex; align-items: center; min-height: 44px; padding: 0 12px; border-radius: 4px; font-size: 13px; white-space: nowrap; '
        f'background: {"rgba(20,20,20,0.06)" if n == selected else "transparent"}; color: {INK if n == selected else INK2}; font-weight: {600 if n == selected else 400}">{n}</span>'
        for n in names)
    return f'<div style="display: flex; flex-shrink: 0; gap: 2px; padding: 0 12px; overflow: hidden; border-bottom: 0.5px solid {LINE}; background: #ffffff">{chips}</div>'


def settings_summary():
    return (f'<div style="margin: 12px 12px 0; padding: 12px 14px; border-radius: 4px; background: rgba(20,20,20,0.04); display: flex; flex-direction: column; gap: 8px">'
            f'<span style="font-family: {MONO}; font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase; color: {WARNING_TEXT}">Needs you · 2</span>'
            f'<div style="display: flex; align-items: center; gap: 10px; min-height: 44px"><span style="width: 6px; height: 6px; border-radius: 999px; background: {DANGER}"></span><span style="flex: 1; font-size: 14px; color: {INK}">1 job failed</span><span style="font-family: {MONO}; font-size: 11px; color: {INK3}">Schedule</span>{ic("chev-r", 14, INK4)}</div>'
            f'<div style="display: flex; align-items: center; gap: 10px; min-height: 44px"><span style="width: 6px; height: 6px; border-radius: 999px; background: {DANGER}"></span><span style="flex: 1; font-size: 14px; color: {INK}">2 memory files over their limit</span><span style="font-family: {MONO}; font-size: 11px; color: {INK3}">Brain</span>{ic("chev-r", 14, INK4)}</div></div>')


def list_row(job, running=False, selected=False):
    failed = job["state"] == "failed"
    paused = job["state"] == "paused"
    mark = dot(P["ink"], 8, "box-shadow: 0 0 0 3px " + P["selected"]) if running else pk.job_mark(job["state"])
    word = "running" if running else job["word"]
    tail = mono(word, 10, P["danger"] if failed else P["ink3"]) if word else ""
    top = flex(mark, ell(job["title"], 13, P["ink3"] if paused else P["ink"], 600, "flex: 1"), tail, gap=8)
    last = "started 07:31" if running else ("failed 1h ago · timed out" if failed else job["last"])
    lines = f'<div style="padding-left: 15px; display: flex; flex-direction: column; gap: 2px">{ell(job["about"], 11, P["ink3"])}{mono(last, 10, P["danger"] if failed else P["ink3"])}</div>'
    html = pk.phone_row(top + lines)
    return f'<div style="background: {P["selected"]}; border-radius: 4px">{html}</div>' if selected else html


def schedule_list(flagged=True):
    jobs = MJOBS if flagged else [j for j in MJOBS if j["state"] != "failed"]
    groups = [(f"{label} · {len(items)}", [list_row(j, running=flagged and j["id"] == "a3f9c21e") for j in items]) for label, items in pps.job_groups(jobs) if items]
    body = pk.phone_body(pk.search_row("Search jobs…"), *[pk.phone_group(label, rows) for label, rows in groups], gap=0, pad="0 10px")
    return panel_phone(pk.phone_head(f"SCHEDULES · {len(jobs)}") + body, 590 if flagged else 520)


FOLD_SCHEDULE_H = 620


def fold_schedule():
    from gen import page
    return page("Fold · schedule, list and job side by side", 1104, FOLD_SCHEDULE_H, fold_open(1104, True, 300, True, FOLD_SCHEDULE_H))


def notifications_fold(total_w, with_sidebar, master_detail, h):
    import notif_studies as ns
    side = m_sidebar(h, selected="") if with_sidebar else ""
    pane_w = total_w - (280 if with_sidebar else 0)
    mark_all = f'<span style="display: inline-flex; align-items: center; min-height: 44px; padding: 0 12px; font-weight: 500; font-size: 14px; color: {INK2}">Mark all read</span>'
    head = m_screen_header("Notifications", "2 UNREAD", glyph="", wide=True, back=not with_sidebar, sidebar_toggle=not with_sidebar, right=mark_all)
    v = ns.VIEW
    filters = ns.phone_segmented(v, [("All", ""), ("Needs you", "1"), ("Unread", "2")])
    groups = [ns.eyebrow("Needs you · 1", v, "14px 16px 6px"), ns.phone_row(v, ns.ROWS[1]), ns.eyebrow("Today", v, "14px 16px 6px"), ns.phone_row(v, ns.ROWS[0]),
              ns.phone_row(v, ns.ROWS[2]), ns.phone_row(v, ns.ROWS[3]), ns.eyebrow("Yesterday", v, "14px 16px 6px"), ns.phone_row(v, ns.ROWS[4])]
    triage = f'<div style="flex: 1; min-height: 0; overflow: hidden; background: {v["pane"]}"><div style="padding: 8px 0 6px">{filters}</div>{"".join(groups)}</div>'
    list_col = f'<div style="width: {300 if master_detail else pane_w}px; flex-shrink: 0; display: flex; flex-direction: column; overflow: hidden; background: {v["pane"]}; box-shadow: inset -0.5px 0 0 {v["line"]}">{triage}</div>'
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
