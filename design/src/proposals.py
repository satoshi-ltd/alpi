from gen import m_button, m_screen_header, page
from desktop_boards import INK, INK3, LINE2
from conversation_boards import h1, label, mono, spec
from notif_studies import VIEW, a_panel, phone_triage

PAGE_W = 1280
COLUMN_PAD = 20


def drawing(title, inner):
    return f'<div style="flex: 1; min-width: 0; display: flex; flex-direction: column">{spec(title, inner, pad=COLUMN_PAD)}</div>'


def cap(text):
    return mono(text, 11, INK3)


def stack(*items, gap=14):
    return f'<div style="display: flex; flex-direction: column; gap: {gap}px">{"".join(items)}</div>'


def tagged(title, inner):
    return stack(cap(title), inner, gap=8)


def phone_frame(inner):
    return f'<div style="width: 390px; max-width: 100%; border-radius: 12px; border: 0.5px solid {LINE2}; overflow: hidden; background: #ffffff">{inner}</div>'


DELETED = ("Security: billing-api P1", "Security: web-app P0", "Security: auth-gateway P1", "Security: search-index P2", "Security: rates-sync P1",
           "Security: mail-relay P0", "Security: export-worker P2", "Security: image-proxy P1", "Security: crm-bridge P1")


def toast_dot(color, top=0):
    return f'<span style="width: 8px; height: 8px; border-radius: 4px; background: {color}; flex-shrink: 0; margin-top: {top}px"></span>'


def d_toast(message, action="", dot=VIEW["ink3"]):
    tail = (f'<span style="width: 1px; height: 14px; background: {VIEW["line2"]}; margin: 0 2px; flex-shrink: 0"></span>'
            f'<span style="padding: 2px 10px; border-radius: 4px; font-size: 12px; font-weight: 500; color: {VIEW["ink"]}; flex-shrink: 0">{action}</span>') if action else ""
    pad = "6px 8px 6px 14px" if action else "8px 16px 8px 14px"
    return (f'<div style="display: inline-flex; align-items: center; gap: 10px; padding: {pad}; max-width: 100%; box-sizing: border-box; border-radius: 4px; '
            f'background: {VIEW["elev"]}; box-shadow: 0 0 0 0.5px {VIEW["line2"]}; font-size: 13px; line-height: 18px; color: {VIEW["ink2"]}; white-space: nowrap">'
            f'{toast_dot(dot)}<span style="overflow: hidden; text-overflow: ellipsis">{message}</span>{tail}</div>')


def hug(inner):
    return f'<div style="display: flex">{inner}</div>'


def inbox_with_toasts(toasts, h):
    pile = (f'<div style="position: absolute; right: 22px; bottom: 22px; left: 22px; display: flex; flex-direction: column-reverse; align-items: flex-end; gap: 8px">'
            f'{"".join(toasts)}</div>')
    return f'<div style="position: relative">{a_panel(VIEW, h)}{pile}</div>'


def toast_stack_now():
    toasts = [d_toast(f"Deleted “{title}”", "Undo") for title in DELETED]
    return stack(
        tagged("Nine ⌫ presses in the inbox · one toast each, newest on top", inbox_with_toasts(toasts, 470)),
        cap("Every pill has its own Undo and its own 5 s; the stack has no cap and climbs over the list, the reader and the composer behind the modal."),
        cap("Hover pauses a pill but not its delete: Undo after the 5 s can only say “Already deleted”."),
    )


def toast_stack_proposed():
    toasts = [d_toast("Copied"), d_toast("Deleted 9 notifications", "Undo")]
    steps = stack(
        tagged("First delete · names the row", hug(d_toast("Deleted “Security: billing-api P1”", "Undo"))),
        tagged("Another inside the window · the same toast counts", hug(d_toast("Deleted 2 notifications", "Undo"))),
        gap=12,
    )
    return stack(
        tagged("Nine ⌫ presses · one toast for the batch, at most three on screen", inbox_with_toasts(toasts, 470)),
        steps,
        cap("Each delete restarts one 5 s window for the batch; Undo brings all nine back; hover pauses the toast and the deletes together. A fourth toast retires the oldest."),
    )


def m_toast(message, action="", faded=False):
    tail = (f'<span style="min-width: 44px; min-height: 44px; margin: -10px -8px -10px 0; padding: 0 10px; box-sizing: border-box; display: inline-flex; align-items: center; justify-content: center; '
            f'font-size: 14px; font-weight: 600; color: {VIEW["ink"]}; flex-shrink: 0">{action}</span>') if action else ""
    return (f'<div style="display: flex; align-items: flex-start; gap: 10px; padding: 14px; box-sizing: border-box; border-radius: 4px; background: {VIEW["pane"]}; '
            f'border: 0.5px solid {VIEW["line2"]}; opacity: {0.45 if faded else 1}">{toast_dot(VIEW["ink3"], 6)}'
            f'<span style="flex: 1; min-width: 0; font-size: 14px; line-height: 20px; color: {VIEW["ink2"]}">{message}</span>{tail}</div>')


