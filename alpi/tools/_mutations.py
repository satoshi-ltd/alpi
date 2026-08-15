"""CF.2 — per-turn file mutation recorder, drained by the engine after each tool batch."""

from __future__ import annotations

import contextvars
import difflib
import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


DIFF_PREVIEW_MAX_CHARS = 400


@dataclass(frozen=True)
class MutationRecord:
    path: str
    op: str  # "create" | "write" | "edit" | "delete"
    sha_before: str | None
    sha_after: str | None
    bytes_before: int
    bytes_after: int
    lines_before: int
    lines_after: int
    diff_preview: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ContextVar (not a global) so parallel turns in the same daemon process don't see each other's pending mutations.
_buffer: contextvars.ContextVar[list[MutationRecord] | None] = contextvars.ContextVar(
    "alpi_mutations_buffer", default=None,
)


def begin_batch() -> object:
    return _buffer.set([])


def end_batch(token: object) -> list[MutationRecord]:
    drained = _buffer.get() or []
    _buffer.reset(token)
    return list(drained)


def record_mutation(rec: MutationRecord) -> None:
    # No-op when no batch is active — standalone tool calls (tests, REPL) must not crash.
    buf = _buffer.get()
    if buf is None:
        return
    buf.append(rec)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _line_count(text: str) -> int:
    if not text:
        return 0
    return text.count("\n") + (0 if text.endswith("\n") else 1)


def _diff_preview(path: Path, before: str | None, after: str | None) -> str:
    before_lines = (before or "").splitlines(keepends=True)
    after_lines = (after or "").splitlines(keepends=True)
    diff = difflib.unified_diff(
        before_lines, after_lines,
        fromfile=str(path), tofile=str(path),
        n=2,
    )
    text = "".join(diff)
    if len(text) > DIFF_PREVIEW_MAX_CHARS:
        text = text[:DIFF_PREVIEW_MAX_CHARS] + "…[truncated]"
    return text


def build_record(
    path: Path, before: str | None, after: str | None, *, op_hint: str | None = None,
) -> MutationRecord:
    if op_hint is not None:
        op = op_hint
    elif before is None:
        op = "create"
    else:
        op = "write"
    sha_before = _sha256(before) if before is not None else None
    sha_after = _sha256(after) if after is not None else None
    return MutationRecord(
        path=str(path),
        op=op,
        sha_before=sha_before,
        sha_after=sha_after,
        bytes_before=len((before or "").encode("utf-8")),
        bytes_after=len((after or "").encode("utf-8")),
        lines_before=_line_count(before or ""),
        lines_after=_line_count(after or ""),
        diff_preview=_diff_preview(path, before, after),
    )


def format_footer(records: list[MutationRecord]) -> str:
    if not records:
        return ""
    lines = ["[file_mutations] (committed by the last tool batch)"]
    for i, r in enumerate(records, 1):
        sha_short = r.sha_after[:8] if r.sha_after else "deleted"
        lines.append(
            f"  {i}. {r.op:<6} {r.path}  sha={sha_short}  "
            f"bytes {r.bytes_before}→{r.bytes_after}  "
            f"lines {r.lines_before}→{r.lines_after}"
        )
    return "\n".join(lines)


__all__ = [
    "MutationRecord",
    "DIFF_PREVIEW_MAX_CHARS",
    "begin_batch",
    "end_batch",
    "record_mutation",
    "build_record",
    "format_footer",
]
