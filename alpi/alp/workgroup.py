"""ALP.3 — workgroups (PR 1 + PR 2: hub state, 4 core verbs, leave +
rekey, lifetime budget).

A workgroup is a multi-party shared transcript anchored at a single
hub (the creator). Members post ciphertext under a shared group key;
the hub fans out the same ciphertext on `pull`. The hub holds sealed
copies of the group key — one per member, sealed under the member's
X25519 pubkey (derived from their Ed25519 ALP identity) — and never
sees post plaintext on disk.

Group keys are versioned: every successful `leave` (or hub-side
``kick``) generates a fresh key, re-sealed for each remaining member.
Members detect the new version on their next `pull` (the response
carries `current_key_version` and the member's current sealed key)
and update their local key map. Old keys stay valid for past
ciphertext — forward secrecy applies to **new** traffic only, by
design.

Budget is **lifetime, not daily** — the workgroup is project-scoped.
Either USD or tokens (pick one, mirroring the profile budget shape);
authors declare the cost of producing each post and the hub gates
cumulative spend against the cap. Hitting the cap freezes the
workgroup; bumping it requires editing ``meta.yaml`` (TUI in PR 4).

On-disk layout under ``~/.alpi/<profile>/alp/workgroups/<wg_id>/``:

    meta.yaml         # name, hub_pubkey, created_at, current_key_version, budget?
    members.yaml      # [{pubkey, sealed_key, key_version, joined, joined_at}]
    transcript.jsonl  # one ciphertext post per line, tagged with key_version + cost
    ledger.json       # {usd, tokens, posts} cumulative across the workgroup's life

Out of scope here: ``pause`` / ``resume`` (PR 3), TUI / CLI surface,
engine context integration (PR 4).
"""

from __future__ import annotations

import base64
import datetime as _dt
import json
import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey,
    X25519PublicKey,
)
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from alpi.alp import peers as peers_mod
from alpi.alp import server as alp_server
from alpi.alp.keys import Keypair, decode_pubkey
from alpi.alp.noise import (
    ed25519_to_x25519_private,
    ed25519_to_x25519_public,
)


_WG_DIR = "alp/workgroups"
_META = "meta.yaml"
_MEMBERS = "members.yaml"
_TRANSCRIPT = "transcript.jsonl"
_LEDGER = "ledger.json"

GROUP_KEY_BYTES = 32  # ChaCha20-Poly1305 key size
_HKDF_INFO = b"alp.workgroup.seal.v1"
_PROTOCOL_KIND_SEAL = b"seal"
_PROTOCOL_KIND_POST = b"post"


# Crypto helpers


def _hkdf(shared: bytes, salt: bytes) -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        info=_HKDF_INFO,
    ).derive(shared)


def seal_group_key(group_key: bytes, recipient_ed_pubkey_b64: str) -> str:
    """ECIES-style seal: ephemeral X25519 + HKDF-SHA256 + ChaCha20-Poly1305.

    Output is a single base64 string ``ephemeral_pub(32) || nonce(12) ||
    ciphertext+tag(GROUP_KEY_BYTES + 16)``. The recipient derives the
    same shared secret with their X25519 private key (converted from
    Ed25519 with the standard birational map, same as Noise) and opens
    the AEAD. Anyone without the recipient's static private key can't
    decrypt — that is the entire point.
    """
    if len(group_key) != GROUP_KEY_BYTES:
        raise ValueError(f"group_key must be {GROUP_KEY_BYTES} bytes")
    recipient_x = ed25519_to_x25519_public(decode_pubkey(recipient_ed_pubkey_b64))
    eph_priv = X25519PrivateKey.generate()
    eph_pub_raw = eph_priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    shared = eph_priv.exchange(recipient_x)
    salt = eph_pub_raw + recipient_x.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    key = _hkdf(shared, salt)
    nonce = os.urandom(12)
    ct = ChaCha20Poly1305(key).encrypt(nonce, group_key, _PROTOCOL_KIND_SEAL)
    return base64.b64encode(eph_pub_raw + nonce + ct).decode("ascii")


