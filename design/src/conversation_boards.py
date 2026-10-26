from gen import ic as _ic, DANGER, DOC_ACCENT, EDGE, FIELD, FLOAT_EDGE, diamond, di as ic, identity_glyph, m_button, mi, mix, page, profile_mark
from desktop_boards import ELEV, HOVER, INK, INK2, INK3, INK4, LG_FLOAT, LINE, LINE2, MONO, PANE, RING_CTRL, SELECTED, SIDE, SM_FLOAT

AMBER = "#14110c"
BRAND = "#14110c"
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


def iconbtn(name, size=24, glyph=14, color=INK2):
    return (f'<button aria-label="{name}" style="width: {size}px; height: {size}px; border: 0; border-radius: 4px; background: transparent; display: inline-flex; '
            f'align-items: center; justify-content: center; padding: 0; color: {color}; cursor: pointer">{ic(name, glyph, color)}</button>')


def sep():
    return f'<span style="color: {INK4}; margin: 0 6px">·</span>'


def dot(color, size=8, ring=False):
    shadow = f"box-shadow: 0 0 0 4px {mix(color, 0.4)};" if ring else ""
    return f'<span style="width: {size}px; height: {size}px; border-radius: 999px; background: {color}; display: inline-block; flex-shrink: 0; {shadow}"></span>'


def meter(value, tail, pct, color=BRAND, percent=True):
    drawn = pct >= 0.01
    p = mono(f"{round(pct * 100)}%" if drawn else "—", 11) if percent else ""
    bar = (f'<span style="width: 56px; height: 5px; border-radius: 999px; background: {LINE}; overflow: hidden; display: inline-block"><span style="display: block; width: {pct * 100}%; height: 100%; background: {color}"></span></span>') if drawn else ""
    return f'<span style="display: inline-flex; align-items: center; gap: 8px">{mono(value, 11, INK2)}{mono(tail, 11)}{bar}{p}</span>'


def vsep():
    return f'<span style="width: 1px; height: 10px; background: {LINE2}; display: inline-block"></span>'



def d_user(text, accent=AMBER):
    return (f'<div style="display: flex; flex-direction: column; align-items: flex-end; gap: 4px">'
            f'<div style="max-width: 76%; padding: 12px 16px; border-radius: 4px; background: {SELECTED}; font-size: 15px; line-height: 1.65; color: {INK}">{text}</div>'
            f'<div style="display: flex; align-items: center; gap: 8px; color: {INK3}">{mono("2m", 11)}<span style="opacity: 0.4; display: inline-flex; margin-right: -5px">{iconbtn("pencil", 24, 14)}{iconbtn("copy", 24, 14)}</span></div></div>')


def d_assistant(body, meta=True, hover=True):
    footer = ""
    if meta:
        tip = (f'<span style="display: inline-flex; flex-direction: column; gap: 4px; margin-left: 8px; padding: 4px 8px; border-radius: 4px; background: {INK}; {SM_FLOAT}">'
               f'{mono("3.4K tokens · $0.0123", 11, PANE)}{mono("sonnet-4 · 12.4s", 11, INK4)}</span>')
        footer = (f'<div style="display: flex; align-items: center; gap: 8px; margin-top: 4px"><span style="display: inline-flex; margin-left: -7px; opacity: {1 if hover else 0.4}">{iconbtn("copy", 28, 14)}{iconbtn("refresh", 28, 14)}{iconbtn("volume", 28, 14)}{iconbtn("download", 28, 14)}</span>{mono("2m", 11)}{tip if hover else ""}</div>')
    return f'<div style="display: flex; flex-direction: column; gap: 8px"><div style="font-size: 15px; line-height: 1.65; letter-spacing: -0.003em; color: {INK}">{body}</div>{footer}</div>'


def code_inline(text):
    return f'<code style="font-family: {MONO}; font-size: 0.92em; background: {HOVER}; padding: 1px 5px; border-radius: 4px">{text}</code>'


def d_code_block(lang, code):
    return (f'<div style="margin: 12px 0; border: 0.5px solid {LINE}; border-radius: 4px; overflow: hidden">'
            f'<div style="display: flex; justify-content: space-between; padding: 8px 12px; background: {HOVER}; border-bottom: 0.5px solid {LINE}">{mono(lang, 11)}{mono("copy", 11)}</div>'
            f'<pre style="margin: 0; padding: 12px; font-family: {MONO}; font-size: 11px; line-height: 1.5; color: {INK}; background: {HOVER}">{code}</pre></div>')


def d_table():
    cells = [("job", "status", "time"), ("api-migrate", "timed out", "300s"), ("web-build", "lint error", "42s")]
    head = "".join(f'<th style="text-align: left; padding: 12px 14px; font-weight: 600; color: {INK2}; background: {SIDE}; border-bottom: 0.5px solid {LINE}">{c}</th>' for c in cells[0])
    body = "".join("<tr>" + "".join(f'<td style="padding: 12px 14px; border-top: 0.5px solid {LINE}; background: {PANE}">{c}</td>' for c in r) + "</tr>" for r in cells[1:])
    return f'<div style="margin: 12px 0; border: 0.5px solid {LINE2}; border-radius: 4px; overflow: hidden"><table style="width: 100%; border-collapse: collapse; font-size: 13px"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def d_reasoning(open_=False, streaming=False):
    caret = ic("chev-r", 14, INK3).replace('style="', 'style="transform: rotate(90deg); ' if open_ else 'style="', 1)
    peek = "" if open_ else f'<span style="flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap">{mono("Checking which jobs exited non-zero…", 11)}</span>'
    lines = ""
    if open_:
        body = "".join(f'<div style="font-family: {MONO}; font-size: 11px; line-height: 1.65; color: {INK3}">{t}</div>' for t in ("The user wants a summary of yesterday's deploys.", "Read the log, group by job, count exits.", "Two jobs failed; call them out first."))
        mask = "mask-image: linear-gradient(to bottom, transparent, black 28px); max-height: 116px; overflow: hidden;" if streaming else ""
        lines = f'<div style="margin-top: 8px; display: flex; flex-direction: column; gap: 8px; {mask}">{body}</div>'
    label_text = "thinking · 4s" if streaming else "thinking · 7s"
    return f'<div><div style="display: flex; align-items: center; gap: 8px">{mono(label_text, 11)}<span style="margin-left: -4px; display: inline-flex">{caret}</span>{peek}</div>{lines}</div>'


