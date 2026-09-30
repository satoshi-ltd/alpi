from gen import ic, mix, page
from desktop_boards import INK, INK2, INK3, LINE, MONO
from conversation_boards import AMBER, DANGER_FILL, SUCCESS, WARNING, h1, label, mono

DOC = "#3a7ca5"

PROPOSALS = [
    ("remote", "mobile", "Running work", "A Live Activity for a running workgroup, updated from the daemon, and approval pushes that arrive with the app closed.", "Both need a remote push path (APNs / FCM relay) the daemon does not have; today the phone polls every 15 minutes in the background and only shows actionable approval notifications it has already fetched.", "ChatGPT, Codex", "L"),
    ("controls", "both", "Button sizes", "Move Button heights to 28 / 32 / 40 on both clients.", "The shared button tokens in common/button.mjs drive both apps, so the change needs a paired release and a pass over every dense toolbar.", "Linear", "S"),
    ("reasoning", "desktop", "Step order", "Place the reasoning row between the tool rows in the order they happened, not after all of them.", "Inside the opened block the order is already chronological; the row itself still sits below the tool list.", "Claude, Zed", "S"),
]

NUM = {key: i for i, (key, *_rest) in enumerate(PROPOSALS, start=1)}

ALIGNED = [
    ("Message layout", "User in a tinted bubble, the reply full width with no avatar, one centred column. The same grammar as ChatGPT and Claude."),
    ("Stop in place", "Send turns into Stop where the finger already is, on both clients."),
    ("Grouped steps", "“+N previous tool calls” with the failure count visible while collapsed is the pattern Perplexity and Copilot converged on."),
    ("Model in the composer", "Both clients keep the model picker in the composer row, as Zed and Claude do."),
    ("One token file", "Shared tokens with parity tests on both sides, and an accent kept rare enough to mean something."),
    ("Sticky scroll", "Follow while streaming, stop when the user scrolls up, a Latest pill to come back."),
]


def tag(text):
    tone = {"desktop": mix(AMBER, 0.22), "mobile": mix(DOC, 0.2), "both": mix("#9d4dc6", 0.2), "S": mix(SUCCESS, 0.18), "M": mix(WARNING, 0.2), "L": mix(DANGER_FILL, 0.16)}[text]
    return f'<span style="display: inline-flex; align-items: center; height: 18px; padding: 0 8px; border-radius: 16px; background: {tone}; color: {INK}; font-family: {MONO}; font-size: 11px; white-space: nowrap">{text}</span>'


def para(text, size=13, color=INK2, extra=""):
    return f'<p style="margin: 0; font-size: {size}px; line-height: 1.55; color: {color}; {extra}">{text}</p>'


def board(title, sub, body, h):
    return page(title, 1280, h, f'<div style="padding: 40px 48px; display: flex; flex-direction: column; gap: 26px; box-sizing: border-box">{h1(title, sub)}{body}</div>')


def overview():
    head_cols = "28px 76px 130px 1fr 1fr 150px 44px"
    head = (f'<div style="display: grid; grid-template-columns: {head_cols}; gap: 14px; padding-bottom: 8px; font-family: {MONO}; font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase; color: {INK3}">'
            '<span></span><span>client</span><span>area</span><span>proposal</span><span>why it is still open</span><span>seen in</span><span>effort</span></div>')
    rows = "".join(
        f'<div style="display: grid; grid-template-columns: {head_cols}; gap: 14px; align-items: start; padding: 11px 0; border-top: 0.5px solid {LINE}">'
        f'{mono(f"{i:02d}", 12)}<span>{tag(who)}</span><span style="font-size: 13px; font-weight: 600">{area}</span>{para(what, 12.5, INK)}{para(why, 12.5)}{para(seen, 12, INK3)}<span>{tag(effort)}</span></div>'
        for i, (_key, who, area, what, why, seen, effort) in enumerate(PROPOSALS, start=1)
    )
    aligned = "".join(
        f'<div style="display: flex; flex-direction: column; gap: 4px; padding: 14px; border-radius: 10px; background: {mix(SUCCESS, 0.08)}"><span style="display: inline-flex; align-items: center; gap: 6px; font-size: 13px; font-weight: 600">{ic("check", 13, SUCCESS)}{t}</span>{para(d, 12.5)}</div>'
        for t, d in ALIGNED
    )
    verdict = para(
        "The review of both clients against the agent and chat apps shipping now landed in alpi 0.16.0, desktop 0.7.0 and mobile 0.6.0: steps you can open, what each agent is doing and what waits on you, reasoning that gets out of the way, one type scale, real contrast, motion where the eye needs it, and a phone that feels native. The System page shows the result. Only what is below is still open.",
        14, INK, "max-width: 1080px")
    body = (f'{verdict}<div style="display: flex; flex-direction: column">{label("Still open")}<div style="height: 12px"></div>{head}{rows}</div>'
            f'<div style="display: flex; flex-direction: column; gap: 10px">{label("In line with the field · keep")}'
            f'<div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px">{aligned}</div></div>')
    return board("Where Alpi could go next", "What is left from the UX and UI review. A row leaves this table when it ships.", body, 790)


PROPOSAL_BOARDS = [
    ("Proposals-Overview.dc.html", overview, 790, "Still open"),
]
