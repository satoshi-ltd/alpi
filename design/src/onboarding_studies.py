import json
import os
import subprocess

from brand_boards import black_alpaca
from desktop_boards import MONO
from gen import COMMON, ic, page
from notif_studies import VIEW, dot, ell, flex, mark, mono, spacer, stack, wrap
from paper_studies import PAPER, button, field, line_up, note, text


def _load_copy():
    script = (
        f"const m = await import({json.dumps(os.path.join(COMMON, 'onboarding.mjs'))});"
        "const f = (k, h) => m.pairingFailure(k, h);"
        "process.stdout.write(JSON.stringify({sources: m.LINK_SOURCES, install: m.INSTALL_COMMANDS, start: m.START_COMMAND,"
        "steps: m.PAIRING_STEPS.map((s) => m.pairingStepLabel(s, 'casa')), member: m.memberEmptyCopy('this phone'),"
        "admin: m.pairedRoleLine('admin'), shared: m.pairedRoleLine('member', 2),"
        "unreachable: f('unreachable', 'casa'), used: f('link-used', 'casa')}));"
    )
    out = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


COPY = _load_copy()
READ, REACH, SIGN = COPY["steps"]
SKETCH_ZOOM = 1.35
PHONE_ZOOM = 390 / 168


def say(value, p=VIEW, size=11.5):
    return wrap(value, size, p["ink3"], lh=1.5)


def code(value, p, size=10):
    return f'<code style="font-family: {MONO}; font-size: {size}px; color: {p["ink"]}; background: {p["hover"]}; padding: 0 3px; border-radius: 2px">{value}</code>'


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


def ladder(p, steps, size=9.5):
    rows = ""
    for state, label in steps:
        glyph = {"done": ic("check", 10, p["ink"]), "fail": ic("x", 10, p["danger"]),
                 "now": f'<span style="width: 8px; height: 8px; border-radius: 999px; box-shadow: inset 0 0 0 1.5px {p["ink2"]}; display: inline-block"></span>',
                 "todo": dot(p["ink4"], 5)}[state]
        colour = {"done": p["ink"], "fail": p["danger"], "now": p["ink"], "todo": p["ink3"]}[state]
        rows += flex(f'<span style="width: 12px; display: inline-flex; justify-content: center; flex-shrink: 0">{glyph}</span>', text(label, size, colour, 500 if state != "todo" else 400), gap=6)
    return f'<div style="display: flex; flex-direction: column; gap: 5px">{rows}</div>'


def pairing_ladder(p, states, size=9.5):
    return ladder(p, list(zip(states, (READ, REACH, SIGN))), size)


def failure_note(p, failure, size=10):
    return stack(text(failure["title"], size, p["ink"], 600, "white-space: normal"), wrap(failure["hint"], size - 1, p["ink2"], lh=1.45), gap=2)


def command(p, value, size=9.5):
    return flex(f'<span style="font-family: {MONO}; font-size: {size}px; color: {p["ink"]}; flex: 1; white-space: nowrap">{value}</span>', ic("copy", 10, p["ink3"]), gap=6,
                extra=f"padding: 5px 7px; border-radius: 4px; background: {p['hover']}")


def welcome(p, title, sub, inner):
    head = stack(black_alpaca(30, p["ink"]), text(title, 14, p["ink"], 600, "margin-top: 6px"), wrap(sub, 9.5, p["ink3"], lh=1.45) if sub else "", gap=2)
    return f'<div style="flex: 1; min-height: 0; display: flex; flex-direction: column; gap: 10px; padding: 14px 18px">{head}{inner}</div>'


def hint_card(p):
    body = stack(text("This is alpi on this computer", 10.5, p["ink"], 600), wrap("To use it from a phone: Settings → Connections → New connection, then scan the code.", 9.5, p["ink2"], lh=1.45), gap=2, extra="flex: 1")
    return flex(body, button("Got it", "secondary", p, PAPER, 22), gap=10, align="flex-start",
                extra=f"margin: 10px 12px; padding: 8px 10px; border-radius: 4px; background: {p['hover']}")


