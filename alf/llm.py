"""Thin wrapper over litellm.

Keeps provider choice (Anthropic, OpenAI, OpenRouter, Ollama) out of the rest
of the codebase. Model strings use litellm conventions:
    anthropic/claude-sonnet-4-6
    openai/gpt-4o
    openrouter/anthropic/claude-sonnet-4-5
    ollama/llama3.1
"""

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
    """Litellm prints init messages via raw FDs — silence at the fd level."""
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


DEBUG = bool(__import__("os").environ.get("ALF_DEBUG"))


def stream(
    model: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    api_base: str | None = None,
    api_key: str | None = None,
):
    """Yield streaming chunks. Each yield is a dict with:

    - ``text_delta``: str (may be "")
    - ``tool_calls_delta``: list of partial tool calls being built up
    - ``usage``: Completion-like tokens/cost info (only on final chunk)
    - ``finish_reason``: str | None (only on final chunk with real value)
    """
    import os
    import litellm

    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
    if api_base:
        kwargs["api_base"] = api_base
    if api_key:
        kwargs["api_key"] = api_key

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
        tc_deltas = []
        if delta is not None:
            text_delta = getattr(delta, "content", "") or ""
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
            "tool_calls_delta": tc_deltas,
            "finish_reason": getattr(choice, "finish_reason", None),
        }

    # Final tool calls + usage (on the last chunk)
    usage = getattr(last_chunk, "usage", None) if last_chunk else None
    try:
        cost = litellm.completion_cost(completion_response=last_chunk) or 0.0
    except Exception:
        cost = 0.0

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
) -> Completion:
    """Call the LLM and return a normalized Completion.

    Provider defaults are used for max_tokens/temperature — we don't second-guess them.
    ``api_base``/``api_key`` are passed through to litellm for custom endpoints.
    """
    import os
    import litellm

    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
    if api_base:
        kwargs["api_base"] = api_base
    if api_key:
        kwargs["api_key"] = api_key

    # Don't redirect FDs here — _silence_litellm() at import time warmed up
    # the provider cache, so no more "Provider List" banners. Redirecting
    # during the call would starve Textual's render pipeline of stdout and
    # freeze the UI for the duration of the call.
    response = litellm.completion(**kwargs)

    if DEBUG:
        import sys
        print(f"[alf.llm] finish_reason={response.choices[0].finish_reason!r}",
              file=sys.stderr)
        print(f"[alf.llm] raw choice={response.choices[0].message}", file=sys.stderr)
    choice = response.choices[0].message
    usage = getattr(response, "usage", None)

    try:
        cost = litellm.completion_cost(completion_response=response) or 0.0
    except Exception:
        cost = 0.0

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
