from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


@lru_cache(maxsize=1)
def catalogue() -> dict[str, dict[str, Any]]:
    path = Path(__file__).with_name("native_models.yaml")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    return {str(k): dict(v) for k, v in data.items() if isinstance(v, dict)}


def register(litellm: Any) -> list[str]:
    known = getattr(litellm, "model_cost", None) or {}
    missing = {mid: info for mid, info in catalogue().items() if mid not in known}
    if missing:
        litellm.register_model(missing)
    return sorted(missing)
