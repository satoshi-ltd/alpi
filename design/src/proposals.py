from gen import page
from desktop_boards import INK, INK3
from conversation_boards import h1, label, mono, spec

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


PROPOSALS = []


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
