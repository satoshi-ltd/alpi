"""Server-level guarantees (param validation, error envelopes) that bypass any individual handler."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

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
