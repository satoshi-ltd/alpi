from gen import ic
from desktop_boards import INK3
from brand_boards import PAL, PAIR_COLOUR
from paper_studies import PAPER, button, deep, field, line_up, object_mark, text

MONO = "'Geist Mono', monospace"
VIEW = {"bg": "#f0f0f0", "side": "#f6f6f6", "pane": "#ffffff", "elev": "#ffffff", "ink": "#141414", "ink2": "#454545", "ink3": "#6b6b6b", "ink4": "#b4b4b4",
        "line": "rgba(20,20,20,0.07)", "line2": "rgba(20,20,20,0.14)", "hover": "rgba(20,20,20,0.04)", "selected": "rgba(20,20,20,0.06)", "danger": "#b73737", "warn": "#b3470e", "dark": False}
WARN = {False: "#B3470E", True: "#F59E5B"}

ROWS = [
    {"conn": "casa", "who": "abby", "shape": "plane", "at": "06:31", "ago": "2h", "title": "Daily mail digest", "summary": "14 new emails since yesterday, 3 need a reply.",
     "type": "info", "unread": True, "group": "Today", "job": True},
    {"conn": "casa", "who": "abby", "shape": "plane", "at": "06:02", "ago": "3h", "title": "Daily mail digest",
     "summary": "token refresh failed (400): { &quot;error&quot;: &quot;invalid_grant&quot;, &quot;error_description&quot;: &quot;Token has been expired or revoked.&quot; }",
     "type": "error", "unread": True, "group": "Today", "job": True},
    {"conn": "mirai", "who": "sentinel", "shape": "shield", "at": "05:40", "ago": "3h", "title": "PR #482 is waiting on you", "summary": "Two blocking findings; the author answered both.",
     "type": "warning", "unread": False, "group": "Today", "job": False},
    {"conn": "mirai", "who": "curator", "shape": "house", "at": "04:00", "ago": "5h", "title": "Knowledge pass finished", "summary": "212 pages checked, 4 updated, 1 flagged as stale.",
     "type": "info", "unread": False, "group": "Today", "job": True},
    {"conn": "casa", "who": "doc", "shape": "heart", "at": "21:10", "ago": "12h", "title": "Weekly vitals", "summary": "Resting heart rate 54, sleep 7 h 12 min on average.",
     "type": "info", "unread": False, "group": "Yesterday", "job": True},
]

LEAD = "14 new emails since yesterday, 3 need a reply."
NEEDS = [
    ("Lucy Grant", "lucy.grant@studio-north.example", "Quote for the October shoot; she needs an answer by Friday"),
    ("Tax Agency", "notices@tax-agency.example", "A new notice is waiting in your electronic mailbox"),
    ("Marc Vidal", "marc.vidal@clonara.example", "Can we move Thursday’s review to Tuesday morning?"),
]
FYI = [
    ("Amazon", "ship-confirm@amazon.example", "Your order has shipped"),
    ("GitHub", "noreply@github.example", "[alpi] CI passed on main"),
]

def mono(value, size=12, color=INK3, weight=400):
    return f'<span style="font-family: {MONO}; font-size: {size}px; color: {color}; font-weight: {weight}; white-space: nowrap; flex-shrink: 0">{value}</span>'


def row_title(r):
    return r["title"] + " failed" if r["type"] == "error" and r["job"] else r["title"]


def row_summary(r):
    return "The mail account refused the saved token." if r["type"] == "error" else r["summary"]


def tone(kind, p):
    return p["danger"] if kind == "error" else p.get("warn", WARN[p["dark"]])


def wrap(value, size, color, weight=400, lh=1.45, extra=""):
    return f'<span style="font-size: {size}px; font-weight: {weight}; line-height: {lh}; color: {color}; white-space: normal; {extra}">{value}</span>'


def ell(value, size, color, weight=400, extra=""):
    return text(value, size, color, weight, f"display: block; overflow: hidden; text-overflow: ellipsis; min-width: 0; {extra}")


def clamp(value, size, color, lines=2):
    return (f'<span style="font-size: {size}px; line-height: 1.4; color: {color}; display: -webkit-box; -webkit-line-clamp: {lines}; '
            f'-webkit-box-orient: vertical; overflow: hidden">{value}</span>')


def dot(color, size=6, extra=""):
    return f'<span style="width: {size}px; height: {size}px; border-radius: 999px; background: {color}; flex-shrink: 0; display: inline-block; {extra}"></span>'


