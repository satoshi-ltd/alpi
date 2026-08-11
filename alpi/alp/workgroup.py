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
    files/            # encrypted file sidecars keyed by plaintext SHA-256
"""

from __future__ import annotations

import asyncio as _asyncio
import base64
import datetime as _dt
import fcntl as _fcntl
import json
import logging as _logging
import os
import re as _re
import secrets
import shutil as _shutil
import time as _time
from contextlib import contextmanager as _contextmanager
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any


from alpi import yamlfast
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


_log = _logging.getLogger("alpi.alp.workgroup")
# Warn-once: the poller re-loads every workgroup each tick.
_warned_unloadable: set[str] = set()

_WG_DIR = "alp/workgroups"
_META = "meta.yaml"
_MEMBERS = "members.yaml"
_TRANSCRIPT = "transcript.jsonl"
_LEDGER = "ledger.json"
_HUB_KEYS = "hub_keys.json"  # hub-only history: past group keys (sealed for the hub) across rekeys

_BIO_MAX = 200
_VOICE_MAX = 64

# Hub-side bounds on remote posts (the poster is untrusted).
_MAX_POST_CIPHERTEXT = 256 * 1024   # bytes of one post's ciphertext
_MAX_TRANSCRIPT_POSTS = 10_000      # per-workgroup transcript cap
_MAX_DECLARED_USD = 1000.0          # clamp self-declared cost
_MAX_DECLARED_TOKENS = 100_000_000

# Long-poll pull: wait_s clamp keeps a held request under the 30s client RPC timeout.
_LONG_POLL_MAX_WAIT_S = 25.0
_LONG_POLL_PROBE_SECONDS = 0.5
_PRESENCE_WRITE_INTERVAL_S = 30.0


def _coerce_wait_s(raw: Any) -> float:
    try:
        w = float(raw)
    except (TypeError, ValueError):
        return 0.0
    if w <= 0:
        return 0.0
    return min(w, _LONG_POLL_MAX_WAIT_S)


def _presence_write_due(last_seen_at: str, now: _dt.datetime) -> bool:
    if not last_seen_at:
        return True
    try:
        previous = _dt.datetime.strptime(
            last_seen_at, "%Y-%m-%dT%H:%M:%SZ",
        ).replace(tzinfo=_dt.timezone.utc)
    except ValueError:
        return True
    return (now - previous).total_seconds() >= _PRESENCE_WRITE_INTERVAL_S


def _as_float(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _as_int(v: Any) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0

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
    # ``max_usd`` lifetime cap (empty = none), additional to the upstream profile cap
    budget: dict[str, Any] = field(default_factory=dict)
    # Soft circuit-breaker on ``workgroup.post`` only — ``pull``/``join``/``leave`` keep working so members can catch up and exit cleanly.
    paused: bool = False
    paused_at: str = ""
    paused_by: str = ""
    # Hub-injected anchor in every member agent's system prompt — plaintext on the hub since it describes purpose, not transcript content.
    briefing: str = ""
    # Push target on ``#done`` landing: ``"none"`` (silent) or ``"notify"`` (native push to the owner's apps).
    notify_on_close: str = "none"
    # Named ordered chains, each keyed by its own first phase (empty = deliberation wg); the single source of phase order for gates and continuation.
    pipelines: dict[str, tuple[str, ...]] = field(default_factory=dict)
    # Which chain the launch kickoff opens; None = idle workgroup whose chains wait for an explicit trigger.
    launch_pipeline: str | None = None
    # Hub-local gate specs per phase ({phase: {owner, task?, gate: {argv, cwd?}}}); never transmitted on the wire, never accepts remote text.
    pipeline_steps: dict = field(default_factory=dict)
    # Hub-local desktop playback preference — not replicated to members
    auto_read: bool = False
    # Closure-quorum grace (s) before the hub may `#done` with no substantive peer input; 0 = the _FULL_QUORUM_TIMEOUT_SECONDS default.
    quorum_timeout_seconds: int = 0
    # Recipe launch provenance (recipe_id, digest, params, project dest, template commit); informational — editing the source recipe never mutates this.
    launch: dict = field(default_factory=dict)

    @property
    def launch_chain(self) -> tuple[str, ...]:
        return self.pipelines.get(self.launch_pipeline or "", ())


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


_WG_ID_RE = _re.compile(r"^[A-Za-z0-9_-]+$")
_TURN_ID_RE = _re.compile(r"^[0-9a-f]{32}$")


def _wg_dir(home: Path, wg_id: str) -> Path:
    # wg_id is off-the-wire — reject separators/`..` so a peer can't reach a sibling profile's workgroups.
    if not _WG_ID_RE.match(wg_id or ""):
        raise ValueError(f"invalid workgroup id: {wg_id!r}")
    return _root(home) / wg_id


def validate_turn_id(value: Any) -> str:
    """Validate the optional daemon-to-transcript correlation id."""
    if value in (None, ""):
        return ""
    if not isinstance(value, str) or not _TURN_ID_RE.fullmatch(value):
        raise ValueError("turn_id must be 32 lowercase hexadecimal characters")
    return value


def _utcnow() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_id() -> str:
    return "wg_" + base64.b32encode(secrets.token_bytes(10)).decode("ascii").lower().rstrip("=")


def _coerce_positive_int(value: object) -> int:
    """Non-negative int, else 0 (the default) — tolerant of junk/negatives in meta.yaml; a negative timeout would let the hub close instantly."""
    try:
        n = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0
    return n if n > 0 else 0


def _load_meta(d: Path) -> Meta | None:
    p = d / _META
    if not p.exists():
        return None
    raw = yamlfast.safe_load(p.read_text()) or {}
    if not isinstance(raw, dict):
        return None
    try:
        pipelines, launch_pipeline = pipelines_from_raw(raw)
    except ValueError as e:
        if str(d) not in _warned_unloadable:
            _warned_unloadable.add(str(d))
            _log.warning("workgroup %s did not load: %s", d.name, e)
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
            notify_on_close=str(raw.get("notify_on_close") or "none"),
            pipelines=pipelines,
            launch_pipeline=launch_pipeline,
            pipeline_steps=_steps_without_next(raw.get("pipeline_steps")),
            auto_read=bool(raw.get("auto_read", False)),
            quorum_timeout_seconds=_coerce_positive_int(raw.get("quorum_timeout_seconds")),
            launch=raw.get("launch") if isinstance(raw.get("launch"), dict) else {},
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
    if meta.notify_on_close and meta.notify_on_close != "none":
        payload["notify_on_close"] = meta.notify_on_close
    if meta.pipelines:
        payload["pipelines"] = {k: list(v) for k, v in meta.pipelines.items()}
    if meta.launch_pipeline:
        payload["launch_pipeline"] = meta.launch_pipeline
    if meta.pipeline_steps:
        payload["pipeline_steps"] = dict(meta.pipeline_steps)
    if meta.auto_read:
        payload["auto_read"] = True
    if meta.quorum_timeout_seconds:
        payload["quorum_timeout_seconds"] = meta.quorum_timeout_seconds
    if meta.launch:
        payload["launch"] = dict(meta.launch)
    (d / _META).write_text(yamlfast.safe_dump(payload, sort_keys=False, allow_unicode=True))


def _load_members(d: Path) -> list[Member]:
    p = d / _MEMBERS
    if not p.exists():
        return []
    raw = yamlfast.safe_load(p.read_text()) or []
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
    (d / _MEMBERS).write_text(yamlfast.safe_dump(data, sort_keys=False, allow_unicode=True))


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
    notify_on_close: str = "none",
    pipelines: dict | None = None,
    launch_pipeline: str | None = None,
    pipeline_steps: Any = None,
    quorum_timeout_seconds: int = 0,
    launch: dict | None = None,
    hub_bio: str = "",
    hub_voice: str = "",
) -> Workgroup:
    """Create a workgroup on this profile as hub; seals the fresh group key once per member."""
    name = (name or "").strip()
    if not name:
        raise ValueError("workgroup name required")
    budget = _validate_budget(budget or {})
    norm_pipelines = normalize_pipelines(pipelines)
    norm_launch = normalize_launch_pipeline(norm_pipelines, launch_pipeline)
    norm_steps = validate_pipeline_steps(norm_pipelines, pipeline_steps)

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

    try:
        meta = Meta(
            id=wg_id,
            name=name,
            hub_pubkey=hub_pk,
            created_at=_utcnow(),
            current_key_version=1,
            budget=budget,
            briefing=(briefing or "").strip(),
            notify_on_close=str(notify_on_close or "none"),
            pipelines=norm_pipelines,
            launch_pipeline=norm_launch,
            pipeline_steps=norm_steps,
            quorum_timeout_seconds=_coerce_positive_int(quorum_timeout_seconds),
            launch=dict(launch) if launch else {},
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
    except BaseException:
        destroy(home, wg_id)
        raise
    return wg


def destroy(home: Path, wg_id: str) -> list[str]:
    # Tolerant (ignore_errors) — for recipe-launch rollbacks; user-facing deletes go through remove().
    _shutil.rmtree(_wg_dir(home, wg_id), ignore_errors=True)
    return _purge_after_delete(home, wg_id)


def remove(home: Path, wg_id: str) -> list[str]:
    # Canonical user-facing delete: spend survives deletion, or nothing is deleted.
    from alpi.cleanup import archive_workgroup_spend

    wg_dir = _wg_dir(home, wg_id)
    archive_err = archive_workgroup_spend(home, wg_dir)
    if archive_err:
        raise OSError(f"spend archive failed; workgroup not removed: {archive_err}")
    _shutil.rmtree(wg_dir)
    return _purge_after_delete(home, wg_id)


def _purge_after_delete(home: Path, wg_id: str) -> list[str]:
    from alpi.alp import subscription as sub_mod
    from alpi.home import _ROOT

    try:
        from alpi.tools.workgroup_search import forget_workgroup
        forget_workgroup(home, wg_id)
    except Exception:  # noqa: BLE001
        pass
    purged: list[str] = []
    profiles_root = _ROOT / "profiles"
    for prof_dir in (profiles_root.iterdir() if profiles_root.exists() else []):
        if not prof_dir.is_dir():
            continue
        try:
            had = sub_mod.get(prof_dir, wg_id) is not None
            # Unconditional: a write-back in flight resurrects a plain remove.
            sub_mod.tombstone(prof_dir, wg_id)
            if had:
                sub_mod.compact(prof_dir)
                purged.append(prof_dir.name)
        except Exception:  # noqa: BLE001
            continue
    try:
        had = sub_mod.get(_ROOT, wg_id) is not None
        sub_mod.tombstone(_ROOT, wg_id)
        if had:
            sub_mod.compact(_ROOT)
            purged.append("default")
    except Exception:  # noqa: BLE001
        pass
    return purged


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
        # Before the first pull, or an idle pipeline workgroup dispatches turn one under deliberation rules.
        sub.absorb_pipeline_state(_wire_pipeline_state(wg.meta))
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


def _record_hub_key(home: Path, wg_id: str, version: int, sealed: str) -> None:
    # Stash the hub's sealed group key for `version` before a rekey overwrites it,
    # so the hub can still fold posts written under the rotated-out version.
    if not sealed:
        return
    p = _wg_dir(home, wg_id) / _HUB_KEYS
    hist: dict[str, str] = {}
    if p.exists():
        try:
            hist = json.loads(p.read_text()) or {}
        except json.JSONDecodeError:
            hist = {}
    hist[str(int(version))] = sealed
    p.write_text(json.dumps(hist, separators=(",", ":")))


def hub_group_keys(home: Path, wg: "Workgroup", kp: Keypair) -> dict[int, bytes]:
    # version -> group key for every version the hub can still open: its current
    # member sealed_key plus the hub_keys.json history. Lets a hub decrypt the
    # full transcript across rekeys instead of blanking rotated-out posts.
    out: dict[int, bytes] = {}
    me = wg.member(kp.pubkey_b64())
    if me is not None and me.sealed_key:
        try:
            out[int(me.key_version)] = open_sealed_group_key(me.sealed_key, kp)
        except Exception:  # noqa: BLE001
            pass
    p = _wg_dir(home, wg.meta.id) / _HUB_KEYS
    if p.exists():
        try:
            hist = json.loads(p.read_text()) or {}
        except json.JSONDecodeError:
            hist = {}
        for v, sealed in hist.items():
            try:
                vi = int(v)
            except (TypeError, ValueError):
                continue
            if vi in out:
                continue
            try:
                out[vi] = open_sealed_group_key(sealed, kp)
            except Exception:  # noqa: BLE001
                pass
    return out


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
    hub_member = wg.member(wg.meta.hub_pubkey)
    if hub_member is not None:
        _record_hub_key(home, wg_id, hub_member.key_version, hub_member.sealed_key)
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

    hub_member = wg.member(wg.meta.hub_pubkey)
    if hub_member is not None:
        _record_hub_key(home, wg_id, hub_member.key_version, hub_member.sealed_key)
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


@_contextmanager
def _transcript_write_lock(d: Path):
    # flock spans read-seq + append so two same-machine writers cannot mint one seq.
    d.mkdir(parents=True, exist_ok=True)
    with open(d / ".transcript.lock", "w") as fh:
        _fcntl.flock(fh, _fcntl.LOCK_EX)
        try:
            yield
        finally:
            _fcntl.flock(fh, _fcntl.LOCK_UN)


def append_with_seq(d: Path, entry: dict[str, Any]) -> dict[str, Any]:
    """Assign the next seq and append atomically with respect to other local writers."""
    with _transcript_write_lock(d):
        existing = _read_transcript(d)
        entry["seq"] = (existing[-1]["seq"] + 1) if existing else 1
        _append_transcript(d, entry)
    return entry


def admit_post(
    d: Path, meta: "Meta", entry: dict[str, Any],
    declared_usd: float = 0.0, declared_tokens: int = 0,
    *, enforce_cap: bool = False, reject_nonce_reuse: bool = False,
) -> dict[str, Any]:
    """Budget gate, cap, nonce, seq+append and ledger under ONE lock — split apart, concurrent writers overwrite each other's ledger and race past the cap."""
    with _transcript_write_lock(d):
        return _admit_post_locked(
            d, meta, entry, declared_usd, declared_tokens,
            enforce_cap=enforce_cap, reject_nonce_reuse=reject_nonce_reuse,
        )


