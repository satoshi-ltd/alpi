"""Interactive setup for the email tool (IMAP + SMTP).

Generic — no provider-specific branches. Asks the user for address,
password, hosts, ports. Tests the connection at the end so they know
the creds work before leaving the wizard. Everything lands in
``~/.alf/.env`` under the ``EMAIL_*`` prefix — same source of truth
as ``TELEGRAM_*``.
"""

from __future__ import annotations

import os
from pathlib import Path

import questionary
from rich.console import Console

from alf.email.client import DEFAULT_IMAP_PORT, DEFAULT_SMTP_PORT, EmailClient, EmailError
from alf.model_selector import _append_env, _ask

_console = Console()


def run(home: Path) -> None:
    _console.print("[b]Email setup[/b]  [dim](IMAP + SMTP)[/dim]")
    _console.print(
        "[dim]Alf speaks plain IMAP (read) and SMTP (send). Any mailbox "
        "that supports both works — Gmail, Outlook, iCloud, Fastmail, "
        "self-hosted, etc. You'll need the hosts + credentials from "
        "your provider.\n"
        "Existing values show as defaults — press ENTER to keep them.[/dim]\n"
    )

    current_addr = os.environ.get("EMAIL_ADDRESS", "")
    current_pw = os.environ.get("EMAIL_PASSWORD", "")
    current_imap = os.environ.get("EMAIL_IMAP_HOST", "")
    current_smtp = os.environ.get("EMAIL_SMTP_HOST", "")
    current_imap_port = os.environ.get("EMAIL_IMAP_PORT") or str(DEFAULT_IMAP_PORT)
    current_smtp_port = os.environ.get("EMAIL_SMTP_PORT") or str(DEFAULT_SMTP_PORT)

    address = _ask(questionary.text(
        "Email address:", default=current_addr,
    ))
    if not address:
        return _cancelled()

    if current_pw:
        _console.print(
            f"[dim]Current password ends in …{current_pw[-4:]}  "
            f"(press ENTER to keep, or paste a new one)[/dim]"
        )
        password = _ask(questionary.password("Password (or app password):")) or current_pw
    else:
        password = _ask(questionary.password("Password (or app password):"))
    if not password:
        return _cancelled()

    imap_host = _ask(questionary.text(
        "IMAP host (e.g. imap.yourprovider.com):",
        default=current_imap,
    ))
    if not imap_host:
        return _cancelled()

    imap_port_raw = _ask(questionary.text(
        f"IMAP port:", default=current_imap_port,
    ))
    imap_port = int(imap_port_raw) if imap_port_raw else DEFAULT_IMAP_PORT

    smtp_host = _ask(questionary.text(
        "SMTP host (e.g. smtp.yourprovider.com):",
        default=current_smtp,
    ))
    if not smtp_host:
        return _cancelled()

    smtp_port_raw = _ask(questionary.text(
        f"SMTP port:", default=current_smtp_port,
    ))
    smtp_port = int(smtp_port_raw) if smtp_port_raw else DEFAULT_SMTP_PORT

    _console.print("\n[dim]Testing IMAP + SMTP connections…[/dim]")
    client = EmailClient(
        address=address, password=password,
        imap_host=imap_host, smtp_host=smtp_host,
        imap_port=imap_port, smtp_port=smtp_port,
    )
    try:
        client.test()
    except EmailError as e:
        _console.print(f"[red]✗[/red] {e}")
        _console.print(
            "[yellow]Credentials look wrong or the server is unreachable. "
            "Not saving anything.[/yellow]"
        )
        return

    env = home / ".env"
    writes: list[tuple[str, str]] = [
        ("EMAIL_ADDRESS", address),
        ("EMAIL_PASSWORD", password),
        ("EMAIL_IMAP_HOST", imap_host),
        ("EMAIL_SMTP_HOST", smtp_host),
    ]
    if imap_port != DEFAULT_IMAP_PORT:
        writes.append(("EMAIL_IMAP_PORT", str(imap_port)))
    if smtp_port != DEFAULT_SMTP_PORT:
        writes.append(("EMAIL_SMTP_PORT", str(smtp_port)))
    for key, val in writes:
        _append_env(env, key, val)
        # Also propagate to the live process so the setup menu's status
        # line (which reads os.environ) reflects the new state right
        # after the wizard returns — not only on the next alf launch.
        os.environ[key] = val

    _console.print(f"[green]✓[/green] saved to [dim]{env}[/dim]")
    _console.print(
        "[dim]Inside alf, try:[/dim] "
        "[b]\"list my 5 most recent unread emails\"[/b]"
    )


def _cancelled() -> None:
    _console.print("[yellow]cancelled[/yellow]")
