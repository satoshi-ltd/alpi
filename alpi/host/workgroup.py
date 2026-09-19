from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from alpi.alp import subscription as sub_mod
from alpi.alp import tasks as wg_tasks
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


def _attempt_state(task) -> str:
    if task.is_open:
        return "current"
    result = (task.result or "").strip()
    override = wg_tasks.close_override_kind(result)
    if override == "blocked":
        return "blocked"
    if result.lower().startswith("preempted"):
        return "preempted"
    if override == "skipped":
        return "skipped"
    return "completed"


def _num(value: Any, cast, floor):
    try:
        return max(floor, cast(value))
    except (TypeError, ValueError):
        return floor


def _zero_cost() -> dict[str, Any]:
    return {"usd": 0.0, "tokens": 0, "tokens_in": 0, "tokens_out": 0}


def _add_cost(into: dict[str, Any], cost: Any) -> None:
    if not isinstance(cost, dict):
        return
    into["usd"] = round(into["usd"] + _num(cost.get("usd"), float, 0.0), 6)
    for key in ("tokens", "tokens_in", "tokens_out"):
        into[key] += _num(cost.get(key), int, 0)


def _charges(posts: list[dict[str, Any]], settlements: Any) -> list[tuple[int, Any]]:
    """Every cost in the transcript placed on a seq, so a phase span can own it.

    A settlement carries the residual an author did not declare on its posts. The
    ledger keys a turn by ``(from, turn_id)`` and so does this, or two authors that
    happened to pick the same turn id would both land on whichever posted first. It
    is placed on that author's first post of the turn; a turn that settled without
    ever posting cannot be placed on the timeline and is left out rather than
    guessed onto a phase.
    """
    out = [(int(p.get("seq", 0)), p.get("cost")) for p in posts]
    first_seq: dict[tuple[str, str], int] = {}
    for p in posts:
        turn = str(p.get("turn_id") or "")
        if not turn:
            continue
        key = (str(p.get("from_pubkey") or ""), turn)
        seq = int(p.get("seq", 0))
        if seq < first_seq.get(key, seq + 1):
            first_seq[key] = seq
    if isinstance(settlements, list):
        for row in settlements:
            if not isinstance(row, dict):
                continue
            seq = first_seq.get(
                (str(row.get("from") or ""), str(row.get("turn_id") or "")),
            )
            if seq is not None:
                out.append((seq, row.get("cost")))
    return out


