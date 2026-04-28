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
    r"^(?:@\S+\s+)*#task\s+(.+?)\s*$", re.MULTILINE,
)
_DONE_RE = re.compile(
    r"^(?:@\S+\s+)*#done\s+(.+?)\s*$", re.MULTILINE,
)


@dataclass(frozen=True)
class TaskEvent:
    """One marker found in a post's plaintext body."""
    kind: str          # "task" or "done"
    text: str          # description (task) or result (done)
    seq: int           # post seq this marker came from
    by: str            # author pubkey b64


@dataclass(frozen=True)
class Task:
    """An open or closed task in a workgroup."""
    description: str
    opened_seq: int
    opened_by: str
    closed_seq: int | None = None    # None while open
    closed_by: str | None = None
    result: str | None = None        # None while open

    @property
    def is_open(self) -> bool:
        return self.closed_seq is None


def has_markers(text: str) -> list[str]:
    out: list[str] = []
    if _TASK_RE.search(text or ""):
        out.append("task")
    if _DONE_RE.search(text or ""):
        out.append("done")
    return out


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
        desc = m.group(1).strip()
        if desc:
            out.append(TaskEvent(kind="task", text=desc, seq=seq, by=by))
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
                    closed_seq=ev.seq,
                    closed_by=ev.by,
                    result=f"preempted by {ev.text}",
                ))
            active = Task(
                description=ev.text,
                opened_seq=ev.seq,
                opened_by=ev.by,
            )
        elif ev.kind == "done":
            if active is None:
                continue  # silent no-op
            closed.append(Task(
                description=active.description,
                opened_seq=active.opened_seq,
                opened_by=active.opened_by,
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
