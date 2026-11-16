import marks
from conversation_boards import (DANGER, DANGER_FILL, DOC_ACCENT, INK, INK2, INK3, LINE, MONO, PANE, d_bucket, d_step, d_thinking, d_thought, ic, m_bucket, m_reasoning, m_tool,
                                 m_process, mi, mono, process, step_body, thinking)
from volume_cap_proposal import column, section, text, well

MARK = 24
VERBS = (("thinking", "Thinking"), ("read_file", "Reading"), ("grep", "Searching"), ("shell", "Running"), ("web_fetch", "Fetching"), ("memory", "Remembering"), ("send_message", "Messaging"))


def mark(state="working"):
    return marks.shape_mark("bell", DOC_ACCENT, MARK, state=state, seed=f"work-{state}")


def chev(open_=False, phone=False):
    glyph = mi("chev-r", 16, INK3) if phone else ic("chev-r", 14, INK3)
    return glyph.replace('style="', 'style="transform: rotate(90deg); ', 1) if open_ else glyph


def work_line(state="running", action="Reading <span style=\"font-family: %s; font-size: 14px\">deploy.log</span>" % MONO, secs="12s", steps=6, failed=0, open_=False, phone=False):
    h, size, pad = (36, 16, 16) if phone else (32, 15, 0)
    if state == "running":
        lead = f'<span style="font-size: {size}px; font-weight: 500; color: {INK}">Working</span>'
        detail = f'<span style="flex: 1; min-width: 0; font-size: {size}px; color: {INK3}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis">{action}…</span>'
        tail = mono(secs, 12)
        glyph = mark("working")
    else:
        lead = f'<span style="font-size: {size}px; font-weight: 500; color: {INK2}">Worked for {secs}</span>'
        fail = (f'<span style="display: inline-flex; align-items: center; gap: 4px">{ic("alert", 14, DANGER_FILL)}<span style="font-size: {size - 1}px; color: {DANGER}">{failed} failed</span></span>' if failed else "")
        detail = f'<span style="flex: 1; min-width: 0; display: inline-flex; align-items: center; gap: 8px; font-size: {size}px; color: {INK3}; white-space: nowrap">· {steps} steps{fail}</span>'
        tail = ""
        glyph = mark("failed" if state == "failed" else "idle")
    return (f'<div role="button" aria-expanded="{"true" if open_ else "false"}" style="display: flex; align-items: center; gap: 10px; height: {h}px; padding: 0 {pad}px">'
            f'{glyph}{lead}{detail}{tail}{chev(open_, phone)}</div>')


def answer(phone=False):
    size = 16
    pad = "0 16px" if phone else "0"
    return (f'<div style="padding: {pad}; font-size: {size}px; line-height: 1.6; color: {INK}">Two of yesterday’s deploys failed: <b>billing-api</b> exited 1 on migrations and '
            f'<b>web</b> timed out on health checks. The other four went out clean.</div>')


def timeline(*rows, phone=False):
    inset = "margin: 4px 0 4px 27px" if phone else "margin: 2px 0 2px 11px"
    return f'<div style="{inset}; padding-left: 12px; border-left: 2px solid {LINE}; display: flex; flex-direction: column; gap: 2px">{"".join(rows)}</div>'


def surface(*items, w=None, phone=False):
    width = f"width: {w}px; " if w else ""
    pad = "16px 0" if phone else "20px"
    return f'<div style="{width}display: flex; flex-direction: column; gap: 12px; padding: {pad}; background: {PANE}; border-radius: 12px; border: 0.5px solid {LINE}">{"".join(items)}</div>'


def stage(label, inner):
    return column(text(label, 12, INK3, mono=True), inner, gap=8)


def desktop_now():
    running = process(d_thought(secs="3s"), d_step("read_file", "deploy.log · first 200 lines", "0.2s"), d_step("web_fetch", "status.example.com", "3s", "running"), d_thinking())
    done = process(d_thought(secs="3s"), d_bucket("6 tool calls · 2 thoughts", 1))
    return column(stage("while it works", surface(running)), stage("after the answer", surface(done, answer())),
                  text("Today the work is a stack: a thought row with a 14 px mark, one row per tool, a live Thinking… row and a bucket that only appears from two tools on. The stack grows and shrinks while the agent works, and at 14 px the mark is below the 20 px where motion starts, so it never turns."), gap=16)


