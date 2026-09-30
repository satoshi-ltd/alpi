from __future__ import annotations

import asyncio
import threading
import time

import pytest

from alpi.tools._approval import Severity
from alpi.tui.app import AlpiApp
from alpi.tui.screens import ApprovalPanel, ClarificationPanel, HelpPanel


def _ask_approval(app: AlpiApp, command: str, results: list) -> threading.Thread:
    t = threading.Thread(
        target=lambda: results.append((command, app._approval_prompt_blocking(command, "rm -r", Severity.CAUTION, "/tmp"))),
        daemon=True,
    )
    t.start()
    return t


async def _wait_for(pilot, cond, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while not cond():
        if time.monotonic() > deadline:
            raise AssertionError("condition not met")
        await pilot.pause(0.02)


@pytest.mark.asyncio
async def test_escape_denies_the_approval_and_unblocks_the_tool_thread(tui_home) -> None:
    app = AlpiApp(home_dir=tui_home)
    results: list = []
    async with app.run_test(size=(110, 40)) as pilot:
        t = _ask_approval(app, "rm -rf build", results)
        await _wait_for(pilot, lambda: app.query(ApprovalPanel))
        await pilot.press("escape")
        await asyncio.to_thread(t.join, 10)
        assert results == [("rm -rf build", "deny")]
        assert app.pending_prompts == []
        await _wait_for(pilot, lambda: not app.query(ApprovalPanel))


@pytest.mark.asyncio
async def test_click_outside_and_other_panels_cannot_dismiss_a_pending_prompt(tui_home) -> None:
    app = AlpiApp(home_dir=tui_home)
    results: list = []
    async with app.run_test(size=(110, 40)) as pilot:
        t = _ask_approval(app, "rm -rf dist", results)
        await _wait_for(pilot, lambda: app.query(ApprovalPanel))
        await pilot.click("#chat", offset=(2, 1))
        app._show_panel(HelpPanel())
        await pilot.pause()
        assert app.query(ApprovalPanel)
        assert not app.query(HelpPanel)
        assert results == []
        panel = app.query_one(ApprovalPanel)
        panel.resolve("once")
        await asyncio.to_thread(t.join, 10)
        assert results == [("rm -rf dist", "once")]


@pytest.mark.asyncio
async def test_concurrent_prompts_queue_behind_the_first(tui_home) -> None:
    app = AlpiApp(home_dir=tui_home)
    results: list = []
    async with app.run_test(size=(110, 40)) as pilot:
        t1 = _ask_approval(app, "first", results)
        await _wait_for(pilot, lambda: len(app.pending_prompts) == 1)
        t2 = _ask_approval(app, "second", results)
        await _wait_for(pilot, lambda: len(app.pending_prompts) == 2)
        shown = list(app.query(ApprovalPanel))
        assert len(shown) == 1 and shown[0]._command == "first"
        assert "(+1 queued)" in shown[0].panel_title
        assert app.status_line.waiting == 2
        await pilot.press("enter")
        await asyncio.to_thread(t1.join, 10)
        await _wait_for(pilot, lambda: [p._command for p in app.query(ApprovalPanel)] == ["second"])
        await pilot.press("escape")
        await asyncio.to_thread(t2.join, 10)
        assert results == [("first", "once"), ("second", "deny")]
        assert app.status_line.waiting == 0


@pytest.mark.asyncio
async def test_countdown_is_shown_and_expiry_auto_denies(tui_home, monkeypatch) -> None:
    monkeypatch.setattr(AlpiApp, "APPROVAL_TIMEOUT_S", 0.6)
    app = AlpiApp(home_dir=tui_home)
    results: list = []
    async with app.run_test(size=(110, 40)) as pilot:
        t = _ask_approval(app, "sleep", results)
        await _wait_for(pilot, lambda: app.query(ApprovalPanel))
        assert "esc deny · auto-deny in 1s" == app.query_one(ApprovalPanel).hint_text()
        await asyncio.to_thread(t.join, 10)
        assert results == [("sleep", "deny")]
        await _wait_for(pilot, lambda: not app.query(ApprovalPanel))


@pytest.mark.asyncio
async def test_escape_cancels_a_clarification_immediately(tui_home) -> None:
    from alpi.host.clarification import CANCEL_SENTINEL

    app = AlpiApp(home_dir=tui_home)
    results: list = []
    async with app.run_test(size=(110, 40)) as pilot:
        t = threading.Thread(target=lambda: results.append(app._clarification_prompt_blocking(
            "Which?", [{"label": "A"}, {"label": "B"}], False, False,
        )), daemon=True)
        t.start()
        await _wait_for(pilot, lambda: app.query(ClarificationPanel))
        assert app.query_one(ClarificationPanel).hint_text().startswith("esc cancel · auto-cancel in 5m")
        await pilot.press("escape")
        await asyncio.to_thread(t.join, 10)
        assert results == [CANCEL_SENTINEL]


@pytest.mark.asyncio
async def test_clarification_choice_reaches_the_tool_thread(tui_home) -> None:
    app = AlpiApp(home_dir=tui_home)
    results: list = []
    async with app.run_test(size=(110, 40)) as pilot:
        t = threading.Thread(target=lambda: results.append(app._clarification_prompt_blocking(
            "Which?", [{"label": "A"}, {"label": "B"}], False, False,
        )), daemon=True)
        t.start()
        await _wait_for(pilot, lambda: app.query(ClarificationPanel))
        await pilot.pause()
        await pilot.press("down", "enter")
        await asyncio.to_thread(t.join, 10)
        assert results == ["B"]


@pytest.mark.asyncio
async def test_quitting_resolves_every_pending_prompt(tui_home) -> None:
    app = AlpiApp(home_dir=tui_home)
    results: list = []
    async with app.run_test(size=(110, 40)) as pilot:
        t1 = _ask_approval(app, "a", results)
        t2 = _ask_approval(app, "b", results)
        await _wait_for(pilot, lambda: len(app.pending_prompts) == 2)
        app._resolve_all_prompts()
        await asyncio.to_thread(t1.join, 10)
        await asyncio.to_thread(t2.join, 10)
    assert sorted(results) == [("a", "deny"), ("b", "deny")]


@pytest.mark.asyncio
async def test_submitting_while_a_prompt_is_open_resolves_it(tui_home, monkeypatch) -> None:
    app = AlpiApp(home_dir=tui_home)
    results: list = []
    async with app.run_test(size=(110, 40)) as pilot:
        t = _ask_approval(app, "rm -rf node_modules", results)
        await _wait_for(pilot, lambda: app.query(ApprovalPanel))
        monkeypatch.setattr(app, "_turn_in_progress", lambda: True)
        monkeypatch.setattr(app, "_kickoff_turn", lambda text: None)
        interrupts: list[str] = []
        monkeypatch.setattr(app.engine, "request_interrupt", lambda reason: interrupts.append(reason))
        app.chat_input.value = "never mind"
        app.chat_input.focus()
        await pilot.press("enter")
        await asyncio.to_thread(t.join, 10)
        assert results == [("rm -rf node_modules", "deny")]
        assert interrupts == ["tui-stop"]
        await _wait_for(pilot, lambda: not app.query(ApprovalPanel))


@pytest.mark.asyncio
async def test_quit_mid_turn_interrupts_the_engine_first(tui_home, monkeypatch) -> None:
    app = AlpiApp(home_dir=tui_home)
    async with app.run_test(size=(110, 40)):
        calls: list[str] = []
        monkeypatch.setattr(app, "_turn_in_progress", lambda: True)
        monkeypatch.setattr(app.engine, "request_interrupt", lambda reason: calls.append(reason))
        monkeypatch.setattr(app, "exit", lambda *a, **k: calls.append("exit"))
        app.action_quit()
        assert calls == ["tui-quit", "exit"]


@pytest.mark.asyncio
async def test_a_prompt_that_expires_while_queued_says_so(tui_home) -> None:
    from alpi.tui.widgets import DimLine

    app = AlpiApp(home_dir=tui_home)
    async with app.run_test(size=(110, 40)) as pilot:
        head = ApprovalPanel("first", "p", "caution", lambda c: None, timeout_s=60)
        queued = ApprovalPanel("second", "p", "caution", lambda c: None, timeout_s=0.1)
        app._enqueue_prompt(head)
        app._enqueue_prompt(queued)
        await pilot.pause()
        assert queued.hint_text() == "esc deny · auto-deny in 1s"
        queued.expire()
        await pilot.pause()
        assert app.pending_prompts == [head]
        notes = [str(w.render()) for w in app.query(DimLine)]
        assert any("approval for `second` timed out while queued" in n for n in notes)
        head.expire()
        await pilot.pause()
        notes = [str(w.render()) for w in app.query(DimLine)]
        assert any("approval for `first` timed out — auto-deny" in n for n in notes)


def test_zero_remaining_is_a_deadline_not_none() -> None:
    panel = ApprovalPanel("x", "p", "caution", lambda c: None, timeout_s=0.0, blocking=False)
    assert panel.deadline is not None
    assert panel.hint_text() == "esc back · expired"
