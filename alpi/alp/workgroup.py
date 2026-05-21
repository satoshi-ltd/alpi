"""ALP.3 workgroups — multi-party shared transcript anchored at a single hub.

Members post ciphertext under a shared group key; the hub fans out the same
ciphertext on `pull`. The hub holds sealed copies of the group key (one per
member, sealed under the member's X25519 pubkey derived from their Ed25519
ALP identity) and never sees post plaintext on disk.

Group keys are versioned: every successful `leave` / hub-side `kick`
generates a fresh key, re-sealed for each remaining member. Members detect
the new version on their next `pull` and update their local key map. Old
keys stay valid for past ciphertext — forward secrecy applies to **new**
traffic only, by design.

Budget is **lifetime, not daily** — the workgroup is project-scoped. USD
xor tokens. Authors declare per-post cost; the hub gates cumulative spend
against the cap. Hitting the cap freezes the workgroup.

On-disk layout under ``~/.alpi/<profile>/alp/workgroups/<wg_id>/``:

    meta.yaml         # name, hub_pubkey, created_at, current_key_version, budget?
    members.yaml      # [{pubkey, sealed_key, key_version, joined, joined_at}]
    transcript.jsonl  # one ciphertext post per line, tagged with key_version + cost
    ledger.json       # {usd, tokens, posts} cumulative across the workgroup's life
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

_BIO_MAX = 200
_VOICE_MAX = 64

GROUP_KEY_BYTES = 32
_HKDF_INFO = b"alp.workgroup.seal.v1"
_PROTOCOL_KIND_SEAL = b"seal"
_PROTOCOL_KIND_POST = b"post"


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
    ciphertext+tag(GROUP_KEY_BYTES + 16)``. The recipient derives the same
    shared secret with their X25519 private key (converted from Ed25519 via
    the standard birational map, same as Noise) and opens the AEAD."""
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
    """ChaCha20-Poly1305 over the group key. Returns ``(nonce_b64, ciphertext_b64)``.

    Random 12-byte nonce per post — collision risk is 2^-32 after ~2^48
    posts in the same group, far beyond any realistic workgroup lifetime."""
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


@dataclass
class Member:
    pubkey: str            # base64 Ed25519 — stable identity
    sealed_key: str        # base64 of seal_group_key output for this pubkey
    key_version: int = 1   # matches Meta.current_key_version at seal time
    joined: bool = False   # flips True on first successful workgroup.join
    joined_at: str = ""
    # Passive liveness signal — hub stamps this on every pull/post from the member, so the roster carries an implicit "online" indicator without probe traffic.
    last_seen_at: str = ""
    # Self-published one-liner; member supplies on ``workgroup.join``. Source of truth is the joiner's ``public_bio`` config; AGENT.md stays private.
    bio: str = ""
    voice: str = ""


@dataclass
class Meta:
    id: str
    name: str
    hub_pubkey: str
    created_at: str
    current_key_version: int = 1
    # ``max_usd`` xor ``max_tokens`` (pick one). Empty/missing = no workgroup-level cap; profile cap still applies upstream.
    budget: dict[str, Any] = field(default_factory=dict)
    # Soft circuit-breaker on ``workgroup.post`` only — ``pull``/``join``/``leave`` keep working so members can catch up and exit cleanly.
    paused: bool = False
    paused_at: str = ""
    paused_by: str = ""
    # Hub-injected anchor in every member agent's system prompt — plaintext on the hub since it describes purpose, not transcript content.
    briefing: str = ""
    # When True, member engines engage with the briefing on their next turn after create — no human prompt required.
    auto_kickoff: bool = True
    # Push target on ``#done`` landing: ``"none"`` (silent), ``"telegram"`` (user's configured gateway DM).
    notify_on_close: str = "none"


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
            briefing=str(raw.get("briefing") or ""),
            auto_kickoff=bool(raw.get("auto_kickoff", True)),
            notify_on_close=str(raw.get("notify_on_close") or "none"),
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
    if meta.briefing:
        payload["briefing"] = meta.briefing
    if not meta.auto_kickoff:
        payload["auto_kickoff"] = False
    if meta.notify_on_close and meta.notify_on_close != "none":
        payload["notify_on_close"] = meta.notify_on_close
    (d / _META).write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True))


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
            last_seen_at=str(entry.get("last_seen_at") or ""),
            bio=str(entry.get("bio") or ""),
            voice=str(entry.get("voice") or ""),
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
        if m.last_seen_at:
            entry["last_seen_at"] = m.last_seen_at
        if m.bio:
            entry["bio"] = m.bio
        if m.voice:
            entry["voice"] = m.voice
        data.append(entry)
    (d / _MEMBERS).write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))


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