def flex(*items, gap=8, align="center", extra=""):
    return f'<div style="display: flex; align-items: {align}; gap: {gap}px; min-width: 0; {extra}">{"".join(items)}</div>'


def stack(*items, gap=4, extra=""):
    return f'<div style="display: flex; flex-direction: column; gap: {gap}px; min-width: 0; {extra}">{"".join(items)}</div>'


def spacer():
    return '<span style="flex: 1"></span>'


def icon(name, p, size=14, box=24, color=None):
    return (f'<span style="width: {box}px; height: {box}px; display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0">'
            f'{ic(name, size, color or p["ink2"])}</span>')


def eyebrow(value, p, pad="10px 10px 4px"):
    return (f'<div style="padding: {pad}; font-family: {MONO}; font-size: 9.5px; letter-spacing: 0.08em; text-transform: uppercase; '
            f'color: {p["ink3"]}; white-space: nowrap">{value}</div>')


def mark(shape, size, muted=False):
    return f'<span style="display: inline-flex; flex-shrink: 0; opacity: {0.5 if muted else 1}">{object_mark(shape, size)}</span>'


def sev_tag(kind, p):
    colour = tone(kind, p)
    return (f'<span style="font-family: {MONO}; font-size: 9.5px; letter-spacing: 0.06em; text-transform: uppercase; color: {colour}; padding: 1px 5px; '
            f'border-radius: 2px; background: color-mix(in srgb, {colour} 12%, transparent); flex-shrink: 0; line-height: 1.4">{kind}</span>')


def fbutton(label, p, on=False, glyph="", count=""):
    bg, fg = (p["ink"], p["pane"]) if on else ("transparent", p["ink2"])
    tail = f'<span style="font-family: {MONO}; font-size: 10px; opacity: 0.7">{count}</span>' if count else ""
    return (f'<span style="display: inline-flex; align-items: center; gap: 5px; height: 24px; padding: 0 8px; border-radius: 4px; background: {bg}; color: {fg}; '
            f'font-size: 12px; font-weight: 500; white-space: nowrap; flex-shrink: 0">{glyph}{label}{tail}</span>')


def kbd(key, what, p):
    return (f'<span style="display: inline-flex; align-items: center; gap: 4px; white-space: nowrap"><span style="font-family: {MONO}; font-size: 9.5px; color: {p["ink2"]}; '
            f'padding: 0 4px; border-radius: 2px; background: {p["hover"]}; line-height: 15px">{key}</span>{mono(what, 9.5, p["ink3"])}</span>')


def ground(p, inner, pad=10):
    return f'<div style="padding: {pad}px; background: {p["bg"]}; border-radius: 4px">{inner}</div>'


def a_row(p, r, active=False, pad_left=8):
    weight, colour = (600, p["ink"]) if r["unread"] else (400, p["ink2"])
    gutter = f'<span style="width: 6px; padding-top: 6px; flex-shrink: 0; display: inline-flex">{dot(p["ink"] if r["unread"] else "transparent")}</span>'
    line1 = flex(text(f'@{r["who"]}', 11.5, colour, weight, f"font-family: {MONO}"), mono(r["conn"], 9.5, p["ink3"]), spacer(),
                 sev_tag(r["type"], p) if r["type"] != "info" else "", mono(r["at"], 10, p["ink3"]), gap=6)
    title = ell(row_title(r), 12.5, colour, weight)
    summ = ell(row_summary(r), 11, p["ink3"])
    bg = p["pane"] if active else "transparent"
    return (f'<div style="display: flex; gap: 7px; align-items: flex-start; padding: 8px 10px 8px {pad_left}px; background: {bg}">{gutter}'
            f'<span style="padding-top: 2px; display: inline-flex">{mark(r["shape"], 16)}</span>{stack(line1, title, summ, gap=2, extra="flex: 1")}</div>')


def a_filters(p, compact=False):
    tags = line_up(fbutton("All", p, True, count="5"), fbutton("Needs you", p, count="1"), fbutton("Unread", p, count="2"), gap=2, wrap=False)
    return f'<div style="padding: 8px 10px 6px; display: flex; flex-direction: column; gap: 6px">{field("Search", p, PAPER, 206)}{tags}</div>'