def _admit_post_locked(
    d: Path, meta: "Meta", entry: dict[str, Any],
    declared_usd: float = 0.0, declared_tokens: int = 0,
    *, enforce_cap: bool = False, reject_nonce_reuse: bool = False,
) -> dict[str, Any]:
    # flock is not reentrant across fds: callers already inside _transcript_write_lock must use this, never admit_post.
    ledger = _load_ledger(d)
    _gate_post(meta, ledger, {"usd": declared_usd, "tokens": declared_tokens})
    existing = _read_transcript(d)
    if enforce_cap and len(existing) >= _MAX_TRANSCRIPT_POSTS:
        raise alp_server.HandlerError(
            -32010, "workgroup-full",
            data={"detail": f"transcript at cap ({_MAX_TRANSCRIPT_POSTS} posts)"},
        )
    if reject_nonce_reuse and any(
        e.get("nonce") == entry.get("nonce")
        and _as_int(e.get("key_version", 1)) == _as_int(entry.get("key_version", 1))
        for e in existing
    ):
        raise alp_server.HandlerError(
            -32602, "invalid-params",
            data={"detail": "nonce reuse for this key_version"},
        )
    entry["seq"] = (existing[-1]["seq"] + 1) if existing else 1
    transcript = d / _TRANSCRIPT
    prev_size = transcript.stat().st_size if transcript.exists() else 0
    _append_transcript(d, entry)
    ledger["usd"] = float(ledger.get("usd", 0.0)) + declared_usd
    ledger["tokens"] = int(ledger.get("tokens", 0)) + declared_tokens
    ledger["posts"] = int(ledger.get("posts", 0)) + 1
    try:
        _save_ledger(d, ledger)
    except Exception:
        # Still under the lock: truncating the append keeps transcript and ledger consistent — a phase must never open without its accounting.
        with transcript.open("rb+") as fh:
            fh.truncate(prev_size)
        raise
    return entry


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
    import tempfile
    d.mkdir(parents=True, exist_ok=True)
    text = json.dumps(
        {
            "usd": float(ledger.get("usd", 0.0)),
            "tokens": int(ledger.get("tokens", 0)),
            "posts": int(ledger.get("posts", 0)),
        },
        separators=(",", ":"),
    )
    fd, tmp_name = tempfile.mkstemp(dir=str(d), prefix=f".{_LEDGER}.", suffix=".tmp")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, 0o600)
        os.replace(str(tmp), str(d / _LEDGER))
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


