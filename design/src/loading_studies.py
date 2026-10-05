import folds
from notif_studies import dot, flex, stack, wrap
from wg_settings_studies import P, accent, caption, crease_name, glyph, labelled, mono, phase_chip, phone, rippling
from wg_strip_studies import CHAIN, d_header, frame, hub_task, m_header, now_trigger, sep

BUSY = [accent(name) for name in ("mira", "pixel", "scout", "muse", "quill", "lingua", "lens")]


def alpaca(size, key):
    style = folds.busy_style(key, BUSY, 4.8)
    svg = folds.fold("alpaca", BUSY[0], size, facet_attrs=folds.busy_attrs(key, 4.8))
    return f'<span role="img" aria-label="Loading" style="display: inline-flex; flex-shrink: 0">{style}{svg}</span>'


def arc(size=13, colour=None):
    colour = colour or P["ink2"]
    return (f'<svg viewBox="0 0 16 16" width="{size}" height="{size}" fill="none" stroke="{colour}" stroke-width="1.5" stroke-linecap="round" style="flex-shrink: 0">'
            f'<path d="M8 2a6 6 0 1 0 6 6"/></svg>')


def spokes(size=18):
    lines = "".join(f'<line x1="12" y1="3" x2="12" y2="7" stroke="{P["ink3"]}" stroke-width="2" stroke-linecap="round" opacity="{0.25 + i * 0.09:.2f}" '
                    f'transform="rotate({i * 45} 12 12)"/>' for i in range(8))
    return f'<svg viewBox="0 0 24 24" width="{size}" height="{size}" style="flex-shrink: 0">{lines}</svg>'


def bar(w, h=10):
    return f'<span style="display: inline-block; width: {w}px; height: {h}px; border-radius: 2px; background: {P["hover"]}; flex-shrink: 0"></span>'


def ghost_chip(inner):
    return f'<span style="display: inline-flex; align-items: center; gap: 6px; height: 21px; padding: 0 6px; border-radius: 2px; flex-shrink: 0">{inner}</span>'


def strip_row(*parts):
    return (f'<div style="display: flex; flex-wrap: wrap; align-items: center; gap: 6px 5px; padding: 9px 16px; box-shadow: inset 0 -0.5px 0 {P["line"]}">'
            f'{"".join(parts)}</div>')


def d_now():
    return frame(d_header(now_trigger()), strip_row(ghost_chip(arc() + mono("Loading flow…", 11, P["ink2"]))), hub_task("qa", "audit the built dist read-only…", ""))


def pending_chain(key):
    return "".join((sep() if i else "") + phase_chip(slug, None, f"{key}{i}", strong=True) for i, slug in enumerate(CHAIN))


def d_known():
    return frame(d_header(now_trigger()), strip_row(pending_chain("lp")), hub_task("qa", "audit the built dist read-only…", ""))


def d_unknown():
    bars = "".join((sep() if i else "") + bar(w, 21) for i, w in enumerate((62, 70, 66, 70, 74)))
    return frame(d_header(now_trigger()), strip_row(rippling("mira", 13, "lu"), bars))


def specimen(mark, name, note):
    return stack(f'<div style="height: 84px; display: flex; align-items: center; justify-content: center; border-radius: 4px; background: {P["pane"]}; '
                 f'box-shadow: 0 0 0 1px {P["line2"]}">{mark}</div>', mono(name, 10.5, P["ink2"]), wrap(note, 11, P["ink3"], lh=1.4), gap=6, extra="width: 200px")


def now_inventory():
    send = (f'<span style="width: 30px; height: 30px; border-radius: 999px; background: {P["ink"]}; display: inline-flex; align-items: center; justify-content: center">'
            f'{arc(14, P["pane"])}</span>')
    text = mono("Loading…", 12, P["ink3"])
    return flex(
        specimen(arc(18), "SpinnerIcon", "desktop: Send, attachments, read aloud, the flow chip"),
        specimen(send, "Button · Chip spinner", "two more CSS arcs, chipSpin and btnSpin"),
        specimen(text, "Loading…", "the skill viewer and the email cell print the word alone"),
        specimen(spokes(), "ActivityIndicator", "mobile: 25 screens, iOS spokes and an Android ring"),
        gap=14, align="flex-start", extra="flex-wrap: wrap",
    )


def scales():
    return flex(
        specimen(alpaca(56, "a1"), "alpi · 56", "boot and an empty page: nobody owns the wait"),
        specimen(flex(alpaca(18, "a2"), mono("reaching the daemon", 11, P["ink2"]), gap=7), "alpi · 18 + word", "a page that waits on the daemon, with what it waits for"),
        specimen(flex(rippling("lens", 18, "o1"), crease_name("lens", 15), gap=7), "owner · 18", "a profile’s skills, schedules or memories: its own object sweeps"),
        specimen(f'<span style="width: 30px; height: 30px; border-radius: 999px; background: {P["ink"]}; display: inline-flex; align-items: center; justify-content: center">'
                 f'{alpaca(16, "a3")}</span>', "inside a control · 16", "Send, Button and Chip keep their size; the mark replaces the arc"),
        gap=14, align="flex-start", extra="flex-wrap: wrap",
    )


