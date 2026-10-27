from gen import page
from desktop_boards import INK
from conversation_boards import h1, label, spec

PAGE_W = 1280

from proposals_e import PROPOSALS_E
from proposals_f import PROPOSALS_F
from proposals_g import PROPOSALS_G
from proposals_h import PROPOSALS_H

PROPOSALS = PROPOSALS_E + PROPOSALS_F + PROPOSALS_G + PROPOSALS_H


def drawing(title, inner):
    return f'<div style="flex: 1; min-width: 0; display: flex; flex-direction: column">{spec(title, inner, pad=20)}</div>'


def surface_row(name, pair):
    now, proposed = pair
    right = drawing("Proposed", proposed()) if proposed else drawing("Proposed", f'<span style="font-size: 12px; color: #6b6b6b">No change on {name.lower()}.</span>')
    return (f'<div style="display: flex; flex-direction: column; gap: 10px"><span style="font-size: 17px; font-weight: 600; color: {INK}">{name}</span>'
            f'<div style="display: flex; gap: 24px; align-items: stretch">{drawing("Now", now())}{right}</div></div>')


def proposal_board(p):
    kicker = " · ".join((p["id"], p["client"], p["area"]))
    head = f'<div style="display: flex; flex-direction: column; gap: 10px">{label(kicker)}{h1(p["title"], p["why"])}</div>'
    drawings = surface_row("Mobile", p["mobile"]) + surface_row("Desktop", p["desktop"])
    accept = (f'<div style="display: flex; flex-direction: column; gap: 6px">{label("Accept")}'
              f'<p style="margin: 0; max-width: 1080px; font-size: 13px; line-height: 1.55; color: {INK}">{p["accept"]}</p></div>')
    body = (f'<div data-proposal="{p["id"]}" style="padding: 40px 48px; display: flex; flex-direction: column; gap: 26px; box-sizing: border-box">'
            f'{head}{drawings}{accept}</div>')
    return page("Proposal " + p["id"], PAGE_W, p["h"], body)


def board_name(p):
    return "Proposals-" + p["id"] + ".dc.html"


PROPOSAL_BOARDS = [(board_name(p), (lambda p=p: proposal_board(p)), p["h"], p["id"] + " · " + p["title"]) for p in PROPOSALS]