def open_sealed_group_key(sealed_b64: str, my_kp: Keypair) -> bytes:
    """Inverse of ``seal_group_key`` — returns the 32-byte group key."""
    blob = base64.b64decode(sealed_b64)
    if len(blob) < 32 + 12 + 16:
        raise ValueError("sealed blob too short")
    eph_pub_raw, rest = blob[:32], blob[32:]
    nonce, ct = rest[:12], rest[12:]
    eph_pub = X25519PublicKey.from_public_bytes(eph_pub_raw)
    my_x_priv = ed25519_to_x25519_private(my_kp.private)
    my_x_pub_raw = my_x_priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    shared = my_x_priv.exchange(eph_pub)
    salt = eph_pub_raw + my_x_pub_raw
    key = _hkdf(shared, salt)
    return ChaCha20Poly1305(key).decrypt(nonce, ct, _PROTOCOL_KIND_SEAL)


def encrypt_post(group_key: bytes, plaintext: bytes) -> tuple[str, str]:
    """ChaCha20-Poly1305 over the group key. Returns ``(nonce_b64,
    ciphertext_b64)``. Random 12-byte nonce per post — collision risk is
    2^-32 after ~2^48 posts in the same group, far beyond any realistic
    workgroup lifetime."""
    nonce = os.urandom(12)
    ct = ChaCha20Poly1305(group_key).encrypt(nonce, plaintext, _PROTOCOL_KIND_POST)
    return (
        base64.b64encode(nonce).decode("ascii"),
        base64.b64encode(ct).decode("ascii"),
    )


def decrypt_post(group_key: bytes, nonce_b64: str, ciphertext_b64: str) -> bytes:
    nonce = base64.b64decode(nonce_b64)
    ct = base64.b64decode(ciphertext_b64)
    return ChaCha20Poly1305(group_key).decrypt(nonce, ct, _PROTOCOL_KIND_POST)


# Storage


@dataclass
class Member:
    pubkey: str            # base64 Ed25519 — stable identity
    sealed_key: str        # base64 of seal_group_key output for this pubkey
    key_version: int = 1   # bumps every rekey; matches Meta.current_key_version
    joined: bool = False   # flips True on first successful workgroup.join
    joined_at: str = ""    # ISO-8601, set when ``joined`` flips


@dataclass
class Meta:
    id: str
    name: str
    hub_pubkey: str
    created_at: str
    current_key_version: int = 1
    # Optional lifetime budget. ``max_usd`` xor ``max_tokens`` (pick
    # one). Empty / missing = no workgroup-level cap (profile cap still
    # applies upstream).
    budget: dict[str, Any] = field(default_factory=dict)
    # Pause is a soft circuit-breaker on ``workgroup.post`` only —
    # ``pull`` / ``join`` / ``leave`` keep working so members can
    # catch up on past traffic and exit cleanly. Idempotent verbs.
    paused: bool = False
    paused_at: str = ""        # ISO-8601, set when paused flips True
    paused_by: str = ""        # Ed25519 pubkey of the member who paused


@dataclass
class Workgroup:
    meta: Meta
    members: list[Member] = field(default_factory=list)

    def member(self, pubkey: str) -> Member | None:
        for m in self.members:
            if m.pubkey == pubkey:
                return m
        return None


def _root(home: Path) -> Path:
    return home / _WG_DIR


def _wg_dir(home: Path, wg_id: str) -> Path:
    return _root(home) / wg_id


def _utcnow() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_id() -> str:
    return "wg_" + base64.b32encode(secrets.token_bytes(10)).decode("ascii").lower().rstrip("=")