def create(
    home: Path,
    *,
    name: str,
    hub_kp: Keypair,
    member_pubkeys: list[str],
    budget: dict[str, Any] | None = None,
    briefing: str = "",
    auto_kickoff: bool = True,
    notify_on_close: str = "none",
    hub_bio: str = "",
    hub_voice: str = "",
) -> Workgroup:
    """Create a workgroup on this profile as hub; seals the fresh group key once per member."""
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
        briefing=(briefing or "").strip(),
        auto_kickoff=bool(auto_kickoff),
        notify_on_close=str(notify_on_close or "none"),
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
            m.last_seen_at = now
            if hub_bio:
                m.bio = hub_bio[:_BIO_MAX]
            if hub_voice:
                m.voice = hub_voice[:_VOICE_MAX]
        members.append(m)
    _save_members(d, members)

    (d / _TRANSCRIPT).touch()
    (d / _LEDGER).write_text(json.dumps(
        {"usd": 0.0, "tokens": 0, "posts": 0}, separators=(",", ":"),
    ))

    wg = Workgroup(meta=meta, members=members)
    _auto_join_local_members(home, wg)
    return wg


def _auto_join_local_members(hub_home: Path, wg: "Workgroup") -> None:
    """Auto-join every member whose profile dir is on this filesystem; cross-machine peers must run workgroup.join."""
    from alpi import config as _cfg
    from alpi.alp import peers as peers_mod
    from alpi.alp import subscription as sub_mod
    from alpi.alp.keys import load_or_generate
    from alpi.home import _ROOT

    profiles_root = _ROOT / "profiles"
    if not profiles_root.exists():
        return

    pubkey_to_home: dict[str, Path] = {}
    for prof_dir in profiles_root.iterdir():
        if not prof_dir.is_dir():
            continue
        try:
            kp = load_or_generate(prof_dir)
            pubkey_to_home[kp.pubkey_b64()] = prof_dir
        except Exception:  # noqa: BLE001
            continue

    now = _utcnow()
    hub_pinned = peers_mod.load(hub_home)
    members_changed = False

    # Two-pass: pass 1 mutates Member.bio/voice BEFORE pass 2 snapshots roster_payload — do not merge.
    for m in wg.members:
        if m.pubkey == wg.meta.hub_pubkey:
            continue
        member_home = pubkey_to_home.get(m.pubkey)
        if member_home is None:
            continue

        member_cfg = _cfg.load(member_home)
        member_bio = (member_cfg.public_bio or "").strip()[:_BIO_MAX]
        if member_bio and member_bio != m.bio:
            m.bio = member_bio
            members_changed = True
        member_voice = (member_cfg.tools.tts.voice or "").strip()[:_VOICE_MAX]
        if member_voice and member_voice != m.voice:
            m.voice = member_voice
            members_changed = True
        if not m.joined:
            m.joined = True
            m.joined_at = now
            m.last_seen_at = now
            members_changed = True

    roster_payload = [
        {
            "pubkey": m.pubkey,
            "last_seen_at": m.last_seen_at,
            "bio": m.bio,
            "voice": m.voice,
        }
        for m in wg.members
    ]
    for m in wg.members:
        if m.pubkey == wg.meta.hub_pubkey:
            continue
        member_home = pubkey_to_home.get(m.pubkey)
        if member_home is None:
            continue

        hub_id = _resolve_hub_alias(member_home, wg.meta.hub_pubkey, hub_pinned)
        if hub_id is None:
            continue
        sub = sub_mod.get(member_home, wg.meta.id) or sub_mod.Subscription(
            wg_id=wg.meta.id,
            name=wg.meta.name,
            hub_id=hub_id,
            hub_pubkey=wg.meta.hub_pubkey,
        )
        sub.name = wg.meta.name
        sub.hub_id = hub_id
        sub.hub_pubkey = wg.meta.hub_pubkey
        sub.briefing = wg.meta.briefing
        sub.upsert_key(m.key_version, m.sealed_key)
        if not sub.joined_at:
            sub.joined_at = now
        sub.roster = {
            r["pubkey"]: r["last_seen_at"] for r in roster_payload
        }
        sub.roster_bios = {
            r["pubkey"]: r["bio"] for r in roster_payload if r.get("bio")
        }
        sub.roster_voices = {
            r["pubkey"]: r["voice"] for r in roster_payload if r.get("voice")
        }
        sub_mod.upsert(member_home, sub)

    if members_changed:
        _save_members(_wg_dir(hub_home, wg.meta.id), wg.members)


