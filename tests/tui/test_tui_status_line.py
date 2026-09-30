from __future__ import annotations

import pytest

from alpi import outputs
from alpi.tui.app import AlpiApp
from alpi.tui.screens import HelpPanel


@pytest.mark.asyncio
async def test_status_line_carries_model_ctx_sandbox_unread_and_waiting(tui_home, monkeypatch) -> None:
    outputs.append(tui_home, profile="default", body="one")
    outputs.append(tui_home, profile="default", body="two")
    app = AlpiApp(home_dir=tui_home)
    async with app.run_test(size=(160, 40)) as pilot:
        monkeypatch.setattr(app, "_resolve_ctx_window", lambda model: 100_000)
        app.engine.session.model = "openrouter/acme/model-x"
        app.engine.session.last_ctx_tokens = 12_000
        app.cfg.tools.terminal.sandbox = True
        app.cfg.tools.terminal.allow_network = False
        app._remote_waiting = 1
        app._update_header()
        await pilot.pause()
        plain = app.status_line.plain
        assert "openrouter/acme/model-x" in plain
        assert "ctx 12% of 100K" in plain
        assert "sandbox · offline" in plain
        assert "2 unread" in plain
        assert "1 waiting on you" in plain
        assert "/ commands" in plain


@pytest.mark.asyncio
async def test_key_hints_follow_the_context(tui_home, monkeypatch) -> None:
    app = AlpiApp(home_dir=tui_home)
    async with app.run_test(size=(160, 40)) as pilot:
        assert app.key_hints().startswith("/ commands")
        await pilot.press(*"hi")
        assert app.key_hints().startswith("enter send")
        app._show_panel(HelpPanel())
        await pilot.pause()
        assert "esc close" in app.key_hints()
        app._dismiss_panels()
        await pilot.pause()
        monkeypatch.setattr(app, "_turn_in_progress", lambda: True)
        assert app.key_hints().startswith("esc stop")


@pytest.mark.asyncio
async def test_narrow_status_line_drops_hints_before_state(tui_home) -> None:
    app = AlpiApp(home_dir=tui_home)
    async with app.run_test(size=(50, 30)) as pilot:
        app.engine.session.model = "provider/some-model"
        app._update_header()
        await pilot.pause()
        rendered = str(app.status_line.render())
        assert "some-model" in rendered
        assert "/ commands" not in rendered
