"""Engine pre-turn hook: turn workgroup state into a system-prompt block.

Runs before every agent turn (interactive, scheduled) so
the agent always sees its current workgroup context: briefing,
active task, recent posts, and budget headroom for each workgroup
this profile is a member of (subscriptions) or hosts.

No network IO here — reads ``Subscription.recent_posts`` cached by
the most recent ``workgroup_client.pull``. The cache is refreshed
by the workgroup poller running inside the unified service, so the
engine block stays cheap even when the agent runs on a tight loop.
"""

from __future__ import annotations

import json
from pathlib import Path

from alpi.alp import subscription as sub_mod
from alpi.alp import pipeline_gates
from alpi.alp import tasks
from alpi.alp import workgroup as wg_mod
from alpi.alp.keys import load_or_generate
from alpi.home import _ROOT


_RECENT_POSTS = 5            # show last N in the system-prompt block
_POST_PREVIEW_CHARS = 220
_DIRECTED_POST_CHARS = pipeline_gates.GATE_FINDINGS_POST_CHARS + 200
_BRIEFING_INJECT_CHARS = 4096
_MAX_BLOCKS = 10             # ceiling — protects token budget
_OMITTED_NAMES = 12


def build(
    home: Path, wg_id: str | None = None, max_chars: int | None = None,
) -> str | None:
    """Render all visible workgroups, or only the exact dispatch target."""
    own_id = _profile_id(home)
    own_pubkey = load_or_generate(home).pubkey_b64()
    subs = sub_mod.load(home)
    hubs = wg_mod.list_workgroups(home)
    if not subs and not hubs:
        return None

    aliases = _build_aliases(home, own_id, own_pubkey)
    zone = _budget_zone(home)
    candidates = _context_candidates(home, subs, hubs, directed=bool(wg_id))
    if wg_id:
        candidates = [candidate for candidate in candidates if candidate[1] == wg_id]
        if not candidates:
            return None
    pipeline_only = bool(candidates) and all(_candidate_pipelines(c) for c in candidates)
    blocks: list[str] = []
    selected = 0
    limit = len(candidates) if wg_id else min(len(candidates), _MAX_BLOCKS)
    for kind, _candidate_id, item in candidates[:limit]:
        block = (
            _format_subscription_block(item, own_id, aliases)
            if kind == "subscription"
            else _format_hub_block(home, item, own_id, own_pubkey, aliases)
        )
        if not block:
            continue
        trial = _render_context(
            own_id, len(subs), len(hubs), blocks + [block],
            [] if wg_id else [_candidate_name(c) for c in candidates[selected + 1:]],
            zone, pipeline_only,
        )
        if max_chars is not None and len(trial) > max_chars:
            break
        blocks.append(block)
        selected += 1

    if wg_id:
        if not blocks:
            return None
        return _render_context(own_id, len(subs), len(hubs), blocks, [], zone, pipeline_only)

    omitted = [_candidate_name(c) for c in candidates[selected:]]
    out = _render_context(own_id, len(subs), len(hubs), blocks, omitted, zone, pipeline_only)
    if max_chars is not None and len(out) > max_chars:
        return None
    return out


def _context_candidates(home: Path, subs, hubs, directed: bool):
    candidates = [
        ("subscription", sub.wg_id, sub)
        for sub in subs
    ] + [
        ("hub", wg.meta.id, wg)
        for wg in hubs
    ]
    if directed:
        return candidates
    return _rank_undirected(
        candidates,
        lambda c: c[2].paused if c[0] == "subscription" else c[2].meta.paused,
        lambda c: (
            _subscription_last_activity(c[2])
            if c[0] == "subscription"
            else _hub_last_activity(home, c[2].meta.id, c[2].meta.created_at)
        ),
    )


def _candidate_pipelines(candidate) -> dict:
    kind, _candidate_id, item = candidate
    if kind == "subscription":
        return getattr(item, "pipelines", None) or {}
    return getattr(item.meta, "pipelines", None) or {}


def _candidate_name(candidate) -> str:
    kind, candidate_id, item = candidate
    if kind == "subscription":
        return item.name or candidate_id
    return item.meta.name or candidate_id