def d_running(p=VIEW):
    main = hint_card(p) + chat_head(p) + f'<div style="flex: 1; display: flex; align-items: center; justify-content: center">{say("A session starts with your first message.", p, 10)}</div>' + composer(p)
    return window(p, sidebar(p, "online", ROSTER), main)


def d_stopped(p=VIEW):
    actions = line_up(button("Start alpi", "primary", p, PAPER, 26), button("Connect to another computer", "ghost", p, PAPER, 26), gap=6, wrap=False)
    main = welcome(p, "alpi is installed but not running", "Start it here, or connect to an alpi that runs somewhere else.", actions)
    return window(p, sidebar(p, "offline"), main, h=170)


def d_starting(p=VIEW):
    main = welcome(p, "Starting alpi…", "", ladder(p, [("done", "Start requested"), ("now", "Waiting for alpi to answer")]))
    return window(p, sidebar(p, "offline"), main, h=170)


def d_failed(p=VIEW):
    error = (f'<pre style="margin: 0; padding: 6px 8px; border-radius: 4px; background: color-mix(in srgb, {p["danger"]} 8%, transparent); font-family: {MONO}; '
             f'font-size: 8.5px; line-height: 1.45; color: {p["danger"]}; white-space: pre-wrap">alpi did not answer within 45 seconds\n~/.alpi/logs/service.log:\nERROR config.yaml: line 12 · bad indentation</pre>')
    inner = (error + wrap("Start it from a terminal to see what it says:", 9.5, p["ink3"]) + command(p, COPY["start"])
             + line_up(button("Retry", "secondary", p, PAPER, 24), button("Connect to another computer", "ghost", p, PAPER, 24), gap=6, wrap=False))
    return window(p, sidebar(p, "offline"), welcome(p, "alpi didn't start", "", inner), h=266)


def choice(p, title, sub, inner):
    return (f'<div style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 7px; padding: 10px; border-radius: 4px; background: {p["side"]}; box-shadow: 0 0 0 1px {p["line"]}">'
            f'{text(title, 11, p["ink"], 600)}{wrap(sub, 9, p["ink3"], lh=1.4)}{inner}</div>')


def connect_form(p, link="", ladder_states=None, failure=None, action="Connect"):
    value = field(link or "alpi://device?url=…", p, PAPER)
    sources = wrap(" ".join(COPY["sources"]), 8.5, p["ink3"], lh=1.45)
    progress = pairing_ladder(p, ladder_states, 9) if ladder_states else ""
    told = failure_note(p, failure, 9.5) if failure else ""
    return value + sources + progress + told + f'<div style="margin-top: auto">{button(action, "primary", p, PAPER, 24)}</div>'


def d_absent(p=VIEW, form=None, h=300):
    here = choice(p, "Run alpi here", "Install it, then pick a model in setup. This window notices when it starts.",
                  "".join(command(p, c) for c in COPY["install"]) + f'<div style="margin-top: auto">{button("Check again", "secondary", p, PAPER, 24)}</div>')
    away = choice(p, "Connect to alpi elsewhere", "Paste the link made on the computer that runs it.", form or connect_form(p))
    main = welcome(p, "Set up alpi", "No alpi on this computer yet. Both paths end in the same window.", f'<div style="flex: 1; display: flex; gap: 8px; min-height: 0">{here}{away}</div>')
    return window(p, sidebar(p, "offline"), main, h=h)


def d_unreachable(p=VIEW):
    form = connect_form(p, "alpi://device?…&amp;name=casa", ("done", "fail", "todo"), COPY["unreachable"], COPY["unreachable"]["action"])
    return d_absent(p, form, h=380)


def sketch(title, body, drawing):
    return (f'<div style="display: flex; gap: 24px; align-items: flex-start"><div style="width: 300px; flex-shrink: 0">{note(title, body)}</div>'
            f'<div style="zoom: {SKETCH_ZOOM}; width: 640px">{drawing}</div></div>')


