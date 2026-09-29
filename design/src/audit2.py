from gen import ALPI_ACCENT, DANGER, DOC_ACCENT, mix, page
from desktop_boards import HOVER, INK, INK2, INK3, LINE, MONO

OPEN = []


EMPTY_ROW = f'<div style="padding: 18px 0; border-top: 0.5px solid {LINE}; font-size: 14px; color: {INK2}">Nothing open. Both clients match the design; new findings land here first.</div>'


def audit2_board():
    tone = {"mobile": (mix(DOC_ACCENT, 0.22), INK), "desktop": (mix(ALPI_ACCENT, 0.22), INK), "both": (mix("#9d4dc6", 0.22), INK)}
    tag = lambda who: f'<span style="display: inline-flex; align-items: center; height: 18px; padding: 0 8px; border-radius: 16px; background: {tone[who][0]}; color: {tone[who][1]}; font-family: {MONO}; font-size: 11px; white-space: nowrap">{who}</span>'
    cell = lambda t, c=INK2, w=400: f'<span style="font-size: 13px; line-height: 1.5; color: {c}; font-weight: {w}">{t}</span>'
    head = f'<div style="display: grid; grid-template-columns: 22px 80px 170px 1fr 1fr; gap: 16px; padding: 0 0 8px; font-family: {MONO}; font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase; color: {INK3}"><span></span><span>client</span><span>topic</span><span>today</span><span>next</span></div>'
    rows = "".join(
        f'<div style="display: grid; grid-template-columns: 22px 80px 170px 1fr 1fr; gap: 16px; align-items: start; padding: 12px 0; border-top: 0.5px solid {LINE}"><span style="font-family: {MONO}; font-size: 12px; color: {INK3}">{i:02d}</span>{tag(who)}{cell(topic, INK, 600)}{cell(now)}{cell(nxt, INK)}</div>'
        for i, (who, topic, now, nxt) in enumerate(OPEN, start=1)
    )
    body = f"""<div style="padding: 40px 48px; display: flex; flex-direction: column; gap: 10px; height: 100%; box-sizing: border-box">
<span style="font-family: {MONO}; font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase; color: {INK3}">Open work · {len(OPEN)} items</span>
<span style="font-size: 30px; font-weight: 600; letter-spacing: -0.02em; line-height: 1.15">What is left between the two clients</span>
<span style="font-size: 13px; line-height: 1.5; color: {INK3}; max-width: 900px">Only pending work lives here. A row leaves this table the moment it ships; what shipped is in each client's changelog.</span>
<div style="height: 18px"></div>
{head if OPEN else ""}
{rows or EMPTY_ROW}
</div>"""
    return page("Open work", 1280, 140 + 90 * len(OPEN) + 120, body)
