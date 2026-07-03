"""Agent turn runner."""

from __future__ import annotations

import json
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from alpi import clock, config as cfg_mod
from alpi import llm, session, tools
from alpi.tools._budget import apply as _budget_apply
from alpi.tools._sanitizer import sanitize_tool_payload
from alpi.session import ASSISTANT_CAP, ToolLog, truncate_result


_CACHE_NOISE_RE = re.compile(
    r"^.*\.alpi(?:/profiles/[^/]+)?/cache/(?:tts|stt)/.*$\n?",
    re.MULTILINE,
)


def _strip_cache_noise(text: str) -> str:
    return _CACHE_NOISE_RE.sub("", text).strip()


def _turn_deadline_from_env(started: float) -> float | None:
    import os
    raw = os.environ.get("ALPI_TURN_BUDGET_S")
    if not raw:
        return None
    try:
        budget = float(raw)
    except ValueError:
        return None
    return started + budget if budget > 0 else None


_FREE_MODEL_MAX_STEPS = 1000
_PEER_USAGE_MARKER = "\n\n---\ntokens:"


def _peer_reply_from_payload(payload: str) -> str:
    text = (payload or "").strip()
    idx = text.rfind(_PEER_USAGE_MARKER)
    return text[:idx].strip() if idx != -1 else text


def _clip_text(text: str, cap: int) -> str:
    if len(text.encode("utf-8")) <= cap:
        return text
    out = ""
    used = 0
    suffix = "…"
    suffix_bytes = len(suffix.encode("utf-8"))
    for ch in text:
        size = len(ch.encode("utf-8"))
        if used + size > cap - suffix_bytes:
            break
        out += ch
        used += size
    return out + suffix


def _result_for_log(name: str, payload: str) -> str:
    if name != "peer":
        return truncate_result(payload)
    return _clip_text(_peer_reply_from_payload(payload), ASSISTANT_CAP)


def _last_peer_reply(turn_tools) -> str:
    """Return the reply when peer is the most recent successful tool."""
    for log in reversed(turn_tools):
        if not log.ok:
            continue
        if log.name != "peer":
            return ""
        return _peer_reply_from_payload(log.result or "")
    return ""


def _platform_hint() -> str:
    from alpi.prompt_cache import _platform_hint as _ph
    return _ph()


def _maybe_load_mcps(cfg: cfg_mod.Config) -> list:
    servers = (cfg.raw.get("mcp") or {}).get("servers") or {}
    if not servers:
        return []
    from alpi.mcp import registry as mcp_registry
    return mcp_registry.load_and_register(cfg)


