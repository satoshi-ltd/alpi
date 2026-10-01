from gen import DANGER, DOC_ACCENT, diamond, ic, mix, page
from desktop_boards import HOVER, INK, INK2, INK3, INK4, LINE, LINE2, MONO, PANE, SELECTED, SIDE

AMBER = "#f0b447"
BRAND = "#8a5a0a"
BUILDER = "#c14545"
SUCCESS, WARNING, DANGER_FILL = "#3fb37a", "#e08a3c", "#c14545"
SUCCESS_TEXT, WARNING_TEXT = "#217a45", "#b3470e"
SANS = "Geist, ui-sans-serif, system-ui, sans-serif"


def h1(text, sub):
    return (f'<div style="display: flex; flex-direction: column; gap: 6px"><span style="font-size: 28px; font-weight: 600; letter-spacing: -0.02em; line-height: 1.15">{text}</span>'
            f'<span style="font-size: 13px; line-height: 1.5; color: {INK3}; max-width: 900px">{sub}</span></div>')


def label(text):
    return f'<span style="font-family: {MONO}; font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase; color: {INK3}">{text}</span>'


def spec(title, inner, w=None, pad=20, bg=PANE):
    width = f"width: {w}px;" if w else ""
    return (f'<div style="display: flex; flex-direction: column; gap: 8px; {width} flex-shrink: 0">{label(title)}'
            f'<div style="display: flex; flex-direction: column; gap: 14px; padding: {pad}px; border-radius: 12px; background: {bg}; border: 0.5px solid {LINE}">{inner}</div></div>')


def row(*items, gap=22):
    return f'<div style="display: flex; gap: {gap}px; align-items: flex-start; flex-wrap: wrap">{"".join(items)}</div>'


def mono(text, size=12, color=INK3, weight=400):
    return f'<span style="font-family: {MONO}; font-size: {size}px; color: {color}; font-weight: {weight}">{text}</span>'


def small_diamond(color, size=8):
    return f'<span style="width: {size}px; height: {size}px; border-radius: 1.5px; background: {color}; transform: rotate(45deg); display: inline-block; flex-shrink: 0"></span>'


def iconbtn(name, size=24, glyph=12, color=INK2):
    return (f'<button aria-label="{name}" style="width: {size}px; height: {size}px; border: 0; border-radius: 8px; background: transparent; display: inline-flex; '
            f'align-items: center; justify-content: center; padding: 0; color: {color}; cursor: pointer">{ic(name, glyph, color)}</button>')


def sep():
    return f'<span style="color: {INK4}; margin: 0 6px">·</span>'


def dot(color, size=7, ring=False):
    shadow = f"box-shadow: 0 0 0 4px {mix(color, 0.4)};" if ring else ""
    return f'<span style="width: {size}px; height: {size}px; border-radius: 999px; background: {color}; display: inline-block; flex-shrink: 0; {shadow}"></span>'


def meter(value, tail, pct, color=BRAND, percent=True):
    p = mono(f"{round(pct * 100)}%", 11) if percent else ""
    return (f'<span style="display: inline-flex; align-items: center; gap: 8px">{mono(value, 11, INK2)}{mono(tail, 11)}'
            f'<span style="width: 56px; height: 5px; border-radius: 999px; background: {LINE}; overflow: hidden; display: inline-block"><span style="display: block; width: {max(pct * 100, 3)}%; height: 100%; background: {color}"></span></span>{p}</span>')


def vsep():
    return f'<span style="width: 1px; height: 10px; background: {LINE2}; display: inline-block"></span>'



def d_user(text, accent=AMBER):
    return (f'<div style="display: flex; flex-direction: column; align-items: flex-end; gap: 4px">'
            f'<div style="max-width: 76%; padding: 12px 16px; border-radius: 14px 6px 14px 14px; background: {mix(accent, 0.12)}; font-size: 15px; line-height: 1.65; color: {INK}">{text}</div>'
            f'<div style="display: flex; align-items: center; gap: 4px; color: {INK3}"><span style="margin-right: 6px">{mono("2m", 11)}</span><span style="opacity: 0.4; display: inline-flex">{iconbtn("pencil")}{iconbtn("copy")}</span></div></div>')


def d_assistant(body, meta=True, hover=True):
    footer = ""
    if meta:
        tip = (f'<span style="display: inline-flex; flex-direction: column; gap: 3px; margin-left: 10px; padding: 6px 9px; border-radius: 8px; background: {INK}">'
               f'{mono("3.4K tokens · $0.0123", 11, PANE)}{mono("sonnet-4 · 12.4s", 11, INK4)}</span>')
        footer = (f'<div style="display: flex; align-items: center; gap: 2px; margin-top: 4px">{mono("2m", 11)}'
                  f'<span style="display: inline-flex; margin-left: 6px; opacity: {1 if hover else 0.4}">{iconbtn("copy", 26, 13)}{iconbtn("refresh", 26, 13)}{iconbtn("volume", 26, 13)}</span>{tip if hover else ""}</div>')
    return f'<div style="display: flex; flex-direction: column; gap: 6px"><div style="font-size: 15px; line-height: 1.65; letter-spacing: -0.003em; color: {INK}">{body}</div>{footer}</div>'


def code_inline(text):
    return f'<code style="font-family: {MONO}; font-size: 0.92em; background: {HOVER}; padding: 1px 5px; border-radius: 4px">{text}</code>'


def d_code_block(lang, code):
    return (f'<div style="margin: 12px 0; border: 0.5px solid {LINE}; border-radius: 8px; overflow: hidden">'
            f'<div style="display: flex; justify-content: space-between; padding: 6px 10px; background: {HOVER}; border-bottom: 0.5px solid {LINE}">{mono(lang, 11)}{mono("copy", 11)}</div>'
            f'<pre style="margin: 0; padding: 12px 14px; font-family: {MONO}; font-size: 12px; line-height: 1.5; color: {INK}; background: {HOVER}">{code}</pre></div>')


