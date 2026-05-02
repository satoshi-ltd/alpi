"""Unit tests for the session_search tool."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import alpi.tools.session_search as ss


@pytest.fixture
def isolated_home(tmp_home_no_env: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("ALPI_HOME", str(tmp_home_no_env))
    (tmp_home_no_env / "sessions").mkdir(exist_ok=True)
    return tmp_home_no_env


def _write_session(home: Path, sid: str, started: int,
                   turns: list[dict]) -> None:
    """Write a session file using the new turns-based schema."""
    (home / "sessions" / f"{sid}.json").write_text(json.dumps({
        "id": sid,
        "started_at": started,
        "turns": turns,
    }))


def _turn(user: str = "", assistant: str = "", tools: list[dict] | None = None) -> dict:
    return {
        "at": 0, "user": user, "assistant": assistant,
        "tools": tools or [],
    }


def test_finds_matching_session(isolated_home: Path) -> None:
    _write_session(isolated_home, "s1", 1_700_000_000, [
        _turn(user="hablemos de tailscale",
              assistant="tailscale permite red privada"),
    ])
    r = ss.SessionSearch().run(query="tailscale")
    assert r.ok
    assert "tailscale" in r.output.lower()
    assert "s1" in r.output


def test_excludes_current_session(isolated_home: Path) -> None:
    _write_session(isolated_home, "current-id", 1_700_000_000,
                   [_turn(user="topic alpha")])
    _write_session(isolated_home, "older-id", 1_699_000_000,
                   [_turn(user="topic alpha")])
    ss.set_current_session_id("current-id")
    r = ss.SessionSearch().run(query="alpha")
    assert r.ok
    assert "older-id" in r.output
    assert "current-id" not in r.output


def test_no_match_returns_readable_message(isolated_home: Path) -> None:
    _write_session(isolated_home, "s1", 1_700_000_000,
                   [_turn(user="random topic")])
    r = ss.SessionSearch().run(query="zzzinexistente")
    assert r.ok
    assert "no past sessions" in r.output.lower()


def test_short_query_rejected(isolated_home: Path) -> None:
    r = ss.SessionSearch().run(query="ab")
    assert not r.ok


def test_ranking_higher_score_first(isolated_home: Path) -> None:
    _write_session(isolated_home, "low", 1_000,
                   [_turn(user="python")])
    _write_session(isolated_home, "high", 2_000,
                   [_turn(user="python python python python")])
    r = ss.SessionSearch().run(query="python")
    assert r.output.index("high") < r.output.index("low")


def test_output_includes_tools_summary(isolated_home: Path) -> None:
    """Turn tool names appear in the thread tail."""
    _write_session(isolated_home, "s1", 1_700_000_000, [
        _turn(
            user="busca restaurantes",
            assistant="aquí tienes",
            tools=[{"at": 1, "name": "web_search", "args": {"query": "x"},
                    "result": "12 results", "ok": True, "duration_s": 0.8}],
        ),
    ])
    r = ss.SessionSearch().run(query="restaurantes")
    assert r.ok
    assert "web_search" in r.output
    # Raw result is NOT in the thread tail — just the name.
    assert "12 results" not in r.output
