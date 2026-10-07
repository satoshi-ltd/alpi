import folds
import os
import re

from gen import DANGER, DOC_ACCENT, ic, m_button, m_count_badge, m_group, m_roster_row, m_row, m_row_state, m_wide_row, meter, page, pill, switch, textbox
from desktop_boards import (HOVER, INK, INK2, INK3, INK4, LINE, LINE2, MONO, PANE, SELECTED, SIDE, alink, badged, button, chip, code_chip, count_badge, field_input, iconbtn, kbd, key_hint,
                            meterchip, phase_count, selectish, settings_rail, state_chip, textarea)
from desktop_overlays import checkbox, dialog_footer, dropdown_row, dropdown_trigger, ds_field, menu_item, modal
from mobile_overlays import action_item, picker_row, separator, sheet_header
from loading_studies import DUR_LOOP, DUR_SPIN, PULSE_MS, SPINNER_TURN_MS, waiting

AMBER, ACCENT_LIGHT, ACCENT_DARK = "#14110c", "#14110c", "#f3efe6"
TOKENS_MJS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "common", "tokens.mjs")
SWATCH_KEYS = ("bg", "bgPane", "bgSide", "bgElev", "bgInput", "ink", "ink2", "ink3", "ink4", "accent", "successText", "warningText", "dangerText")


def token_block(name):
    with open(TOKENS_MJS) as f:
        src = f.read()
    body = re.search(r"const " + name + r" = \{(.*?)\};", src, re.S).group(1)
    return dict(re.findall(r"(\w+):\s*\"(#[0-9a-fA-F]{6})\"", body))


LIGHT = [(k, token_block("light")[k]) for k in SWATCH_KEYS]
DARK = [(k, token_block("dark")[k]) for k in SWATCH_KEYS]
STATUS = list(token_block("status").items())
FS = [("xxs", 9), ("label", 10), ("xs", 11), ("sm", 12), ("base", 13), ("md", 14), ("lg", 15), ("xl", 18), ("xxl", 22), ("display", 28), ("hero", 56)]
SPACE = [("s1", 4), ("s2", 6), ("s3", 8), ("s4", 10), ("s5", 12), ("s6", 14), ("s7", 16), ("s8", 20), ("s9", 24), ("s10", 32), ("s11", 40)]
RADII = [("tag", 2), ("xs", 4), ("pill", 999)]
TOKENS_CSS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "desktop", "src", "styles", "tokens.css")


def css_tokens(prefix):
    with open(TOKENS_CSS) as f:
        root = f.read().split("}", 1)[0]
    return re.findall(r"--" + prefix + r"-([\w-]+):\s*([^;]+);", root)


CTRL = [(name, int(value.rstrip("px"))) for name, value in css_tokens("ctrl") if value.strip().endswith("px")]
ROLES = [("--text-meta", 11, "timestamps, chips, eyebrows, keys"), ("--text-ui", 13, "rows, buttons, labels, palette"), ("--text-chat", 15, "messages, settings section titles"),
         ("--text-title", 18, "dialog titles, empty headings"), ("--text-display", 28, "chat and settings hero"), ("--text-hero", 56, "empty-state glyph")]
MOTION = [("--dur-1", "120ms", 120, "hover, press, tooltip"), ("--dur-2", "200ms", 200, "turn rise, card in, text reveal"), ("--dur-3", "260ms", 260, "panels"), ("--dur-4", "360ms", 360, "slow reveals"),
          ("--dur-loop", "1.4s", 1400, "working pulse, dots"), ("--dur-spin", "0.9s", 900, "spinners")]
ICON_SIZES = [("--icon-sm", 14), ("--icon-md", 16)]


def h1(text, sub):
    return f'<div style="display: flex; flex-direction: column; gap: 6px"><span style="font-size: 28px; font-weight: 600; letter-spacing: -0.02em; line-height: 1.15">{text}</span><span style="font-size: 13px; line-height: 1.5; color: {INK3}; max-width: 880px">{sub}</span></div>'


def h2(text, n):
    return f'<div style="display: flex; align-items: baseline; gap: 10px; margin-top: 8px"><span style="font-size: 18px; font-weight: 600; letter-spacing: -0.01em">{text}</span><span style="font-family: {MONO}; font-size: 11px; color: {INK4}">{n:02d}</span></div>'


def label(text):
    return f'<span style="font-family: {MONO}; font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase; color: {INK3}">{text}</span>'


def specimen(title, inner, w=None, bg=PANE):
    width = f"width: {w}px;" if w else ""
    return (f'<div style="display: flex; flex-direction: column; gap: 8px; {width} flex-shrink: 0">{label(title)}'
            f'<div style="display: flex; flex-wrap: wrap; align-items: center; gap: 12px; padding: 16px; border-radius: 12px; background: {bg}; border: 0.5px solid {LINE}">{inner}</div></div>')


def swatch(name, hexv, on_dark=False):
    fg = "#ededed" if on_dark else INK
    return (f'<div style="display: flex; flex-direction: column; gap: 6px; width: 96px"><div style="height: 44px; border-radius: 4px; background: {hexv}; border: 0.5px solid {LINE2}"></div>'
            f'<span style="font-size: 12px; font-weight: 500; color: {fg}">{name}</span><span style="font-family: {MONO}; font-size: 11px; color: {INK3}">{hexv}</span></div>')


