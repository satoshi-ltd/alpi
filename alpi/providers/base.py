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
    model_prefix: str = ""  # head of qualified model ids when it differs from ``name`` (Google → "gemini")
    description: str = ""

    def has_key(self, env: dict[str, str] | None = None) -> bool:
        """``env`` overrides ``os.environ`` so the daemon can probe a specific profile's .env without leaking the process-global env across profiles. Callers that already have a profile env map (e.g. from ``home.effective_profile_env``) should pass it explicitly."""
        import os
        src = env if env is not None else os.environ
        return bool(self.api_key_env) and bool(src.get(self.api_key_env))

    @abc.abstractmethod
    def list_models(self) -> list[ModelInfo]: ...
