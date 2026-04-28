"""ALP.3 PR 5 — in-chat task protocol parsing.

Covers ``alpi.alp.tasks.parse_post`` / ``fold_tasks`` /
``active_task`` / ``mentions_in``. The hub stays zero-knowledge —
all of this runs against the decrypted transcript on each member's
side, so the tests work on plain dicts without spinning up a
server.
"""

from __future__ import annotations

import pytest

from alpi.alp import tasks


def _post(seq: int, frm: str, text: str) -> dict:
    return {"seq": seq, "from": frm, "text": text}


# parse_post


def test_parse_post_extracts_task_marker_at_start_of_line() -> None:
    events = tasks.parse_post("#task research peptides for protein X", 1, "alice")
    assert len(events) == 1
    assert events[0].kind == "task"
    assert events[0].text == "research peptides for protein X"
    assert events[0].seq == 1
    assert events[0].by == "alice"


def test_parse_post_accepts_leading_at_mentions_before_marker() -> None:
    """Real-world kickoffs put @-mentions before the marker:
    ``@alice @bob #task analyze the stack``. The natural address-then-
    instruction shape must parse as a task."""
    events = tasks.parse_post(
        "@alice @bob #task analyze the stack choice", 1, "user",
    )
    assert len(events) == 1
    assert events[0].kind == "task"
    assert events[0].text == "analyze the stack choice"


def test_parse_post_done_with_leading_at_mentions() -> None:
    events = tasks.parse_post("@alice #done shortlist of 5", 7, "alice")
    assert len(events) == 1
    assert events[0].kind == "done"
    assert events[0].text == "shortlist of 5"


def test_parse_post_ignores_inline_task_marker() -> None:
    """`#task` mid-sentence does NOT open one — only line starts."""
    events = tasks.parse_post(
        "I'll create a #task tomorrow when we know more.", 1, "alice",
    )
    assert events == []


def test_parse_post_extracts_done_marker_with_result() -> None:
    events = tasks.parse_post(
        "#done shortlist of 5 candidates: A, B, C, D, E", 7, "alice",
    )
    assert len(events) == 1
    assert events[0].kind == "done"
    assert events[0].text == "shortlist of 5 candidates: A, B, C, D, E"


def test_parse_post_with_both_markers_is_ambiguous() -> None:
    """A post containing both a #task and a #done at line starts is
    treated as ambiguous and yields no events — the engine logs a
    warning (not under test here) and treats the post as plain prose."""
    text = "#task new direction\n#done old one wrapped"
    assert tasks.parse_post(text, 5, "alice") == []


def test_parse_post_silent_on_empty_marker() -> None:
    """`#task` with no text after it is a silent no-op."""
    assert tasks.parse_post("#task   ", 1, "alice") == []
    assert tasks.parse_post("#done\n", 2, "alice") == []


def test_parse_post_handles_multiline_post() -> None:
    """A long post can have a marker on one line and prose on another."""
    text = (
        "Here's what I think we should pursue:\n"
        "#task literature review of recent papers (2024-2026)\n"
        "I'll start tomorrow."
    )
    events = tasks.parse_post(text, 3, "bob")
    assert len(events) == 1
    assert events[0].kind == "task"
    assert events[0].text == "literature review of recent papers (2024-2026)"


# fold_tasks


def test_fold_tasks_single_open_close_cycle() -> None:
    events = [
        tasks.TaskEvent("task", "research X", 1, "alice"),
        tasks.TaskEvent("done", "found 5 candidates", 4, "bob"),
    ]
    folded = tasks.fold_tasks(events)
    assert len(folded) == 1
    t = folded[0]
    assert t.description == "research X"
    assert t.is_open is False
    assert t.closed_seq == 4
    assert t.closed_by == "bob"
    assert t.result == "found 5 candidates"


def test_fold_tasks_active_task_remains_open() -> None:
    events = [tasks.TaskEvent("task", "research X", 1, "alice")]
    folded = tasks.fold_tasks(events)
    assert len(folded) == 1
    assert folded[0].is_open is True
    assert folded[0].result is None


def test_fold_tasks_preempt_writes_synthetic_result() -> None:
    """Posting a new #task while one is open closes the previous with
    ``result = "preempted by <new>"`` and starts the new one."""
    events = [
        tasks.TaskEvent("task", "research X", 1, "alice"),
        tasks.TaskEvent("task", "switch to Y", 3, "alice"),
    ]
    folded = tasks.fold_tasks(events)
    assert len(folded) == 2
    closed, active = folded
    assert closed.description == "research X"
    assert closed.is_open is False
    assert closed.result == "preempted by switch to Y"
    assert closed.closed_seq == 3
    assert active.description == "switch to Y"
    assert active.is_open is True


def test_fold_tasks_done_with_no_active_is_noop() -> None:
    events = [tasks.TaskEvent("done", "stray result", 1, "alice")]
    assert tasks.fold_tasks(events) == []


def test_fold_tasks_full_lifecycle_with_preempt() -> None:
    events = [
        tasks.TaskEvent("task", "A", 1, "alice"),
        tasks.TaskEvent("task", "B", 2, "alice"),    # preempts A
        tasks.TaskEvent("done", "B done", 3, "bob"),
        tasks.TaskEvent("task", "C", 4, "alice"),
    ]
    folded = tasks.fold_tasks(events)
    assert len(folded) == 3
    a, b, c = folded
    assert a.description == "A" and a.result == "preempted by B"
    assert b.description == "B" and b.result == "B done"
    assert c.description == "C" and c.is_open


