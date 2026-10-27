import json
import os
import subprocess

from brand_boards import black_alpaca
from desktop_boards import HOVER, INK, INK2, INK3, INK4, LINE, LINE2, MONO, PANE, SELECTED, SIDE
from gen import COMMON, DOC_ACCENT, di, m_button, m_conn_header, m_eyebrow, m_row, m_shell_footer, mi, pill, switch
from loading_studies import alpaca as busy_alpaca


def _load_copy():
    script = (
        f"const m = await import({json.dumps(os.path.join(COMMON, 'onboarding.mjs'))});"
        f"const f = await import({json.dumps(os.path.join(COMMON, 'folds.mjs'))});"
        f"const e = await import({json.dumps(os.path.join(COMMON, 'emptyCopy.mjs'))});"
        "const pts = f.foldFacets(f.ALPACA_FOLD).flatMap((x) => x.points);"
        "const g = (k, h) => m.pairingFailure(k, h);"
        "process.stdout.write(JSON.stringify({rows: m.LINK_SOURCE_ROWS, start: m.START_COMMAND,"
        "steps: m.PAIRING_STEPS.map((s) => m.pairingStepLabel(s, 'casa')), member: m.memberEmptyCopy('this phone'),"
        "admin: m.pairedRoleLine('admin'), roster: e.EMPTY.roster,"
        "ink: {left: Math.min(...pts.map((p) => p[0])), top: Math.min(...pts.map((p) => p[1]))},"
        "unreachable: g('unreachable', 'casa'), used: g('link-used', 'casa')}));"
    )
    out = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


COPY = _load_copy()
DANGER_TEXT = "#b73737"
Z_FOLD = 0.6


def t(value, size=13, color=INK, weight=400, extra=""):
    return f'<span style="font-size: {size}px; line-height: 1.3; font-weight: {weight}; color: {color}; {extra}">{value}</span>'


def mono(value, size=11, color=INK3, extra=""):
    return f'<span style="font-family: {MONO}; font-size: {size}px; line-height: 1.3; color: {color}; {extra}">{value}</span>'


def col(*items, gap=8, align="stretch", extra=""):
    return f'<div style="display: flex; flex-direction: column; gap: {gap}px; align-items: {align}; {extra}">{"".join(items)}</div>'


def line(*items, gap=8, align="center", extra=""):
    return f'<div style="display: flex; align-items: {align}; gap: {gap}px; {extra}">{"".join(items)}</div>'


def alp(size):
    return black_alpaca(size, INK)


def scaled(inner, w, h, z):
    return (f'<div style="width: {round(w * z)}px; height: {round(h * z)}px; overflow: hidden; flex-shrink: 0; border-radius: 4px; box-shadow: 0 0 0 1px {LINE2}">'
            f'<div style="width: {w}px; height: {h}px; zoom: {z}; box-sizing: border-box; overflow: hidden; background: {PANE}; position: relative">{inner}</div></div>')


def dbtn(label, kind="primary", h=40, w=None, flush=False):
    bg, fg, fw = {"primary": (INK, PANE, 600), "secondary": (SELECTED, INK, 500), "ghost": ("transparent", INK2, 500)}[kind]
    pad = 24 if h >= 48 else 16 if h >= 40 else 12
    width = f"width: {w}px;" if w else f"padding: 0 {pad}px;"
    margin = f"margin-left: -{pad}px;" if flush else ""
    return (f'<span style="display: inline-flex; align-items: center; justify-content: center; height: {h}px; {width} {margin} box-sizing: border-box; border-radius: 4px; '
            f'background: {bg}; color: {fg}; font-size: 13px; font-weight: {fw}; line-height: 1; white-space: nowrap; flex-shrink: 0">{label}</span>')


def dfield(value, w=360, h=40, placeholder=True, focus=False):
    ring = f"box-shadow: inset 0 0 0 1px {'#8c8c8c' if focus else LINE2};"
    return (f'<span style="display: inline-flex; align-items: center; width: {w}px; height: {h}px; padding: 0 12px; box-sizing: border-box; border-radius: 4px; background: var(--bg-elev, #ffffff); {ring} '
            f'font-family: {MONO}; font-size: 13px; color: {INK3 if placeholder else INK}; white-space: nowrap; overflow: hidden">{value}</span>')


