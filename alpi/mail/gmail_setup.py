"""Interactive setup for one Gmail account (OAuth2)."""

from __future__ import annotations

import os
from pathlib import Path

from alpi import ui
from alpi.home import effective_profile_env
from alpi.mail import accounts as accounts_mod
from alpi.mail import gmail_auth
from alpi.model_selector import _append_env


def run(home: Path) -> None:
    ui.banner(
        ui.crumb("setup", "email", "gmail"),
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
        "The Client ID + Secret are SHARED across every Gmail account on this\n"
        "profile — one Google app. On 'Authorize now' Google warns it's\n"
        "unverified and asks for two scopes (send + read/modify). Accept both.\n"
    )
    ui._console.print("")

    env = effective_profile_env(home)
    current_cid = env.get("GMAIL_CLIENT_ID", "")
    current_csec = env.get("GMAIL_CLIENT_SECRET", "")

    address = ui.text("Gmail address:")
    if not address:
        return ui.cancelled()

    client_id = ui.text("OAuth Client ID", default=current_cid)
    if not client_id:
        return ui.cancelled()

    client_secret = ui.password("OAuth Client Secret", current=current_csec)
    if not client_secret:
        return ui.cancelled()

    env_path = home / ".env"
    for key, val in (
        ("GMAIL_CLIENT_ID", client_id),
        ("GMAIL_CLIENT_SECRET", client_secret),
    ):
        _append_env(env_path, key, val)

    account_id = accounts_mod.slug(address)
    accounts_mod.add_gmail(home, address=address)

    if not ui.confirm("Authorize now via browser?", default=True):
        ui.ok_and_wait("credentials saved. Run this wizard again to authorize.")
        return

    headless = os.environ.get("ALPI_HEADLESS", "").strip() not in ("", "0", "false", "no")
    runner = gmail_auth.first_run_paste if headless else gmail_auth.first_run
    try:
        token = runner(home, account_id)
    except gmail_auth.GmailAuthError as e:
        ui.fail_and_wait(str(e))
        return

    ui._console.print("")
    ui.ok(f"authorized as {token.email}")
    from alpi.mail.pgp_setup import maybe_offer
    maybe_offer(home)
    ui.press_enter()