def desktop_proposed():
    open_ = timeline(d_thought(secs="3s"), d_step("read_file", "deploy.log · first 200 lines", "0.2s"), d_step("grep", "3 matches for exit=1", "0.1s"),
                     d_step("shell", "npm run lint", "4.1s", "failed", step_body(["$ npm run lint", '<span style="color: #c14545">src/app.ts:14  no-unused-vars</span>'])),
                     d_step("web_fetch", "status.example.com", "3s"), d_thought(secs="2s"))
    return column(stage("while it works", surface(work_line("running"))),
                  stage("after the answer", surface(work_line("done", secs="34s", steps=6, failed=1), answer())),
                  stage("opened", surface(work_line("done", secs="34s", steps=6, failed=1, open_=True), open_, answer())),
                  text("One line per turn. While it works the line names the current step in plain words and counts up; when the answer lands it settles into what it cost. The mark is the profile’s own at 24 px, the DS row size, so the working turn plays. Opening it shows today’s steps on a rail, unchanged."), gap=16)


def phone_now():
    running = m_process(m_reasoning(secs="3s"), m_tool("read_file", "deploy.log"), m_tool("web_fetch", "status.example.com", "running"), thinking(size=12, h=20, pad=16, glyph=12, label=12))
    done = m_process(m_reasoning(secs="3s"), m_bucket("6 tool calls · 2 thoughts", 1))
    return column(stage("while it works", surface(running, w=360, phone=True)), stage("after the answer", surface(done, answer(True), w=360, phone=True)),
                  text("The phone stacks 28 pt tool rows under a 12 pt mark, and the bucket only appears after the turn."), gap=16)


def phone_proposed():
    rows = timeline(m_reasoning(secs="3s"), m_tool("read_file", "deploy.log"), m_tool("shell", "npm run lint", "failed"), m_tool("web_fetch", "status.example.com"), phone=True)
    return column(stage("while it works", surface(work_line("running", action="Fetching status.example.com", secs="8s", phone=True), w=360, phone=True)),
                  stage("after the answer", surface(work_line("done", secs="34s", steps=6, failed=1, phone=True), answer(True), w=360, phone=True)),
                  stage("opened", surface(work_line("done", secs="34s", steps=6, failed=1, open_=True, phone=True), rows, answer(True), w=360, phone=True)),
                  text("The same line at 36 pt, with the 24 pt row mark; a tap opens the steps in place and a step still opens its detail sheet."), gap=16)


def states():
    rows = (
        ("thinking", work_line("running", action="Thinking", secs="2s")),
        ("a tool runs", work_line("running", action="Searching <span style=\"font-family: %s; font-size: 14px\">exit=1</span>" % MONO, secs="5s")),
        ("waits for you", work_line("running", action="Waiting for your approval", secs="9s").replace(mark("working"), mark("needs"))),
        ("done", work_line("done", secs="34s", steps=6)),
        ("a step failed", work_line("done", secs="34s", steps=6, failed=1)),
        ("stopped", work_line("done", secs="11s", steps=2).replace("Worked for", "Stopped after")),
    )
    grid = "".join(f'<div style="display: grid; grid-template-columns: 140px 1fr; gap: 16px; align-items: center; padding: 6px 0; border-bottom: 0.5px solid {LINE}">{text(k, 13, INK, mono=True)}{v}</div>' for k, v in rows)
    return column(well(column(grid, gap=0), bg=PANE), text("The words come from the step: " + ", ".join(f"<code>{t}</code> {v.lower()}" for t, v in VERBS)
                  + ". Only the newest step speaks; its target is the summary today’s step row already computes. The mark wears the profile’s state: working, needs while an approval or question waits, idle once done; a failed step only adds the count."), gap=12)


def extra():
    return column(section("Every state of the line", states()), gap=34)


PROPOSAL = {
    "id": "CHAT.WORKLINE",
    "client": "mobile · desktop",
    "area": "chat · thinking and tool calls",
    "title": "A turn’s work is one line that names what it is doing and opens into the steps",
    "why": ("Today a turn shows its work as a growing stack of thought and tool rows with a 14 px mark, and folds them into a bucket only from two tools on, so the answer jumps while it streams. "
            "Other assistants keep the work to one line that updates and opens on demand. Recommended: one line per turn with the profile’s mark at the 24 px row size, so the working turn animates, "
            "a plain-words current step and a running clock; after the answer it reads what the work took, and opening it shows today’s steps on a rail."),
    "rows": ("Desktop", "Phone"),
    "mobile": (desktop_now, desktop_proposed),
    "desktop": (phone_now, phone_proposed),
    "extra": extra,
    "accept": ("<code>ProcessBlock</code> on desktop and the phone’s process rows render one work line per turn: the profile’s mark at <code>MARK_SIZES.row</code> in the turn’s state, Working with the newest step in plain words and a clock while it runs, "
               "Worked for, the step count and any failures once done, Stopped after when the user stops it; it opens to today’s steps on a rail and keeps their per-step open state; the step verbs live in <code>common/</code> with a test; "
               "reduce motion keeps the mark still; the conversation boards on Desktop and Mobile are redrawn and this board is deleted."),
    "h": 2440,
}
