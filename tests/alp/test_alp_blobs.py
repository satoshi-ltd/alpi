from __future__ import annotations

import hashlib
import shutil
import socket
import tempfile
from pathlib import Path

import pytest

from alpi.alp import blobs
from alpi.alp import peers as peers_mod
from alpi.alp import server as alp_server
from alpi.alp.keys import load_or_generate
from alpi.alp.peers import Peer


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_blob_publish_is_atomic_and_content_addressed(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    data = b"blob-data"
    digest = _digest(data)

    result = blobs._write_chunk(home, "sender", digest, len(data), 0, data, True)

    target = blobs.blob_root(home) / digest
    assert result == {
        "hash": digest,
        "size": len(data),
        "next_offset": len(data),
        "complete": True,
    }
    assert target.read_bytes() == data
    assert target.stat().st_mode & 0o777 == 0o600
    assert not list((blobs.blob_root(home) / ".incoming").glob("*.part"))


def test_blob_hash_mismatch_is_not_published(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    digest = _digest(b"expected")

    with pytest.raises(blobs.BlobError, match="hash verification"):
        blobs._write_chunk(home, "sender", digest, 6, 0, b"actual", True)

    assert not (blobs.blob_root(home) / digest).exists()


def test_blob_rejects_offset_gap_and_symlink_root(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    data = b"abcdef"
    digest = _digest(data)
    blobs._write_chunk(home, "sender", digest, len(data), 0, data[:3], False)

    with pytest.raises(blobs.BlobError, match="offset mismatch"):
        blobs._write_chunk(home, "sender", digest, len(data), 2, data[3:], True)

    unsafe = tmp_path / "unsafe"
    unsafe.mkdir()
    other = tmp_path / "other"
    other.mkdir()
    (unsafe / "alp").symlink_to(other)
    with pytest.raises(blobs.BlobError, match="unsafe ALP"):
        blobs.blob_root(unsafe)


@pytest.mark.asyncio
async def test_missing_blob_uses_wire_error_code(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    server = alp_server.Server(home=home)
    blobs.register(server, home)
    peer = Peer(id="sender", pubkey=load_or_generate(tmp_path / "sender").pubkey_b64())

    with pytest.raises(alp_server.HandlerError) as error:
        await server.handlers["link.get_blob"](
            {"hash": _digest(b"missing")},
            peer,
            server,
        )

    assert error.value.code == -32012
    assert error.value.message == "blob-not-found"


@pytest.mark.asyncio
async def test_corrupt_blob_uses_not_found_wire_error(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    data = b"original"
    digest = _digest(data)
    blobs._write_chunk(home, "sender", digest, len(data), 0, data, True)
    (blobs.blob_root(home) / digest).write_bytes(b"tampered")
    server = alp_server.Server(home=home)
    blobs.register(server, home)
    peer = Peer(id="sender", pubkey=load_or_generate(tmp_path / "sender").pubkey_b64())

    with pytest.raises(alp_server.HandlerError) as error:
        await server.handlers["link.get_blob"]({"hash": digest}, peer, server)

    assert error.value.code == -32012
    assert error.value.message == "blob-not-found"


def _free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = int(sock.getsockname()[1])
    sock.close()
    return port


@pytest.fixture
def short_tmp() -> Path:
    root = Path(tempfile.mkdtemp(prefix="alp-blob-", dir="/tmp"))
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_blob_roundtrip_over_noise_tcp(short_tmp: Path) -> None:
    alice_home = short_tmp / "alice"
    bob_home = short_tmp / "bob"
    alice_home.mkdir()
    bob_home.mkdir()
    alice = load_or_generate(alice_home)
    bob = load_or_generate(bob_home)
    port = _free_port()
    peers_mod.add(alice_home, Peer(
        id="bob",
        pubkey=bob.pubkey_b64(),
        address=f"127.0.0.1:{port}",
        allow=[],
    ))
    peers_mod.add(bob_home, Peer(
        id="alice",
        pubkey=alice.pubkey_b64(),
        allow=["link.put_blob", "link.get_blob"],
    ))
    source = short_tmp / "source.bin"
    data = b"x" * (blobs.CHUNK_BYTES + 17)
    source.write_bytes(data)
    destination = short_tmp / "download.bin"

    server = alp_server.Server(
        home=bob_home,
        agent_name="bob",
        tcp_host="127.0.0.1",
        tcp_port=port,
    )
    blobs.register(server, bob_home)
    await server.start()
    try:
        uploaded = await blobs.put(alice_home, "bob", source)
        downloaded = await blobs.get(
            alice_home,
            "bob",
            uploaded["hash"],
            destination,
        )
    finally:
        await server.stop()

    assert uploaded == {"hash": _digest(data), "size": len(data), "complete": True}
    assert downloaded["hash"] == uploaded["hash"]
    assert destination.read_bytes() == data


@pytest.mark.asyncio
async def test_blob_roundtrip_over_unix_socket(short_tmp: Path, monkeypatch) -> None:
    alice_home = short_tmp / "alice-local"
    bob_home = short_tmp / "bob-local"
    alice_home.mkdir()
    bob_home.mkdir()
    alice = load_or_generate(alice_home)
    bob = load_or_generate(bob_home)
    peers_mod.add(alice_home, Peer(id="bob", pubkey=bob.pubkey_b64(), allow=[]))
    peers_mod.add(bob_home, Peer(
        id="alice",
        pubkey=alice.pubkey_b64(),
        allow=["link.put_blob", "link.get_blob"],
    ))
    source = short_tmp / "local-source.bin"
    data = b"y" * (blobs.CHUNK_BYTES + 17)
    source.write_bytes(data)
    destination = short_tmp / "local-download.bin"

    server = alp_server.Server(home=bob_home, agent_name="bob")
    blobs.register(server, bob_home)
    await server.start()
    monkeypatch.setattr(peers_mod, "local_socket_path", lambda peer: server.socket_path())
    try:
        uploaded = await blobs.put(alice_home, "bob", source)
        downloaded = await blobs.get(alice_home, "bob", uploaded["hash"], destination)
    finally:
        await server.stop()

    assert uploaded == {"hash": _digest(data), "size": len(data), "complete": True}
    assert downloaded["hash"] == uploaded["hash"]
    assert destination.read_bytes() == data
