import base64
import os

from conversation_boards import label
from desktop_boards import ELEV, LG_FLOAT, SM_FLOAT, badged, button, key_hint
from desktop_overlays import menu_sep
from first_run_parts import DANGER_TEXT, HOVER, INK, INK2, INK3, LINE, PANE, alp, col, line, mono, t
from gen import DOC_ACCENT, button_heights, di, identity_glyph, page

TRAY_ICONS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "desktop", "src-tauri", "icons", "tray")
SUCCESS = "#217a45"
WARNING = "#b3470e"
BAR_LIGHT, BAR_LIGHT_INK = "#e6e4df", "#1d1d1f"
BAR_DARK, BAR_DARK_INK = "#26262a", "#f5f5f7"
WALLPAPER = "linear-gradient(100deg, #7a8fb8 0%, #b98fa8 52%, #d9b27c 100%)"
SM = button_heights("desktop")["sm"]
STATES = ("quiet", "dot", "needs", "offline")
SIZES = (16, 20, 22, 24, 32, 36)

POPOVER_HEIGHTS = {
    "next": 107, "none": 107, "member": 107, "needs": 267, "many": 307, "failing": 147, "running": 147, "update": 147,
    "stopped": 127, "unreachable": 107, "starting": 139, "connecting": 107, "online": 107, "hero": 307,
}
TRAY_H = 2460
TRAY_ICON_H = 1590


