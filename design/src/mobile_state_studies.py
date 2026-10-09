from desktop_boards import INK, INK2, INK3, INK4, LINE2, MONO
from gen import DANGER, m_conn_header, m_group, m_row, m_screen_header, page

TITLES = {
    "activity": "Activity · nothing running",
    "notifications": "Notifications · none yet",
    "schedule_empty": "Schedule · no jobs, New schedule",
    "schedule_error": "Schedule · could not load, Retry",
    "roster": "Roster · daemon unreachable",
    "composer": "Composer · offline and paused",
    "undo": "Notifications · deleted, Undo",
}


def frame(inner, h=300):
    return f'<div style="width: 390px; height: {h}px; box-sizing: border-box; border-radius: 12px; border: 0.5px solid {LINE2}; overflow: hidden; background: #ffffff; display: flex; flex-direction: column">{inner}</div>'


def caption(key):
    return f'<span style="font-family: {MONO}; font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase; color: {INK3}">{TITLES[key]}</span>'


def centered(title, hint, retry=False):
    again = f'<span style="display: inline-flex; align-items: center; min-height: 44px; padding: 0 12px; font-weight: 500; font-size: 14px; color: {INK2}">Retry</span>' if retry else ""
    return (f'<div style="flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 6px; padding: 24px; text-align: center">'
            f'<span style="font-weight: 600; font-size: 15px; color: {INK2}">{title}</span><span style="font-size: 14px; line-height: 1.4; color: {INK3}">{hint}</span>{again}</div>')


def activity_empty():
    return frame(m_screen_header("Activity", "ACROSS PROFILES", glyph="") + centered("Nothing running", "Running turns, workgroup phases, schedules and anything waiting on you show up here."))


def notifications_empty():
    return frame(m_screen_header("Notifications", "INBOX ZERO", glyph="") + centered("No notifications yet", "Notifications land here when an agent notifies you or a scheduled job fails."))


def schedule_empty():
    action = (f'<div style="display: flex; margin: 14px 16px 0; align-items: center; justify-content: center; min-height: 44px; border-radius: 4px; background: #141414; color: #ffffff; font-weight: 600; font-size: 14px">New schedule</div>')
    body = f'<div style="padding-top: 16px">{m_group(m_row("No scheduled jobs", "Ask the agent to set one up.", chevron=False, sep=False))}{action}</div>'
    return frame(m_screen_header("scout", "SCHEDULES · 0", glyph="") + body)


def schedule_error():
    card = (f'<div style="flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 10px; padding: 24px; text-align: center">'
            f'<span style="font-weight: 600; font-size: 17px; color: {INK}">Couldn’t load schedule</span>'
            f'<span style="font-family: {MONO}; font-size: 12px; color: {INK3}">Cannot reach the daemon.</span>'
            f'<span style="display: inline-flex; align-items: center; justify-content: center; min-height: 44px; padding: 0 20px; border-radius: 4px; background: rgba(20,20,20,0.06); font-weight: 600; font-size: 14px; color: {INK}">Retry</span></div>')
    return frame(m_screen_header("scout", "SCHEDULES", glyph="") + card)


def roster_down():
    return frame(m_conn_header(ring="#ffffff", collapse=False, bg="#ffffff") + centered("Daemon unreachable", "Profiles and workgroups show up again once the connection is back.", True))


def composer_box(text):
    return (f'<div style="margin: 0 16px; min-height: 56px; border-radius: 4px; background: rgba(20,20,20,0.04); box-shadow: inset 0 0 0 0.5px {LINE2}; display: flex; align-items: center; padding: 0 16px; font-size: 16px; color: {INK4}">{text}</div>')


def composer_states():
    body = (f'<div style="flex: 1; display: flex; flex-direction: column; justify-content: center; gap: 14px">'
            f'{composer_box("Daemon unreachable — sending paused")}{composer_box("Paused — resume to chat")}'
            f'<span style="padding: 0 20px; font-family: {MONO}; font-size: 11px; color: {INK3}">Offline above, a paused profile below; the send button stays off in both.</span></div>')
    return frame(body)


def undo_toast():
    toast = (f'<div style="margin: 0 16px; display: flex; align-items: flex-start; gap: 10px; padding: 14px; box-sizing: border-box; border-radius: 4px; background: #ffffff; border: 0.5px solid {LINE2}">'
             f'<span style="width: 8px; height: 8px; border-radius: 4px; background: {INK3}; flex-shrink: 0; margin-top: 6px"></span>'
             f'<span style="flex: 1; min-width: 0; font-size: 14px; line-height: 20px; color: {INK2}">Deleted 3 notifications</span>'
             f'<span style="min-width: 44px; min-height: 44px; margin: -10px -8px -10px 0; padding: 0 10px; box-sizing: border-box; display: inline-flex; align-items: center; justify-content: center; font-size: 14px; font-weight: 600; color: {INK}">Undo</span></div>')
    return frame(f'<div style="flex: 1; display: flex; flex-direction: column; justify-content: center; gap: 14px">{toast}'
                 f'<span style="padding: 0 20px; font-family: {MONO}; font-size: 11px; color: {INK3}">One toast for the batch; Undo restores every pending row for 5 s.</span></div>')


STATES = (("activity", activity_empty), ("notifications", notifications_empty), ("schedule_empty", schedule_empty), ("schedule_error", schedule_error),
          ("roster", roster_down), ("composer", composer_states), ("undo", undo_toast))
STATES_H = 1141


def phone_states():
    cells = "".join(f'<div style="display: flex; flex-direction: column; gap: 8px">{caption(key)}{draw()}</div>' for key, draw in STATES)
    body = f'<div style="padding: 40px 30px; display: flex; flex-wrap: wrap; gap: 40px 24px; align-items: flex-start">{cells}</div>'
    return page("Phone · empty, error and offline states", 1280, STATES_H, body)