def tokens_board():
    light = "".join(swatch(n, v) for n, v in LIGHT)
    dark = "".join(swatch(n, v, True) for n, v in DARK)
    status = "".join(swatch(n, v) for n, v in STATUS)
    types = "".join(f'<div style="display: flex; align-items: baseline; gap: 14px"><span style="width: 88px; font-family: {MONO}; font-size: 11px; color: {INK3}">{n} · {px}</span><span style="font-size: {px}px; line-height: 1.2; color: {INK}">Every view says what happened</span></div>' for n, px in FS)
    space = "".join(f'<div style="display: flex; flex-direction: column; align-items: center; gap: 6px"><div style="width: {px}px; height: {px}px; background: {SELECTED}; border-radius: 3px"></div><span style="font-family: {MONO}; font-size: 11px; color: {INK3}">{n}</span><span style="font-family: {MONO}; font-size: 11px; color: {INK4}">{px}</span></div>' for n, px in SPACE)
    radii = "".join(f'<div style="display: flex; flex-direction: column; align-items: center; gap: 6px"><div style="width: 44px; height: 44px; border: 1.5px solid {INK2}; border-radius: {min(px, 22)}px"></div><span style="font-family: {MONO}; font-size: 11px; color: {INK3}">{n} · {px}</span></div>' for n, px in RADII)
    ctrl = "".join(f'<div style="display: flex; flex-direction: column; align-items: center; gap: 6px"><div style="width: 72px; height: {px}px; border-radius: 4px; background: {HOVER}; border: 0.5px solid {LINE2}"></div><span style="font-family: {MONO}; font-size: 11px; color: {INK3}">ctrl-{n} · {px}</span></div>' for n, px in CTRL)
    icons = "".join(f'<div style="display: flex; flex-direction: column; align-items: center; gap: 6px; width: 56px">{ic(n, 20, INK2, 1.75)}<span style="font-family: {MONO}; font-size: 10px; color: {INK3}">{n}</span></div>' for n in ("plus", "search", "gear", "bell", "history", "activity", "sparkle", "check", "x", "chev-d", "chev-r", "copy", "refresh", "clock", "chip", "sun", "moon", "panel", "pin", "trash", "terminal", "file", "globe", "qr", "more"))
    roles = "".join(f'<div style="display: flex; align-items: baseline; gap: 14px"><span style="width: 150px; font-family: {MONO}; font-size: 11px; color: {INK3}">{n} · {px}</span><span style="font-size: {px}px; line-height: 1.2; font-weight: {600 if px >= 18 else 400}; color: {INK}; white-space: nowrap">{"Needs you" if px >= 56 else "Every view says what happened"}</span><span style="font-size: 12px; color: {INK3}">{use}</span></div>' for n, px, use in ROLES)
    motion = "".join(f'<div style="display: flex; align-items: center; gap: 14px"><span style="width: 150px; font-family: {MONO}; font-size: 11px; color: {INK3}">{n} · {v}</span><span style="width: {max(12, ms // 5)}px; height: 6px; border-radius: 999px; background: {INK4}"></span><span style="font-size: 12px; color: {INK3}">{use}</span></div>' for n, v, ms, use in MOTION)
    icon_sizes = "".join(f'<div style="display: flex; flex-direction: column; align-items: center; gap: 6px">{ic("history", px, INK2, 1.75)}<span style="font-family: {MONO}; font-size: 11px; color: {INK3}">{n} · {px}</span></div>' for n, px in ICON_SIZES)
    body = f"""<div style="padding: 40px 48px; display: flex; flex-direction: column; gap: 28px; box-sizing: border-box">
{h1("alpi design system", "One token file, <span style='font-family: " + MONO + "'>common/tokens.mjs</span>, feeds both clients: desktop reads it as CSS custom properties (tokens.css, parity-tested), mobile through useTheme(). Geist for text, Geist Mono for labels and numbers, Lucide icons at 1.75 stroke. The brand accent is Continuity amber: deep on light, signal on dark; the brand mark is the tonal alpaca, a golden amber on light and signal amber on dark.")}
{h2("Colour · light", 1)}
<div style="display: flex; flex-wrap: wrap; gap: 14px">{light}</div>
{h2("Colour · dark", 2)}
<div style="display: flex; flex-wrap: wrap; gap: 14px; padding: 16px; border-radius: 12px; background: #0b0b0b">{dark}</div>
{h2("Status", 3)}
<div style="display: flex; gap: 14px">{status}<div style="font-size: 12px; color: {INK3}; max-width: 520px; line-height: 1.5; align-self: center">Fills for dots, meters and danger buttons. Text on light uses the *Text variants above so it clears 4.5:1; the site shows warnings in red, the apps in orange.</div></div>
{h2("Type scale", 4)}
<div style="display: flex; flex-direction: column; gap: 10px">{types}</div>
<div style="display: flex; gap: 24px; font-size: 12px; color: {INK3}"><span>chat · lg / relaxed (mobile chat 16)</span><span>dialog title · xl / cozy</span><span>body · md / normal</span><span>caption · sm / cozy</span><span>metadata · xs / cozy</span><span>weights 400 · 500 · 600 · 700</span></div>
{h2("Type roles · desktop", 5)}
<div style="font-size: 12px; color: {INK3}; max-width: 900px; line-height: 1.5; margin-top: -14px">desktop paints from six roles in tokens.css; the ladder above stays for the shared token file and mobile.</div>
<div style="display: flex; flex-direction: column; gap: 12px">{roles}</div>
{h2("Motion", 6)}
<div style="font-size: 12px; color: {INK3}; max-width: 900px; line-height: 1.5; margin-top: -14px">ease cubic-bezier(.2, .7, .2, 1); prefers-reduced-motion drops transforms and loops app-wide.</div>
<div style="display: flex; flex-direction: column; gap: 10px">{motion}</div>
{h2("Space, radius, control heights, icon sizes", 7)}
<div style="display: flex; gap: 18px; align-items: flex-end">{space}</div>
<div style="display: flex; gap: 22px">{radii}</div>
<div style="display: flex; gap: 22px; align-items: flex-end">{ctrl}<span style="width: 24px"></span>{icon_sizes}</div>
{h2("Iconography", 8)}
<div style="display: flex; flex-wrap: wrap; gap: 10px">{icons}</div>
</div>"""
    return page("System · tokens", 1280, TOKENS_H, body)