def _span_costs(
    charges: list[tuple[int, Any]], spans: list[tuple[str, int, int | None, bool]],
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Split the run's seq line at each attempt's opener so no charge is counted twice.

    An attempt ends the seq before the next one opens — a preemption closes one phase
    and opens the next on the SAME post, so an inclusive end would charge it to both.
    The final attempt stops at its own close, or runs open-ended while it is still open.
    """
    per_phase: dict[str, dict[str, Any]] = {}
    total = _zero_cost()
    for i, (slug, start, closed, preempted) in enumerate(spans):
        if closed is None:
            # Only the last attempt is open in a well-formed ledger; cap a stray one at
            # the next opener rather than let it swallow the rest of the transcript.
            end = spans[i + 1][1] - 1 if i + 1 < len(spans) else None
        else:
            # A closed attempt owns nothing past its close, or an ad-hoc task opened
            # between two phases would bill to the phase before it. A preempted attempt
            # has no close post of its own — what closed it IS the next task's opener,
            # which may be outside the chain and so absent from these spans entirely.
            end = closed - 1 if preempted else closed
        bucket = per_phase.setdefault(slug, _zero_cost())
        for seq, cost in charges:
            if seq >= start and (end is None or seq <= end):
                _add_cost(bucket, cost)
                _add_cost(total, cost)
    return per_phase, total


def _charges_and_basis(
    home: Path, wg_id: str, posts: list[dict[str, Any]],
) -> tuple[list[tuple[int, Any]], bool]:
    rows, complete = _settlements(home, wg_id)
    return _charges(posts, rows), complete


def _fold_pipeline_run(
    defs: _Defs, ordered, trigger_seqs: set[int] | None = None,
    charges: list[tuple[int, Any]] | None = None,
    cost_complete: bool = True,
) -> dict[str, Any] | None:
    """Fold pipeline attempts, using explicit operator triggers as run boundaries."""
    if not defs.pipelines or not ordered:
        return None
    trigger_seqs = trigger_seqs or set()
    has_trigger_metadata = bool(trigger_seqs)
    run: dict[str, Any] | None = None
    for task in ordered:
        mapped = wg_mod.canonical_pipeline_phase(defs, task.slug)
        if mapped is None:
            continue
        key, phase = mapped
        chain = defs.pipelines[key]
        explicit_trigger = int(task.opened_seq or 0) in trigger_seqs
        legacy_restart = (
            not has_trigger_metadata
            and run is not None
            and phase == chain[0]
            and run["current_phase"] != chain[0]
        )
        restart = run is None or run["pipeline"] != key or explicit_trigger or legacy_restart
        if restart:
            run = {
                "pipeline": key,
                "status": "running",
                "started_seq": int(task.opened_seq or 0),
                "current_phase": phase,
                "states": {},
                "seqs": {},
                "spans": [],
            }
        for downstream in chain[chain.index(phase) + 1:]:
            run["states"].pop(downstream, None)
            run["seqs"].pop(downstream, None)
        state = _attempt_state(task)
        run["current_phase"] = phase
        run["states"][phase] = state
        run["seqs"][phase] = int(
            (task.opened_seq if task.is_open else task.closed_seq) or 0,
        )
        run["spans"].append((
            phase,
            int(task.opened_seq or 0),
            None if task.is_open else int(task.closed_seq or 0),
            state == "preempted",
        ))
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
    per_phase, total = _span_costs(charges or [], run["spans"])
    phases = []
    for slug in chain:
        state = run["states"].get(slug, "pending")
        if state == "blocked":
            state = "current"
        elif state == "preempted":
            state = "pending"
        phases.append({
            "slug": slug,
            "state": state,
            "seq": run["seqs"].get(slug),
            "cost": per_phase.get(slug) or _zero_cost(),
        })
    return {
        "pipeline": run["pipeline"],
        "status": run["status"],
        "started_seq": run["started_seq"],
        "current_phase": run["current_phase"],
        "phases": phases,
        "cost": total,
        "cost_complete": cost_complete,
    }


def run_cost_label(run: dict[str, Any] | None) -> str:
    """``$0.5500 · 550 tokens`` for a run that spent anything, else empty."""
    cost = (run or {}).get("cost") or {}
    usd = _num(cost.get("usd"), float, 0.0)
    tokens = _num(cost.get("tokens"), int, 0)
    if usd <= 0 and tokens <= 0:
        return ""
    label = f"${usd:.4f} · {tokens:,} tokens"
    return label if (run or {}).get("cost_complete", True) else f"{label} (declared only)"


_FOLD_CACHE: dict[str, tuple[tuple, dict[str, Any]]] = {}
_FOLD_CACHE_LOCK = threading.Lock()
_FOLD_CACHE_CAP = 64


def _settlements(home: Path, wg_id: str) -> tuple[list, bool]:
    """The ledger rows and whether they are authoritative here.

    Settlements live only in the hub's home: a member posts its residual to the hub
    over ALP and never keeps a copy, so a member's fold can see declared post costs
    and nothing else. The flag travels with the numbers so a partial total is never
    rendered as a complete one.
    """
    d = home / "alp" / "workgroups" / wg_id
    if not (d / "members.yaml").exists():
        return [], False
    try:
        raw = json.loads((d / "ledger.json").read_text())
    except (OSError, ValueError):
        return [], False
    # A hub writes the ledger at creation, so anything that is not a readable object
    # is a ledger we cannot vouch for — partial, never a confident zero.
    if not isinstance(raw, dict):
        return [], False
    rows = raw.get("settlements")
    return (rows if isinstance(rows, list) else []), True


def _fold_stamp(home: Path, wg_id: str, defs: _Defs) -> tuple:
    # Definitions join the stamp so a metadata edit can never serve a stale phase mapping.
    d = home / "alp" / "workgroups" / wg_id
    # The ledger joins the stamp because a settlement lands after its posts: without it
    # a run's cost would be served from the fold cached before the residual was known.
    identity = []
    for name in ("transcript.jsonl", "ledger.json"):
        try:
            st = (d / name).stat()
            identity.append((st.st_mtime_ns, st.st_size))
        except OSError:
            identity.append((0, 0))
    return (
        tuple(identity),
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
                "blocked": wg_tasks.close_override_kind(t.result or "") == "blocked",
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
        "pipeline_run": _fold_pipeline_run(
            defs, ordered,
            {int(p.get("seq", 0)) for p in posts if p.get("pipeline_trigger") is True},
            *_charges_and_basis(home, wg_id, posts),
        ),
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
        "pipeline_trigger": post.get("pipeline_trigger") is True,
    }