def _resolve_hub_alias(
    member_home: Path,
    hub_pubkey: str,
    hub_pinned: list,
) -> str | None:
    """Resolve the member's alias for the hub from peers.yaml."""
    from alpi.alp import peers as peers_mod
    pinned = peers_mod.load(member_home)
    for p in pinned:
        if p.pubkey == hub_pubkey:
            return p.id
    for p in hub_pinned:
        if p.pubkey == hub_pubkey:
            return p.id
    return None


def _rekey(home: Path, wg_id: str, dropped_pubkey: str) -> Workgroup:
    """Drop pubkey, mint fresh group key, re-seal for remaining members, bump version. Hub cannot be dropped."""
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
    """Remove target from the workgroup and rotate the group key."""
    return _rekey(home, wg_id, target_pubkey)


def add_member(home: Path, wg_id: str, target_pubkey: str) -> Workgroup:
    """Add a new member by pubkey, mint a fresh group key, re-seal for all members, bump key version."""
    wg = load(home, wg_id)
    if wg is None:
        raise ValueError(f"workgroup {wg_id!r} not found")
    pk = (target_pubkey or "").strip()
    if not pk:
        raise ValueError("target pubkey required")
    try:
        decode_pubkey(pk)
    except Exception as e:  # noqa: BLE001
        raise ValueError(f"invalid pubkey: {pk!r}") from e
    if wg.member(pk) is not None:
        raise ValueError(f"pubkey {pk!r} already in roster")

    new_key = secrets.token_bytes(GROUP_KEY_BYTES)
    new_version = wg.meta.current_key_version + 1
    for m in wg.members:
        m.sealed_key = seal_group_key(new_key, m.pubkey)
        m.key_version = new_version
    wg.members.append(
        Member(
            pubkey=pk,
            sealed_key=seal_group_key(new_key, pk),
            key_version=new_version,
        )
    )
    wg.meta.current_key_version = new_version

    d = _wg_dir(home, wg_id)
    _save_meta(d, wg.meta)
    _save_members(d, wg.members)
    _auto_join_local_members(home, wg)
    return wg