def notification_reader(w, size=13, mobile=False):
    entries = (("Ana Ruiz", "ana@example.com", "Can we move Friday’s review to Monday?"), ("Bob Lee", "bob@acme.io", "Invoice 0412 is attached"), ("Carmen", "", "Thanks, all set"))
    rows = "".join(f'<div style="display: flex; flex-direction: column; gap: 2px; padding: 8px 0; box-shadow: {"inset 0 -0.5px 0 rgba(20,20,20,0.07)" if i < len(entries) - 1 else "none"}">'
                   f'<span style="display: flex; align-items: baseline; gap: 8px"><span style="font-size: {size}px; font-weight: 600; color: {INK}">{n}</span>'
                   f'<span style="font-family: {MONO}; font-size: 11px; color: {INK3}">{m}</span></span><span style="font-size: {size}px; line-height: 1.45; color: {INK2}">{t}</span></div>'
                   for i, (n, m, t) in enumerate(entries))
    digest = (f'<div style="width: {w}px; display: flex; flex-direction: column; gap: 6px"><span style="font-size: {size + 3}px; font-weight: 600; color: {INK}">Daily mail digest</span>'
              f'<span style="font-size: {size}px; color: {INK2}">14 new emails since yesterday, 3 need a reply.</span><div>{rows}</div></div>')
    facts = (("Reason", "The mail account refused the saved token."), ("Exit", "1"), ("Timeout", "none"))
    kv = "".join(f'<div style="display: flex; gap: 10px; padding: 6px 0; box-shadow: {"inset 0 -0.5px 0 rgba(20,20,20,0.07)" if i < len(facts) - 1 else "none"}">'
                 f'<span style="min-width: 64px; padding-top: 2px; font-family: {MONO}; font-size: 11px; letter-spacing: 0.06em; color: {INK3}">{k.upper()}</span>'
                 f'<span style="flex: 1; font-size: {size}px; line-height: 1.4; color: {INK if i == 0 else INK2}">{v}</span></div>' for i, (k, v) in enumerate(facts))
    details = (f'<div style="display: flex; align-items: center; gap: 6px; padding: 8px 10px; border-radius: 4px; background: rgba(20,20,20,0.04); font-family: {MONO}; font-size: 11px; color: {INK2}">'
               f'{ic("chev-r", 12, INK3)}Details</div>')
    actions = (m_button("Run again", "primary", "sm") + m_button("Open job", "secondary", "sm")) if mobile else (button("Run again", "primary") + button("Open job", "secondary"))
    card = (f'<div style="width: {w}px; box-sizing: border-box; display: flex; flex-direction: column; gap: 10px; padding: 14px 16px; border-radius: 4px; background: #f6f6f6">'
            f'<span style="display: flex; align-items: center; gap: 8px; font-size: {size + 3}px; font-weight: 600; color: {INK}">{ic("triangle-alert", 14, DANGER)}Daily mail digest <span style="color: {DANGER}">failed</span></span>'
            f'<div>{kv}</div>{details}<div style="display: flex; gap: 6px">{actions}</div></div>')
    return f'<div style="display: flex; gap: 32px; align-items: flex-start">{digest}{card}</div>'


