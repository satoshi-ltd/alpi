from gen import DOC_ACCENT, ic, page
from desktop_boards import AMBER, HOVER, INK, INK2, INK3, INK4, LINE, LINE2, PANE, MONO, SIDE, diamond_stack, row
from conversation_boards import h1, label, mono, spec

PAGE_W = 1280
COLUMN_PAD = 20


def drawing(title, inner):
    return f'<div style="flex: 1; min-width: 0; display: flex; flex-direction: column">{spec(title, inner, pad=COLUMN_PAD)}</div>'


def cap(text):
    return mono(text, 11, INK3)


def stack(*items, gap=14):
    return f'<div style="display: flex; flex-direction: column; gap: {gap}px">{"".join(items)}</div>'


def tagged(title, inner):
    return stack(cap(title), inner, gap=8)


WG_GRID = "grid-template-columns: minmax(90px, 1fr) 168px 40px 52px 44px; gap: 12px; padding: 0 10px"


def wg_head():
    cells = "".join(f'<span style="{"text-align: right" if i > 2 else ""}">{t}</span>' for i, t in enumerate(("Workgroup", "Status", "Members", "Spend", "Updated"), start=1))
    return f'<div style="display: grid; {WG_GRID}; align-items: center; min-height: 32px; font-family: {MONO}; font-size: 11px; text-transform: uppercase; color: {INK3}">{cells}</div>'


def wg_row(name, accent, dot, status, members, spend, age, note=""):
    lines = (f'<span style="display: inline-flex; align-items: center; gap: 6px; font-size: 12px; color: {INK2}; white-space: nowrap">'
             f'<span style="width: 7px; height: 7px; border-radius: 999px; background: {dot}; flex-shrink: 0"></span>{status}</span>')
    if note:
        lines += f'<span style="padding-left: 13px; font-family: {MONO}; font-size: 11px; color: {INK3}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis">{note}</span>'
    cell = lambda v, size: f'<span style="text-align: right; font-family: {MONO}; font-size: {size}px; color: {INK2 if size == 12 else INK3}">{v}</span>'
    return (f'<div style="display: grid; {WG_GRID}; align-items: center; min-height: 64px; border-bottom: 0.5px solid {LINE}">'
            f'<span style="display: flex; align-items: center; gap: 10px; min-width: 0">{diamond_stack(accent)}<strong style="font-size: 13px; font-weight: 700; color: {INK}">{name}</strong></span>'
            f'<span style="display: flex; flex-direction: column; gap: 3px; min-width: 0">{lines}</span>{cell(members, 12)}{cell(spend, 12)}{cell(age, 11)}</div>')


def wg_list(notes):
    note = lambda text: text if notes else ""
    return stack(
        wg_head()
        + wg_row("alpha", DOC_ACCENT, "#3fb37a", "Working · media", 3, "$0.40", "2m", note("setup done"))
        + wg_row("launch-crew", AMBER, "#e08a3c", "Queued · #2", 4, "$1.12", "9m", note("setup done · media next"))
        + wg_row("digest", "#8a5cf6", INK4, "Idle", 2, "$0.08", "1d"),
        cap("A queued workgroup hides its finished setup; the pipeline phase shows only while it runs." if not notes else "The caption names what finished and what waits; rows with nothing finished draw none."),
        gap=10,
    )


def wg_now():
    return wg_list(False)


def wg_proposed():
    return wg_list(True)


def phone_frame(inner):
    return f'<div style="width: 390px; max-width: 100%; border-radius: 12px; border: 0.5px solid {LINE2}; overflow: hidden; background: #ffffff">{inner}</div>'


LOCK_BG = "background: linear-gradient(180deg, #1b2530 0%, #0d131a 100%)"


def glass(inner, pad=14):
    return f'<div style="padding: {pad}px; border-radius: 22px; background: rgba(255,255,255,0.14); display: flex; flex-direction: column; gap: 10px; box-sizing: border-box">{inner}</div>'


def app_icon():
    return f'<span style="width: 34px; height: 34px; border-radius: 8px; background: #fff; display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0">{diamond_stack(AMBER, 10)}</span>'


