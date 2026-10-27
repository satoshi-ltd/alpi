import onboarding_studies as ob
from first_run_parts import (q_first_profile, HOVER, INK, INK2, INK3, LINE, PANE, SELECTED, Z_PHONE, alp, col, dbtn, dfield, dwin, grid, line, mono,
                             scaled, shot, sidebar_chip, stage, head, t, zoomed)
from conversation_boards import m_composer
from gen import m_button, m_conn_header, m_empty_state, m_shell_footer


def ph(inner, z=Z_PHONE, h=844):
    return scaled(f'<div style="width: 390px; height: {h}px; display: flex; flex-direction: column; background: {PANE}">{inner}</div>', 390, h, z)


def hero_btn(label, kind="primary"):
    return m_button(label, kind, "hero").replace("border-radius: 4px", "border-radius: 4px; width: 100%", 1)


def w_model():
    fields = col(
        line(dfield("Provider", 176, 40, False), dfield("API key", 176, 40), gap=8, extra="width: 360px"),
        dbtn("Continue", "primary", 40, 360), dbtn("Later, in Settings", "ghost", 32), gap=8, align="center", extra="margin-top: 24px")
    return dwin(stage(head("Choose a model", "alpi needs one provider to answer. The key stays on this computer.", 64), fields))


def w_ready():
    roster = (f'<div style="padding: 8px 12px; display: flex; flex-direction: column; gap: 4px">{line(alp(16), t("alpi", 13, INK, 500), gap=8, extra=f"height: 32px; padding: 0 8px; border-radius: 4px; background: {SELECTED}")}</div>')
    side = sidebar_chip("online", roster)
    composer = (f'<div style="padding: 0 32px 16px; display: flex; flex-direction: column; gap: 8px; align-items: center">'
                f'{line(dfield("Message alpi…", 456, 40, True, True), gap=0)}{mono("Use it from your phone · Settings → Connections", 11, INK3)}</div>')
    body = stage(alp(48), t("alpi is ready", 22, INK, 600, "margin-top: 16px; letter-spacing: -0.012em"), t("Ask anything. A session starts with your first message.", 13, INK3, 400, "margin-top: 4px")) + composer
    return dwin(body, side=side)


def desktop_c_now():
    return col(
        shot("alpi answered", "A one-time card on top, an empty chat with a gray line, the model left to Settings.", zoomed(ob.d_running())), gap=24)


def desktop_c_proposed():
    return col(
        shot("Choose a model", "The one thing alpi needs before it can answer, asked at the moment it matters, on the same stage.", w_model()),
        shot("Ready", "The chat opens with the composer focused. The phone hint becomes one mono line under it, with no card to dismiss.", w_ready()),
        gap=20)


def phone_empty(inner, bottom=""):
    return (f'<div style="height: 100%; display: flex; flex-direction: column">{m_conn_header(ring="#ffffff", collapse=False, bg="#ffffff")}<div style="height: 0.5px; background: {LINE}"></div>'
            f'<div style="flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; padding: 0 24px; gap: 8px">{inner}</div>'
            f'{m_shell_footer(ring="#ffffff", border=True)}</div>')


def e_roster_new():
    return phone_empty(alp(64) + t("Create your first profile", 22, INK, 600, "letter-spacing: -0.018em; margin-top: 16px")
                       + t("A profile is an agent with its own memory and tools.", 14, INK3, 400, "line-height: 1.5; max-width: 296px")
                       + f'<div style="margin-top: 16px; width: 100%">{hero_btn("New profile")}</div>')


def e_member_new():
    return phone_empty(alp(64) + t("Nothing shared yet", 22, INK, 600, "letter-spacing: -0.018em; margin-top: 16px")
                       + t("Ask the host admin to share a profile with this device.", 14, INK3, 400, "line-height: 1.5; max-width: 296px")
                       + f'<span style="margin-top: 8px; padding: 6px 12px; border-radius: 4px; background: {HOVER}">{mono("This device: pixel-7", 12, INK2)}</span>')


def e_chat_now():
    from gen import m_chat_header
    return (f'<div style="height: 100%; display: flex; flex-direction: column">{m_chat_header("doc", "#3899e2", "")}'
            f'{m_empty_state("No sessions yet", "A session starts with your first message.")}{m_composer(name="doc")}</div>')


def e_chat_new():
    from gen import m_chat_header
    return (f'<div style="height: 100%; display: flex; flex-direction: column">{m_chat_header("doc", "#3899e2", "")}'
            f'<div style="flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; padding: 0 24px; gap: 8px">'
            f'{t("Say hello to doc", 22, INK, 600, "letter-spacing: -0.018em")}{t("A session starts with your first message.", 14, INK3, 400)}</div>{m_composer(name="doc")}</div>')


def mobile_c_now():
    return grid(
        shot("Roster, no profiles", "Shipped: the mark, the sentence and New profile as the one primary.", ph(q_first_profile("admin"))),
        shot("Roster, nothing shared", "Shipped: the role line in mono, no action; the device name is not shown.", ph(q_first_profile("member"))),
        shot("First chat", "Gray line, no hint of what to type.", ph(e_chat_now())),
    )


def mobile_c_proposed():
    return grid(
        shot("Roster, no profiles", "Alpaca 64, one sentence, New profile 56 pt.", ph(e_roster_new())),
        shot("Roster, nothing shared", "The device name to quote to the admin, one tap to copy.", ph(e_member_new())),
        shot("First chat", "Composer focused; the profile is named.", ph(e_chat_new())),
    )


PROPOSALS_H = [
    {
        "id": "UX.46",
        "client": "mobile · desktop",
        "area": "Empty states after onboarding",
        "title": "Every first empty screen says what to do next",
        "why": "After pairing or starting, the first screens are gray lines: the desktop chat says a session starts with the first message and leaves the model to Settings, the phone roster says Create one to begin without a button, a member sees plain text with no device name, and the first chat gives no hint. Recommendation: each empty state is a mark, one sentence and the one action that ends it: choose a model, say hello, create a profile, copy the device name.",
        "mobile": (mobile_c_now, mobile_c_proposed),
        "desktop": (desktop_c_now, desktop_c_proposed),
        "accept": "With no provider the desktop shows Choose a model on the Welcome stage before the first chat and Later, in Settings leaves it; the ready chat focuses the composer and replaces the dismissible card by one mono line. The phone roster with no profiles shows the alpaca at 64 pt, one sentence and New profile (admin only); a member sees the device name as a copyable chip; the first chat names the profile and focuses the composer. Every state is a component with a test that fails without it.",
        "h": 2520,
    },
]
