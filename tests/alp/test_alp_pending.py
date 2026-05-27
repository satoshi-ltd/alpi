from __future__ import annotations

from pathlib import Path

import pytest

from alpi.alp import pending


def test_record_creates_entry(tmp_path: Path) -> None:
    pending.record(tmp_path, "PUBKEY_A")
    entries = pending.load(tmp_path)
    assert len(entries) == 1
    assert entries[0].pubkey == "PUBKEY_A"
    assert entries[0].first_seen > 0
    assert entries[0].last_seen >= entries[0].first_seen


def test_record_dedupes_by_pubkey(tmp_path: Path) -> None:
    pending.record(tmp_path, "PUBKEY_A")
    first = pending.load(tmp_path)[0].first_seen
    pending.record(tmp_path, "PUBKEY_A")
    entries = pending.load(tmp_path)
    assert len(entries) == 1
    assert entries[0].first_seen == first
    assert entries[0].last_seen >= first


def test_record_caps_at_20(tmp_path: Path) -> None:
    for i in range(25):
        pending.record(tmp_path, f"PUBKEY_{i}")
    entries = pending.load(tmp_path)
    assert len(entries) == 20
    pubkeys = {e.pubkey for e in entries}
    assert "PUBKEY_24" in pubkeys
    assert "PUBKEY_0" not in pubkeys


def test_remove_returns_false_when_missing(tmp_path: Path) -> None:
    assert pending.remove(tmp_path, "GHOST") is False


def test_remove_drops_only_target(tmp_path: Path) -> None:
    pending.record(tmp_path, "A")
    pending.record(tmp_path, "B")
    assert pending.remove(tmp_path, "A") is True
    pubkeys = {e.pubkey for e in pending.load(tmp_path)}
    assert pubkeys == {"B"}


def test_load_empty_when_file_missing(tmp_path: Path) -> None:
    assert pending.load(tmp_path) == []


def test_peers_status_appends_invite_count(tmp_path: Path, monkeypatch) -> None:
    """The ``alpi setup`` main menu surfaces pending invites alongside
    pinned-peers count, so the user discovers the section without
    having to drill in."""
    from alpi import cli, home as home_mod

    home = tmp_path / ".alpi"
    home.mkdir()
    monkeypatch.setattr(home_mod, "_ROOT", home)

    assert cli._peers_status(home) == "none pinned"

    pending.record(home, "PK_A")
    assert cli._peers_status(home) == "none pinned · 1 invite pending"

    pending.record(home, "PK_B")
    assert cli._peers_status(home) == "none pinned · 2 invites pending"


@pytest.mark.asyncio
async def test_dispatch_records_pending_when_unknown_sender(
    tmp_path: Path,
) -> None:
    """Both transports converge on ``Server._dispatch`` for the
    pinning check; a sender that isn't in ``peers.yaml`` triggers
    ``pending.record`` regardless of whether the envelope arrived
    via Unix socket or TCP/Noise."""
    from alpi.alp import server as alp_server
    from alpi.alp import envelope as env
    from alpi.alp.keys import load_or_generate

    home = tmp_path / "h"
    home.mkdir()
    load_or_generate(home)

    sender_home = tmp_path / "sender"
    sender_home.mkdir()
    sender = load_or_generate(sender_home)

    srv = alp_server.Server(home=home, agent_name="x")
    body = env.build_request(
        sender=sender,
        recipient_pubkey_b64=srv.kp.pubkey_b64(),
        method="link.ping",
        params={"nonce": "n"},
    )
    response = await srv._dispatch(body)
    assert response is None
    recorded = pending.load(home)
    assert len(recorded) == 1
    assert recorded[0].pubkey == sender.pubkey_b64()


@pytest.mark.asyncio
async def test_host_pending_accept_pins_peer_and_clears(
    tmp_path: Path, monkeypatch,
) -> None:
    from alpi import home as home_mod
    from alpi.alp import keys as keys_mod
    from alpi.alp import peers as peers_mod
    from alpi.host import config as host_config
    from alpi.host import server as host_server

    home = tmp_path / ".alpi"
    home.mkdir()
    monkeypatch.setattr(home_mod, "_ROOT", home)
    keys_mod.load_or_generate(home)

    pending.record(home, "INCOMING_PUBKEY")

    srv = host_server.Server(home=home)
    host_config.register(srv)

    accept = {
        "id": "r",
        "method": "host.peers.pending_accept",
        "params": {
            "profile": "default",
            "id": "alice",
            "pubkey": "INCOMING_PUBKEY",
        },
    }
    response = await srv._dispatch(accept)
    assert response["result"]["ok"] is True

    pinned = peers_mod.get_by_id(home, "alice")
    assert pinned is not None
    assert pinned.pubkey == "INCOMING_PUBKEY"
    assert pinned.allow == ["link.ping", "link.ask"]
    assert pending.load(home) == []


