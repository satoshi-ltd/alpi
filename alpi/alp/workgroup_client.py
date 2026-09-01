"""Member-side workgroup helpers."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from alpi.alp import client as alp_client
from alpi.alp import peers as peers_mod
from alpi.alp import server as alp_server
from alpi.alp import subscription as sub_mod
from alpi.alp import tasks as tasks_mod
from alpi.alp import workgroup as wg_mod
from alpi.alp.keys import Keypair, load_or_generate


def _last_hub_seq(posts: list[dict], hub_pubkey: str) -> int:
    """Highest hub-authored seq in `posts`, or 0."""
    best = 0
    for p in posts:
        if str(p.get("from") or "") == hub_pubkey:
            seq = int(p.get("seq", 0))
            if seq > best:
                best = seq
    return best


def _current_round_posts(
    posts: list[dict], hub_pubkey: str,
) -> list[dict]:
    """Posts after the latest hub post."""
    cutoff = _last_hub_seq(posts, hub_pubkey)
    if cutoff == 0:
        return list(posts)
    return [p for p in posts if int(p.get("seq", 0)) > cutoff]


def _check_member_rotation(
    posts: list[dict], own_pubkey: str, hub_pubkey: str,
    plaintext: str = "", *, phase_owner: bool = False,
) -> None:
    """Reject posts that would violate member rotation."""
    round_posts = _current_round_posts(posts, hub_pubkey)
    own_in_round = [
        p for p in round_posts
        if str(p.get("from") or "") == own_pubkey
    ]
    new_is_working = tasks_mod.is_working_only(plaintext)
    prior_working = sum(
        1 for p in own_in_round
        if tasks_mod.is_working_only(str(p.get("text") or ""))
    )
    prior_consuming = len(own_in_round) - prior_working

    if new_is_working:
        if prior_working >= 1:
            raise ValueError(
                "turn-rotation: you already posted `#working` in "
                "this round. Wait until you have substantive "
                "content or `#skip` to post again."
            )
        return
    if phase_owner:
        # Rotation guards peer ping-pong, not an owner iterating on its own open phase.
        return
    if prior_consuming >= 1:
        raise ValueError(
            "turn-rotation: you already posted in the current "
            "round (since the hub's last post). Stay silent until "
            "the hub speaks again."
        )


_PHASE_TAG_RE = re.compile(r"#([a-z0-9][a-z0-9-]*)")


def _hub_named_phase(sub, own_id: str) -> str:
    """The opener scrolls out of the recent-post window in long repair sequences; the daemon's own notes still name the phase."""
    for post in reversed(list(sub.recent_posts or [])):
        if str(post.get("from") or "") != sub.hub_pubkey:
            continue
        text = str(post.get("text") or "")
        if f"@{own_id}" not in text:
            continue
        for tag in _PHASE_TAG_RE.findall(text):
            if tag in (sub.phase_map or {}):
                return tag
    return ""


def _member_owns_active_phase(sub, active, own_id: str) -> bool:
    """Only the phase's DECLARED owner iterates freely — a merely-mentioned participant keeps rotation."""
    if not (getattr(sub, "pipeline_mode", False) and own_id):
        return False
    slug = active.slug if active is not None else _hub_named_phase(sub, own_id)
    if not slug:
        return False
    canon = wg_mod.canonical_pipeline_phase(sub, slug)
    if canon is None:
        return False
    owner = str((sub.phase_map.get(canon[1]) or {}).get("owner") or "")
    return owner.lower() == own_id


def _check_member_round_fresh(
    posts: list[dict], hub_pubkey: str,
) -> None:
    """Reject stale-round posts when the dispatcher already advanced."""
    raw = os.environ.get("ALPI_WORKGROUP_ROUND_HUB_SEQ", "").strip()
    if not raw:
        return
    try:
        trigger_seq = int(raw)
    except ValueError:
        return
    current = _last_hub_seq(posts, hub_pubkey)
    if current > trigger_seq:
        raise ValueError(
            f"stale-round: the hub posted again (seq #{current}) "
            f"while this turn was thinking — your reaction was for "
            f"round seq #{trigger_seq}. Aborting; the next poller "
            f"tick will re-evaluate against fresh state."
        )


def _check_substantive(plaintext: str) -> None:
    """Reject empty posts before they burn a slot."""
    if not (plaintext or "").strip():
        raise ValueError(
            "empty post — silence in a workgroup is the absence of "
            "a workgroup_post call, not an empty post."
        )


def _check_task_shape(plaintext: str) -> None:
    """Reject `#task` posts missing the required `#<slug>` identifier."""
    if tasks_mod.has_task_intent(plaintext) and not tasks_mod.is_valid_task_open(plaintext):
        raise ValueError(
            "task-missing-slug: `#task` must be followed by `#<slug>`, "
            "e.g. `#task #adr-7 unify build pipeline`. Slug pattern: "
            "[A-Za-z0-9][A-Za-z0-9_-]{0,63}."
        )


def _check_task_slug_is_routable(wg, plaintext: str) -> None:
    """An unroutable opener leaves the run with no pipeline, so closing it advances nothing."""
    if not wg_mod.is_pipeline_workgroup(wg.meta):
        return
    opens = [
        e for e in tasks_mod.parse_post(plaintext, 0, "", hub_pubkey="")
        if e.kind == "task" and e.slug
    ]
    if not opens:
        return
    slug = opens[0].slug
    if wg_mod.canonical_pipeline_phase(wg.meta, slug) is not None:
        return
    phases = sorted({p for chain in (wg.meta.pipelines or {}).values() for p in chain})
    raise ValueError(
        f"task-slug-unroutable: `#{slug}` belongs to no declared chain, so the "
        "daemon cannot sequence it and closing it would advance nothing. Use a "
        "declared phase or a repair of one (`#<phase>`, `#<phase>-fix`). "
        f"Declared phases: {', '.join(phases)}."
    )


def _check_hub_single_marker(plaintext: str) -> None:
    """One post = one transition. A hub post carrying more than one lifecycle
    marker — `#done` + `#task`, two `#task` openers, or two `#done` closers — is
    ambiguous: parse_post drops a mixed open+close to prose, so the phase
    silently never moves and the canonical task ledger drifts from the
    transcript. Reject so the model self-corrects in the same turn."""
    if tasks_mod.marker_count(plaintext) > 1:
        raise ValueError(
            "use only one lifecycle marker per post — post a single `#done` or "
            "a single `@peer #task #slug`, then stop; open the next task in a "
            "later turn."
        )


def _check_closure_only(plaintext: str) -> None:
    if os.environ.get("ALPI_WORKGROUP_CLOSURE_ONLY") == "1" and not tasks_mod.is_done(plaintext):
        raise ValueError(
            "closure-only: this watchdog wake may only close the task "
            "(`#done …`) or stay silent — new content would reopen a "
            "stalled round."
        )


_FULL_QUORUM_TIMEOUT_SECONDS = 10 * 60


def _opener_post(
    posts: list[dict], hub_pubkey: str,
) -> dict | None:
    """Return the active `#task` opener, if any."""
    opener: dict | None = None
    for p in posts:
        if str(p.get("from") or "") != hub_pubkey:
            continue
        events = tasks_mod.parse_post(
            str(p.get("text") or ""),
            int(p.get("seq", 0)),
            str(p.get("from") or ""),
        )
        if any(e.kind == "task" for e in events):
            opener = p
        elif any(e.kind == "done" for e in events):
            opener = None
    return opener


def _quorum_roster(
    home: Path, wg, posts: list[dict], member_pubkeys: list[str],
) -> list[str]:
    """Closure-quorum roster for the active task. When the task named
    participants (opener-line mentions like ``@scout #task #intake``),
    the quorum is just those peers — members the task didn't name don't
    block the close. A collective task (no mentions) keeps the full
    roster, as before."""
    active = tasks_mod.active_task(posts, hub_pubkey=wg.meta.hub_pubkey)
    if active is None or not active.participants:
        return member_pubkeys
    wanted = {p.lower() for p in active.participants}
    roster: list[str] = []
    for pk in member_pubkeys:
        peer = peers_mod.get_by_pubkey(home, pk)
        name = (peer.id if peer else "").lower()
        if name and name in wanted:
            roster.append(pk)
    return roster or member_pubkeys


def _own_profile_id(home: Path) -> str:
    try:
        from alpi.home import profile_name
        return (profile_name(home) or "").lower()
    except Exception:  # noqa: BLE001
        return ""