def d_table():
    cells = [("job", "status", "time"), ("api-migrate", "timed out", "300s"), ("web-build", "lint error", "42s")]
    head = "".join(f'<th style="text-align: left; padding: 12px 14px; font-weight: 600; color: {INK2}; background: #f8f8f8; border-bottom: 0.5px solid {LINE}">{c}</th>' for c in cells[0])
    body = "".join("<tr>" + "".join(f'<td style="padding: 12px 14px; border-top: 0.5px solid {LINE}; background: {PANE}">{c}</td>' for c in r) + "</tr>" for r in cells[1:])
    return f'<div style="margin: 12px 0; border: 0.5px solid {LINE2}; border-radius: 8px; overflow: hidden"><table style="width: 100%; border-collapse: collapse; font-size: 13px"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def d_reasoning(open_=False, streaming=False):
    caret = ic("chev-d", 11, INK3).replace('style="', 'style="transform: rotate(-90deg); ' if not open_ else 'style="', 1)
    peek = "" if open_ else f'<span style="flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap">{mono("Checking which jobs exited non-zero…")}</span>'
    lines = ""
    if open_:
        size = 11 if streaming else 12
        body = "".join(f'<div style="font-family: {MONO}; font-size: {size}px; line-height: 1.65; color: {INK3}">{t}</div>' for t in ("The user wants a summary of yesterday's deploys.", "Read the log, group by job, count exits.", "Two jobs failed; call them out first."))
        mask = "mask-image: linear-gradient(to bottom, transparent, black 28px); max-height: 116px; overflow: hidden;" if streaming else ""
        lines = f'<div style="margin-top: 8px; display: flex; flex-direction: column; gap: 6px; {mask}">{body}</div>'
    label_text = "thinking · 4s" if streaming else "thinking · 7s"
    return f'<div><div style="display: flex; align-items: center; gap: 6px">{caret}{mono(label_text)}{peek}</div>{lines}</div>'


def d_tool(name, args, state="done"):
    color = {"running": BRAND, "done": INK3, "failed": DANGER_FILL}[state]
    name_color = DANGER if state == "failed" else INK
    arg_html = "".join(f'<span style="color: {INK4}">{k}=</span><span style="color: {INK2}; margin-right: 8px">{v}</span>' for k, v in args)
    trailer = ""
    if state == "running":
        trailer = f'<span style="display: inline-flex; gap: 2px; margin-left: 6px">{"".join(dot(BRAND, 3) for _ in range(3))}</span>'
    return (f'<div style="display: inline-flex; align-items: center; gap: 8px; padding: 2px 0; font-family: {MONO}; font-size: 12px; color: {INK2}">'
            f'{ic("chip", 14, color)}<span style="font-weight: 500; color: {name_color}">{name}</span><span style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis">{arg_html}</span>{trailer}</div>')


def d_bucket(text, failed=0, size=12, h=22):
    fail = f'<span style="display: inline-flex; align-items: center; gap: 4px; margin-left: 6px">{ic("alert", 12, DANGER_FILL)}{mono(f"{failed} failed", size, DANGER)}</span>' if failed else ""
    chev = ic("chev-d", 14, INK3).replace("style=" + chr(34), "style=" + chr(34) + "transform: rotate(-90deg); ", 1)
    return f'<div style="display: flex; align-items: center; gap: 10px; height: {h}px; padding: 0 10px">{chev}{mono(text, size)}{fail}</div>'


def d_attachment(name, sub, variant="composer"):
    bg = PANE if variant == "composer" else HOVER
    border = LINE2 if variant == "composer" else "transparent"
    box_bg = HOVER if variant == "composer" else PANE
    remove = iconbtn("x", 20, 12, INK3) if variant == "composer" else ""
    return (f'<div style="display: inline-flex; align-items: center; gap: 8px; padding: 8px 10px; border: 0.5px solid {border}; border-radius: 8px; background: {bg}; max-width: 280px">'
            f'<span style="width: 32px; height: 32px; border-radius: 6px; background: {box_bg}; display: inline-flex; align-items: center; justify-content: center">{ic("copy", 16, INK3)}</span>'
            f'<span style="display: flex; flex-direction: column; min-width: 0"><span style="font-size: 12px; color: {INK}">{name}</span>{mono(sub, 11)}</span>{remove}</div>')


def d_images():
    tile = lambda c: f'<div style="aspect-ratio: 4 / 3; border-radius: 8px; border: 0.5px solid {LINE}; background: linear-gradient(135deg, {mix(c, 0.35)}, {mix(c, 0.12)})"></div>'
    return f'<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6px; max-width: 420px">{tile(DOC_ACCENT)}{tile(AMBER)}</div>'


def d_peer():
    return (f'<div style="display: flex; flex-direction: column; align-items: flex-start; gap: 6px">'
            f'<div style="display: flex; align-items: center; gap: 5px; font-size: 11px; color: {INK3}">{small_diamond(DOC_ACCENT)}<span style="font-weight: 600; color: {INK2}">@doc</span></div>'
            f'<div style="max-width: 76%; padding: 12px 16px; border-radius: 6px 14px 14px 14px; background: {mix(DOC_ACCENT, 0.11)}; font-size: 15px; line-height: 1.65">The staging migration is safe to rerun; I added the missing index.</div></div>')


def d_ask_answered():
    return f'<div style="display: flex; align-items: center; gap: 8px; font-size: 13px; color: {INK}">{small_diamond(AMBER)}Use the staging database</div>'


def d_ask_missing():
    return (f'<div style="display: flex; flex-direction: column; gap: 4px; padding: 8px 10px; border: 1px solid {LINE}; border-radius: 8px">'
            f'<span style="font-size: 13px; color: {INK3}">Which environment should I target?</span>'
            f'<span style="font-family: {MONO}; font-size: 11px; letter-spacing: 0.6px; text-transform: uppercase; color: {INK3}">∅ expired</span></div>')


def kbd(t):
    return f'<span style="padding: 1px 5px; border-radius: 4px; background: {HOVER}; border: 0.5px solid {LINE}; font-family: {MONO}; font-size: 11px; font-weight: 500; color: {INK2}">{t}</span>'


