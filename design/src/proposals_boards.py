from gen import DANGER, diamond, ic, mix, page
from desktop_boards import HOVER, INK, INK2, INK3, INK4, LINE, LINE2, MONO, PANE, SELECTED, SIDE
from conversation_boards import (
    AMBER, BRAND, BUILDER, DANGER_FILL, SUCCESS, WARNING, d_composer, d_user, dot, h1, kbd, label, m_composer, m_user, mono, phone,
    small_diamond,
)

DOC = "#3a7ca5"
SANS = "Geist, ui-sans-serif, system-ui, sans-serif"

PROPOSALS = [
    ("steps", "both", "Agent steps", "Tool calls you can open: a family icon, a plain summary, the duration, and the arguments and result one click away. Failures open by default; approvals ask in the flow.", "A tool call is the one thing a user has to trust in an agent host; today every call is the same chip icon with two clipped arguments and no result.", "Copilot, Perplexity, Zed, Claude Code", "M"),
    ("activity", "both", "Agents at work", "“Needs you” becomes a first-class state: a state on every roster row and an Activity panel that lists running turns, workgroup phases and schedule runs, what waits on you first.", "An approval or a question can sit unseen in a background profile; every agent tool now leads with the runs that need you.", "Codex, Cursor 3, Warp, Devin", "L"),
    ("rhythm", "desktop", "Conversation", "Turns read as units: 8–12 px inside a turn, 40 px between turns.", "Today the user bubble, the steps, the reply and the next question are all 24 px apart, so the eye cannot find where an exchange ends.", "ChatGPT, Claude", "S"),
    ("composer", "mobile", "Composer", "Return adds a line on phones and only the button sends; model and effort become a chip in the composer that opens a sheet.", "Multi-line prompts are impossible today, and changing model means a trip to the full settings screen from an 11 pt header label.", "ChatGPT, Claude, Zed", "S"),
    ("reasoning", "both", "Reasoning", "A shimmer label while thinking, one full-width “Thought for 7s” row after, readable sans when opened, collapsed when the answer lands.", "Live reasoning streams in 11 px mono in a box that cannot scroll, and stays open after the answer.", "Claude, ChatGPT, Open WebUI, Zed", "S"),
    ("type", "both", "Typography", "Six sizes with named roles instead of eleven, chat at 15 on desktop and 16 on the phone, mono only for identifiers, numbers and code.", "The core UI lives at 11–12 px and mono is used seven times more than sans, which makes prose read like logs.", "Linear, Claude, ChatGPT", "M"),
    ("motion", "both", "Motion", "One motion vocabulary: new turns rise in 200 ms, only the newest streamed text fades, the phone composer rides the keyboard, every loop honours reduced motion.", "Nothing moves where the eye needs help, while six looping animations with six durations ignore the reduced-motion setting.", "Claude, Dia, iOS guidelines", "M"),
    ("palette", "desktop", "Command palette", "⌘K searches profiles, workgroups and sessions as well as commands; ⌘N starts a session; ⌘/ lists every shortcut.", "The palette only lists commands, cannot jump to anything, and prints “⌘1–9” as four separate keys.", "Linear, Raycast, Zed, Claude Code", "S"),
    ("settings", "desktop", "Settings", "A section rail with search beside the profile settings, section titles in 15 px sans, labels in sentence case.", "Ten sections stack on one page and titles look like their own row labels, so finding MCP or Email means scrolling and reading.", "ChatGPT, Raycast, VS Code", "M"),
    ("footer", "both", "Message footer", "One footer rule for both speakers: the time always visible and faint, actions on hover or long press, tokens, cost and model in a tooltip on the time.", "The user footer is always on and the agent footer only on hover, and the agent line mixes four numbers with an amber model name.", "ChatGPT, Claude", "S"),
    ("contrast", "desktop", "Contrast", "ink-4 becomes decoration only; readable text never drops below ink-3, with a test that forbids it.", "ink-4 carries argument keys, helpers and separators at about 2.2:1 in dark mode, below any reading threshold.", "WCAG 2.2", "S"),
    ("msteps", "mobile", "Agent steps", "A tool row opens a sheet with the full arguments, the result and a copy button.", "On the phone a tool call is one truncated line with no way to see what ran or why it failed.", "ChatGPT, Codex", "S"),
    ("native", "mobile", "Native feel", "Haptics on send, long press and approvals; 44 pt targets and 12 pt minimum chat text; Select text on long press; tablets rotate and the open Fold shows the roster.", "Only two controls buzz, wide rows are 36 pt, labels go down to 9 pt, and a tablet or open Fold renders as a stretched phone.", "Apple HIG, Material 3, Codex on iPad", "M"),
    ("controls", "desktop", "Controls", "One Button with an icon-only form, one tooltip, icon sizes as tokens.", "Button, IconBtn, two ActionLinks, raw buttons and two tooltip systems plus native titles drift apart one tweak at a time.", "Linear", "M"),
    ("remote", "mobile", "Running work", "A Live Activity for a running workgroup and an actionable push when an agent needs an approval or an answer.", "The phone buzzes for notify messages and failed jobs but never for a question an agent is blocked on.", "ChatGPT, Codex", "L"),
]

NUM = {key: i for i, (key, *_rest) in enumerate(PROPOSALS, start=1)}

ALIGNED = [
    ("Message layout", "User in a tinted bubble, the reply full width with no avatar, one centred column. The same grammar as ChatGPT and Claude."),
    ("Stop in place", "Send turns into Stop where the finger already is, on both clients."),
    ("Grouped steps", "“+N previous tool calls” with the failure count visible while collapsed is the pattern Perplexity and Copilot converged on."),
    ("Model in the composer", "Desktop already keeps the picker in the composer row, as Zed and Claude do; the phone is the gap."),
    ("One token file", "Shared tokens with parity tests on both sides, and an accent kept rare enough to mean something."),
    ("Sticky scroll", "Follow while streaming, stop when the user scrolls up, a Latest pill to come back."),
]

