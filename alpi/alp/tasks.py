"""In-chat protocol for ALP workgroups (PR 5).

Two markers parsed client-side on the decrypted transcript:

- ``#task <description>`` opens the active task. Preempts whatever
  was open before with synthetic result ``"preempted by …"``.
- ``#done <result>`` closes the active task. ``<result>`` is the
  text persisted with the task record.

Recognition rule: markers count only when they appear at the
**start of a line**, lowercase, with at least one space after the
marker keyword. So ``"I'll create a #task tomorrow"`` does NOT
open one — only a line beginning with ``#task `` does.

The hub stays zero-knowledge. Task state is recomputed on every
``pull`` by scanning the post stream in order. No separate state
file; the transcript IS the source of truth.

A post is identified by its ``seq`` (1-based monotonic). Each task
record carries ``opened_seq``, ``opened_by`` (pubkey b64), the
description text, and on close ``closed_seq``, ``closed_by``,
``result``. A task that never gets a ``#done`` stays open
indefinitely; preemption assigns
``result = "preempted by <new>"`` and ``closed_*`` from the new
``#task`` post.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


# Marker recognition — at the start of a line, optionally preceded
# by one or more ``@<peer>`` handles (the natural way humans address
# tasks: ``@alice @bob #task <description>``). Single space required
# after the marker keyword, the rest of the line is the payload.
_TASK_RE = re.compile(
    r"^(?:@\S+\s+)*#task\s+#([A-Za-z0-9][A-Za-z0-9_-]{0,63})(?:\s+(.+?))?\s*$",
    re.MULTILINE,
)
# Matches any ``#task`` opener line regardless of slug — used for "this post tried to open a task" detection so the SDK can reject slug-less attempts with a clear error before encryption.
_TASK_INTENT_RE = re.compile(
    r"^(?:@\S+\s+)*#task\b.*$", re.MULTILINE,
)
_DONE_RE = re.compile(
    r"^(?:@\S+\s+)*#done\s+(.+?)\s*$", re.MULTILINE,
)
# ``#skip`` is the member-side "I considered and have nothing to add"
# signal. Final answer for this round — counts toward closure-quorum
# but NOT as substantive. Payload optional ("waiting on FX data").
_SKIP_RE = re.compile(
    r"^(?:@\S+\s+)*#skip(?:\s+(.+?))?\s*$", re.MULTILINE,
)
# ``#working`` is the member-side "I'm processing, give me time"
# heartbeat. Posted at the start of a turn that will use slow tools
# (web_fetch, research, multi-step delegate). Does NOT consume the
# round slot — the same member may post substantive or `#skip`
# afterwards in the same round. Does NOT satisfy closure-quorum on
# its own (a member who only `#working`'d hasn't actually
# contributed). The hub uses recent `#working` posts as a hint to
# wait longer, but the 10-minute closure-quorum timeout still
# applies as a hard ceiling.
_WORKING_RE = re.compile(
    r"^(?:@\S+\s+)*#working(?:\s+(.+?))?\s*$", re.MULTILINE,
)


@dataclass(frozen=True)
class TaskEvent:
    """One marker found in a post's plaintext body."""
    kind: str          # "task" or "done"
    text: str          # description (task) or result (done)
    seq: int           # post seq this marker came from
    by: str            # author pubkey b64
    slug: str = ""     # stable identifier for `#task` events ("" for `#done`)


@dataclass(frozen=True)
class Task:
    """An open or closed task in a workgroup."""
    description: str
    opened_seq: int
    opened_by: str
    slug: str = ""                   # stable identifier captured at open time
    closed_seq: int | None = None    # None while open
    closed_by: str | None = None
    result: str | None = None        # None while open

    @property
    def is_open(self) -> bool:
        return self.closed_seq is None


def has_markers(text: str) -> list[str]:
    """Return the lifecycle markers (``task``, ``done``) present in
    ``text``. ``#skip`` is intentionally NOT in this list — it is a
    member-side signal, not a hub-only lifecycle marker, so it
    doesn't gate the same SDK rejection path."""
    out: list[str] = []
    if _TASK_RE.search(text or ""):
        out.append("task")
    if _DONE_RE.search(text or ""):
        out.append("done")
    return out


def is_done(text: str) -> bool:
    """``True`` when the post contains a valid ``#done <…>`` marker
    (start of line, line-anchored, with a non-empty payload). Used by
    the rotation enforcement to allow the hub one back-to-back post
    when (and only when) it is closing the active task."""
    return _DONE_RE.search(text or "") is not None


def is_task(text: str) -> bool:
    """``True`` when the post contains a valid ``#task <…>`` marker.
    Used by the rotation enforcement to allow a hub `#task` post
    even when the hub spoke last — opening a new task is a
    lifecycle action that preempts the previous one, not "more
    content", so the back-to-back rule doesn't apply."""
    return _TASK_RE.search(text or "") is not None


