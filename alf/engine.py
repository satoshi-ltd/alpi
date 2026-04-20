"""Agent turn runner.

Owns the Session and runs one turn at a time (user input → possibly many LLM
calls with tool-use loop). It emits events via a callback so the caller
(CLI / gateway / tests) renders progress without knowing how the loop works.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from alf import config as cfg_mod
from alf import llm, memory, session, tools
from alf.session import ToolLog, truncate_result


def _maybe_load_mcps(cfg: cfg_mod.Config) -> list:
    """Spawn+register configured MCP servers. Never fatal.

    Kept isolated so a user who hasn't touched MCPs pays no import
    cost (the deep import below only runs if there's at least one
    entry in ``mcp.servers``).
    """
    servers = (cfg.raw.get("mcp") or {}).get("servers") or {}
    if not servers:
        return []
    from alf.mcp import registry as mcp_registry
    return mcp_registry.load_and_register(cfg)


@dataclass
class AgentEvent:
    kind: str                      # 'user' | 'assistant_delta' | 'assistant_done' | 'tool_start' | 'tool_state' | 'tool_end' | 'usage' | 'error' | 'done' | 'interrupted'
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
        # Spawn MCP servers the user configured and register their
        # tools BEFORE we bake the system prompt, so the tool list in
        # the prompt includes them.
        self._mcp_clients = _maybe_load_mcps(cfg)
        self._system_prompt = self._build_system_prompt()
        self.session.messages.append({"role": "system", "content": self._system_prompt})
        # Cross-thread flag: the UI sets this to True on new user input while
        # a turn is still running. The loop polls it between LLM streaming,
        # between tool-use iterations, and between individual tool calls.
        self.interrupt_requested: bool = False
        # Serializes turns. A new run_turn() blocks on this lock until the
        # previous one has fully exited — otherwise two turns race on
        # session.messages and a slow tool call (e.g. delegate mid-stream)
        # can vomit its result into the *next* turn's context.
        self._turn_lock = threading.Lock()

    def request_interrupt(self) -> None:
        """Ask the current run_turn() to stop at the next check-point."""
        self.interrupt_requested = True

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_turn(self, user_text: str, emit: EventSink) -> None:
        """Run a full user turn. Blocking — call from a worker thread.

        Streams assistant tokens via ``assistant_delta`` events and emits
        ``tool_start`` / ``tool_end`` per tool invocation.

        Serialized: if another turn is still running (common when the user
        interrupted it and immediately sent a new message), this blocks
        until the previous turn releases the lock. The in-flight turn
        should exit quickly because ``interrupt_requested`` is set.
        """
        with self._turn_lock:
            self._run_turn_locked(user_text, emit)

    def _run_turn_locked(self, user_text: str, emit: EventSink) -> None:
        # Fresh run: clear any lingering interrupt request from the previous
        # turn before we start consuming input.
        self.interrupt_requested = False

        # Accumulate this turn's state. The try/finally at the bottom
        # always appends a Turn to the persistent log, regardless of how
        # we exit (normal / interrupt / error / max_steps).
        turn_started = time.time()
        turn_tools: list[ToolLog] = []
        final_assistant = ""

        self.session.messages.append({"role": "user", "content": user_text})
        emit(AgentEvent(kind="user", text=user_text))

        schemas = tools.schemas()
        call_kwargs = cfg_mod.resolve_model(self.cfg)
        max_steps = self.cfg.tools.max_steps_per_turn

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

                content = "".join(accumulated_text)
                tool_calls = final.get("tool_calls", [])

                # Bookkeeping
                self.session.record(
                    input_tokens=final.get("input_tokens", 0),
                    output_tokens=final.get("output_tokens", 0),
                    cost=final.get("cost_usd", 0.0),
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
                    emit(AgentEvent(kind="done"))
                    return

                from alf.tools import _state as tool_state_mod
                tool_state_mod.set_interrupt_getter(lambda: self.interrupt_requested)

                def _absorb_usage(in_tok: int, out_tok: int, cost: float) -> None:
                    self.session.record(
                        input_tokens=in_tok, output_tokens=out_tok, cost=cost,
                    )
                    emit(AgentEvent(
                        kind="usage", tokens_in=in_tok, tokens_out=out_tok,
                        cost=cost,
                    ))
                tool_state_mod.set_usage_sink(_absorb_usage)

                for tc in tool_calls:
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
                    payload = payload[:10_000]
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

    def _finalize_interrupt(self, emit: EventSink) -> None:
        """Emit a terminal 'interrupted' event and reset the flag.

        Caller is expected to return immediately after this.
        """
        emit(AgentEvent(kind="interrupted",
                        text="Turn interrupted by new user input."))
        self.interrupt_requested = False

    def save_session(self) -> Path:
        return self.session.save()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_system_prompt(self) -> str:
        from importlib import resources

        personality = (
            self.cfg.personality_path.read_text()
            if self.cfg.personality_path.exists() else ""
        )
        base = resources.files("alf.prompts").joinpath("system_prompt.md").read_text()
        mem = memory.MemoryStore(home=self.home)
        snap = mem.snapshot()

        # Environment context — the model only thinks in terms of the
        # workspace. cwd is intentionally hidden: it bled confusion into
        # path interpretation (``/mirai`` → absolute root) and the user
        # never references it by name anyway.
        workspace = self.cfg.workspace_path
        env_parts = ["# ENVIRONMENT"]
        if workspace is not None:
            env_parts.append(f"- **workspace** (your only filesystem root): `{workspace}`")
            env_parts.append(f"- **profile home** (memory/skills/config): `{self.home}`")
            env_parts.append(
                "- **Path rule**: every path the user mentions is relative "
                "to the workspace unless it's clearly a system path "
                "(`/etc/...`, `/usr/...`, etc.). User-style references like "
                "`/mirai`, `foo/`, `my-project` → resolve as "
                f"`{workspace}/mirai`, `{workspace}/foo/`, etc. Do **not** "
                "run commands from outside the workspace, and do not reach "
                "into the user's home with `~/Documents` etc. unless they "
                "explicitly ask with a full path."
            )
        else:
            env_parts.append(
                "- **workspace**: NOT SET. Ask the user to run `/workspace <path>` "
                "to pin a directory. Until then, refuse file/terminal tool calls "
                "that reference any path — you don't have enough context."
            )
            env_parts.append(f"- **profile home**: `{self.home}`")
        env = "\n".join(env_parts)

        parts = [personality.strip(), base.strip(), env]
        if snap["USER.md"].strip():
            parts.append("# USER PROFILE\n" + snap["USER.md"].strip())
        if snap["MEMORY.md"].strip():
            parts.append("# AGENT MEMORY\n" + snap["MEMORY.md"].strip())
        return "\n\n".join(p for p in parts if p)