BUGS = [
    ("desktop", "The palette splits every hint into single-letter keys, so “⌘1–9” shows four chips and “light · dark · system” shows twenty."),
    ("desktop", "⇧⌘H, ⇧⌘R and ⇧⌘P are each bound to two different commands."),
    ("desktop", "Workgroup bubbles read a --color-accent variable that does not exist, so light mode always gets the dark-mode amber."),
]


def tag(text):
    tone = {"desktop": mix(AMBER, 0.22), "mobile": mix(DOC, 0.2), "both": mix("#9d4dc6", 0.2), "S": mix(SUCCESS, 0.18), "M": mix(WARNING, 0.2), "L": mix(DANGER_FILL, 0.16)}[text]
    return f'<span style="display: inline-flex; align-items: center; height: 18px; padding: 0 8px; border-radius: 16px; background: {tone}; color: {INK}; font-family: {MONO}; font-size: 11px; white-space: nowrap">{text}</span>'


def para(text, size=13, color=INK2, extra=""):
    return f'<p style="margin: 0; font-size: {size}px; line-height: 1.55; color: {color}; {extra}">{text}</p>'


def box(title, inner, w, tone="today", pad=20, h=None):
    head_color = INK3 if tone == "today" else BRAND
    border = LINE if tone == "today" else mix(AMBER, 0.55)
    height = f"min-height: {h}px;" if h else ""
    return (f'<div style="display: flex; flex-direction: column; gap: 8px; width: {w}px; flex-shrink: 0">'
            f'<span style="font-family: {MONO}; font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase; color: {head_color}">{title}</span>'
            f'<div style="display: flex; flex-direction: column; gap: 12px; padding: {pad}px; border-radius: 12px; background: {PANE}; border: {0.5 if tone == "today" else 1}px solid {border}; box-sizing: border-box; {height}">{inner}</div></div>')


def proposal(key, title, clients, effort, before, after, why, seen, w=560):
    head = (f'<div style="display: flex; align-items: baseline; gap: 12px">{mono(f"{NUM[key]:02d}", 13, INK3)}'
            f'<span style="font-size: 18px; font-weight: 600; letter-spacing: -0.01em">{title}</span>'
            f'<span style="display: inline-flex; gap: 6px">{"".join(tag(c) for c in clients)}{tag(effort)}</span></div>')
    foot = (f'<div style="display: grid; grid-template-columns: 1fr 300px; gap: 28px; max-width: 1184px">{para("<strong>Why.</strong> " + why)}'
            f'{para("<strong>Seen in.</strong> " + seen, 12, INK3)}</div>')
    return (f'<div style="display: flex; flex-direction: column; gap: 14px; padding-top: 22px; border-top: 0.5px solid {LINE}">{head}'
            f'<div style="display: flex; gap: 24px; align-items: flex-start">{box("Today", before, w)}{box("Proposed", after, w, "next")}</div>{foot}</div>')


def board(title, sub, body, h):
    return page(title, 1280, h, f'<div style="padding: 40px 48px; display: flex; flex-direction: column; gap: 26px; box-sizing: border-box">{h1(title, sub)}{body}</div>')


def overview():
    head_cols = "28px 76px 130px 1fr 1fr 150px 44px"
    head = (f'<div style="display: grid; grid-template-columns: {head_cols}; gap: 14px; padding-bottom: 8px; font-family: {MONO}; font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase; color: {INK3}">'
            '<span></span><span>client</span><span>area</span><span>proposal</span><span>why</span><span>seen in</span><span>effort</span></div>')
    rows = "".join(
        f'<div style="display: grid; grid-template-columns: {head_cols}; gap: 14px; align-items: start; padding: 11px 0; border-top: 0.5px solid {LINE}">'
        f'{mono(f"{i:02d}", 12)}<span>{tag(who)}</span><span style="font-size: 13px; font-weight: 600">{area}</span>{para(what, 12.5, INK)}{para(why, 12.5)}{para(seen, 12, INK3)}<span>{tag(effort)}</span></div>'
        for i, (_key, who, area, what, why, seen, effort) in enumerate(PROPOSALS, start=1)
    )
    aligned = "".join(
        f'<div style="display: flex; flex-direction: column; gap: 4px; padding: 14px; border-radius: 10px; background: {mix(SUCCESS, 0.08)}"><span style="display: inline-flex; align-items: center; gap: 6px; font-size: 13px; font-weight: 600">{ic("check", 13, SUCCESS)}{t}</span>{para(d, 12.5)}</div>'
        for t, d in ALIGNED
    )
    bugs = "".join(f'<div style="display: flex; gap: 10px; align-items: baseline; padding: 8px 0; border-top: 0.5px solid {LINE}">{tag(w)}{para(t, 13, INK)}</div>' for w, t in BUGS)
    verdict = para(
        "Alpi is in line on the conversation itself: the message grammar, the composer and the way steps group match what Claude, ChatGPT and Zed ship. "
        "It is behind on what makes an agent host different from a chat app: seeing what each agent is doing, opening a step to trust it, and noticing when one waits on you. "
        "The rest is polish that compounds: a tighter type scale, real contrast, motion where the eye needs it, and a phone that feels native under the thumb.",
        14, INK, "max-width: 1080px")
    body = (f'{verdict}<div style="display: flex; flex-direction: column; gap: 10px">{label("Already in line · keep")}'
            f'<div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px">{aligned}</div></div>'
            f'<div style="display: flex; flex-direction: column">{label("Proposals · ranked by impact over effort")}<div style="height: 12px"></div>{head}{rows}</div>'
            f'<div style="display: flex; flex-direction: column">{label("Bugs found on the way")}<div style="height: 8px"></div>{bugs}</div>')
    return board("Where Alpi could go next", "A review of both clients against the agent and chat apps shipping in 2025–2026. Each proposal says what changes, why it matters, and who already does it. Effort is S (a day), M (a few days) or L (a release).", body, 1900)