def desktop_components_board():
    buttons = "".join(button(t, v) for t, v in (("Primary", "primary"), ("Secondary", "secondary"), ("Ghost", "ghost"), ("Danger", "danger"), ("Danger ghost", "danger-ghost"))) + button("sm", "secondary", "sm") + button("lg", "secondary", "lg") + button("hero", "primary", "hero") + button("Connections", "ghost", "md", "globe") + alink("Action link") + alink("Remove", danger=True)
    icon_only = "".join(button("Settings", "ghost", z, "gear", True) for z in ("sm", "md", "lg", "hero")) + button("Close", "secondary", "md", "x", True) + button("Stop", "primary", "md", "x", True) + f'<span style="font-size: 12px; color: {INK3}">IconBtn is Button ghost iconOnly · square at the size height · scale .96 on press</span>'
    tip = (f'<span style="display: inline-flex; flex-direction: column; align-items: center; gap: 6px">{iconbtn("gear", "Settings")}'
           f'<span style="position: relative; padding: 4px 8px; border-radius: 4px; background: {INK}; color: {PANE}; font-size: 11px; font-weight: 500; letter-spacing: 0.02em; line-height: 1.3">'
           f'<span style="position: absolute; left: 50%; top: -3px; width: 6px; height: 6px; background: {INK}; transform: translateX(-50%) rotate(45deg)"></span>Settings · ⌘,</span></span>'
           f'<span style="display: inline-flex; flex-direction: column; align-items: center; gap: 6px"><span style="position: relative; padding: 4px 8px; border-radius: 4px; background: {INK}; color: {PANE}; font-size: 11px; font-weight: 500; letter-spacing: 0.02em; line-height: 1.3">'
           f'<span style="position: absolute; left: 50%; bottom: -3px; width: 6px; height: 6px; background: {INK}; transform: translateX(-50%) rotate(45deg)"></span>Activity · 2 need you · ⌘J</span>{iconbtn("role:activity", "Activity")}</span>')
    keys = "".join(f'<span style="display: inline-flex; align-items: center; gap: 8px"><span style="font-size: 12px; color: {INK3}">{h}</span>{key_hint(h)}</span>' for h in ("⌘K", "⌘/", "⇧⌘N", "⌘1–9", "Esc")) + f'<span style="display: inline-flex; align-items: center; gap: 8px"><span style="font-size: 12px; color: {INK3}">text hint</span>{key_hint("light · dark · system")}</span>'
    states = (state_chip("needs-you") + state_chip("failed") + state_chip("working", "#3899e2") + phase_count(2, 4)
              + badged("role:notifications", "Notifications · 1 unread", 1, "danger") + badged("role:activity", "Activity · 2 need you", 2, "danger"))
    rail = f'<div style="display: flex; gap: 32px">{settings_rail(("Overview", "Usage", "Service", "ALP", "Sandbox"), 0)}{settings_rail(("Voice",), 0, "voice")}<span style="font-size: 12px; color: {INK3}; max-width: 280px; line-height: 1.5">Rail 168 wide, search 28 high; rows follow the section in view and jump on click. A query hides every section and row that does not match; Enter jumps to the first hit.</span></div>'
    chips = chip("plain") + chip("on", "on") + chip("off", "off") + chip("warn", "warn") + chip("clickable", clickable=True) + code_chip("deepseek-v4.1-flash") + kbd("⌘") + kbd("K")
    fields = field_input("phone") + textarea("Identity as the agent sees itself", rows=2, w=300) + ds_field("phone", 160) + selectish("nova") + dropdown_trigger("medium") + f'<span class="ds-seg" style="display: inline-flex; gap: 2px; padding: 2px; border-radius: 4px; background: {SELECTED}"><span style="height: 22px; padding: 0 8px; border-radius: 4px; background: {INK}; color: {PANE}; font-size: 12px; font-weight: 500; display: inline-flex; align-items: center">All</span><span style="height: 22px; padding: 0 8px; font-size: 12px; font-weight: 500; color: {INK3}; display: inline-flex; align-items: center">Working</span><span style="height: 22px; padding: 0 8px; font-size: 12px; font-weight: 500; color: {INK3}; display: inline-flex; align-items: center">Paused</span></span>' + checkbox(True) + checkbox(False) + f'<span style="width: 16px; height: 16px; border-radius: 999px; border: 1.5px solid {INK}; display: inline-flex; align-items: center; justify-content: center"><span style="width: 8px; height: 8px; border-radius: 999px; background: {INK}"></span></span>'
    meters = meterchip("$0.40", "/$5.00", 0.08) + meterchip("24K", "/1.0M", 0.024) + f'<span style="display: inline-flex; align-items: center; gap: 6px; font-family: {MONO}; font-size: 11px; color: {INK3}"><span style="width: 7px; height: 7px; border-radius: 999px; background: #3fb37a"></span>online</span>' + f'<span style="display: inline-flex; align-items: center; gap: 6px; font-family: {MONO}; font-size: 11px; color: {INK3}"><span style="width: 7px; height: 7px; border-radius: 999px; background: #e08a3c"></span>probing</span>'
    menu = (f'<div style="width: 210px; padding: 4px; border-radius: 4px; background: {PANE}; border: 0.5px solid {LINE2}; box-shadow: 0 0 0 0.5px rgba(20,20,20,0.14)">{menu_item("pin", "Pin to top")}<div style="height: 1px; background: {LINE}; margin: 4px 6px"></div>{menu_item("gear", "Open settings", hint="⌘,")}<div style="height: 1px; background: {LINE}; margin: 4px 6px"></div>{menu_item("trash", "Delete workgroup…", danger=True)}</div>')
    dropdown = f'<div style="width: 260px; padding: 6px; border-radius: 4px; background: {PANE}; border: 0.5px solid {LINE2}; box-shadow: 0 0 0 0.5px rgba(20,20,20,0.14)">{dropdown_row("Default", "use provider default")}{dropdown_row("Medium", "balanced", True)}{dropdown_row("High", "slower, more thorough")}</div>'
    banner = (f'<div style="display: flex; align-items: center; gap: 10px; width: 100%; padding: 8px 14px; border-radius: 4px; background: rgba(193,69,69,0.10); font-size: 13px; color: {INK}"><span style="width: 7px; height: 7px; border-radius: 999px; background: #c14545"></span><span style="flex: 1">alpi on this computer is not answering — reconnecting…</span>{button("Retry", "ghost", "sm")}</div>'
              f'<div style="display: flex; align-items: center; gap: 10px; width: 100%; padding: 8px 14px; border-radius: 4px; background: rgba(224,138,60,0.12); font-size: 13px; color: {INK}"><span style="width: 7px; height: 7px; border-radius: 999px; background: #e08a3c"></span><span style="flex: 1">This profile is paused. Resume from the header to chat.</span></div>')
    load_failed = (f'<div style="display: flex; flex-direction: column; align-items: center; gap: 12px; padding: 24px 16px; text-align: center; width: 100%"><span style="font-size: 13px; font-weight: 500">Couldn’t load this conversation</span><span style="font-family: {MONO}; font-size: 11px; color: {INK3}">read timeout</span>{button("Retry", "secondary")}</div>'
                   f'<span style="display: inline-flex; align-items: center; gap: 8px; color: {DANGER}; font-size: 13px">Couldn’t load members {alink("Retry")}</span>')
    empty = f'<div style="display: flex; flex-direction: column; align-items: center; gap: 16px; padding: 24px; width: 100%; text-align: center">{folds.fold("honeycomb", INK3, 72)}<span style="font-size: 28px; font-weight: 600; letter-spacing: -0.02em">No workgroups yet</span><span style="font-family: {MONO}; font-size: 12px; color: {INK3}">A workgroup is a hub profile plus the members it directs.</span>{button("New workgroup", "secondary")}</div>'
    mbody = (f'<div style="display: flex; flex-direction: column; gap: 6px"><span style="font-size: 12px; color: {INK3}">Label</span>{ds_field("phone", 380)}</div>'
             f'<div style="display: flex; gap: 16px"><div style="display: flex; flex-direction: column; gap: 6px"><span style="font-size: 12px; color: {INK3}">Role</span>{dropdown_trigger("Member")}</div><div style="display: flex; flex-direction: column; gap: 6px"><span style="font-size: 12px; color: {INK3}">Sessions</span>{dropdown_trigger("Shared across its devices")}</div></div>')
    modal_spec = f'<div style="position: relative; width: 520px; height: 300px; border-radius: 12px; background: {SIDE}; overflow: hidden">{modal("Edit connection", mbody, dialog_footer("Save changes"), w=440, x=40, y=24)}</div>'
    confirm_body = (f'<span style="font-size: 13px; line-height: 1.5; color: {INK2}">Permanently removes identity, memory, skills, schedule and chat history. This cannot be undone.</span>'
                    f'<div style="display: flex; flex-direction: column; gap: 6px; margin-top: 8px"><span style="font-family: {MONO}; font-size: 11px; letter-spacing: 0.06em; color: {INK3}">TYPE <b style="color: {INK}">doc</b> TO CONFIRM</span>{ds_field("d", 360)}</div>')
    confirm_spec = f'<div style="position: relative; width: 460px; height: 300px; border-radius: 12px; background: {SIDE}; overflow: hidden">{modal("Delete profile @doc", confirm_body, dialog_footer("Delete profile", variant="danger"), w=400, x=30, y=24)}</div>'
    body = f"""<div style="padding: 40px 48px; display: flex; flex-direction: column; gap: 22px; box-sizing: border-box">
{h1("Components · desktop", "Every primitive lives in desktop/src/primitives and paints with the .ds-* classes from design-system.css. One Button (IconBtn is its ghost iconOnly form) and one Tip; buttons are 28 px by default, fields 32, dialogs 520 with a shared DialogFooter; shortcuts show as KeyHint chips; menus and confirms register on useOverlay so Escape, focus and layering behave the same everywhere.")}
{specimen("Button · primary, secondary, ghost, danger, danger ghost · sm 24 · md 28 · lg 32 · hero 40 · leading icon · action links", buttons)}
{specimen("Button iconOnly · sm 24 · md 28 · lg 32 · hero 40", icon_only)}
<div style="display: flex; gap: 22px; align-items: flex-start">{specimen("Tip · ink 11 medium, radius 4, arrow", tip, 440)}{specimen("KeyHint · modifiers and key as Kbd chips, text when it is not a chord", keys, 710)}</div>
{specimen("Roster state chips · needs you · failed · working (pulses on --dur-loop) · workgroup phase · footer badges (one danger count, capped at 9+)", states)}
{specimen("Chips, code chip, keys", chips)}
{specimen("SettingsNav · section rail with search", rail)}
{specimen("Fields · Field 32 · Textarea · ds-field · Selectish (mono, voice + budget) · Dropdown field (every choice) · ds-seg · Checkbox · Radio", fields)}
{specimen("Meters and status dots", meters)}
<div style="display: flex; gap: 22px; align-items: flex-start">{specimen("Context menu · 6/10 rows, radius 4", menu, 260)}{specimen("Dropdown menu · 8/10 rows, caption mono 11, active = selected fill", dropdown, 300)}{specimen("Banners · danger with Retry · warning", banner, 560)}</div>
<div style="display: flex; gap: 22px; align-items: flex-start">{specimen("Modal 520 · title 18 · content scrolls · DialogFooter (ghost Cancel, primary)", modal_spec, 552, SIDE)}{specimen("ConfirmDelete · typed only for irreversible deletes · waits for the delete", confirm_spec, 492, SIDE)}</div>
{specimen("NotificationBody · a digest as entries (name, address in mono, text) · a failed run as a flat card: red on the mark and the word failed, facts, trace folded under Details, Run again and Open job", notification_reader(420))}
{specimen("Waiting · Busy for a page or a section, SpinnerIcon inside controls, shimmering skeleton rows and lines for lists and readers", waiting())}
<div style="display: flex; gap: 22px; align-items: flex-start">{specimen("LoadFailed · card and inline (role alert)", load_failed, 420)}{specimen("EmptyState · glyph, display heading, mono subtitle, one action", empty, 620)}</div>
</div>"""
    return page("System · desktop components", 1280, DESKTOP_COMPONENTS_H, body)