_PIPELINE_SLUG_RE = _re.compile(r"^[a-z0-9][a-z0-9_-]*$")
# Closed allowlist: any wider rule would let an operational chain name resolve to an unrelated phase.
_RECOVERY_SUFFIXES = ("-fix", "-recheck")


def _normalize_pipeline(raw: Any) -> tuple[str, ...]:
    """Validate + normalise an ordered pipeline phase list. Empty/absent →
    ``()`` (normal workgroup). Slugs are lowercased; each must match
    ``[a-z0-9][a-z0-9_-]*``; duplicates are rejected (order is identity)."""
    if not raw:
        return ()
    if not isinstance(raw, (list, tuple)):
        raise ValueError(f"pipeline must be a list of phase slugs, got {type(raw).__name__}")
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        slug = str(item).strip().lower()
        if not _PIPELINE_SLUG_RE.match(slug):
            raise ValueError(
                f"invalid pipeline phase slug {item!r}: must match "
                "[a-z0-9][a-z0-9_-]*"
            )
        if slug in seen:
            raise ValueError(f"duplicate pipeline phase slug {slug!r}")
        seen.add(slug)
        out.append(slug)
    return tuple(out)


def normalize_pipelines(raw: Any) -> dict[str, tuple[str, ...]]:
    """Each key must equal its own first phase and phases are globally disjoint, so a task slug has at most one owning pipeline."""
    if not raw:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(
            f"pipelines must be a mapping of name → phase list, got {type(raw).__name__}"
        )
    out: dict[str, tuple[str, ...]] = {}
    claimed: dict[str, str] = {}
    for name, chain in raw.items():
        key = str(name).strip().lower()
        if not _PIPELINE_SLUG_RE.match(key):
            raise ValueError(f"pipeline name {name!r} is not a valid slug")
        if key in out:
            raise ValueError(f"duplicate pipeline {key!r}")
        slugs = _normalize_pipeline(chain)
        if not slugs:
            raise ValueError(f"pipeline {key!r} must declare a non-empty phase list")
        if slugs[0] != key:
            raise ValueError(
                f"pipeline {key!r} must be keyed by its first phase so `#task #{key}` "
                f"opens it; got {slugs[0]!r}"
            )
        for slug in slugs:
            if slug in claimed:
                raise ValueError(
                    f"phase {slug!r} belongs to pipelines {claimed[slug]!r} and {key!r}; "
                    "chains must be disjoint"
                )
            claimed[slug] = key
        out[key] = slugs
    return out


