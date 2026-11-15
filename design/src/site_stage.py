from conversation_boards import d_assistant, d_composer, d_step, d_thought, d_user, inline_request, process
from desktop_boards import DOC_ACCENT, chat_actions, d_hero, d_sidebar, h1, stream_shell
from gen import identity_glyph, m_conn_header, m_roster, m_shell_footer, m_tiles, page

DESK = (1280, 680)
PHONE = (390, 844)
BEZEL, FRAME, PHONE_RADIUS = 8, 2, 52


def root(html):
    return html[html.index("</helmet>\n") + len("</helmet>\n"):html.index("\n</x-dc>")]


def desk():
    header = d_hero(h1("doc", identity_glyph("doc", DOC_ACCENT, 28), DOC_ACCENT), "", chat_actions(), DOC_ACCENT)
    steps = process(d_thought(secs="2s"), d_step("memory", "ferritin follow-up · 2 results", "0.3s"), d_step("read_file", "labs/2026-10-panel.pdf", "0.2s"), d_step("web_fetch", "labs.example.com/availability", "1.1s"))
    stream = (f'<div style="display: flex; flex-direction: column; gap: 14px">{d_assistant("Filed the October panel under labs/2026-10 and added the ferritin result to your health notes.", meta=False, hover=False)}{d_user("Book a follow-up draw for early November.", DOC_ACCENT)}{steps}'
              f'{d_assistant("Your October ferritin came back at 18 ng/mL, and Dr. Ruiz asked for a recheck four weeks later. The lab has an opening on Tuesday the 4th at 8:10, fasting from midnight. I can book it once you allow the page.", meta=False, hover=False)}'
              f'{inline_request("@doc", "open https://labs.example.com/book?date=2026-11-04")}</div>')
    body = (f'<div style="display: flex; height: 100%">{d_sidebar(DESK[1])}<div style="flex: 1; min-width: 0; display: flex; flex-direction: column; background: #ffffff">'
            f'{header}{stream_shell(stream, d_composer(name="doc", model_name="deepseek-v4.1-flash"))}</div></div>')
    inner = root(page("Desktop · one approval", *DESK, body, bg="#ffffff"))
    return f'<div style="width: {DESK[0]}px; height: {DESK[1]}px; overflow: hidden; background: #ffffff">{inner}</div>'


def phone():
    body = (f'<div style="display: flex; flex-direction: column; height: 100%; background: #ffffff">{m_conn_header(ring="#ffffff", collapse=False, bg="#ffffff")}'
            f'<div style="flex: 1; min-height: 0; overflow: hidden">{m_tiles()}{m_roster(compact=False, tiles=False)}</div>{m_shell_footer(ring="#ffffff", border=True)}</div>')
    inner = root(page("Phone · roster", *PHONE, body))
    return (f'<div style="padding: {FRAME}px; border-radius: {PHONE_RADIUS + BEZEL + FRAME}px; background: #3a3a3a; width: fit-content">'
            f'<div style="padding: {BEZEL}px; border-radius: {PHONE_RADIUS + BEZEL}px; background: #0b0b0b">'
            f'<div style="width: {PHONE[0]}px; height: {PHONE[1]}px; overflow: hidden; border-radius: {PHONE_RADIUS}px; background: #ffffff">{inner}</div></div></div>')


SHOTS = {"desktop": (desk, DESK), "phone": (phone, (PHONE[0] + 2 * (BEZEL + FRAME), PHONE[1] + 2 * (BEZEL + FRAME)))}
