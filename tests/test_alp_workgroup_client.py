"""ALP.3 PR 4 — member-side helpers.

Covers ``subscription`` (member-side state) and ``workgroup_client``
(the verbs a remote member calls). Hub still served by
``test_alp_workgroup.py``.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import stat
import tempfile
from pathlib import Path

import pytest

from alpi.alp import peers as peers_mod
from alpi.alp import server as alp_server
from alpi.alp import subscription as sub_mod
from alpi.alp import workgroup as wg_mod
from alpi.alp import workgroup_client as wc
from alpi.alp.keys import load_or_generate
from alpi.alp.peers import Peer


@pytest.fixture
def short_tmp() -> Path:
    d = Path(tempfile.mkdtemp(prefix="alp-wgc-", dir="/tmp"))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


def _pin(home: Path, peer_id: str, pubkey: str, allow: list[str],
         address: str | None = None) -> None:
    peers_mod.add(home, Peer(
        id=peer_id, pubkey=pubkey, allow=allow, address=address,
    ))


# Subscription module


def test_subscription_roundtrip_persists_with_0600_mode(short_tmp: Path) -> None:
    home = short_tmp / "alice"; home.mkdir()
    sub = sub_mod.Subscription(
        wg_id="wg_test", name="design", hub_id="bob",
        hub_pubkey="b" * 44, last_seq=3,
    )
    sub.upsert_key(1, "sealed1")
    sub.upsert_key(2, "sealed2")
    sub_mod.upsert(home, sub)

    p = sub_mod.path(home)
    assert p.exists()
    mode = stat.S_IMODE(os.stat(p).st_mode)
    assert mode == 0o600, f"expected 0600, got {oct(mode)}"

    loaded = sub_mod.get(home, "wg_test")
    assert loaded is not None
    assert loaded.name == "design"
    assert loaded.last_seq == 3
    assert loaded.latest_version() == 2
    assert loaded.sealed_for(1) == "sealed1"
    assert loaded.sealed_for(2) == "sealed2"


def test_upsert_replaces_existing_subscription(short_tmp: Path) -> None:
    home = short_tmp / "alice"; home.mkdir()
    s1 = sub_mod.Subscription(wg_id="wg1", name="a", hub_id="h", hub_pubkey="x")
    sub_mod.upsert(home, s1)
    s1_updated = sub_mod.Subscription(wg_id="wg1", name="b", hub_id="h", hub_pubkey="x")
    sub_mod.upsert(home, s1_updated)
    loaded = sub_mod.load(home)
    assert len(loaded) == 1
    assert loaded[0].name == "b"


def test_recent_posts_cache_dedupes_and_trims(short_tmp: Path) -> None:
    sub = sub_mod.Subscription(wg_id="wg_x", name="x", hub_id="h", hub_pubkey="k")
    posts = [{"seq": i, "text": f"msg {i}", "from": "x"} for i in range(1, 26)]
    sub.append_recent(posts)
    assert len(sub.recent_posts) == sub_mod.RECENT_POSTS_CACHE
    seqs = [int(p["seq"]) for p in sub.recent_posts]
    assert seqs[-1] == 25
    assert seqs[0] == 25 - sub_mod.RECENT_POSTS_CACHE + 1


def test_recent_posts_cache_replaces_on_same_seq() -> None:
    sub = sub_mod.Subscription(wg_id="wg_x", name="x", hub_id="h", hub_pubkey="k")
    sub.append_recent([{"seq": 1, "text": "first", "from": "a"}])
    sub.append_recent([{"seq": 1, "text": "first (updated)", "from": "a"}])
    assert len(sub.recent_posts) == 1
    assert sub.recent_posts[0]["text"] == "first (updated)"


def test_recent_posts_persist_through_load_save(short_tmp: Path) -> None:
    home = short_tmp / "alice"; home.mkdir()
    sub = sub_mod.Subscription(wg_id="wg_x", name="x", hub_id="h", hub_pubkey="k")
    sub.append_recent([
        {"seq": 1, "text": "alpha", "from": "a"},
        {"seq": 2, "text": "beta",  "from": "b"},
    ])
    sub_mod.upsert(home, sub)
    reloaded = sub_mod.get(home, "wg_x")
    assert reloaded is not None
    assert len(reloaded.recent_posts) == 2
    assert reloaded.recent_posts[1]["text"] == "beta"


def test_briefing_persists_through_load_save(short_tmp: Path) -> None:
    """Member-side briefing is fetched on join and cached in
    subscriptions.yaml so the engine pre-turn hook surfaces it on
    every turn without an extra network call."""
    home = short_tmp / "alice"; home.mkdir()
    sub = sub_mod.Subscription(
        wg_id="wg_x", name="x", hub_id="h", hub_pubkey="k",
        briefing="research peptides for protein X",
    )
    sub_mod.upsert(home, sub)
    reloaded = sub_mod.get(home, "wg_x")
    assert reloaded is not None
    assert reloaded.briefing == "research peptides for protein X"


def test_remove_returns_false_for_unknown(short_tmp: Path) -> None:
    home = short_tmp / "x"; home.mkdir()
    assert sub_mod.remove(home, "wg_nope") is False
    sub_mod.upsert(home, sub_mod.Subscription(
        wg_id="wg1", name="a", hub_id="h", hub_pubkey="x",
    ))
    assert sub_mod.remove(home, "wg1") is True
    assert sub_mod.load(home) == []


# Member-side e2e via workgroup_client


@pytest.mark.asyncio
async def test_join_persists_subscription_and_pull_decrypts(
    short_tmp: Path,
) -> None:
    """Bob joins via ``wc.join`` → subscription stored on disk → pull
    decrypts a hub-side post without bob having to re-import the
    sealed key by hand."""
    hub_home = short_tmp / "alice"; hub_home.mkdir()
    bob_home = short_tmp / "bob"; bob_home.mkdir()
    alice_kp = load_or_generate(hub_home)
    bob_kp = load_or_generate(bob_home)
    _pin(hub_home, "bob", bob_kp.pubkey_b64(),
         ["workgroup.join", "workgroup.post", "workgroup.pull",
          "workgroup.leave"])
    # Bob pins alice (the hub) using a unix socket convention that
    # workgroup_client._intra_socket_path resolves.
    _pin(bob_home, "alice", alice_kp.pubkey_b64(),
         ["link.ping"])

    wg = wg_mod.create(
        hub_home, name="design", hub_kp=alice_kp,
        member_pubkeys=[bob_kp.pubkey_b64()],
    )

    server = alp_server.Server(home=hub_home, agent_name="alice")
    wg_mod.register(server, hub_home)
    await server.start()
    # ``wc._intra_socket_path`` looks under ~/.alpi/profiles/<id>/...
    # In tests we monkey-patch it to use the test home directly.
    import alpi.alp.workgroup_client as wc_mod
    original_resolver = wc_mod._intra_socket_path
    wc_mod._intra_socket_path = lambda peer_id: server.socket_path()
    try:
        sub = await wc.join(bob_home, "alice", wg.meta.id)
        assert sub.wg_id == wg.meta.id
        assert sub.name == "design"
        assert sub.hub_id == "alice"
        assert sub.latest_version() == 1
        assert sub.joined_at  # set on first join
        # Persisted to disk under ~/<bob>/alp/secrets/subscriptions.yaml
        assert sub_mod.path(bob_home).exists()

        # Bob posts via wc.post
        await wc.post(bob_home, wg.meta.id, b"hi via wc")

        # Bob pulls via wc.pull — gets decrypted text
        posts, head = await wc.pull(bob_home, wg.meta.id)
        assert head == 1
        assert len(posts) == 1
        assert posts[0]["text"] == "hi via wc"
        # Cursor advanced
        sub_after = sub_mod.get(bob_home, wg.meta.id)
        assert sub_after.last_seq == 1

        # A second pull returns nothing new
        posts2, _ = await wc.pull(bob_home, wg.meta.id)
        assert posts2 == []
    finally:
        wc_mod._intra_socket_path = original_resolver
        await server.stop()


@pytest.mark.asyncio
async def test_pull_picks_up_rotated_key(short_tmp: Path) -> None:
    """After a kick on the hub, bob's next pull learns the new
    `current_key_version` + sealed_key, stores it, and decrypts a v2
    post correctly."""
    hub_home = short_tmp / "alice"; hub_home.mkdir()
    bob_home = short_tmp / "bob"; bob_home.mkdir()
    extra_home = short_tmp / "carol"; extra_home.mkdir()
    alice_kp = load_or_generate(hub_home)
    bob_kp = load_or_generate(bob_home)
    carol_kp = load_or_generate(extra_home)
    _pin(hub_home, "bob", bob_kp.pubkey_b64(),
         ["workgroup.join", "workgroup.post", "workgroup.pull"])
    _pin(hub_home, "carol", carol_kp.pubkey_b64(),
         ["workgroup.join"])
    _pin(bob_home, "alice", alice_kp.pubkey_b64(), ["link.ping"])

    wg = wg_mod.create(
        hub_home, name="rotate", hub_kp=alice_kp,
        member_pubkeys=[bob_kp.pubkey_b64(), carol_kp.pubkey_b64()],
    )

    server = alp_server.Server(home=hub_home, agent_name="alice")
    wg_mod.register(server, hub_home)
    await server.start()
    import alpi.alp.workgroup_client as wc_mod
    original = wc_mod._intra_socket_path
    wc_mod._intra_socket_path = lambda peer_id: server.socket_path()
    try:
        await wc.join(bob_home, "alice", wg.meta.id)
        # Hub kicks carol → key rotates to v2
        wg_mod.kick(hub_home, wg.meta.id, carol_kp.pubkey_b64())

        # Bob posts under v2 — wc.post must read the new sealed_key
        # via pull-detected rotation. So we issue a pull first.
        await wc.pull(bob_home, wg.meta.id)
        sub = sub_mod.get(bob_home, wg.meta.id)
        assert sub.latest_version() == 2

        await wc.post(bob_home, wg.meta.id, b"after rotate")
        posts, head = await wc.pull(bob_home, wg.meta.id)
        assert head == 1
        assert posts[0]["text"] == "after rotate"
        assert posts[0]["key_version"] == 2
    finally:
        wc_mod._intra_socket_path = original
        await server.stop()


@pytest.mark.asyncio
async def test_leave_drops_subscription_locally(short_tmp: Path) -> None:
    hub_home = short_tmp / "alice"; hub_home.mkdir()
    bob_home = short_tmp / "bob"; bob_home.mkdir()
    alice_kp = load_or_generate(hub_home)
    bob_kp = load_or_generate(bob_home)
    _pin(hub_home, "bob", bob_kp.pubkey_b64(),
         ["workgroup.join", "workgroup.leave"])
    _pin(bob_home, "alice", alice_kp.pubkey_b64(), ["link.ping"])
    wg = wg_mod.create(
        hub_home, name="bye", hub_kp=alice_kp,
        member_pubkeys=[bob_kp.pubkey_b64()],
    )
    server = alp_server.Server(home=hub_home, agent_name="alice")
    wg_mod.register(server, hub_home)
    await server.start()
    import alpi.alp.workgroup_client as wc_mod
    original = wc_mod._intra_socket_path
    wc_mod._intra_socket_path = lambda peer_id: server.socket_path()
    try:
        await wc.join(bob_home, "alice", wg.meta.id)
        assert sub_mod.get(bob_home, wg.meta.id) is not None
        await wc.leave(bob_home, wg.meta.id)
        assert sub_mod.get(bob_home, wg.meta.id) is None
    finally:
        wc_mod._intra_socket_path = original
        await server.stop()


@pytest.mark.asyncio
async def test_post_without_subscription_raises(short_tmp: Path) -> None:
    home = short_tmp / "bob"; home.mkdir()
    load_or_generate(home)
    with pytest.raises(ValueError, match="not subscribed"):
        await wc.post(home, "wg_unknown", b"hello")


def test_resolve_hub_rejects_unpinned_peer(short_tmp: Path) -> None:
    home = short_tmp / "bob"; home.mkdir()
    load_or_generate(home)
    with pytest.raises(ValueError, match="not pinned"):
        wc._resolve_hub(home, "ghost")
