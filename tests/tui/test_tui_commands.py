from __future__ import annotations

import pytest
from click.testing import CliRunner

from alpi.tui import commands
from alpi.tui.app import AlpiApp
from alpi.tui.screens import HelpPanel
from alpi.tui.widgets import DimLine, ErrorLine


def test_every_command_has_a_handler_and_a_summary() -> None:
    names = [c.name for c in commands.COMMANDS]
    assert len(names) == len(set(names))
    for c in commands.COMMANDS:
        assert callable(getattr(AlpiApp, c.method, None)), c.method
        assert c.summary


def test_registry_covers_the_commands_help_used_to_miss() -> None:
    names = {c.name for c in commands.COMMANDS}
    assert {"runs", "quit", "activity", "clear", "new", "help"} <= names
    assert commands.lookup("exit") is commands.lookup("quit")
    assert "fresh session" in commands.lookup("clear").summary


def test_complete_matches_names_and_aliases() -> None:
    assert [c.name for c in commands.complete("/cl")] == ["clear", "clear-attachments"]
    assert [c.name for c in commands.complete("/ex")] == ["quit"]
    assert commands.parse("/diff  7d ") == ("diff", "7d")


@pytest.mark.parametrize("argv", [["--help"], ["chat", "--help"]])
def test_cli_help_has_no_rst_literals(argv) -> None:
    from alpi.cli import main

    result = CliRunner().invoke(main, argv)
    assert result.exit_code == 0
    assert "``" not in result.output
    assert '--once "text"' in result.output


@pytest.mark.asyncio
async def test_help_panel_is_built_from_the_registry(tui_home) -> None:
    from textual.widgets import OptionList

    app = AlpiApp(home_dir=tui_home)
    async with app.run_test(size=(120, 50)) as pilot:
        app._handle_slash("/help")
        await pilot.pause()
        options = app.query_one(HelpPanel).query_one("#help-commands", OptionList)
        ids = [options.get_option_at_index(i).id for i in range(options.option_count)]
        assert ids == [c.name for c in commands.COMMANDS]


@pytest.mark.asyncio
async def test_clear_starts_a_fresh_session_and_exit_quits(tui_home, monkeypatch) -> None:
    app = AlpiApp(home_dir=tui_home)
    async with app.run_test(size=(120, 50)) as pilot:
        before = app.engine.session.id
        await pilot.press(*"/clear", "escape", "enter")
        await pilot.pause()
        assert app.engine.session.id != before
        assert any("new session" in str(w.render()) for w in app.query(DimLine))
        quits: list[bool] = []
        monkeypatch.setattr(app, "action_quit", lambda: quits.append(True))
        app._handle_slash("/exit")
        assert quits == [True]
        app._handle_slash("/nope")
        await pilot.pause()
        assert any("/help lists them" in str(w.render()) for w in app.query(ErrorLine))


@pytest.mark.asyncio
@pytest.mark.parametrize("command", ["/clear", "/new", "ctrl+l"])
async def test_session_resets_wait_for_the_running_turn(tui_home, monkeypatch, command) -> None:
    app = AlpiApp(home_dir=tui_home)
    async with app.run_test(size=(120, 50)) as pilot:
        before = app.engine.session.id
        monkeypatch.setattr(app, "_turn_in_progress", lambda: True)
        if command == "ctrl+l":
            await pilot.press("ctrl+l")
        else:
            app._handle_slash(command)
        await pilot.pause()
        assert app.engine.session.id == before
        assert any("turn in progress" in str(w.render()) for w in app.query(DimLine))


@pytest.mark.asyncio
@pytest.mark.parametrize("command", ["/clear", "/new"])
async def test_session_resets_repoint_session_search(tui_home, command) -> None:
    from alpi.tools import session_search

    app = AlpiApp(home_dir=tui_home)
    async with app.run_test(size=(120, 50)) as pilot:
        app._handle_slash(command)
        await pilot.pause()
        assert session_search._CURRENT_SESSION_ID == app.engine.session.id


