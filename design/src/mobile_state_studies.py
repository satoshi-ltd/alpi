from conversation_boards import m_composer
from desktop_boards import INK3, LINE2, MONO
from gen import m_banner, m_conn_header, m_empty_state, m_roster, m_screen_header, m_toast, page

TITLES = {
    "activity": "Activity · nothing running",
    "notifications": "Notifications · none yet",
    "schedule_empty": "Schedule · no jobs, New schedule",
    "schedule_error": "Schedule · could not load, Retry",
    "roster": "Roster · daemon unreachable",
    "roster_rows": "Roster · rows kept, glyphs unfolded",
    "composer": "Composer · offline and paused",
    "undo": "Notifications · deleted, Undo",
    "error": "Toast · error, Retry and Dismiss",
}


def frame(inner, h=300):
    return f'<div style="width: 390px; height: {h}px; box-sizing: border-box; border-radius: 12px; border: 0.5px solid {LINE2}; overflow: hidden; background: #ffffff; display: flex; flex-direction: column">{inner}</div>'


def caption(key):
    return f'<span style="font-family: {MONO}; font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase; color: {INK3}">{TITLES[key]}</span>'


def activity_empty():
    return frame(m_screen_header("Activity", "ACROSS PROFILES", glyph="") + m_empty_state("Nothing running", "Running turns, workgroup phases, schedules and anything waiting on you show up here."))


def notifications_empty():
    return frame(m_screen_header("Notifications", "INBOX ZERO", glyph="") + m_empty_state("No notifications yet", "Notifications land here when an agent notifies you or a scheduled job fails."))


def schedule_empty():
    return frame(m_screen_header("scout", "SCHEDULES · 0", glyph="") + m_empty_state("No scheduled jobs", "Ask the agent to set one up.", "New schedule"))


def schedule_error():
    return frame(m_screen_header("scout", "SCHEDULES", glyph="") + m_empty_state("Couldn’t load schedule", "Cannot reach the daemon.", "Retry"))


def roster_down():
    banner = m_banner("Daemon unreachable. Reconnecting…", "Retry", "danger", secondary="Manage")
    return frame(m_conn_header(ring="#ffffff", collapse=False, bg="#ffffff", status="offline") + banner + m_empty_state("Daemon unreachable", "Profiles and workgroups show up again once the connection is back.", "Retry"), 360)


def roster_rows_down():
    banner = m_banner("Daemon unreachable. Reconnecting…", "Retry", "danger", secondary="Manage")
    return frame(m_conn_header(ring="#ffffff", collapse=False, bg="#ffffff", status="offline") + banner + f'<div style="flex: 1; min-height: 0; overflow: hidden">{m_roster(compact=False, offline=True)}</div>', 560)


def composer_states():
    body = (f'<div style="flex: 1; display: flex; flex-direction: column; justify-content: center">'
            f'{m_composer(state="offline")}{m_composer(state="paused", resume=True)}'
            f'<span style="padding: 12px 20px 0; font-family: {MONO}; font-size: 11px; color: {INK3}">Offline above, a paused profile below; only the controls dim and the send button stays off in both.</span></div>')
    return frame(body, 360)


def undo_toast():
    return frame(f'<div style="position: relative; flex: 1"><span style="position: absolute; left: 20px; right: 20px; top: 16px; font-family: {MONO}; font-size: 11px; color: {INK3}">One toast for the batch, anchored above the bottom edge; Undo restores every pending row for 5 s.</span>'
                 f'{m_toast("Deleted 3 notifications", action="Undo", bottom=40)}</div>')


def error_toast():
    return frame(f'<div style="position: relative; flex: 1"><span style="position: absolute; left: 20px; right: 20px; top: 16px; font-family: {MONO}; font-size: 11px; color: {INK3}">An error lasts 6 s; with Retry it stays until dismissed. The message wraps to two lines and Dismiss is a 44 pt target.</span>'
                 f'{m_toast("Couldn’t save: the daemon refused the request for this device.", kind="danger", retry=True, dismiss=True, bottom=40)}</div>', 300)


STATES = (("activity", activity_empty), ("notifications", notifications_empty), ("schedule_empty", schedule_empty), ("schedule_error", schedule_error),
          ("roster", roster_down), ("roster_rows", roster_rows_down), ("composer", composer_states), ("undo", undo_toast), ("error", error_toast))
STATES_H = 1460


def phone_states():
    cells = "".join(f'<div style="display: flex; flex-direction: column; gap: 8px">{caption(key)}{draw()}</div>' for key, draw in STATES)
    body = f'<div style="padding: 40px 30px; display: flex; flex-wrap: wrap; gap: 40px 24px; align-items: flex-start">{cells}</div>'
    return page("Phone · empty, error and offline states", 1280, STATES_H, body)
