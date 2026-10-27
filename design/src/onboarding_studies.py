from brand_boards import black_alpaca
from desktop_boards import MONO
from first_run_parts import (COPY, PANE, desktop_states, fold_box, fold_first_profile, q_denied, q_first_profile, q_pair, q_paired,
                             q_scan, q_welcome, Q_COL, Q_FOLD_EDGE, Q_FOLD_H, Q_FOLD_W)
from gen import ic, page
from notif_studies import VIEW, dot, ell, flex, mark, mono, spacer, stack, wrap
from paper_studies import PAPER, button, field, note, text

SKETCH_ZOOM = 1.35


def say(value, p=VIEW, size=11.5):
    return wrap(value, size, p["ink3"], lh=1.5)


def status_dot(p, state, size=6):
    colour = {"online": p["ink"], "offline": p["danger"], "stopped": p["ink4"]}[state]
    return dot(colour, size)


def window(p, side, main, h=232):
    bar = (f'<div style="height: 20px; flex-shrink: 0; display: flex; align-items: center; gap: 5px; padding: 0 9px; background: {p["side"]}; '
           f'box-shadow: inset 0 -0.5px 0 {p["line"]}">{dot(p["ink4"], 7)}{dot(p["ink4"], 7)}{dot(p["ink4"], 7)}</div>')
    body = (f'<div style="flex: 1; min-height: 0; display: flex; position: relative">{side}'
            f'<div style="flex: 1; min-width: 0; display: flex; flex-direction: column; background: {p["pane"]}">{main}</div></div>')
    return (f'<div style="height: {h}px; border-radius: 4px; overflow: hidden; background: {p["pane"]}; box-shadow: 0 0 0 1px {p["line2"]}; '
            f'display: flex; flex-direction: column">{bar}{body}</div>')


def conn_chip(p, name, host, state):
    glyph = f'<span style="position: relative; display: inline-flex">{ic("chip", 12, p["ink2"])}<span style="position: absolute; right: -3px; bottom: -3px; display: inline-flex">{status_dot(p, state, 5)}</span></span>'
    names = stack(text(name, 10.5, p["ink"], 500), ell(host, 8.5, p["ink3"], extra=f"font-family: {MONO}"), gap=1, extra="flex: 1")
    return flex(glyph, names, ic("chev-d", 10, p["ink3"]), gap=7,
                extra=f"padding: 5px 7px; background: {p['pane']}; border-radius: 4px; box-shadow: 0 0 0 0.5px {p['line2']}")


def srow(p, shape, name, active=False):
    glyph = black_alpaca(15, p["ink"]) if shape == "alpaca" else mark(shape, 12)
    bg = p["pane"] if active else "transparent"
    return flex(f'<span style="width: 15px; display: inline-flex; justify-content: center">{glyph}</span>', text(name, 10.5, p["ink"] if active else p["ink2"], 500 if active else 400),
                gap=6, extra=f"height: 22px; padding: 0 6px; border-radius: 4px; background: {bg}")


def sidebar(p, state, rows=()):
    head = f'<div style="padding: 8px 8px 4px; font-family: {MONO}; font-size: 8px; letter-spacing: 0.08em; text-transform: uppercase; color: {p["ink3"]}">Connection</div>'
    roster = "".join(srow(p, *r) for r in rows)
    return (f'<div style="width: 136px; flex-shrink: 0; background: {p["side"]}; box-shadow: inset -0.5px 0 0 {p["line"]}; display: flex; flex-direction: column">'
            f'{head}<div style="padding: 0 8px">{conn_chip(p, "This computer", "host.sock", state)}</div><div style="padding: 8px 4px; display: flex; flex-direction: column; gap: 1px">{roster}</div></div>')


ROSTER = (("alpaca", "alpi", True), ("plane", "abby"), ("heart", "doc"), ("house", "etxea"))


def chat_head(p):
    return flex(black_alpaca(16, p["ink"]), text("alpi", 11.5, p["ink"], 600), mono("sonnet-4", 9, p["ink3"]), spacer(), ic("more", 12, p["ink3"]), gap=6,
                extra=f"padding: 8px 12px; box-shadow: inset 0 -0.5px 0 {p['line']}")


def composer(p, name="alpi"):
    return f'<div style="display: flex; padding: 8px 12px 10px">{field(f"Message {name}…", p, PAPER)}</div>'


def hint_line(p):
    return f'<div style="padding: 0 12px 8px; text-align: center">{mono("This is alpi on this computer · To use it from a phone: Settings → Connections", 8.5, p["ink3"])}</div>'