def _load_meta(d: Path) -> Meta | None:
    p = d / _META
    if not p.exists():
        return None
    raw = yaml.safe_load(p.read_text()) or {}
    if not isinstance(raw, dict):
        return None
    try:
        return Meta(
            id=str(raw["id"]),
            name=str(raw["name"]),
            hub_pubkey=str(raw["hub_pubkey"]),
            created_at=str(raw["created_at"]),
            current_key_version=int(raw.get("current_key_version", 1)),
            budget=dict(raw.get("budget") or {}),
            paused=bool(raw.get("paused", False)),
            paused_at=str(raw.get("paused_at") or ""),
            paused_by=str(raw.get("paused_by") or ""),
        )
    except KeyError:
        return None


def _save_meta(d: Path, meta: Meta) -> None:
    d.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "id": meta.id,
        "name": meta.name,
        "hub_pubkey": meta.hub_pubkey,
        "created_at": meta.created_at,
        "current_key_version": meta.current_key_version,
    }
    if meta.budget:
        payload["budget"] = meta.budget
    if meta.paused:
        payload["paused"] = True
        if meta.paused_at:
            payload["paused_at"] = meta.paused_at
        if meta.paused_by:
            payload["paused_by"] = meta.paused_by
    (d / _META).write_text(yaml.safe_dump(payload, sort_keys=False))


def _load_members(d: Path) -> list[Member]:
    p = d / _MEMBERS
    if not p.exists():
        return []
    raw = yaml.safe_load(p.read_text()) or []
    if not isinstance(raw, list):
        return []
    out: list[Member] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        if "pubkey" not in entry or "sealed_key" not in entry:
            continue
        out.append(Member(
            pubkey=str(entry["pubkey"]),
            sealed_key=str(entry["sealed_key"]),
            key_version=int(entry.get("key_version", 1)),
            joined=bool(entry.get("joined", False)),
            joined_at=str(entry.get("joined_at") or ""),
        ))
    return out


def _save_members(d: Path, members: list[Member]) -> None:
    d.mkdir(parents=True, exist_ok=True)
    data = []
    for m in members:
        entry: dict[str, Any] = {
            "pubkey": m.pubkey,
            "sealed_key": m.sealed_key,
            "key_version": m.key_version,
        }
        if m.joined:
            entry["joined"] = True
            if m.joined_at:
                entry["joined_at"] = m.joined_at
        data.append(entry)
    (d / _MEMBERS).write_text(yaml.safe_dump(data, sort_keys=False))


def load(home: Path, wg_id: str) -> Workgroup | None:
    d = _wg_dir(home, wg_id)
    meta = _load_meta(d)
    if meta is None:
        return None
    return Workgroup(meta=meta, members=_load_members(d))


def list_workgroups(home: Path) -> list[Workgroup]:
    root = _root(home)
    if not root.exists():
        return []
    out: list[Workgroup] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        wg = load(home, child.name)
        if wg is not None:
            out.append(wg)
    return out


# Local primitive — create