def tool_old(name, args, failed=False):
    color = DANGER_FILL if failed else INK3
    a = "".join(f'<span style="color: {INK4}">{k}=</span><span style="color: {INK2}; margin-right: 8px">{v}</span>' for k, v in args)
    return f'<div style="display: flex; align-items: center; gap: 8px; font-family: {MONO}; font-size: 12px">{ic("chip", 14, color)}<span style="font-weight: 500; color: {DANGER if failed else INK}">{name}</span><span style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: {INK2}">{a}</span></div>'


def tool_new(icon, name, summary, dur, state="done", body=""):
    color = {"done": INK3, "failed": DANGER_FILL, "running": BRAND}[state]
    status = {"done": mono(dur, 11), "failed": mono(f"failed · {dur}", 11, DANGER), "running": mono(f"{dur} …", 11, BRAND)}[state]
    chev = ic("chev-d", 12, INK3) if body else ic("chev-r", 12, INK3)
    head = (f'<div style="display: flex; align-items: center; gap: 10px; height: 32px; padding: 0 10px; border-radius: 8px; background: {HOVER if body else "transparent"}">'
            f'{ic(icon, 14, color)}<span style="font-family: {MONO}; font-size: 12px; font-weight: 500; color: {DANGER if state == "failed" else INK}">{name}</span>'
            f'<span style="flex: 1; min-width: 0; font-size: 13px; color: {INK2}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis">{summary}</span>{status}{chev}</div>')
    return f'<div style="display: flex; flex-direction: column; gap: 6px">{head}{body}</div>'


def code(lines, tone=INK2):
    return f'<div style="margin-left: 34px; padding: 10px 12px; border-radius: 8px; background: {SIDE}; border: 0.5px solid {LINE}; font-family: {MONO}; font-size: 12px; line-height: 1.6; color: {tone}">{"<br>".join(lines)}</div>'


def approval_inline():
    btn = lambda t, primary=False: f'<span style="display: inline-flex; align-items: center; height: 28px; padding: 0 12px; border-radius: 8px; font-size: 13px; font-weight: 500; background: {INK if primary else HOVER}; color: {PANE if primary else INK}">{t}</span>'
    return (f'<div style="display: flex; flex-direction: column; gap: 10px; padding: 12px 14px; border-radius: 10px; border: 1px solid {mix(WARNING, 0.6)}; background: {mix(WARNING, 0.08)}">'
            f'<span style="display: inline-flex; align-items: center; gap: 8px; font-size: 13px; font-weight: 600">{ic("alert", 14, WARNING)}shell wants to run a command</span>'
            f'<span style="font-family: {MONO}; font-size: 12px; color: {INK}">rm -rf dist &amp;&amp; npm run build</span>'
            f'<span style="display: flex; gap: 8px">{btn("Deny")}{btn("Allow once", True)}{btn("Always allow")}</span></div>')


def rhythm(gaps):
    blocks = [("user", "Summarize yesterday's deploys"), ("steps", "3 tool calls"), ("reply", "Two jobs failed overnight…"), ("user", "Open a fix for the lint error"), ("steps", "2 tool calls"), ("reply", "Opened PR #412…")]
    out = []
    for i, (kind, text) in enumerate(blocks):
        if kind == "user":
            el = f'<div style="align-self: flex-end; padding: 8px 12px; border-radius: 12px 4px 12px 12px; background: {mix(AMBER, 0.14)}; font-size: 13px">{text}</div>'
        elif kind == "steps":
            el = f'<div style="display: flex; align-items: center; gap: 6px">{ic("chev-r", 11, INK3)}{mono(text, 11)}</div>'
        else:
            el = f'<div style="font-size: 13px; color: {INK}">{text}</div>'
        out.append(el)
        if i < len(blocks) - 1:
            g = gaps[i]
            out.append(f'<div style="height: {g}px; display: flex; align-items: center; gap: 8px"><span style="flex: 1; height: 0; border-top: 1px dashed {mix(BRAND if g >= 40 else INK4, 0.7)}"></span>{mono(f"{g}px", 10, BRAND if g >= 40 else INK3)}</div>')
    return f'<div style="display: flex; flex-direction: column">{"".join(out)}</div>'


def footer_row(parts):
    return f'<div style="display: flex; align-items: center; gap: 8px">{"".join(parts)}</div>'


