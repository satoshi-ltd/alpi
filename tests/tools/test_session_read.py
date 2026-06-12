from __future__ import annotations

import json
from pathlib import Path

import pytest

from alpi.tools import session_read as mod
from alpi.tools.session_read import SessionRead


def _write_session(sessions: Path, sid: str, started: float, turns: list[dict]) -> None:
    (sessions / f"{sid}.json").write_text(json.dumps({
        "id": sid, "started_at": started, "turns": turns,
    }))


@pytest.fixture
def home(tmp_path, monkeypatch):
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    _write_session(sessions, "alpha", 1000, [
        {"user": "hello there", "assistant": "hi"},
        {"user": "talk about pricing thresholds", "assistant": "the cap is $5"},
        {"user": "thanks", "assistant": "welcome"},
    ])
    _write_session(sessions, "beta", 2000, [
        {"user": "unrelated", "assistant": "ok"},
    ])
    monkeypatch.setattr(mod, "get_home", lambda: tmp_path)
    monkeypatch.setattr(mod, "current_session_id", lambda: None)
    return tmp_path


def test_lists_recent_sessions_newest_first(home):
    out = SessionRead().run().output
    assert "recent sessions:" in out
    assert out.index("beta") < out.index("alpha")  # beta started later
    assert "talk about pricing thresholds"[:20] not in out  # only first user line preview
    assert "hello there" in out


def test_excludes_current_session_from_list(home, monkeypatch):
    monkeypatch.setattr(mod, "current_session_id", lambda: "beta")
    out = SessionRead().run().output
    assert "beta" not in out
    assert "alpha" in out


def test_phrase_window_marks_anchor_and_neighbors(home):
    out = SessionRead().run(session="alpha", phrase="pricing thresholds", window=1).output
    assert "◀ match" in out
    assert "[#1]" in out and "the cap is $5" in out
    assert "[#0]" in out and "[#2]" in out  # ±1 neighbours


def test_phrase_not_found(home):
    out = SessionRead().run(session="alpha", phrase="nonexistent zzz").output
    assert "no turn" in out


def test_start_paging(home):
    out = SessionRead().run(session="alpha", start=2, limit=1).output
    assert "[#2]" in out and "thanks" in out
    assert "[#0]" not in out


def test_unknown_session_errors(home):
    r = SessionRead().run(session="ghost")
    assert not r.ok and "no session" in r.error


def test_corrupt_started_at_does_not_break_listing(home):
    sessions = home / "sessions"
    _write_session(sessions, "gamma", "not-a-number", [{"user": "garbled ts", "assistant": "ok"}])
    r = SessionRead().run()
    assert r.ok
    assert "gamma" in r.output and "alpha" in r.output
