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


@pytest.fixture(autouse=True)
def _fresh_row_cache():
    data_sessions._clear_row_cache()
    yield
    data_sessions._clear_row_cache()


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
    (tmp_path / "sessions" / "._abc.json").write_text("{}", encoding="utf-8")
    rows = data_sessions.list_sessions(tmp_path)
    assert [r["id"] for r in rows] == ["abc"]


def test_count_sessions_ignores_sidecars_hidden_and_appledouble(tmp_path: Path) -> None:
    _seed_session(tmp_path, "abc", "hello world")
    d = tmp_path / "sessions"
    (d / "_events_abc.jsonl").write_text("frame\n", encoding="utf-8")
    (d / "_gateway_map.json").write_text("{}", encoding="utf-8")
    (d / "._abc.json").write_text("{}", encoding="utf-8")
    (d / ".hidden.json").write_text("{}", encoding="utf-8")
    (d / "notes.txt").write_text("{}", encoding="utf-8")

    assert data_sessions.count_sessions(tmp_path) == 1
    assert [r["id"] for r in data_sessions.list_sessions(tmp_path)] == ["abc"]


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
    _seed_session(tmp_path, "a", "[INBOUND IMAP] hi")
    _seed_session(tmp_path, "b", "[SCHEDULED: digest]")
    _seed_session(tmp_path, "c", "ordinary chat")
    rows = data_sessions.list_sessions(tmp_path)
    by_id = {r["id"]: r for r in rows}
    assert by_id["a"]["kind"] == "email"
    assert by_id["b"]["kind"] == "scheduled"
    assert by_id["c"]["kind"] == "chat"


def test_list_sessions_limit_reads_recent_first(tmp_path: Path) -> None:
    _seed_session(tmp_path, "old", "old chat", started_at=1_714_000_000.0)
    _seed_session(tmp_path, "new", "new chat", started_at=1_714_000_001.0)
    rows = data_sessions.list_sessions(tmp_path, limit=1)
    assert [r["id"] for r in rows] == ["new"]


def test_list_sessions_exposes_first_and_last_turn_previews(tmp_path: Path) -> None:
    """first_user keeps the THREAD TOPIC (oldest turn); last_user / last_assistant track the MOST RECENT turn (mobile inbox preview)."""
    sid = "multi"
    p = tmp_path / "sessions" / f"{sid}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({
        "id": sid,
        "model": "openrouter/x",
        "started_at": 1_714_000_000.0,
        "turns": [
            {"at": 1_714_000_000.0, "user": "what is the weather", "assistant": "sunny"},
            {"at": 1_714_000_500.0, "user": "and tomorrow",        "assistant": "rain"},
        ],
    }), encoding="utf-8")

    row = next(r for r in data_sessions.list_sessions(tmp_path) if r["id"] == sid)
    assert row["first_user"] == "what is the weather"
    assert row["last_user"] == "and tomorrow"
    assert row["last_assistant"] == "rain"
    assert row["turn_count"] == 2


def test_list_sessions_first_equals_last_for_single_turn(tmp_path: Path) -> None:
    _seed_session(tmp_path, "single", "hola")
    row = next(r for r in data_sessions.list_sessions(tmp_path) if r["id"] == "single")
    assert row["first_user"] == "hola"
    assert row["last_user"] == "hola"
    assert row["last_assistant"] == "ok"


def test_list_sessions_handles_assistantless_last_turn(tmp_path: Path) -> None:
    """Mid-stream session: last turn missing the `assistant` key → `last_assistant` empty, `last_user` still surfaced."""
    sid = "mid"
    p = tmp_path / "sessions" / f"{sid}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({
        "id": sid,
        "model": "openrouter/x",
        "started_at": 1_714_000_000.0,
        "turns": [
            {"at": 1_714_000_000.0, "user": "hello", "assistant": "hi"},
            {"at": 1_714_000_500.0, "user": "siguiente pregunta"},
        ],
    }), encoding="utf-8")

    row = next(r for r in data_sessions.list_sessions(tmp_path) if r["id"] == sid)
    assert row["last_user"] == "siguiente pregunta"
    assert row["last_assistant"] == ""


