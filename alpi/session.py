"""Session state — turns-based storage."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# Per-tool log stored under each Turn. Short, human-friendly, JSON-safe.
# We deliberately keep ``result`` capped so search snippets stay tight.
TOOL_RESULT_CAP = 400
SESSION_SCHEMA_VERSION = 2
USER_CAP = 64 * 1024
ASSISTANT_CAP = 64 * 1024
TURN_REASONING_CAP = 16 * 1024
TOOL_REASONING_CAP = 8 * 1024
TOOL_ARGS_CAP = 16 * 1024


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
    # Subdirectory under ``home`` where ``save()`` lands.
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
        from alpi._redact import redact
        payload = {
            "schema_version": SESSION_SCHEMA_VERSION,
            "id": self.id,
            "model": self.model,
            "started_at": self.started_at,
            "elapsed": self.elapsed,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": self.cost_usd,
            "last_ctx_tokens": self.last_ctx_tokens,
            "turns": [
                _serialize_turn_v2(t, redact=redact) for t in self.turns
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


def _serialize_turn_v2(t: Turn, *, redact) -> dict[str, Any]:  # noqa: ANN001
    user_meta = _compact_text(redact(t.user), USER_CAP)
    assistant_meta = _compact_text(redact(t.assistant), ASSISTANT_CAP)
    row: dict[str, Any] = {
        "at": t.at,
        "user": user_meta["preview"],
        "assistant": assistant_meta["preview"],
        "tools": [_serialize_tool_v2(tl, redact=redact) for tl in t.tools],
    }
    if user_meta["truncated"]:
        row["user_meta"] = _meta_without_preview(user_meta)
    if assistant_meta["truncated"]:
        row["assistant_meta"] = _meta_without_preview(assistant_meta)
    if t.reasoning:
        row["reasoning"] = _compact_text(redact(t.reasoning), TURN_REASONING_CAP)
    if t.reasoned_s:
        row["reasoned_s"] = round(t.reasoned_s, 1)
    if t.attachments:
        row["attachments"] = redact(t.attachments)
    if t.output_attachments:
        row["output_attachments"] = redact(t.output_attachments)
    return row


def _serialize_tool_v2(tl: ToolLog, *, redact) -> dict[str, Any]:  # noqa: ANN001
    row: dict[str, Any] = {
        "at": tl.at,
        "name": tl.name,
        "status": "ok" if tl.ok else "failed",
        "ok": tl.ok,
        "duration_s": round(tl.duration_s, 3),
        "args": _compact_json(redact(tl.args), TOOL_ARGS_CAP),
        "result": redact(tl.result),
    }
    if tl.reasoning:
        row["reasoning"] = _compact_text(redact(tl.reasoning), TOOL_REASONING_CAP)
    return row


def _compact_json(value: Any, cap: int) -> dict[str, Any]:
    try:
        text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    except Exception:  # noqa: BLE001
        text = str(value)
    return _compact_text(text, cap)


def _compact_text(value: Any, cap: int) -> dict[str, Any]:
    text = "" if value is None else str(value)
    raw = text.encode("utf-8", errors="replace")
    preview, truncated = _clip_utf8(raw, cap)
    return {
        "preview": preview,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "truncated": truncated,
    }


def _clip_utf8(raw: bytes, cap: int) -> tuple[str, bool]:
    if len(raw) <= cap:
        return raw.decode("utf-8", errors="replace"), False
    suffix = "…".encode("utf-8")
    head = raw[: max(0, cap - len(suffix))]
    return head.decode("utf-8", errors="ignore") + "…", True


def _meta_without_preview(obj: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in obj.items() if k != "preview"}


def _preview(value: Any) -> str:
    if _is_compact_field(value):
        return str(value.get("preview") or "")
    return str(value or "")


def _field_meta(value: Any) -> dict[str, Any] | None:
    if _is_compact_field(value):
        return _meta_without_preview(value)
    return None


def _args_from_serialized(value: Any) -> dict[str, Any]:
    if _is_compact_field(value):
        preview = str(value.get("preview") or "")
        try:
            parsed = json.loads(preview)
            if isinstance(parsed, dict):
                return parsed
        except Exception:  # noqa: BLE001
            pass
        return {"preview": preview} if preview else {}
    if isinstance(value, dict):
        return value
    return {}


def _is_compact_field(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and isinstance(value.get("preview"), str)
        and isinstance(value.get("bytes"), int)
        and isinstance(value.get("sha256"), str)
        and isinstance(value.get("truncated"), bool)
    )


def normalize_payload(data: dict[str, Any]) -> dict[str, Any]:
    out = dict(data)
    turns: list[dict[str, Any]] = []
    for t in data.get("turns") or []:
        if not isinstance(t, dict):
            continue
        row = dict(t)
        row["reasoning"] = _preview(t.get("reasoning"))
        meta = _field_meta(t.get("reasoning"))
        if meta:
            row["reasoning_meta"] = meta
        row["tools"] = [_normalize_tool_payload(tl) for tl in (t.get("tools") or []) if isinstance(tl, dict)]
        turns.append(row)
    out["turns"] = turns
    return out


def _normalize_tool_payload(tl: dict[str, Any]) -> dict[str, Any]:
    row = dict(tl)
    row["args"] = _args_from_serialized(tl.get("args"))
    row["result"] = _preview(tl.get("result"))
    row["output"] = row.get("output") or row["result"]
    row["reasoning"] = _preview(tl.get("reasoning"))
    for key in ("args", "result", "reasoning"):
        meta = _field_meta(tl.get(key))
        if meta:
            row[f"{key}_meta"] = meta
    row.setdefault("status", "ok" if row.get("ok", True) else "failed")
    return row


def load_turns(data: dict[str, Any]) -> list[Turn]:
    """Parse the turns list from a serialized session payload."""
    out: list[Turn] = []
    for t in data.get("turns", []):
        tools = [
            ToolLog(
                at=float(tl.get("at", 0)),
                name=str(tl.get("name", "")),
                args=_args_from_serialized(tl.get("args")),
                result=_preview(tl.get("result")),
                ok=bool(tl.get("ok", True)),
                duration_s=float(tl.get("duration_s", 0)),
                reasoning=_preview(tl.get("reasoning")),
            )
            for tl in (t.get("tools") or [])
        ]
        out.append(Turn(
            at=float(t.get("at", 0)),
            user=str(t.get("user", "")),
            tools=tools,
            assistant=str(t.get("assistant", "")),
            reasoning=_preview(t.get("reasoning")),
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
