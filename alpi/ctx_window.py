"""Shared context-window resolver. The TUI status bar, the desktop
header, and any future surface all need the same answer for "how
many tokens does this model accept", so the logic lives here.

Three sources, in order:
  1. Ollama provider registered in `providers.ollama` — query the
     daemon at runtime (`resolve_num_ctx`).
  2. ``litellm.model_cost`` lookup for paid APIs.
  3. Fallback ``200_000`` (matches the Claude default).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


_FALLBACK = 200_000


def resolve(home: Path, cfg: Any, model: str) -> int:
    """Resolve the context window in tokens. ``cfg`` is the loaded
    profile config (needs ``cfg.providers``). ``home`` is unused
    today but reserved for future per-profile model overrides."""
    if not model:
        return _FALLBACK
    head, _, rest = model.partition("/")
    providers = getattr(cfg, "providers", {}) or {}
    for entry in providers.get("ollama", []) or []:
        if entry.get("name") == head:
            from alpi.providers.ollama import resolve_num_ctx

            return resolve_num_ctx(entry.get("url", ""), rest)
    try:
        import litellm

        for key in (model, rest, f"{head}/{rest}"):
            info = litellm.model_cost.get(key)
            if info and info.get("max_input_tokens"):
                return int(info["max_input_tokens"])
    except Exception:  # noqa: BLE001
        pass
    return _FALLBACK
