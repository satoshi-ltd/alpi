"""End-to-end: gateway per-chat session threading via `--resume-chat`."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from alpi import cli, session_map


@pytest.fixture
def fake_engine(monkeypatch):
    """Stub Engine so _run_once never talks to an LLM."""
    from alpi import engine as engine_mod

    class _FakeEngine:
        def __init__(self, home, cfg):
            from alpi.session import Session
            self.home = home
            self.cfg = cfg
            self.session = Session(home=home, model=cfg.model)

        def run_turn(self, user_text, emit=None, persist_inflight=True):
            from alpi.session import Turn
            self.session.turns.append(Turn(at=0.0, user=user_text, tools=[], assistant="ok"))
            self.session.messages.append({"role": "user", "content": user_text})
            self.session.messages.append({"role": "assistant", "content": "ok"})

        def save_session(self):
            path = self.home / self.session.subdir / f"{self.session.id}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({
                "id": self.session.id,
                "model": self.session.model,
                "turns": [
                    {"at": t.at, "user": t.user, "assistant": t.assistant, "tools": []}
                    for t in self.session.turns
                ],
                "input_tokens": 0,
                "output_tokens": 0,
                "cost_usd": 0.0,
            }))
            return path

    monkeypatch.setattr(engine_mod, "Engine", _FakeEngine)
    monkeypatch.setattr(cli, "Engine", _FakeEngine)
    return _FakeEngine


def test_fresh_chat_creates_and_binds_new_session(tmp_path: Path, fake_engine) -> None:
    cli._run_once(tmp_path, "hola", resume_chat_id="chat-1")
    assert session_map.get(tmp_path, "chat-1") is not None
    bound = session_map.get(tmp_path, "chat-1")
    # Gateway sessions live in ``gateway/sessions/`` so they don't show
    # up in TUI/desktop's ``sessions/`` listing.
    assert (tmp_path / "gateway" / "sessions" / f"{bound}.json").exists()
    assert not (tmp_path / "sessions" / f"{bound}.json").exists()


def test_second_inbound_same_chat_resumes_same_session(
    tmp_path: Path, fake_engine,
) -> None:
    cli._run_once(tmp_path, "hola", resume_chat_id="chat-1")
    first_id = session_map.get(tmp_path, "chat-1")

    cli._run_once(tmp_path, "¿sigues ahí?", resume_chat_id="chat-1")
    second_id = session_map.get(tmp_path, "chat-1")

    assert first_id == second_id, "same chat should keep resuming the same session"
    data = json.loads(
        (tmp_path / "gateway" / "sessions" / f"{first_id}.json").read_text()
    )
    users = [t["user"] for t in data["turns"]]
    assert users == ["hola", "¿sigues ahí?"]


def test_different_chats_stay_isolated(tmp_path: Path, fake_engine) -> None:
    cli._run_once(tmp_path, "work thing", resume_chat_id="chat-work")
    cli._run_once(tmp_path, "personal thing", resume_chat_id="chat-personal")
    work = session_map.get(tmp_path, "chat-work")
    personal = session_map.get(tmp_path, "chat-personal")
    assert work != personal
    gw = tmp_path / "gateway" / "sessions"
    work_data = json.loads((gw / f"{work}.json").read_text())
    personal_data = json.loads((gw / f"{personal}.json").read_text())
    assert [t["user"] for t in work_data["turns"]] == ["work thing"]
    assert [t["user"] for t in personal_data["turns"]] == ["personal thing"]


def test_forget_gets_a_fresh_session_next_inbound(
    tmp_path: Path, fake_engine,
) -> None:
    """Emulates the /new shortcut flow."""
    cli._run_once(tmp_path, "first round", resume_chat_id="chat-1")
    old = session_map.get(tmp_path, "chat-1")

    # /new: drop the pointer, session file stays.
    session_map.forget(tmp_path, "chat-1")

    cli._run_once(tmp_path, "second round", resume_chat_id="chat-1")
    new = session_map.get(tmp_path, "chat-1")

    assert old != new
    gw = tmp_path / "gateway" / "sessions"
    assert (gw / f"{old}.json").exists()
    assert (gw / f"{new}.json").exists()


def test_gateway_session_invisible_to_local_continue(
    tmp_path: Path, fake_engine,
) -> None:
    """A gateway turn must not produce any file under ``sessions/`` —
    that's the dir TUI/desktop scan for the local chat list and for
    ``--continue``."""
    cli._run_once(tmp_path, "telegram inbound", resume_chat_id="chat-tg")
    assert not (tmp_path / "sessions").exists() or not list(
        (tmp_path / "sessions").glob("*.json")
    )


def test_gateway_map_lives_under_gateway_sessions(
    tmp_path: Path, fake_engine,
) -> None:
    """The ``chat_id → session_id`` pointer file lives next to the
    gateway sessions, not in ``sessions/`` (where it used to leak as a
    bogus row in the desktop list)."""
    cli._run_once(tmp_path, "hi", resume_chat_id="chat-1")
    assert (tmp_path / "gateway" / "sessions" / "_map.json").exists()
    assert not (tmp_path / "sessions" / "_gateway_map.json").exists()


def test_no_resume_chat_id_behaves_as_before(
    tmp_path: Path, fake_engine,
) -> None:
    """Fresh session per call when no chat id is passed (TUI / manual --once)."""
    cli._run_once(tmp_path, "one")
    cli._run_once(tmp_path, "two")
    # Two separate session files, no map entries.
    files = list((tmp_path / "sessions").glob("*.json"))
    assert len(files) == 2
    assert session_map.all_pointers(tmp_path) == {}


def test_no_save_writes_no_session_files(
    tmp_path: Path, fake_engine,
) -> None:
    cli._run_once(tmp_path, "scheduled run", persist=False)
    assert not list((tmp_path / "sessions").glob("*.json"))
    assert not list((tmp_path / "gateway" / "sessions").glob("*.json"))
    assert not list((tmp_path / "schedule" / "sessions").glob("*.json"))
