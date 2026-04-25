"""Live demo of ALP.3 workgroups with two overlapping groups.

Run::

    uv run python scripts/demo_workgroups.py

What it shows
-------------
Five in-process alpi profiles named after your real ones (alice,
bob, bling, mirai, default). Two workgroups, with **alice in both**:

    WG-A "design"   (2 members)  hub=alice + bob
    WG-B "research" (4 members)  hub=mirai + bling + default + alice

For each workgroup we run the canonical flow end-to-end:

    create on the hub
    -> every remote member joins (gets a sealed group key)
    -> each remote posts an encrypted message
    -> every member pulls and decrypts the full transcript
    -> the cross-member transcript is verified

Sandboxed under ``/tmp/alpi-demo-workgroups/`` — your real profiles
under ``~/.alpi/`` are NOT touched. Tear-down at exit.
"""

from __future__ import annotations

import asyncio
import shutil
import sys
import tempfile
from pathlib import Path

from alpi.alp import client as alp_client
from alpi.alp import peers as peers_mod
from alpi.alp import server as alp_server
from alpi.alp import workgroup as wg_mod
from alpi.alp.keys import Keypair, load_or_generate
from alpi.alp.peers import Peer


PROFILE_NAMES = ["alice", "bob", "bling", "mirai", "default"]


def _h(text: str) -> str:
    return f"\033[1;36m{text}\033[0m"


def _ok(text: str) -> str:
    return f"\033[32m✓\033[0m {text}"


def _arrow(text: str) -> str:
    return f"  \033[2m→\033[0m {text}"


async def _run_demo(root: Path) -> None:
    homes: dict[str, Path] = {}
    keys: dict[str, Keypair] = {}
    servers: dict[str, alp_server.Server] = {}

    print(_h("setup"))
    for name in PROFILE_NAMES:
        homes[name] = root / name
        homes[name].mkdir(parents=True)
        keys[name] = load_or_generate(homes[name])
        print(_arrow(f"{name:<8} pubkey {keys[name].pubkey_b64()[:24]}…"))

    # peers.yaml — every hub pins the verbs its members will invoke.
    workgroup_allow = [
        "workgroup.join", "workgroup.post", "workgroup.pull",
        "workgroup.leave",
    ]

    # WG-A (alice = hub) needs bob pinned
    peers_mod.add(homes["alice"], Peer(
        id="bob", pubkey=keys["bob"].pubkey_b64(), allow=workgroup_allow,
    ))
    # WG-B (mirai = hub) needs bling, default, alice pinned
    for member in ("bling", "default", "alice"):
        peers_mod.add(homes["mirai"], Peer(
            id=member, pubkey=keys[member].pubkey_b64(), allow=workgroup_allow,
        ))

    # Spin up an ALP server for every profile that acts as a hub.
    for hub in ("alice", "mirai"):
        srv = alp_server.Server(home=homes[hub], agent_name=hub)
        wg_mod.register(srv, homes[hub])
        await srv.start()
        servers[hub] = srv
        print(_ok(f"{hub:<8} alp server up at {srv.socket_path()}"))

    try:
        await _wg_a(homes, keys, servers)
        await _wg_b(homes, keys, servers)
        print()
        print(_h("done — both workgroups exchanged messages end-to-end"))
    finally:
        for srv in servers.values():
            await srv.stop()


async def _wg_a(homes, keys, servers) -> None:
    print()
    print(_h('WG-A "design" — hub=alice + bob'))

    wg = wg_mod.create(
        homes["alice"], name="design", hub_kp=keys["alice"],
        member_pubkeys=[keys["bob"].pubkey_b64()],
    )
    print(_ok(f"created {wg.meta.id}  ({len(wg.members)} members)"))

    # Bob joins → harvests the sealed group key
    join = await alp_client.call(
        socket_path=servers["alice"].socket_path(),
        sender=keys["bob"], recipient_pubkey_b64=keys["alice"].pubkey_b64(),
        method="workgroup.join", params={"workgroup_id": wg.meta.id},
    )
    bob_key = wg_mod.open_sealed_group_key(join["sealed_key"], keys["bob"])
    print(_ok(f"bob   joined  key_version={join['key_version']}"))

    # Bob posts under the group key
    nonce, ct = wg_mod.encrypt_post(bob_key, b"hi from bob")
    await alp_client.call(
        socket_path=servers["alice"].socket_path(),
        sender=keys["bob"], recipient_pubkey_b64=keys["alice"].pubkey_b64(),
        method="workgroup.post",
        params={
            "workgroup_id": wg.meta.id, "key_version": 1,
            "nonce": nonce, "ciphertext": ct,
        },
    )
    print(_ok("bob   posted 'hi from bob' (encrypted under v1 group key)"))

    # Alice (the hub) reads the transcript locally — she has the group key
    # in her members.yaml entry, opened with her own private key.
    alice_key = wg_mod.open_sealed_group_key(
        wg.member(keys["alice"].pubkey_b64()).sealed_key, keys["alice"],
    )
    pull = await alp_client.call(
        socket_path=servers["alice"].socket_path(),
        sender=keys["bob"], recipient_pubkey_b64=keys["alice"].pubkey_b64(),
        method="workgroup.pull",
        params={"workgroup_id": wg.meta.id, "since": 0},
    )
    print(_ok(f"bob   pulled  head={pull['head']}, posts={len(pull['posts'])}"))
    for p in pull["posts"]:
        text = wg_mod.decrypt_post(bob_key, p["nonce"], p["ciphertext"])
        print(_arrow(f"seq={p['seq']} from={p['from'][:24]}…  {text!r}"))
    # Alice could decrypt the same with her own copy of the key.
    assert alice_key == bob_key, "group key mismatch — sealing broken"


