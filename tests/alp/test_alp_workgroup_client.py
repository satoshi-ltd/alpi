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


@pytest.mark.integration
@pytest.mark.asyncio
async def test_join_persists_subscription_and_pull_decrypts(
    short_tmp: Path,
) -> None:
    """Join stores the subscription and pull decrypts a post."""
    hub_home = short_tmp / "alice"; hub_home.mkdir()
    bob_home = short_tmp / "bob"; bob_home.mkdir()
    alice_kp = load_or_generate(hub_home)
    bob_kp = load_or_generate(bob_home)
    _pin(hub_home, "bob", bob_kp.pubkey_b64(),
         ["workgroup.join", "workgroup.post", "workgroup.pull",
          "workgroup.leave"])
    # Bob pins alice using the unix-socket convention.
    _pin(bob_home, "alice", alice_kp.pubkey_b64(),
         ["link.ping"])

    wg = wg_mod.create(
        hub_home, name="design", hub_kp=alice_kp,
        member_pubkeys=[bob_kp.pubkey_b64()],
    )

    server = alp_server.Server(home=hub_home, agent_name="alice")
    wg_mod.register(server, hub_home)
    await server.start()
    # Monkey-patch the socket resolver to use the test home.
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
        # Persisted to bob's subscription file.
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
async def test_post_rejects_non_hub_marker(short_tmp: Path) -> None:
    """Only the hub may post protocol markers."""
    bob_home = short_tmp / "bob"; bob_home.mkdir()
    load_or_generate(bob_home)
    # Bob is a remote member; alice is the hub.
    sub = sub_mod.Subscription(
        wg_id="wg_test", name="x", hub_id="alice",
        hub_pubkey="a" * 44,
    )
    sub.upsert_key(1, "sealed-stub")
    sub_mod.upsert(bob_home, sub)

    # `#done` from a member → rejected with a clear error.
    with pytest.raises(ValueError, match="only the workgroup hub"):
        await wc.post(bob_home, "wg_test", b"#done unilateral close")

    # `#task` from a member → also rejected.
    with pytest.raises(ValueError, match="only the workgroup hub"):
        await wc.post(bob_home, "wg_test", b"#task spawn sub-task")

    # Mentioning the token in prose must not trip the guard.
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
        # Hub kicks carol → key rotates to v2
        wg_mod.kick(hub_home, wg.meta.id, carol_kp.pubkey_b64())

        # Pull first so wc.post reads the rotated sealed key.
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


# Public bio (self-published tag-line)


def test_absorb_roster_captures_bios(short_tmp: Path) -> None:
    """Roster bios populate both maps; empty bios are dropped."""
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
    """Join copies `public_bio` into the hub roster."""
    from alpi import config as cfg_mod

    hub_home = short_tmp / "alice"; hub_home.mkdir()
    bob_home = short_tmp / "bob"; bob_home.mkdir()
    alice_kp = load_or_generate(hub_home)
    bob_kp = load_or_generate(bob_home)
    _pin(hub_home, "bob", bob_kp.pubkey_b64(),
         ["workgroup.join", "workgroup.post", "workgroup.pull"])
    _pin(bob_home, "alice", alice_kp.pubkey_b64(), ["link.ping"])

    # Bob declares a public bio.
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

    # The join response persists both bios.
    assert sub.roster_bios.get(bob_kp.pubkey_b64()) == \
        "systems engineer — durability bias"
    assert sub.roster_bios.get(alice_kp.pubkey_b64()) == \
        "product engineer — velocity"

    # The hub-side member record keeps Bob's bio.
    wg_after = wg_mod.load(hub_home, wg.meta.id)
    bob_member = wg_after.member(bob_kp.pubkey_b64())
    assert bob_member is not None
    assert bob_member.bio == "systems engineer — durability bias"


def test_member_bio_persists_on_disk(short_tmp: Path) -> None:
    """Member bios survive save/load and restart."""
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


# SDK rotation guards.


import datetime as _dt


def _now_iso() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ",
    )


def _post(seq: int, frm: str, text: str, ts: str | None = None) -> dict:
    return {"seq": seq, "from": frm, "text": text, "ts": ts or _now_iso()}


# `_check_substantive` — empty rejected, content allowed


def test_check_substantive_rejects_empty() -> None:
    with pytest.raises(ValueError, match="empty post"):
        wc._check_substantive("")
    with pytest.raises(ValueError, match="empty post"):
        wc._check_substantive("   \n\t  ")


def test_check_substantive_allows_short_content() -> None:
    """Short answers count; only empty bodies are rejected."""
    wc._check_substantive("Yes.")
    wc._check_substantive("Agreed — keep the kefir foam.")


# `_last_hub_seq` / `_current_round_posts`


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
    assert [p["seq"] for p in cur] == [4]  # only after #3


# `_check_member_rotation` keeps one CONTRIBUTING post per round.


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
    """`#working` does not consume the substantive slot."""
    posts = [
        _post(1, "HUB", "#task X"),
        _post(2, "BOB", "#working researching"),
    ]
    wc._check_member_rotation(posts, "BOB", "HUB", "my findings")


