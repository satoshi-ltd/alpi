"""Interactive setup for the email platform (IMAP + SMTP)."""

from __future__ import annotations

import os
from pathlib import Path

from alpi import ui
from alpi.email.client import (
    DEFAULT_IMAP_PORT, DEFAULT_SMTP_PORT, EmailClient, EmailError,
)
from alpi.model_selector import _append_env


def run(home: Path) -> None:
    ui.banner(
        ui.crumb("setup", "gateways", "email"),
        subtitle="IMAP + SMTP",
        home=home,
    )

    current_addr = os.environ.get("EMAIL_ADDRESS", "")
    current_pw = os.environ.get("EMAIL_PASSWORD", "")
    current_imap = os.environ.get("EMAIL_IMAP_HOST", "")
    current_smtp = os.environ.get("EMAIL_SMTP_HOST", "")
    current_imap_port = os.environ.get("EMAIL_IMAP_PORT") or str(DEFAULT_IMAP_PORT)
    current_smtp_port = os.environ.get("EMAIL_SMTP_PORT") or str(DEFAULT_SMTP_PORT)
    current_senders = os.environ.get("EMAIL_ALLOWED_SENDERS", "")

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
    # trigger alf from inbound".
    senders_raw = ui.text(
        "Allowed senders (comma-separated, empty = no inbound):",
        default=current_senders,
    )
    senders = ",".join(
        s.strip().lower() for s in (senders_raw or "").split(",") if s.strip()
    )

    client = EmailClient(
        address=address, password=password,
        imap_host=imap_host, smtp_host=smtp_host,
        imap_port=imap_port, smtp_port=smtp_port,
    )
    try:
        with ui.activity("Testing IMAP + SMTP connections…"):
            client.test()
    except EmailError as e:
        ui.fail(str(e))
        ui.warn("Credentials look wrong or the server is unreachable. Not saving anything.")
        ui.press_enter()
        return

    env = home / ".env"
    writes: list[tuple[str, str]] = [
        ("EMAIL_ADDRESS", address),
        ("EMAIL_PASSWORD", password),
        ("EMAIL_IMAP_HOST", imap_host),
        ("EMAIL_SMTP_HOST", smtp_host),
        ("EMAIL_ALLOWED_SENDERS", senders),
    ]
    if imap_port != DEFAULT_IMAP_PORT:
        writes.append(("EMAIL_IMAP_PORT", str(imap_port)))
    if smtp_port != DEFAULT_SMTP_PORT:
        writes.append(("EMAIL_SMTP_PORT", str(smtp_port)))
    for key, val in writes:
        _append_env(env, key, val)
        os.environ[key] = val

    ui.saved(env)
    ui.press_enter()
