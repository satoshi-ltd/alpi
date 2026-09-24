from __future__ import annotations

import asyncio
import re
from pathlib import Path

import pytest

from alpi.alp import mention as alp_mention
from alpi.alp import peers as peers_mod
from alpi.core.run_context import RunContext, use as use_run


def _wire(monkeypatch, tmp_path: Path, final: dict) -> dict:
    sock = tmp_path / "alp.sock"
    sock.write_text("")
    peer = peers_mod.Peer(id="bob", pubkey="bobkey", allow=["link.ask"])
    monkeypatch.setattr(alp_mention.peers_mod, "get_by_id", lambda home, pid: peer)
    monkeypatch.setattr(alp_mention.peers_mod, "local_socket_path", lambda p: sock)
    monkeypatch.setattr(alp_mention, "load_or_generate", lambda home: object())
    monkeypatch.setattr(alp_mention, "_link_timeouts", lambda home, t, m: (5.0, 0.0))
    seen: dict = {}

    async def fake_call_stream(**kwargs):
        seen["params"] = kwargs["params"]
        yield (dict(final), "final")

    monkeypatch.setattr(alp_mention.alp_client, "call_stream", fake_call_stream)
    return seen


def _ctx(tmp_path: Path, session_id: str) -> RunContext:
    return RunContext("r1", tmp_path, tmp_path, "relay", "user", session_id, "host")


def test_conversation_id_is_stable_opaque_and_wire_safe() -> None:
    first = alp_mention.conversation_id("sess-1")
    assert first == alp_mention.conversation_id("sess-1")
    assert first != alp_mention.conversation_id("sess-2")
    assert "sess-1" not in first
    assert re.fullmatch(r"[A-Za-z0-9_-]{1,64}", first)


def test_execute_derives_the_conversation_from_the_running_turns_session(monkeypatch, tmp_path: Path) -> None:
    seen = _wire(monkeypatch, tmp_path, {"text": "pong", "history": "conversation"})

    with use_run(_ctx(tmp_path, "relay-session-7")):
        result = asyncio.run(alp_mention.execute(tmp_path, "bob", "ping"))

    assert seen["params"]["conversation"] == alp_mention.conversation_id("relay-session-7")
    assert result.ok and result.history == "conversation" and result.history_shared is False


def test_execute_prefers_an_explicit_source_session_over_the_run_context(monkeypatch, tmp_path: Path) -> None:
    seen = _wire(monkeypatch, tmp_path, {"text": "pong", "history": "conversation"})

    with use_run(_ctx(tmp_path, "ignored")):
        asyncio.run(alp_mention.execute(tmp_path, "bob", "ping", source_session="chat-42"))

    assert seen["params"]["conversation"] == alp_mention.conversation_id("chat-42")


def test_execute_sends_an_empty_conversation_when_none_can_be_established(monkeypatch, tmp_path: Path) -> None:
    seen = _wire(monkeypatch, tmp_path, {"text": "pong", "history": "none"})

    result = asyncio.run(alp_mention.execute(tmp_path, "bob", "ping"))

    assert seen["params"]["conversation"] == ""
    assert result.history == "none" and result.history_shared is False


@pytest.mark.parametrize("final", [{"text": "pong"}, {"text": "pong", "history": "peer"}])
def test_execute_reports_a_target_that_ignored_the_conversation(monkeypatch, tmp_path: Path, final: dict) -> None:
    _wire(monkeypatch, tmp_path, final)

    with use_run(_ctx(tmp_path, "relay-session-7")):
        result = asyncio.run(alp_mention.execute(tmp_path, "bob", "ping"))

    assert result.ok and result.history_shared is True


def test_execute_stream_marks_the_final_frame_with_history_shared(monkeypatch, tmp_path: Path) -> None:
    _wire(monkeypatch, tmp_path, {"text": "pong"})

    async def run() -> list[dict]:
        with use_run(_ctx(tmp_path, "relay-session-7")):
            return [f async for f in alp_mention.execute_stream(tmp_path, "bob", "ping")]

    frames = asyncio.run(run())

    assert frames[-1]["kind"] == "final" and frames[-1]["history_shared"] is True


def test_annotate_reply_appends_the_shared_history_note_only_when_shared() -> None:
    assert alp_mention.annotate_reply("pong", "bob", history_shared=False) == "pong"
    annotated = alp_mention.annotate_reply("pong", "bob", history_shared=True)
    assert annotated.startswith("pong\n\n")
    assert annotated.endswith(alp_mention.shared_history_note("bob"))
    assert alp_mention.annotate_reply("", "bob", history_shared=True) == alp_mention.shared_history_note("bob")


def test_reply_text_prefers_the_final_text_and_carries_the_note_from_the_final_frame() -> None:
    note = alp_mention.shared_history_note("bob")
    assert alp_mention.reply_text("bob", {"text": " pong "}, ["po", "ng"]) == "pong"
    assert alp_mention.reply_text("bob", {}, ["po", "ng"]) == "pong"
    assert alp_mention.reply_text("bob", None, []) == ""
    assert alp_mention.reply_text("bob", {"text": "pong", "history_shared": True}, []) == f"pong\n\n{note}"
    assert alp_mention.reply_text("bob", {"history_shared": True}, ["pong"]) == f"pong\n\n{note}"
