"""Engine pre-turn hook: turn workgroup state into a system-prompt block.

Runs before every agent turn (interactive, gateway, scheduler) so
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
from alpi.alp import tasks
from alpi.alp import workgroup as wg_mod
from alpi.alp.keys import load_or_generate
from alpi.home import _ROOT


_RECENT_POSTS = 5            # show last N in the system-prompt block
_POST_PREVIEW_CHARS = 220
_MAX_BLOCKS = 10             # ceiling — protects token budget


def build(home: Path) -> str | None:
    """Return a system-prompt block describing every workgroup this
    profile participates in, or None if there are none. Safe to call
    on every turn — read-only against on-disk caches."""
    own_id = _profile_id(home)
    own_pubkey = load_or_generate(home).pubkey_b64()
    subs = sub_mod.load(home)
    hubs = wg_mod.list_workgroups(home)
    if not subs and not hubs:
        return None

    aliases = _build_aliases(home, own_id, own_pubkey)
    blocks: list[str] = []

    for sub in subs[:_MAX_BLOCKS]:
        block = _format_subscription_block(sub, own_id, aliases)
        if block:
            blocks.append(block)

    for wg in hubs[: _MAX_BLOCKS - len(blocks)]:
        block = _format_hub_block(home, wg, own_id, own_pubkey, aliases)
        if block:
            blocks.append(block)

    if not blocks:
        return None

    header = (
        f"=== Workgroups (you are @{own_id} · "
        f"{len(subs)} joined, {len(hubs)} hosting) ==="
    )
    return header + "\n\n" + "\n\n".join(blocks) + "\n\n" + WORKGROUP_GUARDRAILS


# Guardrails — prescriptive rules the agent reads on every turn.
# Defaults the agent to OBSERVER, not PARTICIPANT. The protocol
# permits any member to post; these rules bias behaviour so peers
# don't desyncrhonize into a pingpong loop that drains budgets.

WORKGROUP_GUARDRAILS = """\
=== Workgroup engagement rules ===

YOUR DEFAULT POSTURE IS OBSERVER. Workgroups are not chat rooms for
casual back-and-forth. They are focused collaborations with a real
budget that depletes with every post. Bias strongly toward silence.

POST (via `workgroup_post(wg_id="…", text="…")`) ONLY WHEN:
  ✓ A recent post explicitly @-mentions you AND you have substantive
    content to add (an answer, a result, a fact, a question that
    unblocks the task).
  ✓ The active #task is collective (no specific @-targets) AND you
    bring a unique capability the others can't, AND you can claim
    a concrete slice ("I'll take the literature review") rather
    than just acknowledging.
  ✓ You completed the work specified in the active #task and have a
    real result. Post a final message starting with
    `#done <one-line result summary>` to close the task.
  ✓ The recent posts have CONVERGED on a recommendation, OTHER
    participants have actually contributed (not just you), and
    nobody has closed yet. Then YOUR job is to close: post
    `#done <one-line summary of the agreed recommendation>` and
    stop. Do NOT add more details; do NOT propose more refinements.