def sidebar_chip(state, extra="", w=192):
    dot = {"online": INK, "offline": DANGER_TEXT, "stopped": INK4}[state]
    status_dot = f'<span style="width: 8px; height: 8px; border-radius: 999px; background: {dot}"></span>'
    return (f'<div style="width: {w}px; flex-shrink: 0; background: {SIDE}; box-shadow: inset -0.5px 0 0 {LINE}; display: flex; flex-direction: column; padding: 12px; gap: 8px; box-sizing: border-box">'
            f'{mono("Connection", 11, INK3, "letter-spacing: 0.08em; text-transform: uppercase")}'
            f'{line(di("chip", 16, INK2), col(t("This computer", 13, INK, 500), mono("host.sock", 11, INK3), gap=0, extra="flex: 1"), status_dot, gap=8, extra=f"padding: 8px; border-radius: 4px; background: {PANE}; box-shadow: 0 0 0 0.5px {LINE2}")}'
            f'{extra}</div>')


U_W, U_H, U_Z = 960, 600, 0.75
U_SHORT = 440
C_MARK = 72
C_COL = 520
C_BTN_W = 176
C_STRIP = 38
C_EDGE = 64
C_TOP = 32
C_LOG_LINES = 12
INK_LEFT = COPY["ink"]["left"]
INK_TOP = COPY["ink"]["top"]
C_INSET = round(INK_LEFT * C_MARK / 100, 2)
C_INK_TOP = round(INK_TOP * C_MARK / 100, 2)
BUSY_PX = 77
GHOST = "Connect to another computer"
CONNECT_SUB = "Paste the link made on the computer that runs it."


def ct(value, size=13, lh=20, color=INK, weight=400, extra=""):
    return f'<div style="font-size: {size}px; line-height: {lh}px; font-weight: {weight}; color: {color}; {extra}">{value}</div>'


def cm(value, size=13, lh=20, color=INK, extra=""):
    return f'<div style="font-family: {MONO}; font-size: {size}px; line-height: {lh}px; color: {color}; {extra}">{value}</div>'


def c_win(inner, side="", w=U_W, h=U_H, z=U_Z):
    dots = "".join(f'<span style="width: 12px; height: 12px; border-radius: 999px; background: {INK4}"></span>' for _ in range(3))
    traffic = f'<div style="position: absolute; left: 18px; top: 22px; display: flex; gap: 8px; z-index: 1">{dots}</div>'
    main = (f'<div style="flex: 1; min-width: 0; display: flex; flex-direction: column"><div style="height: {C_STRIP}px; flex-shrink: 0"></div>'
            f'<div style="flex: 1; min-height: 0; overflow: hidden; padding: {C_TOP}px {C_EDGE}px; box-sizing: border-box">{inner}</div></div>')
    return scaled(f'<div style="display: flex; height: 100%; position: relative">{traffic}{side}{main}</div>', w, h, z)


def c_side():
    return f'<div style="display: flex; padding-top: {C_STRIP - 12}px; background: {SIDE}; flex-shrink: 0">{sidebar_chip("offline")}</div>'


def c_page(*parts):
    rows = "".join(f'<div style="margin-top: {gap}px; width: 100%">{html}</div>' for gap, html in parts)
    return f'<div style="width: {C_COL}px; max-width: 100%; display: flex; flex-direction: column; align-items: flex-start; text-align: left">{rows}</div>'


def c_mark(busy=None):
    inner = busy_alpaca(C_MARK, busy, fill=INK) if busy else alp(C_MARK)
    return f'<div style="width: {C_MARK}px; height: {C_MARK}px; margin: -{C_INK_TOP}px 0 -{C_INK_TOP}px -{C_INSET}px; flex-shrink: 0">{inner}</div>'


def c_head(title, sub=None, busy=None):
    parts = [(0, c_mark(busy)), (24, ct(title, 28, 36, INK, 600, "letter-spacing: -0.020em"))]
    return parts + ([(8, ct(sub, 13, 20, INK3))] if sub else [])


def c_ring(html):
    return f'<span style="display: inline-flex; border-radius: 4px; flex-shrink: 0; box-shadow: 0 0 0 2px {PANE}, 0 0 0 4px {INK2}">{html}</span>'


