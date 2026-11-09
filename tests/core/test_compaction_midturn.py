from __future__ import annotations

from alpi import compaction


def _msg(role: str, content: str, **extra) -> dict:
    return {"role": role, "content": content, **extra}


def _call(call_id: str) -> dict:
    return {"id": call_id, "type": "function", "function": {"name": "search", "arguments": "{}"}}


def test_prune_shrinks_only_tool_outputs_behind_the_tail() -> None:
    messages = [_msg("system", "sys"), _msg("user", "go")]
    for i in range(6):
        messages.append(_msg("assistant", None, tool_calls=[_call(f"c{i}")]))
        messages.append(_msg("tool", "x" * 10_000, name="search", tool_call_id=f"c{i}"))
    pruned = compaction._prune_stale_tool_outputs(messages, keep_tail=4)
    tool_msgs = [m for m in messages if m["role"] == "tool"]
    assert pruned == 4
    assert all("elided by auto-compact" in m["content"] for m in tool_msgs[:4])
    assert all(len(m["content"]) == 10_000 for m in tool_msgs[4:])


def test_prune_leaves_small_outputs_alone() -> None:
    messages = [_msg("user", "go")]
    for i in range(6):
        messages.append(_msg("assistant", None, tool_calls=[_call(f"c{i}")]))
        messages.append(_msg("tool", "x" * 100, name="search", tool_call_id=f"c{i}"))
    assert compaction._prune_stale_tool_outputs(messages, keep_tail=2) == 0


def test_tail_starts_at_the_assistant_that_called_its_leading_tool_replies() -> None:
    body = [_msg("user", "go")]
    body.append(_msg("assistant", None, tool_calls=[_call("a"), _call("b"), _call("c")]))
    body += [_msg("tool", "r", name="search", tool_call_id=i) for i in ("a", "b", "c")]
    body.append(_msg("assistant", "done"))
    assert compaction._tail_start(body, 3) == 1


def test_tail_keeps_its_cut_when_no_calling_assistant_precedes() -> None:
    body = [_msg("user", "go"), _msg("assistant", "plain"), _msg("tool", "r", tool_call_id="x"), _msg("assistant", "end")]
    assert compaction._tail_start(body, 2) == 2


def test_compact_prune_alone_can_avoid_the_summary() -> None:
    messages = [_msg("system", "sys"), _msg("user", "go")]
    for i in range(12):
        messages.append(_msg("assistant", None, tool_calls=[_call(f"c{i}")]))
        messages.append(_msg("tool", "x" * 20_000, name="search", tool_call_id=f"c{i}"))
    called = {"n": 0}

    def _summarize(_t, _m):
        called["n"] += 1
        return "summary"

    # 12 × 20k chars ≈ 60k tokens > 0.75 × 70k; pruning the 8 oldest outputs drops it under.
    new_messages, result = compaction.compact(
        messages=messages, user_text="", ctx_window=70_000, summarize=_summarize,
        policy=compaction.CompactionPolicy(keep_head=1, keep_tail=8),
    )
    assert result.fired is False
    assert result.tool_truncated == 8
    assert called["n"] == 0
    assert result.tokens_after < result.tokens_before
    assert len(new_messages) == len(messages)


def test_compact_summary_never_leaves_an_orphan_tool_reply() -> None:
    messages = [_msg("system", "sys"), _msg("user", "go")]
    for i in range(10):
        ids = [f"c{i}a", f"c{i}b", f"c{i}c"]
        messages.append(_msg("assistant", "y" * 30_000, tool_calls=[_call(c) for c in ids]))
        messages += [_msg("tool", "r", name="search", tool_call_id=c) for c in ids]
    new_messages, result = compaction.compact(
        messages=messages, user_text="", ctx_window=60_000, summarize=lambda _t, _m: "summary",
        policy=compaction.CompactionPolicy(keep_head=1, keep_tail=5),
    )
    assert result.fired is True
    known: set[str] = set()
    for m in new_messages:
        if m.get("role") == "assistant":
            known.update(c["id"] for c in (m.get("tool_calls") or []))
        if m.get("role") == "tool":
            assert m["tool_call_id"] in known, m["tool_call_id"]
    assert any(str(m.get("content") or "").startswith("[auto-compacted summary]") for m in new_messages)


def test_stub_covers_every_leading_tool_reply() -> None:
    tail = [
        _msg("tool", "r1", name="search", tool_call_id="k1"),
        _msg("tool", "r2", name="grep", tool_call_id="k2"),
        _msg("assistant", "after"),
    ]
    out = compaction._coalesce_tail_tool_calls(tail)
    assert out[0]["role"] == "assistant"
    assert [c["id"] for c in out[0]["tool_calls"]] == ["k1", "k2"]
    assert [c["function"]["name"] for c in out[0]["tool_calls"]] == ["search", "grep"]