def d_send(state="idle", accent=AMBER):
    if state == "busy":
        return f'<button aria-label="Stop" style="width: 32px; height: 32px; border: 0; border-radius: 10.67px; background: {INK}; display: inline-flex; align-items: center; justify-content: center"><span style="width: 12px; height: 12px; background: {PANE}; border-radius: 2px"></span></button>'
    bg, fg = (accent, "#0b1117") if state == "ready" else (LINE, INK3)
    return f'<button aria-label="Send" style="width: 32px; height: 32px; border: 0; border-radius: 10.67px; background: {bg}; display: inline-flex; align-items: center; justify-content: center">{ic("up", 14, fg)}</button>'


def d_composer(text="", state="idle", hint=True, model=True, name="alpi", model_name="sonnet-4"):
    value = f'<span style="font-size: 14px; line-height: 1.5; color: {INK}">{text}</span>' if text else f'<span style="font-size: 14px; line-height: 1.5; color: {INK3}">Message {name}…</span>'
    hints = f'<span style="display: inline-flex; align-items: center; gap: 10px; font-size: 11px; color: {INK3}"><span>{mono("@", 11, INK2)} mention</span><span style="display: inline-flex; gap: 3px; align-items: center">{kbd("⌘")}{kbd("↵")} send</span></span>' if hint else ""
    picker = f'<span style="display: inline-flex; align-items: center; gap: 6px; height: 28px; padding: 0 12px; border-radius: 8px">{ic("sun", 12, INK3)}{mono(model_name, 12, INK)}{ic("chev-d", 12, INK3)}</span>' if model else ""
    return (f'<div style="display: flex; flex-direction: column; gap: 8px; padding: 14px 16px 10px; border-radius: 16px; background: {PANE}; border: 0.5px solid {LINE2}">'
            f'<div style="min-height: 22px">{value}</div>'
            f'<div style="display: flex; align-items: center; gap: 6px">{hints}<span style="flex: 1"></span>{iconbtn("clip", 28, 16)}{picker}{d_send(state)}</div></div>')


def d_mention():
    items = "".join(f'<div style="display: flex; align-items: center; gap: 8px; padding: 8px 10px; border-radius: 8px; {"background: " + SELECTED + ";" if i == 0 else ""} font-size: 13px; font-weight: 500">{small_diamond(c, 9)}{n}</div>' for i, (n, c) in enumerate((("doc", DOC_ACCENT), ("abby", "#c14580"), ("builder", BUILDER))))
    return f'<div style="width: 160px; padding: 6px; border-radius: 12px; background: {PANE}; border: 0.5px solid {LINE2}; box-shadow: 0 18px 50px rgba(11,17,23,0.10)">{items}</div>'


def d_jump():
    return f'<span style="width: 32px; height: 32px; border-radius: 999px; background: {PANE}; border: 0.5px solid {LINE2}; box-shadow: 0 18px 50px rgba(11,17,23,0.10); display: inline-flex; align-items: center; justify-content: center">{ic("chev-d", 14, INK2)}</span>'


def d_header(kind="profile"):
    if kind == "profile":
        glyph = diamond(AMBER, 14)
        title = "alpi"
        meta = f'{mono("sonnet-4", 12, INK2)}{vsep()}{meter("12.4K", "/200K", 0.06)}{vsep()}{meter("$0.42", "/$5.00", 0.08)}'
        right = f'<span style="display: inline-flex; align-items: center; gap: 6px; font-size: 13px; font-weight: 500; color: {INK2}">Sessions{ic("chev-d", 12, INK2)}</span>{iconbtn("more", 28, 16)}'
    else:
        glyph = f'<span style="position: relative; width: 21px; height: 21px; display: inline-block">{small_diamond(mix(AMBER, 0.35), 14).replace("display: inline-block", "display: inline-block; position: absolute; left: 7px; top: 0")}{small_diamond(AMBER, 14).replace("display: inline-block", "display: inline-block; position: absolute; left: 0; top: 7px")}</span>'
        title = "launch-crew"
        meta = f'<span style="display: inline-flex; align-items: center; gap: 5px; font-size: 12px"><span style="color: {INK4}">hub</span>{small_diamond(AMBER)}{mono("@alpi", 12, INK2)}</span>{vsep()}<span style="font-size: 12px"><span style="color: {INK4}">members</span> {mono("4", 12, INK2)}</span>{vsep()}{meter("$1.20", "/$10.00", 0.12)}'
        right = f'<span style="display: inline-flex; align-items: center; gap: 6px; font-size: 13px; font-weight: 500; color: {INK2}">Tasks{ic("chev-d", 12, INK2)}</span>{iconbtn("more", 28, 16)}'
    return (f'<div style="position: relative; display: flex; align-items: flex-end; justify-content: space-between; padding: 30px 24px 18px; background: {PANE}; border-bottom: 0.5px solid {LINE}">'
            f'<div style="display: flex; flex-direction: column; gap: 8px"><div style="display: flex; align-items: center; gap: 12px">{glyph}<span style="font-size: 28px; font-weight: 600; letter-spacing: -0.018em; line-height: 1">{title}</span></div>'
            f'<div style="display: flex; align-items: center; gap: 14px; color: {INK3}">{meta}</div></div><div style="display: flex; align-items: center; gap: 2px">{right}</div>'
            f'<span style="position: absolute; left: 24px; bottom: -0.5px; width: 40px; height: 1.5px; background: {AMBER}"></span></div>')


def d_skeleton():
    bar = lambda w: f'<div style="height: 13px; width: {w}; border-radius: 6px; background: linear-gradient(90deg, {HOVER}, rgba(11,17,23,0.09), {HOVER})"></div>'
    return (f'<div style="display: flex; flex-direction: column; gap: 9px">{bar("88%")}{bar("100%")}{bar("62%")}</div>'
            f'<div style="align-self: flex-end; min-width: 220px; max-width: 70%; padding: 12px 16px; border-radius: 16px; background: {HOVER}"><div style="height: 13px; width: 160px; border-radius: 6px; background: rgba(11,17,23,0.09)"></div></div>')


