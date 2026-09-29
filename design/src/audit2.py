from gen import ALPI_ACCENT, DANGER, DOC_ACCENT, mix, page
from desktop_boards import HOVER, INK, INK2, INK3, LINE, MONO

BUGS = [
    (1, "desktop", "⌘A inside Manage sessions selects every session, even while typing in the DELETE field or a rename.", "ManageSessionsModal.jsx:191", "fixed 0.6.6"),
    (2, "desktop", "The current choice is never highlighted: rows receive `selected`, Dropdown.Row reads `active`.", "ReasoningEffortField.jsx:33 · ProviderPickerForm.jsx:155, 249", "fixed 0.6.6"),
    (3, "desktop", "The pair-device Sessions select has no styles: its class exists in no CSS file.", "devices.jsx:608", "fixed 0.6.6"),
    (4, "desktop", "Sidebar “Archive workgroup” only shows a toast; nothing is archived.", "Sidebar.jsx:405", "fixed 0.6.6"),
    (5, "mobile", "Settings sheets say “saved” after a failed save: saveField swallows the error and resolves.", "profile/[id]/settings.jsx:205", "fixed 0.5.4"),
    (6, "mobile", "The notification primer never shows “Not now”: Sheet drops the footer when primaryAction is set, so any dismiss is a permanent decline.", "Sheet.jsx:138 · NotificationPrimer.jsx:30", "fixed 0.5.4"),
    (7, "mobile", "A switch stays flipped when the RPC fails or the confirm is cancelled.", "Toggle.jsx:10 · connections/[id].jsx:181", "fixed 0.5.4"),
    (8, "mobile", "Approval and Clarification mount outside PaneShell and render full-width on the fold and tablets.", "_layout.jsx:123", "fixed 0.5.4"),
    (9, "both", "A thread that fails to load shows an endless skeleton on desktop and a false “start a thread” on mobile.", "session-open.js:133 · chat/[id].jsx:252", "open"),
    (10, "desktop", "“Remove” inside the MCP detail dialog opened its confirm as an anchored popover that the dialog body clipped, so nothing seemed to happen.", "McpField.jsx:142 · ConfirmDelete.jsx:27", "fixed 0.6.7"),
    (11, "desktop", "Cold start on a remote connection could leave the roster empty: a failed first round trip fell back to a cache that a full store had never written, and nothing retried while online.", "useHostConnections.js:216", "fixed 0.6.8"),
]

OVERLAYS = [
    (1, "Select-like controls", "Five looks: raw &lt;select&gt; at 38 px in the system font, an unstyled native select, Selectish (mono 32), the Dropdown field (sans 32) and .ds-seg.", "Seven selected-state styles: PickerRow dot, radio, pill, role card, member chip, “in link” pill, swatch ring.", "One Dropdown field on desktop; PickerRow with one selected style on mobile.", "both", "desktop done 0.6.6 · mobile partial 0.5.4"),
    (2, "Confirm dialogs", "ConfirmDelete types on 6 of 20 uses and closes before the async delete finishes, with no busy state.", "TypedConfirm is always typed and red on 19 sites, including update, restart, role and scope.", "Typed and red only for irreversible deletes; a neutral confirm elsewhere; busy state on both.", "both", "done 0.6.6 / 0.5.4"),
    (3, "Footers", "DialogFooter on 8 of 15 modals; hand-made footers in Email, MCP, Pairing, Approval, Clarification; 28 px buttons next to 32 px ones.", "Sheet has a primary bar but no Cancel pattern, and the footer slot disappears under a primary action.", "DialogFooter everywhere with a leading slot for Remove; Sheet takes [secondary, primary].", "both", "done 0.6.6 / 0.5.4"),
    (4, "Dismiss as an action", "Backdrop click closes every form modal with no dirty guard; a stray click kills a live pairing code.", "Backdrop or swipe means Deny, cancel the question, cancel the pairing, or decline notifications for good.", "Non-dismissible Approval, Clarification, Pairing and Primer; dirty guard on the Create dialogs.", "both", "mobile done 0.5.4"),
    (5, "Menus", "Only Dropdown and ContextMenu have arrow keys and role=menu; HeaderMenu, Sessions, Tasks, Voice and Model pickers have neither.", "ActionSheet closes before the action runs and shows no selected mark when used as a picker.", "Shared menu navigation on Popover menus; a selected mark in ActionSheet pickers.", "both", "done 0.6.6 / 0.5.4"),
    (6, "Esc, focus, keyboard", "Manage sessions, Approval and Clarification ignore Esc and have no focus trap.", "TypedConfirm has no autoFocus or keyboard avoidance; the Clarification body does not scroll.", "Register on useOverlay; autoFocus and keyboard height on the confirm cards; ScrollView in Clarification.", "both", "done 0.6.6 / 0.5.4"),
    (7, "Wide layouts", "n/a", "Sheets stay bottom-anchored as 560 cards, confirm cards centre at 420, toasts stretch to 808, the bottom inset is counted twice.", "Centre sheets as dialogs on two panes; cap the toast width; count the inset once.", "mobile", "done 0.5.4"),
    (8, "Budget editor", "BudgetEdit (Selectish, Cancel + Save) for profiles vs BudgetEditor (Edit button, Save only) for workgroups.", "BudgetSheet cannot clear a cap; EditBudgetSheet sends the value unvalidated.", "One editor per client that validates and can clear.", "both", "mobile done 0.5.4"),
    (9, "Text inputs", "Raw 40 px &lt;input&gt;s in Create profile and the provider form vs the 32 px Field in Create workgroup.", "Field has no error prop, so validation only reaches a toast.", "Field everywhere on desktop; an error prop on the mobile Field.", "both", "mobile done 0.5.4"),
]