def conversation():
    p1 = proposal("steps", "Tool calls you can open", ["both"], "M",
                  tool_old("read_file", [("path", "/var/log/deploy.log"), ("limit", "200")]) + tool_old("grep", [("pattern", "exit=1")]) + tool_old("shell", [("cmd", "npm run lint")], failed=True) + tool_old("web_fetch", [("url", "https://status.example.com/api/v2/summ…")]),
                  tool_new("file", "read_file", "deploy.log · first 200 lines", "0.2s") + tool_new("search", "grep", "3 matches for exit=1", "0.1s")
                  + tool_new("terminal", "shell", "npm run lint", "4.1s", "failed", code(["$ npm run lint", '<span style="color: #c14545">src/app.ts:14  no-unused-vars  “config” is never used</span>', "1 error, 0 warnings"]))
                  + tool_new("globe", "web_fetch", "status.example.com", "3s", "running") + approval_inline(),
                  "Every call shares one chip icon, shows two arguments clipped at 60 characters and never shows what came back. A failed lint looks almost like a successful read. Approvals interrupt as a modal over the whole window.",
                  "Copilot collapses tool details but streams terminal output inline and asks for approval in the flow; Perplexity labels steps in plain words; Zed and Claude Code let a step open to its full input and output.")
    p3 = proposal("rhythm", "Turns that read as units", ["desktop"], "S", rhythm([24] * 5), rhythm([10, 10, 40, 10, 10]),
                  "One gap everywhere flattens the thread: the question, the work and the answer of one exchange sit as far apart as two different exchanges. Grouping them is a two-line change in the timeline styles.",
                  "ChatGPT and Claude keep a turn tight and open generous space before the next question.")
    reason_old = (f'<div style="display: flex; align-items: center; gap: 6px">{ic("chev-d", 11, INK3)}{mono("thinking · 4s")}</div>'
                  f'<div style="display: flex; flex-direction: column; gap: 6px; max-height: 76px; overflow: hidden; mask-image: linear-gradient(to bottom, transparent, black 24px)">'
                  + "".join(f'<div style="font-family: {MONO}; font-size: 11px; line-height: 1.65; color: {INK3}">{t}</div>' for t in ("The user wants a summary of yesterday's deploys.", "Read the log, group by job, count exits.", "Two jobs failed; call them out first."))
                  + "</div>")
    shimmer = f'background: linear-gradient(90deg, {INK3} 0%, {INK} 50%, {INK3} 100%); -webkit-background-clip: text; background-clip: text; color: transparent;'
    reason_new = (f'<div style="display: flex; align-items: center; gap: 8px; height: 30px; padding: 0 10px; border-radius: 8px; background: {HOVER}"><span style="font-size: 13px; font-weight: 500; {shimmer}">Thinking…</span>{mono("reading the deploy log", 11)}</div>'
                  f'<div style="display: flex; align-items: center; gap: 8px; height: 30px; padding: 0 10px; border-radius: 8px">{ic("chev-r", 12, INK3)}<span style="font-size: 13px; color: {INK2}">Thought for 7s</span></div>'
                  f'<div style="display: flex; flex-direction: column; gap: 6px; padding: 0 10px 0 30px; border-left: 2px solid {LINE}">'
                  + "".join(para(t, 13, INK2) for t in ("The user wants a summary of yesterday's deploys.", "Read the log, group by job, count exits."))
                  + "</div>")
    p_reason = proposal("reasoning", "Reasoning that gets out of the way", ["both"], "S", reason_old, reason_new,
                        "Live reasoning streams in 11 px mono inside a box that cannot scroll, and it stays open after the answer. A shimmer label while thinking, then one full-width “Thought for 7s” row that opens to readable sans, keeps the answer as the main thing.",
                        "Claude, ChatGPT and Open WebUI collapse to “Thought for Xs”; Zed users asked for live-open, auto-collapse-on-answer.")
    old_foot = (footer_row([mono("2m", 11), ic("pencil", 12, INK3), ic("copy", 12, INK3)]) + f'<div style="height: 1px"></div>'
                + footer_row([ic("copy", 12, INK3), ic("refresh", 12, INK3), ic("volume", 12, INK3), mono("2m · 3.4K · $0.0123 ·", 11), mono("sonnet-4", 11, BRAND)]))
    tip = (f'<div style="display: inline-flex; flex-direction: column; gap: 4px; padding: 8px 10px; border-radius: 8px; background: {INK}; width: max-content">'
           f'{mono("3.4K tokens · $0.0123", 11, PANE)}{mono("sonnet-4 · 12.4s", 11, "#b1bac4")}</div>')
    new_foot = (footer_row([mono("2m", 11, INK4 if False else INK3), f'<span style="opacity: 0.35; display: inline-flex; gap: 8px">{ic("pencil", 12, INK3)}{ic("copy", 12, INK3)}</span>', mono("actions on hover", 10, INK4)])
                + footer_row([mono("2m", 11, INK3), f'<span style="opacity: 0.35; display: inline-flex; gap: 8px">{ic("copy", 12, INK3)}{ic("refresh", 12, INK3)}{ic("volume", 12, INK3)}</span>'])
                + tip)
    p_foot = proposal("footer", "One footer for both speakers", ["both"], "S", old_foot, new_foot,
                      "The two footers follow different rules, and the agent's mixes actions with four numbers and an amber model name that competes with the reply. Time stays as the anchor; the numbers live one hover away.",
                      "ChatGPT and Claude keep a quiet action row and move usage detail out of the thread.")
    return board("Proposals · conversation", "How a turn reads, how its steps open, and how reasoning and metadata stay out of the answer's way.", p1 + p3 + p_reason + p_foot, 1860)


def roster_row(color, name, right="", active=False, bold=False):
    bg = SELECTED if active else "transparent"
    return (f'<div style="display: flex; align-items: center; gap: 10px; height: 30px; padding: 0 10px; border-radius: 8px; background: {bg}">'
            f'{small_diamond(color, 8)}<span style="flex: 1; font-size: 13px; font-weight: {600 if bold else 500}; color: {INK}">{name}</span>{right}</div>')


def state_chip(text, color):
    return f'<span style="display: inline-flex; align-items: center; gap: 5px; font-family: {MONO}; font-size: 10.5px; color: {color}">{dot(color, 6)}{text}</span>'


def activity_row(icon, color, title, sub, action=""):
    act = f'<span style="display: inline-flex; align-items: center; height: 24px; padding: 0 10px; border-radius: 7px; background: {INK}; color: {PANE}; font-size: 12px; font-weight: 500">{action}</span>' if action else ""
    return (f'<div style="display: flex; align-items: center; gap: 10px; padding: 8px 10px; border-radius: 8px">{ic(icon, 14, color)}'
            f'<div style="flex: 1; display: flex; flex-direction: column; gap: 2px"><span style="font-size: 13px; color: {INK}">{title}</span>{mono(sub, 11)}</div>{act}</div>')