def d_hero():
    recents = "".join(
        f'<div style="display: grid; grid-template-columns: auto auto 1fr auto; gap: 14px; align-items: center; padding: 10px 8px; border-radius: 8px">{small_diamond(c)}{mono("@" + n, 12, INK2)}<span style="font-size: 13px; color: {INK2}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis">{t}</span>{mono(ago, 11)}</div>'
        for n, c, t, ago in (("doc", DOC_ACCENT, "Draft the Q3 incident review", "3h"), ("alpi", AMBER, "Summarize yesterday's deploys", "1d")))
    to = f'<div style="display: flex; align-items: center; gap: 8px; height: 40px; padding: 0 16px; border-bottom: 0.5px solid {LINE}">{mono("TO", 11)}{small_diamond(AMBER)}{mono("@alpi", 13, INK, 600)}<span style="color: {INK4}">·</span>{mono("sonnet-4", 13)}<span style="flex: 1"></span>{ic("chev-d", 14, INK3)}</div>'
    return (f'<div style="display: flex; flex-direction: column; gap: 16px; max-width: 560px">'
            f'<div style="border-radius: 16px; border: 0.5px solid {LINE2}; background: {PANE}; overflow: hidden">{to}<div style="padding: 16px 20px 12px; min-height: 60px; font-size: 14px; color: {INK3}">Message alpi…</div></div>'
            f'<div style="display: flex; justify-content: space-between; padding: 0 8px">{label("Recents")}{mono("5 sessions", 11)}</div>{recents}</div>')


TOOL_ICONS = {"read_file": "file", "grep": "search", "shell": "terminal", "web_fetch": "globe", "memory": "chip", "send_message": "link"}


def d_step(name, summary, dur, state="done", body="", size=12, h=22):
    icon = TOOL_ICONS.get(name, "chip")
    color = {"done": INK3, "failed": DANGER_FILL, "running": BRAND}[state]
    status = {"done": mono(dur, size), "failed": mono(f"failed · {dur}", size, DANGER), "running": mono(f"{dur} …", size, BRAND)}[state]
    chev = ic("chev-d", 12, INK3) if body else ic("chev-r", 12, INK3)
    head = (f'<div style="display: flex; align-items: center; gap: 10px; height: {h}px; padding: 0 10px">'
            f'{ic(icon, 14, color)}{mono(name, size, DANGER if state == "failed" else INK2)}'
            f'<span style="flex: 1; min-width: 0; font-family: {MONO}; font-size: {size}px; color: {INK3}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis">{summary}</span>{status}{chev}</div>')
    return f'<div style="display: flex; flex-direction: column; gap: 4px">{head}{body}</div>'


def step_body(lines, size=12):
    return f'<div style="margin: 2px 10px 4px 32px; padding: 8px 10px; border-radius: 8px; background: {SIDE}; border: 0.5px solid {LINE}; font-family: {MONO}; font-size: {size}px; line-height: 1.6; color: {INK2}">{"<br>".join(lines)}</div>'


def req_btn(text, variant="secondary"):
    bg, fg = {"primary": (INK, PANE), "secondary": (HOVER, INK), "ghost": ("transparent", INK2)}[variant]
    return f'<span style="display: inline-flex; align-items: center; height: 24px; padding: 0 10px; border-radius: 8px; font-size: 12px; font-weight: 500; white-space: nowrap; background: {bg}; color: {fg}">{text}</span>'


def inline_request(who="@alpi", command="rm -rf dist &amp;&amp; npm run build", seconds=42):
    return (f'<div style="display: flex; flex-direction: column; gap: 10px; padding: 12px 14px; border-radius: 10px; border: 1px solid {mix(WARNING, 0.6)}; background: {mix(WARNING, 0.08)}">'
            f'<span style="display: flex; align-items: center; gap: 8px; font-size: 13px; font-weight: 600">{ic("alert", 14, WARNING)}<span style="flex: 1">{who} wants to run a command</span>{mono(f"auto-deny in {seconds}s", 11)}</span>'
            f'<span style="font-family: {MONO}; font-size: 12px; line-height: 1.65; color: {INK}">{command}</span>'
            f'<span style="display: flex; flex-wrap: wrap; gap: 8px">{req_btn("Deny")}{req_btn("Allow once", "primary")}{req_btn("Allow this session")}{req_btn("Always allow")}</span></div>')


def inline_ask(question="Which lab should I book with?", choices=("Quest · Main St", "Labcorp · 5th Ave"), seconds=88):
    return (f'<div style="display: flex; flex-direction: column; gap: 10px; padding: 12px 14px; border-radius: 10px; border: 1px solid {mix(WARNING, 0.6)}; background: {mix(WARNING, 0.08)}">'
            f'<span style="display: flex; align-items: center; gap: 8px; font-size: 13px; font-weight: 600">{ic("sparkle", 14, BRAND)}<span style="flex: 1">{question}</span>{mono(f"auto-cancel in {seconds}s", 11)}</span>'
            f'<span style="display: flex; flex-wrap: wrap; gap: 8px">{"".join(req_btn(c) for c in choices)}{req_btn("Type your own…", "ghost")}</span></div>')


def thinking(peek="reading the deploy log", size=12, h=22, pad=10, glyph=14):
    return f'<div style="display: flex; align-items: center; gap: 10px; height: {h}px; padding: 0 {pad}px; border-radius: 6px; background: {HOVER}">{ic("chev-r", glyph, INK3)}<span style="font-family: {MONO}; font-size: {size}px; color: {INK3}">Thinking…</span>{mono(peek, size)}</div>'


def thought(open_=False, size=12, h=22, secs="7s", chev=INK3, pad=10, glyph=14, rule=(2, 14, 12), lines=("The user wants a summary of yesterday’s deploys.", "Read the log, group by job, count exits.", "Two jobs failed; call them out first.")):
    head = f'<div style="display: flex; align-items: center; gap: 10px; height: {h}px; padding: 0 {pad}px">{ic("chev-d" if open_ else "chev-r", glyph, chev)}{mono(f"Thought for {secs}", size)}</div>'
    if not open_:
        return head
    body = "".join(f'<div style="font-family: {MONO}; font-size: {size}px; line-height: 1.65; color: {INK2}">{t}</div>' for t in lines)
    return head + f'<div style="display: flex; flex-direction: column; gap: 4px; margin: 4px 0 4px {rule[1]}px; padding-left: {rule[2]}px; border-left: {rule[0]}px solid {LINE}">{body}</div>'


def process(*rows, gap=2):
    return f'<div style="display: flex; flex-direction: column; gap: {gap}px; margin-left: -10px">{"".join(rows)}</div>'


