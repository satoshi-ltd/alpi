import json
import os
import subprocess

from brand_boards import black_alpaca
from desktop_boards import MONO
from gen import COMMON, ic, mi, page
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


def stacked(p, primary, primary_label, ghost_label, kind="primary"):
    ghost = f'<span style="margin-left: -12px; display: inline-flex">{button(ghost_label, "ghost", p, PAPER, 30)}</span>'
    return f'<div style="display: flex; flex-direction: column; align-items: flex-start; gap: 6px">{button(primary_label, kind, p, PAPER, 30)}{ghost}</div>'


def d_running(p=VIEW):
    main = hint_card(p) + chat_head(p) + f'<div style="flex: 1; display: flex; align-items: center; justify-content: center">{say("A session starts with your first message.", p, 10)}</div>' + composer(p)
    return window(p, sidebar(p, "online", ROSTER), main)


def d_stopped(p=VIEW):
    actions = stacked(p, None, "Start alpi", "Connect to another computer")
    main = welcome(p, "alpi is installed but not running", "Start it here, or connect to an alpi that runs somewhere else.", actions)
    return window(p, sidebar(p, "offline"), main, h=200)


def d_starting(p=VIEW):
    main = welcome(p, "Starting alpi…", "", ladder(p, [("done", "Start requested"), ("now", "Waiting for alpi to answer")]))
    return window(p, sidebar(p, "offline"), main, h=170)


def d_installing(p=VIEW):
    main = welcome(p, "Installing alpi…", "Downloading uv, Python and alpi. This can take a few minutes. Keep this window open.",
                   ladder(p, [("now", "Installing alpi and its runtime"), ("todo", "Start alpi")]))
    return window(p, sidebar(p, "offline"), main, h=210)


def d_install_failed(p=VIEW):
    inner = wrap("Could not download uv. Check your internet connection and try again.", 9.5, p["danger"])
    inner += stacked(p, None, "Retry", "Connect to another computer", "secondary")
    return window(p, sidebar(p, "offline"), welcome(p, "alpi couldn't be installed", "", inner), h=230)


def d_failed(p=VIEW):
    error = (f'<pre style="margin: 0; padding: 6px 8px; border-radius: 4px; background: {p["hover"]}; font-family: {MONO}; '
             f'font-size: 8.5px; line-height: 1.45; color: {p["danger"]}; white-space: pre-wrap">alpi did not answer within 45 seconds\n~/.alpi/logs/service.log:\nERROR config.yaml: line 12 · bad indentation</pre>')
    inner = (error + wrap("Start it from a terminal to see what it says:", 9.5, p["ink3"]) + command(p, COPY["start"])
             + stacked(p, None, "Retry", "Connect to another computer", "secondary"))
    return window(p, sidebar(p, "offline"), welcome(p, "alpi didn't start", "", inner), h=300)


def choice(p, title, sub, inner):
    return (f'<div style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 6px; padding: 12px; border-radius: 4px; background: var(--card); box-shadow: 0 0 0 0.5px {p["line"]}">'
            f'{text(title, 11, p["ink"], 600)}{wrap(sub, 9, p["ink3"], lh=1.4)}{inner}</div>')


def connect_form(p, link="", ladder_states=None, failure=None, action="Connect"):
    value = field(link or "alpi://device?url=…", p, PAPER)
    sources = wrap(" ".join(COPY["sources"]), 8.5, p["ink3"], lh=1.45)
    progress = pairing_ladder(p, ladder_states, 9) if ladder_states else ""
    told = failure_note(p, failure, 9.5) if failure else ""
    return value + sources + progress + told + f'<div style="margin-top: auto">{button(action, "primary", p, PAPER, 24)}</div>'


def d_absent(p=VIEW, form=None, h=300):
    here = choice(p, "Run alpi here", "Install alpi and its runtime here, then choose a model in Settings. Requires an internet connection.",
                  f'<div style="margin-top: auto">{stacked(p, None, "Install and start alpi", "Check again")}</div>')
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
    ("No alpi on this computer", "Two paths, never a dead end: Install and start alpi downloads uv, Python and alpi, then starts the daemon. Installation shows progress and a retry on failure. Check again re-detects installation, also when the window gains focus, or a pasted alpi:// link. Where alpi cannot run, only the second card shows.", d_absent),
    ("Installing", "Install and start alpi installs the runtime and alpi before requesting a start. Keep the window open while downloads finish.", d_installing),
    ("Installation failed", "Installation errors keep Retry on the installation step; a start failure retries only the start.", d_install_failed),
    ("Connecting elsewhere", "The link is read, the host reached and the device signed in, each step named. A failure names its cause and next step; a used or expired link is cleared, any other keeps it. The connection switcher's foot uses the same form.", d_unreachable),
)
DESKTOP_ONBOARDING_H = 3190