DESKTOP_ONBOARDING = (
    ("alpi runs here", "The window lands on the roster, alpi first. The connection reads This computer; a one-time card says how to add a phone and stays dismissed on this machine.", d_running),
    ("Installed, not running", "Detected from the alpi binary or its launchd / systemd unit. The first detection starts it once on its own; after that Start alpi kicks the unit, or runs alpi daemon start on its own when there is none.", d_stopped),
    ("Starting", "Shown until host.sock answers, up to 45 seconds; the welcome gives way to the roster on its own. Once alpi has answered in a session, a later outage keeps the open view under the reconnecting banner, whose Retry starts it again.", d_starting),
    ("Didn't start", "The tail of the launcher's error and of ~/.alpi/logs/service.log, the command that shows the rest, Retry, and the way out to another computer.", d_failed),
    ("No alpi on this computer", "Two paths, never a dead end: the install commands with copy, re-checked when the window gains focus, or a pasted alpi:// link. Where alpi cannot run, only the second card shows.", d_absent),
    ("Connecting elsewhere", "The link is read, the host reached and the device signed in, each step named. A failure names its cause and next step; a used or expired link is cleared, any other keeps it. The connection switcher's foot uses the same form.", d_unreachable),
)
DESKTOP_ONBOARDING_H = 2400


def desktop_onboarding():
    head = ('<div style="display: flex; flex-direction: column; gap: 6px"><span style="font-size: 22px; font-weight: 600; letter-spacing: -0.018em; line-height: 1.3">First run</span>'
            f'<span style="font-size: 13px; color: {VIEW["ink3"]}; max-width: 720px; line-height: 1.5">Before drawing the shell the app asks the machine for its own alpi: running, stopped, absent or unsupported. '
            'Until alpi answers for the first time, anything but running replaces the main pane with one welcome; then the window is the app.</span></div>')
    rows = "".join(sketch(t, b, fn()) for t, b, fn in DESKTOP_ONBOARDING)
    body = f'<div style="padding: 40px; display: flex; flex-direction: column; gap: 36px; box-sizing: border-box">{head}{rows}</div>'
    return page("Desktop · first run", 1280, DESKTOP_ONBOARDING_H, body)


def phone(p, *parts, pad="8px 12px 14px", gap=8):
    bar = f'<div style="display: flex; padding: 7px 14px 2px">{mono("9:41", 8.5, p["ink"], 600)}</div>'
    return (f'<div style="width: 168px; height: 364px; box-sizing: border-box; overflow: hidden; background: {p["bg"]}; display: flex; flex-direction: column">{bar}'
            f'<div style="flex: 1; min-height: 0; display: flex; flex-direction: column; gap: {gap}px; padding: {pad}">{"".join(parts)}</div></div>')


def pbtn(p, label, kind="primary", h=30, icon=""):
    bg, fg = {"primary": (p["ink"], p["pane"]), "secondary": (p["selected"], p["ink"]), "ghost": ("transparent", p["ink2"])}[kind]
    glyph = ic(icon, 11, fg) if icon else ""
    return (f'<span style="display: flex; align-items: center; justify-content: center; gap: 5px; height: {h}px; border-radius: 4px; background: {bg}; color: {fg}; '
            f'font-size: 10.5px; font-weight: 500; white-space: nowrap; flex-shrink: 0">{glyph}{label}</span>')


def center(*items, gap=8):
    return f'<div style="flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; gap: {gap}px">{"".join(items)}</div>'


def ptitle(value, p, size=17):
    return text(value, size, p["ink"], 600, "letter-spacing: -0.01em; white-space: normal")


def pbody(value, p, size=10):
    return wrap(value, size, p["ink2"], lh=1.45)


def p_head(p, title, sub=""):
    return flex(ic("back", 13, p["ink"]), stack(text(title, 12, p["ink"], 600), mono(sub, 8, p["ink3"]) if sub else "", gap=1), gap=6, extra="padding: 2px 0 4px")


def well(p, value, filled=False):
    return (f'<div style="min-height: 34px; box-sizing: border-box; padding: 5px 7px; border-radius: 4px; background: {p["hover"]}; font-family: {MONO}; font-size: 8px; '
            f'line-height: 1.4; color: {p["ink"] if filled else p["ink4"]}; word-break: break-all">{value}</div>')