def desktop_conversation():
    body = f"""<div style="padding: 40px 48px; display: flex; flex-direction: column; gap: 24px; box-sizing: border-box">
{h1("Conversation · desktop", "Messages, alpi’s process and the composer as ChatPane paints them. The user writes in a tinted bubble; alpi answers full width in sans. Reasoning and tool steps are alpi’s process: one mono block at 12 px, in the order they happened, 12 px above the answer. Both footers keep a faint time; usage lives in a tooltip on the time. Turns sit 40 px apart.")}
{spec("Chat header · profile", d_header("profile"), 1184, 0)}
{spec("Chat header · workgroup", d_header("workgroup"), 1184, 0)}
{row(spec("User message · accent 12%, radius 14 6 14 14, faint time, actions on hover", d_user("Can you summarize yesterday’s deploy logs and flag anything that failed?"), 580), spec("Peer reply · peer accent 11%, radius 6 14 14 14", d_peer(), 580))}
{spec("Alpi message · markdown body, faint time, actions on hover, usage in a tooltip on the time", d_assistant("<strong>Deploy summary</strong>: 14 jobs ran; 2 failed.<ul style='margin: 8px 0; padding-left: 22px'><li>" + code_inline("api-migrate") + " timed out after 300s</li><li>" + code_inline("web-build") + " hit a lint error</li></ul>" + d_code_block("bash", "alpi logs api-migrate --tail 50") + d_table() + "Want me to open a fix?"), 1184)}
{row(spec("Process block · collapsed: one mono block, 22 px rows 2 px apart, in the order it happened", process(thought(secs="3s"), d_bucket("2 tool calls")), 380), spec("Process block · streaming: the running step and Thinking… (static under reduced motion)", process(thought(secs="3s"), d_step("read_file", "deploy.log · first 200 lines", "0.2s"), d_step("web_fetch", "status.example.com", "3s", "running"), thinking()), 380), spec("Process block · opened: reasoning in mono, spans between the steps", process(thought(True, secs="3s", lines=("The user wants yesterday’s deploys.", "Read the log first.")), d_step("read_file", "deploy.log · first 200 lines", "0.2s"), thought(secs="2s"), d_step("grep", "3 matches for exit=1", "0.1s")), 380))}
{row(spec("Process block · steps open to arguments and output; failures open themselves", process(d_bucket("+3 previous tool calls", 1), d_step("shell", "npm run lint", "4.1s", "failed", step_body(["$ npm run lint", '<span style="color: #c14545">src/app.ts:14  no-unused-vars</span>', "1 error, 0 warnings"])), d_step("grep", "3 matches for exit=1", "0.1s")), 580), spec("Inline approval · the open chat asks in the flow; a question uses the same card", inline_request() + inline_ask(), 580))}
{spec("Load skeleton · after 450 ms", d_skeleton(), 580)}
{row(spec("Attachments · composer and message variants", d_attachment("deploy-report.pdf", "1.2 MB") + d_attachment("chart.png", "png · 240 KB", "message"), 380), spec("Produced images · 2-column grid, 4:3", d_images(), 380), spec("Ask user · answered and unanswered", d_ask_answered() + d_ask_missing(), 380))}
{row(spec("Composer · idle", d_composer(), 580), spec("Composer · ready to send", d_composer("Open a fix for the lint error", "ready"), 580))}
{row(spec("Composer · busy (Stop)", d_composer("Open a fix for the lint error", "busy"), 580), spec("Mention popover · jump to latest", row(d_mention(), d_jump()), 580))}
{spec("New chat hero · TO picker, composer, recents", d_hero(), 1184)}
</div>"""
    return page("System · desktop conversation", 1280, 2900, body)



def d_post(name, color, text, seq, side="left", cost="1.2K · $0.01"):
    radius = "6px 14px 14px 14px" if side == "left" else "14px 6px 14px 14px"
    meta_items = [f'<span style="display: inline-flex; align-items: center; gap: 5px">{small_diamond(color)}<span style="font-weight: 600; color: {INK2}">{name}</span></span>', mono(f"#{seq}", 11), mono(cost, 11)]
    meta = "".join(meta_items if side == "left" else list(reversed(meta_items)))
    align = "flex-start" if side == "left" else "flex-end"
    return (f'<div style="display: flex; flex-direction: column; align-items: {align}; gap: 6px"><div style="display: flex; align-items: center; gap: 10px; font-size: 11px; color: {INK3}">{meta}</div>'
            f'<div style="max-width: 76%; padding: 12px 16px; border-radius: {radius}; background: {mix(color, 0.11)}; font-size: 15px; line-height: 1.65">{text}</div></div>')


def d_marker(variant, color, body, side="right"):
    tints = {"task": (mix(color, 0.18), color), "working": (mix(color, 0.14), color), "done": (mix(color, 0.18), color), "blocked": (mix(DANGER_FILL, 0.12), DANGER), "skipped": (mix(WARNING, 0.12), WARNING_TEXT), "skip": (mix(color, 0.11), color)}
    bg, ey = tints[variant]
    icon = {"task": dot(ey), "working": dot(ey, ring=True), "done": ic("check", 11, ey), "blocked": ic("x", 11, ey), "skipped": ic("x", 11, ey), "skip": ic("x", 11, ey)}[variant]
    radius = "14px 6px 14px 14px" if side == "right" else "6px 14px 14px 14px"
    align = "flex-end" if side == "right" else "flex-start"
    eyebrow_color = ey if variant in ("blocked", "skipped") else f"color-mix(in srgb, {ey} 75%, {INK})"
    return (f'<div style="display: flex; flex-direction: column; align-items: {align}"><div style="max-width: 76%; min-width: 320px; padding: 14px 16px 16px; border-radius: {radius}; background: {bg}">'
            f'<div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px; font-family: {MONO}; font-size: 11px; font-weight: 600; letter-spacing: 0.10em; color: {eyebrow_color}">{icon}{variant.upper()}</div>'
            f'<div style="font-size: 15px; line-height: 1.5; color: {INK}">{body}</div></div></div>')


