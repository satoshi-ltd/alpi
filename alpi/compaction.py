"""Automatic context compaction for long-running sessions.

Triggered preemptively by the engine before each LLM round-trip when the
prompt would exceed a fraction of the model's context window. Preserves
the system prefix and the most recent turns intact, summarizes the
middle, and as a cheaper first pass truncates oversized tool outputs.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


# Heuristic: 1 token ≈ 4 characters. Matches the existing approximation
# in ``cli._continue_specific_session`` / ``tui.app._do_compact``.
CHARS_PER_TOKEN = 4

# Trigger threshold as a fraction of the model's context window. When the
# next prompt would exceed this, auto-compaction fires.
DEFAULT_TRIGGER_RATIO = 0.75

# Target size of the post-compaction prompt, as a fraction of the window.
# We aim well below ``DEFAULT_TRIGGER_RATIO`` so a single compaction buys
# many subsequent turns before we have to compact again.
DEFAULT_TARGET_RATIO = 0.40

# How many of the most recent assistant/user/tool messages stay intact.
DEFAULT_KEEP_TAIL = 8

# How many of the earliest user/assistant messages stay intact as anchor.
DEFAULT_KEEP_HEAD = 2

# Tool messages whose content is at least this long are candidates for
# the cheap first-pass truncation step. 8k tokens = ~32k chars.
TOOL_TRUNCATE_MIN_CHARS = 32_000

# When we truncate a tool message we keep this many chars at head + tail.
TOOL_TRUNCATE_KEEP_HEAD_CHARS = 8_000
TOOL_TRUNCATE_KEEP_TAIL_CHARS = 4_000

# Floor for the summary's output budget: even on tiny windows we never
# squeeze the summarizer below this.
MIN_SUMMARY_OUTPUT_TOKENS = 800

# COMPACT_PROMPT + user-wrapper tokens reserved when fitting input to the summarizer.
SUMMARY_PROMPT_OVERHEAD_TOKENS = 800


def clip_transcript(transcript: str, budget_tokens: int) -> str:
    """Fit the summarizer's (possibly much smaller) window; the tail wins — recent context first."""
    max_chars = max(500, budget_tokens) * CHARS_PER_TOKEN
    if len(transcript) <= max_chars:
        return transcript
    head = max_chars // 4
    tail = max_chars - head
    dropped = len(transcript) - head - tail
    return (
        transcript[:head]
        + f"\n\n[... {dropped} chars elided to fit the summarizer window ...]\n\n"
        + transcript[-tail:]
    )


CANDIDATE_PROMPT = (
    "You are reading a dense briefing produced by an auto-compaction pass over "
    "an agent conversation. Identify any DURABLE facts in the briefing that "
    "deserve to be promoted to long-term memory — facts that will still matter "
    "in future sessions, not session-specific state.\n\n"
    "Targets:\n"
    "- USER.md: stable facts about the human (name, location, role, family, "
    "  long-term preferences). True regardless of which agent they use.\n"
    "- MEMORY.md: the world the user operates in — project paths, tool quirks, "
    "  team conventions, environment specifics.\n"
    "- AGENT.md: behavioral directives for the agent (tone, response length, "
    "  output format). NEVER facts about the user or world.\n\n"
    "Output ONE JSON object, no prose, no fences:\n"
    "{\"candidates\": [{\"target\": \"USER.md|MEMORY.md|AGENT.md\", "
    "\"text\": \"the fact, one declarative English sentence\", "
    "\"confidence\": \"low|normal|high\"}]}\n\n"
    "Skip operational state (chat_id, session_id, ISO timestamps, today-only "
    "context). Skip facts the agent merely speculated about. Empty list is "
    "acceptable. At most 5 candidates per call — prefer fewer high-quality "
    "facts over many shaky ones."
)


COMPACT_PROMPT = (
    "You are summarizing the middle of an agent conversation so the "
    "running session can stay within its context window. Your summary "
    "REPLACES the messages shown below — the agent will continue from "
    "your summary plus the most recent turns.\n\n"
    "Preserve, in roughly this priority order:\n"
    "- Active tasks and their current status; what is done vs pending\n"
    "- Decisions made and the reason for each\n"
    "- Identifiers verbatim: paths, IDs, URLs, hashes, commit SHAs, "
    "  flag names, env vars, file names, function names\n"
    "- Open TODOs and unresolved questions\n"
    "- The user's most recent ask and why it matters\n"
    "- Relevant tool outputs (cite values literally; do not paraphrase "
    "  numbers, errors, or stack traces)\n\n"
    "Do NOT:\n"
    "- Add opinions, suggestions, or rewrites\n"
    "- Drop concrete data in favor of generic descriptions\n"
    "- Restate the system prompt or the agent's role\n\n"
    "Output a dense briefing — bullets are fine. Prioritize recent "
    "context over older. No preamble, no sign-off."
)


