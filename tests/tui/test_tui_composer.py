from __future__ import annotations

import pytest
from textual import events

from alpi.tui.app import AlpiApp
from alpi.tui.screens import HelpPanel
from alpi.tui.widgets import ChatInput, CompletionPopup, UserMessage


def _record_turns(app: AlpiApp, monkeypatch) -> list[str]:
    sent: list[str] = []
    monkeypatch.setattr(app, "_kickoff_turn", lambda text: sent.append(text))
    return sent


@pytest.mark.asyncio
async def test_enter_sends_and_newline_keys_insert_lines(tui_home, monkeypatch) -> None:
    app = AlpiApp(home_dir=tui_home)
    async with app.run_test(size=(110, 40)) as pilot:
        sent = _record_turns(app, monkeypatch)
        await pilot.press(*"one", "shift+enter", *"two", "ctrl+j", *"three\\", "enter", *"four")
        assert app.chat_input.text == "one\ntwo\nthree\nfour"
        await pilot.press("enter")
        await pilot.pause()
        assert sent == ["one\ntwo\nthree\nfour"]
        assert app.chat_input.text == ""
        assert app.query(UserMessage)


@pytest.mark.asyncio
async def test_paste_keeps_newlines(tui_home) -> None:
    app = AlpiApp(home_dir=tui_home)
    async with app.run_test(size=(110, 40)) as pilot:
        app.post_message(events.Paste("line 1\nline 2\n"))
        await pilot.pause()
        assert app.chat_input.text == "line 1\nline 2\n"


@pytest.mark.asyncio
async def test_up_recalls_history_only_when_empty(tui_home, monkeypatch) -> None:
    app = AlpiApp(home_dir=tui_home)
    async with app.run_test(size=(110, 40)) as pilot:
        _record_turns(app, monkeypatch)
        await pilot.press(*"first", "enter", *"second", "enter")
        await pilot.press("up")
        assert app.chat_input.text == "second"
        await pilot.press("up")
        assert app.chat_input.text == "first"
        await pilot.press("down")
        assert app.chat_input.text == "second"
        await pilot.press("down")
        assert app.chat_input.text == ""
        await pilot.press(*"draft", "up")
        assert app.chat_input.text == "draft"


@pytest.mark.asyncio
async def test_escape_stops_the_running_turn(tui_home, monkeypatch) -> None:
    app = AlpiApp(home_dir=tui_home)
    async with app.run_test(size=(110, 40)) as pilot:
        interrupts: list[str] = []
        monkeypatch.setattr(app, "_turn_in_progress", lambda: True)
        monkeypatch.setattr(app.engine, "request_interrupt", lambda reason: interrupts.append(reason))
        await pilot.press("escape")
        assert interrupts == ["tui-stop"]


@pytest.mark.asyncio
async def test_ctrl_c_stops_the_turn_before_it_quits(tui_home, monkeypatch) -> None:
    app = AlpiApp(home_dir=tui_home)
    async with app.run_test(size=(110, 40)) as pilot:
        quits: list[bool] = []
        interrupts: list[str] = []
        monkeypatch.setattr(app, "action_quit", lambda: quits.append(True))
        monkeypatch.setattr(app.engine, "request_interrupt", lambda reason: interrupts.append(reason))
        running = [True]
        monkeypatch.setattr(app, "_turn_in_progress", lambda: running[0])
        await pilot.press("ctrl+c")
        assert interrupts == ["tui-stop"] and quits == []
        running[0] = False
        await pilot.press("ctrl+c")
        assert quits == []
        assert "press ctrl+c again to quit" in app.status_line.hints
        await pilot.press("ctrl+c")
        assert quits == [True]


@pytest.mark.asyncio
async def test_a_single_ctrl_c_expires_after_the_window(tui_home, monkeypatch) -> None:
    app = AlpiApp(home_dir=tui_home)
    async with app.run_test(size=(110, 40)) as pilot:
        quits: list[bool] = []
        monkeypatch.setattr(app, "action_quit", lambda: quits.append(True))
        monkeypatch.setattr(AlpiApp, "QUIT_WINDOW_S", 0.05)
        await pilot.press("ctrl+c")
        await pilot.pause(0.1)
        await pilot.press("ctrl+c")
        assert quits == []


@pytest.mark.asyncio
async def test_completion_popup_lists_commands_with_descriptions(tui_home) -> None:
    app = AlpiApp(home_dir=tui_home)
    async with app.run_test(size=(110, 40)) as pilot:
        await pilot.press(*"/he")
        popup = app.query_one(CompletionPopup)
        assert popup.active
        rows = [str(popup.get_option_at_index(i).prompt) for i in range(popup.option_count)]
        assert any(r.startswith("/help") and "commands and keys" in r for r in rows)
        assert "tab complete" in app.status_line.hints
        await pilot.press("enter")
        await pilot.pause()
        assert app.query(HelpPanel)
        assert app.chat_input.text == ""


@pytest.mark.asyncio
async def test_tab_completes_a_command_that_takes_an_argument(tui_home) -> None:
    app = AlpiApp(home_dir=tui_home)
    async with app.run_test(size=(110, 40)) as pilot:
        await pilot.press(*"/att", "tab")
        assert app.chat_input.text == "/attach "
        assert not app.query_one(CompletionPopup).active
        assert isinstance(app.focused, ChatInput)


@pytest.mark.asyncio
async def test_escape_closes_the_popup_first(tui_home) -> None:
    app = AlpiApp(home_dir=tui_home)
    async with app.run_test(size=(110, 40)) as pilot:
        await pilot.press(*"/s")
        assert app.query_one(CompletionPopup).active
        await pilot.press("escape")
        assert not app.query_one(CompletionPopup).active
        assert app.chat_input.text == "/s"


@pytest.mark.asyncio
async def test_recalled_commands_do_not_open_the_popup(tui_home, monkeypatch) -> None:
    app = AlpiApp(home_dir=tui_home)
    async with app.run_test(size=(110, 40)) as pilot:
        _record_turns(app, monkeypatch)
        await pilot.press(*"hello", "enter", *"/status", "escape", "enter")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("up")
        await pilot.pause()
        assert app.chat_input.text == "/status"
        assert not app.query_one(CompletionPopup).active
        await pilot.press("up")
        await pilot.pause()
        assert app.chat_input.text == "hello"
        app.chat_input.value = ""
        await pilot.press(*"/st")
        await pilot.pause()
        assert app.query_one(CompletionPopup).active


@pytest.mark.asyncio
async def test_enter_on_a_command_with_an_optional_argument_runs_it(tui_home) -> None:
    from alpi.tui.screens import DiffPanel

    app = AlpiApp(home_dir=tui_home)
    async with app.run_test(size=(110, 40)) as pilot:
        await pilot.press(*"/dif", "enter")
        await pilot.pause()
        assert app.query(DiffPanel)


def test_new_line_hints_advertise_keys_that_work_everywhere() -> None:
    from alpi.tui import commands

    keys = " ".join(k for k, _ in commands.KEYS)
    assert "Ctrl+J" in keys and "Alt+Enter" not in keys


@pytest.mark.asyncio
async def test_placeholder_and_hint_name_ctrl_j(tui_home) -> None:
    app = AlpiApp(home_dir=tui_home)
    async with app.run_test(size=(110, 40)) as pilot:
        assert "ctrl+j" in str(app.chat_input.placeholder)
        assert "alt+enter" not in str(app.chat_input.placeholder).lower()
        await pilot.press("x")
        assert "ctrl+j new line" in app.key_hints()