def where_link(p):
    rows = text("Where do I get a link?", 9.5, p["ink"], 600) + "".join(wrap(s, 8.5, p["ink2"], lh=1.45) for s in COPY["sources"])
    return f'<div style="display: flex; flex-direction: column; gap: 3px; padding: 7px 8px; border-radius: 4px; background: {p["hover"]}; text-align: left">{rows}</div>'


def m_welcome(p=VIEW):
    return phone(p, center(black_alpaca(46, p["ink"]), ptitle("Pair with your alpi", p), pbody("alpi runs on a computer or a server. Pair this phone once and its profiles come with you.", p, 9.5)),
                 where_link(p) + pbtn(p, "Scan QR", h=34, icon="qr") + pbtn(p, "Paste link", "ghost"))


LINK = "alpi://device?url=ws%3A%2F%2F100.99.29.84%3A49200&amp;name=casa&amp;pairing_token=…"


def m_pair(p, link, states, failure=None, action="Pair"):
    guide = wrap(f'Open your daemon’s settings, choose {code("Settings → Connections → New connection / Add device", p, 7.5)}, then scan the QR or paste the link below.', 8, p["ink2"], lh=1.4)
    box = (f'<div style="display: flex; flex-direction: column; gap: 6px; padding: 7px 8px; border-radius: 4px; background: {p["hover"]}">'
           f'{pairing_ladder(p, states, 8.5)}{failure_note(p, failure, 9.5) if failure else ""}</div>')
    return phone(p, p_head(p, "Pair this phone", "CONNECT TO YOUR DAEMON") + guide + pbtn(p, "Scan QR", h=24) + mono("OR PASTE LINK", 7.5, p["ink3"])
                 + well(p, link or "alpi://device?url=wss://…&amp;name=…&amp;pairing_token=…", bool(link)) + box
                 + f'<div style="margin-top: auto">{pbtn(p, action, h=28)}</div>', pad="4px 10px 12px", gap=6)


def m_connecting(p=VIEW):
    return m_pair(p, LINK, ("done", "done", "now"), action="Pairing…")


def m_unreachable(p=VIEW):
    failure = COPY["unreachable"]
    return m_pair(p, LINK, ("done", "fail", "todo"), failure, failure["action"])


def m_link_used(p=VIEW):
    failure = COPY["used"]
    return m_pair(p, "", ("done", "done", "fail"), failure, failure["action"])


def m_paired(p=VIEW):
    return phone(p, center(black_alpaca(40, p["ink"]), ptitle("Paired with casa", p), mono(COPY["admin"], 8.5, p["ink3"]),
                           pbody("Your daemon is reachable and your profiles are available.", p, 9.5)),
                 pbtn(p, "Open inbox", h=34))


def footer_bar(p):
    return flex(ic("gear", 12, p["ink2"]), spacer(), ic("bell", 12, p["ink2"]), ic("activity", 12, p["ink2"]), gap=12, extra=f"margin-top: auto; padding-top: 8px; box-shadow: inset 0 0.5px 0 {p['line']}")


def m_member_empty(p=VIEW):
    head = flex(stack(flex(text("mirai", 12, p["ink"], 600), status_dot(p, "online", 5), gap=5), mono("wss://alpi.mirai.example", 8, p["ink3"]), gap=1), spacer(), ic("search", 12, p["ink2"]), gap=6, extra="padding: 2px 0 6px")
    copy = COPY["member"]
    empty = center(text(copy["title"], 11.5, p["ink"], 600, "white-space: normal"), pbody(copy["hint"], p, 9), gap=6)
    return phone(p, head + empty + footer_bar(p))


def phone_screen(title, drawing):
    return page(title, 390, 844, f'<div style="zoom: {PHONE_ZOOM}">{drawing}</div>')


def phone_onboarding():
    return {
        "welcome": phone_screen("Phone · pair with your alpi", m_welcome()),
        "connecting": phone_screen("Phone · pairing", m_connecting()),
        "paired": phone_screen("Phone · paired", m_paired()),
        "unreachable": phone_screen("Phone · host unreachable", m_unreachable()),
        "used": phone_screen("Phone · link used", m_link_used()),
        "member": phone_screen("Phone · nothing shared", m_member_empty()),
    }
