import re

import volume_cap_proposal
import work_line_proposal
from desktop_boards import INK3, MONO


def as_rgb(html):
    return re.sub(r"#([0-9a-fA-F]{6})\b", lambda m: "rgb({}, {}, {})".format(*(int(m.group(1)[i:i + 2], 16) for i in (0, 2, 4))), html)


def stack(*items, gap=10):
    return f'<div style="display: flex; flex-direction: column; gap: {gap}px">{"".join(items)}</div>'


def hrow(*items, gap=8):
    return f'<div style="display: flex; flex-wrap: wrap; gap: {gap}px; align-items: center">{"".join(items)}</div>'


def caption(text):
    return f'<span style="font-size: 12px; line-height: 1.45; color: {INK3}">{text}</span>'


def labelled(text, inner):
    return stack(f'<span style="font-family: {MONO}; font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase; color: {INK3}">{text}</span>', inner, gap=6)


PROPOSALS = [work_line_proposal.PROPOSAL, volume_cap_proposal.PROPOSAL]
