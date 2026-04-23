"""Interactive setup for the IMAP gateway + SMTP outbound."""

from __future__ import annotations

import os
from pathlib import Path

from alpi import ui
from alpi.mail.imap import (
    DEFAULT_IMAP_PORT, DEFAULT_SMTP_PORT, ImapClient, ImapError,
)
from alpi.model_selector import _append_env


def run(home: Path) -> None:
    ui.banner(
        ui.crumb("setup", "gateways", "imap"),
        subtitle="IMAP + SMTP",
        home=home,
    )

    current_addr = os.environ.get("IMAP_ADDRESS", "")
    current_pw = os.environ.get("IMAP_PASSWORD", "")
    current_imap = os.environ.get("IMAP_HOST", "")
    current_smtp = os.environ.get("SMTP_HOST", "")
    current_imap_port = os.environ.get("IMAP_PORT") or str(DEFAULT_IMAP_PORT)
    current_smtp_port = os.environ.get("SMTP_PORT") or str(DEFAULT_SMTP_PORT)
    current_senders = os.environ.get("IMAP_ALLOWED_SENDERS", "")

    if not current_addr:
        ui.dim(
            "You need your IMAP + SMTP hostnames and an app password (NOT\n"
            "your login — 2FA providers require a generated one). Defaults\n"
            "are 993 (IMAP SSL) + 587 (SMTP STARTTLS).\n"
            "\n"
            "The allowlist is fail-closed: unlisted senders are ignored.\n"
        )
        ui._console.print("")

    address = ui.text("Email address:", default=current_addr)
    if not address:
        return ui.cancelled()

    password = ui.password("Password (or app password):", current=current_pw)
    if not password:
        return ui.cancelled()

    imap_host = ui.text("IMAP host (e.g. imap.yourprovider.com):", default=current_imap)
    if not imap_host:
        return ui.cancelled()

    imap_port_raw = ui.text("IMAP port:", default=current_imap_port)
    imap_port = int(imap_port_raw) if imap_port_raw else DEFAULT_IMAP_PORT

    smtp_host = ui.text("SMTP host (e.g. smtp.yourprovider.com):", default=current_smtp)
    if not smtp_host:
        return ui.cancelled()

    smtp_port_raw = ui.text("SMTP port:", default=current_smtp_port)
    smtp_port = int(smtp_port_raw) if smtp_port_raw else DEFAULT_SMTP_PORT

    # Allowlist controls the INBOUND gateway only — outbound
    # (send_message, schedule delivery, email tool) works regardless.
    # Empty is a valid choice: "use email for outbound, never
    # trigger alpi from inbound".
    senders_raw = ui.text(
        "Allowed senders (comma-separated, empty = no inbound):",
        default=current_senders,
    )
    senders = ",".join(
        s.strip().lower() for s in (senders_raw or "").split(",") if s.strip()
    )

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

    env = home / ".env"
    writes: list[tuple[str, str]] = [
        ("IMAP_ADDRESS", address),
        ("IMAP_PASSWORD", password),
        ("IMAP_HOST", imap_host),
        ("SMTP_HOST", smtp_host),
        ("IMAP_ALLOWED_SENDERS", senders),
    ]
    if imap_port != DEFAULT_IMAP_PORT:
        writes.append(("IMAP_PORT", str(imap_port)))
    if smtp_port != DEFAULT_SMTP_PORT:
        writes.append(("SMTP_PORT", str(smtp_port)))
    for key, val in writes:
        _append_env(env, key, val)
        os.environ[key] = val

    ui.saved_and_wait(env)
