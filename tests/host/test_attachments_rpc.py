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


async def _fetch(srv, **params):
    return await srv._dispatch({
        "id": "f", "method": "host.attachments.fetch", "params": params,
    })


@pytest.mark.asyncio
async def test_fetch_returns_image_base64(tmp_path, monkeypatch):
    from alpi import home as home_mod
    monkeypatch.setattr(home_mod, "_ROOT", tmp_path)
    srv = host_server.Server(home=tmp_path)
    attachments_rpc.register(srv)
    img = tmp_path / "hero.png"
    img.write_bytes(PNG)
    resp = await _fetch(srv, profile="default", path=str(img))
    r = resp["result"]
    assert r["mime"] == "image/png"
    assert r["name"] == "hero.png"
    assert base64.b64decode(r["data_base64"]) == PNG


@pytest.mark.asyncio
async def test_fetch_rejects_non_image(tmp_path, monkeypatch):
    from alpi import home as home_mod
    monkeypatch.setattr(home_mod, "_ROOT", tmp_path)
    srv = host_server.Server(home=tmp_path)
    attachments_rpc.register(srv)
    resp = await _fetch(srv, profile="default", path=str(tmp_path / "notes.txt"))
    assert resp["error"]["code"] == -32602


@pytest.mark.asyncio
async def test_fetch_not_found(tmp_path, monkeypatch):
    from alpi import home as home_mod
    monkeypatch.setattr(home_mod, "_ROOT", tmp_path)
    srv = host_server.Server(home=tmp_path)
    attachments_rpc.register(srv)
    resp = await _fetch(srv, profile="default", path="/tmp/alpi-no-such-image-zzz.png")
    assert resp["error"]["code"] == -32004


def test_fetch_allowed_rejects_outside_roots(tmp_path):
    # A real file outside workspace/home/temp must be refused.
    assert not attachments_rpc._fetch_allowed(tmp_path / "home", Path("/etc/hosts").resolve())


def test_fetch_allowed_includes_profile_workspace(tmp_path, monkeypatch):
    # The real web-factory case: a workspace outside ~/.alpi must be served.
    from types import SimpleNamespace
    from alpi import config as cfg_mod

    target = Path("/etc/hosts").resolve()
    monkeypatch.setattr(cfg_mod, "load", lambda h: SimpleNamespace(workspace_path=None))
    assert not attachments_rpc._fetch_allowed(tmp_path / "home", target)
    monkeypatch.setattr(cfg_mod, "load", lambda h: SimpleNamespace(workspace_path=Path("/etc")))
    assert attachments_rpc._fetch_allowed(tmp_path / "home", target)
