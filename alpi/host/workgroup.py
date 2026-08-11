from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from alpi.alp import subscription as sub_mod
from alpi.alp import workgroup as wg_mod
from alpi.alp.keys import load_or_generate


def decrypt_transcript(
    home: Path,
    wg_id: str,
    *,
    after_seq: int | None = None,
    limit: int | None = None,
    tail: bool = False,
) -> list[dict[str, Any]]:
    """Return decrypted transcript posts, oldest-first.

    Pagination is mandatory once a transcript grows past a few hundred posts:
    decrypt cost is per-post (libsodium AEAD + JSON parse), so even with the
    group key opened once the linear walk dominates for chatty hubs. Callers
    pass ``after_seq`` for incremental updates or ``tail=True`` with ``limit``
    for first-paint of a large transcript.
    """
    raw = _read_jsonl(home, wg_id)
    if not raw:
        return []

    if after_seq is not None:
        raw = [p for p in raw if int(p.get("seq", 0)) > int(after_seq)]
        if not raw:
            return []
    if tail and limit is not None and limit > 0 and len(raw) > limit:
        raw = raw[-limit:]
    elif limit is not None and limit > 0 and len(raw) > limit:
        raw = raw[:limit]

    kp = load_or_generate(home)

    hub_dir = home / "alp" / "workgroups" / wg_id
    if (hub_dir / "members.yaml").exists():
        return _decrypt_as_hub(home, wg_id, kp, raw)

    sub = sub_mod.get(home, wg_id)
    if sub is not None:
        return _decrypt_as_member(sub, kp, raw)

    return []


def _hub_pubkey(home: Path, wg_id: str) -> str:
    wg = wg_mod.load(home, wg_id)
    if wg is not None:
        return wg.meta.hub_pubkey
    sub = sub_mod.get(home, wg_id)
    return sub.hub_pubkey if sub is not None else ""


@dataclass(frozen=True)
class _Defs:
    """The pipeline definitions the fold needs, from hub meta or member subscription state."""
    pipelines: dict[str, tuple[str, ...]] = field(default_factory=dict)
    launch_pipeline: str | None = None
    pipeline_steps: dict = field(default_factory=dict)


def pipeline_defs(home: Path, wg_id: str) -> _Defs:
    wg = wg_mod.load(home, wg_id)
    if wg is not None:
        return _Defs(
            pipelines=wg.meta.pipelines,
            launch_pipeline=wg.meta.launch_pipeline,
            pipeline_steps=wg_mod.safe_phase_map(wg.meta),
        )
    sub = sub_mod.get(home, wg_id)
    if sub is not None:
        return _Defs(
            pipelines=sub.pipelines,
            launch_pipeline=sub.launch_pipeline,
            pipeline_steps=dict(sub.phase_map),
        )
    return _Defs()


_SKIPPED_RE = re.compile(r"^skipped\s*·\s*\S", re.IGNORECASE)


def _attempt_state(task) -> str:
    if task.is_open:
        return "current"
    result = (task.result or "").strip()
    if result.upper().startswith("BLOCKED"):
        return "blocked"
    if result.lower().startswith("preempted"):
        return "preempted"
    if _SKIPPED_RE.match(result):
        return "skipped"
    return "completed"


