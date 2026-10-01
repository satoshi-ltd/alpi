from __future__ import annotations

import json
from pathlib import Path

import pytest
import websockets
import yaml

from alpi.alp.rate_limit import RateLimiter
from alpi.host import connections
from tests.host.test_tcp_listener import _start_security_test_server, _ws_request, short_tmp  # noqa: F401


async def _attempt(url: str, token: str) -> tuple[dict | None, int | None, str | None]:
    async with websockets.connect(url) as ws:
        try:
            await ws.send(_ws_request(token))
            reply = json.loads(await ws.recv())
        except websockets.ConnectionClosed:
            return None, ws.close_code, ws.close_reason
        try:
            await ws.recv()
        except websockets.ConnectionClosed:
            pass
        return reply, ws.close_code, ws.close_reason


def _limits(server, device_limit: int, address_limit: int = 100) -> None:
    server._ws_auth_failures = RateLimiter(default_per_minute=address_limit)
    server._ws_device_failures = RateLimiter(default_per_minute=device_limit)


@pytest.mark.asyncio
async def test_a_revoked_device_retrying_is_throttled_while_another_device_keeps_connecting(short_tmp, monkeypatch) -> None:
    connections.invalidate_cache()
    server, url = await _start_security_test_server(short_tmp, monkeypatch)
    _limits(server, device_limit=3)
    row, revoked = connections.create_connection("Web")
    _row, healthy = connections.add_device(row["id"])
    assert connections.revoke_device(row["id"], revoked["id"])
    try:
        outcomes = [await _attempt(url, revoked["token"]) for _ in range(8)]

        assert outcomes[0][0]["error"]["data"] == {"reason": "device-revoked"}
        assert [code for _reply, code, _why in outcomes[:3]] == [1008, 1008, 1008]
        assert all(code == 1013 and why == "auth-rate-limited" for _r, code, why in outcomes[3:])
        async with websockets.connect(url) as ws:
            await ws.send(_ws_request(healthy["token"]))
            assert "result" in json.loads(await ws.recv())
        assert server.websocket_status()["auth_rate_limited"] == 5
        assert not server._ws_auth_failures.exceeded("127.0.0.1")
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_anonymous_failures_still_close_the_address(short_tmp, monkeypatch) -> None:
    connections.invalidate_cache()
    server, url = await _start_security_test_server(short_tmp, monkeypatch)
    _limits(server, device_limit=50, address_limit=2)
    _row, healthy = connections.create_connection("Web")
    try:
        await _attempt(url, "unknown-token-1")
        await _attempt(url, "unknown-token-2")

        reply, code, why = await _attempt(url, healthy["token"])

        assert reply is None and code == 1013 and why == "auth-rate-limited"
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_a_disabled_connections_devices_are_counted_one_by_one(short_tmp, monkeypatch) -> None:
    connections.invalidate_cache()
    server, url = await _start_security_test_server(short_tmp, monkeypatch)
    _limits(server, device_limit=2)
    row, first = connections.create_connection("Web")
    _row, second = connections.add_device(row["id"])
    assert connections.update_connection(row["id"], status="disabled")
    try:
        for _ in range(2):
            reply, _code, _why = await _attempt(url, first["token"])
            assert reply["error"]["data"] == {"reason": "connection-disabled"}
        reply, code, why = await _attempt(url, first["token"])
        assert reply is None and code == 1013 and why == "auth-rate-limited"

        reply, code, _why = await _attempt(url, second["token"])
        assert reply["error"]["data"] == {"reason": "connection-disabled"}
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_an_expired_token_counts_against_its_own_device(short_tmp, monkeypatch) -> None:
    connections.invalidate_cache()
    server, url = await _start_security_test_server(short_tmp, monkeypatch)
    _limits(server, device_limit=1)
    _row, device = connections.create_connection("Web")
    monkeypatch.setattr(connections, "device_expired", lambda *a, **k: True)
    try:
        reply, _code, _why = await _attempt(url, device["token"])
        assert reply["error"]["data"] == {"reason": "token-expired"}
        reply, code, why = await _attempt(url, device["token"])
        assert reply is None and code == 1013 and why == "auth-rate-limited"
        assert not server._ws_auth_failures.exceeded("127.0.0.1")
    finally:
        await server.stop()