def d_pipeline():
    chip = lambda icon, text, extra="": f'<span style="display: inline-flex; align-items: center; gap: 4px; height: 18px; padding: 0 8px; border-radius: 16px; font-family: {MONO}; font-size: 11px; color: {INK2}; {extra}">{icon}{text}</span>'
    arrow = f'<span style="color: {INK3}">›</span>'
    return (f'<div style="display: flex; align-items: center; flex-wrap: wrap; gap: 8px; padding: 8px 0">'
            f'<span style="font-family: {MONO}; font-size: 11px; font-weight: 500; letter-spacing: 0.06em; text-transform: uppercase; color: {INK3}; margin-right: 6px">Pipeline · triage</span>'
            f'{chip(ic("check", 9, SUCCESS), "#intake")}{arrow}{chip(dot(AMBER), "#analyze")}{arrow}{chip("", "#report")}{arrow}{chip(ic("x", 9, DANGER), "#publish", "background: " + mix(DANGER_FILL, 0.16) + "; color: " + DANGER)}</div>')


def d_wg_composer():
    hint = f'<span style="font-size: 11px; color: {INK3}"><span style="color: {INK3}">→</span> {small_diamond(AMBER)} {mono("@alpi", 12, INK2)} formulates as {mono("#task #&lt;slug&gt;", 12, INK2)}</span>'
    return (f'<div style="display: flex; flex-direction: column; gap: 8px; padding: 14px 16px 10px; border-radius: 16px; background: {PANE}; border: 0.5px solid {LINE2}">'
            f'<span style="font-size: 14px; color: {INK3}">Send a message — use @&lt;peer&gt; or #task #&lt;slug&gt; to open</span>'
            f'<div style="display: flex; align-items: center; gap: 6px">{hint}<span style="flex: 1"></span>{kbd("⌘")}{kbd("↵")}{d_send()}</div></div>')


def desktop_workgroup():
    body = f"""<div style="padding: 40px 48px; display: flex; flex-direction: column; gap: 24px; box-sizing: border-box">
{h1("Workgroups · desktop", "Posts from members sit on the left, the hub on the right, each tinted with its speaker's accent at 11%. Marker cards record the #task lifecycle; the pipeline strip under the header tracks the phases.")}
{spec("Pipeline strip · done, current, pending, blocked", d_pipeline(), 1184)}
{spec("Posts · member (left) and hub (right)", d_post("builder", BUILDER, "Patched the retry loop; tests green locally.", 57) + d_post("alpi", AMBER, "Good. Ship it behind the flag and report back.", 58, "right"), 1184)}
{row(spec("Marker · task", d_marker("task", AMBER, "<strong>#onboarding-friction</strong> Find the top 3 drop-off points<br>Use last week’s funnel data."), 580), spec("Marker · working (pulsing dot)", d_marker("working", AMBER, "Pulling funnel events…", "left"), 580))}
{row(spec("Marker · done", d_marker("done", AMBER, "Top 3: email verify, workspace invite, first prompt."), 580), spec("Marker · skip", d_marker("skip", AMBER, "Out of scope for this sprint.", "left"), 580))}
{row(spec("Marker · done → blocked", d_marker("blocked", AMBER, "Needs a production API key nobody has."), 580), spec("Marker · done → skipped", d_marker("skipped", AMBER, "Preempted by the incident review."), 580))}
{spec("Workgroup composer · no attach, no model picker", d_wg_composer(), 1184)}
</div>"""
    return page("System · desktop workgroups", 1280, 1200, body)



def phone(inner, w=390):
    return f'<div style="width: {w}px; box-sizing: border-box; display: flex; flex-direction: column; gap: 14px">{inner}</div>'


def m_stamp(text="2m"):
    return f'<span style="font-family: {MONO}; font-size: 12px; font-weight: 500; line-height: 1; color: {INK3}">{text}</span>'


def m_user(text, accent=AMBER, pane=False):
    return (f'<div style="display: flex; flex-direction: column; align-items: flex-end; gap: 4px; padding: 0 16px">'
            f'<div style="max-width: {76 if pane else 82}%; padding: 12px 16px; border-radius: 18px 4px 18px 18px; background: {mix(accent, 0.12)}; font-size: 16px; line-height: 26.4px">{text}</div>'
            f'{m_stamp()}</div>')


def m_assistant():
    code = (f'<div style="margin: 8px 0; border-radius: 10px; border: 0.5px solid {LINE}; background: {HOVER}; overflow: hidden"><div style="padding: 6px 10px; border-bottom: 0.5px solid {LINE}">{mono("bash", 11)}</div>'
            f'<div style="padding: 12px; font-family: {MONO}; font-size: 14px; line-height: 21px">alpi logs api-migrate</div></div>')
    quote = f'<div style="margin: 6px 0; padding-left: 10px; border-left: 3px solid {INK}; opacity: 0.85">Two jobs failed overnight.</div>'
    lst = "".join(f'<div style="display: flex; gap: 8px"><span>•</span><span>{t}</span></div>' for t in ("api-migrate timed out", "web-build hit a lint error"))
    return (f'<div style="padding: 0 16px; font-size: 16px; line-height: 26.4px; color: {INK}"><div style="font-weight: 600; margin-top: 4px; margin-bottom: 4px">Deploy summary</div>'
            f'{quote}<div style="display: flex; flex-direction: column; gap: 4px; margin: 6px 0; padding-left: 20px">{lst}</div>{code}Want me to open a fix?'
            f'<div style="margin-top: 4px; display: flex; gap: 10px; align-items: center">{m_stamp()}{mono("⇢ sonnet-4", 11)}</div></div>')


def m_agent_text(text, stamp="2m"):
    return f'<div style="padding: 0 16px; display: flex; flex-direction: column; gap: 4px"><div style="font-size: 16px; line-height: 26.4px; color: {INK}">{text}</div>{m_stamp(stamp)}</div>'


def m_reasoning(open_=False, secs="7s"):
    return thought(open_, 12, 20, secs, INK3, 16, 12, (1, 23, 12))


