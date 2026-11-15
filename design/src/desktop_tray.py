import base64
import os

import agent_marks as am
import marks
from brand_boards import BRICOLAGE, EXTRA_FONTS
from conversation_boards import label
from desktop_boards import ELEV, SM_FLOAT, badged, button, key_hint
from desktop_boards import LINE
from first_run_parts import DANGER_TEXT, INK, INK2, INK3, PANE, col, line, mono, t
from gen import PALETTES, R_CONTROL, R_SURFACE, banner_surface, button_heights, di, page

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
    "next": 346, "next_long": 208, "none": 124, "member": 124, "online": 124, "update": 176, "needs": 326, "other": 346, "many": 402, "failing": 410,
    "running_one": 376, "running": 400, "needs_running": 514, "full": 352, "stopped": 172, "unreachable": 124, "starting": 156, "connecting": 124,
}
TRAY_H = 4400
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
    clock = f'<span style="font-size: 14px; line-height: 1; font-weight: 500; color: {fg}">Tue 9:41</span>'
    return (f'<div style="width: {w}px; height: 24px; box-sizing: border-box; display: flex; align-items: center; justify-content: flex-end; gap: 12px; padding: 0 12px; '
            f'border-radius: 4px; background: {bg}; color: {fg}">{glyph(state, 36, 18, ink)}{clock}</div>')


def window(inner):
    return f'<div style="width: 342px; padding: 1px; box-sizing: border-box; flex-shrink: 0">{inner}</div>'


def popover(*parts):
    return window(f'<main style="width: 340px; display: flex; flex-direction: column; border-radius: {R_SURFACE}px; background: {ELEV}; box-shadow: inset 0 0 0 1px {LINE}; overflow: hidden">{"".join(parts)}</main>')


C = am.COLOUR
CAST = {
    "abby": ("drop", C["magenta"]), "doc": ("squircle", C["blue"]), "clonara": ("arch", C["vermilion"]), "sentinel": ("bell", C["indigo"]),
    "scribe": ("cloud", C["sky"]), "curator": ("pebble", C["green"]), "alpi": ("twin", None),
}
TABULAR = "font-variant-numeric: tabular-nums"
NAME_CSS = (f'<style>.tray-name {{ font-family: {BRICOLAGE}; font-weight: 800; letter-spacing: -0.04em; color: var(--name-light, {INK}) }}'
            f'@media (prefers-color-scheme: dark) {{ :root:not([data-mode="light"]) .tray-name {{ color: var(--name-dark, {INK}) }} }}'
            f'[data-mode="dark"] .tray-name {{ color: var(--name-dark, {INK}) }}</style>')
HEAD_MARK = {"needs": "needs", "running": "working", "failing": "failed", "offline": "offline", "starting": "busy", "connecting": "busy"}
ELLIPSIS = "white-space: nowrap; overflow: hidden; text-overflow: ellipsis"


def tone_vars(name):
    accent = CAST[name][1]
    if not accent:
        return ""
    return f"--name-light: {marks.name_tone(accent, PALETTES['light']['bgPane'])}; --name-dark: {marks.name_tone(accent, PALETTES['dark']['bgPane'])}; "


def head(title, sub, state="quiet"):
    return (f'<header style="display: flex; align-items: center; gap: 12px; padding: 16px 16px 12px">'
            f'<span style="display: inline-flex; flex-shrink: 0">{marks.twin(40, HEAD_MARK.get(state, "idle"), seed="tray-head" + state + title)}</span>'
            f'<div style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px">'
            f'<h1 style="margin: 0; font-size: 20px; line-height: 24px; font-weight: 600; letter-spacing: -0.01em; color: {INK}; {ELLIPSIS}">{title}</h1>'
            f'<p style="margin: 0; font-size: 14px; line-height: 18px; color: {INK3}; {ELLIPSIS}">{sub}</p></div></header>')


