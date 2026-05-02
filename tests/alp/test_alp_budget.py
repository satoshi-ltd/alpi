from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest
import yaml

from alpi import ledger
from alpi.alp import client as alp_client
from alpi.alp import peers as peers_mod
from alpi.alp import server as alp_server
from alpi.alp.keys import load_or_generate
from alpi.alp.peers import Peer


@pytest.fixture
def short_tmp() -> Path:
    d = Path(tempfile.mkdtemp(prefix="alp-budget-", dir="/tmp"))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


async def _pick_free_port() -> int:
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _write_budget_cfg(home: Path, usd: float) -> None:
    cfg = home / "config.yaml"
    cfg.write_text(yaml.safe_dump({"model": "", "budget": {"daily_usd": usd}}))


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tcp_budget_exceeded_returns_32005(short_tmp: Path) -> None:
    alice_home = short_tmp / "alice"
    bob_home = short_tmp / "bob"
    alice_home.mkdir()
    bob_home.mkdir()

    alice_kp = load_or_generate(alice_home)
    bob_kp = load_or_generate(bob_home)

    _write_budget_cfg(bob_home, usd=1.0)
    peers_mod.add(
        bob_home,
        Peer(id="alice", pubkey=alice_kp.pubkey_b64(), allow=["link.ping"]),
    )

    ledger.record(bob_home, usd=1.5, tokens=0)

    port = await _pick_free_port()
    srv = alp_server.Server(
        home=bob_home, agent_name="bob", tcp_host="127.0.0.1", tcp_port=port,
    )
    await srv.start()
    try:
        with pytest.raises(alp_client.RemoteError) as exc:
            await alp_client.call_tcp(
                host="127.0.0.1", port=port,
                sender=alice_kp,
                recipient_pubkey_b64=bob_kp.pubkey_b64(),
                method="link.ping", params={},
            )
        assert exc.value.code == -32005
        assert exc.value.message == "budget-exceeded"
        assert exc.value.data["cap_kind"] == "usd"
    finally:
        await srv.stop()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tcp_budget_admits_under_cap(short_tmp: Path) -> None:
    alice_home = short_tmp / "alice"
    bob_home = short_tmp / "bob"
    alice_home.mkdir()
    bob_home.mkdir()

    alice_kp = load_or_generate(alice_home)
    bob_kp = load_or_generate(bob_home)

    _write_budget_cfg(bob_home, usd=5.0)
    peers_mod.add(
        bob_home,
        Peer(id="alice", pubkey=alice_kp.pubkey_b64(), allow=["link.ping"]),
    )

    ledger.record(bob_home, usd=2.0, tokens=100)

    port = await _pick_free_port()
    srv = alp_server.Server(
        home=bob_home, agent_name="bob", tcp_host="127.0.0.1", tcp_port=port,
    )
    await srv.start()
    try:
        r = await alp_client.call_tcp(
            host="127.0.0.1", port=port,
            sender=alice_kp,
            recipient_pubkey_b64=bob_kp.pubkey_b64(),
            method="link.ping", params={"nonce": "cli"},
        )
        assert r["agent_name"] == "bob"
    finally:
        await srv.stop()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_no_budget_configured_never_trips(short_tmp: Path) -> None:
    alice_home = short_tmp / "alice"
    bob_home = short_tmp / "bob"
    alice_home.mkdir()
    bob_home.mkdir()

    alice_kp = load_or_generate(alice_home)
    bob_kp = load_or_generate(bob_home)

    peers_mod.add(
        bob_home,
        Peer(id="alice", pubkey=alice_kp.pubkey_b64(), allow=["link.ping"]),
    )
    ledger.record(bob_home, usd=999999.0, tokens=10**12)

    port = await _pick_free_port()
    srv = alp_server.Server(
        home=bob_home, agent_name="bob", tcp_host="127.0.0.1", tcp_port=port,
    )
    await srv.start()
    try:
        r = await alp_client.call_tcp(
            host="127.0.0.1", port=port,
            sender=alice_kp,
            recipient_pubkey_b64=bob_kp.pubkey_b64(),
            method="link.ping", params={},
        )
        assert r["agent_name"] == "bob"
    finally:
        await srv.stop()