def png_uri(name):
    with open(os.path.join(TRAY_ICONS, name), "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()


ASSETS = {(s, n): png_uri(f"tray-{s}-{n}.png") for s in STATES for n in SIZES}


def glyph(state, size, shown, ink="light"):
    tone = "" if ink == "light" else " filter: brightness(0) invert(1);"
    return (f'<img src="{ASSETS[(state, size)]}" alt="{state} tray icon" width="{shown}" height="{shown}" '
            f'style="display: block; flex-shrink: 0; image-rendering: pixelated;{tone}">')


def zoom_glyph(state, size, factor=8):
    px = size * factor
    mask = f"url({ASSETS[(state, size)]}) center / 100% 100% no-repeat"
    return (f'<span role="img" aria-label="{state} tray icon, {factor}x" style="display: block; width: {px}px; height: {px}px; flex-shrink: 0; '
            f'background: {INK}; -webkit-mask: {mask}; mask: {mask}; image-rendering: pixelated; -webkit-mask-size: 100% 100%; mask-size: 100% 100%"></span>')


def menubar(state, bar, w=342):
    bg, fg, ink = (BAR_LIGHT, BAR_LIGHT_INK, "light") if bar == "light" else (BAR_DARK, BAR_DARK_INK, "dark")
    clock = f'<span style="font-size: 12px; line-height: 1; font-weight: 500; color: {fg}">Tue 9:41</span>'
    return (f'<div style="width: {w}px; height: 24px; box-sizing: border-box; display: flex; align-items: center; justify-content: flex-end; gap: 12px; padding: 0 12px; '
            f'border-radius: 4px; background: {bg}; color: {fg}">{glyph(state, 36, 18, ink)}{clock}</div>')


def window(inner):
    return f'<div style="width: 342px; padding: 1px; box-sizing: border-box; flex-shrink: 0">{inner}</div>'


def popover(*parts):
    return window(f'<main style="width: 340px; display: flex; flex-direction: column; border-radius: 4px; background: {ELEV}; {LG_FLOAT}; overflow: hidden">{"".join(parts)}</main>')


def head(title, sub, right="", nowrap=False):
    sub_style = "display: flex; white-space: nowrap" if nowrap else ""
    return (f'<header style="display: flex; align-items: center; gap: 12px; padding: 12px">{alp(28)}'
            f'<div style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px">'
            f'<h1 style="margin: 0; font-size: 15px; line-height: 20px; font-weight: 600; color: {INK}">{title}</h1>'
            f'<p style="margin: 0; font-size: 13px; line-height: 16px; color: {INK3}; {sub_style}">{sub}</p></div>{right}</header>')


def next_sub(title, when):
    return (f'<span style="flex-shrink: 0">Next:&nbsp;</span><span style="min-width: 0; overflow: hidden; text-overflow: ellipsis">{title}</span>'
            f'<span style="flex-shrink: 0">&nbsp;·&nbsp;{when}</span>')


def needs_row(profile, color, title, sub):
    return (f'<li style="display: flex; align-items: center; gap: 8px; height: 40px; padding-right: 8px; border-radius: 4px">'
            f'<span style="flex: 1; min-width: 0; height: 100%; display: flex; align-items: center; gap: 8px; padding: 0 12px">'
            f'<span style="width: 16px; display: inline-flex; justify-content: center; flex-shrink: 0">{identity_glyph(profile, color, 16)}</span>'
            f'<span style="flex: 1; min-width: 0; display: flex; flex-direction: column">'
            f'<span style="font-size: 13px; line-height: 16px; color: {INK}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis">{title}</span>'
            f'<span style="font-family: \'Geist Mono\', monospace; font-size: 11px; line-height: 16px; color: {INK3}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis">{sub}</span></span></span>'
            f'{button("Review", "secondary", "sm")}</li>')


def needs_section(rows, more=0):
    tail = more_row(more) if more else ""
    return f'<section aria-label="Needs you" style="padding: 0 8px 8px"><ul style="margin: 0; padding: 0; list-style: none">{"".join(rows)}</ul>{tail}</section>'


def count_row(icon, text, value, danger=False):
    tone = DANGER_TEXT if danger else INK3
    return (f'<div role="button" style="display: flex; align-items: center; gap: 8px; height: 32px; padding: 0 12px; border-radius: 4px">'
            f'<span style="width: 16px; display: inline-flex; justify-content: center; flex-shrink: 0">{di(icon, 16, tone)}</span>'
            f'<span style="flex: 1; min-width: 0; font-size: 13px; line-height: 16px; color: {INK2}">{text}</span>'
            f'<span style="font-family: \'Geist Mono\', monospace; font-size: 11px; color: {tone}">{value}</span>{di("chev-r", 14, INK3)}</div>')


def counts_section(*rows):
    return f'<section aria-label="Counts" style="padding: 0 8px 8px">{"".join(rows)}</section>'


def more_row(n):
    return (f'<div role="button" style="display: flex; align-items: center; height: 32px; padding: 0 12px; border-radius: 4px; font-size: 13px; line-height: 16px; color: {INK2}">'
            f'<span style="flex: 1">{n} more · Open alpi</span>{di("chev-r", 14, INK3)}</div>')


def busy_row(text):
    return (f'<div role="status" style="display: flex; align-items: center; gap: 8px; height: 32px; padding: 0 12px">'
            f'<span style="width: 16px; display: inline-flex; justify-content: center; flex-shrink: 0">{di("refresh", 16, INK3)}</span>'
            f'<span style="flex: 1; font-size: 13px; line-height: 16px; color: {INK2}">{text}</span></div>')


def update_row(version="0.10.1"):
    return (f'<div style="display: flex; align-items: center; gap: 8px; min-height: 40px; padding: 4px 12px; box-sizing: border-box; border-top: 0.5px solid {LINE}">'
            f'<span style="width: 16px; display: inline-flex; justify-content: center; flex-shrink: 0">{di("download", 16, SUCCESS)}</span>'
            f'<span style="flex: 1; min-width: 0; font-size: 13px; line-height: 16px; color: {INK}">alpi {version} is ready</span>{button("Restart to update", "secondary", "sm")}</div>')


def foot(unread=0, bell=True):
    notifications = badged("role:notifications", "Notifications · " + str(unread) + " unread" if unread else "Notifications", unread, SM) if bell else ""
    settings = button("", "ghost", "sm", icon="role:settings", icon_only=True).replace('<button ', '<button aria-label="Settings" ', 1)
    quit_ = button("", "ghost", "sm", icon="power", icon_only=True).replace('<button ', '<button aria-label="Quit alpi" ', 1)
    return (f'<footer style="display: flex; align-items: center; gap: 4px; padding: 8px 12px; border-top: 0.5px solid {LINE}">'
            f'{button("Open alpi", "secondary", "sm")}<span style="flex: 1"></span>{notifications}{settings}{quit_}</footer>')


ABBY = ("abby", "#df4b9d")
DOC = ("doc", DOC_ACCENT)
CLONARA = ("clonara", "#f05940")
SENTINEL = ("sentinel", "#3b6fe0")
ALPI = ("alpi", "#14110c")
APPROVAL = "wants to run a command"
FAILING_COUNT = count_row("alert", "Failing jobs", "3 in 2 profiles", True)
RUNNING_COUNT = count_row("activity", "Running", "2")

ROWS = (
    needs_row(*ABBY, APPROVAL, "abby · approval · 2m ago"),
    needs_row(*DOC, "Which lab should I book with?", "doc · question · just now"),
    needs_row(*CLONARA, APPROVAL, "clonara · approval · 6m ago"),
    needs_row(*SENTINEL, "has a question", "sentinel · question · 9m ago"),
)


def s_next():
    return popover(head("All quiet", next_sub("Daily brief", "today 18:00"), nowrap=True), foot())


def s_next_long():
    return popover(head("All quiet", next_sub("Summarize yesterday’s deploys and flag anything that needs a rollback", "tomorrow 07:30"), nowrap=True), foot())


def s_none():
    return popover(head("All quiet", "Nothing scheduled"), foot())


def s_member():
    return popover(head("All quiet", "Nothing needs you · online"), foot(bell=False))


def s_needs():
    return popover(head("2 need you", "abby is waiting for an approval"), needs_section(ROWS[:2]), counts_section(FAILING_COUNT, RUNNING_COUNT), foot(1))


def s_many():
    return popover(head("7 need you", "5 approvals, 2 questions"), needs_section(ROWS, 3), foot(4))


def s_failing():
    return popover(head("3 jobs failing", "sentinel and clonara · last 24 h"), counts_section(FAILING_COUNT), foot())


def s_running():
    return popover(head("2 running", "alpi · Summarize yesterday’s deploys"), counts_section(RUNNING_COUNT), foot())


def s_update():
    return popover(head("All quiet", next_sub("Daily brief", "today 18:00"), nowrap=True), update_row(), foot())


def s_stopped():
    return popover(head("alpi is installed but not running", "Start it on this computer.", button("Start alpi", "primary", "sm")), foot())


def s_unreachable():
    return popover(head("Can’t reach alpi", "Check the connection in alpi."), foot())


def s_starting():
    return popover(head("Starting alpi…", "Waiting for the daemon"), busy_row("Start requested"), foot())


def s_connecting():
    return popover(head("Connecting…", "Waiting for the daemon"), foot())


def s_online():
    return popover(head("alpi", "online"), foot())


def s_hero():
    return popover(head("2 need you", "abby is waiting for an approval"), needs_section(ROWS[:2]), counts_section(FAILING_COUNT, RUNNING_COUNT), update_row(), foot(1))


def native_item(text, hint="", disabled=False):
    color = INK3 if disabled else INK
    return (f'<div role="menuitem" aria-disabled="{"true" if disabled else "false"}" style="display: flex; align-items: center; gap: 8px; min-height: 32px; padding: 8px 12px; box-sizing: border-box; border-radius: 4px; font-size: 13px; line-height: 16px; color: {color}">'
            f'<span style="flex: 1">{text}</span>{key_hint(hint) if hint else ""}</div>')


def native_menu(*items, w=240):
    return f'<div style="width: {w}px; flex-shrink: 0; padding: 4px; box-sizing: border-box; border-radius: 4px; background: {ELEV}; {SM_FLOAT}">{"".join(items)}</div>'


def menu_plain():
    return native_menu(native_item("Open Alpi", "⌘⇧A"), native_item("Settings…", "⌘,"), menu_sep(), native_item("Quit Alpi", "⌘Q"))


def menu_full():
    return native_menu(native_item("Open Alpi", "⌘⇧A"), native_item("Settings…", "⌘,"), native_item("Notifications (3)", "⌘O"), menu_sep(),
                       native_item("An update is available (0.10.1)", disabled=True), native_item("Restart to update"), menu_sep(), native_item("Quit Alpi", "⌘Q"))


def caption(title, note, size=None):
    dims = mono(size, 11, INK3) if size else ""
    return col(t(title, 13, INK, 600), t(note, 12, INK3, 400, "line-height: 1.45"), dims, gap=3, extra="min-width: 0")


def cell(drawing, title, note, key=None):
    size = f"342 × {POPOVER_HEIGHTS[key] + 2} px window" if key else None
    return col(drawing, caption(title, note, size), gap=8, extra="width: 342px; flex-shrink: 0")


def grid3(*cells):
    return f'<div style="display: grid; grid-template-columns: repeat(3, 342px); gap: 28px 24px; align-items: start">{"".join(cells)}</div>'


def section(title, inner, gap=12):
    return col(label(title), inner, gap=gap)


def fact_table(head_cells, rows, widths):
    tpl = " ".join(widths)

    def r(cells, hd=False):
        look = f"font-family: 'Geist Mono', monospace; font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase; color: {INK3}" if hd else f"font-size: 12px; line-height: 1.45; color: {INK2}"
        body = "".join(f'<span style="min-width: 0; {look}">{c}</span>' for c in cells)
        return f'<div style="display: grid; grid-template-columns: {tpl}; gap: 12px; padding: 6px 0; border-bottom: 0.5px solid {LINE}; align-items: start">{body}</div>'

    return f'<div style="display: flex; flex-direction: column">{r(head_cells, True)}{"".join(r(x) for x in rows)}</div>'


def intro(title, text):
    return (f'<div style="display: flex; flex-direction: column; gap: 4px"><span style="font-size: 22px; font-weight: 600; letter-spacing: -0.018em">{title}</span>'
            f'<span style="font-size: 13px; color: {INK3}; max-width: 960px; line-height: 1.5">{text}</span></div>')


def note(text):
    return t(text, 12, INK3, 400, "line-height: 1.5; max-width: 960px")


def click_pair():
    left = col(menubar("needs", "light"), s_hero(), t("Left click on macOS and Windows: the popover under the icon.", 12, INK3), gap=6, extra="width: 342px")
    right = col(menubar("dot", "light", 240), menu_full(), t("Right click: the native menu, three unread and an update ready.", 12, INK3), gap=6, extra="width: 240px")
    plain = col(menu_plain(), t("Nothing unread, no update.", 12, INK3), gap=6, extra="width: 240px")
    return line(left, right, plain, gap=40, align="flex-start")


def per_platform():
    rows = (
        ("Left click", "popover under the icon", "popover above the taskbar", "native menu on click"),
        ("Right click", "native menu", "native menu", "native menu"),
        ("Dismiss", "Esc, or focus leaves the popover", "Esc, or focus leaves the popover", "the menu closes itself"),
        ("Icon asset", "36 px, template", "16, 20, 24 or 32 px by display scale", "22 px, 24 px above 1.0 scale"),
    )
    return fact_table(("", "macOS", "Windows", "Linux"), rows, ("96px", "1fr", "1fr", "1fr"))


def tray_board():
    hero = section("Left click and right click", click_pair())
    states = section("Quiet and member", grid3(
        cell(s_next(), "All quiet, next job", "An admin with an upcoming scheduled job: Next: the job, then when.", "next"),
        cell(s_next_long(), "All quiet, long job title", "The title truncates with an ellipsis; the lead and the time stay whole.", "next"),
        cell(s_none(), "All quiet, nothing scheduled", "An admin with no upcoming job.", "none"),
        cell(s_member(), "All quiet, member", "No scheduled jobs and no bell: a member never sees them.", "member"),
        cell(s_online(), "Online, no activity verb", "An older daemon without host.activity.list: the heading says only that it is online.", "online"),
        cell(s_update(), "Update ready", "The update row sits above the footer in every state.", "update")))
    attention = section("Needs you, failing and running", grid3(
        cell(s_needs(), "Needs you", "Approvals and questions with Review; the failing and running counts below.", "needs"),
        cell(s_many(), "Many items", "Four rows, then the rest named; the row opens alpi.", "many"),
        cell(s_failing(), "Failing jobs", "Danger count over the last 24 h; the row opens alpi.", "failing"),
        cell(s_running(), "Running turns", "The first running turn is named under the count.", "running")))
    link = section("Daemon states", grid3(
        cell(s_stopped(), "Daemon stopped", "Installed here: Start alpi is the one action.", "stopped"),
        cell(s_unreachable(), "Can’t reach alpi", "A remote daemon: the heading names the problem and the footer stays.", "unreachable"),
        cell(s_starting(), "Starting", "While Start alpi runs.", "starting"),
        cell(s_connecting(), "Connecting", "Activity still loading: the popover never claims all quiet.", "connecting")))
    rules = section("Rules", col(
        note("The popover never calls the daemon and never reads ~/.alpi: the main window pushes one snapshot, already filtered by connection and profile scope. It follows the app theme (System, Light or Dark) and is 340 wide inside a 342 window."),
        note("Esc and losing focus hide it. Open alpi and Review show, unminimize and focus the main window; Review carries the deeplink of an approval or a question. The footer bell is hidden for members."),
        per_platform(), gap=10))
    body = (f'<div style="padding: 28px 32px; display: flex; flex-direction: column; gap: 28px; box-sizing: border-box">'
            f'{intro("Tray popover", "A left click on the menu bar icon opens a small popover that triages: what needs you with Review, failing jobs, running turns, the next scheduled job, an update ready, and Open alpi, notifications, Settings and Quit in the footer. A right click keeps the native menu.")}'
            f'{hero}{states}{attention}{link}{rules}</div>')
    return page("Desktop · tray", 1280, TRAY_H, body)


def strip(state, bar, size=36, shown=18, w=64):
    if bar == "light":
        bg, ink = BAR_LIGHT, "light"
    elif bar == "dark":
        bg, ink = BAR_DARK, "dark"
    else:
        bg, ink = "rgba(255, 255, 255, 0.28)", "light"
    wall = f"background: {WALLPAPER}; " if bar == "glass" else ""
    return (f'<span style="{wall}display: inline-flex; border-radius: 4px; overflow: hidden; flex-shrink: 0">'
            f'<span style="width: {w}px; height: {max(24, shown + 8)}px; display: inline-flex; align-items: center; justify-content: center; background: {bg}">{glyph(state, size, shown, ink)}</span></span>')


STATE_NOTES = {
    "quiet": ("Quiet", "Nothing wants you.", "alpi · all quiet"),
    "dot": ("Dot", "Unread output or an update ready.", "alpi · 0.10.1 is ready"),
    "needs": ("Needs you", "An approval or a question waits: a ring.", "alpi · 2 need you"),
    "offline": ("Offline", "The daemon is not running: a slash.", "alpi · not running"),
}


def state_card(state):
    name, rule, tip = STATE_NOTES[state]
    bars = line(strip(state, "light", w=56), strip(state, "dark", w=56), strip(state, "glass", w=56), gap=8)
    return col(bars, t(name, 13, INK, 600), t(rule, 12, INK3, 400, "line-height: 1.45"), mono(tip, 11, INK2), mono(f"tray-{state}-36.png", 11, INK3), gap=6, extra="width: 280px; flex-shrink: 0")


def zoom_card(state):
    return col(
        f'<div style="padding: 0; border-radius: 4px; background: {PANE}; box-shadow: 0 0 0 0.5px {LINE}; width: 288px; height: 288px; flex-shrink: 0">{zoom_glyph(state, 36)}</div>',
        mono(f"{STATE_NOTES[state][0].lower()} · 36 px · 8x", 11, INK3), gap=8)


def size_row(size, where):
    cells = "".join(strip(s, "light", size, size, size + 16) for s in STATES)
    dark = "".join(strip(s, "dark", size, size, size + 16) for s in STATES)
    return (f'<div style="display: grid; grid-template-columns: 132px 1fr; gap: 12px; align-items: center; padding: 6px 0; border-bottom: 0.5px solid {LINE}">'
            f'{col(t(f"{size} px", 12, INK, 500), t(where, 12, INK3), gap=1)}'
            f'{line(line(cells, gap=4), line(dark, gap=4), gap=16)}</div>')


SIZE_USE = {16: "Windows, scale 1.0", 20: "Windows, scale 1.25", 22: "Linux", 24: "Windows 1.5, Linux above 1.0", 32: "Windows, scale 2.0 and up", 36: "macOS, shown at 18 pt"}


def tooltip_table():
    rows = (
        ("All quiet", "alpi · all quiet"), ("Needs you", "alpi · 2 need you"), ("Failing jobs", "alpi · 3 jobs failing"), ("Running", "alpi · 2 running"),
        ("Update ready", "alpi · 0.10.1 is ready"), ("Daemon stopped", "alpi · not running"), ("Starting", "alpi · starting…"), ("Connecting", "alpi · connecting…"), ("Online", "alpi · online"))
    return fact_table(("State", "Tooltip"), [(a, mono(b, 12, INK)) for a, b in rows], ("140px", "1fr"))


def tray_icon_board():
    ones = section("Four states at 1:1", line(*(state_card(s) for s in STATES), gap=24, align="flex-start"))
    zoomed = section("Zoomed 8x, nearest neighbour", line(*(zoom_card(s) for s in STATES), gap=12, align="flex-start"))
    ladder = section("Every shipped size, light and dark bars", col(*(size_row(n, SIZE_USE[n]) for n in SIZES), gap=0))
    rules = section("Rules", col(
        note("One ink with binary alpha: the asset is a template the OS tints for the bar, so it reads on a light, a dark and a translucent bar. The facets sit on the pixel grid of each size, the creases are exact 1 px gaps from 32 px, and the marks carry a 1 px knock-out."),
        note("Priority: needs you (ring), then offline (slash), then unread or an update (dot), then quiet. The icon is set once, and only when the state or the size changed."),
        note("Windows and Linux pick the size from the display scale when the state changes: moving the app between displays of different scale keeps the old size until the next state change."), gap=8))
    tips = section("Tooltip", tooltip_table())
    body = (f'<div style="padding: 28px 32px; display: flex; flex-direction: column; gap: 28px; box-sizing: border-box">'
            f'{intro("Tray icon", "Four pixel-exact states generated by scripts/gen_icons.py and read here from the shipped PNGs: quiet, dot, needs you and offline. On macOS the 36 px asset is shown at 18 pt.")}'
            f'{ones}{zoomed}{ladder}{rules}{tips}</div>')
    return page("Desktop · tray icon", 1280, TRAY_ICON_H, body)