def row(name, title, where="", time="", state="idle", review=False):
    shape, accent = CAST[name]
    live = state != "idle"
    mark = marks.shape_mark(shape, accent, 24, state, seed="tray" + name + title + state, still=not live)
    tail = f'<span style="font-size: 12px; color: {INK3}">&nbsp;·&nbsp;{where}</span>' if where else ""
    clock = f'<span style="flex-shrink: 0; font-size: 14px; color: {INK2}; white-space: nowrap; {TABULAR}">{time}</span>' if time else ""
    who = (f'<span style="display: flex; align-items: baseline; gap: 8px; min-width: 0; height: 18px; line-height: 18px">'
           f'<span style="flex: 1; min-width: 0; {ELLIPSIS}"><span class="tray-name" style="{tone_vars(name)}font-size: 14px">{name}</span>{tail}</span>{clock}</span>')
    text = (f'<span style="flex: 1; min-width: 0; display: flex; flex-direction: column">{who}'
            f'<span style="font-size: 15px; line-height: 20px; color: {INK}; {ELLIPSIS}">{title}</span></span>')
    main_pad = "8px 0 8px 12px" if review else "8px 12px"
    side = button("Review", "secondary", "sm") if review else ""
    return (f'<li style="display: flex; align-items: center; gap: 12px; min-height: 52px; padding-right: {12 if review else 0}px; border-radius: {R_CONTROL}px">'
            f'<span style="flex: 1; min-width: 0; align-self: stretch; display: flex; align-items: center; gap: 12px; padding: {main_pad}">'
            f'<span style="width: 24px; display: inline-flex; justify-content: center; flex-shrink: 0">{mark}</span>{text}</span>{side}</li>')


def group(title, *parts):
    return (f'<section aria-label="{title}" style="padding: 0 8px 4px">'
            f'<p style="margin: 0; padding: 6px 12px 2px; font-size: 14px; line-height: 18px; font-weight: 500; color: {INK3}">{title}</p>'
            f'<ul style="margin: 0; padding: 0; list-style: none">{"".join(p for p in parts if p.startswith("<li"))}</ul>{"".join(p for p in parts if not p.startswith("<li"))}</section>')


def line_row(text, value="", icon=None):
    glyph = f'<span style="width: 24px; display: inline-flex; justify-content: center; flex-shrink: 0">{di(icon, 16, INK3)}</span>' if icon else ""
    val = f'<span style="font-size: 14px; color: {INK2}; {TABULAR}">{value}</span>' if value else ""
    return (f'<div role="button" style="display: flex; align-items: center; gap: 8px; height: 32px; padding: 0 12px; border-radius: {R_CONTROL}px">'
            f'{glyph}<span style="flex: 1; min-width: 0; font-size: 15px; line-height: 16px; color: {INK2}">{text}</span>{val}{di("chev-r", 16, INK3)}</div>')


def counts_section(*rows):
    return f'<section aria-label="Counts" style="padding: 0 8px 4px">{"".join(rows)}</section>'


def busy_row(text):
    return (f'<div role="status" style="display: flex; align-items: center; gap: 8px; height: 32px; padding: 0 12px">'
            f'<span style="width: 24px; display: inline-flex; justify-content: center; flex-shrink: 0">{di("refresh", 16, INK3)}</span>'
            f'<span style="flex: 1; font-size: 15px; line-height: 16px; color: {INK2}">{text}</span></div>')


def failing_banner(title="3 jobs failed in 24 h", detail="sentinel and clonara"):
    return (f'<div role="button" style="display: flex; align-items: center; gap: 12px; margin: 4px 8px 8px; padding: 8px 12px; min-height: 52px; box-sizing: border-box; '
            f'border-radius: {R_CONTROL}px; background: {banner_surface("danger")}">'
            f'<span style="width: 24px; display: inline-flex; justify-content: center; flex-shrink: 0">{di("alert", 20, DANGER_TEXT)}</span>'
            f'<span style="flex: 1; min-width: 0; display: flex; flex-direction: column">'
            f'<span style="font-size: 15px; line-height: 20px; font-weight: 500; color: {DANGER_TEXT}">{title}</span>'
            f'<span style="font-size: 12px; line-height: 16px; color: {INK2}; {ELLIPSIS}">{detail}</span></span>{di("chev-r", 16, INK3)}</div>')


