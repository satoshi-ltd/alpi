"""ALP intra-profile end-to-end — Server + client over a Unix socket."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from alpi.alp import client as alp_client
from alpi.alp import peers as peers_mod
from alpi.alp import server as alp_server
from alpi.alp.keys import load_or_generate
from alpi.alp.peers import Peer


@pytest.fixture
def short_tmp() -> Path:
    """AF_UNIX paths on macOS are capped at ~104 bytes — pytest's tmp_path
    under ``/private/var/folders/...`` blows that out. Use a short prefix."""
    d = Path(tempfile.mkdtemp(prefix="alp-", dir="/tmp"))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


def _pin(home: Path, peer_id: str, pubkey: str, allow: list[str]) -> None:
    peers_mod.add(home, Peer(id=peer_id, pubkey=pubkey, allow=allow))


@pytest.mark.asyncio
async def test_ping_roundtrip_between_two_profiles(short_tmp: Path) -> None:
    alice_home = short_tmp / "alice"
    bob_home = short_tmp / "bob"
    alice_home.mkdir()
    bob_home.mkdir()

    alice_kp = load_or_generate(alice_home)
    bob_kp = load_or_generate(bob_home)

    _pin(alice_home, "bob", bob_kp.pubkey_b64(), ["link.ping"])
    _pin(bob_home, "alice", alice_kp.pubkey_b64(), ["link.ping"])

    bob_srv = alp_server.Server(home=bob_home, agent_name="bob")
    await bob_srv.start()
    try:
        result = await alp_client.call(
            socket_path=bob_srv.socket_path(),
            sender=alice_kp,
            recipient_pubkey_b64=bob_kp.pubkey_b64(),
            method="link.ping",
            params={"nonce": "hi"},
        )
    finally:
        await bob_srv.stop()

    assert result["nonce"] == "hi"
    assert result["agent_name"] == "bob"


@pytest.mark.asyncio
async def test_capability_denied_when_method_not_allowed(short_tmp: Path) -> None:
    alice_home = short_tmp / "alice"
    bob_home = short_tmp / "bob"
    alice_home.mkdir()
    bob_home.mkdir()

    alice_kp = load_or_generate(alice_home)
    bob_kp = load_or_generate(bob_home)

    # Alice is pinned by Bob but NOT granted link.ping.
    _pin(bob_home, "alice", alice_kp.pubkey_b64(), allow=[])

    bob_srv = alp_server.Server(home=bob_home, agent_name="bob")
    await bob_srv.start()
    try:
        with pytest.raises(alp_client.RemoteError) as ei:
            await alp_client.call(
                socket_path=bob_srv.socket_path(),
                sender=alice_kp,
                recipient_pubkey_b64=bob_kp.pubkey_b64(),
                method="link.ping",
            )
    finally:
        await bob_srv.stop()

    assert ei.value.code == -32001


@pytest.mark.asyncio
async def test_unknown_peer_gets_silent_drop(short_tmp: Path) -> None:
    alice_home = short_tmp / "alice"
    bob_home = short_tmp / "bob"
    alice_home.mkdir()
    bob_home.mkdir()

    alice_kp = load_or_generate(alice_home)
    bob_kp = load_or_generate(bob_home)

    # Bob never pins alice — silent drop, client times out.
    bob_srv = alp_server.Server(home=bob_home, agent_name="bob")
    await bob_srv.start()
    try:
        with pytest.raises(alp_client.ClientError):
            await alp_client.call(
                socket_path=bob_srv.socket_path(),
                sender=alice_kp,
                recipient_pubkey_b64=bob_kp.pubkey_b64(),
                method="link.ping",
                timeout=1.0,
            )
    finally:
        await bob_srv.stop()


@pytest.mark.asyncio
async def test_method_not_found_returns_32601(short_tmp: Path) -> None:
    alice_home = short_tmp / "alice"
    bob_home = short_tmp / "bob"
    alice_home.mkdir()
    bob_home.mkdir()

    alice_kp = load_or_generate(alice_home)
    bob_kp = load_or_generate(bob_home)

    _pin(bob_home, "alice", alice_kp.pubkey_b64(), ["link.mystery"])

    bob_srv = alp_server.Server(home=bob_home, agent_name="bob")
    await bob_srv.start()
    try:
        with pytest.raises(alp_client.RemoteError) as ei:
            await alp_client.call(
                socket_path=bob_srv.socket_path(),
                sender=alice_kp,
                recipient_pubkey_b64=bob_kp.pubkey_b64(),
                method="link.mystery",
            )
    finally:
        await bob_srv.stop()

    assert ei.value.code == -32601


@pytest.mark.asyncio
async def test_handler_error_is_mapped(short_tmp: Path) -> None:
    alice_home = short_tmp / "alice"
    bob_home = short_tmp / "bob"
    alice_home.mkdir()
    bob_home.mkdir()

    alice_kp = load_or_generate(alice_home)
    bob_kp = load_or_generate(bob_home)

    _pin(bob_home, "alice", alice_kp.pubkey_b64(), ["custom.boom"])

    bob_srv = alp_server.Server(home=bob_home, agent_name="bob")

    async def boom(params, peer, server):
        raise alp_server.HandlerError(-32010, "on fire", data={"why": "test"})

    bob_srv.register("custom.boom", boom)
    await bob_srv.start()
    try:
        with pytest.raises(alp_client.RemoteError) as ei:
            await alp_client.call(
                socket_path=bob_srv.socket_path(),
                sender=alice_kp,
                recipient_pubkey_b64=bob_kp.pubkey_b64(),
                method="custom.boom",
            )
    finally:
        await bob_srv.stop()

    assert ei.value.code == -32010
    assert ei.value.message == "on fire"


@pytest.mark.asyncio
async def test_link_cancel_noop_when_no_active_turn(short_tmp: Path) -> None:
    """``link.cancel`` is idempotent — a cancel for a finished / never-
    started turn must succeed with ``cancelled: false``, not error."""
    from alpi.alp import handlers as alp_handlers

    alice_home = short_tmp / "alice"
    bob_home = short_tmp / "bob"
    alice_home.mkdir()
    bob_home.mkdir()

    alice_kp = load_or_generate(alice_home)
    bob_kp = load_or_generate(bob_home)

    _pin(bob_home, "alice", alice_kp.pubkey_b64(), ["link.cancel"])

    bob_srv = alp_server.Server(home=bob_home, agent_name="bob")
    alp_handlers.register_link_ask(bob_srv, bob_home)
    await bob_srv.start()
    try:
        result = await alp_client.call(
            socket_path=bob_srv.socket_path(),
            sender=alice_kp,
            recipient_pubkey_b64=bob_kp.pubkey_b64(),
            method="link.cancel",
            params={"session_id": "does-not-exist"},
        )
    finally:
        await bob_srv.stop()

    assert result == {"cancelled": False}


@pytest.mark.asyncio
async def test_target_offline_raises(short_tmp: Path) -> None:
    alice_home = short_tmp / "alice"
    alice_home.mkdir()
    alice_kp = load_or_generate(alice_home)

    with pytest.raises(alp_client.TargetOffline):
        await alp_client.call(
            socket_path=short_tmp / "does-not-exist.sock",
            sender=alice_kp,
            recipient_pubkey_b64=alice_kp.pubkey_b64(),
            method="link.ping",
            timeout=1.0,
        )
