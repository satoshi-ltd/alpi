"""Server-level guarantees (param validation, error envelopes) that bypass any individual handler."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest
import websockets

from alpi.host import server as host_server


@pytest.mark.asyncio
async def test_invalid_params_type_returns_minus_32602(tmp_path: Path) -> None:
    """A handler that assumes `params` is a dict must never see an array/string body — the server normalises at the door and returns invalid-params."""
    srv = host_server.Server(home=tmp_path)
    sent: list[dict] = []
    async def send(payload: dict) -> None:
        sent.append(payload)

    body = json.dumps({"id": "r", "method": "host.profile.summaries", "params": ["bad"]})
    await srv._handle_request(body, send)

    assert sent and sent[0]["error"]["code"] == -32602
    assert sent[0]["error"]["message"] == "invalid-params"


@pytest.mark.asyncio
async def test_missing_params_is_fine(tmp_path: Path) -> None:
    """Most handlers tolerate missing `params` — null/absent must NOT be rejected."""
    srv = host_server.Server(home=tmp_path)

    async def echo(_params, _server):
        return {"ok": True}

    srv.register("host.test.echo", echo)

    sent: list[dict] = []
    async def send(payload: dict) -> None:
        sent.append(payload)

    body = json.dumps({"id": "r", "method": "host.test.echo"})
    await srv._handle_request(body, send)

    assert sent and sent[0].get("result") == {"ok": True}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exc",
    [
        websockets.ConnectionClosed(None, None),
        ConnectionResetError(),
        BrokenPipeError(),
    ],
)
async def test_stream_client_disconnect_is_swallowed(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, exc: Exception,
) -> None:
    srv = host_server.Server(home=tmp_path)

    async def hung_up(_params, _server, _send_frame):
        raise exc

    srv.register_stream("host.test.stream", hung_up)

    sent: list[dict] = []
    async def send(payload: dict) -> None:
        sent.append(payload)

    body = json.dumps({"id": "r", "method": "host.test.stream"})
    with caplog.at_level(logging.ERROR):
        await srv._handle_request(body, send)

    assert sent == []
    assert "crashed" not in caplog.text


@pytest.mark.asyncio
async def test_stream_real_crash_still_reports_internal_error(tmp_path: Path) -> None:
    srv = host_server.Server(home=tmp_path)

    async def boom(_params, _server, _send_frame):
        raise RuntimeError("kaboom")

    srv.register_stream("host.test.stream", boom)

    sent: list[dict] = []
    async def send(payload: dict) -> None:
        sent.append(payload)

    body = json.dumps({"id": "r", "method": "host.test.stream"})
    await srv._handle_request(body, send)

    assert sent and sent[0]["error"]["code"] == -32603

@pytest.mark.asyncio
async def test_remote_token_validation_runs_off_the_event_loop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import threading
    seen: dict = {}

    def fake_check(body):
        seen["thread"] = threading.current_thread()
        return True, "admin", []

    monkeypatch.setattr(host_server, "_check_token_meta", fake_check)
    srv = host_server.Server(home=tmp_path)

    async def echo(_params, _server):
        return {"ok": True}

    srv.register("host.test.echo", echo)
    sent: list[dict] = []

    async def send(payload: dict) -> None:
        sent.append(payload)

    body = json.dumps({"id": "r", "method": "host.test.echo", "params": {"auth_token": "t" * 32}})
    await srv._handle_request(body, send, require_token=True)

    assert sent and sent[0].get("result") == {"ok": True}
    assert seen["thread"] is not threading.main_thread()

def _member(scope):
    def _fake(_body):
        return True, "member", scope
    return _fake


def _admin():
    def _fake(_body):
        return True, "admin", []
    return _fake


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["host.config.set_field", "host.config.unset_field"])
@pytest.mark.parametrize(
    "key", ["alp.tcp_port", "host.tcp_port", "host.allow_public_bind", "network.host"],
)
async def test_config_field_local_only_key_blocked_over_remote(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, method: str, key: str,
) -> None:
    monkeypatch.setattr(host_server, "_check_token_meta", _admin())
    srv = host_server.Server(home=tmp_path)
    reached = {"n": 0}

    async def stub(_params, _server):
        reached["n"] += 1
        return {"ok": True}

    srv.register(method, stub)
    sent: list[dict] = []

    async def send(p):
        sent.append(p)

    body = json.dumps({"id": "r", "method": method,
                       "params": {"auth_token": "t", "profile": "default", "key": key, "value": "true"}})
    await srv._handle_request(body, send, require_token=True)
    assert sent[0]["error"]["message"] == "forbidden"
    assert sent[0]["error"]["data"]["detail"] == "config key is local-only"
    assert reached["n"] == 0


@pytest.mark.asyncio
async def test_config_set_field_normal_key_passes_gate_over_remote(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(host_server, "_check_token_meta", _admin())
    srv = host_server.Server(home=tmp_path)
    reached = {"n": 0}

    async def stub(_params, _server):
        reached["n"] += 1
        return {"ok": True}

    srv.register("host.config.set_field", stub)
    sent: list[dict] = []

    async def send(p):
        sent.append(p)

    body = json.dumps({"id": "r", "method": "host.config.set_field",
                       "params": {"auth_token": "t", "profile": "default", "key": "model", "value": "x"}})
    await srv._handle_request(body, send, require_token=True)
    assert reached["n"] == 1
    assert sent[0].get("result") == {"ok": True}


@pytest.mark.asyncio
async def test_config_set_field_local_only_key_allowed_over_unix_socket(
    tmp_path: Path,
) -> None:
    srv = host_server.Server(home=tmp_path)
    reached = {"n": 0}

    async def stub(_params, _server):
        reached["n"] += 1
        return {"ok": True}

    srv.register("host.config.set_field", stub)
    sent: list[dict] = []

    async def send(p):
        sent.append(p)

    body = json.dumps({"id": "r", "method": "host.config.set_field",
                       "params": {"profile": "default", "key": "host.tcp_port", "value": "7423"}})
    await srv._handle_request(body, send)  # no token = local socket
    assert reached["n"] == 1


@pytest.mark.asyncio
async def test_clarification_respond_scoped_member_out_of_scope_blocked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(host_server, "_check_token_meta", _member(["allowed"]))
    monkeypatch.setattr("alpi.host.clarification.pending_profile", lambda rid: "other")
    srv = host_server.Server(home=tmp_path)
    reached = {"n": 0}

    async def stub(_params, _server):
        reached["n"] += 1
        return {"ok": True}

    srv.register("host.clarification.respond", stub)
    sent: list[dict] = []

    async def send(p):
        sent.append(p)

    body = json.dumps({"id": "r", "method": "host.clarification.respond",
                       "params": {"auth_token": "t", "request_id": "abc", "choice": "A"}})
    await srv._handle_request(body, send, require_token=True)
    assert reached["n"] == 0
    assert sent[0]["error"]["data"]["detail"] == "profile not in device scope"


@pytest.mark.asyncio
async def test_clarification_respond_scoped_member_in_scope_allowed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(host_server, "_check_token_meta", _member(["allowed"]))
    monkeypatch.setattr("alpi.host.clarification.pending_profile", lambda rid: "allowed")
    srv = host_server.Server(home=tmp_path)
    reached = {"n": 0}

    async def stub(_params, _server):
        reached["n"] += 1
        return {"ok": True}

    srv.register("host.clarification.respond", stub)
    sent: list[dict] = []

    async def send(p):
        sent.append(p)

    body = json.dumps({"id": "r", "method": "host.clarification.respond",
                       "params": {"auth_token": "t", "request_id": "abc", "choice": "A"}})
    await srv._handle_request(body, send, require_token=True)
    assert reached["n"] == 1


@pytest.mark.asyncio
async def test_clarification_respond_scoped_member_unknown_id_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(host_server, "_check_token_meta", _member(["allowed"]))
    monkeypatch.setattr("alpi.host.clarification.pending_profile", lambda rid: None)
    srv = host_server.Server(home=tmp_path)

    async def stub(_params, _server):
        return {"ok": True}

    srv.register("host.clarification.respond", stub)
    sent: list[dict] = []

    async def send(p):
        sent.append(p)

    body = json.dumps({"id": "r", "method": "host.clarification.respond",
                       "params": {"auth_token": "t", "request_id": "ghost", "choice": "A"}})
    await srv._handle_request(body, send, require_token=True)
    assert sent[0]["error"]["message"] == "forbidden"


@pytest.mark.asyncio
async def test_clarification_respond_unscoped_member_allowed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(host_server, "_check_token_meta", _member([]))  # empty scope = all
    srv = host_server.Server(home=tmp_path)
    reached = {"n": 0}

    async def stub(_params, _server):
        reached["n"] += 1
        return {"ok": True}

    srv.register("host.clarification.respond", stub)
    sent: list[dict] = []

    async def send(p):
        sent.append(p)

    body = json.dumps({"id": "r", "method": "host.clarification.respond",
                       "params": {"auth_token": "t", "request_id": "abc", "choice": "A"}})
    await srv._handle_request(body, send, require_token=True)
    assert reached["n"] == 1