def _emit_hub_wg_mention(
    home: Path, wg: "Workgroup", entry: dict[str, Any],
    nonce: str, ciphertext: str,
) -> None:
    """Decrypt a member's incoming post on the hub side and emit ``wg.mention`` if the hub profile is ``@``-tagged. Mirrors ``_emit_wg_mentions`` on the client pull path."""
    if entry.get("from") == wg.meta.hub_pubkey:
        return
    try:
        from alpi.alp import tasks as tasks_mod
        from alpi.alp.keys import load_or_generate
        from alpi.home import profile_name
        from alpi.host import events as host_events
    except Exception:  # noqa: BLE001
        return

    me = (profile_name(home) or "").lower()
    if not me:
        return

    hub_member = wg.member(wg.meta.hub_pubkey)
    if hub_member is None or not hub_member.sealed_key:
        return

    try:
        hub_kp = load_or_generate(home)
        group_key = open_sealed_group_key(hub_member.sealed_key, hub_kp)
        plaintext = decrypt_post(group_key, nonce, ciphertext).decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return

    mentioned = {m.lower() for m in tasks_mod.mentions_in(plaintext)}
    if me not in mentioned:
        return
    try:
        host_events.emit("wg.mention", {
            "profile": profile_name(home),
            "wg_id": wg.meta.id,
            "seq": int(entry.get("seq") or 0),
            "from": str(entry.get("from") or ""),
            "summary": plaintext[:200],
        })
    except Exception:  # noqa: BLE001
        pass


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
    """Normalise the workgroup budget; empty dict = no cap, non-positive raises."""
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
    """Raise -32005 budget-exceeded if admitting this post breaches the workgroup cap."""
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


def register(server: alp_server.Server, home: Path) -> None:
    """Register workgroup.{join,post,pull,leave}; handlers verify roster and raise -32008 workgroup-not-member."""

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
        now = _utcnow()
        member.last_seen_at = now
        bio = str((params or {}).get("bio") or "").strip()
        if bio:
            member.bio = bio[:_BIO_MAX]
        voice = str((params or {}).get("voice") or "").strip()
        if voice:
            member.voice = voice[:_VOICE_MAX]
        if not member.joined:
            member.joined = True
            member.joined_at = now
        _save_members(_wg_dir(home, wg_id), wg.members)
        return {
            "workgroup_id": wg.meta.id,
            "name": wg.meta.name,
            "briefing": wg.meta.briefing,
            "sealed_key": member.sealed_key,
            "key_version": member.key_version,
            "current_key_version": wg.meta.current_key_version,
            "members": [
                {
                    "pubkey": m.pubkey,
                    "last_seen_at": m.last_seen_at,
                    "bio": m.bio,
                    "voice": m.voice,
                }
                for m in wg.members
            ],
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

        member = wg.member(peer.pubkey)
        if member is not None:
            member.last_seen_at = entry["ts"]
            _save_members(d, wg.members)

        try:
            from alpi.host import events as host_events
            from alpi.home import profile_name
            host_events.emit("wg.post", {
                "profile": profile_name(home),
                "wg_id": wg_id,
                "seq": seq,
            })
        except Exception:  # noqa: BLE001
            pass

        _emit_hub_wg_mention(home, wg, entry, nonce, ciphertext)

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
        member.last_seen_at = _utcnow()
        _save_members(_wg_dir(home, wg_id), wg.members)
        all_posts = _read_transcript(_wg_dir(home, wg_id))
        fresh = [p for p in all_posts if int(p.get("seq", 0)) > since]
        return {
            "posts": fresh,
            "head": all_posts[-1]["seq"] if all_posts else 0,
            "current_key_version": wg.meta.current_key_version,
            "sealed_key": member.sealed_key,
            "members": [
                {
                    "pubkey": m.pubkey,
                    "last_seen_at": m.last_seen_at,
                    "bio": m.bio,
                    "voice": m.voice,
                }
                for m in wg.members
            ],
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
        if peer.pubkey != wg.meta.hub_pubkey:
            raise alp_server.HandlerError(
                -32008, "workgroup-not-hub",
                data={"detail": "only the hub may pause this workgroup"},
            )
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
        if peer.pubkey != wg.meta.hub_pubkey:
            raise alp_server.HandlerError(
                -32008, "workgroup-not-hub",
                data={"detail": "only the hub may resume this workgroup"},
            )
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
