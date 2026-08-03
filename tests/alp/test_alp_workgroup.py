"""Workgroup hub state and verbs."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from alpi.alp import client as alp_client
from alpi.alp import peers as peers_mod
from alpi.alp import server as alp_server
from alpi.alp import workgroup as wg_mod
from alpi.alp import workgroup_client as wc
from alpi.alp.keys import load_or_generate
from alpi.alp.peers import Peer


@pytest.fixture
def short_tmp() -> Path:
    d = Path(tempfile.mkdtemp(prefix="alp-wg-", dir="/tmp"))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


def _pin(home: Path, peer_id: str, pubkey: str, allow: list[str]) -> None:
    peers_mod.add(home, Peer(id=peer_id, pubkey=pubkey, allow=allow))


# Meta persistence


def test_meta_auto_read_roundtrip(short_tmp: Path) -> None:
    d = wg_mod._wg_dir(short_tmp, "wg-test")
    meta = wg_mod.Meta(
        id="wg-test", name="t", hub_pubkey="pk",
        created_at="2026-01-01T00:00:00Z", auto_read=True,
    )
    wg_mod._save_meta(d, meta)
    loaded = wg_mod._load_meta(d)
    assert loaded is not None and loaded.auto_read is True

    d2 = wg_mod._wg_dir(short_tmp, "wg-default")
    wg_mod._save_meta(d2, wg_mod.Meta(
        id="wg-default", name="t", hub_pubkey="pk",
        created_at="2026-01-01T00:00:00Z",
    ))
    assert wg_mod._load_meta(d2).auto_read is False


# Crypto round-trip


def test_seal_and_open_group_key_roundtrip(short_tmp: Path) -> None:
    home = short_tmp / "alice"
    home.mkdir()
    kp = load_or_generate(home)
    key = b"\x01" * wg_mod.GROUP_KEY_BYTES
    sealed = wg_mod.seal_group_key(key, kp.pubkey_b64())
    assert wg_mod.open_sealed_group_key(sealed, kp) == key


def test_sealed_key_unopenable_by_other_pubkey(short_tmp: Path) -> None:
    a = short_tmp / "a"
    b = short_tmp / "b"
    a.mkdir()
    b.mkdir()
    a_kp = load_or_generate(a)
    b_kp = load_or_generate(b)
    sealed = wg_mod.seal_group_key(b"\x02" * 32, a_kp.pubkey_b64())
    with pytest.raises(Exception):
        wg_mod.open_sealed_group_key(sealed, b_kp)


def test_post_encrypt_decrypt_roundtrip() -> None:
    key = b"\x03" * 32
    nonce_b64, ct_b64 = wg_mod.encrypt_post(key, b"hello workgroup")
    assert wg_mod.decrypt_post(key, nonce_b64, ct_b64) == b"hello workgroup"


def test_post_decrypt_with_wrong_key_fails() -> None:
    key = b"\x04" * 32
    nonce_b64, ct_b64 = wg_mod.encrypt_post(key, b"secret")
    with pytest.raises(Exception):
        wg_mod.decrypt_post(b"\x05" * 32, nonce_b64, ct_b64)


# Local create


def test_create_persists_meta_members_and_empty_transcript(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    home.mkdir()
    hub_kp = load_or_generate(home)
    bob_home = short_tmp / "bob"
    bob_home.mkdir()
    bob_kp = load_or_generate(bob_home)

    wg = wg_mod.create(
        home,
        name="design",
        hub_kp=hub_kp,
        member_pubkeys=[bob_kp.pubkey_b64()],
    )

    assert wg.meta.id.startswith("wg_")
    assert wg.meta.name == "design"
    assert wg.meta.hub_pubkey == hub_kp.pubkey_b64()
    pubkeys = {m.pubkey for m in wg.members}
    assert pubkeys == {hub_kp.pubkey_b64(), bob_kp.pubkey_b64()}
    # Hub auto-joins; remote members start un-joined.
    hub_member = wg.member(hub_kp.pubkey_b64())
    assert hub_member is not None and hub_member.joined
    bob_member = wg.member(bob_kp.pubkey_b64())
    assert bob_member is not None and not bob_member.joined

    # Persisted under ``alp/workgroups/<id>/``.
    d = home / "alp" / "workgroups" / wg.meta.id
    assert (d / "meta.yaml").exists()
    assert (d / "members.yaml").exists()
    assert (d / "transcript.jsonl").exists()
    assert (d / "transcript.jsonl").read_text() == ""


def test_create_seals_the_same_group_key_for_every_member(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    home.mkdir()
    hub_kp = load_or_generate(home)
    a_home = short_tmp / "a"
    a_home.mkdir()
    b_home = short_tmp / "b"
    b_home.mkdir()
    a_kp = load_or_generate(a_home)
    b_kp = load_or_generate(b_home)

    wg = wg_mod.create(
        home,
        name="trio",
        hub_kp=hub_kp,
        member_pubkeys=[a_kp.pubkey_b64(), b_kp.pubkey_b64()],
    )
    hub_key = wg_mod.open_sealed_group_key(wg.member(hub_kp.pubkey_b64()).sealed_key, hub_kp)
    a_key = wg_mod.open_sealed_group_key(wg.member(a_kp.pubkey_b64()).sealed_key, a_kp)
    b_key = wg_mod.open_sealed_group_key(wg.member(b_kp.pubkey_b64()).sealed_key, b_kp)
    assert hub_key == a_key == b_key
    assert len(hub_key) == wg_mod.GROUP_KEY_BYTES


def test_create_rejects_empty_name(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    home.mkdir()
    kp = load_or_generate(home)
    with pytest.raises(ValueError):
        wg_mod.create(home, name="", hub_kp=kp, member_pubkeys=[])


def test_create_rejects_invalid_member_pubkey(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    home.mkdir()
    kp = load_or_generate(home)
    with pytest.raises(ValueError):
        wg_mod.create(home, name="x", hub_kp=kp, member_pubkeys=["not-a-real-key"])


def test_create_dedups_repeated_pubkeys(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    home.mkdir()
    hub_kp = load_or_generate(home)
    bob_home = short_tmp / "b"
    bob_home.mkdir()
    bob_kp = load_or_generate(bob_home)
    wg = wg_mod.create(
        home,
        name="dup",
        hub_kp=hub_kp,
        member_pubkeys=[
            bob_kp.pubkey_b64(),
            bob_kp.pubkey_b64(),
            hub_kp.pubkey_b64(),
        ],
    )
    assert len({m.pubkey for m in wg.members}) == 2


def test_load_and_list_workgroups(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    home.mkdir()
    hub_kp = load_or_generate(home)
    wg1 = wg_mod.create(home, name="one", hub_kp=hub_kp, member_pubkeys=[])
    wg2 = wg_mod.create(home, name="two", hub_kp=hub_kp, member_pubkeys=[])
    ids = {w.meta.id for w in wg_mod.list_workgroups(home)}
    assert ids == {wg1.meta.id, wg2.meta.id}
    reloaded = wg_mod.load(home, wg1.meta.id)
    assert reloaded is not None and reloaded.meta.name == "one"


def test_load_returns_none_for_missing_workgroup(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    home.mkdir()
    assert wg_mod.load(home, "wg_nonexistent") is None


def test_coerce_wait_s_clamps_and_rejects_junk() -> None:
    assert wg_mod._coerce_wait_s(None) == 0.0
    assert wg_mod._coerce_wait_s("junk") == 0.0
    assert wg_mod._coerce_wait_s(-5) == 0.0
    assert wg_mod._coerce_wait_s(3.5) == 3.5
    assert wg_mod._coerce_wait_s(9999) == wg_mod._LONG_POLL_MAX_WAIT_S


def test_presence_write_is_coalesced() -> None:
    import datetime as dt

    now = dt.datetime(2026, 7, 17, 12, 0, 30, tzinfo=dt.timezone.utc)
    assert wg_mod._presence_write_due("", now) is True
    assert wg_mod._presence_write_due("invalid", now) is True
    assert wg_mod._presence_write_due("2026-07-17T12:00:01Z", now) is False
    assert wg_mod._presence_write_due("2026-07-17T12:00:00Z", now) is True


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pull_long_poll_times_out_empty_and_returns_early_on_post(short_tmp: Path) -> None:
    import asyncio
    import time as _t

    alice_home = short_tmp / "alice"
    alice_home.mkdir()
    bob_home = short_tmp / "bob"
    bob_home.mkdir()
    alice_kp = load_or_generate(alice_home)
    bob_kp = load_or_generate(bob_home)
    _pin(alice_home, "bob", bob_kp.pubkey_b64(),
         ["workgroup.join", "workgroup.post", "workgroup.pull"])
    wg = wg_mod.create(
        alice_home, name="lp", hub_kp=alice_kp,
        member_pubkeys=[bob_kp.pubkey_b64()],
    )
    server = alp_server.Server(home=alice_home, agent_name="alice")
    wg_mod.register(server, alice_home)
    await server.start()
    try:
        join_result = await alp_client.call(
            socket_path=server.socket_path(), sender=bob_kp,
            recipient_pubkey_b64=alice_kp.pubkey_b64(),
            method="workgroup.join", params={"workgroup_id": wg.meta.id},
        )
        group_key = wg_mod.open_sealed_group_key(join_result["sealed_key"], bob_kp)
        members_path = alice_home / "alp" / "workgroups" / wg.meta.id / "members.yaml"
        presence_mtime = members_path.stat().st_mtime_ns

        t0 = _t.monotonic()
        empty = await alp_client.call(
            socket_path=server.socket_path(), sender=bob_kp,
            recipient_pubkey_b64=alice_kp.pubkey_b64(),
            method="workgroup.pull",
            params={"workgroup_id": wg.meta.id, "since": 0, "wait_s": 1.2},
        )
        held = _t.monotonic() - t0
        assert empty["posts"] == []
        assert held >= 1.0
        assert members_path.stat().st_mtime_ns == presence_mtime

        async def _post_later() -> None:
            await asyncio.sleep(0.6)
            nonce_b64, ct_b64 = wg_mod.encrypt_post(group_key, b"wake up")
            await alp_client.call(
                socket_path=server.socket_path(), sender=bob_kp,
                recipient_pubkey_b64=alice_kp.pubkey_b64(),
                method="workgroup.post",
                params={"workgroup_id": wg.meta.id, "nonce": nonce_b64, "ciphertext": ct_b64},
            )

        poster = asyncio.create_task(_post_later())
        t0 = _t.monotonic()
        woke = await alp_client.call(
            socket_path=server.socket_path(), sender=bob_kp,
            recipient_pubkey_b64=alice_kp.pubkey_b64(),
            method="workgroup.pull",
            params={"workgroup_id": wg.meta.id, "since": 0, "wait_s": 10},
        )
        early = _t.monotonic() - t0
        await poster
        assert len(woke["posts"]) == 1
        assert early < 5.0
    finally:
        await server.stop()


# End-to-end over the Unix socket


@pytest.mark.integration
@pytest.mark.asyncio
async def test_join_post_pull_end_to_end(short_tmp: Path) -> None:
    """Alice is the hub and bob joins, posts, then pulls."""
    alice_home = short_tmp / "alice"
    alice_home.mkdir()
    bob_home = short_tmp / "bob"
    bob_home.mkdir()
    alice_kp = load_or_generate(alice_home)
    bob_kp = load_or_generate(bob_home)

    # Alice pins Bob and lets him invoke the three workgroup verbs.
    _pin(alice_home, "bob", bob_kp.pubkey_b64(),
         ["workgroup.join", "workgroup.post", "workgroup.pull"])

    wg = wg_mod.create(
        alice_home,
        name="design",
        hub_kp=alice_kp,
        member_pubkeys=[bob_kp.pubkey_b64()],
    )

    server = alp_server.Server(home=alice_home, agent_name="alice")
    wg_mod.register(server, alice_home)
    await server.start()
    try:
        # Bob joins → receives sealed group key + member roster
        join_result = await alp_client.call(
            socket_path=server.socket_path(),
            sender=bob_kp,
            recipient_pubkey_b64=alice_kp.pubkey_b64(),
            method="workgroup.join",
            params={"workgroup_id": wg.meta.id},
        )
        assert join_result["workgroup_id"] == wg.meta.id
        assert join_result["name"] == "design"
        sealed = join_result["sealed_key"]
        group_key = wg_mod.open_sealed_group_key(sealed, bob_kp)

        # Bob posts encrypted text under the group key
        nonce_b64, ct_b64 = wg_mod.encrypt_post(group_key, b"hi from bob")
        post_result = await alp_client.call(
            socket_path=server.socket_path(),
            sender=bob_kp,
            recipient_pubkey_b64=alice_kp.pubkey_b64(),
            method="workgroup.post",
            params={
                "workgroup_id": wg.meta.id,
                "nonce": nonce_b64,
                "ciphertext": ct_b64,
            },
        )
        assert post_result["seq"] == 1

        # Bob pulls — sees his own post echoed back from the hub
        pull_result = await alp_client.call(
            socket_path=server.socket_path(),
            sender=bob_kp,
            recipient_pubkey_b64=alice_kp.pubkey_b64(),
            method="workgroup.pull",
            params={"workgroup_id": wg.meta.id, "since": 0},
        )
        assert pull_result["head"] == 1
        assert len(pull_result["posts"]) == 1
        echoed = pull_result["posts"][0]
        assert echoed["from"] == bob_kp.pubkey_b64()
        decoded = wg_mod.decrypt_post(group_key, echoed["nonce"], echoed["ciphertext"])
        assert decoded == b"hi from bob"

        # Pull with since=head returns empty
        empty = await alp_client.call(
            socket_path=server.socket_path(),
            sender=bob_kp,
            recipient_pubkey_b64=alice_kp.pubkey_b64(),
            method="workgroup.pull",
            params={"workgroup_id": wg.meta.id, "since": 1},
        )
        assert empty["posts"] == []
    finally:
        await server.stop()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_join_marks_member_as_joined(short_tmp: Path) -> None:
    alice_home = short_tmp / "alice"
    alice_home.mkdir()
    bob_home = short_tmp / "bob"
    bob_home.mkdir()
    alice_kp = load_or_generate(alice_home)
    bob_kp = load_or_generate(bob_home)
    _pin(alice_home, "bob", bob_kp.pubkey_b64(), ["workgroup.join"])

    wg = wg_mod.create(
        alice_home, name="x", hub_kp=alice_kp,
        member_pubkeys=[bob_kp.pubkey_b64()],
    )
    server = alp_server.Server(home=alice_home, agent_name="alice")
    wg_mod.register(server, alice_home)
    await server.start()
    try:
        await alp_client.call(
            socket_path=server.socket_path(),
            sender=bob_kp,
            recipient_pubkey_b64=alice_kp.pubkey_b64(),
            method="workgroup.join",
            params={"workgroup_id": wg.meta.id},
        )
    finally:
        await server.stop()

    reloaded = wg_mod.load(alice_home, wg.meta.id)
    bob_member = reloaded.member(bob_kp.pubkey_b64())
    assert bob_member is not None and bob_member.joined
    assert bob_member.joined_at  # non-empty ISO timestamp


@pytest.mark.integration
@pytest.mark.asyncio
async def test_unknown_workgroup_returns_not_found(short_tmp: Path) -> None:
    alice_home = short_tmp / "alice"
    alice_home.mkdir()
    bob_home = short_tmp / "bob"
    bob_home.mkdir()
    alice_kp = load_or_generate(alice_home)
    bob_kp = load_or_generate(bob_home)
    _pin(alice_home, "bob", bob_kp.pubkey_b64(), ["workgroup.pull"])

    server = alp_server.Server(home=alice_home, agent_name="alice")
    wg_mod.register(server, alice_home)
    await server.start()
    try:
        with pytest.raises(alp_client.RemoteError) as exc:
            await alp_client.call(
                socket_path=server.socket_path(),
                sender=bob_kp,
                recipient_pubkey_b64=alice_kp.pubkey_b64(),
                method="workgroup.pull",
                params={"workgroup_id": "wg_does_not_exist"},
            )
        assert exc.value.code == -32009
    finally:
        await server.stop()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_non_member_peer_rejected_with_not_member(short_tmp: Path) -> None:
    """A capable but non-member peer gets `-32008`."""
    alice_home = short_tmp / "alice"
    alice_home.mkdir()
    bob_home = short_tmp / "bob"
    bob_home.mkdir()
    alice_kp = load_or_generate(alice_home)
    bob_kp = load_or_generate(bob_home)
    _pin(alice_home, "bob", bob_kp.pubkey_b64(),
         ["workgroup.join", "workgroup.post", "workgroup.pull"])

    # Create the workgroup without Bob in the roster.
    wg = wg_mod.create(alice_home, name="closed", hub_kp=alice_kp, member_pubkeys=[])

    server = alp_server.Server(home=alice_home, agent_name="alice")
    wg_mod.register(server, alice_home)
    await server.start()
    try:
        for method, extra in [
            ("workgroup.join", {}),
            ("workgroup.pull", {"since": 0}),
            ("workgroup.post", {"nonce": "AAA", "ciphertext": "BBB"}),
        ]:
            with pytest.raises(alp_client.RemoteError) as exc:
                await alp_client.call(
                    socket_path=server.socket_path(),
                    sender=bob_kp,
                    recipient_pubkey_b64=alice_kp.pubkey_b64(),
                    method=method,
                    params={"workgroup_id": wg.meta.id, **extra},
                )
            assert exc.value.code == -32008, f"{method} returned {exc.value.code}"
    finally:
        await server.stop()


async def _pick_free_port() -> int:
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.mark.integration
@pytest.mark.asyncio
async def test_three_members_post_and_each_decrypts_each_other(short_tmp: Path) -> None:
    """Hub + 2 remote members. Each remote posts; both remotes plus
    the hub pull and decrypt the full transcript."""
    hub_home = short_tmp / "hub"
    hub_home.mkdir()
    a_home = short_tmp / "a"
    a_home.mkdir()
    b_home = short_tmp / "b"
    b_home.mkdir()
    hub_kp = load_or_generate(hub_home)
    a_kp = load_or_generate(a_home)
    b_kp = load_or_generate(b_home)
    _pin(hub_home, "a", a_kp.pubkey_b64(),
         ["workgroup.join", "workgroup.post", "workgroup.pull"])
    _pin(hub_home, "b", b_kp.pubkey_b64(),
         ["workgroup.join", "workgroup.post", "workgroup.pull"])

    wg = wg_mod.create(
        hub_home, name="trio", hub_kp=hub_kp,
        member_pubkeys=[a_kp.pubkey_b64(), b_kp.pubkey_b64()],
    )

    server = alp_server.Server(home=hub_home, agent_name="hub")
    wg_mod.register(server, hub_home)
    await server.start()
    try:
        # Each remote joins and decrypts their sealed key
        async def _join(kp):
            r = await alp_client.call(
                socket_path=server.socket_path(),
                sender=kp,
                recipient_pubkey_b64=hub_kp.pubkey_b64(),
                method="workgroup.join",
                params={"workgroup_id": wg.meta.id},
            )
            return wg_mod.open_sealed_group_key(r["sealed_key"], kp)
        a_key = await _join(a_kp)
        b_key = await _join(b_kp)
        assert a_key == b_key  # same group key for both

        # Both post in turn
        for kp, key, text in [(a_kp, a_key, b"hello from a"),
                              (b_kp, b_key, b"hello from b")]:
            nonce, ct = wg_mod.encrypt_post(key, text)
            await alp_client.call(
                socket_path=server.socket_path(),
                sender=kp,
                recipient_pubkey_b64=hub_kp.pubkey_b64(),
                method="workgroup.post",
                params={"workgroup_id": wg.meta.id, "nonce": nonce, "ciphertext": ct},
            )

        # A pulls, sees both posts in order, decrypts each
        a_pull = await alp_client.call(
            socket_path=server.socket_path(),
            sender=a_kp,
            recipient_pubkey_b64=hub_kp.pubkey_b64(),
            method="workgroup.pull",
            params={"workgroup_id": wg.meta.id, "since": 0},
        )
        assert [p["seq"] for p in a_pull["posts"]] == [1, 2]
        assert a_pull["head"] == 2
        decoded = [
            wg_mod.decrypt_post(a_key, p["nonce"], p["ciphertext"])
            for p in a_pull["posts"]
        ]
        assert decoded == [b"hello from a", b"hello from b"]

        # B pulls only the second post (since=1)
        b_pull = await alp_client.call(
            socket_path=server.socket_path(),
            sender=b_kp,
            recipient_pubkey_b64=hub_kp.pubkey_b64(),
            method="workgroup.pull",
            params={"workgroup_id": wg.meta.id, "since": 1},
        )
        assert [p["seq"] for p in b_pull["posts"]] == [2]
        assert wg_mod.decrypt_post(
            b_key, b_pull["posts"][0]["nonce"], b_pull["posts"][0]["ciphertext"],
        ) == b"hello from b"
    finally:
        await server.stop()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_concurrent_posts_assign_distinct_sequential_seqs(short_tmp: Path) -> None:
    """Two posts launched concurrently must each land with a unique
    seq, no skip and no duplicate. The single-loop async dispatch is
    the implicit lock — this test pins that guarantee."""
    import asyncio

    hub_home = short_tmp / "hub"
    hub_home.mkdir()
    bob_home = short_tmp / "bob"
    bob_home.mkdir()
    hub_kp = load_or_generate(hub_home)
    bob_kp = load_or_generate(bob_home)
    _pin(hub_home, "bob", bob_kp.pubkey_b64(),
         ["workgroup.join", "workgroup.post", "workgroup.pull"])

    wg = wg_mod.create(
        hub_home, name="race", hub_kp=hub_kp,
        member_pubkeys=[bob_kp.pubkey_b64()],
    )
    server = alp_server.Server(home=hub_home, agent_name="hub")
    wg_mod.register(server, hub_home)
    await server.start()
    try:
        join = await alp_client.call(
            socket_path=server.socket_path(),
            sender=bob_kp,
            recipient_pubkey_b64=hub_kp.pubkey_b64(),
            method="workgroup.join",
            params={"workgroup_id": wg.meta.id},
        )
        key = wg_mod.open_sealed_group_key(join["sealed_key"], bob_kp)

        async def _post(text: bytes):
            nonce, ct = wg_mod.encrypt_post(key, text)
            return await alp_client.call(
                socket_path=server.socket_path(),
                sender=bob_kp,
                recipient_pubkey_b64=hub_kp.pubkey_b64(),
                method="workgroup.post",
                params={"workgroup_id": wg.meta.id, "nonce": nonce, "ciphertext": ct},
            )

        results = await asyncio.gather(
            _post(b"first"), _post(b"second"), _post(b"third"),
        )
        seqs = sorted(r["seq"] for r in results)
        assert seqs == [1, 2, 3]

        # Transcript on disk reflects the same three posts in order.
        pull = await alp_client.call(
            socket_path=server.socket_path(),
            sender=bob_kp,
            recipient_pubkey_b64=hub_kp.pubkey_b64(),
            method="workgroup.pull",
            params={"workgroup_id": wg.meta.id, "since": 0},
        )
        assert [p["seq"] for p in pull["posts"]] == [1, 2, 3]
    finally:
        await server.stop()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_workgroup_state_survives_server_restart(short_tmp: Path) -> None:
    """Restarting the server should preserve the workgroup on disk."""
    hub_home = short_tmp / "hub"
    hub_home.mkdir()
    bob_home = short_tmp / "bob"
    bob_home.mkdir()
    hub_kp = load_or_generate(hub_home)
    bob_kp = load_or_generate(bob_home)
    _pin(hub_home, "bob", bob_kp.pubkey_b64(),
         ["workgroup.join", "workgroup.post", "workgroup.pull"])

    wg = wg_mod.create(
        hub_home, name="persistent", hub_kp=hub_kp,
        member_pubkeys=[bob_kp.pubkey_b64()],
    )

    server = alp_server.Server(home=hub_home, agent_name="hub")
    wg_mod.register(server, hub_home)
    await server.start()
    try:
        join = await alp_client.call(
            socket_path=server.socket_path(),
            sender=bob_kp,
            recipient_pubkey_b64=hub_kp.pubkey_b64(),
            method="workgroup.join",
            params={"workgroup_id": wg.meta.id},
        )
        key = wg_mod.open_sealed_group_key(join["sealed_key"], bob_kp)
        nonce, ct = wg_mod.encrypt_post(key, b"survive me")
        await alp_client.call(
            socket_path=server.socket_path(),
            sender=bob_kp,
            recipient_pubkey_b64=hub_kp.pubkey_b64(),
            method="workgroup.post",
            params={"workgroup_id": wg.meta.id, "nonce": nonce, "ciphertext": ct},
        )
    finally:
        await server.stop()

    # New server instance proves state is on disk.
    server2 = alp_server.Server(home=hub_home, agent_name="hub")
    wg_mod.register(server2, hub_home)
    await server2.start()
    try:
        pull = await alp_client.call(
            socket_path=server2.socket_path(),
            sender=bob_kp,
            recipient_pubkey_b64=hub_kp.pubkey_b64(),
            method="workgroup.pull",
            params={"workgroup_id": wg.meta.id, "since": 0},
        )
        assert pull["head"] == 1
        assert wg_mod.decrypt_post(
            key, pull["posts"][0]["nonce"], pull["posts"][0]["ciphertext"],
        ) == b"survive me"
    finally:
        await server2.stop()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_workgroup_over_tcp_noise(short_tmp: Path) -> None:
    """Same cycle over TCP / Noise_XK."""
    hub_home = short_tmp / "hub"
    hub_home.mkdir()
    bob_home = short_tmp / "bob"
    bob_home.mkdir()
    hub_kp = load_or_generate(hub_home)
    bob_kp = load_or_generate(bob_home)
    port = await _pick_free_port()
    _pin(hub_home, "bob", bob_kp.pubkey_b64(),
         ["workgroup.join", "workgroup.post", "workgroup.pull"])

    wg = wg_mod.create(
        hub_home, name="remote", hub_kp=hub_kp,
        member_pubkeys=[bob_kp.pubkey_b64()],
    )
    server = alp_server.Server(
        home=hub_home, agent_name="hub",
        tcp_host="127.0.0.1", tcp_port=port,
    )
    wg_mod.register(server, hub_home)
    await server.start()
    try:
        join = await alp_client.call_tcp(
            host="127.0.0.1", port=port,
            sender=bob_kp,
            recipient_pubkey_b64=hub_kp.pubkey_b64(),
            method="workgroup.join",
            params={"workgroup_id": wg.meta.id},
        )
        key = wg_mod.open_sealed_group_key(join["sealed_key"], bob_kp)

        nonce, ct = wg_mod.encrypt_post(key, b"hello via tcp")
        await alp_client.call_tcp(
            host="127.0.0.1", port=port,
            sender=bob_kp,
            recipient_pubkey_b64=hub_kp.pubkey_b64(),
            method="workgroup.post",
            params={"workgroup_id": wg.meta.id, "nonce": nonce, "ciphertext": ct},
        )

        pull = await alp_client.call_tcp(
            host="127.0.0.1", port=port,
            sender=bob_kp,
            recipient_pubkey_b64=hub_kp.pubkey_b64(),
            method="workgroup.pull",
            params={"workgroup_id": wg.meta.id, "since": 0},
        )
        assert pull["head"] == 1
        assert wg_mod.decrypt_post(
            key, pull["posts"][0]["nonce"], pull["posts"][0]["ciphertext"],
        ) == b"hello via tcp"
    finally:
        await server.stop()


# Leave + rekey.


@pytest.mark.integration
@pytest.mark.asyncio
async def test_leave_rotates_group_key_and_drops_member(short_tmp: Path) -> None:
    """Leave rotates the key and drops the leaver."""
    hub_home = short_tmp / "hub"
    hub_home.mkdir()
    a_home = short_tmp / "a"
    a_home.mkdir()
    b_home = short_tmp / "b"
    b_home.mkdir()
    hub_kp = load_or_generate(hub_home)
    a_kp = load_or_generate(a_home)
    b_kp = load_or_generate(b_home)
    _pin(hub_home, "a", a_kp.pubkey_b64(),
         ["workgroup.join", "workgroup.post", "workgroup.pull", "workgroup.leave"])
    _pin(hub_home, "b", b_kp.pubkey_b64(),
         ["workgroup.join", "workgroup.post", "workgroup.pull"])

    wg = wg_mod.create(
        hub_home, name="rekey-me", hub_kp=hub_kp,
        member_pubkeys=[a_kp.pubkey_b64(), b_kp.pubkey_b64()],
    )
    server = alp_server.Server(home=hub_home, agent_name="hub")
    wg_mod.register(server, hub_home)
    await server.start()
    try:
        # Both join and harvest the v1 key.
        async def _join(kp):
            r = await alp_client.call(
                socket_path=server.socket_path(),
                sender=kp,
                recipient_pubkey_b64=hub_kp.pubkey_b64(),
                method="workgroup.join",
                params={"workgroup_id": wg.meta.id},
            )
            return r, wg_mod.open_sealed_group_key(r["sealed_key"], kp)
        a_join, a_key_v1 = await _join(a_kp)
        b_join, b_key_v1 = await _join(b_kp)
        assert a_join["current_key_version"] == 1
        assert a_key_v1 == b_key_v1

        # B posts under v1 so we have pre-leave transcript.
        nonce, ct = wg_mod.encrypt_post(b_key_v1, b"before leave")
        await alp_client.call(
            socket_path=server.socket_path(),
            sender=b_kp,
            recipient_pubkey_b64=hub_kp.pubkey_b64(),
            method="workgroup.post",
            params={
                "workgroup_id": wg.meta.id,
                "key_version": 1,
                "nonce": nonce,
                "ciphertext": ct,
            },
        )

        # A leaves; the hub rotates to v2 for B.
        leave_result = await alp_client.call(
            socket_path=server.socket_path(),
            sender=a_kp,
            recipient_pubkey_b64=hub_kp.pubkey_b64(),
            method="workgroup.leave",
            params={"workgroup_id": wg.meta.id},
        )
        assert leave_result["current_key_version"] == 2
        assert a_kp.pubkey_b64() not in leave_result["remaining_members"]
        assert b_kp.pubkey_b64() in leave_result["remaining_members"]

        # B pulls, refreshes the key, and posts under v2.
        b_pull = await alp_client.call(
            socket_path=server.socket_path(),
            sender=b_kp,
            recipient_pubkey_b64=hub_kp.pubkey_b64(),
            method="workgroup.pull",
            params={"workgroup_id": wg.meta.id, "since": 0},
        )
        assert b_pull["current_key_version"] == 2
        b_key_v2 = wg_mod.open_sealed_group_key(b_pull["sealed_key"], b_kp)
        assert b_key_v2 != b_key_v1

        # Past post still decrypts with v1.
        old_post = b_pull["posts"][0]
        assert old_post["key_version"] == 1
        assert wg_mod.decrypt_post(
            b_key_v1, old_post["nonce"], old_post["ciphertext"],
        ) == b"before leave"

        # New post under v2 lands and decrypts.
        nonce2, ct2 = wg_mod.encrypt_post(b_key_v2, b"after leave")
        await alp_client.call(
            socket_path=server.socket_path(),
            sender=b_kp,
            recipient_pubkey_b64=hub_kp.pubkey_b64(),
            method="workgroup.post",
            params={
                "workgroup_id": wg.meta.id,
                "key_version": 2,
                "nonce": nonce2,
                "ciphertext": ct2,
            },
        )
        b_pull2 = await alp_client.call(
            socket_path=server.socket_path(),
            sender=b_kp,
            recipient_pubkey_b64=hub_kp.pubkey_b64(),
            method="workgroup.pull",
            params={"workgroup_id": wg.meta.id, "since": 1},
        )
        new_post = b_pull2["posts"][0]
        assert new_post["key_version"] == 2
        assert wg_mod.decrypt_post(
            b_key_v2, new_post["nonce"], new_post["ciphertext"],
        ) == b"after leave"
        # Old key cannot open new traffic.
        with pytest.raises(Exception):
            wg_mod.decrypt_post(
                b_key_v1, new_post["nonce"], new_post["ciphertext"],
            )
    finally:
        await server.stop()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_left_member_cannot_post_or_pull(short_tmp: Path) -> None:
    """After leave, the ex-member gets `-32008`."""
    hub_home = short_tmp / "hub"
    hub_home.mkdir()
    bob_home = short_tmp / "b"
    bob_home.mkdir()
    hub_kp = load_or_generate(hub_home)
    bob_kp = load_or_generate(bob_home)
    _pin(hub_home, "b", bob_kp.pubkey_b64(),
         ["workgroup.join", "workgroup.post", "workgroup.pull", "workgroup.leave"])
    wg = wg_mod.create(
        hub_home, name="bye", hub_kp=hub_kp,
        member_pubkeys=[bob_kp.pubkey_b64()],
    )
    server = alp_server.Server(home=hub_home, agent_name="hub")
    wg_mod.register(server, hub_home)
    await server.start()
    try:
        await alp_client.call(
            socket_path=server.socket_path(),
            sender=bob_kp,
            recipient_pubkey_b64=hub_kp.pubkey_b64(),
            method="workgroup.leave",
            params={"workgroup_id": wg.meta.id},
        )
        with pytest.raises(alp_client.RemoteError) as exc:
            await alp_client.call(
                socket_path=server.socket_path(),
                sender=bob_kp,
                recipient_pubkey_b64=hub_kp.pubkey_b64(),
                method="workgroup.pull",
                params={"workgroup_id": wg.meta.id, "since": 0},
            )
        assert exc.value.code == -32008
    finally:
        await server.stop()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_hub_cannot_leave_its_own_workgroup(short_tmp: Path) -> None:
    hub_home = short_tmp / "hub"
    hub_home.mkdir()
    other_home = short_tmp / "h2"
    other_home.mkdir()  # for envelope round-trip
    hub_kp = load_or_generate(hub_home)
    load_or_generate(other_home)
    # Pin the hub's own pubkey so its envelope passes the gate.
    _pin(hub_home, "self", hub_kp.pubkey_b64(), ["workgroup.leave"])
    wg = wg_mod.create(
        hub_home, name="solo", hub_kp=hub_kp, member_pubkeys=[],
    )
    server = alp_server.Server(home=hub_home, agent_name="hub")
    wg_mod.register(server, hub_home)
    await server.start()
    try:
        with pytest.raises(alp_client.RemoteError) as exc:
            await alp_client.call(
                socket_path=server.socket_path(),
                sender=hub_kp,
                recipient_pubkey_b64=hub_kp.pubkey_b64(),
                method="workgroup.leave",
                params={"workgroup_id": wg.meta.id},
            )
        assert exc.value.code == -32602
    finally:
        await server.stop()


def test_kick_local_primitive_drops_member_and_rekeys(short_tmp: Path) -> None:
    hub_home = short_tmp / "hub"
    hub_home.mkdir()
    a_home = short_tmp / "a"
    a_home.mkdir()
    b_home = short_tmp / "b"
    b_home.mkdir()
    hub_kp = load_or_generate(hub_home)
    a_kp = load_or_generate(a_home)
    b_kp = load_or_generate(b_home)

    wg = wg_mod.create(
        hub_home, name="kicker", hub_kp=hub_kp,
        member_pubkeys=[a_kp.pubkey_b64(), b_kp.pubkey_b64()],
    )
    assert wg.meta.current_key_version == 1
    a_v1 = wg_mod.open_sealed_group_key(
        wg.member(a_kp.pubkey_b64()).sealed_key, a_kp,
    )

    updated = wg_mod.kick(hub_home, wg.meta.id, a_kp.pubkey_b64())
    assert updated.meta.current_key_version == 2
    assert updated.member(a_kp.pubkey_b64()) is None
    b_v2 = wg_mod.open_sealed_group_key(
        updated.member(b_kp.pubkey_b64()).sealed_key, b_kp,
    )
    assert b_v2 != a_v1


def test_kick_rejects_hub_pubkey(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    home.mkdir()
    hub_kp = load_or_generate(home)
    wg = wg_mod.create(home, name="x", hub_kp=hub_kp, member_pubkeys=[])
    with pytest.raises(ValueError, match="hub cannot leave"):
        wg_mod.kick(home, wg.meta.id, hub_kp.pubkey_b64())


def test_kick_rejects_unknown_pubkey(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    home.mkdir()
    other_home = short_tmp / "o"
    other_home.mkdir()
    hub_kp = load_or_generate(home)
    other_kp = load_or_generate(other_home)
    wg = wg_mod.create(home, name="x", hub_kp=hub_kp, member_pubkeys=[])
    with pytest.raises(ValueError, match="not in roster"):
        wg_mod.kick(home, wg.meta.id, other_kp.pubkey_b64())


# PR 2 — workgroup budget


def test_create_validates_budget_shape(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    home.mkdir()
    kp = load_or_generate(home)
    # USD cap accepted, non-max_usd keys dropped (token budget removed)
    wg = wg_mod.create(
        home, name="usd", hub_kp=kp, member_pubkeys=[],
        budget={"max_usd": 1.0, "max_tokens": 1000},
    )
    assert wg.meta.budget == {"max_usd": 1.0}
    # Budget dict without max_usd
    with pytest.raises(ValueError, match="max_usd"):
        wg_mod.create(
            home, name="x", hub_kp=kp, member_pubkeys=[],
            budget={"foo": "bar"},
        )
    # Non-positive
    with pytest.raises(ValueError, match="max_usd"):
        wg_mod.create(
            home, name="x", hub_kp=kp, member_pubkeys=[],
            budget={"max_usd": 0},
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_post_admits_under_usd_cap_and_blocks_at_breach(short_tmp: Path) -> None:
    hub_home = short_tmp / "hub"
    hub_home.mkdir()
    bob_home = short_tmp / "b"
    bob_home.mkdir()
    hub_kp = load_or_generate(hub_home)
    bob_kp = load_or_generate(bob_home)
    _pin(hub_home, "b", bob_kp.pubkey_b64(),
         ["workgroup.join", "workgroup.post", "workgroup.pull"])

    wg = wg_mod.create(
        hub_home, name="capped", hub_kp=hub_kp,
        member_pubkeys=[bob_kp.pubkey_b64()],
        budget={"max_usd": 1.00},
    )
    server = alp_server.Server(home=hub_home, agent_name="hub")
    wg_mod.register(server, hub_home)
    await server.start()
    try:
        join = await alp_client.call(
            socket_path=server.socket_path(),
            sender=bob_kp,
            recipient_pubkey_b64=hub_kp.pubkey_b64(),
            method="workgroup.join",
            params={"workgroup_id": wg.meta.id},
        )
        key = wg_mod.open_sealed_group_key(join["sealed_key"], bob_kp)

        async def _post(declared_usd: float):
            nonce, ct = wg_mod.encrypt_post(key, b"x")
            return await alp_client.call(
                socket_path=server.socket_path(),
                sender=bob_kp,
                recipient_pubkey_b64=hub_kp.pubkey_b64(),
                method="workgroup.post",
                params={
                    "workgroup_id": wg.meta.id,
                    "key_version": 1,
                    "nonce": nonce,
                    "ciphertext": ct,
                    "cost": {"usd": declared_usd, "tokens": 0},
                },
            )

        # Two posts at 0.40 each stay under the cap.
        await _post(0.40)
        await _post(0.40)
        # Next post at 0.30 would push to 1.10 → reject
        with pytest.raises(alp_client.RemoteError) as exc:
            await _post(0.30)
        assert exc.value.code == -32005
        assert exc.value.data["cap_kind"] == "workgroup_usd"
        assert exc.value.data["cap"] == 1.00
        assert abs(exc.value.data["used"] - 0.80) < 1e-9
    finally:
        await server.stop()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_post_persists_token_split_in_transcript(short_tmp: Path) -> None:
    import json

    hub_home = short_tmp / "hub"
    hub_home.mkdir()
    bob_home = short_tmp / "b"
    bob_home.mkdir()
    hub_kp = load_or_generate(hub_home)
    bob_kp = load_or_generate(bob_home)
    _pin(hub_home, "b", bob_kp.pubkey_b64(), ["workgroup.join", "workgroup.post"])

    wg = wg_mod.create(
        hub_home, name="split", hub_kp=hub_kp,
        member_pubkeys=[bob_kp.pubkey_b64()],
    )
    server = alp_server.Server(home=hub_home, agent_name="hub")
    wg_mod.register(server, hub_home)
    await server.start()
    try:
        join = await alp_client.call(
            socket_path=server.socket_path(),
            sender=bob_kp,
            recipient_pubkey_b64=hub_kp.pubkey_b64(),
            method="workgroup.join",
            params={"workgroup_id": wg.meta.id},
        )
        key = wg_mod.open_sealed_group_key(join["sealed_key"], bob_kp)
        nonce, ct = wg_mod.encrypt_post(key, b"x")
        await alp_client.call(
            socket_path=server.socket_path(),
            sender=bob_kp,
            recipient_pubkey_b64=hub_kp.pubkey_b64(),
            method="workgroup.post",
            params={
                "workgroup_id": wg.meta.id,
                "key_version": 1,
                "nonce": nonce,
                "ciphertext": ct,
                "cost": {"usd": 0.05, "tokens": 1000, "tokens_in": 700, "tokens_out": 300},
            },
        )
        d = hub_home / "alp" / "workgroups" / wg.meta.id
        entry = json.loads((d / "transcript.jsonl").read_text().strip())
        assert entry["cost"]["tokens_in"] == 700
        assert entry["cost"]["tokens_out"] == 300
        assert entry["cost"]["tokens"] == 1000
    finally:
        await server.stop()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_post_requires_join_first(short_tmp: Path) -> None:
    import os as _os

    hub_home = short_tmp / "hub"
    hub_home.mkdir()
    bob_home = short_tmp / "b"
    bob_home.mkdir()
    hub_kp = load_or_generate(hub_home)
    bob_kp = load_or_generate(bob_home)
    _pin(hub_home, "b", bob_kp.pubkey_b64(), ["workgroup.join", "workgroup.post"])
    wg = wg_mod.create(
        hub_home, name="needsjoin", hub_kp=hub_kp,
        member_pubkeys=[bob_kp.pubkey_b64()],
    )
    server = alp_server.Server(home=hub_home, agent_name="hub")
    wg_mod.register(server, hub_home)
    await server.start()
    try:
        # Bob is on the roster but never joined → he holds no key, but the hub
        # must reject before that even matters.
        nonce, ct = wg_mod.encrypt_post(_os.urandom(wg_mod.GROUP_KEY_BYTES), b"x")
        with pytest.raises(alp_client.RemoteError) as exc:
            await alp_client.call(
                socket_path=server.socket_path(), sender=bob_kp,
                recipient_pubkey_b64=hub_kp.pubkey_b64(), method="workgroup.post",
                params={"workgroup_id": wg.meta.id, "key_version": 1,
                        "nonce": nonce, "ciphertext": ct},
            )
        assert exc.value.code == -32008
    finally:
        await server.stop()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_post_rejects_duplicate_nonce_and_clamps_negative_cost(short_tmp: Path) -> None:
    hub_home = short_tmp / "hub"
    hub_home.mkdir()
    bob_home = short_tmp / "b"
    bob_home.mkdir()
    hub_kp = load_or_generate(hub_home)
    bob_kp = load_or_generate(bob_home)
    _pin(hub_home, "b", bob_kp.pubkey_b64(), ["workgroup.join", "workgroup.post"])
    wg = wg_mod.create(
        hub_home, name="nonce", hub_kp=hub_kp,
        member_pubkeys=[bob_kp.pubkey_b64()],
    )
    server = alp_server.Server(home=hub_home, agent_name="hub")
    wg_mod.register(server, hub_home)
    await server.start()
    try:
        join = await alp_client.call(
            socket_path=server.socket_path(), sender=bob_kp,
            recipient_pubkey_b64=hub_kp.pubkey_b64(), method="workgroup.join",
            params={"workgroup_id": wg.meta.id},
        )
        key = wg_mod.open_sealed_group_key(join["sealed_key"], bob_kp)
        nonce, ct = wg_mod.encrypt_post(key, b"hello")

        async def _post(n, c, cost):
            return await alp_client.call(
                socket_path=server.socket_path(), sender=bob_kp,
                recipient_pubkey_b64=hub_kp.pubkey_b64(), method="workgroup.post",
                params={"workgroup_id": wg.meta.id, "key_version": 1,
                        "nonce": n, "ciphertext": c, "cost": cost},
            )

        # Negative cost is clamped to zero, not subtracted from the ledger.
        await _post(nonce, ct, {"usd": -5.0, "tokens": -10})
        ledger = wg_mod._load_ledger(wg_mod._wg_dir(hub_home, wg.meta.id))
        assert ledger["usd"] == 0.0
        assert ledger["tokens"] == 0

        # Re-posting the same (key_version, nonce) is rejected.
        nonce2, ct2 = wg_mod.encrypt_post(key, b"world")
        with pytest.raises(alp_client.RemoteError) as exc:
            await _post(nonce, ct2, {})
        assert exc.value.code == -32602
        # A fresh nonce works; combined tokens are normalized up to the in+out split.
        await _post(nonce2, ct2, {"tokens": 1, "tokens_in": 100, "tokens_out": 50})
        ledger = wg_mod._load_ledger(wg_mod._wg_dir(hub_home, wg.meta.id))
        assert ledger["tokens"] == 150
    finally:
        await server.stop()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_post_rejects_oversized_ciphertext(short_tmp: Path, monkeypatch) -> None:
    # The real cap (256 KiB) bites on TCP (1 MiB frames); the Unix socket's
    # 64 KiB readline limit is stricter. Shrink the cap to test the handler
    # logic with a payload the transport will still deliver.
    monkeypatch.setattr(wg_mod, "_MAX_POST_CIPHERTEXT", 64)
    hub_home = short_tmp / "hub"
    hub_home.mkdir()
    bob_home = short_tmp / "b"
    bob_home.mkdir()
    hub_kp = load_or_generate(hub_home)
    bob_kp = load_or_generate(bob_home)
    _pin(hub_home, "b", bob_kp.pubkey_b64(), ["workgroup.join", "workgroup.post"])
    wg = wg_mod.create(
        hub_home, name="big", hub_kp=hub_kp,
        member_pubkeys=[bob_kp.pubkey_b64()],
    )
    server = alp_server.Server(home=hub_home, agent_name="hub")
    wg_mod.register(server, hub_home)
    await server.start()
    try:
        with pytest.raises(alp_client.RemoteError) as exc:
            await alp_client.call(
                socket_path=server.socket_path(), sender=bob_kp,
                recipient_pubkey_b64=hub_kp.pubkey_b64(), method="workgroup.post",
                params={"workgroup_id": wg.meta.id, "key_version": 1, "nonce": "n",
                        "ciphertext": "a" * 200},
            )
        assert exc.value.code == -32602
    finally:
        await server.stop()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_no_budget_means_no_workgroup_cap(short_tmp: Path) -> None:
    hub_home = short_tmp / "hub"
    hub_home.mkdir()
    bob_home = short_tmp / "b"
    bob_home.mkdir()
    hub_kp = load_or_generate(hub_home)
    bob_kp = load_or_generate(bob_home)
    _pin(hub_home, "b", bob_kp.pubkey_b64(),
         ["workgroup.join", "workgroup.post"])

    wg = wg_mod.create(
        hub_home, name="open", hub_kp=hub_kp,
        member_pubkeys=[bob_kp.pubkey_b64()],
    )
    server = alp_server.Server(home=hub_home, agent_name="hub")
    wg_mod.register(server, hub_home)
    await server.start()
    try:
        join = await alp_client.call(
            socket_path=server.socket_path(),
            sender=bob_kp,
            recipient_pubkey_b64=hub_kp.pubkey_b64(),
            method="workgroup.join",
            params={"workgroup_id": wg.meta.id},
        )
        key = wg_mod.open_sealed_group_key(join["sealed_key"], bob_kp)
        # Five posts at $1000 each — no cap, so all admit.
        for i in range(5):
            nonce, ct = wg_mod.encrypt_post(key, str(i).encode())
            r = await alp_client.call(
                socket_path=server.socket_path(),
                sender=bob_kp,
                recipient_pubkey_b64=hub_kp.pubkey_b64(),
                method="workgroup.post",
                params={
                    "workgroup_id": wg.meta.id,
                    "key_version": 1,
                    "nonce": nonce,
                    "ciphertext": ct,
                    "cost": {"usd": 1000.0, "tokens": 999999},
                },
            )
            assert r["seq"] == i + 1
    finally:
        await server.stop()


def test_pr1_format_workgroup_loads_with_version_defaults(short_tmp: Path) -> None:
    """A workgroup written by PR 1 (no ``current_key_version`` in
    meta.yaml, no ``key_version`` per member) loads cleanly under PR 2,
    defaulting both to version 1. Backward-compat for any state on
    disk before this commit."""
    import yaml as _yaml
    home = short_tmp / "hub"
    home.mkdir()
    hub_kp = load_or_generate(home)
    other_home = short_tmp / "o"
    other_home.mkdir()
    other_kp = load_or_generate(other_home)

    wg_id = "wg_legacy"
    d = home / "alp" / "workgroups" / wg_id
    d.mkdir(parents=True)
    sealed = wg_mod.seal_group_key(b"\x00" * 32, hub_kp.pubkey_b64())
    sealed_other = wg_mod.seal_group_key(b"\x00" * 32, other_kp.pubkey_b64())
    (d / "meta.yaml").write_text(_yaml.safe_dump({
        "id": wg_id, "name": "legacy",
        "hub_pubkey": hub_kp.pubkey_b64(),
        "created_at": "2026-04-25T00:00:00Z",
    }))  # NOTE: no current_key_version
    (d / "members.yaml").write_text(_yaml.safe_dump([
        {"pubkey": hub_kp.pubkey_b64(), "sealed_key": sealed,
         "joined": True, "joined_at": "2026-04-25T00:00:00Z"},
        {"pubkey": other_kp.pubkey_b64(), "sealed_key": sealed_other},
    ]))  # NOTE: no key_version per member
    (d / "transcript.jsonl").touch()

    wg = wg_mod.load(home, wg_id)
    assert wg is not None
    assert wg.meta.current_key_version == 1
    for m in wg.members:
        assert m.key_version == 1
    # Rekey on top of legacy state still bumps cleanly to v2.
    updated = wg_mod.kick(home, wg_id, other_kp.pubkey_b64())
    assert updated.meta.current_key_version == 2


@pytest.mark.integration
@pytest.mark.asyncio
async def test_concurrent_post_and_leave_serialise_cleanly(short_tmp: Path) -> None:
    """Asyncio is single-loop; a leave fired alongside a post is
    serialised by the dispatcher. Pin that — if someone ever moves
    handler I/O off the loop and breaks the implicit lock, the test
    catches the race."""
    import asyncio

    hub_home = short_tmp / "hub"
    hub_home.mkdir()
    a_home = short_tmp / "a"
    a_home.mkdir()
    b_home = short_tmp / "b"
    b_home.mkdir()
    hub_kp = load_or_generate(hub_home)
    a_kp = load_or_generate(a_home)
    b_kp = load_or_generate(b_home)
    _pin(hub_home, "a", a_kp.pubkey_b64(),
         ["workgroup.join", "workgroup.post", "workgroup.leave"])
    _pin(hub_home, "b", b_kp.pubkey_b64(),
         ["workgroup.join", "workgroup.post"])

    wg = wg_mod.create(
        hub_home, name="race", hub_kp=hub_kp,
        member_pubkeys=[a_kp.pubkey_b64(), b_kp.pubkey_b64()],
    )
    server = alp_server.Server(home=hub_home, agent_name="hub")
    wg_mod.register(server, hub_home)
    await server.start()
    try:
        async def _join(kp):
            r = await alp_client.call(
                socket_path=server.socket_path(),
                sender=kp,
                recipient_pubkey_b64=hub_kp.pubkey_b64(),
                method="workgroup.join",
                params={"workgroup_id": wg.meta.id},
            )
            return wg_mod.open_sealed_group_key(r["sealed_key"], kp)
        await _join(a_kp)
        b_key = await _join(b_kp)

        async def _b_post():
            nonce, ct = wg_mod.encrypt_post(b_key, b"during race")
            return await alp_client.call(
                socket_path=server.socket_path(),
                sender=b_kp,
                recipient_pubkey_b64=hub_kp.pubkey_b64(),
                method="workgroup.post",
                params={
                    "workgroup_id": wg.meta.id,
                    "key_version": 1,
                    "nonce": nonce, "ciphertext": ct,
                },
            )

        async def _a_leave():
            return await alp_client.call(
                socket_path=server.socket_path(),
                sender=a_kp,
                recipient_pubkey_b64=hub_kp.pubkey_b64(),
                method="workgroup.leave",
                params={"workgroup_id": wg.meta.id},
            )

        # Race both; either order is fine if state stays coherent.
        results = await asyncio.gather(_b_post(), _a_leave(), return_exceptions=True)
        for r in results:
            assert not isinstance(r, Exception), f"crash: {r!r}"

        # Final state: A is gone, B remains, version is 2.
        wg_after = wg_mod.load(hub_home, wg.meta.id)
        assert wg_after.meta.current_key_version == 2
        assert wg_after.member(a_kp.pubkey_b64()) is None
        assert wg_after.member(b_kp.pubkey_b64()) is not None
        # Transcript should end with one post from B.
        d = hub_home / "alp" / "workgroups" / wg.meta.id
        lines = (d / "transcript.jsonl").read_text().strip().splitlines()
        assert len(lines) == 1
    finally:
        await server.stop()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_profile_budget_gate_fires_before_workgroup_gate(short_tmp: Path) -> None:
    """Profile caps win before the workgroup gate."""
    from alpi import config as cfg_mod
    from alpi import ledger

    hub_home = short_tmp / "hub"
    hub_home.mkdir()
    bob_home = short_tmp / "b"
    bob_home.mkdir()
    hub_kp = load_or_generate(hub_home)
    bob_kp = load_or_generate(bob_home)
    _pin(hub_home, "b", bob_kp.pubkey_b64(),
         ["workgroup.join", "workgroup.post"])

    # Pre-spend the hub's daily USD cap so the next call trips.
    cfg = cfg_mod.load(hub_home)
    cfg.budget = {"daily_usd": 0.10}
    cfg_mod.save(cfg)
    ledger.record(hub_home, usd=0.50, tokens=0)

    wg = wg_mod.create(
        hub_home, name="bothcaps", hub_kp=hub_kp,
        member_pubkeys=[bob_kp.pubkey_b64()],
        budget={"max_usd": 100.00},
    )
    server = alp_server.Server(home=hub_home, agent_name="hub")
    wg_mod.register(server, hub_home)
    await server.start()
    try:
        with pytest.raises(alp_client.RemoteError) as exc:
            await alp_client.call(
                socket_path=server.socket_path(),
                sender=bob_kp,
                recipient_pubkey_b64=hub_kp.pubkey_b64(),
                method="workgroup.join",
                params={"workgroup_id": wg.meta.id},
            )
        assert exc.value.code == -32005
        # Profile cap, not workgroup.
        assert exc.value.data.get("cap_kind") == "usd"
    finally:
        await server.stop()


def test_sequential_leaves_keep_bumping_versions(short_tmp: Path) -> None:
    """Two leaves in a row keep the latest sealed key on the survivors."""
    hub_home = short_tmp / "hub"
    hub_home.mkdir()
    a_home = short_tmp / "a"
    a_home.mkdir()
    b_home = short_tmp / "b"
    b_home.mkdir()
    c_home = short_tmp / "c"
    c_home.mkdir()
    hub_kp = load_or_generate(hub_home)
    a_kp = load_or_generate(a_home)
    b_kp = load_or_generate(b_home)
    c_kp = load_or_generate(c_home)

    wg = wg_mod.create(
        hub_home, name="seq", hub_kp=hub_kp,
        member_pubkeys=[a_kp.pubkey_b64(), b_kp.pubkey_b64(),
                        c_kp.pubkey_b64()],
    )
    assert wg.meta.current_key_version == 1
    c_v1 = wg_mod.open_sealed_group_key(
        wg.member(c_kp.pubkey_b64()).sealed_key, c_kp,
    )

    after_a = wg_mod.kick(hub_home, wg.meta.id, a_kp.pubkey_b64())
    assert after_a.meta.current_key_version == 2
    c_v2 = wg_mod.open_sealed_group_key(
        after_a.member(c_kp.pubkey_b64()).sealed_key, c_kp,
    )

    after_b = wg_mod.kick(hub_home, wg.meta.id, b_kp.pubkey_b64())
    assert after_b.meta.current_key_version == 3
    c_v3 = wg_mod.open_sealed_group_key(
        after_b.member(c_kp.pubkey_b64()).sealed_key, c_kp,
    )

    assert c_v1 != c_v2 != c_v3
    # A and B are gone; only hub + C remain
    remaining_pks = {m.pubkey for m in after_b.members}
    assert remaining_pks == {hub_kp.pubkey_b64(), c_kp.pubkey_b64()}


def test_ledger_records_cumulative_spend(short_tmp: Path) -> None:
    """Ledger updates are atomic and increment all counters."""
    import json
    hub_home = short_tmp / "hub"
    hub_home.mkdir()
    bob_home = short_tmp / "b"
    bob_home.mkdir()
    hub_kp = load_or_generate(hub_home)
    bob_kp = load_or_generate(bob_home)

    wg = wg_mod.create(
        hub_home, name="led", hub_kp=hub_kp,
        member_pubkeys=[bob_kp.pubkey_b64()],
    )
    ledger_path = (
        hub_home / "alp" / "workgroups" / wg.meta.id / "ledger.json"
    )
    initial = json.loads(ledger_path.read_text())
    assert initial == {"usd": 0.0, "tokens": 0, "posts": 0}


# PR 3 — pause + resume


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pause_blocks_post_but_allows_pull(short_tmp: Path) -> None:
    hub_home = short_tmp / "hub"
    hub_home.mkdir()
    a_home = short_tmp / "a"
    a_home.mkdir()
    b_home = short_tmp / "b"
    b_home.mkdir()
    hub_kp = load_or_generate(hub_home)
    a_kp = load_or_generate(a_home)
    b_kp = load_or_generate(b_home)
    _pin(hub_home, "a", a_kp.pubkey_b64(),
         ["workgroup.join", "workgroup.post", "workgroup.pull",
          "workgroup.leave"])
    _pin(hub_home, "b", b_kp.pubkey_b64(),
         ["workgroup.join", "workgroup.post", "workgroup.pull",
          "workgroup.leave"])

    wg = wg_mod.create(
        hub_home, name="paused", hub_kp=hub_kp,
        member_pubkeys=[a_kp.pubkey_b64(), b_kp.pubkey_b64()],
    )
    server = alp_server.Server(home=hub_home, agent_name="hub")
    wg_mod.register(server, hub_home)
    await server.start()
    try:
        async def _join(kp):
            r = await alp_client.call(
                socket_path=server.socket_path(),
                sender=kp,
                recipient_pubkey_b64=hub_kp.pubkey_b64(),
                method="workgroup.join",
                params={"workgroup_id": wg.meta.id},
            )
            return wg_mod.open_sealed_group_key(r["sealed_key"], kp)
        await _join(a_kp)
        b_key = await _join(b_kp)

        nonce, ct = wg_mod.encrypt_post(b_key, b"before pause")
        await alp_client.call(
            socket_path=server.socket_path(),
            sender=b_kp,
            recipient_pubkey_b64=hub_kp.pubkey_b64(),
            method="workgroup.post",
            params={
                "workgroup_id": wg.meta.id, "key_version": 1,
                "nonce": nonce, "ciphertext": ct,
            },
        )

        pause_result = await wc.pause(hub_home, wg.meta.id)
        assert pause_result["paused"] is True
        assert pause_result["paused_by"] == hub_kp.pubkey_b64()
        assert pause_result["paused_at"]

        b_pull = await alp_client.call(
            socket_path=server.socket_path(),
            sender=b_kp,
            recipient_pubkey_b64=hub_kp.pubkey_b64(),
            method="workgroup.pull",
            params={"workgroup_id": wg.meta.id, "since": 0},
        )
        assert b_pull["head"] == 1

        nonce2, ct2 = wg_mod.encrypt_post(b_key, b"during pause")
        with pytest.raises(alp_client.RemoteError) as exc:
            await alp_client.call(
                socket_path=server.socket_path(),
                sender=b_kp,
                recipient_pubkey_b64=hub_kp.pubkey_b64(),
                method="workgroup.post",
                params={
                    "workgroup_id": wg.meta.id, "key_version": 1,
                    "nonce": nonce2, "ciphertext": ct2,
                },
            )
        assert exc.value.code == -32010
        assert exc.value.data["paused_by"] == hub_kp.pubkey_b64()
    finally:
        await server.stop()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_resume_re_admits_posts(short_tmp: Path) -> None:
    hub_home = short_tmp / "hub"
    hub_home.mkdir()
    bob_home = short_tmp / "b"
    bob_home.mkdir()
    hub_kp = load_or_generate(hub_home)
    bob_kp = load_or_generate(bob_home)
    _pin(hub_home, "b", bob_kp.pubkey_b64(),
         ["workgroup.join", "workgroup.post"])

    wg = wg_mod.create(
        hub_home, name="cycle", hub_kp=hub_kp,
        member_pubkeys=[bob_kp.pubkey_b64()],
    )
    server = alp_server.Server(home=hub_home, agent_name="hub")
    wg_mod.register(server, hub_home)
    await server.start()
    try:
        join = await alp_client.call(
            socket_path=server.socket_path(),
            sender=bob_kp,
            recipient_pubkey_b64=hub_kp.pubkey_b64(),
            method="workgroup.join",
            params={"workgroup_id": wg.meta.id},
        )
        key = wg_mod.open_sealed_group_key(join["sealed_key"], bob_kp)

        await wc.pause(hub_home, wg.meta.id)
        resume = await wc.resume(hub_home, wg.meta.id)
        assert resume["paused"] is False

        nonce, ct = wg_mod.encrypt_post(key, b"after resume")
        r = await alp_client.call(
            socket_path=server.socket_path(),
            sender=bob_kp,
            recipient_pubkey_b64=hub_kp.pubkey_b64(),
            method="workgroup.post",
            params={
                "workgroup_id": wg.meta.id, "key_version": 1,
                "nonce": nonce, "ciphertext": ct,
            },
        )
        assert r["seq"] == 1

        wg_after = wg_mod.load(hub_home, wg.meta.id)
        assert wg_after.meta.paused is False
        assert wg_after.meta.paused_at == ""
        assert wg_after.meta.paused_by == ""
    finally:
        await server.stop()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_wire_pause_resume_reject_non_hub_callers(short_tmp: Path) -> None:
    hub_home = short_tmp / "hub"
    hub_home.mkdir()
    bob_home = short_tmp / "b"
    bob_home.mkdir()
    hub_kp = load_or_generate(hub_home)
    bob_kp = load_or_generate(bob_home)
    _pin(hub_home, "b", bob_kp.pubkey_b64(),
         ["workgroup.pause", "workgroup.resume"])

    wg = wg_mod.create(
        hub_home, name="guarded", hub_kp=hub_kp,
        member_pubkeys=[bob_kp.pubkey_b64()],
    )
    server = alp_server.Server(home=hub_home, agent_name="hub")
    wg_mod.register(server, hub_home)
    await server.start()
    try:
        for method in ("workgroup.pause", "workgroup.resume"):
            with pytest.raises(alp_client.RemoteError) as exc:
                await alp_client.call(
                    socket_path=server.socket_path(),
                    sender=bob_kp,
                    recipient_pubkey_b64=hub_kp.pubkey_b64(),
                    method=method,
                    params={"workgroup_id": wg.meta.id},
                )
            assert exc.value.code == -32008
            assert exc.value.message == "workgroup-not-hub"
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_pause_and_resume_are_idempotent(short_tmp: Path) -> None:
    hub_home = short_tmp / "hub"
    hub_home.mkdir()
    hub_kp = load_or_generate(hub_home)
    wg = wg_mod.create(
        hub_home, name="idem", hub_kp=hub_kp, member_pubkeys=[],
    )

    first = await wc.pause(hub_home, wg.meta.id)
    second = await wc.pause(hub_home, wg.meta.id)
    assert first["paused_at"] == second["paused_at"]
    assert first["paused_by"] == second["paused_by"] == hub_kp.pubkey_b64()

    await wc.resume(hub_home, wg.meta.id)
    again = await wc.resume(hub_home, wg.meta.id)
    assert again["paused"] is False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pause_does_not_block_leave(short_tmp: Path) -> None:
    hub_home = short_tmp / "hub"
    hub_home.mkdir()
    bob_home = short_tmp / "b"
    bob_home.mkdir()
    hub_kp = load_or_generate(hub_home)
    bob_kp = load_or_generate(bob_home)
    _pin(hub_home, "b", bob_kp.pubkey_b64(),
         ["workgroup.join", "workgroup.leave"])

    wg = wg_mod.create(
        hub_home, name="paused-exit", hub_kp=hub_kp,
        member_pubkeys=[bob_kp.pubkey_b64()],
    )
    server = alp_server.Server(home=hub_home, agent_name="hub")
    wg_mod.register(server, hub_home)
    await server.start()
    try:
        await alp_client.call(
            socket_path=server.socket_path(),
            sender=bob_kp,
            recipient_pubkey_b64=hub_kp.pubkey_b64(),
            method="workgroup.join",
            params={"workgroup_id": wg.meta.id},
        )
        await wc.pause(hub_home, wg.meta.id)
        leave_result = await alp_client.call(
            socket_path=server.socket_path(),
            sender=bob_kp,
            recipient_pubkey_b64=hub_kp.pubkey_b64(),
            method="workgroup.leave",
            params={"workgroup_id": wg.meta.id},
        )
        assert bob_kp.pubkey_b64() not in leave_result["remaining_members"]
        assert leave_result["current_key_version"] == 2
    finally:
        await server.stop()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pause_persists_across_server_restart(short_tmp: Path) -> None:
    hub_home = short_tmp / "hub"
    hub_home.mkdir()
    bob_home = short_tmp / "b"
    bob_home.mkdir()
    hub_kp = load_or_generate(hub_home)
    bob_kp = load_or_generate(bob_home)
    _pin(hub_home, "b", bob_kp.pubkey_b64(),
         ["workgroup.join", "workgroup.post"])

    wg = wg_mod.create(
        hub_home, name="restart-paused", hub_kp=hub_kp,
        member_pubkeys=[bob_kp.pubkey_b64()],
    )
    server = alp_server.Server(home=hub_home, agent_name="hub")
    wg_mod.register(server, hub_home)
    await server.start()
    try:
        join = await alp_client.call(
            socket_path=server.socket_path(),
            sender=bob_kp,
            recipient_pubkey_b64=hub_kp.pubkey_b64(),
            method="workgroup.join",
            params={"workgroup_id": wg.meta.id},
        )
        key = wg_mod.open_sealed_group_key(join["sealed_key"], bob_kp)
        await wc.pause(hub_home, wg.meta.id)
    finally:
        await server.stop()

    server2 = alp_server.Server(home=hub_home, agent_name="hub")
    wg_mod.register(server2, hub_home)
    await server2.start()
    try:
        nonce, ct = wg_mod.encrypt_post(key, b"x")
        with pytest.raises(alp_client.RemoteError) as exc:
            await alp_client.call(
                socket_path=server2.socket_path(),
                sender=bob_kp,
                recipient_pubkey_b64=hub_kp.pubkey_b64(),
                method="workgroup.post",
                params={
                    "workgroup_id": wg.meta.id, "key_version": 1,
                    "nonce": nonce, "ciphertext": ct,
                },
            )
        assert exc.value.code == -32010
    finally:
        await server2.stop()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_workgroup_verbs_bypass_peer_allow_list(short_tmp: Path) -> None:
    """`workgroup.*` bypasses the peer allow list; membership is the gate."""
    alice_home = short_tmp / "alice"
    alice_home.mkdir()
    bob_home = short_tmp / "bob"
    bob_home.mkdir()
    alice_kp = load_or_generate(alice_home)
    bob_kp = load_or_generate(bob_home)
    # Bob is pinned with no workgroup verbs; only link.ping.
    _pin(alice_home, "bob", bob_kp.pubkey_b64(), ["link.ping"])

    wg = wg_mod.create(
        alice_home, name="x", hub_kp=alice_kp,
        member_pubkeys=[bob_kp.pubkey_b64()],
    )
    server = alp_server.Server(home=alice_home, agent_name="alice")
    wg_mod.register(server, alice_home)
    await server.start()
    try:
        # Bob is a member, so workgroup.join succeeds despite his
        # peer entry on alice not listing any workgroup verb.
        result = await alp_client.call(
            socket_path=server.socket_path(),
            sender=bob_kp,
            recipient_pubkey_b64=alice_kp.pubkey_b64(),
            method="workgroup.join",
            params={"workgroup_id": wg.meta.id},
        )
        assert result["workgroup_id"] == wg.meta.id
    finally:
        await server.stop()


def test_create_persists_the_launch_chain(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    home.mkdir()
    kp = load_or_generate(home)
    wg = wg_mod.create(
        home, name="proj", hub_kp=kp, member_pubkeys=[],
        pipelines={"intake": ["intake", "design", "content"]},
        launch_pipeline="intake",
    )
    assert wg_mod.load(home, wg.meta.id).meta.launch_chain == ("intake", "design", "content")
    wg2 = wg_mod.create(home, name="delib", hub_kp=kp, member_pubkeys=[])
    assert wg_mod.load(home, wg2.meta.id).meta.launch_chain == ()


def test_create_rejects_invalid_and_duplicate_pipeline_slugs(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    home.mkdir()
    kp = load_or_generate(home)
    with pytest.raises(ValueError, match="invalid pipeline phase slug"):
        wg_mod.create(home, name="x", hub_kp=kp, member_pubkeys=[], pipelines={"bad": ["Bad Slug"]})
    with pytest.raises(ValueError, match="duplicate pipeline phase slug"):
        wg_mod.create(home, name="y", hub_kp=kp, member_pubkeys=[], pipelines={"seo": ["seo", "seo"]})


def test_meta_quorum_timeout_round_trips(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    home.mkdir()
    kp = load_or_generate(home)
    wg = wg_mod.create(home, name="qt", hub_kp=kp, member_pubkeys=[])
    d = home / "alp" / "workgroups" / wg.meta.id
    wg.meta.quorum_timeout_seconds = 120
    wg_mod._save_meta(d, wg.meta)
    reloaded = wg_mod.load(home, wg.meta.id)
    assert reloaded is not None
    assert reloaded.meta.quorum_timeout_seconds == 120


def test_coerce_positive_int_rejects_junk_and_negatives() -> None:
    assert wg_mod._coerce_positive_int("bad") == 0
    assert wg_mod._coerce_positive_int(-1) == 0
    assert wg_mod._coerce_positive_int(0) == 0
    assert wg_mod._coerce_positive_int(None) == 0
    assert wg_mod._coerce_positive_int(120) == 120


def test_load_meta_tolerant_to_bad_quorum_timeout(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    home.mkdir()
    kp = load_or_generate(home)
    wg = wg_mod.create(home, name="qtbad", hub_kp=kp, member_pubkeys=[])
    meta_path = home / "alp" / "workgroups" / wg.meta.id / "meta.yaml"
    import yaml as _yaml
    for junk in ("bad", -1):
        raw = _yaml.safe_load(meta_path.read_text())
        raw["quorum_timeout_seconds"] = junk
        meta_path.write_text(_yaml.safe_dump(raw))
        reloaded = wg_mod.load(home, wg.meta.id)
        assert reloaded is not None and reloaded.meta.quorum_timeout_seconds == 0


def _pipeline_meta(
    pipelines: dict, launch: str | None, steps: dict | None = None,
) -> wg_mod.Meta:
    return wg_mod.Meta(
        id="wg-x", name="x", hub_pubkey="pk", created_at="2026-01-01T00:00:00Z",
        pipelines={k: tuple(v) for k, v in pipelines.items()},
        launch_pipeline=launch,
        pipeline_steps={k: dict(v) for k, v in (steps or {}).items()},
    )


def _write_raw_meta(home: Path, wg_id: str, hub_pubkey: str, extra: dict) -> Path:
    import yaml as _yaml
    d = home / "alp" / "workgroups" / wg_id
    d.mkdir(parents=True)
    (d / "meta.yaml").write_text(_yaml.safe_dump({
        "id": wg_id, "name": "old", "hub_pubkey": hub_pubkey,
        "created_at": "2026-07-01T00:00:00Z", **extra,
    }))
    (d / "members.yaml").write_text(_yaml.safe_dump([]))
    (d / "transcript.jsonl").touch()
    return d


def test_create_persists_named_chains_and_their_steps(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    home.mkdir()
    kp = load_or_generate(home)
    wg = wg_mod.create(
        home, name="proj", hub_kp=kp, member_pubkeys=[],
        pipelines={
            "intake": ["intake", "build"],
            "media-update": ["media-update", "media-qa"],
        },
        launch_pipeline="intake",
        pipeline_steps={
            "intake": {"owner": "scout"},
            "build": {"owner": "pixel"},
            "media-update": {"owner": "muse"},
            "media-qa": {"owner": "lens"},
        },
    )
    meta = wg_mod.load(home, wg.meta.id).meta
    assert meta.pipelines == {
        "intake": ("intake", "build"),
        "media-update": ("media-update", "media-qa"),
    }
    assert meta.launch_pipeline == "intake"
    assert meta.launch_chain == ("intake", "build")
    assert wg_mod.dormant_pipelines(meta) == {
        "media-update": ("media-update", "media-qa"),
    }
    assert {"media-update", "media-qa"} <= set(meta.pipeline_steps)


@pytest.mark.parametrize("retired", [
    {"pipeline": ["intake", "build"]},
    {"operations": {"media-update": ["media-update", "media-qa"]}},
])
def test_create_no_longer_accepts_the_retired_kwargs(short_tmp: Path, retired) -> None:
    home = short_tmp / "hub"
    home.mkdir()
    kp = load_or_generate(home)
    with pytest.raises(TypeError, match="unexpected keyword argument"):
        wg_mod.create(home, name="x", hub_kp=kp, member_pubkeys=[], **retired)


def test_create_rejects_a_chain_not_keyed_by_its_first_phase(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    home.mkdir()
    kp = load_or_generate(home)
    with pytest.raises(ValueError, match="must be keyed by its first phase"):
        wg_mod.create(
            home, name="x", hub_kp=kp, member_pubkeys=[],
            pipelines={"intake": ["intake"], "media-update": ["media-qa"]},
            launch_pipeline="intake",
            pipeline_steps={"intake": {"owner": "scout"}, "media-qa": {"owner": "lens"}},
        )


def test_pipeline_steps_outside_every_declared_chain_still_rejected(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    home.mkdir()
    kp = load_or_generate(home)
    with pytest.raises(
        ValueError,
        match=r"pipeline_steps key 'ghost' belongs to no declared pipeline \['intake'\]",
    ):
        wg_mod.create(
            home, name="x", hub_kp=kp, member_pubkeys=[],
            pipelines={"intake": ["intake"]}, launch_pipeline="intake",
            pipeline_steps={"intake": {"owner": "scout"}, "ghost": {"owner": "lens"}},
        )


def test_pipeline_steps_reject_author_supplied_next(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    home.mkdir()
    kp = load_or_generate(home)
    with pytest.raises(
        ValueError,
        match=(
            r"pipeline_steps\['intake'\].next is derived from pipelines\['intake'\]; "
            r"remove next"
        ),
    ):
        wg_mod.create(
            home, name="x", hub_kp=kp, member_pubkeys=[],
            pipelines={"intake": ["intake", "build"]}, launch_pipeline="intake",
            pipeline_steps={
                "intake": {"owner": "scout", "next": "build"},
                "build": {"owner": "pixel"},
            },
        )


def test_create_without_dormant_chains_leaves_only_the_launch_chain(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    home.mkdir()
    kp = load_or_generate(home)
    wg = wg_mod.create(
        home, name="proj", hub_kp=kp, member_pubkeys=[],
        pipelines={"intake": ["intake"]}, launch_pipeline="intake",
    )
    meta = wg_mod.load(home, wg.meta.id).meta
    assert meta.pipelines == {"intake": ("intake",)}
    assert wg_mod.dormant_pipelines(meta) == {}


@pytest.mark.parametrize("pipelines,needle", [
    ({"x": []}, "non-empty phase list"),
    ({"x": "xyz"}, "must be a list of phase slugs"),
    ({"Bad Op": ["bad op"]}, "not a valid slug"),
    ({"x": ["x", "x"]}, "duplicate pipeline phase slug"),
    ({"x": ["y"]}, "must be keyed by its first phase"),
    ({"x": ["x", "intake"], "intake": ["intake"]}, "chains must be disjoint"),
    ({"x": ["x", "shared"], "z": ["z", "shared"]}, "chains must be disjoint"),
    ("nope", "must be a mapping"),
])
def test_create_rejects_malformed_pipelines(short_tmp: Path, pipelines, needle) -> None:
    home = short_tmp / "hub"
    home.mkdir()
    kp = load_or_generate(home)
    steps = {
        "intake": {"owner": "scout"}, "x": {"owner": "muse"}, "y": {"owner": "muse"},
        "z": {"owner": "muse"}, "shared": {"owner": "lens"}, "bad op": {"owner": "lens"},
    }
    with pytest.raises(ValueError, match=needle):
        wg_mod.create(
            home, name="x", hub_kp=kp, member_pubkeys=[],
            pipelines=pipelines, pipeline_steps=steps,
        )


def test_create_rejects_an_unknown_launch_pipeline(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    home.mkdir()
    kp = load_or_generate(home)
    with pytest.raises(ValueError, match="is not one of"):
        wg_mod.create(
            home, name="x", hub_kp=kp, member_pubkeys=[],
            pipelines={"intake": ["intake"]}, launch_pipeline="build",
        )
    with pytest.raises(ValueError, match="without any pipelines"):
        wg_mod.create(
            home, name="y", hub_kp=kp, member_pubkeys=[], launch_pipeline="intake",
        )


def test_meta_launch_chain_is_a_read_only_derived_view() -> None:
    meta = _pipeline_meta({"intake": ["intake", "build"]}, "intake")
    assert meta.launch_chain == ("intake", "build")
    assert not hasattr(meta, "pipeline")
    assert not hasattr(meta, "operations")
    with pytest.raises(AttributeError):
        meta.launch_chain = ("other",)


def test_meta_carries_launch_provenance_beside_canonical_chains(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    home.mkdir()
    hub_kp = load_or_generate(home)
    launch_provenance = {
        "recipe_id": "hotel-site",
        "digest": "sha256:abc123",
        "params": {"slug": "hotel-abad"},
        "project": "/git/web-factory/hotel-abad",
        "template_commit": "953de0d",
    }
    _write_raw_meta(home, "wg_canon", hub_kp.pubkey_b64(), {
        "pipelines": {
            "intake": ["intake", "build"],
            "media-update": ["media-update", "media-qa"],
        },
        "launch_pipeline": "intake",
        "pipeline_steps": {
            "intake": {"owner": "scout", "next": "build"},
            "build": {"owner": "pixel"},
            "media-update": {"owner": "muse", "next": "media-qa"},
            "media-qa": {"owner": "lens"},
        },
        "launch": launch_provenance,
    })

    meta = wg_mod.load(home, "wg_canon").meta
    assert meta.pipelines == {
        "intake": ("intake", "build"),
        "media-update": ("media-update", "media-qa"),
    }
    assert meta.launch_pipeline == "intake"
    assert meta.launch_chain == ("intake", "build")
    assert wg_mod.dormant_pipelines(meta) == {
        "media-update": ("media-update", "media-qa"),
    }
    assert meta.launch == launch_provenance
    assert all("next" not in spec for spec in meta.pipeline_steps.values())


@pytest.mark.parametrize("retired", [
    {"pipeline": ["intake", "build"]},
    {"operations": {"media-update": ["media-update", "media-qa"]}},
])
def test_meta_on_the_retired_shape_does_not_load(short_tmp: Path, retired, caplog) -> None:
    home = short_tmp / "hub"
    home.mkdir()
    hub_kp = load_or_generate(home)
    _write_raw_meta(home, "wg_retired", hub_kp.pubkey_b64(), {
        "pipelines": {"intake": ["intake", "build"]},
        "launch_pipeline": "intake",
        "pipeline_steps": {"intake": {"owner": "scout"}, "build": {"owner": "pixel"}},
        **retired,
    })
    with caplog.at_level("WARNING", logger="alpi.alp.workgroup"):
        assert wg_mod.load(home, "wg_retired") is None
        assert wg_mod.load(home, "wg_retired") is None
    warnings = [r for r in caplog.records if "did not load" in r.message]
    assert len(warnings) == 1
    assert "wg_retired" in warnings[0].getMessage()
    assert "retired" in warnings[0].getMessage()


def test_save_meta_writes_no_retired_or_derived_keys(short_tmp: Path) -> None:
    import yaml as _yaml
    home = short_tmp / "hub"
    home.mkdir()
    kp = load_or_generate(home)
    wg = wg_mod.create(
        home, name="proj", hub_kp=kp, member_pubkeys=[],
        pipelines={
            "intake": ["intake", "build"],
            "media-update": ["media-update", "media-qa"],
        },
        launch_pipeline="intake",
        pipeline_steps={
            "intake": {"owner": "scout"},
            "build": {"owner": "pixel"},
            "media-update": {"owner": "muse"},
            "media-qa": {"owner": "lens"},
        },
    )
    meta_path = home / "alp" / "workgroups" / wg.meta.id / "meta.yaml"
    raw = _yaml.safe_load(meta_path.read_text())
    assert raw["pipelines"] == {
        "intake": ["intake", "build"],
        "media-update": ["media-update", "media-qa"],
    }
    assert raw["launch_pipeline"] == "intake"
    assert "pipeline" not in raw
    assert "operations" not in raw
    assert all("next" not in spec for spec in raw["pipeline_steps"].values())
    assert wg_mod.load(home, wg.meta.id) is not None


def test_launchless_meta_writes_no_launch_selector(short_tmp: Path) -> None:
    import yaml as _yaml
    home = short_tmp / "hub"
    home.mkdir()
    kp = load_or_generate(home)
    wg = wg_mod.create(
        home, name="idle", hub_kp=kp, member_pubkeys=[],
        pipelines={"media-update": ["media-update", "media-qa"]},
        pipeline_steps={
            "media-update": {"owner": "muse"},
            "media-qa": {"owner": "lens"},
        },
    )
    meta_path = home / "alp" / "workgroups" / wg.meta.id / "meta.yaml"
    raw = _yaml.safe_load(meta_path.read_text())
    assert raw["pipelines"] == {"media-update": ["media-update", "media-qa"]}
    assert "launch_pipeline" not in raw
    assert "pipeline" not in raw
    assert "operations" not in raw
    assert all("next" not in spec for spec in raw["pipeline_steps"].values())

    reloaded = wg_mod.load(home, wg.meta.id).meta
    assert reloaded.launch_pipeline is None
    assert reloaded.launch_chain == ()


def test_meta_save_load_save_round_trips_byte_identical(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    home.mkdir()
    kp = load_or_generate(home)
    wg = wg_mod.create(
        home, name="rt", hub_kp=kp, member_pubkeys=[],
        budget={"max_usd": 5.0},
        briefing="ship the site",
        notify_on_close="notify",
        pipelines={
            "intake": ["intake", "build"],
            "media-update": ["media-update", "media-qa"],
        },
        launch_pipeline="intake",
        pipeline_steps={
            "intake": {"owner": "scout", "task": "gather #intake"},
            "build": {"owner": "pixel", "gate": {"argv": ["make", "build"], "cwd": "/tmp"}},
            "media-update": {"owner": "muse"},
            "media-qa": {"owner": "lens", "gate": {"argv": ["make", "qa"]}},
        },
        quorum_timeout_seconds=120,
        launch={"recipe_id": "hotel-site", "digest": "sha256:abc123"},
    )
    d = home / "alp" / "workgroups" / wg.meta.id
    first = (d / "meta.yaml").read_bytes()
    reloaded = wg_mod._load_meta(d)
    wg_mod._save_meta(d, reloaded)
    assert (d / "meta.yaml").read_bytes() == first
    again = wg_mod._load_meta(d)
    assert again.pipelines == reloaded.pipelines
    assert again.launch_pipeline == reloaded.launch_pipeline
    assert again.pipeline_steps == reloaded.pipeline_steps


def test_load_meta_strips_derived_next_from_pipeline_steps(short_tmp: Path) -> None:
    import yaml as _yaml
    home = short_tmp / "hub"
    home.mkdir()
    kp = load_or_generate(home)
    wg = wg_mod.create(
        home, name="stripnext", hub_kp=kp, member_pubkeys=[],
        pipelines={"intake": ["intake", "build"]}, launch_pipeline="intake",
        pipeline_steps={"intake": {"owner": "scout"}, "build": {"owner": "pixel"}},
    )
    meta_path = home / "alp" / "workgroups" / wg.meta.id / "meta.yaml"
    raw = _yaml.safe_load(meta_path.read_text())
    raw["pipeline_steps"]["intake"]["next"] = "bogus"
    raw["pipeline_steps"]["build"]["next"] = "intake"
    meta_path.write_text(_yaml.safe_dump(raw))

    meta = wg_mod.load(home, wg.meta.id).meta
    assert meta.pipeline_steps == {"intake": {"owner": "scout"}, "build": {"owner": "pixel"}}
    assert wg_mod.pipeline_successor(meta, "intake") == "build"
    assert wg_mod.pipeline_successor(meta, "build") == ""


@pytest.mark.parametrize("gone", [
    "set_launch_chain",
    "resolve_pipelines",
    "legacy_pipelines",
    "legacy_operations",
    "_prune_orphan_steps",
])
def test_post_launch_chain_editing_helpers_are_gone(gone: str) -> None:
    assert not hasattr(wg_mod, gone)