def update_banner(version="0.18.11"):
    return (f'<div style="display: flex; align-items: center; gap: 12px; margin: 4px 8px 0; padding: 8px 8px 8px 12px; min-height: 48px; box-sizing: border-box; '
            f'border-radius: {R_CONTROL}px; background: {banner_surface("success")}">'
            f'<span style="width: 24px; display: inline-flex; justify-content: center; flex-shrink: 0">{di("download", 20, SUCCESS)}</span>'
            f'<span style="flex: 1; min-width: 0; font-size: 15px; line-height: 20px; color: {INK}">alpi {version} is ready</span>{button("Restart", "secondary", "sm")}</div>')


def start_row():
    pill = button("Start alpi", "primary", "md").replace("flex-shrink: 0", "flex: 1; justify-content: center")
    return f'<div style="display: flex; padding: 0 16px 8px">{pill}</div>'


def foot(unread=0, bell=True):
    notifications = badged("role:notifications", "Notifications · " + str(unread) + " unread" if unread else "Notifications", unread, SM) if bell else ""
    settings = button("", "ghost", "sm", icon="role:settings", icon_only=True).replace('<button ', '<button aria-label="Settings" ', 1)
    quit_ = button("", "ghost", "sm", icon="power", icon_only=True).replace('<button ', '<button aria-label="Quit alpi" ', 1)
    return (f'<footer style="display: flex; align-items: center; gap: 4px; padding: 8px 12px 12px">'
            f'{button("Open alpi", "secondary", "sm")}<span style="flex: 1"></span>{notifications}{settings}{quit_}</footer>')


def pop(*parts):
    return popover(NAME_CSS, *parts)


APPROVAL = "wants to run a command"
NEEDS = (
    row("abby", "wants to run git push origin main", "approval · 2m", state="needs", review=True),
    row("doc", "Which lab should I book with?", "question · now", state="needs", review=True),
    row("clonara", APPROVAL, "approval · 6m", state="needs", review=True),
    row("sentinel", "has a question", "question · 9m", state="needs", review=True),
)
LATER = row("scribe", "Blog · post semanal", time="in 2h")
TOMORROW = (row("curator", "Knowledge · nuevos documentos", time="7:00 AM"), row("doc", "Daily brief", time="7:30 AM"))
REVIEW_PRS = row("sentinel", "Review the open pull requests", time="11m", state="working")


def s_next():
    return pop(head("All quiet", "Nothing needs you · next in 2h"), group("Later today", LATER), group("Tomorrow", *TOMORROW), foot())


def s_next_long():
    return pop(head("All quiet", "Nothing needs you · next tomorrow"),
               group("Tomorrow", row("alpi", "Summarize yesterday’s deploys and flag anything that needs a rollback", time="7:30 AM")), foot())


def s_none():
    return pop(head("All quiet", "Nothing needs you, nothing scheduled"), foot())


def s_member():
    return pop(head("All quiet", "Nothing needs you"), foot(bell=False))


def s_online():
    return pop(head("alpi", "online"), foot())


def s_update():
    return pop(head("All quiet", "Nothing needs you, nothing scheduled"), update_banner(), foot())


def s_needs():
    return pop(head("2 need you", "1 approval, 1 question", "needs"), group("Needs you", *NEEDS[:2]), failing_banner(), foot(1))


def s_other():
    rows = (row("sentinel", APPROVAL, "mirai · approval · now", state="needs", review=True),
            row("doc", "Which lab should I book with?", "atlas · question · now", state="needs", review=True))
    return pop(head("2 need you", "1 running", "needs"), group("Needs you", *rows),
               group("Running", row("alpi", "Summarize yesterday’s deploys", "atlas", "&lt;1m", "working")), foot(1))


def s_many():
    return pop(head("7 need you", "5 approvals, 2 questions", "needs"), group("Needs you", *NEEDS, line_row("3 more · Open alpi")), foot(4))


def s_failing():
    return pop(head("3 jobs failing", "Nothing needs you · next in 2h", "failing"), failing_banner(), group("Later today", LATER), group("Tomorrow", *TOMORROW), foot())