def _fold_pipeline_run(defs: _Defs, ordered) -> dict[str, Any] | None:
    """Boundaries, not first-slug occurrences: a same-slug reopen (first phase included) is another attempt in the current run; a first-phase opener that finds the run elsewhere restarts."""
    if not defs.pipelines or not ordered:
        return None
    run: dict[str, Any] | None = None
    for task in ordered:
        mapped = wg_mod.canonical_pipeline_phase(defs, task.slug)
        if mapped is None:
            continue
        key, phase = mapped
        chain = defs.pipelines[key]
        restart = (
            run is None
            or run["pipeline"] != key
            or (phase == chain[0] and run["current_phase"] != chain[0])
        )
        if restart:
            run = {
                "pipeline": key,
                "status": "running",
                "started_seq": int(task.opened_seq or 0),
                "current_phase": phase,
                "states": {},
                "seqs": {},
            }
        state = _attempt_state(task)
        run["current_phase"] = phase
        run["states"][phase] = state
        run["seqs"][phase] = int(
            (task.opened_seq if task.is_open else task.closed_seq) or 0,
        )
        if state == "current":
            run["status"] = "running"
        elif state == "blocked":
            run["status"] = "blocked"
        elif state == "preempted":
            run["status"] = "between"
        elif phase == chain[-1]:
            run["status"] = "completed"
        else:
            run["status"] = "between"
    if run is None:
        return None
    latest = max(ordered, key=lambda t: int(t.opened_seq or 0))
    if wg_mod.canonical_pipeline_phase(defs, latest.slug) is None:
        return None
    chain = defs.pipelines[run["pipeline"]]
    phases = []
    for slug in chain:
        state = run["states"].get(slug, "pending")
        if state == "blocked":
            state = "current"
        elif state == "preempted":
            state = "pending"
        phases.append({"slug": slug, "state": state, "seq": run["seqs"].get(slug)})
    return {
        "pipeline": run["pipeline"],
        "status": run["status"],
        "started_seq": run["started_seq"],
        "current_phase": run["current_phase"],
        "phases": phases,
    }


_FOLD_CACHE: dict[str, tuple[tuple, dict[str, Any]]] = {}
_FOLD_CACHE_LOCK = threading.Lock()
_FOLD_CACHE_CAP = 64


def _fold_stamp(home: Path, wg_id: str, defs: _Defs) -> tuple:
    # Definitions join the stamp so a metadata edit can never serve a stale phase mapping.
    p = home / "alp" / "workgroups" / wg_id / "transcript.jsonl"
    try:
        st = p.stat()
        identity = (st.st_mtime_ns, st.st_size)
    except OSError:
        identity = (0, 0)
    return (
        identity,
        json.dumps(
            [
                {k: list(v) for k, v in sorted(defs.pipelines.items())},
                defs.launch_pipeline,
                {k: defs.pipeline_steps[k] for k in sorted(defs.pipeline_steps)},
            ],
            sort_keys=True, ensure_ascii=False,
        ),
    )


def fold_task_state(home: Path, wg_id: str) -> dict[str, Any]:
    # Canonical host-side fold (active/closed/blocked/pipeline_run); the apps consume it, they do not re-derive which pipeline is active.
    from alpi.alp import tasks as wg_tasks

    defs = pipeline_defs(home, wg_id)
    stamp = _fold_stamp(home, wg_id, defs)
    cache_key = str(home / "alp" / "workgroups" / wg_id)
    with _FOLD_CACHE_LOCK:
        hit = _FOLD_CACHE.get(cache_key)
        if hit is not None and hit[0] == stamp:
            return hit[1]

    posts = decrypt_transcript(home, wg_id)
    if not posts:
        return _cache_fold(
            cache_key, stamp,
            {"active": None, "closed": [], "blocked": None, "pipeline_run": None},
        )
    hub_pubkey = _hub_pubkey(home, wg_id)
    events: list = []
    for p in posts:
        events += wg_tasks.parse_post(
            str(p.get("body") or ""), int(p.get("seq", 0)),
            str(p.get("from_pubkey") or ""), hub_pubkey=hub_pubkey or None,
        )
    ledger = wg_tasks.fold_tasks(events)
    active: dict[str, Any] | None = None
    closed: list[dict[str, Any]] = []
    for t in ledger:
        if t.is_open:
            active = {"slug": t.slug, "title": t.description, "opened_seq": t.opened_seq}
        else:
            closed.append({
                "slug": t.slug,
                "result": t.result or "",
                "closed_seq": t.closed_seq,
                "blocked": (t.result or "").strip().upper().startswith("BLOCKED"),
            })
    # Only blocked when nothing was re-tasked after the BLOCKED close — a later
    # #task (active) means a human moved it on (matches mobile findBlocked).
    blocked = None
    if active is None and closed:
        latest = max(closed, key=lambda c: c["closed_seq"] or 0)
        if latest["blocked"]:
            blocked = {"slug": latest["slug"], "reason": latest["result"]}
    ordered = sorted(ledger, key=lambda t: int(t.opened_seq or 0))
    out = {
        "active": active,
        "closed": closed[-20:],
        "blocked": blocked,
        "pipeline_run": _fold_pipeline_run(defs, ordered),
    }
    return _cache_fold(cache_key, stamp, out)