def d_tool(name, args, state="done"):
    color = {"running": BRAND, "done": INK3, "failed": DANGER_FILL}[state]
    name_color = DANGER if state == "failed" else INK
    arg_html = "".join(f'<span style="color: {INK4}">{k}=</span><span style="color: {INK2}; margin-right: 8px">{v}</span>' for k, v in args)
    trailer = ""
    if state == "running":
        trailer = f'<span style="display: inline-flex; gap: 2px; margin-left: 4px">{"".join(dot(BRAND, 3) for _ in range(3))}</span>'
    return (f'<div style="display: inline-flex; align-items: center; gap: 8px; padding: 2px 0; font-family: {MONO}; font-size: 11px; color: {INK2}">'
            f'{ic("chip", 14, color)}<span style="font-weight: 500; color: {name_color}">{name}</span><span style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis">{arg_html}</span>{trailer}</div>')


def d_bucket(text, failed=0, size=11, h=24, open_=False):
    fail = f'<span style="display: inline-flex; align-items: center; gap: 4px; margin-left: 4px">{ic("alert", 14, DANGER_FILL)}{mono(f"{failed} failed", size, DANGER)}</span>' if failed else ""
    chev = ic("chev-r", 14, INK3).replace("style=" + chr(34), "style=" + chr(34) + ("transform: rotate(90deg); " if open_ else ""), 1)
    return f'<div style="display: flex; align-items: center; gap: 8px; height: {h}px; padding: 0 12px">{mono(text, size)}<span style="margin-left: -4px; display: inline-flex">{chev}</span>{fail}</div>'


def d_attachment(name, sub, variant="composer"):
    bg = PANE if variant == "composer" else HOVER
    border = LINE2 if variant == "composer" else "transparent"
    box_bg = HOVER if variant == "composer" else PANE
    remove = iconbtn("x", 24, 14, INK3) if variant == "composer" else ""
    return (f'<div style="display: inline-flex; align-items: center; gap: 8px; padding: 8px 12px; border: 0.5px solid {border}; border-radius: 4px; background: {bg}; max-width: 280px">'
            f'<span style="width: 32px; height: 32px; border-radius: 4px; background: {box_bg}; display: inline-flex; align-items: center; justify-content: center">{ic("copy", 16, INK3)}</span>'
            f'<span style="display: flex; flex-direction: column; min-width: 0"><span style="font-size: 11px; color: {INK}">{name}</span>{mono(sub, 11)}</span>{remove}</div>')


def d_images():
    tile = lambda c: f'<div style="aspect-ratio: 4 / 3; border-radius: 4px; border: 0.5px solid {LINE}; background: linear-gradient(135deg, {mix(c, 0.35)}, {mix(c, 0.12)})"></div>'
    return f'<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; max-width: 420px">{tile(DOC_ACCENT)}{tile(AMBER)}</div>'


def d_peer():
    return (f'<div style="display: flex; flex-direction: column; align-items: flex-start; gap: 8px">'
            f'<div style="display: flex; align-items: center; gap: 8px; font-size: 11px; color: {INK3}">{profile_mark(DOC_ACCENT)}<span style="font-weight: 600; color: {INK}">@doc</span></div>'
            f'<div style="max-width: 76%; padding: 12px 16px; border-radius: 4px; background: {mix(DOC_ACCENT, 0.11)}; font-size: 15px; line-height: 1.65">The staging migration is safe to rerun; I added the missing index.</div></div>')


def d_ask_answered():
    return f'<div style="display: flex; align-items: center; gap: 8px; font-size: 13px; color: {INK}">{profile_mark(AMBER)}Use the staging database</div>'


def d_ask_missing():
    return (f'<div style="display: flex; flex-direction: column; gap: 4px; padding: 8px 12px; border: 1px solid {LINE}; border-radius: 4px">'
            f'<span style="font-size: 13px; color: {INK3}">Which environment should I target?</span>'
            f'<span style="font-family: {MONO}; font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase; color: {INK3}">∅ expired</span></div>')


def kbd(t):
    return f'<span style="padding: 1px 5px; border-radius: 4px; background: {HOVER}; border: 0.5px solid {LINE}; font-family: {MONO}; font-size: 11px; font-weight: 500; color: {INK2}">{t}</span>'


def d_send(state="idle", accent=AMBER):
    if state == "busy":
        return f'<button aria-label="Stop" style="width: 32px; height: 32px; border: 0; border-radius: 4px; background: {INK}; display: inline-flex; align-items: center; justify-content: center"><span style="width: 12px; height: 12px; background: {PANE}; border-radius: 2px"></span></button>'
    bg, fg = (accent, "#ffffff") if state == "ready" else (LINE, INK3)
    return f'<button aria-label="Send" style="width: 32px; height: 32px; border: 0; border-radius: 4px; background: {bg}; display: inline-flex; align-items: center; justify-content: center">{ic("up", 14, fg)}</button>'


def d_composer(text="", state="idle", hint=True, model=True, name="alpi", model_name="sonnet-4", effort=None, reason=None, reason_action=None, dim=False, placeholder=None):
    shown = placeholder or f"Message {name}…"
    value = f'<span style="font-size: 13px; line-height: 1.5; color: {INK}">{text}</span>' if text else f'<span style="font-size: 13px; line-height: 1.5; color: {INK3}">{shown}</span>'
    hints = f'<span style="display: inline-flex; align-items: center; gap: 8px; font-size: 11px; color: {INK3}"><span>{mono("@", 11, INK2)} mention</span><span style="display: inline-flex; gap: 4px; align-items: center">{kbd("⌘")}{kbd("↵")} send</span></span>' if hint else ""
    tail = f'<span style="flex: none; white-space: pre">{" · " + effort}</span>' if effort else ""
    label = (f'<span style="display: inline-flex; min-width: 0; max-width: 160px; font-family: {MONO}; font-size: 11px; color: {INK}">'
             f'<span style="min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap">{model_name}</span>{tail}</span>')
    picker = f'<span style="display: inline-flex; align-items: center; gap: 8px; height: 28px; padding: 0 12px; border-radius: 4px">{ic("sun", 14, INK3)}{label}{ic("chev-d", 14, INK3)}</span>' if model else ""
    fade = "opacity: 0.6;" if dim else ""
    why = ""
    if reason:
        from desktop_boards import button
        act = button(reason_action, "secondary", "sm") if reason_action else ""
        why = f'<div style="display: flex; align-items: center; gap: 12px; min-height: 28px"><span style="flex: 1; min-width: 0; font-size: 13px; font-weight: 500; color: {INK2}">{reason}</span>{act}</div>'
    return (f'<div style="display: flex; flex-direction: column; gap: 8px; padding: 16px 16px 12px; border-radius: 4px; background: {FIELD}">'
            f'<div style="min-height: 24px; {fade}">{value}</div>{why}'
            f'<div style="display: flex; align-items: center; gap: 8px; {fade}">{hints}<span style="flex: 1"></span>{iconbtn("clip", 28, 16)}{picker}{d_send(state)}</div></div>')


