from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

_FALLBACK = 200_000
_CATALOG_PATH = Path(__file__).parent / "providers" / "openrouter_models.yaml"
# Same model behind each of these — a provider preference, or the web-search plugin — so
# the base row's window still holds. Real variants (`:free`, `:batch`) have rows of their own.
_SAME_WINDOW_SUFFIXES = frozenset({"nitro", "floor", "online", "exacto"})


@lru_cache(maxsize=1)
def _openrouter_limits() -> dict[str, int]:
    import yaml

    try:
        data = yaml.safe_load(_CATALOG_PATH.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, int] = {}
    for key, val in data.items():
        try:
            out[str(key)] = int(val)
        except (TypeError, ValueError):
            continue
    return out


def _from_openrouter(model: str) -> int | None:
    candidates = [model]
    if model.startswith("openrouter/"):
        candidates.append(model.split("/", 1)[1])
    limits = _openrouter_limits()
    for c in candidates:
        if c in limits:
            return limits[c]
    return None


def _from_litellm(model: str) -> int | None:
    try:
        import litellm
    except Exception:  # noqa: BLE001
        return None
    head, _, rest = model.partition("/")
    cost = getattr(litellm, "model_cost", None) or {}
    for key in (model, rest, f"{head}/{rest}"):
        info = cost.get(key)
        if info and info.get("max_input_tokens"):
            return int(info["max_input_tokens"])
    if head == "openrouter":  # get_model_info can't map openrouter-namespaced ids
        return None
    try:
        gi = litellm.get_model_info(model)
        val = gi.get("max_input_tokens") or gi.get("max_tokens")
        if val:
            return int(val)
    except Exception:  # noqa: BLE001
        pass
    return None


def _without_same_window_suffix(model: str) -> str | None:
    base, sep, suffix = model.rpartition(":")
    return base if sep and suffix in _SAME_WINDOW_SUFFIXES else None


def _lookup(model: str) -> int | None:
    head, _, _ = model.partition("/")
    val = _from_openrouter(model) if head == "openrouter" else None
    return val if val is not None else _from_litellm(model)


def resolve(home: Path, cfg: Any, model: str) -> int:
    if not model:
        return _FALLBACK
    head, _, rest = model.partition("/")
    providers = getattr(cfg, "providers", {}) or {}
    for entry in providers.get("ollama", []) or []:
        if entry.get("name") == head:
            from alpi.providers.ollama import resolve_num_ctx

            return resolve_num_ctx(entry.get("url", ""), rest)
    # Exact id first, so a suffix the catalog does carry answers for itself.
    val = _lookup(model)
    if val is None:
        base = _without_same_window_suffix(model)
        val = _lookup(base) if base else None
    return val or _FALLBACK
