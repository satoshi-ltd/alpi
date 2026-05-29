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
    events = tasks.parse_post(
        "#task #peptides-protein-x research peptides for protein X", 1, "alice",
    )
    assert len(events) == 1
    assert events[0].kind == "task"
    assert events[0].slug == "peptides-protein-x"
    assert events[0].text == "research peptides for protein X"
    assert events[0].seq == 1
    assert events[0].by == "alice"


def test_parse_post_accepts_leading_at_mentions_before_marker() -> None:
    """Real-world kickoffs put @-mentions before the marker:
    ``@alice @bob #task #slug analyze the stack``."""
    events = tasks.parse_post(
        "@alice @bob #task #stack-choice analyze the stack choice", 1, "user",
    )
    assert len(events) == 1
    assert events[0].kind == "task"
    assert events[0].slug == "stack-choice"
    assert events[0].text == "analyze the stack choice"


def test_parse_post_task_slug_lowercased() -> None:
    events = tasks.parse_post("#task #Mixed-Case-Slug a title", 1, "alice")
    assert events[0].slug == "mixed-case-slug"


def test_parse_post_task_slug_only_no_text() -> None:
    """A `#task #slug` with no description is still a valid task open."""
    events = tasks.parse_post("#task #icp-v2", 1, "alice")
    assert len(events) == 1
    assert events[0].kind == "task"
    assert events[0].slug == "icp-v2"
    assert events[0].text == ""


def test_parse_post_task_missing_slug_is_not_a_task() -> None:
    """`#task <text>` without a `#<slug>` does not open a task."""
    assert tasks.parse_post("#task no slug here", 1, "alice") == []
    assert tasks.parse_post("@alice #task another one", 1, "alice") == []


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
    text = "#task #new-dir new direction\n#done old one wrapped"
    assert tasks.parse_post(text, 5, "alice") == []


def test_parse_post_silent_on_empty_marker() -> None:
    """`#task` with no slug is a silent no-op; `#done` with no payload too."""
    assert tasks.parse_post("#task   ", 1, "alice") == []
    assert tasks.parse_post("#done\n", 2, "alice") == []


def test_parse_post_handles_multiline_post() -> None:
    """A long post can have a marker on one line and prose on another."""
    text = (
        "Here's what I think we should pursue:\n"
        "#task #lit-review-2024-26 literature review of recent papers\n"
        "I'll start tomorrow."
    )
    events = tasks.parse_post(text, 3, "bob")
    assert len(events) == 1
    assert events[0].kind == "task"
    assert events[0].slug == "lit-review-2024-26"
    assert events[0].text == "literature review of recent papers"


# fold_tasks


def test_fold_tasks_single_open_close_cycle() -> None:
    events = [
        tasks.TaskEvent("task", "research X", 1, "alice", slug="research-x"),
        tasks.TaskEvent("done", "found 5 candidates", 4, "bob"),
    ]
    folded = tasks.fold_tasks(events)
    assert len(folded) == 1
    t = folded[0]
    assert t.description == "research X"
    assert t.slug == "research-x"
    assert t.is_open is False
    assert t.closed_seq == 4
    assert t.closed_by == "bob"
    assert t.result == "found 5 candidates"


def test_fold_tasks_active_task_remains_open() -> None:
    events = [tasks.TaskEvent("task", "research X", 1, "alice", slug="research-x")]
    folded = tasks.fold_tasks(events)
    assert len(folded) == 1
    assert folded[0].is_open is True
    assert folded[0].slug == "research-x"
    assert folded[0].result is None


def test_fold_tasks_preempt_writes_synthetic_result() -> None:
    """Posting a new #task while one is open closes the previous with
    ``result = "preempted by #<new-slug>"`` and starts the new one."""
    events = [
        tasks.TaskEvent("task", "research X", 1, "alice", slug="research-x"),
        tasks.TaskEvent("task", "switch to Y", 3, "alice", slug="switch-y"),
    ]
    folded = tasks.fold_tasks(events)
    assert len(folded) == 2
    closed, active = folded
    assert closed.description == "research X"
    assert closed.slug == "research-x"
    assert closed.is_open is False
    assert closed.result == "preempted by #switch-y"
    assert closed.closed_seq == 3
    assert active.description == "switch to Y"
    assert active.slug == "switch-y"
    assert active.is_open is True


