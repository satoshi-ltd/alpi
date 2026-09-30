from __future__ import annotations

import time

import pytest

from alpi.engine import AgentEvent
from alpi.session import ToolLog, Turn
from alpi.tool_hints import tool_family
from alpi.tui.app import AlpiApp, EngineEvent, _LiveTurn
from alpi.tui.turns import consolidate_reasoning, thought_label, turn_parts
from alpi.tui.widgets import (
    AskUserLine, AssistantMessage, ReasoningBlock, StepsGroup, ThinkingIndicator, ToolCard, UserMessage,
)


def _feed(app: AlpiApp, *events: AgentEvent) -> None:
    for ev in events:
        app.on_engine_event(EngineEvent(ev))


def _start_turn(app: AlpiApp, seconds_ago: float = 0.0) -> None:
    app._turn = _LiveTurn()
    app._turn.started = time.time() - seconds_ago
    app._show_thinking()


def test_thought_label_mirrors_the_shared_helper() -> None:
    assert thought_label(None) == "Thought"
    assert thought_label(0.4) == "Thought"
    assert thought_label(7.2) == "Thought for 7s"
    assert thought_label(125) == "Thought for 2m 5s"
    assert thought_label(120) == "Thought for 2m"


def test_consolidate_reasoning_strips_segments_already_in_the_turn_join() -> None:
    tools = [{"reasoning": "look at the log"}, {"reasoning": ""}, {"reasoning": "count exits"}]
    joined = "look at the log\n\ncount exits\n\nwrite it up"
    assert consolidate_reasoning(tools, joined) == "look at the log\n\ncount exits\n\nwrite it up"
    assert consolidate_reasoning([], "only turn") == "only turn"


def test_turn_parts_splits_ask_user_out_of_the_steps() -> None:
    turn = Turn(at=0, user="u", assistant="a", reasoned_s=3.0, tools=[
        ToolLog(at=0, name="read_file", args={"path": "x"}, result="ok", ok=True, duration_s=0.1),
        ToolLog(at=0, name="ask_user", args={"question": "Which?"}, result="B", ok=True, duration_s=1),
    ])
    parts = turn_parts(turn)
    assert [t.name for t in parts["tools"]] == ["read_file"]
    assert parts["ask_users"] == [{"question": "Which?", "result": "B"}]
    assert parts["reasoned_s"] == 3.0


@pytest.mark.parametrize("name,family", [
    ("read_file", "file"), ("edit_file", "file"), ("list_dir", "file"),
    ("terminal", "terminal"), ("web_fetch", "globe"), ("browser", "globe"),
    ("grep", "search"), ("send_message", "link"), ("notify", "link"), ("peer", "link"),
    ("memory", "memory"), ("schedule", "chip"), ("mcp:thing", "chip"),
])
def test_tool_family(name: str, family: str) -> None:
    assert tool_family(name) == family


@pytest.mark.asyncio
async def test_live_reasoning_collapses_into_a_thought_row(tui_home) -> None:
    app = AlpiApp(home_dir=tui_home)
    async with app.run_test(size=(110, 40)) as pilot:
        _start_turn(app, seconds_ago=7.2)
        _feed(app, AgentEvent(kind="reasoning_delta", text="The user wants "),
              AgentEvent(kind="reasoning_delta", text="a summary."))
        await pilot.pause()
        indicator = app.query_one(ThinkingIndicator)
        assert indicator.label == "Thinking…"
        assert not app.query(ReasoningBlock)
        _feed(app, AgentEvent(kind="assistant_delta", text="Here it is."))
        await pilot.pause()
        assert not app.query(ThinkingIndicator)
        block = app.query_one(ReasoningBlock)
        assert block.label == "Thought for 7s"
        assert block.text == "The user wants a summary."
        assert not block.expanded
        head = block.query_one(".reasoning-head")
        await pilot.click(head)
        assert block.expanded


@pytest.mark.asyncio
async def test_live_steps_group_counts_tools_and_opens_on_failure(tui_home) -> None:
    app = AlpiApp(home_dir=tui_home)
    async with app.run_test(size=(110, 40)) as pilot:
        _start_turn(app)
        _feed(
            app,
            AgentEvent(kind="assistant_delta", text="Let me check."),
            AgentEvent(kind="tool_start", tool_id="t1", name="read_file", args={"path": "/tmp/a.log"}),
            AgentEvent(kind="tool_end", tool_id="t1", name="read_file", output="l1\nl2", ok=True),
            AgentEvent(kind="tool_start", tool_id="t2", name="terminal", args={"command": "npm run lint"}),
        )
        await pilot.pause()
        group = app.query_one(StepsGroup)
        assert len(group.cards) == 2
        assert group.running
        assert "2 steps" in group.head_text().plain
        assert not group.expanded
        block = app.query_one(ReasoningBlock)
        assert block.text == "Let me check."
        assert not app.query(AssistantMessage)
        _feed(app, AgentEvent(kind="tool_end", tool_id="t2", name="terminal", output="ERROR: 1 error", ok=False))
        await pilot.pause()
        assert not group.running
        assert group.expanded
        failed = [c for c in group.cards if not c.ok][0]
        assert failed.expanded
        assert "npm run lint" in failed.detail_text()
        assert "1 failed" in group.head_text().plain
        ok_card = group.cards[0]
        assert not ok_card.expanded
        assert "▤" in ok_card.head_text().plain


