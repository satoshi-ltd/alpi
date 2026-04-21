"""Provider metadata — used by the model selector only."""

from __future__ import annotations

import abc
from dataclasses import dataclass


@dataclass
class ModelInfo:
    """One model row for the picker."""
    id: str           # full litellm id, e.g. "anthropic/claude-sonnet-4-6"
    display: str      # short label, e.g. "claude-sonnet-4-6"
    note: str = ""    # optional free-form suffix (pricing, tag, etc.)


class Provider(abc.ABC):
    name: str          # internal id, e.g. "anthropic"
    display: str       # human label, e.g. "Anthropic"
    api_key_env: str   # "" if none
    description: str = ""

    def has_key(self) -> bool:
        import os
        return bool(self.api_key_env) and bool(os.environ.get(self.api_key_env))

    @abc.abstractmethod
    def list_models(self) -> list[ModelInfo]: ...
