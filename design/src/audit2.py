from gen import ALPI_ACCENT, DANGER, DOC_ACCENT, mix, page
from desktop_boards import HOVER, INK, INK2, INK3, LINE, MONO

OPEN = [
    ("mobile", "Selected state", "Seven selected styles remain: PickerRow dot, radio, pill, role card, member chip, “in link” pill, swatch ring. Only ActionSheet pickers gained the mark.", "One selected style everywhere, the PickerRow's."),
    ("desktop", "Dismiss as an action", "A backdrop click closes every form modal with no dirty guard, and a stray click kills a live pairing code.", "Dirty guard on the Create dialogs; the pairing dialog ignores the backdrop while a code is pending."),
    ("desktop", "Budget editor", "Profiles use BudgetEdit (Selectish, Cancel + Save); workgroups use BudgetEditor (Edit button, Save only).", "One editor that validates and can clear the cap."),
    ("desktop", "Text inputs", "Create profile and the provider form use raw 40 px inputs; Create workgroup uses the 32 px Field.", "Field everywhere."),
    ("desktop", "Unreachable daemons", "Notifications drop an unreachable daemon silently, so the list can look complete when it is not.", "Say which daemons did not answer, as mobile does."),
    ("mobile", "Failed loads", "MCP, skills and tools still show their empty row when the read fails.", "Inline “Couldn’t load” with Retry, as email and memories do."),
]


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
{head}
{rows}
</div>"""
    return page("Open work", 1280, 140 + 90 * len(OPEN) + 120, body)