def create(
    home: Path,
    *,
    name: str,
    hub_kp: Keypair,
    member_pubkeys: list[str],
    budget: dict[str, Any] | None = None,
) -> Workgroup:
    """Create a workgroup on this profile (we are the hub).

    ``member_pubkeys`` is the initial roster — base64 Ed25519 pubkeys
    of every alpi we want to invite. The hub's own pubkey is added
    automatically; passing it again is a no-op. The group key is
    generated fresh, sealed once per member, and persisted alongside
    the empty transcript.

    ``budget`` is an optional ``{"max_usd": float}`` xor
    ``{"max_tokens": int}``. Leave unset for no workgroup-level cap.

    Returns the created ``Workgroup``. Raises ``ValueError`` on bad
    inputs (empty name, malformed pubkey, ill-formed budget).
    """
    name = (name or "").strip()
    if not name:
        raise ValueError("workgroup name required")
    budget = _validate_budget(budget or {})

    hub_pk = hub_kp.pubkey_b64()
    roster = [hub_pk]
    seen = {hub_pk}
    for pk in member_pubkeys:
        pk = (pk or "").strip()
        if not pk or pk in seen:
            continue
        try:
            decode_pubkey(pk)
        except Exception as e:  # noqa: BLE001
            raise ValueError(f"invalid pubkey: {pk!r}") from e
        seen.add(pk)
        roster.append(pk)

    group_key = secrets.token_bytes(GROUP_KEY_BYTES)

    wg_id = _new_id()
    d = _wg_dir(home, wg_id)
    d.mkdir(parents=True, exist_ok=True)

    meta = Meta(
        id=wg_id,
        name=name,
        hub_pubkey=hub_pk,
        created_at=_utcnow(),
        current_key_version=1,
        budget=budget,
    )
    _save_meta(d, meta)

    now = _utcnow()
    members: list[Member] = []
    for pk in roster:
        sealed = seal_group_key(group_key, pk)
        m = Member(pubkey=pk, sealed_key=sealed, key_version=1)
        if pk == hub_pk:
            m.joined = True
            m.joined_at = now
        members.append(m)
    _save_members(d, members)

    # Empty transcript so ``pull`` works on a brand-new workgroup
    # without an existence check.
    (d / _TRANSCRIPT).touch()
    (d / _LEDGER).write_text(json.dumps(
        {"usd": 0.0, "tokens": 0, "posts": 0}, separators=(",", ":"),
    ))

    return Workgroup(meta=meta, members=members)


# Rekey + remove (used by leave + kick)


def _rekey(home: Path, wg_id: str, dropped_pubkey: str) -> Workgroup:
    """Drop ``dropped_pubkey`` from the roster, mint a fresh group key,
    seal it for every remaining member, bump versions and persist.
    Returns the updated Workgroup. Raises ``ValueError`` if the dropped
    pubkey is the hub's (the hub cannot leave its own workgroup; spec
    is hub-anchored, no failover) or if the workgroup is unknown."""
    wg = load(home, wg_id)
    if wg is None:
        raise ValueError(f"workgroup {wg_id!r} not found")
    if dropped_pubkey == wg.meta.hub_pubkey:
        raise ValueError("hub cannot leave its own workgroup")
    if wg.member(dropped_pubkey) is None:
        raise ValueError(f"pubkey {dropped_pubkey!r} not in roster")

    remaining = [m for m in wg.members if m.pubkey != dropped_pubkey]
    new_key = secrets.token_bytes(GROUP_KEY_BYTES)
    new_version = wg.meta.current_key_version + 1
    for m in remaining:
        m.sealed_key = seal_group_key(new_key, m.pubkey)
        m.key_version = new_version

    wg.members = remaining
    wg.meta.current_key_version = new_version

    d = _wg_dir(home, wg_id)
    _save_meta(d, wg.meta)
    _save_members(d, wg.members)
    return wg


def kick(home: Path, wg_id: str, target_pubkey: str) -> Workgroup:
    """Hub-side primitive — remove ``target_pubkey`` from the workgroup
    and rotate the group key. Equivalent to the target calling
    ``workgroup.leave`` themselves, but initiated locally. Raises
    ``ValueError`` if the target is the hub or not in the roster."""
    return _rekey(home, wg_id, target_pubkey)


# Transcript


def _read_transcript(d: Path) -> list[dict[str, Any]]:
    p = d / _TRANSCRIPT
    if not p.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(entry, dict):
            out.append(entry)
    return out


def _append_transcript(d: Path, entry: dict[str, Any]) -> None:
    p = d / _TRANSCRIPT
    p.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(entry, separators=(",", ":"), ensure_ascii=False)
    with p.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


# Ledger — workgroup lifetime spend


def _load_ledger(d: Path) -> dict[str, Any]:
    p = d / _LEDGER
    if not p.exists():
        return {"usd": 0.0, "tokens": 0, "posts": 0}
    try:
        raw = json.loads(p.read_text())
    except json.JSONDecodeError:
        return {"usd": 0.0, "tokens": 0, "posts": 0}
    return {
        "usd": float(raw.get("usd", 0.0)),
        "tokens": int(raw.get("tokens", 0)),
        "posts": int(raw.get("posts", 0)),
    }