def d_mention(rows=None, empty=None):
    people = (("doc", DOC_ACCENT, ""), ("abby", "#c14580", "Abby · labs"), ("builder", BUILDER, "")) if rows is None else rows
    items = "".join(f'<div role="option" style="display: flex; align-items: center; gap: 8px; padding: 8px 12px; border-radius: 4px; {"background: " + SELECTED + ";" if i == 0 else ""} font-size: 13px; font-weight: 500">{profile_mark(c)}{n}'
                    + (f'<span style="font-size: 11px; font-weight: 400; color: {INK3}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis">{h}</span>' if h else "") + '</div>'
                    for i, (n, c, h) in enumerate(people))
    if empty:
        items = f'<div style="padding: 8px 12px; font-size: 13px; color: {INK2}">{empty}</div>'
    w = 260 if empty else 200
    return f'<div style="width: {w}px; padding: 8px; border-radius: 4px; background: {ELEV}; {SM_FLOAT}">{items}</div>'


def d_jump():
    return f'<span style="width: 32px; height: 32px; border-radius: 4px; background: {ELEV}; {SM_FLOAT}; display: inline-flex; align-items: center; justify-content: center">{ic("chev-d", 14, INK2)}</span>'


def d_header(kind="profile", w=1032):
    from brand_boards import app_crease
    from desktop_boards import wg_mark
    edge = max(32, (w - 920) // 2)
    if kind == "profile":
        glyph = identity_glyph("alpi", AMBER, 20)
        title = "alpi"
        meta = f'{mono("sonnet-4", 11, INK2)}{vsep()}{meter("12.4K", "/200K", 0.06)}{vsep()}{meter("$0.42", "/$5.00", 0.08)}'
        right = f'<span style="display: inline-flex; align-items: center; gap: 8px; height: 32px; padding: 0 12px; font-size: 13px; font-weight: 500; color: {INK2}">Sessions{ic("chev-d", 14, INK2)}</span>{iconbtn("more", 32, 16)}'
    else:
        glyph = wg_mark(AMBER, 20)
        title = "launch-crew"
        meta = f'<span style="display: inline-flex; align-items: center; gap: 4px; font-size: 11px"><span style="color: {INK3}">hub</span>{profile_mark(AMBER)}{mono("@alpi", 11, INK2)}</span>{vsep()}<span style="font-size: 11px"><span style="color: {INK3}">members</span> {mono("4", 11, INK2)}</span>{vsep()}{meter("$1.20", "/$10.00", 0.12)}'
        right = f'<span style="display: inline-flex; align-items: center; gap: 8px; height: 28px; padding: 0 12px; font-size: 11px; font-weight: 500; color: {INK}"><span style="width: 9px; height: 9px; box-sizing: border-box; border-radius: 50%; border: 1.5px solid #8c8c8c; display: inline-block"></span>Tasks{ic("chev-d", 14, INK2)}</span>{iconbtn("more", 32, 16)}'
    return (f'<div style="position: relative; display: flex; align-items: flex-start; justify-content: space-between; padding: 30px {edge}px 18px; background: {PANE}; border-bottom: 0.5px solid {LINE}">'
            f'<div style="display: flex; flex-direction: column; gap: 8px"><div style="display: flex; align-items: center; gap: 12px">{glyph}{app_crease(title, 28, AMBER, PANE, track="-0.018em")}</div>'
            f'<div style="display: flex; align-items: center; gap: 12px; white-space: nowrap; color: {INK3}">{meta}</div></div><div style="display: flex; align-items: center; gap: 2px; height: 32px; margin-top: -2px">{right}</div>'
            f'</div>')


def d_skeleton():
    from loading_studies import BREATH, bone
    return (f'{BREATH}<div style="display: flex; flex-direction: column; gap: 9px">{bone("88%", 13, 2, 0)}{bone("100%", 13, 2, 1)}{bone("62%", 13, 2, 2)}</div>'
            f'<div style="align-self: flex-end; min-width: 220px; max-width: 70%; padding: 12px 16px; border-radius: 4px; background: {HOVER}">{bone("160px", 13, 2, 3)}</div>')


TOOL_ICONS = {"read_file": "file", "grep": "search", "shell": "terminal", "web_fetch": "globe", "memory": "chip", "send_message": "link"}


def d_step(name, summary, dur, state="done", body="", size=11, h=24, open_=None):
    icon = TOOL_ICONS.get(name, "chip")
    color = {"done": INK3, "failed": DANGER_FILL, "running": BRAND}[state]
    status = {"done": mono(dur, size), "failed": mono(f"failed · {dur}", size, DANGER), "running": mono(f"{dur} …", size, BRAND)}[state]
    expanded = bool(body) if open_ is None else open_
    chev = ic("chev-r", 14, INK3).replace("style=" + chr(34), "style=" + chr(34) + ("transform: rotate(90deg); " if expanded else ""), 1)
    head = (f'<div style="display: flex; align-items: center; gap: 8px; height: {h}px; padding: 0 12px">'
            f'{ic(icon, 14, color)}{mono(name, size, DANGER if state == "failed" else INK2)}<span style="margin-left: -4px; display: inline-flex">{chev}</span>'
            f'<span style="flex: 1; min-width: 0; font-family: {MONO}; font-size: {size}px; color: {INK3}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis">{summary}</span>{status}</div>')
    return f'<div style="display: flex; flex-direction: column; gap: 4px">{head}{body}</div>'


def step_body(lines, size=11):
    return f'<div style="margin: 4px 12px 4px 34px; padding: 12px; border-radius: 4px; background: {SIDE}; border: 0.5px solid {LINE}; font-family: {MONO}; font-size: {size}px; line-height: 1.65; color: {INK2}">{"<br>".join(lines)}</div>'


def req_btn(text, variant="ghost"):
    bg, fg = {"primary": (INK, PANE), "secondary": (SELECTED, INK), "ghost": ("transparent", INK2)}[variant]
    return f'<span style="display: inline-flex; align-items: center; height: 28px; padding: 0 12px; border-radius: 4px; font-size: 11px; font-weight: 500; white-space: nowrap; background: {bg}; color: {fg}">{text}</span>'


def inline_request(who="@alpi", command="rm -rf dist &amp;&amp; npm run build", seconds=42):
    return (f'<div style="display: flex; flex-direction: column; gap: 8px; padding: 12px 16px; border-radius: 4px; {RING_CTRL}; background: var(--card, #f4f4f4)">'
            f'<span style="display: flex; align-items: center; gap: 8px; font-size: 13px; font-weight: 600">{ic("alert", 14, WARNING)}<span style="flex: 1">{who} wants to run a command</span>{mono(f"auto-deny in {seconds}s", 11)}</span>'
            f'<span style="font-family: {MONO}; font-size: 11px; line-height: 1.65; color: {INK}">{command}</span>'
            f'<span style="display: flex; flex-wrap: wrap; gap: 8px">{req_btn("Deny")}{req_btn("Allow once", "primary")}{req_btn("Allow this session")}{req_btn("Always allow")}</span></div>')


def inline_ask(question="Which lab should I book with?", choices=("Quest · Main St", "Labcorp · 5th Ave"), seconds=88):
    return (f'<div style="display: flex; flex-direction: column; gap: 8px; padding: 12px 16px; border-radius: 4px; {RING_CTRL}; background: var(--card, #f4f4f4)">'
            f'<span style="display: flex; align-items: center; gap: 8px; font-size: 13px; font-weight: 600">{ic("sparkle", 14, BRAND)}<span style="flex: 1">{question}</span>{mono(f"auto-cancel in {seconds}s", 11)}</span>'
            f'<span style="display: flex; flex-wrap: wrap; gap: 8px">{"".join(req_btn(c, "secondary") for c in choices)}{req_btn("Type your own…", "ghost")}</span></div>')


def reasoning_mark(glyph=14):
    import folds
    return folds.fold("shield", DOC_ACCENT, glyph)


def reasoning_label(text, size):
    return f'<span style="font-size: {size}px; font-weight: 500; color: color-mix(in srgb, {DOC_ACCENT} 50%, {INK})">{text}</span>'


def d_reasoning_label(text, size):
    return f'<span style="font-size: {size}px; font-weight: 500; color: {INK3}">{text}</span>'


def thinking(peek="reading the deploy log", size=12, h=22, pad=10, glyph=14, label=None):
    label = label or size + 1
    return (f'<div style="display: flex; align-items: center; gap: 10px; height: {h}px; padding: 0 {pad}px">{reasoning_mark(glyph)}{reasoning_label("Thinking…", label)}'
            f'<span style="font-size: {label}px; font-style: italic; color: {INK3}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis">{peek}</span></div>')


def d_thinking(peek="reading the deploy log", size=11, h=24, pad=12, glyph=14, label=None):
    label = label or 13
    return (f'<div style="display: flex; align-items: center; gap: 8px; height: {h}px; padding: 0 {pad}px">{reasoning_mark(glyph)}{d_reasoning_label("Thinking…", label)}'
            f'<span style="font-size: {label}px; font-style: italic; color: {INK3}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis">{peek}</span></div>')


def thought(open_=False, size=12, h=22, secs="7s", chev=INK3, pad=10, glyph=14, rule=(2, 14, 12), label=None, lines=("The user wants a summary of yesterday’s deploys.", "Read the log, group by job, count exits.", "Two jobs failed; call them out first.")):
    head = (f'<div style="display: flex; align-items: center; gap: 10px; height: {h}px; padding: 0 {pad}px">{reasoning_mark(glyph)}{reasoning_label(f"Thought for {secs}", label or size + 1)}'
            f'<span style="margin-left: auto">{_ic("chev-d" if open_ else "chev-r", 12, chev)}</span></div>')
    if not open_:
        return head
    body = "".join(f'<div style="font-family: {MONO}; font-size: {size}px; line-height: 1.65; color: {INK2}">{t}</div>' for t in lines)
    return head + f'<div style="display: flex; flex-direction: column; gap: 4px; margin: 4px 0 4px {rule[1]}px; padding-left: {rule[2]}px; border-left: {rule[0]}px solid {LINE}">{body}</div>'


def d_thought(open_=False, size=11, h=24, secs="7s", chev=INK3, pad=12, glyph=14, rule=(2, 4, 12), label=None, lines=("The user wants a summary of yesterday’s deploys.", "Read the log, group by job, count exits.", "Two jobs failed; call them out first.")):
    chev_html = ic("chev-r", 14, chev).replace("style=" + chr(34), "style=" + chr(34) + ("transform: rotate(90deg); " if open_ else ""), 1)
    head = (f'<div style="display: flex; align-items: center; gap: 8px; height: {h}px; padding: 0 {pad}px">{reasoning_mark(glyph)}{d_reasoning_label(f"Thought for {secs}", label or 13)}'
            f'<span style="margin-left: -4px; display: inline-flex">{chev_html}</span></div>')
    if not open_:
        return head
    body = "".join(f'<div style="font-family: {MONO}; font-size: {size}px; line-height: 1.65; color: {INK2}">{t}</div>' for t in lines)
    return head + f'<div style="display: flex; flex-direction: column; gap: 8px; margin: 4px 0 4px {rule[1]}px; padding: 4px 12px 4px {rule[2]}px; border-left: {rule[0]}px solid {LINE}">{body}</div>'


def process(*rows, gap=2):
    return f'<div style="display: flex; flex-direction: column; gap: {gap}px; margin-left: -12px">{"".join(rows)}</div>'


def desktop_conversation():
    body = f"""<div style="padding: 40px 48px; display: flex; flex-direction: column; gap: 24px; box-sizing: border-box">
{h1("Conversation · desktop", "Messages, alpi’s process and the composer as ChatPane paints them. The user writes in a tinted bubble; alpi answers full width in sans. Reasoning and tool steps are alpi’s process: one mono block at 11 px, in the order they happened, 8 px above the answer; every row opens with one chevron after its label that turns 90°. Both footers keep a faint time, with the action row flush with the bubble edge; usage lives in a tooltip on the time. Turns sit 32 px apart. The header controls centre on the title line; a usage bar below 1 % is not drawn and its figure reads —.")}
{spec("Chat header · profile", d_header("profile", 1184), 1184, 0)}
{spec("Chat header · workgroup", d_header("workgroup", 1184), 1184, 0)}
{row(spec("User message · neutral selected tone, radius 4, faint time then actions flush with the bubble’s right edge, on hover or focus within", d_user("Can you summarize yesterday’s deploy logs and flag anything that failed?"), 580), spec("Peer reply · peer accent 11%, radius 6 14 14 14", d_peer(), 580))}
{spec("Alpi message · markdown body, actions flush with the left edge then the faint time, on hover or focus within and at rest on the last message, usage in a tooltip on the time", d_assistant("<strong>Deploy summary</strong>: 14 jobs ran; 2 failed.<ul style='margin: 8px 0; padding-left: 22px'><li>" + code_inline("api-migrate") + " timed out after 300s</li><li>" + code_inline("web-build") + " hit a lint error</li></ul>" + d_code_block("bash", "alpi logs api-migrate --tail 50") + d_table() + "Want me to open a fix?"), 1184)}
{row(spec("Process block · collapsed: the thinking row leads with the profile’s object, tool rows in mono, 24 px rows 2 px apart, in order", process(d_thought(secs="3s"), d_bucket("2 tool calls")), 380), spec("Process block · streaming: the running step and Thinking… (static under reduced motion)", process(d_thought(secs="3s"), d_step("read_file", "deploy.log · first 200 lines", "0.2s"), d_step("web_fetch", "status.example.com", "3s", "running"), d_thinking()), 380), spec("Process block · opened: reasoning in mono, spans between the steps", process(d_thought(True, secs="3s", lines=("The user wants yesterday’s deploys.", "Read the log first.")), d_step("read_file", "deploy.log · first 200 lines", "0.2s"), d_thought(secs="2s"), d_step("grep", "3 matches for exit=1", "0.1s")), 380))}
{row(spec("Process block · steps open to arguments and output; failures open themselves", process(d_bucket("+3 previous tool calls", 1), d_step("shell", "npm run lint", "4.1s", "failed", step_body(["$ npm run lint", '<span style="color: #c14545">src/app.ts:14  no-unused-vars</span>', "1 error, 0 warnings"])), d_step("grep", "3 matches for exit=1", "0.1s")), 580), spec("Inline approval · the open chat asks in the flow on a card with an ink-4 ring; one primary action and three ghost alternatives; a question uses the same card", inline_request() + inline_ask(), 580))}
{spec("Load skeleton · after 450 ms", d_skeleton(), 580)}
{row(spec("Attachments · composer and message variants", d_attachment("deploy-report.pdf", "1.2 MB") + d_attachment("chart.png", "png · 240 KB", "message"), 380), spec("Produced images · 2-column grid, 4:3", d_images(), 380), spec("Ask user · answered and unanswered", d_ask_answered() + d_ask_missing(), 380))}
{row(spec("Composer · idle", d_composer(), 580), spec("Composer · ready to send", d_composer("Open a fix for the lint error", "ready"), 580))}
{row(spec("Composer · busy (Stop)", d_composer("Open a fix for the lint error", "busy"), 580), spec("Mention popover · peer alias caption, 1 px edge ring · jump to latest", row(d_mention(), d_jump()), 580))}
{row(spec("Composer · model label capped at 160 px with an ellipsis, the effort stays after it", d_composer(model_name="claude-sonnet-4-5-20251001-extended", effort="medium"), 580), spec("Composer · paused: only the input dims; the banner above is the one place that says it and offers Resume", d_composer(name="doc", dim=True, placeholder="Paused — resume to chat"), 580))}
{row(spec("Composer · offline: the placeholder stays normal, the reason line is the only offline text", d_composer(name="doc", dim=True, reason="Daemon offline — sending paused"), 580), spec("Mention popover · empty rows: no peers, no match", d_mention(empty="No peers yet. Add one in Connections.") + d_mention(empty="No peer matches @zz"), 580))}
</div>"""
    return page("System · desktop conversation", 1280, 3040, body)



def d_post(name, color, text, seq, side="left", cost="1.2K · $0.01"):
    radius = "4px"
    meta_items = [f'<span style="display: inline-flex; align-items: center; gap: 8px">{profile_mark(color)}<span style="font-weight: 600; color: {INK}">{name}</span></span>', mono(f"#{seq}", 11), mono(cost, 11)]
    meta = "".join(meta_items if side == "left" else list(reversed(meta_items)))
    align = "flex-start" if side == "left" else "flex-end"
    return (f'<div style="display: flex; flex-direction: column; align-items: {align}; gap: 8px"><div style="display: flex; align-items: center; gap: 8px; font-size: 11px; color: {INK3}">{meta}</div>'
            f'<div style="max-width: 76%; padding: 12px 16px; border-radius: {radius}; background: {mix(color, 0.11)}; font-size: 15px; line-height: 1.65">{text}</div></div>')


def d_marker(variant, color, body, side="right"):
    tints = {"task": (mix(color, 0.18), color), "working": (mix(color, 0.14), color), "done": (mix(color, 0.18), color), "blocked": (mix(DANGER_FILL, 0.12), DANGER), "skipped": (mix(WARNING, 0.12), WARNING_TEXT), "skip": (mix(color, 0.11), color)}
    bg, ey = tints[variant]
    icon = {"task": dot(ey), "working": dot(ey, ring=True), "done": ic("check", 11, ey), "blocked": ic("x", 11, ey), "skipped": ic("x", 11, ey), "skip": ic("x", 11, ey)}[variant]
    radius = "4px"
    align = "flex-end" if side == "right" else "flex-start"
    eyebrow_color = ey if variant in ("blocked", "skipped") else f"color-mix(in srgb, {ey} 75%, {INK})"
    return (f'<div style="display: flex; flex-direction: column; align-items: {align}"><div style="max-width: 76%; min-width: 320px; padding: 16px; border-radius: {radius}; background: {bg}">'
            f'<div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px; font-family: {MONO}; font-size: 11px; font-weight: 600; letter-spacing: 0.08em; color: {eyebrow_color}">{icon}{variant.upper()}</div>'
            f'<div style="font-size: 15px; line-height: 1.5; color: {INK}">{body}</div></div></div>')


def d_pipeline():
    from wg_strip_studies import d_proposed
    return d_proposed()


def d_before_run():
    from wg_strip_studies import d_before_run as drawn
    return drawn()


def m_before_run():
    from wg_strip_studies import m_before_run as drawn
    return drawn()


def d_pipeline_detail():
    from wg_strip_studies import BLOCKED, STATES, blocked_trigger, excerpt, hover_pair, repair_trigger
    from wg_settings_studies import labelled
    from notif_studies import stack
    return stack(
        labelled("Hover a phase · task, owner, cost; click jumps", hover_pair()),
        labelled("Routed repair · owner, then → the member the hub added", stack(excerpt(STATES, "vr", "lingua"), repair_trigger("vrh"), gap=8)),
        labelled("Blocked · the word in red, nothing ripples", stack(excerpt(BLOCKED, "vb"), blocked_trigger(), gap=8)),
        gap=18,
    )


def d_wg_composer():
    hint = f'<span style="font-size: 11px; color: {INK3}"><span style="color: {INK3}">→</span> {identity_glyph("alpi", AMBER, 16)} {mono("@alpi", 11, INK2)} formulates as {mono("#task #&lt;slug&gt;", 11, INK2)}</span>'
    return (f'<div style="display: flex; flex-direction: column; gap: 8px; padding: 16px 16px 12px; border-radius: 4px; background: {FIELD}">'
            f'<span style="font-size: 13px; color: {INK3}">Send a message — use @&lt;peer&gt; or #task #&lt;slug&gt; to open</span>'
            f'<div style="display: flex; align-items: center; gap: 6px">{hint}<span style="flex: 1"></span>{kbd("⌘")}{kbd("↵")}{d_send()}</div></div>')


def desktop_workgroup():
    body = f"""<div style="padding: 40px 48px; display: flex; flex-direction: column; gap: 24px; box-sizing: border-box">
{h1("Workgroups · desktop", "Posts from members sit on the left, the hub on the right, each tinted with its speaker's accent at 11%. Marker cards record the #task lifecycle; the pipeline strip under the header names who owns and works each phase.")}
{spec("Pipeline strip · each phase with its owner, the header counts the same phases", d_pipeline(), 1184)}
{spec("Pipeline strip · detail, routed repair and block", d_pipeline_detail(), 1184)}
{spec("Pipeline strip · before the run: with one pipeline the chain is drawn from the row at once; with several, skeleton chips until the run arrives", d_before_run(), 1184)}
{spec("Posts · member (left) and hub (right)", d_post("builder", BUILDER, "Patched the retry loop; tests green locally.", 57) + d_post("alpi", AMBER, "Good. Ship it behind the flag and report back.", 58, "right"), 1184)}
{row(spec("Marker · task", d_marker("task", AMBER, "<strong>#onboarding-friction</strong> Find the top 3 drop-off points<br>Use last week’s funnel data."), 580), spec("Marker · working (pulsing dot)", d_marker("working", AMBER, "Pulling funnel events…", "left"), 580))}
{row(spec("Marker · done", d_marker("done", AMBER, "Top 3: email verify, workspace invite, first prompt."), 580), spec("Marker · skip", d_marker("skip", AMBER, "Out of scope for this sprint.", "left"), 580))}
{row(spec("Marker · done → blocked", d_marker("blocked", AMBER, "Needs a production API key nobody has."), 580), spec("Marker · done → skipped", d_marker("skipped", AMBER, "Preempted by the incident review."), 580))}
{spec("Workgroup composer · no attach, no model picker", d_wg_composer(), 1184)}
</div>"""
    return page("System · desktop workgroups", 1280, 2260, body)



def phone(inner, w=390):
    return f'<div style="width: {w}px; box-sizing: border-box; display: flex; flex-direction: column; gap: 14px">{inner}</div>'


def m_stamp(text="2m"):
    return f'<span style="font-family: {MONO}; font-size: 12px; font-weight: 500; line-height: 1; color: {INK3}">{text}</span>'


def m_user(text, accent=AMBER, pane=False):
    return (f'<div style="display: flex; flex-direction: column; align-items: flex-end; gap: 4px; padding: 0 16px">'
            f'<div style="max-width: {76 if pane else 82}%; padding: 12px 16px; border-radius: 4px; background: {SELECTED}; font-size: 16px; line-height: 26.4px">{text}</div>'
            f'{m_stamp()}</div>')


def m_assistant():
    code = (f'<div style="margin: 8px 0; border-radius: 4px; border: 0.5px solid {LINE}; background: {HOVER}; overflow: hidden"><div style="padding: 6px 10px; border-bottom: 0.5px solid {LINE}">{mono("bash", 11)}</div>'
            f'<div style="padding: 12px; font-family: {MONO}; font-size: 14px; line-height: 21px">alpi logs api-migrate</div></div>')
    quote = f'<div style="margin: 6px 0; padding-left: 10px; border-left: 3px solid {INK}; opacity: 0.85">Two jobs failed overnight.</div>'
    lst = "".join(f'<div style="display: flex; gap: 8px"><span>•</span><span>{t}</span></div>' for t in ("api-migrate timed out", "web-build hit a lint error"))
    return (f'<div style="padding: 0 16px; font-size: 16px; line-height: 26.4px; color: {INK}"><div style="font-weight: 600; margin-top: 4px; margin-bottom: 4px">Deploy summary</div>'
            f'{quote}<div style="display: flex; flex-direction: column; gap: 4px; margin: 6px 0; padding-left: 20px">{lst}</div>{code}Want me to open a fix?'
            f'<div style="margin-top: 4px; display: flex; gap: 10px; align-items: center">{m_stamp()}{mono("⇢ sonnet-4", 11)}</div></div>')


def m_more_button():
    return f'<span role="button" aria-label="Message actions" style="width: 44px; height: 44px; display: inline-flex; align-items: center; justify-content: center">{mi("more", 16, INK3)}</span>'


def m_agent_text(text, stamp="2m", more=False):
    foot = f'<div style="display: flex; align-items: center; justify-content: space-between">{m_stamp(stamp)}{m_more_button()}</div>' if more else m_stamp(stamp)
    return f'<div style="padding: 0 16px; display: flex; flex-direction: column; gap: 4px"><div style="font-size: 16px; line-height: 26.4px; color: {INK}">{text}</div>{foot}</div>'


def m_reasoning(open_=False, secs="7s"):
    return thought(open_, 12, 20, secs, INK3, 16, 12, (1, 23, 12), label=12)


def m_tool(name, args, state="done"):
    color = {"running": BRAND, "done": INK3, "failed": DANGER_FILL}[state]
    return (f'<div style="display: flex; align-items: center; gap: 8px; height: 20px; padding: 0 16px">{mi(TOOL_ICONS.get(name, "chip"), 12, color)}{mono(name, 12, DANGER if state == "failed" else INK2)}'
            f'<span style="flex: 1; min-width: 0; font-family: {MONO}; font-size: 12px; color: {DANGER if state == "failed" else INK3}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis">{args}</span>{mi("chev-r", 12, INK4)}</div>')


def m_process(*rows):
    return f'<div style="display: flex; flex-direction: column; gap: 4px">{"".join(rows)}</div>'


def m_bucket(text, failed=0, open_=False):
    chev = mi("chev-d", 12, INK3) if open_ else mi("chev-d", 12, INK3).replace("style=" + chr(34), "style=" + chr(34) + "transform: rotate(-90deg); ", 1)
    fail = f'<span style="display: inline-flex; align-items: center; gap: 4px">{mi("alert", 12, DANGER_FILL)}{mono(f"{failed} failed", 12, DANGER)}</span>' if failed else ""
    return f'<div style="display: flex; align-items: center; gap: 8px; height: 20px; padding: 0 16px">{chev}{mono(text, 12)}{fail}</div>'


CHIP = "display: inline-flex; align-items: center; gap: 6px; min-height: 36px; padding: 0 12px; border-radius: 4px; background: rgba(20,20,20,0.06); box-sizing: border-box"


def m_model_chip(text="sonnet-4 · medium"):
    model, _, effort = text.partition(" · ")
    tail = f'<span style="flex-shrink: 0; white-space: pre">{" · " + effort}</span>' if effort else ""
    return (f'<span role="button" aria-label="Model and effort: {text}" style="{CHIP}; min-width: 0">{mi("sparkle", 12, INK3)}<span style="display: inline-flex; min-width: 0; font-size: 14px; color: {INK2}">'
            f'<span style="min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap">{model}</span>{tail}</span>{mi("chev-d", 12, INK3)}</span>')


def m_mention_chip():
    return f'<span role="button" aria-label="Mention a peer" style="{CHIP}; flex-shrink: 0"><span style="font-family: {MONO}; font-size: 14px; color: {INK3}">@</span><span style="font-size: 14px; color: {INK2}">mention</span></span>'


def m_attachment(name, sub, variant="composer"):
    bg = PANE if variant == "composer" else HOVER
    border = LINE2 if variant == "composer" else "transparent"
    remove = mi("x", 14, INK3) if variant == "composer" else ""
    return (f'<div style="display: inline-flex; align-items: center; gap: 8px; padding: 6px 10px; border-radius: 4px; background: {bg}; border: 0.5px solid {border}; max-width: 240px">'
            f'<span style="width: 32px; height: 32px; border-radius: 4px; background: {HOVER}; display: inline-flex; align-items: center; justify-content: center">{mi("copy", 16, INK3)}</span>'
            f'<span style="display: flex; flex-direction: column"><span style="font-size: 12px">{name}</span>{mono(sub, 11)}</span>{remove}</div>')


def m_composer(text="", state="idle", workgroup=False, name="alpi", chip="sonnet-4 · medium", accent=AMBER, placeholder="", mention=None, resume=False):
    paused = state in ("offline", "paused")
    shown = placeholder or {"offline": "Daemon unreachable — sending paused", "paused": "Paused — resume to chat"}.get(state, f"Message @{name}…")
    value = f'<span style="font-size: 16px; line-height: 24px">{text}</span>' if text else f'<span style="font-size: 16px; line-height: 24px; color: {INK2 if paused else INK3}">{shown}</span>'
    dim = (lambda inner: f'<span style="display: inline-flex; min-width: 0; opacity: 0.45">{inner}</span>') if paused else (lambda inner: inner)
    box = lambda inner, bg: f'<span style="width: 36px; height: 36px; border-radius: 4px; background: {bg}; display: inline-flex; align-items: center; justify-content: center">{inner}</span>'
    if state == "busy":
        send = box('<span style="width: 12px; height: 12px; background: #141414; border-radius: 2px"></span>', accent)
    elif state == "ready":
        send = box(mi("up", 14, "#141414"), accent)
    else:
        send = box(mi("up", 16, INK3), LINE)
    clip = "" if workgroup else dim(f'<span style="width: 36px; height: 36px; display: inline-flex; align-items: center; justify-content: center">{mi("clip", 20, INK3)}</span>')
    model = "" if workgroup else dim(m_model_chip(chip))
    mention_html = dim(m_mention_chip()) if (workgroup if mention is None else mention) else ""
    controls = f'<div style="display: flex; align-items: center; gap: 8px">{mention_html}{model}<span style="flex: 1"></span>{clip}{dim(send)}</div>'
    edge = f"border: 2px solid {EDGE};" if paused else "border: 2px solid transparent;"
    resume_html = f'<div style="display: flex; justify-content: flex-end; padding-top: 8px">{m_button("Resume profile", "secondary", "lg")}</div>' if resume else ""
    return (f'<div style="padding: 8px 16px; border-top: 0.5px solid {LINE}; background: {PANE}"><div style="display: flex; flex-direction: column; gap: 8px; padding: 12px 14px 8px; box-sizing: border-box; border-radius: 4px; {edge} background: var(--field)">'
            f'{value}{controls}</div>{resume_html}</div>')


def m_header(kind="profile"):
    from brand_boards import app_crease
    from desktop_boards import wg_mark
    glyph = identity_glyph("alpi", AMBER, 20) if kind == "profile" else wg_mark(AMBER, 20)
    title = "alpi" if kind == "profile" else "launch-crew"
    meta = f'{mono("sonnet-4", 11, INK2)} {meter("12.4K", "/200K", 0.06, BRAND, False)}' if kind == "profile" else f'{mono("hub", 11)} {profile_mark(AMBER)} {mono("@alpi · 4 members", 11)}'
    return (f'<div style="position: relative; display: flex; align-items: flex-start; gap: 10px; padding: 6px 16px 8px; border-bottom: 0.5px solid {LINE}; background: {PANE}">{mi("back", 20, INK2)}'
            f'<div style="flex: 1; display: flex; flex-direction: column; gap: 1px"><div style="display: flex; align-items: center; gap: 6px">{glyph}{app_crease(title, 28, AMBER, PANE, track="-0.018em")}</div><div style="display: flex; align-items: center; gap: 6px">{meta}</div></div>'
            f'{mi("clock", 20, INK2)}{mi("more", 20, INK2)}</div>')


def m_jump():
    return f'<span style="display: inline-flex; align-items: center; gap: 8px; height: 36px; padding: 0 14px; border-radius: 4px; background: {PANE}; {FLOAT_EDGE}; font-size: 12px; font-weight: 500; color: {INK2}">{mi("chev-d", 14, INK2)}Latest</span>'


def m_empty():
    from gen import m_empty_state
    return m_empty_state("Start a new thread", "sonnet-4", mark=identity_glyph("alpi", AMBER, 72), mono_detail=True, hero=True)


def m_mention_popover(items=(), token="zz"):
    from gen import pill
    rows = "".join(
        f'<div style="display: flex; align-items: center; gap: 10px; min-height: 44px; padding: 0 14px; border-top: {"0.5px solid " + LINE if i else "0"}">'
        f'{profile_mark(c, 16)}<span style="flex: 1; font-family: {MONO}; font-size: 14px; color: {INK}">@{n}</span>{pill("hub", tone="success") if hub else ""}'
        f'<span style="font-family: {MONO}; font-size: 12px; color: {INK3}">{model}</span></div>' for i, (n, c, hub, model) in enumerate(items))
    if not items:
        rows = f'<div style="min-height: 44px; padding: 0 16px; display: flex; align-items: center; font-size: 14px; color: {INK3}">No peer matches “{token}”</div>'
    return f'<div style="margin: 0 16px 8px; border-radius: 4px; background: {PANE}; {FLOAT_EDGE}; overflow: hidden">{rows}</div>'


def m_failure_row(label, action=""):
    act = f'<span role="button" style="min-width: 44px; min-height: 44px; padding: 0 10px; box-sizing: border-box; display: inline-flex; align-items: center; justify-content: center; font-weight: 600; font-size: 12px; color: #b73737">{action}</span>' if action else ""
    return (f'<div style="display: flex; align-items: center; gap: 8px; min-height: 44px; padding: 0 16px">{mi("alert", 14, DANGER_FILL)}'
            f'<span style="flex: 1; font-size: 12px; color: #b73737">{label}</span>{act}</div>')


def m_chat_states():
    from gen import m_banner
    sentence = lambda inner: f'<div style="padding-bottom: 8px">{inner}</div>'
    failures = m_failure_row("Message failed to send.", "Retry") + m_failure_row("@alpi didn’t respond in 60s.", "Retry") + m_failure_row("shell · exit 1")
    paused = m_banner("<b style=\"font-weight: 600; color: #141414\">This profile is paused.</b> You can read the history.", "Resume", "warning")
    offline = m_banner("Daemon unreachable. Reconnecting…", "Retry", "danger")
    return phone(paused + offline + failures + m_composer(state="paused", mention=True), 390)


def mobile_conversation():
    body = f"""<div style="padding: 40px 48px; display: flex; flex-direction: column; gap: 24px; box-sizing: border-box">
{h1("Conversation · phone and Fold", "The phone draws the same conversation with touch rules: bubbles at radius 4, chat text at 16, actions behind a long press (with Select text), steps that open into a sheet, and a composer where Return adds a line and the model chip sits beside attach.")}
{row(spec("Chat header · profile", m_header("profile"), 420, 0), spec("Chat header · workgroup", m_header("workgroup"), 420, 0), spec("Empty thread", m_empty(), 300))}
{row(spec("User message · neutral selected tone, radius 4, long press for actions", phone(m_user("Can you summarize yesterday’s deploy logs?")), 420, 16), spec("Alpi message · rich text: heading, quote, list, code, routed model", phone(m_assistant()), 420, 16))}
{row(spec("Process block · the thinking row leads with the profile’s object, tool rows in mono at 12 pt, flush with the answer, in order; tap a step for its sheet", phone(m_process(m_reasoning(secs="3s"), m_tool("read_file", "deploy.log · 200 lines"), m_bucket("2 tool calls", 1), m_reasoning(True, "2s"), thinking("reading the log", 12, 20, 16, 12, label=12))), 420, 16), spec("Attachments · composer and message", m_attachment("deploy-report.pdf", "1.2 MB") + m_attachment("chart.png", "png · 240 KB", "message"), 420))}
{row(spec("Composer · idle", phone(m_composer()), 420, 0), spec("Composer · ready", phone(m_composer("Open a fix", "ready")), 420, 0))}
{row(spec("Composer · busy (Stop on the accent)", phone(m_composer("Open a fix", "busy")), 420, 0), spec("Jump to latest · floating, edged in the edge ink", m_jump(), 300))}
{row(spec("Composer · daemon unreachable (controls dim, the reason stays readable on an edged well)", phone(m_composer(state="offline")), 420, 0), spec("Composer · paused (no Resume here; the banner above is the one place that offers it)", phone(m_composer(state="paused")), 420, 0))}
{row(spec("Mention · 44 pt rows on the composer’s 16 pt edge, scrolls past four", phone(m_mention_popover((("mira", AMBER, True, "deepseek-v4.1"), ("morpheus", BUILDER, False, "sonnet-4"), ("maya", DOC_ACCENT, False, "gpt-5")), "m") + m_composer(workgroup=True, text="@m", mention=True)), 420, 0), spec("Mention · no match says so", phone(m_mention_popover() + m_composer(workgroup=True, text="@zz", mention=True)), 420, 0))}
{row(spec("Banners and failures · paused is the warning banner with Resume; each failure is one row: icon, sentence, Retry", m_chat_states(), 420, 0), spec("Last agent message · the visible ‘…’ opens the same actions as a long press", phone(m_agent_text("Triglycerides moved most: <strong>142 → 88 mg/dL</strong> since March.", more=True)), 420, 16))}
</div>"""
    return page("System · mobile conversation", 1280, 2580, body)


def m_post(name, color, text, seq, side="left"):
    radius = "4px"
    align = "flex-start" if side == "left" else "flex-end"
    return (f'<div style="display: flex; flex-direction: column; align-items: {align}; gap: 6px; padding: 0 16px"><div style="display: flex; align-items: center; gap: 6px">{profile_mark(color)}{mono(name, 12, INK3, 500)}{mono(f"#{seq}", 12, INK3, 500)}{mono("1.2K · $0.01", 12, INK3, 500)}</div>'
            f'<div style="max-width: 90%; padding: 14px 16px; border-radius: {radius}; background: {mix(color, 0.11)}; font-size: 16px; line-height: 26.4px">{text}</div></div>')


def m_marker(variant, color, body, side="left"):
    base = WARNING if variant == "skip" else color
    pct = {"task": 0.10, "working": 0.10, "done": 0.10, "skip": 0.12}[variant]
    skip = f'<span style="position: relative; width: 10px; height: 10px; box-sizing: border-box; border-radius: 999px; border: 1.5px solid {base}; overflow: hidden; display: inline-block"><span style="position: absolute; width: 14px; height: 1.5px; top: 3.5px; left: -2.5px; transform: rotate(45deg); background: {base}"></span></span>'
    icon = {"task": dot(base, 6), "working": dot(base, 6), "done": mi("check", 12, base), "skip": skip}[variant]
    return (f'<div style="display: flex; flex-direction: column; align-items: flex-start; padding: 0 16px"><div style="max-width: 90%; padding: 14px 16px; border-radius: 4px; background: {mix(base, pct)}">'
            f'<div style="display: flex; align-items: center; gap: 6px; margin-bottom: 6px; font-family: {MONO}; font-size: 12px; font-weight: 600; letter-spacing: 0.1em; color: {base}"><span style="width: 14px; display: inline-flex; justify-content: center">{icon}</span>{variant.upper()}</div>'
            f'<div style="font-size: 14px; line-height: 21px">{body}</div></div></div>')


def m_pipeline():
    from wg_strip_studies import m_proposed, m_sheet_phone
    return f'<div style="display: flex; gap: 24px; align-items: flex-start">{m_proposed()}{m_sheet_phone()}</div>'


def mobile_workgroup():
    body = f"""<div style="padding: 40px 48px; display: flex; flex-direction: column; gap: 24px; box-sizing: border-box">
{h1("Workgroups · phone and Fold", "Member posts left, hub right, tinted with the speaker accent. Meta is mono on the phone. Marker cards keep the four lifecycle states on one left lane, calm at a 10 % tint (skip 12 % in the warning colour); the state is the eyebrow word and its icon.")}
{spec("Pipeline strip · centred on the live phase; a tap opens its detail", m_pipeline(), 760, 0)}
{spec("Pipeline strip · before the run: one pipeline draws its pending phases with their owners still; several draw placeholder chips", m_before_run(), 760, 0)}
{row(spec("Posts · member and hub", phone(m_post("builder", BUILDER, "Patched the retry loop; tests green locally.", 57) + m_post("alpi", AMBER, "Ship it behind the flag.", 58, "right")), 420, 16), spec("Markers · task and working", phone(m_marker("task", AMBER, "<strong>#onboarding-friction</strong> Find the top 3 drop-off points") + m_marker("working", AMBER, "Pulling funnel events…", "left")), 420, 16))}
{row(spec("Markers · done and skip", phone(m_marker("done", AMBER, "Top 3: email verify, invite, first prompt.") + m_marker("skip", AMBER, "Out of scope for this sprint.", "left")), 420, 16), spec("Workgroup composer · @ mention, no attach", phone(m_composer(workgroup=True)), 420, 0))}
</div>"""
    return page("System · mobile workgroups", 1280, 1560, body)


CONVERSATION = {"desktop": desktop_conversation, "desktop_wg": desktop_workgroup, "mobile": mobile_conversation, "mobile_wg": mobile_workgroup}
