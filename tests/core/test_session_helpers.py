from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from alpi.session import (
    ASSISTANT_CAP,
    SESSION_SCHEMA_VERSION,
    TOOL_ARGS_CAP,
    TURN_REASONING_CAP,
    Session,
    ToolLog,
    Turn,
    load_turns,
    truncate_result,
    TOOL_RESULT_CAP,
)


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
    assert data["schema_version"] == SESSION_SCHEMA_VERSION
    assert data["model"] == "openai/gpt-4o"
    assert data["turns"][0]["user"] == "hola"
    assert data["turns"][0]["assistant"] == "adios"
    assert data["turns"][0]["tools"][0]["name"] == "web_search"
    assert data["turns"][0]["tools"][0]["args"] == '{"q": "x"}'
    assert data["turns"][0]["tools"][0]["result"] == "done"
    assert "args_meta" not in data["turns"][0]["tools"][0]
    assert "assistant_meta" not in data["turns"][0]


def test_interrupted_flag_round_trips_through_save_and_load() -> None:
    session = Session(home=Path("/tmp"), model="m")
    session.log_turn(user="a", assistant="", tools=[], started_at=1.0)
    session.log_turn(user="b", assistant="", tools=[], started_at=2.0, interrupted=True)

    assert session.turns[0].interrupted is False
    assert session.turns[1].interrupted is True

    from alpi.session import _serialize_turn_v2

    rows = [_serialize_turn_v2(t, redact=lambda v: v) for t in session.turns]
    assert "interrupted" not in rows[0]
    assert rows[1]["interrupted"] is True

    loaded = load_turns({"turns": rows})
    assert loaded[0].interrupted is False
    assert loaded[1].interrupted is True


def test_load_turns_defaults_interrupted_false_for_legacy_data_without_the_field() -> None:
    turns = load_turns({"turns": [{"at": 1.0, "user": "hi", "assistant": ""}]})
    assert turns[0].interrupted is False


def test_session_save_leaves_no_temp_sibling(tmp_path: Path) -> None:
    session = Session(home=tmp_path, model="m")
    session.log_turn(user="hi", assistant="hello", tools=[], started_at=1.0)

    path = session.save()

    assert path is not None and path.exists()
    assert not any(p.name.endswith(".tmp") for p in path.parent.iterdir())
    assert load_turns(json.loads(path.read_text()))[0].user == "hi"


def test_session_save_failure_preserves_existing_file(tmp_path: Path) -> None:
    session = Session(home=tmp_path, model="m")
    session.log_turn(user="first", assistant="one", tools=[], started_at=1.0)
    path = session.save()
    original = path.read_text()

    session.log_turn(user="second", assistant="two", tools=[], started_at=2.0)

    def _boom(*_a, **_k):
        raise OSError("disk full")

    with patch("os.replace", _boom), pytest.raises(OSError):
        session.save()

    assert path.read_text() == original
    assert not any(p.name.endswith(".tmp") for p in path.parent.iterdir())


def test_session_save_compacts_large_payloads(tmp_path: Path) -> None:
    big_arg = "a" * (TOOL_ARGS_CAP * 4)
    big_reasoning = "r" * (TURN_REASONING_CAP * 4)
    big_assistant = "z" * (ASSISTANT_CAP * 2)
    session = Session(home=tmp_path, model="m")
    session.turns.append(
        Turn(
            at=1.0,
            user="build a large payload",
            assistant=big_assistant,
            tools=[
                ToolLog(
                    at=2.0,
                    name="write_big",
                    args={"payload": big_arg},
                    result="ok",
                    ok=False,
                    duration_s=0.5,
                    reasoning=big_reasoning,
                ),
            ],
            reasoning=big_reasoning,
        ),
    )

    path = session.save()
    data = json.loads(path.read_text())
    turn = data["turns"][0]
    tool = turn["tools"][0]

    assert path.stat().st_size < 120_000
    assert turn["assistant"].endswith("…")
    assert turn["assistant_meta"]["truncated"] is True
    assert turn["reasoning"].endswith("…")
    assert turn["reasoning_meta"]["truncated"] is True
    assert turn["reasoning_meta"]["bytes"] == len(big_reasoning)
    assert tool["status"] == "failed"
    assert tool["args_meta"]["truncated"] is True
    assert tool["args_meta"]["bytes"] > len(tool["args"])
    assert tool["args_meta"]["sha256"]
    assert tool["reasoning_meta"]["truncated"] is True


def test_load_turns_reads_v2_compact_fields() -> None:
    turns = load_turns({
        "schema_version": 2,
        "turns": [{
            "at": 1.0,
            "user": "hello",
            "assistant": "done",
            "reasoning": {"preview": "compact thinking", "bytes": 999, "sha256": "x", "truncated": True},
            "tools": [{
                "at": 2.0,
                "name": "ask_user",
                "args": {"preview": '{"question":"which?"}', "bytes": 21, "sha256": "x", "truncated": False},
                "result": "answer",
                "ok": True,
                "duration_s": 0.1,
                "reasoning": {"preview": "ask first", "bytes": 8, "sha256": "x", "truncated": False},
            }],
        }],
    })

    assert turns[0].reasoning == "compact thinking"
    assert turns[0].tools[0].args == {"question": "which?"}
    assert turns[0].tools[0].result == "answer"
    assert turns[0].tools[0].reasoning == "ask first"


def test_load_turns_reads_v2_bare_meta_fields() -> None:
    turns = load_turns({
        "schema_version": 2,
        "turns": [{
            "at": 1.0,
            "user": "hello",
            "assistant": "done",
            "reasoning": "compact thinking…",
            "reasoning_meta": {"bytes": 999, "sha256": "x", "truncated": True},
            "tools": [{
                "at": 2.0,
                "name": "ask_user",
                "args": '{"question": "which?"}',
                "result": "answer",
                "ok": True,
                "duration_s": 0.1,
                "reasoning": "ask first",
            }],
        }],
    })

    assert turns[0].reasoning == "compact thinking…"
    assert turns[0].tools[0].args == {"question": "which?"}
    assert turns[0].tools[0].result == "answer"
    assert turns[0].tools[0].reasoning == "ask first"


def test_load_turns_preserves_v1_args_with_preview_key() -> None:
    turns = load_turns({
        "turns": [{
            "at": 1.0,
            "user": "hello",
            "assistant": "done",
            "tools": [{
                "at": 2.0,
                "name": "custom",
                "args": {"preview": "literal arg", "other": 1},
                "result": "ok",
                "ok": True,
                "duration_s": 0.1,
            }],
        }],
    })

    assert turns[0].tools[0].args == {"preview": "literal arg", "other": 1}


def test_turn_model_round_trips_and_is_omitted_when_empty(tmp_path: Path) -> None:
    s = Session(home=tmp_path, model="openrouter/main")
    s.turns.append(Turn(at=1.0, user="hi", tools=[], assistant="hola",
                        model="openrouter/deep"))
    s.turns.append(Turn(at=2.0, user="bye", tools=[], assistant="adiós"))
    path = s.save()
    payload = json.loads(path.read_text())
    assert payload["turns"][0]["model"] == "openrouter/deep"
    assert "model" not in payload["turns"][1]
    loaded = load_turns(payload)
    assert loaded[0].model == "openrouter/deep"
    assert loaded[1].model == ""