DO NOT CLOSE (#done) WHEN:
  ✗ You are the first peer to respond to a `#task`. Other named
    participants must have a chance to contribute first. Closing
    alone means you decided unilaterally — that's not convergence.
  ✗ The active `#task` explicitly asks for evidence (`"cite
    sources"`, `"search the web"`, `"benchmarks"`, `"react to each
    other"`) and that work hasn't happened yet in the transcript.
    Do the asked work first; close only when the deliverable in
    the task description is genuinely done.
  ✗ Your `#done` would be the second post in the workgroup
    (kickoff + your close). At minimum the discussion needs your
    contribution AND at least one other peer's reaction.

CONVERGENCE DETECTION (critical to avoid paraphrase loops):
  Read the last 2-3 posts. If they all advocate the same direction,
  with each post mostly restating or refining the previous one in
  different words, the discussion is converged. Your options are:
    (a) Post `#done <summary>` and close — preferred.
    (b) Stay silent and let your peer close.
  DO NOT post yet another paraphrase of the same recommendation.
  That's the failure mode this rule exists to prevent.

REACT TO PROPOSALS (critical — this is the most common failure):
  If the most recent post by a peer contains a CONCRETE PROPOSAL
  (a specific stack/decision/path forward, not just evidence or
  questions), your next post MUST do exactly ONE of these:
    (a) ACCEPT and close: post `#done <1-2 line summary of the
        agreed decision>` — preferred when the proposal is workable.
    (b) COUNTER-PROPOSE specifically: "agreed except X, change to
        Y because Z". Be concrete; vague disagreement is noise.
    (c) BLOCK with a specific reason: cite a concrete blocker that
        prevents acceptance ("won't work because <fact>, here's the
        evidence: <link>").
  YOU MAY NOT post more research, evidence, or "I couldn't find
  numbers" updates after a peer has made a workable proposal.
  Searching for the perfect benchmark while a workable answer
  already exists in the transcript is the failure mode. If you
  have nothing to add and nothing to counter, stay silent and let
  another peer close.

STOP HUNTING NUMBERS:
  If you've already searched for the same data point twice and
  couldn't extract it, declare the limitation explicitly ("I can't
  find a direct comparison") AND take a position with the evidence
  you DO have. Repeating the same failed search is wasted budget.
  Decisions are made under uncertainty; that's fine.

CONVERGENCE BIAS AFTER 4 POSTS:
  Once the workgroup has 4+ substantive posts on the active task,
  your next post should bias toward closure: either accept a
  proposal with `#done`, counter-propose specifically, or stay
  silent. Adding another piece of evidence without taking a
  position is almost always wrong at this stage.

DO NOT POST WHEN:
  ✗ The post mentions another peer (not you). It's not your turn.
  ✗ The active #task tags peers other than you. The task is for them.
  ✗ Your previous post is the most recent in the transcript. Avoid
    back-to-back posts; let others respond first.
  ✗ You only have an acknowledgment ("ok", "got it", "on it"). These
    are noise. If you want to confirm, do it implicitly by starting
    the work.
  ✗ Your message would be a paraphrase, refinement, or echo of any
    of the last 3 posts. Not a contribution. Either close with
    `#done` or stay silent.
  ✗ Workgroup or profile budget is below 20% headroom. Stop posting
    unless the message is critical to the task.

DO NOT WRITE:
  ✗ Don't open new `#task` markers. Opening tasks is the human
    user's role (or the workgroup hub on their behalf). As an agent
    member, you RESPOND to tasks, you do not author them.
  ✗ Don't post `#done` unless the task work is genuinely complete or
    the discussion has converged on a single recommendation.
  ✗ Don't @-mention peers unnecessarily — every mention wakes their
    service and burns their budget.
  ✗ Don't fabricate. If you don't have data, say "I don't know" or
    stay silent.

COSTS ARE REAL:
  Every `workgroup_post` you make auto-declares this turn's USD
  cost. The hub gates against the workgroup's lifetime budget, and
  your profile's daily cap applies on top. Posting noise depletes
  both. Treat the budget the way you'd treat a shared credit card.
"""


def _format_subscription_block(
    sub: sub_mod.Subscription, own_id: str, aliases: dict[str, str],
) -> str:
    posts = sub.recent_posts or []
    active = tasks.active_task(posts)
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
        lines.append(f"  briefing: {_preview(sub.briefing)}")
    if sub.roster:
        roster_line = _format_roster(sub.roster, aliases)
        if roster_line:
            lines.append(f"  members: {roster_line}")
    if active is not None:
        opener = aliases.get(active.opened_by, _short_author(active.opened_by))
        lines.append(
            f"  active task: {active.description}  "
            f"(opened by {opener} at seq #{active.opened_seq})",
        )
    else:
        lines.append("  no active task")
    if last:
        lines.append("  recent:")
        for p in last:
            who = aliases.get(p.get("from", ""), _short_author(p.get("from", "")))
            text = _preview(str(p.get("text", "")))
            lines.append(f"    [#{p.get('seq')}] {who}: {text}")
    if mentions:
        lines.append(
            f"  → @{own_id} mentioned in {mentions} of the last "
            f"{len(last)} posts",
        )
    return "\n".join(lines)


def _format_roster(roster: dict[str, str], aliases: dict[str, str]) -> str:
    """Render the roster as ``@alice (online) · @bob (last seen 12m ago)``.
    "Online" = stamp within last 90s (≈3 poll ticks); otherwise we
    show how long ago. Empty stamp = "unknown" (likely never pulled)."""
    import datetime as _dt
    now = _dt.datetime.now(tz=_dt.timezone.utc)
    parts: list[str] = []
    for pubkey, stamp in roster.items():
        who = aliases.get(pubkey, _short_author(pubkey))
        if not stamp:
            parts.append(f"{who} (unknown)")
            continue
        try:
            seen = _dt.datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ")
            seen = seen.replace(tzinfo=_dt.timezone.utc)
        except ValueError:
            parts.append(f"{who} (unknown)")
            continue
        elapsed = (now - seen).total_seconds()
        if elapsed < 90:
            parts.append(f"{who} (online)")
        elif elapsed < 1800:
            parts.append(f"{who} (last seen {int(elapsed/60)}m ago)")
        else:
            parts.append(f"{who} (offline >30m)")
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

    active = tasks.active_task(decrypted)
    last = decrypted[-_RECENT_POSTS:]
    lines = [f"#{wg.meta.name}  (wg_id={wg.meta.id} · hosting · you are the hub)"]
    if wg.meta.briefing:
        lines.append(f"  briefing: {_preview(wg.meta.briefing)}")
    if wg.members:
        roster = {m.pubkey: m.last_seen_at for m in wg.members}
        roster_line = _format_roster(roster, aliases)
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
    elif decrypted:
        lines.append("  no active task")
    if last:
        lines.append("  recent:")
        for p in last:
            who = aliases.get(p.get("from", ""), _short_author(p.get("from", "")))
            lines.append(
                f"    [#{p.get('seq')}] {who}: {_preview(str(p.get('text','')))}",
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


def _preview(text: str) -> str:
    text = text.strip()
    if len(text) <= _POST_PREVIEW_CHARS:
        return text
    return text[: _POST_PREVIEW_CHARS - 1] + "…"


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
