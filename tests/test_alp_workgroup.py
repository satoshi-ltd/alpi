"""ALP.3 PR 1 — workgroup hub state + 4 core verbs.

Covers the local primitive (``create``) plus the over-the-wire
handlers (``workgroup.join``, ``workgroup.post``, ``workgroup.pull``)
end-to-end against a real Server over a Unix socket.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from alpi.alp import client as alp_client
from alpi.alp import peers as peers_mod
from alpi.alp import server as alp_server
from alpi.alp import workgroup as wg_mod
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
    a.mkdir(); b.mkdir()
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
    # hub auto-joined; remote members start un-joined
    hub_member = wg.member(hub_kp.pubkey_b64())
    assert hub_member is not None and hub_member.joined
    bob_member = wg.member(bob_kp.pubkey_b64())
    assert bob_member is not None and not bob_member.joined

    # Persisted under ``alp/workgroups/<id>/``
    d = home / "alp" / "workgroups" / wg.meta.id
    assert (d / "meta.yaml").exists()
    assert (d / "members.yaml").exists()
    assert (d / "transcript.jsonl").exists()
    assert (d / "transcript.jsonl").read_text() == ""


def test_create_seals_the_same_group_key_for_every_member(short_tmp: Path) -> None:
    home = short_tmp / "hub"; home.mkdir()
    hub_kp = load_or_generate(home)
    a_home = short_tmp / "a"; a_home.mkdir()
    b_home = short_tmp / "b"; b_home.mkdir()
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
    home = short_tmp / "hub"; home.mkdir()
    kp = load_or_generate(home)
    with pytest.raises(ValueError):
        wg_mod.create(home, name="", hub_kp=kp, member_pubkeys=[])


def test_create_rejects_invalid_member_pubkey(short_tmp: Path) -> None:
    home = short_tmp / "hub"; home.mkdir()
    kp = load_or_generate(home)
    with pytest.raises(ValueError):
        wg_mod.create(home, name="x", hub_kp=kp, member_pubkeys=["not-a-real-key"])


def test_create_dedups_repeated_pubkeys(short_tmp: Path) -> None:
    home = short_tmp / "hub"; home.mkdir()
    hub_kp = load_or_generate(home)
    bob_home = short_tmp / "b"; bob_home.mkdir()
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
    home = short_tmp / "hub"; home.mkdir()
    hub_kp = load_or_generate(home)
    wg1 = wg_mod.create(home, name="one", hub_kp=hub_kp, member_pubkeys=[])
    wg2 = wg_mod.create(home, name="two", hub_kp=hub_kp, member_pubkeys=[])
    ids = {w.meta.id for w in wg_mod.list_workgroups(home)}
    assert ids == {wg1.meta.id, wg2.meta.id}
    reloaded = wg_mod.load(home, wg1.meta.id)
    assert reloaded is not None and reloaded.meta.name == "one"


def test_load_returns_none_for_missing_workgroup(short_tmp: Path) -> None:
    home = short_tmp / "hub"; home.mkdir()
    assert wg_mod.load(home, "wg_nonexistent") is None


# End-to-end over the Unix socket


@pytest.mark.asyncio
async def test_join_post_pull_end_to_end(short_tmp: Path) -> None:
    """Two-profile scenario: alice is the hub, bob is the remote
    member. Bob joins, posts, then pulls; the transcript fans back
    out under the same group key."""
    alice_home = short_tmp / "alice"; alice_home.mkdir()
    bob_home = short_tmp / "bob"; bob_home.mkdir()
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


@pytest.mark.asyncio
async def test_join_marks_member_as_joined(short_tmp: Path) -> None:
    alice_home = short_tmp / "alice"; alice_home.mkdir()
    bob_home = short_tmp / "bob"; bob_home.mkdir()
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


@pytest.mark.asyncio
async def test_unknown_workgroup_returns_not_found(short_tmp: Path) -> None:
    alice_home = short_tmp / "alice"; alice_home.mkdir()
    bob_home = short_tmp / "bob"; bob_home.mkdir()
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


@pytest.mark.asyncio
async def test_non_member_peer_rejected_with_not_member(short_tmp: Path) -> None:
    """A peer with the verb capability but not part of *this* workgroup
    sees ``-32008 workgroup-not-member`` instead of silent success."""
    alice_home = short_tmp / "alice"; alice_home.mkdir()
    bob_home = short_tmp / "bob"; bob_home.mkdir()
    alice_kp = load_or_generate(alice_home)
    bob_kp = load_or_generate(bob_home)
    _pin(alice_home, "bob", bob_kp.pubkey_b64(),
         ["workgroup.join", "workgroup.post", "workgroup.pull"])

    # Workgroup created without bob in the roster.
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


@pytest.mark.asyncio
async def test_three_members_post_and_each_decrypts_each_other(short_tmp: Path) -> None:
    """Hub + 2 remote members. Each remote posts; both remotes plus
    the hub pull and decrypt the full transcript."""
    hub_home = short_tmp / "hub"; hub_home.mkdir()
    a_home = short_tmp / "a"; a_home.mkdir()
    b_home = short_tmp / "b"; b_home.mkdir()
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


@pytest.mark.asyncio
async def test_concurrent_posts_assign_distinct_sequential_seqs(short_tmp: Path) -> None:
    """Two posts launched concurrently must each land with a unique
    seq, no skip and no duplicate. The single-loop async dispatch is
    the implicit lock — this test pins that guarantee."""
    import asyncio

    hub_home = short_tmp / "hub"; hub_home.mkdir()
    bob_home = short_tmp / "bob"; bob_home.mkdir()
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


@pytest.mark.asyncio
async def test_workgroup_state_survives_server_restart(short_tmp: Path) -> None:
    """Stop the server, restart it, confirm the workgroup + transcript
    reload from disk and ``pull`` keeps working."""
    hub_home = short_tmp / "hub"; hub_home.mkdir()
    bob_home = short_tmp / "bob"; bob_home.mkdir()
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

    # Fresh Server instance — proves state is on disk, not in memory.
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


@pytest.mark.asyncio
async def test_workgroup_over_tcp_noise(short_tmp: Path) -> None:
    """Same join → post → pull cycle but routed through Noise_XK / TCP
    instead of the Unix socket, to confirm the dispatch path is
    transport-agnostic."""
    hub_home = short_tmp / "hub"; hub_home.mkdir()
    bob_home = short_tmp / "bob"; bob_home.mkdir()
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


@pytest.mark.asyncio
async def test_capability_denied_when_verb_not_allowed(short_tmp: Path) -> None:
    """Even a workgroup member is rejected at the capability layer if
    the verb isn't in their peers.yaml ``allow`` list — fail-closed."""
    alice_home = short_tmp / "alice"; alice_home.mkdir()
    bob_home = short_tmp / "bob"; bob_home.mkdir()
    alice_kp = load_or_generate(alice_home)
    bob_kp = load_or_generate(bob_home)
    # Bob is pinned but with NO workgroup verbs allowed.
    _pin(alice_home, "bob", bob_kp.pubkey_b64(), ["link.ping"])

    wg = wg_mod.create(
        alice_home, name="x", hub_kp=alice_kp,
        member_pubkeys=[bob_kp.pubkey_b64()],
    )
    server = alp_server.Server(home=alice_home, agent_name="alice")
    wg_mod.register(server, alice_home)
    await server.start()
    try:
        with pytest.raises(alp_client.RemoteError) as exc:
            await alp_client.call(
                socket_path=server.socket_path(),
                sender=bob_kp,
                recipient_pubkey_b64=alice_kp.pubkey_b64(),
                method="workgroup.join",
                params={"workgroup_id": wg.meta.id},
            )
        assert exc.value.code == -32001  # capability-denied
    finally:
        await server.stop()