def c_actions(primary, *ghosts, focus=True, dim=False):
    main = dbtn(primary, "primary", 40, C_BTN_W)
    main = f'<span style="display: inline-flex; opacity: 0.45">{main}</span>' if dim else main
    main = c_ring(main) if focus else main
    return line(main, *[dbtn(g, "ghost", 40) for g in ghosts], gap=8, extra="flex-wrap: wrap")


def c_command(value):
    copy = f'<span style="width: 28px; height: 28px; display: inline-flex; align-items: center; justify-content: center">{di("copy", 16, INK2)}</span>'
    return line(cm(value, 13, 20, INK), copy, gap=4, extra="height: 28px")


def c_log(text):
    rows = "".join(f'<div style="min-height: 16px; flex-shrink: 0">{row}</div>' for row in text.split("\n"))
    return (f'<div style="max-height: {C_LOG_LINES * 16}px; overflow: hidden; display: flex; flex-direction: column; justify-content: flex-end; '
            f'font-family: {MONO}; font-size: 11px; line-height: 16px; color: {DANGER_TEXT}; white-space: pre-wrap; overflow-wrap: anywhere">{rows}</div>')


def c_ladder(*steps):
    rows = []
    for state, label in steps:
        glyph = {
            "done": di("check", 14, INK),
            "fail": di("x", 14, DANGER_TEXT),
            "now": f'<span style="width: 6px; height: 6px; border-radius: 4px; box-shadow: inset 0 0 0 1.5px {INK2}"></span>',
            "todo": f'<span style="width: 6px; height: 6px; border-radius: 4px; background: {INK4}"></span>',
        }[state]
        color = {"todo": INK3, "fail": DANGER_TEXT}.get(state, INK)
        mark = f'<span style="width: 14px; flex-shrink: 0; display: inline-flex; align-items: center; justify-content: flex-start">{glyph}</span>'
        rows.append(line(mark, t(label, 13, color, 400, "line-height: 20px"), gap=8, extra="height: 20px"))
    return col(*rows, gap=4)


def c_sources():
    return col(*[col(ct(r["label"], 11, 16, INK3), cm(r["path"], 13, 20, INK2), gap=0) for r in COPY["rows"]], gap=8)


def c_failure(failure):
    return col(ct(failure["title"], 13, 20, DANGER_TEXT, 600), ct(failure["hint"], 11, 16, INK2), gap=0)


def c_connect(sub, link="", steps=None, failure=None, action="Connect", back=True):
    label = ct("alpi:// link", 11, 16, INK2, 500, "margin-bottom: 4px")
    field = dfield(link or "alpi://device?url=…", C_COL, 40, placeholder=not link, focus=not link and not steps)
    middle = c_ladder(*steps) if steps else c_sources()
    parts = c_head("Connect to alpi", sub) + [(24, label + field), (16, middle)]
    if failure:
        parts.append((16, c_failure(failure)))
    return c_page(*parts, (24, c_actions(action, *(["Back"] if back else []), focus=False, dim=not link or bool(steps) and not failure)))


C_LOG = "\n".join([
    "alpi did not answer within 45 seconds",
    "Traceback (most recent call last):",
    '  File "/Users/javier.fernandez/.local/share/uv/tools/alpi-agent/lib/python3.11/site-packages/alpi/cli.py", line 214, in main',
    "    daemon.run(load_config(home))",
    '  File "/Users/javier.fernandez/.local/share/uv/tools/alpi-agent/lib/python3.11/site-packages/alpi/config.py", line 88, in load_config',
    "    raw = yaml.safe_load(path.read_text())",
    "yaml.scanner.ScannerError: mapping values are not allowed here",
    '  in "/Users/javier.fernandez/.alpi/profiles/default/config.yaml", line 12, column 9',
    "alpi.errors.ConfigError: config.yaml: line 12 · bad indentation",
    "daemon exited with status 1",
    "/Users/javier.fernandez/.alpi/logs/service.log:",
    "2026-10-27 09:14:02 INFO  daemon starting pid=48211",
    "2026-10-27 09:14:02 ERROR config.yaml: line 12 · bad indentation",
])
C_INSTALL_ERROR = "Could not download uv. Check your internet connection and try again."
LINK = "alpi://device?url=…&amp;name=casa"


