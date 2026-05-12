"""Agent turn runner."""

from __future__ import annotations

import json
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from alpi import config as cfg_mod
from alpi import llm, memory, session, tools
from alpi.tools._budget import apply as _budget_apply
from alpi.session import ToolLog, truncate_result


_CACHE_NOISE_RE = re.compile(
    r"^.*\.alpi(?:/profiles/[^/]+)?/cache/(?:tts|stt)/.*$\n?",
    re.MULTILINE,
)


def _strip_cache_noise(text: str) -> str:
    return _CACHE_NOISE_RE.sub("", text).strip()


_PLATFORM_HINTS: dict[str, str] = {
    "cron": (
        "# SURFACE: scheduled job\n"
        "You are running as a scheduled job. No user is present — you "
        "cannot ask questions, request clarification, or wait for "
        "follow-up. Execute the task fully and autonomously, making "
        "reasonable decisions where needed. Your reply is "
        "auto-delivered to the job's configured destination; put the "
        "primary content directly in your response."
    ),
    "telegram": (
        "# SURFACE: Telegram\n"
        "You are replying on Telegram. Plain Markdown is auto-converted "
        "to Telegram's MarkdownV2 (bold, italic, inline code, code "
        "blocks, links, headers). Tables, blockquotes, and deeply "
        "nested lists do NOT render — prefer flat text. Keep replies "
        "chat-friendly: short paragraphs, no sign-offs. Attach files "
        "via `send_message(attachment=…)`, not by inlining paths."
    ),
    "email": (
        "# SURFACE: email\n"
        "You are replying by email. Plain text only — no Markdown, it "
        "shows as literal asterisks and backticks. Keep replies "
        "concise. The subject line is preserved for threading. Skip "
        "greetings and sign-offs unless the user's message warranted "
        "them (business tone vs casual)."
    ),
    "gmail": (
        "# SURFACE: email\n"
        "You are replying by email. Plain text only — no Markdown, it "
        "shows as literal asterisks and backticks. Keep replies "
        "concise. The subject line is preserved for threading. Skip "
        "greetings and sign-offs unless the user's message warranted "
        "them (business tone vs casual)."
    ),
}


def _last_peer_reply(turn_tools) -> str:
    """Return the reply when peer is the most recent successful tool."""
    for log in reversed(turn_tools):
        if not log.ok:
            continue
        if log.name != "peer":
            return ""
        result = log.result or ""
        idx = result.rfind("\n\n---\ntokens:")
        return result[:idx].strip() if idx != -1 else result.strip()
    return ""


def _platform_hint() -> str:
    import os
    platform = (os.environ.get("ALPI_PLATFORM") or "").strip().lower()
    return _PLATFORM_HINTS.get(platform, "")


def _maybe_load_mcps(cfg: cfg_mod.Config) -> list:
    servers = (cfg.raw.get("mcp") or {}).get("servers") or {}
    if not servers:
        return []
    from alpi.mcp import registry as mcp_registry
    return mcp_registry.load_and_register(cfg)


def _profile_name(home: Path) -> str:
    parts = home.parts
    if "profiles" in parts:
        i = parts.index("profiles")
        if i + 1 < len(parts):
            return parts[i + 1]
    return "default"


@dataclass
class AgentEvent:
    kind: str                      # 'user' | 'reasoning_delta' | 'assistant_delta' | 'assistant_done' | 'tool_start' | 'tool_state' | 'tool_end' | 'usage' | 'error' | 'done' | 'interrupted' | 'auto_compact'
    text: str = ""
    name: str = ""                 # tool name for tool_* events
    args: dict = field(default_factory=dict)
    output: str = ""               # tool output for tool_end
    ok: bool = True
    tokens_in: int = 0
    tokens_out: int = 0
    cost: float = 0.0
    tool_id: str = ""


EventSink = Callable[[AgentEvent], None]


