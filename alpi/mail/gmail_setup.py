"""Interactive setup for the Gmail gateway (OAuth2)."""

from __future__ import annotations

from pathlib import Path

from alpi import ui
from alpi.home import effective_profile_env
from alpi.mail import gmail_auth
from alpi.model_selector import _append_env


def run(home: Path) -> None:
    ui.banner(
        ui.crumb("setup", "gateways", "gmail"),
        subtitle="Gmail REST API (OAuth2)",
        home=home,
    )

    ui.dim(
        "You need an OAuth Desktop client from Google Cloud. ~5 min:\n"
        "\n"
        "  1. https://console.cloud.google.com → new project → enable 'Gmail API'.\n"
        "  2. OAuth consent screen → External → fill wizard → leave in Testing.\n"
        "  3. Create OAuth client → Desktop app → copy Client ID + Secret.\n"
        "  4. Audience → add your Gmail as Test user (else consent blocks).\n"
        "\n"
        "On 'Authorize now' Google will warn it's unverified and ask for two\n"
        "scopes (send + read/modify). Accept both — without them the token\n"
        "has no Gmail access.\n"
    )
    ui._console.print("")

    env = effective_profile_env(home)
    current_cid = env.get("GMAIL_CLIENT_ID", "")
    current_csec = env.get("GMAIL_CLIENT_SECRET", "")
    current_senders = env.get("GMAIL_ALLOWED_SENDERS", "")

    client_id = ui.text("OAuth Client ID", default=current_cid)
    if not client_id:
        return ui.cancelled()

    client_secret = ui.password("OAuth Client Secret", current=current_csec)
    if not client_secret:
        return ui.cancelled()

    senders_raw = ui.text(
        "Allowed senders (comma-separated, empty = no inbound)",
        default=current_senders,
    )
    senders = ",".join(
        s.strip().lower() for s in (senders_raw or "").split(",") if s.strip()
    )

    env = home / ".env"
    for key, val in (
        ("GMAIL_CLIENT_ID", client_id),
        ("GMAIL_CLIENT_SECRET", client_secret),
        ("GMAIL_ALLOWED_SENDERS", senders),
    ):
        _append_env(env, key, val)

    if not ui.confirm("Authorize now via browser?", default=True):
        ui.ok_and_wait("credentials saved. Run this wizard again to authorize.")
        return

    try:
        token = gmail_auth.first_run(home)
    except gmail_auth.GmailAuthError as e:
        ui.fail_and_wait(str(e))
        return

    ui._console.print("")
    ui.ok(f"authorized as {token.email}")
    ui.saved(env)
    from alpi.mail.pgp_setup import maybe_offer
    maybe_offer(home)
    ui.press_enter()