def desktop_states():
    r = COPY["unreachable"]
    s = COPY["steps"]
    absent = c_page(*c_head("Set up alpi", "alpi runs your agents on this computer. Installing it needs an internet connection."),
                    (24, c_actions("Install and start alpi", "Check again", GHOST)))
    return [
        ("No alpi on this computer",
         "One column on the left edge, no sidebar: the first launch on a machine where the local alpi has never answered. One primary holds first focus; Check again and the way out are ghosts.",
         c_win(absent, h=U_SHORT)),
        ("Installed, not running",
         "The first detection starts alpi once on its own; if it did not answer, Start alpi is the primary and the way out its ghost.",
         c_win(c_page(*c_head("alpi is installed but not running", "Start it here, or connect to an alpi that runs somewhere else."),
                      (24, c_actions("Start alpi", GHOST))), h=U_SHORT)),
        ("Installing",
         "The BusyMark stands where the Fold stood and is the only wait. No actions, so nothing to focus.",
         c_win(c_page(*c_head("Installing alpi…", "Downloading uv, Python and alpi. This can take a few minutes. Keep this window open.", busy="fr_a"),
                      (16, c_ladder(("now", "Installing alpi and its runtime"), ("todo", "Start alpi")))), h=U_SHORT)),
        ("Starting",
         "Shown until host.sock answers, up to 45 seconds, and for 15 seconds after a launch that returned so the window never flashes the offline banner.",
         c_win(c_page(*c_head("Starting alpi…", busy="fr_b"),
                      (16, c_ladder(("done", "Start requested"), ("now", "Waiting for alpi to answer")))), h=U_SHORT)),
        ("Didn't start, worst-case log",
         "The log is capped at 12 lines (192 px), scrolled to its tail, keyboard-focusable and wraps inside the column, so Retry stays in the window. Retry is the one primary.",
         c_win(c_page(*c_head("alpi didn't start"), (16, c_log(C_LOG)),
                      (16, ct("Start it from a terminal to see what it says:", 13, 20, INK3)), (8, c_command(COPY["start"])),
                      (24, c_actions("Retry", GHOST))))),
        ("Installation failed",
         "The same log block and the same Retry slot; no Command row, because installation has nothing to run by hand.",
         c_win(c_page(*c_head("alpi couldn't be installed"), (16, c_log(C_INSTALL_ERROR)), (24, c_actions("Retry", GHOST))), h=U_SHORT)),
        ("Connect to another computer",
         "alpi:// link label over a 40 px field, the sources as a two-row list, one action row: Connect (dim until a link is in) and Back. The field holds first focus.",
         c_win(c_connect(CONNECT_SUB))),
        ("Connecting",
         "The StepLadder replaces the sources; the field and the action row keep their place.",
         c_win(c_connect(CONNECT_SUB, LINK, [("done", s[0]), ("now", s[1]), ("todo", s[2])]))),
        ("Connection failed",
         "One failure line between ladder and actions; the retry takes the Connect slot at the same size and the link is kept unless it was used or expired.",
         c_win(c_connect(CONNECT_SUB, LINK, [("done", s[0]), ("fail", s[1]), ("todo", s[2])], r, r["action"]))),
        ("A system alpi cannot run on",
         "Only the form, under the sentence that says why; Connect alone, no Back.",
         c_win(c_connect("alpi does not run on this system yet, so connect to one that runs elsewhere.", back=False))),
        ("After the first run: beside the sidebar",
         "Once the local alpi has answered on this machine, or with a second saved connection, the Sidebar stays and the same Welcome fills the main pane. The full-window frame is only the true first run, and the shortcuts that need the shell are off while it shows.",
         c_win(absent, side=c_side(), h=U_SHORT)),
        ("Large window, 1440 x 900",
         "The column keeps its left margin and width; the empty space on the right is intentional.",
         c_win(absent, w=1440, h=900, z=0.5)),
    ]


