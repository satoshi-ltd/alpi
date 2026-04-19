"""Session state — turns-based storage.

A session is a list of :class:`Turn`\\s. Each turn is one user input, the
tools/skills alf ran, and alf's final reply. That's the full log — we do
*not* persist the raw OpenAI-style message thread (with huge tool
outputs) because it bloats disk without giving anything session-search
or humans actually need.

Runtime state (:attr:`Session.messages`) still holds OpenAI messages —
the LLM API needs that format — but ``save()`` only writes turns. On
``--continue`` we rebuild a lean ``messages`` list from turns (system +
[user, assistant] per turn, no tool messages). The LLM on resume sees a
clean chat history; it can't reproduce the exact tool trace but the
assistant's own words carry the conclusions forward.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# Per-tool log stored under each Turn. Short, human-friendly, JSON-safe.
# We deliberately keep ``result`` capped so search snippets stay tight.
TOOL_RESULT_CAP = 400


@dataclass
class ToolLog:
    at: float
    name: str
    args: dict[str, Any]
    result: str           # short hint — not the full raw output
    ok: bool
    duration_s: float


@dataclass
class Turn:
    at: float
    user: str
    tools: list[ToolLog]
    assistant: str        # alf's final text reply (last no-tool-calls message)


@dataclass
class Session:
    home: Path
    model: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    started_at: float = field(default_factory=time.time)
    # Runtime-only: the OpenAI message thread the engine feeds to the LLM.
    # Contains system + user/assistant/tool messages. NOT saved to disk.
    messages: list[dict[str, Any]] = field(default_factory=list)
    # Persisted log of completed user turns.
    turns: list[Turn] = field(default_factory=list)
    input_tokens: int = 0       # cumulative across all turns in this session
    output_tokens: int = 0      # cumulative across all turns in this session
    last_ctx_tokens: int = 0    # size of the last LLM prompt (current context window usage)
    cost_usd: float = 0.0

    @property
    def elapsed(self) -> float:
        return time.time() - self.started_at

    def record(self, *, input_tokens: int, output_tokens: int, cost: float) -> None:
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.cost_usd += cost

    def log_turn(
        self,
        *,
        user: str,
        assistant: str,
        tools: list[ToolLog],
        started_at: float | None = None,
    ) -> None:
        """Append a completed user turn to the persistent log."""
        self.turns.append(Turn(
            at=started_at if started_at is not None else time.time(),
            user=user,
            tools=tools,
            assistant=assistant,
        ))

    def status_line(self) -> str:
        mins, secs = divmod(int(self.elapsed), 60)
        total = self.input_tokens + self.output_tokens
        return (
            f"model: {self.model}  │  "
            f"tokens: {total:,}  │  "
            f"session: {mins:02d}:{secs:02d}  │  "
            f"cost: ${self.cost_usd:.3f}"
        )

    def save(self) -> Path | None:
        """Persist this session as JSON if at least one turn completed."""
        if not self.turns:
            return None
        path = self.home / "sessions" / f"{self.id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        import json
        payload = {
            "id": self.id,
            "model": self.model,
            "started_at": self.started_at,
            "elapsed": self.elapsed,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": self.cost_usd,
            "last_ctx_tokens": self.last_ctx_tokens,
            "turns": [
                {
                    "at": t.at,
                    "user": t.user,
                    "assistant": t.assistant,
                    "tools": [
                        {
                            "at": tl.at, "name": tl.name, "args": tl.args,
                            "result": tl.result, "ok": tl.ok,
                            "duration_s": round(tl.duration_s, 3),
                        }
                        for tl in t.tools
                    ],
                }
                for t in self.turns
            ],
        }
        path.write_text(json.dumps(payload, indent=2, default=str))
        return path


def load_turns(data: dict[str, Any]) -> list[Turn]:
    """Parse the turns list from a serialized session payload."""
    out: list[Turn] = []
    for t in data.get("turns", []):
        tools = [
            ToolLog(
                at=float(tl.get("at", 0)),
                name=str(tl.get("name", "")),
                args=dict(tl.get("args") or {}),
                result=str(tl.get("result", "")),
                ok=bool(tl.get("ok", True)),
                duration_s=float(tl.get("duration_s", 0)),
            )
            for tl in (t.get("tools") or [])
        ]
        out.append(Turn(
            at=float(t.get("at", 0)),
            user=str(t.get("user", "")),
            tools=tools,
            assistant=str(t.get("assistant", "")),
        ))
    return out


def truncate_result(raw: str) -> str:
    """Apply the standard cap to a tool output before storing it."""
    text = (raw or "").strip()
    if len(text) <= TOOL_RESULT_CAP:
        return text
    return text[:TOOL_RESULT_CAP - 1] + "…"
