from gen import DANGER, DOC_ACCENT, diamond, ic, m_button, m_group, m_row, m_screen_header, m_section, mix, page, pill

INK, INK2, INK3, INK4 = "#141414", "#454545", "#6b6b6b", "#b4b4b4"
LINE, LINE2, SELECTED, INPUT = "rgba(20,20,20,0.07)", "rgba(20,20,20,0.14)", "rgba(20,20,20,0.06)", "#f2f2f2"
MONO = "'Geist Mono', monospace"
BACKDROP = "color-mix(in srgb, #ffffff 72%, transparent)"


def backdrop(w, h):
    return f'<div style="position: absolute; inset: 0; width: {w}px; height: {h}px; background: {BACKDROP}"></div>'


def sheet_header(title, subtitle):
    return f"""<div style="display: flex; justify-content: center; padding-top: 8px"><span style="width: 36px; height: 4px; border-radius: 2px; background: {INK4}; opacity: 0.6"></span></div>
<div style="display: flex; align-items: flex-start; gap: 12px; padding: 12px 12px 14px 20px">
<div style="flex: 1; min-width: 0; display: flex; flex-direction: column"><span style="font-weight: 600; font-size: 18px; line-height: 1.3; letter-spacing: -0.01em; color: {INK}">{title}</span>{f'<span style="font-family: {MONO}; font-size: 12px; color: {INK3}; margin-top: 4px">{subtitle}</span>' if subtitle else ""}</div>
<button aria-label="Close" style="width: 44px; height: 44px; border: 0; border-radius: 4px; background: transparent; display: inline-flex; align-items: center; justify-content: center; margin-top: -8px; cursor: pointer">{ic("x", 20, INK3)}</button>
</div>"""


def primary_bar(label, variant="primary", second=None):
    btn = lambda t, v: f'<span style="flex: 1; display: flex">{m_button(t, v, "lg").replace("border-radius: 4px", "border-radius: 4px; width: 100%")}</span>'
    inner = (btn(second[0], second[1]) if second else "") + btn(label, variant)
    return f'<div style="display: flex; gap: 10px; padding: 20px 16px 24px; background: #ffffff">{inner}</div>'


def sheet(w, h, title, subtitle, body, primary=None, variant="primary", dialog=False, second=None, top=None):
    bar = primary_bar(primary, variant, second) if primary else '<div style="height: 24px"></div>'
    if dialog:
        box = f'position: absolute; left: {(w - 560) // 2}px; top: 50%; transform: translateY(-50%); width: 560px; border-radius: 4px;'
    else:
        box = f'position: absolute; left: 0; right: 0; bottom: 0; border-radius: 4px 4px 0 0;'
    return f"""{backdrop(w, h)}
<div style="{box} background: #ffffff; box-shadow: 0 0 0 0.5px rgba(20,20,20,0.14); overflow: hidden; display: flex; flex-direction: column">
{sheet_header(title, subtitle)}
{body}
{bar}
</div>"""


def picker_row(label, helper="", selected=False, accent=DOC_ACCENT, meta=""):
    dot = f'<span style="width: 7px; height: 7px; border-radius: 999px; background: {accent}"></span>' if selected else ""
    m = f'{pill(meta, tone="success")}' if meta else ""
    return f"""<div style="display: flex; align-items: center; gap: 12px; padding: 14px 20px; background: {SELECTED if selected else "transparent"}">
<span style="width: 14px; display: inline-flex; justify-content: center">{dot}</span>
<div style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 3px"><span style="font-weight: 500; font-size: 14px; color: {INK}">{label}</span>{f'<span style="font-family: {MONO}; font-size: 11px; color: {INK3}">{helper}</span>' if helper else ""}</div>
{m}
</div>"""


def separator(inset=20):
    return f'<div style="height: 0.5px; background: {LINE}; margin-left: {inset}px"></div>'


def action_item(icon, label, detail="", danger=False):
    color = DANGER if danger else INK
    det = f'<span style="font-family: {MONO}; font-weight: 500; font-size: 12px; color: {INK3}">{detail}</span>' if detail else ""
    return f"""<div style="display: flex; align-items: center; gap: 14px; padding: 14px 20px">
<span style="width: 24px; display: inline-flex; justify-content: center">{ic(icon, 20, DANGER if danger else INK2)}</span>
<span style="flex: 1; font-size: 15px; color: {color}">{label}</span>{det}
</div>"""