def a_list(p, w=252):
    needs = [r for r in ROWS if r["type"] == "error" and r["unread"]]
    rest = [r for r in ROWS if r not in needs]
    rows = [eyebrow("Needs you · 1", p, "8px 10px 2px")] + [a_row(p, r) for r in needs]
    last = None
    for r in rest:
        if r["group"] != last:
            rows.append(eyebrow(r["group"], p, "10px 10px 2px"))
            last = r["group"]
        rows.append(a_row(p, r, active=r is ROWS[0]))
    return f'<div style="width: {w}px; flex-shrink: 0; background: {p["side"]}; overflow: hidden">{a_filters(p)}{"".join(rows)}</div>'


def digest_item(p, name, mail, subject, size=12.5, seam=True):
    edge = f"box-shadow: inset 0 -0.5px 0 {p['line']};" if seam else ""
    head = flex(text(name, size, p["ink"], 600), ell(mail, size - 2, p["ink3"], extra=f"font-family: {MONO}"), gap=6)
    return f'<div style="padding: 6px 0; {edge}">{stack(head, wrap(subject, size, p["ink2"], lh=1.4), gap=1)}</div>'


def digest(p, size=12.5, fyi=True):
    parts = [eyebrow("Needs a reply · 3", p, "4px 0 0")] + [digest_item(p, *it, size=size, seam=i < 2) for i, it in enumerate(NEEDS)]
    if fyi:
        parts += [eyebrow("For your information · 11", p, "10px 0 0")] + [digest_item(p, *it, size=size, seam=i < 1) for i, it in enumerate(FYI)]
    return stack(*parts, gap=0)


def a_detail(p):
    colour = PAL[PAIR_COLOUR["plane"]]
    who = flex(mark("plane", 18), text("abby", 14, deep(colour, p), 600), mono("casa · 06:31", 10, p["ink3"]), spacer(),
               icon("ellipsis", p, 13, 22), gap=6)
    actions = line_up(button("Reply", "primary", p, PAPER, 26), button("Open job", "secondary", p, PAPER, 26), button("Mark unread", "ghost", p, PAPER, 26), gap=6, wrap=False)
    body = stack(who, actions, text("Daily mail digest", 17, p["ink"], 600, "margin-top: 4px"), wrap(LEAD, 12.5, p["ink2"], lh=1.5), digest(p), gap=10)
    return f'<div style="flex: 1; min-width: 0; overflow: hidden; background: {p["pane"]}; padding: 14px 16px">{body}</div>'


def keys_strip(p):
    return flex(kbd("↑↓", "move", p), kbd("⏎", "open", p), kbd("R", "reply", p), kbd("U", "unread", p), kbd("⌫", "delete", p), kbd("/", "search", p), kbd("1–3", "filter", p),
                gap=10, extra=f"padding: 7px 12px; background: {p['side']}; box-shadow: inset 0 0.5px 0 {p['line2']}; overflow: hidden")


def paper_frame(p, inner, h, kicker="2 UNREAD"):
    head = flex(text("Notifications", 14, p["ink"], 600), mono(kicker, 10, p["ink3"]), spacer(), button("Mark all read", "ghost", p, PAPER, 26), icon("x", p),
                gap=8, extra=f"padding: 9px 10px 9px 14px; background: {p['elev']}; box-shadow: inset 0 -0.5px 0 {p['line2']}")
    frame = f'border-radius: 4px; background: {p["elev"]}; box-shadow: 0 0 0 1px {p["line2"]}; overflow: hidden; height: {h}px; display: flex; flex-direction: column'
    return ground(p, f'<div style="{frame}">{head}{inner}</div>')


def a_panel(p, h=500):
    return paper_frame(p, f'<div style="flex: 1; display: flex; min-height: 0">{a_list(p)}{a_detail(p)}</div>{keys_strip(p)}', h)


def phone_segmented(p, items, on=0):
    cells = "".join(f'<span style="flex: 1; min-height: 40px; display: inline-flex; align-items: center; justify-content: center; gap: 4px; font-size: 12px; '
                    f'font-weight: {600 if i == on else 400}; color: {p["ink"] if i == on else p["ink3"]}; background: {p["pane"] if i == on else "transparent"}; border-radius: 4px">'
                    f'{label}{mono(count, 11, p["ink"] if i == on else p["ink3"]) if count else ""}</span>'
                    for i, (label, count) in enumerate(items))
    return f'<div style="display: flex; padding: 2px; background: {p["hover"]}; border-radius: 4px; margin: 0 12px">{cells}</div>'