def activity():
    old = (f'<div style="width: 240px; display: flex; flex-direction: column; gap: 2px; padding: 8px; border-radius: 10px; background: {SIDE}">{label("Profiles")}'
           + roster_row(AMBER, "alpi", f'<span style="opacity: .6">{small_diamond(AMBER, 6)}</span>') + roster_row(BUILDER, "builder") + roster_row(DOC, "doc") + roster_row("#9d4dc6", "abby")
           + f'<div style="height: 8px"></div>{label("Workgroups")}' + roster_row(INK3, "# launch-crew") + "</div>"
           + para("A busy agent pulses its diamond. An approval waiting in builder, a failed job in doc and a workgroup mid-phase all look like the idle rows.", 12.5))
    new_side = (f'<div style="width: 240px; display: flex; flex-direction: column; gap: 2px; padding: 8px; border-radius: 10px; background: {SIDE}">'
                + f'<span style="display: inline-flex; align-items: center; gap: 6px">{ic("pin", 11, INK3)}{label("Pinned")}</span>' + roster_row(AMBER, "alpi", state_chip("working", BRAND), True)
                + f'<div style="height: 8px"></div>{label("Profiles")}' + roster_row(BUILDER, "builder", state_chip("needs you", WARNING), bold=True) + roster_row(DOC, "doc", state_chip("failed", DANGER_FILL)) + roster_row("#9d4dc6", "abby")
                + f'<div style="height: 8px"></div>{label("Workgroups")}' + roster_row(INK3, "# launch-crew", mono("2/4", 10.5, BRAND)) + "</div>")
    panel = (f'<div style="width: 250px; display: flex; flex-direction: column; gap: 2px; padding: 10px; border-radius: 12px; border: 0.5px solid {LINE2}; box-shadow: 0 18px 50px rgba(11,17,23,0.10)">'
             f'<div style="display: flex; align-items: center; gap: 8px; padding: 2px 6px 8px">{ic("activity", 14, INK)}<span style="font-size: 13px; font-weight: 600">Activity</span><span style="flex: 1"></span>{kbd("⌘")}{kbd("J")}</div>'
             f'{label("Needs you · 1")}' + activity_row("alert", WARNING, "builder · run a shell command", "12s ago", "Review")
             + f'<div style="height: 6px"></div>{label("Running · 2")}' + activity_row("activity", BRAND, "alpi · deploy summary", "42s · 3 tools") + activity_row("activity", BRAND, "launch-crew · #analyze", "phase 2 of 4 · 3 members")
             + f'<div style="height: 6px"></div>{label("Scheduled")}' + activity_row("clock", INK3, "doc · daily brief", "in 2h") + activity_row("x", DANGER_FILL, "doc · weekly labs", "failed 1d ago") + "</div>")
    p2 = proposal("activity", "Agents at work, and the ones that need you", ["both"], "L", old, f'<div style="display: flex; gap: 16px; align-items: flex-start">{new_side}{panel}</div>',
                  "An agent host runs many things at once. Today the only signal is a pulse on the diamond, so an approval can wait unseen behind another chat and a failed job only surfaces in the inbox. A state on each row and one Activity panel, needs-you first, answer “what is running and what is waiting on me” in one glance.",
                  "Codex added a “Needs input” status and a task list; Cursor 3 and Warp have an agent panel with jump-to-waiting; Devin groups sessions by status.", w=560)
    lock = (f'<div style="width: 340px; padding: 16px; border-radius: 22px; background: {mix(INK, 0.9)}; display: flex; flex-direction: column; gap: 10px">'
            f'<div style="display: flex; align-items: center; gap: 8px">{diamond(AMBER, 12)}<span style="font-size: 13px; font-weight: 600; color: #ffffff">launch-crew</span><span style="flex: 1"></span>{mono("3m", 11, "#b1bac4")}</div>'
            f'<span style="font-size: 14px; color: #ffffff">#analyze · phase 2 of 4</span>'
            f'<div style="height: 5px; border-radius: 999px; background: rgba(255,255,255,0.18)"><div style="width: 50%; height: 100%; border-radius: 999px; background: {AMBER}"></div></div>'
            f'{mono("builder · doc · abby working", 11, "#b1bac4")}</div>')
    push = (f'<div style="width: 340px; padding: 12px 14px; border-radius: 16px; background: {SIDE}; border: 0.5px solid {LINE}; display: flex; gap: 10px; align-items: flex-start">{ic("alert", 16, WARNING)}'
            f'<div style="display: flex; flex-direction: column; gap: 2px"><span style="font-size: 13px; font-weight: 600">builder needs you</span>{para("Allow “rm -rf dist &amp;&amp; npm run build”?", 12.5)}'
            f'<span style="display: flex; gap: 8px; margin-top: 6px">{mono("Deny", 12, INK)}{mono("Allow once", 12, BRAND, 600)}</span></div></div>')
    old_m = para("A running workgroup or a pending approval is only visible inside the app; the phone buzzes for notify messages and failed jobs, never for a question the agent is blocked on.", 13)
    p2m = proposal("remote", "The phone as the remote for running work", ["mobile"], "L", old_m, lock + push,
                   "The phone is where people are when a background agent needs them. A Live Activity for a running workgroup and an actionable push for an approval turn “come back to the desk” into one tap.",
                   "ChatGPT shows progress in the Lock Screen and Dynamic Island; Codex pushes when a task needs input.")
    return board("Proposals · agents at work", "What is running, what is waiting on you, and how to answer it from wherever you are.", p2 + p2m, 1330)


def palette_row(icon, text, sub="", keys=(), active=False):
    k = "".join(kbd(x) for x in keys)
    return (f'<div style="display: flex; align-items: center; gap: 10px; height: 32px; padding: 0 10px; border-radius: 8px; background: {SELECTED if active else "transparent"}">'
            f'{icon}<span style="font-size: 13px; color: {INK}">{text}</span>{mono(sub, 11) if sub else ""}<span style="flex: 1"></span><span style="display: inline-flex; gap: 3px">{k}</span></div>')


