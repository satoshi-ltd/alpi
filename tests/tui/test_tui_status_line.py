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


@pytest.mark.asyncio
async def test_waiting_prompts_use_the_warning_text_not_the_accent(tui_home) -> None:
    from textual.color import Color

    from alpi.tui import themes

    app = AlpiApp(home_dir=tui_home)
    async with app.run_test(size=(160, 40)) as pilot:
        app._remote_waiting = 1
        app._update_header()
        await pilot.pause()
        text = app.status_line.left_text()
        start = text.plain.index("1 waiting on you")
        (span,) = [s for s in text.spans if s.start <= start < s.end]
        colour = Color.parse(str(span.style).split()[-1])

        def near(hex_: str) -> bool:
            return sum(abs(x - y) for x, y in zip(colour.rgb, Color.parse(hex_).rgb)) <= 6

        assert near(themes.DARK["warningText"])
        assert not near(themes.DARK["accent"])


@pytest.mark.asyncio
async def test_status_line_and_list_rows_wear_the_profile_glyph_on_a_truecolor_terminal(
    tui_profile_home, monkeypatch,
) -> None:
    from alpi import config, fold_art
    from alpi.tui import list_row

    cfg = config.load(tui_profile_home)
    cfg.tui = {"fold": "rocket", "accent": "#2cb3b5"}
    config.save(cfg)
    monkeypatch.setattr(list_row, "_marker", "◆")
    monkeypatch.setattr(fold_art, "supports_fold_art", lambda *a, **k: True)
    app = AlpiApp(home_dir=tui_profile_home)
    async with app.run_test(size=(160, 40)) as pilot:
        await pilot.pause()
        assert app.status_line.plain.startswith(f"{fold_art.glyph('rocket')} ")
        row = list_row.row_text("m", "", width=4, active=True, accent="#2cb3b5")
        assert row.plain.startswith(f"{fold_art.glyph('rocket')} ")


@pytest.mark.asyncio
async def test_status_line_keeps_the_diamond_without_truecolor(tui_profile_home, monkeypatch) -> None:
    from alpi import fold_art
    from alpi.tui import list_row

    monkeypatch.setattr(list_row, "_marker", "◆")
    monkeypatch.setattr(fold_art, "supports_fold_art", lambda *a, **k: False)
    app = AlpiApp(home_dir=tui_profile_home)
    async with app.run_test(size=(160, 40)) as pilot:
        await pilot.pause()
        assert app.status_line.plain.startswith("◆ ")
        assert list_row.row_text("m", "", width=4, active=True, accent="#fff").plain.startswith("◆ ")