@dataclass
class CompactionPolicy:
    trigger_ratio: float = DEFAULT_TRIGGER_RATIO
    target_ratio: float = DEFAULT_TARGET_RATIO
    keep_head: int = DEFAULT_KEEP_HEAD
    keep_tail: int = DEFAULT_KEEP_TAIL


@dataclass
class CompactionResult:
    fired: bool                       # whether the LLM-summarize path ran
    tool_truncated: int = 0           # number of tool messages truncated by the cheap pass
    summarized_messages: int = 0      # number of messages replaced by the summary
    tokens_before: int = 0
    tokens_after: int = 0


def estimate_tokens(content: Any) -> int:
    """Rough char/4 estimate. Good enough for trigger decisions."""
    if content is None:
        return 0
    if isinstance(content, str):
        return max(1, len(content) // CHARS_PER_TOKEN)
    if isinstance(content, list):
        total = 0
        for item in content:
            total += estimate_tokens(item)
        return total
    if isinstance(content, dict):
        total = 0
        for v in content.values():
            total += estimate_tokens(v)
        return total
    return max(1, len(str(content)) // CHARS_PER_TOKEN)


def estimate_message_tokens(message: dict) -> int:
    total = estimate_tokens(message.get("content"))
    # Tool-call arguments often dominate a message; account for them.
    for call in message.get("tool_calls") or []:
        fn = (call or {}).get("function") or {}
        total += estimate_tokens(fn.get("arguments"))
        total += estimate_tokens(fn.get("name"))
    return max(1, total)


def estimate_messages_tokens(messages: list[dict]) -> int:
    return sum(estimate_message_tokens(m) for m in messages)


def should_compact(
    messages: list[dict],
    user_text: str,
    ctx_window: int,
    policy: CompactionPolicy,
) -> bool:
    if ctx_window <= 0:
        return False
    projected = estimate_messages_tokens(messages) + estimate_tokens(user_text)
    return projected > policy.trigger_ratio * ctx_window


def _truncate_oversized_tools(messages: list[dict]) -> int:
    """Replace huge tool outputs with head + … + tail. Returns count truncated."""
    count = 0
    for msg in messages:
        if msg.get("role") != "tool":
            continue
        content = msg.get("content")
        if not isinstance(content, str) or len(content) < TOOL_TRUNCATE_MIN_CHARS:
            continue
        head = content[:TOOL_TRUNCATE_KEEP_HEAD_CHARS]
        tail = content[-TOOL_TRUNCATE_KEEP_TAIL_CHARS:]
        dropped = len(content) - len(head) - len(tail)
        msg["content"] = (
            f"{head}\n\n[... {dropped} chars elided by auto-compact ...]\n\n{tail}"
        )
        count += 1
    return count


def _partition(
    messages: list[dict],
    keep_head: int,
    keep_tail: int,
) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    """Split into (system_prefix, head_anchor, middle, tail).

    ``system_prefix`` is every leading system message. After it, the
    first ``keep_head`` non-system messages become ``head_anchor`` and the
    last ``keep_tail`` non-system messages become ``tail``. Any system
    messages interleaved in the middle stay in ``middle`` so the
    summarizer can fold them into the briefing if they matter.
    """
    n = len(messages)
    system_end = 0
    while system_end < n and messages[system_end].get("role") == "system":
        system_end += 1
    system_prefix = messages[:system_end]
    body = messages[system_end:]

    if not body:
        return system_prefix, [], [], []

    keep_head = max(0, keep_head)
    keep_tail = max(0, keep_tail)
    if keep_head + keep_tail >= len(body):
        # Nothing to compact — head + tail already covers the body.
        return system_prefix, body, [], []

    head_anchor = body[:keep_head]
    tail = body[-keep_tail:] if keep_tail else []
    middle = body[keep_head:len(body) - keep_tail]
    return system_prefix, head_anchor, middle, tail


def _coalesce_tail_tool_calls(tail: list[dict]) -> list[dict]:
    """If the tail starts with a ``tool`` reply whose matching ``assistant``
    tool_calls message is in the dropped middle, prepend a minimal stub
    so the LLM doesn't see a dangling tool result.
    """
    if not tail:
        return tail
    if tail[0].get("role") != "tool":
        return tail
    tool_call_id = tail[0].get("tool_call_id") or ""
    stub_name = (tail[0].get("name") or "tool")
    stub = {
        "role": "assistant",
        "content": None,
        "tool_calls": [{
            "id": tool_call_id or f"compacted-{stub_name}",
            "type": "function",
            "function": {"name": stub_name, "arguments": "{}"},
        }],
    }
    return [stub] + tail


def _summary_max_tokens(
    ctx_window: int, preserved_tokens: int, policy: CompactionPolicy,
) -> int:
    target = int(ctx_window * policy.target_ratio)
    budget = target - preserved_tokens
    return max(MIN_SUMMARY_OUTPUT_TOKENS, budget)


SummarizeFn = Callable[[str, int], str]
"""``(transcript, max_tokens) -> summary_text``.

The transcript is a flat role/name/content rendering of the middle
block — never raw OpenAI messages, since those may start with ``tool``
or contain orphan ``tool_calls`` references that some providers reject.
"""


def _flatten_for_summary(middle: list[dict]) -> str:
    """Render the middle block as a provider-agnostic textual transcript.

    Each message becomes a labelled section. Tool calls are summarized
    inline so the summarizer sees ``what was called`` and ``what it
    returned`` without needing the full OpenAI message structure.
    """
    lines: list[str] = []
    for msg in middle:
        role = str(msg.get("role") or "?")
        raw_content = msg.get("content")
        if isinstance(raw_content, list):
            parts = []
            for part in raw_content:
                if isinstance(part, dict):
                    parts.append(str(part.get("text") or part.get("content") or ""))
                else:
                    parts.append(str(part))
            content = " ".join(p for p in parts if p)
        elif raw_content is None:
            content = ""
        else:
            content = str(raw_content)
        content = content.strip()

        if role == "tool":
            name = str(msg.get("name") or "tool")
            header = f"[tool:{name}]"
        elif role == "assistant":
            tool_calls = msg.get("tool_calls") or []
            if tool_calls:
                names = ", ".join(
                    str((tc.get("function") or {}).get("name") or "?")
                    for tc in tool_calls
                )
                header = f"[assistant calls: {names}]"
            else:
                header = "[assistant]"
        else:
            header = f"[{role}]"

        if content:
            lines.append(f"{header}\n{content}")
        else:
            lines.append(header)
    return "\n\n".join(lines)


def compact(
    messages: list[dict],
    user_text: str,
    ctx_window: int,
    summarize: SummarizeFn,
    policy: CompactionPolicy | None = None,
    force: bool = False,
) -> tuple[list[dict], CompactionResult]:
    """Run the full compaction pipeline. Returns ``(new_messages, result)``.

    The pipeline:
    1. Truncate oversized tool outputs in-place (cheap first pass).
    2. Unless ``force=True``, stop when below ``trigger_ratio``.
    3. Partition into system + head + middle + tail.
    4. Flatten the middle into a transcript and call ``summarize``.
    5. If the summarizer returns a non-empty result, splice it in.
       Otherwise leave the original middle in place — never destroy
       history because of a provider error.

    The returned message list is suitable to assign directly back to
    ``session.messages``.
    """
    policy = policy or CompactionPolicy()
    tokens_before = estimate_messages_tokens(messages)
    new_messages = [dict(m) for m in messages]

    truncated = _truncate_oversized_tools(new_messages)

    if not force and not should_compact(new_messages, user_text, ctx_window, policy):
        return new_messages, CompactionResult(
            fired=False,
            tool_truncated=truncated,
            summarized_messages=0,
            tokens_before=tokens_before,
            tokens_after=estimate_messages_tokens(new_messages),
        )

    system_prefix, head_anchor, middle, tail = _partition(
        new_messages, policy.keep_head, policy.keep_tail,
    )
    if not middle:
        # Tail/head already cover the body; nothing else we can do.
        return new_messages, CompactionResult(
            fired=False,
            tool_truncated=truncated,
            summarized_messages=0,
            tokens_before=tokens_before,
            tokens_after=estimate_messages_tokens(new_messages),
        )

    preserved_tokens = (
        estimate_messages_tokens(system_prefix)
        + estimate_messages_tokens(head_anchor)
        + estimate_messages_tokens(tail)
        + estimate_tokens(user_text)
    )
    summary_budget = _summary_max_tokens(ctx_window, preserved_tokens, policy)
    transcript = _flatten_for_summary(middle)

    try:
        summary_text = (summarize(transcript, summary_budget) or "").strip()
    except Exception:  # noqa: BLE001
        summary_text = ""

    if not summary_text:
        # Summarizer failed or returned empty. Refuse to replace real
        # history with a placeholder — keep what tool-truncation gave us.
        return new_messages, CompactionResult(
            fired=False,
            tool_truncated=truncated,
            summarized_messages=0,
            tokens_before=tokens_before,
            tokens_after=estimate_messages_tokens(new_messages),
        )

    summary_msg = {
        "role": "system",
        "content": f"[auto-compacted summary]\n{summary_text}",
    }

    safe_tail = _coalesce_tail_tool_calls(tail)
    rebuilt = system_prefix + head_anchor + [summary_msg] + safe_tail
    return rebuilt, CompactionResult(
        fired=True,
        tool_truncated=truncated,
        summarized_messages=len(middle),
        tokens_before=tokens_before,
        tokens_after=estimate_messages_tokens(rebuilt),
    )


def event_log_path(home: Path) -> Path:
    """Where ``record_event`` appends. Same logs/ dir as agent.log / service.log."""
    return home / "logs" / "compaction.jsonl"


def parse_candidates(raw: str) -> list[dict]:
    """Parse the LLM's structured JSON output for promotion candidates.

    Tolerates leading/trailing junk, code fences, and the LLM occasionally
    wrapping the object in markdown. Returns the list of well-shaped
    candidate dicts; rejects anything missing target/text or with a
    target outside the allowed three files.
    """
    if not raw:
        return []
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return []
    try:
        obj = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return []
    raw_candidates = obj.get("candidates") if isinstance(obj, dict) else None
    if not isinstance(raw_candidates, list):
        return []
    valid: list[dict] = []
    for c in raw_candidates[:5]:
        if not isinstance(c, dict):
            continue
        target = str(c.get("target") or "").strip()
        text_val = str(c.get("text") or "").strip()
        if target not in ("USER.md", "MEMORY.md", "AGENT.md") or not text_val:
            continue
        confidence = str(c.get("confidence") or "normal").lower()
        if confidence not in ("low", "normal", "high"):
            confidence = "normal"
        valid.append({
            "target": target,
            "text": text_val,
            "confidence": confidence,
        })
    return valid


CandidateLLM = Callable[[list[dict], int], str]
"""``(messages, max_tokens) -> raw_text``. Engine wires this to ``llm.complete``."""


def emit_candidates_from_summary(
    home: Path,
    summary_text: str,
    *,
    call_llm: CandidateLLM,
    session_id: str,
    model: str,
) -> int:
    """Run the candidate-extraction LLM call against ``summary_text`` and push
    every well-formed result into the promotion queue.

    Returns the number of candidates added. Best-effort: any exception is
    swallowed so compaction does not break on a flaky LLM. The queue is
    bounded (``promotion.MAX_PENDING``) and expires entries after
    ``promotion.MAX_AGE_DAYS`` — over-emission cannot grow unbounded.
    """
    if not summary_text.strip():
        return 0
    try:
        messages = [
            {"role": "system", "content": CANDIDATE_PROMPT},
            {"role": "user", "content": f"--- briefing ---\n{summary_text}"},
        ]
        raw = call_llm(messages, 800)
        if not raw:
            return 0
        from alpi import promotion
        from alpi.tools.memory import compute_promotion_warnings
        parsed = parse_candidates(raw)
        for c in parsed:
            try:
                warnings = compute_promotion_warnings(home, c["target"], c["text"])
            except Exception:  # noqa: BLE001
                warnings = []
            promotion.add(
                home,
                source="compaction",
                session_id=session_id,
                model=model,
                target=c["target"],
                text=c["text"],
                confidence=c["confidence"],
                warnings=warnings,
            )
        return len(parsed)
    except Exception:  # noqa: BLE001
        return 0


def record_event(
    home: Path,
    *,
    result: CompactionResult,
    trigger: str,
    session_id: str,
    model: str,
    ctx_window: int,
) -> None:
    """Append one JSONL line per compaction. Best-effort; never raises."""
    path = event_log_path(home)
    record = {
        "ts": time.time(),
        "trigger": trigger,                       # "auto" | "manual"
        "session_id": session_id,
        "model": model,
        "ctx_window": ctx_window,
        "fired": bool(result.fired),
        "tokens_before": int(result.tokens_before),
        "tokens_after": int(result.tokens_after),
        "summarized_messages": int(result.summarized_messages),
        "tool_truncated": int(result.tool_truncated),
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, separators=(",", ":")) + "\n")
    except OSError:
        return  # never let telemetry break a turn — CM.1 will surface the gap


__all__ = [
    "CANDIDATE_PROMPT",
    "CHARS_PER_TOKEN",
    "COMPACT_PROMPT",
    "CandidateLLM",
    "CompactionPolicy",
    "CompactionResult",
    "MIN_SUMMARY_OUTPUT_TOKENS",
    "SUMMARY_PROMPT_OVERHEAD_TOKENS",
    "clip_transcript",
    "compact",
    "emit_candidates_from_summary",
    "estimate_message_tokens",
    "estimate_messages_tokens",
    "estimate_tokens",
    "event_log_path",
    "parse_candidates",
    "record_event",
    "should_compact",
]
