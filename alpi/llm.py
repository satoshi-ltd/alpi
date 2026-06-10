"""Thin wrapper over litellm."""

from __future__ import annotations

import queue
import random
import threading
import time
from dataclasses import dataclass
from typing import Any

# RT.1 provider stale-call hardening — defaults, overridable via cfg.runtime.
DEFAULT_FIRST_BYTE_TIMEOUT_S = 300.0
DEFAULT_STREAM_IDLE_TIMEOUT_S = 120.0
DEFAULT_MAX_RETRIES = 2
DEFAULT_RETRY_BACKOFF_S = 1.5

# litellm exception class names that mean "the request produced nothing usable — retry".
_TRANSIENT_EXC_NAMES = frozenset({
    "Timeout", "APITimeoutError", "APIConnectionError", "APIError",
    "RateLimitError", "ServiceUnavailableError", "InternalServerError",
})


class ProviderStalled(RuntimeError):
    pass


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


def _with_openrouter_extras(kwargs: dict[str, Any], model: str) -> dict[str, Any]:
    if not str(model).startswith("openrouter/"):
        return kwargs
    from alpi import __version__
    from alpi.providers.reasoning import merge_into_kwargs
    # App attribution headers — without them OpenRouter's dashboard credits the traffic to litellm.
    headers = dict(kwargs.get("extra_headers") or {})
    headers.setdefault("HTTP-Referer", "https://alpi.satoshi.ltd")
    headers.setdefault("X-Title", f"alpi/{__version__}")
    out = merge_into_kwargs(kwargs, {"extra_body": {"usage": {"include": True}}})
    out["extra_headers"] = headers
    return out


_OR_PRICING: "dict[str, tuple[float, float]] | None" = None
_OR_PRICING_RETRY_AT: float = 0.0


# Best-effort: fetched at most once per process (cached in _OR_PRICING). A 2s
# timeout caps the worst case; a failed fetch backs off for 5 min so per-turn
# free-model classification can't hammer a down /models on every turn.
def _openrouter_pricing() -> "dict[str, tuple[float, float]]":
    global _OR_PRICING, _OR_PRICING_RETRY_AT
    if _OR_PRICING is not None:
        return _OR_PRICING
    import time as _time
    if _time.time() < _OR_PRICING_RETRY_AT:
        return {}
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
        _OR_PRICING_RETRY_AT = _time.time() + 300.0
        return {}


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


def is_free_model(model: str) -> bool:
    m = str(model or "")
    if m.startswith("openrouter/"):
        price = _openrouter_pricing().get(m.split("/", 1)[1])
        return price is not None and price[0] == 0.0 and price[1] == 0.0
    return False


def _is_transient(exc: Exception) -> bool:
    if isinstance(exc, ProviderStalled):
        return True
    name = type(exc).__name__
    code = getattr(exc, "status_code", None)
    # A 4xx (bad request / auth / not-found) is permanent; 429 is the rate-limit exception.
    if name == "APIError" and isinstance(code, int) and 400 <= code < 500 and code != 429:
        return False
    if name in _TRANSIENT_EXC_NAMES:
        return True
    return isinstance(code, int) and (code == 429 or code >= 500)


def _backoff_sleep(base: float, attempt: int) -> None:
    time.sleep(base * (2 ** (attempt - 1)) * random.uniform(0.8, 1.2))


def _completion_silenced(kwargs: dict[str, Any]):
    # FD-level silence only while litellm resolves the provider (the banner escapes sys.stdout).
    import os
    import litellm
    save_out, save_err = os.dup(1), os.dup(2)
    devnull = os.open(os.devnull, os.O_WRONLY)
    os.dup2(devnull, 1)
    os.dup2(devnull, 2)
    try:
        return litellm.completion(**kwargs)
    finally:
        os.dup2(save_out, 1)
        os.dup2(save_err, 2)
        for fd in (save_out, save_err, devnull):
            os.close(fd)