def _save_ledger(d: Path, ledger: dict[str, Any]) -> None:
    d.mkdir(parents=True, exist_ok=True)
    (d / _LEDGER).write_text(json.dumps(
        {
            "usd": float(ledger.get("usd", 0.0)),
            "tokens": int(ledger.get("tokens", 0)),
            "posts": int(ledger.get("posts", 0)),
        },
        separators=(",", ":"),
    ))


def _validate_budget(budget: dict[str, Any]) -> dict[str, Any]:
    """Normalise + sanity-check the workgroup budget shape, mirroring
    the profile-budget UX (``daily_usd`` / ``daily_tokens`` — both
    optional, set what you care about). Empty dict = no cap.
    Non-positive values raise ``ValueError`` so a typo fails fast.
    When both are set, both gate independently — whichever trips
    first wins."""
    if not budget:
        return {}
    usd = budget.get("max_usd")
    tokens = budget.get("max_tokens")
    if usd is None and tokens is None:
        raise ValueError("budget must set max_usd or max_tokens")
    out: dict[str, Any] = {}
    if usd is not None:
        usd_f = float(usd)
        if usd_f <= 0:
            raise ValueError("max_usd must be > 0")
        out["max_usd"] = usd_f
    if tokens is not None:
        tokens_i = int(tokens)
        if tokens_i <= 0:
            raise ValueError("max_tokens must be > 0")
        out["max_tokens"] = tokens_i
    return out


def _gate_post(meta: Meta, ledger: dict[str, Any], cost: dict[str, Any]) -> None:
    """Workgroup budget check: would admitting this post breach the
    lifetime cap? Reuses error code ``-32005 budget-exceeded`` with
    ``data.cap_kind`` set to ``workgroup_usd`` / ``workgroup_tokens`` so
    callers can tell it apart from the profile-level cap."""
    if not meta.budget:
        return
    usd_cap = meta.budget.get("max_usd")
    tokens_cap = meta.budget.get("max_tokens")
    declared_usd = float(cost.get("usd", 0.0)) if cost else 0.0
    declared_tokens = int(cost.get("tokens", 0)) if cost else 0
    if usd_cap is not None:
        used = float(ledger.get("usd", 0.0))
        if used >= usd_cap or used + declared_usd > usd_cap:
            raise alp_server.HandlerError(
                -32005, "budget-exceeded",
                data={
                    "cap_kind": "workgroup_usd",
                    "cap": usd_cap,
                    "used": used,
                    "declared": declared_usd,
                },
            )
    if tokens_cap is not None:
        used_t = int(ledger.get("tokens", 0))
        if used_t >= tokens_cap or used_t + declared_tokens > tokens_cap:
            raise alp_server.HandlerError(
                -32005, "budget-exceeded",
                data={
                    "cap_kind": "workgroup_tokens",
                    "cap": tokens_cap,
                    "used": used_t,
                    "declared": declared_tokens,
                },
            )


# Server-side handlers — registered against ``alpi.alp.server.Server``


