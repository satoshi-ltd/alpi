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

import contextlib
import copy
import logging as _logging
import math
import os
import re
import sys
import threading
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

import yaml

from alpi import yamlfast
from alpi.alp.keys import Keypair
from alpi.alp import workgroup as wg_mod

if sys.platform == "win32":
    import msvcrt
    _fcntl = None
else:
    import fcntl as _fcntl
    msvcrt = None


_SECRETS_DIR = "alp/secrets"
_FILENAME = "subscriptions.yaml"
_RETIRED_FILENAME = "subscriptions.retired.yaml"
_TOMBSTONES_DIR = "subscriptions.removed.d"
_TOMBSTONE_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")

_log = _logging.getLogger("alpi.alp.subscription")
# Warn-once: load() runs every poller tick, and the next save() drops the entry permanently.
_warned_skipped: set[str] = set()


@dataclass
class SealedKey:
    version: int
    sealed: str            # base64 ECIES blob (open with our Ed25519 priv)


RECENT_POSTS_CACHE = 20  # last N posts cached locally for engine context
DISPATCH_COOLDOWN_SECONDS = 60  # min gap between auto-dispatches per workgroup


def coerce_phase_map(value: Any) -> dict[str, dict[str, Any]]:
    """Keep only member-safe phase routing and write-boundary metadata."""
    if not isinstance(value, dict):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for phase, spec in value.items():
        if not isinstance(spec, dict):
            continue
        owner = str(spec.get("owner") or "").strip()
        if not owner:
            continue
        entry: dict[str, Any] = {"owner": owner}
        task = str(spec.get("task") or "").strip()
        if task:
            entry["task"] = task
        try:
            budget = int(spec.get("turn_budget_s") or 0)
        except (TypeError, ValueError):
            budget = 0
        if budget > 0:
            entry["turn_budget_s"] = budget
        paths = spec.get("paths")
        cwd = str(spec.get("cwd") or "").strip()
        if isinstance(paths, list) and all(isinstance(item, str) for item in paths):
            entry["paths"] = [item for item in paths if item.strip()]
            entry["cwd"] = cwd
        out[str(phase)] = entry
    return out


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
    # Mirror of the hub's named chains (join/pull) — definitions only, never gate commands.
    pipelines: dict[str, tuple[str, ...]] = field(default_factory=dict)
    launch_pipeline: str | None = None
    # Explicit so member behavior never depends on a launch pipeline existing; `pipeline_mode` → longer production turn budget.
    pipeline_mode: bool = False
    # Safe projection of the hub's phase routing and write boundaries.
    phase_map: dict[str, dict[str, Any]] = field(default_factory=dict)
    # Mirror of hub's `meta.paused` (join/pull); True → the member poller skips dispatch (no wasted turns on a paused wg).
    paused: bool = False
    # Decoupled from ``last_seq`` so a tick that pulls a new post but skips on cooldown doesn't lose the trigger — next tick re-evaluates against the cache.
    last_responded_seq: int = 0
    roster: dict[str, str] = field(default_factory=dict)
    roster_bios: dict[str, str] = field(default_factory=dict)
    roster_voices: dict[str, str] = field(default_factory=dict)
    last_dispatch_at: str = ""
    recent_posts: list[dict] = field(default_factory=list)

    @property
    def launch_chain(self) -> tuple[str, ...]:
        return self.pipelines.get(self.launch_pipeline or "", ())

    def absorb_pipeline_state(self, raw: dict[str, Any]) -> None:
        try:
            pipelines, launch = wg_mod.pipelines_from_raw(raw)
        except ValueError:
            pipelines, launch = {}, None
        self.pipelines = pipelines
        self.launch_pipeline = launch
        mode = raw.get("pipeline_mode")
        self.pipeline_mode = bool(mode) if mode is not None else bool(pipelines)
        self.phase_map = coerce_phase_map(raw.get("phase_map"))

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
        window = ordered[-RECENT_POSTS_CACHE:]
        # The dispatched child rebuilds its task from this window alone, so trimming the opener out launches a turn that cannot see what it was asked to do.
        opener = _active_opener(ordered, self.hub_pubkey)
        if opener is not None and all(
            int(p.get("seq", 0)) != int(opener.get("seq", 0)) for p in window
        ):
            window = [opener, *window]
        self.recent_posts = window