def _hub_owns_phase(home: Path, wg, slug: str) -> bool:
    """A declared phase whose owner IS the hub profile: the hub is the worker, not the orchestrator."""
    owner = _workflow_phase_owner(wg, slug)
    own_id = _own_profile_id(home)
    return bool(owner and own_id and owner.lower() == own_id)


def _workflow_phase_owner(wg, slug: str) -> str:
    canonical = wg_mod.canonical_pipeline_phase(wg.meta, slug)
    if canonical is None:
        return ""
    raw = (getattr(wg.meta, "pipeline_steps", None) or {}).get(canonical[1])
    return str((raw or {}).get("owner") or "").strip() if isinstance(raw, dict) else ""


def _validate_task_participants(home: Path, wg, plaintext: str) -> None:
    """Validate a hub `#task` opener before it lands in the transcript:

    - **Unknown mention** (typo / never-joined peer) → reject; it would
      open a task that wakes nobody and can never reach quorum.
    - **Pipeline workgroup, no participants** → reject; a pipeline phase
      must be targeted at its owner(s) (`@pixel #task #build …`), not
      collective. Collective tasks stay allowed in non-pipeline (delib)
      workgroups.
    """
    events = tasks_mod.parse_post(
        plaintext, 0, wg.meta.hub_pubkey, hub_pubkey=wg.meta.hub_pubkey,
    )
    task_events = [ev for ev in events if ev.kind == "task"]
    if not task_events:
        return
    parts = [p for ev in task_events for p in ev.participants]
    if not parts:
        if wg_mod.is_pipeline_workgroup(wg.meta):
            raise ValueError(
                "pipeline-task-untargeted: in a pipeline workgroup every "
                "`#task` must name its owner(s) with `@`-mentions on the "
                "opener line (e.g. `@pixel #task #build …`, or "
                "`@pixel @atlas #task …`). A collective task would wake the "
                "whole roster — not allowed in a pipeline."
            )
        return
    member_ids: set[str] = set()
    for m in wg.members:
        peer = peers_mod.get_by_pubkey(home, m.pubkey)
        if peer and peer.id:
            member_ids.add(peer.id.lower())
    try:
        from alpi.home import profile_name
        own = (profile_name(home) or "").lower()
        if own:
            member_ids.add(own)
    except Exception:  # noqa: BLE001
        pass
    unknown = [p for p in parts if p.lower() not in member_ids]
    if unknown:
        raise ValueError(
            "unknown-participant: "
            + ", ".join(f"@{u}" for u in unknown)
            + " not in this workgroup. A `#task` may only name joined "
            "members — an unknown mention opens a task that wakes nobody. "
            "Fix the handle, or omit mentions for a collective task."
        )
    for ev in task_events:
        owner = _workflow_phase_owner(wg, ev.slug)
        if owner and owner.lower() not in {p.lower() for p in ev.participants}:
            raise ValueError(
                f"workflow-task-owner-missing: `#{ev.slug}` declares @{owner} "
                "as its owner, so the opener must mention that profile. Other "
                "participants may be included, but cannot replace the declared "
                f"owner. Use `@{owner} #task #{ev.slug} <what to produce>`."
            )


def _check_pipeline_close_owner(
    home: Path, wg, posts: list[dict], plaintext: str, own_pubkey: str,
) -> bool:
    """Validate an active pipeline close and return whether it waives quorum."""
    if not tasks_mod.is_done(plaintext):
        return False
    active = tasks_mod.active_task(posts, hub_pubkey=own_pubkey)
    if active is None or not active.slug:
        return False
    declared_owner = _workflow_phase_owner(wg, active.slug)
    if wg_mod.pipeline_for_phase(wg.meta, active.slug) is None:
        return False
    override = _close_override_kind(plaintext, own_pubkey)
    if override == "blocked":
        return True
    id_to_pubkey: dict[str, str] = {}
    for m in wg.members:
        peer = peers_mod.get_by_pubkey(home, m.pubkey)
        if peer and peer.id:
            id_to_pubkey[peer.id.lower()] = m.pubkey
    # The hub is nobody's peer, so a phase it owns itself would read as unresolvable.
    own_id = _own_profile_id(home)
    if own_id:
        id_to_pubkey.setdefault(own_id, own_pubkey)
    if declared_owner:
        participants = [declared_owner]
    else:
        participants = [str(pid) for pid in (active.participants or ())]
    unresolved = [pid for pid in participants if pid.lower() not in id_to_pubkey]
    if unresolved:
        raise ValueError(
            "phase-owner-unresolved: closing `#" + active.slug + "` but "
            + ", ".join(f"@{pid}" for pid in unresolved)
            + " no longer resolves to a pinned member — owner participation "
            "cannot be verified. Re-pin the peer, or halt loudly with "
            "`#done BLOCKED · <reason>`."
        )
    from alpi.alp import pipeline_gates as gates_mod

    owner_pubkeys = {id_to_pubkey[pid.lower()] for pid in participants}
    delivered_seq = gates_mod.owner_post_under_gate(
        posts, owner_pubkeys, own_pubkey, int(active.opened_seq),
    )
    if override == "skipped":
        if delivered_seq is not None or _phase_delivered_in_current_run(
            wg.meta, posts, active.slug, owner_pubkeys, own_pubkey,
        ):
            remedy = (
                "Pass the declared gate or repair the same phase"
                if gates_mod.step_for(wg.meta, active.slug) is not None
                else "Close the delivered phase normally with `#done <result>`"
            )
            raise ValueError(
                f"phase-skip-after-delivery: `#{active.slug}` already has a "
                "substantive owner delivery in this pipeline run, so it cannot be recorded as "
                f"skipped. {remedy}, or "
                "close `#done BLOCKED · <reason>`."
            )
        return True
    if delivered_seq is not None:
        _require_passing_gate(home, wg, active, delivered_seq, own_pubkey)
        return False
    owners = ", ".join(f"@{pid}" for pid in participants) or "the owner"
    first_owner = f"@{participants[0]}" if participants else "@<owner>"
    raise ValueError(
        f"phase-owner-missing: closing `#{active.slug}` but {owners} never "
        "posted in this task — the deliverable cannot exist. RE-TASK the "
        f"owner instead: `{first_owner} #task #{active.slug} "
        "<what to produce>` (a new `#task` is allowed even though you spoke "
        "last). To skip the phase deliberately, close loudly with "
        "`#done skipped · <reason>` or `#done BLOCKED · <reason>` — the "
        "`· <reason>` part is required."
    )


def _phase_delivered_in_current_run(
    meta, posts: list[dict], phase: str, owner_pubkeys: set[str], hub_pubkey: str,
) -> bool:
    events = []
    for post in posts:
        events.extend(tasks_mod.parse_post(
            str(post.get("text") or ""), int(post.get("seq", 0)),
            str(post.get("from") or ""), hub_pubkey=hub_pubkey,
        ))
    attempts = tasks_mod.fold_tasks(events)
    trigger_seqs = {
        int(post.get("seq", 0)) for post in posts if post.get("pipeline_trigger") is True
    }
    has_trigger_metadata = bool(trigger_seqs)
    run_key = ""
    run_start = 0
    current_phase = ""
    for attempt in attempts:
        mapped = wg_mod.canonical_pipeline_phase(meta, attempt.slug)
        if mapped is None:
            continue
        key, mapped_phase = mapped
        chain = tuple((getattr(meta, "pipelines", None) or {}).get(key) or ())
        if not chain:
            continue
        explicit_trigger = int(attempt.opened_seq or 0) in trigger_seqs
        legacy_restart = (
            not has_trigger_metadata
            and mapped_phase == chain[0]
            and current_phase != chain[0]
        )
        if not run_key or key != run_key or explicit_trigger or legacy_restart:
            run_key = key
            run_start = int(attempt.opened_seq or 0)
        current_phase = mapped_phase
    target = wg_mod.canonical_pipeline_phase(meta, phase)
    if target is None or target[0] != run_key:
        return False
    for attempt in attempts:
        mapped = wg_mod.canonical_pipeline_phase(meta, attempt.slug)
        if mapped != target or int(attempt.opened_seq or 0) < run_start:
            continue
        upper = int(attempt.closed_seq or 0) or None
        for post in posts:
            seq = int(post.get("seq", 0))
            if seq <= int(attempt.opened_seq or 0) or (upper is not None and seq >= upper):
                continue
            if str(post.get("from") or "") not in owner_pubkeys:
                continue
            text = str(post.get("text") or "")
            if not tasks_mod.is_working_only(text) and not tasks_mod.is_skip_only(text):
                return True
    return False


