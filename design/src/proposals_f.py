from desktop_boards import INK3, LINE, button, code_chip, muted, row, section, selectish
from gen import m_group, m_row, m_section
from mobile_overlays import picker_row, sheet

PHONE_W = 390
SCALE = 0.68
FALLBACKS = (("claude-sonnet-5-5", "Anthropic"), ("gpt-6.1-sol", "OpenAI"))


def stage(inner, w, h, bg="#f6f6f6"):
    return f'<div style="position: relative; width: {w}px; height: {h}px; border-radius: 12px; background: {bg}; border: 0.5px solid {LINE}; overflow: hidden; flex-shrink: 0">{inner}</div>'


def phone(inner, h, bg="#ececec"):
    frame = stage(inner, PHONE_W, h, bg)
    return (f'<div style="width: {PHONE_W * SCALE:.0f}px; height: {h * SCALE:.0f}px; overflow: hidden; flex-shrink: 0">'
            f'<div style="width: {PHONE_W}px; height: {h}px; transform: scale({SCALE}); transform-origin: top left">{frame}</div></div>')


def pair(*items):
    return f'<div style="display: flex; gap: 16px; align-items: flex-start">{"".join(items)}</div>'


def stack(*items, gap=10):
    return f'<div style="display: flex; flex-direction: column; gap: {gap}px">{"".join(items)}</div>'


def hrow(*items, gap=8):
    return f'<div style="display: flex; flex-wrap: wrap; gap: {gap}px; align-items: center">{"".join(items)}</div>'


def caption(text):
    return f'<span style="font-size: 12px; line-height: 1.45; color: {INK3}">{text}</span>'


def model_rows_desktop(fallbacks):
    rows = (row("model", selectish("deepseek/deepseek-v4.1-flash") + selectish("Default", mono=False)) + row("fast model", muted("uses main model"))
            + row("deep model", muted("uses main model")) + row("vision model", muted("read_image uses main model")))
    return rows + fallbacks + row("budget", selectish("$1.00/day"))


def fallbacks_now_desktop():
    rows = model_rows_desktop(row("fallbacks", muted("console only · alpi setup")))
    return stage(f'<div style="padding: 20px 24px">{section("Overview", "", rows, first=True)}</div>', 540, 360, bg="#ffffff")


def fallbacks_proposed_desktop():
    chips = "".join(code_chip(f"{i} · {m} · {p}") for i, (m, p) in enumerate(FALLBACKS, 1)) + button("Add", "ghost", "sm", "plus")
    field = stack(hrow(chips, gap=6), caption("Tried in order when the main model's provider fails. Drag to reorder."), gap=4)
    rows = model_rows_desktop(row("fallbacks", field, align_top=True))
    return stage(f'<div style="padding: 20px 24px">{section("Overview", "", rows, first=True)}</div>', 540, 400, bg="#ffffff")


def model_rows_mobile(last):
    return (m_row("Model", "", "deepseek-v4.1-flash") + m_row("Reasoning", "how hard the model thinks before answering", "default")
            + m_row("Fast model", "cheap model for side-tasks &amp; delegation", "main model") + m_row("Deep model", "stronger model for escalation &amp; deep research", "main model")
            + m_row("Vision model", "image inspection via read_image", "main model", sep=last is not None) + (last or ""))


def settings_screen(rows):
    return f'<div style="padding-top: 16px; background: #ffffff; height: 100%">{m_section("Overview", first=True)}{m_group(rows)}</div>'


def fallbacks_now_mobile():
    return phone(settings_screen(model_rows_mobile(None)), 640)


def fallbacks_proposed_mobile():
    settings = settings_screen(model_rows_mobile(m_row("Fallbacks", "tried in order when the provider fails", "2", sep=False)))
    body = "".join(picker_row(f"{i} · {m}", p, False) for i, (m, p) in enumerate(FALLBACKS, 1)) + picker_row("Add model…", "any model with a key")
    picker = sheet(PHONE_W, 640, "Fallbacks", "tried in order · hold to reorder", body, primary="Done")
    return pair(phone(settings, 640), phone(picker, 640))


PROPOSALS_F = [
    dict(
        id="UI-PROFILE.FALLBACKS", client="mobile · desktop", area="Profile settings · model",
        title="Fallback models are set and ordered from the apps",
        why=("A profile can list <code>fallback_models</code>, tried in order when the main model's provider fails, but only <code>alpi setup</code> edits them: "
             "the apps do not show that fallbacks exist, <code>host.profile.detail</code> does not return them, and <code>host.config.set_field</code> would store a list as a string. A profile on one provider has no cover for an outage "
             "unless its owner knows to open the console. The proposal adds one Fallbacks row under the helper models: the ordered list with Add and reorder, "
             "and one line on when it is used. The rest of the model section stays as it ships."),
        mobile=(fallbacks_now_mobile, fallbacks_proposed_mobile),
        desktop=(fallbacks_now_desktop, fallbacks_proposed_desktop),
        accept=("<code>host.config.set_field</code> accepts <code>fallback_models</code> as an ordered list of models whose provider has a key, and "
                "<code>host.profile.detail</code> returns it; both clients show the Fallbacks row with the list, Add (from the same model picker) and reorder, "
                "and an empty list reads none; the logic is its own task whose accept says the interface follows board UI-PROFILE.FALLBACKS; the console already edits it."),
        h=1240,
    ),
]