@pytest.mark.asyncio
async def test_host_pending_accept_unknown_pubkey_404(
    tmp_path: Path, monkeypatch,
) -> None:
    from alpi import home as home_mod
    from alpi.alp import keys as keys_mod
    from alpi.host import config as host_config
    from alpi.host import server as host_server

    home = tmp_path / ".alpi"
    home.mkdir()
    monkeypatch.setattr(home_mod, "_ROOT", home)
    keys_mod.load_or_generate(home)

    srv = host_server.Server(home=home)
    host_config.register(srv)

    response = await srv._dispatch({
        "id": "r", "method": "host.peers.pending_accept",
        "params": {"profile": "default", "id": "x", "pubkey": "NEVER_SEEN"},
    })
    assert response["error"]["code"] == -32004


@pytest.mark.asyncio
async def test_host_pending_list_enriches_local_profile(
    tmp_path: Path, monkeypatch,
) -> None:
    """When a pending pubkey matches a profile on the same machine,
    ``pending_list`` attaches ``local_profile`` so the desktop can
    pre-fill the peer id without prompting the user."""
    from alpi import home as home_mod
    from alpi.alp import keys as keys_mod
    from alpi.host import config as host_config
    from alpi.host import server as host_server

    root = tmp_path / ".alpi"
    root.mkdir()
    monkeypatch.setattr(home_mod, "_ROOT", root)

    default_kp = keys_mod.load_or_generate(root)
    mirai_home = root / "profiles" / "mirai"
    mirai_home.mkdir(parents=True)
    mirai_kp = keys_mod.load_or_generate(mirai_home)

    pending.record(mirai_home, default_kp.pubkey_b64())
    pending.record(mirai_home, "STRANGER_PUBKEY_NOT_LOCAL")

    srv = host_server.Server(home=root)
    host_config.register(srv)

    response = await srv._dispatch({
        "id": "r", "method": "host.peers.pending_list",
        "params": {"profile": "mirai"},
    })
    rows = {r["pubkey"]: r for r in response["result"]["pending"]}
    assert rows[default_kp.pubkey_b64()]["local_profile"] == "default"
    assert "local_profile" not in rows["STRANGER_PUBKEY_NOT_LOCAL"]


@pytest.mark.asyncio
async def test_host_pending_discard(tmp_path: Path, monkeypatch) -> None:
    from alpi import home as home_mod
    from alpi.alp import keys as keys_mod
    from alpi.host import config as host_config
    from alpi.host import server as host_server

    home = tmp_path / ".alpi"
    home.mkdir()
    monkeypatch.setattr(home_mod, "_ROOT", home)
    keys_mod.load_or_generate(home)

    pending.record(home, "PK_A")
    pending.record(home, "PK_B")

    srv = host_server.Server(home=home)
    host_config.register(srv)

    drop = await srv._dispatch({
        "id": "r", "method": "host.peers.pending_discard",
        "params": {"profile": "default", "pubkey": "PK_A"},
    })
    assert drop["result"] == {"ok": True, "existed": True}

    idem = await srv._dispatch({
        "id": "r", "method": "host.peers.pending_discard",
        "params": {"profile": "default", "pubkey": "GHOST"},
    })
    assert idem["result"] == {"ok": True, "existed": False}

    remaining = {e.pubkey for e in pending.load(home)}
    assert remaining == {"PK_B"}


@pytest.mark.asyncio
async def test_host_pending_discard_does_not_block_future_record(
    tmp_path: Path, monkeypatch,
) -> None:
    # Discard is local-and-now only — no hidden cooldown or denylist.
    from alpi import home as home_mod
    from alpi.alp import keys as keys_mod
    from alpi.host import config as host_config
    from alpi.host import server as host_server

    home = tmp_path / ".alpi"
    home.mkdir()
    monkeypatch.setattr(home_mod, "_ROOT", home)
    keys_mod.load_or_generate(home)
    pending.record(home, "PK_X")

    srv = host_server.Server(home=home)
    host_config.register(srv)

    await srv._dispatch({
        "id": "r", "method": "host.peers.pending_discard",
        "params": {"profile": "default", "pubkey": "PK_X"},
    })
    assert pending.load(home) == []

    pending.record(home, "PK_X")
    pubkeys = {e.pubkey for e in pending.load(home)}
    assert pubkeys == {"PK_X"}


@pytest.mark.asyncio
async def test_host_pending_list(tmp_path: Path, monkeypatch) -> None:
    from alpi import home as home_mod
    from alpi.alp import keys as keys_mod
    from alpi.host import config as host_config
    from alpi.host import server as host_server

    home = tmp_path / ".alpi"
    home.mkdir()
    monkeypatch.setattr(home_mod, "_ROOT", home)
    keys_mod.load_or_generate(home)

    pending.record(home, "A")
    pending.record(home, "B")

    srv = host_server.Server(home=home)
    host_config.register(srv)

    response = await srv._dispatch({
        "id": "r", "method": "host.peers.pending_list",
        "params": {"profile": "default"},
    })
    pubkeys = {e["pubkey"] for e in response["result"]["pending"]}
    assert pubkeys == {"A", "B"}
