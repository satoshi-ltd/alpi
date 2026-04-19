"""Tool base class + JSON-schema helpers.

Every tool is a subclass of ``Tool`` living in its own module under
``alf/tools/``. A tool declares:
- ``name``: snake_case identifier (used by the LLM)
- ``description``: one-line what it does (shown to the LLM)
- ``parameters``: JSON schema for its arguments
- ``run(**kwargs)``: the actual implementation

Registration is automatic: every Tool subclass imported via
``alf.tools`` is picked up by the registry.
"""

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