def phone_row(p, r, swiped=False):
    weight, colour = (600, p["ink"]) if r["unread"] else (400, p["ink2"])
    gutter = f'<span style="width: 7px; padding-top: 8px; display: inline-flex; flex-shrink: 0">{dot(p["ink"] if r["unread"] else "transparent", 7)}</span>'
    line1 = flex(mono("@" + r["who"], 12, colour), mono(r["conn"], 11, p["ink3"]), spacer(), sev_tag(r["type"], p) if r["type"] != "info" else "", mono(r["ago"], 11, p["ink3"]), gap=6)
    title = ell(row_title(r), 15, colour, weight)
    summ = ell(row_summary(r), 12, p["ink3"])
    inner = (f'<div style="display: flex; gap: 8px; align-items: flex-start; padding: 10px 14px 10px 10px; background: {p["pane"]}; box-shadow: inset 0 -0.5px 0 {p["line"]}; '
             f'{"transform: translateX(-152px);" if swiped else ""}">{gutter}<span style="padding-top: 2px; display: inline-flex">{mark(r["shape"], 20)}</span>'
             f'{stack(line1, title, summ, gap=2, extra="flex: 1")}</div>')
    if not swiped:
        return inner
    toggle = "Read" if r["unread"] else "Unread"
    under = (f'<div style="position: absolute; top: 0; right: 0; bottom: 0; width: 152px; display: flex">'
             f'<span style="flex: 1; display: flex; align-items: center; justify-content: center; background: {p["selected"]}; font-size: 12px; font-weight: 500; color: {p["ink"]}">{toggle}</span>'
             f'<span style="flex: 1; display: flex; align-items: center; justify-content: center; background: {p["ink"]}; font-size: 12px; font-weight: 500; color: {p["pane"]}">Delete</span></div>')
    return f'<div style="position: relative; overflow: hidden">{under}{inner}</div>'


def phone_triage(p):
    filters = phone_segmented(p, [("All", ""), ("Needs you", "1"), ("Unread", "2")])
    groups = [eyebrow("Needs you · 1", p, "14px 16px 6px"), phone_row(p, ROWS[1]), eyebrow("Today", p, "14px 16px 6px"), phone_row(p, ROWS[0]),
              phone_row(p, ROWS[2], swiped=True), phone_row(p, ROWS[3]), eyebrow("Yesterday", p, "14px 16px 6px"), phone_row(p, ROWS[4])]
    head = f'<div style="display: flex; flex-direction: column; gap: 8px; padding: 8px 0 6px">{filters}</div>'
    return f'<div style="flex: 1; min-height: 0; overflow: hidden; background: {p["pane"]}">{head}{"".join(groups)}</div>'


def phone_icon_button(name, p, label):
    return f'<span role="button" aria-label="{label}" style="width: 44px; height: 44px; display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0">{ic(name, 20, p["ink2"])}</span>'


def phone_page_nav(p):
    return flex(f'<span style="margin-right: 6px; display: inline-flex">{mono("1 of 5", 11, p["ink3"])}</span>', phone_icon_button("chevron-up", p, "Previous notification"), phone_icon_button("chevron-down", p, "Next notification"),
                phone_icon_button("ellipsis", p, "More"), gap=0)


def phone_reader(p):
    colour = PAL[PAIR_COLOUR["plane"]]
    who = flex(mark("plane", 20), text("abby", 15, deep(colour, p), 600), mono("casa · 2h ago", 11, p["ink3"]), gap=8)
    body = stack(who, text("Daily mail digest", 22, p["ink"], 600, "white-space: normal"), wrap(LEAD, 14, p["ink2"], lh=1.5), digest(p, 14, fyi=True), gap=12,
                 extra="padding: 16px; flex: 1; min-height: 0; overflow: hidden")
    bar = flex(button("Reply", "primary", p, PAPER, 48), button("Open job", "secondary", p, PAPER, 48), spacer(), phone_icon_button("eye", p, "Mark unread"),
               phone_icon_button("trash-2", p, "Delete"), gap=8, extra=f"padding: 10px 12px 30px; background: {p['side']}; box-shadow: inset 0 0.5px 0 {p['line2']}")
    return f'<div style="flex: 1; min-height: 0; display: flex; flex-direction: column; background: {p["pane"]}">{body}{bar}</div>'