def normalize_launch_pipeline(
    pipelines: dict[str, tuple[str, ...]], raw: Any,
) -> str | None:
    key = str(raw or "").strip().lower()
    if not key:
        return None
    if not pipelines:
        raise ValueError(f"launch pipeline {key!r} declared without any pipelines")
    if key not in pipelines:
        raise ValueError(
            f"launch pipeline {key!r} is not one of {sorted(pipelines)}"
        )
    return key


RETIRED_PIPELINE_KEYS = ("pipeline", "operations")


def reject_retired_keys(raw: Any, where: str) -> None:
    """The split `pipeline` + `operations` shape is gone; a file still carrying it must not load."""
    if not isinstance(raw, dict):
        return
    present = [k for k in RETIRED_PIPELINE_KEYS if raw.get(k)]
    if present:
        raise ValueError(
            f"{where} declares retired {'/'.join(present)}; declare `pipelines` "
            "(a map of named chains) plus `launch_pipeline` instead"
        )


def pipelines_from_raw(raw: Any) -> tuple[dict[str, tuple[str, ...]], str | None]:
    """Junk degrades to no pipelines; the retired shape raises so the caller can refuse the file."""
    if not isinstance(raw, dict):
        return {}, None
    reject_retired_keys(raw, "this workgroup")
    try:
        pipelines = normalize_pipelines(raw.get("pipelines"))
        return pipelines, normalize_launch_pipeline(
            pipelines, raw.get("launch_pipeline"),
        )
    except ValueError:
        return {}, None