def desktop_onboarding():
    head = ('<div style="display: flex; flex-direction: column; gap: 6px"><span style="font-size: 22px; font-weight: 600; letter-spacing: -0.018em; line-height: 1.3">First run</span>'
            f'<span style="font-size: 13px; color: {VIEW["ink3"]}; max-width: 720px; line-height: 1.5">Before drawing the shell the app asks the machine for its own alpi: running, stopped, absent or unsupported. '
            'Until alpi answers for the first time, anything but running replaces the main pane with one welcome; then the window is the app.</span></div>')
    rows = "".join(sketch(t, b, fn()) for t, b, fn in DESKTOP_ONBOARDING)
    body = f'<div style="padding: 40px; display: flex; flex-direction: column; gap: 36px; box-sizing: border-box">{head}{rows}</div>'
    return page("Desktop · first run", 1280, DESKTOP_ONBOARDING_H, body)


LINK = "alpi://device?url=ws%3A%2F%2F100.99.29.84%3A49200&amp;name=casa&amp;pairing_token=…"


INK, INK2, INK3, INK4 = "#141414", "#454545", "#6b6b6b", "#b4b4b4"
DANGER_INK = "#b73737"
HOVER = "rgba(20,20,20,0.04)"
FILL = "width: 100%; box-sizing: border-box"


def full(html):
    return html.replace("border-radius: 4px", f"border-radius: 4px; {FILL}", 1)


def mono_run(value):
    return f'<span style="font-family: {MONO}; color: {INK}">{value}</span>'


def welcome_screen():
    from gen import m_button, m_eyebrow
    sources = "".join(f'<span style="font-size: 12px; line-height: 1.65; color: {INK2}">{line}</span>' for line in COPY["sources"])
    card = (f'<div style="display: flex; flex-direction: column; gap: 6px; padding: 14px; border-radius: 4px; background: {HOVER}">'
            f'<span style="font-weight: 600; font-size: 14px; color: {INK}">Where do I get a link?</span>{sources}</div>')
    top = (f'<div style="flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 24px; text-align: center">{black_alpaca(88, INK)}'
           f'<span style="font-weight: 600; font-size: 28px; letter-spacing: -0.018em; color: {INK}">Pair with your alpi</span>'
           f'<span style="max-width: 320px; font-size: 15px; line-height: 1.65; color: {INK2}">alpi runs on a computer or a server. Pair this phone once and its profiles come with you.</span></div>')
    bottom = f'<div style="display: flex; flex-direction: column; gap: 24px">{card}<div style="display: flex; flex-direction: column; gap: 10px">{full(m_button("Scan QR", "primary", "hero"))}{full(m_button("Paste link", "ghost", "lg"))}</div></div>'
    return f'<div style="height: 100%; box-sizing: border-box; display: flex; flex-direction: column; padding: 24px">{top}{bottom}</div>'


def ladder_rows(states):
    rows = ""
    for state, label in zip(states, (READ, REACH, SIGN)):
        glyph = {"done": mi("check", 14, INK), "fail": mi("x", 14, "#c14545"),
                 "now": f'<span style="width: 6px; height: 6px; border-radius: 4px; background: {INK2}"></span>',
                 "todo": f'<span style="width: 6px; height: 6px; border-radius: 4px; background: {INK4}"></span>'}[state]
        colour = DANGER_INK if state == "fail" else INK3 if state == "todo" else INK
        rows += (f'<div style="display: flex; align-items: center; gap: 8px"><span style="width: 16px; display: inline-flex; justify-content: center">{glyph}</span>'
                 f'<span style="flex: 1; font-size: 14px; font-weight: {400 if state == "todo" else 500}; color: {colour}">{label}</span></div>')
    return f'<div style="display: flex; flex-direction: column; gap: 8px">{rows}</div>'