def typed_confirm(w, h, title, body, code, confirm):
    return f"""{backdrop(w, h)}
<div style="position: absolute; left: 24px; right: 24px; top: {h // 2 - 190}px; border-radius: 4px; background: #ffffff; padding: 24px; box-sizing: border-box; display: flex; flex-direction: column; gap: 16px; box-shadow: 0 0 0 0.5px rgba(20,20,20,0.14)">
<span style="font-weight: 600; font-size: 18px; color: {DANGER}">{title}</span>
<span style="font-size: 14px; line-height: 1.5; color: {INK2}">{body}</span>
<span style="font-family: {MONO}; font-size: 11px; letter-spacing: 0.06em; color: {INK3}">TYPE <span style="font-weight: 500; font-size: 12px; color: {INK}; background: {INPUT}; border-radius: 4px; padding: 1px 6px; letter-spacing: 0">{code}</span> TO CONFIRM</span>
<div style="height: 44px; border-radius: 4px; background: {INPUT}; border: 0.5px solid {LINE2}; display: flex; align-items: center; padding: 0 12px; font-family: {MONO}; font-size: 14px; color: {INK4}">{code[:2]}<span style="width: 1px; height: 18px; background: {INK}; margin-left: 1px"></span></div>
<div style="display: flex; flex-direction: column; gap: 8px">{m_button(confirm, "danger", "lg")}{m_button("Cancel", "ghost", "lg")}</div>
</div>"""


def settings_backdrop_rows():
    return f"""{m_screen_header("doc", "Profile · settings", creased=True)}
{m_section("Model")}
{m_group(m_row("Default model", "", "deepseek-v4.1-flash"), m_row("Reasoning effort", "how hard the model thinks", "Medium"), m_row("Fast model", "", "deepseek-v4.1-flash", sep=False))}
{m_section("Budget")}
{m_group(m_row("Daily cap", "$0.00 of $1.00 today", "$1.00", sep=False))}
{m_section("Danger zone")}
{m_group(m_row("Delete profile", "removes everything under ~/.alpi/profiles/doc", danger=True, sep=False))}"""


def phone_sheet():
    body = f"""<div style="padding: 12px 0 0">{picker_row("Default", "use provider default")}{separator()}{picker_row("Low", "fastest, cheapest")}{separator()}{picker_row("Medium", "balanced", selected=True)}{separator()}{picker_row("High", "slower, more thorough")}</div>"""
    page_body = f"""<div style="display: flex; flex-direction: column">{settings_backdrop_rows()}</div>
{sheet(390, 844, "Reasoning effort", "how hard the model thinks before answering", body, primary="Save")}
"""
    return page("Phone · sheet with picker rows", 390, 844, page_body)


def phone_action_sheet():
    items = (action_item("gear", "Profile settings") + separator(56) + action_item("clock", "Pause profile") + separator(56)
             + action_item("bell", "Auto-read replies", "off") + separator(56) + action_item("chip", "Skills") + separator(56)
             + action_item("copy", "Memory") + separator(56) + action_item("clock", "Schedule") + separator(56)
             + action_item("refresh", "Refresh thread"))
    body = f'<div style="height: 0.5px; background: {LINE}"></div><div style="padding-bottom: 24px">{items}</div>'
    page_body = f"""<div style="display: flex; flex-direction: column">{settings_backdrop_rows()}</div>
{sheet(390, 844, "doc", "profile · deepseek-v4.1-flash", body)}
"""
    return page("Phone · action sheet", 390, 844, page_body)


def phone_typed_confirm():
    page_body = f"""<div style="display: flex; flex-direction: column">{settings_backdrop_rows()}</div>
{typed_confirm(390, 844, "Delete profile @doc", "Permanently removes <span style='font-family: " + MONO + "'>~/.alpi/profiles/doc/</span> — identity, memory, skills, schedule and chat history. <b>This action cannot be undone.</b>", "doc", "Delete profile")}
"""
    return page("Phone · typed confirm", 390, 844, page_body)