def test_a_revoked_token_is_recognised_without_storing_the_token(tmp_path: Path, monkeypatch) -> None:
    from alpi import home

    monkeypatch.setattr(home, "_ROOT", tmp_path)
    connections.invalidate_cache()
    row, device = connections.create_connection("Web")
    assert connections.revoke_device(row["id"], device["id"])
    connections.invalidate_cache()

    result = connections.authenticate(device["token"])

    assert result.valid is False
    assert result.reason == "device-revoked"
    assert result.device_id == device["id"]
    assert result.connection_id == row["id"]
    assert device["token"] not in connections.store_path().read_text()
    assert connections.authenticate("some-other-token").reason == ""


def test_a_deleted_connections_tokens_read_as_revoked(tmp_path: Path, monkeypatch) -> None:
    from alpi import home

    monkeypatch.setattr(home, "_ROOT", tmp_path)
    connections.invalidate_cache()
    row, device = connections.create_connection("Web")
    assert connections.delete_connection(row["id"])
    connections.invalidate_cache()

    assert connections.authenticate(device["token"]).reason == "device-revoked"


@pytest.mark.asyncio
async def test_a_revoked_device_attempt_is_audited_by_device(short_tmp, monkeypatch) -> None:
    from alpi.host import admin_audit

    connections.invalidate_cache()
    server, url = await _start_security_test_server(short_tmp, monkeypatch)
    _limits(server, device_limit=10)
    row, device = connections.create_connection("Web")
    assert connections.revoke_device(row["id"], device["id"])
    try:
        await _attempt(url, device["token"])

        entries = admin_audit.list_entries(
            server.home, connection_id=row["id"], device_id=device["id"], result="denied",
        )["entries"]
        assert len(entries) == 1
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_varying_the_method_does_not_multiply_audit_rows(short_tmp, monkeypatch) -> None:
    from alpi.host import admin_audit

    connections.invalidate_cache()
    server, url = await _start_security_test_server(short_tmp, monkeypatch)
    _limits(server, device_limit=50)
    row, device = connections.create_connection("Web")
    assert connections.revoke_device(row["id"], device["id"])
    try:
        for method in ("host.version", "host.chat.send", "host.sessions.list"):
            async with websockets.connect(url) as ws:
                await ws.send(json.dumps({
                    "id": "1", "method": method, "params": {"auth_token": device["token"]},
                }))
                await ws.recv()

        entries = admin_audit.list_entries(
            server.home, connection_id=row["id"], device_id=device["id"], result="denied",
        )["entries"]
        assert len(entries) == 1
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_a_device_revoked_before_tokens_were_kept_still_counts_per_address(short_tmp, monkeypatch) -> None:
    connections.invalidate_cache()
    server, url = await _start_security_test_server(short_tmp, monkeypatch)
    _limits(server, device_limit=50, address_limit=2)
    row, device = connections.create_connection("Web")
    assert connections.revoke_device(row["id"], device["id"])
    store = connections.store_path()
    data = yaml.safe_load(store.read_text())
    for connection in data["connections"]:
        for stored in connection["devices"]:
            stored["revoked_token_hash"] = ""
    store.write_text(yaml.safe_dump(data))
    connections.invalidate_cache()
    try:
        outcomes = [await _attempt(url, device["token"]) for _ in range(4)]

        assert [code for _reply, code, _why in outcomes[:2]] == [1008, 1008]
        assert all(code == 1013 for _reply, code, _why in outcomes[2:])
        assert server._ws_auth_failures.exceeded("127.0.0.1")
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_two_devices_of_one_connection_are_counted_apart(short_tmp, monkeypatch) -> None:
    connections.invalidate_cache()
    server, url = await _start_security_test_server(short_tmp, monkeypatch)
    _limits(server, device_limit=2)
    row, first = connections.create_connection("Web")
    _row, second = connections.add_device(row["id"])
    assert connections.revoke_device(row["id"], first["id"])
    assert connections.revoke_device(row["id"], second["id"])
    try:
        for _ in range(3):
            await _attempt(url, first["token"])
        reply, code, _why = await _attempt(url, second["token"])

        assert code == 1008
        assert reply["error"]["data"] == {"reason": "device-revoked"}
    finally:
        await server.stop()
