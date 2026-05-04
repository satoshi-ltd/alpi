"""Per-device pairing tokens — store, verbs, middleware."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from alpi.host import devices
from alpi.host import server as host_server


@pytest.fixture
def short_tmp(monkeypatch):
    d = Path(tempfile.mkdtemp(prefix="alp-host-devs-", dir="/tmp"))
    from alpi import home as home_mod
    monkeypatch.setattr(home_mod, "_ROOT", d)
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_empty_store_loads_empty(short_tmp: Path) -> None:
    assert devices.load() == []


def test_add_persists(short_tmp: Path) -> None:
    row = devices.add(label="iPhone")
    loaded = devices.load()
    assert len(loaded) == 1
    assert loaded[0]["token"] == row["token"]
    assert loaded[0]["label"] == "iPhone"


def test_is_valid_round_trip(short_tmp: Path) -> None:
    row = devices.add(label="x")
    assert devices.is_valid(row["token"])
    assert not devices.is_valid("nope")
    assert not devices.is_valid("")


def test_revoke(short_tmp: Path) -> None:
    row = devices.add(label="x")
    assert devices.revoke(row["token"]) is True
    assert devices.is_valid(row["token"]) is False
    assert devices.revoke(row["token"]) is False  # idempotent


def test_touch_updates_last_seen(short_tmp: Path) -> None:
    row = devices.add(label="x")
    assert row["last_seen"] is None
    devices.touch(row["token"])
    assert devices.load()[0]["last_seen"] is not None


def test_rename(short_tmp: Path) -> None:
    row = devices.add(label="pending")
    devices.rename(row["token"], "iPhone")
    assert devices.load()[0]["label"] == "iPhone"


@pytest.mark.asyncio
async def test_list_verb_redacts_token(short_tmp: Path) -> None:
    row = devices.add(label="iPhone")
    srv = host_server.Server(home=short_tmp)
    devices.register(srv)
    resp = await srv._dispatch({
        "id": "r", "method": "host.devices.list", "params": {},
    })
    assert "result" in resp
    listed = resp["result"]["devices"]
    assert len(listed) == 1
    assert listed[0]["label"] == "iPhone"
    assert listed[0]["token_id"] == row["token"][-8:]
    assert "token" not in listed[0]


@pytest.mark.asyncio
async def test_generate_verb_returns_full_token(short_tmp: Path) -> None:
    srv = host_server.Server(home=short_tmp)
    devices.register(srv)
    resp = await srv._dispatch({
        "id": "r",
        "method": "host.devices.generate",
        "params": {"label": "iPad"},
    })
    assert resp["result"]["token"]
    assert resp["result"]["label"] == "iPad"
    assert len(devices.load()) == 1


@pytest.mark.asyncio
async def test_revoke_verb(short_tmp: Path) -> None:
    row = devices.add(label="x")
    srv = host_server.Server(home=short_tmp)
    devices.register(srv)
    resp = await srv._dispatch({
        "id": "r",
        "method": "host.devices.revoke",
        "params": {"token_id": row["token"][-8:]},
    })
    assert resp["result"]["ok"]
    assert devices.load() == []


@pytest.mark.asyncio
async def test_revoke_unknown_returns_not_found(short_tmp: Path) -> None:
    srv = host_server.Server(home=short_tmp)
    devices.register(srv)
    resp = await srv._dispatch({
        "id": "r",
        "method": "host.devices.revoke",
        "params": {"token_id": "deadbeef"},
    })
    assert resp["error"]["code"] == -32004


def test_check_token_open_when_store_empty(short_tmp: Path) -> None:
    """Migration: empty store = open. Tailscale-only setups keep
    working until first Add device."""
    from alpi.host.server import _check_token

    assert _check_token({"params": {}}) is True
    assert _check_token({"params": {"auth_token": "anything"}}) is True


def test_check_token_enforces_once_store_has_entries(short_tmp: Path) -> None:
    from alpi.host.server import _check_token

    row = devices.add(label="x")
    assert _check_token({"params": {}}) is False
    assert _check_token({"params": {"auth_token": "wrong"}}) is False
    assert _check_token({"params": {"auth_token": row["token"]}}) is True


def test_check_token_touches_last_seen_on_match(short_tmp: Path) -> None:
    from alpi.host.server import _check_token

    row = devices.add(label="x")
    assert devices.load()[0]["last_seen"] is None
    _check_token({"params": {"auth_token": row["token"]}})
    assert devices.load()[0]["last_seen"] is not None
