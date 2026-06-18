#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import httpx
import yaml

URL = "https://openrouter.ai/api/v1/models"
OUT = Path(__file__).resolve().parent.parent / "alpi" / "providers" / "openrouter_models.yaml"
_OUTPUT_RESERVE = 32_768


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
    # reserve a modest reply margin, never the provider's theoretical max output
    reserve = min(_OUTPUT_RESERVE, mc) if mc > 0 else _OUTPUT_RESERVE
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


def main() -> int:
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