def phone_with_toast(toast, h=420):
    screen = (f'<div style="height: {h}px; display: flex; flex-direction: column; overflow: hidden; background: {VIEW["pane"]}">'
              f'{m_screen_header("Notifications", "2 UNREAD", glyph="", right=m_button("Mark all read", "ghost", "md"))}{phone_triage(VIEW)}</div>')
    return phone_frame(f'<div style="position: relative">{screen}<div style="position: absolute; top: 16px; left: 16px; right: 16px">{toast}</div></div>')


def toast_undo_now():
    swipes = stack(
        tagged("Swipe 1 · replaced by swipe 2, its Undo gone", m_toast("Deleted “Security: billing-api P1”", "Undo", faded=True)),
        tagged("Swipe 2 · replaced by swipe 3, its Undo gone", m_toast("Deleted “Security: web-app P0”", "Undo", faded=True)),
        gap=10,
    )
    return stack(
        tagged("Swipe 3 · the only toast left", phone_with_toast(m_toast("Deleted “Security: auth-gateway P1”", "Undo"))),
        swipes,
        cap("One toast at a time: each delete replaces it, so only the last can be undone and the first two go through after 5 s anyway."),
    )


def toast_undo_proposed():
    return stack(
        tagged("Three swipes · one toast for the batch", phone_with_toast(m_toast("Deleted 3 notifications", "Undo"))),
        tagged("First swipe · names the row", m_toast("Deleted “Security: billing-api P1”", "Undo")),
        cap("Each swipe restarts one 5 s window; Undo brings back all three; the copy matches desktop."),
    )


PROPOSALS = [
    {
        "id": "UI-TOAST.STACK",
        "client": "desktop",
        "area": "Toasts · Notifications inbox delete and Undo",
        "title": "A run of deletes is one toast that counts, and the stack stops at three",
        "why": "Every delete in the Notifications inbox raises its own toast with its own Undo (NotificationsModal.jsx onDeleteRow), and the toast stack appends without a cap, bottom-right and growing upwards (Notification.jsx, Notification.module.css), so ten ⌫ presses leave ten pills over the inbox and the composer. The toast pauses on hover but its 5 s delete in useDeleteOutput does not, so a late Undo can only answer “Already deleted”. Recommendation: deletes inside the undo window join one toast that counts them, with one Undo for all, and never more than three toasts on screen. Mobile replaces instead of stacking and loses the earlier Undo: board UI-MOB.TOAST-UNDO.",
        "now": toast_stack_now,
        "proposed": toast_stack_proposed,
        "accept": "Deleting several notifications within the undo window shows one toast: the first names the row as today, the next ones turn it into “Deleted N notifications”. Each delete restarts one 5 s window for the batch, Undo brings every pending row back, and the rows are deleted together when the window ends; hovering the toast pauses the window, so Undo never shows a row the daemon already removed. At most three toasts are on screen and a fourth retires the oldest. A test presses ⌫ ten times and finds one toast, then ten rows back after Undo and no delete sent.",
        "h": 1130,
    },
    {
        "id": "UI-MOB.TOAST-UNDO",
        "client": "mobile",
        "area": "Toasts · Notifications delete and Undo",
        "title": "A run of deletes keeps one Undo for all of them",
        "why": "The phone shows one toast at a time and each delete replaces it (Toast.jsx show, app/outputs.jsx onDelete), so after three quick swipes only the last can be undone while the first two still go through when their own 5 s run out. It does not pile up like desktop (board UI-TOAST.STACK), but the earlier Undo disappears without a word. Recommendation: the same batch as desktop, one counting toast whose Undo restores every pending row.",
        "now": toast_undo_now,
        "proposed": toast_undo_proposed,
        "accept": "Deleting several notifications within the undo window, from the list or the reader, keeps one toast: the first names the row, the next ones read “Deleted N notifications”. Each delete restarts one 5 s window for the batch, Undo restores every pending row, and the rows are deleted together when it ends. The Undo target stays 44 pt and the copy matches desktop. A test deletes three rows, presses Undo once and finds all three back and no delete sent.",
        "h": 1050,
    },
]





def proposal_board(p):
    kicker = " · ".join((p["id"], p["client"], p["area"]))
    head = f'<div style="display: flex; flex-direction: column; gap: 10px">{label(kicker)}{h1(p["title"], p["why"])}</div>'
    drawings = f'<div style="display: flex; gap: 24px; align-items: stretch">{drawing("Now", p["now"]())}{drawing("Proposed", p["proposed"]())}</div>'
    accept = (f'<div style="display: flex; flex-direction: column; gap: 6px">{label("Accept")}'
              f'<p style="margin: 0; max-width: 1080px; font-size: 13px; line-height: 1.55; color: {INK}">{p["accept"]}</p></div>')
    body = (f'<div data-proposal="{p["id"]}" style="padding: 40px 48px; display: flex; flex-direction: column; gap: 26px; box-sizing: border-box">'
            f'{head}{drawings}{accept}</div>')
    return page("Proposal " + p["id"], PAGE_W, p["h"], body)


def board_name(p):
    return "Proposals-" + p["id"] + ".dc.html"


PROPOSAL_BOARDS = [(board_name(p), (lambda p=p: proposal_board(p)), p["h"], p["id"] + " · " + p["title"]) for p in PROPOSALS]