def palette(query, rows):
    return (f'<div style="display: flex; flex-direction: column; gap: 2px; padding: 8px; border-radius: 12px; border: 0.5px solid {LINE2}; box-shadow: 0 18px 50px rgba(11,17,23,0.10)">'
            f'<div style="display: flex; align-items: center; gap: 8px; height: 36px; padding: 0 10px; border-bottom: 0.5px solid {LINE}; margin-bottom: 6px">{ic("search", 14, INK3)}<span style="font-size: 14px; color: {INK if query else INK3}">{query or "Type a command…"}</span></div>{rows}</div>')


def navigation():
    old_rows = (palette_row(ic("chev-r", 12, INK3), "Switch profile", "", ("⌘", "1", "–", "9")) + palette_row(ic("chev-r", 12, INK3), "Theme", "", tuple("light · d")) + palette_row(ic("chev-r", 12, INK3), "Jump to profile / workgroup") + palette_row(ic("chev-r", 12, INK3), "Filter sidebar", "", ("⌘", "S")))
    new_rows = (label("Profiles") + palette_row(small_diamond(AMBER, 8), "alpi", "profile", ("⌘", "1"), True) + label("Sessions")
                + palette_row(ic("clock", 12, INK3), "Summarize yesterday's <strong>dep</strong>loys", "@alpi · 1d") + palette_row(ic("clock", 12, INK3), "Staging <strong>dep</strong>loy checklist", "#launch-crew · 3d")
                + label("Commands") + palette_row(ic("plus", 12, INK3), "New session", "", ("⌘", "N")) + palette_row(ic("sun", 12, INK3), "Theme", "light · dark · system") + palette_row(ic("more", 12, INK3), "Keyboard shortcuts", "", ("⌘", "/")))
    p7 = proposal("palette", "A palette that goes anywhere", ["desktop"], "S", palette("", old_rows), palette("dep", new_rows),
                  "⌘K is where keyboard users live, but today it only runs commands: it cannot open a profile, a workgroup or a past session, and it prints key hints letter by letter. Searching everything, ⌘N for a new session and a ⌘/ sheet make the keyboard path complete.",
                  "Linear, Raycast and Zed search entities and commands in one list; Claude Code lists shortcuts under ⌘/.")
    sec_old = "".join(
        f'<div style="display: flex; flex-direction: column; gap: 5px; padding: 7px 0; border-top: 0.5px solid {LINE}">{label(t)}'
        f'<div style="display: flex; justify-content: space-between">{mono(r.upper(), 11)}{mono("…", 11, INK2)}</div></div>'
        for t, r in (("Overview", "model"), ("Usage", "budget"), ("Service", "workspace"), ("ALP", "peers"), ("Sandbox", "mode"), ("Voice", "voice"))) + para("…then MCP, Email, Storage and Danger zone further down the same scroll.", 12.5)
    rail = "".join(f'<span style="display: block; padding: 6px 10px; border-radius: 7px; font-size: 13px; color: {INK if i == 5 else INK2}; background: {SELECTED if i == 5 else "transparent"}">{t}</span>'
                   for i, t in enumerate(("Overview", "Model", "Usage", "Peers", "Sandbox", "MCP", "Email", "Voice", "Storage", "Danger zone")))
    rows = "".join(f'<div style="display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-top: 0.5px solid {LINE}"><div style="display: flex; flex-direction: column; gap: 2px"><span style="font-size: 13px; color: {INK}">{a}</span><span style="font-size: 12px; color: {INK3}">{b}</span></div>{mono(c, 12, INK2)}</div>'
                   for a, b, c in (("atlassian", "npx mcp-atlassian · 14 tools", "on"), ("github", "npx server-github · 22 tools", "on")))
    sec_new = (f'<div style="display: flex; gap: 18px"><div style="width: 150px; display: flex; flex-direction: column; gap: 2px">'
               f'<div style="display: flex; align-items: center; gap: 6px; height: 28px; padding: 0 8px; border-radius: 7px; border: 0.5px solid {LINE2}; margin-bottom: 6px">{ic("search", 12, INK3)}<span style="font-size: 12px; color: {INK3}">Search settings</span></div>{rail}</div>'
               f'<div style="flex: 1; display: flex; flex-direction: column"><span style="font-size: 15px; font-weight: 600; margin-bottom: 4px">MCP servers</span>{para("Tools this profile can call through the Model Context Protocol.", 12.5, INK3)}<div style="height: 8px"></div>{rows}</div></div>')
    p8 = proposal("settings", "Settings you can navigate", ["desktop"], "M", sec_old, sec_new,
                  "Ten sections share one scroll and their titles use the same 11 px mono uppercase as the rows beneath, so the page has no landmarks. A rail with search gives each section an address, and sans titles give the page a hierarchy.",
                  "ChatGPT, Raycast and VS Code use a left rail and a search box; ChatGPT added settings search in 2026.")
    return board("Proposals · navigation", "Getting anywhere from the keyboard, and finding a setting without reading the whole page.", p7 + p8, 1300)


def scale_chip(size, note, strong=False):
    return (f'<div style="display: flex; align-items: baseline; gap: 12px; padding: 4px 0"><span style="width: 44px">{mono(f"{size}", 11, INK3)}</span>'
            f'<span style="font-size: {min(size, 28)}px; line-height: 1.2; font-weight: {600 if strong else 400}; color: {INK}">Deploy summary</span>{mono(note, 11)}</div>')


