"""Interactive setup for one IMAP + SMTP email account."""

from __future__ import annotations

from pathlib import Path

from alpi import ui
from alpi.mail import accounts as accounts_mod
from alpi.mail.imap import (
    DEFAULT_IMAP_PORT, DEFAULT_SMTP_PORT, ImapClient, ImapError,
)


def run(home: Path) -> None:
    ui.banner(
        ui.crumb("setup", "email", "imap"),
        subtitle="IMAP + SMTP",
        home=home,
    )

    ui.dim(
        "You need your IMAP + SMTP hostnames and an app password (NOT\n"
        "your login — 2FA providers require a generated one). Defaults\n"
        "are 993 (IMAP SSL) + 587 (SMTP STARTTLS).\n"
    )
    ui._console.print("")

    address = ui.text("Email address:")
    if not address:
        return ui.cancelled()

    password = ui.password("Password (or app password):")
    if not password:
        return ui.cancelled()

    imap_host = ui.text("IMAP host (e.g. imap.yourprovider.com):")
    if not imap_host:
        return ui.cancelled()

    imap_port_raw = ui.text("IMAP port:", default=str(DEFAULT_IMAP_PORT))
    imap_port = int(imap_port_raw) if imap_port_raw else DEFAULT_IMAP_PORT

    smtp_host = ui.text("SMTP host (e.g. smtp.yourprovider.com):")
    if not smtp_host:
        return ui.cancelled()

    smtp_port_raw = ui.text("SMTP port:", default=str(DEFAULT_SMTP_PORT))
    smtp_port = int(smtp_port_raw) if smtp_port_raw else DEFAULT_SMTP_PORT

    client = ImapClient(
        address=address, password=password,
        imap_host=imap_host, smtp_host=smtp_host,
        imap_port=imap_port, smtp_port=smtp_port,
    )
    try:
        with ui.activity("Testing IMAP + SMTP connections…"):
            client.test()
    except ImapError as e:
        ui._console.print("")
        ui.fail(str(e))
        ui.warn("Credentials look wrong or the server is unreachable. Not saving anything.")
        ui.press_enter()
        return

    account_id = accounts_mod.add_imap(
        home,
        address=address,
        password=password,
        imap_host=imap_host,
        smtp_host=smtp_host,
        imap_port=imap_port,
        smtp_port=smtp_port,
    )
    ui.ok(f"saved account {account_id}")
    from alpi.mail.pgp_setup import maybe_offer
    maybe_offer(home)
    ui.press_enter()
