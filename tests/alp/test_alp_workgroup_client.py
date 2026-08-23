"""Member-side workgroup helpers."""

from __future__ import annotations

import asyncio
import os
import shutil
import stat
import tempfile
from pathlib import Path

import pytest
import yaml

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


def test_upsert_skips_unchanged_subscription_write(
    short_tmp: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = short_tmp / "alice"
    home.mkdir()
    sub = sub_mod.Subscription(wg_id="wg1", name="a", hub_id="h", hub_pubkey="x")
    sub_mod.upsert(home, sub)
    writes = 0
    real_save = sub_mod._save_unsafe

    def counting_save(target_home, subscriptions):
        nonlocal writes
        writes += 1
        return real_save(target_home, subscriptions)

    monkeypatch.setattr(sub_mod, "_save_unsafe", counting_save)
    loaded = sub_mod.get(home, "wg1")
    assert loaded is not None
    sub_mod.upsert(home, loaded)

    assert writes == 0


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


@pytest.mark.asyncio
async def test_pull_does_not_overwrite_cursor_advanced_during_long_poll(
    short_tmp: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from alpi import service

    home = short_tmp / "member"
    home.mkdir()
    sub_mod.upsert(home, sub_mod.Subscription(
        wg_id="wg_race", name="race", hub_id="hub", hub_pubkey="h" * 44,
    ))
    entered = asyncio.Event()
    release = asyncio.Event()

    async def delayed_call(*args, **kwargs):
        entered.set()
        await release.wait()
        return {"posts": [], "head": 3, "paused": False, "members": []}

    monkeypatch.setattr(wc, "_call", delayed_call)
    pending = asyncio.create_task(wc.pull(home, "wg_race", wait_s=25))
    await entered.wait()
    service._advance_member_cursor(home, "wg_race", 9)
    release.set()
    await pending

    stored = sub_mod.get(home, "wg_race")
    assert stored is not None
    assert stored.last_seq == 3
    assert stored.last_responded_seq == 9


@pytest.mark.integration
@pytest.mark.asyncio
async def test_join_persists_subscription_and_pull_decrypts(
    short_tmp: Path,
) -> None:
    hub_home = short_tmp / "alice"; hub_home.mkdir()
    bob_home = short_tmp / "bob"; bob_home.mkdir()
    alice_kp = load_or_generate(hub_home)
    bob_kp = load_or_generate(bob_home)
    _pin(hub_home, "bob", bob_kp.pubkey_b64(),
         ["workgroup.join", "workgroup.post", "workgroup.pull",
          "workgroup.leave"])
    _pin(bob_home, "alice", alice_kp.pubkey_b64(),
         ["link.ping"])

    wg = wg_mod.create(
        hub_home, name="design", hub_kp=alice_kp,
        member_pubkeys=[bob_kp.pubkey_b64()],
    )

    server = alp_server.Server(home=hub_home, agent_name="alice")
    wg_mod.register(server, hub_home)
    await server.start()
    from alpi.alp import peers as peers_mod
    original_resolver = peers_mod.local_socket_path
    peers_mod.local_socket_path = lambda peer: server.socket_path()
    try:
        sub = await wc.join(bob_home, "alice", wg.meta.id)
        assert sub.wg_id == wg.meta.id
        assert sub.name == "design"
        assert sub.hub_id == "alice"
        assert sub.latest_version() == 1
        assert sub.joined_at
        assert sub_mod.path(bob_home).exists()

        await wc.post(
            bob_home, wg.meta.id, b"hi via wc", turn_id="a" * 32,
        )

        posts, head = await wc.pull(bob_home, wg.meta.id)
        assert head == 1
        assert len(posts) == 1
        assert posts[0]["text"] == "hi via wc"
        assert posts[0]["turn_id"] == "a" * 32
        sub_after = sub_mod.get(bob_home, wg.meta.id)
        assert sub_after.last_seq == 1

        posts2, _ = await wc.pull(bob_home, wg.meta.id)
        assert posts2 == []
    finally:
        peers_mod.local_socket_path = original_resolver
        await server.stop()


def _stub_member_sub(home: Path) -> None:
    load_or_generate(home)
    sub = sub_mod.Subscription(
        wg_id="wg_test", name="x", hub_id="alice",
        hub_pubkey="a" * 44,
    )
    sub.upsert_key(1, "sealed-stub")
    sub_mod.upsert(home, sub)


@pytest.mark.asyncio
async def test_post_rejects_non_hub_task(short_tmp: Path) -> None:
    """A member never opens tasks: `#task` (and the ambiguous
    `#task`+`#done` open-and-close combo) is rejected before encryption."""
    bob_home = short_tmp / "bob"; bob_home.mkdir()
    _stub_member_sub(bob_home)

    with pytest.raises(ValueError, match="only the workgroup hub"):
        await wc.post(bob_home, "wg_test", b"#task #sub-task spawn sub-task")

    with pytest.raises(ValueError, match="only the workgroup hub"):
        await wc.post(
            bob_home, "wg_test", b"#task #x do it\n#done already did it",
        )


@pytest.mark.asyncio
async def test_post_strips_non_hub_done_marker(short_tmp: Path) -> None:
    """A member's `#done <handoff>` is NOT dropped — the hub-only close marker
    is stripped and the substantive handoff survives (so the hub still sees the
    deliverable). The stub key makes it fail downstream at encryption, but
    crucially NOT at the marker gate."""
    bob_home = short_tmp / "bob"; bob_home.mkdir()
    _stub_member_sub(bob_home)

    with pytest.raises(Exception) as exc:
        await wc.post(
            bob_home, "wg_test", b"#done build green \xc2\xb7 dist generated",
        )
    assert "only the workgroup hub" not in str(exc.value)

    # A `#done` whose payload strips to nothing carries no handoff → rejected.
    with pytest.raises(ValueError, match="no handoff text"):
        await wc.post(bob_home, "wg_test", b"#done    ")

    # A line-internal `#done` was never a marker; it posts as plain prose
    # (fails only downstream on the stub key, not at the marker gate).
    with pytest.raises(Exception) as exc2:
        await wc.post(bob_home, "wg_test", b"converge with #done eventually")
    assert "only the workgroup hub" not in str(exc2.value)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pull_picks_up_rotated_key(short_tmp: Path) -> None:
    """Pull refreshes the sealed key after a hub-side rotation."""
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
    from alpi.alp import peers as peers_mod
    original = peers_mod.local_socket_path
    peers_mod.local_socket_path = lambda peer: server.socket_path()
    try:
        await wc.join(bob_home, "alice", wg.meta.id)
        wg_mod.kick(hub_home, wg.meta.id, carol_kp.pubkey_b64())

        await wc.pull(bob_home, wg.meta.id)
        sub = sub_mod.get(bob_home, wg.meta.id)
        assert sub.latest_version() == 2

        await wc.post(bob_home, wg.meta.id, b"after rotate")
        posts, head = await wc.pull(bob_home, wg.meta.id)
        assert head == 1
        assert posts[0]["text"] == "after rotate"
        assert posts[0]["key_version"] == 2
    finally:
        peers_mod.local_socket_path = original
        await server.stop()


@pytest.mark.integration
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
    from alpi.alp import peers as peers_mod
    original = peers_mod.local_socket_path
    peers_mod.local_socket_path = lambda peer: server.socket_path()
    try:
        await wc.join(bob_home, "alice", wg.meta.id)
        assert sub_mod.get(bob_home, wg.meta.id) is not None
        await wc.leave(bob_home, wg.meta.id)
        assert sub_mod.get(bob_home, wg.meta.id) is None
    finally:
        peers_mod.local_socket_path = original
        await server.stop()


@pytest.mark.asyncio
async def test_post_without_subscription_raises(short_tmp: Path) -> None:
    home = short_tmp / "bob"; home.mkdir()
    load_or_generate(home)
    with pytest.raises(ValueError, match="not subscribed"):
        await wc.post(home, "wg_unknown", b"hello")


@pytest.mark.asyncio
async def test_post_rejects_task_without_slug(short_tmp: Path) -> None:
    """SDK gate: `#task` posts must carry a `#<slug>` or the SDK refuses to encrypt them, regardless of whether the caller is the hub or a member."""
    home = short_tmp / "bob"; home.mkdir()
    load_or_generate(home)
    with pytest.raises(ValueError, match="task-missing-slug"):
        await wc.post(home, "wg_unknown", b"#task no slug here")
    # Slug present → falls through to the subscription check (not the shape check).
    with pytest.raises(ValueError, match="not subscribed"):
        await wc.post(home, "wg_unknown", b"#task #valid-slug with title")


def test_resolve_hub_rejects_unpinned_peer(short_tmp: Path) -> None:
    home = short_tmp / "bob"; home.mkdir()
    load_or_generate(home)
    with pytest.raises(ValueError, match="not pinned"):
        wc._resolve_hub(home, "ghost")


def test_absorb_roster_captures_bios(short_tmp: Path) -> None:
    sub = sub_mod.Subscription(
        wg_id="wg_x", name="x", hub_id="h", hub_pubkey="hk",
    )
    raw = [
        {"pubkey": "PK_A", "last_seen_at": "2026-04-26T10:00:00Z",
         "bio": "product engineer — velocity"},
        {"pubkey": "PK_B", "last_seen_at": "2026-04-26T10:00:00Z",
         "bio": ""},
        {"pubkey": "PK_C", "last_seen_at": ""},
    ]
    wc._absorb_roster(sub, raw)
    assert sub.roster == {
        "PK_A": "2026-04-26T10:00:00Z",
        "PK_B": "2026-04-26T10:00:00Z",
        "PK_C": "",
    }
    assert sub.roster_bios == {"PK_A": "product engineer — velocity"}


def test_subscription_persists_roster_bios(short_tmp: Path) -> None:
    home = short_tmp / "alice"; home.mkdir()
    sub = sub_mod.Subscription(
        wg_id="wg1", name="x", hub_id="h", hub_pubkey="hk",
        roster={"PK_A": "stamp"},
        roster_bios={"PK_A": "product engineer — velocity"},
    )
    sub_mod.upsert(home, sub)
    reloaded = sub_mod.get(home, "wg1")
    assert reloaded is not None
    assert reloaded.roster_bios == {"PK_A": "product engineer — velocity"}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_join_propagates_public_bio_to_hub(short_tmp: Path) -> None:
    from alpi import config as cfg_mod

    hub_home = short_tmp / "alice"; hub_home.mkdir()
    bob_home = short_tmp / "bob"; bob_home.mkdir()
    alice_kp = load_or_generate(hub_home)
    bob_kp = load_or_generate(bob_home)
    _pin(hub_home, "bob", bob_kp.pubkey_b64(),
         ["workgroup.join", "workgroup.post", "workgroup.pull"])
    _pin(bob_home, "alice", alice_kp.pubkey_b64(), ["link.ping"])

    bob_cfg = cfg_mod.load(bob_home)
    bob_cfg.public_bio = "systems engineer — durability bias"
    cfg_mod.save(bob_cfg)

    wg = wg_mod.create(
        hub_home, name="design", hub_kp=alice_kp,
        member_pubkeys=[bob_kp.pubkey_b64()],
        hub_bio="product engineer — velocity",
    )

    server = alp_server.Server(home=hub_home, agent_name="alice")
    wg_mod.register(server, hub_home)
    await server.start()
    from alpi.alp import peers as peers_mod
    original = peers_mod.local_socket_path
    peers_mod.local_socket_path = lambda peer: server.socket_path()
    try:
        sub = await wc.join(bob_home, "alice", wg.meta.id)
    finally:
        peers_mod.local_socket_path = original
        await server.stop()

    assert sub.roster_bios.get(bob_kp.pubkey_b64()) == \
        "systems engineer — durability bias"
    assert sub.roster_bios.get(alice_kp.pubkey_b64()) == \
        "product engineer — velocity"

    wg_after = wg_mod.load(hub_home, wg.meta.id)
    bob_member = wg_after.member(bob_kp.pubkey_b64())
    assert bob_member is not None
    assert bob_member.bio == "systems engineer — durability bias"


def test_member_bio_persists_on_disk(short_tmp: Path) -> None:
    home = short_tmp / "alice"; home.mkdir()
    alice_kp = load_or_generate(home)
    wg = wg_mod.create(
        home, name="design", hub_kp=alice_kp, member_pubkeys=[],
        hub_bio="product engineer — velocity",
    )
    reloaded = wg_mod.load(home, wg.meta.id)
    hub = reloaded.member(alice_kp.pubkey_b64())
    assert hub is not None
    assert hub.bio == "product engineer — velocity"


def test_absorb_roster_captures_voices(short_tmp: Path) -> None:
    sub = sub_mod.Subscription(
        wg_id="wg_x", name="x", hub_id="h", hub_pubkey="hk",
    )
    raw = [
        {"pubkey": "PK_A", "last_seen_at": "2026-04-26T10:00:00Z",
         "voice": "en-US-GuyNeural"},
        {"pubkey": "PK_B", "last_seen_at": "2026-04-26T10:00:00Z",
         "voice": ""},
        {"pubkey": "PK_C", "last_seen_at": ""},
    ]
    wc._absorb_roster(sub, raw)
    assert sub.roster_voices == {"PK_A": "en-US-GuyNeural"}


def test_subscription_persists_roster_voices(short_tmp: Path) -> None:
    home = short_tmp / "alice"; home.mkdir()
    sub = sub_mod.Subscription(
        wg_id="wg1", name="x", hub_id="h", hub_pubkey="hk",
        roster={"PK_A": "stamp"},
        roster_voices={"PK_A": "en-US-GuyNeural"},
    )
    sub_mod.upsert(home, sub)
    reloaded = sub_mod.get(home, "wg1")
    assert reloaded is not None
    assert reloaded.roster_voices == {"PK_A": "en-US-GuyNeural"}


def test_auto_join_local_propagates_voice_and_bio(
    short_tmp: Path, monkeypatch,
) -> None:
    """``wg_mod.create()`` calls ``_auto_join_local_members`` which is
    supposed to pick up each local member's ``public_bio`` and
    ``tools.tts.voice`` and (a) stamp them on the hub's Member record,
    (b) seed the member's subscriptions.yaml with the *fresh* roster
    bios/voices — not a snapshot taken before the update. Regression
    guard for a two-pass-required ordering bug."""
    from alpi import config as cfg_mod
    from alpi import home as home_mod

    profiles_root = short_tmp / "profiles"
    profiles_root.mkdir()
    monkeypatch.setattr(home_mod, "_ROOT", short_tmp)

    alice_home = profiles_root / "alice"; alice_home.mkdir()
    bob_home = profiles_root / "bob"; bob_home.mkdir()
    alice_kp = load_or_generate(alice_home)
    bob_kp = load_or_generate(bob_home)

    cfg_a = cfg_mod.Config(home=alice_home, model="x")
    cfg_a.public_bio = "hub bio"
    cfg_a.tools.tts.voice = "en-US-AriaNeural"
    cfg_mod.save(cfg_a)
    cfg_b = cfg_mod.Config(home=bob_home, model="x")
    cfg_b.public_bio = "member bio"
    cfg_b.tools.tts.voice = "en-US-GuyNeural"
    cfg_mod.save(cfg_b)

    _pin(bob_home, "alice", alice_kp.pubkey_b64(),
         ["workgroup.join", "workgroup.post", "workgroup.pull"])

    wg = wg_mod.create(
        alice_home, name="design", hub_kp=alice_kp,
        member_pubkeys=[bob_kp.pubkey_b64()],
        hub_bio="hub bio", hub_voice="en-US-AriaNeural",
    )

    reloaded = wg_mod.load(alice_home, wg.meta.id)
    bob_member = reloaded.member(bob_kp.pubkey_b64())
    assert bob_member is not None
    assert bob_member.bio == "member bio"
    assert bob_member.voice == "en-US-GuyNeural"

    sub = sub_mod.get(bob_home, wg.meta.id)
    assert sub is not None
    assert sub.roster_voices.get(bob_kp.pubkey_b64()) == "en-US-GuyNeural"
    assert sub.roster_voices.get(alice_kp.pubkey_b64()) == "en-US-AriaNeural"
    assert sub.roster_bios.get(bob_kp.pubkey_b64()) == "member bio"


def test_auto_join_local_persists_voice_change_on_rerun(
    short_tmp: Path, monkeypatch,
) -> None:
    """members_changed must flip on bio/voice deltas, not only on first-time join."""
    from alpi import config as cfg_mod
    from alpi import home as home_mod

    profiles_root = short_tmp / "profiles"
    profiles_root.mkdir()
    monkeypatch.setattr(home_mod, "_ROOT", short_tmp)

    alice_home = profiles_root / "alice"; alice_home.mkdir()
    bob_home = profiles_root / "bob"; bob_home.mkdir()
    alice_kp = load_or_generate(alice_home)
    bob_kp = load_or_generate(bob_home)

    cfg_a = cfg_mod.Config(home=alice_home, model="x")
    cfg_mod.save(cfg_a)
    cfg_b = cfg_mod.Config(home=bob_home, model="x")
    cfg_b.tools.tts.voice = "en-US-GuyNeural"
    cfg_mod.save(cfg_b)
    _pin(bob_home, "alice", alice_kp.pubkey_b64(),
         ["workgroup.join", "workgroup.post", "workgroup.pull"])

    wg = wg_mod.create(
        alice_home, name="design", hub_kp=alice_kp,
        member_pubkeys=[bob_kp.pubkey_b64()],
    )

    cfg_b = cfg_mod.load(bob_home)
    cfg_b.tools.tts.voice = "en-GB-RyanNeural"
    cfg_mod.save(cfg_b)
    wg_mod._auto_join_local_members(alice_home, wg_mod.load(alice_home, wg.meta.id))

    reloaded = wg_mod.load(alice_home, wg.meta.id)
    bob_member = reloaded.member(bob_kp.pubkey_b64())
    assert bob_member.voice == "en-GB-RyanNeural"


def test_member_voice_persists_on_disk(short_tmp: Path) -> None:
    home = short_tmp / "alice"; home.mkdir()
    alice_kp = load_or_generate(home)
    wg = wg_mod.create(
        home, name="design", hub_kp=alice_kp, member_pubkeys=[],
        hub_voice="en-US-AriaNeural",
    )
    reloaded = wg_mod.load(home, wg.meta.id)
    hub = reloaded.member(alice_kp.pubkey_b64())
    assert hub is not None
    assert hub.voice == "en-US-AriaNeural"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_join_propagates_tts_voice_to_hub(short_tmp: Path) -> None:
    from alpi import config as cfg_mod

    hub_home = short_tmp / "alice"; hub_home.mkdir()
    bob_home = short_tmp / "bob"; bob_home.mkdir()
    alice_kp = load_or_generate(hub_home)
    bob_kp = load_or_generate(bob_home)
    _pin(hub_home, "bob", bob_kp.pubkey_b64(),
         ["workgroup.join", "workgroup.post", "workgroup.pull"])
    _pin(bob_home, "alice", alice_kp.pubkey_b64(), ["link.ping"])

    bob_cfg = cfg_mod.load(bob_home)
    bob_cfg.tools.tts.voice = "en-US-GuyNeural"
    cfg_mod.save(bob_cfg)

    wg = wg_mod.create(
        hub_home, name="design", hub_kp=alice_kp,
        member_pubkeys=[bob_kp.pubkey_b64()],
        hub_voice="en-US-AriaNeural",
    )

    server = alp_server.Server(home=hub_home, agent_name="alice")
    wg_mod.register(server, hub_home)
    await server.start()
    from alpi.alp import peers as peers_mod
    original = peers_mod.local_socket_path
    peers_mod.local_socket_path = lambda peer: server.socket_path()
    try:
        sub = await wc.join(bob_home, "alice", wg.meta.id)
    finally:
        peers_mod.local_socket_path = original
        await server.stop()

    assert sub.roster_voices.get(bob_kp.pubkey_b64()) == "en-US-GuyNeural"
    assert sub.roster_voices.get(alice_kp.pubkey_b64()) == "en-US-AriaNeural"

    wg_after = wg_mod.load(hub_home, wg.meta.id)
    bob_member = wg_after.member(bob_kp.pubkey_b64())
    assert bob_member is not None
    assert bob_member.voice == "en-US-GuyNeural"


import datetime as _dt


def _now_iso() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ",
    )


def _post(seq: int, frm: str, text: str, ts: str | None = None) -> dict:
    return {"seq": seq, "from": frm, "text": text, "ts": ts or _now_iso()}


def test_check_substantive_rejects_empty() -> None:
    with pytest.raises(ValueError, match="empty post"):
        wc._check_substantive("")
    with pytest.raises(ValueError, match="empty post"):
        wc._check_substantive("   \n\t  ")


def test_check_substantive_allows_short_content() -> None:
    wc._check_substantive("Yes.")
    wc._check_substantive("Agreed — keep the kefir foam.")


def test_last_hub_seq_returns_zero_when_no_hub_post() -> None:
    posts = [_post(1, "BOB", "hi"), _post(2, "CAROL", "hey")]
    assert wc._last_hub_seq(posts, "HUB") == 0


def test_last_hub_seq_returns_highest_hub_seq() -> None:
    posts = [
        _post(1, "HUB", "#task #x X"),
        _post(2, "BOB", "answer"),
        _post(3, "HUB", "follow-up"),
        _post(4, "CAROL", "comment"),
    ]
    assert wc._last_hub_seq(posts, "HUB") == 3


def test_current_round_posts_excludes_hub_opener() -> None:
    posts = [
        _post(1, "HUB", "#task #x X"),
        _post(2, "BOB", "first"),
        _post(3, "CAROL", "second"),
    ]
    cur = wc._current_round_posts(posts, "HUB")
    assert [p["seq"] for p in cur] == [2, 3]


def test_current_round_resets_on_each_hub_post() -> None:
    posts = [
        _post(1, "HUB", "#task"),
        _post(2, "BOB", "r1"),
        _post(3, "HUB", "follow-up"),
        _post(4, "CAROL", "r2"),
    ]
    cur = wc._current_round_posts(posts, "HUB")
    assert [p["seq"] for p in cur] == [4]


def test_member_rotation_first_post_allowed() -> None:
    posts = [_post(1, "HUB", "#task #x X")]
    wc._check_member_rotation(posts, "BOB", "HUB", "my take")


def test_member_rotation_blocks_second_substantive_in_same_round() -> None:
    posts = [
        _post(1, "HUB", "#task #x X"),
        _post(2, "BOB", "first take"),
    ]
    with pytest.raises(ValueError, match="turn-rotation"):
        wc._check_member_rotation(posts, "BOB", "HUB", "second take")


def test_member_rotation_allows_substantive_after_own_working() -> None:
    posts = [
        _post(1, "HUB", "#task #x X"),
        _post(2, "BOB", "#working researching"),
    ]
    wc._check_member_rotation(posts, "BOB", "HUB", "my findings")


def test_member_rotation_blocks_double_working_in_same_round() -> None:
    posts = [
        _post(1, "HUB", "#task #x X"),
        _post(2, "BOB", "#working researching"),
    ]
    with pytest.raises(ValueError, match="already posted `#working`"):
        wc._check_member_rotation(posts, "BOB", "HUB", "#working still going")


def test_member_rotation_resets_after_hub_speaks() -> None:
    posts = [
        _post(1, "HUB", "#task #x X"),
        _post(2, "BOB", "first round answer"),
        _post(3, "HUB", "follow-up question"),
    ]
    wc._check_member_rotation(posts, "BOB", "HUB", "second round answer")


def test_member_round_fresh_no_op_without_env_var(monkeypatch) -> None:
    monkeypatch.delenv("ALPI_WORKGROUP_ROUND_HUB_SEQ", raising=False)
    posts = [_post(1, "HUB", "#task #x X"), _post(2, "HUB", "follow")]
    wc._check_member_round_fresh(posts, "HUB")


def test_member_round_fresh_passes_when_round_matches(monkeypatch) -> None:
    monkeypatch.setenv("ALPI_WORKGROUP_ROUND_HUB_SEQ", "3")
    posts = [
        _post(1, "HUB", "#task"),
        _post(2, "BOB", "x"),
        _post(3, "HUB", "follow"),
    ]
    wc._check_member_round_fresh(posts, "HUB")


def test_member_round_fresh_aborts_when_hub_advanced(monkeypatch) -> None:
    monkeypatch.setenv("ALPI_WORKGROUP_ROUND_HUB_SEQ", "1")
    posts = [
        _post(1, "HUB", "#task"),
        _post(2, "BOB", "x"),
        _post(3, "HUB", "second-task"),
    ]
    with pytest.raises(ValueError, match="stale-round"):
        wc._check_member_round_fresh(posts, "HUB")


def test_hub_reposting_active_slug_is_rejected() -> None:
    # A stalled task (no member response yet) may be re-tasked with the same slug; the duplicate is only rejected once members responded.
    posts = [
        _post(1, "HUB", "@bob #task #translation translate everything"),
        _post(2, "BOB", "#working translating the catalogue"),
    ]
    with pytest.raises(ValueError, match="task-already-active"):
        wc._check_hub_rotation(posts, "HUB", "@bob #task #translation translate everything again", ["BOB"])


def test_hub_may_preempt_with_a_different_slug() -> None:
    posts = [_post(1, "HUB", "@bob #task #translation translate everything")]
    wc._check_hub_rotation(posts, "HUB", "@bob #task #translation-fix redo the German entries", ["BOB"])


def test_closure_only_rejects_content_when_env_set(monkeypatch) -> None:
    monkeypatch.setenv("ALPI_WORKGROUP_CLOSURE_ONLY", "1")
    with pytest.raises(ValueError, match="closure-only"):
        wc._check_closure_only("fresh content that would reopen the round")


def test_closure_only_allows_done_when_env_set(monkeypatch) -> None:
    monkeypatch.setenv("ALPI_WORKGROUP_CLOSURE_ONLY", "1")
    wc._check_closure_only("#done wrapped up · artifact verified")


def test_closure_only_no_op_without_env(monkeypatch) -> None:
    monkeypatch.delenv("ALPI_WORKGROUP_CLOSURE_ONLY", raising=False)
    wc._check_closure_only("plain content posts fine")


def test_hub_rotation_allows_speaking_after_member() -> None:
    posts = [_post(1, "HUB", "#task"), _post(2, "BOB", "answer")]
    wc._check_hub_rotation(posts, "HUB", "follow-up content", ["BOB", "CAROL"])


def test_hub_rotation_blocks_back_to_back_content() -> None:
    posts = [_post(1, "HUB", "#task #x X")]
    with pytest.raises(ValueError, match="turn-rotation"):
        wc._check_hub_rotation(posts, "HUB", "more content", ["BOB"])


def test_hub_rotation_ignores_working_when_computing_last_poster() -> None:
    posts = [
        _post(1, "HUB", "#task #x X"),
        _post(2, "BOB", "#working researching"),
    ]
    with pytest.raises(ValueError, match="turn-rotation"):
        wc._check_hub_rotation(
            posts, "HUB", "sneaky content", ["BOB", "CAROL"],
        )


def test_hub_rotation_allows_done_after_member_substantive() -> None:
    posts = [
        _post(1, "HUB", "#task #x X"),
        _post(2, "BOB", "substantive answer"),
        _post(3, "CAROL", "#skip no angle"),
    ]
    wc._check_hub_rotation(posts, "HUB", "#done synthesis", ["BOB", "CAROL"])


def test_hub_rotation_blocks_done_when_member_pending() -> None:
    posts = [
        _post(1, "HUB", "#task #x X"),
        _post(2, "BOB", "answer"),
    ]
    with pytest.raises(ValueError, match="closure-quorum"):
        wc._check_hub_rotation(posts, "HUB", "#done foo", ["BOB", "CAROL"])


def test_hub_rotation_blocks_done_when_only_working_from_member() -> None:
    posts = [
        _post(1, "HUB", "#task #x X"),
        _post(2, "BOB", "answer"),
        _post(3, "CAROL", "#working researching"),
    ]
    with pytest.raises(ValueError, match="closure-quorum"):
        wc._check_hub_rotation(posts, "HUB", "#done foo", ["BOB", "CAROL"])


def test_hub_rotation_blocks_done_when_all_skip_no_substantive() -> None:
    posts = [
        _post(1, "HUB", "#task #x X"),
        _post(2, "BOB", "#skip"),
        _post(3, "CAROL", "#skip"),
    ]
    with pytest.raises(ValueError, match="closure-quorum"):
        wc._check_hub_rotation(posts, "HUB", "#done foo", ["BOB", "CAROL"])


def test_hub_rotation_done_allowed_after_timeout_even_when_pending() -> None:
    eleven_min_ago = (
        _dt.datetime.now(tz=_dt.timezone.utc) - _dt.timedelta(minutes=11)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    posts = [
        _post(1, "HUB", "#task #x X", ts=eleven_min_ago),
        _post(2, "BOB", "answer", ts=eleven_min_ago),
    ]
    wc._check_hub_rotation(
        posts, "HUB", "#done timeout escape", ["BOB", "CAROL"],
    )


def test_hub_rotation_custom_quorum_timeout_allows_earlier_close() -> None:
    two_min_ago = (
        _dt.datetime.now(tz=_dt.timezone.utc) - _dt.timedelta(minutes=2)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    posts = [
        _post(1, "HUB", "#task #x X", ts=two_min_ago),
        _post(2, "BOB", "answer", ts=two_min_ago),
    ]
    # Default 10-min timeout: CAROL still pending → blocked.
    with pytest.raises(ValueError, match="closure-quorum"):
        wc._check_hub_rotation(posts, "HUB", "#done foo", ["BOB", "CAROL"])
    # 60s timeout: 2 min elapsed > 60s → close allowed.
    wc._check_hub_rotation(posts, "HUB", "#done foo", ["BOB", "CAROL"], 60)


def test_hub_rotation_custom_quorum_timeout_can_extend() -> None:
    eleven_min_ago = (
        _dt.datetime.now(tz=_dt.timezone.utc) - _dt.timedelta(minutes=11)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    posts = [
        _post(1, "HUB", "#task #x X", ts=eleven_min_ago),
        _post(2, "BOB", "answer", ts=eleven_min_ago),
    ]
    with pytest.raises(ValueError, match="closure-quorum"):
        wc._check_hub_rotation(
            posts, "HUB", "#done foo", ["BOB", "CAROL"], 30 * 60,
        )


def test_hub_rotation_task_always_allowed_even_back_to_back() -> None:
    posts = [_post(1, "HUB", "#task #original original")]
    wc._check_hub_rotation(
        posts, "HUB", "#task #new-direction new direction", ["BOB", "CAROL"],
    )


def test_hub_rotation_done_allowed_when_unnamed_member_absent() -> None:
    """Targeted task: the close is allowed on the named participant's
    substantive post even though other members never posted — they were
    not on the task roster, so they don't block the quorum."""
    posts = [
        _post(1, "HUB", "@scout #task #intake produce intake"),
        _post(2, "SCOUT_PK", "intake.md + info.json on disk"),
    ]
    wc._check_hub_rotation(posts, "HUB", "#done verified", ["SCOUT_PK"])


def _fake_wg(
    hub_pubkey: str,
    member_pubkeys: list[str],
    pipelines: dict | None = None,
    launch_pipeline: str | None = None,
    pipeline_steps: dict | None = None,
):
    import types
    chains = {k: tuple(v) for k, v in (pipelines or {}).items()}
    return types.SimpleNamespace(
        meta=types.SimpleNamespace(
            id="wg_fake",
            hub_pubkey=hub_pubkey,
            pipelines=chains,
            launch_pipeline=launch_pipeline,
            pipeline_steps=pipeline_steps or {},
        ),
        members=[types.SimpleNamespace(pubkey=pk) for pk in member_pubkeys],
    )


def test_quorum_roster_narrows_to_named_participants(short_tmp: Path) -> None:
    home = short_tmp / "hub"; home.mkdir()
    _pin(home, "scout", "SCOUT_PK", ["workgroup.post"])
    _pin(home, "canvas", "CANVAS_PK", ["workgroup.post"])
    wg = _fake_wg("HUB", ["SCOUT_PK", "CANVAS_PK"])
    posts = [{"seq": 1, "from": "HUB", "text": "@scout #task #intake produce"}]
    roster = wc._quorum_roster(home, wg, posts, ["SCOUT_PK", "CANVAS_PK"])
    assert roster == ["SCOUT_PK"]


def test_quorum_roster_full_for_collective_task(short_tmp: Path) -> None:
    home = short_tmp / "hub2"; home.mkdir()
    _pin(home, "scout", "SCOUT_PK", ["workgroup.post"])
    _pin(home, "canvas", "CANVAS_PK", ["workgroup.post"])
    wg = _fake_wg("HUB", ["SCOUT_PK", "CANVAS_PK"])
    posts = [{"seq": 1, "from": "HUB", "text": "#task #intake produce"}]
    roster = wc._quorum_roster(home, wg, posts, ["SCOUT_PK", "CANVAS_PK"])
    assert roster == ["SCOUT_PK", "CANVAS_PK"]


def test_leave_purges_local_subscription_when_hub_unreachable(
    short_tmp: Path,
) -> None:
    home = short_tmp / "bob"; home.mkdir()
    load_or_generate(home)
    sub = sub_mod.Subscription(
        wg_id="wg_orphan", name="ghosted", hub_id="ghost_hub",
        hub_pubkey="ZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZw=",
    )
    sub.upsert_key(1, "sealed_blob_placeholder")
    sub_mod.upsert(home, sub)
    assert sub_mod.get(home, "wg_orphan") is not None

    result = asyncio.run(wc.leave(home, "wg_orphan"))
    assert result.get("hub_unreachable") is True
    assert sub_mod.get(home, "wg_orphan") is None


def test_leave_rejects_unknown_workgroup(short_tmp: Path) -> None:
    home = short_tmp / "alice"; home.mkdir()
    load_or_generate(home)
    with pytest.raises(ValueError, match="not subscribed"):
        asyncio.run(wc.leave(home, "wg_does_not_exist"))


@pytest.mark.asyncio
async def test_post_as_hub_emits_wg_post_event(
    short_tmp: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every hub post fires `wg.post` so live clients (mobile) refresh the
    transcript without a filesystem watcher. Desktop has a Tauri fs-watcher
    so this event is technically redundant there, but emission is cheap and
    keeps both runtimes on the same event bus."""
    hub_home = short_tmp / "alice"; hub_home.mkdir()
    hub_kp = load_or_generate(hub_home)
    wg = wg_mod.create(
        hub_home, name="design", hub_kp=hub_kp, member_pubkeys=[],
    )

    captured: list[tuple[str, dict]] = []
    import alpi.host.events as host_events
    monkeypatch.setattr(
        host_events, "emit",
        lambda kind, data=None: captured.append((kind, data or {})),
    )

    await wc.post(hub_home, wg.meta.id, b"hello team")

    posts = [(k, d) for (k, d) in captured if k == "wg.post"]
    dones = [(k, d) for (k, d) in captured if k == "wg.done"]
    assert len(posts) == 1, f"expected one wg.post, got {captured}"
    assert posts[0][1]["wg_id"] == wg.meta.id
    assert isinstance(posts[0][1].get("seq"), int)
    # Plain message without a #done marker → no wg.done.
    assert dones == []


@pytest.mark.asyncio
async def test_post_as_hub_persists_turn_id(short_tmp: Path) -> None:
    hub_home = short_tmp / "alice"; hub_home.mkdir()
    hub_kp = load_or_generate(hub_home)
    wg = wg_mod.create(
        hub_home, name="design", hub_kp=hub_kp, member_pubkeys=[],
    )

    await wc.post(
        hub_home, wg.meta.id, b"hello team", turn_id="b" * 32,
    )

    raw = wg_mod._read_transcript(wg_mod._wg_dir(hub_home, wg.meta.id))
    assert raw[0]["turn_id"] == "b" * 32


@pytest.mark.asyncio
async def test_post_rejects_invalid_turn_id(short_tmp: Path) -> None:
    home = short_tmp / "alice"; home.mkdir()
    with pytest.raises(ValueError, match="turn_id"):
        await wc.post(home, "wg_x", b"hello", turn_id="not-a-turn-id")


@pytest.mark.asyncio
async def test_post_as_hub_with_done_emits_both_events(
    short_tmp: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A `#done` marker fires wg.post AND wg.done — they are separate signals."""
    hub_home = short_tmp / "alice"; hub_home.mkdir()
    hub_kp = load_or_generate(hub_home)
    wg = wg_mod.create(
        hub_home, name="design", hub_kp=hub_kp, member_pubkeys=[],
    )

    captured: list[tuple[str, dict]] = []
    import alpi.host.events as host_events
    monkeypatch.setattr(
        host_events, "emit",
        lambda kind, data=None: captured.append((kind, data or {})),
    )

    await wc.post(hub_home, wg.meta.id, b"#done shipped to staging")

    kinds = [k for (k, _) in captured]
    assert "wg.post" in kinds
    assert "wg.done" in kinds


@pytest.mark.integration
@pytest.mark.asyncio
async def test_remote_member_post_emits_wg_post_on_hub(
    short_tmp: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When a remote member posts to the hub via ALP, the hub-side
    workgroup_post handler must also emit `wg.post` — otherwise a mobile
    client subscribed to the hub's host.events stream would never see incoming
    member transcript posts in real time (desktop watches the FS, mobile
    only has the event bus)."""
    hub_home = short_tmp / "alice"; hub_home.mkdir()
    bob_home = short_tmp / "bob"; bob_home.mkdir()
    alice_kp = load_or_generate(hub_home)
    bob_kp = load_or_generate(bob_home)
    _pin(hub_home, "bob", bob_kp.pubkey_b64(),
         ["workgroup.join", "workgroup.post", "workgroup.pull"])
    _pin(bob_home, "alice", alice_kp.pubkey_b64(), ["link.ping"])

    wg = wg_mod.create(
        hub_home, name="design", hub_kp=alice_kp,
        member_pubkeys=[bob_kp.pubkey_b64()],
    )

    server = alp_server.Server(home=hub_home, agent_name="alice")
    wg_mod.register(server, hub_home)
    await server.start()

    captured: list[tuple[str, dict]] = []
    import alpi.host.events as host_events
    monkeypatch.setattr(
        host_events, "emit",
        lambda kind, data=None: captured.append((kind, data or {})),
    )

    from alpi.alp import peers as peers_mod
    original_resolver = peers_mod.local_socket_path
    peers_mod.local_socket_path = lambda peer: server.socket_path()
    try:
        await wc.join(bob_home, "alice", wg.meta.id)
        await wc.post(bob_home, wg.meta.id, b"hi from bob")
    finally:
        peers_mod.local_socket_path = original_resolver
        await server.stop()

    posts = [(k, d) for (k, d) in captured if k == "wg.post"]
    # Bob's own emit (from workgroup_client._emit_wg_post) + Alice's hub-side emit (from workgroup.py::workgroup_post) — at least the hub-side one must be present.
    assert len(posts) >= 1, f"expected wg.post from hub server, got {captured}"
    hub_post = next(((k, d) for (k, d) in posts if d.get("profile") == "default"), None)
    assert hub_post is not None, (
        f"hub (alice) didn't emit wg.post on incoming remote member post; captured: {captured}"
    )
    assert hub_post[1]["wg_id"] == wg.meta.id
    assert isinstance(hub_post[1].get("seq"), int)


def test_emit_wg_mentions_fires_when_local_profile_is_mentioned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pulled posts that ``@``-mention the local profile name must produce a
    ``wg.mention`` host event so mobile ALN can surface them as notifications."""
    home = tmp_path / "profiles" / "vera"
    home.mkdir(parents=True)

    captured: list[tuple[str, dict]] = []
    import alpi.host.events as host_events
    monkeypatch.setattr(
        host_events, "emit",
        lambda kind, data=None: captured.append((kind, data or {})),
    )

    from alpi.alp.workgroup_client import _emit_wg_mentions
    posts = [
        {"seq": 7, "from": "peer_alice_pubkey", "text": "@vera can you look at this?"},
    ]
    _emit_wg_mentions(home, "wg_xyz", posts, own_pubkey="vera_pubkey")

    hits = [d for k, d in captured if k == "wg.mention"]
    assert len(hits) == 1
    assert hits[0]["profile"] == "vera"
    assert hits[0]["wg_id"] == "wg_xyz"
    assert hits[0]["seq"] == 7
    assert hits[0]["from"] == "peer_alice_pubkey"
    assert "@vera" in hits[0]["summary"]


def test_emit_wg_mentions_skips_self_posts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A profile mentioning itself in an outbound post must NOT generate a
    notification — that's a self-emit, not a peer mention."""
    home = tmp_path / "profiles" / "vera"
    home.mkdir(parents=True)

    captured: list[tuple[str, dict]] = []
    import alpi.host.events as host_events
    monkeypatch.setattr(
        host_events, "emit",
        lambda kind, data=None: captured.append((kind, data or {})),
    )

    from alpi.alp.workgroup_client import _emit_wg_mentions
    posts = [
        {"seq": 8, "from": "vera_pubkey", "text": "@vera taking this"},
    ]
    _emit_wg_mentions(home, "wg_xyz", posts, own_pubkey="vera_pubkey")

    assert [(k, d) for k, d in captured if k == "wg.mention"] == []


def test_emit_wg_mentions_skips_unrelated_mentions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A peer mentioning ``@alice`` in a workgroup where the local profile is
    ``vera`` must not fire — only mentions of the local profile count."""
    home = tmp_path / "profiles" / "vera"
    home.mkdir(parents=True)

    captured: list[tuple[str, dict]] = []
    import alpi.host.events as host_events
    monkeypatch.setattr(
        host_events, "emit",
        lambda kind, data=None: captured.append((kind, data or {})),
    )

    from alpi.alp.workgroup_client import _emit_wg_mentions
    posts = [
        {"seq": 9, "from": "bob_pubkey", "text": "@alice please review"},
    ]
    _emit_wg_mentions(home, "wg_xyz", posts, own_pubkey="vera_pubkey")

    assert [(k, d) for k, d in captured if k == "wg.mention"] == []


def test_emit_wg_mentions_does_not_match_emails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``foo@vera.com`` should not be treated as a mention of ``@vera`` — the
    regex requires a whitespace/start-of-line boundary before ``@``."""
    home = tmp_path / "profiles" / "vera"
    home.mkdir(parents=True)

    captured: list[tuple[str, dict]] = []
    import alpi.host.events as host_events
    monkeypatch.setattr(
        host_events, "emit",
        lambda kind, data=None: captured.append((kind, data or {})),
    )

    from alpi.alp.workgroup_client import _emit_wg_mentions
    posts = [
        {"seq": 10, "from": "bob", "text": "contact me at foo@vera.com for details"},
    ]
    _emit_wg_mentions(home, "wg_xyz", posts, own_pubkey="vera_pubkey")

    assert [(k, d) for k, d in captured if k == "wg.mention"] == []


def test_emit_wg_mentions_skips_seq_below_min_seq(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A re-pull with ``since=0`` (or any explicit replay) must NOT re-emit
    notifications for posts the caller already saw. ``min_seq`` is the cursor
    at the start of the pull — only ``seq > min_seq`` posts emit."""
    home = tmp_path / "profiles" / "vera"
    home.mkdir(parents=True)

    captured: list[tuple[str, dict]] = []
    import alpi.host.events as host_events
    monkeypatch.setattr(
        host_events, "emit",
        lambda kind, data=None: captured.append((kind, data or {})),
    )

    from alpi.alp.workgroup_client import _emit_wg_mentions
    posts = [
        {"seq": 3,  "from": "bob", "text": "@vera ping (old)"},   # below cursor
        {"seq": 5,  "from": "bob", "text": "@vera ping (cursor)"},  # at cursor — excluded
        {"seq": 7,  "from": "bob", "text": "@vera ping (new)"},   # above cursor
    ]
    _emit_wg_mentions(home, "wg_xyz", posts,
                      own_pubkey="vera_pubkey", min_seq=5)

    seqs = [d["seq"] for k, d in captured if k == "wg.mention"]
    assert seqs == [7], f"expected only seq=7 to emit, got {seqs}"


@pytest.mark.asyncio
async def test_pull_emits_wg_mention_for_remote_post_targeting_local(
    short_tmp: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end wiring: an incoming workgroup post that ``@``-mentions the
    local profile must produce a ``wg.mention`` host event when ``pull()`` runs.
    Guards against a refactor that silently drops the emit hook."""
    hub_home = short_tmp / "profiles" / "alice"; hub_home.mkdir(parents=True)
    bob_home = short_tmp / "profiles" / "vera"; bob_home.mkdir(parents=True)
    alice_kp = load_or_generate(hub_home)
    bob_kp = load_or_generate(bob_home)
    _pin(hub_home, "vera", bob_kp.pubkey_b64(),
         ["workgroup.join", "workgroup.post", "workgroup.pull",
          "workgroup.leave"])
    _pin(bob_home, "alice", alice_kp.pubkey_b64(),
         ["link.ping"])

    wg = wg_mod.create(
        hub_home, name="ops", hub_kp=alice_kp,
        member_pubkeys=[bob_kp.pubkey_b64()],
    )

    server = alp_server.Server(home=hub_home, agent_name="alice")
    wg_mod.register(server, hub_home)
    await server.start()

    captured: list[tuple[str, dict]] = []
    import alpi.host.events as host_events
    monkeypatch.setattr(
        host_events, "emit",
        lambda kind, data=None: captured.append((kind, data or {})),
    )

    from alpi.alp import peers as peers_mod
    original_resolver = peers_mod.local_socket_path
    peers_mod.local_socket_path = lambda peer: server.socket_path()
    try:
        await wc.join(bob_home, "alice", wg.meta.id)
        # Alice (hub) posts a message that mentions @vera (bob's profile).
        await wc.post(hub_home, wg.meta.id, b"@vera could you take this?")
        # Bob (vera) pulls — that's when the daemon should fire wg.mention.
        await wc.pull(bob_home, wg.meta.id)
    finally:
        peers_mod.local_socket_path = original_resolver
        await server.stop()

    mentions = [d for k, d in captured if k == "wg.mention"]
    vera_mentions = [d for d in mentions if d.get("profile") == "vera"]
    assert len(vera_mentions) >= 1, (
        f"expected wg.mention emit on vera's pull side; captured: {captured}"
    )
    m = vera_mentions[0]
    assert m["wg_id"] == wg.meta.id
    assert isinstance(m["seq"], int) and m["seq"] >= 1
    assert "@vera" in m["summary"]


@pytest.mark.asyncio
async def test_hub_emits_wg_mention_when_member_post_targets_hub_profile(
    short_tmp: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When a member posts a message mentioning the hub profile, the hub-side
    workgroup.post handler must decrypt the ciphertext and emit wg.mention so
    the hub's mobile/desktop also sees the alert."""
    hub_home = short_tmp / "profiles" / "alice"; hub_home.mkdir(parents=True)
    bob_home = short_tmp / "profiles" / "bob"; bob_home.mkdir(parents=True)
    alice_kp = load_or_generate(hub_home)
    bob_kp = load_or_generate(bob_home)
    _pin(hub_home, "bob", bob_kp.pubkey_b64(),
         ["workgroup.join", "workgroup.post", "workgroup.pull",
          "workgroup.leave"])
    _pin(bob_home, "alice", alice_kp.pubkey_b64(),
         ["link.ping"])

    wg = wg_mod.create(
        hub_home, name="ops", hub_kp=alice_kp,
        member_pubkeys=[bob_kp.pubkey_b64()],
    )

    server = alp_server.Server(home=hub_home, agent_name="alice")
    wg_mod.register(server, hub_home)
    await server.start()

    captured: list[tuple[str, dict]] = []
    import alpi.host.events as host_events
    monkeypatch.setattr(
        host_events, "emit",
        lambda kind, data=None: captured.append((kind, data or {})),
    )

    from alpi.alp import peers as peers_mod
    original_resolver = peers_mod.local_socket_path
    peers_mod.local_socket_path = lambda peer: server.socket_path()
    try:
        await wc.join(bob_home, "alice", wg.meta.id)
        await wc.post(bob_home, wg.meta.id, b"@alice can you take this?")
    finally:
        peers_mod.local_socket_path = original_resolver
        await server.stop()

    mentions = [d for k, d in captured if k == "wg.mention"]
    hub_mentions = [d for d in mentions if d.get("profile") == "alice"]
    assert len(hub_mentions) >= 1, (
        f"hub didn't emit wg.mention for incoming @alice post; captured: {captured}"
    )
    m = hub_mentions[0]
    assert m["wg_id"] == wg.meta.id
    assert "@alice" in m["summary"]


def test_validate_task_participants_rejects_unknown_member(short_tmp: Path) -> None:
    home = short_tmp / "hubv"; home.mkdir()
    _pin(home, "scout", "SCOUT_PK", ["workgroup.post"])
    wg = _fake_wg("HUB", ["SCOUT_PK"])
    # Naming a real member is fine.
    wc._validate_task_participants(home, wg, "@scout #task #intake go")
    # A typo / non-member must be rejected before it lands.
    with pytest.raises(ValueError, match="unknown-participant"):
        wc._validate_task_participants(home, wg, "@sout #task #intake go")


def test_validate_task_participants_allows_collective(short_tmp: Path) -> None:
    home = short_tmp / "hubv2"; home.mkdir()
    _pin(home, "scout", "SCOUT_PK", ["workgroup.post"])
    wg = _fake_wg("HUB", ["SCOUT_PK"])
    # No mention on the opener line = collective task = always allowed.
    wc._validate_task_participants(home, wg, "#task #intake go")


def test_validate_task_participants_ignores_non_task(short_tmp: Path) -> None:
    home = short_tmp / "hubv3"; home.mkdir()
    _pin(home, "scout", "SCOUT_PK", ["workgroup.post"])
    wg = _fake_wg("HUB", ["SCOUT_PK"])
    # A mention in plain prose (not a #task opener) is not validated.
    wc._validate_task_participants(home, wg, "thanks @sout for the help")


def test_subscription_pipeline_state_persists(short_tmp: Path) -> None:
    """Chain definitions propagated on join survive save/load, so member dispatch keeps the pipeline turn budget."""
    home = short_tmp / "m"; home.mkdir()
    sub = sub_mod.Subscription(
        wg_id="wg_p", name="proj", hub_id="mira", hub_pubkey="x" * 44,
        pipelines={
            "intake": ("intake", "design"),
            "media-update": ("media-update",),
        },
        launch_pipeline="intake",
        pipeline_mode=True,
        phase_map={"intake": {"owner": "scout", "task": "produce intake.md"}},
    )
    sub_mod.upsert(home, sub)
    loaded = sub_mod.get(home, "wg_p")
    assert loaded is not None
    assert loaded.pipelines == {
        "intake": ("intake", "design"),
        "media-update": ("media-update",),
    }
    assert loaded.launch_pipeline == "intake"
    assert loaded.pipeline_mode is True
    assert loaded.phase_map == {
        "intake": {"owner": "scout", "task": "produce intake.md"},
    }
    assert loaded.launch_chain == ("intake", "design")


def test_subscription_launch_chain_is_read_only_derived() -> None:
    """`launch_chain` is the selected chain, never a second authority."""
    sub = sub_mod.Subscription(
        wg_id="wg_p", name="proj", hub_id="mira", hub_pubkey="x" * 44,
        pipelines={"intake": ("intake", "design"), "media-update": ("media-update",)},
        launch_pipeline="media-update",
    )
    assert sub.launch_chain == ("media-update",)
    sub.launch_pipeline = None
    assert sub.launch_chain == ()
    assert not hasattr(sub, "pipeline")
    with pytest.raises(AttributeError):
        sub.launch_chain = ("nope",)


@pytest.mark.parametrize("retired", [
    "  pipeline:\n    - intake\n    - design\n",
    "  operations:\n    media-update:\n      - media-update\n",
])
def test_subscription_entry_on_the_retired_shape_is_skipped(
    short_tmp: Path, retired: str, caplog,
) -> None:
    home = short_tmp / "retired"; home.mkdir()
    p = sub_mod.path(home)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        "- wg_id: wg_old\n"
        "  name: proj\n"
        "  hub_id: mira\n"
        "  hub_pubkey: " + "x" * 44 + "\n"
        "  last_seq: 4\n" + retired,
    )
    with caplog.at_level("WARNING", logger="alpi.alp.subscription"):
        assert sub_mod.get(home, "wg_old") is None
        assert sub_mod.load(home) == []
    warnings = [r for r in caplog.records if "skipped" in r.message]
    assert len(warnings) == 1
    assert "wg_old" in warnings[0].getMessage()


def test_launchless_subscription_stays_in_pipeline_mode(short_tmp: Path) -> None:
    """Dormant-only chains still mean pipeline rules: `pipeline_mode` true, no launch selected, empty launch chain."""
    home = short_tmp / "idle"; home.mkdir()
    sub = sub_mod.Subscription(
        wg_id="wg_idle", name="proj", hub_id="mira", hub_pubkey="x" * 44,
    )
    sub.absorb_pipeline_state({
        "pipelines": {"media-update": ["media-update", "media-qa"]},
        "launch_pipeline": None,
        "pipeline_mode": True,
        "phase_map": {"media-update": {"owner": "muse"}},
    })
    assert sub.pipelines == {"media-update": ("media-update", "media-qa")}
    assert sub.launch_pipeline is None
    assert sub.pipeline_mode is True
    assert sub.launch_chain == ()
    sub_mod.upsert(home, sub)
    loaded = sub_mod.get(home, "wg_idle")
    assert loaded is not None
    assert loaded.pipeline_mode is True
    assert loaded.launch_pipeline is None
    assert loaded.pipelines == {"media-update": ("media-update", "media-qa")}


def test_phase_map_drops_gate_argv_and_cwd(short_tmp: Path) -> None:
    """A hub that ever leaked gate commands gets them stripped member-side, in memory and on disk."""
    home = short_tmp / "gk"; home.mkdir()
    sub = sub_mod.Subscription(
        wg_id="wg_g", name="proj", hub_id="mira", hub_pubkey="x" * 44,
    )
    sub.absorb_pipeline_state({
        "pipelines": {"intake": ["intake"]},
        "launch_pipeline": "intake",
        "phase_map": {
            "intake": {
                "owner": "scout", "task": "produce intake.md",
                "gate": {"argv": ["npm", "run", "check:config"], "cwd": "site"},
            },
        },
    })
    assert sub.phase_map == {
        "intake": {"owner": "scout", "task": "produce intake.md"},
    }
    sub_mod.upsert(home, sub)
    saved = yaml.safe_load(sub_mod.path(home).read_text())
    assert saved[0]["phase_map"]["intake"] == {
        "owner": "scout", "task": "produce intake.md",
    }


def test_validate_pipeline_task_requires_participants(short_tmp: Path) -> None:
    """In a pipeline workgroup a `#task` must be targeted (≥1 owner);
    a collective task (no mentions) is rejected before it lands."""
    home = short_tmp / "hubpipe"; home.mkdir()
    _pin(home, "pixel", "PIXEL_PK", ["workgroup.post"])
    wg = _fake_wg(
        "HUB", ["PIXEL_PK"],
        pipelines={"build": ["build"]}, launch_pipeline="build",
    )
    with pytest.raises(ValueError, match="pipeline-task-untargeted"):
        wc._validate_task_participants(home, wg, "#task #build do the build")
    # Targeted is fine.
    wc._validate_task_participants(home, wg, "@pixel #task #build do the build")


def test_validate_workflow_task_requires_declared_owner(short_tmp: Path) -> None:
    home = short_tmp / "hubowner"; home.mkdir()
    _pin(home, "muse", "MUSE_PK", ["workgroup.post"])
    _pin(home, "canvas", "CANVAS_PK", ["workgroup.post"])
    wg = _fake_wg(
        "HUB", ["MUSE_PK", "CANVAS_PK"],
        pipelines={"intake": ("intake",), "media-update": ("media-update",)},
        launch_pipeline="intake",
        pipeline_steps={
            "intake": {"owner": "muse"},
            "media-update": {"owner": "muse"},
        },
    )

    with pytest.raises(ValueError, match="workflow-task-owner-missing"):
        wc._validate_task_participants(
            home, wg, "@canvas #task #media-update install client media",
        )
    wc._validate_task_participants(
        home, wg, "@muse @canvas #task #media-update install client media",
    )


def test_gate_less_workflow_close_requires_declared_owner(short_tmp: Path) -> None:
    home = short_tmp / "hubclose"; home.mkdir()
    _pin(home, "muse", "MUSE_PK", ["workgroup.post"])
    _pin(home, "canvas", "CANVAS_PK", ["workgroup.post"])
    wg = _fake_wg(
        "HUB", ["MUSE_PK", "CANVAS_PK"],
        pipelines={"intake": ("intake",), "media-update": ("media-update",)},
        launch_pipeline="intake",
        pipeline_steps={
            "intake": {"owner": "muse"},
            "media-update": {"owner": "muse"},
        },
    )
    posts = [
        _post(1, "HUB", "@canvas #task #media-update install client media"),
        _post(2, "CANVAS_PK", "media installed"),
    ]

    with pytest.raises(ValueError, match="phase-owner-missing"):
        wc._check_pipeline_close_owner(
            home, wg, posts, "#done media update complete", "HUB",
        )

    posts.append(_post(3, "MUSE_PK", "verified media map"))
    assert wc._check_pipeline_close_owner(
        home, wg, posts, "#done media update complete", "HUB",
    ) is False


def test_validate_non_pipeline_collective_task_allowed(short_tmp: Path) -> None:
    """A non-pipeline (deliberation) workgroup still allows collective tasks."""
    home = short_tmp / "hubdelib"; home.mkdir()
    _pin(home, "pixel", "PIXEL_PK", ["workgroup.post"])
    wg = _fake_wg("HUB", ["PIXEL_PK"])
    wc._validate_task_participants(home, wg, "#task #adr decide the thing")


def test_quorum_roster_multi_participant(short_tmp: Path) -> None:
    """A multi-owner pipeline task scopes the quorum to all named peers."""
    home = short_tmp / "hubm"; home.mkdir()
    _pin(home, "pixel", "PIXEL_PK", ["workgroup.post"])
    _pin(home, "atlas", "ATLAS_PK", ["workgroup.post"])
    _pin(home, "quill", "QUILL_PK", ["workgroup.post"])
    wg = _fake_wg(
        "HUB", ["PIXEL_PK", "ATLAS_PK", "QUILL_PK"],
        pipelines={"build": ["build"]}, launch_pipeline="build",
    )
    posts = [{"seq": 1, "from": "HUB", "text": "@pixel @atlas #task #build go"}]
    roster = wc._quorum_roster(home, wg, posts, ["PIXEL_PK", "ATLAS_PK", "QUILL_PK"])
    assert set(roster) == {"PIXEL_PK", "ATLAS_PK"}  # quill not named → not in quorum


@pytest.mark.asyncio
async def test_pull_ignores_a_retired_pipeline_field_from_an_old_hub(
    short_tmp: Path, monkeypatch,
) -> None:
    """A hub still answering with `pipeline` declares no chain the member will honour."""
    home = short_tmp / "m"; home.mkdir()
    load_or_generate(home)
    sub = sub_mod.Subscription(
        wg_id="wg_p", name="proj", hub_id="hub", hub_pubkey="x" * 44,
    )
    sub.upsert_key(1, "sealed")
    sub_mod.upsert(home, sub)

    async def fake_call(*a, **k):
        return {"posts": [], "head": 0, "current_key_version": 1, "pipeline": ["intake", "design"]}

    monkeypatch.setattr(wc, "_call", fake_call)
    await wc.pull(home, "wg_p")
    reloaded = sub_mod.get(home, "wg_p")
    assert reloaded.pipelines == {}
    assert reloaded.launch_pipeline is None
    assert reloaded.launch_chain == ()
    assert reloaded.pipeline_mode is False


@pytest.mark.asyncio
async def test_pull_refreshes_changed_definitions_without_rejoin(
    short_tmp: Path, monkeypatch,
) -> None:
    """Hub-side chain edits (new chain, moved launch, new task text) reach an existing subscription on the next pull."""
    home = short_tmp / "m2"; home.mkdir()
    load_or_generate(home)
    sub = sub_mod.Subscription(
        wg_id="wg_r", name="proj", hub_id="hub", hub_pubkey="x" * 44,
        pipelines={"intake": ("intake", "qa")},
        launch_pipeline="intake",
        pipeline_mode=True,
        phase_map={"intake": {"owner": "scout", "task": "produce intake.md"}},
    )
    sub.upsert_key(1, "sealed")
    sub_mod.upsert(home, sub)

    payload = {
        "posts": [], "head": 0, "current_key_version": 1,
        "pipelines": {
            "media-update": ["media-update", "media-qa"],
            "intake": ["intake", "qa"],
        },
        "launch_pipeline": "media-update",
        "pipeline_mode": True,
        "phase_map": {
            "intake": {"owner": "scout", "task": "produce intake.md v2"},
            "media-update": {"owner": "muse", "task": "install client media"},
        },
    }

    async def fake_call(*a, **k):
        return payload

    monkeypatch.setattr(wc, "_call", fake_call)
    await wc.pull(home, "wg_r")

    reloaded = sub_mod.get(home, "wg_r")
    assert reloaded.pipelines == {
        "media-update": ("media-update", "media-qa"),
        "intake": ("intake", "qa"),
    }
    assert reloaded.launch_pipeline == "media-update"
    assert reloaded.launch_chain == ("media-update", "media-qa")
    assert reloaded.phase_map["intake"]["task"] == "produce intake.md v2"
    assert reloaded.phase_map["media-update"] == {
        "owner": "muse", "task": "install client media",
    }


def test_effective_profile_env_adds_node_when_missing(short_tmp: Path, monkeypatch) -> None:
    """When `npm` isn't on the inherited PATH, the agent env gets node bins
    prepended (so a terminal tool's `npm run build` resolves)."""
    from alpi import home as home_mod
    home = short_tmp / "p"; home.mkdir()
    monkeypatch.setattr(home_mod, "_node_bin_dirs", lambda: ["/fake/node/bin"])
    env = home_mod.effective_profile_env(home, base={"PATH": "/usr/bin:/bin"})
    assert "/fake/node/bin" in env["PATH"].split(":")
    # Idempotent / no-op when npm is already resolvable on PATH.
    import shutil
    monkeypatch.setattr(shutil, "which", lambda *a, **k: "/somewhere/npm")
    env2 = home_mod.effective_profile_env(home, base={"PATH": "/usr/bin:/bin"})
    assert "/fake/node/bin" not in env2["PATH"].split(":")


def test_pipelines_from_raw_degrades_junk_and_rejects_the_retired_shape() -> None:
    assert not hasattr(sub_mod, "coerce_pipeline")
    assert wg_mod.pipelines_from_raw({"pipelines": {"intake": ["intake", "design"]}}) == (
        {"intake": ("intake", "design")}, None,
    )
    for junk in (True, None, "nope", {"pipelines": "nope"}, {"pipelines": {"x": ["y"]}}):
        assert wg_mod.pipelines_from_raw(junk) == ({}, None)
    with pytest.raises(ValueError, match="declares retired"):
        wg_mod.pipelines_from_raw({"pipeline": ["intake", "design"]})


def test_load_parses_once_until_file_changes(short_tmp: Path, monkeypatch) -> None:
    home = short_tmp / "carol"; home.mkdir()
    sub = sub_mod.Subscription(
        wg_id="wg_cache", name="site", hub_id="hub",
        hub_pubkey="h" * 44, last_seq=1,
    )
    sub_mod.upsert(home, sub)

    from alpi import yamlfast
    calls = {"n": 0}
    real = yamlfast.safe_load

    def counting(text):
        calls["n"] += 1
        return real(text)

    monkeypatch.setattr(sub_mod.yamlfast, "safe_load", counting)
    sub_mod._invalidate_cache(sub_mod.path(home))

    first = sub_mod.load(home)
    second = sub_mod.load(home)
    third = sub_mod.get(home, "wg_cache")
    assert calls["n"] == 1, calls
    assert [s.wg_id for s in first] == [s.wg_id for s in second] == ["wg_cache"]
    assert third is not None and third.last_seq == 1

    sub.last_seq = 7
    sub_mod.upsert(home, sub)  # our own save writes through, so no re-parse
    reloaded = sub_mod.get(home, "wg_cache")
    assert reloaded is not None and reloaded.last_seq == 7
    assert calls["n"] == 1, calls


def test_cached_load_returns_independent_subscriptions(short_tmp: Path) -> None:
    home = short_tmp / "dave"; home.mkdir()
    sub = sub_mod.Subscription(
        wg_id="wg_iso", name="site", hub_id="hub",
        hub_pubkey="h" * 44,
    )
    sub.append_recent([{"seq": 1, "text": "hello"}])
    sub_mod.upsert(home, sub)

    a = sub_mod.get(home, "wg_iso")
    a.recent_posts[0]["text"] = "mutated"
    a.roster["x"] = "y"
    b = sub_mod.get(home, "wg_iso")
    assert b.recent_posts[0]["text"] == "hello"
    assert b.roster == {}


def test_external_write_busts_cache_via_mtime(short_tmp: Path, monkeypatch) -> None:
    home = short_tmp / "erin"; home.mkdir()
    sub = sub_mod.Subscription(
        wg_id="wg_ext", name="site", hub_id="hub",
        hub_pubkey="h" * 44, last_seq=1,
    )
    sub_mod.upsert(home, sub)

    from alpi import yamlfast
    calls = {"n": 0}
    real = yamlfast.safe_load

    def counting(text):
        calls["n"] += 1
        return real(text)

    monkeypatch.setattr(sub_mod.yamlfast, "safe_load", counting)
    sub_mod._invalidate_cache(sub_mod.path(home))

    assert sub_mod.get(home, "wg_ext").last_seq == 1
    assert calls["n"] == 1

    # external writer (another process): mutates the file directly, no _invalidate_cache in this process
    p = sub_mod.path(home)
    p.write_text(p.read_text().replace("last_seq: 1", "last_seq: 777"))

    refreshed = sub_mod.get(home, "wg_ext")
    assert refreshed is not None and refreshed.last_seq == 777
    assert calls["n"] == 2, calls


def _dormant_chain_hub(home: Path):
    muse_home = home.parent / f"{home.name}-muse"
    canvas_home = home.parent / f"{home.name}-canvas"
    muse_home.mkdir(exist_ok=True)
    canvas_home.mkdir(exist_ok=True)
    muse_pk = load_or_generate(muse_home).pubkey_b64()
    canvas_pk = load_or_generate(canvas_home).pubkey_b64()
    _pin(home, "muse", muse_pk, ["workgroup.post"])
    _pin(home, "canvas", canvas_pk, ["workgroup.post"])
    return wg_mod.create(
        home, name="site", hub_kp=load_or_generate(home),
        member_pubkeys=[muse_pk, canvas_pk],
        pipelines={
            "intake": ["intake", "qa"],
            "media-update": ["media-update", "media-qa"],
        },
        launch_pipeline="intake",
        pipeline_steps={
            "intake": {"owner": "muse"},
            "qa": {"owner": "muse"},
            "media-update": {"owner": "muse"},
            "media-qa": {"owner": "muse"},
        },
    )


@pytest.mark.asyncio
async def test_post_rejects_a_dormant_chain_task_targeted_at_the_wrong_owner(
    short_tmp: Path,
) -> None:
    home = short_tmp / "hubwrong"; home.mkdir()
    wg = _dormant_chain_hub(home)

    with pytest.raises(ValueError, match="workflow-task-owner-missing"):
        await wc.post(
            home, wg.meta.id,
            b"@canvas #task #media-update install client media",
        )


@pytest.mark.asyncio
async def test_post_rejects_closing_a_dormant_chain_phase_with_no_owner_delivery(
    short_tmp: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = short_tmp / "hub"; home.mkdir()
    wg = _dormant_chain_hub(home)

    await wc.post(home, wg.meta.id, b"@muse #task #media-update map the client media", operator_abandon=True)
    with pytest.raises(ValueError, match="phase-owner-missing"):
        await wc.post(home, wg.meta.id, b"#done media-update complete")


@pytest.mark.asyncio
async def test_post_allows_blocked_override_on_a_dormant_chain_phase(
    short_tmp: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = short_tmp / "hub"; home.mkdir()
    wg = _dormant_chain_hub(home)

    await wc.post(home, wg.meta.id, b"@muse #task #media-update map the client media", operator_abandon=True)
    out = await wc.post(
        home, wg.meta.id,
        "#done BLOCKED · media-update · logo format unsupported".encode(),
    )
    assert isinstance(out.get("seq"), int)


@pytest.mark.asyncio
async def test_automatic_hub_cannot_block_before_final_repair(
    short_tmp: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = short_tmp / "hubauto"
    home.mkdir()
    wg = _dormant_chain_hub(home)
    await wc.post(home, wg.meta.id, b"@muse #task #media-update map the client media", operator_abandon=True)
    monkeypatch.setenv("ALPI_WORKGROUP_DISPATCH", wg.meta.id)

    with pytest.raises(ValueError, match="pipeline-blocked-premature"):
        await wc.post(
            home, wg.meta.id,
            b"#done BLOCKED \xc2\xb7 media-update \xc2\xb7 owner stayed silent",
        )


@pytest.mark.asyncio
async def test_final_repair_may_block_a_pipeline(
    short_tmp: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = short_tmp / "hubfinal"
    home.mkdir()
    wg = _dormant_chain_hub(home)
    await wc.post(home, wg.meta.id, b"@muse #task #media-update map the client media", operator_abandon=True)
    monkeypatch.setenv("ALPI_WORKGROUP_DISPATCH", wg.meta.id)
    monkeypatch.setenv("ALPI_WORKGROUP_FINAL_REPAIR", "1")

    out = await wc.post(
        home, wg.meta.id,
        b"#done BLOCKED \xc2\xb7 media-update \xc2\xb7 owner stayed silent",
    )
    assert isinstance(out.get("seq"), int)


@pytest.mark.asyncio
async def test_post_allows_skipped_override_on_a_dormant_chain_phase(
    short_tmp: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = short_tmp / "hub"; home.mkdir()
    wg = _dormant_chain_hub(home)

    await wc.post(home, wg.meta.id, b"@muse #task #media-qa audit the rebuild", operator_abandon=True)
    out = await wc.post(home, wg.meta.id, "#done skipped · no media changed".encode())
    assert isinstance(out.get("seq"), int)


def _gated_hub(home: Path):
    scout_home = home.parent / f"{home.name}-scout"
    scout_home.mkdir(exist_ok=True)
    pk = load_or_generate(scout_home).pubkey_b64()
    _pin(home, "scout", pk, ["workgroup.post"])
    wg = wg_mod.create(
        home, name="site", hub_kp=load_or_generate(home), member_pubkeys=[pk],
        pipelines={"intake": ["intake", "qa"]},
        launch_pipeline="intake",
        pipeline_steps={
            "intake": {
                "owner": "scout",
                "gate": {"argv": ["npm", "run", "check:config"], "cwd": "p"},
            },
            "qa": {"owner": "scout"},
        },
    )
    return wg, pk


def _member_post(home: Path, wg, pubkey: str, text: str) -> int:
    import json as _json

    kp = load_or_generate(home)
    keys = wg_mod.hub_group_keys(home, wg, kp)
    version = max(keys)
    nonce, ct = wg_mod.encrypt_post(keys[version], text.encode())
    path = home / "alp" / "workgroups" / wg.meta.id / "transcript.jsonl"
    lines = [ln for ln in path.read_text().splitlines() if ln.strip()]
    seq = (_json.loads(lines[-1])["seq"] + 1) if lines else 1
    with path.open("a") as fh:
        fh.write(_json.dumps({
            "seq": seq, "ts": "2026-07-30T00:00:00Z", "from": pubkey,
            "key_version": version, "nonce": nonce, "ciphertext": ct,
        }) + "\n")
    return seq


@pytest.mark.asyncio
async def test_working_only_cannot_close_a_gated_phase(short_tmp: Path) -> None:
    home = short_tmp / "hub"; home.mkdir()
    wg, pk = _gated_hub(home)
    await wc.post(home, wg.meta.id, b"@scout #task #intake produce site.json")
    _member_post(home, wg, pk, "#working still reading the brief")
    with pytest.raises(ValueError, match="phase-owner-missing"):
        await wc.post(home, wg.meta.id, b"#done intake complete")


@pytest.mark.asyncio
async def test_skip_only_cannot_close_a_gated_phase(short_tmp: Path) -> None:
    home = short_tmp / "hub"; home.mkdir()
    wg, pk = _gated_hub(home)
    await wc.post(home, wg.meta.id, b"@scout #task #intake produce site.json")
    _member_post(home, wg, pk, "#skip not my phase")
    with pytest.raises(ValueError, match="phase-owner-missing"):
        await wc.post(home, wg.meta.id, b"#done intake complete")


@pytest.mark.asyncio
async def test_blocked_override_closes_a_gated_phase_with_only_working(
    short_tmp: Path,
) -> None:
    home = short_tmp / "hub"; home.mkdir()
    wg, pk = _gated_hub(home)
    await wc.post(home, wg.meta.id, b"@scout #task #intake produce site.json")
    _member_post(home, wg, pk, "#working still reading the brief")
    await wc.post(
        home, wg.meta.id,
        "#done BLOCKED · scout cannot reach the engine id".encode(),
    )


@pytest.mark.asyncio
async def test_a_hub_note_after_delivery_does_not_hide_it(short_tmp: Path) -> None:
    from alpi.alp import pipeline_gates as gates

    home = short_tmp / "hub"; home.mkdir()
    wg, pk = _gated_hub(home)
    await wc.post(home, wg.meta.id, b"@scout #task #intake produce site.json")
    delivered = _member_post(home, wg, pk, "wrote src/config/site.json")
    await wc.post(home, wg.meta.id, b"noted, one clarification on scope follows")

    posts = [
        {"seq": 1, "from": "HUB", "text": "@scout #task #intake produce site.json"},
        {"seq": delivered, "from": pk, "text": "wrote src/config/site.json"},
        {"seq": delivered + 1, "from": "HUB", "text": "one more note on scope"},
    ]
    assert gates.owner_post_under_gate(posts, {pk}, "HUB", 1) == delivered

    with pytest.raises(ValueError, match="phase-gate-unverified"):
        await wc.post(home, wg.meta.id, b"#done intake complete")


_CHAIN_STEPS = {
    "intake": {
        "owner": "muse", "task": "produce intake.md",
        "gate": {"argv": ["npm", "run", "check:config"], "cwd": "app"},
    },
    "qa": {"owner": "muse"},
    "media-update": {"owner": "muse", "task": "install client media"},
    "media-qa": {"owner": "muse"},
}


def _chain_hub(
    home: Path, *, launch: str | None = "intake", steps: dict | None = None,
):
    muse_home = home.parent / f"{home.name}-muse"
    muse_home.mkdir(exist_ok=True)
    muse_pk = load_or_generate(muse_home).pubkey_b64()
    _pin(home, "muse", muse_pk, ["workgroup.post"])
    wg = wg_mod.create(
        home, name="site", hub_kp=load_or_generate(home),
        member_pubkeys=[muse_pk],
        pipelines={
            "intake": ["intake", "qa"],
            "media-update": ["media-update", "media-qa"],
        },
        launch_pipeline=launch,
        pipeline_steps=_CHAIN_STEPS if steps is None else steps,
    )
    return wg, muse_pk


def _transcript_texts(home: Path, wg) -> list[str]:
    kp = load_or_generate(home)
    keys = wg_mod.hub_group_keys(home, wg, kp)
    out: list[str] = []
    for entry in wg_mod._read_transcript(wg_mod._wg_dir(home, wg.meta.id)):
        key = keys[int(entry.get("key_version", 1))]
        out.append(wg_mod.decrypt_post(
            key, entry["nonce"], entry["ciphertext"],
        ).decode("utf-8"))
    return out


async def _hub_handler(
    home: Path, method: str, params: dict, member_pk: str,
) -> dict:
    server = alp_server.Server(home=home, agent_name="hub")
    wg_mod.register(server, home)
    peer = Peer(id="muse", pubkey=member_pk, allow=[])
    return await server.handlers[method](params, peer, server)


@pytest.mark.asyncio
async def test_join_and_pull_payloads_carry_canonical_chain_state(
    short_tmp: Path,
) -> None:
    """Members learn chains, selector, mode and safe owners/tasks — never a gate command."""
    home = short_tmp / "hubwire"; home.mkdir()
    wg, muse_pk = _chain_hub(home)

    for method in ("workgroup.join", "workgroup.pull"):
        payload = await _hub_handler(
            home, method, {"workgroup_id": wg.meta.id, "since": 0}, muse_pk,
        )
        assert payload["pipelines"] == {
            "intake": ["intake", "qa"],
            "media-update": ["media-update", "media-qa"],
        }, method
        assert payload["launch_pipeline"] == "intake", method
        assert payload["pipeline_mode"] is True, method
        assert payload["phase_map"]["intake"] == {
            "owner": "muse", "task": "produce intake.md",
        }, method
        assert payload["phase_map"]["qa"] == {"owner": "muse"}, method
        assert "pipeline" not in payload, method
        assert "operations" not in payload, method

        assert all(
            set(spec) <= {"owner", "task"}
            for spec in payload["phase_map"].values()
        ), method


@pytest.mark.asyncio
async def test_member_absorbs_join_payload_without_persisting_gates(
    short_tmp: Path,
) -> None:
    """The subscription file mirrors the chains but never the gate command."""
    home = short_tmp / "hubwire2"; home.mkdir()
    member_home = short_tmp / "member2"; member_home.mkdir()
    wg, muse_pk = _chain_hub(home)
    payload = await _hub_handler(
        home, "workgroup.join", {"workgroup_id": wg.meta.id}, muse_pk,
    )

    sub = sub_mod.Subscription(
        wg_id=wg.meta.id, name="site", hub_id="hub", hub_pubkey=wg.meta.hub_pubkey,
    )
    sub.absorb_pipeline_state(payload)
    sub_mod.upsert(member_home, sub)

    loaded = sub_mod.get(member_home, wg.meta.id)
    assert loaded.pipelines == {
        "intake": ("intake", "qa"),
        "media-update": ("media-update", "media-qa"),
    }
    assert loaded.launch_pipeline == "intake"
    assert loaded.pipeline_mode is True
    assert loaded.phase_map["intake"] == {
        "owner": "muse", "task": "produce intake.md",
    }
    saved = yaml.safe_load(sub_mod.path(member_home).read_text())
    saved_sub = next(row for row in saved if row["wg_id"] == wg.meta.id)
    assert saved_sub["phase_map"] == loaded.phase_map
    assert all(
        set(spec) <= {"owner", "task", "turn_budget_s"}
        for spec in saved_sub["phase_map"].values()
    )


@pytest.mark.asyncio
async def test_launchless_workgroup_reports_pipeline_mode_on_the_wire(
    short_tmp: Path,
) -> None:
    """Dormant-only chains: no selector, still pipeline mode."""
    home = short_tmp / "hubidlewire"; home.mkdir()
    wg, muse_pk = _chain_hub(home, launch=None)
    payload = await _hub_handler(
        home, "workgroup.join", {"workgroup_id": wg.meta.id}, muse_pk,
    )
    assert set(payload["pipelines"]) == {"intake", "media-update"}
    assert payload["launch_pipeline"] is None
    assert payload["pipeline_mode"] is True
    assert "pipeline" not in payload


@pytest.mark.asyncio
async def test_launchless_workgroup_rejects_untargeted_task_and_open_closure(
    short_tmp: Path,
) -> None:
    """A launchless pipeline workgroup keeps both pipeline guards: targeted tasks only, and no close without the owner's delivery."""
    home = short_tmp / "hubidle"; home.mkdir()
    wg, muse_pk = _chain_hub(home, launch=None)

    with pytest.raises(ValueError, match="pipeline-task-untargeted"):
        await wc.post(
            home, wg.meta.id, b"#task #media-update install client media",
        )
    with pytest.raises(ValueError, match="chain-jump"):
        await wc.post(
            home, wg.meta.id, b"@muse #task #media-update install client media",
        )
    await wc.post(
        home, wg.meta.id, b"@muse #task #media-update install client media",
        operator_abandon=True,
    )
    with pytest.raises(ValueError, match="phase-owner-missing"):
        await wc.post(home, wg.meta.id, b"#done media update complete")


@pytest.mark.asyncio
async def test_trigger_pipeline_posts_the_declared_opener_verbatim(
    short_tmp: Path,
) -> None:
    """The opener is authored byte for byte from `pipeline_steps`, never invented."""
    home = short_tmp / "hubtrig"; home.mkdir()
    wg, muse_pk = _chain_hub(home, launch=None)

    out = await wc.trigger_pipeline(home, wg.meta.id, "media-update")
    assert out == {
        "ok": True, "pipeline": "media-update", "phase": "media-update",
        "seq": 1, "stopped": None,
    }
    assert _transcript_texts(home, wg) == [
        "@muse #task #media-update · install client media",
    ]


@pytest.mark.asyncio
async def test_trigger_pipeline_normalizes_the_requested_key(
    short_tmp: Path,
) -> None:
    home = short_tmp / "hubtrignorm"; home.mkdir()
    wg, muse_pk = _chain_hub(home, launch=None)
    out = await wc.trigger_pipeline(home, wg.meta.id, "  Media-Update  ")
    assert out["pipeline"] == "media-update"
    assert out["phase"] == "media-update"


@pytest.mark.asyncio
async def test_trigger_pipeline_rejects_an_empty_key(short_tmp: Path) -> None:
    home = short_tmp / "hubtrigempty"; home.mkdir()
    wg, muse_pk = _chain_hub(home, launch=None)
    with pytest.raises(wc.TriggerError) as exc:
        await wc.trigger_pipeline(home, wg.meta.id, "   ")
    assert exc.value.code == "pipeline-required"
    assert _transcript_texts(home, wg) == []


@pytest.mark.asyncio
async def test_trigger_pipeline_rejects_an_unknown_pipeline(
    short_tmp: Path,
) -> None:
    home = short_tmp / "hubtrigunknown"; home.mkdir()
    wg, muse_pk = _chain_hub(home, launch=None)
    with pytest.raises(wc.TriggerError) as exc:
        await wc.trigger_pipeline(home, wg.meta.id, "ghost")
    assert exc.value.code == "pipeline-unknown"
    assert _transcript_texts(home, wg) == []


@pytest.mark.asyncio
async def test_trigger_pipeline_rejects_a_paused_workgroup(
    short_tmp: Path,
) -> None:
    home = short_tmp / "hubtrigpaused"; home.mkdir()
    wg, muse_pk = _chain_hub(home, launch=None)
    await wc.pause(home, wg.meta.id)
    with pytest.raises(wc.TriggerError) as exc:
        await wc.trigger_pipeline(home, wg.meta.id, "media-update")
    assert exc.value.code == "workgroup-paused"
    assert _transcript_texts(home, wg) == []


@pytest.mark.asyncio
async def test_trigger_pipeline_rejects_a_workgroup_we_only_subscribe_to(
    short_tmp: Path,
) -> None:
    home = short_tmp / "trigmember"; home.mkdir()
    load_or_generate(home)
    sub_mod.upsert(home, sub_mod.Subscription(
        wg_id="wg_remote", name="site", hub_id="mira", hub_pubkey="x" * 44,
        pipelines={"media-update": ("media-update",)},
        launch_pipeline="media-update",
        pipeline_mode=True,
    ))
    with pytest.raises(wc.TriggerError) as exc:
        await wc.trigger_pipeline(home, "wg_remote", "media-update")
    assert exc.value.code == "pipeline-trigger-not-hub"


@pytest.mark.asyncio
async def test_trigger_pipeline_rejects_an_unknown_workgroup(
    short_tmp: Path,
) -> None:
    home = short_tmp / "trignowhere"; home.mkdir()
    load_or_generate(home)
    with pytest.raises(wc.TriggerError) as exc:
        await wc.trigger_pipeline(home, "wg_nope", "media-update")
    assert exc.value.code == "workgroup-not-found"


@pytest.mark.asyncio
async def test_trigger_pipeline_stops_the_chain_that_was_in_flight(
    short_tmp: Path,
) -> None:
    """Pipelines run one at a time: starting one stops whatever was mid-flight."""
    home = short_tmp / "hubtrigbusy"; home.mkdir()
    wg, muse_pk = _chain_hub(home, launch=None)
    await wc.trigger_pipeline(home, wg.meta.id, "media-update")

    out = await wc.trigger_pipeline(home, wg.meta.id, "intake")
    assert out["ok"] is True and out["pipeline"] == "intake"
    assert out["stopped"] == {
        "pipeline": "media-update",
        "phase": "media-update",
        "status": "running",
        "open_task": "media-update",
        "same_pipeline": False,
    }
    assert _transcript_texts(home, wg) == [
        "@muse #task #media-update · install client media",
        "@muse #task #intake · produce intake.md",
    ]

    from alpi.host import workgroup as host_wg
    state = host_wg.fold_task_state(home, wg.meta.id)
    assert state["pipeline_run"]["pipeline"] == "intake"
    stopped = next(c for c in state["closed"] if c["slug"] == "media-update")
    assert stopped["result"] == "preempted by #intake"


@pytest.mark.asyncio
async def test_a_stopped_phase_is_never_reported_as_completed(
    short_tmp: Path,
) -> None:
    home = short_tmp / "hubtrigpre"; home.mkdir()
    wg, muse_pk = _chain_hub(home, launch=None)
    await wc.trigger_pipeline(home, wg.meta.id, "media-update")
    await wc.trigger_pipeline(home, wg.meta.id, "intake")

    from alpi.host import workgroup as host_wg
    run = host_wg.fold_task_state(home, wg.meta.id)["pipeline_run"]
    assert run["pipeline"] == "intake"
    assert [p["state"] for p in run["phases"]][0] == "current"


@pytest.mark.asyncio
async def test_trigger_reports_a_blocked_run_it_displaces(
    short_tmp: Path,
) -> None:
    """A blocked run counts as stopped: what the trigger costs it is its position."""
    home = short_tmp / "hubtrigblocked"; home.mkdir()
    wg, muse_pk = _chain_hub(home, launch=None)
    await wc.trigger_pipeline(home, wg.meta.id, "media-update")
    await wc.post(home, wg.meta.id, "#done BLOCKED · gate red".encode())

    out = await wc.trigger_pipeline(home, wg.meta.id, "intake")
    assert out["stopped"] == {
        "pipeline": "media-update",
        "phase": "media-update",
        "status": "blocked",
        "open_task": None,
        "same_pipeline": False,
    }


@pytest.mark.asyncio
async def test_trigger_pipeline_rejects_a_first_phase_without_a_contract(
    short_tmp: Path,
) -> None:
    """No declared owner/task for the first phase means there is no opener to author."""
    home = short_tmp / "hubtrigbare"; home.mkdir()
    wg, muse_pk = _chain_hub(
        home, launch=None,
        steps={"media-update": {"owner": "muse"}, "qa": {"owner": "muse"}},
    )
    with pytest.raises(wc.TriggerError) as exc:
        await wc.trigger_pipeline(home, wg.meta.id, "media-update")
    assert exc.value.code == "pipeline-trigger-contract-missing"
    assert _transcript_texts(home, wg) == []

    with pytest.raises(wc.TriggerError) as exc2:
        await wc.trigger_pipeline(home, wg.meta.id, "intake")
    assert exc2.value.code == "pipeline-trigger-contract-missing"
    assert _transcript_texts(home, wg) == []


@pytest.mark.asyncio
async def test_a_completed_pipeline_can_be_triggered_again(
    short_tmp: Path,
) -> None:
    home = short_tmp / "hubtrigagain"; home.mkdir()
    wg, muse_pk = _chain_hub(home, launch=None)

    first = await wc.trigger_pipeline(home, wg.meta.id, "media-update")
    _member_post(home, wg, muse_pk, "media installed · logo + hero swapped")
    await wc.post(home, wg.meta.id, b"#done media-update complete")

    second = await wc.trigger_pipeline(home, wg.meta.id, "media-update")
    assert second["ok"] is True
    assert second["seq"] > first["seq"]
    assert _transcript_texts(home, wg)[-1] == (
        "@muse #task #media-update · install client media"
    )
    raw = wg_mod._read_transcript(wg_mod._wg_dir(home, wg.meta.id))
    marked = [int(post["seq"]) for post in raw if post.get("pipeline_trigger") is True]
    assert marked == [first["seq"], second["seq"]]

    from alpi.host import workgroup as host_wg
    run = host_wg.fold_task_state(home, wg.meta.id)["pipeline_run"]
    assert run["started_seq"] == second["seq"]


@pytest.mark.asyncio
async def test_a_blocked_phase_cannot_be_advanced_past(short_tmp: Path) -> None:
    """After `#done BLOCKED` on a phase, opening its chain's successor is refused; re-opening the phase is the way out."""
    home = short_tmp / "hubblocked"; home.mkdir()
    wg, muse_pk = _chain_hub(home, launch=None)
    await wc.trigger_pipeline(home, wg.meta.id, "intake")
    await wc.post(home, wg.meta.id, "#done BLOCKED · gate red and unfixable today".encode())

    with pytest.raises(ValueError, match="blocked-phase-not-cleared"):
        await wc.post(home, wg.meta.id, b"@muse #task #qa \xc2\xb7 audit anyway")

    result = await wc.post(home, wg.meta.id, b"@muse #task #intake \xc2\xb7 second try")
    assert result.get("seq")


@pytest.mark.asyncio
async def test_operator_trigger_may_restart_a_blocked_chain(short_tmp: Path) -> None:
    home = short_tmp / "hubblockedtrig"; home.mkdir()
    wg, muse_pk = _chain_hub(home, launch=None)
    await wc.trigger_pipeline(home, wg.meta.id, "intake")
    await wc.post(home, wg.meta.id, "#done BLOCKED · halted".encode())

    out = await wc.trigger_pipeline(home, wg.meta.id, "media-update")
    assert out["ok"] is True


def test_qa_verdict_mismatch_is_rejected(short_tmp: Path, monkeypatch) -> None:
    import types

    home = short_tmp / "qaverdict"; home.mkdir()
    load_or_generate(home)
    wg = types.SimpleNamespace(
        meta=types.SimpleNamespace(
            pipelines={"intake": ("intake", "qa")}, launch_pipeline="intake",
            pipeline_steps={"qa": {"owner": "lens"}},
        ),
        members=[types.SimpleNamespace(pubkey="LENSPK")],
    )
    monkeypatch.setattr(
        "alpi.alp.peers.get_by_pubkey",
        lambda h, pk: types.SimpleNamespace(id="lens") if pk == "LENSPK" else None,
    )
    posts = [
        {"seq": 1, "from": "HUB", "text": "@lens #task #qa audit it"},
        {"seq": 2, "from": "LENSPK", "text": "Verdict: **QA FAIL** · broken alt text"},
    ]
    with pytest.raises(ValueError, match="qa-verdict-mismatch"):
        wc._check_qa_verdict_respected(
            home, wg, posts, "#done qa PASS · all gates green", "HUB",
        )
    with pytest.raises(ValueError, match="qa-verdict-mismatch"):
        wc._check_qa_verdict_respected(
            home, wg, posts,
            "#done review-qa · No QA FAIL finding to route", "HUB",
        )
    wc._check_qa_verdict_respected(
        home, wg, posts, "#done BLOCKED · lens found real defects", "HUB",
    )
    with pytest.raises(ValueError, match="qa-verdict-mismatch"):
        wc._check_qa_verdict_respected(
            home, wg, posts, "#done BLOCKED·lens found real defects", "HUB",
        )
    wc._check_qa_verdict_respected(
        home, wg, posts, "#done review-qa · QA FAIL · broken alt text", "HUB",
    )
    posts[1]["text"] = "Verdict: **QA PASS** · clean"
    wc._check_qa_verdict_respected(
        home, wg, posts, "#done qa PASS · quoting lens", "HUB",
    )


def test_hub_task_cannot_jump_into_a_dormant_chain() -> None:
    """The regio-v24 misroute: a QA finding re-tasked into the dormant review chain without a trigger."""
    import types

    meta = types.SimpleNamespace(
        pipelines={
            "setup": ("content", "qa"),
            "review": ("review", "review-content", "review-close"),
        },
        launch_pipeline="setup",
        pipeline_steps={},
    )
    wg = types.SimpleNamespace(meta=meta, members=[])
    posts = [
        {"seq": 1, "from": "HUB", "text": "@quill #task #content · author it"},
        {"seq": 2, "from": "QUILLPK", "text": "delivered"},
        {"seq": 3, "from": "HUB", "text": "@lens #task #qa · audit the dist"},
        {"seq": 4, "from": "LENSPK", "text": "QA audit complete · one unsourced claim"},
    ]
    with pytest.raises(ValueError, match="chain-jump"):
        wc._check_task_stays_in_running_chain(
            wg, posts, "@quill #task #review-content · prune the unsourced claim", "HUB",
        )
    wc._check_task_stays_in_running_chain(
        wg, posts, "@quill #task #content · prune the unsourced claim", "HUB",
    )
    wc._check_task_stays_in_running_chain(
        wg, posts, "@quill #task #content-fix · prune the unsourced claim", "HUB",
    )
    wc._check_task_stays_in_running_chain(
        wg, posts, "plain prose reply without a task", "HUB",
    )
    wc._check_task_stays_in_running_chain(
        wg, [], "@quill #task #content · launch-chain kickoff shape", "HUB",
    )
    with pytest.raises(ValueError, match="trigger-only"):
        wc._check_task_stays_in_running_chain(
            wg, [], "@quill #task #review-content · dormant chain on an empty workgroup", "HUB",
        )
    adhoc_history = [
        {"seq": 1, "from": "HUB", "text": "@quill #task #brainstorm · free discussion"},
    ]
    with pytest.raises(ValueError, match="trigger-only"):
        wc._check_task_stays_in_running_chain(
            wg, adhoc_history, "@quill #task #review-close · sneak a dormant chain open", "HUB",
        )
    with pytest.raises(ValueError, match="trigger-only"):
        wc._check_task_stays_in_running_chain(
            wg, adhoc_history, "@quill #task #content · reopen launch after legacy ad-hoc", "HUB",
        )
    wc._check_task_stays_in_running_chain(
        wg, posts, "@quill #task #brainstorm · ad-hoc, no declared chain", "HUB",
    )
    launchless = types.SimpleNamespace(meta=types.SimpleNamespace(
        pipelines=meta.pipelines, launch_pipeline=None, pipeline_steps={},
    ), members=[])
    with pytest.raises(ValueError, match="trigger-only"):
        wc._check_task_stays_in_running_chain(
            launchless, [], "@quill #task #review-content · launchless has no privileged chain", "HUB",
        )


def test_qa_verdict_carry_is_verdict_position_only(
    short_tmp: Path, monkeypatch,
) -> None:
    """Only a segment STARTING with the verdict carries it: prose can deny or hypothesise the token, and the rejection must teach the exact shape (jaime v24 deadlock)."""
    import types

    home = short_tmp / "qacarry"; home.mkdir()
    load_or_generate(home)
    wg = types.SimpleNamespace(
        meta=types.SimpleNamespace(
            pipelines={"intake": ("content", "qa")}, launch_pipeline="intake",
            pipeline_steps={"content": {"owner": "quill"}},
        ),
        members=[types.SimpleNamespace(pubkey="QUILLPK")],
    )
    monkeypatch.setattr(
        "alpi.alp.peers.get_by_pubkey",
        lambda h, pk: types.SimpleNamespace(id="quill") if pk == "QUILLPK" else None,
    )
    posts = [
        {"seq": 1, "from": "HUB", "text": "@quill #task #content · QA FAIL (lens seq #50): fix accents"},
        {"seq": 2, "from": "QUILLPK", "text": "#working repairing the QA FAIL findings"},
        {"seq": 3, "from": "QUILLPK", "text": "re-audit of my repair · QA FAIL · homepage still renders stale copy"},
    ]
    wc._check_qa_verdict_respected(
        home, wg, posts,
        "#done #content · QA FAIL (lens seq #50) findings resolved on disk and gate green — routes to #build",
        "HUB",
    )
    wc._check_qa_verdict_respected(
        home, wg, posts, "#done content · **QA FAIL** carried verbatim · routing to build", "HUB",
    )
    with pytest.raises(ValueError, match="must START with the verdict token"):
        wc._check_qa_verdict_respected(
            home, wg, posts,
            "#done content · carries QA FAIL (lens seq #50) findings resolved — routes to #build",
            "HUB",
        )
    wc._check_qa_verdict_respected(
        home, wg, posts, "#done content · QA FAIL. routed to build for a rebuild", "HUB",
    )
    for denial_or_hypothetical in (
        "#done content · QA FAIL-SAFE enabled on the build",
        "#done content · QA FAIL_OVER configured",
        "#done content · no evidence remains that this is QA FAIL",
        "#done content · we cannot classify the result as QA FAIL",
        "#done content · **NO** QA FAIL was found",
        "#done content · if this were QA FAIL we would route it",
        "#done content · sin QA FAIL pendiente, todo verde",
        "#done content · all findings addressed",
        "#done content · QA FAILURE ANALYSIS PENDING for next sprint",
        "#done content · QA FAILSAFE enabled on the build",
        '#done content · "QA FAIL" was not observed on the rebuilt dist',
        "#done content · (QA FAIL) not applicable here",
        "#done content · ~~QA FAIL~~ withdrawn by lens",
    ):
        with pytest.raises(ValueError, match="qa-verdict-mismatch"):
            wc._check_qa_verdict_respected(
                home, wg, posts, denial_or_hypothetical, "HUB",
            )


def test_qa_verdict_is_the_last_token_by_position_and_exact(
    short_tmp: Path, monkeypatch,
) -> None:
    """A final FAIL after a PASS mention must read FAIL, and the close must carry the OWNER'S token."""
    import types

    home = short_tmp / "qalast"; home.mkdir()
    load_or_generate(home)
    wg = types.SimpleNamespace(
        meta=types.SimpleNamespace(
            pipelines={"intake": ("content", "qa")}, launch_pipeline="intake",
            pipeline_steps={"qa": {"owner": "lens"}},
        ),
        members=[types.SimpleNamespace(pubkey="LENSPK")],
    )
    monkeypatch.setattr(
        "alpi.alp.peers.get_by_pubkey",
        lambda h, pk: types.SimpleNamespace(id="lens") if pk == "LENSPK" else None,
    )
    posts = [
        {"seq": 1, "from": "HUB", "text": "@lens #task #qa audit it"},
        {"seq": 2, "from": "LENSPK",
         "text": "cannot grant QA PASS yet — final verdict: QA FAIL · stale homepage"},
    ]
    with pytest.raises(ValueError, match="`QA FAIL`"):
        wc._check_qa_verdict_respected(
            home, wg, posts, "#done qa PASS · all findings met", "HUB",
        )
    wc._check_qa_verdict_respected(
        home, wg, posts, "#done qa · QA FAIL · routed to build", "HUB",
    )

    posts[1]["text"] = "looked like QA FAIL at first, but the rebuilt dist is clean: QA PASS"
    wc._check_qa_verdict_respected(
        home, wg, posts, "#done qa PASS · verified clean", "HUB",
    )

    posts[1]["text"] = "the build QA PASSED overall"
    wc._check_qa_verdict_respected(
        home, wg, posts, "#done qa · closing on prose, no token issued", "HUB",
    )

    posts[1]["text"] = "verdict: QA BLOCKED · template gap"
    with pytest.raises(ValueError, match="`QA BLOCKED`"):
        wc._check_qa_verdict_respected(
            home, wg, posts, "#done qa · QA FAIL · downgraded to fail", "HUB",
        )
    wc._check_qa_verdict_respected(
        home, wg, posts, "#done qa · QA BLOCKED · template gap carried", "HUB",
    )

    for negated_mention in (
        "No QA FAIL was observed anywhere in the dist",
        "If this were QA FAIL we would route it to build",
        '"QA FAIL" is not the verdict here',
        "we cannot classify the result as QA FAIL",
    ):
        posts[1]["text"] = negated_mention
        wc._check_qa_verdict_respected(
            home, wg, posts, "#done qa PASS · clean close over a prose mention", "HUB",
        )