def s_running_one():
    return pop(head("Sentinel is working", "Nothing needs you · next in 2h", "running"), group("Running", REVIEW_PRS), group("Later today", LATER), group("Tomorrow", TOMORROW[0]), foot())


def s_running():
    rows = (row("sentinel", "Review the open pull requests", "mirai", "11m", "working"), row("scribe", "Blog · post semanal", "casa", "&lt;1m", "working"))
    return pop(head("2 working", "Nothing needs you · next tomorrow", "running"), group("Running", *rows), group("Tomorrow", *TOMORROW), foot())


def s_needs_running():
    return pop(head("2 need you", "1 running · next in 2h", "needs"), group("Needs you", *NEEDS[:2]), group("Running", REVIEW_PRS),
               group("Later today", LATER), group("Tomorrow", TOMORROW[0]), foot(1))


def s_full():
    return pop(head("3 need you", "2 running", "needs"), group("Needs you", *NEEDS[:3]), counts_section(line_row("Running", "2", "activity")), foot(3))


def s_stopped():
    return pop(head("alpi isn’t running", "It is installed on this computer.", "offline"), start_row(), foot())


def s_unreachable():
    return pop(head("Can’t reach alpi", "Check the connection in alpi.", "offline"), foot())


def s_starting():
    return pop(head("Starting alpi…", "Waiting for the daemon", "starting"), busy_row("Start requested"), foot())


def s_connecting():
    return pop(head("Connecting…", "Waiting for the daemon", "connecting"), foot())


def s_hero():
    return s_needs_running()


def native_item(text, hint="", disabled=False):
    color = INK3 if disabled else INK
    return (f'<div role="menuitem" aria-disabled="{"true" if disabled else "false"}" style="display: flex; align-items: center; gap: 8px; min-height: 32px; padding: 8px 12px; box-sizing: border-box; border-radius: 4px; font-size: 15px; line-height: 16px; color: {color}">'
            f'<span style="flex: 1">{text}</span>{key_hint(hint) if hint else ""}</div>')


def menu_sep():
    return f'<div style="height: 1px; background: {LINE}; margin: 4px 12px"></div>'


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
        look = f"font-size: 14px; font-weight: 500; line-height: 1.45; color: {INK3}" if hd else f"font-size: 14px; line-height: 1.45; color: {INK2}"
        body = "".join(f'<span style="min-width: 0; {look}">{c}</span>' for c in cells)
        return f'<div style="display: grid; grid-template-columns: {tpl}; gap: 12px; padding: 6px 0; border-bottom: 0.5px solid {LINE}; align-items: start">{body}</div>'

    return f'<div style="display: flex; flex-direction: column">{r(head_cells, True)}{"".join(r(x) for x in rows)}</div>'