def _active_opener(posts: list[dict], hub_pubkey: str | None) -> dict | None:
    from alpi.alp import tasks as wg_tasks

    # An empty hub_pubkey makes parse_post reject every author, so no task ever reads as open — pass None, never "".
    task = wg_tasks.active_task(posts, hub_pubkey=hub_pubkey or None)
    if task is None:
        return None
    return next(
        (p for p in posts if int(p.get("seq", 0)) == int(task.opened_seq)), None,
    )


def path(home: Path) -> Path:
    return home / _SECRETS_DIR / _FILENAME


@contextlib.contextmanager
def _locked(home: Path) -> Iterator[None]:
    lock_path = path(home).with_suffix(".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    f = open(lock_path, "w")
    try:
        if sys.platform == "win32":
            msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
        else:
            _fcntl.flock(f.fileno(), _fcntl.LOCK_EX)
        yield
    finally:
        try:
            if sys.platform == "win32":
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                _fcntl.flock(f.fileno(), _fcntl.LOCK_UN)
        finally:
            f.close()


def _tombstones_dir(home: Path) -> Path:
    return home / _SECRETS_DIR / _TOMBSTONES_DIR


def tombstones(home: Path) -> set[str]:
    try:
        return set(os.listdir(_tombstones_dir(home)))
    except OSError:
        return set()


def tombstone(home: Path, wg_id: str) -> None:
    """One atomic marker file per id (no read-modify-write to race, no eviction ever); load() hides and save() drops marked ids in every process."""
    if not _TOMBSTONE_ID_RE.match(wg_id or ""):
        return
    d = _tombstones_dir(home)
    d.mkdir(mode=0o700, parents=True, exist_ok=True)
    (d / wg_id).touch()
    _invalidate_cache(path(home))


def revive(home: Path, wg_id: str) -> None:
    """A deliberate re-join lifts the tombstone; a stale write-back never calls this."""
    if not _TOMBSTONE_ID_RE.match(wg_id or ""):
        return
    try:
        (_tombstones_dir(home) / wg_id).unlink()
    except OSError:
        return
    _invalidate_cache(path(home))


# pollers call load() 4-5x per pull on the event loop — without this mtime cache the YAML parse starves it
_raw_cache: dict[str, tuple[tuple[int, int], list]] = {}
_raw_cache_lock = threading.Lock()


_CACHE_MAX_DEPTH = 32
_UNCACHEABLE = object()
# Redundant while atomic_write_yaml stays libyaml-only (it round trips both); kept so a lossy writer could only ever cost a re-parse, never a wrong cache hit.
_STR_UNCACHEABLE = re.compile("[\x85\ud800-\udfff]")


# Only types whose YAML round trip is exact may be cached; anything else must force a re-parse or the cache would serve values the file does not hold.
def _cacheable_copy(value: Any, depth: int = 0) -> Any:
    if depth > _CACHE_MAX_DEPTH:
        return _UNCACHEABLE
    if isinstance(value, str):
        return _UNCACHEABLE if _STR_UNCACHEABLE.search(value) else value
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else _UNCACHEABLE
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            if not isinstance(k, str):
                return _UNCACHEABLE
            copied = _cacheable_copy(v, depth + 1)
            if copied is _UNCACHEABLE:
                return _UNCACHEABLE
            out[k] = copied
        return out
    if isinstance(value, (list, tuple)):
        items: list[Any] = []
        for item in value:
            copied = _cacheable_copy(item, depth + 1)
            if copied is _UNCACHEABLE:
                return _UNCACHEABLE
            items.append(copied)
        return items
    return _UNCACHEABLE


def _detached_dict(value: Any) -> dict:
    if not isinstance(value, dict):
        return {}
    copied = _cacheable_copy(value)
    return copied if copied is not _UNCACHEABLE else copy.deepcopy(value)


def _invalidate_cache(p: Path) -> None:
    with _raw_cache_lock:
        _raw_cache.pop(str(p), None)


def _cache_after_write(p: Path, data: list) -> None:
    snapshot = _cacheable_copy(data)
    if snapshot is _UNCACHEABLE:
        _invalidate_cache(p)
        return
    try:
        st = p.stat()
    except OSError:
        _invalidate_cache(p)
        return
    with _raw_cache_lock:
        _raw_cache[str(p)] = ((st.st_mtime_ns, st.st_size), snapshot)


def _read_raw(p: Path) -> list:
    try:
        st = p.stat()
    except OSError:
        return []
    stamp = (st.st_mtime_ns, st.st_size)
    key = str(p)
    with _raw_cache_lock:
        hit = _raw_cache.get(key)
        if hit is not None and hit[0] == stamp:
            return hit[1]
    try:
        raw = yamlfast.safe_load(p.read_text()) or []
    except (OSError, yaml.YAMLError):
        return []
    if not isinstance(raw, list):
        return []
    try:
        st = p.stat()
    except OSError:
        return raw
    # A write that landed while we parsed already cached its own snapshot; installing this older parse would silently undo the write-through.
    if (st.st_mtime_ns, st.st_size) != stamp:
        return raw
    with _raw_cache_lock:
        _raw_cache[key] = (stamp, raw)
    return raw


def _from_entry(home: Path, entry: Any, dead: set[str]) -> Subscription | None:
    if not isinstance(entry, dict):
        return None
    if str(entry.get("wg_id") or "") in dead:
        return None
    try:
        pipelines, launch = wg_mod.pipelines_from_raw(entry)
    except ValueError as e:
        wg_id = str(entry.get("wg_id") or "?")
        key = f"{home}:{wg_id}"
        if key not in _warned_skipped:
            _warned_skipped.add(key)
            _log.warning("subscription %s skipped (dropped on next save): %s", wg_id, e)
        return None
    declared_mode = entry.get("pipeline_mode")
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
            pipelines=pipelines,
            launch_pipeline=launch,
            pipeline_mode=(
                bool(declared_mode) if declared_mode is not None
                else bool(pipelines)
            ),
            phase_map=coerce_phase_map(entry.get("phase_map")),
            paused=bool(entry.get("paused", False)),
            last_responded_seq=int(entry.get("last_responded_seq", 0)),
            roster=_detached_dict(entry.get("roster")),
            roster_bios=_detached_dict(entry.get("roster_bios")),
            roster_voices=_detached_dict(entry.get("roster_voices")),
        )
    except KeyError:
        return None
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
    for post in entry.get("recent_posts") or []:
        if not isinstance(post, dict):
            continue
        if "seq" not in post or "text" not in post:
            continue
        sub.recent_posts.append(_detached_dict(post))
    return sub


