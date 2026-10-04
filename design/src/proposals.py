from gen import ic, page
from desktop_boards import AMBER, HOVER, INK, INK2, INK3, LINE2, PANE, MONO, SIDE, wg_mark
from conversation_boards import h1, label, mono, spec
from loading_studies import loading_now, loading_proposed

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


def phone_frame(inner):
    return f'<div style="width: 390px; max-width: 100%; border-radius: 12px; border: 0.5px solid {LINE2}; overflow: hidden; background: #ffffff">{inner}</div>'


LOCK_BG = "background: linear-gradient(180deg, #1b2530 0%, #0d131a 100%)"


def glass(inner, pad=14):
    return f'<div style="padding: {pad}px; border-radius: 22px; background: rgba(255,255,255,0.14); display: flex; flex-direction: column; gap: 10px; box-sizing: border-box">{inner}</div>'


def app_icon():
    return f'<span style="width: 34px; height: 34px; border-radius: 8px; background: #fff; display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0">{wg_mark(AMBER, 16)}</span>'


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
    top = (f'<div style="display: flex; align-items: center; gap: 10px">{wg_mark(AMBER, 16)}<span style="flex: 1; font-size: 15px; font-weight: 600; color: #fff">alpha · #collect</span>'
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
              f'<div style="display: flex; gap: 10px; align-items: flex-start"><span style="width: 34px; height: 34px; border-radius: 8px; background: {PANE}; border: 0.5px solid {LINE2}; display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0">{wg_mark(AMBER, 16)}</span>'
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


PROPOSALS = [
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
        "id": "UI-LOADING",
        "client": "desktop",
        "area": "Every wait · spinners, the pipeline strip and lists, desktop and mobile",
        "title": "Waiting looks like alpi, and the pipeline never waits for what it already knows",
        "why": "Desktop waits four ways: <code>SpinnerIcon</code> (a line arc, in Send, attachments, read aloud and the workgroup’s “Loading flow…” chip), the <code>chipSpin</code> and <code>btnSpin</code> CSS arcs, and the bare word “Loading…” in the skill viewer and the email cell. Mobile uses the platform <code>ActivityIndicator</code> in 25 screens, centred on an empty page, so every list jumps when its rows land. None of them is alpi’s, although <code>folds.mjs</code> already gives every profile an object with three tones and the alpaca a busy cycle through the profile colours. The workgroup strip shows “Loading flow…” until <code>host.workgroup.tasks</code> answers, but the workgroup row already carries <code>pipelines</code>, <code>launch</code> and <code>phase_map</code>, so the chain and its owners are known before the run state. Recommendation: the alpaca busy cycle when nobody owns the wait, the owner’s object sweeping when a profile does, placeholder rows and chips in the shape of what will land, and the strip drawn from the row at once. Alternative: one shared spinner restyled in ink on both clients, which unifies the look but keeps the empty pages and the strip’s wait.",
        "now": loading_now,
        "proposed": loading_proposed,
        "accept": "Shared: a <code>Busy</code> mark on both clients (the alpaca through the busy cycle, or a given fold sweeping its tones) built on the existing <code>Fold</code> components and <code>common/folds.mjs</code>, shown only after 300 ms, labelled “Loading” for screen readers, static with the word under reduced motion. Desktop: <code>SpinnerIcon</code>, the <code>Button</code> and <code>Chip</code> spinners and the <code>ChatPane</code> spinners become it at their current sizes; “Loading…” alone is gone; lists use <code>primitives/Skeleton</code> rows. Mobile: every <code>ActivityIndicator</code> becomes it and lists draw placeholder rows inside their cards. Workgroup strip: with one pipeline, or a cached run, the chain draws at once from the row with every phase pending and its owner, filled in place when the run arrives; otherwise the hub’s object sweeps beside placeholder chips; never the word. Tests cover the delay, reduced motion and the strip before and after the run on both clients; no green; light and dark match this board; the views are regenerated and the board is deleted.",
        "h": 2140,
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