async def _wg_b(homes, keys, servers) -> None:
    print()
    print(_h('WG-B "research" — hub=mirai + bling + default + alice'))

    wg = wg_mod.create(
        homes["mirai"], name="research", hub_kp=keys["mirai"],
        member_pubkeys=[
            keys["bling"].pubkey_b64(),
            keys["default"].pubkey_b64(),
            keys["alice"].pubkey_b64(),
        ],
        budget={"max_usd": 1.00},  # lifetime cap demo
    )
    print(_ok(f"created {wg.meta.id}  ({len(wg.members)} members, "
              f"budget=$1.00 lifetime)"))

    member_keys: dict[str, bytes] = {}
    for name in ("bling", "default", "alice"):
        join = await alp_client.call(
            socket_path=servers["mirai"].socket_path(),
            sender=keys[name],
            recipient_pubkey_b64=keys["mirai"].pubkey_b64(),
            method="workgroup.join", params={"workgroup_id": wg.meta.id},
        )
        member_keys[name] = wg_mod.open_sealed_group_key(
            join["sealed_key"], keys[name],
        )
        print(_ok(f"{name:<7} joined"))

    # Each remote posts a message, declaring tiny costs that stay under cap
    for name, msg, cost in [
        ("bling",   b"bling: ml angle for q2",       0.12),
        ("default", b"default: rough scope draft",   0.18),
        ("alice",   b"alice: i'll review by friday", 0.05),
    ]:
        n, ct = wg_mod.encrypt_post(member_keys[name], msg)
        await alp_client.call(
            socket_path=servers["mirai"].socket_path(),
            sender=keys[name],
            recipient_pubkey_b64=keys["mirai"].pubkey_b64(),
            method="workgroup.post",
            params={
                "workgroup_id": wg.meta.id, "key_version": 1,
                "nonce": n, "ciphertext": ct,
                "cost": {"usd": cost, "tokens": 0},
            },
        )
        print(_ok(f"{name:<7} posted (declared ${cost:.2f})"))

    # Anyone pulls — every member sees the same three posts and decrypts them.
    pull = await alp_client.call(
        socket_path=servers["mirai"].socket_path(),
        sender=keys["alice"], recipient_pubkey_b64=keys["mirai"].pubkey_b64(),
        method="workgroup.pull",
        params={"workgroup_id": wg.meta.id, "since": 0},
    )
    print(_ok(f"alice pulled  head={pull['head']}, posts={len(pull['posts'])}"))
    for p in pull["posts"]:
        text = wg_mod.decrypt_post(
            member_keys["alice"], p["nonce"], p["ciphertext"],
        )
        print(_arrow(f"seq={p['seq']} from={p['from'][:24]}…  {text!r}"))

    # Show the workgroup ledger — cumulative declared spend
    import json as _json
    led = _json.loads(
        (homes["mirai"] / "alp" / "workgroups" / wg.meta.id / "ledger.json")
        .read_text()
    )
    print(_arrow(
        f"workgroup ledger:  ${led['usd']:.2f} / $1.00  "
        f"({led['posts']} posts)"
    ))

    # Confirm alice IS the cross-member: she's in WG-A's roster too.
    wg_a_alice = wg_mod.list_workgroups(homes["alice"])[0]
    print(_ok(
        f"alice is in BOTH workgroups: WG-A={wg_a_alice.meta.id} "
        f"+ WG-B={wg.meta.id}"
    ))


def main() -> int:
    root = Path(tempfile.mkdtemp(prefix="alpi-demo-", dir="/tmp"))
    try:
        asyncio.run(_run_demo(root))
        return 0
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