def load(home: Path) -> list[Subscription]:
    p = path(home)
    if not p.exists():
        return []
    raw = _read_raw(p)
    dead = tombstones(home)
    out: list[Subscription] = []
    for entry in raw:
        sub = _from_entry(home, entry, dead)
        if sub is not None:
            out.append(sub)
    return out


def _entry(s: Subscription) -> dict[str, Any]:
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
    if s.pipelines:
        entry["pipelines"] = {k: list(v) for k, v in s.pipelines.items()}
    if s.launch_pipeline:
        entry["launch_pipeline"] = s.launch_pipeline
    if s.pipeline_mode:
        entry["pipeline_mode"] = True
    if s.phase_map:
        entry["phase_map"] = s.phase_map
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
    return entry


PRESENCE_BUCKET_SECONDS = 120


def _presence_bucket(stamp: Any) -> Any:
    import datetime as _dt

    try:
        seen = _dt.datetime.strptime(str(stamp), "%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError):
        return str(stamp)
    epoch = seen.replace(tzinfo=_dt.timezone.utc).timestamp()
    return int(epoch) // PRESENCE_BUCKET_SECONDS


def persisted_signature(s: Subscription) -> str:
    entry = _entry(s)
    roster = entry.get("roster")
    if roster:
        # Bucket, never raw (hub restamps every pull, so the file rewrites every tick) and never dropped (mirror freezes, healthy peers render offline).
        entry["roster"] = sorted(
            (str(pk), _presence_bucket(ts)) for pk, ts in roster.items()
        )
    return repr(entry)


def _save_unsafe(home: Path, subs: list[Subscription]) -> None:
    from alpi.config import atomic_write_yaml

    p = path(home)
    dead = tombstones(home)
    data: list[dict[str, Any]] = [
        _entry(s) for s in subs if s.wg_id not in dead
    ]
    atomic_write_yaml(p, data)
    # Correctness rests on the caller holding _locked(home): an unlocked foreign write landing between the replace and the stat would stamp our data with their file.
    _cache_after_write(p, data)


def save(home: Path, subs: list[Subscription]) -> None:
    with _locked(home):
        _save_unsafe(home, subs)


def compact(home: Path) -> None:
    with _locked(home):
        _save_unsafe(home, load(home))


def update(
    home: Path,
    mutator: Callable[[list[Subscription]], list[Subscription] | None],
) -> list[Subscription]:
    with _locked(home):
        subs = load(home)
        result = mutator(subs)
        if result is None:
            return subs
        _save_unsafe(home, result)
        return result


# Never `for s in load(home)`: pollers call this 2-3x per pull and load() would build every subscription in the file to answer one lookup.
def get(home: Path, wg_id: str) -> Subscription | None:
    p = path(home)
    if not p.exists():
        return None
    dead: set[str] | None = None
    for entry in _read_raw(p):
        if not isinstance(entry, dict):
            continue
        # Must build the id exactly as load() does, or a falsy-but-real id resolves in one and not the other.
        if "wg_id" not in entry or str(entry["wg_id"]) != wg_id:
            continue
        if dead is None:
            dead = tombstones(home)
        sub = _from_entry(home, entry, dead)
        if sub is not None:
            return sub
    return None


def _merge_archived_keys(entries: list[dict[str, Any]], sub: Subscription) -> bool:
    found = False
    for entry in entries:
        if str(entry.get("wg_id") or "") != sub.wg_id:
            continue
        found = True
        for raw in entry.get("sealed_keys") or []:
            if not isinstance(raw, dict):
                continue
            version = int(raw.get("version", 0) or 0)
            sealed = str(raw.get("sealed") or "")
            if version and sealed and sub.sealed_for(version) is None:
                sub.upsert_key(version, sealed)
    return found


def upsert(home: Path, sub: Subscription) -> None:
    from alpi.config import atomic_write_yaml

    # Reclaim, active save and archive cleanup share ONE lock: a retire() slipping between the last two would archive the restored keys and then see them deleted, losing both copies.
    with _locked(home):
        entries = _archive_entries(retired_path(home))
        reclaimed = _merge_archived_keys(entries, sub)
        subs = load(home)
        for i, existing in enumerate(subs):
            if existing.wg_id == sub.wg_id:
                if existing != sub:
                    subs[i] = sub
                    _save_unsafe(home, subs)
                break
        else:
            subs.append(sub)
            _save_unsafe(home, subs)
        # Only once the active file holds them: crashing here duplicates the entry, the reverse order loses the keys.
        if reclaimed:
            atomic_write_yaml(
                retired_path(home),
                [e for e in entries if str(e.get("wg_id") or "") != sub.wg_id],
            )


def mutate(
    home: Path,
    wg_id: str,
    mutator: Callable[[Subscription], bool],
) -> Subscription | None:
    with _locked(home):
        # Full load only once the mutator says it changed something: a no-change tick must not pay for every other subscription in the file.
        sub = get(home, wg_id)
        if sub is None:
            return None
        if not mutator(sub):
            return sub
        subs = load(home)
        for i, existing in enumerate(subs):
            if existing.wg_id == wg_id:
                subs[i] = sub
                break
        else:
            return sub
        _save_unsafe(home, subs)
        return sub


def remove(home: Path, wg_id: str) -> bool:
    removed = [False]

    def _mutate(subs: list[Subscription]) -> list[Subscription] | None:
        keep = [s for s in subs if s.wg_id != wg_id]
        if len(keep) == len(subs):
            return None
        removed[0] = True
        return keep

    update(home, _mutate)
    return removed[0]


def retired_path(home: Path) -> Path:
    return home / _SECRETS_DIR / _RETIRED_FILENAME


def retired(home: Path) -> set[str]:
    return {
        str(e.get("wg_id") or "") for e in _archive_entries(retired_path(home))
    } - {""}


def _archive_entries(p: Path) -> list[dict[str, Any]]:
    if not p.exists():
        return []
    try:
        raw = yamlfast.safe_load(p.read_text()) or []
    except (OSError, yaml.YAMLError):
        return []
    if not isinstance(raw, list):
        return []
    return [e for e in raw if isinstance(e, dict)]


def retire(home: Path, wg_id: str) -> bool:
    """Archive one subscription's entry, sealed keys and all, then drop it from the active file — a retirement inferred from a hub error must cost a re-join, never the keys."""
    from alpi.config import atomic_write_yaml

    with _locked(home):
        subs = load(home)
        doomed = next((s for s in subs if s.wg_id == wg_id), None)
        if doomed is None:
            return False
        p = retired_path(home)
        kept = [e for e in _archive_entries(p) if e.get("wg_id") != wg_id]
        # Archive before dropping: crashing between the two duplicates the entry, the reverse order loses it.
        atomic_write_yaml(p, [*kept, _entry(doomed)])
        _save_unsafe(home, [s for s in subs if s.wg_id != wg_id])
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