def mobile_components_board():
    buttons = "".join(m_button(t, v, "lg") for t, v in (("Primary", "primary"), ("Secondary", "secondary"), ("Ghost", "ghost"), ("Danger", "danger"), ("Danger ghost", "danger-ghost"))) + m_button("md", "secondary", "md") + m_button("sm", "secondary", "sm")
    rows = f'<div style="width: 414px">{m_group(m_row("Reasoning effort", "how hard the model thinks", "Medium"), m_row("Paused", "paused profiles can’t be chatted", control=switch(False, DOC_ACCENT, "Paused"), chevron=False), m_row("Delete profile", "cannot be undone", danger=True, sep=False))}</div>'
    wide = f'<div style="width: 520px; padding: 0 16px; border-radius: 4px; border: 0.5px solid {LINE}">{m_wide_row("Default model", value="deepseek-v4.1-flash")}{m_wide_row("Sandbox", "wraps shell tools", control=switch(True, DOC_ACCENT, "Sandbox"), chevron=False)}{m_wide_row("Workspace", value="/data/workspace/doc")}</div>'
    pills = pill("on", True) + pill("off") + pill("warn", tone="warning") + pill("2 sessions", tone="success") + meter("$0.40", "/$5.00", 0.08) + meter("24K", "/1.0M", 0.024)
    fields = f'<div style="width: 300px">{textbox("phone", rows=1)}</div><div style="width: 300px; display: flex; flex-direction: column; gap: 6px"><div style="height: 44px; border-radius: 4px; border: 1px solid {DANGER}; background: #f2f2f2; display: flex; align-items: center; padding: 0 12px; font-family: {MONO}; font-size: 14px">abc</div><span style="font-family: {MONO}; font-size: 11px; color: {DANGER}">Enter a number, or leave it empty for no cap</span></div>{switch(True, DOC_ACCENT)}{switch(False, DOC_ACCENT)}'
    picker = f'<div style="width: 360px; border-radius: 4px; border: 0.5px solid {LINE}; overflow: hidden">{picker_row("Low", "fastest, cheapest")}{separator()}{picker_row("Medium", "balanced", selected=True)}{separator()}{picker_row("High", "slower, more thorough")}</div>'
    actions = f'<div style="width: 360px; border-radius: 4px; border: 0.5px solid {LINE}; overflow: hidden">{action_item("gear", "Profile settings")}{separator(56)}{action_item("bell", "Auto-read replies", "off")}{separator(56)}{action_item("x", "Delete profile…", danger=True)}</div>'
    sheet_spec = f'<div style="width: 390px; border-radius: 4px 4px 0 0; background: #ffffff; border: 0.5px solid {LINE2}; overflow: hidden; box-shadow: 0 0 0 0.5px rgba(20,20,20,0.14)">{sheet_header("Reasoning effort", "how hard the model thinks before answering")}<div style="padding: 0 0 8px">{picker_row("Medium", "balanced", selected=True)}</div><div style="display: flex; gap: 10px; padding: 20px 16px 24px"><span style="flex: 1; display: flex">{m_button("Not now", "ghost", "lg").replace("border-radius: 4px", "border-radius: 4px; width: 100%")}</span><span style="flex: 1; display: flex">{m_button("Save", "primary", "lg").replace("border-radius: 4px", "border-radius: 4px; width: 100%")}</span></div></div>'
    confirm = (f'<div style="width: 360px; border-radius: 4px; background: #ffffff; padding: 24px; box-sizing: border-box; display: flex; flex-direction: column; gap: 14px; box-shadow: 0 0 0 0.5px rgba(20,20,20,0.14)"><span style="font-weight: 600; font-size: 18px; color: {DANGER}">Delete profile @doc</span><span style="font-size: 14px; line-height: 1.5; color: {INK2}">Permanently removes identity, memory, skills and chat history.</span><span style="font-family: {MONO}; font-size: 11px; letter-spacing: 0.06em; color: {INK3}">TYPE <b style="color: {INK}">doc</b> TO CONFIRM</span><div style="height: 44px; border-radius: 4px; background: #f2f2f2; border: 0.5px solid {LINE2}"></div>{m_button("Delete profile", "danger", "lg")}{m_button("Cancel", "ghost", "lg")}</div>'
               f'<div style="width: 360px; border-radius: 4px; background: #ffffff; padding: 24px; box-sizing: border-box; display: flex; flex-direction: column; gap: 14px; box-shadow: 0 0 0 0.5px rgba(20,20,20,0.14)"><span style="font-weight: 600; font-size: 18px; color: {INK}">Restart the daemon</span><span style="font-size: 14px; line-height: 1.5; color: {INK2}">Every connected client briefly loses its socket.</span>{m_button("Restart", "primary", "lg")}{m_button("Cancel", "ghost", "lg")}</div>')
    toast = f'<div style="width: 360px; padding: 14px; border-radius: 4px; background: #ffffff; box-shadow: 0 0 0 0.5px rgba(20,20,20,0.14); display: flex; gap: 10px; align-items: flex-start"><span style="width: 8px; height: 8px; border-radius: 4px; background: #c14545; margin-top: 6px"></span><div style="display: flex; flex-direction: column; gap: 2px"><span style="font-size: 14px; font-weight: 600">Save failed</span><span style="font-size: 14px; color: {INK2}">daemon said no</span></div></div>'
    banners = f'<div style="width: 360px; padding: 10px 14px; border-radius: 4px; background: rgba(193,69,69,0.12); display: flex; align-items: center; gap: 10px; font-size: 14px; color: {INK}"><span style="flex: 1">Daemon unreachable. Reconnecting…</span>{m_button("Retry", "ghost", "sm")}</div>'
    load_failed = f'<div style="width: 360px; display: flex; flex-direction: column; align-items: center; gap: 12px; padding: 20px; text-align: center"><span style="font-size: 18px; font-weight: 600">Couldn’t load this conversation</span><span style="font-family: {MONO}; font-size: 11px; color: {INK3}">read timeout</span>{m_button("Retry", "secondary", "md")}</div><div style="width: 360px; display: flex; align-items: center; gap: 10px; padding: 14px 20px"><span style="flex: 1; font-size: 14px; font-weight: 500; color: {DANGER}">Couldn’t load email accounts</span><span style="font-size: 14px; font-weight: 500; color: {INK2}">Retry</span></div>'
    from conversation_boards import m_model_chip, m_tool
    m_scale = [("xs", 11), ("sm", 12), ("base", 13), ("md", 14), ("lg", 15), ("chat", 16), ("xl", 18), ("xxl", 22), ("display", 28)]
    m_types = "".join(f'<div style="display: flex; align-items: baseline; gap: 14px"><span style="width: 80px; font-family: {MONO}; font-size: 11px; color: {INK3}">{n} · {px}</span><span style="font-size: {px}px; line-height: 1.2; font-weight: {600 if n == "chat" else 400}; color: {INK}">{"Chat text reads at 16" if n == "chat" else "Made for the thumb"}</span></div>' for n, px in m_scale)
    m_types = f'<div style="display: flex; flex-direction: column; gap: 8px">{m_types}<span style="font-size: 12px; color: {INK3}">mobile drops xxs 9 and label 10 from the shared ladder and adds chat 16; every size follows the text-size setting</span></div>'
    row_states = f'<div style="display: flex; gap: 22px; align-items: center">{m_row_state("needs-you")}{m_row_state("failed")}{m_row_state("working", profile=DOC_ACCENT)}{m_row_state("working", "2/4", DOC_ACCENT)}</div>'
    roster = (f'<div style="width: 300px; padding: 6px 0; border-radius: 4px; background: {SIDE}; border: 0.5px solid {LINE}">{m_roster_row("abby", "#c33d7e", state="needs-you")}{m_roster_row("alpha", DOC_ACCENT, "workgroup", state="working", phases="2/4")}{m_roster_row("yuri", "#f0a58f", ts="6w", unread=True)}</div>'
              f'<div style="width: 390px; border-radius: 4px; border: 0.5px solid {LINE}; overflow: hidden">{m_roster_row("clonara", "#e2704a", state="failed", compact=False)}</div>')
    badges = (f'<span style="position: relative; display: inline-flex; margin: 8px">{ic("role:notifications", 16, INK2)}{m_count_badge(1, "danger", "#ffffff")}</span>'
              f'<span style="position: relative; display: inline-flex; margin: 8px">{ic("role:activity", 16, "#454545")}{m_count_badge(2, "danger", "#ffffff")}</span>'
              f'<span style="font-size: 12px; color: {INK3}">footer badges · one danger count, capped at 9+</span>')
    targets = (f'<div style="display: flex; gap: 18px; align-items: center">'
               + "".join(f'<span style="display: inline-flex; flex-direction: column; align-items: center; gap: 6px"><span style="width: {w}px; height: {h}px; border-radius: 4px; background: {HOVER}; border: 0.5px dashed {LINE2}; display: inline-flex; align-items: center; justify-content: center">{ic(i, 16, INK2) if i else ""}</span><span style="font-family: {MONO}; font-size: 11px; color: {INK3}">{t}</span></span>'
                         for w, h, i, t in ((44, 44, "gear", "tap 44"), (36, 36, "search", "chrome 36 + slop"), (80, 44, "", "row 44"), (120, 48, "", "button 48")))
               + '</div>')
    tools = f'<div style="width: 390px; border-radius: 4px; border: 0.5px solid {LINE}">{m_tool("read_file", "labs/2026-08-lipids.pdf")}{m_tool("shell", "src/app.ts:14  no-unused-vars", "failed")}{m_tool("web_fetch", "status.example.com", "running")}</div>'
    jump = f'<span style="display: inline-flex; align-items: center; gap: 8px; height: 36px; padding: 0 14px; border-radius: 4px; background: #ffffff; border: 0.5px solid {LINE2}; font-size: 12px; font-weight: 500; color: {INK2}">{ic("chev-d", 14, INK2)}Latest</span>'
    body = f"""<div style="padding: 40px 48px; display: flex; flex-direction: column; gap: 22px; box-sizing: border-box">
{h1("Components · phone and Fold", "Every primitive lives in mobile/src/components and reads the same tokens through useTheme(). Every target is 44 pt (chrome buttons draw 36 and pad the rest), rows at 44, buttons at 48, chat text at 16. On a fold or tablet the wide layout borrows the desktop grammar: eyebrow rows, a chat-style header, sheets that open as centred 560 dialogs.")}
<div style="display: flex; gap: 22px; align-items: flex-start">{specimen("Type scale · mobile", m_types, 560)}{specimen("Targets · 44 pt everywhere", targets, 600)}</div>
{specimen("Buttons · lg 48 · md 40 · sm 40 · radius 4 · haptic on press", buttons)}
<div style="display: flex; gap: 22px; align-items: flex-start">{specimen("RowState · needs you · failed · working · phases in mono", row_states, 560)}{specimen("Model chip · composer, model · effort, opens the model and effort sheets", m_model_chip("deepseek-v4.1-flash · medium"), 600)}</div>
{specimen("Roster rows · Fold compact 44 and phone 64 with preview, state under the time", roster)}
<div style="display: flex; gap: 22px; align-items: flex-start">{specimen("ToolCallRow · 44 pt, family icon, tap opens the sheet", tools, 422)}{specimen("CountBadge", badges, 400)}</div>
<div style="display: flex; gap: 22px; align-items: flex-start">{specimen("Row · phone (15 px label, mono helper, chevron gutter, danger)", rows, 422)}{specimen("WideRow · fold and tablet (eyebrow label, control right, gutter reserved)", wide, 552)}</div>
{specimen("Pill, OnOff, Meter, Toggle (optimistic, snaps back on failure)", pills + switch(True, DOC_ACCENT) + switch(False, DOC_ACCENT))}
{specimen("Field · 44 high, radius 4 · error state (border and helper in dangerText)", fields)}
<div style="display: flex; gap: 22px; align-items: flex-start">{specimen("PickerRow · 7 px dot, selected fill, one style everywhere", picker, 392)}{specimen("ActionSheet items · 20 px icon slot, mono detail, danger", actions, 392)}</div>
<div style="display: flex; gap: 22px; align-items: flex-start">{specimen("Sheet · grabber, title 18, mono subtitle, X · primaryAction [secondary, primary] · dismissible=false for decisions", sheet_spec, 422, SIDE)}{specimen("TypedConfirm · danger + typed for deletes · neutral untyped for reversible actions", confirm, 400, SIDE)}</div>
<div style="display: flex; gap: 22px; align-items: flex-start">{specimen("Toast · top, max 560, 2.8 s", toast, 392)}{specimen("Banner · daemon states", banners, 392)}{specimen("JumpToLatest", jump, 200)}</div>
{specimen("Waiting · Busy for a page or a section, the Spinner arc inside controls, pulsing skeleton rows inside the cards they will fill · no ActivityIndicator", waiting(mobile=True))}
{specimen("LoadFailed · card and inline row (accessibilityRole alert)", load_failed, 780)}
{specimen("NotificationBody · digest entries · a failed run as a flat card on the group tone, Details folds at 44 pt, Run again and Open job", notification_reader(360, 14, mobile=True))}
</div>"""
    return page("System · mobile components", 1280, MOBILE_COMPONENTS_H, body)