def test_fold_tasks_done_with_no_active_is_noop() -> None:
    events = [tasks.TaskEvent("done", "stray result", 1, "alice")]
    assert tasks.fold_tasks(events) == []


def test_fold_tasks_full_lifecycle_with_preempt() -> None:
    events = [
        tasks.TaskEvent("task", "A", 1, "alice", slug="a"),
        tasks.TaskEvent("task", "B", 2, "alice", slug="b"),    # preempts A
        tasks.TaskEvent("done", "B done", 3, "bob"),
        tasks.TaskEvent("task", "C", 4, "alice", slug="c"),
    ]
    folded = tasks.fold_tasks(events)
    assert len(folded) == 3
    a, b, c = folded
    assert a.slug == "a" and a.result == "preempted by #b"
    assert b.slug == "b" and b.result == "B done"
    assert c.slug == "c" and c.is_open


# active_task — high-level helper used by the engine pre-turn hook


def test_active_task_returns_open_task() -> None:
    posts = [
        _post(1, "alice", "#task #peptides research peptides"),
        _post(2, "bob",   "ok, splitting into lit + screening"),
        _post(3, "mirai", "screening pipeline ready"),
    ]
    active = tasks.active_task(posts)
    assert active is not None
    assert active.description == "research peptides"
    assert active.slug == "peptides"
    assert active.opened_seq == 1
    assert active.opened_by == "alice"


def test_active_task_returns_none_after_done() -> None:
    posts = [
        _post(1, "alice", "#task #peptides research peptides"),
        _post(2, "alice", "#done found 5"),
    ]
    assert tasks.active_task(posts) is None


def test_active_task_picks_latest_after_preempt() -> None:
    posts = [
        _post(1, "alice", "#task #peptides research peptides"),
        _post(2, "bob",   "I think we should pivot"),
        _post(3, "alice", "#task #small-molecules pivot to small molecules"),
    ]
    active = tasks.active_task(posts)
    assert active is not None
    assert active.description == "pivot to small molecules"
    assert active.slug == "small-molecules"
    assert active.opened_seq == 3


def test_active_task_returns_none_on_empty_transcript() -> None:
    assert tasks.active_task([]) is None


# Hub-only marker enforcement


def test_has_markers_detects_task_and_done() -> None:
    assert tasks.has_markers("#task #thing do the thing") == ["task"]
    assert tasks.has_markers("@alice #done it's done") == ["done"]
    assert tasks.has_markers("plain text only") == []
    assert tasks.has_markers("") == []
    # Inline mention is not a marker.
    assert tasks.has_markers("converge with #done eventually") == []
    # `#task` without a slug is NOT a recognised task marker.
    assert tasks.has_markers("#task no slug") == []


