"""ALP inter-machine end-to-end — Server (TCP + Noise_XK) + client."""

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
    d = Path(tempfile.mkdtemp(prefix="alp-tcp-", dir="/tmp"))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


def _pin(
    home: Path,
    peer_id: str,
    pubkey: str,
    allow: list[str],
    *,
    address: str | None = None,
    rate_limit: dict | None = None,
) -> None:
    peers_mod.add(home, Peer(
        id=peer_id,
        pubkey=pubkey,
        allow=allow,
        address=address,
        rate_limit=rate_limit or {},
    ))


async def _pick_free_port() -> int:
    """Bind to port 0 to let the OS choose, then release."""
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tcp_ping_roundtrip_with_pinned_peer(short_tmp: Path) -> None:
    alice_home = short_tmp / "alice"
    bob_home = short_tmp / "bob"
    alice_home.mkdir()
    bob_home.mkdir()

    alice_kp = load_or_generate(alice_home)
    bob_kp = load_or_generate(bob_home)

    port = await _pick_free_port()
    _pin(alice_home, "bob", bob_kp.pubkey_b64(), ["link.ping"],
         address=f"127.0.0.1:{port}")
    _pin(bob_home, "alice", alice_kp.pubkey_b64(), ["link.ping"])

    bob_srv = alp_server.Server(
        home=bob_home, agent_name="bob",
        tcp_host="127.0.0.1", tcp_port=port,
    )
    await bob_srv.start()
    try:
        result = await alp_client.call_tcp(
            host="127.0.0.1", port=port,
            sender=alice_kp,
            recipient_pubkey_b64=bob_kp.pubkey_b64(),
            method="link.ping",
            params={"nonce": "hi-over-tcp"},
        )
    finally:
        await bob_srv.stop()

    assert result["nonce"] == "hi-over-tcp"
    assert result["agent_name"] == "bob"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tcp_unpinned_peer_is_silently_dropped(short_tmp: Path) -> None:
    alice_home = short_tmp / "alice"
    bob_home = short_tmp / "bob"
    alice_home.mkdir()
    bob_home.mkdir()

    alice_kp = load_or_generate(alice_home)
    bob_kp = load_or_generate(bob_home)
    # Bob does NOT pin alice — connection must be dropped after handshake.

    port = await _pick_free_port()
    bob_srv = alp_server.Server(
        home=bob_home, agent_name="bob",
        tcp_host="127.0.0.1", tcp_port=port,
    )
    await bob_srv.start()
    try:
        with pytest.raises(alp_client.ClientError):
            await alp_client.call_tcp(
                host="127.0.0.1", port=port,
                sender=alice_kp,
                recipient_pubkey_b64=bob_kp.pubkey_b64(),
                method="link.ping",
                params={},
                timeout=3.0,
            )
    finally:
        await bob_srv.stop()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tcp_capability_denied(short_tmp: Path) -> None:
    alice_home = short_tmp / "alice"
    bob_home = short_tmp / "bob"
    alice_home.mkdir()
    bob_home.mkdir()

    alice_kp = load_or_generate(alice_home)
    bob_kp = load_or_generate(bob_home)

    port = await _pick_free_port()
    # Alice is pinned but cannot call link.ping (empty allow list).
    _pin(bob_home, "alice", alice_kp.pubkey_b64(), allow=[])

    bob_srv = alp_server.Server(
        home=bob_home, agent_name="bob",
        tcp_host="127.0.0.1", tcp_port=port,
    )
    await bob_srv.start()
    try:
        with pytest.raises(alp_client.RemoteError) as exc:
            await alp_client.call_tcp(
                host="127.0.0.1", port=port,
                sender=alice_kp,
                recipient_pubkey_b64=bob_kp.pubkey_b64(),
                method="link.ping",
                params={},
            )
        assert exc.value.code == -32001
    finally:
        await bob_srv.stop()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tcp_rate_limit_triggers_32005(short_tmp: Path) -> None:
    alice_home = short_tmp / "alice"
    bob_home = short_tmp / "bob"
    alice_home.mkdir()
    bob_home.mkdir()

    alice_kp = load_or_generate(alice_home)
    bob_kp = load_or_generate(bob_home)

    port = await _pick_free_port()
    # Allow link.ping but cap at 2 requests per minute.
    _pin(bob_home, "alice", alice_kp.pubkey_b64(),
         allow=["link.ping"], rate_limit={"per_minute": 2})

    bob_srv = alp_server.Server(
        home=bob_home, agent_name="bob",
        tcp_host="127.0.0.1", tcp_port=port,
    )
    await bob_srv.start()
    try:
        # First two succeed.
        for _ in range(2):
            r = await alp_client.call_tcp(
                host="127.0.0.1", port=port,
                sender=alice_kp,
                recipient_pubkey_b64=bob_kp.pubkey_b64(),
                method="link.ping", params={},
            )
            assert r["agent_name"] == "bob"
        # Third must be rejected with -32005 rate-limited.
        with pytest.raises(alp_client.RemoteError) as exc:
            await alp_client.call_tcp(
                host="127.0.0.1", port=port,
                sender=alice_kp,
                recipient_pubkey_b64=bob_kp.pubkey_b64(),
                method="link.ping", params={},
            )
        assert exc.value.code == -32005
    finally:
        await bob_srv.stop()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_call_peer_dispatches_tcp_when_address_set(short_tmp: Path) -> None:
    alice_home = short_tmp / "alice"
    bob_home = short_tmp / "bob"
    alice_home.mkdir()
    bob_home.mkdir()

    alice_kp = load_or_generate(alice_home)
    bob_kp = load_or_generate(bob_home)

    port = await _pick_free_port()
    _pin(alice_home, "bob", bob_kp.pubkey_b64(), allow=[],
         address=f"127.0.0.1:{port}")
    _pin(bob_home, "alice", alice_kp.pubkey_b64(), ["link.ping"])

    bob_srv = alp_server.Server(
        home=bob_home, agent_name="bob",
        tcp_host="127.0.0.1", tcp_port=port,
    )
    await bob_srv.start()
    try:
        r = await alp_client.call_peer(
            home=alice_home, peer_id="bob",
            sender=alice_kp, method="link.ping",
            params={"nonce": "peer-dispatch"},
        )
        assert r["nonce"] == "peer-dispatch"
    finally:
        await bob_srv.stop()


@pytest.mark.asyncio
async def test_call_peer_without_address_raises(short_tmp: Path) -> None:
    home = short_tmp / "a"
    home.mkdir()
    kp = load_or_generate(home)
    # Peer with no address → call_peer should refuse rather than guess.
    _pin(home, "bob", kp.pubkey_b64(), allow=[])
    with pytest.raises(alp_client.ClientError):
        await alp_client.call_peer(
            home=home, peer_id="bob",
            sender=kp, method="link.ping", params={},
        )


@pytest.mark.asyncio
async def test_call_peer_rejects_unknown_peer(short_tmp: Path) -> None:
    home = short_tmp / "a"
    home.mkdir()
    kp = load_or_generate(home)
    with pytest.raises(alp_client.ClientError):
        await alp_client.call_peer(
            home=home, peer_id="ghost",
            sender=kp, method="link.ping", params={},
        )