def _paired(messages: list[dict]) -> None:
    pending: set[str] = set()
    for m in messages:
        if m.get("role") == "assistant":
            assert not pending, pending
            pending = {c["id"] for c in (m.get("tool_calls") or [])}
        elif m.get("role") == "tool":
            assert m["tool_call_id"] in pending, m["tool_call_id"]
            pending.discard(m["tool_call_id"])
        else:
            assert not pending, (m.get("role"), pending)
    assert not pending, pending


def test_the_head_anchor_never_ends_inside_a_tool_batch() -> None:
    messages = [_msg("system", "sys"), _msg("user", "go")]
    for i in range(12):
        messages.append(_msg("assistant", "y" * 30_000, tool_calls=[_call(f"c{i}")]))
        messages.append(_msg("tool", "r", name="search", tool_call_id=f"c{i}"))
    new_messages, result = compaction.compact(
        messages=messages, user_text="", ctx_window=60_000, summarize=lambda _t, _m: "summary",
        policy=compaction.CompactionPolicy(keep_head=2, keep_tail=4),
    )
    assert result.fired is True
    _paired(new_messages)


def test_head_end_moves_past_the_replies_of_a_split_batch() -> None:
    body = [_msg("user", "go"), _msg("assistant", None, tool_calls=[_call("a"), _call("b")]),
            _msg("tool", "r", tool_call_id="a"), _msg("tool", "r", tool_call_id="b"), _msg("assistant", "x")]
    assert compaction._head_end(body, 2) == 4
    assert compaction._head_end(body, 3) == 4
    assert compaction._head_end(body, 1) == 1


def test_a_middle_that_is_only_the_previous_summary_is_not_summarized_again() -> None:
    messages = [_msg("system", "sys"), _msg("user", "go"), _msg("system", "[auto-compacted summary]\nold"), _msg("assistant", "a")]
    for i in range(6):
        messages.append(_msg("assistant", None, tool_calls=[_call(f"c{i}")]))
        messages.append(_msg("tool", "x" * 20_000, name="search", tool_call_id=f"c{i}"))
    called = {"n": 0}

    def _summarize(_t, _m):
        called["n"] += 1
        return "again"

    _new, result = compaction.compact(
        messages=messages, user_text="", ctx_window=20_000, summarize=_summarize,
        policy=compaction.CompactionPolicy(keep_head=1, keep_tail=12),
    )
    assert called["n"] == 0 and result.fired is False


def test_no_summary_when_the_tail_is_over_the_trigger_and_the_middle_is_small() -> None:
    messages = [_msg("system", "sys"), _msg("user", "go")]
    for i in range(8):
        messages.append(_msg("assistant", "y" * 4_000, tool_calls=[_call(f"c{i}")]))
        messages.append(_msg("tool", "r", name="search", tool_call_id=f"c{i}"))
    called = {"n": 0}

    def _summarize(_t, _m):
        called["n"] += 1
        return "s"

    _new, result = compaction.compact(
        messages=messages, user_text="", ctx_window=8_000, summarize=_summarize,
        policy=compaction.CompactionPolicy(keep_head=1, keep_tail=14),
    )
    assert called["n"] == 0 and result.fired is False


def test_a_large_middle_is_summarized_even_when_the_tail_alone_is_over_the_trigger() -> None:
    messages = [_msg("system", "sys"), _msg("user", "go")]
    for i in range(6):
        messages.append(_msg("assistant", "m" * 12_000))
    for i in range(8):
        messages.append(_msg("assistant", "y" * 40_000, tool_calls=[_call(f"c{i}")]))
        messages.append(_msg("tool", "r", name="search", tool_call_id=f"c{i}"))
    called = {"n": 0}

    def _summarize(_t, _m):
        called["n"] += 1
        return "s"

    _new, result = compaction.compact(
        messages=messages, user_text="", ctx_window=100_000, summarize=_summarize,
        policy=compaction.CompactionPolicy(keep_head=1, keep_tail=16),
    )
    assert called["n"] == 1 and result.fired is True
    assert result.tokens_after < result.tokens_before


def test_a_previous_summary_plus_one_large_message_is_summarized_again() -> None:
    messages = [
        _msg("system", "sys"), _msg("user", "go"),
        _msg("system", "[auto-compacted summary]\nold"),
        _msg("assistant", "m" * 40_000),
    ]
    for i in range(4):
        messages.append(_msg("assistant", "y" * 8_000, tool_calls=[_call(f"c{i}")]))
        messages.append(_msg("tool", "r", name="search", tool_call_id=f"c{i}"))
    called = {"n": 0}

    def _summarize(_t, _m):
        called["n"] += 1
        return "fresh"

    new_messages, result = compaction.compact(
        messages=messages, user_text="", ctx_window=20_000, summarize=_summarize,
        policy=compaction.CompactionPolicy(keep_head=1, keep_tail=8),
    )
    assert called["n"] == 1 and result.fired is True
    assert result.tokens_after < 20_000 * compaction.DEFAULT_TRIGGER_RATIO
    assert sum(1 for m in new_messages if str(m.get("content") or "").startswith("[auto-compacted summary]")) == 1
