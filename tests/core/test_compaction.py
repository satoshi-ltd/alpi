"""Tests for ``alpi.compaction`` — the auto-compact pipeline."""

from __future__ import annotations

import pytest

from alpi import compaction


def _msg(role: str, content: str = "", **extra) -> dict:
    out = {"role": role, "content": content}
    out.update(extra)
    return out


# ---------------------------------------------------------------------------
# estimate_tokens / estimate_message_tokens
# ---------------------------------------------------------------------------


def test_estimate_tokens_handles_str_list_dict_none() -> None:
    assert compaction.estimate_tokens(None) == 0
    assert compaction.estimate_tokens("") == 1   # floor at 1
    assert compaction.estimate_tokens("x" * 400) == 100
    assert compaction.estimate_tokens(["x" * 400, "y" * 400]) == 200
    assert compaction.estimate_tokens({"a": "x" * 400}) == 100


def test_estimate_message_tokens_includes_tool_calls() -> None:
    msg = _msg(
        "assistant",
        content="hi",
        tool_calls=[{"function": {"name": "search", "arguments": "x" * 400}}],
    )
    n = compaction.estimate_message_tokens(msg)
    # content (1) + tool_calls.arguments (100) + name "search" (1)
    assert n >= 100


# ---------------------------------------------------------------------------
# should_compact
# ---------------------------------------------------------------------------


def test_should_compact_false_when_well_below_threshold() -> None:
    messages = [_msg("system", "ok"), _msg("user", "hi")]
    assert compaction.should_compact(messages, "", 200_000, compaction.CompactionPolicy()) is False


def test_should_compact_true_when_projected_exceeds_trigger_ratio() -> None:
    # 200k * 0.75 = 150k tokens threshold. 800k chars / 4 = 200k tokens projected.
    messages = [_msg("user", "x" * 800_000)]
    assert compaction.should_compact(messages, "", 200_000, compaction.CompactionPolicy()) is True


def test_should_compact_false_when_ctx_window_zero() -> None:
    messages = [_msg("user", "x" * 800_000)]
    assert compaction.should_compact(messages, "", 0, compaction.CompactionPolicy()) is False


# ---------------------------------------------------------------------------
# Tool-output truncation (cheap first pass)
# ---------------------------------------------------------------------------


def test_compact_truncates_oversized_tool_outputs_without_summarizing() -> None:
    # Build a session whose tokens come almost entirely from one huge tool
    # message. After truncation the prompt fits, so summarize is never called.
    big_payload = "X" * 600_000  # 150k tokens
    messages = [
        _msg("system", "you are alpi"),
        _msg("user", "fetch the dataset"),
        _msg("tool", big_payload, name="fetch", tool_call_id="t1"),
        _msg("user", "ok thanks"),
    ]
    summarize_calls: list[tuple] = []

    def _summarize(transcript, max_tokens):
        summarize_calls.append((len(transcript), max_tokens))
        return "SHOULD NOT FIRE"

    new_messages, result = compaction.compact(
        messages=messages,
        user_text="",
        ctx_window=200_000,
        summarize=_summarize,
    )

    assert summarize_calls == [], "summarizer should not run if truncation is enough"
    assert result.fired is False
    assert result.tool_truncated == 1
    tool_msg = next(m for m in new_messages if m["role"] == "tool")
    assert "elided by auto-compact" in tool_msg["content"]
    assert len(tool_msg["content"]) < len(big_payload)


# ---------------------------------------------------------------------------
# Full pipeline: head + middle summarized + tail intact
# ---------------------------------------------------------------------------


