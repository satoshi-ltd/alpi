from gen import DANGER, DOC_ACCENT, diamond, ic, page
from desktop_boards import HOVER, INK, INK2, INK3, INK4, LINE, LINE2, MONO, PANE, SELECTED, SIDE, button, d_sidebar, field_input, selectish

SHADOW = "0 0 0 0.5px rgba(11,17,23,0.08), 0 18px 50px rgba(11,17,23,0.10)"


def panel(title, inner, w, h, bg=SIDE):
    return (f'<div style="display: flex; flex-direction: column; gap: 10px; width: {w}px; flex-shrink: 0">'
            f'<span style="font-family: {MONO}; font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase; color: {INK3}">{title}</span>'
            f'<div style="position: relative; width: {w}px; height: {h}px; border-radius: 12px; background: {bg}; border: 0.5px solid {LINE}; overflow: hidden; box-sizing: border-box">{inner}</div></div>')


def raw_select(value, w=200):
    return (f'<span style="display: inline-flex; align-items: center; justify-content: space-between; width: {w}px; height: 38px; padding: 0 10px; box-sizing: border-box; '
            f'border-radius: 6px; border: 1px solid {LINE2}; background: #ffffff; font-family: -apple-system, system-ui, sans-serif; font-size: 13px; color: {INK}">{value}{ic("chev-d", 12, INK3)}</span>')


def native_select(value):
    return (f'<span style="display: inline-flex; align-items: center; gap: 18px; height: 22px; padding: 0 8px; border-radius: 5px; border: 1px solid #8f8f8f; '
            f'background: linear-gradient(#ffffff, #ededed); font-family: -apple-system, system-ui, sans-serif; font-size: 13px; color: #000000">{value}{ic("chev-d", 10, "#000000")}</span>')


def dropdown_trigger(label):
    return selectish(f'<span style="max-width: 240px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap">{label}</span>', mono=False)


def ds_field(value, w=200):
    return (f'<span style="display: inline-flex; align-items: center; width: {w}px; height: 32px; padding: 0 12px; box-sizing: border-box; border-radius: 8px; '
            f'background: #ffffff; border: 0.5px solid {LINE2}; font-size: 13px; color: {INK}">{value}</span>')


def checkbox(on=False):
    return (f'<span style="width: 16px; height: 16px; border-radius: 4px; box-sizing: border-box; display: inline-flex; align-items: center; justify-content: center; '
            f'border: 1.5px solid {INK if on else INK4}; background: {INK if on else "transparent"}">{ic("check", 12, PANE) if on else ""}</span>')


def label_row(label, control):
    return f'<div style="display: flex; flex-direction: column; gap: 6px"><span style="font-size: 12px; color: {INK3}">{label}</span>{control}</div>'


def dialog_footer(primary, secondary="Cancel", variant="primary"):
    return f'<div style="display: flex; justify-content: flex-end; gap: 8px; margin-top: 10px">{button(secondary, "ghost")}{button(primary, variant)}</div>'


def modal(title, body, footer, w=520, x=40, y=28):
    return (f'<div style="position: absolute; inset: 0; background: rgba(11,17,23,0.32)"></div>'
            f'<div style="position: absolute; left: {x}px; top: {y}px; width: {w}px; box-sizing: border-box; border-radius: 14px; padding: 24px; background: {PANE}; '
            f'border: 0.5px solid {LINE2}; box-shadow: {SHADOW}; display: flex; flex-direction: column; gap: 8px">'
            f'<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px"><span style="font-size: 18px; font-weight: 600; letter-spacing: -0.005em; color: {INK}">{title}</span></div>'
            f'{body}{footer}</div>')


def edit_connection_panel():
    profiles = "".join(f'<label style="display: inline-flex; align-items: center; gap: 8px; font-size: 13px; color: {INK}">{checkbox(on)}{name}</label>'
                       for name, on in (("doc", True), ("abby", True), ("etxea", False)))
    profiles_row = f'<div style="display: flex; gap: 16px">{profiles}</div>'
    body = (f'<div style="display: flex; flex-direction: column; gap: 14px">'
            f'{label_row("Label", field_input("phone", 472))}'
            f'<div style="display: flex; gap: 16px">{label_row("Role", dropdown_trigger("Member"))}{label_row("Sessions", dropdown_trigger("Shared across its devices"))}</div>'
            f'{label_row("Profiles", profiles_row)}'
            f'</div>')
    inner = modal("Edit connection", body, dialog_footer("Save"))
    return panel("Modal · edit connection (Dropdown field for role and sessions)", inner, 600, 360)


def dropdown_row(label, caption="", active=False):
    cap = f'<span style="font-family: {MONO}; font-size: 11px; color: {INK3}; margin-top: 4px">{caption}</span>' if caption else ""
    return (f'<div style="display: flex; flex-direction: column; padding: 8px 10px; border-radius: 8px; background: {SELECTED if active else "transparent"}">'
            f'<span style="font-size: 13px; color: {INK}">{label}</span>{cap}</div>')


