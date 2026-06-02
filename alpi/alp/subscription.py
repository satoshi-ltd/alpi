"""Member-side state for workgroups this profile has joined.

Hubs hold the authoritative workgroup state in
``~/.alpi/<profile>/alp/workgroups/<wg_id>/``. Members hold a much
lighter mirror — just enough to send ``workgroup.post`` /
``workgroup.pull`` / ``workgroup.leave`` to the hub without having to
re-``join`` on every restart, and to decrypt past traffic across key
rotations.

Layout::

    ~/.alpi/<profile>/alp/secrets/subscriptions.yaml   # mode 0600

The file lives alongside the Ed25519 keypair under ``secrets/`` —
both are sensitive enough to deserve the same posture. Sealed keys
are stored as-is (they only open with this profile's private key, so
disk exposure alone reveals nothing without the keypair) and the
post cursor is per-workgroup. Old sealed keys are retained so
transcript history past a rotation stays decryptable.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

import yaml

from alpi.alp.keys import Keypair
from alpi.alp import workgroup as wg_mod


_SECRETS_DIR = "alp/secrets"
_FILENAME = "subscriptions.yaml"


@dataclass
class SealedKey:
    version: int
    sealed: str            # base64 ECIES blob (open with our Ed25519 priv)


RECENT_POSTS_CACHE = 20  # last N posts cached locally for engine context
DISPATCH_COOLDOWN_SECONDS = 60  # min gap between auto-dispatches per workgroup


def coerce_pipeline(value: Any) -> tuple[str, ...]:
    """Normalise a pipeline value from disk or the wire to a tuple of phase
    slugs. Anything that isn't a list/tuple — legacy ``True``, ``None``,
    garbage — degrades to ``()`` instead of raising (no crash on old data)."""
    return tuple(value) if isinstance(value, (list, tuple)) else ()


@dataclass
class Subscription:
    """One workgroup we are a remote member of (we are NOT the hub)."""
    wg_id: str
    name: str
    hub_id: str            # peer.id from this profile's peers.yaml
    hub_pubkey: str        # cross-check against the peer entry
    sealed_keys: list[SealedKey] = field(default_factory=list)
    last_seq: int = 0      # cursor for pull(since=…)
    joined_at: str = ""
    # Hub-side anchor cached locally so the engine pre-turn hook gives the member's agent the same briefing the hub's agent sees. Refreshed on every successful ``workgroup.join``.
    briefing: str = ""
    # Mirror of hub's `meta.pipeline` (join/pull); non-empty → member uses the longer production turn budget.
    pipeline: tuple[str, ...] = ()
    # Mirror of hub's `meta.paused` (join/pull); True → the member poller skips dispatch (no wasted turns on a paused wg).
    paused: bool = False
    # Decoupled from ``last_seq`` so a tick that pulls a new post but skips on cooldown doesn't lose the trigger — next tick re-evaluates against the cache.
    last_responded_seq: int = 0
    roster: dict[str, str] = field(default_factory=dict)
    roster_bios: dict[str, str] = field(default_factory=dict)
    roster_voices: dict[str, str] = field(default_factory=dict)
    last_dispatch_at: str = ""
    recent_posts: list[dict] = field(default_factory=list)

    def latest_version(self) -> int:
        if not self.sealed_keys:
            return 0
        return max(sk.version for sk in self.sealed_keys)

    def sealed_for(self, version: int) -> str | None:
        for sk in self.sealed_keys:
            if sk.version == version:
                return sk.sealed
        return None

    def upsert_key(self, version: int, sealed: str) -> None:
        """Add or replace the sealed key for `version`."""
        for i, sk in enumerate(self.sealed_keys):
            if sk.version == version:
                self.sealed_keys[i] = SealedKey(version=version, sealed=sealed)
                return
        self.sealed_keys.append(SealedKey(version=version, sealed=sealed))

    def append_recent(self, posts: list[dict]) -> None:
        """Deduplicate decrypted posts by seq and trim the cache."""
        if not posts:
            return
        merged: dict[int, dict] = {int(p["seq"]): p for p in self.recent_posts}
        for p in posts:
            merged[int(p["seq"])] = p
        ordered = sorted(merged.values(), key=lambda x: int(x["seq"]))
        self.recent_posts = ordered[-RECENT_POSTS_CACHE:]


def path(home: Path) -> Path:
    return home / _SECRETS_DIR / _FILENAME


def load(home: Path) -> list[Subscription]:
    p = path(home)
    if not p.exists():
        return []
    try:
        raw = yaml.safe_load(p.read_text()) or []
    except yaml.YAMLError:
        return []
    if not isinstance(raw, list):
        return []
    out: list[Subscription] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        try:
            sub = Subscription(
                wg_id=str(entry["wg_id"]),
                name=str(entry.get("name") or ""),
                hub_id=str(entry["hub_id"]),
                hub_pubkey=str(entry["hub_pubkey"]),
                last_seq=int(entry.get("last_seq", 0)),
                joined_at=str(entry.get("joined_at") or ""),
                last_dispatch_at=str(entry.get("last_dispatch_at") or ""),
                briefing=str(entry.get("briefing") or ""),
                pipeline=coerce_pipeline(entry.get("pipeline")),
                paused=bool(entry.get("paused", False)),
                last_responded_seq=int(entry.get("last_responded_seq", 0)),
                roster=dict(entry.get("roster") or {}),
                roster_bios=dict(entry.get("roster_bios") or {}),
                roster_voices=dict(entry.get("roster_voices") or {}),
            )
        except KeyError:
            continue
        for sk in entry.get("sealed_keys") or []:
            if not isinstance(sk, dict):
                continue
            try:
                sub.sealed_keys.append(SealedKey(
                    version=int(sk["version"]),
                    sealed=str(sk["sealed"]),
                ))
            except (KeyError, TypeError, ValueError):
                continue
        for p in entry.get("recent_posts") or []:
            if not isinstance(p, dict):
                continue
            if "seq" not in p or "text" not in p:
                continue
            sub.recent_posts.append(dict(p))
        out.append(sub)
    return out


def save(home: Path, subs: list[Subscription]) -> None:
    p = path(home)
    p.parent.mkdir(parents=True, exist_ok=True)
    data: list[dict[str, Any]] = []
    for s in subs:
        entry: dict[str, Any] = {
            "wg_id": s.wg_id,
            "name": s.name,
            "hub_id": s.hub_id,
            "hub_pubkey": s.hub_pubkey,
            "last_seq": s.last_seq,
            "sealed_keys": [asdict(sk) for sk in s.sealed_keys],
        }
        if s.joined_at:
            entry["joined_at"] = s.joined_at
        if s.last_dispatch_at:
            entry["last_dispatch_at"] = s.last_dispatch_at
        if s.briefing:
            entry["briefing"] = s.briefing
        if s.pipeline:
            entry["pipeline"] = list(s.pipeline)
        if s.paused:
            entry["paused"] = True
        if s.last_responded_seq:
            entry["last_responded_seq"] = s.last_responded_seq
        if s.roster:
            entry["roster"] = s.roster
        if s.roster_bios:
            entry["roster_bios"] = s.roster_bios
        if s.roster_voices:
            entry["roster_voices"] = s.roster_voices
        if s.recent_posts:
            entry["recent_posts"] = s.recent_posts
        data.append(entry)
    p.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))
    try:
        os.chmod(p, 0o600)
    except OSError:
        pass


def get(home: Path, wg_id: str) -> Subscription | None:
    for s in load(home):
        if s.wg_id == wg_id:
            return s
    return None


def upsert(home: Path, sub: Subscription) -> None:
    subs = load(home)
    for i, s in enumerate(subs):
        if s.wg_id == sub.wg_id:
            subs[i] = sub
            save(home, subs)
            return
    subs.append(sub)
    save(home, subs)


def remove(home: Path, wg_id: str) -> bool:
    subs = load(home)
    keep = [s for s in subs if s.wg_id != wg_id]
    if len(keep) == len(subs):
        return False
    save(home, keep)
    return True


def decrypt_post(
    sub: Subscription, kp: Keypair, post: dict[str, Any],
) -> bytes:
    """Decrypt one post; raises KeyError if we don't hold the sealed key for its version."""
    version = int(post.get("key_version", 1))
    sealed = sub.sealed_for(version)
    if sealed is None:
        raise KeyError(f"no sealed key for version {version}")
    group_key = wg_mod.open_sealed_group_key(sealed, kp)
    return wg_mod.decrypt_post(group_key, post["nonce"], post["ciphertext"])
