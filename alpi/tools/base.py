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

    def to_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "output": self.output, "error": self.error}


class Tool(abc.ABC):
    name: ClassVar[str]
    description: ClassVar[str]
    parameters: ClassVar[dict[str, Any]] = {"type": "object", "properties": {}}

    @abc.abstractmethod
    def run(self, **kwargs: Any) -> ToolResult: ...

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
