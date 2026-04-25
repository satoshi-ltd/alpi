"""Member-side workgroup helpers — the verbs a remote member calls
against the hub. Wraps :mod:`alpi.alp.client` with workgroup-specific
state management (subscription cache, sealed-key tracking, pull
cursor advancement).

Hub-side primitives (``create``, ``kick``, listing locally-hosted
workgroups, reading their transcripts) live in :mod:`alpi.alp.workgroup`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from alpi.alp import client as alp_client
from alpi.alp import peers as peers_mod
from alpi.alp import subscription as sub_mod
from alpi.alp import workgroup as wg_mod
from alpi.alp.keys import Keypair, load_or_generate


@dataclass
class _Resolved:
    socket_path: Path | None
    host: str | None
    port: int | None
    hub_pubkey: str

    def is_tcp(self) -> bool:
        return self.host is not None and self.port is not None


def _resolve_hub(home: Path, peer_id: str) -> _Resolved:
    """Locate the hub of a workgroup via this profile's ``peers.yaml``.
    Returns the right transport for ``alpi.alp.client.call_*``."""
    peer = peers_mod.get_by_id(home, peer_id)
    if peer is None:
        raise ValueError(f"peer {peer_id!r} not pinned in this profile's peers.yaml")
    if peer.address:
        host, _, port_s = peer.address.rpartition(":")
        if not host or not port_s.isdigit():
            raise ValueError(f"peer {peer_id!r} has invalid address {peer.address!r}")
        return _Resolved(
            socket_path=None, host=host, port=int(port_s), hub_pubkey=peer.pubkey,
        )
    socket_path = _intra_socket_path(peer_id)
    return _Resolved(
        socket_path=socket_path, host=None, port=None, hub_pubkey=peer.pubkey,
    )


def _intra_socket_path(peer_id: str) -> Path:
    """Convention for intra-machine peers — same root as ``alp/setup.py``."""
    if peer_id == "default":
        return Path.home() / ".alpi" / "alp" / "alp.sock"
    return Path.home() / ".alpi" / "profiles" / peer_id / "alp" / "alp.sock"


async def _call(home: Path, kp: Keypair, peer_id: str, method: str,
                params: dict[str, Any]) -> dict[str, Any]:
    res = _resolve_hub(home, peer_id)
    if res.is_tcp():
        return await alp_client.call_tcp(
            host=res.host, port=res.port,
            sender=kp, recipient_pubkey_b64=res.hub_pubkey,
            method=method, params=params,
        )
    return await alp_client.call(
        socket_path=res.socket_path,
        sender=kp, recipient_pubkey_b64=res.hub_pubkey,
        method=method, params=params,
    )


# Public verbs


async def join(home: Path, peer_id: str, wg_id: str) -> sub_mod.Subscription:
    """Send ``workgroup.join`` to the hub identified by ``peer_id`` and
    persist a subscription locally. Idempotent: re-joining refreshes
    the sealed key in case the hub rotated it while we were away.

    Hub identity is explicit by design — we don't probe pinned peers
    for which one hosts this workgroup. Probing would leak the
    ``wg_id`` to every pinned peer (metadata leak) and would let a
    malicious pinned peer that pre-created a same-id workgroup
    impersonate the real hub. Trust must be declared, not inferred.
    """
    kp = load_or_generate(home)
    result = await _call(home, kp, peer_id, "workgroup.join",
                         {"workgroup_id": wg_id})
    res = _resolve_hub(home, peer_id)
    sub = sub_mod.get(home, wg_id) or sub_mod.Subscription(
        wg_id=wg_id,
        name=str(result.get("name") or ""),
        hub_id=peer_id,
        hub_pubkey=res.hub_pubkey,
    )
    if not sub.joined_at:
        import datetime as _dt
        sub.joined_at = _dt.datetime.now(tz=_dt.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ",
        )
    if not sub.name:
        sub.name = str(result.get("name") or "")
    # Briefing is plaintext metadata on the hub — refresh on every
    # successful join so the member's agent sees the same anchor the
    # hub publishes.
    sub.briefing = str(result.get("briefing") or "")
    sub.upsert_key(int(result.get("key_version", 1)), str(result["sealed_key"]))
    _absorb_roster(sub, result.get("members"))
    sub_mod.upsert(home, sub)
    return sub


def _absorb_roster(sub: sub_mod.Subscription, raw) -> None:
    """Hub returns ``members`` as a list of either bare pubkey strings
    (legacy shape from PR 1-4) or ``{pubkey, last_seen_at}`` dicts
    (PR 5+). Normalise both into ``sub.roster: {pubkey: last_seen_at}``
    so the engine context block always has a stable map."""
    if not raw:
        return
    out: dict[str, str] = {}
    for entry in raw:
        if isinstance(entry, dict) and "pubkey" in entry:
            out[str(entry["pubkey"])] = str(entry.get("last_seen_at") or "")
        elif isinstance(entry, str):
            out[entry] = ""
    if out:
        sub.roster = out


async def post(
    home: Path, wg_id: str, text: bytes,
    cost: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Encrypt ``text`` under the latest known group key and send to
    the hub. ``cost`` is the optional ``{usd, tokens}`` declaration
    used for the workgroup's lifetime budget gate.

    Works for both roles: if this profile is a remote member it
    encrypts and dials the hub via ALP; if this profile is the hub
    of the workgroup, it writes directly to its own transcript +
    ledger (no network roundtrip)."""
    kp = load_or_generate(home)

    # Hub path — short-circuits the network. Hub holds the canonical
    # transcript, so posting locally is correct and avoids the loopback
    # over our own ALP socket.
    wg = wg_mod.load(home, wg_id)
    if wg is not None and wg.meta.hub_pubkey == kp.pubkey_b64():
        return _post_as_hub(home, wg, kp, text, cost)

    sub = sub_mod.get(home, wg_id)
    if sub is None:
        raise ValueError(
            f"not subscribed to {wg_id!r} — run `alpi workgroup join` first",
        )
    version = sub.latest_version()
    if version == 0:
        raise ValueError(f"no group key cached for {wg_id!r}; re-join")
    sealed = sub.sealed_for(version)
    group_key = wg_mod.open_sealed_group_key(sealed, kp)
    nonce, ct = wg_mod.encrypt_post(group_key, text)
    params: dict[str, Any] = {
        "workgroup_id": wg_id,
        "key_version": version,
        "nonce": nonce,
        "ciphertext": ct,
    }
    if cost:
        params["cost"] = cost
    return await _call(home, kp, sub.hub_id, "workgroup.post", params)