def is_pipeline_workgroup(meta: Any) -> bool:
    return bool(getattr(meta, "pipelines", None))


def pipeline_for_phase(
    meta: Any, phase: str,
) -> tuple[str, tuple[str, ...]] | None:
    for key, chain in (getattr(meta, "pipelines", None) or {}).items():
        if phase in chain:
            return key, tuple(chain)
    return None


def canonical_pipeline_phase(meta: Any, slug: str) -> tuple[str, str] | None:
    """Exact membership first, then the LONGEST declared-phase prefix — shortest-first would let `content` swallow the declared `content-update` chain."""
    slug = str(slug or "").strip().lower()
    if not slug:
        return None
    exact = pipeline_for_phase(meta, slug)
    if exact is not None:
        return exact[0], slug
    parts = slug.split("-")
    for cut in range(len(parts) - 1, 0, -1):
        base = "-".join(parts[:cut])
        owner = pipeline_for_phase(meta, base)
        if owner is not None:
            return owner[0], base
    return None


def pipeline_successor(meta: Any, phase: str) -> str:
    """The one direct successor of an exact declared phase; "" when terminal or unknown."""
    owner = pipeline_for_phase(meta, phase)
    if owner is None:
        return ""
    chain = owner[1]
    idx = chain.index(phase)
    return chain[idx + 1] if idx + 1 < len(chain) else ""