def _render_context(
    own_id: str, joined: int, hosting: int, blocks: list[str],
    omitted: list[str], zone: str, pipeline_only: bool = False,
) -> str:
    header = f"=== Workgroups (you are @{own_id} · {joined} joined, {hosting} hosting) ==="
    if omitted:
        names = ", ".join(omitted[:_OMITTED_NAMES])
        if len(omitted) > _OMITTED_NAMES:
            names += f", +{len(omitted) - _OMITTED_NAMES} more"
        header += (
            f"\nShowing {len(blocks)} of {joined + hosting} workgroups "
            f"(most recently active first).\nOmitted: {names}"
        )
    guardrails = WORKGROUP_GUARDRAILS_PIPELINE if pipeline_only else WORKGROUP_GUARDRAILS
    parts = [header, guardrails]
    parts.extend(blocks)
    if zone:
        parts.append(zone)
    return "\n\n".join(parts)


def _rank_undirected(items, paused_of, activity_of):
    # Two passes: stable sort keeps the recency order inside each paused group.
    ranked = sorted(items, key=activity_of, reverse=True)
    ranked.sort(key=lambda x: bool(paused_of(x)))
    return ranked


def _subscription_last_activity(sub: sub_mod.Subscription) -> str:
    for post in reversed(sub.recent_posts):
        ts = str(post.get("ts") or "")
        if ts:
            return ts
    return sub.joined_at