def _cache_fold(key: str, stamp: tuple, out: dict[str, Any]) -> dict[str, Any]:
    with _FOLD_CACHE_LOCK:
        if len(_FOLD_CACHE) >= _FOLD_CACHE_CAP:
            _FOLD_CACHE.pop(next(iter(_FOLD_CACHE)))
        _FOLD_CACHE[key] = (stamp, out)
    return out


def _read_jsonl(home: Path, wg_id: str) -> list[dict[str, Any]]:
    p = home / "alp" / "workgroups" / wg_id / "transcript.jsonl"
    if not p.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in p.read_text(encoding="utf-8").splitlines():
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


def _decrypt_as_hub(
    home: Path, wg_id: str, kp, raw: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    wg = wg_mod.load(home, wg_id)
    if wg is None:
        return []
    me = wg.member(kp.pubkey_b64())
    if me is None:
        return []
    # All versions the hub can open (current + rekey history): unsealed once each,
    # so posts written before a leave/kick rotation still decrypt instead of blanking.
    keys = wg_mod.hub_group_keys(home, wg, kp)

    handles = _handle_map(home, wg)
    out: list[dict[str, Any]] = []
    for post in raw:
        v = int(post.get("key_version", 1))
        sender_pk = str(post.get("from") or "")
        group_key = keys.get(v)
        if group_key is None:
            body = f"[v{v} key rotated out of hub state]"
        else:
            try:
                body = wg_mod.decrypt_post(
                    group_key, post["nonce"], post["ciphertext"],
                ).decode("utf-8", errors="replace")
            except Exception as e:  # noqa: BLE001
                body = f"[decrypt failed: {e}]"
        out.append(_envelope(post, sender_pk, handles.get(sender_pk, ""), body))
    return out


def _decrypt_as_member(
    sub, kp, raw: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for post in raw:
        sender_pk = str(post.get("from") or "")
        try:
            body = sub_mod.decrypt_post(sub, kp, post).decode(
                "utf-8", errors="replace",
            )
        except Exception as e:  # noqa: BLE001
            body = f"[decrypt failed: {e}]"
        out.append(_envelope(post, sender_pk, "", body))
    return out


def _handle_map(home: Path, wg) -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        from alpi.alp import peers as peers_mod

        for p in peers_mod.load(home):
            out[p.pubkey] = f"@{p.id}"
    except Exception:  # noqa: BLE001
        pass
    try:
        from alpi.alp.keys import load_or_generate as _load

        kp = _load(home)
        out.setdefault(kp.pubkey_b64(), f"@{_local_handle(home)}")
    except Exception:  # noqa: BLE001
        pass
    return out


def _local_handle(home: Path) -> str:
    parts = home.parts
    if "profiles" in parts:
        i = parts.index("profiles")
        if i + 1 < len(parts):
            return parts[i + 1]
    return "default"


def _envelope(
    post: dict[str, Any], sender_pk: str, handle: str, body: str,
) -> dict[str, Any]:
    return {
        "seq": int(post.get("seq", 0)),
        "at": str(post.get("ts") or ""),
        "from_pubkey": sender_pk,
        "from": handle,
        "body": body,
        "key_version": int(post.get("key_version", 1)),
        "cost": post.get("cost") or {},
        "turn_id": str(post.get("turn_id") or ""),
    }