def safe_phase_map(meta: Any) -> dict[str, dict[str, str]]:
    """Owner, declared task and turn budget only — gate argv/cwd, gate output and provenance never leave the hub."""
    out: dict[str, dict[str, str]] = {}
    for phase, raw in (getattr(meta, "pipeline_steps", None) or {}).items():
        if not isinstance(raw, dict):
            continue
        owner = str(raw.get("owner") or "").strip()
        if not owner:
            continue
        entry: dict[str, Any] = {"owner": owner}
        task = str(raw.get("task") or "").strip()
        if task:
            entry["task"] = task
        try:
            budget = int(raw.get("turn_budget_s") or 0)
        except (TypeError, ValueError):
            budget = 0
        if budget > 0:
            entry["turn_budget_s"] = budget
        out[str(phase)] = entry
    return out


def _wire_pipeline_state(meta: Any) -> dict[str, Any]:
    """What a member is allowed to learn: chains, selector, mode and safe owners/tasks — never gates."""
    return {
        "pipelines": {k: list(v) for k, v in (meta.pipelines or {}).items()},
        "launch_pipeline": meta.launch_pipeline,
        "pipeline_mode": is_pipeline_workgroup(meta),
        "phase_map": safe_phase_map(meta),
    }


def dormant_pipelines(meta: Any) -> dict[str, tuple[str, ...]]:
    """Every declared chain except the selected launch one: read-only, trigger-only."""
    launch = getattr(meta, "launch_pipeline", None)
    return {
        k: tuple(v)
        for k, v in (getattr(meta, "pipelines", None) or {}).items()
        if k != launch
    }


def _steps_without_next(raw: Any) -> dict[str, dict]:
    if not isinstance(raw, dict):
        return {}
    return {
        str(phase): {k: v for k, v in spec.items() if k != "next"}
        for phase, spec in raw.items()
        if isinstance(spec, dict)
    }


