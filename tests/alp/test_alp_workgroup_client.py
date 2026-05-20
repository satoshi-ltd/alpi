"""Member-side workgroup helpers."""

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
    import alpi.alp.workgroup_client as wc_mod
    original_resolver = wc_mod._intra_socket_path
    wc_mod._intra_socket_path = lambda peer_id: server.socket_path()
    try:
        sub = await wc.join(bob_home, "alice", wg.meta.id)
        assert sub.wg_id == wg.meta.id
        assert sub.name == "design"
        assert sub.hub_id == "alice"
        assert sub.latest_version() == 1
        assert sub.joined_at
        assert sub_mod.path(bob_home).exists()

        await wc.post(bob_home, wg.meta.id, b"hi via wc")

        posts, head = await wc.pull(bob_home, wg.meta.id)
        assert head == 1
        assert len(posts) == 1
        assert posts[0]["text"] == "hi via wc"
        sub_after = sub_mod.get(bob_home, wg.meta.id)
        assert sub_after.last_seq == 1

        posts2, _ = await wc.pull(bob_home, wg.meta.id)
        assert posts2 == []
    finally:
        wc_mod._intra_socket_path = original_resolver
        await server.stop()


@pytest.mark.asyncio
async def test_post_rejects_non_hub_marker(short_tmp: Path) -> None:
    bob_home = short_tmp / "bob"; bob_home.mkdir()
    load_or_generate(bob_home)
    sub = sub_mod.Subscription(
        wg_id="wg_test", name="x", hub_id="alice",
        hub_pubkey="a" * 44,
    )
    sub.upsert_key(1, "sealed-stub")
    sub_mod.upsert(bob_home, sub)

    with pytest.raises(ValueError, match="only the workgroup hub"):
        await wc.post(bob_home, "wg_test", b"#done unilateral close")

    with pytest.raises(ValueError, match="only the workgroup hub"):
        await wc.post(bob_home, "wg_test", b"#task spawn sub-task")

    try:
        await wc.post(bob_home, "wg_test", b"converge with #done eventually")
    except ValueError as e:
        assert "only the workgroup hub" not in str(e)
    except Exception:
        pass


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
    import alpi.alp.workgroup_client as wc_mod
    original = wc_mod._intra_socket_path
    wc_mod._intra_socket_path = lambda peer_id: server.socket_path()
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
        wc_mod._intra_socket_path = original
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
    import alpi.alp.workgroup_client as wc_mod
    original = wc_mod._intra_socket_path
    wc_mod._intra_socket_path = lambda peer_id: server.socket_path()
    try:
        sub = await wc.join(bob_home, "alice", wg.meta.id)
    finally:
        wc_mod._intra_socket_path = original
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
    import alpi.alp.workgroup_client as wc_mod
    original = wc_mod._intra_socket_path
    wc_mod._intra_socket_path = lambda peer_id: server.socket_path()
    try:
        sub = await wc.join(bob_home, "alice", wg.meta.id)
    finally:
        wc_mod._intra_socket_path = original
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
        _post(1, "HUB", "#task X"),
        _post(2, "BOB", "answer"),
        _post(3, "HUB", "follow-up"),
        _post(4, "CAROL", "comment"),
    ]
    assert wc._last_hub_seq(posts, "HUB") == 3