def foundations():
    old = "".join(scale_chip(s, n) for s, n in ((9, ""), (10, ""), (11, "×158 · most of the UI"), (12, "×94"), (13, ""), (14, ""), (15, "chat"), (17, ""), (20, ""), (28, ""), (56, "")))
    new = "".join(scale_chip(s, n, s >= 18) for s, n in ((11, "meta · mono · ids, numbers, time"), (13, "UI · labels, rows, buttons"), (15, "chat · desktop (16 on the phone)"), (18, "title · sections, dialogs"), (28, "display · empty states"), (56, "hero · first run")))
    p5 = proposal("type", "Six sizes with a job each", ["both"], "M", old + para("Plus about twelve ad-hoc em and rem sizes in markdown. Mono is used 174 times, sans 25.", 12.5), new + para("Mono only for identifiers, numbers and code. Reasoning, helpers and section titles move to sans.", 12.5),
                  "When most of the interface is 11–12 px mono, prose, labels and data all look alike and nothing leads. Fewer sizes with named roles make hierarchy come from size and weight, the way Linear gets calm from a small scale.",
                  "Linear, Claude and ChatGPT: 15–16 px chat body at about 1.6, 13–14 px chrome, mono for code and metadata only.")
    sample = lambda color, ratio, name: f'<div style="display: flex; align-items: center; gap: 14px"><span style="width: 60px">{mono(name, 11)}</span><span style="font-family: {MONO}; font-size: 12px; color: {color}">path=/var/log/deploy.log</span><span style="flex: 1"></span>{mono(ratio, 11, INK2)}</div>'
    p10 = proposal("contrast", "Readable means ink-3 or darker", ["desktop"], "S",
                   sample(INK4, "2.2:1 dark · 1.9:1 light", "ink-4") + para("Used 48 times for text: argument keys, helpers, separators, skill metadata.", 12.5),
                   sample(INK3, "≥ 4.5:1", "ink-3") + para("ink-4 stays for rules, dots and disabled glyphs. A test fails when text uses it, next to the palette contrast test.", 12.5),
                   "Text below 3:1 is effectively invisible in the dark theme, and it is the text that explains what a tool did. The fix is a token swap plus a guard so it does not come back.", "WCAG 2.2 AA; the existing palette contrast test already stops at ink-3.")
    mrow = lambda moment, what: f'<div style="display: grid; grid-template-columns: 170px 1fr; gap: 12px; padding: 7px 0; border-top: 0.5px solid {LINE}"><span style="font-size: 13px; color: {INK}">{moment}</span>{para(what, 12.5)}</div>'
    old_m = (mrow("Loops", "pulse 1.4s and 1.6s side by side; spin 0.7s, 0.9s, 1s; shimmer 1.5s") + mrow("Reduced motion", "covers five anim classes; every loop keeps running")
             + mrow("New turn", "appears instantly") + mrow("Streaming", "text appears, no sign of life at the edge") + mrow("Modal exit", "unmounts, no exit") + mrow("Phone keyboard", "composer jumps after the keyboard lands"))
    new_m = (mrow("Tokens", "--dur-1 120 ms · --dur-2 200 ms · --dur-loop 1.4 s · one ease") + mrow("Reduced motion", "one global rule stops every loop and fades")
             + mrow("New turn", "rises 8 px and fades in, 200 ms, only the newest") + mrow("Streaming", "the newest slice fades in 150 ms; nothing earlier re-animates")
             + mrow("Reasoning", "collapses to “Thought for Xs” when the answer lands") + mrow("Phone keyboard", "useAnimatedKeyboard moves the composer frame by frame"))
    p6 = proposal("motion", "Motion where the eye needs it", ["both"], "M", old_m, new_m,
                  "Motion is the cue that something changed. Today the moments that matter (a new turn, the streaming edge, the keyboard) are static while decorative loops run at six unrelated speeds and ignore the user's reduced-motion setting.",
                  "Claude and ChatGPT fade only the newest text; Dia's polish is mostly fluid motion; iOS expects the input to ride the keyboard.")
    brow = lambda a, b: f'<div style="display: grid; grid-template-columns: 150px 1fr; gap: 12px; padding: 7px 0; border-top: 0.5px solid {LINE}"><span style="font-size: 13px; color: {INK}">{a}</span>{para(b, 12.5)}</div>'
    old_b = brow("Buttons", "Button 5 variants at 24/28/32/40, IconBtn in 46 places, two ActionLinks, raw buttons in the header menu, settings and sidebar") + brow("Tooltips", "Tip (52), Tooltip (2) and 36 native titles") + brow("Icons", "12 or 13 px set inline; message actions 24 px for the user, 26 for the agent")
    new_b = brow("Buttons", "one Button: primary, secondary, ghost, danger × sm 28, md 32, lg 40, with iconOnly") + brow("Tooltips", "one Tip, keyboard hint included") + brow("Icons", "--icon-sm 14 · --icon-md 16, one size per context")
    p13 = proposal("controls", "One set of controls", ["desktop"], "M", old_b, new_b,
                   "Every parallel control is a place where a hover, a focus ring or a size drifts. Collapsing them is invisible to users when done well, and makes every later polish land everywhere at once.", "Linear's 2026 refresh rebuilt its controls on one primitive set.")
    return board("Proposals · foundations", "Type, contrast, motion and controls: the layer every screen inherits.", p5 + p10 + p6 + p13, 2060)


def m_tool_row(icon, name, summary, state="done"):
    color = {"done": INK3, "failed": DANGER_FILL}[state]
    return (f'<div style="display: flex; align-items: center; gap: 10px; min-height: 44px; padding: 0 16px">{ic(icon, 16, color)}'
            f'<div style="flex: 1; display: flex; flex-direction: column"><span style="font-family: {MONO}; font-size: 13px; font-weight: 500; color: {DANGER if state == "failed" else INK}">{name}</span><span style="font-size: 13px; color: {INK2}">{summary}</span></div>{ic("chev-r", 14, INK3)}</div>')