@pytest.mark.asyncio
async def test_shape_command_shows_and_sets_the_pair(tui_profile_home) -> None:
    from alpi import config
    from alpi.tui.app import AlpiApp
    from alpi.tui.widgets import DimLine

    app = AlpiApp(home_dir=tui_profile_home)
    async with app.run_test(size=(120, 40)) as pilot:
        app._cmd_shape("")
        await pilot.pause()
        shown = " ".join(str(w.render()) for w in app.query(DimLine))
        assert "amber round" in shown and "shapes:" in shown
        app._cmd_shape("bell blue")
        await pilot.pause()
        assert config.load(tui_profile_home).tui["shape"] == "bell"
        assert config.load(tui_profile_home).tui["accent"] == "#3899e2"
        app._cmd_shape("pencil")
        await pilot.pause()
        assert config.load(tui_profile_home).tui["shape"] == "bell"
        assert "pencil" in " ".join(str(w.render()) for w in app.query(DimLine))
        app._cmd_shape("shield")
        await pilot.pause()
        assert config.load(tui_profile_home).tui["shape"] == "bell"
        assert "'shield' is neither" in " ".join(str(w.render()) for w in app.query(DimLine))


@pytest.mark.asyncio
async def test_shape_recolours_the_running_console(tui_profile_home) -> None:
    from alpi.tui.app import AlpiApp

    app = AlpiApp(home_dir=tui_profile_home)
    async with app.run_test(size=(120, 40)) as pilot:
        app._cmd_shape("bell blue")
        await pilot.pause()
        assert app.current_theme.accent == "#3899e2"
        assert app.get_css_variables()["accent"].lower() == "#3899e2"


@pytest.mark.asyncio
async def test_shape_keeps_a_session_only_model_switch(tui_profile_home) -> None:
    from alpi import config
    from alpi.tui.app import AlpiApp

    app = AlpiApp(home_dir=tui_profile_home)
    async with app.run_test(size=(120, 40)) as pilot:
        app.cfg.model = "openai/session-only"
        app.engine.cfg = app.cfg
        app._cmd_shape("heart")
        await pilot.pause()
        assert app.engine.cfg is app.cfg and app.cfg.model == "openai/session-only"
        assert app.cfg.tui["shape"] == "heart"
        assert config.load(tui_profile_home).tui["shape"] == "heart"
        assert config.load(tui_profile_home).model != "openai/session-only"
        app._cmd_shape(",")
        await pilot.pause()
        assert app.cfg.tui["shape"] == "heart"


@pytest.mark.asyncio
async def test_shape_on_the_default_profile_explains_twin_and_writes_nothing(tui_home) -> None:
    from alpi import config
    from alpi.tui.app import AlpiApp
    from alpi.tui.widgets import DimLine

    app = AlpiApp(home_dir=tui_home)
    async with app.run_test(size=(120, 40)) as pilot:
        app._cmd_shape("")
        await pilot.pause()
        shown = " ".join(str(w.render()) for w in app.query(DimLine))
        assert "twin (brand mark)" in shown and "shapes:" not in shown and "alpaca" not in shown
        app._cmd_shape("bell blue")
        await pilot.pause()
        assert "brand mark" in " ".join(str(w.render()) for w in app.query(DimLine))
        assert "shape" not in config.load(tui_home).tui and "fold" not in config.load(tui_home).tui
        assert config.load(tui_home).tui["accent"] == "#f0b447"


@pytest.mark.asyncio
async def test_shape_refreshes_the_marker_without_a_restart(tui_profile_home) -> None:
    from alpi import fold_art
    from alpi.tui import list_row
    from alpi.tui.app import AlpiApp

    app = AlpiApp(home_dir=tui_profile_home)
    async with app.run_test(size=(120, 40)) as pilot:
        app._fold_art = True
        app._cmd_shape("heart")
        await pilot.pause()
        assert app._fold_marker == fold_art.GLYPHS["heart"]
        assert list_row._marker == fold_art.GLYPHS["heart"]
        app._fold_art = False
        app._cmd_shape("pebble")
        await pilot.pause()
        assert app._fold_marker == fold_art.FALLBACK_GLYPH