def test_current_round_posts_excludes_hub_opener() -> None:
    posts = [
        _post(1, "HUB", "#task X"),
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
    posts = [_post(1, "HUB", "#task X")]
    wc._check_member_rotation(posts, "BOB", "HUB", "my take")


def test_member_rotation_blocks_second_substantive_in_same_round() -> None:
    posts = [
        _post(1, "HUB", "#task X"),
        _post(2, "BOB", "first take"),
    ]
    with pytest.raises(ValueError, match="turn-rotation"):
        wc._check_member_rotation(posts, "BOB", "HUB", "second take")


def test_member_rotation_allows_substantive_after_own_working() -> None:
    posts = [
        _post(1, "HUB", "#task X"),
        _post(2, "BOB", "#working researching"),
    ]
    wc._check_member_rotation(posts, "BOB", "HUB", "my findings")


def test_member_rotation_blocks_double_working_in_same_round() -> None:
    posts = [
        _post(1, "HUB", "#task X"),
        _post(2, "BOB", "#working researching"),
    ]
    with pytest.raises(ValueError, match="already posted `#working`"):
        wc._check_member_rotation(posts, "BOB", "HUB", "#working still going")


def test_member_rotation_resets_after_hub_speaks() -> None:
    posts = [
        _post(1, "HUB", "#task X"),
        _post(2, "BOB", "first round answer"),
        _post(3, "HUB", "follow-up question"),
    ]
    wc._check_member_rotation(posts, "BOB", "HUB", "second round answer")


def test_member_round_fresh_no_op_without_env_var(monkeypatch) -> None:
    monkeypatch.delenv("ALPI_WORKGROUP_ROUND_HUB_SEQ", raising=False)
    posts = [_post(1, "HUB", "#task X"), _post(2, "HUB", "follow")]
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


def test_hub_rotation_allows_speaking_after_member() -> None:
    posts = [_post(1, "HUB", "#task"), _post(2, "BOB", "answer")]
    wc._check_hub_rotation(posts, "HUB", "follow-up content", ["BOB", "CAROL"])


def test_hub_rotation_blocks_back_to_back_content() -> None:
    posts = [_post(1, "HUB", "#task X")]
    with pytest.raises(ValueError, match="turn-rotation"):
        wc._check_hub_rotation(posts, "HUB", "more content", ["BOB"])


def test_hub_rotation_ignores_working_when_computing_last_poster() -> None:
    posts = [
        _post(1, "HUB", "#task X"),
        _post(2, "BOB", "#working researching"),
    ]
    with pytest.raises(ValueError, match="turn-rotation"):
        wc._check_hub_rotation(
            posts, "HUB", "sneaky content", ["BOB", "CAROL"],
        )


def test_hub_rotation_allows_done_after_member_substantive() -> None:
    posts = [
        _post(1, "HUB", "#task X"),
        _post(2, "BOB", "substantive answer"),
        _post(3, "CAROL", "#skip no angle"),
    ]
    wc._check_hub_rotation(posts, "HUB", "#done synthesis", ["BOB", "CAROL"])


def test_hub_rotation_blocks_done_when_member_pending() -> None:
    posts = [
        _post(1, "HUB", "#task X"),
        _post(2, "BOB", "answer"),
    ]
    with pytest.raises(ValueError, match="closure-quorum"):
        wc._check_hub_rotation(posts, "HUB", "#done foo", ["BOB", "CAROL"])


def test_hub_rotation_blocks_done_when_only_working_from_member() -> None:
    posts = [
        _post(1, "HUB", "#task X"),
        _post(2, "BOB", "answer"),
        _post(3, "CAROL", "#working researching"),
    ]
    with pytest.raises(ValueError, match="closure-quorum"):
        wc._check_hub_rotation(posts, "HUB", "#done foo", ["BOB", "CAROL"])


def test_hub_rotation_blocks_done_when_all_skip_no_substantive() -> None:
    posts = [
        _post(1, "HUB", "#task X"),
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
        _post(1, "HUB", "#task X", ts=eleven_min_ago),
        _post(2, "BOB", "answer", ts=eleven_min_ago),
    ]
    wc._check_hub_rotation(
        posts, "HUB", "#done timeout escape", ["BOB", "CAROL"],
    )


def test_hub_rotation_task_always_allowed_even_back_to_back() -> None:
    posts = [_post(1, "HUB", "#task original")]
    wc._check_hub_rotation(
        posts, "HUB", "#task new direction", ["BOB", "CAROL"],
    )


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

    import alpi.alp.workgroup_client as wc_mod
    original_resolver = wc_mod._intra_socket_path
    wc_mod._intra_socket_path = lambda peer_id: server.socket_path()
    try:
        await wc.join(bob_home, "alice", wg.meta.id)
        await wc.post(bob_home, wg.meta.id, b"hi from bob")
    finally:
        wc_mod._intra_socket_path = original_resolver
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