def push_banner(actions):
    buttons = ""
    if actions:
        pill_ = lambda text, color: f'<span style="flex: 1; text-align: center; padding: 9px 0; border-radius: 12px; background: rgba(255,255,255,0.14); font-size: 14px; font-weight: 600; color: {color}">{text}</span>'
        buttons = f'<div style="display: flex; gap: 8px; margin-top: 4px">{pill_("Deny", "#ff9b94")}{pill_("Allow once", "#fff")}</div>'
    head = (f'<div style="display: flex; gap: 10px; align-items: flex-start">{app_icon()}<div style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px">'
            f'<span style="display: flex; justify-content: space-between; font-size: 12px; color: rgba(255,255,255,0.6)"><span>ALPI</span><span>now</span></span>'
            f'<span style="font-size: 14px; font-weight: 600; color: #fff">remote-casa · abby · approval needed</span>'
            f'<span style="font-family: {MONO}; font-size: 12px; color: rgba(255,255,255,0.75)">rm -rf dist &amp;&amp; npm run build</span></div></div>')
    return glass(head + buttons, 12)


def live_activity():
    seg = lambda on: f'<span style="flex: 1; height: 5px; border-radius: 999px; background: {AMBER if on else "rgba(255,255,255,0.25)"}"></span>'
    top = (f'<div style="display: flex; align-items: center; gap: 10px">{diamond_stack(AMBER, 10)}<span style="flex: 1; font-size: 15px; font-weight: 600; color: #fff">alpha · #collect</span>'
           f'<span style="font-family: {MONO}; font-size: 13px; color: #fff">4:12</span></div>')
    bar = f'<div style="display: flex; gap: 4px">{seg(True)}{seg(True)}{seg(False)}{seg(False)}</div>'
    foot = (f'<div style="display: flex; justify-content: space-between; font-family: {MONO}; font-size: 12px; color: rgba(255,255,255,0.7)"><span>phase 2 of 4</span><span>doc · alpi · yuri</span></div>')
    return glass(top + bar + foot)


def lock_screen():
    return (f'<div style="width: 360px; box-sizing: border-box; padding: 34px 16px 22px; border-radius: 34px; {LOCK_BG}; display: flex; flex-direction: column; gap: 14px">'
            f'<div style="display: flex; flex-direction: column; align-items: center; gap: 2px; padding-bottom: 10px"><span style="font-size: 13px; color: rgba(255,255,255,0.7)">Thursday 1 October</span>'
            f'<span style="font-size: 64px; font-weight: 600; line-height: 1.05; letter-spacing: -0.02em; color: #fff">9:41</span></div>'
            f'{live_activity()}{push_banner(True)}</div>')


def live_now():
    activity = phone_frame(f'<div style="padding: 12px 16px 4px">{cap("Running · 2")}</div>'
                           + f'<div style="display: flex; align-items: center; gap: 12px; min-height: 56px; padding: 8px 16px">{ic("activity", 16, "#8a5a0a")}'
                           f'<div style="flex: 1; display: flex; flex-direction: column; gap: 4px"><span style="font-weight: 500; font-size: 15px; color: {INK}">alpha · #collect</span>'
                           f'<span style="font-family: {MONO}; font-size: 12px; color: {INK3}">phase 2 of 4 · daily-digest</span></div></div>')
    banner = (f'<div style="width: 350px; box-sizing: border-box; padding: 12px; border-radius: 18px; background: {SIDE}; border: 0.5px solid {LINE2}; display: flex; flex-direction: column; gap: 10px">'
              f'<div style="display: flex; gap: 10px; align-items: flex-start"><span style="width: 34px; height: 34px; border-radius: 8px; background: {PANE}; border: 0.5px solid {LINE2}; display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0">{diamond_stack(AMBER, 10)}</span>'
              f'<div style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px"><span style="display: flex; justify-content: space-between; font-size: 12px; color: {INK3}"><span>ALPI</span><span>now</span></span>'
              f'<span style="font-size: 14px; font-weight: 600; color: {INK}">remote-casa · abby · approval needed</span><span style="font-family: {MONO}; font-size: 12px; color: {INK2}">rm -rf dist &amp;&amp; npm run build</span></div></div>'
              f'<div style="display: flex; gap: 8px"><span style="flex: 1; text-align: center; padding: 9px 0; border-radius: 12px; background: {HOVER}; font-size: 14px; font-weight: 600; color: #b73737">Deny</span>'
              f'<span style="flex: 1; text-align: center; padding: 9px 0; border-radius: 12px; background: {HOVER}; font-size: 14px; font-weight: 600; color: {INK}">Allow once</span></div></div>')
    return stack(
        tagged("Activity tab · only while the app is open", activity),
        tagged("Local notification · only while the app holds a socket", banner),
        cap("Close the app and neither reaches the lock screen."),
        gap=18,
    )


