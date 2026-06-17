from __future__ import annotations

import json
from pathlib import Path

import pytest

from alpi import config, home, memory
from alpi.cli import _hydrate_from_path
from alpi.engine import Engine
from alpi.session import ToolLog, Turn, turn_replayable


def test_turn_replayable_distinguishes_aborted_turns() -> None:
    tool = ToolLog(at=0.0, name="web_search", args={}, result="", ok=True, duration_s=0.0)
    assert turn_replayable(Turn(at=0.0, user="x", tools=[], assistant="hi there"))
    assert turn_replayable(
        Turn(at=0.0, user="x", tools=[], assistant="", output_attachments=[{"path": "/p"}])
    )
    assert not turn_replayable(Turn(at=0.0, user="do a long research", tools=[], assistant=""))
    assert not turn_replayable(Turn(at=0.0, user="old question", tools=[tool], assistant=""))


@pytest.fixture
def bootstrapped_home(tmp_home_no_env: Path) -> Path:
    home.ensure_home(tmp_home_no_env)
    config.seed_defaults(tmp_home_no_env)
    memory.MemoryStore(tmp_home_no_env).seed_defaults()
    (tmp_home_no_env / "memories" / "AGENT.md").write_text("# Identity\nYou are alpi.\n")
    return tmp_home_no_env


def test_resume_drops_aborted_turn_from_prompt(bootstrapped_home: Path) -> None:
    sess = {
        "id": "abc123",
        "turns": [
            {"at": 1.0, "user": "hello", "assistant": "hi there", "tools": []},
            {"at": 2.0, "user": "do a long research on economic news", "assistant": "", "tools": []},
            {
                "at": 3.0,
                "user": "an older tool-only question",
                "assistant": "",
                "tools": [
                    {"at": 3.0, "name": "web_search", "args": {}, "result": "", "ok": True, "duration_s": 0.1},
                ],
            },
        ],
    }
    path = bootstrapped_home / "sessions" / "abc123.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sess))

    cfg = config.load(bootstrapped_home)
    engine = Engine(home=bootstrapped_home, cfg=cfg)
    assert _hydrate_from_path(engine, path)

    user_msgs = [m["content"] for m in engine.session.messages if m.get("role") == "user"]
    assert any("hello" in m for m in user_msgs)
    assert not any("research" in m for m in user_msgs)
    assert not any("tool-only" in m for m in user_msgs)


def test_host_rewrite_drops_aborted_turn_from_prompt(bootstrapped_home: Path) -> None:
    from alpi.host.chat import _truncate_hydrated_session

    tool = ToolLog(at=2.0, name="web_search", args={}, result="", ok=True, duration_s=0.1)
    cfg = config.load(bootstrapped_home)
    engine = Engine(home=bootstrapped_home, cfg=cfg)
    engine.session.turns = [
        Turn(at=1.0, user="hello", tools=[], assistant="hi there"),
        Turn(at=2.0, user="an older tool-only question", tools=[tool], assistant=""),
    ]

    _truncate_hydrated_session(engine, keep_turns=2)

    user_msgs = [m["content"] for m in engine.session.messages if m.get("role") == "user"]
    assert any("hello" in m for m in user_msgs)
    assert not any("tool-only" in m for m in user_msgs)