def test_compact_preserves_system_head_tail_and_summarizes_middle() -> None:
    # 50 user/assistant turns of ~10k tokens each = 500k tokens; window 400k.
    messages = [_msg("system", "you are alpi")]
    for i in range(50):
        messages.append(_msg("user", f"msg{i} " + "y" * 40_000))
        messages.append(_msg("assistant", f"reply{i} " + "z" * 40_000))

    captured: dict = {}

    def _summarize(transcript, max_tokens):
        captured["transcript"] = transcript
        captured["max_tokens"] = max_tokens
        return "[BRIEFING]"

    policy = compaction.CompactionPolicy(keep_head=2, keep_tail=4)
    new_messages, result = compaction.compact(
        messages=messages,
        user_text="",
        ctx_window=400_000,
        summarize=_summarize,
        policy=policy,
    )

    assert result.fired is True
    # Transcript carries one labelled section per middle message.
    assert isinstance(captured["transcript"], str)
    assert captured["transcript"].count("[user]") + captured["transcript"].count("[assistant]") \
        == result.summarized_messages
    # system + head(2) + summary(1) + tail(4)
    assert len(new_messages) == 1 + 2 + 1 + 4
    assert new_messages[0]["role"] == "system" and "you are alpi" in new_messages[0]["content"]
    assert new_messages[1]["content"].startswith("msg0")     # first head
    summary_msg = new_messages[3]
    assert summary_msg["role"] == "system"
    assert "[auto-compacted summary]" in summary_msg["content"]
    assert "[BRIEFING]" in summary_msg["content"]
    # Tail must be the last 4 messages of the original body.
    assert new_messages[-1]["content"].startswith("reply49")
    assert new_messages[-2]["content"].startswith("msg49")


def test_summary_budget_proportional_to_context_window() -> None:
    # Same conversation, two windows: 400k and 1M. Larger window must yield a
    # larger summary budget.
    messages = [_msg("system", "ok")]
    for i in range(40):
        messages.append(_msg("user", "u" * 40_000))
        messages.append(_msg("assistant", "a" * 40_000))

    budgets: list[int] = []

    def _summarize(_transcript, max_tokens):
        budgets.append(max_tokens)
        return "x"

    for window in (400_000, 1_000_000):
        compaction.compact(
            messages=messages,
            user_text="",
            ctx_window=window,
            summarize=_summarize,
        )

    assert len(budgets) == 2
    assert budgets[1] > budgets[0], budgets


def test_compact_does_not_strand_dangling_tool_reply() -> None:
    # Tail starts with a ``tool`` reply whose ``assistant`` tool_calls parent
    # would otherwise live in the summarized middle. The pipeline must
    # synthesize a stub so the LLM doesn't see an orphaned tool result.
    messages = [_msg("system", "ok")]
    for i in range(40):
        messages.append(_msg("user", "u" * 40_000))
        messages.append(_msg("assistant", "a" * 40_000))
    # Replace the first tail message with a tool reply (keep_tail=4 → tail[0] = messages[-4]).
    messages[-4] = _msg("tool", "result", name="search", tool_call_id="call_x")

    def _summarize(_transcript, _max_tokens):
        return "ok"

    policy = compaction.CompactionPolicy(keep_head=2, keep_tail=4)
    new_messages, result = compaction.compact(
        messages=messages,
        user_text="",
        ctx_window=400_000,
        summarize=_summarize,
        policy=policy,
    )

    assert result.fired is True
    # Find the index of our tool reply; the message immediately before it
    # must be a synthesized assistant stub with the matching tool_call_id.
    tool_idx = next(i for i, m in enumerate(new_messages) if m.get("role") == "tool")
    parent = new_messages[tool_idx - 1]
    assert parent["role"] == "assistant"
    tool_calls = parent.get("tool_calls") or []
    assert tool_calls and tool_calls[0]["id"] == "call_x"


def test_compact_does_nothing_below_threshold() -> None:
    messages = [_msg("system", "ok"), _msg("user", "hello"), _msg("assistant", "hi")]
    new_messages, result = compaction.compact(
        messages=messages,
        user_text="",
        ctx_window=400_000,
        summarize=lambda _t, _n: "should not run",
    )
    assert result.fired is False
    assert result.summarized_messages == 0
    assert result.tool_truncated == 0
    assert [m["content"] for m in new_messages] == ["ok", "hello", "hi"]