def list_row(i):
    return flex(bar(14, 14), stack(bar(80 + (i % 3) * 20), bar(110 + (i % 2) * 20, 8), gap=6), gap=10, extra=f"padding: 12px 14px; box-shadow: inset 0 -0.5px 0 {P['line']}")


def d_list():
    head = flex(rippling("lens", 18, "dl"), crease_name("lens", 16), mono("skills", 11, P["ink3"]), gap=8, extra=f"padding: 12px 14px; box-shadow: inset 0 -0.5px 0 {P['line']}")
    return frame(head, *(list_row(i) for i in range(4)))


def m_list_now():
    body = f'<div style="flex: 1; display: flex; align-items: center; justify-content: center; background: {P["bg"]}">{spokes(22)}</div>'
    return phone(m_title("Skills") + body, 300, 200)


def m_title(value, lead=""):
    back = glyph("chevron-left", 20, P["ink2"])
    return flex(back, lead, mono(value, 15, P["ink"], 600), gap=8, extra=f"height: 48px; padding: 0 12px; background: {P['bg']}")


def m_list_proposed():
    rows = "".join(f'<div style="margin: 0 12px; border-radius: 4px; background: {P["pane"]}">{list_row(i)}</div>' for i in range(3))
    return phone(m_title("Skills", rippling("lens", 16, "ml")) + f'<div style="display: flex; flex-direction: column; gap: 8px; padding-top: 4px">{rows}</div>', 300, 200)


def m_strip():
    chips = "".join((sep(12) if i else "") + phase_chip(slug, None, f"mk{i}", strong=True, height=30, size=12) for i, slug in enumerate(CHAIN[:3]))
    return (f'<div style="height: 46px; display: flex; align-items: center; gap: 6px; padding: 0 12px; overflow: hidden; white-space: nowrap; background: {P["pane"]}; '
            f'box-shadow: inset 0 -0.5px 0 {P["line"]}">{chips}</div>')


def m_now_strip():
    return (f'<div style="height: 38px; display: flex; align-items: center; gap: 8px; padding: 0 16px; background: {P["pane"]}; box-shadow: inset 0 -0.5px 0 {P["line"]}">'
            f'{spokes(14)}{mono("Loading flow…", 12, P["ink3"])}</div>')


def m_chat():
    return f'<div style="flex: 1; background: {P["bg"]}"></div>'


def m_button():
    return f'<span style="width: 44px; height: 44px; display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0">{rippling("mira", 14, "mb")}</span>'


def side(drawing, note):
    return flex(drawing, caption(note), gap=16, align="flex-start")


def loading_now():
    return stack(
        labelled("Desktop · opening a workgroup", d_now(),
                 "A ghost chip with a line arc and “Loading flow…” until host.workgroup.tasks answers, although the workgroup row already declares the pipelines and phase_map, so the chain and its owners are known before the run state is."),
        labelled("Four ways to wait", now_inventory(), "None of them is alpi’s: two CSS arcs, an SVG arc, a bare word and the platform indicator, each in its own size and grey."),
        labelled("Mobile · strip and lists", flex(phone(m_header(dot(accent("mira"), 6)) + m_now_strip() + m_chat(), 200, 240), m_list_now(), gap=16, align="flex-start"),
                 "The platform spinner centred on an empty page: the layout jumps when the rows arrive."),
        gap=22,
    )


def loading_proposed():
    return stack(
        labelled("Who waits draws the wait", scales(),
                 "Nothing owns the wait: the alpaca folds through the profile colours (the busy cycle). A profile owns it: that profile’s object sweeps its three tones. Both stop under reduced motion and keep the word."),
        labelled("Desktop · the chain is known before the run", d_known(),
                 "With one pipeline, or a cached run, the strip draws at once from the workgroup row: every phase pending with its owner’s object, filled in place when the run state arrives. No word, no layout shift."),
        labelled("Desktop · several pipelines, nothing cached", d_unknown(),
                 "The hub’s object sweeps beside placeholder chips the size of a phase; the real chain replaces them."),
        labelled("Desktop · lists", d_list(), "Skills, schedules, memories, outputs and email: placeholder rows in the shape of the list under the owner’s sweeping object."),
        labelled("Mobile · strip and lists", flex(phone(m_header(m_button()) + m_strip() + m_chat(), 200, 240), m_list_proposed(), gap=16, align="flex-start"),
                 "The same rules: the pending chain from the row, placeholder rows inside the cards they will fill, the owner’s object in the title."),
        gap=22,
    )
