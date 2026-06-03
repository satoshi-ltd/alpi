"""Thin wrapper over litellm."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Completion:
    content: str
    tool_calls: list[dict[str, Any]]
    input_tokens: int
    output_tokens: int
    cost_usd: float
    raw: Any


def _silence_litellm() -> None:
    import logging
    import os
    import warnings
    os.environ.setdefault("LITELLM_LOG", "ERROR")
    warnings.filterwarnings("ignore", module="litellm")

    # FD-level redirect while litellm initializes (its "Provider List" banner
    # escapes Python-level sys.stdout/stderr redirection).
    save_out, save_err = os.dup(1), os.dup(2)
    devnull = os.open(os.devnull, os.O_WRONLY)
    os.dup2(devnull, 1)
    os.dup2(devnull, 2)
    try:
        import litellm
        litellm.suppress_debug_info = True
        litellm.set_verbose = False
        # LiteLLM ships with ``telemetry = True`` by default, which phones
        # home to their backend. alpi's principle is no telemetry — flip
        # it off at import time so no request to our own providers ever
        # carries a side-effect call.
        litellm.telemetry = False
        # Warm the provider cache once so future calls don't emit banners.
        try:
            litellm.get_llm_provider("openrouter/dummy")
        except Exception:
            pass
    finally:
        os.dup2(save_out, 1)
        os.dup2(save_err, 2)
        for fd in (save_out, save_err, devnull):
            os.close(fd)

    for name in (
        "litellm", "LiteLLM", "litellm.utils", "litellm.main",
        "litellm.cost_calculator", "httpx", "openai",
    ):
        logging.getLogger(name).setLevel(logging.CRITICAL)


_silence_litellm()


DEBUG = bool(__import__("os").environ.get("ALPI_DEBUG"))


# Prefer the provider-reported cost. litellm.completion_cost() raises for models
# not in its pricing map (every new OpenRouter model), so without this alpi logs
# $0 for them. OpenRouter returns the real cost in usage.cost when usage.include
# is requested; litellm surfaces it as _hidden_params.response_cost.
def _reported_cost(resp) -> float | None:
    hp = getattr(resp, "_hidden_params", None) or {}
    rc = hp.get("response_cost")
    if rc is not None:
        return float(rc)
    u = getattr(resp, "usage", None)
    if u is not None:
        c = getattr(u, "cost", None)
        if c is None and hasattr(u, "model_dump"):
            c = (u.model_dump() or {}).get("cost")
        if c is not None:
            return float(c)
    return None


def _with_openrouter_usage(kwargs: dict[str, Any], model: str) -> dict[str, Any]:
    if not str(model).startswith("openrouter/"):
        return kwargs
    from alpi.providers.reasoning import merge_into_kwargs
    return merge_into_kwargs(kwargs, {"extra_body": {"usage": {"include": True}}})


_OR_PRICING: "dict[str, tuple[float, float]] | None" = None


# Best-effort: fetched at most once per process (cached in _OR_PRICING) and only
# when a turn produced no reported cost and litellm couldn't price the model. A
# 2s timeout caps the worst case; on any failure cost is just 0.0 for that turn.
def _openrouter_pricing() -> "dict[str, tuple[float, float]]":
    global _OR_PRICING
    if _OR_PRICING is not None:
        return _OR_PRICING
    import json as _json
    import os as _os
    import urllib.request as _u
    out: dict[str, tuple[float, float]] = {}
    try:
        key = _os.environ.get("OPENROUTER_API_KEY", "")
        headers = {"Authorization": f"Bearer {key}"} if key else {}
        req = _u.Request("https://openrouter.ai/api/v1/models", headers=headers)
        with _u.urlopen(req, timeout=2) as resp:
            data = _json.load(resp)
        for m in data.get("data", []):
            p = m.get("pricing") or {}
            try:
                out[m["id"]] = (float(p.get("prompt", 0)), float(p.get("completion", 0)))
            except (TypeError, ValueError, KeyError):
                continue
        _OR_PRICING = out
        return out
    except Exception:  # noqa: BLE001
        return {}  # leave cache unset → retry on a later turn


# litellm prices the models in its catalog (most providers, incl. the OpenRouter
# models it already knows) — that path works in streaming and is why older
# OpenRouter models reported cost. Brand-new OpenRouter models aren't mapped yet,
# so fall back to OpenRouter's own published per-token pricing.
def _compute_cost(resp, model: str) -> float:
    c = _reported_cost(resp)
    if c is not None:
        return c
    import litellm
    try:
        c = litellm.completion_cost(completion_response=resp)
        if c is not None:
            return float(c or 0.0)
    except Exception:  # noqa: BLE001
        pass
    if str(model).startswith("openrouter/"):
        price = _openrouter_pricing().get(model.split("/", 1)[1])
        u = getattr(resp, "usage", None)
        if price and u is not None:
            pin = getattr(u, "prompt_tokens", 0) or 0
            pout = getattr(u, "completion_tokens", 0) or 0
            return pin * price[0] + pout * price[1]
    return 0.0


def stream(
    model: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    api_base: str | None = None,
    api_key: str | None = None,
    **extra: Any,
):
    """Yield streaming chunks from the LLM."""
    import os
    import litellm

    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    kwargs = _with_openrouter_usage(kwargs, model)
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
    if api_base:
        kwargs["api_base"] = api_base
        from alpi.providers.ollama import is_ollama, resolve_num_ctx
        if is_ollama(api_base):
            raw_model = model.split("/", 1)[1] if "/" in model else model
            kwargs["extra_body"] = {
                "options": {
                    "num_ctx": resolve_num_ctx(api_base, raw_model),
                },
            }
    if api_key:
        kwargs["api_key"] = api_key
    if extra:
        # Deep-merge so reasoning's extra_body coexists with Ollama's options.num_ctx.
        from alpi.providers.reasoning import merge_into_kwargs
        kwargs = merge_into_kwargs(kwargs, extra)

    # FD-level silence only while litellm resolves the provider (first chunk).
    save_out, save_err = os.dup(1), os.dup(2)
    devnull = os.open(os.devnull, os.O_WRONLY)
    os.dup2(devnull, 1)
    os.dup2(devnull, 2)
    try:
        stream_iter = litellm.completion(**kwargs)
    finally:
        os.dup2(save_out, 1)
        os.dup2(save_err, 2)
        for fd in (save_out, save_err, devnull):
            os.close(fd)

    # Accumulate tool_calls across chunks (they stream by index).
    tool_calls_accum: dict[int, dict[str, str]] = {}
    last_chunk = None

    for chunk in stream_iter:
        last_chunk = chunk
        if not getattr(chunk, "choices", None):
            continue
        choice = chunk.choices[0]
        delta = getattr(choice, "delta", None)
        text_delta = ""
        reasoning_delta = ""
        tc_deltas = []
        if delta is not None:
            text_delta = getattr(delta, "content", "") or ""
            reasoning_delta = (
                getattr(delta, "reasoning_content", None)
                or getattr(delta, "reasoning", None)
                or ""
            )
            raw_tcs = getattr(delta, "tool_calls", None) or []
            for tc in raw_tcs:
                idx = getattr(tc, "index", 0) or 0
                entry = tool_calls_accum.setdefault(
                    idx, {"id": "", "name": "", "arguments": ""}
                )
                if getattr(tc, "id", None):
                    entry["id"] = tc.id
                fn = getattr(tc, "function", None)
                if fn is not None:
                    if getattr(fn, "name", None):
                        entry["name"] += fn.name
                    if getattr(fn, "arguments", None):
                        entry["arguments"] += fn.arguments
                tc_deltas.append(entry)
        yield {
            "text_delta": text_delta,
            "reasoning_delta": reasoning_delta,
            "tool_calls_delta": tc_deltas,
            "finish_reason": getattr(choice, "finish_reason", None),
        }

    # Final tool calls + usage (on the last chunk)
    usage = getattr(last_chunk, "usage", None) if last_chunk else None
    cost = _compute_cost(last_chunk, model)

    final_tool_calls = [
        {"id": v["id"], "name": v["name"], "arguments": v["arguments"]}
        for _, v in sorted(tool_calls_accum.items())
    ]

    yield {
        "final": True,
        "tool_calls": final_tool_calls,
        "input_tokens": getattr(usage, "prompt_tokens", 0) if usage else 0,
        "output_tokens": getattr(usage, "completion_tokens", 0) if usage else 0,
        "cost_usd": float(cost),
    }


def complete(
    model: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    api_base: str | None = None,
    api_key: str | None = None,
    **extra: Any,
) -> Completion:
    """Call the LLM and return a normalized Completion."""
    import os
    import litellm

    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
    }
    kwargs = _with_openrouter_usage(kwargs, model)
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
    if api_base:
        kwargs["api_base"] = api_base
    if api_key:
        kwargs["api_key"] = api_key
    if extra:
        from alpi.providers.reasoning import merge_into_kwargs
        kwargs = merge_into_kwargs(kwargs, extra)

    # Don't redirect FDs here — _silence_litellm() at import time warmed up
    # the provider cache, so no more "Provider List" banners. Redirecting
    # during the call would starve Textual's render pipeline of stdout and
    # freeze the UI for the duration of the call.
    response = litellm.completion(**kwargs)

    if DEBUG:
        import sys
        print(f"[alpi.llm] finish_reason={response.choices[0].finish_reason!r}",
              file=sys.stderr)
        print(f"[alpi.llm] raw choice={response.choices[0].message}", file=sys.stderr)
    choice = response.choices[0].message
    usage = getattr(response, "usage", None)

    cost = _compute_cost(response, model)

    raw_calls = getattr(choice, "tool_calls", None) or []
    tool_calls = [
        {
            "id": tc.id,
            "name": tc.function.name,
            "arguments": tc.function.arguments,
        }
        for tc in raw_calls
    ]

    return Completion(
        content=choice.content or "",
        tool_calls=tool_calls,
        input_tokens=getattr(usage, "prompt_tokens", 0) if usage else 0,
        output_tokens=getattr(usage, "completion_tokens", 0) if usage else 0,
        cost_usd=float(cost),
        raw=response,
    )