def sheet(title, inner):
    return (f'<div style="margin: 0 16px; border-radius: 18px 18px 0 0; background: {PANE}; border: 0.5px solid {LINE2}; padding: 8px 0 16px; box-shadow: 0 -10px 40px rgba(11,17,23,0.10)">'
            f'<div style="width: 36px; height: 4px; border-radius: 2px; background: {INK4}; margin: 0 auto 10px"></div><div style="padding: 0 16px; font-size: 17px; font-weight: 600; margin-bottom: 10px">{title}</div>{inner}</div>')


def mobile():
    comp_old = phone(m_composer("Open a fix for the lint error") + para("Return sends, so a second line is impossible. The model is an 11 pt label in the header that opens the full settings screen.", 12.5))
    chip = f'<span style="display: inline-flex; align-items: center; gap: 6px; height: 32px; padding: 0 12px; border-radius: 16px; background: {HOVER}">{ic("sun", 13, INK3)}<span style="font-size: 13px">sonnet-4 · medium</span>{ic("chev-d", 12, INK3)}</span>'
    send = f'<span style="width: 36px; height: 36px; border-radius: 12px; background: {AMBER}; display: inline-flex; align-items: center; justify-content: center">{ic("up", 16, "#0b1117")}</span>'
    comp_new = phone(f'<div style="padding: 8px 16px"><div style="display: flex; flex-direction: column; gap: 10px; padding: 14px 16px 10px; border-radius: 18px; border: 0.5px solid {LINE2}">'
                     f'<span style="font-size: 16px; line-height: 1.45">Open a fix for the lint error<br>and add a test for it</span>'
                     f'<div style="display: flex; align-items: center; gap: 10px">{ic("clip", 20, INK3)}{chip}<span style="flex: 1"></span>{send}</div></div></div>'
                     + para("Return adds a line on phones; a hardware keyboard on a Fold still sends on Return. The chip opens a sheet with models and effort.", 12.5))
    p4 = proposal("composer", "A phone composer for real prompts", ["mobile"], "S", comp_old, comp_new,
                  "Agent prompts run to several lines, and the model is the setting people change most. Both are one tap away in every mainstream chat app and both are hard today.",
                  "ChatGPT and Claude put the model in the composer and send only from the button; Zed switches model from the composer.", w=440)
    tool_old_m = phone(f'<div style="padding: 0 16px; display: flex; align-items: center; gap: 8px; font-family: {MONO}; font-size: 12px">{ic("chip", 14, DANGER_FILL)}<span style="color: {DANGER}">shell</span><span style="color: {INK2}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis">cmd=npm run lint --fix --max-warn…</span></div>'
                       + para("One truncated line. What ran, what came back and why it failed stay on the desktop.", 12.5))
    tool_new_m = phone(m_tool_row("file", "read_file", "deploy.log · 200 lines") + m_tool_row("terminal", "shell", "npm run lint · failed", "failed")
                       + sheet("shell · failed in 4.1s", f'<div style="margin: 0 16px; padding: 10px 12px; border-radius: 10px; background: {SIDE}; font-family: {MONO}; font-size: 12.5px; line-height: 1.6">$ npm run lint --fix<br><span style="color: #c14545">src/app.ts:14 no-unused-vars</span><br>1 error</div>'
                               f'<div style="display: flex; gap: 10px; padding: 12px 16px 0">{mono("Copy output", 13, INK)}{mono("Copy command", 13, INK2)}</div>'))
    p12 = proposal("msteps", "Steps you can open on the phone", ["mobile"], "S", tool_old_m, tool_new_m,
                   "The phone is where people check on an agent away from the desk. If a failed step cannot be read there, the phone can only say that something went wrong, not what.",
                   "ChatGPT and Codex open a step into a sheet with its full input and output.", w=440)
    hrow = lambda a, b: f'<div style="display: grid; grid-template-columns: 170px 1fr; gap: 12px; padding: 7px 0; border-top: 0.5px solid {LINE}"><span style="font-size: 13px; color: {INK}">{a}</span>{para(b, 12.5)}</div>'
    hap_old = hrow("Toggle, typed confirm", "the only two controls with haptics") + hrow("Long press", "bubble dims to 85%, menu has Copy · Edit · Retry") + hrow("Targets", "wide rows 36 pt, Latest 36 pt, reasoning 11 pt, xxs 9 pt in the scale") + hrow("Fold and tablet", "portrait locked; roster hidden under 800 px; panes swap with no transition")
    hap_new = (hrow("Send, stop", "light impact") + hrow("Long press, refresh", "selection tick; the bubble scales to 0.98; menu adds Select text") + hrow("Approval, question", "warning notification the moment the sheet opens")
               + hrow("Targets", "44 pt (48 dp) minimum; secondary chat text 12 pt or more; chrome capped at 1.3× font scale") + hrow("Fold and tablet", "tablets rotate; roster from 600 px in landscape; 120 ms crossfade"))
    p11 = proposal("native", "Feels native under the thumb", ["mobile"], "M", hap_old, hap_new,
                   "Haptics, target size and type size are what make a phone app feel made for the phone. Each is small; together they are the gap between a web view and a native app.",
                   "Apple HIG and Material 3 minimums; Claude and ChatGPT tick on send and on long press; Codex splits list and task on iPad.", w=560)
    return board("Proposals · phone and Fold", "The composer, the steps and the feel of the phone client.", p4 + p12 + p11, 1720)


PROPOSAL_BOARDS = [
    ("Proposals-Overview.dc.html", overview, 1900, "Overview · ranked proposals"),
    ("Proposals-Conversation.dc.html", conversation, 1860, "Conversation"),
    ("Proposals-Activity.dc.html", activity, 1330, "Agents at work"),
    ("Proposals-Navigation.dc.html", navigation, 1300, "Navigation"),
    ("Proposals-Foundations.dc.html", foundations, 2060, "Foundations"),
    ("Proposals-Mobile.dc.html", mobile, 1720, "Phone and Fold"),
]