def live_proposed():
    return stack(tagged("Lock screen · app closed", lock_screen()), cap("A Live Activity for the running workgroup and the approval as a push with the same two actions."), gap=10)


EMPTY = (
    ("Desktop · Workgroups list", "box-d", ("No workgroups yet", "a hub profile plus the members it directs"), ("No workgroups yet", "A workgroup is a hub profile plus the members it directs.")),
    ("Desktop · Workgroup thread", "box-d", ("no posts yet", "direct @doc to open a #task"), ("No posts yet", "Direct @doc to open a #task.")),
    ("Desktop · Activity panel", "box-d", ("Nothing running · agents at work show up here", ""), ("Nothing running", "Running turns, workgroup phases, schedules and anything waiting on you show up here.")),
    ("Desktop · Sessions menu", "box-d", ("No sessions yet", ""), ("No sessions yet", "A session starts with your first message.")),
    ("Desktop · Connections", "box-d", ("No paired apps yet · create a connection and share its pairing link with a phone or desktop.", ""), ("No paired apps yet", "Create a connection and share its pairing link with a phone or desktop.")),
    ("Desktop · MCP server, env keys", "env", "none", "No env keys"),
    ("Mobile · Roster", "box-m", ("Nothing here yet", "This daemon has no profiles or workgroups yet."), ("No profiles or workgroups yet", "Create one to begin.")),
    ("Mobile · Activity", "box-m", ("Nothing running", "Running turns, workgroup phases, schedules and anything waiting on you show up here."), ("Nothing running", "Running turns, workgroup phases, schedules and anything waiting on you show up here.")),
    ("Mobile · Workgroup thread", "box-m", ("no posts yet", "direct @doc to open a #task"), ("No posts yet", "Direct @doc to open a #task.")),
    ("Mobile · Connection sheet", "box-m", ("Not paired yet — tap below to scan a QR.", ""), ("Not paired yet", "Tap below to scan a QR.")),
    ("Mobile · Email row", "pill", "none", "No accounts yet"),
)


def empty_box(client, title, hint):
    size, hint_size = (14, 12) if client == "d" else (16, 14)
    body = f'<span style="font-size: {hint_size}px; line-height: 1.45; color: {INK3}; max-width: 380px">{hint}</span>' if hint else ""
    return (f'<div style="display: flex; flex-direction: column; align-items: center; gap: 6px; padding: 14px 20px; border-radius: 10px; border: 0.5px solid {LINE}; background: {PANE}; text-align: center">'
            f'<span style="font-size: {size}px; font-weight: 600; color: {INK if client == "d" else INK2}">{title}</span>{body}</div>')


def empty_inline(kind, text):
    pill = f'<span style="display: inline-flex; align-items: center; min-height: 22px; padding: 0 8px; border-radius: 999px; background: {HOVER}; font-family: {MONO}; font-size: 12px; color: {INK2}; opacity: 0.55">{text}</span>'
    value = pill if kind == "pill" else f'<span style="font-size: 12px; color: {INK3}">{text}</span>'
    name = "Email" if kind == "pill" else "env"
    return f'<div style="display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; border-radius: 10px; border: 0.5px solid {LINE}; background: {PANE}"><span style="font-size: 13px; color: {INK}">{name}</span>{value}</div>'