@pytest.mark.asyncio
async def test_ask_user_is_not_a_step(tui_home) -> None:
    app = AlpiApp(home_dir=tui_home)
    async with app.run_test(size=(110, 40)) as pilot:
        _start_turn(app)
        _feed(
            app,
            AgentEvent(kind="tool_start", tool_id="q", name="ask_user", args={"question": "Which env?"}),
            AgentEvent(kind="tool_end", tool_id="q", name="ask_user", output="staging", ok=True),
        )
        await pilot.pause()
        assert not app.query(StepsGroup)
        line = app.query_one(AskUserLine)
        assert "Which env?" in str(line.render()) and "staging" in str(line.render())


@pytest.mark.asyncio
async def test_model_state_relabels_the_indicator(tui_home) -> None:
    app = AlpiApp(home_dir=tui_home)
    async with app.run_test(size=(110, 40)) as pilot:
        _start_turn(app)
        _feed(app, AgentEvent(kind="model_state"))
        await pilot.pause()
        assert app.query_one(ThinkingIndicator).label == "Preparing a step…"


@pytest.mark.asyncio
async def test_replay_uses_reasoned_s_and_groups_steps(tui_home) -> None:
    app = AlpiApp(home_dir=tui_home)
    turn = Turn(
        at=100.0, user="Summarize deploys", assistant="Two jobs failed.",
        reasoning="plan it", reasoned_s=4.0,
        tools=[
            ToolLog(at=101.0, name="read_file", args={"path": "a"}, result="x", ok=True, duration_s=0.5),
            ToolLog(at=102.0, name="terminal", args={"command": "ls"}, result="boom", ok=False, duration_s=1.0),
        ],
    )
    async with app.run_test(size=(110, 40)) as pilot:
        widgets = app.replay_widgets([turn])
        await app.query_one("#chat").mount(*widgets)
        await pilot.pause()
        block = app.query_one(ReasoningBlock)
        assert block.label == "Thought for 4s"
        assert "▸ Thought for 4s" in str(block.query_one(".reasoning-head").render())
        group = app.query_one(StepsGroup)
        assert "2 steps · 2.0s" in group.head_text().plain
        assert "2 steps · 2.0s" in str(group.query_one(".steps-head").render())
        assert "read_file" in str(group.cards[0].query_one(".tool-head").render())
        assert app.query_one(UserMessage).region.height <= 2
        assert group.expanded
        cards = list(group.query(ToolCard))
        assert [c.expanded for c in cards] == [False, True]
        assert "500ms" in cards[0].head_text().plain


@pytest.mark.asyncio
async def test_ctrl_o_toggles_the_last_turn_details(tui_home) -> None:
    app = AlpiApp(home_dir=tui_home)
    turn = Turn(at=0, user="u", assistant="a", reasoning="r", reasoned_s=2.0, tools=[
        ToolLog(at=0, name="grep", args={"pattern": "x"}, result="1", ok=True, duration_s=0.1),
    ])
    async with app.run_test(size=(110, 40)) as pilot:
        await app.query_one("#chat").mount(*app.replay_widgets([turn]))
        await pilot.pause()
        await pilot.press("ctrl+o")
        assert app.query_one(ReasoningBlock).expanded and app.query_one(StepsGroup).expanded
        await pilot.press("ctrl+o")
        assert not app.query_one(ReasoningBlock).expanded and not app.query_one(StepsGroup).expanded


@pytest.mark.asyncio
async def test_steps_timer_runs_only_while_a_step_is_live(tui_home) -> None:
    app = AlpiApp(home_dir=tui_home)
    turn = Turn(at=0, user="u", assistant="a", tools=[
        ToolLog(at=0, name="grep", args={"pattern": "x"}, result="1", ok=True, duration_s=0.1),
    ])
    async with app.run_test(size=(110, 40)) as pilot:
        await app.query_one("#chat").mount(*app.replay_widgets([turn]))
        await pilot.pause()
        assert not app.query_one(StepsGroup).live
        _start_turn(app)
        _feed(app, AgentEvent(kind="tool_start", tool_id="t", name="grep", args={"pattern": "y"}))
        await pilot.pause()
        live = app._turn.steps
        assert live.live
        _feed(app, AgentEvent(kind="tool_end", tool_id="t", name="grep", output="a", ok=True))
        await pilot.pause()
        assert not live.live


def test_result_hints_pluralise() -> None:
    from alpi.tool_hints import result_hint

    assert result_hint("read_file", "one", muted="m") == "[m]1 line[/m]"
    assert result_hint("grep", "one", muted="m") == "[m]1 match[/m]"
    assert result_hint("glob", "a\nb", muted="m") == "[m]2 files[/m]"
    assert result_hint("terminal", "a\nb", muted="m") == "a  [m]+1 line[/m]"


@pytest.mark.asyncio
async def test_huge_user_messages_render_as_plain_text(tui_home) -> None:
    from textual.widgets import Markdown

    app = AlpiApp(home_dir=tui_home)
    async with app.run_test(size=(110, 40)) as pilot:
        small = UserMessage("# short")
        big = UserMessage("line\n" * 500)
        await app.query_one("#chat").mount(small, big)
        await pilot.pause()
        assert small.query(Markdown) and not small.plain
        assert big.plain and not big.query(Markdown)
        assert big.query_one(".user-plain").region.width > 50