STATES = [
    (1, "Thread fails to load", "toast, then an endless skeleton", "a false “start a thread with …”", "inline error card with Retry", "both", "done 0.6.9 / 0.5.5"),
    (2, "Composer while offline", "“daemon offline — sending paused”", "“Paused — resume to chat”", "split offline from paused on mobile", "mobile", "done 0.5.5"),
    (3, "Empty roster", "blank nav; the EmptyState primitive is unused", "copy, but it claims “no profiles” while the daemon is unreachable", "EmptyState with a New profile action; offline-aware copy", "both", "done 0.6.9 / 0.5.5"),
    (4, "Workgroup thread", "blank while loading; raw error string in a red box", "skeleton; the error hides behind “no posts yet”", "skeleton and an error card with Retry on both", "both", "done 0.6.9 / 0.5.5"),
    (5, "Connections", "no zero state; stuck on “Loading connections…” after an error; no refresh", "“No paired apps yet” and pull-to-refresh; the error is never shown", "error with Retry, a zero state and a refresh button on desktop; the error on mobile", "both", "done 0.6.9 / 0.5.5"),
    (6, "Notifications", "“Inbox zero” while still syncing; unreachable daemons are dropped silently", "spinner while loading; unreachable copy with pull to retry", "hide the empty state while loading; unreachable copy on desktop", "desktop", "partial 0.6.9"),
    (7, "Failed loads shown as “none”", "email, storage, workgroup members", "email, memory, MCP, skills, tools, connections, usage", "an inline error row with Retry", "both", "done 0.6.9 / 0.5.5 (email, memory)"),
    (8, "Empty copy", "lowercase “none” / “nothing yet”", "sentence case with a hint", "one voice on both: sentence case with a hint", "both", "proposed"),
    (9, "Crash screen", "root ErrorBoundary: “Something broke on screen”, Reload", "none", "expo-router ErrorBoundary with the desktop copy", "mobile", "done 0.5.5"),
    (10, "Refresh", "no refresh in settings, connections, workgroups or sessions; onSettingsRefresh is unwired", "a failed pull is silent; MCP, skills, tools, schedule and email cannot refresh; the chat toast says “pull to refresh”", "refresh buttons on desktop lists; pull-to-refresh with a failure toast on mobile", "both", "done 0.6.9 / 0.5.5"),
]

PLAN = [
    ("desktop 0.6.6 ✓", "Overlays", "Bugs 1–4 · every select becomes a Dropdown field · DialogFooter on every modal · Esc and focus on Sessions, Approval, Clarification · keyboard navigation on Popover menus · ConfirmDelete waits for the delete."),
    ("mobile 0.5.4 ✓", "Overlays", "Bugs 5–8 · non-dismissible Approval, Clarification, Pairing, Primer · neutral confirm for reversible actions · Field error prop and budget validation · busy state on every primary · one selected style · centred dialogs on two panes."),
    ("desktop 0.6.9 ✓", "View states", "Thread error card · EmptyState in the sidebar, workgroups and connections · error rows with Retry instead of “none” · refresh buttons · offline banner in settings · notifications hide “Inbox zero” while syncing."),
    ("mobile 0.5.5 ✓", "View states", "Transcript error instead of the empty thread · offline composer copy · offline-aware roster · ErrorBoundary · pull-to-refresh everywhere with a failure toast · jump to latest."),
]


