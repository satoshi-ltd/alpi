from __future__ import annotations

import pytest
from textual.widgets import Static

from alpi import outputs as outputs_mod
from alpi.tui.app import AlpiApp
from alpi.tui.screens import OutputDetailPanel


@pytest.mark.asyncio
async def test_a_given_summary_with_brackets_shows_as_written(tui_home) -> None:
    summary = "Paths [/tmp] cleaned; [b]3[/b] hosts on [prod]."
    item = outputs_mod.append(tui_home, profile="default", body="## Detail\n- done", title="Cleanup", summary=summary)
    app = AlpiApp(home_dir=tui_home)
    async with app.run_test(size=(110, 40)) as pilot:
        app._show_panel(OutputDetailPanel(item))
        await pilot.pause()
        texts = [str(widget.render()) for widget in app.query(Static) if type(widget) is Static]
        assert summary in texts


@pytest.mark.asyncio
async def test_a_summary_the_body_opens_with_is_not_repeated(tui_home) -> None:
    lead = "Three replies are waiting on you today."
    item = outputs_mod.append(tui_home, profile="default", body=f"{lead}\n\n## Inbox\n- a", title="Digest", summary=lead)
    app = AlpiApp(home_dir=tui_home)
    async with app.run_test(size=(110, 40)) as pilot:
        app._show_panel(OutputDetailPanel(item))
        await pilot.pause()
        assert lead not in [str(widget.render()) for widget in app.query(Static) if type(widget) is Static]