def _check_gated_phase_not_abandoned(
    wg, posts: list[dict], plaintext: str, own_pubkey: str,
) -> None:
    from alpi.alp import pipeline_gates as gates_mod

    if not tasks_mod.is_task(plaintext):
        return
    active = tasks_mod.active_task(posts, hub_pubkey=own_pubkey)
    if active is None or not active.slug:
        return
    if gates_mod.step_for(wg.meta, active.slug) is None:
        return
    evs = tasks_mod.parse_post(plaintext, 0, own_pubkey)
    new_slug = next((e.slug for e in evs if e.kind == "task"), "")
    if not new_slug or new_slug == active.slug:
        return
    # A differently named repair abandons the checked phase, so only same-slug re-tasking is valid.
    raise ValueError(
        f"phase-gate-abandoned: `#{active.slug}` declares a check and is still "
        f"open, so `#{new_slug}` would leave it behind and the pipeline could "
        f"never advance past it. To repair a failed check, RE-TASK THE SAME "
        f"PHASE — `@<owner> #task #{active.slug} <what to fix>` is allowed even "
        "though you spoke last, and the check re-runs on the owner's next post. "
        "To halt the chain, close it with `#done BLOCKED · <reason>`."
    )


def _check_task_stays_in_running_chain(
    wg, posts: list[dict], plaintext: str, own_pubkey: str,
) -> None:
    """Declared chains are trigger-only: hub prose may not jump a task into a dormant chain."""
    if not tasks_mod.is_task(plaintext):
        return
    events = tasks_mod.parse_post(plaintext, 0, own_pubkey)
    new_slug = next((e.slug for e in events if e.kind == "task"), "")
    if not new_slug:
        return
    new_resolved = wg_mod.canonical_pipeline_phase(wg.meta, new_slug)
    if new_resolved is None:
        return
    prev_chain = None
    saw_hub_task = False
    for p in reversed(posts):
        if str(p.get("from") or "") != own_pubkey:
            continue
        text = str(p.get("text") or "")
        if not tasks_mod.is_task(text):
            continue
        saw_hub_task = True
        prev_events = tasks_mod.parse_post(text, int(p.get("seq", 0)), own_pubkey)
        prev_slug = next((e.slug for e in prev_events if e.kind == "task"), "")
        if prev_slug:
            prev_resolved = wg_mod.canonical_pipeline_phase(wg.meta, prev_slug)
            if prev_resolved is not None:
                prev_chain = prev_resolved[0]
        break
    if prev_chain is not None and prev_chain == new_resolved[0]:
        return
    launch = getattr(wg.meta, "launch_pipeline", None)
    # Kickoff shape: only a VIRGIN transcript may open, and only the declared launch chain — an ad-hoc history is not virgin.
    if not saw_hub_task and launch is not None and new_resolved[0] == launch:
        return
    running = (
        f"the running chain is `{prev_chain}`"
        if prev_chain
        else "no declared chain is running"
    )
    inside = (
        f"Route the work inside `{prev_chain}` (re-task or rewind one of its "
        "phases), or ask"
        if prev_chain
        else "Ask"
    )
    raise ValueError(
        f"chain-jump: `#{new_slug}` belongs to the declared pipeline "
        f"`{new_resolved[0]}`, but {running} and declared chains are "
        f"trigger-only. {inside} the operator to run "
        f"`workgroup trigger {new_resolved[0]}`."
    )


def _check_blocked_phase_not_skipped(
    wg, posts: list[dict], plaintext: str, own_pubkey: str,
) -> None:
    """A BLOCKED close halts its chain; only re-opening the blocked phase (or an operator trigger) may move it."""
    if not tasks_mod.is_task(plaintext):
        return
    if tasks_mod.active_task(posts, hub_pubkey=own_pubkey) is not None:
        return
    events: list = []
    for p in posts:
        events += tasks_mod.parse_post(
            str(p.get("text") or ""), int(p.get("seq", 0)),
            str(p.get("from") or ""), hub_pubkey=own_pubkey,
        )
    closed = [t for t in tasks_mod.fold_tasks(events) if not t.is_open]
    if not closed:
        return
    latest = max(closed, key=lambda t: t.closed_seq or 0)
    if _close_result_override_kind(latest.result or "") != "blocked":
        return
    blocked_owner = wg_mod.canonical_pipeline_phase(wg.meta, latest.slug)
    if blocked_owner is None:
        return
    chain_key, blocked_phase = blocked_owner
    evs = tasks_mod.parse_post(plaintext, 0, own_pubkey)
    new_slug = next((e.slug for e in evs if e.kind == "task"), "")
    new_owner = wg_mod.canonical_pipeline_phase(wg.meta, new_slug) if new_slug else None
    if new_owner is None or new_owner[0] != chain_key or new_owner[1] == blocked_phase:
        return
    chain = tuple((getattr(wg.meta, "pipelines", None) or {}).get(chain_key) or ())
    if (
        new_owner[1] in chain and blocked_phase in chain
        and chain.index(new_owner[1]) < chain.index(blocked_phase)
    ):
        # A rewind re-walks forward through the blocked phase, so nothing is skipped.
        return
    raise ValueError(
        f"blocked-phase-not-cleared: `#{blocked_phase}` closed BLOCKED, which "
        f"halts the `{chain_key}` chain — opening `#{new_slug}` would advance "
        f"past a phase that never passed. Re-open `#{blocked_phase}` — or any "
        "phase EARLIER in the chain — so its close continues the chain, or "
        "leave the chain halted."
    )


# Verdict position only, per ·-segment: segment start (after emphasis) or right after a `label:` — prose can deny or hypothesise a token, and word boundaries keep "QA FAILURE"/"QA PASSED" out.
_QA_VERDICT_SEGMENT_RE = re.compile(
    r"^(?:[^·]*:)?\s*[*_\s]*(QA BLOCKED|QA FAIL|QA PASS)(?![\w-])"
)


def _done_carries_failed_qa(plaintext: str, verdict: str) -> bool:
    # Verdict position only, exact token: prose can deny or hypothesise it, and a FAIL may not stand in for the owner's BLOCKED.
    events = tasks_mod.parse_post(plaintext, 0, "hub", hub_pubkey="hub")
    result = next((event.text for event in events if event.kind == "done"), "")
    normalized = result.strip().upper()
    # Emphasis-only prefix: quotes/parens/strikethrough are mention or deletion, not assertion.
    carry_re = re.compile(r"^[*_\s]*" + re.escape(verdict) + r"(?![\w-])")
    return _close_override_kind(plaintext, "hub") == "blocked" or any(
        carry_re.match(segment.strip()) for segment in normalized.split("·")
    )


def _latest_qa_verdict(
    home: Path, wg, posts: list[dict], own_pubkey: str,
) -> str:
    active = tasks_mod.active_task(posts, hub_pubkey=own_pubkey)
    if active is None or not active.slug:
        return ""
    declared_owner = _workflow_phase_owner(wg, active.slug)
    if not declared_owner:
        return ""
    owner_pubkeys = {own_pubkey} if declared_owner.lower() == _own_profile_id(home) else set()
    for m in wg.members:
        peer = peers_mod.get_by_pubkey(home, m.pubkey)
        if peer and peer.id and peer.id.lower() == declared_owner.lower():
            owner_pubkeys.add(m.pubkey)
    verdict = ""
    for p in posts:
        if int(p.get("seq", 0)) <= int(active.opened_seq):
            continue
        if str(p.get("from") or "") not in owner_pubkeys:
            continue
        # The LAST verdict-position token wins: "cannot grant QA PASS … VERDICT: QA FAIL" must read FAIL.
        for segment in str(p.get("text") or "").split("·"):
            m = _QA_VERDICT_SEGMENT_RE.match(segment.strip())
            if m:
                verdict = m.group(1)
    return verdict


