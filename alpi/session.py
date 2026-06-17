"""Session state — turns-based storage."""

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
    reasoning: str = ""   # inter-tool prose; non-empty only on the first tool of a batch


@dataclass
class Turn:
    at: float
    user: str
    tools: list[ToolLog]
    assistant: str        # alpi's final text reply (last no-tool-calls message)
    reasoning: str = ""
    reasoned_s: float = 0.0
    attachments: list[dict[str, Any]] = field(default_factory=list)  # bytes-free; carries a best-effort local path (may be unfetchable cross-client / post-TTL)
    output_attachments: list[dict[str, Any]] = field(default_factory=list)  # bytes-free; carries a best-effort local path (may be unfetchable cross-client / post-TTL)


@dataclass
class Session:
    home: Path
    model: str
    # Subdirectory under ``home`` where ``save()`` lands. Gateway turns
    # use ``gateway/sessions`` so they stay out of the local TUI/desktop
    # list (which reads ``sessions/`` only) and don't collide with the
    # transport state files in ``gateway/`` itself.
    subdir: str = "sessions"
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    started_at: float = field(default_factory=time.time)
    # Runtime-only: the OpenAI message thread the engine feeds to the LLM.
    # Contains system + user/assistant/tool messages. NOT saved to disk.
    messages: list[dict[str, Any]] = field(default_factory=list)
    # Runtime-only: per-session todo store; engine binds it for the `todo` tool. Not persisted.
    todos: list[dict[str, Any]] = field(default_factory=list)
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
        attachments: list[dict[str, Any]] | None = None,
    ) -> None:
        """Append a completed user turn to the persistent log."""
        self.turns.append(Turn(
            at=started_at if started_at is not None else time.time(),
            user=user,
            tools=tools,
            assistant=assistant,
            attachments=list(attachments or []),
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
        path = self.home / self.subdir / f"{self.id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        import json
        import os
        import tempfile
        from alpi._redact import redact
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
                    "user": redact(t.user),
                    "assistant": redact(t.assistant),
                    "tools": [
                        {
                            "at": tl.at, "name": tl.name,
                            "args": redact(tl.args),
                            "result": redact(tl.result), "ok": tl.ok,
                            "duration_s": round(tl.duration_s, 3),
                            **({"reasoning": redact(tl.reasoning)} if tl.reasoning else {}),
                        }
                        for tl in t.tools
                    ],
                    **({"reasoning": redact(t.reasoning)} if t.reasoning else {}),
                    **({"reasoned_s": round(t.reasoned_s, 1)} if t.reasoned_s else {}),
                    **({"attachments": redact(t.attachments)} if t.attachments else {}),
                    **({"output_attachments": redact(t.output_attachments)} if t.output_attachments else {}),
                }
                for t in self.turns
            ],
        }
        fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{self.id}.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(json.dumps(payload, indent=2, default=str))
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_name, path)
        except Exception:
            try:
                Path(tmp_name).unlink()
            except OSError:
                pass
            raise
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
                reasoning=str(tl.get("reasoning", "")),
            )
            for tl in (t.get("tools") or [])
        ]
        out.append(Turn(
            at=float(t.get("at", 0)),
            user=str(t.get("user", "")),
            tools=tools,
            assistant=str(t.get("assistant", "")),
            reasoning=str(t.get("reasoning", "")),
            reasoned_s=float(t.get("reasoned_s", 0)),
            attachments=list(t.get("attachments") or []),
            output_attachments=list(t.get("output_attachments") or []),
        ))
    return out


# tools aren't replayed into the prompt, so they don't make a turn replayable.
def turn_replayable(t: Turn | dict[str, Any]) -> bool:
    if isinstance(t, dict):
        return bool(t.get("assistant") or t.get("output_attachments"))
    return bool(getattr(t, "assistant", "") or getattr(t, "output_attachments", None))


def truncate_result(raw: str) -> str:
    """Apply the standard cap to a tool output before storing it."""
    text = (raw or "").strip()
    if len(text) <= TOOL_RESULT_CAP:
        return text
    return text[:TOOL_RESULT_CAP - 1] + "…"