def m_tool(name, args, state="done"):
    color = {"running": BRAND, "done": INK3, "failed": DANGER_FILL}[state]
    return (f'<div style="display: flex; align-items: center; gap: 8px; height: 20px; padding: 0 16px">{ic(TOOL_ICONS.get(name, "chip"), 12, color)}{mono(name, 12, DANGER if state == "failed" else INK2)}'
            f'<span style="flex: 1; min-width: 0; font-family: {MONO}; font-size: 12px; color: {DANGER if state == "failed" else INK3}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis">{args}</span>{ic("chev-r", 12, INK4)}</div>')


def m_process(*rows):
    return f'<div style="display: flex; flex-direction: column; gap: 4px">{"".join(rows)}</div>'


def m_bucket(text, failed=0, open_=False):
    chev = ic("chev-d", 12, INK3) if open_ else ic("chev-d", 12, INK3).replace("style=" + chr(34), "style=" + chr(34) + "transform: rotate(-90deg); ", 1)
    fail = f'<span style="display: inline-flex; align-items: center; gap: 4px">{ic("alert", 12, DANGER_FILL)}{mono(f"{failed} failed", 12, DANGER)}</span>' if failed else ""
    return f'<div style="display: flex; align-items: center; gap: 8px; height: 20px; padding: 0 16px">{chev}{mono(text, 12)}{fail}</div>'


def m_model_chip(text="sonnet-4 · medium"):
    return (f'<span style="display: inline-flex; align-items: center; gap: 6px; min-width: 0; height: 32px; padding: 0 12px; border-radius: 16px; background: #f1f3f5">'
            f'{ic("sparkle", 12, INK3)}<span style="font-size: 14px; color: {INK2}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis">{text}</span>{ic("chev-d", 12, INK3)}</span>')


def m_attachment(name, sub, variant="composer"):
    bg = PANE if variant == "composer" else HOVER
    border = LINE2 if variant == "composer" else "transparent"
    remove = ic("x", 14, INK3) if variant == "composer" else ""
    return (f'<div style="display: inline-flex; align-items: center; gap: 8px; padding: 6px 10px; border-radius: 10px; background: {bg}; border: 0.5px solid {border}; max-width: 240px">'
            f'<span style="width: 32px; height: 32px; border-radius: 8px; background: {HOVER}; display: inline-flex; align-items: center; justify-content: center">{ic("copy", 16, INK3)}</span>'
            f'<span style="display: flex; flex-direction: column"><span style="font-size: 12px">{name}</span>{mono(sub, 11)}</span>{remove}</div>')


def m_composer(text="", state="idle", workgroup=False, name="alpi", chip="sonnet-4 · medium", accent=AMBER):
    value = f'<span style="font-size: 16px; line-height: 24px">{text}</span>' if text else f'<span style="font-size: 16px; line-height: 24px; color: {INK3}">Message @{name}…</span>'
    mention = f'<span style="font-size: 12px; color: {INK3}">{mono("@", 12)} mention</span>' if workgroup else ""
    if state == "busy":
        send = f'<span style="width: 30px; height: 30px; border-radius: 10px; background: {accent}; display: inline-flex; align-items: center; justify-content: center"><span style="width: 12px; height: 12px; background: #0b1117; border-radius: 2px"></span></span>'
    elif state == "ready":
        send = f'<span style="width: 30px; height: 30px; border-radius: 10px; background: {accent}; display: inline-flex; align-items: center; justify-content: center">{ic("up", 14, "#0b1117")}</span>'
    else:
        send = f'<span style="width: 30px; height: 30px; border-radius: 10px; background: {LINE}; display: inline-flex; align-items: center; justify-content: center">{ic("up", 14, INK3)}</span>'
    clip = "" if workgroup else f'<span style="width: 36px; display: inline-flex; justify-content: center">{ic("clip", 20, INK3)}</span>'
    model = "" if workgroup else m_model_chip(chip)
    return (f'<div style="padding: 8px 16px; border-top: 0.5px solid {LINE}; background: {PANE}"><div style="display: flex; flex-direction: column; gap: 8px; padding: 14px 16px 10px; border-radius: 16px; background: {PANE}; border: 0.5px solid {LINE2}">'
            f'{value}<div style="display: flex; align-items: center; gap: 8px">{mention}{model}<span style="flex: 1"></span>{clip}{send}</div></div></div>')


def m_header(kind="profile"):
    glyph = diamond(AMBER, 14) if kind == "profile" else f'<span style="font-family: {MONO}; font-size: 18px; font-weight: 500; color: {INK3}">#</span>'
    title = "alpi" if kind == "profile" else "launch-crew"
    meta = f'{mono("sonnet-4", 11, INK2)} {meter("12.4K", "/200K", 0.06, BRAND, False)}' if kind == "profile" else f'{mono("hub", 11)} {small_diamond(AMBER)} {mono("@alpi · 4 members", 11)}'
    return (f'<div style="position: relative; display: flex; align-items: flex-start; gap: 10px; padding: 6px 16px 8px; border-bottom: 0.5px solid {LINE}; background: {PANE}">{ic("back", 20, INK2)}'
            f'<div style="flex: 1; display: flex; flex-direction: column; gap: 1px"><div style="display: flex; align-items: center; gap: 6px">{glyph}<span style="font-size: 18px; font-weight: 600; line-height: 23.4px">{title}</span></div><div style="display: flex; align-items: center; gap: 6px">{meta}</div></div>'
            f'{ic("clock", 20, INK2)}{ic("more", 20, INK2)}<span style="position: absolute; left: 16px; bottom: -0.5px; width: 36px; height: 1.5px; background: {AMBER}"></span></div>')


def m_jump():
    return f'<span style="display: inline-flex; align-items: center; gap: 8px; height: 36px; padding: 0 14px; border-radius: 999px; background: {PANE}; border: 0.5px solid {LINE2}; box-shadow: 0 8px 24px rgba(11,17,23,0.08); font-size: 12px; font-weight: 500; color: {INK2}">{ic("chev-d", 14, INK2)}Latest</span>'


def m_empty():
    return (f'<div style="display: flex; flex-direction: column; align-items: center; gap: 16px; padding: 24px 28px; text-align: center">'
            f'<span style="font-size: 22px; font-weight: 600; letter-spacing: -0.396px; line-height: 28.6px">Start a thread with alpi</span>{mono("sonnet-4", 11)}</div>')