TOKENS_H = 2580
DESKTOP_COMPONENTS_H = 3080
MOBILE_COMPONENTS_H = 3870

DESKTOP_MOTION = [
    ("Hover, press, tooltip", "--dur-1 · 120 ms", "colour and opacity only"),
    ("New turn", "--dur-2 · 200 ms", "rises 8 px and fades in; only turns appended after the thread is on screen"),
    ("Streaming text", "150 ms", "only the newest chunk fades; nothing already shown re-animates"),
    ("Steps and reasoning open", "--dur-2 · 200 ms", "grid-rows reveal; reasoning folds itself when the answer lands"),
    ("Modal and dialog exit", "120 ms", "fade and scale down; a timer closes it if the animation never ends"),
    ("Working pulse, dots", "--dur-loop · 1.4 s", "a phase or a profile at work; the only loop that carries a profile colour"),
    ("Busy mark", "1.6 s wave", "the brand alpaca for a page or section wait: after 300 ms, at least 400 ms on screen, opacity only"),
    ("Spinner", f"--dur-spin · {DUR_SPIN} s", "SpinnerIcon, a dashed circle inside Button, Chip, the stopping Send, attachments and read aloud"),
    ("Skeleton shimmer", f"--dur-loop · {DUR_LOOP} s", "skShimmer over SkeletonRows and SkeletonReader lines, an ink 9 % highlight"),
    ("Reduced motion", "global rule", "one prefers-reduced-motion rule stops every animation and transition"),
]
MOBILE_MOTION = [
    ("New message", "180 ms FadeIn", "only rows that arrive after the first page; recycled rows never fade again"),
    ("Pane replace", "120 ms crossfade", "Fold and tablet two-pane navigation"),
    ("Sidebar open and close", "200 ms", "the Fold and tablet roster slides and narrows instead of snapping"),
    ("Thought, group, step", "180 ms", "opening and closing measure the height and fade the content"),
    ("Latest button", "150 ms", "fades in with an 8 pt rise when the reader scrolls away"),
    ("Sheet in and out", "220 ms", "drag to dismiss on the header when the sheet is dismissible"),
    ("Keyboard", "frame by frame", "the composer rides the keyboard with useAnimatedKeyboard; swipe down dismisses"),
    ("Long press", "350 ms · pulse 160 ms", "nothing moves on a tap or a scroll; only a recognised long press pulses once with the haptic as the menu opens"),
    ("Working pulse", "1.4 s", "roster state dot; static under reduce motion"),
    ("Busy mark", "1.6 s wave", "the brand alpaca for a page or section wait: after 300 ms, at least 400 ms on screen"),
    ("Spinner", f"{SPINNER_TURN_MS} ms turn", "a 270° arc inside Button, attachment cards, rich text images, the member sheet and the model sheets; RefreshControl stays the system gesture"),
    ("Skeleton", f"{PULSE_MS} ms pulse", "SkeletonBar opacity 0.4 ↔ 0.8 inside the RowGroup cards they will fill; still at 0.6 under reduce motion"),
    ("Reduce motion", "one shared value", "every fade, pulse and shimmer reads one app-wide setting"),
]
HAPTICS = [
    ("tap", "light impact", "send, stop"),
    ("selection", "selection tick", "long press, pull to refresh, action sheet open, toggles, roster create buttons"),
    ("warning", "warning notification", "an approval or a question sheet opens; a destructive typed confirm"),
    ("success", "success notification", "available for confirmations; unused today"),
]