def test_list_sessions_empty_turns_gives_empty_previews(tmp_path: Path) -> None:
    p = tmp_path / "sessions" / "empty.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({
        "id": "empty", "model": "x", "started_at": 1_714_000_000.0, "turns": [],
    }), encoding="utf-8")
    row = next(r for r in data_sessions.list_sessions(tmp_path) if r["id"] == "empty")
    assert row["first_user"] == ""
    assert row["last_user"] == ""
    assert row["last_assistant"] == ""


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


@pytest.mark.asyncio
async def test_session_read_marks_unfinished_from_the_persisted_flag_only(
    tmp_path: Path, monkeypatch,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    p = home / "sessions" / "mixed.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({
        "id": "mixed",
        "started_at": 1.0,
        "turns": [
            {"at": 1.0, "user": "hello", "assistant": "hi", "tools": []},
            {"at": 2.0, "user": "do research", "assistant": "", "tools": [
                {"at": 2.0, "name": "web_search", "args": {}, "result": "", "ok": True, "duration_s": 0.1},
            ]},
            {"at": 3.0, "user": "made a file", "assistant": "", "output_attachments": [{"path": "/p"}]},
            {"at": 4.0, "user": "in-flight stub", "assistant": "", "tools": []},
            {"at": 5.0, "user": "cut off mid-turn", "assistant": "", "tools": [], "interrupted": True},
        ],
    }), encoding="utf-8")
    srv = host_server.Server(home=home)
    data_handlers.register(srv)
    monkeypatch.setattr(data_handlers, "_resolve_home", lambda p: home)

    response = await srv._dispatch({
        "id": "r", "method": "host.session.read",
        "params": {"profile": "default", "id": "mixed"},
    })
    turns = response["result"]["session"]["turns"]
    assert turns[0]["unfinished"] is False
    # Tool-only reply with no closing text: completed normally, never interrupted.
    assert turns[1]["unfinished"] is False
    assert turns[2]["unfinished"] is False
    # The in-flight stub another client can read mid-turn must not read as interrupted.
    assert turns[3]["unfinished"] is False
    assert turns[4]["unfinished"] is True


def test_list_sessions_size_bytes_sums_main_and_sidecar(tmp_path: Path) -> None:
    p = _seed_session(tmp_path, "sized", "hello")
    sidecar = tmp_path / "sessions" / "_events_sized.jsonl"
    sidecar.write_text("x" * 1000, encoding="utf-8")
    row = next(r for r in data_sessions.list_sessions(tmp_path) if r["id"] == "sized")
    assert row["size_bytes"] == p.stat().st_size + 1000


def test_list_sessions_size_bytes_works_without_sidecar(tmp_path: Path) -> None:
    p = _seed_session(tmp_path, "lonely", "hello")
    row = next(r for r in data_sessions.list_sessions(tmp_path) if r["id"] == "lonely")
    assert row["size_bytes"] == p.stat().st_size


def _seed_large_session(home: Path, sid: str = "huge") -> Path:
    p = home / "sessions" / f"{sid}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = (
        '{"id":"%s","model":"openrouter/deepseek/deepseek-v4-flash",'
        '"started_at":1714000000.0,"input_tokens":123,'
        '"output_tokens":456,"cost_usd":0.078,"last_ctx_tokens":789,'
        '"turns":[{"at":1714000001.0,"user":"summarize this large session",'
        '"assistant":"%s"}]}'
    ) % (sid, "x" * (2 * 1024 * 1024 + 32))
    p.write_text(payload, encoding="utf-8")
    return p


def test_latest_chat_summary_handles_large_session_without_full_json_parse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    p = _seed_large_session(tmp_path, "huge")
    sidecar = tmp_path / "sessions" / "_events_huge.jsonl"
    sidecar.write_text("event\n", encoding="utf-8")
    original_loads = data_sessions.json.loads

    def bounded_loads(src: str, *args, **kwargs):
        if isinstance(src, str) and len(src) > 1_000_000:
            raise AssertionError("large session JSON was fully parsed")
        return original_loads(src, *args, **kwargs)

    monkeypatch.setattr(data_sessions.json, "loads", bounded_loads)

    row = data_sessions.latest_chat_summary(tmp_path)
    assert row is not None
    assert row["id"] == "huge"
    assert row["size_bytes"] == p.stat().st_size + sidecar.stat().st_size
    assert row["updated_at"] >= 1_714_000_000.0
    assert row["first_user"] == "summarize this large session"
    assert row["last_user"] == ""
    assert row["last_assistant"] == ""
    assert row["kind"] == "chat"
    assert row["input_tokens"] == 123
    assert row["output_tokens"] == 456
    assert row["cost_usd"] == pytest.approx(0.078)
    assert row["last_ctx_tokens"] == 789