def mobile_conversation():
    body = f"""<div style="padding: 40px 48px; display: flex; flex-direction: column; gap: 24px; box-sizing: border-box">
{h1("Conversation · phone and Fold", "The phone draws the same conversation with touch rules: bubbles at radius 18, chat text at 16, actions behind a long press (with Select text), steps that open into a sheet, and a composer where Return adds a line and the model chip sits beside attach.")}
{row(spec("Chat header · profile", m_header("profile"), 420, 0), spec("Chat header · workgroup", m_header("workgroup"), 420, 0), spec("Empty thread", m_empty(), 300))}
{row(spec("User message · accent 12%, radius 18 4 18 18, long press for actions", phone(m_user("Can you summarize yesterday’s deploy logs?")), 420, 16), spec("Alpi message · rich text: heading, quote, list, code, routed model", phone(m_assistant()), 420, 16))}
{row(spec("Process block · one mono block at 12 pt like desktop, flush with the answer, in order; tap a step for its sheet", phone(m_process(m_reasoning(secs="3s"), m_tool("read_file", "deploy.log · 200 lines"), m_bucket("2 tool calls", 1), m_reasoning(True, "2s"), thinking("reading the log", 12, 20, 16, 12))), 420, 16), spec("Attachments · composer and message", m_attachment("deploy-report.pdf", "1.2 MB") + m_attachment("chart.png", "png · 240 KB", "message"), 420))}
{row(spec("Composer · idle", phone(m_composer()), 420, 0), spec("Composer · ready", phone(m_composer("Open a fix", "ready")), 420, 0))}
{row(spec("Composer · busy (Stop on the accent)", phone(m_composer("Open a fix", "busy")), 420, 0), spec("Jump to latest", m_jump(), 300))}
</div>"""
    return page("System · mobile conversation", 1280, 1400, body)


def m_post(name, color, text, seq, side="left"):
    radius = "4px 18px 18px 18px" if side == "left" else "18px 4px 18px 18px"
    align = "flex-start" if side == "left" else "flex-end"
    return (f'<div style="display: flex; flex-direction: column; align-items: {align}; gap: 6px; padding: 0 16px"><div style="display: flex; align-items: center; gap: 6px">{small_diamond(color)}{mono(name, 12, INK3, 500)}{mono(f"#{seq}", 12, INK3, 500)}{mono("1.2K · $0.01", 12, INK3, 500)}</div>'
            f'<div style="max-width: 90%; padding: 14px 16px; border-radius: {radius}; background: {mix(color, 0.11)}; font-size: 16px; line-height: 26.4px">{text}</div></div>')


def m_marker(variant, color, body, side="right"):
    base = WARNING if variant == "skip" else color
    pct = {"task": 0.18, "working": 0.14, "done": 0.18, "skip": 0.12}[variant]
    icon = {"task": dot(base, 6), "working": dot(base, ring=True), "done": ic("check", 12, base), "skip": ic("x", 12, base)}[variant]
    radius = "18px 4px 18px 18px" if side == "right" else "4px 18px 18px 18px"
    align = "flex-end" if side == "right" else "flex-start"
    return (f'<div style="display: flex; flex-direction: column; align-items: {align}; padding: 0 16px"><div style="max-width: 90%; padding: 14px 16px; border-radius: {radius}; background: {mix(base, pct)}">'
            f'<div style="display: flex; align-items: center; gap: 6px; margin-bottom: 6px; font-family: {MONO}; font-size: 12px; font-weight: 600; letter-spacing: 1.2px; color: {base}"><span style="width: 14px; display: inline-flex; justify-content: center">{icon}</span>{variant.upper()}</div>'
            f'<div style="font-size: 14px; line-height: 21px">{body}</div></div></div>')


def m_pipeline():
    seg = lambda icon, text, color=INK2, extra="": f'<span style="display: inline-flex; align-items: center; gap: 4px; {extra}">{icon}{mono(text, 12, color)}</span>'
    arrow = f'<span style="font-size: 11px; color: {INK4}; margin-right: 8px">›</span>'
    return (f'<div style="display: flex; align-items: center; gap: 8px; padding: 10px 16px; white-space: nowrap; overflow: hidden">'
            f'<span style="font-family: {MONO}; font-size: 11px; font-weight: 500; letter-spacing: 0.66px; text-transform: uppercase; color: {INK3}">Pipeline</span>'
            f'{seg(ic("check", 12, SUCCESS), "#intake")}{arrow}{seg(dot(AMBER), "#analyze", AMBER)}{arrow}{seg("", "#report", INK3)}{arrow}'
            f'{seg(ic("x", 12, DANGER), "#publish", DANGER, "padding: 2px 8px; border-radius: 999px; background: " + mix(DANGER_FILL, 0.09))}</div>')


def mobile_workgroup():
    body = f"""<div style="padding: 40px 48px; display: flex; flex-direction: column; gap: 24px; box-sizing: border-box">
{h1("Workgroups · phone and Fold", "Member posts left, hub right, tinted with the speaker accent. Meta is mono on the phone. Marker cards keep the four lifecycle states; skip always tints with the warning colour.")}
{spec("Pipeline strip · scrolls horizontally", phone(m_pipeline(), 560), 600, 0)}
{row(spec("Posts · member and hub", phone(m_post("builder", BUILDER, "Patched the retry loop; tests green locally.", 57) + m_post("alpi", AMBER, "Ship it behind the flag.", 58, "right")), 420, 16), spec("Markers · task and working", phone(m_marker("task", AMBER, "<strong>#onboarding-friction</strong> Find the top 3 drop-off points") + m_marker("working", AMBER, "Pulling funnel events…", "left")), 420, 16))}
{row(spec("Markers · done and skip", phone(m_marker("done", AMBER, "Top 3: email verify, invite, first prompt.") + m_marker("skip", AMBER, "Out of scope for this sprint.", "left")), 420, 16), spec("Workgroup composer · @ mention, no attach", phone(m_composer(workgroup=True)), 420, 0))}
</div>"""
    return page("System · mobile workgroups", 1280, 760, body)


CONVERSATION = {"desktop": desktop_conversation, "desktop_wg": desktop_workgroup, "mobile": mobile_conversation, "mobile_wg": mobile_workgroup}
