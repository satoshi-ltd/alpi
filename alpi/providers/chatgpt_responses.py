from __future__ import annotations

import itertools
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterator

import httpx

from alpi.providers import chatgpt
from alpi.providers.chatgpt import PlanError

NAMESPACE = "alpi"
_LIMIT_CODES = frozenset({"subscription_sharing_usage_limit_exceeded"})
_RETRY_CODES = frozenset({
    "subscription_sharing_usage_unavailable", "subscription_sharing_user_unavailable",
    "server_error", "rate_limit_exceeded", "overloaded",
})
_SIGN_IN_CODES = frozenset({"subscription_sharing_invalid_user"})


def _text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(str(p.get("text") or "") for p in content if isinstance(p, dict) and p.get("type") in ("text", "input_text"))
    return "" if content is None else str(content)


def _parts(content: Any) -> Any:
    if not isinstance(content, list):
        return _text(content)
    out: list[dict[str, Any]] = []
    for part in content:
        if not isinstance(part, dict):
            continue
        if part.get("type") == "image_url":
            image = part.get("image_url")
            out.append({"type": "input_image", "image_url": image.get("url") if isinstance(image, dict) else image})
        elif part.get("type") in ("text", "input_text"):
            out.append({"type": "input_text", "text": str(part.get("text") or "")})
    return out