def register(server: alp_server.Server, home: Path) -> None:
    """Register ``workgroup.join``, ``workgroup.post``, ``workgroup.pull``,
    ``workgroup.leave``.

    Capability is enforced upstream by ``peer.may_call``; the handlers
    additionally check workgroup membership so a peer with the verb
    allowed but not in this specific workgroup gets ``-32008
    workgroup-not-member`` rather than silent success.
    """

    async def workgroup_join(
        params: dict[str, Any],
        peer: peers_mod.Peer,
        srv: alp_server.Server,
    ) -> dict[str, Any]:
        wg_id = str((params or {}).get("workgroup_id") or "").strip()
        if not wg_id:
            raise alp_server.HandlerError(
                -32602, "invalid-params",
                data={"detail": "workgroup_id required"},
            )
        wg = load(home, wg_id)
        if wg is None:
            raise alp_server.HandlerError(-32009, "workgroup-not-found")
        member = wg.member(peer.pubkey)
        if member is None:
            raise alp_server.HandlerError(-32008, "workgroup-not-member")
        if not member.joined:
            member.joined = True
            member.joined_at = _utcnow()
            _save_members(_wg_dir(home, wg_id), wg.members)
        return {
            "workgroup_id": wg.meta.id,
            "name": wg.meta.name,
            "sealed_key": member.sealed_key,
            "key_version": member.key_version,
            "current_key_version": wg.meta.current_key_version,
            "members": [m.pubkey for m in wg.members],
        }

    async def workgroup_post(
        params: dict[str, Any],
        peer: peers_mod.Peer,
        srv: alp_server.Server,
    ) -> dict[str, Any]:
        wg_id = str((params or {}).get("workgroup_id") or "").strip()
        nonce = str((params or {}).get("nonce") or "")
        ciphertext = str((params or {}).get("ciphertext") or "")
        if not (wg_id and nonce and ciphertext):
            raise alp_server.HandlerError(
                -32602, "invalid-params",
                data={"detail": "workgroup_id, nonce, ciphertext required"},
            )
        try:
            key_version = int((params or {}).get("key_version", 1))
        except (TypeError, ValueError):
            key_version = 1
        cost = (params or {}).get("cost") or {}
        if not isinstance(cost, dict):
            cost = {}

        wg = load(home, wg_id)
        if wg is None:
            raise alp_server.HandlerError(-32009, "workgroup-not-found")
        if wg.member(peer.pubkey) is None:
            raise alp_server.HandlerError(-32008, "workgroup-not-member")
        if wg.meta.paused:
            raise alp_server.HandlerError(
                -32010, "workgroup-paused",
                data={
                    "paused_at": wg.meta.paused_at,
                    "paused_by": wg.meta.paused_by,
                },
            )

        d = _wg_dir(home, wg_id)
        ledger = _load_ledger(d)
        _gate_post(wg.meta, ledger, cost)  # raises -32005 on breach

        existing = _read_transcript(d)
        seq = (existing[-1]["seq"] + 1) if existing else 1
        entry: dict[str, Any] = {
            "seq": seq,
            "ts": _utcnow(),
            "from": peer.pubkey,
            "key_version": key_version,
            "nonce": nonce,
            "ciphertext": ciphertext,
        }
        declared_usd = float(cost.get("usd", 0.0)) if cost else 0.0
        declared_tokens = int(cost.get("tokens", 0)) if cost else 0
        if declared_usd or declared_tokens:
            entry["cost"] = {"usd": declared_usd, "tokens": declared_tokens}
        _append_transcript(d, entry)

        ledger["usd"] = float(ledger.get("usd", 0.0)) + declared_usd
        ledger["tokens"] = int(ledger.get("tokens", 0)) + declared_tokens
        ledger["posts"] = int(ledger.get("posts", 0)) + 1
        _save_ledger(d, ledger)

        return {"seq": seq, "ts": entry["ts"]}

    async def workgroup_pull(
        params: dict[str, Any],
        peer: peers_mod.Peer,
        srv: alp_server.Server,
    ) -> dict[str, Any]:
        wg_id = str((params or {}).get("workgroup_id") or "").strip()
        since_raw = (params or {}).get("since", 0)
        try:
            since = int(since_raw)
        except (TypeError, ValueError):
            since = 0
        if not wg_id:
            raise alp_server.HandlerError(
                -32602, "invalid-params",
                data={"detail": "workgroup_id required"},
            )
        wg = load(home, wg_id)
        if wg is None:
            raise alp_server.HandlerError(-32009, "workgroup-not-found")
        member = wg.member(peer.pubkey)
        if member is None:
            raise alp_server.HandlerError(-32008, "workgroup-not-member")
        all_posts = _read_transcript(_wg_dir(home, wg_id))
        fresh = [p for p in all_posts if int(p.get("seq", 0)) > since]
        return {
            "posts": fresh,
            "head": all_posts[-1]["seq"] if all_posts else 0,
            # Always echo the caller's current sealed key + version so
            # rekey detection is implicit in pull. Members compare
            # ``current_key_version`` against the highest version they
            # already hold; if behind, they ``open_sealed_group_key``
            # the returned blob and store the new group_key under that
            # version in their local map.
            "current_key_version": wg.meta.current_key_version,
            "sealed_key": member.sealed_key,
        }

    async def workgroup_leave(
        params: dict[str, Any],
        peer: peers_mod.Peer,
        srv: alp_server.Server,
    ) -> dict[str, Any]:
        wg_id = str((params or {}).get("workgroup_id") or "").strip()
        if not wg_id:
            raise alp_server.HandlerError(
                -32602, "invalid-params",
                data={"detail": "workgroup_id required"},
            )
        wg = load(home, wg_id)
        if wg is None:
            raise alp_server.HandlerError(-32009, "workgroup-not-found")
        if wg.member(peer.pubkey) is None:
            raise alp_server.HandlerError(-32008, "workgroup-not-member")
        if peer.pubkey == wg.meta.hub_pubkey:
            raise alp_server.HandlerError(
                -32602, "invalid-params",
                data={"detail": "hub cannot leave its own workgroup"},
            )
        updated = _rekey(home, wg_id, peer.pubkey)
        return {
            "workgroup_id": updated.meta.id,
            "current_key_version": updated.meta.current_key_version,
            "remaining_members": [m.pubkey for m in updated.members],
        }

    async def workgroup_pause(
        params: dict[str, Any],
        peer: peers_mod.Peer,
        srv: alp_server.Server,
    ) -> dict[str, Any]:
        wg_id = str((params or {}).get("workgroup_id") or "").strip()
        if not wg_id:
            raise alp_server.HandlerError(
                -32602, "invalid-params",
                data={"detail": "workgroup_id required"},
            )
        wg = load(home, wg_id)
        if wg is None:
            raise alp_server.HandlerError(-32009, "workgroup-not-found")
        if wg.member(peer.pubkey) is None:
            raise alp_server.HandlerError(-32008, "workgroup-not-member")
        # Idempotent — already paused returns the existing state.
        if not wg.meta.paused:
            wg.meta.paused = True
            wg.meta.paused_at = _utcnow()
            wg.meta.paused_by = peer.pubkey
            _save_meta(_wg_dir(home, wg_id), wg.meta)
        return {
            "workgroup_id": wg.meta.id,
            "paused": True,
            "paused_at": wg.meta.paused_at,
            "paused_by": wg.meta.paused_by,
        }

    async def workgroup_resume(
        params: dict[str, Any],
        peer: peers_mod.Peer,
        srv: alp_server.Server,
    ) -> dict[str, Any]:
        wg_id = str((params or {}).get("workgroup_id") or "").strip()
        if not wg_id:
            raise alp_server.HandlerError(
                -32602, "invalid-params",
                data={"detail": "workgroup_id required"},
            )
        wg = load(home, wg_id)
        if wg is None:
            raise alp_server.HandlerError(-32009, "workgroup-not-found")
        if wg.member(peer.pubkey) is None:
            raise alp_server.HandlerError(-32008, "workgroup-not-member")
        # Idempotent — already running returns the cleared state.
        if wg.meta.paused:
            wg.meta.paused = False
            wg.meta.paused_at = ""
            wg.meta.paused_by = ""
            _save_meta(_wg_dir(home, wg_id), wg.meta)
        return {"workgroup_id": wg.meta.id, "paused": False}

    server.register("workgroup.join", workgroup_join)
    server.register("workgroup.post", workgroup_post)
    server.register("workgroup.pull", workgroup_pull)
    server.register("workgroup.leave", workgroup_leave)
    server.register("workgroup.pause", workgroup_pause)
    server.register("workgroup.resume", workgroup_resume)
