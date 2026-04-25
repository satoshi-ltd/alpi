"""ALP.3 — workgroups (PR 1: hub state + 4 core verbs).

A workgroup is a multi-party shared transcript anchored at a single
hub (the creator). Members post ciphertext under a shared group key;
the hub fans out the same ciphertext on `pull`. The hub holds sealed
copies of the group key — one per member, sealed under the member's
X25519 pubkey (derived from their Ed25519 ALP identity) — and never
sees post plaintext on disk. Layout::

    ~/.alpi/<profile>/alp/workgroups/<wg_id>/
        meta.yaml         # name, hub_pubkey, created_at
        members.yaml      # [{pubkey, sealed_key, joined, joined_at}]
        transcript.jsonl  # one ciphertext post per line

This module exposes both the local primitive (``create``, used by
the future TUI/CLI to start a workgroup on this profile) and the
over-the-wire handlers (``workgroup.join``, ``workgroup.post``,
``workgroup.pull``) registered against the ALP server.

Out of scope for PR 1: ``leave`` + group-key rotation, ``pause`` /
``resume``, budget double-gate, TUI surface. Tracked in ROADMAP §
ALP.3.
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
    joined: bool = False   # flips True on first successful workgroup.join
    joined_at: str = ""    # ISO-8601, set when ``joined`` flips


@dataclass
class Meta:
    id: str
    name: str
    hub_pubkey: str
    created_at: str


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
        )
    except KeyError:
        return None


def _save_meta(d: Path, meta: Meta) -> None:
    d.mkdir(parents=True, exist_ok=True)
    (d / _META).write_text(yaml.safe_dump(
        {
            "id": meta.id,
            "name": meta.name,
            "hub_pubkey": meta.hub_pubkey,
            "created_at": meta.created_at,
        },
        sort_keys=False,
    ))


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
            joined=bool(entry.get("joined", False)),
            joined_at=str(entry.get("joined_at") or ""),
        ))
    return out


def _save_members(d: Path, members: list[Member]) -> None:
    d.mkdir(parents=True, exist_ok=True)
    data = []
    for m in members:
        entry: dict[str, Any] = {"pubkey": m.pubkey, "sealed_key": m.sealed_key}
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
) -> Workgroup:
    """Create a workgroup on this profile (we are the hub).

    ``member_pubkeys`` is the initial roster — base64 Ed25519 pubkeys
    of every alpi we want to invite. The hub's own pubkey is added
    automatically; passing it again is a no-op. The group key is
    generated fresh, sealed once per member, and persisted alongside
    the empty transcript.

    Returns the created ``Workgroup``. Raises ``ValueError`` on bad
    inputs (empty name, duplicate or malformed pubkey).
    """
    name = (name or "").strip()
    if not name:
        raise ValueError("workgroup name required")

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
    )
    _save_meta(d, meta)

    now = _utcnow()
    members: list[Member] = []
    for pk in roster:
        sealed = seal_group_key(group_key, pk)
        m = Member(pubkey=pk, sealed_key=sealed)
        if pk == hub_pk:
            m.joined = True
            m.joined_at = now
        members.append(m)
    _save_members(d, members)

    # Empty transcript file so ``pull`` works on a brand-new workgroup
    # without an existence check.
    (d / _TRANSCRIPT).touch()

    return Workgroup(meta=meta, members=members)


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


# Server-side handlers — registered against ``alpi.alp.server.Server``


def register(server: alp_server.Server, home: Path) -> None:
    """Register ``workgroup.join``, ``workgroup.post``, ``workgroup.pull``.

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
        wg = load(home, wg_id)
        if wg is None:
            raise alp_server.HandlerError(-32009, "workgroup-not-found")
        if wg.member(peer.pubkey) is None:
            raise alp_server.HandlerError(-32008, "workgroup-not-member")
        d = _wg_dir(home, wg_id)
        existing = _read_transcript(d)
        seq = (existing[-1]["seq"] + 1) if existing else 1
        entry = {
            "seq": seq,
            "ts": _utcnow(),
            "from": peer.pubkey,
            "nonce": nonce,
            "ciphertext": ciphertext,
        }
        _append_transcript(d, entry)
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
        if wg.member(peer.pubkey) is None:
            raise alp_server.HandlerError(-32008, "workgroup-not-member")
        all_posts = _read_transcript(_wg_dir(home, wg_id))
        fresh = [p for p in all_posts if int(p.get("seq", 0)) > since]
        return {"posts": fresh, "head": all_posts[-1]["seq"] if all_posts else 0}

    server.register("workgroup.join", workgroup_join)
    server.register("workgroup.post", workgroup_post)
    server.register("workgroup.pull", workgroup_pull)
