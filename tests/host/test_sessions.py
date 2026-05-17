"""``data.sessions.list`` + ``data.session.read`` — plaintext session
metadata served from the local control plane."""

from __future__ import annotations

import json
from pathlib import Path
import os

import pytest

from alpi.host import server as host_server
from alpi.host import handlers as data_handlers
from alpi.host import sessions as data_sessions


def _seed_session(
    home: Path,
    sid: str,
    first_user: str,
    started_at: float = 1714000000.0,
    last_turn_at: float | None = None,
) -> Path:
    p = home / "sessions" / f"{sid}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    turn_at = last_turn_at if last_turn_at is not None else started_at
    payload = {
        "id": sid,
        "model": "openrouter/x",
        "started_at": started_at,
        "input_tokens": 10,
        "output_tokens": 20,
        "cost_usd": 0.001,
        "last_ctx_tokens": 5,
        "turns": [
            {"at": turn_at, "user": first_user, "assistant": "ok", "tools": []},
        ],
    }
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


def test_list_sessions_skips_underscore_prefixed(tmp_path: Path) -> None:
    _seed_session(tmp_path, "abc", "hello world")
    _seed_session(tmp_path, "_gateway_map", "")
    rows = data_sessions.list_sessions(tmp_path)
    assert [r["id"] for r in rows] == ["abc"]


def test_list_sessions_tolerates_corrupt_started_at(tmp_path: Path) -> None:
    """One session JSON with a non-numeric ``started_at`` must not nuke
    the whole listing. The bad row falls back to mtime; good rows are
    untouched."""
    _seed_session(tmp_path, "good", "fine chat", started_at=1_714_000_000.0)
    bad = tmp_path / "sessions" / "bad.json"
    bad.write_text(
        json.dumps({
            "id": "bad",
            "model": "openrouter/x",
            "started_at": "not-a-number",
            "turns": [{"at": "also-bad", "user": "hi", "assistant": "ok"}],
        }),
        encoding="utf-8",
    )

    rows = data_sessions.list_sessions(tmp_path)
    by_id = {r["id"]: r for r in rows}
    assert set(by_id.keys()) == {"good", "bad"}
    assert by_id["good"]["updated_at"] == 1_714_000_000.0
    assert by_id["bad"]["updated_at"] > 0


def test_list_sessions_classifies_kinds(tmp_path: Path) -> None:
    _seed_session(tmp_path, "a", "[INBOUND TELEGRAM] hi")
    _seed_session(tmp_path, "b", "[SCHEDULED: digest]")
    _seed_session(tmp_path, "c", "ordinary chat")
    rows = data_sessions.list_sessions(tmp_path)
    by_id = {r["id"]: r for r in rows}
    assert by_id["a"]["kind"] == "telegram"
    assert by_id["b"]["kind"] == "scheduled"
    assert by_id["c"]["kind"] == "chat"


def test_list_sessions_limit_reads_recent_first(tmp_path: Path) -> None:
    _seed_session(tmp_path, "old", "old chat", started_at=1_714_000_000.0)
    _seed_session(tmp_path, "new", "new chat", started_at=1_714_000_001.0)
    rows = data_sessions.list_sessions(tmp_path, limit=1)
    assert [r["id"] for r in rows] == ["new"]


def test_list_sessions_orders_by_content_not_filesystem_mtime(tmp_path: Path) -> None:
    old = _seed_session(
        tmp_path, "old", "older chat",
        started_at=1_714_000_000.0, last_turn_at=1_714_000_500.0,
    )
    new = _seed_session(
        tmp_path, "new", "newer chat",
        started_at=1_714_001_000.0, last_turn_at=1_714_002_000.0,
    )
    os.utime(new, ns=(1_500_000_000_000_000_000, 1_500_000_000_000_000_000))
    os.utime(old, ns=(1_900_000_000_000_000_000, 1_900_000_000_000_000_000))
    rows = data_sessions.list_sessions(tmp_path)
    assert [r["id"] for r in rows] == ["new", "old"]
    by_id = {r["id"]: r for r in rows}
    assert by_id["new"]["updated_at"] == pytest.approx(1_714_002_000.0)
    assert by_id["old"]["updated_at"] == pytest.approx(1_714_000_500.0)


@pytest.mark.asyncio
async def test_sessions_list_accepts_limit_param(
    tmp_path: Path, monkeypatch,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    _seed_session(home, "a", "older")
    _seed_session(home, "b", "newer")
    srv = host_server.Server(home=home)
    data_handlers.register(srv)
    monkeypatch.setattr(data_handlers, "_resolve_home", lambda p: home)

    response = await srv._dispatch({
        "id": "r",
        "method": "host.sessions.list",
        "params": {"profile": "default", "limit": 1},
    })

    assert len(response["result"]["sessions"]) == 1


def test_read_session_returns_full_payload(tmp_path: Path) -> None:
    _seed_session(tmp_path, "abc", "hello")
    data = data_sessions.read_session(tmp_path, "abc")
    assert data["id"] == "abc"
    assert data["turns"][0]["user"] == "hello"


def test_read_session_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        data_sessions.read_session(tmp_path, "nope")


@pytest.mark.asyncio
async def test_data_session_read_method_not_found_for_unknown_id(
    tmp_path: Path, monkeypatch,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    srv = host_server.Server(home=home)
    data_handlers.register(srv)
    monkeypatch.setattr(data_handlers, "_resolve_home", lambda p: home)

    body = {"id": "r", "method": "host.session.read", "params": {"id": "missing"}}
    response = await srv._dispatch(body)
    assert response is not None
    assert response.get("error", {}).get("code") == -32004