def pair_screen(link, states, failure=None, action="Pair"):
    from gen import m_button, m_eyebrow
    head = (f'<div style="display: flex; align-items: center; gap: 12px; padding: 16px">{mi("back", 16, INK)}<div style="flex: 1; display: flex; flex-direction: column">'
            f'<span style="font-weight: 600; font-size: 18px; color: {INK}">Pair this phone</span>{m_eyebrow("Connect to your daemon", INK3, 500, 0.06, 11, "margin-top: 4px")}</div></div>')
    intro = (f'<span style="font-size: 14px; line-height: 1.5; color: {INK2}">Open your daemon’s settings, choose {mono_run("Settings → Connections → New connection / Add device")}, '
             f'then either scan the QR or paste the {mono_run("alpi://")} link below.</span>')
    shown = link or "alpi://device?url=wss://…&amp;name=…&amp;pairing_token=…"
    well = (f'<div style="min-height: 64px; box-sizing: border-box; padding: 12px; border-radius: 4px; border: 2px solid transparent; background: var(--field); font-family: {MONO}; '
            f'font-size: 12px; line-height: 1.3; color: {INK if link else INK4}; word-break: break-all">{shown}</div>')
    paste = (f'<div style="display: flex; flex-direction: column; gap: 8px">{m_eyebrow("or paste link", INK3)}{well}'
             f'<span style="align-self: flex-end; font-weight: 500; font-size: 14px; color: {INK2}">Paste from clipboard</span></div>')
    told = ""
    if failure:
        told = (f'<div style="display: flex; flex-direction: column; gap: 6px"><span style="font-weight: 600; font-size: 15px; color: {INK}">{failure["title"]}</span>'
                f'<span style="font-size: 14px; line-height: 1.5; color: {INK2}">{failure["hint"]}</span></div>')
    box = f'<div style="display: flex; flex-direction: column; gap: 12px; padding: 14px; border-radius: 4px; background: {HOVER}">{ladder_rows(states)}{told}</div>'
    body = (f'<div style="display: flex; flex-direction: column; gap: 24px; padding: 16px">{intro}{full(m_button("Scan QR", "primary", "lg"))}{paste}{box}'
            f'{full(m_button(action, "primary", "lg"))}</div>')
    return f'<div style="display: flex; flex-direction: column; height: 100%">{head}{body}</div>'


def paired_screen():
    from gen import m_button
    top = (f'<div style="flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 24px; text-align: center">{black_alpaca(88, INK)}'
           f'<span style="font-weight: 600; font-size: 28px; letter-spacing: -0.018em; color: {INK}">Paired with casa</span>'
           f'<span style="font-family: {MONO}; font-size: 12px; color: {INK3}">{COPY["admin"]}</span>'
           f'<span style="max-width: 320px; font-size: 15px; line-height: 1.65; color: {INK2}">Your daemon is reachable and your profiles are available.</span></div>')
    return f'<div style="height: 100%; box-sizing: border-box; display: flex; flex-direction: column; padding: 24px">{top}{full(m_button("Open inbox", "primary", "hero"))}</div>'


def member_screen():
    from gen import m_conn_header, m_empty_state, m_shell_footer
    copy = COPY["member"]
    return (f'<div style="display: flex; flex-direction: column; height: 100%; background: #ffffff">{m_conn_header(ring="#ffffff", collapse=False, bg="#ffffff")}'
            f'<div style="height: 0.5px; background: rgba(20,20,20,0.07)"></div>'
            f'<div style="flex: 1; min-height: 0; display: flex; flex-direction: column">{m_empty_state(copy["title"], copy["hint"])}</div>'
            f'{m_shell_footer(ring="#ffffff", border=True)}</div>')


def phone_screen(title, drawing, bg="#ffffff"):
    return page(title, 390, 844, drawing, bg=bg)


def phone_onboarding():
    unreachable, used = COPY["unreachable"], COPY["used"]
    return {
        "welcome": phone_screen("Phone · pair with your alpi", welcome_screen()),
        "connecting": phone_screen("Phone · pairing", pair_screen(LINK, ("done", "done", "now"), action="Pairing…")),
        "paired": phone_screen("Phone · paired", paired_screen()),
        "unreachable": phone_screen("Phone · host unreachable", pair_screen(LINK, ("done", "fail", "todo"), unreachable, unreachable["action"])),
        "used": phone_screen("Phone · link used", pair_screen("", ("done", "done", "fail"), used, used["action"])),
        "member": phone_screen("Phone · nothing shared", member_screen()),
    }