def motion_board():
    def table(rows, cols="200px 170px 1fr"):
        return "".join(
            f'<div style="display: grid; grid-template-columns: {cols}; gap: 14px; padding: 9px 0; border-top: 0.5px solid {LINE}; align-items: baseline">'
            f'<span style="font-size: 13px; color: {INK}">{a}</span><span style="font-family: {MONO}; font-size: 12px; color: {INK2}">{b}</span><span style="font-size: 12.5px; line-height: 1.5; color: {INK3}">{c}</span></div>'
            for a, b, c in rows)
    body = f"""<div style="padding: 40px 48px; display: flex; flex-direction: column; gap: 22px; box-sizing: border-box">
{h1("Motion and feel", "Still boards cannot move, so this page states what moves, for how long and what it answers to. Motion marks change: a new turn, the streaming edge, a step opening, the keyboard. Nothing loops except the working pulse, the brand busy wave, the control spinner and the skeleton shimmer or pulse, and reduced motion turns it all off.")}
<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 28px; align-items: start">
<div style="display: flex; flex-direction: column">{label("Desktop")}<div style="height: 8px"></div>{table(DESKTOP_MOTION, "170px 140px 1fr")}</div>
<div style="display: flex; flex-direction: column">{label("Phone and Fold")}<div style="height: 8px"></div>{table(MOBILE_MOTION, "150px 130px 1fr")}</div>
</div>
<div style="display: flex; flex-direction: column">{label("Haptics · src/lib/haptics.js")}<div style="height: 8px"></div>{table(HAPTICS, "120px 180px 1fr")}</div>
</div>"""
    return page("System · motion and feel", 1280, 900, body)


SYSTEM = {"tokens": tokens_board, "motion": motion_board, "desktop": desktop_components_board, "mobile": mobile_components_board}
