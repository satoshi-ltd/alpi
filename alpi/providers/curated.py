"""Shared curated model catalog (read by Python + the desktop Rust crate)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml


@lru_cache(maxsize=1)
def _load_all() -> dict[str, list[dict]]:
    path = Path(__file__).with_name("curated_models.yaml")
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return {k: list(v or []) for k, v in data.items()}


def load_curated(provider: str) -> list[dict]:
    return list(_load_all().get(provider, []))
