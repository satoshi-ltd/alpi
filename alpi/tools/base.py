"""Tool base class + JSON-schema helpers."""

from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Any, ClassVar


@dataclass
class ToolResult:
    ok: bool
    output: str
    error: str | None = None
    transient: bool = False

    def to_dict(self) -> dict[str, Any]:
        out = {"ok": self.ok, "output": self.output, "error": self.error}
        if self.transient:
            out["transient"] = True
        return out


# Every consumer that relays a failed tool to a model must use this: the output often carries the diagnosis (skill runners print their fail() JSON to stdout), and dropping it forces the model to debug blind. Callers cap size afterwards via their budget.
def failure_payload(result: "ToolResult") -> str:
    if (result.output or "").strip():
        return f"ERROR: {result.error}\n{result.output}"
    return f"ERROR: {result.error}"


class Tool(abc.ABC):
    name: ClassVar[str]
    description: ClassVar[str]
    parameters: ClassVar[dict[str, Any]] = {"type": "object", "properties": {}}
    parallel_safe: ClassVar[bool] = False

    @abc.abstractmethod
    def run(self, **kwargs: Any) -> ToolResult: ...

    @classmethod
    def is_parallel_safe(cls, arguments: dict[str, Any]) -> bool:
        return cls.parallel_safe

    @classmethod
    def schema(cls) -> dict[str, Any]:
        """OpenAI/Anthropic tool-calling schema (litellm accepts this format)."""
        return {
            "type": "function",
            "function": {
                "name": cls.name,
                "description": cls.description,
                "parameters": cls.parameters,
            },
        }

    @classmethod
    def check(cls) -> tuple[bool, str]:
        """TL.1 — fast availability probe. ``(True, "")`` = ready; ``(False, reason)`` hides the tool from the LLM schema and flags it in ``alpi doctor``. Override on tools whose optional runtime deps may be missing on a minimal install. Never install anything; the runtime implementation is the final authority."""
        return True, ""