def _input_items(messages: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    # Only the first message is the stable prompt; a later system message (a summary, a note) would rewrite it.
    leading = 1 if messages and messages[0].get("role") == "system" else 0
    instructions = _text(messages[0].get("content")) if leading else ""
    items: list[dict[str, Any]] = []
    for message in messages[leading:]:
        role = message.get("role")
        if role == "system":
            # This route rejects system-role items; a note in the middle of the history is the developer's.
            items.append({"role": "developer", "content": _text(message.get("content"))})
        elif role == "tool":
            items.append({"type": "function_call_output", "call_id": str(message.get("tool_call_id") or ""), "output": _parts(message.get("content"))})
        elif role == "assistant":
            text = _text(message.get("content"))
            if text.strip():
                items.append({"role": "assistant", "content": text})
            for call in message.get("tool_calls") or []:
                function = call.get("function") or {}
                items.append({
                    "type": "function_call", "call_id": str(call.get("id") or ""), "namespace": NAMESPACE,
                    "name": str(function.get("name") or ""), "arguments": str(function.get("arguments") or "{}"),
                })
        else:
            items.append({"role": "user", "content": _parts(message.get("content"))})
    return instructions, items


def request_body(kwargs: dict[str, Any]) -> dict[str, Any]:
    instructions, items = _input_items(list(kwargs.get("messages") or []))
    body: dict[str, Any] = {
        "model": str(kwargs.get("model") or "").split("/", 1)[-1],
        "input": items,
        "store": False,
        "stream": True,
    }
    if instructions:
        body["instructions"] = instructions
    functions = [
        # Left out, strict is on in the Responses API and would turn every optional parameter into a required one.
        {"type": "function", "strict": False, **{k: v for k, v in (tool.get("function") or {}).items() if k in ("name", "description", "parameters")}}
        for tool in kwargs.get("tools") or [] if isinstance(tool, dict) and (tool.get("function") or {}).get("name")
    ]
    if functions:
        # The plan route takes function tools grouped in a namespace, not at the top level.
        body["tools"] = [{"type": "namespace", "name": NAMESPACE, "description": "The tools alpi gives this agent.", "tools": functions}]
        for key in ("tool_choice", "parallel_tool_calls"):
            if kwargs.get(key) is not None:
                body[key] = kwargs[key]
    from alpi.providers.reasoning import supports_reasoning

    if supports_reasoning(str(kwargs.get("model") or "")):
        # The summary is what shows the model thinking and tells the watchdog it is alive.
        body["reasoning"] = {"summary": "auto"}
        if kwargs.get("reasoning_effort"):
            body["reasoning"]["effort"] = kwargs["reasoning_effort"]
    return body


def _api_error(status: int, raw: bytes, request_id: str = "") -> PlanError:
    try:
        body = json.loads(raw or b"{}")
    except ValueError:
        body = {}
    error = body.get("error") if isinstance(body, dict) and isinstance(body.get("error"), dict) else {}
    code = str(error.get("code") or "")
    detail = str(error.get("message") or (body.get("detail") if isinstance(body, dict) else "") or raw[:300].decode("utf-8", "replace"))
    if error.get("param"):
        detail = f"{detail} (param: {error['param']})"
    return _plan_error(code, detail, status, request_id)


def _plan_error(code: str, detail: str, status: int | None, request_id: str = "") -> PlanError:
    if request_id:
        detail = f"{detail} [request {request_id}]"
    if code in _LIMIT_CODES:
        message = f"ChatGPT plan usage limit reached ({detail}). Review the plan's and this app's limit at {chatgpt.USAGE_URL}"
    elif code in _SIGN_IN_CODES or status == 401:
        message = f"ChatGPT did not accept this sign-in ({code or status}: {detail}). Run `alpi chatgpt login` again."
    else:
        message = f"ChatGPT plan request failed: {code or status or 'error'} {detail}".strip()
    retryable = code in _RETRY_CODES or (status is not None and status >= 500 and not code.startswith("subscription_sharing_"))
    return PlanError(message, code=code, status_code=status, retryable=retryable)


def _events(response: httpx.Response) -> Iterator[dict[str, Any]]:
    data: list[str] = []
    # The trailing "" flushes an event the server did not close with a blank line; chained, never unpacked, or the body is read whole first.
    for line in itertools.chain(response.iter_lines(), ("",)):
        if line.startswith("data:"):
            data.append(line[5:].lstrip())
        elif not line and data:
            payload = "\n".join(data)
            data = []
            if payload != "[DONE]":
                try:
                    event = json.loads(payload)
                except ValueError:
                    continue
                if isinstance(event, dict):
                    yield event


def _chunk(*, content: str = "", reasoning: str = "", tool_call: Any = None, finish: str | None = None, usage: Any = None, response_id: str = "") -> SimpleNamespace:
    delta = SimpleNamespace(content=content, reasoning_content=reasoning, tool_calls=[tool_call] if tool_call else None)
    return SimpleNamespace(id=response_id, provider="chatgpt-plan", usage=usage, choices=[SimpleNamespace(delta=delta, finish_reason=finish)])


def _usage(response: dict[str, Any]) -> SimpleNamespace:
    usage = response.get("usage") or {}
    cached = (usage.get("input_tokens_details") or {}).get("cached_tokens")
    return SimpleNamespace(
        prompt_tokens=int(usage.get("input_tokens") or 0), completion_tokens=int(usage.get("output_tokens") or 0),
        prompt_tokens_details=SimpleNamespace(cached_tokens=cached),
    )


def _finish(kind: str, response: dict[str, Any], called: bool) -> str:
    if kind == "response.completed":
        return "tool_calls" if called else "stop"
    reason = str((response.get("incomplete_details") or {}).get("reason") or "")
    return "length" if reason in ("max_output_tokens", "") else reason


def _converted(response: httpx.Response) -> Iterator[SimpleNamespace]:
    slots: dict[Any, int] = {}
    streamed: set[tuple[str, Any]] = set()
    completed = False
    for event in _events(response):
        kind = event.get("type")
        item = event.get("item") if isinstance(event.get("item"), dict) else {}
        index = event.get("output_index")
        if index is None:
            index = item.get("id") or item.get("call_id") or event.get("item_id") or 0
        part = (index, event.get("content_index") or 0)
        if kind in ("response.output_text.delta", "response.refusal.delta"):
            streamed.add(("text", part))
            yield _chunk(content=str(event.get("delta") or ""))
        elif kind in ("response.output_text.done", "response.refusal.done") and ("text", part) not in streamed:
            yield _chunk(content=str(event.get("text") or event.get("refusal") or ""))
        elif kind in ("response.reasoning_summary_text.delta", "response.reasoning_text.delta"):
            yield _chunk(reasoning=str(event.get("delta") or ""))
        elif kind in ("response.output_item.added", "response.output_item.done") and item.get("type") == "function_call":
            first = index not in slots
            if first:
                slots[index] = len(slots)
            arguments = str(item.get("arguments") or "")
            if first or (arguments and ("arguments", index) not in streamed):
                if arguments:
                    streamed.add(("arguments", index))
                yield _chunk(tool_call=SimpleNamespace(
                    index=slots[index], id=str(item.get("call_id") or "") if first else None,
                    function=SimpleNamespace(name=str(item.get("name") or "") if first else None, arguments=arguments),
                ))
        elif kind == "response.function_call_arguments.delta" and index in slots:
            streamed.add(("arguments", index))
            yield _chunk(tool_call=SimpleNamespace(index=slots[index], id=None, function=SimpleNamespace(name=None, arguments=str(event.get("delta") or ""))))
        elif kind == "response.function_call_arguments.done" and index in slots and ("arguments", index) not in streamed:
            streamed.add(("arguments", index))
            yield _chunk(tool_call=SimpleNamespace(index=slots[index], id=None, function=SimpleNamespace(name=None, arguments=str(event.get("arguments") or ""))))
        elif kind in ("response.completed", "response.incomplete"):
            done = event.get("response") or {}
            completed = True
            yield _chunk(finish=_finish(kind, done, bool(slots)), usage=_usage(done), response_id=str(done.get("id") or ""))
        elif kind == "response.failed":
            error = (event.get("response") or {}).get("error") or {}
            raise _plan_error(str(error.get("code") or ""), str(error.get("message") or "the response failed"), None)
        elif kind == "error":
            raise _plan_error(str(event.get("code") or ""), str(event.get("message") or "the stream reported an error"), None)
    if not completed:
        raise PlanError("the ChatGPT plan stream ended before the response completed", code="stream_interrupted", retryable=True)


def stream(kwargs: dict[str, Any]) -> Iterator[SimpleNamespace]:
    if not kwargs.get("chatgpt_home"):
        raise chatgpt.NotSignedIn()
    home = Path(str(kwargs["chatgpt_home"]))
    timeout = kwargs.get("timeout")
    body = request_body(kwargs)
    token = chatgpt.access_token(home)
    try:
        with httpx.Client(timeout=httpx.Timeout(float(timeout) if timeout else 300.0, connect=30.0)) as client:
            for renewed in (False, True, True):
                with client.stream(
                    "POST", chatgpt.RESPONSES_URL, json=body,
                    headers={"Authorization": f"Bearer {token}", "Accept": "text/event-stream"},
                ) as response:
                    if response.status_code == 401 and not renewed:
                        # The token can be refused before its nominal expiry (a clock that moved, a record renewed elsewhere).
                        response.read()
                        token = chatgpt.access_token(home, refused=token)
                        continue
                    if response.status_code != 200:
                        failure = _api_error(response.status_code, response.read(), response.headers.get("x-request-id", ""))
                        if response.status_code == 400 and "reasoning" in body and "param: reasoning" in str(failure):
                            # A model the plan lists without reasoning refuses the block alpi adds unasked; the turn matters more than the summary.
                            body = {k: v for k, v in body.items() if k != "reasoning"}
                            continue
                        raise failure
                    yield from _converted(response)
                    return
    except httpx.HTTPError as exc:
        raise chatgpt.unreachable(exc, "for this request") from exc


def complete(kwargs: dict[str, Any]) -> dict[str, Any]:
    text: list[str] = []
    calls: dict[int, dict[str, str]] = {}
    usage = SimpleNamespace(prompt_tokens=0, completion_tokens=0, prompt_tokens_details=SimpleNamespace(cached_tokens=None))
    finish, response_id = None, ""
    for chunk in stream(kwargs):
        choice = chunk.choices[0]
        text.append(choice.delta.content or "")
        for call in choice.delta.tool_calls or []:
            entry = calls.setdefault(call.index, {"id": "", "name": "", "arguments": ""})
            entry["id"] = call.id or entry["id"]
            entry["name"] += call.function.name or ""
            entry["arguments"] += call.function.arguments or ""
        if choice.finish_reason:
            finish, usage, response_id = choice.finish_reason, chunk.usage, chunk.id
    return {"content": "".join(text), "tool_calls": [calls[i] for i in sorted(calls)], "usage": usage, "finish_reason": finish, "id": response_id}