def test_member_rotation_blocks_double_working_in_same_round() -> None:
    """One `#working` heartbeat per round per peer."""
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
    # New round: Bob can post again.
    wc._check_member_rotation(posts, "BOB", "HUB", "second round answer")


# `_check_member_round_fresh` checks stale-round env state.


def test_member_round_fresh_no_op_without_env_var(monkeypatch) -> None:
    """Manual posts skip the stale-round guard."""
    monkeypatch.delenv("ALPI_WORKGROUP_ROUND_HUB_SEQ", raising=False)
    posts = [_post(1, "HUB", "#task X"), _post(2, "HUB", "follow")]
    wc._check_member_round_fresh(posts, "HUB")  # no raise


def test_member_round_fresh_passes_when_round_matches(monkeypatch) -> None:
    monkeypatch.setenv("ALPI_WORKGROUP_ROUND_HUB_SEQ", "3")
    posts = [
        _post(1, "HUB", "#task"),
        _post(2, "BOB", "x"),
        _post(3, "HUB", "follow"),
    ]
    wc._check_member_round_fresh(posts, "HUB")  # latest hub seq == 3, OK


def test_member_round_fresh_aborts_when_hub_advanced(monkeypatch) -> None:
    monkeypatch.setenv("ALPI_WORKGROUP_ROUND_HUB_SEQ", "1")
    posts = [
        _post(1, "HUB", "#task"),
        _post(2, "BOB", "x"),
        _post(3, "HUB", "second-task"),
    ]
    with pytest.raises(ValueError, match="stale-round"):
        wc._check_member_round_fresh(posts, "HUB")


# `_check_hub_rotation` enforces back-to-back and quorum rules.


def test_hub_rotation_allows_speaking_after_member() -> None:
    posts = [_post(1, "HUB", "#task"), _post(2, "BOB", "answer")]
    wc._check_hub_rotation(posts, "HUB", "follow-up content", ["BOB", "CAROL"])


def test_hub_rotation_blocks_back_to_back_content() -> None:
    posts = [_post(1, "HUB", "#task X")]
    with pytest.raises(ValueError, match="turn-rotation"):
        wc._check_hub_rotation(posts, "HUB", "more content", ["BOB"])


def test_hub_rotation_ignores_working_when_computing_last_poster() -> None:
    """`#working` is a signal, not a contribution."""
    posts = [
        _post(1, "HUB", "#task X"),
        _post(2, "BOB", "#working researching"),
    ]
    with pytest.raises(ValueError, match="turn-rotation"):
        wc._check_hub_rotation(
            posts, "HUB", "sneaky content", ["BOB", "CAROL"],
        )


def test_hub_rotation_allows_done_after_member_substantive() -> None:
    """`#done` is allowed once quorum is met."""
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
        # CAROL never posted
    ]
    with pytest.raises(ValueError, match="closure-quorum"):
        wc._check_hub_rotation(posts, "HUB", "#done foo", ["BOB", "CAROL"])


def test_hub_rotation_blocks_done_when_only_working_from_member() -> None:
    """`#working` alone does not satisfy quorum."""
    posts = [
        _post(1, "HUB", "#task X"),
        _post(2, "BOB", "answer"),
        _post(3, "CAROL", "#working researching"),
    ]
    with pytest.raises(ValueError, match="closure-quorum"):
        wc._check_hub_rotation(posts, "HUB", "#done foo", ["BOB", "CAROL"])


def test_hub_rotation_blocks_done_when_all_skip_no_substantive() -> None:
    """All-skip stays open until timeout."""
    posts = [
        _post(1, "HUB", "#task X"),
        _post(2, "BOB", "#skip"),
        _post(3, "CAROL", "#skip"),
    ]
    with pytest.raises(ValueError, match="closure-quorum"):
        wc._check_hub_rotation(posts, "HUB", "#done foo", ["BOB", "CAROL"])


def test_hub_rotation_done_allowed_after_timeout_even_when_pending() -> None:
    """Timeout lets the hub force-close a stuck round."""
    eleven_min_ago = (
        _dt.datetime.now(tz=_dt.timezone.utc) - _dt.timedelta(minutes=11)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    posts = [
        _post(1, "HUB", "#task X", ts=eleven_min_ago),
        _post(2, "BOB", "answer", ts=eleven_min_ago),
        # CAROL still pending
    ]
    wc._check_hub_rotation(
        posts, "HUB", "#done timeout escape", ["BOB", "CAROL"],
    )


def test_hub_rotation_task_always_allowed_even_back_to_back() -> None:
    """`#task` may always preempt the round."""
    posts = [_post(1, "HUB", "#task original")]
    wc._check_hub_rotation(
        posts, "HUB", "#task new direction", ["BOB", "CAROL"],
    )


# `leave` always purges locally.


def test_leave_purges_local_subscription_when_hub_unreachable(
    short_tmp: Path,
) -> None:
    """Local cleanup still happens when the hub is unreachable."""
    home = short_tmp / "bob"; home.mkdir()
    load_or_generate(home)
    # No pin for `ghost_hub`; leave should still drop the sub.
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
