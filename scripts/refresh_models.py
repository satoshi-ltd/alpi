#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path

import httpx
import yaml

URL = "https://openrouter.ai/api/v1/models"
LITELLM_URL = "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"
PROVIDERS = Path(__file__).resolve().parent.parent / "alpi" / "providers"
OUT = PROVIDERS / "openrouter_models.yaml"
NATIVE_OUT = PROVIDERS / "native_models.yaml"
CURATED = PROVIDERS / "curated_models.yaml"
NATIVE_PROVIDERS = ("openai", "anthropic")
CURATED_PREFIX = {"openai": "", "anthropic": "", "google": "gemini/", "groq": "groq/"}
_DATED_SNAPSHOT = re.compile(r"-\d{4}-\d{2}-\d{2}$|-\d{8}$")
_OUTPUT_RESERVE = 32_768
_MAX_RESERVE_FRACTION = 4  # the reply margin never exceeds a quarter of the window


def safe_input_limit(model: dict) -> int | None:
    tp = model.get("top_provider") or {}
    ctx = tp.get("context_length") or model.get("context_length")
    try:
        ctx = int(ctx)
    except (TypeError, ValueError):
        return None
    if ctx <= 0:
        return None
    try:
        mc = int(tp.get("max_completion_tokens") or 0)
    except (TypeError, ValueError):
        mc = 0
    # Reserve a reply margin that is never the provider's theoretical max output and never
    # eats the window: a 4K model advertising 3.6K of output would otherwise leave 400 tokens
    # of input and send every short chat straight into compaction.
    reserve = min(_OUTPUT_RESERVE, ctx // _MAX_RESERVE_FRACTION)
    if mc > 0:
        reserve = min(reserve, mc)
    limit = ctx - reserve
    return limit if limit > 0 else ctx


def build(models: list[dict]) -> dict[str, int]:
    out: dict[str, int] = {}
    for m in models:
        mid = m.get("id")
        if not mid:
            continue
        limit = safe_input_limit(m)
        if limit is None:
            continue
        out[str(mid)] = limit
    return dict(sorted(out.items()))


def write_atomic(path: Path, text: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-", suffix=".yaml")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def curated_native_ids(curated: dict) -> list[str]:
    return [f"{prefix}{entry['id']}" for provider, prefix in CURATED_PREFIX.items() for entry in (curated.get(provider) or []) if entry.get("id")]


def bundled_ids() -> set[str]:
    from importlib.resources import files

    try:
        return set(json.loads(files("litellm").joinpath("model_prices_and_context_window_backup.json").read_text()))
    except Exception:  # noqa: BLE001
        return set()


def native_chat_ids(prices: dict) -> list[str]:
    return sorted(
        k for k, v in prices.items()
        if isinstance(v, dict) and v.get("litellm_provider") in NATIVE_PROVIDERS
        and v.get("mode") == "chat" and "/" not in k and ":" not in k
    )


def build_native(prices: dict, curated: list[str], bundled: set[str]) -> tuple[dict[str, dict], list[str]]:
    wanted = list(dict.fromkeys([*curated, *(k for k in native_chat_ids(prices) if k not in bundled and not _DATED_SNAPSHOT.search(k))]))
    out: dict[str, dict] = {}
    missing: list[str] = []
    for mid in wanted:
        info = prices.get(mid)
        if not isinstance(info, dict) or not info.get("max_input_tokens") or not info.get("input_cost_per_token"):
            if mid in curated:
                missing.append(mid)
            continue
        out[mid] = dict(info)
    return out, missing


def uncurated_chat_models(prices: dict, curated: list[str]) -> dict[str, list[str]]:
    known = set(curated)
    grouped: dict[str, list[str]] = {}
    for k in native_chat_ids(prices):
        if k in known or _DATED_SNAPSHOT.search(k):
            continue
        grouped.setdefault(prices[k]["litellm_provider"], []).append(k)
    return grouped


def refresh_native() -> int:
    try:
        r = httpx.get(LITELLM_URL, timeout=30)
        r.raise_for_status()
        prices = r.json()
    except Exception as e:  # noqa: BLE001
        print(f"native refresh aborted, kept existing catalog: {e}", file=sys.stderr)
        return 1
    curated = curated_native_ids(yaml.safe_load(CURATED.read_text(encoding="utf-8")) or {})
    native, missing = build_native(prices, curated, bundled_ids())
    if missing:
        print(f"native refresh aborted: no window or price for curated {missing}", file=sys.stderr)
        return 1
    write_atomic(NATIVE_OUT, yaml.safe_dump(native, sort_keys=True, allow_unicode=True))
    print(f"wrote {len(native)} models -> {NATIVE_OUT.name}")
    for provider, ids in uncurated_chat_models(prices, curated).items():
        print(f"{provider}: {len(ids)} chat models not curated (review for curated_models.yaml): {', '.join(ids)}")
    return 0


def main() -> int:
    native_code = refresh_native()
    try:
        r = httpx.get(URL, timeout=30)
        r.raise_for_status()
        models = r.json().get("data", []) or []
    except Exception as e:  # noqa: BLE001
        print(f"refresh aborted, kept existing catalog: {e}", file=sys.stderr)
        return 1
    catalog = build(models)
    if not catalog:
        print("refresh aborted: no valid models", file=sys.stderr)
        return 1
    write_atomic(OUT, yaml.safe_dump(catalog, sort_keys=True, allow_unicode=True))
    print(f"wrote {len(catalog)} models -> {OUT.name}")
    return native_code


if __name__ == "__main__":
    sys.exit(main())