def _check_qa_verdict_respected(
    home: Path, wg, posts: list[dict], plaintext: str, own_pubkey: str,
) -> None:
    """A hub close may not claim PASS over the phase owner's FAIL/BLOCKED verdict."""
    if not tasks_mod.is_done(plaintext):
        return
    verdict = _latest_qa_verdict(home, wg, posts, own_pubkey)
    if verdict in ("QA FAIL", "QA BLOCKED") and not _done_carries_failed_qa(plaintext, verdict):
        raise ValueError(
            f"qa-verdict-mismatch: the phase owner's verdict was `{verdict}` and "
            "this close does not carry it — a `·`-separated segment of the close "
            f"must START with the verdict token, exactly like "
            f"`#done <phase> · {verdict} · <finding routing>`. Alternatively "
            "re-task the findings to their owner, or close "
            "`#done BLOCKED · <reason>`. A close may not claim PASS over the "
            "owner's FAIL."
        )


def _require_passing_gate(
    home: Path, wg, active, latest: int, own_pubkey: str,
) -> None:
    from alpi.alp import pipeline_gates as gates_mod

    step = gates_mod.step_for(wg.meta, active.slug)
    if step is None:
        return
    wg_dir = wg_mod._wg_dir(home, wg.meta.id)
    record = gates_mod.gate_log_record(wg_dir, active.slug, latest)
    if record is not None and bool(record.get("passed")):
        return
    if record is not None:
        output = str(record.get("output") or "gate returned no findings").strip()
        findings = gates_mod.findings_excerpt(output)
        raise ValueError(
            f"phase-gate-failed: `#{active.slug}` ran `{' '.join(step.argv)}` "
            f"on the owner's latest post (seq #{latest}) and failed:\n"
            f"{findings}\n"
            "Have the owner fix these findings and post a new "
            "delivery so the gate runs against that new post, or close loudly "
            "with `#done BLOCKED · <reason>` if the gate cannot pass."
        )
    raise ValueError(
        f"phase-gate-unverified: `#{active.slug}` declares the gate "
        f"`{' '.join(step.argv)}` and it has not passed on the owner's latest "
        f"post (seq #{latest}). A summary is not a green check. Have the owner "
        f"post again so the gate re-runs, or close loudly with `#done BLOCKED "
        "· <reason>` if the gate cannot pass."
    )


def _close_result_override_kind(result: str) -> str:
    return tasks_mod.close_override_kind(result)


def _close_override_kind(plaintext: str, own_pubkey: str) -> str:
    """Return the exact loud close kind, or an empty string."""
    if not tasks_mod.is_done(plaintext):
        return ""
    evs = tasks_mod.parse_post(plaintext, 0, own_pubkey, hub_pubkey=own_pubkey)
    result = next((e.text for e in evs if e.kind == "done"), "")
    return _close_result_override_kind(result)


def _check_automatic_blocked_close(
    is_pipeline: bool, plaintext: str, own_pubkey: str,
    *, operator_abandon: bool, qa_verdict: str = "",
) -> None:
    if (
        not is_pipeline
        or operator_abandon
        or _close_override_kind(plaintext, own_pubkey) != "blocked"
        or not os.environ.get("ALPI_WORKGROUP_DISPATCH")
        or os.environ.get("ALPI_WORKGROUP_FINAL_REPAIR") == "1"
        or qa_verdict in ("QA FAIL", "QA BLOCKED")
    ):
        return
    raise ValueError(
        "pipeline-blocked-premature: automatic hub turns may halt a pipeline "
        "only during FINAL REPAIR; re-task the owner or leave the task open"
    )


def _check_hub_rotation(
    posts: list[dict], own_pubkey: str, plaintext: str,
    member_pubkeys: list[str] | None = None,
    quorum_timeout: int = _FULL_QUORUM_TIMEOUT_SECONDS,
    *, allow_stalled_retask: bool = False,
    pipeline_close_override: bool = False,
    hub_owns_active_phase: bool = False,
) -> None:
    """Reject hub back-to-back content or premature `#done`."""
    if not posts:
        return
    last_contributing = None
    for p in reversed(posts):
        if not tasks_mod.is_working_only(str(p.get("text") or "")):
            last_contributing = p
            break
    is_back_to_back = (
        last_contributing is not None
        and str(last_contributing.get("from") or "") == own_pubkey
    )

    if tasks_mod.is_task(plaintext):
        active = tasks_mod.active_task(posts, hub_pubkey=own_pubkey)
        if active is not None and active.slug:
            evs = tasks_mod.parse_post(plaintext, 0, own_pubkey)
            new_slug = next((e.slug for e in evs if e.kind == "task"), "")
            if new_slug and new_slug == active.slug:
                # Pipeline-only: a stalled phase may be re-tasked with the same slug; #working is a heartbeat, not a response.
                stalled = allow_stalled_retask and not any(
                    int(p.get("seq", 0)) > int(active.opened_seq)
                    and str(p.get("from") or "") != own_pubkey
                    and not tasks_mod.is_working_only(str(p.get("text") or ""))
                    for p in posts
                )
                if not stalled:
                    raise ValueError(
                        f"task-already-active: #{new_slug} is already the open "
                        "task and its members have responded — a duplicate "
                        "#task only preempts itself. Wait for the owner's "
                        "handoff or close with #done."
                    )
        return

    if tasks_mod.is_done(plaintext):
        if pipeline_close_override:
            return  # explicit `skipped ·`/`blocked ·` close — quorum does not apply
        if hub_owns_active_phase:
            # `_check_pipeline_close_owner` still requires the hub's own delivery post.
            return
        opener = _opener_post(posts, own_pubkey)
        if opener is None:
            if not is_back_to_back:
                return
            raise ValueError(
                "turn-rotation: no active task to close, and you "
                "(hub) were the most recent poster. Wait for a "
                "member to speak before posting again."
            )
        opener_seq = int(opener.get("seq", 0))
        in_task = [
            p for p in posts if int(p.get("seq", 0)) > opener_seq
        ]

        def _is_marker_only(text: str) -> bool:
            return tasks_mod.is_skip_only(text) or tasks_mod.is_working_only(text)

        non_hub_substantive = any(
            str(p.get("from") or "") != own_pubkey
            and not _is_marker_only(str(p.get("text") or ""))
            for p in in_task
        )
        age = _opener_age_seconds(opener)
        window = (
            f"{quorum_timeout}s" if quorum_timeout < 60
            else f"{quorum_timeout // 60}-minute"
        )
        if not non_hub_substantive and age < quorum_timeout:
            raise ValueError(
                "closure-quorum: no substantive peer input yet. "
                f"Wait for content or the {window} timeout "
                f"({int(age)}s elapsed)."
            )
        expected = [
            pk for pk in (member_pubkeys or [])
            if pk and pk != own_pubkey
        ]
        if expected:
            spoken = {
                str(p.get("from") or "")
                for p in in_task
                if not tasks_mod.is_working_only(
                    str(p.get("text") or "")
                )
            }
            pending = [pk for pk in expected if pk not in spoken]
            if pending and age < quorum_timeout:
                short = [f"{pk[:12]}…" for pk in pending]
                raise ValueError(
                    f"closure-quorum: {len(pending)} member(s) still "
                    f"pending ({', '.join(short)}); wait for content, "
                    f"`#skip`, or timeout."
                )
        return  # Closure is allowed.

    if not is_back_to_back:
        return  # Someone else spoke last; new round, hub may speak.
    if hub_owns_active_phase:
        return  # Producing the deliverable for a phase it owns is not orchestration.
    raise ValueError(
        "turn-rotation: hub spoke last. Wait for a member or use `#done`."
    )


def _opener_age_seconds(opener: dict) -> float:
    """Seconds since the opener timestamp; 0 on parse failure."""
    import datetime as _dt
    ts = str(opener.get("ts") or "").strip()
    if not ts:
        return 0.0
    try:
        opened_dt = _dt.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")
        opened_dt = opened_dt.replace(tzinfo=_dt.timezone.utc)
    except ValueError:
        return 0.0
    return (_dt.datetime.now(tz=_dt.timezone.utc) - opened_dt).total_seconds()


@dataclass
class _Resolved:
    socket_path: Path | None
    host: str | None
    port: int | None
    hub_pubkey: str

    def is_tcp(self) -> bool:
        return self.host is not None and self.port is not None


def _resolve_hub(home: Path, peer_id: str) -> _Resolved:
    """Resolve the hub and transport from `peers.yaml`."""
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
    socket_path = peers_mod.local_socket_path(peer)
    return _Resolved(
        socket_path=socket_path, host=None, port=None, hub_pubkey=peer.pubkey,
    )