def d_running(p=VIEW):
    main = chat_head(p) + f'<div style="flex: 1; display: flex; align-items: center; justify-content: center">{say("A session starts with your first message.", p, 10)}</div>' + composer(p) + hint_line(p)
    return window(p, sidebar(p, "online", ROSTER), main)


def sketch(title, body, drawing, zoom=None):
    wrapped = f'<div style="zoom: {zoom}; width: 640px">{drawing}</div>' if zoom else drawing
    return f'<div style="display: flex; gap: 24px; align-items: flex-start"><div style="width: 300px; flex-shrink: 0">{note(title, body)}</div>{wrapped}</div>'


RUNNING = ("alpi runs here", "The window lands on the roster, alpi first. The connection reads This computer; one Mono line under the composer, with the composer focused, says how to add a phone and goes away with the first message.")
DESKTOP_ONBOARDING_H = 5660


def desktop_onboarding():
    head = ('<div style="display: flex; flex-direction: column; gap: 6px"><span style="font-size: 22px; font-weight: 600; letter-spacing: -0.018em; line-height: 1.3">First run</span>'
            f'<span style="font-size: 13px; color: {VIEW["ink3"]}; max-width: 760px; line-height: 1.5">Before drawing the shell the app asks the machine for its own alpi: running, stopped, absent or unsupported. '
            'On a true first run, with the local alpi never having answered on this machine and at most one saved connection, the window is the Welcome alone, with no sidebar. '
            'In every other case the Sidebar stays and the Welcome fills the main pane beside it. Once alpi has answered in a session, a later outage keeps the open view under the reconnecting banner.</span></div>')
    rows = sketch(RUNNING[0], RUNNING[1], d_running(), SKETCH_ZOOM) + "".join(sketch(title, body, drawing) for title, body, drawing in desktop_states())
    body = f'<div style="padding: 40px; display: flex; flex-direction: column; gap: 36px; box-sizing: border-box">{head}{rows}</div>'
    return page("Desktop · first run", 1280, DESKTOP_ONBOARDING_H, body)


def phone_screen(title, drawing):
    return page(title, 390, 844, drawing, bg=PANE)


def fold_screen(title, drawing):
    return page(title, Q_FOLD_W, Q_FOLD_H, drawing, bg=PANE)


def phone_onboarding():
    unreachable, used = COPY["unreachable"], COPY["used"]
    kept = {**unreachable, "hint": f"{unreachable['hint']} This phone kept the connection.", "action": "Open inbox", "saved": True}
    steps_fail = ("done", "fail", "todo")
    return {
        "welcome": phone_screen("Phone · pair with your alpi", q_welcome()),
        "paste": phone_screen("Phone · paste link", q_pair()),
        "connecting": phone_screen("Phone · pairing", q_pair(("done", "now", "todo"), busy="fr_p")),
        "unreachable": phone_screen("Phone · host unreachable", q_pair(steps_fail, failure=unreachable)),
        "used": phone_screen("Phone · link used", q_pair(("done", "done", "fail"), value="", failure=used, focus=True)),
        "kept": phone_screen("Phone · failed, connection kept", q_pair(steps_fail, failure=kept)),
        "scan": phone_screen("Phone · scan", q_scan()),
        "camera": phone_screen("Phone · camera not allowed", q_denied()),
        "blocked": phone_screen("Phone · camera blocked", q_denied(blocked=True)),
        "keyboard": phone_screen("Phone · typing, keyboard open", q_pair(keyboard=True)),
        "saved": phone_screen("Phone · pair again, connection saved", q_pair(value="", saved=True)),
        "paired": phone_screen("Phone · paired", q_paired()),
        "paired_done": phone_screen("Phone · paired, both on", q_paired(bio_on=True, alerts="granted")),
        "paired_denied": phone_screen("Phone · paired, alerts denied", q_paired(alerts="denied")),
        "first_profile": phone_screen("Phone · first profile", q_first_profile("admin")),
        "member": phone_screen("Phone · nothing shared", q_first_profile("member")),
        "fold_welcome": fold_screen("Fold · pair with your alpi", fold_box(q_welcome(w=Q_FOLD_W, h=Q_FOLD_H, edge=Q_FOLD_EDGE, col_w=Q_COL))),
        "fold_paired": fold_screen("Fold · paired", fold_box(q_paired(w=Q_FOLD_W, h=Q_FOLD_H, edge=Q_FOLD_EDGE, col_w=Q_COL))),
        "fold_profile": fold_screen("Fold · first profile", fold_first_profile()),
        "fold_profile_folded": fold_screen("Fold · first profile, list folded", fold_first_profile(folded=True)),
    }
