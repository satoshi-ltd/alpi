"""Engine wiring for `alpi.clock` — system prompt + per-turn NOW block."""

from __future__ import annotations

from pathlib import Path

import pytest

from alpi import config, home, memory
from alpi.engine import Engine


@pytest.fixture
def bootstrapped_home(tmp_home_no_env: Path) -> Path:
    home.ensure_home(tmp_home_no_env)
    config.seed_defaults(tmp_home_no_env)
    memory.MemoryStore(tmp_home_no_env).seed_defaults()
    return tmp_home_no_env


def test_system_prompt_includes_date_time_section(
    bootstrapped_home: Path, monkeypatch
) -> None:
    monkeypatch.setenv("TZ", "Europe/Madrid")
    cfg = config.load(bootstrapped_home)
    engine = Engine(home=bootstrapped_home, cfg=cfg)
    prompt = engine._system_prompt
    assert "# DATE & TIME" in prompt
    assert "Timezone: Europe/Madrid" in prompt
    assert "# NOW" in prompt  # the system prompt POINTS the agent at the NOW block
    # The actual fresh date must NOT live in the system prompt — that would
    # rot across cache TTL / compaction reuse.
    assert "Local:" not in prompt
    assert "UTC:" not in prompt


def _fake_stream_final(text: str = "ok"):
    def _stream(*_a, **_kw):
        yield {"text_delta": text, "reasoning_delta": "", "tool_calls_delta": []}
        yield {
            "final": True,
            "tool_calls": [],
            "input_tokens": 1,
            "output_tokens": 1,
            "cost_usd": 0.0,
        }
    return _stream


def test_run_turn_carries_fresh_now_block_in_the_user_suffix(
    bootstrapped_home: Path, monkeypatch
) -> None:
    """CL.4 — the NOW block rides the user turn (host-context suffix), never a strippable system message that would rewrite history."""
    monkeypatch.setenv("TZ", "Europe/Madrid")

    from alpi import engine as engine_mod
    monkeypatch.setattr(engine_mod.llm, "stream", _fake_stream_final("done"))

    cfg = config.load(bootstrapped_home)
    engine = Engine(home=bootstrapped_home, cfg=cfg)
    baseline = len(engine.session.messages)

    engine.run_turn("hola, qué día es hoy?", lambda _ev: None)

    new_msgs = engine.session.messages[baseline:]
    assert not [
        m for m in new_msgs
        if m["role"] == "system" and str(m["content"]).startswith("# NOW")
    ], "no system NOW messages anymore"

    user_msgs = [m for m in new_msgs if m["role"] == "user"]
    assert user_msgs
    block = user_msgs[0]["content"]
    assert block.startswith("hola, qué día es hoy?")
    assert "# HOST CONTEXT" in block
    assert "# NOW" in block
    assert "Local:" in block
    assert "(Europe/Madrid)" in block
    assert "UTC:" in block


def test_multi_turn_history_is_append_only_with_per_turn_now(
    bootstrapped_home: Path, monkeypatch
) -> None:
    """Each turn carries its own dated suffix; prior turns are never rewritten (the header says the newest supersedes)."""
    monkeypatch.setenv("TZ", "UTC")

    from alpi import engine as engine_mod
    monkeypatch.setattr(engine_mod.llm, "stream", _fake_stream_final("ok"))

    cfg = config.load(bootstrapped_home)
    engine = Engine(home=bootstrapped_home, cfg=cfg)

    engine.run_turn("first", lambda _ev: None)
    snapshot = [dict(m) for m in engine.session.messages]
    engine.run_turn("second", lambda _ev: None)
    engine.run_turn("third", lambda _ev: None)

    assert engine.session.messages[: len(snapshot)] == snapshot, (
        "a new turn must never rewrite prior provider-visible messages"
    )
    user_msgs = [m for m in engine.session.messages if m["role"] == "user"]
    assert len(user_msgs) == 3
    assert all("# NOW" in m["content"] for m in user_msgs)


def test_stale_now_blocks_from_prior_run_survive_untouched(
    bootstrapped_home: Path, monkeypatch
) -> None:
    """Legacy system NOW blocks (pre-CL.4 sessions) are historical bytes now — deleting them would split the provider prefix."""
    monkeypatch.setenv("TZ", "UTC")

    from alpi import engine as engine_mod
    monkeypatch.setattr(engine_mod.llm, "stream", _fake_stream_final("ok"))

    cfg = config.load(bootstrapped_home)
    engine = Engine(home=bootstrapped_home, cfg=cfg)
    # Plant two stale blocks (as if loaded from a long-running saved session).
    engine.session.messages.append({"role": "system", "content": "# NOW\nLocal: stale-1"})
    engine.session.messages.append({"role": "system", "content": "# NOW\nLocal: stale-2"})

    engine.run_turn("what time is it?", lambda _ev: None)

    legacy = [
        m for m in engine.session.messages
        if m["role"] == "system" and m["content"].startswith("# NOW\n")
    ]
    assert len(legacy) == 2, "legacy blocks stay as immutable history"
    user_msgs = [m for m in engine.session.messages if m["role"] == "user"]
    assert user_msgs and "# NOW" in user_msgs[-1]["content"], (
        "the fresh clock arrives in the new turn's suffix instead"
    )
