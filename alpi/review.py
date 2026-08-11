"""Post-turn memory reviewer — a narrow forked agent that watches the
conversation in retrospect and persists facts the main loop missed.

Fires after every N user turns (``Config.memory.review_interval``,
default 0 = off). Runs in a daemon thread so the parent session never
blocks on it. The reviewer's only tool is ``memory``; its only job is
to scan the turn snapshot and decide whether anything stable belongs
on disk. The parent's frozen system prompt is unaffected — writes
land on disk and load into the next session, as memory always has.

Single round-trip: one LLM call with a narrow prompt and the memory
schema. No multi-step tool loop. Reviewer errors never disturb the
parent.
"""

from __future__ import annotations

import copy
import json
import threading
from pathlib import Path
from typing import Any

from alpi import config as cfg_mod
from alpi import llm
from alpi.home import reset_active_home, set_active_home
from alpi.tools import execute as run_tool, schemas as all_schemas


_REVIEW_PROMPT = """You are a focused memory reviewer running between turns of an alpi session.

Read the conversation above and decide: did the user reveal a stable
fact, preference, or correction worth persisting? If yes, append it
via `memory(action="add", target=..., content=...)`. If nothing
qualifies, reply 'Nothing to save.' and stop. The agent only sees
the conversation history — no other state.

You may ONLY call `memory` with `action="add"`. The reviewer does not
read the current memory contents, so issuing `replace` or `remove`
risks rewriting unrelated entries. Append-only is the contract; any
consolidation will happen later by the curator.

Save signals:
- Stable user facts (name, location, role, long-term preferences) → USER.md
- Environment / tool / project notes (paths, commands, conventions, API quirks) → MEMORY.md
- Persona / behavioural correction the user gave the agent
  ("be more concise", "stop using emoji", "always answer in Spanish") → AGENT.md

Do NOT save:
- Operational state (session ids, chat ids, ISO timestamps, "first interaction")
- Restatements of the current turn that won't survive next week
- Anything that sounds like an instruction to yourself ("always do X")
  rather than a fact about the user ("user prefers X")

Frustration signals — when the user says "stop doing X", "don't format
like that", "I hate when you Y" — are usually skill-level corrections,
NOT memory entries. Skip them here; the main agent will patch the
relevant skill on the next turn.

Be conservative. One precise save beats five fuzzy ones. Most reviews
should produce zero or one entries. If unsure, don't save."""


def _filter_messages(snapshot: list[dict]) -> list[dict]:
    """Keep user/assistant text only; strip system, tool calls, tool results.

    The reviewer needs the conversation, not the runtime apparatus."""
    out: list[dict] = []
    for msg in snapshot:
        role = msg.get("role")
        if role not in ("user", "assistant"):
            continue
        content = msg.get("content")
        if not isinstance(content, str) or not content.strip():
            continue
        out.append({"role": role, "content": content})
    return out


def _memory_schema() -> dict | None:
    for s in all_schemas():
        if s.get("function", {}).get("name") == "memory":
            return s
    return None


def _apply_calls(tool_calls: list[dict]) -> int:
    """Run ``memory(action="add", ...)`` calls only; return count of saves.

    The reviewer is APPEND-ONLY by contract: it never read the current
    memory, so a guessed `match` for `replace` / `remove` could rewrite
    or delete unrelated entries. Anything that isn't a clean `add` call
    (other tools, other actions, malformed args, tool errors) is dropped
    silently — this is a best-effort background pass."""
    saved = 0
    for call in tool_calls or []:
        if call.get("name") != "memory":
            continue
        raw = call.get("arguments") or "{}"
        try:
            args = json.loads(raw) if isinstance(raw, str) else dict(raw)
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
        if not isinstance(args, dict):
            continue
        if args.get("action") != "add":
            continue
        try:
            result = run_tool("memory", args)
        except Exception:  # noqa: BLE001
            continue
        if result.ok:
            saved += 1
    return saved


def _run_review(
    home: Path, cfg: cfg_mod.Config, snapshot: list[dict], session_id: str = "",
) -> int:
    from alpi import ledger

    history = _filter_messages(snapshot)
    if not history:
        return 0
    schema = _memory_schema()
    if schema is None:
        return 0
    try:
        ledger.check(home, cfg.budget)
    except ledger.BudgetExceeded:
        return 0

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": _REVIEW_PROMPT},
        *history,
        {"role": "user", "content": "Run the review now."},
    ]
    call_kwargs = cfg_mod.resolve_model(cfg, tier="fast")
    if session_id and str(call_kwargs.get("model", "")).startswith("openrouter/"):
        from alpi import prefix_diag
        from alpi.home import profile_name
        from alpi.providers.reasoning import merge_into_kwargs
        call_kwargs = merge_into_kwargs(call_kwargs, {"extra_body": {"session_id": prefix_diag.affinity_id(
            profile_name(home), session_id=session_id, purpose="review",
        )}})
    try:
        out = llm.complete(
            messages=messages, tools=[schema], **call_kwargs
        )
    except Exception:  # noqa: BLE001
        return 0
    ledger.record_completion(home, out, cfg_budget=cfg.budget)
    return _apply_calls(out.tool_calls or [])


def spawn_review(
    home: Path, cfg: cfg_mod.Config, messages: list[dict], session_id: str = "",
) -> threading.Thread:
    """Fire a daemon thread that runs the post-turn review and returns immediately.

    The caller need not (and should not) join the returned thread. It is
    handed back so tests can wait for completion deterministically."""
    snapshot = copy.deepcopy(messages)
    from alpi.host.connection_context import current
    parent_connection = current()

    def _worker() -> None:
        token = set_active_home(home)
        try:
            from alpi.host.connection_context import use
            with use(parent_connection):
                _run_review(home, cfg, snapshot, session_id=session_id)
        finally:
            reset_active_home(token)

    t = threading.Thread(target=_worker, daemon=True, name="alpi-memory-review")
    t.start()
    return t