def test_delete_session_removes_main_and_sidecar(tmp_path: Path) -> None:
    p = _seed_session(tmp_path, "doomed", "hi")
    sidecar = tmp_path / "sessions" / "_events_doomed.jsonl"
    sidecar.write_text("frame\n", encoding="utf-8")
    assert data_sessions.delete_session(tmp_path, "doomed") is True
    assert not p.exists()
    assert not sidecar.exists()


def test_delete_session_returns_false_when_missing(tmp_path: Path) -> None:
    (tmp_path / "sessions").mkdir(parents=True, exist_ok=True)
    assert data_sessions.delete_session(tmp_path, "ghost") is False


@pytest.mark.asyncio
async def test_sessions_delete_rpc_deletes_each_id(
    tmp_path: Path, monkeypatch,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    _seed_session(home, "a", "a")
    _seed_session(home, "b", "b")
    srv = host_server.Server(home=home)
    data_handlers.register(srv)
    monkeypatch.setattr(data_handlers, "_resolve_home", lambda p: home)

    response = await srv._dispatch({
        "id": "r", "method": "host.sessions.delete",
        "params": {"profile": "default", "ids": ["a", "b"]},
    })
    assert response["result"] == {"deleted": ["a", "b"], "errors": []}
    assert not (home / "sessions" / "a.json").exists()
    assert not (home / "sessions" / "b.json").exists()


@pytest.mark.asyncio
async def test_sessions_delete_rpc_refuses_busy_id(
    tmp_path: Path, monkeypatch,
) -> None:
    from alpi.host import chat as host_chat
    home = tmp_path / "home"
    home.mkdir()
    _seed_session(home, "busy", "hi")
    srv = host_server.Server(home=home)
    data_handlers.register(srv)
    monkeypatch.setattr(data_handlers, "_resolve_home", lambda p: home)
    monkeypatch.setitem(host_chat._session_active, host_chat.session_key("default", "busy"), object())

    response = await srv._dispatch({
        "id": "r", "method": "host.sessions.delete",
        "params": {"profile": "default", "ids": ["busy"]},
    })
    assert response["result"] == {
        "deleted": [],
        "errors": [{"id": "busy", "code": "session-busy"}],
    }
    assert (home / "sessions" / "busy.json").exists()


@pytest.mark.asyncio
async def test_sessions_delete_rpc_reports_missing(
    tmp_path: Path, monkeypatch,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    _seed_session(home, "real", "hi")
    srv = host_server.Server(home=home)
    data_handlers.register(srv)
    monkeypatch.setattr(data_handlers, "_resolve_home", lambda p: home)

    response = await srv._dispatch({
        "id": "r", "method": "host.sessions.delete",
        "params": {"profile": "default", "ids": ["real", "ghost"]},
    })
    assert response["result"]["deleted"] == ["real"]
    assert response["result"]["errors"] == [{"id": "ghost", "code": "not-found"}]


@pytest.mark.asyncio
async def test_sessions_delete_rpc_rejects_invalid_id(
    tmp_path: Path, monkeypatch,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    srv = host_server.Server(home=home)
    data_handlers.register(srv)
    monkeypatch.setattr(data_handlers, "_resolve_home", lambda p: home)

    response = await srv._dispatch({
        "id": "r", "method": "host.sessions.delete",
        "params": {"profile": "default", "ids": ["../etc/passwd"]},
    })
    assert response["result"]["deleted"] == []
    assert response["result"]["errors"] == [
        {"id": "../etc/passwd", "code": "invalid-id"},
    ]


@pytest.mark.asyncio
async def test_sessions_delete_rpc_requires_non_empty_ids(
    tmp_path: Path, monkeypatch,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    srv = host_server.Server(home=home)
    data_handlers.register(srv)
    monkeypatch.setattr(data_handlers, "_resolve_home", lambda p: home)

    response = await srv._dispatch({
        "id": "r", "method": "host.sessions.delete",
        "params": {"profile": "default", "ids": []},
    })
    assert response["error"]["message"] == "invalid-params"


@pytest.mark.asyncio
async def test_profile_summary_latest_session_includes_preview_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end: `host.profile.summaries` carries last_user + last_assistant under latest_session so the mobile inbox renders the preview without an extra RPC."""
    from alpi import config as cfg_mod
    from alpi.alp.keys import load_or_generate
    from alpi.host import device_state as host_device_state

    home = tmp_path / "h"
    home.mkdir()
    cfg = cfg_mod.Config(home=home, model="openai/gpt-5.4-mini")
    cfg_mod.save(cfg)
    load_or_generate(home)
    (home / "sessions").mkdir(exist_ok=True, parents=True)
    (home / "sessions" / "abc.json").write_text(json.dumps({
        "id": "abc",
        "started_at": 100.0,
        "turns": [
            {"at": 100.5, "user": "recuerdame X", "assistant": "listo te aviso"},
        ],
    }))
    monkeypatch.setattr(host_device_state.home_mod, "_ROOT", home)
    monkeypatch.setattr(data_handlers, "_resolve_home", lambda profile: home)

    srv = host_server.Server(home=home)
    host_device_state.register(srv)
    resp = await srv._dispatch({
        "id": "p", "method": "host.profile.summaries", "params": {},
    })
    latest = resp["result"]["profiles"][0]["latest_session"]
    assert latest["first_user"] == "recuerdame X"
    assert latest["last_assistant"] == "listo te aviso"


@pytest.mark.asyncio
async def test_profile_summaries_counts_large_sessions_without_full_parse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from alpi import config as cfg_mod
    from alpi.alp.keys import load_or_generate
    from alpi.host import device_state as host_device_state

    home = tmp_path / "h"
    home.mkdir()
    cfg_mod.save(cfg_mod.Config(home=home, model="openai/gpt-5.4-mini"))
    load_or_generate(home)
    _seed_large_session(home, "huge")
    d = home / "sessions"
    (d / "_events_huge.jsonl").write_text("event\n", encoding="utf-8")
    (d / "._huge.json").write_text("{}", encoding="utf-8")
    original_loads = data_sessions.json.loads

    def bounded_loads(src: str, *args, **kwargs):
        if isinstance(src, str) and len(src) > 1_000_000:
            raise AssertionError("large session JSON was fully parsed")
        return original_loads(src, *args, **kwargs)

    monkeypatch.setattr(data_sessions.json, "loads", bounded_loads)
    monkeypatch.setattr(host_device_state.home_mod, "_ROOT", home)
    monkeypatch.setattr(data_handlers, "_resolve_home", lambda profile: home)

    srv = host_server.Server(home=home)
    host_device_state.register(srv)
    resp = await srv._dispatch({
        "id": "p", "method": "host.profile.summaries", "params": {},
    })

    profile = resp["result"]["profiles"][0]
    assert profile["counts"]["sessions"] == 1
    assert profile["latest_session"]["id"] == "huge"
    assert profile["latest_session"]["first_user"] == "summarize this large session"
    assert profile["latest_session"]["last_assistant"] == ""

def test_list_sessions_serves_cached_rows_without_reparsing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_session(tmp_path, "aaa", "first chat")
    _seed_session(tmp_path, "bbb", "second chat")
    first = data_sessions.list_sessions(tmp_path)

    def no_parse(*_a, **_k):
        raise AssertionError("unchanged session was re-parsed")

    monkeypatch.setattr(data_sessions.json, "loads", no_parse)
    second = data_sessions.list_sessions(tmp_path)
    assert second == first


def test_row_cache_invalidates_when_session_file_changes(tmp_path: Path) -> None:
    p = _seed_session(tmp_path, "live", "hello")
    row = next(r for r in data_sessions.list_sessions(tmp_path) if r["id"] == "live")
    assert row["last_assistant"] == "ok"

    payload = json.loads(p.read_text(encoding="utf-8"))
    payload["turns"].append({"at": 1714000100.0, "user": "more", "assistant": "changed"})
    p.write_text(json.dumps(payload), encoding="utf-8")

    row = next(r for r in data_sessions.list_sessions(tmp_path) if r["id"] == "live")
    assert row["last_assistant"] == "changed"
    assert row["turn_count"] == 2


def test_row_cache_returns_copies_not_aliases(tmp_path: Path) -> None:
    _seed_session(tmp_path, "alias", "hello")
    first = next(r for r in data_sessions.list_sessions(tmp_path) if r["id"] == "alias")
    first["kind"] = "mutated"
    second = next(r for r in data_sessions.list_sessions(tmp_path) if r["id"] == "alias")
    assert second["kind"] == "chat"


def _seed_large_empty_session(home: Path, sid: str = "bigempty") -> Path:
    p = home / "sessions" / f"{sid}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    filler = "x" * (2 * 1024 * 1024 + 32)
    p.write_text(
        '{"id":"%s","started_at":1714000000.0,"filler":"%s","turns":[]}' % (sid, filler),
        encoding="utf-8",
    )
    return p


def test_large_default_kind_is_not_baked_into_the_cache(tmp_path: Path) -> None:
    _seed_large_empty_session(tmp_path)
    best = data_sessions.latest_chat_summary(tmp_path)
    assert best is not None and best["kind"] == "chat"
    row = next(r for r in data_sessions.list_sessions(tmp_path) if r["id"] == "bigempty")
    assert row["kind"] == "empty"
    best_again = data_sessions.latest_chat_summary(tmp_path)
    assert best_again is not None and best_again["kind"] == "chat"


def _seed_multi_turn(home: Path, sid: str = "multi3") -> Path:
    p = home / "sessions" / f"{sid}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({
        "id": sid,
        "started_at": 1.0,
        "turns": [
            {"at": 1.0, "user": "one", "assistant": "a1"},
            {"at": 2.0, "user": "two", "assistant": "a2"},
            {"at": 3.0, "user": "three", "assistant": "a3"},
        ],
    }), encoding="utf-8")
    return p


async def _read_rpc(home: Path, monkeypatch, params: dict) -> dict:
    srv = host_server.Server(home=home)
    data_handlers.register(srv)
    monkeypatch.setattr(data_handlers, "_resolve_home", lambda p: home)
    resp = await srv._dispatch({
        "id": "r", "method": "host.session.read",
        "params": {"profile": "default", **params},
    })
    return resp["result"]


@pytest.mark.asyncio
async def test_session_read_full_carries_total_turns_marker(
    tmp_path: Path, monkeypatch,
) -> None:
    _seed_multi_turn(tmp_path)
    result = await _read_rpc(tmp_path, monkeypatch, {"id": "multi3"})
    assert result["total_turns"] == 3
    assert result["turns_offset"] == 0
    assert [t["user"] for t in result["session"]["turns"]] == ["one", "two", "three"]


@pytest.mark.asyncio
async def test_session_read_in_flight_false_when_no_active_engine(
    tmp_path: Path, monkeypatch,
) -> None:
    _seed_multi_turn(tmp_path)
    result = await _read_rpc(tmp_path, monkeypatch, {"id": "multi3"})
    assert result["in_flight"] is False


@pytest.mark.asyncio
async def test_session_read_in_flight_true_while_a_turn_is_running(
    tmp_path: Path, monkeypatch,
) -> None:
    from alpi.host import chat as host_chat
    _seed_multi_turn(tmp_path)
    monkeypatch.setitem(host_chat._session_active, host_chat.session_key("default", "multi3"), object())
    result = await _read_rpc(tmp_path, monkeypatch, {"id": "multi3"})
    assert result["in_flight"] is True


@pytest.mark.asyncio
async def test_session_read_in_flight_ignores_same_session_id_on_another_profile(
    tmp_path: Path, monkeypatch,
) -> None:
    from alpi.host import chat as host_chat
    _seed_multi_turn(tmp_path)
    # A different profile's turn happens to share this session id — must not leak here.
    monkeypatch.setitem(host_chat._session_active, host_chat.session_key("other-profile", "multi3"), object())
    result = await _read_rpc(tmp_path, monkeypatch, {"id": "multi3"})
    assert result["in_flight"] is False


@pytest.mark.asyncio
async def test_session_read_after_turn_returns_only_new_turns(
    tmp_path: Path, monkeypatch,
) -> None:
    _seed_multi_turn(tmp_path)
    result = await _read_rpc(tmp_path, monkeypatch, {"id": "multi3", "after_turn": 1})
    assert result["total_turns"] == 3
    assert result["turns_offset"] == 1
    assert [t["user"] for t in result["session"]["turns"]] == ["two", "three"]
    assert all("unfinished" in t for t in result["session"]["turns"])


@pytest.mark.asyncio
async def test_session_read_after_turn_beyond_total_returns_empty(
    tmp_path: Path, monkeypatch,
) -> None:
    _seed_multi_turn(tmp_path)
    result = await _read_rpc(tmp_path, monkeypatch, {"id": "multi3", "after_turn": 99})
    assert result["total_turns"] == 3
    assert result["turns_offset"] == 3
    assert result["session"]["turns"] == []


@pytest.mark.asyncio
async def test_session_read_tail_turns_returns_last_n(
    tmp_path: Path, monkeypatch,
) -> None:
    _seed_multi_turn(tmp_path)
    result = await _read_rpc(tmp_path, monkeypatch, {"id": "multi3", "tail_turns": 1})
    assert result["total_turns"] == 3
    assert result["turns_offset"] == 2
    assert [t["user"] for t in result["session"]["turns"]] == ["three"]


@pytest.mark.asyncio
async def test_session_read_before_turn_with_max_turns_slices_older_chunk(
    tmp_path: Path, monkeypatch,
) -> None:
    _seed_multi_turn(tmp_path)
    result = await _read_rpc(
        tmp_path, monkeypatch, {"id": "multi3", "before_turn": 2, "max_turns": 1},
    )
    assert result["total_turns"] == 3
    assert result["turns_offset"] == 1
    assert [t["user"] for t in result["session"]["turns"]] == ["two"]


@pytest.mark.asyncio
async def test_session_read_before_turn_without_max_turns_returns_prefix(
    tmp_path: Path, monkeypatch,
) -> None:
    _seed_multi_turn(tmp_path)
    result = await _read_rpc(tmp_path, monkeypatch, {"id": "multi3", "before_turn": 2})
    assert result["turns_offset"] == 0
    assert [t["user"] for t in result["session"]["turns"]] == ["one", "two"]


@pytest.mark.asyncio
async def test_session_read_before_turn_beyond_total_clamps(
    tmp_path: Path, monkeypatch,
) -> None:
    _seed_multi_turn(tmp_path)
    result = await _read_rpc(
        tmp_path, monkeypatch, {"id": "multi3", "before_turn": 99, "max_turns": 2},
    )
    assert result["turns_offset"] == 1
    assert [t["user"] for t in result["session"]["turns"]] == ["two", "three"]


@pytest.mark.asyncio
async def test_session_read_after_turn_wins_over_before_turn(
    tmp_path: Path, monkeypatch,
) -> None:
    _seed_multi_turn(tmp_path)
    result = await _read_rpc(
        tmp_path, monkeypatch,
        {"id": "multi3", "after_turn": 2, "before_turn": 1, "max_turns": 1},
    )
    assert result["turns_offset"] == 2
    assert [t["user"] for t in result["session"]["turns"]] == ["three"]


@pytest.mark.asyncio
async def test_session_read_kind_classifies_pre_slice_first_turn(
    tmp_path: Path, monkeypatch,
) -> None:
    sid = "wgtail"
    p = tmp_path / "sessions" / f"{sid}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({
        "id": sid,
        "started_at": 1.0,
        "turns": [
            {"at": 1.0, "user": "[workgroup-poller] tick", "assistant": "a1"},
            {"at": 2.0, "user": "plain follow-up", "assistant": "a2"},
        ],
    }), encoding="utf-8")
    result = await _read_rpc(tmp_path, monkeypatch, {"id": sid, "tail_turns": 1})
    assert result["kind"] == "workgroup"
    assert [t["user"] for t in result["session"]["turns"]] == ["plain follow-up"]


@pytest.mark.asyncio
async def test_session_read_kind_chat_for_plain_sessions(
    tmp_path: Path, monkeypatch,
) -> None:
    _seed_multi_turn(tmp_path)
    result = await _read_rpc(tmp_path, monkeypatch, {"id": "multi3"})
    assert result["kind"] == "chat"


@pytest.mark.asyncio
async def test_session_read_runs_off_the_event_loop(
    tmp_path: Path, monkeypatch,
) -> None:
    import asyncio as _asyncio
    _seed_multi_turn(tmp_path)
    seen: list[str] = []
    real = _asyncio.to_thread

    async def spy(fn, *args, **kwargs):
        seen.append(getattr(fn, "__name__", ""))
        return await real(fn, *args, **kwargs)

    monkeypatch.setattr(data_handlers.asyncio, "to_thread", spy)
    result = await _read_rpc(tmp_path, monkeypatch, {"id": "multi3"})
    assert result["total_turns"] == 3
    assert "_load" in seen