# ---------------------------------------------------------------------------
# P1: empty / failed summary must NOT destroy history
# ---------------------------------------------------------------------------


def test_compact_keeps_history_when_summarizer_returns_empty() -> None:
    messages = [_msg("system", "ok")]
    for i in range(40):
        messages.append(_msg("user", f"msg{i} " + "u" * 40_000))
        messages.append(_msg("assistant", f"reply{i} " + "a" * 40_000))
    original_content = [m["content"] for m in messages]

    new_messages, result = compaction.compact(
        messages=messages,
        user_text="",
        ctx_window=400_000,
        summarize=lambda _t, _n: "",   # empty result → simulate provider failure
    )

    assert result.fired is False
    assert result.summarized_messages == 0
    assert [m["content"] for m in new_messages] == original_content
    # No summary placeholder leaks in.
    assert not any(
        "[auto-compacted summary]" in (m.get("content") or "")
        for m in new_messages
    )


def test_compact_keeps_history_when_summarizer_raises() -> None:
    messages = [_msg("system", "ok")]
    for i in range(40):
        messages.append(_msg("user", "u" * 40_000))
        messages.append(_msg("assistant", "a" * 40_000))

    def _boom(_transcript, _max_tokens):
        raise RuntimeError("provider 500")

    new_messages, result = compaction.compact(
        messages=messages,
        user_text="",
        ctx_window=400_000,
        summarize=_boom,
    )

    assert result.fired is False
    assert all(
        "[auto-compacted summary]" not in (m.get("content") or "")
        for m in new_messages
    )


# ---------------------------------------------------------------------------
# P2: transcript passed to summarizer is a flat string, not raw OpenAI messages
# ---------------------------------------------------------------------------


def test_summarizer_receives_flat_transcript_not_messages() -> None:
    # Build a middle that, if passed raw, would START with a ``tool`` reply
    # (orphan tool result without its assistant parent). Flattening must
    # produce a plain string with labelled sections.
    messages = [
        _msg("system", "ok"),
        _msg("user", "first u"),
        _msg("assistant", "first a"),
        _msg("tool", "tool reply 1", name="search", tool_call_id="t1"),
        _msg("assistant", "second a", tool_calls=[
            {"function": {"name": "fetch", "arguments": "{}"}, "id": "t2"},
        ]),
        _msg("tool", "tool reply 2", name="fetch", tool_call_id="t2"),
    ]
    # Pad to force compaction.
    for i in range(30):
        messages.append(_msg("user", "pad " + "u" * 40_000))
        messages.append(_msg("assistant", "pad " + "a" * 40_000))

    captured = {}

    def _summarize(transcript, max_tokens):
        captured["transcript"] = transcript
        captured["max_tokens"] = max_tokens
        return "OK"

    compaction.compact(
        messages=messages,
        user_text="",
        ctx_window=400_000,
        summarize=_summarize,
        policy=compaction.CompactionPolicy(keep_head=2, keep_tail=4),
    )

    transcript = captured["transcript"]
    assert isinstance(transcript, str)
    assert "[tool:search]" in transcript
    assert "[assistant calls: fetch]" in transcript
    assert "tool reply 1" in transcript


# ---------------------------------------------------------------------------
# force=True drives the manual ``/compact`` path through the same pipeline
# ---------------------------------------------------------------------------


def test_compact_force_runs_below_threshold() -> None:
    messages = [_msg("system", "ok")]
    for i in range(6):
        messages.append(_msg("user", f"u{i}"))
        messages.append(_msg("assistant", f"a{i}"))

    captured: dict = {}

    def _summarize(transcript, max_tokens):
        captured["len"] = len(transcript)
        return "[FORCED]"

    new_messages, result = compaction.compact(
        messages=messages,
        user_text="",
        ctx_window=1_000_000,   # well above any threshold
        summarize=_summarize,
        policy=compaction.CompactionPolicy(keep_head=1, keep_tail=2),
        force=True,
    )

    assert result.fired is True
    assert any(
        "[FORCED]" in (m.get("content") or "")
        for m in new_messages
    )
