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


@pytest.mark.asyncio
async def test_a_chart_block_shows_as_text_bars(tui_home) -> None:
    from textual.widgets import Markdown

    body = 'Locales.\n\n```chart\n{"type": "bar", "x": ["es-ES", "en-GB"], "series": [{"values": [863, 509]}]}\n```'
    item = outputs_mod.append(tui_home, profile="default", body=body, title="Daily")
    app = AlpiApp(home_dir=tui_home)
    async with app.run_test(size=(110, 40)) as pilot:
        app._show_panel(OutputDetailPanel(item))
        await pilot.pause()
        source = app.query_one(OutputDetailPanel).query_one(Markdown).source
        assert "es-ES  ████" in source and '"series"' not in source


@pytest.mark.asyncio
async def test_an_assistant_reply_draws_its_chart_as_text(tui_home) -> None:
    from textual.widgets import Markdown

    from alpi.tui.widgets import AssistantMessage

    reply = 'Trend.\n\n```chart\n{"type": "line", "x": ["Mon", "Tue", "Wed"], "series": [{"values": [3, 1, 4]}]}\n```'
    app = AlpiApp(home_dir=tui_home)
    async with app.run_test(size=(110, 40)) as pilot:
        message = AssistantMessage()
        await app.screen.mount(message)
        message.replace(reply)
        await pilot.pause()
        await pilot.pause()
        source = message.query_one(Markdown).source
        assert "▆▁█  3 → 4" in source and '"series"' not in source


@pytest.mark.asyncio
async def test_a_resumed_reply_draws_its_chart_as_text(tui_home) -> None:
    from textual.widgets import Markdown

    from alpi.tui.widgets import AssistantMessage

    reply = 'Trend.\n\n```chart\n{"type": "line", "x": ["Mon", "Tue", "Wed"], "series": [{"values": [3, 1, 4]}]}\n```'
    app = AlpiApp(home_dir=tui_home)
    async with app.run_test(size=(110, 40)) as pilot:
        message = AssistantMessage(reply)
        await app.screen.mount(message)
        await pilot.pause()
        assert "▆▁█  3 → 4" in message.query_one(Markdown).source
