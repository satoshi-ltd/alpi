"""host.outputs.* — list / read / mark_read / mark_all_read verbs."""

from __future__ import annotations

from pathlib import Path

import pytest

from alpi import outputs as outputs_mod
from alpi.host import handlers as data_handlers
from alpi.host import outputs as host_outputs
from alpi.host import server as host_server


def _seed(home: Path, **overrides) -> dict:
    base = dict(profile="default", source="send_message", body="b")
    base.update(overrides)
    return outputs_mod.append(home, **base)


def _bind(monkeypatch, home: Path) -> host_server.Server:
    monkeypatch.setattr(data_handlers, "_resolve_home", lambda p: home)
    srv = host_server.Server(home=home)
    host_outputs.register(srv)
    return srv


@pytest.mark.asyncio
async def test_list_returns_outputs(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "h"
    home.mkdir()
    a = _seed(home, body="first")
    b = _seed(home, body="second")
    srv = _bind(monkeypatch, home)

    resp = await srv._dispatch({
        "id": "r", "method": "host.outputs.list",
        "params": {"profile": "default"},
    })
    rows = resp["result"]["outputs"]
    assert [it["id"] for it in rows] == [b["id"], a["id"]]


@pytest.mark.asyncio
async def test_list_filters_by_status(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "h"
    home.mkdir()
    a = _seed(home, body="a")
    _seed(home, body="b")
    outputs_mod.mark_read(home, a["id"])
    srv = _bind(monkeypatch, home)

    resp = await srv._dispatch({
        "id": "r", "method": "host.outputs.list",
        "params": {"profile": "default", "status": "unread"},
    })
    rows = resp["result"]["outputs"]
    assert [it["body"] for it in rows] == ["b"]


@pytest.mark.asyncio
async def test_list_rejects_unknown_status(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "h"
    home.mkdir()
    srv = _bind(monkeypatch, home)

    resp = await srv._dispatch({
        "id": "r", "method": "host.outputs.list",
        "params": {"profile": "default", "status": "wibble"},
    })
    assert resp["error"]["message"] == "invalid-params"


@pytest.mark.asyncio
async def test_read_returns_record(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "h"
    home.mkdir()
    out = _seed(home, body="hi")
    srv = _bind(monkeypatch, home)

    resp = await srv._dispatch({
        "id": "r", "method": "host.outputs.read",
        "params": {"profile": "default", "id": out["id"]},
    })
    assert resp["result"]["output"]["id"] == out["id"]


@pytest.mark.asyncio
async def test_read_missing_returns_not_found(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "h"
    home.mkdir()
    srv = _bind(monkeypatch, home)

    resp = await srv._dispatch({
        "id": "r", "method": "host.outputs.read",
        "params": {"profile": "default", "id": "deadbeefcafe"},
    })
    assert resp["error"]["message"] == "not-found"


@pytest.mark.asyncio
async def test_read_rejects_bad_id(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "h"
    home.mkdir()
    srv = _bind(monkeypatch, home)

    resp = await srv._dispatch({
        "id": "r", "method": "host.outputs.read",
        "params": {"profile": "default", "id": "../etc/passwd"},
    })
    assert resp["error"]["message"] == "invalid-params"


@pytest.mark.asyncio
async def test_mark_read_flips_status(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "h"
    home.mkdir()
    out = _seed(home, body="hi")
    srv = _bind(monkeypatch, home)

    resp = await srv._dispatch({
        "id": "r", "method": "host.outputs.mark_read",
        "params": {"profile": "default", "id": out["id"]},
    })
    assert resp["result"]["ok"] is True
    assert outputs_mod.read(home, out["id"])["status"] == "read"


@pytest.mark.asyncio
async def test_mark_read_emits_output_updated(tmp_path: Path, monkeypatch) -> None:
    """mark_read emits output.updated so other paired surfaces refresh."""
    home = tmp_path / "h"
    home.mkdir()
    out = _seed(home, body="hi")
    captured: list = []
    from alpi.host import events as host_events
    monkeypatch.setattr(
        host_events, "emit",
        lambda kind, data=None: captured.append((kind, dict(data or {}))),
    )
    srv = _bind(monkeypatch, home)

    await srv._dispatch({
        "id": "r", "method": "host.outputs.mark_read",
        "params": {"profile": "default", "id": out["id"]},
    })
    updated = [d for k, d in captured if k == "output.updated"]
    assert len(updated) == 1
    assert updated[0] == {"profile": "default", "id": out["id"], "status": "read"}


@pytest.mark.asyncio
async def test_archive_verb_is_not_registered(tmp_path: Path, monkeypatch) -> None:
    """archive verb is removed — host plane must reject it."""
    home = tmp_path / "h"
    home.mkdir()
    out = _seed(home, body="hi")
    srv = _bind(monkeypatch, home)

    resp = await srv._dispatch({
        "id": "r", "method": "host.outputs.archive",
        "params": {"profile": "default", "id": out["id"]},
    })
    assert resp["error"]["message"] == "method-not-found"


@pytest.mark.asyncio
async def test_mark_all_read_flips_every_unread(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "h"
    home.mkdir()
    a = _seed(home, body="a")
    _seed(home, body="b")
    _seed(home, body="c")
    outputs_mod.mark_read(home, a["id"])
    srv = _bind(monkeypatch, home)

    resp = await srv._dispatch({
        "id": "r", "method": "host.outputs.mark_all_read",
        "params": {"profile": "default"},
    })
    assert resp["result"] == {"ok": True, "count": 2}
    assert outputs_mod.list_outputs(home, status="unread") == []


@pytest.mark.asyncio
async def test_mark_all_read_emits_output_updated_with_count(
    tmp_path: Path, monkeypatch,
) -> None:
    """mark_all_read with count>0 emits output.updated."""
    home = tmp_path / "h"
    home.mkdir()
    _seed(home, body="a")
    _seed(home, body="b")
    captured: list = []
    from alpi.host import events as host_events
    monkeypatch.setattr(
        host_events, "emit",
        lambda kind, data=None: captured.append((kind, dict(data or {}))),
    )
    srv = _bind(monkeypatch, home)

    await srv._dispatch({
        "id": "r", "method": "host.outputs.mark_all_read",
        "params": {"profile": "default"},
    })
    updated = [d for k, d in captured if k == "output.updated"]
    assert updated == [{"profile": "default", "action": "mark_all_read", "count": 2}]


@pytest.mark.asyncio
async def test_mark_all_read_zero_count_does_not_emit(
    tmp_path: Path, monkeypatch,
) -> None:
    """count=0 → no event broadcast."""
    home = tmp_path / "h"
    home.mkdir()
    captured: list = []
    from alpi.host import events as host_events
    monkeypatch.setattr(
        host_events, "emit",
        lambda kind, data=None: captured.append((kind, dict(data or {}))),
    )
    srv = _bind(monkeypatch, home)

    await srv._dispatch({
        "id": "r", "method": "host.outputs.mark_all_read",
        "params": {"profile": "default"},
    })
    assert [k for k, _ in captured if k == "output.updated"] == []


@pytest.mark.asyncio
async def test_mark_all_read_zero_when_inbox_clean(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "h"
    home.mkdir()
    srv = _bind(monkeypatch, home)

    resp = await srv._dispatch({
        "id": "r", "method": "host.outputs.mark_all_read",
        "params": {"profile": "default"},
    })
    assert resp["result"] == {"ok": True, "count": 0}