async def _call(home: Path, kp: Keypair, peer_id: str, method: str,
                params: dict[str, Any], timeout: float = 30.0) -> dict[str, Any]:
    res = _resolve_hub(home, peer_id)
    if res.is_tcp():
        return await alp_client.call_tcp(
            host=res.host, port=res.port,
            sender=kp, recipient_pubkey_b64=res.hub_pubkey,
            method=method, params=params, timeout=timeout,
        )
    return await alp_client.call(
        socket_path=res.socket_path,
        sender=kp, recipient_pubkey_b64=res.hub_pubkey,
        method=method, params=params, timeout=timeout,
    )


async def join(home: Path, peer_id: str, wg_id: str) -> sub_mod.Subscription:
    """Join the hub and persist the subscription locally; broadcasts public_bio + voice on the way in."""
    kp = load_or_generate(home)
    from alpi import config as _cfg
    cfg = _cfg.load(home)
    bio = (cfg.public_bio or "").strip()
    voice = (cfg.tools.tts.voice or "").strip()
    params: dict[str, Any] = {"workgroup_id": wg_id}
    if bio:
        params["bio"] = bio
    if voice:
        params["voice"] = voice
    result = await _call(home, kp, peer_id, "workgroup.join", params)
    sub_mod.revive(home, wg_id)
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
    sub.briefing = str(result.get("briefing") or "")
    sub.absorb_pipeline_state(result)
    sub.paused = bool(result.get("paused", False))
    sub.upsert_key(int(result.get("key_version", 1)), str(result["sealed_key"]))
    _absorb_roster(sub, result.get("members"))
    sub_mod.upsert(home, sub)
    return sub


def _absorb_roster(sub: sub_mod.Subscription, raw) -> None:
    """Normalize roster shapes into `roster` plus `roster_bios`/`roster_voices`."""
    if not raw:
        return
    seen: dict[str, str] = {}
    bios: dict[str, str] = {}
    voices: dict[str, str] = {}
    for entry in raw:
        if isinstance(entry, dict) and "pubkey" in entry:
            pk = str(entry["pubkey"])
            seen[pk] = str(entry.get("last_seen_at") or "")
            bio = str(entry.get("bio") or "").strip()
            if bio:
                bios[pk] = bio
            voice = str(entry.get("voice") or "").strip()
            if voice:
                voices[pk] = voice
        elif isinstance(entry, str):
            seen[entry] = ""
    if seen:
        sub.roster = seen
    sub.roster_bios = bios
    sub.roster_voices = voices