Q_W, Q_H = 390, 844
Q_EDGE = 16
Q_FOLD_EDGE = 24
Q_SAFE_TOP = 48
Q_SAFE_BOTTOM = 34
Q_KEYBOARD = 336
Q_COL = 480
Q_HOST = "casa"
Q_URL = "ws://100.99.29.84:49200"
Q_LINK = "alpi://device?url=…&amp;name=casa"
Q_CAM = "#1c1c1c"
Q_WHITE = "#fffffe"
Q_STEPS = COPY["steps"]
Q_FOLD_W, Q_FOLD_H = 852, 884


def qt(value, size=14, lh=21, color=INK2, weight=400, extra=""):
    return f'<div style="font-size: {size}px; line-height: {lh}px; font-weight: {weight}; color: {color}; {extra}">{value}</div>'


def qm(value, size=12, lh=16, color=INK3, extra=""):
    return f'<div style="font-family: {MONO}; font-size: {size}px; line-height: {lh}px; color: {color}; overflow-wrap: anywhere; {extra}">{value}</div>'


def q_page(*parts):
    rows = "".join(f'<div style="margin-top: {gap}px; width: 100%">{html}</div>' for gap, html in parts)
    return f'<div style="width: 100%; display: flex; flex-direction: column; align-items: flex-start; text-align: left">{rows}</div>'


def q_mark(busy=None):
    if busy:
        top = round(INK_TOP * BUSY_PX / 100, 2)
        left = round(INK_LEFT * BUSY_PX / 100, 2)
        bottom = round(BUSY_PX - C_MARK - top, 2)
        return (f'<div style="width: {BUSY_PX}px; height: {BUSY_PX}px; margin: -{top}px 0 -{bottom}px -{left}px; flex-shrink: 0">'
                f'{busy_alpaca(BUSY_PX, busy, fill=INK)}</div>')
    return f'<div style="width: {C_MARK}px; height: {C_MARK}px; margin-left: -{C_INSET}px; flex-shrink: 0">{alp(C_MARK)}</div>'


def q_head(title, sub=None, fact=None, busy=None, mark=True, size=28):
    parts = [(0, q_mark(busy))] if mark else []
    parts.append((24 if mark else 0, qt(title, size, round(size * 1.3), INK, 600, "letter-spacing: -0.018em")))
    if fact:
        parts.append((8, qm(fact)))
    if sub:
        parts.append((8, qt(sub)))
    return parts


def q_label(text):
    return f'<div style="margin-bottom: 8px">{m_eyebrow(text, INK3, 500, 0.08, 11, "line-height: 11px; display: block")}</div>'


def q_field(value="", focus=False):
    shown = value or "alpi://device?url=wss://…&amp;name=…&amp;pairing_token=…"
    ring = "#8c8c8c" if focus else LINE2
    return (f'<div style="min-height: 92px; box-sizing: border-box; padding: 12px; border-radius: 4px; border: 1px solid {ring}; background: var(--bg-elev, #ffffff); font-family: {MONO}; '
            f'font-size: 12px; line-height: 1.3; color: {INK if value else INK4}; word-break: break-all">{shown}</div>')


def q_sources():
    return col(*[col(qt(r["label"], 12, 16, INK3), qm(r["path"], 14, 21, INK2), gap=0) for r in COPY["rows"]], gap=8)


def q_ladder(states):
    rows = []
    for state, label in zip(states, Q_STEPS):
        glyph = {
            "done": mi("check", 12, INK),
            "fail": mi("x", 12, DANGER_TEXT),
            "now": f'<span style="width: 6px; height: 6px; border-radius: 4px; background: {INK2}"></span>',
            "todo": f'<span style="width: 6px; height: 6px; border-radius: 4px; background: {INK4}"></span>',
        }[state]
        color = {"todo": INK3, "fail": DANGER_TEXT}.get(state, INK)
        weight = 400 if state == "todo" else 500
        rows.append(line(f'<span style="width: 16px; flex-shrink: 0; display: inline-flex; justify-content: center">{glyph}</span>',
                         t(label, 14, color, weight, "line-height: 20px"), gap=8))
    return f'<div style="display: flex; flex-direction: column; gap: 8px">{"".join(rows)}</div>'


def q_failure(failure):
    return col(qt(failure["title"], 15, 20, DANGER_TEXT, 600), qt(failure["hint"]), gap=6)


