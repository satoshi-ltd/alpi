from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from alpi.session import Session, ToolLog, load_turns, truncate_result, TOOL_RESULT_CAP


def test_truncate_result_strips_whitespace() -> None:
    assert truncate_result("  hello world  ") == "hello world"


def test_truncate_result_caps_long_values() -> None:
    text = "x" * (TOOL_RESULT_CAP + 20)
    out = truncate_result(text)
    assert len(out) == TOOL_RESULT_CAP
    assert out.endswith("…")


def test_load_turns_parses_tool_logs_and_reasoning() -> None:
    turns = load_turns({
        "turns": [
            {
                "at": 1.5,
                "user": "hola",
                "assistant": "saludo",
                "tools": [
                    {
                        "at": 2.0,
                        "name": "web_search",
                        "args": {"query": "x"},
                        "result": "ok",
                        "ok": False,
                        "duration_s": 0.25,
                        "reasoning": "first tool of batch",
                    }
                ],
            }
        ]
    })

    assert len(turns) == 1
    turn = turns[0]
    assert turn.at == 1.5
    assert turn.user == "hola"
    assert turn.assistant == "saludo"
    assert len(turn.tools) == 1
    tool = turn.tools[0]
    assert tool.name == "web_search"
    assert tool.args == {"query": "x"}
    assert tool.ok is False
    assert tool.duration_s == 0.25
    assert tool.reasoning == "first tool of batch"


def test_session_status_line_uses_current_elapsed_and_cost(tmp_path: Path) -> None:
    session = Session(home=tmp_path, model="anthropic/claude")
    session.record(input_tokens=123, output_tokens=7, cost=0.4567)

    with patch("alpi.session.time.time", return_value=session.started_at + 65):
        line = session.status_line()

    assert "model: anthropic/claude" in line
    assert "tokens: 130" in line
    assert "session: 01:05" in line
    assert "cost: $0.457" in line


def test_session_save_writes_serialized_turns(tmp_path: Path) -> None:
    session = Session(home=tmp_path, model="openai/gpt-4o")
    session.log_turn(
        user="hola",
        assistant="adios",
        tools=[ToolLog(at=1.0, name="web_search", args={"q": "x"}, result="done", ok=True, duration_s=0.1)],
        started_at=1.0,
    )

    path = session.save()

    assert path == tmp_path / "sessions" / f"{session.id}.json"
    data = json.loads(path.read_text())
    assert data["model"] == "openai/gpt-4o"
    assert data["turns"][0]["user"] == "hola"
    assert data["turns"][0]["assistant"] == "adios"
    assert data["turns"][0]["tools"][0]["name"] == "web_search"
