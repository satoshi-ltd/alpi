"""Tests for ``host.workgroup.transcript``."""

from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
from pathlib import Path

import pytest

from alpi.host import server as host_server
from alpi.alp import workgroup as wg_mod
from alpi.alp.keys import load_or_generate
from alpi.host import handlers as data_handlers
from alpi.host import workgroup as data_workgroup


@pytest.fixture
def short_tmp() -> Path:
    d = Path(tempfile.mkdtemp(prefix="alp-data-", dir="/tmp"))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


def _seed_workgroup_with_one_post(home: Path, body: bytes) -> str:
    """Create a local workgroup transcript with one post."""
    home.mkdir(exist_ok=True)
    kp = load_or_generate(home)
    wg = wg_mod.create(
        home,
        name="test-wg",
        hub_kp=kp,
        member_pubkeys=[],
        briefing="",
    )
    me = wg.member(kp.pubkey_b64())
    assert me is not None, "hub must be member of its own workgroup"
    group_key = wg_mod.open_sealed_group_key(me.sealed_key, kp)
    nonce_b64, ct_b64 = wg_mod.encrypt_post(group_key, body)
    d = home / "alp" / "workgroups" / wg.meta.id
    entry = {
        "seq": 1,
        "ts": "2026-05-01T00:00:00Z",
        "from": kp.pubkey_b64(),
        "key_version": me.key_version,
        "nonce": nonce_b64,
        "ciphertext": ct_b64,
    }
    (d / "transcript.jsonl").write_text(
        json.dumps(entry, separators=(",", ":")) + "\n", encoding="utf-8",
    )
    return wg.meta.id


def test_decrypt_transcript_hub_roundtrip(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    wg_id = _seed_workgroup_with_one_post(home, b"hello workgroup")

    posts = data_workgroup.decrypt_transcript(home, wg_id)
    assert len(posts) == 1
    assert posts[0]["body"] == "hello workgroup"
    assert posts[0]["seq"] == 1
    assert posts[0]["from"] == "@default"


def test_decrypt_transcript_unknown_workgroup_returns_empty(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    home.mkdir()
    load_or_generate(home)
    out = data_workgroup.decrypt_transcript(home, "wg_does_not_exist")
    assert out == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_data_workgroup_transcript_over_unix_socket(
    short_tmp: Path, monkeypatch,
) -> None:
    """The control socket returns decrypted transcript rows."""
    home = short_tmp / "hub"
    wg_id = _seed_workgroup_with_one_post(home, b"first plaintext")

    monkeypatch.setattr(
        Path, "home", classmethod(lambda cls: short_tmp.parent),  # type: ignore[arg-type]
    )

    srv = host_server.Server(home=home)
    data_handlers.register(srv)
    await srv.start()
    try:
        monkeypatch.setattr(
            data_handlers, "_resolve_home",
            lambda profile: home,
        )

        reader, writer = await asyncio.open_unix_connection(
            str(srv.socket_path()),
        )
        request = {
            "id": "req-1",
            "method": "host.workgroup.transcript",
            "params": {"profile": "default", "wg_id": wg_id},
        }
        writer.write((json.dumps(request) + "\n").encode("utf-8"))
        await writer.drain()
        line = await reader.readline()
        writer.close()
        await writer.wait_closed()
    finally:
        await srv.stop()

    response = json.loads(line)
    assert response["id"] == "req-1"
    assert "error" not in response
    posts = response["result"]["posts"]
    assert len(posts) == 1
    assert posts[0]["body"] == "first plaintext"


@pytest.mark.asyncio
async def test_control_method_not_found(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    home.mkdir()
    load_or_generate(home)
    srv = host_server.Server(home=home)
    data_handlers.register(srv)
    await srv.start()
    try:
        reader, writer = await asyncio.open_unix_connection(str(srv.socket_path()))
        writer.write(
            (json.dumps({"id": "x", "method": "host.does.not.exist"}) + "\n").encode(),
        )
        await writer.drain()
        line = await reader.readline()
        writer.close()
        await writer.wait_closed()
    finally:
        await srv.stop()
    response = json.loads(line)
    assert response["error"]["code"] == -32601


def test_register_rejects_non_data_namespace(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    home.mkdir()
    load_or_generate(home)
    srv = host_server.Server(home=home)
    with pytest.raises(ValueError):
        srv.register("link.something", lambda *_: {})