def dropdown_panel():
    menu = "".join(dropdown_row(*r) for r in (("Default", "use provider default"), ("Low", "fastest, cheapest"), ("Medium", "balanced", True), ("High", "slower, more thorough")))
    model = button('deepseek-v4.1-flash', "ghost", "md", icon="chip").replace("font-family: Geist, sans-serif", f"font-family: {MONO}").replace("font-size: 13px", "font-size: 12px")
    inner = (f'<div style="padding: 28px 32px; display: flex; flex-direction: column; gap: 22px; background: {PANE}; height: 100%; box-sizing: border-box">'
             f'<div style="display: flex; align-items: center; gap: 24px"><span style="width: 120px; font-family: {MONO}; font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase; color: {INK3}">Fast model</span>{model}{dropdown_trigger("medium")}</div>'
             f'<div style="display: flex; align-items: center; gap: 24px"><span style="width: 120px; font-family: {MONO}; font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase; color: {INK3}">Reasoning</span>'
             f'<div style="position: relative">{dropdown_trigger("medium")}'
             f'<div style="position: absolute; left: 0; top: 38px; width: 280px; padding: 6px; box-sizing: border-box; border-radius: 12px; background: {PANE}; border: 0.5px solid {LINE2}; box-shadow: {SHADOW}">{menu}</div>'
             f'</div></div></div>')
    return panel("Dropdown field · open, current choice highlighted, beside a ModelPicker", inner, 600, 360)


def menu_item(icon, label, danger=False):
    return (f'<div style="display: flex; align-items: center; gap: 10px; padding: 6px 10px; border-radius: 6px; font-size: 13px; color: {DANGER if danger else INK}">'
            f'{ic(icon, 14, DANGER if danger else INK3)}<span style="flex: 1">{label}</span></div>')


def context_menu_panel():
    menu = (f'<div style="position: absolute; left: 150px; top: 150px; width: 210px; padding: 4px; box-sizing: border-box; border-radius: 10px; background: {PANE}; border: 0.5px solid {LINE2}; box-shadow: {SHADOW}">'
            f'{menu_item("gear", "Workgroup settings")}'
            f'<div style="height: 1px; background: {LINE}; margin: 4px 6px"></div>{menu_item("x", "Delete workgroup…", danger=True)}</div>')
    inner = f'<div style="display: flex; height: 100%">{d_sidebar(300, selected="", wg_selected=True)}<div style="flex: 1; background: {PANE}"></div></div>{menu}'
    return panel("Context menu · sidebar workgroup (archive item removed)", inner, 356, 300)


def confirm_panel():
    body = (f'<span style="font-size: 13px; line-height: 1.5; color: {INK2}">Permanently removes <span style="font-family: {MONO}">~/.alpi/profiles/doc/</span> — identity, memory, skills, schedule and chat history. This cannot be undone.</span>'
            f'<div style="display: flex; flex-direction: column; gap: 6px; margin-top: 8px"><span style="font-family: {MONO}; font-size: 11px; letter-spacing: 0.06em; color: {INK3}">TYPE <b style="color: {INK}">doc</b> TO CONFIRM</span>{ds_field("d", 392)}</div>')
    inner = modal("Delete profile @doc", body, dialog_footer("Delete profile", variant="danger"), w=400, x=28, y=24)
    return panel("ConfirmDelete · typed (waits for the delete, submits on Enter)", inner, 456, 300)


def controls_panel():
    items = (("Selectish", selectish("nova")), ("Dropdown field", dropdown_trigger("medium")), (".ds-field", ds_field("phone", 130)),
             ("was: raw .select", raw_select("member", 130)), ("was: native", native_select("shared")))
    rows = "".join(f'<div style="display: flex; align-items: center; gap: 12px"><span style="width: 96px; font-family: {MONO}; font-size: 11px; color: {INK3}">{k}</span>{v}</div>' for k, v in items)
    inner = f'<div style="padding: 20px 24px; display: flex; flex-direction: column; gap: 14px; background: {PANE}; height: 100%; box-sizing: border-box">{rows}</div>'
    return panel("Two looks left (voice and budget keep Selectish); the raw selects are gone", inner, 376, 300)


def desktop_overlays():
    body = (f'<div style="padding: 28px 32px; display: flex; flex-direction: column; gap: 24px; height: 100%; box-sizing: border-box">'
            f'<div style="display: flex; flex-direction: column; gap: 4px"><span style="font-size: 22px; font-weight: 600; letter-spacing: -0.018em">Desktop overlays as of 0.6.6</span>'
            f'<span style="font-size: 13px; color: {INK3}; max-width: 900px; line-height: 1.5">Drawn from Modal.module.css, Dropdown.module.css, ContextMenu and the connections page after the overlays cycle. Badges point at the round-2 audit rows.</span></div>'
            f'<div style="display: flex; gap: 16px">{edit_connection_panel()}{dropdown_panel()}</div>'
            f'<div style="display: flex; gap: 14px">{context_menu_panel()}{confirm_panel()}{controls_panel()}</div></div>')
    return page("Desktop · overlays", 1280, 860, body)
