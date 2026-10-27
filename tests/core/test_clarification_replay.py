from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from alpi.cli import _hydrate_from_path
from alpi.engine import _result_for_log
from alpi.host.chat import _truncate_hydrated_session
from alpi.session import Session, ToolLog, Turn, clarification_messages, turn_replayable


def clarification(answer: str, *, ok: bool = True, name: str = "ask_user") -> ToolLog:
    return ToolLog(
        at=1.0, name=name, args={"question": "Which system do you operate?"},
        result=answer, ok=ok, duration_s=0.1,
    )


@pytest.mark.parametrize("rewrite", [False, True])
def test_resume_preserves_human_clarification_without_replaying_target_output(
    tmp_path: Path, rewrite: bool,
) -> None:
    original = Session(home=tmp_path, model="test")
    original.turns = [Turn(
        at=1.0, user="Inspect this site", assistant="I will inspect it",
        tools=[clarification("I develop the booking system"),
               clarification("UNTRUSTED_TARGET_TEXT", name="web_fetch")],
    )]
    path = original.save()
    engine = SimpleNamespace(
        session=Session(home=tmp_path, model="test"), _system_prompt="Current instructions",
    )
    engine.session.messages = [{"role": "system", "content": engine._system_prompt}]
    assert _hydrate_from_path(engine, path)
    if rewrite:
        _truncate_hydrated_session(engine, 1)
    messages = engine.session.messages
    answer = next(m for m in messages if "I develop the booking system" in m.get("content", ""))
    assert answer["role"] == "user"
    assert "Which system do you operate?" in answer["content"]
    assert messages.index(answer) < next(i for i, m in enumerate(messages) if m["role"] == "assistant")
    assert "UNTRUSTED_TARGET_TEXT" not in json.dumps(messages)


@pytest.mark.parametrize("answer,ok", [
    ("No response received before timeout.", True),
    ("No user-facing surface accepted the question; ask plainly.", True),
    ("Clarification handler failed: unavailable. Ask the user plainly.", True),
    ("This run has no live user; ask_user cannot be used.", True),
    ("A clipped answer…", True),
    ("I authorise it", False),
])
def test_fallbacks_failures_and_clipped_answers_are_not_user_authorisation(
    tmp_path: Path, answer: str, ok: bool,
) -> None:
    session = Session(home=tmp_path, model="test")
    session.turns = [Turn(at=1, user="Question", assistant="Final", tools=[clarification(answer, ok=ok)])]
    path = session.save()
    engine = SimpleNamespace(session=Session(home=tmp_path, model="test"))
    assert _hydrate_from_path(engine, path)
    assert not any(answer in m.get("content", "") for m in engine.session.messages)


def test_answer_survives_interruption_and_rewrite_keeps_only_retained_turns(tmp_path: Path) -> None:
    answered = Turn(at=1, user="Inspect", assistant="", tools=[clarification("Read-only checks only")], interrupted=True)
    assert turn_replayable(answered)
    session = Session(home=tmp_path, model="test")
    session.turns = [answered, Turn(at=2, user="Later", assistant="Done", tools=[clarification("Later answer")])]
    path = session.save()
    engine = SimpleNamespace(session=Session(home=tmp_path, model="test"))
    assert _hydrate_from_path(engine, path)
    _truncate_hydrated_session(engine, 1)
    messages = json.dumps(engine.session.messages)
    assert "Read-only checks only" in messages
    assert "Later answer" not in messages


def test_clarification_log_keeps_more_than_a_generic_tool_preview_and_stays_bounded() -> None:
    answer = "Specific scope: " + "x" * 700
    assert _result_for_log("ask_user", answer) == answer
    huge = _result_for_log("ask_user", "é" * 5000)
    assert len(huge.encode()) <= 4096
    assert huge.endswith("…")


def test_clarification_is_redacted_when_saved(tmp_path: Path) -> None:
    session = Session(home=tmp_path, model="test")
    session.turns = [Turn(at=1, user="Question", assistant="Done", tools=[clarification("Use sk-" + "x" * 30)])]
    path = session.save()
    engine = SimpleNamespace(session=Session(home=tmp_path, model="test"))
    assert _hydrate_from_path(engine, path)
    text = json.dumps(engine.session.messages)
    assert "[REDACTED]" in text
    assert "sk-" not in text


def test_replay_requires_complete_question_and_caps_combined_answers() -> None:
    long_question = clarification("Approved")
    long_question.args["question"] = "x" * 1025
    assert clarification_messages(Turn(at=1, user="Inspect", assistant="", tools=[long_question])) == []
    turn = Turn(at=1, user="Inspect", assistant="", tools=[clarification("x" * 4000)] * 3)
    messages = clarification_messages(turn)
    assert len(messages) == 2
    assert sum(len(m["content"].encode()) for m in messages) <= 8192