def fold_sheet():
    from gen import m_sidebar, m_wide_row, m_wide_section
    detail = f"""<div style="flex: 1; min-width: 0; display: flex; flex-direction: column; background: #ffffff">
{m_screen_header("doc", "SETTINGS", wide=True, back=False, creased=True)}
<div style="padding: 0 24px">{m_wide_section("Model", first=True)}{m_wide_row("Default model", value="deepseek-v4.1-flash")}{m_wide_row("Reasoning effort", "how hard the model thinks", "Medium")}{m_wide_section("Budget")}{m_wide_row("Daily cap", "$0.00 of $1.00 today", "$1.00")}</div>
</div>"""
    body = f"""<div style="padding: 12px 0 0">{picker_row("Default", "use provider default")}{separator()}{picker_row("Low", "fastest, cheapest")}{separator()}{picker_row("Medium", "balanced", selected=True)}{separator()}{picker_row("High", "slower, more thorough")}</div>"""
    page_body = f"""<div style="display: flex; height: 100%">{m_sidebar(884)}{detail}</div>
{sheet(852, 884, "Reasoning effort", "how hard the model thinks before answering", body, primary="Save", dialog=True)}
"""
    return page("Fold · sheet as a centred dialog", 852, 884, page_body)


def chat_backdrop():
    from gen import m_chat_header, m_composer, m_thread, meter
    meta = f'<span style="font-family: {MONO}; font-size: 11px; color: {INK2}">deepseek-v4.1-flash</span>{meter("24K", "/1.0M", 0.024, DOC_ACCENT, False)}'
    return f'<div style="display: flex; flex-direction: column; height: 100%">{m_chat_header("doc", DOC_ACCENT, meta)}{m_thread(DOC_ACCENT)}{m_composer()}</div>'


def tool_block(label, text, tag="", danger=False):
    t = f'<span style="font-family: {MONO}; font-size: 12px; color: {INK3}">{tag}</span>' if tag else ""
    return (f'<div style="display: flex; flex-direction: column; gap: 8px"><div style="display: flex; align-items: center; gap: 8px"><span style="font-weight: 500; font-size: 12px; color: {INK3}">{label}</span>{t}</div>'
            f'<div style="border-radius: 4px; background: {INPUT}; padding: 12px 14px"><pre style="margin: 0; white-space: pre-wrap; font-family: {MONO}; font-size: 14px; line-height: 23.1px; color: {DANGER if danger else INK}">{text}</pre></div></div>')


def phone_tool_sheet():
    body = (f'<div style="padding: 0 20px 16px; display: flex; flex-direction: column; gap: 16px">'
            f'{tool_block("Arguments", "{" + chr(10) + "  &quot;command&quot;: &quot;npm run lint&quot;," + chr(10) + "  &quot;cwd&quot;: &quot;~/web&quot;" + chr(10) + "}")}'
            f'{tool_block("Output", "src/app.ts:14  no-unused-vars" + chr(10) + "src/app.ts:31  no-console" + chr(10) + "2 errors, 0 warnings", danger=True)}</div>')
    page_body = f"""{chat_backdrop()}
{sheet(390, 844, "shell · failed in 4.1s", "", body, primary="Copy command", variant="ghost", second=("Copy output", "secondary"))}
"""
    return page("Phone · tool step sheet", 390, 844, page_body)


def phone_select_text():
    hl = mix(DOC_ACCENT, 0.28)
    text = (f'Triglycerides moved most: 142 → 88 mg/dL since March, in step with the carb cut you started in June. '
            f'<span style="background: {hl}; border-radius: 2px">LDL-P eased from 1,420 to 1,180 nmol/L</span> and HDL held at 68. '
            f'Nothing here needs a change of plan; keep the draw in November and add ApoB so we can compare particle count directly.')
    body = f'<div style="padding: 0 20px 20px; font-size: 16px; line-height: 26.4px; color: {INK}">{text}</div>'
    page_body = f"""{chat_backdrop()}
{sheet(390, 844, "Select text", "", body)}
"""
    return page("Phone · select text", 390, 844, page_body)


def phone_message_actions():
    items = action_item("copy", "Copy") + separator(56) + action_item("file", "Select text") + separator(56) + action_item("refresh", "Ask again")
    body = f'<div style="height: 0.5px; background: {LINE}"></div><div style="padding-bottom: 24px">{items}</div>'
    page_body = f"""{chat_backdrop()}
{sheet(390, 844, "Agent message", "", body)}
"""
    return page("Phone · message actions", 390, 844, page_body)


MOBILE_OVERLAYS = {"phone_sheet": phone_sheet, "phone_action": phone_action_sheet, "phone_confirm": phone_typed_confirm, "fold_sheet": fold_sheet,
                   "phone_tool": phone_tool_sheet, "phone_select": phone_select_text, "phone_message": phone_message_actions}