def empty_column(index):
    items = []
    for where, kind, *texts in EMPTY:
        now_or_proposed = texts[index]
        drawn = empty_inline(kind, now_or_proposed) if kind in ("env", "pill") else empty_box(kind[-1], *now_or_proposed)
        items.append(tagged(where, drawn))
    return stack(*items, gap=12)


def empty_now():
    return empty_column(0)


def empty_proposed():
    return empty_column(1)


PROPOSALS = [
    {
        "id": "UI-WG.STATUS",
        "client": "desktop",
        "area": "Workgroups · list",
        "title": "A workgroup row says what finished as well as what runs",
        "why": "The Status cell shows one state, so a workgroup whose setup is done and whose media pipeline waits reads only Queued · #2. The recommendation is a second mono line under the existing dot and label naming the finished phases and what is next. The alternative is one compound line, setup done · media queued #2, which does not fit the 10.5rem column and would truncate.",
        "now": wg_now,
        "proposed": wg_proposed,
        "accept": "The Status cell keeps today's dot and label and adds one mono caption naming the finished phases and, when a later phase waits, that phase; a row with nothing finished draws no caption; the row keeps its 64px height and the caption truncates with an ellipsis at the column width; dot colours are unchanged.",
        "h": 700,
    },
    {
        "id": "UI-MOB.LIVE-ACTIVITY",
        "client": "mobile",
        "area": "Lock screen · Live Activity and approval push",
        "title": "A running workgroup and an approval reach a locked phone",
        "why": "Today the phone learns about a running workgroup only in the Activity tab and about an approval only through a local notification while the app is alive. This is a design proposal only while the push relay is pending: the card and the banner are drawn so the relay work has a target. The alternative is the approval push alone, without a Live Activity, which needs no widget extension.",
        "now": live_now,
        "proposed": live_proposed,
        "accept": "A running workgroup shows as a Live Activity with its name and task, phase segments, elapsed time and the members working; an approval arrives as a push with the app closed, carrying Deny and Allow once as actions. Both draw in the light and dark lock screens and stay within the system's Live Activity height.",
        "h": 870,
    },
    {
        "id": "UI-EMPTY-VOICE",
        "client": "desktop + mobile",
        "area": "Empty states",
        "title": "Empty states speak in one voice on both clients",
        "why": "Empty copy mixes lowercase headings, none, a middle dot or em dash joining title and hint, and hints with or without a full stop; desktop and mobile word the same absence differently. The recommendation is one rule: a sentence-case title, No X yet for a list that will fill or Nothing running for a live state, and at most one hint sentence. The alternative is titles without hints, which is shorter but drops the next step.",
        "now": empty_now,
        "proposed": empty_proposed,
        "accept": "Every empty state on both clients has a sentence-case title and, where it helps, one hint sentence that starts with a capital and ends with a full stop; none uses none, a lowercase heading, a middle dot or an em dash to join title and hint; an inline absence reads No X. The same absence reads the same on desktop and mobile.",
        "h": 1580,
    },
]


def proposal_board(p):
    kicker = " · ".join((p["id"], p["client"], p["area"]))
    head = f'<div style="display: flex; flex-direction: column; gap: 10px">{label(kicker)}{h1(p["title"], p["why"])}</div>'
    drawings = f'<div style="display: flex; gap: 24px; align-items: stretch">{drawing("Now", p["now"]())}{drawing("Proposed", p["proposed"]())}</div>'
    accept = (f'<div style="display: flex; flex-direction: column; gap: 6px">{label("Accept")}'
              f'<p style="margin: 0; max-width: 1080px; font-size: 13px; line-height: 1.55; color: {INK}">{p["accept"]}</p></div>')
    body = (f'<div data-proposal="{p["id"]}" style="padding: 40px 48px; display: flex; flex-direction: column; gap: 26px; box-sizing: border-box">'
            f'{head}{drawings}{accept}</div>')
    return page("Proposal " + p["id"], PAGE_W, p["h"], body)


def board_name(p):
    return "Proposals-" + p["id"] + ".dc.html"


PROPOSAL_BOARDS = [(board_name(p), (lambda p=p: proposal_board(p)), p["h"], p["id"] + " · " + p["title"]) for p in PROPOSALS]