def test_parse_post_ignores_non_hub_markers_when_filter_set() -> None:
    """A non-hub member who writes `#done` in a post body must be
    ignored by the protocol — the hub is the manager."""
    HUB = "HUB_PK"
    BOB = "BOB_PK"
    # Hub author with hub_pubkey filter → markers count.
    events = tasks.parse_post(
        "#task #stack pick stack", seq=1, by=HUB, hub_pubkey=HUB,
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
        {"seq": 1, "from": HUB, "text": "#task #stack pick stack"},
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
        _post(1, "alice", "#task #peptides-protein-x research peptides for protein X. shortlist 5."),
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


# ---------------------------------------------------------------------------
# Boolean marker helpers — `is_task`, `is_done`, `is_skip`, `is_working`
# ---------------------------------------------------------------------------
#
# These are cheap line-anchored predicates the SDK uses to gate
# rotation / closure-quorum / preempt logic without having to fold
# the full task ledger. Each must:
#   - Recognize the marker at start of line (with optional leading
#     ``@<peer>`` mentions).
#   - Tolerate the optional payload (`#skip` / `#working` allow no
#     payload; `#task` / `#done` require non-empty payload).
#   - NOT trigger on the marker word appearing mid-sentence.


def test_is_task_recognizes_anchored_marker() -> None:
    assert tasks.is_task("#task #path-a pick path A") is True
    assert tasks.is_task("@alice @bob #task #framing framing") is True


def test_is_task_ignores_inline_word_and_slugless_task() -> None:
    assert tasks.is_task("I'll create a #task tomorrow") is False
    assert tasks.is_task("plain content with no marker") is False
    # Without a slug, `#task` is not a recognised opener.
    assert tasks.is_task("#task no slug here") is False


def test_is_done_recognizes_anchored_marker() -> None:
    assert tasks.is_done("#done shortlist: A, B, C") is True
    assert tasks.is_done("@bob #done finalised") is True


def test_is_done_ignores_inline_word() -> None:
    assert tasks.is_done("we're not #done yet") is False


def test_is_skip_recognizes_with_or_without_payload() -> None:
    assert tasks.is_skip("#skip") is True
    assert tasks.is_skip("#skip no wine angle here") is True
    assert tasks.is_skip("@alice #skip waiting on data") is True


def test_is_skip_ignores_inline() -> None:
    assert tasks.is_skip("I should #skip this round") is False
    assert tasks.is_skip("regular content") is False


def test_is_working_recognizes_with_or_without_payload() -> None:
    assert tasks.is_working("#working") is True
    assert tasks.is_working("#working researching FX trends") is True
    assert tasks.is_working("@bob #working pulling sources") is True


def test_is_working_ignores_inline() -> None:
    assert tasks.is_working("I'm currently #working on this") is False


# ---------------------------------------------------------------------------
# `has_markers` — what gates SDK rejection from non-hubs
# ---------------------------------------------------------------------------
#
# Only ``task`` and ``done`` are returned because those are the
# hub-only lifecycle markers — the SDK rejects member posts
# containing them. ``#skip`` and ``#working`` are member-side
# signals that go through unchallenged.


def test_has_markers_excludes_skip_and_working() -> None:
    assert tasks.has_markers("#skip") == []
    assert tasks.has_markers("#working researching") == []


def test_has_markers_includes_task_and_done() -> None:
    assert "task" in tasks.has_markers("#task #x X")
    assert "done" in tasks.has_markers("#done Y")
    both = tasks.has_markers("#task #a A\n#done B")
    assert "task" in both and "done" in both


# ---------------------------------------------------------------------------
# Task-intent helpers — used by the SDK to enforce the slug requirement
# ---------------------------------------------------------------------------


def test_has_task_intent_matches_slugged_and_slugless() -> None:
    assert tasks.has_task_intent("#task #slug title") is True
    assert tasks.has_task_intent("#task no slug") is True
    assert tasks.has_task_intent("@alice #task no slug") is True
    assert tasks.has_task_intent("plain prose") is False
    assert tasks.has_task_intent("inline #task reference") is False


def test_is_valid_task_open_matches_only_with_slug() -> None:
    assert tasks.is_valid_task_open("#task #slug title") is True
    assert tasks.is_valid_task_open("#task #slug") is True
    assert tasks.is_valid_task_open("#task no slug") is False
    assert tasks.is_valid_task_open("#task # invalid") is False
    assert tasks.is_valid_task_open("#task #-leading-hyphen") is False


# ---------------------------------------------------------------------------
# Skip / working markers are NOT confused for task lifecycle events
# ---------------------------------------------------------------------------


def test_parse_post_does_not_emit_events_for_skip_or_working() -> None:
    """`#skip` and `#working` are protocol-level signals (rotation +
    closure-quorum) but they don't move the task ledger. The parser
    must keep ignoring them for fold_tasks / active_task purposes."""
    events = tasks.parse_post("#skip no opinion here", seq=2, by="bob")
    assert events == []
    events = tasks.parse_post("#working researching", seq=3, by="carol")
    assert events == []