def intro(title, text):
    return (f'<div style="display: flex; flex-direction: column; gap: 4px"><span style="font-size: 20px; font-weight: 600; letter-spacing: -0.018em">{title}</span>'
            f'<span style="font-size: 15px; color: {INK3}; max-width: 960px; line-height: 1.5">{text}</span></div>')


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
        cell(s_next(), "All quiet, next jobs", "Up to three upcoming jobs of every connection, soonest first, grouped by day: Later today, Tomorrow, then the short weekday. The time sits on the name line, “in 2h” under six hours and the clock otherwise; the summary says when the next one runs.", "next"),
        cell(s_next_long(), "All quiet, long job title", "The job title has the whole second line and truncates with an ellipsis. With one connection the connection name is left out. The default profile leads with Twin and its name in ink.", "next_long"),
        cell(s_none(), "All quiet, nothing scheduled", "An admin with no upcoming job: Twin at rest, no empty box.", "none"),
        cell(s_member(), "All quiet, member", "No scheduled jobs and no bell: a member never sees them, and the summary never claims nothing is scheduled.", "member"),
        cell(s_online(), "Online, no activity verb", "An older daemon without host.activity.list: the heading says only that it is online.", "online"),
        cell(s_update(), "Update ready", "A success tint above the footer with Restart, in every state.", "update")))
    attention = section("Needs you, failing and running", grid3(
        cell(s_needs(), "Needs you", "Twin wears needs. Each row leads with the profile’s 24 px mark and its name in its tone, then the kind and age; Review opens the request. Failing jobs follow as a danger tint.", "needs"),
        cell(s_other(), "Other connections", "Needs you, failing and running read every connected daemon: with more than one, the connection follows the name and Review switches to it.", "other"),
        cell(s_many(), "Many items", "Four rows, then N more opens alpi; the summary counts the kinds.", "many"),
        cell(s_failing(), "Failing jobs", "Twin wears failed. One danger tint over the last 24 h names the profiles and opens alpi; the schedule fills the rest, three rows at most.", "failing"),
        cell(s_running_one(), "One agent working", "Twin wears working; the title names the agent. Only live rows move: running and needs-you marks animate, scheduled ones hold still.", "running_one"),
        cell(s_running(), "Several running", "The title counts; the elapsed time sits on the name line in tabular figures; two scheduled rows beside running.", "running"),
        cell(s_needs_running(), "Needs you with a running turn", "Needs you first, then running, then what is left of the five-row budget, grouped by day.", "needs_running"),
        cell(s_full(), "Full popover", "Needs you fills three rows: running collapses to a count line and the schedule is hidden.", "full")))
    link = section("Daemon states", grid3(
        cell(s_stopped(), "Daemon stopped", "Installed here: Twin offline and Start alpi as the one full-width action.", "stopped"),
        cell(s_unreachable(), "Can’t reach alpi", "A remote daemon: the heading names the problem and the footer stays.", "unreachable"),
        cell(s_starting(), "Starting", "While Start alpi runs: Twin busy.", "starting"),
        cell(s_connecting(), "Connecting", "Activity still loading: Twin busy, and the popover never claims all quiet.", "connecting")))
    rules = section("Rules", col(
        note("The popover never calls the daemon and never reads ~/.alpi: the main window pushes one snapshot, already filtered by connection and profile scope. It follows the app theme (System, Light or Dark) and is 340 wide inside a 342 window, with a 1 px inset edge and no drop shadow, which the transparent window would clip."),
        note("Type: title 20 semibold, summary 14, section labels 14, names 14 in Bricolage 800 toned with nameTone, job 15, meta 12, times 14 tabular in ink-2. Rows are 52 high on the control radius; marks animate only while the popover has focus and never under reduced motion."),
        note("Esc and losing focus hide it. Open alpi and Review show, unminimize and focus the main window; Review carries the deeplink of an approval or a question. The footer bell is hidden for members."),
        per_platform(), gap=10))
    body = (f'{EXTRA_FONTS}<div style="padding: 28px 32px; display: flex; flex-direction: column; gap: 28px; box-sizing: border-box">'
            f'{intro("Tray popover", "A left click on the menu bar icon opens a small popover that triages. Twin at 40 px wears the state and a one-line summary says what the rows do not: then what needs you with Review, failing jobs as a tinted banner, running turns, and the next scheduled jobs grouped by day, within a five-row budget, over every connected daemon (each row names its connection when there are several), an update ready, and Open alpi, notifications, Settings and Quit in the footer. A right click keeps the native menu.")}'
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
        note("One ink with binary alpha: the asset is a template the OS tints for the bar, so it reads on a light, a dark and a translucent bar. It is Twin at half its held turn, its eyes cut out, drawn on the pixel grid of each size, and the marks carry a 1 px knock-out."),
        note("Priority: needs you (ring), then offline (slash), then unread or an update (dot), then quiet. The icon is set once, and only when the state or the size changed."),
        note("Windows and Linux pick the size from the display scale when the state changes: moving the app between displays of different scale keeps the old size until the next state change."), gap=8))
    tips = section("Tooltip", tooltip_table())
    body = (f'<div style="padding: 28px 32px; display: flex; flex-direction: column; gap: 28px; box-sizing: border-box">'
            f'{intro("Tray icon", "Four pixel-exact states generated by scripts/gen_icons.py and read here from the shipped PNGs: quiet, dot, needs you and offline. On macOS the 36 px asset is shown at 18 pt.")}'
            f'{ones}{zoomed}{ladder}{rules}{tips}</div>')
    return page("Desktop · tray icon", 1280, TRAY_ICON_H, body)