def _iter_with_watchdog(stream_iter, first_byte_timeout: float, idle_timeout: float):
    # Pump the blocking provider iterator on a worker thread; the main thread reads
    # with per-chunk deadlines so a provider that accepts then goes silent can't hang the turn.
    q: queue.Queue = queue.Queue()

    def _pump():
        try:
            for chunk in stream_iter:
                q.put(("chunk", chunk))
            q.put(("done", None))
        except Exception as exc:  # noqa: BLE001
            q.put(("error", exc))

    threading.Thread(target=_pump, daemon=True).start()
    first = True
    while True:
        timeout = first_byte_timeout if first else idle_timeout
        try:
            if timeout and timeout > 0:
                kind, payload = q.get(timeout=timeout)
            else:
                kind, payload = q.get()
        except queue.Empty:
            raise ProviderStalled(
                f"provider sent no {'first token' if first else 'further output'} "
                f"within {timeout:.0f}s"
            ) from None
        first = False
        if kind == "done":
            return
        if kind == "error":
            raise payload
        yield payload


def _normalize_chunk(chunk, tool_calls_accum: dict) -> dict | None:
    if not getattr(chunk, "choices", None):
        return None
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
            entry = tool_calls_accum.setdefault(idx, {"id": "", "name": "", "arguments": ""})
            if getattr(tc, "id", None):
                entry["id"] = tc.id
            fn = getattr(tc, "function", None)
            if fn is not None:
                if getattr(fn, "name", None):
                    entry["name"] += fn.name
                if getattr(fn, "arguments", None):
                    entry["arguments"] += fn.arguments
            tc_deltas.append(entry)
    return {
        "text_delta": text_delta,
        "reasoning_delta": reasoning_delta,
        "tool_calls_delta": tc_deltas,
        "finish_reason": getattr(choice, "finish_reason", None),
    }


def _final_chunk(last_chunk, tool_calls_accum: dict, model: str) -> dict:
    usage = getattr(last_chunk, "usage", None) if last_chunk else None
    cost = _compute_cost(last_chunk, model)
    final_tool_calls = [
        {"id": v["id"], "name": v["name"], "arguments": v["arguments"]}
        for _, v in sorted(tool_calls_accum.items())
    ]
    return {
        "final": True,
        "tool_calls": final_tool_calls,
        "input_tokens": getattr(usage, "prompt_tokens", 0) if usage else 0,
        "output_tokens": getattr(usage, "completion_tokens", 0) if usage else 0,
        "cost_usd": float(cost),
    }


def stream(
    model: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    api_base: str | None = None,
    api_key: str | None = None,
    rt: Any = None,
    **extra: Any,
):
    """Yield streaming chunks, with first-byte / idle watchdogs and jittered retries (RT.1)."""
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    kwargs = _with_openrouter_extras(kwargs, model)
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

    first_byte = float(getattr(rt, "first_byte_timeout_s", DEFAULT_FIRST_BYTE_TIMEOUT_S))
    idle = float(getattr(rt, "stream_idle_timeout_s", DEFAULT_STREAM_IDLE_TIMEOUT_S))
    max_retries = int(getattr(rt, "max_retries", DEFAULT_MAX_RETRIES))
    backoff = float(getattr(rt, "retry_backoff_s", DEFAULT_RETRY_BACKOFF_S))
    if first_byte > 0:
        kwargs.setdefault("timeout", first_byte)  # litellm HTTP backstop for connect stalls

    attempt = 0
    while True:
        produced = False
        tool_calls_accum: dict[int, dict[str, str]] = {}
        last_chunk = None
        try:
            stream_iter = _completion_silenced(kwargs)
            for chunk in _iter_with_watchdog(stream_iter, first_byte, idle):
                last_chunk = chunk
                norm = _normalize_chunk(chunk, tool_calls_accum)
                if norm is None:
                    continue
                produced = True
                yield norm
            yield _final_chunk(last_chunk, tool_calls_accum, model)
            return
        except Exception as exc:  # noqa: BLE001
            # Retry only before any output reached the consumer — a partially-streamed
            # turn can't be safely replayed; surface it instead.
            if not produced and _is_transient(exc) and attempt < max_retries:
                attempt += 1
                _backoff_sleep(backoff, attempt)
                continue
            raise


def complete(
    model: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    api_base: str | None = None,
    api_key: str | None = None,
    **extra: Any,
) -> Completion:
    """Call the LLM and return a normalized Completion."""
    import litellm

    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
    }
    kwargs = _with_openrouter_extras(kwargs, model)
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