def audit2_board():
    tone = {"mobile": (mix(DOC_ACCENT, 0.16), "#2a5f80"), "desktop": (mix(ALPI_ACCENT, 0.18), ALPI_ACCENT), "both": (mix("#9d4dc6", 0.16), "#6b2f8f")}
    tag = lambda who: f'<span style="display: inline-flex; align-items: center; height: 18px; padding: 0 8px; border-radius: 16px; background: {tone[who][0]}; color: {tone[who][1]}; font-family: {MONO}; font-size: 11px; white-space: nowrap">fix {who}</span>'
    status = lambda t: f'<span style="font-family: {MONO}; font-size: 11px; color: {"#217a45" if "done" in t or "fixed" in t else INK3}; white-space: nowrap">{t}</span>'
    badge = lambda n: f'<span style="width: 22px; height: 22px; border-radius: 999px; background: {DANGER}; color: #ffffff; font: 600 12px/22px Geist, sans-serif; text-align: center; flex-shrink: 0">{n}</span>'
    head = lambda cols, tpl: f'<div style="display: grid; grid-template-columns: {tpl}; gap: 14px; padding: 0 0 8px; font-family: {MONO}; font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase; color: {INK3}">{"".join(f"<span>{c}</span>" for c in cols)}</div>'
    cell = lambda t, c=INK2, w=400: f'<span style="font-size: 12px; line-height: 1.5; color: {c}; font-weight: {w}">{t}</span>'
    h2 = lambda t, sub: f'<div style="display: flex; flex-direction: column; gap: 4px; margin-top: 36px"><span style="font-size: 18px; font-weight: 600; letter-spacing: -0.01em">{t}</span><span style="font-size: 13px; color: {INK3}; line-height: 1.5; max-width: 900px">{sub}</span></div>'

    bugs = head(("", "", "bug", "where", "status"), "22px 96px 1fr 300px 90px") + "".join(
        f'<div style="display: grid; grid-template-columns: 22px 96px 1fr 300px 90px; gap: 14px; align-items: start; padding: 10px 0; border-top: 0.5px solid {LINE}">{badge(n)}{tag(who)}{cell(text, INK, 500)}{cell(where, INK3)}{status(st)}</div>'
        for n, who, text, where, st in BUGS)
    overlays = head(("", "topic", "desktop", "mobile", "direction", "", "status"), "22px 130px 1fr 1fr 1fr 96px 90px") + "".join(
        f'<div style="display: grid; grid-template-columns: 22px 130px 1fr 1fr 1fr 96px 90px; gap: 14px; align-items: start; padding: 10px 0; border-top: 0.5px solid {LINE}">{badge(n)}{cell(topic, INK, 600)}{cell(d)}{cell(m)}{cell(v, INK)}{tag(who)}{status(st)}</div>'
        for n, topic, d, m, v, who, st in OVERLAYS)
    states = head(("", "view", "desktop", "mobile", "direction", "", "status"), "22px 130px 1fr 1fr 1fr 96px 90px") + "".join(
        f'<div style="display: grid; grid-template-columns: 22px 130px 1fr 1fr 1fr 96px 90px; gap: 14px; align-items: start; padding: 10px 0; border-top: 0.5px solid {LINE}">{badge(n)}{cell(view, INK, 600)}{cell(d)}{cell(m)}{cell(v, INK)}{tag(who)}{status(st)}</div>'
        for n, view, d, m, v, who, st in STATES)
    plan = "".join(
        f'<div style="display: grid; grid-template-columns: 130px 110px 1fr; gap: 14px; align-items: start; padding: 10px 0; border-top: 0.5px solid {LINE}">{cell(ver, INK, 600)}{cell(kind, INK3)}{cell(text)}</div>'
        for ver, kind, text in PLAN)

    body = f"""<div style="padding: 40px 48px; display: flex; flex-direction: column; gap: 8px; height: 100%; box-sizing: border-box; overflow: hidden">
<span style="font-family: {MONO}; font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase; color: {INK3}">Round 2 · 2026-09-29</span>
<span style="font-size: 30px; font-weight: 600; letter-spacing: -0.02em; line-height: 1.15">Overlays and view states</span>
<span style="font-size: 13px; line-height: 1.5; color: {INK3}; max-width: 900px">Three read-only audits over desktop 0.6.5 and mobile 0.5.3: modals and dropdowns, sheets and pickers, and the empty / loading / error / offline states of every view. The status column tracks what each cycle shipped; desktop 0.6.6 and mobile 0.5.4 closed the overlay rows; 0.6.7 and 0.6.8 are hotfixes the creator reported on the way; desktop 0.6.9 and mobile 0.5.5 closed the view-state rows; the empty-copy voice (row 8) is the one item still open. Badges on the overlay artboards point at the overlay rows.</span>
{h2("Bugs, verified in the code", "Each one reproduces from the lines cited; none needs a device to confirm.")}
{bugs}
{h2("Overlays: desktop against mobile", "Where the same interaction is built two ways, and the one way to keep.")}
{overlays}
{h2("View states", "What each view shows when there is nothing, when it is loading, when the load failed and when the daemon is unreachable.")}
{states}
{h2("Proposed cycles", "Four releases, two per client, in this order. Each one runs the usual loop: implement, emulator, adversarial review, commit and push.")}
{plan}
</div>"""
    return page("Round 2 · overlays and view states", 1280, 2900, body)