# active_task — high-level helper used by the engine pre-turn hook


def test_active_task_returns_open_task() -> None:
    posts = [
        _post(1, "alice", "#task research peptides"),
        _post(2, "bob",   "ok, splitting into lit + screening"),
        _post(3, "mirai", "screening pipeline ready"),
    ]
    active = tasks.active_task(posts)
    assert active is not None
    assert active.description == "research peptides"
    assert active.opened_seq == 1
    assert active.opened_by == "alice"


def test_active_task_returns_none_after_done() -> None:
    posts = [
        _post(1, "alice", "#task research peptides"),
        _post(2, "alice", "#done found 5"),
    ]
    assert tasks.active_task(posts) is None


def test_active_task_picks_latest_after_preempt() -> None:
    posts = [
        _post(1, "alice", "#task research peptides"),
        _post(2, "bob",   "I think we should pivot"),
        _post(3, "alice", "#task pivot to small molecules"),
    ]
    active = tasks.active_task(posts)
    assert active is not None
    assert active.description == "pivot to small molecules"
    assert active.opened_seq == 3


def test_active_task_returns_none_on_empty_transcript() -> None:
    assert tasks.active_task([]) is None


# Hub-only marker enforcement


def test_has_markers_detects_task_and_done() -> None:
    assert tasks.has_markers("#task do the thing") == ["task"]
    assert tasks.has_markers("@alice #done it's done") == ["done"]
    assert tasks.has_markers("plain text only") == []
    assert tasks.has_markers("") == []
    # Inline mention is not a marker.
    assert tasks.has_markers("converge with #done eventually") == []


def test_parse_post_ignores_non_hub_markers_when_filter_set() -> None:
    """A non-hub member who writes `#done` in a post body must be
    ignored by the protocol — the hub is the manager."""
    HUB = "HUB_PK"
    BOB = "BOB_PK"
    # Hub author with hub_pubkey filter → markers count.
    events = tasks.parse_post(
        "#task pick stack", seq=1, by=HUB, hub_pubkey=HUB,
    )
    assert len(events) == 1 and events[0].kind == "task"
    # Non-hub author → ignored.
    events = tasks.parse_post(
        "#done my unilateral decision", seq=2, by=BOB, hub_pubkey=HUB,
    )
    assert events == []


def test_active_task_ignores_non_hub_close() -> None:
    """If a non-hub member posts `#done`, active_task() with hub
    filter still sees the task as open."""
    HUB = "HUB_PK"
    BOB = "BOB_PK"
    posts = [
        {"seq": 1, "from": HUB, "text": "#task pick stack"},
        {"seq": 2, "from": BOB, "text": "#done FastAPI"},  # ignored
    ]
    # Without filter, the non-hub close looks valid.
    assert tasks.active_task(posts) is None
    # With hub filter, the task remains open.
    active = tasks.active_task(posts, hub_pubkey=HUB)
    assert active is not None and active.description == "pick stack"


# mentions_in


def test_mentions_in_collects_handles_in_order() -> None:
    text = "@alice please coordinate with @bob and @mirai"
    assert tasks.mentions_in(text) == ["alice", "bob", "mirai"]


def test_mentions_in_ignores_email_addresses() -> None:
    """@ inside an email is preceded by a non-space char, so it should
    NOT be treated as a mention."""
    assert tasks.mentions_in("contact me at javi@example.com") == []


def test_mentions_in_handles_start_of_string_mention() -> None:
    assert tasks.mentions_in("@alice on it") == ["alice"]


def test_mentions_in_handles_punctuation_after_handle() -> None:
    assert tasks.mentions_in("@alice, @bob: please review") == ["alice", "bob"]


def test_mentions_in_returns_empty_for_no_mentions() -> None:
    assert tasks.mentions_in("just some prose, no handles here") == []


# Integration: parse_post + fold_tasks against a realistic flow


def test_realistic_workgroup_lifecycle() -> None:
    """The kind of transcript a real workgroup produces — emulates the
    'agents collaborate' pattern with #task / #done / @mentions."""
    posts = [
        _post(1, "alice", "#task research peptides for protein X. shortlist 5."),
        _post(2, "bob",   "on it. @mirai you do screening, I'll do lit review."),
        _post(3, "mirai", "pipeline ready, running 1200 candidates."),
        _post(4, "bob",   "found 3 strong papers."),
        _post(5, "mirai", "results: A, B, C, D, E all Tanimoto > 0.7"),
        _post(6, "alice", "#done shortlist: A, B, C, D, E."),
    ]
    assert tasks.active_task(posts) is None  # closed cleanly

    # Walk events to confirm the timeline
    all_events = []
    for p in posts:
        all_events.extend(tasks.parse_post(p["text"], p["seq"], p["from"]))
    folded = tasks.fold_tasks(all_events)
    assert len(folded) == 1
    t = folded[0]
    assert t.description.startswith("research peptides")
    assert t.opened_seq == 1
    assert t.closed_seq == 6
    assert t.result.startswith("shortlist")