def qb(label, kind="primary", size="hero", disabled=False, dark=False):
    html = m_button(label, kind, size, disabled=disabled).replace("border-radius: 4px", "border-radius: 4px; width: 100%", 1)
    if dark:
        html = html.replace("background: rgba(20,20,20,0.06)", "background: rgba(255,255,254,0.12)", 1).replace("color: #141414", f"color: {Q_WHITE}", 1)
    return html


def q_flush_ghost(label):
    return m_button(label, "ghost", "md").replace('<button style="', '<button style="margin-left: -14px; ', 1)


def q_screen(top, bottom="", w=Q_W, h=Q_H, edge=Q_EDGE, col_w=None, keyboard=False):
    width = f"width: {col_w}px;" if col_w else ""
    pad_bottom = 16 + (Q_KEYBOARD if keyboard else Q_SAFE_BOTTOM)
    board = (f'<div style="position: absolute; left: 0; right: 0; bottom: 0; height: {Q_KEYBOARD}px; background: {SELECTED}; display: flex; align-items: center; justify-content: center">'
             f'{mono("keyboard", 11, INK3)}</div>') if keyboard else ""
    return (f'<div style="position: relative; width: {w}px; height: {h}px; box-sizing: border-box; padding: {Q_SAFE_TOP + 24}px {edge}px {pad_bottom}px; display: flex; flex-direction: column; background: {PANE}">'
            f'<div style="{width} flex: 1; min-height: 0; overflow: hidden">{top}</div>'
            f'<div style="{width} flex-shrink: 0; display: flex; flex-direction: column; gap: 8px; padding-top: 16px">{bottom}</div>{board}</div>')


def q_welcome(**kw):
    top = q_page(*q_head("Pair with your alpi", sub="alpi runs on a computer or a server. Pair this phone once and its profiles come with you."),
                 (24, q_label("Where do I get a link?") + q_sources()))
    return q_screen(top, qb("Scan QR") + qb("Paste link", "ghost", "lg"), **kw)


def q_pair(states=None, value=Q_LINK, failure=None, busy=None, keyboard=False, saved=False, focus=False, **kw):
    parts = q_head("Pair this phone", fact=f"{Q_HOST} · {Q_URL}" if value else None, busy=busy, mark=not keyboard)
    parts.append((24, q_label("alpi:// link") + q_field(value, focus=focus or keyboard)))
    if states:
        steps = q_ladder(states)
        if failure:
            steps = col(steps, q_failure(failure), gap=16)
        parts.append((16, steps))
    else:
        parts.append((8, q_flush_ghost("Paste from clipboard")))
        if not keyboard:
            parts.append((16, q_sources()))
    inbox = qb("Open inbox", "ghost", "lg") if saved else ""
    if busy:
        bottom = ""
    elif failure and failure.get("saved"):
        bottom = qb("Open inbox")
    elif failure:
        bottom = qb(failure["action"]) + qb("Scan QR", "ghost", "lg") + inbox
    else:
        bottom = qb("Pair", disabled=not value) + qb("Scan QR", "ghost", "lg") + inbox
    return q_screen(q_page(*parts), bottom, keyboard=keyboard, **kw)


def q_scan():
    head = (f'<div style="padding: {Q_SAFE_TOP + 16}px {Q_EDGE}px 16px; display: flex; flex-direction: column; gap: 4px">'
            f'<div style="font-size: 14px; line-height: 18px; font-weight: 600; color: {Q_WHITE}">Pair this phone</div>'
            f'<div style="font-family: {MONO}; font-size: 11px; line-height: 14px; color: rgba(255,255,254,0.6)">Scan the QR shown on your daemon</div></div>')
    camera = f'<div style="flex: 1; background: {Q_CAM}; display: flex; align-items: center; justify-content: center">{mono("camera", 11, "rgba(255,255,254,0.4)")}</div>'
    bottom = f'<div style="padding: 16px {Q_EDGE}px {16 + Q_SAFE_BOTTOM}px">{qb("Paste link", "secondary", "lg", dark=True)}</div>'
    return f'<div style="width: {Q_W}px; height: {Q_H}px; background: #000000; display: flex; flex-direction: column; box-sizing: border-box">{head}{camera}{bottom}</div>'