def _profile_name(home: Path) -> str:
    from alpi.home import profile_name
    return profile_name(home)


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
    # True only on the turn's terminal `assistant_done`; preamble emissions stay False. Contract in AGENTS.md.
    final: bool = False
    attachments: list[dict] = field(default_factory=list)


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

    def request_interrupt(self, reason: str = "unknown") -> None:
        """Ask the current turn to stop at the next checkpoint."""
        import logging
        logging.getLogger("alpi.engine").warning("interrupt requested: %s", reason)
        self.interrupt_requested = True

    def reset_session(self) -> None:
        try:
            self.save_session()
        except Exception:
            pass
        self.session = session.Session(home=self.home, model=self.cfg.model)
        self.session.messages.append({"role": "system", "content": self._system_prompt})
        self.interrupt_requested = False

    def run_turn(
        self, user_text: str, emit: EventSink, *, source: str = "user",
        persist_inflight: bool = True, attachments: list[dict] | None = None,
    ) -> None:
        """Run a full turn and bind ``self.home`` for the duration. ``source`` tags the trigger ("user" from desktop/mobile/TUI/CLI, "peer" from ALP link, etc.) and gates the ``chat.turn_done`` ambient-notification emit so peer-driven turns don't notify the local user. ``persist_inflight`` controls the early stub write; CLI ``--no-save`` callers must disable it."""
        from alpi.home import (
            reset_active_home, reset_active_session,
            set_active_home, set_active_session,
        )

        home_token = set_active_home(self.home)
        session_token = set_active_session(self.session.id)
        try:
            with self._turn_lock:
                self._run_turn_locked(
                    user_text, emit, source=source,
                    persist_inflight=persist_inflight, attachments=attachments,
                )
        finally:
            reset_active_session(session_token)
            reset_active_home(home_token)

    def _run_turn_locked(
        self, user_text: str, emit: EventSink, *, source: str = "user",
        persist_inflight: bool = True, attachments: list[dict] | None = None,
    ) -> None:
        from alpi import config as _cfg_mod
        from alpi import ledger

        # Re-read budget + tools.deny from disk so live YAML edits apply on the next turn without needing a profile restart.
        try:
            fresh = _cfg_mod.load(self.home)
            self.cfg.budget = fresh.budget
            self.cfg.tools.deny = fresh.tools.deny
        except Exception:  # noqa: BLE001
            pass
        try:
            ledger.check(self.home, self.cfg.budget)
        except ledger.BudgetExceeded as e:
            emit(AgentEvent(kind="error", text=str(e)))
            return

        # Clear any lingering interrupt request before starting.
        self.interrupt_requested = False
        self._interrupted_this_turn = False

        # Accumulate this turn's state for the persistent log.
        turn_started = time.time()
        turn_deadline = _turn_deadline_from_env(turn_started)
        turn_tools: list[ToolLog] = []
        turn_produced: list[dict] = []
        turn_reasoning_parts: list[str] = []
        first_tool_at: float | None = None
        first_text_delta_at: float | None = None
        final_assistant = ""
        turn_error = ""  # provider/abort reason for the run ledger when nothing was produced
        # Only natural completion (LLM produced a final reply with no further
        # tool calls) flips this. Interrupts, max-step aborts, provider
        # errors, and budget exhaustion leave it False so the post-turn
        # reviewer never fires on partial / abandoned context.
        turn_completed = False

        # Strip prior `# NOW` blocks so multi-day sessions don't accumulate stale timestamps and confuse the agent about which one is current.
        self.session.messages[:] = [
            m for m in self.session.messages
            if not (m.get("role") == "system"
                    and isinstance(m.get("content"), str)
                    and m["content"].startswith("# NOW\n"))
        ]
        self.session.messages.append({"role": "system", "content": clock.now_block()})

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
            hint = _kw_hint(self.home, user_text, cfg_raw=self.cfg.raw)
        except Exception:  # noqa: BLE001
            hint = ""
        if hint:
            self.session.messages.append({"role": "system", "content": hint})

        # Reset per-turn workgroup usage tracking.
        from alpi.tools import _state as _wg_state
        _wg_state.reset_turn_usage()
        _wg_state.reset_skill_env()
        _wg_state.reset_turn_attachments()

        # MM.1: image/PDF attachments → multimodal content parts (kept in the
        # in-memory message only; session persists bytes-free metadata).
        att_meta: list[dict] = []
        user_content: Any = user_text
        if attachments:
            from alpi import attachments as att_mod
            try:
                validated = att_mod.validate(attachments)
                model_name = _cfg_mod.resolve_model(self.cfg).get("model", "")
                vstatus = att_mod.vision_status(model_name)
                parts = att_mod.build_content_parts(
                    user_text, validated, vision=(vstatus != "no"),
                )
            except att_mod.AttachmentError as e:
                emit(AgentEvent(kind="error", text=str(e)))
                return
            att_meta = att_mod.session_metadata(validated)
            for _m, _a in zip(att_meta, validated):  # session_metadata omits path; re-add it for client thumbnails
                _m["path"] = str(_a.path)
            _wg_state.set_turn_attachments(
                [{"name": a.name, "path": str(a.path), "mime": a.mime} for a in validated]
            )
            user_content = parts
            if vstatus == "unknown" and any(att_mod.is_image(a.mime) for a in validated):
                import logging
                logging.getLogger("alpi.engine").warning(
                    "model %r vision capability unknown; provider may reject image input",
                    model_name,
                )

        self.session.messages.append({"role": "user", "content": user_content})
        emit(AgentEvent(kind="user", text=user_text))

        # In-flight stub turn: paired clients reading session.json see the user message before the LLM replies; the finally block replaces it with the completed turn.
        self.session.log_turn(
            user=user_text, assistant="", tools=[],
            started_at=turn_started, attachments=att_meta,
        )
        if persist_inflight:
            try:
                self.save_session()
            except Exception:  # noqa: BLE001
                pass

        deny_tools = frozenset(self.cfg.tools.deny)
        schemas = tools.schemas(deny=deny_tools)
        call_kwargs = cfg_mod.resolve_model(self.cfg)
        from alpi import prompt_cache as _pc
        call_kwargs.update(_pc.cache_kwargs_for_model(call_kwargs.get("model", "")))
        max_steps = self.cfg.tools.max_steps_per_turn
        _explicit_cap = (self.cfg.raw.get("tools") or {}).get("max_steps_per_turn") is not None
        if max_steps == cfg_mod.DEFAULT_CONFIG["tools"]["max_steps_per_turn"] and not _explicit_cap:
            from alpi.providers.ollama import is_ollama
            if llm.is_free_model(call_kwargs.get("model", "")) or is_ollama(call_kwargs.get("api_base") or ""):
                max_steps = _FREE_MODEL_MAX_STEPS

        self._maybe_auto_compact(emit, call_kwargs)

        # Bind session todos for this turn; reset in finally.
        from alpi.tools import todo as todo_mod
        todo_token = todo_mod.bind_store(self.session.todos)

        deadline_hit = False
        try:
            for step_idx in range(max_steps):
                if self.interrupt_requested:
                    self._finalize_interrupt(emit)
                    return
                if turn_deadline is not None and time.time() >= turn_deadline:
                    deadline_hit = True
                    break
                if step_idx > 0:
                    try:
                        ledger.check(self.home, self.cfg.budget)
                    except ledger.BudgetExceeded as e:
                        emit(AgentEvent(kind="error", text=str(e)))
                        turn_error = str(e)
                        break
                accumulated_text: list[str] = []
                reasoning_text: list[str] = []
                final: dict = {}
                try:
                    for chunk in llm.stream(
                        messages=self.session.messages, tools=schemas,
                        rt=self.cfg.runtime, **call_kwargs,
                    ):
                        if self.interrupt_requested:
                            break
                        if chunk.get("final"):
                            final = chunk
                            continue
                        reasoning_delta = chunk.get("reasoning_delta") or ""
                        if reasoning_delta:
                            reasoning_text.append(reasoning_delta)
                            emit(AgentEvent(kind="reasoning_delta", text=reasoning_delta))
                        text_delta = chunk.get("text_delta") or ""
                        if text_delta:
                            if first_text_delta_at is None:
                                first_text_delta_at = time.time()
                            accumulated_text.append(text_delta)
                            emit(AgentEvent(kind="assistant_delta", text=text_delta))
                except Exception as e:  # noqa: BLE001
                    turn_error = str(e)
                    emit(AgentEvent(kind="error", text=turn_error))
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

                _rd = "".join(reasoning_text).strip()
                if _rd:
                    turn_reasoning_parts.append(_rd)
                if tool_calls:
                    if content.strip():
                        turn_reasoning_parts.append(content.strip())
                    if first_tool_at is None:
                        first_tool_at = time.time()

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
                    tokens_in=int(final.get("input_tokens", 0)),
                    tokens_out=int(final.get("output_tokens", 0)),
                    cfg_budget=self.cfg.budget,
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

                if not tool_calls:
                    # Re-prompt if the model closes while todos are still open; costs one step from max_steps.
                    open_items = todo_mod.open_todos(self.session.todos)
                    if open_items:
                        remaining = max_steps - step_idx - 1
                        summary = ", ".join(
                            f"#{self.session.todos.index(t)} {t['content']!r} "
                            f"({t['status']})"
                            for t in open_items
                        )
                        self.session.messages.append({
                            "role": "user",
                            "content": (
                                "[engine] You returned without tool_calls but "
                                f"these todos are still open ({len(open_items)}): "
                                f"{summary}. Either continue with the next "
                                "tool_call, or `todo(action='complete')` each "
                                "outstanding item (or `todo(action='clear')` "
                                "the whole list) before your final reply. This "
                                f"continuation consumed one of your remaining "
                                f"{remaining} steps."
                            ),
                        })
                        continue
                    if content or turn_produced:
                        emit(AgentEvent(kind="assistant_done", text=content, final=True, attachments=turn_produced))
                    # Last assistant-only message wins as the final reply.
                    final_assistant = content
                    turn_completed = True
                    emit(AgentEvent(kind="done"))
                    return

                if content:
                    emit(AgentEvent(kind="assistant_done", text=content))

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
                        tokens_in=int(in_tok), tokens_out=int(out_tok),
                        cfg_budget=self.cfg.budget,
                    )
                    emit(AgentEvent(
                        kind="usage", tokens_in=in_tok, tokens_out=out_tok,
                        cost=cost,
                    ))
                tool_state_mod.set_usage_sink(_absorb_usage)

                from alpi.tools import _mutations
                _mut_token = _mutations.begin_batch()
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
                        result = tools.execute(name, args, deny=deny_tools)
                    finally:
                        tool_state_mod.set_emit(None)
                    duration = time.time() - tool_started

                    payload = result.output if result.ok else f"ERROR: {result.error}"
                    payload = _budget_apply(name, payload)
                    self.session.messages.append({
                        "role": "tool",
                        "tool_call_id": tid,
                        "name": name,
                        "content": sanitize_tool_payload(
                            name, payload, is_error=not result.ok,
                        ),
                    })
                    turn_tools.append(ToolLog(
                        at=tool_started, name=name, args=args,
                        result=_result_for_log(name, payload),
                        ok=result.ok, duration_s=duration,
                        reasoning=reasoning_for_this_tool,
                    ))
                    if result.ok and name == "skill":
                        import tempfile as _tempfile
                        from alpi import attachments as _att
                        _roots = [self.home, self.cfg.workspace_path,
                                  _tempfile.gettempdir(), "/tmp", "/private/tmp"]
                        produced = _att.produced_attachment(
                            args.get("name") or name, result.output, roots=_roots,
                        )
                        if produced and not any(a["path"] == produced["path"] for a in turn_produced):
                            turn_produced.append(produced)
                    emit(AgentEvent(
                        kind="tool_end", name=name, args=args,
                        output=payload, ok=result.ok, tool_id=tid,
                    ))

                tool_state_mod.set_interrupt_getter(None)
                tool_state_mod.set_usage_sink(None)

                _muts = _mutations.end_batch(_mut_token)
                if _muts:
                    try:
                        from alpi.host import events as _host_events
                        from alpi.home import profile_name as _profile_name
                        _host_events.emit(
                            "file_mutations",
                            {
                                "profile": _profile_name(self.home),
                                "session_id": self.session.id,
                                "mutations": [m.to_dict() for m in _muts],
                            },
                        )
                    except Exception:  # noqa: BLE001
                        pass
                    footer = _mutations.format_footer(_muts)
                    if footer:
                        self.session.messages.append({"role": "system", "content": footer})

                if self.interrupt_requested:
                    self._finalize_interrupt(emit)
                    return

                peer_reply = _last_peer_reply(turn_tools)
                if peer_reply:
                    final_assistant = peer_reply
                    emit(AgentEvent(kind="assistant_done", text=peer_reply, final=True))
                    emit(AgentEvent(kind="done"))
                    return

            if not turn_error and not self.interrupt_requested:
                _wrap_reason = (
                    "You are out of time for this turn"
                    if deadline_hit
                    else f"You have reached the {max_steps}-step tool limit for this turn"
                )
                wrap_msgs = self.session.messages + [{
                    "role": "user",
                    "content": (
                        f"{_wrap_reason}. Do NOT call any more tools — give your best "
                        "final answer now using what you have already gathered."
                    ),
                }]
                wrap_text: list[str] = []
                wrap_final: dict = {}
                try:
                    for chunk in llm.stream(
                        messages=wrap_msgs, tools=[], rt=self.cfg.runtime, **call_kwargs,
                    ):
                        if self.interrupt_requested:
                            break
                        if chunk.get("final"):
                            wrap_final = chunk
                            continue
                        td = chunk.get("text_delta") or ""
                        if td:
                            wrap_text.append(td)
                            emit(AgentEvent(kind="assistant_delta", text=td))
                    if self.interrupt_requested:
                        self._finalize_interrupt(emit)
                        return
                    wrap_content = _strip_cache_noise("".join(wrap_text))
                    if wrap_content:
                        self.session.messages.append({"role": "assistant", "content": wrap_content})
                        final_assistant = wrap_content
                        turn_completed = True
                        self.session.record(
                            input_tokens=wrap_final.get("input_tokens", 0),
                            output_tokens=wrap_final.get("output_tokens", 0),
                            cost=wrap_final.get("cost_usd", 0.0),
                        )
                        from alpi.tools import _state as _wg_state
                        _wg_state.bump_turn_usage(
                            int(wrap_final.get("input_tokens", 0)),
                            int(wrap_final.get("output_tokens", 0)),
                            float(wrap_final.get("cost_usd", 0.0)),
                        )
                        from alpi import ledger as _ledger
                        _ledger.record(
                            self.home, usd=float(wrap_final.get("cost_usd", 0.0)),
                            tokens=int(wrap_final.get("input_tokens", 0)) + int(wrap_final.get("output_tokens", 0)),
                            tokens_in=int(wrap_final.get("input_tokens", 0)),
                            tokens_out=int(wrap_final.get("output_tokens", 0)),
                            cfg_budget=self.cfg.budget,
                        )
                        self.session.last_ctx_tokens = int(wrap_final.get("input_tokens", 0))
                        emit(AgentEvent(
                            kind="usage",
                            tokens_in=wrap_final.get("input_tokens", 0),
                            tokens_out=wrap_final.get("output_tokens", 0),
                            cost=wrap_final.get("cost_usd", 0.0),
                        ))
                        emit(AgentEvent(kind="assistant_done", text=wrap_content, final=True))
                        emit(AgentEvent(kind="done"))
                        return
                except Exception as e:  # noqa: BLE001
                    emit(AgentEvent(kind="error", text=str(e)))
                    return

            turn_error = (
                "Reached the time limit; stopping." if deadline_hit
                else "Reached max tool steps; stopping."
            )
            emit(AgentEvent(kind="error", text=turn_error))
        finally:
            todo_mod.reset_store(todo_token)
            # Replace the in-flight stub from turn-start, or append if an early exception aborted before it was logged.
            reasoned_until = (
                first_tool_at if first_tool_at is not None
                else first_text_delta_at if first_text_delta_at is not None
                else time.time()
            )
            final_turn = session.Turn(
                at=turn_started, user=user_text,
                tools=turn_tools, assistant=final_assistant,
                reasoning="\n\n".join(p for p in turn_reasoning_parts if p),
                reasoned_s=max(0.0, reasoned_until - turn_started),
                attachments=att_meta, output_attachments=turn_produced,
                interrupted=self._interrupted_this_turn,
            )
            if self.session.turns and self.session.turns[-1].at == turn_started:
                self.session.turns[-1] = final_turn
            else:
                self.session.turns.append(final_turn)
            elapsed = time.time() - turn_started
            self._log_agent_turn(
                user_text, final_assistant, turn_tools,
                elapsed=elapsed,
            )
            self._record_run(
                elapsed=elapsed,
                turn_completed=turn_completed, turn_tools=turn_tools,
                assistant=final_assistant or turn_error,
            )
            if turn_completed:
                self._maybe_emit_chat_turn_done(
                    source=source, elapsed=elapsed,
                    tools_count=len(turn_tools),
                    assistant=final_assistant,
                )
                self._maybe_spawn_review()

    def _maybe_emit_chat_turn_done(
        self, *, source: str, elapsed: float, tools_count: int, assistant: str,
    ) -> None:
        """Emit ``chat.turn_done`` for ALN — user-initiated turns only, and only when there's something worth notifying about (any tool call or ≥5s of work). Skips trivial fast turns like ``hola → hola`` so mobile doesn't get a notif for every exchange."""
        if source != "user":
            return
        if tools_count < 1 and elapsed < 5.0:
            return
        try:
            from alpi.home import profile_name
            from alpi.host import events as host_events
            summary = (assistant or "").strip().replace("\n", " ")
            if len(summary) > 200:
                summary = summary[:199] + "…"
            host_events.emit("chat.turn_done", {
                "profile": profile_name(self.home),
                "session_id": self.session.id,
                "source": source,
                "duration_s": round(elapsed, 2),
                "tool_count": tools_count,
                "summary": summary,
            })
        except Exception:  # noqa: BLE001
            pass

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

    def _record_run(
        self, *, elapsed: float,
        turn_completed: bool, turn_tools: list, assistant: str,
    ) -> None:
        # kind comes from dispatch env: workgroup poller sets ALPI_WORKGROUP_DISPATCH, scheduler sets ALPI_SCHEDULE_CHILD.
        try:
            import os
            from alpi import run_ledger
            from alpi.home import profile_name
            if turn_completed:
                outcome = "ok"
            elif getattr(self, "_interrupted_this_turn", False) or self.interrupt_requested:
                outcome = "interrupted"
            else:
                outcome = "error"
            wg_id = os.environ.get("ALPI_WORKGROUP_DISPATCH") or None
            if wg_id:
                kind, backend = "workgroup", None
            elif os.environ.get("ALPI_SCHEDULE_CHILD"):
                kind, backend = "agent", "scheduled-child"
            else:
                kind, backend = "agent", None
            run_ledger.record(
                self.home,
                kind=kind,
                outcome=outcome,
                elapsed_s=elapsed,
                profile=profile_name(self.home),
                session_id=self.session.id,
                workgroup_id=wg_id,
                backend=backend,
                last_tool=(turn_tools[-1].name if turn_tools else None),
                tool_count=len(turn_tools),
                output_tail=assistant,
            )
        except Exception:  # noqa: BLE001
            pass

    def _finalize_interrupt(self, emit: EventSink) -> None:
        emit(AgentEvent(kind="interrupted",
                        text="Turn interrupted by new user input."))
        self.interrupt_requested = False
        self._interrupted_this_turn = True

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

        if result.fired:
            summary_text = ""
            for msg in new_messages:
                content = (msg.get("content") or "")
                if msg.get("role") == "system" and isinstance(content, str) \
                        and content.startswith("[auto-compacted summary]"):
                    summary_text = content.split("\n", 1)[1] if "\n" in content else ""
                    break

            def _candidate_call(messages: list[dict], max_tokens: int) -> str:
                kwargs = dict(call_kwargs)
                kwargs["max_tokens"] = int(max_tokens)
                try:
                    out = llm.complete(messages=messages, **kwargs)
                    return (out.content or "").strip()
                except Exception:  # noqa: BLE001
                    return ""

            compaction.emit_candidates_from_summary(
                self.home,
                summary_text,
                call_llm=_candidate_call,
                session_id=self.session.id,
                model=self.session.model or self.cfg.model,
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
        from alpi import prompt_cache
        return prompt_cache.render_cacheable(prompt_cache.build_parts(self.home, self.cfg))