def validate_pipeline_steps(
    pipelines: dict[str, tuple[str, ...]] | None, pipeline_steps: Any,
) -> dict[str, dict]:
    if not pipeline_steps:
        return {}
    if not isinstance(pipeline_steps, dict):
        raise ValueError(f"pipeline_steps must be a mapping, got {type(pipeline_steps).__name__}")
    pipelines = pipelines or {}
    phases = {slug for chain in pipelines.values() for slug in chain}
    out: dict[str, dict] = {}
    for phase, raw in pipeline_steps.items():
        phase = str(phase).strip().lower()
        if not _PIPELINE_SLUG_RE.match(phase):
            raise ValueError(f"pipeline_steps key {phase!r} is not a valid phase slug")
        if pipelines and phase not in phases:
            raise ValueError(
                f"pipeline_steps key {phase!r} belongs to no declared pipeline "
                f"{sorted(pipelines)}"
            )
        if not isinstance(raw, dict):
            raise ValueError(f"pipeline_steps[{phase!r}] must be a mapping")
        owner = str(raw.get("owner") or "").strip()
        if not owner:
            raise ValueError(f"pipeline_steps[{phase!r}] missing 'owner'")
        if raw.get("next") is not None:
            owning = next((k for k, c in pipelines.items() if phase in c), "")
            source = f"pipelines[{owning!r}]" if owning else "the pipeline order"
            raise ValueError(
                f"pipeline_steps[{phase!r}].next is derived from {source}; remove next"
            )
        step: dict[str, Any] = {"owner": owner}
        if raw.get("task"):
            step["task"] = str(raw["task"])
        budget = raw.get("turn_budget_s")
        if budget is not None:
            try:
                budget = int(budget)
            except (TypeError, ValueError):
                raise ValueError(
                    f"pipeline_steps[{phase!r}].turn_budget_s must be an integer"
                )
            if not 60 <= budget <= 3600:
                raise ValueError(
                    f"pipeline_steps[{phase!r}].turn_budget_s must be 60..3600 seconds"
                )
            step["turn_budget_s"] = budget
        gate = raw.get("gate")
        if gate is not None:
            if not isinstance(gate, dict):
                raise ValueError(f"pipeline_steps[{phase!r}].gate must be a mapping")
            argv = gate.get("argv")
            if not isinstance(argv, list) or not argv or not all(isinstance(a, str) and a for a in argv):
                raise ValueError(f"pipeline_steps[{phase!r}].gate.argv must be a non-empty list of strings")
            cwd = gate.get("cwd", "")
            if not isinstance(cwd, str):
                raise ValueError(f"pipeline_steps[{phase!r}].gate.cwd must be a string")
            step["gate"] = {"argv": list(argv), "cwd": cwd}
        paths = raw.get("paths")
        if paths is not None:
            if not isinstance(paths, list) or not all(
                isinstance(g, str) and g.strip() for g in paths
            ):
                raise ValueError(
                    f"pipeline_steps[{phase!r}].paths must be a list of relative "
                    "path globs"
                )
            for g in paths:
                pp = PurePosixPath(g.strip())
                if pp.is_absolute() or ".." in pp.parts:
                    raise ValueError(
                        f"pipeline_steps[{phase!r}].paths entry {g!r} must stay "
                        "inside the project"
                    )
            if "gate" not in step:
                raise ValueError(
                    f"pipeline_steps[{phase!r}].paths needs a gate — the gate's "
                    "cwd anchors the project root and its run is when the "
                    "boundary is checked"
                )
            step["paths"] = [g.strip() for g in paths]
        out[phase] = step
    return out


def _validate_budget(budget: dict[str, Any]) -> dict[str, Any]:
    """Normalise the workgroup budget; empty dict = no cap, non-positive raises."""
    if not budget:
        return {}
    usd = budget.get("max_usd")
    if usd is None:
        raise ValueError("budget must set max_usd")
    usd_f = float(usd)
    if usd_f <= 0:
        raise ValueError("max_usd must be > 0")
    return {"max_usd": usd_f}


def _gate_post(meta: Meta, ledger: dict[str, Any], cost: dict[str, Any]) -> None:
    """Raise -32005 budget-exceeded if admitting this post breaches the workgroup cap."""
    if not meta.budget:
        return
    usd_cap = meta.budget.get("max_usd")
    declared_usd = float(cost.get("usd", 0.0)) if cost else 0.0
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