class Engine:
    def __init__(self, home: Path, cfg: cfg_mod.Config):
        self.home = home
        self.cfg = cfg
        self.session = session.Session(home=home, model=cfg.model)
        # Register MCP tools before building the system prompt.
        self._mcp_clients = _maybe_load_mcps(cfg)
        self._system_prompt = self._build_system_prompt()
        self.session.messages.append({"role": "system", "content": self._system_prompt})
        # UI flips this on new input while a turn is still running.
        self.interrupt_requested: bool = False
        # Serialize turns so concurrent runs do not race on session state.
        self._turn_lock = threading.Lock()
        # Post-turn memory reviewer: counter resets when the daemon fires.
        self._turns_since_review: int = 0

    def request_interrupt(self) -> None:
        """Ask the current turn to stop at the next checkpoint."""
        self.interrupt_requested = True

    def reset_session(self) -> None:
        try:
            self.save_session()
        except Exception:
            pass
        self.session = session.Session(home=self.home, model=self.cfg.model)
        self.session.messages.append({"role": "system", "content": self._system_prompt})
        self.interrupt_requested = False

    def run_turn(self, user_text: str, emit: EventSink) -> None:
        """Run a full turn and bind ``self.home`` for the duration."""
        from alpi.home import reset_active_home, set_active_home

        token = set_active_home(self.home)
        try:
            with self._turn_lock:
                self._run_turn_locked(user_text, emit)
        finally:
            reset_active_home(token)

    def _run_turn_locked(self, user_text: str, emit: EventSink) -> None:
        from alpi import config as _cfg_mod
        from alpi import ledger

        # Re-read budget from disk so live edits apply on the next turn.
        try:
            fresh_budget = _cfg_mod.load(self.home).budget
        except Exception:  # noqa: BLE001
            fresh_budget = self.cfg.budget
        self.cfg.budget = fresh_budget
        try:
            ledger.check(self.home, fresh_budget)
        except ledger.BudgetExceeded as e:
            emit(AgentEvent(kind="error", text=str(e)))
            return

        # Clear any lingering interrupt request before starting.
        self.interrupt_requested = False

        # Accumulate this turn's state for the persistent log.
        turn_started = time.time()
        turn_tools: list[ToolLog] = []
        final_assistant = ""
        # Only natural completion (LLM produced a final reply with no further
        # tool calls) flips this. Interrupts, max-step aborts, provider
        # errors, and budget exhaustion leave it False so the post-turn
        # reviewer never fires on partial / abandoned context.
        turn_completed = False

        # Inject transient workgroup context before user input.
        try:
            from alpi.alp import agent_context as _wg_ctx
            wg_block = _wg_ctx.build(self.home)
        except Exception:  # noqa: BLE001
            wg_block = None
        if wg_block:
            self.session.messages.append({"role": "system", "content": wg_block})

        # Per-turn skill boost; only fires when ``user_text`` matches a declared keyword.
        try:
            from alpi.tools.skill import keyword_match_hint as _kw_hint
            hint = _kw_hint(self.home, user_text)
        except Exception:  # noqa: BLE001
            hint = ""
        if hint:
            self.session.messages.append({"role": "system", "content": hint})

        # Reset per-turn workgroup usage tracking.
        from alpi.tools import _state as _wg_state
        _wg_state.reset_turn_usage()
        _wg_state.reset_skill_env()

        self.session.messages.append({"role": "user", "content": user_text})
        emit(AgentEvent(kind="user", text=user_text))

        schemas = tools.schemas()
        call_kwargs = cfg_mod.resolve_model(self.cfg)
        max_steps = self.cfg.tools.max_steps_per_turn

        self._maybe_auto_compact(emit, call_kwargs)

        try:
            for _ in range(max_steps):
                if self.interrupt_requested:
                    self._finalize_interrupt(emit)
                    return
                accumulated_text: list[str] = []
                final: dict = {}
                try:
                    for chunk in llm.stream(
                        messages=self.session.messages, tools=schemas, **call_kwargs
                    ):
                        if self.interrupt_requested:
                            break
                        if chunk.get("final"):
                            final = chunk
                            continue
                        reasoning_delta = chunk.get("reasoning_delta") or ""
                        if reasoning_delta:
                            emit(AgentEvent(kind="reasoning_delta", text=reasoning_delta))
                        text_delta = chunk.get("text_delta") or ""
                        if text_delta:
                            accumulated_text.append(text_delta)
                            emit(AgentEvent(kind="assistant_delta", text=text_delta))
                except Exception as e:  # noqa: BLE001
                    emit(AgentEvent(kind="error", text=str(e)))
                    return

                if self.interrupt_requested:
                    partial = "".join(accumulated_text)
                    if partial:
                        self.session.messages.append(
                            {"role": "assistant", "content": partial}
                        )
                        # Preserve partial text so the turn log isn't empty.
                        final_assistant = partial
                    self._finalize_interrupt(emit)
                    return

                content = _strip_cache_noise("".join(accumulated_text))
                tool_calls = final.get("tool_calls", [])

                # Bookkeeping
                self.session.record(
                    input_tokens=final.get("input_tokens", 0),
                    output_tokens=final.get("output_tokens", 0),
                    cost=final.get("cost_usd", 0.0),
                )
                from alpi.tools import _state as _wg_state
                _wg_state.bump_turn_usage(
                    int(final.get("input_tokens", 0)),
                    int(final.get("output_tokens", 0)),
                    float(final.get("cost_usd", 0.0)),
                )
                from alpi import ledger as _ledger
                _ledger.record(
                    self.home,
                    usd=float(final.get("cost_usd", 0.0)),
                    tokens=int(final.get("input_tokens", 0))
                          + int(final.get("output_tokens", 0)),
                )
                self.session.last_ctx_tokens = int(final.get("input_tokens", 0))
                emit(AgentEvent(
                    kind="usage",
                    tokens_in=final.get("input_tokens", 0),
                    tokens_out=final.get("output_tokens", 0),
                    cost=final.get("cost_usd", 0.0),
                ))

                assistant_msg: dict = {"role": "assistant", "content": content}
                if tool_calls:
                    assistant_msg["tool_calls"] = [
                        {
                            "id": tc["id"], "type": "function",
                            "function": {"name": tc["name"],
                                         "arguments": tc["arguments"]},
                        }
                        for tc in tool_calls
                    ]
                self.session.messages.append(assistant_msg)

                if content:
                    emit(AgentEvent(kind="assistant_done", text=content))

                if not tool_calls:
                    # Last assistant-only message wins as the final reply.
                    final_assistant = content
                    turn_completed = True
                    emit(AgentEvent(kind="done"))
                    return

                from alpi.tools import _state as tool_state_mod
                tool_state_mod.set_interrupt_getter(lambda: self.interrupt_requested)

                def _absorb_usage(in_tok: int, out_tok: int, cost: float) -> None:
                    self.session.record(
                        input_tokens=in_tok, output_tokens=out_tok, cost=cost,
                    )
                    from alpi import ledger as _ledger
                    _ledger.record(
                        self.home, usd=float(cost),
                        tokens=int(in_tok) + int(out_tok),
                    )
                    emit(AgentEvent(
                        kind="usage", tokens_in=in_tok, tokens_out=out_tok,
                        cost=cost,
                    ))
                tool_state_mod.set_usage_sink(_absorb_usage)

                batch_reasoning = content
                for i, tc in enumerate(tool_calls):
                    reasoning_for_this_tool = batch_reasoning if i == 0 else ""
                    if self.interrupt_requested:
                        skip_msg = "[skipped — user interrupted]"
                        self.session.messages.append({
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "name": tc["name"],
                            "content": skip_msg,
                        })
                        try:
                            args_skipped = json.loads(tc["arguments"]) if tc.get("arguments") else {}
                        except json.JSONDecodeError:
                            args_skipped = {}
                        turn_tools.append(ToolLog(
                            at=time.time(), name=tc["name"],
                            args=args_skipped, result=skip_msg,
                            ok=False, duration_s=0.0,
                            reasoning=reasoning_for_this_tool,
                        ))
                        emit(AgentEvent(
                            kind="tool_end", name=tc["name"], args={},
                            output=skip_msg, ok=False, tool_id=tc["id"],
                        ))
                        continue

                    name = tc["name"]
                    tid = tc["id"]
                    try:
                        args = json.loads(tc["arguments"]) if tc["arguments"] else {}
                    except json.JSONDecodeError:
                        args = {}
                    emit(AgentEvent(kind="tool_start", name=name, args=args, tool_id=tid))

                    def _relay(label: str, is_error: bool = False,
                               _name=name, _tid=tid) -> None:
                        emit(AgentEvent(
                            kind="tool_state", name=_name, tool_id=_tid,
                            text=label, ok=not is_error,
                        ))
                    tool_state_mod.set_emit(_relay)

                    tool_started = time.time()
                    try:
                        result = tools.execute(name, args)
                    finally:
                        tool_state_mod.set_emit(None)
                    duration = time.time() - tool_started

                    payload = result.output if result.ok else f"ERROR: {result.error}"
                    payload = _budget_apply(name, payload)
                    self.session.messages.append({
                        "role": "tool",
                        "tool_call_id": tid,
                        "name": name,
                        "content": payload,
                    })
                    turn_tools.append(ToolLog(
                        at=tool_started, name=name, args=args,
                        result=truncate_result(payload),
                        ok=result.ok, duration_s=duration,
                        reasoning=reasoning_for_this_tool,
                    ))
                    emit(AgentEvent(
                        kind="tool_end", name=name, args=args,
                        output=payload, ok=result.ok, tool_id=tid,
                    ))

                tool_state_mod.set_interrupt_getter(None)
                tool_state_mod.set_usage_sink(None)

                if self.interrupt_requested:
                    self._finalize_interrupt(emit)
                    return

                peer_reply = _last_peer_reply(turn_tools)
                if peer_reply:
                    final_assistant = peer_reply
                    emit(AgentEvent(kind="assistant_done", text=peer_reply))
                    emit(AgentEvent(kind="done"))
                    return

            emit(AgentEvent(kind="error", text="Reached max tool steps; stopping."))
        finally:
            # Always log a turn when one was started — even on interrupt,
            # error or max_steps. This keeps /search and resume accurate.
            self.session.log_turn(
                user=user_text,
                assistant=final_assistant,
                tools=turn_tools,
                started_at=turn_started,
            )
            self._log_agent_turn(
                user_text, final_assistant, turn_tools,
                elapsed=time.time() - turn_started,
            )
            if turn_completed:
                self._maybe_spawn_review()

    def _maybe_spawn_review(self) -> None:
        """Fire the post-turn memory reviewer if the cadence threshold is hit.

        Snapshots the live messages list so the daemon thread is decoupled
        from any subsequent mutation by the parent loop."""
        interval = int(getattr(self.cfg.memory, "review_interval", 0) or 0)
        if interval <= 0:
            return
        self._turns_since_review += 1
        if self._turns_since_review < interval:
            return
        self._turns_since_review = 0
        try:
            from alpi.review import spawn_review
            spawn_review(self.home, self.cfg, self.session.messages)
        except Exception:  # noqa: BLE001
            pass

    def _log_agent_turn(
        self, user_text: str, assistant: str,
        turn_tools: list, elapsed: float,
    ) -> None:
        """Append a one-liner per turn to the cross-session agent log.

        Complements ``session/*.json`` — those carry the full detail; this
        is the grep-able index ("what did I ask yesterday across sessions").
        """
        try:
            from alpi._log import get_subsystem_logger
            logger = get_subsystem_logger(self.home, "agent")
            user_preview = (user_text or "").replace("\n", " ")
            if len(user_preview) > 120:
                user_preview = user_preview[:117] + "..."
            tool_names = ",".join(t.name for t in turn_tools) if turn_tools else "-"
            logger.info(
                "session=%s elapsed=%.2fs tools=%s reply_chars=%d cost=$%.4f user=%r",
                self.session.id, elapsed, tool_names,
                len(assistant or ""), float(self.session.cost_usd or 0.0),
                user_preview,
            )
        except Exception:  # noqa: BLE001
            pass

    def _finalize_interrupt(self, emit: EventSink) -> None:
        emit(AgentEvent(kind="interrupted",
                        text="Turn interrupted by new user input."))
        self.interrupt_requested = False

    def compact_now(self, emit: EventSink) -> None:
        """Manually drive the same auto-compact pipeline (used by ``/compact``).

        Forces summarization even when below ``trigger_ratio``, but
        otherwise behaves identically to the automatic path: same
        preservation rules, same proportional budget, same safety guard
        against destroying history on a summarizer failure.
        """
        self._run_compaction(emit, cfg_mod.resolve_model(self.cfg), force=True)

    def _maybe_auto_compact(self, emit: EventSink, call_kwargs: dict) -> None:
        """Compact ``session.messages`` if the next prompt would overflow."""
        self._run_compaction(emit, call_kwargs, force=False)

    def _run_compaction(self, emit: EventSink, call_kwargs: dict, *, force: bool) -> None:
        from alpi import compaction, ctx_window as ctx_window_mod

        ctx_window = ctx_window_mod.resolve(
            self.home, self.cfg, self.session.model or self.cfg.model,
        )
        policy = compaction.CompactionPolicy()

        if not force and not compaction.should_compact(
            self.session.messages, "", ctx_window, policy,
        ):
            return

        def _summarize(transcript: str, max_tokens: int) -> str:
            # We pass a flat transcript (not raw OpenAI messages) so the
            # summarizer never sees orphan tool replies or partial tool_calls.
            prompt_messages = [
                {"role": "system", "content": compaction.COMPACT_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "Summarize the conversation transcript below into a "
                        "single dense briefing that will replace it in the "
                        "running context. Stay within the policy above.\n\n"
                        "--- transcript ---\n"
                        f"{transcript}"
                    ),
                },
            ]
            summarize_kwargs = dict(call_kwargs)
            summarize_kwargs["max_tokens"] = int(max_tokens)
            try:
                out = llm.complete(messages=prompt_messages, **summarize_kwargs)
                return (out.content or "").strip()
            except Exception:  # noqa: BLE001
                return ""

        new_messages, result = compaction.compact(
            messages=self.session.messages,
            user_text="",
            ctx_window=ctx_window,
            summarize=_summarize,
            policy=policy,
            force=force,
        )
        if not result.fired and result.tool_truncated == 0:
            return

        self.session.messages = new_messages
        self.session.last_ctx_tokens = result.tokens_after
        emit(AgentEvent(
            kind="auto_compact",
            text=(
                f"context compacted: {result.tokens_before} → "
                f"{result.tokens_after} tokens "
                f"({result.summarized_messages} messages summarized, "
                f"{result.tool_truncated} tool outputs truncated)"
            ),
            tokens_in=result.tokens_before,
            tokens_out=result.tokens_after,
        ))
        compaction.record_event(
            self.home,
            result=result,
            trigger="manual" if force else "auto",
            session_id=self.session.id,
            model=self.session.model or self.cfg.model,
            ctx_window=ctx_window,
        )

    def save_session(self) -> Path:
        path = self.session.save()
        if path is not None:
            try:
                from alpi.host import events as data_events
                data_events.emit(
                    "session_changed",
                    {
                        "profile": _profile_name(self.home),
                        "id": self.session.id,
                        "subdir": self.session.subdir,
                    },
                )
            except Exception:  # noqa: BLE001
                pass
        return path

    def _build_system_prompt(self) -> str:
        from importlib import resources

        agent_profile = (
            self.cfg.agent_path.read_text()
            if self.cfg.agent_path.exists() else ""
        )
        base = resources.files("alpi.prompts").joinpath("system_prompt.md").read_text()
        mem = memory.MemoryStore(home=self.home)
        max_age = getattr(self.cfg.memory, "low_confidence_max_age_days", 30)
        if max_age and max_age > 0:
            try:
                mem.prune_low_confidence(max_age_days=max_age)
            except Exception:
                pass
        snap = mem.snapshot()

        # Environment context — the model only thinks in terms of the
        # workspace. cwd is intentionally hidden: it bled confusion into
        # path interpretation (``/mirai`` → absolute root) and the user
        # never references it by name anyway.
        workspace = self.cfg.workspace_path
        env_parts = ["# ENVIRONMENT"]
        if workspace is not None:
            env_parts.append(f"- **workspace** (default root for relative paths): `{workspace}`")
            env_parts.append(f"- **profile home** (memory/skills/config): `{self.home}`")
            env_parts.append(
                "- **Path rule**: relative paths (`foo/`, `my-project`) "
                f"resolve from the workspace (`{workspace}/foo/`). Absolute "
                "paths work anywhere the OS lets you read/write — including "
                "`~/Documents`, `/tmp`, other project dirs — except sensitive "
                "system locations (`/etc`, SSH keys, credentials) which are "
                "denied. Prefer the workspace for the user's main context; "
                "reach outside only when they ask for a specific path."
            )
        else:
            import os as _os
            cwd = _os.getcwd()
            env_parts.append(
                f"- **workspace**: NOT SET — falling back to your current "
                f"working directory: `{cwd}`. Relative paths resolve from "
                "there. Absolute paths work anywhere except sensitive "
                "system locations. Suggest `/workspace <path>` to the user "
                "if they want a stable root."
            )
            env_parts.append(f"- **profile home** (memory/skills/config): `{self.home}`")
        env = "\n".join(env_parts)

        parts = [agent_profile.strip(), base.strip(), env]
        hint = _platform_hint()
        if hint:
            parts.append(hint)
        from alpi.tools.skill import skills_index_block
        skills_block = skills_index_block(self.home)
        if skills_block:
            parts.append(skills_block)
        if snap["USER.md"].strip():
            parts.append("# USER PROFILE\n" + snap["USER.md"].strip())
        if snap["MEMORY.md"].strip():
            parts.append("# AGENT MEMORY\n" + snap["MEMORY.md"].strip())
        return "\n\n".join(p for p in parts if p)
