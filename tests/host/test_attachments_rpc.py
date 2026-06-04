from __future__ import annotations

import base64
from pathlib import Path

import pytest

from alpi import attachments as att
from alpi.host import attachments_rpc
from alpi.host import server as host_server

PNG = b"\x89PNG\r\n\x1a\nstaged-bytes"


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


async def _stage(srv, **params):
    return await srv._dispatch({
        "id": "s", "method": "host.attachments.stage", "params": params,
    })


@pytest.mark.asyncio
async def test_stage_writes_sanitized_file(tmp_path, monkeypatch):
    from alpi import home as home_mod
    monkeypatch.setattr(home_mod, "_ROOT", tmp_path)
    srv = host_server.Server(home=tmp_path)
    attachments_rpc.register(srv)

    resp = await _stage(
        srv, profile="default", name="../../e vil name.png",
        mime="image/png", data_base64=_b64(PNG),
    )
    a = resp["result"]["attachment"]
    assert resp["result"]["ok"] is True
    assert a["mime"] == "image/png"
    assert a["size"] == len(PNG)
    assert "/" not in a["name"] and a["name"].endswith(".png")
    assert "attachments/tmp" in a["path"]
    assert Path(a["path"]).read_bytes() == PNG


@pytest.mark.asyncio
async def test_stage_accepts_text(tmp_path, monkeypatch):
    from alpi import home as home_mod
    monkeypatch.setattr(home_mod, "_ROOT", tmp_path)
    srv = host_server.Server(home=tmp_path)
    attachments_rpc.register(srv)
    resp = await _stage(srv, profile="default", name="notes.md", mime="text/markdown",
                        data_base64=_b64(b"# Heading\n\nsome notes"))
    assert resp["result"]["ok"] is True
    assert resp["result"]["attachment"]["mime"] == "text/markdown"


@pytest.mark.asyncio
async def test_stage_validates_content_like_send(tmp_path, monkeypatch):
    from alpi import home as home_mod
    monkeypatch.setattr(home_mod, "_ROOT", tmp_path)
    srv = host_server.Server(home=tmp_path)
    attachments_rpc.register(srv)
    resp = await _stage(srv, profile="default", name="fake.png", mime="image/png",
                        data_base64=_b64(b"definitely not a png"))
    assert resp["error"]["code"] == -32602
    tmp_root = tmp_path / "host" / "attachments" / "tmp"
    assert (not tmp_root.exists()) or not list(tmp_root.iterdir())


@pytest.mark.asyncio
async def test_stage_rejects_unsupported_mime(tmp_path, monkeypatch):
    from alpi import home as home_mod
    monkeypatch.setattr(home_mod, "_ROOT", tmp_path)
    srv = host_server.Server(home=tmp_path)
    attachments_rpc.register(srv)
    resp = await _stage(srv, profile="default", name="x.zip", mime="application/zip", data_base64=_b64(b"x"))
    assert resp["error"]["code"] == -32602


@pytest.mark.asyncio
async def test_stage_rejects_oversize(tmp_path, monkeypatch):
    from alpi import home as home_mod
    monkeypatch.setattr(home_mod, "_ROOT", tmp_path)
    monkeypatch.setattr(att, "MAX_FILE_BYTES", 4)
    srv = host_server.Server(home=tmp_path)
    attachments_rpc.register(srv)
    resp = await _stage(srv, profile="default", name="x.png", mime="image/png", data_base64=_b64(PNG))
    assert resp["error"]["code"] == -32602
    assert "cap" in resp["error"]["message"]


@pytest.mark.asyncio
async def test_stage_uses_lower_cap_for_text(tmp_path, monkeypatch):
    from alpi import home as home_mod
    monkeypatch.setattr(home_mod, "_ROOT", tmp_path)
    monkeypatch.setattr(att, "MAX_TEXT_FILE_BYTES", 4)
    srv = host_server.Server(home=tmp_path)
    attachments_rpc.register(srv)
    resp = await _stage(srv, profile="default", name="a.txt", mime="text/plain",
                        data_base64=_b64(b"this text is well over four bytes"))
    assert resp["error"]["code"] == -32602
    assert "cap" in resp["error"]["message"]


@pytest.mark.asyncio
async def test_stage_rejects_bad_base64(tmp_path, monkeypatch):
    from alpi import home as home_mod
    monkeypatch.setattr(home_mod, "_ROOT", tmp_path)
    srv = host_server.Server(home=tmp_path)
    attachments_rpc.register(srv)
    resp = await _stage(srv, profile="default", name="x.png", mime="image/png", data_base64="not base64 ###")
    assert resp["error"]["code"] == -32602