def register(server: alp_server.Server, home: Path) -> None:
    """Register workgroup protocol handlers for this hub."""

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
            **_wire_pipeline_state(wg.meta),
            "paused": wg.meta.paused,
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
        if len(ciphertext) > _MAX_POST_CIPHERTEXT:
            raise alp_server.HandlerError(
                -32602, "invalid-params",
                data={"detail": f"ciphertext exceeds {_MAX_POST_CIPHERTEXT} bytes"},
            )
        try:
            key_version = int((params or {}).get("key_version", 1))
        except (TypeError, ValueError):
            key_version = 1
        cost = (params or {}).get("cost") or {}
        if not isinstance(cost, dict):
            cost = {}
        try:
            turn_id = validate_turn_id((params or {}).get("turn_id"))
        except ValueError as e:
            raise alp_server.HandlerError(
                -32602, "invalid-params", data={"detail": str(e)},
            ) from e

        wg = load(home, wg_id)
        if wg is None:
            raise alp_server.HandlerError(-32009, "workgroup-not-found")
        member = wg.member(peer.pubkey)
        if member is None:
            raise alp_server.HandlerError(-32008, "workgroup-not-member")
        if not member.joined:
            raise alp_server.HandlerError(
                -32008, "workgroup-not-joined",
                data={"detail": "run workgroup.join before posting"},
            )
        if wg.meta.paused:
            raise alp_server.HandlerError(
                -32010, "workgroup-paused",
                data={
                    "paused_at": wg.meta.paused_at,
                    "paused_by": wg.meta.paused_by,
                },
            )

        # Poster is untrusted: clamp self-declared cost before it gates budget / lands in the ledger.
        declared_usd = max(0.0, min(_as_float(cost.get("usd")), _MAX_DECLARED_USD))
        declared_tokens = max(0, min(_as_int(cost.get("tokens")), _MAX_DECLARED_TOKENS))
        declared_in = max(0, min(_as_int(cost.get("tokens_in")), _MAX_DECLARED_TOKENS))
        declared_out = max(0, min(_as_int(cost.get("tokens_out")), _MAX_DECLARED_TOKENS))
        # Cached is a SHARE of measured_in (<= tokens_in), never an addition; absent = unmeasured.
        raw_cached = cost.get("cached_in") if isinstance(cost, dict) else None
        declared_measured = max(0, min(
            _as_int(cost.get("measured_in", declared_in)), declared_in,
        )) if raw_cached is not None else 0
        declared_cached = (
            max(0, min(_as_int(raw_cached), declared_measured))
            if raw_cached is not None else None
        )
        # Keep the combined total consistent with the split for the gate + usage.
        declared_tokens = max(declared_tokens, declared_in + declared_out)

        d = _wg_dir(home, wg_id)
        entry: dict[str, Any] = {
            "seq": 0,
            "ts": _utcnow(),
            "from": peer.pubkey,
            "key_version": key_version,
            "nonce": nonce,
            "ciphertext": ciphertext,
        }
        if turn_id:
            entry["turn_id"] = turn_id
        if declared_usd or declared_tokens:
            entry["cost"] = {"usd": declared_usd, "tokens": declared_tokens}
            if declared_in or declared_out:
                entry["cost"]["tokens_in"] = declared_in
                entry["cost"]["tokens_out"] = declared_out
                if declared_cached is not None:
                    entry["cost"]["cached_in"] = declared_cached
                    entry["cost"]["measured_in"] = declared_measured
        entry = admit_post(
            d, wg.meta, entry, declared_usd, declared_tokens,
            enforce_cap=True, reject_nonce_reuse=True,
        )
        seq = int(entry["seq"])

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

        from alpi.alp import wakes
        wakes.fire(home, wg_id)

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
        now_dt = _dt.datetime.now(tz=_dt.timezone.utc)
        persist_presence = _presence_write_due(member.last_seen_at, now_dt)
        member.last_seen_at = now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        if persist_presence:
            _save_members(_wg_dir(home, wg_id), wg.members)
        all_posts = _read_transcript(_wg_dir(home, wg_id))
        fresh = [p for p in all_posts if int(p.get("seq", 0)) > since]
        wait_s = _coerce_wait_s((params or {}).get("wait_s"))
        if not fresh and wait_s > 0:
            # Stat-probe wait, not an in-process event: the hub's own posts land via direct file append from dispatch subprocesses, invisible to any signal registry in this process.
            deadline = _time.monotonic() + wait_s
            wg_dir = _wg_dir(home, wg_id)
            tpath = wg_dir / _TRANSCRIPT
            last_size = tpath.stat().st_size if tpath.exists() else 0
            while _time.monotonic() < deadline:
                await _asyncio.sleep(_LONG_POLL_PROBE_SECONDS)
                try:
                    size = tpath.stat().st_size
                except OSError:
                    continue
                if size == last_size:
                    continue
                last_size = size
                all_posts = _read_transcript(wg_dir)
                fresh = [p for p in all_posts if int(p.get("seq", 0)) > since]
                if fresh:
                    break
        return {
            "posts": fresh,
            "head": all_posts[-1]["seq"] if all_posts else 0,
            "current_key_version": wg.meta.current_key_version,
            **_wire_pipeline_state(wg.meta),
            "paused": wg.meta.paused,
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
            # Clear the poller's "already handled" guards so the next tick
            # re-evaluates the transcript instead of staying silent on counters
            # consumed before the pause.
            try:
                from alpi import service as _service
                _service.reset_workgroup_poller_state(home, wg_id)
            except Exception:  # noqa: BLE001
                pass
        return {"workgroup_id": wg.meta.id, "paused": False}

    server.register("workgroup.join", workgroup_join)
    server.register("workgroup.post", workgroup_post)
    server.register("workgroup.pull", workgroup_pull)
    server.register("workgroup.leave", workgroup_leave)
    server.register("workgroup.pause", workgroup_pause)
    server.register("workgroup.resume", workgroup_resume)
    from alpi.alp import workgroup_files
    workgroup_files.register(server, home)