def q_denied(blocked=False):
    top = q_page(*q_head("Pair this phone", sub="Camera permission needed to scan the pairing QR.", fact="camera · not allowed"))
    return q_screen(top, qb("Open settings" if blocked else "Grant access") + qb("Paste link", "ghost", "lg"))


def q_rows(bio_on=False, alerts="undetermined", face_id=True):
    bio = f'<span style="display: inline-flex; min-height: 44px; align-items: center">{switch(bio_on, DOC_ACCENT, "Face ID unlock")}</span>'
    notif = {"granted": pill("on", on=True), "denied": m_button("Open settings", "secondary", "md")}.get(alerts) or m_button("Enable", "secondary", "md")
    rows = ""
    if face_id:
        rows += m_row("Face ID unlock", "required on cold start", control=bio, chevron=False)
    rows += m_row("Notifications", "built on this phone from your daemon · no push service", control=notif, chevron=False, sep=False)
    return f'<div style="margin: 0 -{Q_EDGE}px">{rows}</div>'


def q_paired(bio_on=False, alerts="undetermined", face_id=True, **kw):
    top = q_page(*q_head("Paired with casa", sub="Your daemon is reachable and your profiles are available.", fact=COPY["admin"]),
                 (24, q_label("Optional")), (8, q_rows(bio_on, alerts, face_id)))
    return q_screen(top, qb("Open inbox"), **kw)


def q_first_profile(kind, w=Q_W, h=Q_H, side=False):
    member = kind == "member"
    copy = COPY["member"] if member else COPY["roster"]
    sub = copy["hint"].replace("this phone", "this tablet") if member and side else copy["hint"]
    body = q_page(*q_head(copy["title"], sub=sub, fact="member · nothing shared yet" if member else None, size=22))
    action = "" if member else qb("New profile")
    pane = (f'<div style="flex: 1; min-height: 0; box-sizing: border-box; padding: 24px {Q_EDGE}px 16px; display: flex; flex-direction: column">'
            f'<div style="flex: 1; min-height: 0; overflow: hidden">{body}</div>{action}</div>')
    if side:
        return (f'<div style="width: {w}px; height: {h}px; flex-shrink: 0; box-sizing: border-box; background: #f6f6f6; border-right: 0.5px solid rgba(20,20,20,0.07); display: flex; flex-direction: column">'
                f'{m_conn_header()}<div style="flex: 1; min-height: 0; display: flex; flex-direction: column">{pane}</div>{m_shell_footer(icons_only=True)}</div>')
    return (f'<div style="width: {w}px; height: {h}px; display: flex; flex-direction: column; box-sizing: border-box; padding-top: {Q_SAFE_TOP}px; background: {PANE}">'
            f'{m_conn_header(ring="#ffffff", collapse=False, bg="#ffffff")}<div style="height: 0.5px; background: {LINE}"></div>{pane}'
            f'{m_shell_footer(ring="#ffffff", border=True)}<div style="height: {Q_SAFE_BOTTOM}px"></div></div>')


def fold_box(inner):
    return f'<div style="display: flex; width: {Q_FOLD_W}px; height: {Q_FOLD_H}px; background: {PANE}">{inner}</div>'


def fold_first_profile(member=False, folded=False):
    if folded:
        action = "" if member else f'<div style="padding: 16px">{qb("New profile")}</div>'
        pane = (f'<div style="flex: 1; min-width: 0; display: flex; flex-direction: column; padding-top: {Q_SAFE_TOP}px">'
                f'<div style="padding: 8px 16px">{mi("panel-left", 20, INK2)}</div>'
                f'<div style="flex: 1; display: flex; align-items: center; justify-content: center; padding: 28px">{t("Their chats open here.", 14, INK3, 400)}</div>{action}</div>')
        return fold_box(pane)
    pane = (f'<div style="flex: 1; min-width: 0; display: flex; align-items: center; justify-content: center; padding: {Q_SAFE_TOP}px 28px 0">'
            f'{t("Their chats open here.", 14, INK3, 400)}</div>')
    return fold_box(q_first_profile("member" if member else "admin", 280, Q_FOLD_H, side=True) + pane)
