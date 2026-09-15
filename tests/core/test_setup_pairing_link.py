from __future__ import annotations

import io

from rich.console import Console

from alpi import cli, ui

LINK = (
    "alpi://device?url=ws%3A%2F%2F100.114.140.25%3A49200&name=MacBook-Pro"
    "&pairing_token=ZKqFHPDSdthimwl94OFHyZazXDKhgjday1z9cQRIauc&connection_id=conn_74507b13575f7af6"
)


def test_pairing_link_is_printed_as_one_logical_line_on_a_narrow_console(monkeypatch) -> None:
    buffer = io.StringIO()
    monkeypatch.setattr(ui, "_console", Console(file=buffer, width=60, force_terminal=False))

    cli._print_pairing_link(LINK, "desktop:  ")

    lines = [line for line in buffer.getvalue().splitlines() if line.strip()]
    assert len(lines) == 1
    assert lines[0].endswith(LINK)