def is_skip(text: str) -> bool:
    """``True`` when the post contains a ``#skip`` marker (member
    signals "considered, no contribution this round"). Used by the
    closure-quorum check to count a member as having participated
    in the active task even when they had nothing substantive."""
    return _SKIP_RE.search(text or "") is not None


def is_working(text: str) -> bool:
    """``True`` when the post contains a ``#working`` marker (member
    signals "processing with tools, give me more time"). Used by:

    - **Rotation**: ``#working`` posts don't consume the round slot,
      so a member can `#working` then later post substantive in the
      same round. The SDK still caps at one `#working` per round to
      prevent heartbeat spam.
    - **Closure-quorum**: a member who only posted ``#working`` (and
      neither substantive content nor ``#skip``) hasn't actually
      contributed and is still pending in the quorum check.
    """
    return _WORKING_RE.search(text or "") is not None


def parse_post(
    text: str, seq: int, by: str, hub_pubkey: str | None = None,
) -> list[TaskEvent]:
    """Extract markers from a single decrypted post body. Returns the
    events in document order. A post with both a ``#task`` and a
    ``#done`` is **ambiguous** and yields the empty list — the engine
    should treat it as plain prose."""
    if hub_pubkey is not None and by != hub_pubkey:
        return []
    tasks = list(_TASK_RE.finditer(text or ""))
    dones = list(_DONE_RE.finditer(text or ""))
    if tasks and dones:
        return []
    out: list[TaskEvent] = []
    for m in tasks:
        slug = m.group(1).lower()
        desc = (m.group(2) or "").strip()
        out.append(TaskEvent(
            kind="task", text=desc, seq=seq, by=by, slug=slug,
        ))
    for m in dones:
        result = m.group(1).strip()
        if result:
            out.append(TaskEvent(kind="done", text=result, seq=seq, by=by))
    return out


def fold_tasks(events: Iterable[TaskEvent]) -> list[Task]:
    """Reduce an in-order stream of events into the task ledger.

    Single-task model: one task open at a time. Posting a new
    ``#task`` while one is open implicitly closes the previous one
    with ``result = "preempted by <new description>"``. ``#done``
    against an empty active slot is a silent no-op.
    """
    closed: list[Task] = []
    active: Task | None = None
    for ev in events:
        if ev.kind == "task":
            if active is not None:
                closed.append(Task(
                    description=active.description,
                    opened_seq=active.opened_seq,
                    opened_by=active.opened_by,
                    slug=active.slug,
                    closed_seq=ev.seq,
                    closed_by=ev.by,
                    result=f"preempted by #{ev.slug}" if ev.slug else "preempted",
                ))
            active = Task(
                description=ev.text,
                opened_seq=ev.seq,
                opened_by=ev.by,
                slug=ev.slug,
            )
        elif ev.kind == "done":
            if active is None:
                continue  # silent no-op
            closed.append(Task(
                description=active.description,
                opened_seq=active.opened_seq,
                opened_by=active.opened_by,
                slug=active.slug,
                closed_seq=ev.seq,
                closed_by=ev.by,
                result=ev.text,
            ))
            active = None
    return closed + ([active] if active is not None else [])


def active_task(
    decrypted_posts: Iterable[dict], hub_pubkey: str | None = None,
) -> Task | None:
    """Scan a decrypted transcript and return the active task, or
    None if none is open. Each post must have ``seq`` (int),
    ``from`` (pubkey b64), and ``text`` (decrypted plaintext)."""
    events: list[TaskEvent] = []
    for p in decrypted_posts:
        events.extend(parse_post(
            text=str(p.get("text", "")),
            seq=int(p.get("seq", 0)),
            by=str(p.get("from", "")),
            hub_pubkey=hub_pubkey,
        ))
    for t in fold_tasks(events):
        if t.is_open:
            return t
    return None


# Mention extraction — used by the engine to flag @mentions of the
# current profile in the most recent posts so the system prompt can
# nudge the agent to engage. Mentions must be at start of token
# (preceded by start-of-string or whitespace) and the id is the
# token immediately after the ``@``.

_MENTION_RE = re.compile(r"(?:^|\s)@([A-Za-z0-9_-]+)\b")


def mentions_in(text: str) -> list[str]:
    """Return every peer-id mentioned in ``text``, in order, no dedup."""
    return [m.group(1) for m in _MENTION_RE.finditer(text or "")]


def has_task_intent(text: str) -> bool:
    """``True`` when any line of the post starts a `#task` opener attempt — regardless of whether the slug is valid. Used by the SDK to distinguish "the author tried to open a task but messed up" from "this is plain prose"."""
    return _TASK_INTENT_RE.search(text or "") is not None


def is_valid_task_open(text: str) -> bool:
    """``True`` when the post contains a properly-formed `#task #<slug>` opener line."""
    return _TASK_RE.search(text or "") is not None