async def post(
    home: Path, wg_id: str, text: bytes,
    cost: dict[str, Any] | None = None,
    *, operator_abandon: bool = False, turn_id: str = "",
) -> dict[str, Any]:
    """Encrypt `text` under the latest key and send it to the hub."""
    kp = load_or_generate(home)
    turn_id = wg_mod.validate_turn_id(turn_id)

    try:
        _plaintext = text.decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        _plaintext = ""
    _check_substantive(_plaintext)
    _check_task_shape(_plaintext)

    wg = wg_mod.load(home, wg_id)
    if wg is not None and wg.meta.hub_pubkey == kp.pubkey_b64():
        _check_hub_single_marker(_plaintext)
        result = _post_as_hub(
            home, wg, kp, text, cost,
            operator_abandon=operator_abandon, turn_id=turn_id,
        )
        _emit_wg_post(home, wg_id, result)
        if tasks_mod.is_done(_plaintext):
            try:
                from alpi.host import events as host_events
                from alpi.home import profile_name
                host_events.emit("wg.done", {
                    "profile": profile_name(home),
                    "wg_id": wg_id,
                    "seq": result.get("seq") if isinstance(result, dict) else None,
                    "summary": _plaintext[:200],
                })
            except Exception:  # noqa: BLE001
                pass
        return result

    sub = sub_mod.get(home, wg_id)
    if sub is None:
        raise ValueError(
            f"not subscribed to {wg_id!r} — run `alpi workgroup join` first",
        )
    try:
        plaintext = text.decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        plaintext = ""
    found_markers = tasks_mod.has_markers(plaintext)
    if "task" in found_markers:
        # Members never open tasks; a `#task`+`#done` combo is ambiguous too.
        raise ValueError(
            "only the workgroup hub may post #"
            + "/#".join(found_markers)
            + " markers — non-hub members must stay silent."
        )
    if "done" in found_markers:
        # Strip the hub-only marker, keep the handoff text — don't drop a real
        # deliverable (the parser ignores member markers regardless).
        stripped = tasks_mod.strip_done_marker(plaintext)
        if not stripped.strip():
            raise ValueError(
                "a member `#done` with no handoff text is rejected — post a "
                "plain status line; only the hub closes the task."
            )
        plaintext = stripped
        text = stripped.encode("utf-8")

    try:
        await pull(home, wg_id)
    except Exception:  # noqa: BLE001
        pass
    sub = sub_mod.get(home, wg_id) or sub
    posts_view = list(sub.recent_posts or [])
    _check_member_round_fresh(posts_view, sub.hub_pubkey)
    _active = tasks_mod.active_task(posts_view, hub_pubkey=sub.hub_pubkey)
    _check_member_rotation(
        posts_view, kp.pubkey_b64(), sub.hub_pubkey, plaintext,
        phase_owner=_member_owns_active_phase(sub, _active, _own_profile_id(home)),
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
    if turn_id:
        params["turn_id"] = turn_id
    result = await _call(home, kp, sub.hub_id, "workgroup.post", params)
    _emit_wg_post(home, wg_id, result)
    return result


async def settle_turn(
    home: Path,
    wg_id: str,
    turn_id: str,
    cost: dict[str, Any],
) -> dict[str, Any]:
    """Settle a supervised turn's residual usage without adding a post."""
    kp = load_or_generate(home)
    turn_id = wg_mod.validate_turn_id(turn_id)
    wg = wg_mod.load(home, wg_id)
    if wg is not None and wg.meta.hub_pubkey == kp.pubkey_b64():
        return wg_mod.settle_turn_cost(
            home, wg_id, kp.pubkey_b64(), turn_id, cost,
        )
    sub = sub_mod.get(home, wg_id)
    if sub is None:
        raise ValueError(
            f"not subscribed to {wg_id!r} — run `alpi workgroup join` first",
        )
    return await _call(home, kp, sub.hub_id, "workgroup.post", {
        "workgroup_id": wg_id,
        "settle_only": True,
        "turn_id": turn_id,
        "cost": cost,
    })


def _file_group_key(home: Path, wg_id: str, version: int | None = None) -> tuple[bytes, int]:
    kp = load_or_generate(home)
    wg = wg_mod.load(home, wg_id)
    if wg is not None and wg.meta.hub_pubkey == kp.pubkey_b64():
        keys = wg_mod.hub_group_keys(home, wg, kp)
        selected = int(version or wg.meta.current_key_version)
        key = keys.get(selected)
        if key is None:
            raise ValueError(f"no group key version {selected} for {wg_id!r}")
        return key, selected
    sub = sub_mod.get(home, wg_id)
    if sub is None:
        raise ValueError(
            f"not subscribed to {wg_id!r} — run `alpi workgroup join` first",
        )
    selected = int(version or sub.latest_version())
    sealed = sub.sealed_for(selected)
    if not sealed:
        raise ValueError(f"no group key version {selected} for {wg_id!r}")
    return wg_mod.open_sealed_group_key(sealed, kp), selected


async def send_file(
    home: Path,
    wg_id: str,
    source: Path,
    *,
    note: str = "",
) -> dict[str, Any]:
    from alpi.alp import workgroup_files as wf

    source = source.expanduser()
    data = await asyncio.to_thread(source.read_bytes)
    if not data:
        raise ValueError("workgroup files cannot be empty")
    if len(data) > wf.MAX_FILE_BYTES:
        raise ValueError(f"file exceeds {wf.MAX_FILE_BYTES} bytes")
    name = wf._validate_name(source.name)
    note = wf._validate_note(note)
    digest = hashlib.sha256(data).hexdigest()
    kp = load_or_generate(home)
    wg = wg_mod.load(home, wg_id)
    local_hub = wg is not None and wg.meta.hub_pubkey == kp.pubkey_b64()
    if local_hub and wg.meta.paused:
        raise ValueError("workgroup is paused")
    if not local_hub:
        try:
            await pull(home, wg_id)
        except Exception:  # noqa: BLE001
            pass
    group_key, version = _file_group_key(home, wg_id)
    nonce, encoded = wg_mod.encrypt_post(group_key, data)
    ciphertext = base64.b64decode(encoded)
    params_base = {
        "workgroup_id": wg_id,
        "sha256": digest,
        "name": name,
        "size": len(data),
        "key_version": version,
        "nonce": nonce,
        "note": note,
    }
    offset = 0
    busy_deadline = asyncio.get_running_loop().time() + 300.0
    while offset < len(ciphertext):
        chunk = ciphertext[offset: offset + wf.CHUNK_BYTES]
        params = {
            **params_base,
            "offset": offset,
            "data_base64": base64.b64encode(chunk).decode("ascii"),
            "done": offset + len(chunk) == len(ciphertext),
        }
        if local_hub:
            try:
                result = await asyncio.to_thread(
                    wf.put_chunk, home, wg, kp, kp.pubkey_b64(), params,
                )
            except alp_server.HandlerError as e:
                raise alp_client.ClientError(
                    f"hub rejected: {e.code} {e.message}",
                ) from e
        else:
            sub = sub_mod.get(home, wg_id)
            if sub is None:
                raise ValueError(f"not subscribed to {wg_id!r}")
            result = await _call(
                home, kp, sub.hub_id, "workgroup.file_put", params, timeout=60.0,
            )
        if result.get("busy"):
            if asyncio.get_running_loop().time() >= busy_deadline:
                raise alp_client.ClientError(
                    "another upload of this workgroup file is still in progress",
                )
            await asyncio.sleep(0.05)
            continue
        if result.get("complete"):
            return {
                "sha256": digest,
                "size": len(data),
                "name": name,
                "existed": bool(result.get("existed")),
                "marker": wf._marker_text(name, len(data), digest, note),
            }
        next_offset = int(result.get("next_offset", -1))
        if next_offset <= offset or next_offset > len(ciphertext):
            raise alp_client.ClientError("hub returned an invalid file offset")
        offset = next_offset
    raise alp_client.ClientError("hub did not complete the workgroup file upload")


async def get_file(
    home: Path,
    wg_id: str,
    digest: str,
) -> tuple[dict[str, Any], bytes]:
    from alpi.alp import workgroup_files as wf

    digest = wf._validate_hash(digest)
    kp = load_or_generate(home)
    wg = wg_mod.load(home, wg_id)
    local_hub = wg is not None and wg.meta.hub_pubkey == kp.pubkey_b64()
    sub = None if local_hub else sub_mod.get(home, wg_id)
    if not local_hub and sub is None:
        raise ValueError(
            f"not subscribed to {wg_id!r} — run `alpi workgroup join` first",
        )
    offset = 0
    ciphertext = bytearray()
    metadata: dict[str, Any] | None = None
    while True:
        if local_hub:
            try:
                result = await asyncio.to_thread(
                    wf.get_chunk, home, wg_id, digest, offset,
                )
            except alp_server.HandlerError as e:
                raise alp_client.ClientError(
                    f"hub rejected: {e.code} {e.message}",
                ) from e
        else:
            result = await _call(
                home, kp, sub.hub_id, "workgroup.file_get",
                {"workgroup_id": wg_id, "sha256": digest, "offset": offset},
                timeout=60.0,
            )
        current = {
            key: result.get(key)
            for key in ("name", "size", "sha256", "key_version", "nonce", "ciphertext_size")
        }
        if metadata is None:
            metadata = current
        elif current != metadata:
            raise alp_client.ClientError("workgroup file metadata changed during download")
        try:
            chunk = base64.b64decode(str(result.get("data_base64") or ""), validate=True)
        except Exception as e:  # noqa: BLE001
            raise alp_client.ClientError("hub returned invalid file data") from e
        ciphertext.extend(chunk)
        if len(ciphertext) > wf.MAX_FILE_BYTES + 16:
            raise alp_client.ClientError("workgroup file exceeds the local size limit")
        offset += len(chunk)
        if result.get("eof"):
            break
        if not chunk:
            raise alp_client.ClientError("hub returned an empty non-final file chunk")
    if metadata is None or offset != int(metadata["ciphertext_size"]):
        raise alp_client.ClientError("workgroup file download ended early")
    if metadata["sha256"] != digest:
        raise alp_client.ClientError("hub returned the wrong workgroup file")
    group_key, _ = _file_group_key(home, wg_id, int(metadata["key_version"]))
    try:
        plaintext = wg_mod.decrypt_post(
            group_key,
            str(metadata["nonce"]),
            base64.b64encode(bytes(ciphertext)).decode("ascii"),
        )
    except Exception as e:  # noqa: BLE001
        raise alp_client.ClientError("workgroup file failed authentication") from e
    if (
        len(plaintext) != int(metadata["size"])
        or hashlib.sha256(plaintext).hexdigest() != digest
    ):
        raise alp_client.ClientError("workgroup file failed size or sha256 verification")
    return metadata, plaintext


async def list_files(
    home: Path,
    wg_id: str,
    *,
    offset: int = 0,
    limit: int = 50,
) -> dict[str, Any]:
    from alpi.alp import workgroup_files as wf

    kp = load_or_generate(home)
    wg = wg_mod.load(home, wg_id)
    local_hub = wg is not None and wg.meta.hub_pubkey == kp.pubkey_b64()
    if local_hub:
        return await asyncio.to_thread(
            wf.list_metadata,
            home,
            wg_id,
            offset,
            limit,
        )
    sub = sub_mod.get(home, wg_id)
    if sub is None:
        raise ValueError(
            f"not subscribed to {wg_id!r} — run `alpi workgroup join` first",
        )
    return await _call(
        home,
        kp,
        sub.hub_id,
        "workgroup.file_list",
        {
            "workgroup_id": wg_id,
            "offset": offset,
            "limit": limit,
        },
    )


def _emit_wg_post(home: Path, wg_id: str, result: dict[str, Any] | None) -> None:
    """wg.post fires on every successful post; wg.done is reserved for #done markers."""
    try:
        from alpi.host import events as host_events
        from alpi.home import profile_name
        host_events.emit("wg.post", {
            "profile": profile_name(home),
            "wg_id": wg_id,
            "seq": result.get("seq") if isinstance(result, dict) else None,
        })
    except Exception:  # noqa: BLE001
        pass


def _paths_step(meta, slug: str):
    from alpi.alp import pipeline_gates as gates

    step = gates.step_for(meta, slug)
    return step if step is not None and step.paths else None


def _baselines_before_post(home: Path, wg, d: Path, events) -> list[str]:
    """The baseline must exist before the opener is readable, or the owner's first edits land inside it."""
    from alpi import config as cfg_mod
    from alpi.alp import pipeline_gates as gates

    if not getattr(wg.meta, "pipeline_steps", None):
        return []
    workspace = cfg_mod.load(home).workspace_path or home
    created: list[str] = []
    for ev in events:
        if ev.kind != "task":
            continue
        step = _paths_step(wg.meta, ev.slug)
        if step is None:
            continue
        try:
            if gates.snapshot_baseline(d, step, workspace):
                created.append(step.phase)
        except OSError as e:
            for phase in created:
                gates.clear_baseline(d, phase)
            raise ValueError(f"phase baseline snapshot failed: {e}") from e
    return created


def _baselines_after_post(wg, d: Path, events, active_phase) -> None:
    """A run's baseline dies with the run: `#done` close or cross-phase preemption; a same-phase re-task keeps it."""
    from alpi.alp import pipeline_gates as gates

    if not getattr(wg.meta, "pipeline_steps", None) or active_phase is None:
        return
    ended = any(ev.kind == "done" for ev in events) or any(
        ev.kind == "task" and ev.slug != active_phase.slug for ev in events
    )
    if not ended:
        return
    step = _paths_step(wg.meta, active_phase.slug)
    if step is None:
        return
    try:
        gates.clear_baseline(d, step.phase)
    except OSError:
        pass


def _post_as_hub(
    home: Path, wg, kp: Keypair, text: bytes,
    cost: dict[str, Any] | None,
    *, operator_abandon: bool = False, turn_id: str = "",
) -> dict[str, Any]:
    """Write a hub post directly into the local transcript."""
    from alpi.alp.workgroup import _transcript_write_lock, _wg_dir

    own = wg.member(kp.pubkey_b64())
    if own is None:
        raise ValueError("hub is not a member of its own workgroup")
    if wg.meta.paused:
        raise ValueError("workgroup is paused")

    d = _wg_dir(home, wg.meta.id)
    # Read, validate, baseline and append under ONE lock — a post validated on a stale transcript must never land.
    with _transcript_write_lock(d):
        return _post_as_hub_locked(
            home, wg, own, kp, text, dict(cost) if cost else {}, d,
            operator_abandon=operator_abandon, turn_id=turn_id,
        )


def _post_as_hub_locked(
    home: Path, wg, own, kp: Keypair, text: bytes,
    cost_dict: dict[str, Any], d: Path,
    *, operator_abandon: bool, turn_id: str = "",
) -> dict[str, Any]:
    import datetime as _dt
    from alpi.alp import pipeline_gates as gates
    from alpi.alp.workgroup import (
        _admit_post_locked, _gate_post, _load_ledger, _read_transcript,
    )

    existing_raw = _read_transcript(d)

    # All openable versions (current + rekey history) so the closure-quorum gate
    # still sees a task opened before a leave/kick rotation.
    keys_for_check = wg_mod.hub_group_keys(home, wg, kp)
    existing: list[dict[str, Any]] = []
    for entry in existing_raw:
        gk = keys_for_check.get(int(entry.get("key_version", 1)))
        if gk is None:
            existing.append({**entry, "text": ""})
            continue
        try:
            decrypted_bytes = wg_mod.decrypt_post(
                gk, entry["nonce"], entry["ciphertext"],
            )
            existing.append({
                **entry,
                "text": decrypted_bytes.decode("utf-8", errors="replace"),
            })
        except Exception:  # noqa: BLE001
            existing.append({**entry, "text": ""})

    try:
        plaintext = text.decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        plaintext = ""

    if tasks_mod.is_skip(plaintext):
        raise ValueError(
            "hub-cannot-skip: `#skip` is the member-side pass "
            "signal. As hub you don't skip your own task — open "
            "with `#task`, contribute substantively, or close "
            "with `#done`."
        )
    if tasks_mod.is_working(plaintext):
        raise ValueError(
            "hub-cannot-working: `#working` is the member-side "
            "heartbeat for slow tool work. As hub you orchestrate "
            "the workgroup — you don't need to signal processing. "
            "Either post substantive prose to push the discussion "
            "forward, or post `#done` when the deliverable is in "
            "the transcript."
        )

    _validate_task_participants(home, wg, plaintext)

    _check_closure_only(plaintext)

    member_pubkeys = [m.pubkey for m in wg.members]
    quorum_roster = _quorum_roster(home, wg, existing, member_pubkeys)
    is_pipeline = wg_mod.is_pipeline_workgroup(wg.meta)
    guard_active = tasks_mod.active_task(existing, hub_pubkey=kp.pubkey_b64())
    qa_verdict = (
        _latest_qa_verdict(home, wg, existing, kp.pubkey_b64())
        if guard_active is not None
        and (guard_active.slug == "qa" or guard_active.slug.endswith("-qa"))
        else ""
    )
    _check_automatic_blocked_close(
        is_pipeline, plaintext, kp.pubkey_b64(),
        operator_abandon=operator_abandon, qa_verdict=qa_verdict,
    )
    close_override = _check_pipeline_close_owner(
        home, wg, existing, plaintext, kp.pubkey_b64(),
    )
    if not operator_abandon:
        _check_gated_phase_not_abandoned(wg, existing, plaintext, kp.pubkey_b64())
        _check_blocked_phase_not_skipped(wg, existing, plaintext, kp.pubkey_b64())
        _check_task_slug_is_routable(wg, plaintext)
        _check_task_stays_in_running_chain(wg, existing, plaintext, kp.pubkey_b64())
    _check_qa_verdict_respected(home, wg, existing, plaintext, kp.pubkey_b64())
    active_phase = tasks_mod.active_task(existing, hub_pubkey=kp.pubkey_b64())
    _check_hub_rotation(
        existing, kp.pubkey_b64(), plaintext, quorum_roster,
        wg.meta.quorum_timeout_seconds or _FULL_QUORUM_TIMEOUT_SECONDS,
        allow_stalled_retask=is_pipeline,
        pipeline_close_override=close_override,
        hub_owns_active_phase=(
            active_phase is not None
            and _hub_owns_phase(home, wg, active_phase.slug)
        ),
    )

    declared = wg_mod.normalize_declared_cost(cost_dict)
    declared_usd = declared["usd"]
    declared_tokens = declared["tokens"]
    declared_in = declared["tokens_in"]
    declared_out = declared["tokens_out"]
    declared_cached = declared["cached_in"]
    declared_measured = declared["measured_in"]
    # Budget/cap verdict precedes the baseline write so a rejected opener leaves no trace.
    try:
        _gate_post(wg.meta, _load_ledger(d), {"usd": declared_usd, "tokens": declared_tokens})
    except Exception as e:  # noqa: BLE001
        raise ValueError(str(e)) from e

    post_events = tasks_mod.parse_post(plaintext, 0, kp.pubkey_b64())
    created_baselines = _baselines_before_post(home, wg, d, post_events)

    try:
        group_key = wg_mod.open_sealed_group_key(own.sealed_key, kp)
        nonce, ct = wg_mod.encrypt_post(group_key, text)

        ts = _dt.datetime.now(tz=_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        entry: dict[str, Any] = {
            "seq": 0, "ts": ts, "from": kp.pubkey_b64(),
            "key_version": own.key_version, "nonce": nonce, "ciphertext": ct,
        }
        if operator_abandon:
            entry["pipeline_trigger"] = True
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
        entry = _admit_post_locked(d, wg.meta, entry, declared_usd, declared_tokens)
    except Exception as e:  # noqa: BLE001
        for phase in created_baselines:
            gates.clear_baseline(d, phase)
        raise ValueError(str(e)) from e
    _baselines_after_post(wg, d, post_events, active_phase)
    return {"seq": int(entry["seq"]), "ts": ts}


async def pull(
    home: Path, wg_id: str, *, since: int | None = None, wait_s: float = 0.0,
) -> tuple[list[dict[str, Any]], int]:
    """Fetch/decrypt/cache new posts; ``wait_s`` > 0 long-polls (hub holds ≤25s, answers early on fresh posts)."""
    kp = load_or_generate(home)
    sub = sub_mod.get(home, wg_id)
    if sub is None:
        raise ValueError(
            f"not subscribed to {wg_id!r} — run `alpi workgroup join` first",
        )
    cursor = sub.last_seq if since is None else int(since)
    params: dict[str, Any] = {"workgroup_id": wg_id, "since": cursor}
    if wait_s > 0:
        params["wait_s"] = float(wait_s)
    raw = await _call(home, kp, sub.hub_id, "workgroup.pull", params,
                      timeout=30.0 + max(0.0, float(wait_s)))

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
    def _merge_pull(current: sub_mod.Subscription) -> bool:
        # Most pulls are empty long-poll timeouts; without this the whole file is re-serialized on the event loop every tick.
        before = sub_mod.persisted_signature(current)
        if new_sealed and current.sealed_for(server_version) != new_sealed:
            current.upsert_key(server_version, new_sealed)
        if head > current.last_seq:
            current.last_seq = head
        if any(k in raw for k in ("pipelines", "launch_pipeline", "pipeline_mode")):
            current.absorb_pipeline_state(raw)
        current.paused = bool(raw.get("paused", current.paused))
        current.append_recent(decrypted)
        _absorb_roster(current, raw.get("members"))
        return sub_mod.persisted_signature(current) != before

    if sub_mod.mutate(home, wg_id, _merge_pull) is None:
        return [], head

    _emit_wg_mentions(
        home, wg_id, decrypted,
        own_pubkey=kp.pubkey_b64(), min_seq=cursor,
    )

    return decrypted, head


def _emit_wg_mentions(
    home: Path, wg_id: str, posts: list[dict[str, Any]],
    *, own_pubkey: str, min_seq: int = 0,
) -> None:
    """Emit ``wg.mention`` for pulled posts that mention the local profile; skip self-posts and ``seq <= min_seq`` so re-pulls don't duplicate."""
    try:
        from alpi.alp import tasks as tasks_mod
        from alpi.home import profile_name
        from alpi.host import events as host_events
    except Exception:  # noqa: BLE001
        return

    me = (profile_name(home) or "").lower()
    if not me:
        return

    for p in posts:
        if int(p.get("seq") or 0) <= min_seq:
            continue
        if str(p.get("from") or "") == own_pubkey:
            continue
        text = str(p.get("text") or "")
        if not text:
            continue
        mentioned = {m.lower() for m in tasks_mod.mentions_in(text)}
        if me not in mentioned:
            continue
        try:
            host_events.emit("wg.mention", {
                "profile": profile_name(home),
                "wg_id": wg_id,
                "seq": int(p.get("seq") or 0),
                "from": str(p.get("from") or ""),
                "summary": text[:200],
            })
        except Exception:  # noqa: BLE001
            pass


def _emit_workgroup_changed(home: Path, wg_id: str, action: str) -> None:
    try:
        from alpi.home import profile_name
        from alpi.host import events as host_events
        host_events.emit("workgroup_changed", {
            "profile": profile_name(home),
            "wg_id": wg_id,
            "action": action,
        })
    except Exception:  # noqa: BLE001
        pass


class TriggerError(ValueError):
    """Rejected trigger; ``code`` is the stable reason clients surface verbatim."""

    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


_TRIGGER_LOCKS: dict[str, asyncio.Lock] = {}
_TRIGGER_LOCKS_CAP = 256


def _trigger_lock(home: Path, wg_id: str) -> asyncio.Lock:
    # Serialises check-then-post per workgroup so two clients cannot open competing chains.
    key = f"{home}:{wg_id}"
    lock = _TRIGGER_LOCKS.get(key)
    if lock is None:
        if len(_TRIGGER_LOCKS) >= _TRIGGER_LOCKS_CAP:
            for stale, held in list(_TRIGGER_LOCKS.items()):
                if not held.locked():
                    del _TRIGGER_LOCKS[stale]
        lock = asyncio.Lock()
        _TRIGGER_LOCKS[key] = lock
    return lock


def _run_being_stopped(key: str, state: dict[str, Any] | None) -> dict[str, Any] | None:
    """What this trigger will stop, so every surface can say it before and after; a blocked run counts — what it loses is its position."""
    run = (state or {}).get("pipeline_run") or {}
    status = str(run.get("status") or "")
    if not status or status == "completed":
        return None
    active = (state or {}).get("active") or {}
    return {
        "pipeline": str(run.get("pipeline") or ""),
        "phase": str(run.get("current_phase") or ""),
        "status": str(run.get("status") or ""),
        "open_task": str(active.get("slug") or "") or None,
        "same_pipeline": str(run.get("pipeline") or "") == key,
    }


async def trigger_pipeline(
    home: Path, wg_id: str, pipeline: str, *, _admit: bool = False,
    _opener: str = "",
) -> dict[str, Any]:
    """Hub-admin only: queue or publish the recipe-authored opener."""
    from alpi.host import workgroup as host_wg
    from alpi.alp import pipeline_queue

    key = str(pipeline or "").strip().lower()
    if not key:
        raise TriggerError("pipeline-required", "a pipeline key is required")
    async with _trigger_lock(home, wg_id):
        wg = wg_mod.load(home, wg_id)
        if wg is None:
            if sub_mod.get(home, wg_id) is not None:
                raise TriggerError(
                    "pipeline-trigger-not-hub",
                    "only the hub may start a pipeline in this workgroup",
                )
            raise TriggerError("workgroup-not-found", f"workgroup {wg_id!r} not found")
        own_pubkey = load_or_generate(home).pubkey_b64()
        if wg.meta.hub_pubkey != own_pubkey:
            raise TriggerError(
                "pipeline-trigger-not-hub",
                "only the hub may start a pipeline in this workgroup",
            )
        if wg.meta.paused:
            raise TriggerError(
                "workgroup-paused", "resume the workgroup before starting a pipeline",
            )
        chain = wg.meta.pipelines.get(key)
        if not chain:
            raise TriggerError(
                "pipeline-unknown",
                f"{key!r} is not a declared pipeline; known: {sorted(wg.meta.pipelines)}",
            )
        phase = chain[0]
        spec = (wg.meta.pipeline_steps or {}).get(phase) or {}
        owner = str(spec.get("owner") or "").strip()
        task = str(spec.get("task") or "").strip()
        if not owner or not task:
            raise TriggerError(
                "pipeline-trigger-contract-missing",
                f"pipeline {key!r} declares no owner/task for its first phase "
                f"#{phase}, so the opener cannot be authored from the recipe",
            )
        opener = _opener.strip() or f"@{owner} #task #{phase} · {task}"
        if not _admit and pipeline_queue.limit(home) > 0:
            queued = pipeline_queue.enqueue(
                home, wg_id, key, opener=opener if _opener.strip() else "",
            )
            from alpi.alp import wakes
            wakes.fire(home, wg_id)
            _emit_workgroup_changed(home, wg_id, "queued")
            return {
                "ok": True,
                "queued": True,
                "position": queued["position"],
                "pipeline": key,
                "phase": phase,
                "seq": None,
                "stopped": None,
            }
        from alpi import config as cfg_mod
        from alpi.alp import pipeline_gates as gates
        prepare = gates.prepare_for(wg.meta, key)
        if prepare is not None:
            workspace = cfg_mod.load(home).workspace_path or home
            passed, output = await asyncio.to_thread(
                gates.run_prepare, prepare, workspace,
            )
            try:
                await asyncio.to_thread(
                    gates.write_prepare_log,
                    home / "alp" / "workgroups" / wg.meta.id,
                    prepare, passed, output,
                )
            except OSError as e:
                raise TriggerError(
                    "pipeline-prepare-audit-failed",
                    f"pipeline {key!r} prepare log could not be written: {e}",
                ) from e
            if not passed:
                detail = output.splitlines()[-1][:500] if output else "no output"
                raise TriggerError(
                    "pipeline-prepare-failed",
                    f"pipeline {key!r} prepare failed: {detail}",
                )
        state = await asyncio.to_thread(host_wg.fold_task_state, home, wg_id)
        stopped = _run_being_stopped(key, state)
        try:
            # One chain at a time: the opener preempts whatever was mid-flight.
            result = await post(
                home, wg_id, opener.encode(),
                operator_abandon=True,
            )
        except ValueError as e:
            # Keep the coded contract: clients switch on `.code`, never on prose.
            raise TriggerError("pipeline-trigger-rejected", str(e)) from e
    _emit_workgroup_changed(home, wg_id, "trigger")
    return {
        "ok": True,
        "pipeline": key,
        "phase": phase,
        "seq": result.get("seq") if isinstance(result, dict) else None,
        "stopped": stopped,
    }


async def leave(home: Path, wg_id: str) -> dict[str, Any]:
    """Leave the workgroup and purge the local subscription."""
    kp = load_or_generate(home)
    sub = sub_mod.get(home, wg_id)
    if sub is None:
        raise ValueError(f"not subscribed to {wg_id!r}")
    result: dict[str, Any] = {}
    try:
        result = await _call(home, kp, sub.hub_id, "workgroup.leave",
                             {"workgroup_id": wg_id})
    except Exception as e:  # noqa: BLE001
        result = {
            "workgroup_id": wg_id,
            "hub_unreachable": True,
            "hub_error": f"{type(e).__name__}: {e}",
        }
    sub_mod.remove(home, wg_id)
    return result


async def pause(home: Path, wg_id: str) -> dict[str, Any]:
    return await _set_paused(home, wg_id, True)


async def resume(home: Path, wg_id: str) -> dict[str, Any]:
    return await _set_paused(home, wg_id, False)


async def _set_paused(home: Path, wg_id: str, paused: bool) -> dict[str, Any]:
    from alpi.alp import workgroup as wg_mod
    kp = load_or_generate(home)
    own_pubkey = kp.pubkey_b64()
    wg = wg_mod.load(home, wg_id)
    if wg is not None and wg.meta.hub_pubkey == own_pubkey:
        if wg.meta.paused != paused:
            wg.meta.paused = paused
            wg.meta.paused_at = wg_mod._utcnow() if paused else ""
            wg.meta.paused_by = own_pubkey if paused else ""
            wg_mod._save_meta(wg_mod._wg_dir(home, wg_id), wg.meta)
            if not paused:
                # Resume: clear the poller's "already handled" guards so the
                # next tick re-evaluates instead of staying silent on counters
                # consumed before the pause.
                try:
                    from alpi import service as _service
                    _service.reset_workgroup_poller_state(home, wg_id)
                except Exception:  # noqa: BLE001
                    pass
                from alpi.alp import wakes
                wakes.fire(home, wg_id)
        return {
            "workgroup_id": wg_id,
            "paused": paused,
            "paused_at": wg.meta.paused_at,
            "paused_by": wg.meta.paused_by,
        }
    raise ValueError(
        "only the workgroup hub may pause / resume this workgroup"
    )