def _post_as_hub(
    home: Path, wg, kp: Keypair, text: bytes,
    cost: dict[str, Any] | None,
) -> dict[str, Any]:
    """Write a post directly into the local transcript when this
    profile is the hub. Mirrors what the ``workgroup.post`` server
    handler would do over the wire — same budget gate, same ledger
    update, same paused / membership checks. Returns the same shape
    (``{seq, ts}``) the wire path produces."""
    import datetime as _dt
    import json
    from alpi.alp.workgroup import (
        _append_transcript, _gate_post, _load_ledger, _save_ledger,
        _read_transcript, _wg_dir,
    )

    own = wg.member(kp.pubkey_b64())
    if own is None:
        raise ValueError("hub is not a member of its own workgroup")
    if wg.meta.paused:
        raise ValueError("workgroup is paused")

    cost_dict = dict(cost) if cost else {}
    d = _wg_dir(home, wg.meta.id)
    ledger = _load_ledger(d)

    # _gate_post raises HandlerError on breach, which carries an
    # alpi.alp.server.RemoteError-shaped code. Translate to ValueError
    # here so the calling tool surfaces a clean error string.
    try:
        _gate_post(wg.meta, ledger, cost_dict)
    except Exception as e:  # noqa: BLE001
        raise ValueError(str(e)) from e

    group_key = wg_mod.open_sealed_group_key(own.sealed_key, kp)
    nonce, ct = wg_mod.encrypt_post(group_key, text)

    existing = _read_transcript(d)
    seq = (existing[-1]["seq"] + 1) if existing else 1
    ts = _dt.datetime.now(tz=_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    entry: dict[str, Any] = {
        "seq": seq, "ts": ts, "from": kp.pubkey_b64(),
        "key_version": own.key_version, "nonce": nonce, "ciphertext": ct,
    }
    declared_usd = float(cost_dict.get("usd", 0.0)) if cost_dict else 0.0
    declared_tokens = int(cost_dict.get("tokens", 0)) if cost_dict else 0
    if declared_usd or declared_tokens:
        entry["cost"] = {"usd": declared_usd, "tokens": declared_tokens}
    _append_transcript(d, entry)

    ledger["usd"] = float(ledger.get("usd", 0.0)) + declared_usd
    ledger["tokens"] = int(ledger.get("tokens", 0)) + declared_tokens
    ledger["posts"] = int(ledger.get("posts", 0)) + 1
    _save_ledger(d, ledger)
    return {"seq": seq, "ts": ts}


async def pull(
    home: Path, wg_id: str, *, since: int | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Fetch new posts and decrypt them. Returns ``(decrypted_posts,
    head)`` where each decrypted post carries the original metadata
    plus ``text`` (str). Updates the subscription cursor and any
    sealed-key rotation the hub signalled."""
    kp = load_or_generate(home)
    sub = sub_mod.get(home, wg_id)
    if sub is None:
        raise ValueError(
            f"not subscribed to {wg_id!r} — run `alpi workgroup join` first",
        )
    cursor = sub.last_seq if since is None else int(since)
    raw = await _call(home, kp, sub.hub_id, "workgroup.pull",
                      {"workgroup_id": wg_id, "since": cursor})

    # Hub may have rotated — refresh our sealed key + version cache.
    server_version = int(raw.get("current_key_version", 1))
    new_sealed = str(raw.get("sealed_key") or "")
    if new_sealed and sub.sealed_for(server_version) != new_sealed:
        sub.upsert_key(server_version, new_sealed)

    decrypted: list[dict[str, Any]] = []
    for p in raw.get("posts") or []:
        try:
            text = sub_mod.decrypt_post(sub, kp, p).decode("utf-8", errors="replace")
        except Exception as e:  # noqa: BLE001
            text = f"[decrypt failed: {e}]"
        decrypted.append({**p, "text": text})

    head = int(raw.get("head", cursor))
    if head > sub.last_seq:
        sub.last_seq = head
    # Cache the freshly-decrypted posts so the engine pre-turn hook can
    # build the system-prompt block without an extra network roundtrip.
    sub.append_recent(decrypted)
    # Refresh the liveness roster from the hub's response (hub stamps
    # last_seen_at on every member's pull / post).
    _absorb_roster(sub, raw.get("members"))
    sub_mod.upsert(home, sub)
    return decrypted, head


async def leave(home: Path, wg_id: str) -> dict[str, Any]:
    kp = load_or_generate(home)
    sub = sub_mod.get(home, wg_id)
    if sub is None:
        raise ValueError(f"not subscribed to {wg_id!r}")
    result = await _call(home, kp, sub.hub_id, "workgroup.leave",
                         {"workgroup_id": wg_id})
    sub_mod.remove(home, wg_id)
    return result


async def pause(home: Path, wg_id: str) -> dict[str, Any]:
    kp = load_or_generate(home)
    sub = sub_mod.get(home, wg_id)
    if sub is None:
        raise ValueError(f"not subscribed to {wg_id!r}")
    return await _call(home, kp, sub.hub_id, "workgroup.pause",
                       {"workgroup_id": wg_id})


async def resume(home: Path, wg_id: str) -> dict[str, Any]:
    kp = load_or_generate(home)
    sub = sub_mod.get(home, wg_id)
    if sub is None:
        raise ValueError(f"not subscribed to {wg_id!r}")
    return await _call(home, kp, sub.hub_id, "workgroup.resume",
                       {"workgroup_id": wg_id})