def _hub_last_activity(home: Path, wg_id: str, fallback: str = "") -> str:
    p = home / "alp" / "workgroups" / wg_id / "transcript.jsonl"
    try:
        with p.open("rb") as fh:
            fh.seek(0, 2)
            fh.seek(max(0, fh.tell() - 4096))
            tail = fh.read().decode("utf-8", errors="replace")
    except OSError:
        return fallback
    for line in reversed(tail.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            return str(json.loads(line).get("ts") or fallback)
        except json.JSONDecodeError:
            continue
    return fallback


def _budget_zone(home: Path) -> str:
    from alpi import config as cfg_mod, ledger
    try:
        cfg = cfg_mod.load(home)
    except Exception:  # noqa: BLE001
        return ""
    cap_usd = float((cfg.budget or {}).get("daily_usd") or 0)
    if cap_usd <= 0:
        return ""
    used = ledger.load(home).get("profile", {})
    pct = max(0.0, min(1.0, float(used.get("usd") or 0) / cap_usd))
    if pct < 0.4:
        return ""
    if pct < 0.6:
        return f"BUDGET: {pct:.0%} used today — prefer one paragraph, lead with the answer."
    if pct < 0.8:
        return f"BUDGET: {pct:.0%} used today — one sentence if it's enough; skip preamble."
    return f"BUDGET: {pct:.0%} used today — only post if it changes the outcome."


# Guardrails — prescriptive rules the agent reads on every turn.
# Defaults the agent to OBSERVER, not PARTICIPANT. The protocol
# permits any member to post; these rules bias behaviour so peers
# don't desyncrhonize into a pingpong loop that drains budgets.

WORKGROUP_GUARDRAILS = """\
=== Workgroup engagement rules ===

WHAT A WORKGROUP IS. A profile (the HUB) needs help from peers
whose expertise it doesn't have. Strength in unity: each peer
contributes from their identity (their bio, skills, memories);
the hub frames the problem and synthesises. The hub is NOT a
manager assigning tasks — peers infer what to bring from their
own identity plus the briefing's problem statement.

THE PROTOCOL RULES (the SDK enforces all of them; violating any
gets your post rejected before it goes on the wire):

  1. ONLY THE HUB OPENS, WITH A SLUG. The hub posts
     `#task #<slug> <problem>` to open work — the slug is a stable
     kebab-case identifier (e.g. `#task #onboarding-friction-top3
     top three onboarding friction points`). A `#task` without a
     `#<slug>` is rejected by the SDK with `task-missing-slug`.
     Member `#task` markers are rejected regardless of slug.
  2. ONLY THE HUB CLOSES, WITH QUORUM OF THE PARTICIPANTS. The
     hub posts `#done <result>` to close. Member `#done` markers
     are rejected. A hub `#done` requires:
       (a) every PARTICIPANT in the active task has CONTRIBUTED
           (substantive content OR `#skip`; a bare `#working`
           heartbeat does NOT count). Participants = the members
           the opener `@`-mentioned — a TARGETED task closes on
           just those named, NOT the whole roster. A COLLECTIVE
           task (no `@`-mentions) has every member as a
           participant. AND
       (b) at least one non-hub post is SUBSTANTIVE (not just
           `#skip` / `#working`) — the workgroup must produce
           real content, not "everyone passed".
     Without both: SDK rejects with `closure-quorum`. Hard
     escape: after the closure-quorum timeout (default 10 min)
     since the `#task` opened, the hub may close anyway (so a
     stuck workgroup can't freeze forever).
  3. ONE POST PER ROUND PER PEER. A "round" runs from the hub's
     last post to the next. Each peer (including the hub) posts
     at most one CONTRIBUTING post per round (substantive or
     `#skip`). A second attempt is rejected as `turn-rotation`.
     `#working` heartbeats are exempt — see rule 5.
  4. `#SKIP` IS MEMBER-ONLY AND A LAST RESORT. Only members may
     post `#skip` (the hub doesn't skip its own task — SDK
     rejects). Even for members, `#skip` is a LAST RESORT —
     only valid when your identity has zero overlap with this
     task, or when you already posted substantively in a prior
     round. Reflexive skipping defeats the purpose of the
     workgroup — the SDK additionally rejects a hub `#done` if
     zero non-hub posts were substantive.
  5. `#WORKING` IS MEMBER-ONLY (heartbeat — your sign of life). Only
     members may post `#working` (the hub orchestrates — they
     don't signal processing; SDK rejects hub `#working`). Post
     `#working` BEFORE starting whenever you expect to take more
     than ~30s before your substantive post — this covers BOTH
     slow external tools (web_fetch, research, multi-step delegate)
     AND, when you are the named participant on a production task,
     a long pass of LOCAL file work (writing/translating many
     files, an `npm` build). Writing 20 JSON files locally takes
     minutes; without a `#working` the hub reads your silence as a
     stall and re-tasks you. Make the reason SAY WHAT YOU'RE DOING
     — it is the ONLY thing the hub and the human see while they
     wait — naming the concrete deliverable AND the tool(s):
       `#working <concrete action> (<tool>)`
     Good:
       `#working comparing ECB vs Fed rate paths across 3 sources (web_fetch)`
       `#working writing Spanish source content under src/content/** (write_file)`
       `#working installing deps + building dist/ (terminal)`
       `#working delegating the SQL audit to a sub-agent (delegate)`
     Spartan reasons waste the signal — do NOT post a bare
     `#working`, `#working on it`, or `#working give me a sec`.
     Write the reason in the active task's language. Properties:
       - Does NOT consume your round slot — you can post
         substantive or `#skip` afterwards in the same round.
       - Does NOT count toward the closure-quorum — you must
         still finish with substantive content or `#skip` for
         the hub to close.
       - At most one `#working` per round (no heartbeat spam).
     The hub uses recent `#working` posts as a hint to wait
     longer for your real contribution. Without `#working`,
     a long-running member can be invisible to the hub and
     either get cut off at the closure-quorum timeout or have
     other members close around them.
  6. A NEW `#task` PREEMPTS. When the hub posts a new `#task`
     while one is active, the previous task is closed as
     "preempted" and any peer subprocess currently thinking is
     SIGTERM'd. Don't try to wedge in a stale reaction — the
     SDK rejects it as `stale-round`.
  7. ONE POST = ONE TRANSITION. Never combine lifecycle markers
     in a single post (no `#done` + `#task` together). Post one
     of: `#done <result>` / `@peer #task #slug <problem>` /
     `#working <note>`. After `#done`, STOP — open the next
     `#task` in a later turn. The SDK rejects a mixed-marker hub
     post.

The hub's identity is shown in your context block as
"hosting · you are the hub" (you ARE) or "hub @<id>" (someone
else is). Read it before picking an action.

LANGUAGE. Match the language of the active `#task` in every
workgroup post.

DEFAULT POSTURE depends on whether you've already posted in
this active task:

  - You haven't posted yet (it's your FIRST round on this
    task): your default is **CONTRIBUTE FROM YOUR ROLE**. The
    hub assembled this workgroup specifically for the people
    listed; if you're a member, the hub thought your identity
    was relevant to this task. Post substantive content from
    your role's lens, even if it's a single concrete sentence.
  - You've already posted in this task: your default is
    **OBSERVER**. Speak again only with new content; otherwise
    let the round close.

`#SKIP` IS A LAST RESORT, NOT A DEFAULT. Post `#skip` only when:
  (a) Your identity has GENUINELY zero overlap with this
      specific task. (e.g. a sommelier in a workgroup deciding
      a tax filing question — there's no wine angle.) OR
  (b) You already posted substantively in a prior round of
      this same task and have nothing further this round.

DO NOT `#skip` because:
  ✗ The task feels generic. If you're a listed member, the
    hub picked you for THIS task — find your angle.
  ✗ You're not sure what to say. A half-formed thought from
    your distinct role is more valuable than a skip — other
    peers can build on partial ideas.
  ✗ Other peers seem to have it covered. Your distinct lens
    is the reason the hub assembled this group; even brief
    confirmation, disagreement, or a one-line risk-flag is
    value. Echo and silence are different: the first is
    noise, the second is abdication.

A whole workgroup of `#skip` posts is a degenerate result —
the SDK rejects the hub's `#done` in that case (`closure-
quorum`: zero substantive peer input). Don't be the model
that defaulted to `#skip` when your role was relevant.

When you do `#skip`, the form is: `workgroup_post(wg_id="…",
text="#skip <one-line reason>")`. The reason is optional but
useful for transparency ("waiting on FX data", "no wine angle
on this one"). Do NOT post a prose sentence describing your
decision (`I don't have a contribution`, `nothing to add`,
`deferring to peer`) — that's noise, not the structured
signal. `#skip` is the only valid pass marker.

True silence (no post at all) is reserved for: (a) the round
hasn't woken you on this active task yet, or (b) you're still
working with tools and will post substantive or `#skip` when
done.

POST WHEN you have ONE of these and not before:
  - You're @-mentioned with a direct question or instruction.
  - The active `#task` calls for your kind of contribution
    (your identity tells you which) AND you have substantive
    new content: a fact, a number, a source link, a concrete
    proposal, or a specific blocker.
  - [hub only] You have synthesis or a follow-up question that
    moves the task; or the deliverable is in the transcript and
    you're ready to `#done`.

DO NOT POST WHEN:
  ✗ The post mentions another peer, not you. Not your turn.
  ✗ You already posted in this round. SDK will reject anyway.
  ✗ Your message would be a paraphrase, refinement, or
    "different example of the same idea" relative to any of the
    last 3 posts. Not a contribution.
  ✗ THE WORKGROUP HAS ALREADY CONVERGED. If the last 3 posts
    (yours, the hub's, other members') are all variants of the
    same conclusion — even if each cites a fresh source or uses
    different examples — the discussion is over. The hub will
    close on the next round. Adding another paraphrase keeps
    the loop alive and burns budget across every peer's
    profile. Stay silent.
  ✗ All you have is "ok", "got it", "on it". Implicit
    acknowledgement; do the work instead.
  ✗ Your workgroup or profile budget is below 20% headroom and
    the message isn't critical to closing.

DO NOT WRITE:
  ✗ Don't @-mention peers unnecessarily — every mention wakes
    their service and burns their budget.
  ✗ Don't fabricate. If you don't have data, say "I don't know"
    or stay silent.

CLOSURE IS THE HUB'S DECISION. Read the transcript: is the
deliverable in the active `#task` actually produced? If yes —
post `#done <one-line synthesis>` and stop. If no — keep
waiting, or post a sharper question. Premature close is
recoverable (open a follow-up `#task`); a never-closing task
just rots context and burns budget.

DETECT YOUR OWN LOOP (hub-only — the most common closure
failure). Before posting as the hub, scan your own last 1-2
posts in the active task. If you would be:

  - Citing the same source, study, link, or quote you've
    already cited (even with a fresh framing or a slightly
    different angle), OR
  - Restating a conclusion that's already in the transcript
    (yours or a member's), OR
  - Adding "more evidence" for a position the workgroup has
    already converged on,

…you are looping. The members have heard you. The rotation
rule is keeping them silent on purpose: they posted, the round
is closed for them until you speak, and they're not going to
break a closed round to disagree with content they already
absorbed. Restating won't change their answer.

Your only valid next post in a loop state is `#done
<synthesis>`. If you genuinely can't synthesise yet (the
deliverable isn't in the transcript), the right move is
SILENCE — end the turn without posting and let the next
member-side trigger break the loop with new content. A new
restatement from you keeps the loop alive; the SDK won't
block it (it's a fresh round opener), but it's exactly the
failure mode this rule names.

When the active task stalls — either you (hub) talked last and
members went silent, OR a member talked last and you decided
silence — a watchdog re-invokes you exactly once per stalled
stretch with two valid outcomes: post `#done` or end the turn
without posting. The watchdog won't poke again for the same
stall, so if you stay silent the workgroup deadlocks until a
human intervenes (typically by posting a fresh `#task`, which
preempts). Use this single chance to close if you can — by then
the transcript almost always has enough material to synthesise.
Don't fight the rotation by posting more content; the SDK
rejects it as `turn-rotation`.

COSTS ARE REAL. Every `workgroup_post` auto-declares this
turn's USD cost. The hub gates against the workgroup's lifetime
budget; your profile's daily cap applies on top.
"""


WORKGROUP_GUARDRAILS_PIPELINE = """\
=== Workgroup engagement rules (pipeline) ===

This workgroup runs declared pipelines: the daemon sequences the
phases shown in your context block, posts each phase's task, and
runs each phase's gate mechanically. Your job is your phase, done
with tools, handed off cleanly.

THE PROTOCOL (SDK-enforced; a violating post is rejected):
  1. ONLY THE HUB OPENS a task, as `#task #<slug> <problem>`, and
     ONLY THE HUB CLOSES it with `#done <result>` — member `#task`
     and `#done` markers are rejected. You deliver with a normal
     substantive post.
  2. ONE CONTRIBUTING POST PER ROUND (hub post to hub post).
     `#working` heartbeats are exempt and capped at one per round.
  3. `#WORKING` (member-only) buys time, nothing else. Post it
     BEFORE any pass of work longer than ~30s, naming the concrete
     action and tool: `#working writing src/content/** (write_file)`.
     It must be the only non-empty line in that post; put no plan or
     delivery prose beside it.
     It does not consume your round slot and does not count as a
     contribution — you must still deliver.
  4. `#SKIP` (member-only) means "tasked, but nothing to do here":
     post `#skip <one-line reason>` and nothing else. Never a prose
     paraphrase of it.
  5. A NEW `#task` PREEMPTS the active one; stale reactions are
     rejected. ONE lifecycle marker per post — never `#done` +
     `#task` together.

WHEN TASKED (`@you` in the `#task`): post the one-line `#working`
heartbeat described above,
do the work with your tools, then hand off ONE substantive post in
the task's language: what you produced, where it lives on disk, what
you verified, and any blocker (state a blocker explicitly — the hub
routes on it). Do not narrate tool-by-tool progress across posts.

WHEN NOT TASKED: stay silent. A post that mentions another peer is
not your turn. Do not post acknowledgements ("ok", "on it"), do not
paraphrase other posts, and never fabricate — "I don't know" beats
an invented fact.

HUB: verify a delivery against the disk and gate log — never the prose —
then close `#done <result>`. A green gate opens its successor; after a
gate-less close, open the declared successor yourself when one exists.
Use `skipped` only before any substantive owner delivery; `BLOCKED`
halts the chain. Follow each watchdog wake's explicit repair instruction:
an early closure wake permits silence, while REPAIR requires resolution.

COSTS ARE REAL. Every `workgroup_post` auto-declares this turn's USD
cost against the workgroup budget; your profile's daily cap applies
on top.
"""


def _participants_line(active: tasks.Task, own_id: str) -> str:
    """One line: the active task's participant roster and whether the
    local profile is on it. Collective tasks (no participants) name no
    one — the whole workgroup may engage."""
    if not active.participants:
        return "task participants: everyone (collective task)"
    roster = " ".join(f"@{p}" for p in active.participants)
    if own_id in active.participants:
        return f"task participants: {roster} (you are on it — this task is yours)"
    return (
        f"task participants: {roster} "
        f"(NOT you, @{own_id} — `#skip` unless you're @-mentioned)"
    )


def _format_subscription_block(
    sub: sub_mod.Subscription, own_id: str, aliases: dict[str, str],
) -> str:
    posts = sub.recent_posts or []
    active = tasks.active_task(posts, hub_pubkey=sub.hub_pubkey)
    last = posts[-_RECENT_POSTS:]
    mentions = sum(
        1 for p in last
        if any(m == own_id for m in tasks.mentions_in(str(p.get("text", ""))))
    )

    lines = [
        f"#{sub.name or sub.wg_id}  "
        f"(wg_id={sub.wg_id} · joined · hub @{sub.hub_id})",
    ]
    if sub.briefing:
        lines.extend(_format_briefing(sub.briefing))
    lines.extend(_format_pipelines(sub.pipelines, sub.launch_pipeline, sub.phase_map))
    if sub.roster:
        roster_line = _format_roster(sub.roster, aliases, sub.roster_bios)
        if roster_line:
            lines.append(f"  members: {roster_line}")
    if active is not None:
        opener = aliases.get(active.opened_by, _short_author(active.opened_by))
        lines.append(
            f"  active task: {active.description}  "
            f"(opened by {opener} at seq #{active.opened_seq})",
        )
        lines.append("  " + _participants_line(active, own_id))
    else:
        lines.append("  no active task")
    if last:
        lines.append("  recent:")
        for p in last:
            who = aliases.get(p.get("from", ""), _short_author(p.get("from", "")))
            raw = str(p.get("text", ""))
            lines.append(
                f"    [#{p.get('seq')}] {who}: {_preview(raw, _post_cap(raw, own_id))}",
            )
    if mentions:
        lines.append(
            f"  → @{own_id} mentioned in {mentions} of the last "
            f"{len(last)} posts",
        )
    return "\n".join(lines)


def _format_roster(
    roster: dict[str, str], aliases: dict[str, str],
    bios: dict[str, str] | None = None,
) -> str:
    """Render the roster as ``@alice (online, "product engineer") ·
    @bob (last seen 12m ago, "systems engineer")``. "Online" = stamp
    within last 90s (≈3 poll ticks); otherwise show how long ago.
    Empty stamp = "unknown" (likely never pulled). The bio tag-line is
    self-published by each peer via ``public_bio`` and propagated to
    the hub on ``workgroup.join``; empty bio renders without the
    quoted suffix."""
    import datetime as _dt
    now = _dt.datetime.now(tz=_dt.timezone.utc)
    bios = bios or {}
    parts: list[str] = []
    for pubkey, stamp in roster.items():
        who = aliases.get(pubkey, _short_author(pubkey))
        bio = (bios.get(pubkey) or "").strip()
        if not stamp:
            status = "unknown"
        else:
            try:
                seen = _dt.datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ")
                seen = seen.replace(tzinfo=_dt.timezone.utc)
            except ValueError:
                status = "unknown"
            else:
                elapsed = (now - seen).total_seconds()
                if elapsed < 90:
                    status = "online"
                elif elapsed < 1800:
                    status = f"last seen {int(elapsed/60)}m ago"
                else:
                    status = "offline >30m"
        if bio:
            parts.append(f"{who} ({status}, \"{bio}\")")
        else:
            parts.append(f"{who} ({status})")
    return " · ".join(parts)


def _format_hub_block(
    home: Path, wg, own_id: str, own_pubkey: str, aliases: dict[str, str],
) -> str:
    """Hub-side view — the agent reads its own transcript locally."""
    transcript = _load_local_transcript(home, wg.meta.id)
    own_member = wg.member(own_pubkey)
    decrypted: list[dict] = []
    if own_member is not None:
        try:
            kp = load_or_generate(home)
            group_key = wg_mod.open_sealed_group_key(own_member.sealed_key, kp)
        except Exception:  # noqa: BLE001
            group_key = None
        if group_key is not None:
            for entry in transcript:
                if int(entry.get("key_version", 1)) != own_member.key_version:
                    continue
                try:
                    text = wg_mod.decrypt_post(
                        group_key, entry["nonce"], entry["ciphertext"],
                    ).decode("utf-8", errors="replace")
                except Exception:  # noqa: BLE001
                    continue
                decrypted.append({**entry, "text": text})

    active = tasks.active_task(decrypted, hub_pubkey=wg.meta.hub_pubkey)
    last = decrypted[-_RECENT_POSTS:]
    lines = [f"#{wg.meta.name}  (wg_id={wg.meta.id} · hosting · you are the hub)"]
    if wg.meta.briefing:
        lines.extend(_format_briefing(wg.meta.briefing))
    lines.extend(_format_pipelines(
        wg.meta.pipelines, wg.meta.launch_pipeline,
        wg_mod.safe_phase_map(wg.meta),
    ))
    if wg.members:
        roster = {m.pubkey: m.last_seen_at for m in wg.members}
        bios = {m.pubkey: m.bio for m in wg.members if m.bio}
        roster_line = _format_roster(roster, aliases, bios)
        if roster_line:
            lines.append(f"  members: {roster_line}")
    if wg.meta.paused:
        lines.append("  paused — posting suspended until resumed")
    if active is not None:
        opener = aliases.get(active.opened_by, _short_author(active.opened_by))
        lines.append(
            f"  active task: {active.description}  "
            f"(opened by {opener} at seq #{active.opened_seq})",
        )
        lines.append("  " + _participants_line(active, own_id))
    elif decrypted:
        lines.append("  no active task")
    if last:
        lines.append("  recent:")
        for p in last:
            who = aliases.get(p.get("from", ""), _short_author(p.get("from", "")))
            raw = str(p.get("text", ""))
            lines.append(
                f"    [#{p.get('seq')}] {who}: {_preview(raw, _post_cap(raw, own_id))}",
            )
    return "\n".join(lines)


def _build_aliases(home: Path, own_id: str, own_pubkey: str) -> dict[str, str]:
    """Map base64 pubkey → readable handle. Lets the system prompt
    block say ``@bob`` instead of ``author +W9SE6F5s3d2…``."""
    from alpi.alp import peers as peers_mod
    out: dict[str, str] = {own_pubkey: f"@{own_id}"}
    for p in peers_mod.load(home):
        out[p.pubkey] = f"@{p.id}"
    # Hub pubkeys for subscriptions might not appear in peers.yaml
    # under a friendly id — those still fall through to the short-
    # author rendering. That's an acceptable trade-off; the user can
    # always pin the hub explicitly to get a name.
    return out


def _profile_id(home: Path) -> str:
    if home == _ROOT:
        return "default"
    try:
        return home.relative_to(_ROOT / "profiles").parts[0]
    except Exception:  # noqa: BLE001
        return "me"


def _short_author(pubkey: str) -> str:
    return f"author {pubkey[:12]}…" if pubkey else "author ?"


def _preview(text: str, cap: int = _POST_PREVIEW_CHARS) -> str:
    text = text.strip()
    if len(text) <= cap:
        return text
    return text[: cap - 1] + "…"


def _post_cap(text: str, own_id: str) -> int:
    if own_id and any(m == own_id for m in tasks.mentions_in(text)):
        return _DIRECTED_POST_CHARS
    return _POST_PREVIEW_CHARS


def _format_pipelines(
    pipelines: dict, launch_pipeline: str | None, phase_map: dict,
) -> list[str]:
    """The declared chains with each phase's owner — replaces narrating them in a briefing."""
    if not pipelines:
        return []
    lines = ["  pipelines:"]
    for key, chain in pipelines.items():
        arrow = " → ".join(
            f"#{slug}" + (
                f" @{(phase_map.get(slug) or {}).get('owner')}"
                if (phase_map.get(slug) or {}).get("owner") else ""
            )
            for slug in chain
        )
        mark = " (launch)" if key == launch_pipeline else ""
        lines.append(f"  - {key}: {arrow}{mark}")
    if launch_pipeline is None:
        lines.append(
            "  - no launch pipeline: nothing starts on its own; the hub triggers a "
            "chain by name",
        )
    return lines


def _format_briefing(text: str) -> list[str]:
    text = text.strip()
    if len(text) > _BRIEFING_INJECT_CHARS:
        tail = f"… [briefing truncated at {_BRIEFING_INJECT_CHARS} chars]"
        text = text[: _BRIEFING_INJECT_CHARS - len(tail)].rstrip() + tail
    parts = text.splitlines() or [""]
    return [f"  briefing: {parts[0]}", *(f"            {line}" for line in parts[1:])]


def _load_local_transcript(home: Path, wg_id: str) -> list[dict]:
    p = home / "alp" / "workgroups" / wg_id / "transcript.jsonl"
    if not p.exists():
        return []
    out: list[dict] = []
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out
